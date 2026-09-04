"""Guarded reads from the normalised store.

The database deliberately holds the *whole* corpus, sealed seasons included:
serving predictions for 2026-27 needs 2023-26 match data to know where teams
currently stand. That makes the store a second way into the data, so it gets
the same guard the CSV loaders have -- otherwise the seal would be enforced on
one path and open on the other, which is worse than no seal at all because it
looks safe.
"""

from __future__ import annotations

import pandas as pd

from engine import db
from engine.ingest.holdout import Corpus, Purpose, resolve_seasons
from engine.seasons import ALL_DIVISIONS


def read_matches(
    conn: db.Connection,
    *,
    purpose: Purpose = Purpose.DEV,
    seasons: tuple[str, ...] | None = None,
    divisions: tuple[str, ...] = ALL_DIVISIONS,
    unseal_reason: str | None = None,
) -> Corpus:
    resolved = resolve_seasons(
        purpose, seasons, conn=conn, unseal_reason=unseal_reason, name="store.read_matches"
    )
    frame = _select(
        conn, "matches", resolved, divisions, order="m.match_date, m.match_id",
        # Canonical names come back alongside the ids so that nothing
        # downstream has to carry the id mapping around.
        select="m.*, h.canonical_name AS home_team, a.canonical_name AS away_team",
        joins=("JOIN teams h ON h.team_id = m.home_team_id "
               "JOIN teams a ON a.team_id = m.away_team_id"),
    )
    frame["match_date"] = pd.to_datetime(frame["match_date"])
    return Corpus(frame, purpose, tuple(resolved), tuple(divisions))


def read_player_seasons(
    conn: db.Connection,
    *,
    purpose: Purpose = Purpose.DEV,
    seasons: tuple[str, ...] | None = None,
    divisions: tuple[str, ...] = ALL_DIVISIONS,
    unseal_reason: str | None = None,
) -> Corpus:
    resolved = resolve_seasons(
        purpose, seasons, conn=conn, unseal_reason=unseal_reason,
        name="store.read_player_seasons",
    )
    frame = _select(
        conn, "player_seasons", resolved, divisions, order="m.season, m.division, m.id",
        select="m.*, t.canonical_name AS team",
        joins="LEFT JOIN teams t ON t.team_id = m.team_id",
    )
    return Corpus(frame, purpose, tuple(resolved), tuple(divisions))


def _select(conn, table, seasons, divisions, *, order, select="m.*", joins=""):
    if not seasons or not divisions:
        return db.read_frame(conn, f"SELECT * FROM {table} WHERE false")
    s_marks = ",".join(["%s"] * len(seasons))
    d_marks = ",".join(["%s"] * len(divisions))
    return db.read_frame(
        conn,
        f"SELECT {select} FROM {table} m {joins} "
        f"WHERE m.season IN ({s_marks}) AND m.division IN ({d_marks}) ORDER BY {order}",
        [*seasons, *divisions],
    )
