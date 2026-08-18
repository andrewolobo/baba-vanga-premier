"""B20: a `12`-specific eligibility window on the shipped rule.

    python -m engine.eval.window12 --part probe --dry-run   # lambda only, no row
    python -m engine.eval.window12 --part gate              # outcomes, ledger row

Pre-registration is `docs/BACKLOG.md` B20, written before any of this ran.

`12` (home or away, "not a draw") is 65% of what `confidence-v2` publishes and
its calls deliver 73.6% against an unconditional non-draw base rate of 73.9%
on the same divisions and seasons. This module measures what happens when `12`
is only eligible inside a window `[floor_12, ceiling_12]` of its own
probability, everything else in the rule unchanged:

  ceiling_12 < 0.85   vetoes `12` where the model is *surest* it is not a draw
                      (the owner's ask: cap the least specific call);
  floor_12   > 0      vetoes `12` where the model is *least* sure -- the calls
                      at or below the base rate, which carry no information.

Where `12` is vetoed the fallback is `recommend(..., allow_12=False)` -- the
likeliest of `1X`/`X2` under the shipped ceiling, else the outright -- with one
guard: a union less likely than the outright it replaces is not published (see
`recommend` below). The arm composes over the shipped rule and touches no
product code.

Two parts, two kinds of row:

  probe  mix, mean claimed probability, what the displaced `12` calls become,
         and the *model-implied* strike change (mean p_new - p_old). Reads
         lambda only; **0 configurations**.
  gate   realised strike rate per arm, paired against the shipped arm by ISO
         week, plus delivered-minus-claimed on the published pick. Reads
         outcomes; **1 configuration per arm** whose strike is read.
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

#: The arms. `ceiling` arms are the owner's ask; `floor` arms are the
#: alternative shape the pre-registration argues for. Each name maps to
#: (floor_12, ceiling_12). The shipped arm is (0, 0.85) and costs nothing.
SHIPPED_ARM = "shipped (12 in [0.00, 0.85])"
ARMS: dict[str, tuple[float, float]] = {
    SHIPPED_ARM: (0.0, CEILING),
    "ceiling 0.80": (0.0, 0.80),
    "ceiling 0.75": (0.0, 0.75),
    "ceiling 0.70": (0.0, 0.70),
    "floor 0.75": (0.75, CEILING),
    "floor 0.80": (0.80, CEILING),
}

#: Unconditional share of E0-E3 results 2014-15 -> 2022-23 that were not draws
#: (18,060 matches, `db/premier.db`, computed 2026-08-18). The bar a `12` call's
#: claimed probability has to clear to say anything a customer does not know.
NON_DRAW_BASE_RATE = 0.7385

MARKETS = ("H", "A", "1X", "X2", "12")


def recommend(probs: np.ndarray, floor_12: float, ceiling_12: float,
              *, floor: float = FLOOR, ceiling: float = CEILING):
    """The shipped rule with `12` eligible only inside [floor_12, ceiling_12].

    Composed, not re-implemented: where the shipped rule would publish `12` at
    a probability outside the window, the recommendation is what the shipped
    rule publishes with `12` disallowed -- unless that is a union *less likely
    than the outright it replaces*, in which case the outright is published.
    (`recommend(allow_12=False)` can publish `X2` at 0.46 over `H` at 0.54 when
    `1X` breaches the ceiling; the shipped rule cannot, because `12` >= p_h.)
    Everywhere else it is identical."""
    market, p = selection.recommend(probs, floor, ceiling, allow_12=True)
    without_market, without_p = selection.recommend(probs, floor, ceiling,
                                                    allow_12=False)
    home = probs[:, 0] >= probs[:, 2]
    outright_market = np.where(home, "H", "A")
    outright_p = np.where(home, probs[:, 0], probs[:, 2])
    dominated = without_p < outright_p
    without_market = np.where(dominated, outright_market, without_market)
    without_p = np.where(dominated, outright_p, without_p)
    vetoed = (market == "12") & ((p < floor_12) | (p > ceiling_12))
    return (np.where(vetoed, without_market, market),
            np.where(vetoed, without_p, p))


def _mix(market: np.ndarray) -> dict:
    return {m: round(float((market == m).mean()), 4) for m in MARKETS}


def probe(probs: np.ndarray) -> dict:
    """What each window publishes. Lambda only, no outcomes."""
    print(f"\nprobe  the `12` window at floor {FLOOR} / ceiling {CEILING} "
          f"(no outcomes read; base rate {100*NON_DRAW_BASE_RATE:.2f}% not-draw)")
    base_market, base_p = recommend(probs, *ARMS[SHIPPED_ARM])
    out = {"floor": FLOOR, "ceiling": CEILING,
           "non_draw_base_rate": NON_DRAW_BASE_RATE, "arms": {}}
    print(f"    {'arm':<28} {'12':>6} {'1X':>6} {'H':>6} {'shift':>7} "
          f"{'->1X':>5} {'->X2':>5} {'->out':>5} {'mean p':>7} "
          f"{'12 mean p':>9} {'12<base':>7} {'implied':>8}")
    for name, (lo, hi) in ARMS.items():
        market, p = recommend(probs, lo, hi)
        shifted = market != base_market
        became = _mix(market[shifted]) if shifted.any() else {}
        is_12 = market == "12"
        row = {
            "floor_12": lo, "ceiling_12": hi, "mix": _mix(market),
            "team_named_share": round(float(np.isin(market, ["H", "A"]).mean()), 4),
            "shifted_share": round(float(shifted.mean()), 4),
            "shifted_became": became,
            "mean_claimed": round(float(p.mean()), 4),
            "mean_claimed_12": (round(float(p[is_12].mean()), 4)
                                if is_12.any() else None),
            "share_of_12_below_base_rate": (
                round(float((p[is_12] < NON_DRAW_BASE_RATE).mean()), 4)
                if is_12.any() else None),
            # Mean over all matches of the change in claimed probability. If the
            # head were calibrated this is the strike-rate change the arm costs.
            "model_implied_strike_delta": round(float((p - base_p).mean()), 5),
        }
        out["arms"][name] = row
        print(f"    {name:<28} {100*row['mix']['12']:>5.1f}% {100*row['mix']['1X']:>5.1f}% "
              f"{100*row['mix']['H']:>5.1f}% {100*row['shifted_share']:>6.1f}% "
              f"{100*became.get('1X', 0):>4.0f}% {100*became.get('X2', 0):>4.0f}% "
              f"{100*(became.get('H', 0) + became.get('A', 0)):>4.0f}% "
              f"{row['mean_claimed']:>7.3f} "
              f"{(row['mean_claimed_12'] or float('nan')):>9.3f} "
              f"{100*(row['share_of_12_below_base_rate'] or 0):>6.1f}% "
              f"{100*row['model_implied_strike_delta']:>+7.2f}")
    a = out["arms"]
    out["verdict"] = {
        "P1_ceiling_080_12_share_50_to_58": 0.50 <= a["ceiling 0.80"]["mix"]["12"] <= 0.58,
        "P1_ceiling_075_12_share_20_to_35": 0.20 <= a["ceiling 0.75"]["mix"]["12"] <= 0.35,
        "P1_ceiling_070_12_share_under_8": a["ceiling 0.70"]["mix"]["12"] < 0.08,
        "P2_displaced_go_to_1X_over_80pct_at_075": a["ceiling 0.75"]["shifted_became"].get("1X", 0) > 0.80,
        "P3_implied_delta_at_075_in_minus_3_5_to_minus_1": -0.035 <= a["ceiling 0.75"]["model_implied_strike_delta"] <= -0.010,
        "P4_shipped_12_below_base_rate_over_40pct": (a[SHIPPED_ARM]["share_of_12_below_base_rate"] or 0) > 0.40,
        "P5_floor_075_12_share_25_to_40": 0.25 <= a["floor 0.75"]["mix"]["12"] <= 0.40,
        "P6_floor_075_costs_less_per_shifted_match_than_ceiling_075": (
            abs(a["floor 0.75"]["model_implied_strike_delta"]) / max(a["floor 0.75"]["shifted_share"], 1e-9)
            < abs(a["ceiling 0.75"]["model_implied_strike_delta"]) / max(a["ceiling 0.75"]["shifted_share"], 1e-9)),
    }
    print("    predictions: " + ", ".join(f"{k} {'OK' if v else 'NO'}"
                                          for k, v in out["verdict"].items()))
    return out


def gate(frame: pd.DataFrame, probs: np.ndarray, arms: tuple[str, ...]) -> dict:
    """Realised strike per arm, paired against the shipped arm. Reads outcomes."""
    ftr = frame.ftr.to_numpy()
    blocks = bootstrap.week_blocks(frame.match_date)
    base_market, base_p = recommend(probs, *ARMS[SHIPPED_ARM])
    base_won = selection._won(base_market, ftr).astype(float)
    print(f"\ngate  realised strike, paired against the shipped arm "
          f"({len(frame):,} matches)")
    print(f"    {'arm':<28} {'strike':>7} {'vs shipped, PAIRED':>26} "
          f"{'claimed':>8} {'honesty':>8}")
    out = {"arms": {}}
    for name in (SHIPPED_ARM,) + tuple(a for a in arms if a != SHIPPED_ARM):
        market, p = recommend(probs, *ARMS[name])
        won = selection._won(market, ftr).astype(float)
        cmp = bootstrap.paired(won, base_won, blocks)
        row = {"strike": round(float(won.mean()), 5),
               "claimed": round(float(p.mean()), 5),
               "honesty_gap": round(float(won.mean() - p.mean()), 5),
               "vs_shipped": round(float(cmp.delta), 5),
               "vs_shipped_ci": [round(cmp.ci[0], 5), round(cmp.ci[1], 5)],
               "vs_shipped_excludes_zero": bool(cmp.excludes_zero),
               "mix": _mix(market)}
        out["arms"][name] = row
        print(f"    {name:<28} {100*row['strike']:>6.2f}% "
              f"{100*row['vs_shipped']:>+8.3f} [{100*row['vs_shipped_ci'][0]:>+6.3f},"
              f"{100*row['vs_shipped_ci'][1]:>+6.3f}]"
              f"{'*' if row['vs_shipped_excludes_zero'] else ' '} "
              f"{100*row['claimed']:>7.2f}% {100*row['honesty_gap']:>+7.2f}")
    return out


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--part", choices=("probe", "gate"), default="probe")
    parser.add_argument("--arms", nargs="*", default=None,
                        help="gate only: arm names to read outcomes for "
                             "(default: every non-shipped arm)")
    parser.add_argument("--out", default="docs/window12_results.json")
    parser.add_argument("--dry-run", action="store_true",
                        help="print and write JSON, but record no ledger row")
    args = parser.parse_args(argv)

    conn = db.connect()
    frame = load(conn)
    probs = probs_1x2(joint_of(frame))
    print(f"{len(frame):,} matches, {frame.season.min()} -> {frame.season.max()}, "
          f"{frame.division.nunique()} divisions")

    def row(kind, name, detail, reason, cost):
        if args.dry_run:
            print(f"  [dry-run] {kind}:{name} NOT written ({cost} configurations)")
            return
        ledger.record(conn, kind=kind, name=name, purpose="dev", seasons=DEV_SEASONS,
                      divisions=SERVED_DIVISIONS, detail=detail, reason=reason)
        print(f"  [ledger] {kind}:{name}  ({cost} configurations)")

    results: dict = {}
    if args.part == "probe":
        results["probe"] = probe(probs)
        row(ledger.PROBE, "b20_window12_probe", results["probe"],
            "BACKLOG.md B20 probe. Mix, mean claimed probability and model-implied "
            "strike change for a `12`-only eligibility window on the shipped rule. "
            "Reads lambda only -- no outcome enters; zero configurations.", 0)
    else:
        arms = tuple(args.arms) if args.arms else tuple(
            a for a in ARMS if a != SHIPPED_ARM)
        unknown = set(arms) - set(ARMS)
        if unknown:
            parser.error(f"unknown arms: {sorted(unknown)}; choose from {list(ARMS)}")
        results["gate"] = gate(frame, probs, arms)
        cost = len([a for a in arms if a != SHIPPED_ARM])
        row(ledger.GATE, "b20_window12",
            {"arms": [{"arm": a, "strike": results["gate"]["arms"][a]["strike"],
                       "vs_shipped": results["gate"]["arms"][a]["vs_shipped"]}
                      for a in arms],
             **results["gate"]},
            "BACKLOG.md B20 gate. Realised strike rate of a `12`-only eligibility "
            "window on the shipped rule, paired by ISO week against the shipped "
            f"arm. Reads outcomes; {cost} configuration(s), one per arm read.",
            cost)

    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(results, handle, indent=2, default=str)
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
