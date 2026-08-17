"""Full-time results from the BBC pages, and what they settle.

Nothing here touches the network. The parser runs against a real payload cut
down to six events (`tests/data/bbc_results_2026-08-15.html`, the EFL opening
Saturday) so the assertions are about the field names BBC actually publishes
for a played match -- `PostEvent`, `statusComment.value == "FT"`,
`runningScores.fulltime` -- rather than about a mock of them. Edge cases the
real page does not contain are built with the calendar test's `page()` wrapper.

The properties that matter: only full time settles anything; settlement goes
through the same `settle_tips` the strike rate was measured with; a match with
no fixture row here is dropped, not inserted; and a second pass settles nothing
twice.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from engine import db
from services import bbc_results
from tests.test_bbc_calendar import URN, event, page

REAL_PAGE = Path(__file__).parent / "data" / "bbc_results_2026-08-15.html"

#: Home sides of the four served-division results on the sample page, and
#: their opponents, by canonical name.
TEAMS = ["Bolton", "Preston", "Sheffield United", "Birmingham",
         "Reading", "Luton", "Newport County", "Rochdale"]


def played(home_slug, away_slug, fthg, ftag, *, status="PostEvent", comment="FT", **kw):
    """A played event in the page's shape: `event()` plus the score fields."""
    e = event(home_slug, away_slug, status=status, **kw)
    e["statusComment"] = {"value": comment}
    e["home"]["runningScores"] = {"halftime": "0", "fulltime": str(fthg)}
    e["away"]["runningScores"] = {"halftime": "0", "fulltime": str(ftag)}
    e["home"]["score"], e["away"]["score"] = str(fthg), str(ftag)
    return e


@pytest.fixture
def conn(tmp_path):
    connection = db.connect(tmp_path / "results.db")
    db.migrate(connection)
    for i, name in enumerate(TEAMS, start=1):
        connection.execute("INSERT INTO teams (team_id, canonical_name) VALUES (?, ?)",
                           (i, name))
    connection.commit()
    yield connection
    connection.close()


def tip(conn, division, date, home_id, away_id, side, *, fixture_id=None):
    """A fixture, a prediction and one published tip on it. Returns fixture_id."""
    cur = conn.execute(
        "INSERT INTO fixtures (fixture_id, division, match_date, home_team_id,"
        " away_team_id, max_h, avg_h, source_file) VALUES (?, ?, ?, ?, ?, 2.0, 1.9, 'test')",
        (fixture_id, division, date, home_id, away_id))
    fid = cur.lastrowid
    cur = conn.execute(
        "INSERT INTO predictions (fixture_id, model_version, information_set,"
        " lam_h, lam_a, p_home, p_draw, p_away, p_over25, p_under25)"
        " VALUES (?, 'v1', 'pre_close', 1.5, 1.0, 0.6, 0.25, 0.15, 0.5, 0.5)", (fid,))
    conn.execute(
        "INSERT INTO tips (prediction_id, fixture_id, side, model_prob, floor,"
        " best_price, avg_price, rule_version) VALUES (?, ?, ?, 0.6, 0.55,"
        " 2.0, 1.9, 'confidence-v2')", (cur.lastrowid, fid, side))
    conn.commit()
    return fid


# --- parsing the real page -------------------------------------------------


def test_parses_full_time_results_in_the_served_divisions_only():
    results, counts = bbc_results.parse_results(REAL_PAGE.read_text(encoding="utf-8"))
    assert counts == {"events": 6, "english": 4}    # National League and Scotland excluded
    assert [(r["division"], r["fthg"], r["ftag"], r["ftr"]) for r in results] == [
        ("E1", 2, 1, "H"), ("E1", 0, 0, "D"), ("E2", 3, 4, "A"), ("E3", 3, 0, "H")]
    assert results[0]["home_urn"] == URN.format("bolton-wanderers")
    assert results[0]["match_date"] == "2026-08-15"


@pytest.mark.parametrize("status, comment", [
    ("PreEvent", "Scheduled"),   # not kicked off
    ("MidEvent", "HT"),          # in play
    ("MidEvent", "45'"),
    ("PostEvent", "Postponed"),  # PostEvent is not enough on its own
    ("PostEvent", "Abandoned"),
])
def test_only_full_time_is_a_result(status, comment):
    """A tip settled off an in-play score is a wrong record that cannot be
    corrected -- the outcome is written once. Nothing but FT gets through."""
    html = page(played("bolton-wanderers", "preston-north-end", 2, 1,
                       status=status, comment=comment))
    results, counts = bbc_results.parse_results(html)
    assert counts["english"] == 1
    assert results == []


def test_a_full_time_event_with_no_score_is_not_a_result():
    e = played("bolton-wanderers", "preston-north-end", 2, 1)
    del e["home"]["runningScores"]
    del e["home"]["score"]
    results, _ = bbc_results.parse_results(page(e))
    assert results == []


# --- settling --------------------------------------------------------------


def test_settles_the_tip_through_the_measured_rule(conn):
    """`12` on Bolton v Preston, 2-1: won. Same `selection._won` as the gate."""
    fid = tip(conn, "E1", "2026-08-15", 1, 2, "12")
    report = bbc_results.settle(conn, [("2026-08-15", REAL_PAGE.read_text(encoding="utf-8"))])

    row = conn.execute("SELECT outcome, pnl_best, settled_at FROM tips WHERE fixture_id=?",
                       (fid,)).fetchone()
    assert (report.full_time, report.matched, report.tips_settled) == (4, 1, 1)
    assert row["outcome"] == "win" and row["settled_at"] is not None
    assert row["pnl_best"] == pytest.approx(1.0)


def test_a_draw_loses_a_12_and_wins_a_1x(conn):
    a = tip(conn, "E1", "2026-08-15", 3, 4, "12")            # Sheff Utd 0-0 Birmingham
    pid = conn.execute("SELECT prediction_id FROM tips WHERE fixture_id=?", (a,)).fetchone()[0]
    conn.execute(   # a second rule version on the same fixture, as the schema allows
        "INSERT INTO tips (prediction_id, fixture_id, side, model_prob, floor,"
        " rule_version) VALUES (?, ?, '1X', 0.6, 0.55, 'confidence-v1')", (pid, a))
    conn.commit()
    bbc_results.settle(conn, [("2026-08-15", REAL_PAGE.read_text(encoding="utf-8"))])

    outcomes = dict(conn.execute(
        "SELECT rule_version, outcome FROM tips WHERE fixture_id=?", (a,)).fetchall())
    assert outcomes == {"confidence-v2": "lose", "confidence-v1": "win"}


def test_a_result_with_no_fixture_here_is_dropped_not_inserted(conn):
    """Reading v Luton is on the page and this store never saw the fixture.
    There can be no tip on it, and inserting a played fixture would be a
    backfill the record must never contain."""
    tip(conn, "E1", "2026-08-15", 1, 2, "12")
    report = bbc_results.settle(conn, [("2026-08-15", REAL_PAGE.read_text(encoding="utf-8"))])
    assert report.full_time == 4 and report.matched == 1
    assert conn.execute("SELECT COUNT(*) FROM fixtures").fetchone()[0] == 1


def test_a_second_pass_settles_nothing_twice(conn):
    fid = tip(conn, "E1", "2026-08-15", 1, 2, "12")
    pages = [("2026-08-15", REAL_PAGE.read_text(encoding="utf-8"))]
    bbc_results.settle(conn, pages)
    first = conn.execute("SELECT settled_at FROM tips WHERE fixture_id=?", (fid,)).fetchone()[0]

    again = bbc_results.settle(conn, pages)

    assert again.tips_settled == 0
    assert conn.execute("SELECT settled_at FROM tips WHERE fixture_id=?",
                        (fid,)).fetchone()[0] == first


def test_an_unbridged_club_is_reported_by_name(conn):
    html = page(played("bolton-wanderers", "atlantis-fc", 2, 1))
    report = bbc_results.settle(conn, [("x", html)])
    assert not report.report.clean
    assert "Atlantis Fc" in report.report.describe()


def test_a_page_with_english_fixtures_but_no_result_is_named(conn):
    """The cycle uses this to tell 'nothing played yet' from 'the source did
    not deliver' -- a past date on this list is ATTENTION."""
    html = page(event("bolton-wanderers", "preston-north-end"))     # PreEvent
    report = bbc_results.settle(conn, [("2026-08-15", html)])
    assert report.empty_pages == ["2026-08-15"]


def test_dry_run_writes_nothing(conn):
    fid = tip(conn, "E1", "2026-08-15", 1, 2, "12")
    report = bbc_results.settle(conn, [("2026-08-15", REAL_PAGE.read_text(encoding="utf-8"))],
                                dry_run=True)
    assert report.tips_settled == 1
    assert conn.execute("SELECT settled_at FROM tips WHERE fixture_id=?",
                        (fid,)).fetchone()[0] is None


# --- which dates to fetch --------------------------------------------------


def test_pending_dates_are_played_unsettled_and_recent(conn):
    tip(conn, "E1", "2026-08-15", 1, 2, "12")     # played, unsettled
    tip(conn, "E1", "2026-08-16", 3, 4, "12")     # played, unsettled
    tip(conn, "E1", "2026-08-22", 5, 6, "12")     # future
    tip(conn, "E1", "2026-08-01", 7, 8, "12")     # beyond the lookback
    settled = tip(conn, "E2", "2026-08-15", 8, 7, "12")
    conn.execute("UPDATE tips SET settled_at='x', outcome='win' WHERE fixture_id=?", (settled,))
    conn.commit()

    assert bbc_results.pending_dates(conn, "2026-08-17") == ["2026-08-15", "2026-08-16"]
    assert bbc_results.pending_dates(conn, "2026-08-14") == []
