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


def connect(path: Path | None = None, *,
            check_same_thread: bool = True) -> sqlite3.Connection:
    """Open the database. `check_same_thread=False` is for the API only.

    FastAPI runs a sync generator dependency's setup, the endpoint body and its
    teardown as three separate threadpool hand-offs, which are not guaranteed to
    land on the same worker. So a per-request connection is routinely *created*
    on one thread and *used* on another, and sqlite3's guard rejects it --
    intermittently, only once two requests are ever in flight at the same time,
    which is why a frontend that fetched one endpoint per page never saw it.

    Relaxing the guard is safe **here and only here**: the three stages run
    strictly in sequence for one request, so no two threads touch the connection
    at once, and each request still gets its own. It is not a licence to share a
    connection between concurrent workers. Everything else -- the cycle, the
    grader, the gates -- keeps the guard, because a connection crossing threads
    anywhere else is a bug rather than a framework detail.
    """
    target = Path(path) if path is not None else config.DB_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(target, check_same_thread=check_same_thread)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    # WAL so the cycle can write while the API is reading. Under the default
    # rollback journal the two lock each other out, which is why the runbook
    # used to say "stop the API, re-run, restart it" -- an instruction nobody
    # remembers at 8am on a matchday.
    #
    # This is a property of the database file, not of the connection, so the
    # first connect converts it and the rest are no-ops. It lives here rather
    # than in a migration because a fresh checkout must get it too, before any
    # migration has run.
    #
    # Two consequences worth knowing (docs/RUNBOOK.md sec 8):
    #   - a backup must be VACUUM INTO or .backup, never a copy of the .db
    #     alone; committed transactions can still be sitting in the -wal file
    #   - WAL needs shared memory, so the database cannot live on NFS or SMB
    conn.execute("PRAGMA journal_mode = WAL")
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
