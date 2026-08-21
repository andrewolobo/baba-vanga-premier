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

**The rule (v3, B21).** Outright favourite if it clears FLOOR; otherwise the
likeliest of `1X` / `X2` / `12` / the underdog +1.5 handicap that does not
breach CEILING; otherwise the outright anyway. **Every fixture gets exactly
one recommendation.** The handicap sides are stored concretely — `H+1.5`
(home gets the start) or `A+1.5` — so a tip settles from side + final score
alone; the eval code measured them fav-relative (`D+1.5`,
`engine/eval/b21.py`) and `tests/test_v3_tips.py` pins the mapping.

**What the strike rate is and is not.** Measured on 15,824 out-of-sample dev
matches (`engine/eval/b21.py`, gate row 110, paired against v2):

    v2 (floor 0.55) -> 72.5% strike
    v3 (floor 0.55) -> 77.9% strike, +5.37 [+4.47, +6.26] paired
                       claims 76.9%: the rule under-claims by ~1 pt

Honest, out-of-sample, over nine scored seasons, every match covered. The gain
is the event being likelier, not the model being sharper — the model's edge
over the market-implied prior is unchanged (`BACKLOG.md` B21). **Return is a
separate question with a different answer**, measured in `engine/eval/tips.py`
rather than assumed: at prices a customer without a dozen accounts actually
gets, the point estimate at every sellable setting is negative and no interval
excludes zero. A high strike rate is a property of short odds, not of skill, and
this module's output must never be presented as evidence of return.

**At floor 0.55 the measured v3 mix is 63.8% handicap, 11.8% `H`, 10.2% `12`,
10.1% `1X`, 2.5% `A`, 1.5% `X2`** — the product references a team (as winner
or handicapped side) in ~90% of matches. Owner decision 2026-08-19
(`BACKLOG.md` B21, `V3_ADOPTION_PLAN.md`).

**The handicap has no price.** The feed does not carry the +1.5 line and it is
not derivable from the 1X2 legs (unlike double chance), so those tips publish
with NULL prices — settlement never needs one. The honesty check the price
would have provided is replaced by `referee_gap`: the model's claim against a
**market-implied** probability derived from the fixture's own 1X2 prices
through the same Poisson pmf (`engine/eval/b21_referee.py`, probe row 111 —
calibrated in the publication window, historical gap −0.23). It is a
reference, never a price.

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
from engine.odds import devig_probs

#: Bump when the rule changes, so a tip history can be split by regime. `v2`
#: was B8 (the double-chance fallback); `v3` is B21 (the underdog +1.5 joins
#: the fallback candidates). `/tips/record` pools the versions into its
#: headline and splits them in `by_rule` (B16, reversed 2026-08-21).
RULE_VERSION = "confidence-v3"

#: Sides with no feed price and no derivable one (`V3_ADOPTION_PLAN.md` D2).
#: They publish with NULL prices, settle regardless, and are exempt from the
#: missing-price ATTENTION in `run_cycle.step_tips` -- flagging two thirds of
#: every matchday would bury real gaps on the priced legs.
UNPRICEABLE_SIDES = frozenset({"H+1.5", "A+1.5"})

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
           p.lam_h, p.lam_a,
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
    """One recommendation per fixture, per `PRODUCT.md` §3a as amended by B21.

    Outright favourite if it clears `floor`; otherwise the likeliest of the
    three double chances and the underdog +1.5 that does not breach `ceiling`;
    otherwise the outright anyway. **Every fixture gets exactly one
    recommendation.**

    The selection is `engine.eval.b21.recommend` -- the exact function the
    gate measured -- composed, not re-implemented; the only thing added here
    is the mapping from its fav-relative `D+1.5` to the concrete side stored
    in `tips.side` (model favourite home => the away side gets the start).
    The handicap probability comes from the prediction's stored lambdas, the
    same joint the 1X2 vector was read from.

    Price is carried for reporting only and plays no part in selection, which
    is still the whole difference from `book.py`. Handicap sides have no
    price, derivable or otherwise, and carry NULL (`UNPRICEABLE_SIDES`).
    """
    # Lazy: `engine.eval.b21` pulls in the eval harness (`p7`), which imports
    # this module for COMPONENTS/derived_price. Importing at call time breaks
    # the cycle; by then this module is fully initialised.
    from engine.eval import b21
    from engine.eval.dispersion import score_matrix

    for name, value in (("floor", floor), ("ceiling", ceiling)):
        if not 0.0 < value < 1.0:
            raise ValueError(f"{name} must be a probability, got {value}")

    probs = predictions[[column for _, column, _, _ in LEGS]].to_numpy(dtype=float)
    joint = score_matrix(predictions["lam_h"].to_numpy(dtype=float),
                         predictions["lam_a"].to_numpy(dtype=float))
    p_dog15 = b21.dog15_probs(joint, probs)
    market, model_prob = b21.recommend(probs, p_dog15, floor=floor,
                                       ceiling=ceiling)
    fav_home = probs[:, 0] >= probs[:, 2]
    market = np.where(market == b21.DOG15,
                      np.where(fav_home, "A+1.5", "H+1.5"), market)

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
                      if side in COMPONENTS else np.nan
                      for row, side in enumerate(market)]
    return out


#: The referee's alert band and scope (`V3_ADOPTION_PLAN.md` D4): the probe's
#: historical mean gap of -0.23 pts plus/minus one point, on claims of 0.70
#: and up -- the region where the market-implied probability was measured
#: calibrated in every division (`BACKLOG.md` B21, probe row 111).
REFEREE_BAND = (-0.0123, 0.0077)
REFEREE_MIN_CLAIM = 0.70


def referee_gap(selected: pd.DataFrame,
                predictions: pd.DataFrame) -> tuple[int, float | None]:
    """(n, mean model − market-implied probability) for a batch's handicap tips.

    The +1.5 line has no price, so this is the honesty reference that replaces
    one: fit the market's lambdas to the fixture's devigged avg 1X2 odds and
    read the same handicap probability off the same Poisson pmf the model
    uses (`engine/eval/b21_referee.py`). **Derived from 1X2 prices — a
    reference, never a price**; it never enters selection.

    Tips below `REFEREE_MIN_CLAIM` or on fixtures without 1X2 odds are
    excluded. Returns (0, None) when nothing qualifies.
    """
    from engine.eval import b21_referee  # lazy, as in `select`
    from engine.eval.dispersion import score_matrix

    merged = selected.merge(
        predictions[["fixture_id", "avg_h", "avg_d", "avg_a"]], on="fixture_id")
    rows = merged[merged.side.isin(UNPRICEABLE_SIDES)
                  & (merged.model_prob >= REFEREE_MIN_CLAIM)
                  & merged[["avg_h", "avg_d", "avg_a"]].notna().all(axis=1)]
    if rows.empty:
        return 0, None
    q = np.column_stack(devig_probs(rows.avg_h.to_numpy(float),
                                    rows.avg_d.to_numpy(float),
                                    rows.avg_a.to_numpy(float)))
    lam_h, lam_a, _ = b21_referee.fit_market_lambdas(q[:, 0], q[:, 2])
    joint = score_matrix(lam_h, lam_a)
    n = joint.shape[1]
    margin = np.arange(n)[:, None] - np.arange(n)[None, :]
    home_by_2 = joint[:, margin >= 2].sum(axis=1)
    away_by_2 = joint[:, margin <= -2].sum(axis=1)
    implied = np.where(rows.side.to_numpy() == "H+1.5",
                       1.0 - away_by_2, 1.0 - home_by_2)
    return len(rows), float((rows.model_prob.to_numpy(float) - implied).mean())


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
