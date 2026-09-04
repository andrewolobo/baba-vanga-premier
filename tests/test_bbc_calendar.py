"""The second fixture calendar.

Nothing here touches the network. The parser runs against a real payload cut
down to six events (`tests/data/bbc_scores_fixtures.html`) -- the nesting, the
field names and the double encoding are exactly what BBC publishes, so the
assertions are about what the page actually carries rather than about a mock of
it. Edge cases the real page does not happen to contain are built with `page()`,
which re-creates the same wrapper.

The properties that matter most are the two that make a second source safe:
football-data's rows are never modified, and a fixture in the past is never
inserted.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from engine import db
from services import bbc_calendar

REAL_PAGE = Path(__file__).parent / "data" / "bbc_scores_fixtures.html"

#: Clubs the sample page names, in the served divisions and pre-event.
TEAMS = ["Bolton", "Preston", "Bristol City", "Millwall",
         "Notts County", "Leicester", "Newport County", "Rochdale"]

URN = "urn:bbc:sportsdata:football:team:{}"
CHAMPIONSHIP = "urn:bbc:sportsdata:football:tournament:championship"


_DEFAULT = object()


def event(home_slug, away_slug, *, date="2026-08-15", time="15:00", tournament=CHAMPIONSHIP, status="PreEvent", home_urn=_DEFAULT):
    """One event in the shape the page publishes."""
    return {
        "home": {"fullName": home_slug.replace("-", " ").title(),
                 "urn": URN.format(home_slug) if home_urn is _DEFAULT else home_urn},
        "away": {"fullName": away_slug.replace("-", " ").title(),
                 "urn": URN.format(away_slug)},
        "date": {"isoDate": date},
        "time": {"displayTimeUK": time},
        "status": status,
        "tournament": {"urn": tournament},
    }


def page(*events) -> str:
    """Wrap events in the double-encoded `__INITIAL_DATA__` the page uses."""
    data = {"data": {"sport-data-scores-fixtures?x=1": {"data": {
        "eventGroups": [{"secondaryGroups": [{"events": list(events)}]}]}}}}
    literal = json.dumps(json.dumps(data))
    return f"<html><body><script>window.__INITIAL_DATA__={literal};</script></body></html>"


@pytest.fixture
def conn(database_url):
    connection = db.connect(database_url)
    for i, name in enumerate(TEAMS, start=1):
        connection.execute("INSERT INTO teams (team_id, canonical_name) VALUES (%s, %s)",
                           (i, name))
    connection.commit()
    yield connection
    connection.close()


# --- parsing the real page -------------------------------------------------


def test_extracts_the_double_encoded_payload():
    payload = bbc_calendar.extract(REAL_PAGE.read_text(encoding="utf-8"))
    assert "eventGroups" in payload


def test_parses_only_served_divisions():
    """National League is on the page and must not be ingested: EC is in the
    corpus but is not a served market."""
    out = bbc_calendar.parse(REAL_PAGE.read_text(encoding="utf-8"))
    assert out.events == 6
    assert {f["division"] for f in out.fixtures} == {"E1", "E2", "E3"}
    assert not any("Aldershot" in f["home_name"] for f in out.fixtures)


def test_skips_matches_that_are_not_pre_event():
    """The page's one Premier League row is PostEvent. Inserting it would let
    the next serve price a played match with today's artifact."""
    out = bbc_calendar.parse(REAL_PAGE.read_text(encoding="utf-8"))
    assert out.not_pre_event == 1
    assert not any(f["division"] == "E0" for f in out.fixtures)


def test_stores_uk_local_date_and_kickoff_not_utc():
    """The merge key depends on this. football-data writes UK-local dates, so a
    12:30 BST kickoff must store 12:30 on 2026-08-15 -- not 11:30 from the UTC
    `startDateTime` beside it."""
    out = bbc_calendar.parse(REAL_PAGE.read_text(encoding="utf-8"))
    bolton = next(f for f in out.fixtures if f["home_name"] == "Bolton Wanderers")
    assert bolton["match_date"] == "2026-08-15"
    assert bolton["kickoff_time"] == "12:30"


def test_a_page_without_the_payload_is_an_error():
    with pytest.raises(ValueError, match="__INITIAL_DATA__"):
        bbc_calendar.extract("<html><body>maintenance</body></html>")


# --- writing ---------------------------------------------------------------


def test_inserts_new_fixtures(conn):
    report = bbc_calendar.sync(
        conn, [("bbc", REAL_PAGE.read_text(encoding="utf-8"))], today="2026-08-15")
    assert report.inserted == 4
    rows = conn.execute("SELECT division, match_date, kickoff_time,"
                        " avg_h FROM fixtures ORDER BY division").fetchall()
    assert [r["division"] for r in rows] == ["E1", "E1", "E2", "E3"]
    # No odds: this feed carries none, and NULL is enough to predict.
    assert all(r["avg_h"] is None for r in rows)


def test_never_modifies_a_fixture_football_data_already_published(conn):
    """The safety property. This feed has no odds, so an update would write NULL
    over prices the other feed put there -- and CLV would be ungradeable."""
    conn.execute(
        "INSERT INTO fixtures (division, match_date, home_team_id, away_team_id,"
        " kickoff_time, avg_h, avg_d, avg_a, source_file)"
        " VALUES ('E1', '2026-08-15', 1, 2, '12:30', 1.85, 3.5, 4.2, 'football-data')")
    conn.commit()

    report = bbc_calendar.sync(
        conn, [("bbc", REAL_PAGE.read_text(encoding="utf-8"))], today="2026-08-15")

    assert report.already_known == 1
    assert report.inserted == 3
    row = conn.execute("SELECT avg_h, source_file FROM fixtures"
                       " WHERE division='E1' AND home_team_id=1").fetchone()
    assert row["avg_h"] == 1.85
    assert row["source_file"] == "football-data"


def test_a_past_fixture_is_never_inserted(conn):
    """Predictions are append-only (README). A past fixture inserted here would
    be priced by the next serve using an artifact that has seen the result."""
    report = bbc_calendar.sync(
        conn, [("bbc", REAL_PAGE.read_text(encoding="utf-8"))], today="2026-09-01")
    assert report.inserted == 0
    assert report.past == 5          # four served fixtures, plus the PostEvent row
    assert db.scalar(conn, "SELECT COUNT(*) FROM fixtures") == 0


def test_todays_fixtures_are_still_inserted(conn):
    """The lower bound is `today`, not `after today` -- a matchday-morning run
    is the normal case, not an edge one."""
    report = bbc_calendar.sync(
        conn, [("bbc", REAL_PAGE.read_text(encoding="utf-8"))], today="2026-08-15")
    assert report.inserted == 4


def test_an_unknown_club_is_excluded_by_name_and_counted(conn):
    """SPEC 0.2: never a silent drop. Reported by NAME though keyed by URN --
    an operator reading an alert needs to recognise the club."""
    html = page(event("bolton-wanderers", "preston-north-end"),
                event("hornchurch", "millwall"))
    report = bbc_calendar.sync(conn, [("bbc", html)], today="2026-08-15")

    assert report.inserted == 1
    assert not report.report.clean
    assert ("bbc", "Hornchurch") in report.report.misses


def test_a_side_with_no_urn_is_reported_rather_than_crashing(conn):
    """Foreign clubs on the page can lack a URN. English ones have not, but an
    unhandled None would take a matchday run down for a schema change."""
    html = page(event("bolton-wanderers", "preston-north-end", home_urn=None))
    report = bbc_calendar.sync(conn, [("bbc", html)], today="2026-08-15")
    assert report.inserted == 0
    assert not report.report.clean


def test_dry_run_writes_nothing(conn):
    report = bbc_calendar.sync(
        conn, [("bbc", REAL_PAGE.read_text(encoding="utf-8"))],
        today="2026-08-15", dry_run=True)
    assert report.inserted == 4
    assert db.scalar(conn, "SELECT COUNT(*) FROM fixtures") == 0


def test_rerunning_inserts_nothing_further(conn):
    html = REAL_PAGE.read_text(encoding="utf-8")
    bbc_calendar.sync(conn, [("bbc", html)], today="2026-08-15")
    again = bbc_calendar.sync(conn, [("bbc", html)], today="2026-08-15")
    assert again.inserted == 0
    assert again.already_known == 4
    assert db.scalar(conn, "SELECT COUNT(*) FROM fixtures") == 4
