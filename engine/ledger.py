"""The append-only gate ledger.

Every gate, sweep, probe and holdout unseal run against the corpus lands here.
With a fixed 32k-row corpus the failure mode is over-fitting rather than
under-powering (SPEC §1), so the deflated-performance and PBO calculations need
a real trial count -- which only exists if every trial was recorded at the time.
gtleague had this table and let it go stale; here it is load-bearing.

Append-only by contract: there is no update or delete helper, and adding one
would defeat the purpose.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

HOLDOUT_UNSEAL = "holdout_unseal"
GATE = "gate"
SWEEP = "sweep"
PROBE = "probe"


def record(
    conn: sqlite3.Connection,
    *,
    kind: str,
    name: str,
    purpose: str | None = None,
    seasons: tuple[str, ...] | None = None,
    divisions: tuple[str, ...] | None = None,
    detail: dict[str, Any] | None = None,
    reason: str | None = None,
) -> int:
    """Append one entry. Returns its id."""
    cur = conn.execute(
        """
        INSERT INTO gate_ledger (kind, name, purpose, seasons, divisions, detail, reason)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            kind,
            name,
            purpose,
            ",".join(seasons) if seasons else None,
            ",".join(divisions) if divisions else None,
            json.dumps(detail, sort_keys=True) if detail else None,
            reason,
        ),
    )
    conn.commit()
    return int(cur.lastrowid)


def trial_count(conn: sqlite3.Connection, kinds: tuple[str, ...] = (GATE, SWEEP, PROBE)) -> int:
    """How many trials have been run against the corpus. Feeds PBO deflation."""
    marks = ",".join("?" * len(kinds))
    row = conn.execute(
        f"SELECT COUNT(*) AS n FROM gate_ledger WHERE kind IN ({marks})", kinds
    ).fetchone()
    return int(row["n"])
