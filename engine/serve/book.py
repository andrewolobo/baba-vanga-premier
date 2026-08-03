"""The paper book: which served predictions become bets, at what price.

    python -m engine.serve.book
    python -m engine.serve.book --dry-run

**The rule, and the one line that must never move.** A bet is worth placing when
the model's probability beats the price's break-even, where break-even is the
RAW `1/odds` -- vig-inclusive. It is not the de-vigged probability. De-vigging
tells you what the market thinks; `1/odds` tells you what you have to beat to
make money. Comparing a model probability against a de-vigged market probability
manufactures an edge equal to the bookmaker's margin, on every single bet, and
the resulting book looks profitable while losing money. `engine.eval.metrics`
does not even import `breakeven_prob`, and this module does not import
`devig_probs`, so the two cannot be crossed by accident.

Prices are taken from the **average** columns, not the maximum. The Max column
is the best price any bookmaker showed, which is frequently unobtainable and
would flatter the book. Average is conservative and it is what a bettor without
a dozen accounts actually faces. That choice biases recorded performance
*downward*, which is the safe direction for a paper book whose whole purpose is
to tell the truth about whether this works.

Nothing here is calibrated: P1 serves raw pmf probabilities and P3 does not
exist yet. So the EV figures are wrong in level. They are still worth recording,
because CLV -- the primary metric -- depends on the price taken and the closing
price, not on the model's probability being well calibrated.
"""

from __future__ import annotations

import argparse
import sqlite3

import pandas as pd

from engine import db
from engine.odds import breakeven_prob

#: Bump when the rule changes, so the book can be split by regime afterwards.
RULE_VERSION = "flat-ev-v1"

#: Flat stake. Kelly and its relatives need a calibrated probability, which
#: does not exist until P3.
STAKE = 1.0

#: Minimum edge over break-even. Not zero: uncalibrated probabilities plus a
#: ~5% overround means a zero threshold would bet almost every fixture, and a
#: book that bets everything measures nothing.
MIN_EDGE = 0.02

#: (market, side, probability column, price column). Averages only -- see the
#: module docstring on why not Max.
LEGS = (
    ("1x2", "H", "p_home", "avg_h"),
    ("1x2", "D", "p_draw", "avg_d"),
    ("1x2", "A", "p_away", "avg_a"),
    ("ou25", "over", "p_over25", "avg_over25"),
    ("ou25", "under", "p_under25", "avg_under25"),
)


def unbet_predictions(conn: sqlite3.Connection) -> pd.DataFrame:
    """Predictions with prices attached that have not yet been through the rule."""
    return pd.read_sql_query(
        "SELECT p.*, f.division, f.match_date, f.avg_h, f.avg_d, f.avg_a,"
        "       f.avg_over25, f.avg_under25,"
        "       h.canonical_name AS home_team, a.canonical_name AS away_team "
        "FROM predictions p "
        "JOIN fixtures f ON f.fixture_id = p.fixture_id "
        "JOIN teams h ON h.team_id = f.home_team_id "
        "JOIN teams a ON a.team_id = f.away_team_id "
        "WHERE NOT EXISTS (SELECT 1 FROM paper_bets b"
        "                  WHERE b.prediction_id = p.prediction_id) "
        "ORDER BY f.match_date, p.prediction_id",
        conn,
    )


def candidates(predictions: pd.DataFrame, *, min_edge: float = MIN_EDGE) -> pd.DataFrame:
    """Every leg that clears the break-even bar, one row per bet."""
    rows = []
    for row in predictions.itertuples():
        for market, side, prob_column, price_column in LEGS:
            price = getattr(row, price_column, None)
            probability = getattr(row, prob_column)
            if price is None or pd.isna(price) or price <= 1.0:
                continue
            breakeven = breakeven_prob(price)
            edge = probability - breakeven
            if edge <= min_edge:
                continue
            rows.append({
                "prediction_id": int(row.prediction_id),
                "fixture_id": int(row.fixture_id),
                "division": row.division,
                "match_date": row.match_date,
                "fixture": f"{row.home_team} v {row.away_team}",
                "market": market,
                "side": side,
                "price": float(price),
                "price_source": price_column,
                "model_prob": float(probability),
                "breakeven_prob": float(breakeven),
                "edge": float(edge),
                "expected_value": float(probability * price - 1.0),
                "stake": STAKE,
                "rule_version": RULE_VERSION,
            })
    return pd.DataFrame(rows)


def place(conn: sqlite3.Connection, bets: pd.DataFrame, *, dry_run: bool = False) -> int:
    if bets.empty:
        return 0
    if not dry_run:
        conn.executemany(
            "INSERT INTO paper_bets (prediction_id, fixture_id, market, side, price,"
            " price_source, model_prob, breakeven_prob, edge, expected_value, stake,"
            " rule_version) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [(r.prediction_id, r.fixture_id, r.market, r.side, r.price, r.price_source,
              r.model_prob, r.breakeven_prob, r.edge, r.expected_value, r.stake,
              r.rule_version) for r in bets.itertuples()],
        )
        conn.commit()
    return len(bets)


def run(conn: sqlite3.Connection, *, min_edge: float = MIN_EDGE,
        dry_run: bool = False) -> pd.DataFrame:
    bets = candidates(unbet_predictions(conn), min_edge=min_edge)
    place(conn, bets, dry_run=dry_run)
    return bets


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--min-edge", type=float, default=MIN_EDGE)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    conn = db.connect()
    db.migrate(conn)
    bets = run(conn, min_edge=args.min_edge, dry_run=args.dry_run)

    print(f"{len(bets)} bet(s) at min_edge={args.min_edge} ({RULE_VERSION}, stake {STAKE})")
    for row in bets.itertuples():
        print(f"  {row.match_date} {row.division} {row.fixture:<34} "
              f"{row.market:>4} {row.side:<5} @ {row.price:5.2f}  "
              f"model {row.model_prob:.3f} vs breakeven {row.breakeven_prob:.3f}  "
              f"edge {row.edge:+.3f}")
    if args.dry_run:
        print("(dry run -- nothing written)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
