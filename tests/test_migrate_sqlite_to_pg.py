"""The SQLite -> Postgres copier (docs/POSTGRES_PLAN.md Phase B).

The one script that moves production data, so every claim its docstring makes
is pinned here: the survey names what Postgres would refuse, the copy preserves
ids and advances identities, refuses a non-empty or wrongly-collated target and
never touches the ledger, and the verifier fails on a changed value, a NaN, a
missing ledger and a lagging identity -- not just on a row count.
"""

from __future__ import annotations

import importlib.util
import math
import sqlite3
from pathlib import Path

import pytest

from engine import config, db

SQLITE_TYPE = {"integer": "INTEGER", "double precision": "REAL", "text": "TEXT"}


def _module():
    path = config.REPO_ROOT / "scripts" / "migrate_sqlite_to_pg.py"
    spec = importlib.util.spec_from_file_location("migrate_sqlite_to_pg", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


migrate = _module()


@pytest.fixture
def source(tmp_path, conn):
    """A SQLite store with exactly the Postgres schema's tables and columns,
    built from `information_schema` so the two cannot drift, holding a few
    rows with the shapes that matter: explicit ids with a gap, an integer
    stored in a REAL column, NULLs, and the old migration rows."""
    path = tmp_path / "src.db"
    lite = sqlite3.connect(path)
    for table in migrate.VERIFY_ORDER + ("schema_migrations",):
        cols = migrate.columns(conn, table)
        key = [r["column_name"] for r in conn.execute(
            "SELECT kcu.column_name FROM information_schema.table_constraints tc"
            " JOIN information_schema.key_column_usage kcu"
            "   ON kcu.constraint_name = tc.constraint_name"
            " WHERE tc.table_name = %s AND tc.constraint_type = 'PRIMARY KEY'"
            " ORDER BY kcu.ordinal_position", (table,))]
        lite.execute(f"CREATE TABLE {table} ("
                     + ", ".join(f"{n} {SQLITE_TYPE[t]}" for n, t, _ in cols)
                     + f", PRIMARY KEY ({', '.join(key)}))")
    lite.executemany("INSERT INTO teams VALUES (?, ?)", [(1, "Luton"), (2, "Barnsley")])
    lite.executemany("INSERT INTO team_aliases VALUES (?, ?, ?)",
                     [("football-data", "Luton", 1), ("fbref", "Luton Town", 1)])
    lite.execute(
        "INSERT INTO matches (match_id, season, division, match_date, home_team_id,"
        " away_team_id, fthg, ftag, avg_h, odds_era, source_file)"
        " VALUES ('202526:E2:2026-08-15:1:2', '202526', 'E2', '2026-08-15', 1, 2, 2, 0,"
        " 2, 'market', 't')")                                   # avg_h = 2, an INTEGER in a REAL column
    lite.executemany(
        "INSERT INTO fixtures (fixture_id, division, match_date, home_team_id,"
        " away_team_id, avg_h, first_seen_at, updated_at, source_file)"
        " VALUES (?, 'E2', ?, 1, 2, ?, '2026-08-10 06:00:00', '2026-08-10 06:00:00', 't')",
        [(1, "2026-08-15", 1.9), (7, "2026-08-22", None)])     # a gap in the ids
    lite.execute(
        "INSERT INTO model_runs VALUES ('v3', '2026-08-10 06:00:00', '2026-08-10T00:00:00',"
        " 'H400/a0.1', 13946, 151, 'abc', NULL)")
    lite.execute(
        "INSERT INTO predictions (prediction_id, fixture_id, served_at, model_version,"
        " information_set, lam_h, lam_a, p_home, p_draw, p_away, p_over25, p_under25,"
        " calibrated) VALUES (3, 7, '2026-08-11 06:00:123456', 'v3', 'pre_close',"
        " 1.5, 1.1, 0.5, 0.25, 0.25, 0.5, 0.5, 0)")
    lite.execute(
        "INSERT INTO tips (tip_id, prediction_id, fixture_id, published_at, side,"
        " model_prob, floor, ceiling, rule_version) VALUES (5, 3, 7,"
        " '2026-08-11 06:00:01', 'A+1.5', 0.79, 0.55, 0.85, 'confidence-v3')")
    lite.execute(
        "INSERT INTO serving_state (state_id, created_at, cycle_label, model_version,"
        " fixtures_seen, predictions_written, bets_written, rule_version)"
        " VALUES (1, '2026-08-11 06:00:02', '2026-08-11', 'v3', 2, 1, 0, 'book-off')")
    lite.executemany("INSERT INTO schema_migrations VALUES (?, '2026-08-01 00:00:00')",
                     [("001_data_spine",), ("002_serving",)])
    lite.commit()
    lite.close()
    return path


def _ledger_row(path: Path) -> None:
    lite = sqlite3.connect(path)
    lite.execute("INSERT INTO gate_ledger (id, created_at, kind, name, detail)"
                 " VALUES (110, '2026-08-19 10:00:00', 'gate', 'b21_dog15', '{\"arms\": []}')")
    lite.commit()
    lite.close()


# --- survey ---------------------------------------------------------------------


def test_survey_passes_a_clean_source(source, capsys):
    assert migrate.survey(source) == 0
    assert "clean" in capsys.readouterr().out


def test_survey_names_a_value_postgres_would_refuse(source, capsys):
    lite = sqlite3.connect(source)
    lite.execute("UPDATE matches SET fthg = 'two'")           # SQLite keeps the text
    lite.execute("INSERT INTO model_runs (model_version, created_at, fitted_at,"
                 " config_label, n_train, n_teams, corpus_digest)"
                 " VALUES (NULL, 'x', 'x', 'x', 1, 1, 'd')")   # NULL in a TEXT primary key
    lite.commit()
    assert migrate.survey(source) == 1
    out = capsys.readouterr().out
    assert "matches.fthg declared INTEGER holds {'text': 1}" in out
    assert "model_runs.model_version is a TEXT primary key with 1 NULL" in out


# --- copy and verify -------------------------------------------------------------


def test_copy_preserves_ids_and_the_next_insert_does_not_collide(source, empty_database_url):
    assert migrate.copy(source, empty_database_url) == 0
    assert migrate.verify(source, empty_database_url) == 0

    pg = db.connect(empty_database_url)
    assert [r["fixture_id"] for r in pg.execute("SELECT fixture_id FROM fixtures ORDER BY 1")] == [1, 7]
    assert db.scalar(pg, "SELECT avg_h FROM matches") == 2.0
    assert db.scalar(pg, "SELECT served_at FROM predictions") == "2026-08-11 06:00:123456"
    assert db.scalar(pg, "SELECT COUNT(*) FROM schema_migrations") == 1, "the SQLite rows are not copied"
    new_id = db.scalar(pg, "INSERT INTO fixtures (division, match_date, home_team_id,"
                           " away_team_id, source_file) VALUES ('E2', '2026-08-29', 2, 1, 't')"
                           " RETURNING fixture_id")
    assert new_id == 8, "the identity must start past the highest copied id"
    pg.close()


def test_copy_refuses_a_target_that_already_holds_rows(source, empty_database_url):
    assert migrate.copy(source, empty_database_url) == 0
    with pytest.raises(SystemExit, match="already holds rows"):
        migrate.copy(source, empty_database_url)


def test_copy_refuses_a_target_without_byte_order_collation(source, pg_admin):
    """A locale-collated database would order text differently from SQLite
    (pitfall 14). The default collation is the server's; where that is
    already 'C' there is nothing to refuse and the test says so."""
    default = pg_admin.execute(
        "SELECT datcollate FROM pg_database WHERE datname = 'template1'").fetchone()[0]
    if default == "C":
        pytest.skip("this server's default collation is already 'C'")
    name = "bvp_test_locale_collated"
    pg_admin.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
    pg_admin.execute(f'CREATE DATABASE "{name}" TEMPLATE template0')
    try:
        from psycopg.conninfo import make_conninfo
        from tests.conftest import TEST_DATABASE_URL
        with pytest.raises(SystemExit, match="collation"):
            migrate.copy(source, make_conninfo(TEST_DATABASE_URL, dbname=name))
    finally:
        pg_admin.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')


def test_the_ledger_is_never_copied_and_verify_says_so(source, empty_database_url, capsys):
    _ledger_row(source)
    assert migrate.copy(source, empty_database_url) == 0
    assert "gate_ledger holds 1 row(s) in the source and was NOT copied" in capsys.readouterr().out
    pg = db.connect(empty_database_url)
    assert db.scalar(pg, "SELECT COUNT(*) FROM gate_ledger") == 0
    pg.close()

    assert migrate.verify(source, empty_database_url) == 1
    out = capsys.readouterr().out
    assert "gate_ledger: 1 vs 0 rows" in out and "--restore" in out


def test_verify_fails_on_a_changed_value_not_just_a_lost_row(source, empty_database_url, capsys):
    migrate.copy(source, empty_database_url)
    pg = db.connect(empty_database_url)
    pg.execute("UPDATE tips SET model_prob = 0.78 WHERE tip_id = 5")
    pg.commit()
    pg.close()
    assert migrate.verify(source, empty_database_url) == 1
    assert "tips: 1 vs 1 rows, first difference" in capsys.readouterr().out


def test_verify_fails_on_a_nan_and_on_a_lagging_identity(source, empty_database_url, capsys):
    migrate.copy(source, empty_database_url)
    pg = db.connect(empty_database_url)
    pg.execute("INSERT INTO fixtures (fixture_id, division, match_date, home_team_id,"
               " away_team_id, avg_h, source_file) VALUES (9, 'E2', '2026-09-05', 1, 2,"
               " %s, 't')", (math.nan,))
    pg.execute("SELECT setval(pg_get_serial_sequence('fixtures', 'fixture_id'), 1)")
    pg.commit()
    pg.close()
    assert migrate.verify(source, empty_database_url) == 1
    out = capsys.readouterr().out
    assert "fixtures.avg_h: 1 NaN value(s)" in out
    assert "fixtures.fixture_id: identity at 1, highest row 9" in out


def test_the_source_is_opened_read_only(source):
    lite = migrate.open_source(source)
    with pytest.raises(sqlite3.OperationalError, match="readonly"):
        lite.execute("DELETE FROM teams")
