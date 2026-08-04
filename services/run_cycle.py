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

from engine import db
from engine.serve import cycle
from services import csv_grader, fixture_sync

#: Refit once the frozen artifact is older than this. P1's H1 measured
#: day-frozen refits worth 0.00007 nats over weekly, so weekly is what the base
#: score was established on and weekly is what gets served. Checked rather than
#: scheduled separately, so a missed run cannot leave a stale head serving.
REFIT_AFTER_DAYS = 7

#: Recorded in `serving_state.rule_version` so the row states plainly that no
#: betting rule ran, rather than naming one that was never invoked.
RULE_VERSION = "book-off"


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


def step_grade(conn: sqlite3.Connection, *, dry_run: bool) -> Step:
    """Settle played fixtures and write CLV. A no-op while the book is off."""

    def work(step: Step) -> None:
        pending = conn.execute(
            "SELECT DISTINCT f.division, f.match_date FROM paper_bets b"
            " JOIN fixtures f ON f.fixture_id = b.fixture_id"
            " WHERE b.settled_at IS NULL"
        ).fetchall()
        if not pending:
            step.detail = "nothing unsettled (expected: the book is off)"
            return
        seasons = {(r["division"], csv_grader.season_for(r["match_date"]))
                   for r in pending}
        total = csv_grader.GradeReport()
        for division, season in sorted(seasons):
            rows = [r for r in csv_grader.parse_results(
                csv_grader.fetch(division, season)) if r["division"] == division]
            got = csv_grader.grade(conn, rows, dry_run=dry_run)
            total.results_seen += got.results_seen
            total.settled += got.settled
            total.graded += got.graded
        step.detail = (f"{total.results_seen} result(s), {total.settled} settled, "
                       f"{total.graded} CLV grade(s)")

    return _guard(Step("grade"), work)


def _stale(artifact, today: pd.Timestamp) -> bool:
    return (today - pd.Timestamp(artifact.fitted_at[:10])).days > REFIT_AFTER_DAYS


# --- the cycle -------------------------------------------------------------


def run(conn: sqlite3.Connection, *, dry_run: bool = False, refreeze: bool = False,
        url: str = fixture_sync.FIXTURES_URL, file: Path | None = None,
        today: pd.Timestamp | None = None) -> CycleReport:
    today = pd.Timestamp(today or pd.Timestamp.now().normalize())
    report = CycleReport(label=str(today.date()))

    report.steps.append(step_sync(conn, dry_run=dry_run, url=url, file=file))
    report.steps.append(step_serve(conn, report, dry_run=dry_run,
                                   refreeze=refreeze, today=today))
    report.steps.append(step_grade(conn, dry_run=dry_run))

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
