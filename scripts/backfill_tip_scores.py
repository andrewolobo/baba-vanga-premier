"""Backfill tips.fthg/ftag for tips settled before migration 006 kept them.

One-off and idempotent. Re-reads the same BBC date pages
`services.bbc_results` settled those tips from, matches results to fixtures
exactly the way `settle` does (team bridge + (division, match_date, home,
away)), and fills the score ONLY where it is missing: `outcome`, `settled_at`
and both P&L columns are never touched. A stored outcome the re-read score
contradicts is reported and left alone -- the same principle as
`csv_grader.reconcile_tips` -- because a card showing a score that disagrees
with its own WON mark would be worse than showing no score.

    python -m scripts.backfill_tip_scores --dry-run   # what would be filled
    python -m scripts.backfill_tip_scores             # fill it
"""

from __future__ import annotations

import argparse

import numpy as np

from engine import db
from engine.eval import selection
from engine.ingest.teams import BridgeReport, TeamBridge
from services.bbc_calendar import _resolve_pair
from services.bbc_results import collect, parse_results


def pending_dates(conn: db.Connection) -> list[str]:
    """Dates with a settled tip that has no recorded score."""
    return [r["match_date"] for r in conn.execute(
        "SELECT DISTINCT f.match_date FROM tips t"
        " JOIN fixtures f ON f.fixture_id = t.fixture_id"
        " WHERE t.settled_at IS NOT NULL AND t.fthg IS NULL"
        " ORDER BY f.match_date")]


def backfill(conn: db.Connection, pages: list[tuple[str, str]], *,
             dry_run: bool = False) -> tuple[int, list[int]]:
    """Fill missing scores from `pages`; never touch outcome or P&L.

    Returns (filled, disagreed): tip ids whose stored outcome contradicts the
    re-read score are reported in `disagreed` and left entirely alone.
    """
    bridge = TeamBridge.load()
    ids = {row["canonical_name"]: row["team_id"]
           for row in conn.execute("SELECT team_id, canonical_name FROM teams")}
    report = BridgeReport()
    filled, disagreed = 0, []
    for _label, html in pages:
        results, _counts = parse_results(html)
        for row in results:
            resolved = _resolve_pair(row, bridge, ids, report)
            if resolved is None:
                continue
            fixture = conn.execute(
                "SELECT fixture_id FROM fixtures WHERE division=%s AND match_date=%s"
                " AND home_team_id=%s AND away_team_id=%s",
                (row["division"], row["match_date"], *resolved)).fetchone()
            if fixture is None:
                continue
            tips = conn.execute(
                "SELECT tip_id, side, outcome FROM tips"
                " WHERE fixture_id=%s AND settled_at IS NOT NULL AND fthg IS NULL",
                (fixture["fixture_id"],)).fetchall()
            for tip in tips:
                won = bool(selection.won_from_score(
                    np.array([tip["side"]]), np.array([row["fthg"]]),
                    np.array([row["ftag"]]))[0])
                if (tip["outcome"] in ("win", "lose")
                        and ("win" if won else "lose") != tip["outcome"]):
                    disagreed.append(tip["tip_id"])
                    continue
                if not dry_run:
                    conn.execute("UPDATE tips SET fthg=%s, ftag=%s WHERE tip_id=%s",
                                 (row["fthg"], row["ftag"], tip["tip_id"]))
                filled += 1
    if not dry_run:
        conn.commit()
    return filled, disagreed


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    conn = db.connect()
    db.migrate(conn)
    dates = pending_dates(conn)
    if not dates:
        print("nothing to backfill")
        return 0
    print(f"{len(dates)} date page(s): {', '.join(dates)}")
    filled, disagreed = backfill(conn, collect(dates), dry_run=args.dry_run)
    left = db.scalar(conn, "SELECT COUNT(*) FROM tips WHERE settled_at IS NOT NULL"
                           " AND fthg IS NULL")
    line = f"{filled} tip(s) filled, {left} still missing a score"
    if disagreed:
        line += f"; ATTENTION -- outcome disagreement, left alone: {disagreed}"
    print(line)
    if args.dry_run:
        print("(dry run -- nothing written)")
    return 1 if disagreed else 0


if __name__ == "__main__":
    raise SystemExit(main())
