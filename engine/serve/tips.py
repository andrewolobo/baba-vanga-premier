"""The tip list: the model's most likely outcome, where it is confident enough.

    python -m engine.serve.tips
    python -m engine.serve.tips --floor 0.60

**This is a different rule from `book.py` and must not be confused with it.**
`book.py` bets where the model's probability beats the price's break-even — a
*value* rule, which is what makes money if the model is better than the market.
This module ignores price entirely and recommends the outcome the model thinks
most likely — a *confidence* rule, which is what produces a high strike rate.
They select almost disjoint fixtures: value lives on longshots, confidence lives
on favourites.

**The rule (v2, B8).** Outright favourite if it clears FLOOR; otherwise the
likeliest double chance that does not breach CEILING; otherwise the outright
anyway. **Every fixture gets exactly one recommendation** — v1 tipped 14.4% of
matches, this covers all of them.

**What the strike rate is and is not.** Measured on 15,824 out-of-sample dev
matches (`engine/eval/selection.py`):

    floor 0.45 -> 63.5% strike     floor 0.55 -> 72.5% strike  (shipped)
    floor 0.50 -> 69.3% strike     floor 0.60 -> 74.0% strike

Honest, out-of-sample, over eleven seasons, and every match covered. **Return is
a separate question with a different answer**, measured in `engine/eval/tips.py`
rather than assumed: at prices a customer without a dozen accounts actually
gets, the point estimate at every sellable setting is negative and no interval
excludes zero. A high strike rate is a property of short odds, not of skill, and
this module's output must never be presented as evidence of return.

**At floor 0.55 the published mix is 65% `12`, 17.6% `1X`, 11.8% `H`, 3.0% `X2`,
2.5% `A`** — so the product names a team in 14.3% of matches and says "not a
draw" in 65%. That is the owner's decision of 2026-08-06 (`BACKLOG.md` B3) and
`selection.recommend` explains why `12` dominates arithmetically.

**The model agrees with the market favourite essentially always**, so these are
not a differentiated forecast — what the model adds is that it can rank a fixture
*before* a price exists, which reading the odds cannot.
"""

from __future__ import annotations

import argparse
import sqlite3

import numpy as np
import pandas as pd

from engine import db
from engine.eval import selection

#: Bump when the rule changes, so a tip history can be split by regime. `v2`
#: is B8: the double-chance fallback replaces the outright-only rule, and the
#: two products must never be averaged into one strike rate.
RULE_VERSION = "confidence-v2"

#: The rule's two settings, measured in `engine/eval/selection.py` and chosen by
#: the owner on 2026-08-06 (`BACKLOG.md` B3).
#:
#: FLOOR 0.55 publishes a 72.5% strike rate on 100% of matches. Raising it hedges
#: more often and is right more often; 0.45 gives a balanced mix at 63.5%.
#: CEILING vetoes a fallback that would be a near-certainty. It never selects
#: across market families -- measured, a ceiling used as the selector makes
#: outrights unreachable and turns the product into a goal-line tipster.
DEFAULT_FLOOR = 0.55
DEFAULT_CEILING = 0.85

#: Prices for the outright legs. Double chance has no price in the feed; it is
#: derivable from the 1X2 prices, and `derived_price` does that.
LEGS = (
    ("H", "p_home", "max_h", "avg_h"),
    ("D", "p_draw", "max_d", "avg_d"),
    ("A", "p_away", "max_a", "avg_a"),
)

#: Which outright legs each published market is a union of.
COMPONENTS = {"H": ("H",), "D": ("D",), "A": ("A",),
              "1X": ("H", "D"), "X2": ("A", "D"), "12": ("H", "A")}


#: How far ahead of kickoff a tip may publish, in days. **0 means matchday.**
#:
#: A tip is published once and never revised -- `UNIQUE (fixture_id,
#: rule_version)`, migration 003 -- so whenever it is published is the head that
#: the customer gets. While the only fixture source was football-data's rolling
#: ~7-day window this bounded itself. `services.bbc_calendar` removed that bound,
#: and an ungated rule would lock in a call weeks early from an artifact that
#: refreezes every 7 days (`serve/cycle.py`), publishing a measurably staler
#: forecast than the one `engine/eval/selection.py` measured.
#:
#: The window is closed at both ends. The upper bound keeps the head fresh; the
#: **lower** bound stops a missed cycle publishing a call on a match that has
#: already been played, which a forward calendar makes reachable for the first
#: time. A fixture whose day is missed stays untipped, which is the same rule
#: predictions already follow (`README.md`).
PUBLISH_WITHIN_DAYS = 0

#: Served predictions for fixtures this rule has not tipped yet, joined to the
#: prices the fixture carried. Only the newest prediction per fixture is
#: considered: re-serving appends rather than overwrites, and tipping an
#: earlier row would publish a recommendation the artifact has since revised.
UNTIPPED = """
    SELECT p.prediction_id, p.fixture_id, p.p_home, p.p_draw, p.p_away,
           f.division, f.match_date,
           f.max_h, f.max_d, f.max_a, f.avg_h, f.avg_d, f.avg_a,
           h.canonical_name AS home_team, a.canonical_name AS away_team
    FROM predictions p
    JOIN fixtures f ON f.fixture_id = p.fixture_id
    JOIN teams h ON h.team_id = f.home_team_id
    JOIN teams a ON a.team_id = f.away_team_id
    WHERE p.prediction_id IN (
              SELECT MAX(prediction_id) FROM predictions GROUP BY fixture_id)
      AND NOT EXISTS (SELECT 1 FROM tips t
                      WHERE t.fixture_id = p.fixture_id AND t.rule_version = ?)
      AND f.match_date BETWEEN date('now') AND date('now', ? || ' days')
    ORDER BY f.match_date, f.fixture_id
"""


def derived_price(prices: np.ndarray, components) -> np.ndarray:
    """Fair price for a union of outright legs, from their individual prices.

    `1 / sum(1/o_i)`. Real double-chance markets carry their own margin and are
    usually **worse** than this, so a derived price is an **upper bound** on
    what a customer could actually get. It is recorded for reporting only and
    must be labelled wherever it is shown.
    """
    index = {side: i for i, (side, *_) in enumerate(LEGS)}
    with np.errstate(divide="ignore", invalid="ignore"):
        implied = sum(1.0 / prices[:, index[side]] for side in components)
        return np.where(np.isfinite(implied) & (implied > 0), 1.0 / implied, np.nan)


def select(predictions: pd.DataFrame, *, floor: float = DEFAULT_FLOOR,
           ceiling: float = DEFAULT_CEILING) -> pd.DataFrame:
    """One recommendation per fixture, per `PRODUCT.md` §3a.

    Outright favourite if it clears `floor`; otherwise the likeliest double
    chance that does not breach `ceiling`; otherwise the outright anyway. **Every
    fixture gets exactly one recommendation** -- unlike the v1 rule, which tipped
    14.4% of matches, this covers all of them.

    Price is carried for reporting only and plays no part in selection, which is
    still the whole difference from `book.py`.
    """
    for name, value in (("floor", floor), ("ceiling", ceiling)):
        if not 0.0 < value < 1.0:
            raise ValueError(f"{name} must be a probability, got {value}")

    probs = predictions[[column for _, column, _, _ in LEGS]].to_numpy(dtype=float)
    market, model_prob = selection.recommend(probs, floor, ceiling)

    best = predictions[[column for _, _, column, _ in LEGS]].to_numpy(dtype=float)
    avg = predictions[[column for _, _, _, column in LEGS]].to_numpy(dtype=float)
    out = pd.DataFrame({
        "fixture_id": predictions["fixture_id"].to_numpy(),
        "prediction_id": predictions["prediction_id"].to_numpy(),
        "side": market,
        "model_prob": model_prob,
        "rule_version": RULE_VERSION,
        "floor": floor,
        "ceiling": ceiling,
    })
    for label, prices in (("best_price", best), ("avg_price", avg)):
        out[label] = [derived_price(prices[[row]], COMPONENTS[side])[0]
                      for row, side in enumerate(market)]
    return out


def untipped(conn: sqlite3.Connection, *, rule_version: str = RULE_VERSION,
             within_days: int = PUBLISH_WITHIN_DAYS) -> pd.DataFrame:
    """Predictions eligible to be tipped now. See `PUBLISH_WITHIN_DAYS`."""
    return pd.read_sql_query(
        UNTIPPED, conn, params=[rule_version, f"+{int(within_days)}"])


def publish(conn: sqlite3.Connection, tips: pd.DataFrame, *,
            dry_run: bool = False) -> int:
    """Write the tips. `INSERT OR IGNORE`, so a re-run cannot double-publish.

    The uniqueness key does the work (migration 003): a second tip for a
    fixture already tipped under this rule is silently dropped rather than
    raising, because a cycle that has already published is a normal state to
    re-enter, not an error.
    """
    if tips.empty or dry_run:
        return 0
    cursor = conn.executemany(
        "INSERT OR IGNORE INTO tips (prediction_id, fixture_id, side, model_prob,"
        " floor, ceiling, best_price, avg_price, rule_version)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [(int(t.prediction_id), int(t.fixture_id), t.side, float(t.model_prob),
          float(t.floor), float(t.ceiling), _price(t.best_price),
          _price(t.avg_price), t.rule_version) for t in tips.itertuples()],
    )
    conn.commit()
    return cursor.rowcount


def _price(value):
    """NULL rather than NaN: the feed does not always carry a Max column, and a
    missing price must read as unknown rather than as zero."""
    return None if value is None or pd.isna(value) else float(value)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--floor", type=float, default=DEFAULT_FLOOR)
    parser.add_argument("--ceiling", type=float, default=DEFAULT_CEILING)
    parser.add_argument("--within-days", type=int, default=PUBLISH_WITHIN_DAYS,
                        help="publish window ahead of kickoff (0 = matchday)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    conn = db.connect()
    db.migrate(conn)
    predictions = untipped(conn, within_days=args.within_days)
    if predictions.empty:
        print(f"nothing untipped within {args.within_days} day(s) of kickoff "
              "-- run the serving cycle first")
        return 2

    tips = select(predictions, floor=args.floor, ceiling=args.ceiling)
    written = publish(conn, tips, dry_run=args.dry_run)
    print(f"{len(tips)} tip(s) at floor {args.floor} / ceiling {args.ceiling} "
          f"from {len(predictions)} untipped prediction(s); {written} written")
    context = predictions.set_index("fixture_id")
    for row in tips.itertuples():
        fixture = context.loc[row.fixture_id]
        print(f"  {fixture.match_date} {fixture.division} {fixture.home_team} v "
              f"{fixture.away_team}: {row.side} at {row.model_prob:.3f} "
              f"(best {row.best_price})")
    if args.dry_run:
        print("(dry run -- nothing written)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
