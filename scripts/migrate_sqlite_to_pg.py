"""Move the SQLite store into Postgres, and prove the copy.

    python scripts/migrate_sqlite_to_pg.py --survey SRC.db
    python scripts/migrate_sqlite_to_pg.py --copy   SRC.db [--to URL]
    python scripts/migrate_sqlite_to_pg.py --verify SRC.db [--to URL]

`--to` defaults to `BVP_DATABASE_URL`. The target database must already exist,
created with byte-order collation so `ORDER BY` on text matches SQLite's
(docs/POSTGRES_PLAN.md, pitfall 14):

    CREATE DATABASE bvp TEMPLATE template0 LC_COLLATE 'C' LC_CTYPE 'C';

Three sub-commands, all safe to repeat:

**--survey** reads the source only. Row counts; every column whose stored
`typeof()` disagrees with its declared type (SQLite stores what it is given,
Postgres will not); NULL in a TEXT primary key (SQLite allows it, Postgres
does not); `PRAGMA foreign_key_check`; the highest id in each table. Exit 1
on anything Postgres would refuse.

**--copy** creates the schema with `db.migrate()`, then loads every table in
foreign-key order with `COPY`, ids preserved, NaN as NULL, in one transaction,
and finally advances each identity to its table's highest id so the next
insert does not collide with a copied row (pitfall 5). Refuses a target that
already holds rows. **Never copies `gate_ledger`**: the ledger's row numbers
are load-bearing and its one sanctioned loader is `scripts/export_ledger.py
--restore` (pitfall 6). **Never copies `schema_migrations`**: the SQLite rows
name files that no longer exist, and `db.migrate()` writes the baseline's
own row.

**--verify** compares source and target table by table: row count, and an
order-independent checksum over every column rendered the same way on both
sides (sorted rows, canonical text, sha256) -- so a lost row, a changed
value, a NaN where a NULL was, or a column loaded into the wrong place all
fail, and the first differing row is named. Then: no NaN in any float
column, every identity at or past its table's highest id, the target's
collation is 'C', and `schema_migrations` holds the baseline. Exit 1 on
any difference. `gate_ledger` is compared too, so a target whose ledger has
not been restored is reported as incomplete rather than passed.
"""

from __future__ import annotations

import argparse
import hashlib
import math
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import psycopg  # noqa: E402

from engine import config, db  # noqa: E402

#: Foreign-key order. `gate_ledger` and `schema_migrations` are deliberately
#: absent from the copy (module docstring); `gate_ledger` is verified.
COPY_ORDER = ("teams", "team_aliases", "matches", "player_seasons", "fixtures",
              "model_runs", "predictions", "tips", "paper_bets", "clv_grades",
              "serving_state")
VERIFY_ORDER = COPY_ORDER + ("gate_ledger",)
NOT_COPIED = ("gate_ledger", "schema_migrations")

#: SQLite declared type -> the typeof() values Postgres can accept for it.
ACCEPTABLE = {"INTEGER": {"integer", "null"},
              "REAL": {"real", "integer", "null"},
              "TEXT": {"text", "null"}}


# --- schema, read from the target ------------------------------------------


def columns(pg: db.Connection, table: str) -> list[tuple[str, str, bool]]:
    """(name, data_type, is_identity) in ordinal order, from Postgres."""
    return [(r["column_name"], r["data_type"], r["is_identity"] == "YES")
            for r in pg.execute(
                "SELECT column_name, data_type, is_identity"
                " FROM information_schema.columns"
                " WHERE table_schema = 'public' AND table_name = %s"
                " ORDER BY ordinal_position", (table,))]


def source_columns(lite: sqlite3.Connection, table: str) -> list[str]:
    return [r[1] for r in lite.execute(f"PRAGMA table_info({table})")]


def open_source(path: Path) -> sqlite3.Connection:
    """Read-only: the source is the store of record until the copy is proven."""
    if not path.exists():
        raise SystemExit(f"no such file: {path}")
    return sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)


def open_target(url: str) -> db.Connection:
    try:
        return db.connect(url)
    except psycopg.OperationalError as exc:
        raise SystemExit(f"cannot open the target {url!r}: {exc}".strip()) from None


# --- canonical rendering ------------------------------------------------------


def canonical(value, data_type: str) -> str:
    """One rendering for a value whichever engine it came from."""
    if value is None:
        return "\\N"
    if data_type == "double precision":
        return repr(float(value))
    if data_type == "integer":
        return str(int(value))
    return str(value)


def checksum(rows, types: list[str]) -> tuple[str, list[str]]:
    lines = sorted("\t".join(canonical(v, t) for v, t in zip(row, types)) for row in rows)
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()[:16], lines


# --- survey ---------------------------------------------------------------------


def survey(src: Path) -> int:
    lite = open_source(src)
    problems: list[str] = []
    print(f"survey of {src}")
    tables = [r[0] for r in lite.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name")]
    for table in tables:
        n = lite.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        info = lite.execute(f"PRAGMA table_info({table})").fetchall()
        max_id = None
        for cid, name, declared, notnull, default, pk in info:
            declared = declared.upper()
            kinds = {k: c for k, c in lite.execute(
                f"SELECT typeof({name}), COUNT(*) FROM {table} GROUP BY 1")}
            bad = {k: c for k, c in kinds.items() if k not in ACCEPTABLE.get(declared, set())}
            if bad:
                problems.append(f"{table}.{name} declared {declared} holds {bad}")
            if pk and declared == "TEXT" and kinds.get("null"):
                problems.append(f"{table}.{name} is a TEXT primary key with "
                                f"{kinds['null']} NULL(s)")
            if pk and declared == "INTEGER":
                max_id = lite.execute(f"SELECT MAX({name}) FROM {table}").fetchone()[0]
        note = "  (not copied -- see the docstring)" if table in NOT_COPIED else ""
        print(f"  {table:18s} {n:>8,} rows" + (f"  max id {max_id}" if max_id else "") + note)
    orphans = lite.execute("PRAGMA foreign_key_check").fetchall()
    if orphans:
        problems.append(f"{len(orphans)} foreign-key violation(s), first: {orphans[0]}")
    print()
    if problems:
        print("PROBLEMS Postgres would refuse:")
        for p in problems:
            print("  !", p)
        return 1
    print("clean: every stored value fits its declared type, no NULL text keys, "
          "no orphan rows")
    return 0


# --- copy -----------------------------------------------------------------------


def _nan_to_null(row):
    return tuple(None if isinstance(v, float) and math.isnan(v) else v for v in row)


def copy(src: Path, url: str) -> int:
    lite = open_source(src)
    pg = open_target(url)
    collation = db.scalar(pg, "SELECT datcollate FROM pg_database"
                              " WHERE datname = current_database()")
    if collation != "C":
        raise SystemExit(f"target collation is {collation!r}, not 'C': create the database "
                         "with LC_COLLATE 'C' (docs/POSTGRES_PLAN.md, pitfall 14)")
    applied = db.migrate(pg)
    print(f"migrations applied on the target: {applied or 'none (already current)'}")
    for table in COPY_ORDER:
        if db.scalar(pg, f"SELECT COUNT(*) FROM {table}"):
            raise SystemExit(f"refusing: target {table} already holds rows; the copy "
                             "goes into an empty store only")

    ledger_rows = lite.execute("SELECT COUNT(*) FROM gate_ledger").fetchone()[0]
    # One explicit transaction: the checks above have already opened one on
    # this connection (psycopg opens on the first statement), and a
    # `with pg.transaction()` here would only have been a savepoint inside it
    # -- which is how the first rehearsal loaded 99,408 rows and committed
    # none of them. The verifier caught it; the commit is explicit now, and
    # any exception before it closes the connection with nothing written.
    total = 0
    for table in COPY_ORDER:
        cols = columns(pg, table)
        names = [c[0] for c in cols]
        missing = [n for n in names if n not in source_columns(lite, table)]
        if missing:
            raise SystemExit(f"{table}: target columns {missing} absent from the source")
        select = f"SELECT {', '.join(names)} FROM {table}"
        with pg.cursor() as cur:
            with cur.copy(f"COPY {table} ({', '.join(names)}) FROM STDIN") as out:
                n = 0
                for row in lite.execute(select):
                    out.write_row(_nan_to_null(row))
                    n += 1
        total += n
        print(f"  {table:18s} {n:>8,} rows")
    for table in COPY_ORDER:
        for name, _type, identity in columns(pg, table):
            if identity:
                _advance(pg, table, name)
    pg.commit()
    print(f"copied {total:,} rows; identities advanced; committed")
    if ledger_rows:
        print(f"NOTE: gate_ledger holds {ledger_rows} row(s) in the source and was NOT copied. "
              "Load it with `python scripts/export_ledger.py --restore` (pitfall 6).")
    pg.close()
    return 0


def _advance(pg: db.Connection, table: str, column: str) -> None:
    """Move the identity past the highest copied id, or to the start if empty."""
    top = db.scalar(pg, f"SELECT MAX({column}) FROM {table}")
    seq = f"pg_get_serial_sequence('{table}', '{column}')"
    if top is None:
        pg.execute(f"SELECT setval({seq}, 1, false)")
    else:
        pg.execute(f"SELECT setval({seq}, %s)", (top,))


# --- verify ---------------------------------------------------------------------


def verify(src: Path, url: str) -> int:
    lite = open_source(src)
    pg = open_target(url)
    problems: list[str] = []
    print(f"verifying {url!r} against {src}")
    for table in VERIFY_ORDER:
        cols = columns(pg, table)
        names = [c[0] for c in cols]
        types = [c[1] for c in cols]
        select = f"SELECT {', '.join(names)} FROM {table}"
        s_sum, s_lines = checksum(lite.execute(select).fetchall(), types)
        with pg.cursor(row_factory=psycopg.rows.tuple_row) as cur:
            t_sum, t_lines = checksum(cur.execute(select).fetchall(), types)
        verdict = "ok" if s_sum == t_sum else "DIFFERS"
        print(f"  {table:18s} source {len(s_lines):>8,}  target {len(t_lines):>8,}  "
              f"{s_sum} / {t_sum}  {verdict}")
        if s_sum != t_sum:
            hint = (" -- run scripts/export_ledger.py --restore" if table == "gate_ledger"
                    and len(t_lines) < len(s_lines) else "")
            first = next((a for a, b in zip(s_lines, t_lines) if a != b), None)
            if first is None:
                first = (s_lines + t_lines)[min(len(s_lines), len(t_lines))] if s_lines or t_lines else ""
            problems.append(f"{table}: {len(s_lines)} vs {len(t_lines)} rows, "
                            f"first difference at {first[:120]!r}{hint}")
        for name, data_type, identity in cols:
            if data_type == "double precision":
                nan = db.scalar(pg, f"SELECT COUNT(*) FROM {table} WHERE {name} = 'NaN'::float8")
                if nan:
                    problems.append(f"{table}.{name}: {nan} NaN value(s) where NULL was meant")
            if identity:
                top = db.scalar(pg, f"SELECT MAX({name}) FROM {table}")
                last = db.scalar(pg, f"SELECT pg_sequence_last_value("
                                     f"pg_get_serial_sequence('{table}', '{name}'))")
                if top is not None and (last is None or last < top):
                    problems.append(f"{table}.{name}: identity at {last}, highest row {top} "
                                    "-- the next insert would collide")
    collation = db.scalar(pg, "SELECT datcollate FROM pg_database WHERE datname = current_database()")
    if collation != "C":
        problems.append(f"target collation is {collation!r}, not 'C'")
    if db.scalar(pg, "SELECT COUNT(*) FROM schema_migrations WHERE version = '001_baseline'") != 1:
        problems.append("schema_migrations does not record 001_baseline")
    pg.close()
    print()
    if problems:
        print("DIFFERENCES:")
        for p in problems:
            print("  !", p)
        return 1
    print("identical: every table's rows, no NaN, identities advanced, collation C, "
          "baseline recorded")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--survey", metavar="SRC.db", type=Path)
    mode.add_argument("--copy", metavar="SRC.db", type=Path)
    mode.add_argument("--verify", metavar="SRC.db", type=Path)
    parser.add_argument("--to", default=None, help="target URL (default BVP_DATABASE_URL)")
    args = parser.parse_args(argv)
    url = args.to or config.DATABASE_URL
    if args.survey:
        return survey(args.survey)
    if args.copy:
        return copy(args.copy, url)
    return verify(args.verify, url)


if __name__ == "__main__":
    raise SystemExit(main())
