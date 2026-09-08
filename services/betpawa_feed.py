"""betPawa's upcoming E0-E3 events and the selection ids behind them.

    python -m services.betpawa_feed                  # fetch and store
    python -m services.betpawa_feed --dry-run
    python -m services.betpawa_feed --file capture.json

Drives the site's "bet this on betPawa" button (`docs/BETPAWA_PLAN.md`):
for every fixture ahead, the bookmaker's event id and, for each of the
eight sides the rule can publish, the selection id whose prefill URL opens
that wager in a user's betslip. It stores ids, not a product: the odds are
kept because they arrive with the id, and nothing on the site shows them
(D9).

Three properties of the source shape the code:

*It is an undocumented JSON API behind one brand header.* A single request
(`by-queries`, at most 100 events a page) lists every upcoming event in
the four competitions with exactly the three markets asked for. No login,
no cookie, no device fingerprint. The parse is pinned by a saved capture
(`tests/data/betpawa_efl_2026-09-08.json`); a shape change fails the
cycle step loudly, and the step failing costs the buttons and nothing else.

*Ids are stable and brand-independent.* Event, participant and selection
ids were identical on the Uganda and Kenya sites on 2026-09-08; only the
odds differed. So the scrape runs against one brand and the API chooses a
country host per user. The bridge keys on the **participant id**, as the
BBC bridge keys on the URN: a display name moves, an identifier does not.

*Kick-offs are UTC; the store's are UK wall-clock.* `startTime` converts
through Europe/London to the `(match_date, kickoff_time)` pair both
fixture feeds write, and the join is on bridged team ids and that date.

**It is additive and never destructive.** It writes only its own two
tables (`003_betpawa.sql`), replacing a fixture's rows on every run so a
line the book withdraws is gone at the next scrape. It never touches
`fixtures` or `tips`.
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.parse
import urllib.request
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from engine import db
from engine.ingest.teams import BETPAWA, BridgeReport, TeamBridge

#: The brand the scrape runs against. Any served country would do (the ids
#: are shared, BETPAWA_PLAN.md 1.4); Uganda is the one the captures came from.
HOST = "www.betpawa.ug"
BRAND = "betpawa-uganda"
LIST_URL = f"https://{HOST}/api/sportsbook/v4/events/lists/by-queries"

#: betPawa's category for football, and its competition ids for the served
#: divisions -- read back from the API's own `competition` field on
#: 2026-09-08 (region 288, England), not assumed. EC is absent: not served.
FOOTBALL = "2"
DIVISION_BY_COMPETITION = {
    "11965": "E0",   # Premier League
    "12101": "E1",   # Championship
    "12317": "E2",   # League One
    "12192": "E3",   # League Two
}

#: The three market types that carry every side the rule can publish
#: (BETPAWA_PLAN.md 1.2). "Handicap 1X2" (4724) is a different market.
MARKET_1X2 = "3743"
MARKET_DOUBLE_CHANCE = "4693"
MARKET_ASIAN_HANDICAP = "3774"
MARKETS = (MARKET_1X2, MARKET_DOUBLE_CHANCE, MARKET_ASIAN_HANDICAP)

#: The API refuses more than this per page ("The maximum number of events
#: is 100"). A fortnight of four leagues was 65 events, so one page is the
#: norm and the loop below is for the odd congested week.
PAGE_SIZE = 100
#: Courtesy pause between pages, as the calendar has between date pages.
REQUEST_INTERVAL = 2.0

SIDES = ("H", "D", "A", "1X", "X2", "12", "H+1.5", "A+1.5")

_LONDON = ZoneInfo("Europe/London")


# --- fetching --------------------------------------------------------------


def query(skip: int = 0, take: int = PAGE_SIZE) -> str:
    """The `q` parameter: upcoming football with odds, the four competitions,
    the three markets, one page."""
    return json.dumps({"queries": [{
        "query": {
            "eventType": "UPCOMING",
            "categories": [FOOTBALL],
            "zones": {"competitions": list(DIVISION_BY_COMPETITION)},
            "hasOdds": True,
        },
        "view": {"marketTypes": list(MARKETS)},
        "skip": skip,
        "take": take,
    }]}, separators=(",", ":"))


def _get(url: str, timeout: int) -> dict:
    request = urllib.request.Request(  # noqa: S310
        url, headers={
            "X-Pawa-Brand": BRAND,
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (compatible; bvp-betpawa/0.1)",
        })
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        return json.loads(response.read().decode("utf-8"))


def events_in(payload: dict) -> list[dict]:
    """The event list inside a `by-queries` body, or a ValueError naming what
    was there instead -- the shape is the one thing about this source that is
    not under our control."""
    try:
        return payload["responses"][0]["responses"]
    except (KeyError, IndexError, TypeError):
        keys = sorted(payload) if isinstance(payload, dict) else type(payload).__name__
        raise ValueError(f"unexpected by-queries body: {keys}") from None


def fetch(timeout: int = 30, page_size: int = PAGE_SIZE,
          interval: float = REQUEST_INTERVAL) -> list[dict]:
    """Every upcoming event in the four competitions, raw, across pages."""
    events: list[dict] = []
    skip = 0
    while True:
        page = events_in(_get(
            f"{LIST_URL}?q={urllib.parse.quote(query(skip, page_size), safe='')}",
            timeout))
        events.extend(page)
        if len(page) < page_size:
            return events
        skip += page_size
        time.sleep(interval)


# --- parsing ---------------------------------------------------------------


@dataclass
class Event:
    event_id: str
    competition_id: str
    division: str
    start_time: str            # UTC, as published
    match_date: str            # UK date, the store's convention
    kickoff_time: str          # UK HH:MM
    home_id: str
    home_name: str
    away_id: str
    away_name: str
    selections: dict[str, tuple[str, float | None]]   # side -> (selection id, odds)


@dataclass
class ParseReport:
    events: list[Event] = field(default_factory=list)
    other_competitions: int = 0    # listed under an id we do not serve
    malformed: int = 0             # not two participants, or no start time


def uk_clock(start_time: str) -> tuple[str, str]:
    """('YYYY-MM-DD', 'HH:MM') in Europe/London from a UTC ISO instant."""
    instant = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=timezone.utc)
    local = instant.astimezone(_LONDON)
    return local.strftime("%Y-%m-%d"), local.strftime("%H:%M")


def side_of(market_id: str, hcp: str | None, price_name: str) -> str | None:
    """Our side code for one price, or None for a price the rule never
    publishes (the draw-no-bet of a +0.5 line, a -2.5, ...).

    The Asian Handicap row's `hcp` is stated from the home side, so the away
    +1.5 sits on the `-1.5` row and the home +1.5 on the `1.5` row (no sign).
    """
    if market_id == MARKET_1X2:
        return {"1": "H", "X": "D", "2": "A"}.get(price_name)
    if market_id == MARKET_DOUBLE_CHANCE:
        return price_name if price_name in ("1X", "X2", "12") else None
    if market_id == MARKET_ASIAN_HANDICAP:
        if hcp == "1.5" and price_name == "1":
            return "H+1.5"
        if hcp == "-1.5" and price_name == "2":
            return "A+1.5"
    return None


def selections_of(markets: list[dict]) -> dict[str, tuple[str, float | None]]:
    out: dict[str, tuple[str, float | None]] = {}
    for market in markets or []:
        market_id = str((market.get("marketType") or {}).get("id"))
        for row in market.get("row") or []:
            hcp = (row.get("specifier") or {}).get("hcp")
            for price in row.get("prices") or []:
                side = side_of(market_id, hcp, str(price.get("name")))
                if side is None:
                    continue
                odds = price.get("odds")
                out[side] = (str(price["id"]), float(odds) if odds is not None else None)
    return out


def parse(raw_events: list[dict]) -> ParseReport:
    """Served-division events from the raw list, with UK-clock kick-offs and
    the eight sides' selection ids where the book carries them."""
    out = ParseReport()
    for raw in raw_events:
        competition = str((raw.get("competition") or {}).get("id"))
        division = DIVISION_BY_COMPETITION.get(competition)
        if division is None:
            out.other_competitions += 1
            continue
        by_position = {p.get("position"): p for p in raw.get("participants") or []}
        home, away = by_position.get(1), by_position.get(2)
        start = raw.get("startTime")
        if home is None or away is None or not start:
            out.malformed += 1
            continue
        match_date, kickoff = uk_clock(start)
        out.events.append(Event(
            event_id=str(raw["id"]), competition_id=competition, division=division,
            start_time=start, match_date=match_date, kickoff_time=kickoff,
            home_id=str(home["id"]), home_name=str(home.get("name", "?")),
            away_id=str(away["id"]), away_name=str(away.get("name", "?")),
            selections=selections_of(raw.get("markets") or []),
        ))
    return out


# --- storing ---------------------------------------------------------------


@dataclass
class FeedReport:
    events: int = 0            # served-division events parsed
    past: int = 0              # dated before `today`, skipped
    matched: int = 0           # found our fixture
    unmatched: int = 0         # no fixture of ours on that date (outside the
                               # feed window, or a date the two feeds disagree on)
    selections: int = 0        # selection rows written (or would be, dry-run)
    sides: Counter = field(default_factory=Counter)   # side -> matched events carrying it
    report: BridgeReport = field(default_factory=BridgeReport)

    def describe(self) -> str:
        lines = [
            f"{self.events} event(s); {self.matched} matched our fixtures, "
            f"{self.unmatched} unmatched, {self.past} past; "
            f"{self.selections} selection(s)",
            "sides: " + ", ".join(f"{s} {self.sides[s]}" for s in SIDES),
            self.report.describe(),
        ]
        return "\n".join(lines)


def _resolve_pair(event: Event, bridge: TeamBridge, ids: dict[str, int],
                  report: BridgeReport) -> tuple[int, int] | None:
    """(home_id, away_id), or None with each failure recorded by *name*: the
    lookup is by participant id, but an operator adding a row to
    `reference/betpawa_teams.csv` needs the club, not a number."""
    out = []
    for participant_id, name in ((event.home_id, event.home_name),
                                 (event.away_id, event.away_name)):
        canonical = bridge.try_resolve(BETPAWA, participant_id)
        if canonical is None or canonical not in ids:
            report.record(BETPAWA, f"{name} (id {participant_id})")
            out.append(None)
        else:
            out.append(ids[canonical])
    return None if None in out else (out[0], out[1])


def sync(conn: db.Connection, events: list[Event], *, today: str | None = None,
         dry_run: bool = False) -> FeedReport:
    """Store the ids for every event that is one of our future fixtures.

    Per fixture: upsert the event row, then replace its selection rows
    wholesale, so the table always says what the book carried at the last
    scrape and nothing older. Events for fixtures we do not hold are counted
    and skipped -- this feed never creates a fixture.
    """
    today = today or db.today()
    bridge = TeamBridge.load()
    ids = {row["canonical_name"]: row["team_id"]
           for row in conn.execute("SELECT team_id, canonical_name FROM teams")}
    out = FeedReport()

    for event in events:
        out.events += 1
        if event.match_date < today:
            out.past += 1
            continue
        pair = _resolve_pair(event, bridge, ids, out.report)
        if pair is None:
            continue
        fixture_id = db.scalar(
            conn,
            "SELECT fixture_id FROM fixtures WHERE division=%s AND match_date=%s"
            " AND home_team_id=%s AND away_team_id=%s",
            (event.division, event.match_date, *pair))
        if fixture_id is None:
            out.unmatched += 1
            continue
        out.matched += 1
        out.selections += len(event.selections)
        out.sides.update(event.selections.keys())
        if not dry_run:
            _write(conn, fixture_id, event)
    if not dry_run:
        conn.commit()
    return out


def _write(conn: db.Connection, fixture_id: int, event: Event) -> None:
    # A rescheduled match can come back under a new event id, and the old id
    # must not survive on another fixture's row: UNIQUE(event_id) would refuse
    # the upsert below, and the link would open the wrong game.
    conn.execute("DELETE FROM betpawa_events WHERE event_id=%s AND fixture_id<>%s",
                 (event.event_id, fixture_id))
    conn.execute(
        "INSERT INTO betpawa_events (fixture_id, event_id, competition_id, start_time,"
        f" fetched_at) VALUES (%s, %s, %s, %s, {db.NOW_TEXT})"
        " ON CONFLICT (fixture_id) DO UPDATE SET event_id=EXCLUDED.event_id,"
        " competition_id=EXCLUDED.competition_id, start_time=EXCLUDED.start_time,"
        " fetched_at=EXCLUDED.fetched_at",
        (fixture_id, event.event_id, event.competition_id, event.start_time))
    conn.execute("DELETE FROM betpawa_selections WHERE fixture_id=%s", (fixture_id,))
    conn.executemany(
        "INSERT INTO betpawa_selections (fixture_id, side, selection_id, odds)"
        " VALUES (%s, %s, %s, %s)",
        [(fixture_id, side, selection_id, odds)
         for side, (selection_id, odds) in event.selections.items()])


# --- command line ----------------------------------------------------------


def load_capture(path: Path) -> list[dict]:
    """A saved body -- the raw `by-queries` response, or a bare event list."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, list) else events_in(payload)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--dry-run", action="store_true", help="write nothing")
    parser.add_argument("--file", type=Path, help="replay a saved capture instead of fetching")
    args = parser.parse_args(argv)

    raw = load_capture(args.file) if args.file else fetch()
    parsed = parse(raw)
    conn = db.connect()
    report = sync(conn, parsed.events, dry_run=args.dry_run)
    print(f"{len(raw)} raw event(s), {parsed.other_competitions} in other competitions, "
          f"{parsed.malformed} malformed")
    print(report.describe())
    if args.dry_run:
        print("(dry run -- nothing written)")
    return 0 if report.report.clean else 2


if __name__ == "__main__":
    raise SystemExit(main())
