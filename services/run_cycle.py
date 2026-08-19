"""The unattended serving cycle: sync fixtures, price them, grade results.

    python -m services.run_cycle
    python -m services.run_cycle --dry-run
    python -m services.run_cycle --refreeze

One entry point, so that *scheduling lives outside the application*. Windows
Task Scheduler, cron or a systemd timer calls this and reads the exit code.
Nothing here daemonises and nothing here retries -- a scheduler already knows
how to run something again tomorrow, and a process that supervises itself is a
process with two ways to be wrong.

**The failure this exists to prevent is silence.** A cycle that raises is easy:
it is loud, it has a traceback, someone fixes it. A cycle that returns success
having done nothing is what actually costs a weekend of predictions, and
opening-weekend prediction data cannot be recovered afterwards. So doing
nothing is detected and reported separately from succeeding:

    exit 0    clean
    exit 2    ran, but a human should look
    exit 1    a step failed

`exit 2` is the interesting one. It fires on an empty feed, on club names the
alias table does not know, on fixtures the artifact cannot price, and on an
artifact too old to be serving -- none of which raise, and all of which mean
the next matchday goes unpriced unless someone intervenes.

**Steps are deliberately independent.** A dead fixtures feed must not stop
results being graded; a serving failure must not stop tomorrow's run seeing the
fixtures. Each step records its own outcome and the cycle reports the worst.

**The book is not here.** It is measured-negative (`CALIBRATION.md`) and off at
launch, so it is absent rather than present behind a flag: a scheduled job
should not be one typo away from placing bets.
"""

from __future__ import annotations

import argparse
import sqlite3
import traceback
from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path

import pandas as pd

from engine import config, db
from engine.serve import cycle, tips
from services import bbc_calendar, bbc_results, csv_grader, fixture_sync

#: Refit once the frozen artifact is older than this. P1's H1 measured
#: day-frozen refits worth 0.00007 nats over weekly, so weekly is what the base
#: score was established on and weekly is what gets served. Checked rather than
#: scheduled separately, so a missed run cannot leave a stale head serving.
REFIT_AFTER_DAYS = 7

#: Recorded in `serving_state.rule_version` so the row states plainly that no
#: betting rule ran, rather than naming one that was never invoked. The tip rule
#: is not a betting rule and does not change this: nothing is staked.
RULE_VERSION = "book-off"

#: The tip rule's two settings. Measured in `engine/eval/selection.py`: floor
#: 0.55 publishes a 72.5% strike rate on **100% of matches**, against the v1
#: outright-only rule's 65.5% on 14.4%. Changing either means bumping
#: `tips.RULE_VERSION`, or the published history mixes two products under one
#: strike rate.
TIP_FLOOR = tips.DEFAULT_FLOOR
TIP_CEILING = tips.DEFAULT_CEILING

#: How many date pages the second calendar pulls when it is enabled. Seven
#: matches the artifact's refit cadence, so no fixture is ever priced by a head
#: more than one refit old -- the same horizon football-data's feed gives when
#: it is working, which is what keeps this a fallback rather than a new product.
CALENDAR_DAYS = 7

#: How long after a match `step_grade` keeps pulling football-data's file for
#: tips already settled from the BBC page, so `csv_grader.reconcile_tips` gets
#: to compare the two sources. Two weeks comfortably outlasts the file's
#: publication lag; the cost is one small CSV per served division per cycle.
RECONCILE_DAYS = 14


class Status(IntEnum):
    """Severity, ordered. The exit code is deliberately not the same number."""

    OK = 0
    ATTENTION = 1
    FAILED = 2

    @property
    def exit_code(self) -> int:
        return {Status.OK: 0, Status.ATTENTION: 2, Status.FAILED: 1}[self]

    @property
    def mark(self) -> str:
        return {Status.OK: "ok", Status.ATTENTION: "!!", Status.FAILED: "XX"}[self]


@dataclass
class Step:
    name: str
    status: Status = Status.OK
    detail: str = ""
    trace: str | None = None

    def flag(self, status: Status, note: str) -> None:
        """Raise the severity and append a note. Never lowers an earlier one."""
        self.status = max(self.status, status)
        self.detail = f"{self.detail}; {note}" if self.detail else note

    def line(self) -> str:
        return f"[{self.status.mark}] {self.name:9s} {self.detail}"


@dataclass
class CycleReport:
    label: str
    steps: list[Step] = field(default_factory=list)
    model_version: str = "none"
    artifact_path: str | None = None
    fixtures_seen: int = 0
    predictions_written: int = 0

    @property
    def status(self) -> Status:
        return max((s.status for s in self.steps), default=Status.OK)

    def describe(self) -> str:
        head = f"cycle {self.label}  model={self.model_version}  -> {self.status.name}"
        return "\n".join([head, *(s.line() for s in self.steps)])

    def notes(self) -> str:
        return " | ".join(f"{s.name}={s.status.name}:{s.detail}" for s in self.steps)


def _guard(step: Step, work) -> Step:
    """Run `work(step)`, converting any exception into a FAILED step.

    An unattended cycle must not lose the steps that already succeeded because
    a later one raised, and it must not lose the traceback either.
    """
    try:
        work(step)
    except Exception as exc:  # noqa: BLE001 -- deliberately broad; this is the boundary
        step.status = Status.FAILED
        step.detail = f"{type(exc).__name__}: {exc}"
        step.trace = traceback.format_exc()
    return step


# --- the steps -------------------------------------------------------------


def step_sync(conn: sqlite3.Connection, *, dry_run: bool, url: str,
              file: Path | None = None) -> Step:
    """Pull the rolling fixtures feed and upsert what it carries."""

    def work(step: Step) -> None:
        if file is not None:
            text, source = file.read_text(encoding="utf-8-sig"), str(file)
        else:
            text, source = fixture_sync.fetch(url), url
        report = fixture_sync.sync(conn, text, source, dry_run=dry_run)
        step.detail = (f"{report.fetched} row(s), {report.english} English; "
                       f"{report.inserted} new, {report.updated} updated")
        if report.english == 0:
            # The feed is a rolling ~7-day window and carries English rows only
            # in season. Out of season this is expected; a week before kickoff
            # it is the single thing standing between us and a launch.
            step.flag(Status.ATTENTION, "NO ENGLISH ROWS in the feed")
        if not report.report.clean:
            step.flag(Status.ATTENTION,
                      "unbridged club name(s); re-run scripts/build_team_aliases.py")

    return _guard(Step("sync"), work)


def step_calendar(conn: sqlite3.Connection, *, dry_run: bool,
                  days: int = CALENDAR_DAYS) -> Step:
    """Fill fixture gaps from the second calendar. Additive, never destructive.

    Runs **after** `sync` so football-data keeps first claim on every row it
    publishes: this step inserts only fixtures that feed does not have, and
    never updates one, because it carries no odds and an update would write
    NULL over prices (`services/bbc_calendar.py`).

    Enabled only by `BVP_BBC_CALENDAR=1`. A missing English fixture list is the
    failure this exists for, so an empty result is reported rather than passed
    over -- but the step failing must not stop serving, which is why it is a
    step of its own like every other.
    """

    def work(step: Step) -> None:
        report = bbc_calendar.sync(
            conn, bbc_calendar.collect(days), dry_run=dry_run)
        step.detail = (f"{report.pages} page(s), {report.english} English; "
                       f"{report.inserted} new, "
                       f"{report.already_known} already known")
        if not report.report.clean:
            step.flag(Status.ATTENTION,
                      "unbridged club(s); add to reference/bbc_teams.csv")

    if not config.BBC_CALENDAR_ENABLED:
        return Step("calendar", detail="disabled (BVP_BBC_CALENDAR unset)")
    return _guard(Step("calendar"), work)


def step_serve(conn: sqlite3.Connection, report: CycleReport, *,
               dry_run: bool, refreeze: bool, today: pd.Timestamp) -> Step:
    """Freeze if stale, then price every pending fixture the artifact knows."""

    def work(step: Step) -> None:
        artifact = None if refreeze else cycle.latest_artifact()
        path = None
        reason = "reused"
        if artifact is not None and _stale(artifact, today):
            age = (today - pd.Timestamp(artifact.fitted_at[:10])).days
            artifact, reason = None, f"refroze (was {age}d old)"
        if artifact is None:
            artifact, path = cycle.build_artifact(conn)
            reason = reason if reason.startswith("refroze") else "froze"
        report.model_version = artifact.version
        report.artifact_path = str(path) if path else None
        if not dry_run:
            cycle.register(conn, artifact, path)

        pending = cycle.pending_fixtures(conn, artifact.version)
        report.fixtures_seen = len(pending)
        _, unknown = cycle.servable(pending, artifact)

        served = cycle.serve(conn, artifact, dry_run=dry_run)
        report.predictions_written = len(served)
        step.detail = (f"{reason} {artifact.version}; {len(pending)} pending, "
                       f"{len(served)} priced")
        if not unknown.empty:
            names = ", ".join(cycle.unknown_clubs(unknown, artifact))
            step.flag(Status.ATTENTION,
                      f"{len(unknown)} fixture(s) unpriced, artifact never saw: {names}")

    return _guard(Step("serve"), work)


def step_grade(conn: sqlite3.Connection, *, dry_run: bool,
               today: pd.Timestamp | None = None) -> Step:
    """Settle played fixtures, write CLV, and settle published tips.

    `today` is the cycle's clock, the same one `step_serve` and `step_results`
    are given. It used to bound on SQL `date('now')` instead, so a cycle run
    with an explicit `today` was only partly deterministic (`OUTSTANDING.md`
    §6); the second results step made two adjacent steps on two clocks
    untenable. Identical in production, where the machine is UTC.

    The pending query spans `paper_bets` **and** `tips`. It used to read
    `paper_bets` alone, which was right while that was the only thing needing
    settlement and became a silent no-op the moment tips shipped: the book is
    off, so there are never unsettled bets, so the step returned early and no
    tip would ever have been graded. The product's own strike rate would have
    stayed empty forever while the cycle reported success.

    **A season boundary is not a failure.** For the first week or so of a
    season a division can have played fixtures pending settlement while
    football-data has not published that division's file yet. That is
    ATTENTION, not FAILED -- the tips really are going ungraded, so it is not
    passed over, but it is nobody's bug and must not take a matchday's cycle
    down with an exit 1. `csv_grader.ResultsNotPublished` is the whole of that
    condition, including the redirect shape that returns a 200.
    """

    day = str(pd.Timestamp(today or pd.Timestamp.now().normalize()).date())

    def work(step: Step) -> None:
        # **Played fixtures only.** The v1 tip rule covered 14.4% of matches so
        # unsettled rows were rare; v2 covers 100%, which means every future
        # fixture carries an unsettled tip from the moment it is priced. Without
        # the date bound the cycle would pull a results CSV for every division
        # with an upcoming match, every run, all season -- fetching files that
        # cannot contain the result yet.
        pending = conn.execute(
            "SELECT DISTINCT f.division, f.match_date FROM paper_bets b"
            " JOIN fixtures f ON f.fixture_id = b.fixture_id"
            " WHERE b.settled_at IS NULL AND f.match_date <= ?"
            " UNION"
            " SELECT DISTINCT f.division, f.match_date FROM tips t"
            " JOIN fixtures f ON f.fixture_id = t.fixture_id"
            " WHERE t.settled_at IS NULL AND f.match_date <= ?", (day, day),
        ).fetchall()
        # **Recently settled tips pull the file too, to be reconciled.** With
        # `step_results` on, every played tip is settled from the BBC page
        # before this step runs, so "unsettled" alone would never fetch
        # football-data again and `reconcile_tips` would never see a match.
        # A file that is not published yet is only ATTENTION when something
        # genuinely unsettled is waiting on it.
        recent = conn.execute(
            "SELECT DISTINCT f.division, f.match_date FROM tips t"
            " JOIN fixtures f ON f.fixture_id = t.fixture_id"
            " WHERE t.settled_at IS NOT NULL AND f.match_date <= ?"
            " AND f.match_date >= date(?, ?)", (day, day, f"-{RECONCILE_DAYS} days"),
        ).fetchall()
        if not pending and not recent:
            step.detail = "nothing unsettled"
            return
        waiting = {(r["division"], csv_grader.season_for(r["match_date"]))
                   for r in pending}
        seasons = waiting | {(r["division"], csv_grader.season_for(r["match_date"]))
                             for r in recent}
        total = csv_grader.GradeReport()
        unpublished, mismatched = [], []
        for division, season in sorted(seasons):
            try:
                text = csv_grader.fetch(division, season)
            except csv_grader.ResultsNotPublished:
                if (division, season) in waiting:
                    unpublished.append(f"{division}/{season}")
                continue
            parsed = csv_grader.parse_results(text)
            rows = [r for r in parsed if r["division"] == division]
            if parsed and not rows:
                # A file we asked for, fetched and parsed, that yields nothing
                # to grade. The BOM defect looked exactly like this for two
                # seasons and would have read as a quiet success.
                mismatched.append(f"{division}/{season}")
            got = csv_grader.grade(conn, rows, dry_run=dry_run)
            total.results_seen += got.results_seen
            total.settled += got.settled
            total.graded += got.graded
            total.tips_settled += got.tips_settled
            total.disagreed += got.disagreed
        # Set before flagging: `flag` appends to `detail`, so an assignment
        # after it would wipe the notes.
        step.detail = (f"{total.results_seen} result(s), {total.settled} settled, "
                       f"{total.graded} CLV grade(s), "
                       f"{total.tips_settled} tip(s) settled")
        if unpublished:
            step.flag(Status.ATTENTION,
                      f"no results file published yet for {', '.join(unpublished)}; "
                      "those tips stay unsettled")
        if mismatched:
            step.flag(Status.ATTENTION,
                      f"{', '.join(mismatched)} parsed but carried no row of that "
                      "division -- check the feed's Div column")
        if total.disagreed:
            step.flag(Status.ATTENTION,
                      f"football-data contradicts the settled outcome of tip(s) "
                      f"{total.disagreed} -- settled from the BBC page; check both")

    return _guard(Step("grade"), work)


def step_results(conn: sqlite3.Connection, *, dry_run: bool,
                 today: pd.Timestamp | None = None) -> Step:
    """Settle tips from BBC full-time scores, ahead of football-data's file.

    Runs **before** `grade`, so a Saturday result settles at the Sunday cycle
    rather than whenever football-data publishes the season's CSV -- which for
    the opening weeks is not at all. It reads only tips, only through
    `csv_grader.settle_tips`, and only at full time; `grade` then runs as before
    and, once the file exists, `csv_grader.reconcile_tips` reports any tip the
    two sources disagree on.

    Enabled only by `BVP_BBC_RESULTS=1` -- the same recorded decision and exit
    condition as the calendar (`OUTSTANDING.md` §4.5). A page for a *past* date
    that shows English fixtures but no full-time result is ATTENTION: the
    source did not deliver what it exists to deliver. Today's page is exempt --
    at 06:00 UTC nothing on it has kicked off.
    """
    day = str(pd.Timestamp(today or pd.Timestamp.now().normalize()).date())

    def work(step: Step) -> None:
        dates = bbc_results.pending_dates(conn, day)
        if not dates:
            step.detail = "nothing unsettled"
            return
        report = bbc_results.settle(conn, bbc_results.collect(dates), dry_run=dry_run)
        step.detail = (f"{report.pages} page(s), {report.full_time} full-time; "
                       f"{report.matched} matched, {report.tips_settled} tip(s) settled")
        stale = [d for d in report.empty_pages if d < day]
        if stale:
            step.flag(Status.ATTENTION,
                      f"no English full-time result on {', '.join(stale)}; "
                      "those tips stay unsettled")
        if not report.report.clean:
            step.flag(Status.ATTENTION,
                      "unbridged club(s); add to reference/bbc_teams.csv")

    if not config.BBC_RESULTS_ENABLED:
        return Step("results", detail="disabled (BVP_BBC_RESULTS unset)")
    return _guard(Step("results"), work)


def step_tips(conn: sqlite3.Connection, *, dry_run: bool) -> Step:
    """Publish the confidence-rule tip list for fixtures priced this cycle.

    Runs after `serve` and before `grade`, and is independent of both: a tip
    list that cannot be built must not stop results being settled, and a dead
    fixtures feed must not stop yesterday's tips being graded.

    **Unlike the book, this is present rather than absent.** `run_cycle`'s
    docstring explains why the paper book is not wired in -- it is measured
    negative and a scheduled job should not be one typo from placing bets.
    Tips place no bets and stake nothing, so the same argument does not apply.
    What it publishes is a confidence ranking whose strike rate is measured and
    honest (`engine/eval/tips.py`); what it must never be presented as is a
    return, which the same module measures and does not support.
    """

    def work(step: Step) -> None:
        pending = tips.untipped(conn)
        if pending.empty:
            # Not "nothing to do": with a forward calendar there are usually
            # plenty of untipped predictions, just none for a match played
            # today. Saying which is the difference between a quiet day and a
            # broken rule (`tips.PUBLISH_WITHIN_DAYS`).
            step.detail = (f"nothing untipped within "
                           f"{tips.PUBLISH_WITHIN_DAYS} day(s) of kickoff")
            return
        selected = tips.select(pending, floor=TIP_FLOOR, ceiling=TIP_CEILING)
        written = tips.publish(conn, selected, dry_run=dry_run)
        mix = selected.side.value_counts().to_dict() if not selected.empty else {}
        step.detail = (f"{len(pending)} untipped, {written} published "
                       f"(floor {TIP_FLOOR}); "
                       + ", ".join(f"{k} {v}" for k, v in sorted(mix.items())))
        # Handicap sides are excluded: they have no price and no derivable one
        # (`tips.UNPRICEABLE_SIDES`), so counting them would flag two thirds
        # of every matchday and bury a real gap on the priced legs.
        priceable = selected[~selected.side.isin(tips.UNPRICEABLE_SIDES)]
        missing = int(priceable["best_price"].isna().sum()) if not priceable.empty else 0
        if missing:
            # The tips still stand -- selection never reads a price -- but the
            # product cannot compute its own return without one, and a silent
            # gap in the P&L column is exactly the number nobody notices is
            # missing until it is quoted.
            step.flag(Status.ATTENTION,
                      f"{missing} tip(s) published with no price; return "
                      f"cannot be graded for them")
        # The honesty reference for the unpriced handicap sides: the model's
        # claim against the market-implied probability derived from the
        # fixture's own 1X2 prices (a reference, never a price). Out-of-band
        # means the model has drifted from the market on its modal call, which
        # a price would otherwise have been the first to say.
        n_ref, gap = tips.referee_gap(selected, pending)
        if gap is not None:
            step.detail += (f"; referee gap {100*gap:+.2f} pts on {n_ref} "
                            f"handicap tip(s) (derived from 1X2 prices)")
            lo, hi = tips.REFEREE_BAND
            if not lo <= gap <= hi:
                step.flag(Status.ATTENTION,
                          f"model vs market-implied gap {100*gap:+.2f} pts is "
                          f"outside [{100*lo:+.2f}, {100*hi:+.2f}] "
                          f"(V3_ADOPTION_PLAN.md D4)")

    return _guard(Step("tips"), work)


def _stale(artifact, today: pd.Timestamp) -> bool:
    return (today - pd.Timestamp(artifact.fitted_at[:10])).days > REFIT_AFTER_DAYS


# --- the cycle -------------------------------------------------------------


def run(conn: sqlite3.Connection, *, dry_run: bool = False, refreeze: bool = False,
        url: str = fixture_sync.FIXTURES_URL, file: Path | None = None,
        today: pd.Timestamp | None = None) -> CycleReport:
    today = pd.Timestamp(today or pd.Timestamp.now().normalize())
    report = CycleReport(label=str(today.date()))

    report.steps.append(step_sync(conn, dry_run=dry_run, url=url, file=file))
    report.steps.append(step_calendar(conn, dry_run=dry_run))
    report.steps.append(step_serve(conn, report, dry_run=dry_run,
                                   refreeze=refreeze, today=today))
    report.steps.append(step_tips(conn, dry_run=dry_run))
    report.steps.append(step_results(conn, dry_run=dry_run, today=today))
    report.steps.append(step_grade(conn, dry_run=dry_run, today=today))

    if not dry_run:
        # Written even when a step failed: an unattended run that left no trace
        # is indistinguishable from one that never started.
        cycle.snapshot(
            conn, cycle_label=report.label, version=report.model_version,
            artifact_path=report.artifact_path, fixtures_seen=report.fixtures_seen,
            predictions_written=report.predictions_written, bets_written=0,
            rule_version=RULE_VERSION, notes=report.notes()[:2000],
        )
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="write nothing")
    parser.add_argument("--refreeze", action="store_true", help="refit before serving")
    parser.add_argument("--url", default=fixture_sync.FIXTURES_URL)
    parser.add_argument("--file", type=Path, help="replay a saved feed snapshot")
    args = parser.parse_args(argv)

    conn = db.connect()
    db.migrate(conn)
    report = run(conn, dry_run=args.dry_run, refreeze=args.refreeze,
                 url=args.url, file=args.file)

    print(report.describe())
    for step in report.steps:
        if step.trace:
            print(f"\n--- {step.name} traceback ---\n{step.trace}", end="")
    if args.dry_run:
        print("(dry run -- nothing written)")
    return report.status.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
