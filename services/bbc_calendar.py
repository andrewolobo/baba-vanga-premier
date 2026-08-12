"""Second fixture calendar: the BBC scores-fixtures pages.

    python -m services.bbc_calendar                  # today + 6 days
    python -m services.bbc_calendar --days 3
    python -m services.bbc_calendar --dry-run
    python -m services.bbc_calendar --file page.html --date 2026-08-15

**This is a validation aid, not the production feed, and it is off by default.**
The decision to run it, its scope and the condition that retires it are recorded
in `OUTSTANDING.md` §4.5. It exists because football-data.co.uk's `fixtures.csv`
is a rolling window that has already been observed empty of English rows three
days before an EFL opening weekend, and nothing stood behind it.

**It is additive and never destructive.** football-data.co.uk owns any row it
has published: where a fixture already exists this module counts it and moves
on rather than updating, because it carries no odds and an update would blank
the prices the other feed wrote. New rows are inserted with NULL odds, which is
enough to predict (`RUNBOOK.md` §5.5) and not enough to grade CLV.

Three properties of the page shape the code:

*The payload is server-rendered, not fetched.* `window.__INITIAL_DATA__` holds a
JSON **string** containing JSON -- it is decoded twice. No browser and no
session are needed, which is the whole reason this is viable where the fbref
scraper was not (`FBREF_SCRAPER.md`).

*Clubs carry a stable URN.* `urn:bbc:sportsdata:football:team:bolton-wanderers`
is present on every English side, so the bridge keys on a machine identifier
rather than on a spelling. `reference/bbc_teams.csv` is the reviewed mapping.

*Dates are published twice.* `startDateTime` is UTC; `date.isoDate` and
`time.displayTimeUK` are UK-local. **The UK-local pair is what is stored**,
because football-data writes UK-local dates and the two feeds must agree on
`(division, match_date, home, away)` or the same match lands twice.

**Only future fixtures are ingested.** A past fixture inserted here would be
priced by the next `serve` using today's artifact, which is backfilling a
prediction -- the one thing the record must never contain (`README.md`).
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from engine import db
from engine.ingest.teams import BBC, BridgeReport, TeamBridge
from engine.seasons import SERVED_DIVISIONS

PAGE_URL = "https://www.bbc.com/sport/football/scores-fixtures/{date}"

#: Tournament URN -> our division code. Verified against live pages 2026-08-12.
#: EC is deliberately absent: it is in the corpus but is not a served market
#: (`engine/seasons.py`), and the National League is where clubs from outside
#: the corpus arrive.
DIVISION_BY_TOURNAMENT = {
    "urn:bbc:sportsdata:football:tournament:premier-league": "E0",
    "urn:bbc:sportsdata:football:tournament:championship": "E1",
    "urn:bbc:sportsdata:football:tournament:league-one": "E2",
    "urn:bbc:sportsdata:football:tournament:league-two": "E3",
}

#: Courtesy throttle between date pages. Seven requests a day is not a load, but
#: a loop with no delay is how a polite client becomes an impolite one.
REQUEST_INTERVAL = 3.0

_MARKER = "window.__INITIAL_DATA__="


@dataclass
class CalendarReport:
    pages: int = 0
    events: int = 0
    english: int = 0
    inserted: int = 0
    already_known: int = 0
    past: int = 0
    report: BridgeReport = field(default_factory=BridgeReport)

    def describe(self) -> str:
        lines = [
            f"{self.pages} page(s), {self.events} event(s) "
            f"({self.english} in E0-E3); {self.inserted} new, "
            f"{self.already_known} already known, {self.past} past/in-play skipped",
        ]
        lines.append(self.report.describe())
        return "\n".join(lines)


def fetch(date: str, timeout: int = 30) -> str:
    url = PAGE_URL.format(date=date)
    request = urllib.request.Request(  # noqa: S310
        url, headers={"User-Agent": "Mozilla/5.0 (compatible; bvp-calendar/0.1)"})
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        return response.read().decode("utf-8", errors="replace")


def extract(html: str) -> dict:
    """The scores-fixtures payload from a page's `__INITIAL_DATA__` blob.

    The value is a JS string literal whose contents are JSON, so it decodes
    twice. Scanning for the closing quote rather than regex-matching it is
    deliberate: the payload is ~150 KB of escaped JSON containing every
    character a regex would have to be trusted not to stop at.
    """
    try:
        start = html.index(_MARKER) + len(_MARKER)
    except ValueError:
        raise ValueError("no __INITIAL_DATA__ on this page") from None
    if html[start] != '"':
        raise ValueError("__INITIAL_DATA__ is not a string literal")

    i = start + 1
    while i < len(html):
        if html[i] == "\\":
            i += 2
            continue
        if html[i] == '"':
            break
        i += 1
    else:
        raise ValueError("unterminated __INITIAL_DATA__ literal")

    data = json.loads(json.loads(html[start:i + 1]))
    for key, node in data.get("data", {}).items():
        if key.startswith("sport-data-scores-fixtures"):
            return node["data"]
    raise ValueError("no scores-fixtures block in __INITIAL_DATA__")


def _events(payload: dict):
    for group in payload.get("eventGroups", []):
        for secondary in group.get("secondaryGroups", []):
            yield from secondary.get("events", [])


@dataclass
class PageParse:
    fixtures: list[dict] = field(default_factory=list)
    events: int = 0          # every event on the page, all competitions
    english: int = 0         # events in E0-E3, before the PreEvent filter
    not_pre_event: int = 0   # of those, already played or in play


def parse(html: str) -> PageParse:
    """Served-division fixtures on one date page.

    Only `PreEvent` rows reach `fixtures`. A match already played or in play
    must not, or the next serve prices it with an artifact that has seen the
    result -- see the module docstring.
    """
    payload = extract(html)
    out = PageParse()
    for event in _events(payload):
        out.events += 1
        division = DIVISION_BY_TOURNAMENT.get(
            (event.get("tournament") or {}).get("urn"))
        if division is None or division not in SERVED_DIVISIONS:
            continue
        out.english += 1
        if event.get("status") != "PreEvent":
            out.not_pre_event += 1
            continue
        out.fixtures.append({
            "division": division,
            "match_date": event["date"]["isoDate"],
            "kickoff_time": (event.get("time") or {}).get("displayTimeUK") or None,
            "home_urn": (event.get("home") or {}).get("urn"),
            "away_urn": (event.get("away") or {}).get("urn"),
            "home_name": (event.get("home") or {}).get("fullName", "?"),
            "away_name": (event.get("away") or {}).get("fullName", "?"),
        })
    return out


def _resolve_pair(row, bridge, ids, report) -> tuple[int, int] | None:
    """(home_id, away_id), or None with both failures recorded by name.

    Recorded by *name* though the lookup is by URN: a URN is unreadable in an
    alert, and the operator's next step is to decide whether a real club is
    missing from `reference/bbc_teams.csv` (SPEC §0.2).
    """
    out = []
    for urn, name in ((row["home_urn"], row["home_name"]),
                      (row["away_urn"], row["away_name"])):
        canonical = bridge.try_resolve(BBC, urn) if urn else None
        if canonical is None or canonical not in ids:
            report.record(BBC, name)
            out.append(None)
        else:
            out.append(ids[canonical])
    return None if None in out else (out[0], out[1])


def sync(conn: sqlite3.Connection, pages: list[tuple[str, str]], *,
         today: str | None = None, dry_run: bool = False) -> CalendarReport:
    """Insert fixtures from `pages`, a list of (source_label, html).

    Insert-only by design. Where football-data has already published a fixture
    its row stands untouched, because this feed carries no odds and an update
    would write NULL over prices the other feed put there.
    """
    today = today or str(pd.Timestamp.now().normalize().date())
    bridge = TeamBridge.load()
    ids = {row["canonical_name"]: row["team_id"]
           for row in conn.execute("SELECT team_id, canonical_name FROM teams")}
    out = CalendarReport()

    for source, html in pages:
        page = parse(html)
        out.pages += 1
        out.events += page.events
        out.english += page.english
        out.past += page.not_pre_event
        for row in page.fixtures:
            if row["match_date"] < today:
                out.past += 1
            else:
                _ingest(conn, row, source, bridge, ids, out, dry_run=dry_run)
    if not dry_run:
        conn.commit()
    return out


def _ingest(conn, row, source, bridge, ids, out: CalendarReport, *,
            dry_run: bool) -> None:
    """Insert one future fixture, unless it is unbridged or already present."""
    resolved = _resolve_pair(row, bridge, ids, out.report)
    if resolved is None:
        return
    key = (row["division"], row["match_date"], *resolved)
    existing = conn.execute(
        "SELECT 1 FROM fixtures WHERE division=? AND match_date=?"
        " AND home_team_id=? AND away_team_id=?", key,
    ).fetchone()
    if existing:
        out.already_known += 1
        return
    out.inserted += 1
    if not dry_run:
        conn.execute(
            "INSERT INTO fixtures (division, match_date, home_team_id,"
            " away_team_id, kickoff_time, source_file)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            [*key, row["kickoff_time"], source],
        )


def collect(days: int, start: str | None = None, *,
            interval: float = REQUEST_INTERVAL) -> list[tuple[str, str]]:
    """Fetch `days` consecutive date pages from `start` (default today)."""
    first = pd.Timestamp(start or pd.Timestamp.now().normalize())
    pages = []
    for offset in range(days):
        date = str((first + pd.Timedelta(days=offset)).date())
        pages.append((PAGE_URL.format(date=date), fetch(date)))
        if offset < days - 1:
            time.sleep(interval)
    return pages


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=7,
                        help="forward window, in date pages (default 7)")
    parser.add_argument("--start", help="first date, ISO (default today)")
    parser.add_argument("--file", type=Path, help="parse a saved page instead of fetching")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    if args.file:
        pages = [(str(args.file), args.file.read_text(encoding="utf-8", errors="replace"))]
    else:
        pages = collect(args.days, args.start)

    conn = db.connect()
    db.migrate(conn)
    report = sync(conn, pages, dry_run=args.dry_run)
    print(report.describe())
    if args.dry_run:
        print("(dry run -- nothing written)")
    if not report.report.clean:
        print("\nUnbridged club(s): a club is playing in E0-E3 that "
              "reference/bbc_teams.csv does not know. Add it and re-run "
              "scripts/build_team_aliases.py before serving.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
