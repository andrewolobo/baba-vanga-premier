"""Postgres access and the forward-only migration runner.

Thin on purpose: a connection factory, three query helpers and `migrate()`.
SQL stays in the callers and in db/migrations/*.sql; nothing here knows what a
tip or a fixture is. Moved from SQLite on the plan in docs/POSTGRES_PLAN.md.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

import pandas as pd
import psycopg
from psycopg.rows import dict_row, tuple_row
from psycopg.types.numeric import FloatLoader

from engine import config

#: The store keeps timestamps as UTC text, 'YYYY-MM-DD HH:MM:SS' (plan
#: decision D3). This is that as a SQL expression -- what `datetime('now')`
#: was -- for column defaults and for the graders' `settled_at`.
NOW_TEXT = "to_char(now() AT TIME ZONE 'UTC', 'YYYY-MM-DD HH24:MI:SS')"


class Connection(psycopg.Connection):
    """psycopg's connection plus `executemany`.

    psycopg keeps `executemany` on the cursor; the callers were written against
    sqlite3, where it lives on the connection. One method here is cheaper than
    a cursor at every bulk insert, and keeps the call sites saying what they
    mean.
    """

    def executemany(self, query: str, params_seq) -> int:
        """Returns the rows affected over the whole batch, as sqlite3's cursor
        did -- `ON CONFLICT DO NOTHING` inserts count only what landed."""
        with self.cursor() as cur:
            cur.executemany(query, params_seq)
            return cur.rowcount


def connect(url: str | None = None, *, autocommit: bool = False) -> Connection:
    """Open the database at `url` (default `BVP_DATABASE_URL`).

    Rows come back as dicts, so `row["column"]` works everywhere; positional
    access does not -- use `scalar()` for a one-value query.

    Three things are fixed per connection rather than left to the server:

    - **Timezone UTC**, passed as a startup option so it is outside any
      transaction and cannot be undone by a rollback. Every stored timestamp
      and every `today()` comparison is UTC (docs/DEPLOY.md 3.8), and the
      server's zone must not be able to move them.
    - **`numeric` loads as float.** `AVG()` and `SUM(...) * 1.0` return
      `numeric`, which psycopg hands back as `Decimal`; the callers, the JSON
      encoder and pandas all want a float. Registered here once, for the same
      reason the numpy adapters used to be: a driver quirk fixed at one site
      rather than at every call.
    - **numpy scalars** adapt natively in psycopg 3, so nothing is registered
      for them any more. `np.bool_` becomes a real boolean, which Postgres
      will not put in a numeric column -- the strictness is the point.

    `autocommit=True` is for the read-only API: without it psycopg opens a
    transaction on the first statement of any kind, including a SELECT, and a
    per-request connection would sit *idle in transaction* until closed.
    Everything that writes keeps the default and commits explicitly.
    """
    conn = Connection.connect(
        url or config.DATABASE_URL,
        row_factory=dict_row,
        autocommit=autocommit,
        options="-c timezone=UTC",
    )
    conn.adapters.register_loader("numeric", FloatLoader)
    return conn


def scalar(conn: Connection, sql: str, params=()) -> Any:
    """The single value of a one-row, one-column query, or None for no row."""
    row = conn.execute(sql, params).fetchone()
    return None if row is None else next(iter(row.values()))


def read_frame(conn: Connection, sql: str, params=()) -> pd.DataFrame:
    """A query as a DataFrame, columns named from the cursor.

    Replaces `pd.read_sql_query`, which supports only SQLAlchemy connectables
    and sqlite3 and routes anything else through an untested fallback. An
    empty result still carries its column names.
    """
    with conn.cursor(row_factory=tuple_row) as cur:
        cur.execute(sql, params)
        columns = [d.name for d in cur.description]
        return pd.DataFrame.from_records(cur.fetchall(), columns=columns)


def today() -> str:
    """Today's date in UTC as ISO text -- what SQLite's `date('now')` was.

    Dates are stored as text and compared as text, so the bound has to be
    text too, and it has to be UTC whatever the process's local zone is.
    """
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")


def _applied(conn: Connection) -> set[str]:
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version    TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT {NOW_TEXT}
        )
        """
    )
    conn.commit()
    return {r["version"] for r in conn.execute("SELECT version FROM schema_migrations")}


def migrate(conn: Connection, migrations_dir: Path | None = None) -> list[str]:
    """Apply every unapplied migration in filename order. Returns those applied.

    Each file and its `schema_migrations` row commit together. DDL is
    transactional in Postgres, so a migration that fails halfway leaves
    nothing behind -- neither the tables it made nor a row claiming it ran.
    """
    directory = Path(migrations_dir or config.MIGRATIONS_DIR)
    done = _applied(conn)
    newly = []
    for path in sorted(directory.glob("*.sql")):
        version = path.stem
        if version in done:
            continue
        conn.execute(path.read_text(encoding="utf-8"))
        conn.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (version,))
        conn.commit()
        newly.append(version)
    return newly
