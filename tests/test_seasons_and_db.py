"""Registry facts and database mechanics.

Includes the regression test for the numpy-to-SQLite BLOB defect, which stored
every integer column as a raw byte buffer: row counts stayed perfect and only
aggregates were wrong, so nothing surfaced it until a minutes total was checked
against a known quantity.
"""

from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd
import pytest

from engine import db, ledger
from engine.ingest.build import NUMERIC_CHECKS, validate
from engine.seasons import (
    DEV_SEASONS,
    DIVISIONS,
    HOLDOUT_SEASONS,
    SEASONS,
    crosses_regime_boundary,
    regimes_at,
    season_code,
    season_label,
    season_start_year,
)


# --- registry -------------------------------------------------------------


def test_ec_is_the_national_league_not_the_championship():
    """data/play_history/mapping.txt labels EC "Championship", duplicating E1.
    The engine never reads that file; this is the authority."""
    assert DIVISIONS["EC"].name == "National League"
    assert DIVISIONS["E1"].name == "Championship"
    assert DIVISIONS["EC"].tier > DIVISIONS["E3"].tier


def test_league_one_files_carry_a_txt_extension():
    """A *.csv glob would silently drop the entire E2 tier."""
    assert DIVISIONS["E2"].player_suffix == ".txt"
    assert DIVISIONS["E3"].player_suffix == ".csv"


def test_season_codes_round_trip():
    assert season_code(2010) == "201011"
    assert season_code(2025) == "202526"
    assert season_start_year("202526") == 2025
    assert season_label("202526") == "2025-26"


def test_dev_and_holdout_partition_the_corpus():
    assert set(DEV_SEASONS) | HOLDOUT_SEASONS == set(SEASONS)
    assert not set(DEV_SEASONS) & HOLDOUT_SEASONS
    assert HOLDOUT_SEASONS == {"202324", "202425", "202526"}


# --- regimes --------------------------------------------------------------


def test_covid_window_is_datable_because_attendance_does_not_exist():
    """The SPEC planned to detect empty stadiums from an Attendance column; that
    column is absent from all 80 files, so the regime is a date window."""
    assert "covid_empty_stadiums" in regimes_at(dt.date(2020, 6, 20))
    assert "covid_empty_stadiums" not in regimes_at(dt.date(2019, 12, 1))
    assert "covid_empty_stadiums" not in regimes_at(dt.date(2021, 9, 1))


def test_a_split_spanning_a_regime_change_is_detected():
    crossed = crosses_regime_boundary(dt.date(2020, 1, 1), dt.date(2020, 4, 1))
    assert "covid_empty_stadiums" in crossed
    assert crosses_regime_boundary(dt.date(2015, 1, 1), dt.date(2015, 6, 1)) == ()


# --- migrations -----------------------------------------------------------


def test_migrations_are_idempotent(tmp_path):
    """Applies every migration on disk once, and nothing on a second call.

    Asserted against the migrations directory rather than a hardcoded list, so
    adding a migration does not require editing this test -- and so a migration
    that silently fails to register still fails here.
    """
    from engine import config

    on_disk = sorted(p.stem for p in config.MIGRATIONS_DIR.glob("*.sql"))
    conn = db.connect(tmp_path / "m.db")
    first = db.migrate(conn)
    second = db.migrate(conn)
    assert first == on_disk
    assert second == []
    assert "001_data_spine" in on_disk  # the spine must never be renamed away
    conn.close()


# --- the BLOB regression --------------------------------------------------


@pytest.mark.parametrize(
    "value",
    [np.int64(90), np.int32(90), np.float64(1.5), np.float32(1.5), np.bool_(True)],
)
def test_numpy_scalars_store_as_numbers_not_blobs(conn, value):
    """Without an adapter, sqlite3 writes the raw 8-byte buffer as a BLOB. The
    value round-trips as bytes and SUM() silently returns 0."""
    conn.execute("CREATE TABLE t (v)")
    conn.execute("INSERT INTO t (v) VALUES (?)", (value,))
    stored_type = conn.execute("SELECT typeof(v) FROM t").fetchone()[0]
    assert stored_type in ("integer", "real")


def test_nullable_integer_columns_survive_the_round_trip(conn):
    """pandas hands out numpy scalars from every Int64 column, which is how the
    defect reached the whole corpus at once."""
    from engine.ingest.build import _rows

    frame = pd.DataFrame({"minutes": pd.array([3420, 1620, None], dtype="Int64")})
    conn.execute("CREATE TABLE t (minutes INTEGER)")
    conn.executemany("INSERT INTO t (minutes) VALUES (?)", _rows(frame, ("minutes",)))
    total = conn.execute("SELECT SUM(minutes) FROM t").fetchone()[0]
    assert total == 5040
    assert conn.execute(
        "SELECT COUNT(*) FROM t WHERE typeof(minutes) NOT IN ('integer','null')"
    ).fetchone()[0] == 0


def test_validate_reports_an_empty_store_as_failing(conn):
    """The integrity check must not pass a store it has not actually seen data
    in, or it would green-light a build that loaded nothing."""
    failures = validate(conn)
    assert failures
    assert any("expected" in f for f in failures)


def test_numeric_checks_cover_both_tables():
    assert "minutes" in NUMERIC_CHECKS["player_seasons"]
    assert "fthg" in NUMERIC_CHECKS["matches"]


# --- the duplicated-season defect -----------------------------------------


def _seed_matches(conn, rows):
    """Insert into the real migrated schema, not a convenient stand-in -- the
    point is to exercise the check the build actually runs."""
    conn.executemany("INSERT OR IGNORE INTO teams (team_id, canonical_name)"
                     " VALUES (?, ?)", [(1, "Home FC"), (2, "Away FC")])
    conn.executemany(
        "INSERT INTO matches (season, division, match_date, home_team_id,"
        " away_team_id, fthg, ftag, odds_era, source_file)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, 'market', 'test')", rows,
    )


def test_a_repeated_fixture_is_reported(conn):
    """`data/play_history/201516` was a byte-identical copy of `201415`, so the
    2015-16 season was absent and 2014-15 was counted twice.

    Every check that existed at the time passed: the per-division row counts
    were exactly right, every value was individually valid, and goals per match
    was normal. Only fixture identity catches it.
    """
    _seed_matches(conn, [
        ("201415", "E0", "2014-08-16", 1, 2, 2, 1),
        ("201516", "E0", "2014-08-16", 1, 2, 2, 1),   # the copy
    ])
    failures = validate(conn)
    assert any("appears 2 times" in f for f in failures)


def test_a_season_holding_another_seasons_dates_is_reported(conn):
    """The same defect seen from the other side, which also catches a partial
    overlap that leaves no exact duplicate fixture."""
    _seed_matches(conn, [("201516", "E0", "2014-08-16", 1, 2, 2, 1)])
    failures = validate(conn)
    assert any("outside the season window" in f for f in failures)


def test_a_correctly_dated_season_passes_the_window_check(conn):
    """Seasons legitimately span two calendar years, and 2019-20 ran to July
    2020 after the COVID suspension -- neither may be flagged."""
    _seed_matches(conn, [
        ("201516", "E0", "2015-08-08", 1, 2, 2, 1),
        ("201516", "E0", "2016-05-17", 2, 1, 0, 0),
        ("201920", "E0", "2020-07-26", 1, 2, 1, 1),
    ])
    assert not any("outside the season window" in f for f in validate(conn))


# --- ledger ---------------------------------------------------------------


def test_ledger_appends_and_counts_trials(conn):
    ledger.record(conn, kind=ledger.SWEEP, name="decay_halflife",
                  seasons=("201011",), detail={"grid": [100, 300]})
    ledger.record(conn, kind=ledger.GATE, name="h2h_pair_identity")
    ledger.record(conn, kind=ledger.HOLDOUT_UNSEAL, name="p6", reason="final read")
    # Unseals are not trials; they are the thing trials are protected from.
    assert ledger.trial_count(conn) == 2
    assert ledger.trial_count(conn, kinds=(ledger.HOLDOUT_UNSEAL,)) == 1


def test_ledger_stores_detail_as_json(conn):
    ledger.record(conn, kind=ledger.PROBE, name="dispersion", detail={"var_ratio": 0.978})
    row = conn.execute("SELECT detail FROM gate_ledger").fetchone()
    assert row["detail"] == '{"var_ratio": 0.978}'
