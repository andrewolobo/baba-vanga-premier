"""betPawa's selection ids behind the wager button (docs/BETPAWA_PLAN.md).

The parse is pinned against a real capture cut down to five events
(`tests/data/betpawa_efl_2026-09-08.json`): the Southampton v Swansea ids the
owner-verified prefill link was built from, a one-sided handicap ladder
(Gillingham v Tranmere), and three ordinary games. The store side is tested
on what it must never do -- create a fixture, keep a withdrawn line, let an
event id sit on two fixtures -- more than on the happy path.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from engine import db
from engine.ingest.teams import BETPAWA, TeamBridge
from services import betpawa_feed

CAPTURE = Path(__file__).parent / "data" / "betpawa_efl_2026-09-08.json"

#: Canonical names of the ten clubs in the capture, in the bridge's spelling.
TEAMS = ["Southampton", "Swansea", "Gillingham", "Tranmere", "Bournemouth",
         "Brentford", "Barnet", "Accrington", "Liverpool", "Fulham"]
SOUTHAMPTON, SWANSEA = 1, 2

SOU_SWA = "37536526"
#: The selection the owner-verified link opened (BETPAWA_PLAN.md 1.3).
SWANSEA_PLUS_15 = "1539591711"


@pytest.fixture
def raw() -> list[dict]:
    return betpawa_feed.load_capture(CAPTURE)


@pytest.fixture
def conn(database_url):
    connection = db.connect(database_url)
    for i, name in enumerate(TEAMS, start=1):
        connection.execute("INSERT INTO teams (team_id, canonical_name) VALUES (%s, %s)",
                           (i, name))
    connection.commit()
    yield connection
    connection.close()


def add_fixture(conn, division, date, home_id, away_id, time="19:45") -> int:
    fixture_id = db.scalar(
        conn,
        "INSERT INTO fixtures (division, match_date, kickoff_time, home_team_id,"
        " away_team_id, source_file) VALUES (%s, %s, %s, %s, %s, 'test')"
        " RETURNING fixture_id",
        (division, date, time, home_id, away_id))
    conn.commit()
    return fixture_id


def event(raw, event_id=SOU_SWA) -> dict:
    return next(e for e in raw if e["id"] == event_id)


def stored_sides(conn, fixture_id) -> dict[str, str]:
    return {r["side"]: r["selection_id"] for r in conn.execute(
        "SELECT side, selection_id FROM betpawa_selections WHERE fixture_id=%s",
        (fixture_id,))}


# --- the parse, pinned on the capture --------------------------------------


def test_parses_the_captured_events_into_our_divisions(raw):
    parsed = betpawa_feed.parse(raw)
    assert len(parsed.events) == 5
    assert parsed.other_competitions == 0 and parsed.malformed == 0
    assert {e.division for e in parsed.events} == {"E0", "E1", "E3"}
    sou = next(e for e in parsed.events if e.event_id == SOU_SWA)
    assert (sou.home_id, sou.home_name) == ("655237", "Southampton FC")
    assert (sou.away_id, sou.away_name) == ("657906", "Swansea City")
    assert sou.competition_id == "12101" and sou.division == "E1"


def test_kickoffs_are_stored_as_uk_wall_clock_not_utc(raw):
    """18:45Z on a September evening is 19:45 in London, which is what both
    fixture feeds write; the join would miss on the UTC time."""
    sou = next(e for e in betpawa_feed.parse(raw).events if e.event_id == SOU_SWA)
    assert sou.start_time == "2026-09-08T18:45:00Z"
    assert (sou.match_date, sou.kickoff_time) == ("2026-09-08", "19:45")


@pytest.mark.parametrize("utc, expected", [
    ("2026-09-08T18:45:00Z", ("2026-09-08", "19:45")),   # BST
    ("2026-12-12T15:00:00Z", ("2026-12-12", "15:00")),   # GMT
    ("2026-09-08T23:30:00Z", ("2026-09-09", "00:30")),   # crosses midnight in London
])
def test_uk_clock(utc, expected):
    assert betpawa_feed.uk_clock(utc) == expected


def test_pins_the_selection_ids_the_verified_link_was_built_from(raw):
    sou = next(e for e in betpawa_feed.parse(raw).events if e.event_id == SOU_SWA)
    assert sou.selections["A+1.5"] == (SWANSEA_PLUS_15, 1.32)
    assert sou.selections["1X"][0] == "1537500845"
    assert sou.selections["H"][0] == "1537500854"
    assert sou.selections["D"][0] == "1537500855"
    assert sou.selections["A"][0] == "1537500856"
    assert sou.selections["12"][0] == "1537500846"
    assert sou.selections["X2"][0] == "1537500847"
    # The ladder is one-sided: Southampton were favourites, so no home +1.5.
    assert "H+1.5" not in sou.selections


def test_the_handicap_row_is_read_from_the_home_side(raw):
    """Gillingham v Tranmere carried +1.5 on the home side only; the `hcp`
    on that row is `1.5` (home), and the away +1.5 lives on a `-1.5` row."""
    gil = next(e for e in betpawa_feed.parse(raw).events if e.event_id == "37632855")
    assert "H+1.5" in gil.selections
    assert "A+1.5" not in gil.selections


@pytest.mark.parametrize("market, hcp, name, side", [
    ("3743", None, "1", "H"), ("3743", None, "X", "D"), ("3743", None, "2", "A"),
    ("4693", None, "1X", "1X"), ("4693", None, "12", "12"),
    ("3774", "1.5", "1", "H+1.5"), ("3774", "-1.5", "2", "A+1.5"),
    ("3774", "-1.5", "1", None),    # the favourite's -1.5: never published
    ("3774", "0.5", "1", None),     # other lines: never published
    ("3774", "-2.5", "2", None),
    ("4724", "1", "1", None),       # Handicap 1X2 is a different market
    ("5000", "2.5", "Over", None),  # totals: B4 closed
])
def test_side_of(market, hcp, name, side):
    assert betpawa_feed.side_of(market, hcp, name) == side


def test_an_unserved_competition_is_counted_not_parsed(raw):
    raw = copy.deepcopy(raw)
    event(raw)["competition"] = {"id": "17491", "name": "GT Leagues"}
    parsed = betpawa_feed.parse(raw)
    assert parsed.other_competitions == 1
    assert len(parsed.events) == 4


def test_a_malformed_event_is_counted_not_parsed(raw):
    raw = copy.deepcopy(raw)
    event(raw)["participants"] = event(raw)["participants"][:1]
    parsed = betpawa_feed.parse(raw)
    assert parsed.malformed == 1
    assert len(parsed.events) == 4


def test_an_unexpected_body_is_named_not_swallowed():
    with pytest.raises(ValueError, match="unexpected by-queries body"):
        betpawa_feed.events_in({"error": "BAD_REQUEST"})


def test_the_query_asks_for_the_four_leagues_and_three_markets_one_page():
    import json
    q = json.loads(betpawa_feed.query())["queries"][0]
    assert q["query"]["zones"]["competitions"] == ["11965", "12101", "12317", "12192"]
    assert q["view"]["marketTypes"] == ["3743", "4693", "3774"]
    assert q["take"] == 100 and q["query"]["eventType"] == "UPCOMING"


# --- the bridge --------------------------------------------------------------


def test_the_reference_file_bridges_every_captured_participant(raw):
    """`reference/betpawa_teams.csv` is folded into the bridge by
    scripts/build_team_aliases.py; a participant it cannot resolve is a club
    the button will silently not render for."""
    bridge = TeamBridge.load()
    for e in betpawa_feed.parse(raw).events:
        for pid, name in ((e.home_id, e.home_name), (e.away_id, e.away_name)):
            assert bridge.try_resolve(BETPAWA, pid) is not None, name


# --- the store ---------------------------------------------------------------


def test_stores_the_event_and_every_side_for_a_matching_fixture(conn, raw):
    fixture_id = add_fixture(conn, "E1", "2026-09-08", SOUTHAMPTON, SWANSEA)

    report = betpawa_feed.sync(conn, betpawa_feed.parse(raw).events, today="2026-09-08")

    assert (report.events, report.matched, report.unmatched, report.past) == (5, 1, 4, 0)
    assert report.report.clean
    row = conn.execute("SELECT event_id, competition_id, start_time FROM betpawa_events"
                       " WHERE fixture_id=%s", (fixture_id,)).fetchone()
    assert row == {"event_id": SOU_SWA, "competition_id": "12101",
                   "start_time": "2026-09-08T18:45:00Z"}
    sides = stored_sides(conn, fixture_id)
    assert set(sides) == {"H", "D", "A", "1X", "X2", "12", "A+1.5"}
    assert sides["A+1.5"] == SWANSEA_PLUS_15
    assert report.selections == 7 and report.sides["A+1.5"] == 1


def test_never_creates_a_fixture(conn, raw):
    """This feed keys off fixtures the two calendars wrote; a game we do not
    hold is counted, not invented."""
    report = betpawa_feed.sync(conn, betpawa_feed.parse(raw).events, today="2026-09-08")
    assert report.unmatched == 5 and report.matched == 0
    assert db.scalar(conn, "SELECT COUNT(*) FROM fixtures") == 0
    assert db.scalar(conn, "SELECT COUNT(*) FROM betpawa_events") == 0


def test_a_past_event_is_skipped(conn, raw):
    add_fixture(conn, "E1", "2026-09-08", SOUTHAMPTON, SWANSEA)
    report = betpawa_feed.sync(conn, betpawa_feed.parse(raw).events, today="2026-09-10")
    assert report.past == 1 and report.matched == 0
    assert db.scalar(conn, "SELECT COUNT(*) FROM betpawa_events") == 0


def test_an_unbridged_participant_is_reported_by_name_and_skipped(conn, raw):
    add_fixture(conn, "E1", "2026-09-08", SOUTHAMPTON, SWANSEA)
    raw = copy.deepcopy(raw)
    event(raw)["participants"][1]["id"] = "999999"

    report = betpawa_feed.sync(conn, betpawa_feed.parse(raw).events, today="2026-09-08")

    assert not report.report.clean
    assert (BETPAWA, "Swansea City (id 999999)") in report.report.misses
    assert report.matched == 0
    assert db.scalar(conn, "SELECT COUNT(*) FROM betpawa_events") == 0


def test_a_rerun_replaces_the_selections_and_drops_a_withdrawn_line(conn, raw):
    fixture_id = add_fixture(conn, "E1", "2026-09-08", SOUTHAMPTON, SWANSEA)
    betpawa_feed.sync(conn, betpawa_feed.parse(raw).events, today="2026-09-08")
    assert "A+1.5" in stored_sides(conn, fixture_id)

    later = copy.deepcopy(raw)
    event(later)["markets"] = [m for m in event(later)["markets"]
                               if m["marketType"]["id"] != betpawa_feed.MARKET_ASIAN_HANDICAP]
    betpawa_feed.sync(conn, betpawa_feed.parse(later).events, today="2026-09-08")

    sides = stored_sides(conn, fixture_id)
    assert "A+1.5" not in sides and len(sides) == 6
    assert db.scalar(conn, "SELECT COUNT(*) FROM betpawa_events") == 1


def test_an_event_id_never_sits_on_two_fixtures(conn, raw):
    """A postponed game comes back rescheduled: same event id, new date, and
    on our side a new fixture row. The old row must let go of the id, or the
    UNIQUE refuses the write and the stale row links the wrong game."""
    first = add_fixture(conn, "E1", "2026-09-08", SOUTHAMPTON, SWANSEA)
    betpawa_feed.sync(conn, betpawa_feed.parse(raw).events, today="2026-09-08")

    second = add_fixture(conn, "E1", "2026-09-15", SOUTHAMPTON, SWANSEA)
    moved = copy.deepcopy(raw)
    event(moved)["startTime"] = "2026-09-15T18:45:00Z"
    betpawa_feed.sync(conn, betpawa_feed.parse(moved).events, today="2026-09-08")

    rows = conn.execute("SELECT fixture_id FROM betpawa_events WHERE event_id=%s",
                        (SOU_SWA,)).fetchall()
    assert [r["fixture_id"] for r in rows] == [second]
    assert stored_sides(conn, first) == {}
    assert "A+1.5" in stored_sides(conn, second)


def test_dry_run_writes_nothing(conn, raw):
    add_fixture(conn, "E1", "2026-09-08", SOUTHAMPTON, SWANSEA)
    report = betpawa_feed.sync(conn, betpawa_feed.parse(raw).events,
                               today="2026-09-08", dry_run=True)
    assert report.matched == 1 and report.selections == 7
    assert db.scalar(conn, "SELECT COUNT(*) FROM betpawa_events") == 0
    assert db.scalar(conn, "SELECT COUNT(*) FROM betpawa_selections") == 0


def test_the_report_reads_as_a_sentence(conn, raw):
    add_fixture(conn, "E1", "2026-09-08", SOUTHAMPTON, SWANSEA)
    text = betpawa_feed.sync(conn, betpawa_feed.parse(raw).events,
                             today="2026-09-08").describe()
    assert "5 event(s); 1 matched our fixtures, 4 unmatched" in text
    assert "A+1.5 1" in text and "all team names bridged" in text
