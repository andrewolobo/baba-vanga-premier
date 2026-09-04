"""The fixtures feed client.

The live feed carries no English rows outside the season, so every test here
runs against a synthetic feed built with real football-data club names. That is
the only way to exercise the English path before the season starts -- and the
season starting is exactly when it must already work.
"""

from __future__ import annotations

import pytest

from engine import db
from services import fixture_sync

HEADER = ("Div,Date,Time,HomeTeam,AwayTeam,Referee,B365H,B365D,B365A,"
          "MaxH,MaxD,MaxA,AvgH,AvgD,AvgA,B365>2.5,B365<2.5,"
          "Max>2.5,Max<2.5,Avg>2.5,Avg<2.5,AHh,AvgAHH,AvgAHA")


def feed(*rows: str) -> str:
    return "\n".join([HEADER, *rows]) + "\n"


ARSENAL_CHELSEA = ("E0,15/08/2026,15:00,Arsenal,Chelsea,,1.80,3.60,4.50,"
                   "1.85,3.75,4.70,1.78,3.55,4.40,1.90,1.90,"
                   "1.95,1.98,1.88,1.92,-0.75,1.95,1.95")
LUTON_BARNSLEY = ("E2,15/08/2026,15:00,Luton,Barnsley,,2.10,3.30,3.40,"
                  "2.20,3.40,3.55,2.05,3.25,3.35,2.00,1.80,"
                  "2.10,1.85,2.02,1.82,-0.25,1.90,2.00")
SCOTTISH = ("SC0,15/08/2026,15:00,Celtic,Rangers,,1.50,4.00,6.00,"
            "1.55,4.20,6.50,1.48,3.95,5.90,1.70,2.10,"
            "1.75,2.20,1.68,2.12,-1.00,1.90,1.95")


@pytest.fixture
def conn(database_url):
    connection = db.connect(database_url)
    # Only the clubs these tests use need to exist.
    for i, name in enumerate(["Arsenal", "Chelsea", "Luton", "Barnsley"], start=1):
        connection.execute("INSERT INTO teams (team_id, canonical_name) VALUES (%s, %s)",
                           (i, name))
    connection.commit()
    return connection


# --- parsing ---------------------------------------------------------------


def test_parses_english_rows_and_ignores_other_countries():
    rows = fixture_sync.parse(feed(ARSENAL_CHELSEA, SCOTTISH, LUTON_BARNSLEY))
    assert [r["division"] for r in rows] == ["E0", "E2"]
    assert rows[0]["home"] == "Arsenal"
    assert rows[0]["match_date"] == "2026-08-15"
    assert rows[0]["kickoff_time"] == "15:00"
    assert rows[0]["avg_h"] == 1.78
    assert rows[0]["avg_over25"] == 1.88
    assert rows[0]["ah_line"] == -0.75


def test_accepts_both_date_forms_the_feed_has_used():
    """The feed has published dd/mm/yy and dd/mm/yyyy in different eras, and
    mixes them across divisions within one file."""
    assert fixture_sync._iso_date("15/08/2026") == "2026-08-15"
    assert fixture_sync._iso_date("15/08/26") == "2026-08-15"
    assert fixture_sync._iso_date("7/8/26") == "2026-08-07"


def test_missing_odds_become_none_rather_than_zero():
    """A fixture published before prices are up must not read as odds of 0.0,
    which would make every bet look infinitely valuable."""
    row = ("E0,15/08/2026,15:00,Arsenal,Chelsea,,,,,"
           ",,,,,,,,,,,,,,")
    parsed = fixture_sync.parse(feed(row))[0]
    assert parsed["avg_h"] is None
    assert parsed["avg_over25"] is None


def test_rows_without_teams_are_skipped():
    assert fixture_sync.parse(feed("E0,15/08/2026,15:00,,,,,,,,,,,,,,,,,,,,,")) == []


# --- upsert behaviour ------------------------------------------------------


def test_inserts_new_fixtures(conn):
    report = fixture_sync.sync(conn, feed(ARSENAL_CHELSEA, LUTON_BARNSLEY), "test")
    assert (report.inserted, report.updated) == (2, 0)
    assert report.report.clean
    stored = conn.execute("SELECT * FROM fixtures ORDER BY division").fetchall()
    assert [r["division"] for r in stored] == ["E0", "E2"]
    assert stored[0]["avg_h"] == 1.78


def test_republished_fixtures_update_prices_without_duplicating(conn):
    """The feed republishes the same fixture daily with fresh prices. That is
    the normal path, not an error, and it must not create a second row."""
    fixture_sync.sync(conn, feed(ARSENAL_CHELSEA), "day1")
    moved = ARSENAL_CHELSEA.replace("1.78,3.55,4.40", "1.65,3.80,5.20")
    report = fixture_sync.sync(conn, feed(moved), "day2")

    assert (report.inserted, report.updated) == (0, 1)
    rows = conn.execute("SELECT * FROM fixtures").fetchall()
    assert len(rows) == 1
    assert rows[0]["avg_h"] == 1.65
    assert rows[0]["source_file"] == "day2"


def test_first_seen_is_preserved_across_updates(conn):
    """When we first saw a price is the interesting question for any later
    information-set argument, so an update must not reset it."""
    fixture_sync.sync(conn, feed(ARSENAL_CHELSEA), "day1")
    first_seen = db.scalar(conn, "SELECT first_seen_at FROM fixtures")
    conn.execute("UPDATE fixtures SET first_seen_at = '2000-01-01 00:00:00'")
    conn.commit()

    fixture_sync.sync(conn, feed(ARSENAL_CHELSEA), "day2")
    row = conn.execute("SELECT first_seen_at, updated_at FROM fixtures").fetchone()
    assert row["first_seen_at"] == "2000-01-01 00:00:00"
    assert row["updated_at"] != row["first_seen_at"]
    assert first_seen is not None


def test_a_blank_time_does_not_erase_a_known_kickoff(conn):
    """The merge hazard a second fixture source creates.

    `services.bbc_calendar` publishes a kickoff for every match; this feed omits
    `Time` on some rows. A plain assignment would blank the known value the
    moment the feed republished the fixture without one.
    """
    fixture_sync.sync(conn, feed(ARSENAL_CHELSEA), "day1")
    timeless = ARSENAL_CHELSEA.replace("15/08/2026,15:00,", "15/08/2026,,")
    fixture_sync.sync(conn, feed(timeless), "day2")

    row = conn.execute("SELECT kickoff_time, avg_h FROM fixtures").fetchone()
    assert row["kickoff_time"] == "15:00"
    assert row["avg_h"] == 1.78, "prices must still update normally"


def test_a_withdrawn_price_is_still_written_as_null(conn):
    """The other half of the same rule. A price the feed has stopped carrying is
    real news -- unlike a missing kickoff, it must not be preserved."""
    fixture_sync.sync(conn, feed(ARSENAL_CHELSEA), "day1")
    pulled = ARSENAL_CHELSEA.replace(",1.78,3.55,4.40,", ",,,,")
    fixture_sync.sync(conn, feed(pulled), "day2")

    assert conn.execute("SELECT avg_h FROM fixtures").fetchone()["avg_h"] is None


def test_dry_run_writes_nothing(conn):
    report = fixture_sync.sync(conn, feed(ARSENAL_CHELSEA), "test", dry_run=True)
    assert report.inserted == 1
    assert db.scalar(conn, "SELECT COUNT(*) FROM fixtures") == 0


# --- the bridge ------------------------------------------------------------


def test_an_unknown_club_is_excluded_by_name_and_counted(conn):
    """SPEC §0.2: never silently drop. On this feed it should never fire, so if
    it does, a club from outside the corpus has been promoted into E0-E3.

    'Truro City' is used rather than a real short name because the bridge holds
    every club that has appeared in E0-EC since 2010 -- including ones far below
    the Football League -- so most plausible-sounding names actually resolve.
    """
    unknown = ARSENAL_CHELSEA.replace("Chelsea", "Truro City")
    report = fixture_sync.sync(conn, feed(unknown), "test")

    assert report.inserted == 0
    assert not report.report.clean
    assert ("football-data", "Truro City") in report.report.misses
    assert "Truro City" in report.report.describe()
    assert db.scalar(conn, "SELECT COUNT(*) FROM fixtures") == 0


def test_a_bridged_fixture_survives_alongside_an_unbridged_one(conn):
    """One bad name must not cost the whole matchday."""
    report = fixture_sync.sync(
        conn, feed(ARSENAL_CHELSEA, LUTON_BARNSLEY.replace("Barnsley", "Truro City")), "test")
    assert report.inserted == 1
    assert len(report.report.misses) == 1


def test_a_club_in_the_bridge_but_missing_from_teams_is_reported_not_crashed(conn):
    """`teams` is built from the bridge, so this should be impossible -- but an
    unhandled KeyError here would take the sync down on a matchday morning, and
    'impossible' states are exactly the ones that arrive unannounced.

    'Barnet' is in the alias table (it has played in the National League) but is
    not in this test's `teams` table, which reproduces the split precisely.
    """
    report = fixture_sync.sync(conn, feed(ARSENAL_CHELSEA.replace("Chelsea", "Barnet")), "test")
    assert report.inserted == 0
    assert ("football-data", "Barnet") in report.report.misses
