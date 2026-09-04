"""P5 meta-label: the §1 grounding, as committed code.

    python -m engine.eval.meta

Recomputes every number in `docs/P5_META_PLAN.md` §1 — the measurements the
plan was designed around, taken before any arm was fitted — and checks each one
against the value the document publishes.

**This exists because the plan's §1 was prose with nothing behind it.** The same
defect is on the record twice: `CHANNELS.md` §7's row 53, whose pre-gate was
never committed and is now unresolvable, and `OUTSTANDING.md` §8.2's launch bar,
which stated a vig no code computed. §1.5 is load-bearing — it inverted this
project's prior about power and changed the plan — so leaving it unreproducible
would put the design of P5 in the position row 53 is in.

**No match outcome is read, at any stage.** Not `fthg`, `ftag` or `ftr`, and not
by the arms either: CLV is a function of two prices, so the target the arms fit
is itself outcome-free. Realised ROI is what would need an outcome, and §2.3
makes that reported-not-selected-on, which this module does not compute at all.
`drop_outcomes` removes every post-kickoff column from the frame everything here
works on, so that is a property of the data rather than a claim about the code.

The grounding stage carries no arm list and spends no configuration. **The arms
stage does**: four configurations, declared against §5's budget of twelve.

CLV per leg, the one definition here that is genuinely new:

    clv = devig_probs(closing Pinnacle price) - breakeven_prob(Max price taken)

The two sides are deliberately different conversions, and OUTSTANDING §7.4 is
why that is correct rather than the bug it resembles. The bet side is a price
actually paid, so it is raw `1/odds`; the close side is the market's opinion, so
it is normalised. Mixing them is what makes the three legs of a match sum to
minus the Max overround — §1.4's arithmetic, and the reason a meta-label can
only earn its keep by ranking.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import replace

import numpy as np
import pandas as pd

from engine import db, ledger, store
from engine.eval import bootstrap, metrics, trials
from engine.eval import rest as rest_mod
from engine.eval import travel as travel_mod
from engine.eval.p1 import BASE, served
from engine.eval.walkforward import walk_forward
from engine.odds import breakeven_prob, devig_probs, vig_per_leg
from engine.seasons import DEV_SEASONS, SERVED_DIVISIONS
from services.stadium_coords.reconcile import haversine_km

#: The frozen head, as `travel.py`, `rest.py` and `tod.py` pin it.
HEAD = replace(BASE, half_life=400.0, alpha=0.1, shots_blend=0.3,
               embargo_regimes=("covid_empty_stadiums",))

#: 1X2: de-vigged Pinnacle close as the anchor, best-available Max as the price
#: taken. O/U: market-average close, Max price. `p3.py` uses the same two closing
#: bases; the price side differs because P5 §2 is Max-only.
CLOSE_1X2 = ["close_ps_h", "close_ps_d", "close_ps_a"]
PRICE_1X2 = ["max_h", "max_d", "max_a"]
CLOSE_OU = ["close_avg_over25", "close_avg_under25"]
PRICE_OU = ["max_over25", "max_under25"]

CONSENSUS_1X2 = ["avg_h", "avg_d", "avg_a"]
SHARP_1X2 = ["ps_h", "ps_d", "ps_a"]

#: Everything only knowable after kickoff. Dropped from the frame the whole
#: module works on, so "no outcome is read" is a property of the data rather
#: than a claim about the code -- a later edit that reaches for `ftr` gets a
#: KeyError instead of quietly turning the grounding into the gate.
OUTCOME_COLUMNS = (
    "fthg", "ftag", "ftr", "hthg", "htag", "htr",
    "home_shots", "away_shots", "home_sot", "away_sot",
    "home_corners", "away_corners", "home_fouls", "away_fouls",
    "home_yellow", "away_yellow", "home_red", "away_red", "referee",
)

#: Volume fractions in §1.5's stratum table.
STRATA = (1.00, 0.25, 0.10, 0.05, 0.02)

PRICE_FAMILIES = {
    "max": PRICE_1X2, "avg": CONSENSUS_1X2, "ps": SHARP_1X2,
    "b365": ["b365_h", "b365_d", "b365_a"],
}

# --- §4's feature sets -----------------------------------------------------
#
# `SHARED` is in every arm including the negative control, and it is not in
# either of §4's two lists. The three legs of a match are not exchangeable --
# measured on the basis, mean CLV is -0.00204 (H), -0.00258 (D), -0.00114 (A)
# and the draw leg's sd is less than half the home leg's -- so an arm holding
# the side indicator has a structural advantage over one that does not, and
# `MODEL - BOOK` would then be reading which list it was filed under. Giving it
# to both is the only neutral choice; giving it to neither throws away the
# structure every arm needs to rank within a match at all.
SHARED = ("is_draw", "is_away")

#: BOOK is **one price level plus spreads**, not four levels. Measured on the
#: basis, the four bookmakers' break-even probabilities correlate at 0.997-0.999
#: and a design matrix of the levels has condition number 2e15 -- singular to
#: working precision, so the fit would be reporting arithmetic noise. One level
#: (the price actually taken) plus each other book's spread from consensus
#: carries the same information at condition 2.8. §4 lists "Max, consensus,
#: sharp, their spreads, overround"; this is that list with the redundancy the
#: data showed removed, and it was chosen on conditioning alone, before any
#: target was fitted.
BOOK_FEATURES = ("be_max", "sharp_spread", "max_spread", "b365_spread",
                 "or_max", "or_avg", "or_ps")

MODEL_FEATURES = ("m_prob", "edge", "lam_total", "lam_margin", "entropy",
                  "rest_home", "rest_away", "distance")

#: Contextual blocks §4 files under MODEL. Kept separate only so `noise_block`
#: can match MODEL's continuous dimensionality without duplicating dummies.
CONTEXT_FEATURES = tuple(f"div_{d}" for d in SERVED_DIVISIONS[1:]) + \
    tuple(f"mon_{m}" for m in range(2, 13))

NOISE_FEATURES = tuple(f"noise_{i}" for i in range(len(MODEL_FEATURES)))

FEATURE_SETS = {
    "BOOK": SHARED + BOOK_FEATURES,
    "MODEL": SHARED + MODEL_FEATURES + CONTEXT_FEATURES,
    "FULL": SHARED + BOOK_FEATURES + MODEL_FEATURES + CONTEXT_FEATURES,
    "NOISE": SHARED + BOOK_FEATURES + NOISE_FEATURES,
    # A selector with no price information at all. NOISE contains every BOOK
    # feature, so it answers "do eight useless columns change anything" -- the
    # right control for MODEL - BOOK, and the wrong one for "is BOOK's level
    # real". BLIND answers that one: it should land at the pinned mean, and if
    # it does not, the harness is manufacturing edge and no level here means
    # anything. SHARED stays in because it is in every arm; it carries only
    # which of H/D/A a leg is.
    "BLIND": SHARED + NOISE_FEATURES,
}

#: Seasons of price history behind the first fit. Three, as `p3.py`'s
#: `BURN_IN_SEASONS` -- the only other CLV harness in the project.
MIN_TRAIN_SEASONS = 3

#: Volume the decision is read at. §7's prediction 3 is stated at the top
#: decile, so it is pre-committed here rather than chosen from the results;
#: the other strata are reported and decide nothing.
SELECTION_FRACTION = 0.10
REPORT_FRACTIONS = (0.25, 0.10, 0.05, 0.02)

#: A week too thin to take a decile from is skipped rather than rounded up to
#: its single best leg, which would make thin weeks the loudest.
MIN_WEEK_LEGS = 20

#: §6's criterion 2: selected-volume CLV must beat the Max vig, not zero.
#: `CALIBRATION.md` §1 set this bar after "CLV >= 0" passed two losing strata.
MAX_VIG = 0.00201

NOISE_SEED = 20260806
#: Two disjoint streams. They must not collide: the reference arm's "random"
#: prediction and the control's synthetic target are both standard normals of
#: the same length, so a shared seed makes the reference an exact oracle on the
#: target and the control reads backwards. That happened once here, and the
#: symptom was a control that passed 5/6 while reporting a negative mean lift.
PLANT_SEED = 20260807
REFERENCE_SEED = 20270807

#: §5's positive control. The planted edge sits on a stratum MODEL can see and
#: BOOK cannot, so recovery tests the instrument end to end -- and BOOK's
#: failure to find it is a free second reading. Scaled as `travel.py` does, with
#: the zero arm carrying the false-positive rate.
PLANT_SCALES = (0.0, 0.5, 1.0, 2.0)
PLANT_AS_SPECIFIED = 2      # index of the 1.0 row -- the plan's stop condition
PLANT_DRAWS = 6
#: Size of the planted edge at scale 1.0, in CLV. Chosen so that a perfectly
#: recovered stratum clears §6's bar: the pinned mean is -0.00192, so an edge of
#: 0.005 lands selected volume at ~+0.0031 against the 0.00201 the rule needs.
PLANT_EDGE = 0.005
#: The stratum carrying it: the top fifth of `lam_total`. An indicator, per §5's
#: "a known stratum" -- deliberately not a linear effect, so the control tests a
#: linear family's ability to rank a step it cannot represent exactly.
PLANT_QUANTILE = 0.80

#: Every number `P5_META_PLAN.md` §1 publishes, so a re-run checks the document
#: rather than merely recomputing it. Tolerance is one unit in the last printed
#: place: these are read off a table, not asserted to machine precision.
PUBLISHED = {
    "g2.matches_1x2": (19884, 1),
    "g2.legs_1x2": (59652, 1),
    "g2.matches_ou": (5638, 1),
    "g2.legs_ou": (11276, 1),
    "g3.vig_1x2_avg": (0.02107, 5e-6),
    "g3.vig_1x2_max": (0.00201, 5e-6),
    "g3.vig_ou_avg": (0.03041, 5e-6),
    "g3.vig_ou_max": (0.00718, 5e-6),
    "g4.match_sum_mean": (-0.00577, 5e-6),
    "g4.match_sum_sd": (0.00923, 5e-6),
    "g4.every_leg_return": (-0.00192, 5e-6),
    "g5.sd_clv": (0.02220, 5e-6),
    "g5.n_blocks": (408, 1),
    "g5.block_se": (0.00006, 5e-6),
    "g5.naive_se": (0.00009, 5e-6),
    "g5.design_effect": (0.68, 5e-3),
    "g6.coverage_ps": (99.8, 0.05),
    "g6.coverage_kickoff": (28.3, 0.05),
}


def load(conn) -> pd.DataFrame:
    return store.read_matches(conn, seasons=DEV_SEASONS).for_measurement()


def drop_outcomes(frame: pd.DataFrame) -> pd.DataFrame:
    """Remove every post-kickoff column.

    The enforcement is the removal itself: a later edit that reaches for `ftr`
    raises KeyError rather than quietly turning the grounding into the gate,
    which has a pre-registered budget this is not part of.
    """
    return frame.drop(columns=[c for c in OUTCOME_COLUMNS if c in frame.columns])


# --- the basis, once -------------------------------------------------------


def scored_corpus(frame: pd.DataFrame) -> pd.DataFrame:
    """Served divisions, COVID embargoed, walk-forward lambda attached.

    The lambdas come from the frozen head, which was of course fitted on goals;
    what `drop_outcomes` guarantees is that no outcome enters a statistic *here*,
    so nothing in this module spends information about the answer P5 asks.
    """
    return drop_outcomes(served(walk_forward(frame, HEAD)))


def clv_basis(scored: pd.DataFrame) -> pd.DataFrame:
    """The 1X2 rows gradable against the close at a price P5 would have taken.

    Both sides are required: a close with no Max price cannot be graded, and a
    Max price with no close has nothing to be graded against.
    """
    ok = scored[CLOSE_1X2 + PRICE_1X2].notna().all(axis=1)
    return scored[ok].reset_index(drop=True)


def clv_legs(basis: pd.DataFrame) -> tuple[np.ndarray, pd.Series]:
    """(matches x 3) CLV, and the match date each row belongs to."""
    close = np.column_stack(devig_probs(*[basis[c].to_numpy() for c in CLOSE_1X2]))
    paid = breakeven_prob(basis[PRICE_1X2].to_numpy())
    return close - paid, basis["match_date"]


# --- G1: is the training basis clean? (§1.1) -------------------------------


def g1_training_basis(conn) -> dict:
    """§3.8's survivorship loop cannot exist if the book has never run."""
    counts = {t: db.scalar(conn, f"SELECT COUNT(*) FROM {t}")
              for t in ("predictions", "paper_bets", "clv_grades")}
    out = {"counts": counts, "all_empty": all(v == 0 for v in counts.values())}
    print("\nG1  training basis (§1.1)")
    for table, n in counts.items():
        print(f"  {table:12s} {n}")
    print(f"  all empty: {out['all_empty']} -- 'all leans, never surfaced picks' "
          f"holds by construction" if out["all_empty"] else
          "  NOT EMPTY -- the basis is no longer reconstructible from a replay")
    return out


# --- G2: the gradable sample, by market (§1.2) -----------------------------


def g2_gradable(scored: pd.DataFrame) -> dict:
    ok_ou = scored[CLOSE_OU + PRICE_OU].notna().all(axis=1)
    basis = clv_basis(scored)
    ou = scored[ok_ou]

    out = {
        "scored_matches": int(len(scored)),
        "matches_1x2": int(len(basis)), "legs_1x2": int(3 * len(basis)),
        "matches_ou": int(len(ou)), "legs_ou": int(2 * len(ou)),
        "seasons_1x2": [str(basis.season.min()), str(basis.season.max())],
        "seasons_ou": [str(ou.season.min()), str(ou.season.max())],
        "by_division_1x2": {str(d): int(n) for d, n
                            in basis.groupby("division").size().items()},
    }
    print(f"\nG2  CLV-gradable sample (§1.2), from {len(scored):,} scored matches")
    print(f"  1X2  {out['matches_1x2']:,} matches / {out['legs_1x2']:,} legs "
          f"({out['seasons_1x2'][0]} -> {out['seasons_1x2'][1]})")
    print(f"  O/U  {out['matches_ou']:,} matches / {out['legs_ou']:,} legs "
          f"({out['seasons_ou'][0]} -> {out['seasons_ou'][1]})")
    print("  1X2 by division: " + " / ".join(
        f"{d} {n:,}" for d, n in sorted(out["by_division_1x2"].items())))
    return out


def g2_published_division_basis(frame: pd.DataFrame) -> dict:
    """Where §1.2's published division row actually came from.

    Its cells sum to 22,113 against a scored corpus of 21,896, so they cannot be
    a subset of the gradable sample — they are price availability alone, on the
    corpus *before* the COVID embargo and before a walk-forward lambda is
    required. Recomputed here so the discrepancy is attributable rather than
    merely noted, and so a reader of the document can see which of the two
    numbers answers which question.
    """
    e0e3 = frame[frame["division"].isin(SERVED_DIVISIONS)]
    ok = e0e3[CLOSE_1X2 + PRICE_1X2].notna().all(axis=1)
    counts = e0e3[ok].groupby("division").size().to_dict()
    out = {"by_division": {k: int(v) for k, v in counts.items()},
           "total": int(ok.sum())}
    cells = " / ".join(f"{d} {n:,}" for d, n in sorted(out["by_division"].items()))
    print(f"  [published row was priced-only, no embargo and no lambda: "
          f"{cells} = {out['total']:,}]")
    return out


# --- G3: what a leg has to beat (§1.3) -------------------------------------


def g3_vig(scored: pd.DataFrame) -> dict:
    """`engine.odds.vig_per_leg` on the all-scored corpus.

    Same basis as `OUTSTANDING.md` §8.2's first row, deliberately: §1.3's table
    quotes that row, so re-deriving it here on the narrower CLV basis would
    produce a document that disagrees with the one it cites.
    """
    markets = {
        "1x2_avg": CONSENSUS_1X2, "1x2_max": PRICE_1X2,
        "ou_avg": ["avg_over25", "avg_under25"], "ou_max": PRICE_OU,
    }
    out = {}
    print(f"\nG3  vig per leg (§1.3), all scored (n={len(scored):,})")
    for name, cols in markets.items():
        vig = vig_per_leg(*[scored[c].to_numpy() for c in cols])
        out[f"vig_{name}"] = round(vig, 5)
        out[f"overround_{name}"] = round(vig * len(cols), 5)
        print(f"  {name:8s} overround {100 * vig * len(cols):5.2f}%   "
              f"vig/leg {vig:.5f}")
    return out


# --- G4: the mean is pinned (§1.4) -----------------------------------------


def g4_pinned_mean(basis: pd.DataFrame) -> dict:
    """The finding that makes ranking the only thing a meta-label can sell."""
    clv, _ = clv_legs(basis)
    per_match = clv.sum(axis=1)
    out = {
        "match_sum_mean": round(float(per_match.mean()), 5),
        "match_sum_sd": round(float(per_match.std(ddof=1)), 5),
        "every_leg_return": round(float(clv.mean()), 5),
    }
    print("\nG4  the pinned mean (§1.4)")
    print(f"  three legs sum to {out['match_sum_mean']:+.5f} "
          f"(sd {out['match_sum_sd']:.5f}) -- the Max overround, mechanically")
    print(f"  betting every leg returns {out['every_leg_return']:+.5f}/leg "
          f"by construction")
    return out


# --- G5: power (§1.5) ------------------------------------------------------


def g5_power(basis: pd.DataFrame) -> dict:
    """Block-bootstrap SE of mean CLV, and what it implies for thin strata.

    The stratum rows scale the full-sample SE by sqrt(1/f) rather than measuring
    a subsample, which is what §1.5's table does. `one_leg_design_effect` is the
    check that scaling is not flattering itself: the design effect below 1 comes
    from the three legs of a match being anti-correlated, and a real selection
    takes one leg per match, where that cancellation is unavailable.
    """
    clv, dates = clv_legs(basis)
    legs = clv.reshape(-1, order="F")
    leg_dates = pd.concat([dates] * 3, ignore_index=True)
    blocks = bootstrap.week_blocks(leg_dates)

    sd = float(legs.std(ddof=1))
    block_se = bootstrap.standard_error(legs, blocks)
    naive_se = float(sd / np.sqrt(len(legs)))

    # One leg per match, chosen without reference to anything: the design
    # effect a stratum of selected volume would actually face.
    rng = np.random.default_rng(20260806)
    pick = rng.integers(0, 3, len(clv))
    single = clv[np.arange(len(clv)), pick]
    s_blocks = bootstrap.week_blocks(dates)
    s_block_se = bootstrap.standard_error(single, s_blocks)
    s_naive = float(single.std(ddof=1)) / np.sqrt(len(single))

    one_leg_deff = s_block_se / s_naive
    out = {
        "n_legs": int(len(legs)), "n_blocks": int(len(np.unique(blocks))),
        "sd_clv": round(sd, 5),
        "block_se": round(block_se, 5), "naive_se": round(naive_se, 5),
        "design_effect": round(block_se / naive_se, 2),
        "one_leg_design_effect": round(one_leg_deff, 2),
        "strata": [{"fraction": f, "legs": int(len(legs) * f),
                    "half_width": round(1.96 * block_se / np.sqrt(f), 5),
                    "half_width_one_leg":
                        round(1.96 * one_leg_deff * naive_se / np.sqrt(f), 5)}
                   for f in STRATA],
    }
    print(f"\nG5  power (§1.5): {out['n_legs']:,} legs in {out['n_blocks']} "
          f"ISO-week blocks, sd {sd:.5f}")
    print(f"  block SE {block_se:.6f} vs naive {naive_se:.6f} "
          f"-- design effect {out['design_effect']}, blocking TIGHTENS it")
    print(f"    {'stratum':>9}  {'legs':>7}  {'as published':>12}  "
          f"{'one leg/match':>13}")
    for row in out["strata"]:
        print(f"    {row['fraction']*100:8.0f}%  {row['legs']:7,}  "
              f"{row['half_width']:12.5f}  {row['half_width_one_leg']:13.5f}")
    print(f"  [check] one leg per match, where the within-match cancellation is "
          f"unavailable: design effect {out['one_leg_design_effect']} vs "
          f"{out['design_effect']} -- the right-hand column is what a real "
          f"selection faces")
    return out


# --- G6: features (§1.6) ---------------------------------------------------


def g6_features(basis: pd.DataFrame) -> dict:
    """Coverage of every candidate feature, and the most informative one."""
    families = {
        "avg": CONSENSUS_1X2, "max": PRICE_1X2, "ps": SHARP_1X2,
        "b365": ["b365_h", "b365_d", "b365_a"], "lambda": ["lam_h", "lam_a"],
        "kickoff": ["kickoff_time"],
    }
    out = {"coverage": {}}
    print(f"\nG6  feature coverage (§1.6) on {len(basis):,} matches")
    for name, cols in families.items():
        pct = round(100 * float(basis[cols].notna().all(axis=1).mean()), 1)
        out["coverage"][name] = pct
        note = "   <- excluded by §4, would restrict the gate to 2019-20+" \
            if name == "kickoff" else ""
        print(f"  {name:8s} {pct:5.1f}%{note}")

    ok = basis[SHARP_1X2 + CONSENSUS_1X2].notna().all(axis=1)
    s = basis[ok]
    spread = (breakeven_prob(s[SHARP_1X2].to_numpy())
              - breakeven_prob(s[CONSENSUS_1X2].to_numpy()))
    out["spread"] = {
        "n": int(len(s)),
        "all_legs_mean": round(float(spread.mean()), 5),
        "all_legs_sd": round(float(spread.std(ddof=1)), 5),
        "by_leg": {leg: [round(float(spread[:, i].mean()), 5),
                         round(float(spread[:, i].std(ddof=1)), 5)]
                   for i, leg in enumerate(("H", "D", "A"))},
    }
    print(f"  sharp-vs-consensus 1/ps - 1/avg, n={len(s):,}: "
          f"{out['spread']['all_legs_mean']:+.5f} "
          f"(sd {out['spread']['all_legs_sd']:.5f}) over all legs")
    for leg, (m, sdev) in out["spread"]["by_leg"].items():
        print(f"    {leg}  {m:+.5f} (sd {sdev:.5f})")
    return out


# --- the reproduction check ------------------------------------------------


def check_published(results: dict) -> dict:
    """Every §1 value this run can confirm, against what the document says."""
    actual = {
        "g2.matches_1x2": results["g2"]["matches_1x2"],
        "g2.legs_1x2": results["g2"]["legs_1x2"],
        "g2.matches_ou": results["g2"]["matches_ou"],
        "g2.legs_ou": results["g2"]["legs_ou"],
        "g3.vig_1x2_avg": results["g3"]["vig_1x2_avg"],
        "g3.vig_1x2_max": results["g3"]["vig_1x2_max"],
        "g3.vig_ou_avg": results["g3"]["vig_ou_avg"],
        "g3.vig_ou_max": results["g3"]["vig_ou_max"],
        "g4.match_sum_mean": results["g4"]["match_sum_mean"],
        "g4.match_sum_sd": results["g4"]["match_sum_sd"],
        "g4.every_leg_return": results["g4"]["every_leg_return"],
        "g5.sd_clv": results["g5"]["sd_clv"],
        "g5.n_blocks": results["g5"]["n_blocks"],
        "g5.block_se": results["g5"]["block_se"],
        "g5.naive_se": results["g5"]["naive_se"],
        "g5.design_effect": results["g5"]["design_effect"],
        "g6.coverage_ps": results["g6"]["coverage"]["ps"],
        "g6.coverage_kickoff": results["g6"]["coverage"]["kickoff"],
    }
    rows, failed = [], []
    for key, (published, tol) in PUBLISHED.items():
        got = actual[key]
        # `bool(...)`, not the bare comparison: a numpy scalar anywhere upstream
        # makes this np.bool, which the ledger's json.dumps refuses.
        ok = bool(abs(got - published) <= tol)
        rows.append({"key": key, "published": published, "measured": got, "ok": ok})
        if not ok:
            failed.append(key)

    print("\nReproduction of P5_META_PLAN.md §1")
    for row in rows:
        print(f"  {'ok ' if row['ok'] else 'XX '} {row['key']:22s} "
              f"published {row['published']:<10} measured {row['measured']}")
    print(f"  {len(rows) - len(failed)}/{len(rows)} reproduce")
    return {"rows": rows, "all_reproduce": not failed, "failed": failed}


# === THE ARMS (§4) =========================================================
#
# Everything below fits something. Everything above does not.


def build_legs(conn) -> pd.DataFrame:
    """One row per 1X2 leg, with every §4 feature attached.

    Rest is computed on the **full fixture list** before the walk-forward drops
    burn-in matches, per `rest.load`'s warning: computing it on the scored frame
    would measure the gap to the previous *scored* match and silently lengthen
    rest wherever the harness removed a fixture that was really played.
    """
    raw = load(conn)
    basis = clv_basis(scored_corpus(raw))

    rest = rest_mod.attach_rest(raw)[["match_id", "rest_home", "rest_away"]]
    matches = basis.merge(rest, on="match_id", how="left")
    coords = travel_mod.load_stadiums()
    matches["distance"] = [
        haversine_km(coords[h], coords[a]) if h in coords and a in coords else np.nan
        for h, a in zip(matches.home_team, matches.away_team)]

    # `notna` is not enough: five b365 rows carry a price of 0, which survives a
    # null check and becomes an infinity on conversion. Filter on the converted
    # value, which is what the model actually sees.
    prices = {name: breakeven_prob(matches[cols].to_numpy(dtype=float))
              for name, cols in PRICE_FAMILIES.items()}
    usable = np.ones(len(matches), dtype=bool)
    for value in prices.values():
        usable &= np.isfinite(value).all(axis=1)
    usable &= matches[["rest_home", "rest_away", "distance",
                       "lam_h", "lam_a"]].notna().all(axis=1).to_numpy()

    m = matches[usable].reset_index(drop=True)
    be = {name: breakeven_prob(m[cols].to_numpy(dtype=float))
          for name, cols in PRICE_FAMILIES.items()}
    model = metrics.model_probs(m.lam_h, m.lam_a)[["p_h", "p_d", "p_a"]].to_numpy()
    close = np.column_stack(devig_probs(*[m[c].to_numpy() for c in CLOSE_1X2]))
    entropy = -(model * np.log(np.clip(model, 1e-12, 1))).sum(axis=1)

    n = len(m)
    tile = lambda v: np.tile(np.asarray(v, dtype=float), 3)   # noqa: E731
    stack = lambda a: a.reshape(-1, order="F")                # noqa: E731
    side = np.repeat(np.arange(3), n)

    legs = pd.DataFrame({
        "match_id": np.tile(m.match_id.to_numpy(), 3),
        "season": np.tile(m.season.to_numpy(), 3),
        "division": np.tile(m.division.to_numpy(), 3),
        "match_date": pd.concat([m.match_date] * 3, ignore_index=True),
        "side": np.array(["H", "D", "A"])[side],
        "clv": stack(close - be["max"]),
        # --- shared structural block, in every arm (see SHARED) -------------
        "is_draw": (side == 1).astype(float), "is_away": (side == 2).astype(float),
        # --- BOOK ----------------------------------------------------------
        "be_max": stack(be["max"]),
        "sharp_spread": stack(be["ps"] - be["avg"]),
        "max_spread": stack(be["max"] - be["avg"]),
        "b365_spread": stack(be["b365"] - be["avg"]),
        "or_max": tile(be["max"].sum(axis=1)),
        "or_avg": tile(be["avg"].sum(axis=1)),
        "or_ps": tile(be["ps"].sum(axis=1)),
        # --- MODEL ---------------------------------------------------------
        "m_prob": stack(model),
        "edge": stack(model - be["max"]),
        "lam_total": tile(m.lam_h + m.lam_a),
        "lam_margin": tile(m.lam_h - m.lam_a),
        "entropy": tile(entropy),
        "rest_home": tile(m.rest_home), "rest_away": tile(m.rest_away),
        "distance": tile(m.distance),
    })
    legs["week"] = bootstrap.week_blocks(legs["match_date"])
    legs["month"] = legs["match_date"].dt.month
    for division in SERVED_DIVISIONS[1:]:      # E0 is the reference level
        legs[f"div_{division}"] = (legs["division"] == division).astype(float)
    for month in range(2, 13):                 # January is the reference level
        legs[f"mon_{month}"] = (legs["month"] == month).astype(float)
    legs = legs.sort_values(["match_date", "match_id"]).reset_index(drop=True)
    return noise_block(legs)


def noise_block(legs: pd.DataFrame, seed: int = NOISE_SEED) -> pd.DataFrame:
    """§5's planted negative: MODEL's dimensionality, none of its information.

    `OUTSTANDING.md` §1.7 established that a *positive* result needs a planted
    negative exactly as a null needs a planted positive — adding any predictor
    improves an in-sample fit, and a walk-forward only bounds that. This block
    is drawn independently of every match, so whatever it appears to gain over
    BOOK is the instrument talking rather than the data.
    """
    rng = np.random.default_rng(seed)
    out = legs.copy()
    for i, name in enumerate(MODEL_FEATURES):
        # Matched to the real feature's first two moments, so the negative
        # control differs from MODEL in information and in nothing else.
        column = legs[name].to_numpy(dtype=float)
        out[f"noise_{i}"] = rng.normal(column.mean(), column.std(), len(legs))
    return out


def _design(legs: pd.DataFrame, features: tuple[str, ...]) -> np.ndarray:
    return legs[list(features)].to_numpy(dtype=float)


def walk_forward_predict(legs: pd.DataFrame, features: tuple[str, ...],
                         target: np.ndarray) -> np.ndarray:
    """Out-of-sample prediction per leg: refit weekly on strictly earlier weeks.

    Weekly to match the head's own cadence, expanding rather than rolling, and
    held back until `MIN_TRAIN_SEASONS` distinct seasons are behind the cutoff
    so the first fits are not extrapolating from a single season's price regime.

    `lstsq` rather than a normal-equation solve because FULL is **exactly**
    rank-deficient: `edge = m_prob - be_max`, so BOOK ∪ MODEL contains a linear
    dependence by construction. The pseudo-inverse leaves the fitted *values*
    well defined even where the coefficients are not, and only fitted values are
    ever used — the arms are compared by ranking, never by coefficient.
    """
    X = _design(legs, features)
    weeks = legs["week"].to_numpy()
    seasons = legs["season"].to_numpy()
    out = np.full(len(legs), np.nan)

    for week in np.unique(weeks):
        train = weeks < week
        if len(np.unique(seasons[train])) < MIN_TRAIN_SEASONS:
            continue
        test = weeks == week
        # Standardised on the training fold only. Scale-free for lstsq, but it
        # keeps the SVD well conditioned and means no test-fold moment ever
        # touches the fit.
        mu, sd = X[train].mean(axis=0), X[train].std(axis=0)
        sd = np.where(sd > 0, sd, 1.0)
        z_train = np.column_stack([np.ones(train.sum()), (X[train] - mu) / sd])
        beta, *_ = np.linalg.lstsq(z_train, target[train], rcond=None)
        z_test = np.column_stack([np.ones(test.sum()), (X[test] - mu) / sd])
        out[test] = z_test @ beta
    return out


def select(legs: pd.DataFrame, prediction: np.ndarray,
           fraction: float = SELECTION_FRACTION) -> np.ndarray:
    """Top `fraction` of each week's legs by predicted CLV.

    Per week rather than pooled, for two reasons. A pooled threshold is a
    function of predictions from the whole period, including weeks that had not
    happened — mild lookahead, and avoidable for nothing. And per-week selection
    puts constant volume in every block, which is the unit both the paired
    bootstrap and CSCV resample.
    """
    chosen = np.zeros(len(legs), dtype=bool)
    scored = np.isfinite(prediction)
    for week in np.unique(legs.loc[scored, "week"]):
        rows = np.flatnonzero(scored & (legs["week"].to_numpy() == week))
        if len(rows) < MIN_WEEK_LEGS:
            continue
        k = max(1, int(round(fraction * len(rows))))
        chosen[rows[np.argsort(-prediction[rows])[:k]]] = True
    return chosen


def leg_values(legs: pd.DataFrame, chosen: np.ndarray, target: np.ndarray,
               fraction: float = SELECTION_FRACTION) -> np.ndarray:
    """Per-leg contribution to selected-volume mean CLV.

    `clv * 1[selected] / fraction`, defined on **every** scored leg rather than
    only on the selected ones. That is what makes two arms comparable at all:
    they select different legs, so a mean over each arm's own selection is not a
    paired statistic, and convention 3 forbids reaching for the marginal error
    instead. Averaged over all legs this equals the mean CLV on the selection,
    and the difference between two arms is a per-leg paired difference the block
    bootstrap can take directly.
    """
    scored = np.isfinite(target) & _scored_mask(legs)
    value = np.where(chosen, target, 0.0) / fraction
    return np.where(scored, value, np.nan)


def _scored_mask(legs: pd.DataFrame) -> np.ndarray:
    return legs["_scored"].to_numpy(dtype=bool)


def score_arm(legs: pd.DataFrame, features: tuple[str, ...],
              target: np.ndarray, fraction: float = SELECTION_FRACTION) -> dict:
    """Fit, select, and reduce one arm to what §6 needs to read."""
    prediction = walk_forward_predict(legs, features, target)
    legs = legs.copy()
    legs["_scored"] = np.isfinite(prediction)
    chosen = select(legs, prediction, fraction)
    values = leg_values(legs, chosen, target, fraction)
    ok = np.isfinite(values)
    return {"prediction": prediction, "chosen": chosen, "values": values,
            "scored": ok, "n_scored": int(ok.sum()), "n_selected": int(chosen.sum()),
            "mean_clv_selected": float(np.nanmean(target[chosen])) if chosen.any()
            else float("nan"),
            "mean_clv_all": float(np.nanmean(target[ok]))}


def weekly_performance(legs: pd.DataFrame, arms: dict) -> pd.DataFrame:
    """weeks x arms, mean CLV on that week's selection. Higher is better.

    The natural input shape for `trials.cscv_pbo`, and the same week blocking
    the paired bootstrap uses, so the dependence structure is respected by both.
    """
    weeks = legs["week"].to_numpy()
    rows = {}
    for name, arm in arms.items():
        by_week = {}
        for week in np.unique(weeks[arm["chosen"]]):
            sel = arm["chosen"] & (weeks == week)
            by_week[week] = float(np.nanmean(arm["values"][sel] * SELECTION_FRACTION))
        rows[name] = by_week
    return pd.DataFrame(rows).dropna()


def _random_arm(legs: pd.DataFrame, target: np.ndarray, scored: np.ndarray,
                rng: np.random.Generator, fraction: float) -> np.ndarray:
    """Selection at the same volume, carrying no information. The bar.

    Random selection's expected CLV is the pinned mean of §1.4, so an arm that
    beats it has ranked. Comparing against it rather than against the all-leg
    mean keeps the statistic paired and at identical volume.
    """
    prediction = np.where(scored, rng.normal(size=len(legs)), np.nan)
    work = legs.copy()
    work["_scored"] = scored
    chosen = select(work, prediction, fraction)
    return leg_values(work, chosen, target, fraction)


def p5_control(legs: pd.DataFrame) -> dict:
    """§5's positive control. Runs first, runs alone, and can stop the gate.

    A planted CLV edge on a stratum only MODEL can see, at four sizes including
    zero. `P4_TRAVEL_PLAN.md` §5's stop condition applies: if the instrument
    cannot recover the effect the plan is designed to detect, no arm runs on
    real targets and the finding is "this corpus cannot answer it" -- a
    different result from a null, with a different action.

    Synthetic targets carry no information about the real answer, so this stage
    spends no configuration, exactly as `travel.py`'s `h34_travel_power` does.
    """
    print("\nP5-CONTROL  planted CLV edge on the top "
          f"{100*(1-PLANT_QUANTILE):.0f}% of lam_total (§5)")
    stratum = (legs["lam_total"].to_numpy()
               >= legs["lam_total"].quantile(PLANT_QUANTILE))
    grounding = g5_reference(legs)
    print(f"  stratum is {100*stratum.mean():.1f}% of legs; noise sd "
          f"{grounding['sd']:.5f} about a pinned mean of {grounding['mean']:+.5f}")

    rows = []
    for scale in PLANT_SCALES:
        detected, deltas = 0, []
        for draw in range(PLANT_DRAWS):
            rng = np.random.default_rng(PLANT_SEED + 1000 * draw)
            target = rng.normal(grounding["mean"], grounding["sd"], len(legs)) \
                + PLANT_EDGE * scale * stratum
            arm = score_arm(legs, FEATURE_SETS["MODEL"], target)
            reference = _random_arm(legs, target, arm["scored"],
                                    np.random.default_rng(REFERENCE_SEED + draw),
                                    SELECTION_FRACTION)
            ok = arm["scored"] & np.isfinite(reference)
            blocks = bootstrap.week_blocks(legs.loc[ok, "match_date"])
            # Sign convention: bootstrap.paired reads losses, so CLV is negated.
            cmp = bootstrap.paired(-arm["values"][ok], -reference[ok], blocks)
            deltas.append(-cmp.delta)
            if cmp.delta < 0 and cmp.ci[1] < 0:
                detected += 1
        # What perfect ranking could achieve, so recovery is quantitative and
        # not just a sign test. Selection takes the top decile; the planted
        # stratum is `share` of legs and the random reference picks it at rate
        # `share`, so a perfect arm lifts by delta * (1 - share).
        ceiling = PLANT_EDGE * scale * (1.0 - float(stratum.mean()))
        rows.append({"scale": scale, "planted": round(PLANT_EDGE * scale, 5),
                     "detected": detected, "draws": PLANT_DRAWS,
                     "ceiling": round(ceiling, 5),
                     "recovery": round(float(np.mean(deltas)) / ceiling, 3)
                     if ceiling else None,
                     "mean_lift": round(float(np.mean(deltas)), 5),
                     # Per draw, not just the mean: one anomalous draw hiding
                     # inside an average is how the seed collision above stayed
                     # invisible until the mean disagreed with the count.
                     "lifts": [round(float(d), 5) for d in deltas]})
        pct = f"{100*np.mean(deltas)/ceiling:5.0f}% of ceiling" if ceiling else ""
        print(f"  scale {scale:4.2f}  planted {PLANT_EDGE*scale:.5f}  "
              f"recovered {detected}/{PLANT_DRAWS}  mean lift "
              f"{np.mean(deltas):+.5f}  {pct}")

    as_specified = rows[PLANT_AS_SPECIFIED]
    null_row = rows[0]
    out = {"rows": rows, "stratum_share": round(float(stratum.mean()), 4),
           "passed": bool(as_specified["detected"] >= 5 and null_row["detected"] <= 1)}
    print(f"  false positives at scale 0: {null_row['detected']}/{PLANT_DRAWS}")
    print(f"  CONTROL {'PASSED' if out['passed'] else 'FAILED'} -- "
          + ("the arms may run on real targets"
             if out["passed"] else "P5_META_PLAN §5 says STOP; no arm runs"))
    return out


def g5_reference(legs: pd.DataFrame) -> dict:
    """The mean and sd the synthetic target is built to match."""
    clv = legs["clv"].to_numpy()
    return {"mean": float(clv.mean()), "sd": float(clv.std(ddof=1))}


def p5_arms(legs: pd.DataFrame) -> dict:
    """§4's three arms plus §5's negative control, on the real CLV target."""
    target = legs["clv"].to_numpy()
    print(f"\nP5-ARMS  {len(legs):,} legs, top-{100*SELECTION_FRACTION:.0f}% "
          f"weekly selection, bar = Max vig {MAX_VIG:.5f}")

    arms = {name: score_arm(legs, features, target)
            for name, features in FEATURE_SETS.items()}
    scored = arms["BOOK"]["scored"]
    for arm in arms.values():
        scored &= arm["scored"]
    print(f"  scored out of sample: {int(scored.sum()):,} legs "
          f"({legs.loc[scored, 'season'].min()} -> {legs.loc[scored, 'season'].max()})")

    blocks = bootstrap.week_blocks(legs.loc[scored, "match_date"])
    rows = []
    for name, arm in arms.items():
        selected = arm["chosen"] & scored
        mean_clv = float(target[selected].mean())
        pinned = float(target[scored].mean())
        rows.append({
            "arm": name, "n_features": len(FEATURE_SETS[name]),
            "selected": int(selected.sum()),
            "mean_clv_selected": round(mean_clv, 5),
            # Against random selection at the same volume, whose expectation is
            # the pinned mean of §1.4. An arm below this has not ranked at all.
            "lift_over_random": round(mean_clv - pinned, 5),
            "clears_vig": bool(mean_clv > MAX_VIG),
        })
        print(f"  {name:6s} p={len(FEATURE_SETS[name]):2d}  "
              f"selected {int(selected.sum()):6,}  mean CLV {mean_clv:+.5f}  "
              f"(vs random {mean_clv - pinned:+.5f})  "
              f"{'clears' if mean_clv > MAX_VIG else 'below'} the vig")

    contrasts = {}
    print("\n  contrasts, paired per leg (negative delta = first arm better):")
    for a, b in (("MODEL", "BOOK"), ("FULL", "BOOK"), ("NOISE", "BOOK"),
                 ("MODEL", "NOISE")):
        cmp = bootstrap.paired(-arms[a]["values"][scored],
                               -arms[b]["values"][scored], blocks)
        contrasts[f"{a}-{b}"] = cmp.as_dict() | {"lift": round(-cmp.delta, 5)}
        print(f"    {a:6s} - {b:6s}  lift {-cmp.delta:+.5f} "
              f"[{-cmp.ci[1]:+.5f}, {-cmp.ci[0]:+.5f}]  {cmp.verdict}")

    return {"arms": rows, "contrasts": contrasts,
            "by_division": _by_division(legs, arms, target, scored),
            "strata": _by_stratum(legs, target, scored),
            "pbo": _pbo(legs, arms, scored),
            "book_coefficients": book_coefficients(legs, scored),
            "selection_profile": selection_profile(legs, arms, scored),
            "decision": _decide(rows, contrasts)}


def _by_division(legs, arms, target, scored) -> list[dict]:
    """§6's criterion 3: the sign must hold in at least three of four."""
    out = []
    print("\n  by division (criterion 3 needs the MODEL-BOOK sign in >=3 of 4):")
    for division in SERVED_DIVISIONS:
        rows = scored & (legs["division"].to_numpy() == division)
        if rows.sum() < 100:
            continue
        blocks = bootstrap.week_blocks(legs.loc[rows, "match_date"])
        cmp = bootstrap.paired(-arms["MODEL"]["values"][rows],
                               -arms["BOOK"]["values"][rows], blocks)
        book = float(target[arms["BOOK"]["chosen"] & rows].mean())
        model = float(target[arms["MODEL"]["chosen"] & rows].mean())
        out.append({"division": division, "n": int(rows.sum()),
                    "book_clv": round(book, 5), "model_clv": round(model, 5),
                    "model_minus_book": round(-cmp.delta, 5),
                    "positive": bool(-cmp.delta > 0)})
        print(f"    {division}  BOOK {book:+.5f}  MODEL {model:+.5f}  "
              f"diff {-cmp.delta:+.5f}")
    return out


def _by_stratum(legs, target, scored) -> list[dict]:
    """The other volumes, reported. §7 pre-commits the decision to the decile."""
    out = []
    print("\n  BOOK by selected volume (reported, decides nothing):")
    for fraction in REPORT_FRACTIONS:
        arm = score_arm(legs, FEATURE_SETS["BOOK"], target, fraction)
        selected = arm["chosen"] & scored
        mean_clv = float(target[selected].mean())
        out.append({"fraction": fraction, "selected": int(selected.sum()),
                    "mean_clv": round(mean_clv, 5),
                    "clears_vig": bool(mean_clv > MAX_VIG)})
        print(f"    top {100*fraction:5.1f}%  n={int(selected.sum()):6,}  "
              f"CLV {mean_clv:+.5f}")
    return out


def _pbo(legs, arms, scored) -> dict:
    """§5's multiplicity control, on the shape `trials.cscv_pbo` wants.

    Run on the full field and then on two subsets, because `choice_mattered` can
    be satisfied by the wrong thing. Its guard is the spread of *mean*
    performance across all trials, so one clearly-losing arm makes the field
    look separable even when every arm that could plausibly be chosen is
    interchangeable. `DEFLATION.md` §6 names the failure it protects against;
    this is the mirror image of it, and the subsets are what tell them apart.
    """
    performance = weekly_performance(legs[scored].reset_index(drop=True),
                                     {k: {"chosen": v["chosen"][scored],
                                          "values": v["values"][scored]}
                                      for k, v in arms.items()})
    out = {}
    for label, columns in (("all", list(arms)),
                           ("contenders", ["BOOK", "FULL", "NOISE"]),
                           ("decision", ["BOOK", "MODEL"])):
        result = trials.cscv_pbo(performance[columns])
        out[label] = {"arms": columns, "pbo": result.pbo,
                      "degradation": result.degradation, "spread": result.spread,
                      "n_trials": result.n_trials, "n_splits": result.n_splits,
                      "choice_mattered": bool(result.choice_mattered)}
        print(f"\n  PBO [{label}] {result.describe()}")
    return out


def book_coefficients(legs: pd.DataFrame, scored: np.ndarray) -> list[dict]:
    """Standardised coefficients of one BOOK fit, as a diagnostic only.

    Read with `SHOTS_TARGET.md` §4 and `CHANNELS.md` §1.7 in hand: a coefficient
    diagnostic has given the wrong answer about a feature on this project twice,
    and it decides nothing here either. It is reported because "which price is
    doing the work" is the first thing anyone will ask of a BOOK result, and a
    guess would be worse than a caveated number.
    """
    target = legs["clv"].to_numpy()
    features = list(FEATURE_SETS["BOOK"])
    X = _design(legs[scored], tuple(features))
    y = target[scored]
    mu, sd = X.mean(axis=0), X.std(axis=0)
    Z = np.column_stack([np.ones(len(X)), (X - mu) / np.where(sd > 0, sd, 1.0)])
    beta, *_ = np.linalg.lstsq(Z, y, rcond=None)
    rows = sorted(({"feature": f, "beta_std": round(float(b), 6)}
                   for f, b in zip(features, beta[1:])),
                  key=lambda r: -abs(r["beta_std"]))
    print("\n  BOOK standardised coefficients (diagnostic, decides nothing):")
    for row in rows:
        print(f"    {row['feature']:14s} {row['beta_std']:+.6f}")
    return rows


def selection_profile(legs: pd.DataFrame, arms: dict, scored: np.ndarray) -> dict:
    """What each arm's selected legs look like, against the pool it drew from.

    The headline CLV is 0.34 sd of a single leg, which is large for a market,
    so the mechanism has to be visible before the number is believed. CLV is
    `devig(close) - 1/max`, so anything that makes the best available price
    unusually generous relative to consensus raises it mechanically -- and
    `CALIBRATION.md` §5 already named best-price capture as the thing that
    removes 90% of the 1X2 margin. This profile is how that shows up or does
    not, and it fits nothing.
    """
    profile = {}
    print("\n  selection profile (mean over selected, vs the whole pool):")
    pool = {f: float(legs.loc[scored, f].mean())
            for f in ("be_max", "max_spread", "sharp_spread", "or_max")}
    print("    " + "  ".join(f"{k}={v:+.5f}" for k, v in pool.items()) + "   <- pool")
    for name in arms:
        rows = arms[name]["chosen"] & scored
        entry = {f: round(float(legs.loc[rows, f].mean()), 5) for f in pool}
        entry["side_mix"] = {s: round(float((legs.loc[rows, "side"] == s).mean()), 3)
                             for s in ("H", "D", "A")}
        # Matches whose best-available 1X2 book sums to under 1. Backing every
        # leg of one is a profit before any forecast, so a selection that
        # concentrates there is capturing price dispersion, not predicting.
        entry["share_overround_below_1"] = round(
            float((legs.loc[rows, "or_max"] < 1.0).mean()), 3)
        profile[name] = entry
        print("    " + "  ".join(f"{k}={entry[k]:+.5f}" for k in pool)
              + f"   sides {entry['side_mix']}"
              f"   or<1 {100*entry['share_overround_below_1']:.1f}%   <- {name}")
    profile["pool"] = {k: round(v, 5) for k, v in pool.items()}
    profile["pool"]["side_mix"] = {
        s: round(float((legs.loc[scored, "side"] == s).mean()), 3)
        for s in ("H", "D", "A")}
    profile["pool"]["share_overround_below_1"] = round(
        float((legs.loc[scored, "or_max"] < 1.0).mean()), 3)
    print(f"    pool or<1 {100*profile['pool']['share_overround_below_1']:.1f}%")
    return profile


def _decide(rows: list[dict], contrasts: dict) -> dict:
    """§6's four criteria, evaluated exactly as pre-committed."""
    by_arm = {r["arm"]: r for r in rows}
    model_book = contrasts["MODEL-BOOK"]
    return {
        "c1_model_beats_book": bool(model_book["lift"] > 0
                                    and model_book["ci_high"] < 0),
        "c2_selected_clears_vig": by_arm["MODEL"]["clears_vig"],
        "book_clears_vig": by_arm["BOOK"]["clears_vig"],
    }


def p5_recovery(legs: pd.DataFrame) -> dict:
    """POST-HOC. Is BOOK's edge still there once the beatable books are gone?

    `META.md` §3 found 65.3% of BOOK's picks sit in matches whose best-available
    1X2 book sums to under 1 — where backing every leg profits before any
    forecast exists, and where a real bookmaker limits or voids. That is price
    dispersion, not prediction, and it is the part of BOOK's result that cannot
    be traded. This removes those matches and asks what is left.

    **The subgroup was chosen after seeing the result.** It is registered in
    `trials.POST_HOC_TRIALS` and can motivate a pre-registered follow-up; it
    cannot stand in for one. `DEFLATION.md` §4 is the convention.

    Matches are removed from **training as well as scoring**: the question is
    whether a model built for the executable universe works there, not whether
    a model taught to spot arbitrage transfers. The threshold is exactly 1.0 —
    the point where the book is beatable outright — because any margin around
    it would be a tuned parameter, and this gate has no budget for one.
    """
    executable = legs["or_max"].to_numpy() >= 1.0
    sub = legs[executable].reset_index(drop=True)
    target = sub["clv"].to_numpy()
    pinned_all = float(legs["clv"].mean())
    pinned_sub = float(target.mean())

    print("\nP5-RECOVERY  BOOK with the sub-1 overround matches removed "
          "(POST-HOC)")
    print(f"  kept {len(sub):,} of {len(legs):,} legs ({100*executable.mean():.1f}%), "
          f"{sub.match_id.nunique():,} matches")
    print(f"  the pinned mean moves {pinned_all:+.5f} -> {pinned_sub:+.5f}: "
          f"removing the thin books makes the average leg "
          f"{'worse' if pinned_sub < pinned_all else 'better'}, so the bar is "
          f"{'harder' if pinned_sub < pinned_all else 'easier'} than before")

    arms = {name: score_arm(sub, FEATURE_SETS[name], target)
            for name in ("BOOK", "BLIND")}
    scored = arms["BOOK"]["scored"] & arms["BLIND"]["scored"]
    blocks = bootstrap.week_blocks(sub.loc[scored, "match_date"])

    rows = []
    for name, arm in arms.items():
        selected = arm["chosen"] & scored
        mean_clv = float(target[selected].mean())
        rows.append({"arm": name, "selected": int(selected.sum()),
                     "mean_clv_selected": round(mean_clv, 5),
                     "lift_over_random": round(mean_clv - pinned_sub, 5),
                     "clears_vig": bool(mean_clv > MAX_VIG)})
        print(f"  {name:6s} selected {int(selected.sum()):6,}  "
              f"mean CLV {mean_clv:+.5f}  (vs random {mean_clv - pinned_sub:+.5f})  "
              f"{'CLEARS' if mean_clv > MAX_VIG else 'below'} the vig "
              f"{MAX_VIG:.5f}")

    cmp = bootstrap.paired(-arms["BOOK"]["values"][scored],
                           -arms["BLIND"]["values"][scored], blocks)
    print(f"  BOOK - BLIND  lift {-cmp.delta:+.5f} "
          f"[{-cmp.ci[1]:+.5f}, {-cmp.ci[0]:+.5f}]  {cmp.verdict}")

    book = rows[0]
    # A CI on the selected-volume mean itself, which is what criterion 2 reads.
    selected = arms["BOOK"]["chosen"] & scored
    level = bootstrap.paired(target[selected],
                             np.full(int(selected.sum()), MAX_VIG),
                             bootstrap.week_blocks(sub.loc[selected, "match_date"]))
    print(f"  BOOK selected CLV minus the vig: {level.delta:+.5f} "
          f"[{level.ci[0]:+.5f}, {level.ci[1]:+.5f}]  "
          f"{'excludes zero' if level.excludes_zero else 'spans zero'}")

    return {
        "n_legs": int(len(sub)), "n_matches": int(sub.match_id.nunique()),
        "share_kept": round(float(executable.mean()), 4),
        "pinned_mean_all": round(pinned_all, 5),
        "pinned_mean_executable": round(pinned_sub, 5),
        "arms": rows,
        "book_minus_blind": cmp.as_dict() | {"lift": round(-cmp.delta, 5)},
        "book_vs_vig": level.as_dict(),
        "by_division": _recovery_divisions(sub, arms["BOOK"], target, scored),
        "coefficients": book_coefficients(sub, scored),
        "profile": selection_profile(sub, arms, scored),
        "survives": bool(book["clears_vig"] and level.ci[0] > 0
                         and cmp.ci[1] < 0),
    }


def _recovery_divisions(sub, book, target, scored) -> list[dict]:
    out = []
    print("  by division:")
    for division in SERVED_DIVISIONS:
        rows = scored & (sub["division"].to_numpy() == division)
        selected = book["chosen"] & rows
        if selected.sum() < 100:
            continue
        mean_clv = float(target[selected].mean())
        out.append({"division": division, "selected": int(selected.sum()),
                    "mean_clv": round(mean_clv, 5),
                    "clears_vig": bool(mean_clv > MAX_VIG)})
        print(f"    {division}  n={int(selected.sum()):5,}  CLV {mean_clv:+.5f}  "
              f"{'clears' if mean_clv > MAX_VIG else 'below'}")
    return out


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", default="grounding",
                        choices=["grounding", "control", "arms", "recovery", "all"])
    parser.add_argument("--out", default="docs/p5_grounding_results.json")
    # The arms gate wrote four ledger rows during its own implementation, each
    # spending against §5's budget for numbers that turned out byte-identical
    # (META.md §8). Develop under --dry-run; drop it for the run of record.
    parser.add_argument("--dry-run", action="store_true",
                        help="print and write JSON, but record no ledger row")
    args = parser.parse_args(argv)

    def record(**kwargs):
        if args.dry_run:
            print(f"  [dry-run] ledger row NOT written: {kwargs['name']}")
            return
        ledger.record(conn, purpose="dev", seasons=DEV_SEASONS,
                      divisions=SERVED_DIVISIONS, **kwargs)
        print(f"  [ledger] {kwargs['kind']}:{kwargs['name']}")

    conn = db.connect()
    frame = load(conn)
    scored = scored_corpus(frame)
    basis = clv_basis(scored)

    results = {}
    if args.stage in ("grounding", "all"):
        results["g1"] = g1_training_basis(conn)
        results["g2"] = g2_gradable(scored)
        results["g2"]["published_division_basis"] = g2_published_division_basis(
            drop_outcomes(frame))
        results["g3"] = g3_vig(scored)
        results["g4"] = g4_pinned_mean(basis)
        results["g5"] = g5_power(basis)
        results["g6"] = g6_features(basis)
        results["reproduction"] = check_published(results)

        record(kind=ledger.PROBE, name="p5_grounding", detail=results,
               reason="Grounding for P5_META_PLAN.md §1, as committed code. "
                      "Reads prices and lambda coverage only -- no match "
                      "outcome enters any statistic -- so it carries no arm "
                      "list and spends no configuration, on the same "
                      "accounting as power.py and odds.vig_per_leg.")

    if args.stage in ("control", "arms", "recovery", "all"):
        legs = build_legs(conn)
        print(f"\nleg frame: {len(legs):,} legs / {legs.match_id.nunique():,} "
              f"matches, {legs.week.nunique()} ISO weeks")

    if args.stage in ("control", "all"):
        results["control"] = p5_control(legs)
        record(kind=ledger.PROBE, name="p5_control", detail=results["control"],
               reason="P5_META_PLAN.md §5 positive control. A planted CLV edge "
                      "on a stratum only MODEL can see, at four sizes including "
                      "zero. Synthetic targets carry no information about the "
                      "real answer, so this row spends no configuration -- same "
                      "accounting as travel.py's h34_travel_power. Stop "
                      "condition: the arms do not run unless the as-specified "
                      "scale is recovered in >=5 of 6 draws.")
        if not results["control"]["passed"]:
            print("\nSTOPPING. §5's stop condition is not met, so no arm runs "
                  "on real targets. The finding is 'this corpus cannot answer "
                  "it', which is not a null -- see TOD_SLOT.md for the shape.")
            _write(args.out, results)
            return 1

    if args.stage == "arms" and "control" not in results:
        prior = ledger.last_detail(conn, "p5_control")
        if not prior.get("passed"):
            print("§5 requires a PASSED p5_control row before any arm runs. "
                  "Run `--stage control` first.")
            return 1
        print("  [gate] p5_control passed on a previous run -- arms may run")

    if args.stage in ("arms", "all"):
        results["arms"] = p5_arms(legs)
        record(kind=ledger.GATE, name="p5_meta_arms", detail=results["arms"],
               reason="P5_META_PLAN.md §4. BOOK / MODEL / FULL plus the §5 "
                      "NOISE negative control, on real CLV. Decision statistic "
                      "is MODEL-BOOK per §4; §6's four criteria are "
                      "pre-committed. Four configurations against a declared "
                      "budget of twelve.")

    if args.stage in ("recovery", "all"):
        results["recovery"] = p5_recovery(legs)
        record(kind=ledger.GATE, name="p5_book_no_arb",
               detail=results["recovery"],
               reason="POST-HOC. Does BOOK's edge survive removing the matches "
                      "whose best-available book already sums to under 1? The "
                      "subgroup was chosen after seeing META.md §3, so this row "
                      "is in trials.POST_HOC_TRIALS and cannot support a "
                      "pre-registration claim. Two configurations: BOOK and the "
                      "NOISE negative control, which a positive result needs "
                      "exactly as a null needs a planted positive "
                      "(OUTSTANDING.md §1.7).")

    _write(args.out, results)
    if "reproduction" in results and not results["reproduction"]["all_reproduce"]:
        return 1
    return 0


def _write(path: str, results: dict) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(results, handle, indent=2, default=str)
    print(f"wrote {path}")


if __name__ == "__main__":
    raise SystemExit(main())
