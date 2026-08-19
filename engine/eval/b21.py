"""B21 gate: the underdog +1.5 handicap as a fallback candidate.

    python -m engine.eval.b21 --dry-run   # everything printed, no ledger row
    python -m engine.eval.b21             # outcomes read, 1 configuration

Pre-registration is `docs/BACKLOG.md` B21 ("Gate -- dog +1.5"), written before
this ran. The arm is the shipped rule (floor 0.55, ceiling 0.85, `12` on) with
the underdog +1.5 Asian handicap added to the fallback candidate set: the
fallback picks the likeliest of `1X`/`X2`/`12`/`dog +1.5` at or under the
ceiling. The underdog is the model's underdog (`p_h < p_a` => home is the
dog); the call wins unless the favourite wins by 2 or more (half line, no
push). The outright tier is untouched by construction, and no dominated-union
guard is needed: with `12` on the menu the fallback maximum is >= `12` >= the
outright probability.

Paired by ISO week against the shipped arm, whose strike is already published
(B3); the paired reference spends nothing, so the gate costs 1 configuration.
"""

from __future__ import annotations

import argparse
import json

import numpy as np
import pandas as pd

from engine import db, ledger
from engine.eval import bootstrap, selection
from engine.eval.p7 import joint_of, load, probs_1x2
from engine.seasons import DEV_SEASONS, SERVED_DIVISIONS

FLOOR = selection.SHIPPED_FLOOR
CEILING = selection.CEILING

#: The published label for the new market: the model's underdog with a +1.5
#: goal start. Not in `tips.side`'s CHECK constraint -- adoption would need a
#: migration, which is pre-stated in the registration.
DOG15 = "D+1.5"

MARKETS = ("H", "A", "1X", "X2", "12", DOG15)


def dog15_probs(joint: np.ndarray, probs: np.ndarray) -> np.ndarray:
    """P(the model's underdog loses by at most 1), from the score matrix."""
    n = joint.shape[1]
    margin = np.arange(n)[:, None] - np.arange(n)[None, :]
    fav_home = probs[:, 0] >= probs[:, 2]
    home_by_2 = joint[:, margin >= 2].sum(axis=1)
    away_by_2 = joint[:, margin <= -2].sum(axis=1)
    return 1.0 - np.where(fav_home, home_by_2, away_by_2)


def recommend(probs: np.ndarray, p_dog15: np.ndarray,
              *, floor: float = FLOOR, ceiling: float = CEILING):
    """The shipped rule with `dog +1.5` added to the fallback candidates.

    Identical to `selection.recommend(..., allow_12=True)` except that the
    fallback stack carries a fourth candidate. Everything else -- the outright
    tier, the floor, the ceiling-as-veto -- is unchanged, and a test pins that
    every difference from the shipped rule is a fallback pick becoming DOG15.
    """
    p_h, p_d, p_a = probs[:, 0], probs[:, 1], probs[:, 2]
    home = p_h >= p_a
    outright_p = np.where(home, p_h, p_a)

    names = ["1X", "X2", "12", DOG15]
    stack = np.column_stack([p_h + p_d, p_a + p_d, p_h + p_a, p_dog15])
    eligible = np.where(stack <= ceiling, stack, -1.0)
    best = eligible.argmax(axis=1)
    fallback_p = eligible[np.arange(len(stack)), best]

    take_outright = (outright_p >= floor) | (fallback_p < 0)
    market = np.where(take_outright,
                      np.where(home, "H", "A"),
                      np.array(names)[best])
    probability = np.where(take_outright, outright_p, fallback_p)
    return market, probability


def won(market: np.ndarray, frame: pd.DataFrame, probs: np.ndarray) -> np.ndarray:
    """Settlement for the five shipped markets plus DOG15."""
    ftr = frame.ftr.to_numpy()
    fav_home = probs[:, 0] >= probs[:, 2]
    fav_margin = np.where(fav_home,
                          frame.fthg.to_numpy(float) - frame.ftag.to_numpy(float),
                          frame.ftag.to_numpy(float) - frame.fthg.to_numpy(float))
    return np.where(market == DOG15, fav_margin < 1.5,
                    selection._won(market, ftr))


def _mix(market: np.ndarray) -> dict:
    return {m: round(float((market == m).mean()), 4) for m in MARKETS}


def gate(frame: pd.DataFrame, probs: np.ndarray, p_dog15: np.ndarray) -> dict:
    """Realised strike of the arm, paired against the shipped rule."""
    blocks = bootstrap.week_blocks(frame.match_date)
    base_market, base_p = selection.recommend(probs, FLOOR, CEILING, allow_12=True)
    arm_market, arm_p = recommend(probs, p_dog15)
    base_won = won(base_market, frame, probs).astype(float)
    arm_won = won(arm_market, frame, probs).astype(float)
    cmp = bootstrap.paired(arm_won, base_won, blocks)

    shifted = arm_market != base_market
    out = {
        "n": int(len(frame)),
        "shipped": {"strike": round(float(base_won.mean()), 5),
                    "claimed": round(float(base_p.mean()), 5),
                    "honesty_gap": round(float(base_won.mean() - base_p.mean()), 5),
                    "mix": _mix(base_market)},
        "arm": {"strike": round(float(arm_won.mean()), 5),
                "claimed": round(float(arm_p.mean()), 5),
                "honesty_gap": round(float(arm_won.mean() - arm_p.mean()), 5),
                "mix": _mix(arm_market)},
        "shifted_share": round(float(shifted.mean()), 4),
        "vs_shipped": round(float(cmp.delta), 5),
        "vs_shipped_ci": [round(cmp.ci[0], 5), round(cmp.ci[1], 5)],
        "vs_shipped_excludes_zero": bool(cmp.excludes_zero),
    }
    is_d = arm_market == DOG15
    out["arm"]["dog15_claimed"] = round(float(arm_p[is_d].mean()), 5)
    out["arm"]["dog15_delivered"] = round(float(arm_won[is_d].mean()), 5)

    g1 = 0.025 <= cmp.delta <= 0.045 and cmp.excludes_zero and cmp.delta > 0
    g2 = -0.015 <= out["arm"]["honesty_gap"] <= -0.002
    g3 = 0.750 <= out["arm"]["strike"] <= 0.770
    out["verdict"] = {"G1_delta_2_5_to_4_5_resolved_positive": bool(g1),
                      "G2_overclaim_0_2_to_1_5": bool(g2),
                      "G3_arm_strike_75_to_77": bool(g3)}

    print(f"\ngate  dog +1.5 as a fallback candidate ({len(frame):,} matches, "
          f"paired by ISO week)")
    for name, r in (("shipped", out["shipped"]), ("arm", out["arm"])):
        print(f"    {name:<8} strike {100*r['strike']:.2f}%  claimed "
              f"{100*r['claimed']:.2f}%  honesty {100*r['honesty_gap']:+.2f}  "
              + "  ".join(f"{k} {100*v:.1f}%" for k, v in r["mix"].items() if v))
    print(f"    shifted {100*out['shifted_share']:.1f}%  vs shipped "
          f"{100*out['vs_shipped']:+.3f} [{100*out['vs_shipped_ci'][0]:+.3f},"
          f"{100*out['vs_shipped_ci'][1]:+.3f}]"
          f"{'*' if out['vs_shipped_excludes_zero'] else ''}")
    print(f"    {DOG15} claims {100*out['arm']['dog15_claimed']:.2f}%  delivers "
          f"{100*out['arm']['dog15_delivered']:.2f}%")
    print("    predictions: " + ", ".join(f"{k} {'OK' if v else 'NO'}"
                                          for k, v in out["verdict"].items()))
    return out


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="docs/b21_results.json")
    parser.add_argument("--dry-run", action="store_true",
                        help="print and write JSON, but record no ledger row")
    args = parser.parse_args(argv)

    conn = db.connect()
    frame = load(conn)
    joint = joint_of(frame)
    probs = probs_1x2(joint)
    p_dog15 = dog15_probs(joint, probs)
    print(f"{len(frame):,} matches, {frame.season.min()} -> {frame.season.max()}, "
          f"{frame.division.nunique()} divisions")

    results = {"gate": gate(frame, probs, p_dog15)}

    if args.dry_run:
        print("  [dry-run] ledger row NOT written (1 configuration)")
    else:
        ledger.record(
            conn, kind=ledger.GATE, name="b21_dog15", purpose="dev",
            seasons=DEV_SEASONS, divisions=SERVED_DIVISIONS,
            detail={"arms": [{"arm": "dog +1.5 fallback candidate",
                              "strike": results["gate"]["arm"]["strike"],
                              "vs_shipped": results["gate"]["vs_shipped"]}],
                    **results["gate"]},
            reason="BACKLOG.md B21 gate. The underdog +1.5 handicap added to the "
                   "fallback candidate set of the shipped rule, paired by ISO week "
                   "against the shipped arm. One configuration -- one new arm's "
                   "outcomes read; the shipped reference is already published (B3).")
        print("  [ledger] gate:b21_dog15  (1 configuration)")

    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(results, handle, indent=2, default=str)
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
