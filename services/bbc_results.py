"""Results from the BBC scores-fixtures pages: settle published tips at full time.

    python -m services.bbc_results                       # dates with unsettled played tips
    python -m services.bbc_results --dates 2026-08-15 2026-08-16
    python -m services.bbc_results --file page.html
    python -m services.bbc_results --dry-run

**Same source, same terms, same exit condition as the calendar.** The decision
to read bbc.com at all is `OUTSTANDING.md` §4.5: a pre-release validation aid,
retired at a commercial feed or public launch, whichever comes first. The
calendar runs once a day in the cycle; this module also runs on its own every
two hours (`deploy/systemd/bvp-results.timer`, owner decision 2026-08-21) and
only fetches a page when a played tip is still unsettled. It reads the *same*
pages the calendar reads -- a played match
sits on the page for its date with `status: PostEvent`, `statusComment: FT` and
each side's `runningScores.fulltime` -- so it inherits that decision whole. It
is off unless `BVP_BBC_RESULTS=1`.

**Why it exists.** The only other results source is football-data's per-season
CSV (`services/csv_grader.py`), which is published on their schedule and does
not exist at all until they create the season's file. Every tip on the opening
weekends sits ungraded until it does, and the site shows nothing.

**What it does, and does not, do.** It settles tips -- `outcome` and both
P&L columns -- through `csv_grader.settle_tips`, the same function and the same
`selection._won` the strike rate was measured with. It settles **only** at
full time: an in-play, postponed or abandoned event never settles anything. It
does not grade CLV, which needs closing odds this page does not carry, and it
does not touch `fixtures` -- a result for a match this store has no fixture for
is counted and dropped, because there can be no tip on it. Settlement is
idempotent by construction (`settle_tips` reads `settled_at IS NULL`), so when
football-data's file arrives it settles nothing twice; `csv_grader.reconcile_tips`
then checks that the two sources agree, and a disagreement is ATTENTION.

Dates are UK-local (`date.isoDate`), the calendar's convention, so
`(division, match_date, home, away)` finds the fixture row either feed wrote.
"""

from __future__ import annotations

import argparse
import time
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from engine import db
from engine.ingest.teams import BridgeReport, TeamBridge
from engine.seasons import SERVED_DIVISIONS
from services import csv_grader
from services.bbc_calendar import (DIVISION_BY_TOURNAMENT, REQUEST_INTERVAL, _events,
                                   _resolve_pair, extract, fetch)

#: How far back a cycle looks for played, unsettled tips. Older than this and
#: football-data will have the file; and it bounds the request count on a
#: machine that has been off for a while.
LOOKBACK_DAYS = 7


@dataclass
class ResultsReport:
    pages: int = 0
    events: int = 0
    english: int = 0        # events in E0-E3, any status
    full_time: int = 0      # of those, PostEvent + FT with a score
    matched: int = 0        # full-time results with a fixture row here
    tips_settled: int = 0
    empty_pages: list = field(default_factory=list)   # dates with no English FT
    report: BridgeReport = field(default_factory=BridgeReport)

    def describe(self) -> str:
        lines = [f"{self.pages} page(s), {self.english} English event(s), "
                 f"{self.full_time} at full time; {self.matched} matched a fixture, "
                 f"{self.tips_settled} tip(s) settled"]
        if self.empty_pages:
            lines.append(f"  no English full-time result on: {', '.join(self.empty_pages)}")
        lines.append(self.report.describe())
        return "\n".join(lines)


def _score(side: dict) -> int | None:
    value = (side.get("runningScores") or {}).get("fulltime")
    if value is None:
        value = side.get("score")
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_results(html: str) -> tuple[list[dict], dict]:
    """Full-time results in the served divisions on one date page.

    Returns (results, counts) where counts has `events` and `english`. Only
    `PostEvent` + `FT` with both scores present reaches `results`: a match in
    play, postponed or abandoned must never settle a tip.
    """
    payload = extract(html)
    counts = {"events": 0, "english": 0}
    results = []
    for event in _events(payload):
        counts["events"] += 1
        division = DIVISION_BY_TOURNAMENT.get(
            (event.get("tournament") or {}).get("urn"))
        if division is None or division not in SERVED_DIVISIONS:
            continue
        counts["english"] += 1
        if event.get("status") != "PostEvent":
            continue
        if (event.get("statusComment") or {}).get("value") != "FT":
            continue
        home, away = event.get("home") or {}, event.get("away") or {}
        fthg, ftag = _score(home), _score(away)
        if fthg is None or ftag is None:
            continue
        results.append({
            "division": division,
            "match_date": event["date"]["isoDate"],
            "home_urn": home.get("urn"),
            "away_urn": away.get("urn"),
            "home_name": home.get("fullName", "?"),
            "away_name": away.get("fullName", "?"),
            "fthg": fthg,
            "ftag": ftag,
            "ftr": "H" if fthg > ftag else ("A" if ftag > fthg else "D"),
        })
    return results, counts


def settle(conn: db.Connection, pages: list[tuple[str, str]], *,
           dry_run: bool = False) -> ResultsReport:
    """Settle unsettled tips on every full-time result in `pages`.

    `pages` is a list of (date_label, html). Touches `tips` only, through
    `csv_grader.settle_tips`, and never `fixtures`.
    """
    bridge = TeamBridge.load()
    ids = {row["canonical_name"]: row["team_id"]
           for row in conn.execute("SELECT team_id, canonical_name FROM teams")}
    out = ResultsReport()

    for label, html in pages:
        results, counts = parse_results(html)
        out.pages += 1
        out.events += counts["events"]
        out.english += counts["english"]
        out.full_time += len(results)
        if counts["english"] and not results:
            out.empty_pages.append(label)
        for row in results:
            resolved = _resolve_pair(row, bridge, ids, out.report)
            if resolved is None:
                continue
            fixture = conn.execute(
                "SELECT fixture_id FROM fixtures WHERE division=%s AND match_date=%s"
                " AND home_team_id=%s AND away_team_id=%s",
                (row["division"], row["match_date"], *resolved),
            ).fetchone()
            if fixture is None:
                continue
            out.matched += 1
            out.tips_settled += csv_grader.settle_tips(
                conn, fixture["fixture_id"], row, dry_run=dry_run)
    if not dry_run:
        conn.commit()
    return out


def pending_dates(conn: db.Connection, today: str, *,
                  lookback: int = LOOKBACK_DAYS) -> list[str]:
    """Dates on or before `today` with a played-or-playing, unsettled tip."""
    first = str((pd.Timestamp(today) - pd.Timedelta(days=lookback)).date())
    rows = conn.execute(
        "SELECT DISTINCT f.match_date FROM tips t"
        " JOIN fixtures f ON f.fixture_id = t.fixture_id"
        " WHERE t.settled_at IS NULL AND f.match_date <= %s AND f.match_date >= %s"
        " ORDER BY f.match_date", (today, first),
    ).fetchall()
    return [r["match_date"] for r in rows]


def collect(dates: list[str], *, interval: float = REQUEST_INTERVAL) -> list[tuple[str, str]]:
    """Fetch one page per date, throttled like the calendar."""
    pages = []
    for i, date in enumerate(dates):
        pages.append((date, fetch(date)))
        if i < len(dates) - 1:
            time.sleep(interval)
    return pages


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dates", nargs="+", help="date pages to read (default: pending)")
    parser.add_argument("--file", type=Path, help="parse a saved page instead of fetching")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    conn = db.connect()
    db.migrate(conn)
    if args.file:
        pages = [(str(args.file), args.file.read_text(encoding="utf-8", errors="replace"))]
    else:
        dates = args.dates or pending_dates(conn, str(pd.Timestamp.now().date()))
        if not dates:
            print("nothing unsettled")
            return 0
        pages = collect(dates)
    report = settle(conn, pages, dry_run=args.dry_run)
    print(report.describe())
    if args.dry_run:
        print("(dry run -- nothing written)")
    return 0 if report.report.clean else 1


if __name__ == "__main__":
    raise SystemExit(main())
