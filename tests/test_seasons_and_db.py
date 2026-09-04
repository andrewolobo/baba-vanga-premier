"""Registry facts and database mechanics.

Includes the regression tests for the missing-value round trip. Under SQLite
the defect was numpy scalars stored as raw byte buffers; under Postgres it is
a float NaN stored as a value where a NULL was meant. In both, row counts stay
perfect and only aggregates are wrong, so nothing surfaces it until a minutes
total is checked against a known quantity.
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


def test_migrations_are_idempotent(empty_database_url):
    """Applies every migration on disk once, and nothing on a second call.

    Asserted against the migrations directory rather than a hardcoded list, so
    adding a migration does not require editing this test -- and so a migration
    that silently fails to register still fails here.
    """
    from engine import config

    on_disk = sorted(p.stem for p in config.MIGRATIONS_DIR.glob("*.sql"))
    conn = db.connect(empty_database_url)
    first = db.migrate(conn)
    second = db.migrate(conn)
    assert first == on_disk
    assert second == []
    assert "001_baseline" in on_disk  # the baseline must never be renamed away
    conn.close()


# --- the missing-value regression -----------------------------------------


@pytest.mark.parametrize(
    "value",
    [np.int64(90), np.int32(90), np.float64(1.5), np.float32(1.5)],
)
def test_numpy_scalars_store_as_numbers(conn, value):
    """psycopg adapts numpy scalars natively; this pins that nothing has to be
    registered for it, since a regression would surface as a driver error at
    the first bulk insert rather than as a wrong number."""
    conn.execute("CREATE TABLE t (v DOUBLE PRECISION)")
    conn.execute("INSERT INTO t (v) VALUES (%s)", (value,))
    assert db.scalar(conn, "SELECT v FROM t") == float(value)


def test_nullable_integer_columns_survive_the_round_trip(conn):
    """pandas hands out numpy scalars and pd.NA from every Int64 column, which
    is how a missing-value defect reaches the whole corpus at once. The NA
    must land as NULL -- a NaN would count as a row and poison SUM()."""
    from engine.ingest.build import _rows

    frame = pd.DataFrame({"minutes": pd.array([3420, 1620, None], dtype="Int64")})
    conn.execute("CREATE TABLE t (minutes INTEGER)")
    conn.executemany("INSERT INTO t (minutes) VALUES (%s)", _rows(frame, ("minutes",)))
    assert db.scalar(conn, "SELECT SUM(minutes) FROM t") == 5040
    assert db.scalar(conn, "SELECT COUNT(*) FROM t WHERE minutes IS NULL") == 1


def test_a_float_nan_lands_as_null_not_as_a_value(conn):
    """Postgres will happily store NaN in a double precision column, and it
    then sorts above every number and survives AVG(). `_rows` is the one
    place frames become records, so it is where the guarantee lives."""
    from engine.ingest.build import _rows

    frame = pd.DataFrame({"avg_h": [1.5, float("nan")]})
    conn.execute("CREATE TABLE t (avg_h DOUBLE PRECISION)")
    conn.executemany("INSERT INTO t (avg_h) VALUES (%s)", _rows(frame, ("avg_h",)))
    assert db.scalar(conn, "SELECT COUNT(*) FROM t WHERE avg_h = 'NaN'::float8") == 0
    assert db.scalar(conn, "SELECT AVG(avg_h) FROM t") == 1.5


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
    conn.executemany("INSERT INTO teams (team_id, canonical_name) VALUES (%s, %s)"
                     " ON CONFLICT DO NOTHING", [(1, "Home FC"), (2, "Away FC")])
    conn.executemany(
        "INSERT INTO matches (match_id, season, division, match_date, home_team_id,"
        " away_team_id, fthg, ftag, odds_era, source_file)"
        " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'market', 'test')",
        [(f"{r[0]}:{r[1]}:{r[2]}:{r[3]}:{r[4]}", *r) for r in rows],
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


# --- settings resolution ---------------------------------------------------


def test_dotenv_parses_comments_blanks_and_quotes(tmp_path):
    from engine import config

    path = tmp_path / ".env"
    path.write_text("# a comment\n\nBVP_A=1\nBVP_B = \"two\" \nBVP_C='three'\n"
                    "not_a_pair\n", encoding="utf-8")

    assert config._dotenv(path) == {"BVP_A": "1", "BVP_B": "two", "BVP_C": "three"}


def test_a_missing_dotenv_is_not_an_error(tmp_path):
    from engine import config

    assert config._dotenv(tmp_path / "nope") == {}


def test_the_environment_beats_dotenv(monkeypatch):
    """The order that keeps the server honest: a systemd `Environment=` line
    must not be silently overridden by a stale `.env` in the checkout."""
    from engine import config

    monkeypatch.setitem(config._FILE, "BVP_THING", "from-file")
    assert config.setting("BVP_THING") == "from-file"

    monkeypatch.setenv("BVP_THING", "from-env")
    assert config.setting("BVP_THING") == "from-env"


def test_dotenv_beats_the_default(monkeypatch):
    from engine import config

    monkeypatch.delenv("BVP_THING", raising=False)
    monkeypatch.setitem(config._FILE, "BVP_THING", "from-file")
    assert config.setting("BVP_THING", "fallback") == "from-file"

    monkeypatch.delitem(config._FILE, "BVP_THING")
    assert config.setting("BVP_THING", "fallback") == "fallback"
