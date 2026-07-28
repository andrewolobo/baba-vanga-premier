"""SQLite access and the forward-only migration runner.

Thin on purpose: a connection factory plus `migrate()`. Keeping SQL in .sql
files and access behind this module is what makes the eventual Postgres move a
connection-string change rather than a rewrite.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np

from engine import config

# sqlite3 does not recognise numpy scalars. Without these adapters it stores the
# raw 8-byte buffer as a BLOB, so the value round-trips as bytes and SUM() over
# the column silently returns 0 -- row counts still look perfect, which is what
# makes it dangerous. pandas hands out numpy scalars from every nullable-integer
# column, so this is registered once, globally, rather than at each call site.
for _np_int in (np.int8, np.int16, np.int32, np.int64):
    sqlite3.register_adapter(_np_int, int)
for _np_float in (np.float32, np.float64):
    sqlite3.register_adapter(_np_float, float)
sqlite3.register_adapter(np.bool_, int)


def connect(path: Path | None = None) -> sqlite3.Connection:
    target = Path(path) if path is not None else config.DB_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(target)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _applied(conn: sqlite3.Connection) -> set[str]:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version    TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    return {r["version"] for r in conn.execute("SELECT version FROM schema_migrations")}


def migrate(conn: sqlite3.Connection, migrations_dir: Path | None = None) -> list[str]:
    """Apply every unapplied migration in filename order. Returns those applied."""
    directory = Path(migrations_dir or config.MIGRATIONS_DIR)
    done = _applied(conn)
    newly = []
    for path in sorted(directory.glob("*.sql")):
        version = path.stem
        if version in done:
            continue
        conn.executescript(path.read_text(encoding="utf-8"))
        conn.execute("INSERT INTO schema_migrations (version) VALUES (?)", (version,))
        conn.commit()
        newly.append(version)
    return newly
