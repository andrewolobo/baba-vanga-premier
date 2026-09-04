"""B24 probe: does the parlay page's product of claims deliver?

    python -m engine.eval.b24 --dry-run   # everything printed, no ledger row
    python -m engine.eval.b24             # probe row, 0 configurations

Pre-registration is `docs/PARLAY_PLAN.md` §3 (2026-09-01) with its dated
amendment (2026-09-04) extending the grid to the slider's range. The parlay
page multiplies the claims of the top-k published calls of a matchday and
shows the product as the parlay's own claim. Leg-level calibration is
measured (gate row 110); the product assumes the legs are independent and
that picking the top-k by claim does not pick over-claiming legs, and that
assumption is the one thing the page adds. This row measures it.

The unit is the **slip**: for one matchday (or one division-matchday, for
the split), the top k calls by claim at or above threshold r -- the page's
selector (`engine/serve/parlay.py`) restated on the dev corpus, where every
match has exactly one v3 call and nothing has kicked off. realised = every
leg won; claimed = the product of the legs' claims. The statistic is
mean(realised - claimed) over slips, week-block bootstrapped; **positive
means the page under-claims**, the safe direction.

Control (convention 8): the same match entered twice as a two-leg slip must
read realised - claimed ~= +p(1-p), resolved positive, or the instrument
cannot see dependence and the table is not a result.

**0 configurations, one probe row.** Outcomes were read for row 110's arm;
every slip here re-aggregates those same calls' outcomes, and nothing is
chosen from the result -- a change to the page (an offset, a lower cap) is
the pre-registered consequence, not a selection.
"""

from __future__ import annotations

import argparse
import json

import numpy as np
import pandas as pd

from engine import db, ledger
from engine.eval import b21, bootstrap
from engine.eval.p7 import joint_of, load, probs_1x2
from engine.seasons import DEV_SEASONS, SERVED_DIVISIONS

#: The page's grid (PRESETS x offered sizes) plus the slider extension.
GRID_K = (2, 3, 4)
GRID_R = (0.80, 0.70, 0.0)
EXTENSION_K = (5, 8, 10, 15, 20)

#: A matchday with at least this many fixtures across E0-E3 is a "Saturday"
#: -- the population the page's defaults were sized on (`PARLAY_PLAN.md` §1).
SATURDAY_MIN = 20


def slip_table(dates, claims, won, *, k, r, groups=None) -> pd.DataFrame:
    """One row per group that can fill a slip: its claimed product and hit.

    `groups` defaults to the matchday; the division split passes
    division+date. `k=None` is the full-day slip -- every qualifying call,
    minimum two. A group short of `k` calls at or above `r` contributes
    nothing, exactly as the page never pads a slot (D5).
    """
    df = pd.DataFrame({
        "group": np.asarray(groups if groups is not None else dates),
        "date": np.asarray(dates),
        "p": np.asarray(claims, dtype=float),
        "won": np.asarray(won, dtype=float),
    })
    rows = []
    for _, day in df.groupby("group", sort=True):
        legs = day[day.p >= r].sort_values("p", ascending=False, kind="stable")
        take = len(legs) if k is None else k
        if take < 2 or len(legs) < take:
            continue
        legs = legs.head(take)
        rows.append((day.date.iloc[0], float(legs.p.prod()),
                     float(legs.won.min())))
    return pd.DataFrame(rows, columns=["date", "claimed", "hit"])


def cell(slips: pd.DataFrame) -> dict:
    """realised vs claimed for one grid cell, week-block bootstrapped."""
    out = {"days": int(len(slips)), "hits": int(slips.hit.sum()) if len(slips) else 0}
    if len(slips) < 2:
        return out
    cmp = bootstrap.paired(slips.hit, slips.claimed,
                           bootstrap.week_blocks(slips.date))
    out.update({
        "claimed": round(float(slips.claimed.mean()), 5),
        "realised": round(float(slips.hit.mean()), 5),
        "gap": round(float(cmp.delta), 5),
        "ci": [round(cmp.ci[0], 5), round(cmp.ci[1], 5)],
        "excludes_zero": bool(cmp.excludes_zero),
    })
    return out


def dependent_control(dates, claims, won, *, r=0.80) -> dict:
    """The planted dependence: each call at or above `r` entered twice.

    claimed = p^2 while realised = the leg's own outcome, so the gap must
    read ~= mean p(1-p), resolved positive. If it does not, the instrument
    is dead and no other cell is a result.
    """
    df = pd.DataFrame({"date": np.asarray(dates),
                       "p": np.asarray(claims, dtype=float),
                       "won": np.asarray(won, dtype=float)})
    df = df[df.p >= r]
    cmp = bootstrap.paired(df.won, df.p ** 2, bootstrap.week_blocks(df.date))
    return {"n": int(len(df)),
            "expected": round(float((df.p * (1 - df.p)).mean()), 5),
            "gap": round(float(cmp.delta), 5),
            "ci": [round(cmp.ci[0], 5), round(cmp.ci[1], 5)],
            "fired": bool(cmp.excludes_zero and cmp.delta > 0)}


def probe(frame: pd.DataFrame, claims: np.ndarray, won: np.ndarray) -> dict:
    dates = frame.match_date.to_numpy()
    day_size = pd.Series(dates).map(pd.Series(dates).value_counts()).to_numpy()
    saturday = day_size >= SATURDAY_MIN

    def grid(mask) -> dict:
        d, c, w = dates[mask], claims[mask], won[mask]
        out = {}
        for k in GRID_K:
            for r in GRID_R:
                out[f"k{k}_r{r:g}"] = cell(slip_table(d, c, w, k=k, r=r))
        for k in EXTENSION_K:
            out[f"k{k}_r0"] = cell(slip_table(d, c, w, k=k, r=0.0))
        out["full_day"] = cell(slip_table(d, c, w, k=None, r=0.0))
        return out

    every = np.ones(len(frame), dtype=bool)
    division = frame.division.to_numpy()
    div_groups = np.char.add(np.char.add(division.astype(str), "|"),
                             dates.astype(str))
    by_division = {}
    for div in sorted(set(division)):
        m = division == div
        by_division[div] = {
            f"k2_r{r:g}": cell(slip_table(dates[m], claims[m], won[m],
                                          k=2, r=r, groups=div_groups[m]))
            for r in (0.80, 0.0)}

    return {
        "n": int(len(frame)),
        "pooled": grid(every),
        "saturday": grid(saturday),
        "by_division": by_division,
        "control": dependent_control(dates, claims, won),
    }


def verdicts(results: dict) -> dict:
    """P1-P4 from the pre-registration; P5 is descriptive by design."""
    pooled, sat = results["pooled"], results["saturday"]
    p1 = pooled["k2_r0.8"]
    p3 = sat["k3_r0"]
    p4_cells = [pooled[f"k{k}_r0"] for k in (2, 3, 4, 5, 8, 10)]
    return {
        "P1_pooled_k2_r80_gap_in_minus1_plus3": bool(-0.01 <= p1["gap"] <= 0.03),
        "P2_no_division_k2_r80_resolved_negative": bool(all(
            not (c["excludes_zero"] and c["gap"] < 0)
            for c in (results["by_division"][d]["k2_r0.8"]
                      for d in results["by_division"]) if "gap" in c)),
        "P3_saturday_k3_realised_56_to_63": bool(0.56 <= p3["realised"] <= 0.63),
        "P4_no_resolved_negative_k_le_10_r0": bool(all(
            not (c["excludes_zero"] and c["gap"] < 0) for c in p4_cells)),
        "control_fired": bool(results["control"]["fired"]),
    }


def _print(results: dict) -> None:
    def line(name, c):
        if "gap" not in c:
            print(f"    {name:<10} days {c['days']:>4}  hits {c['hits']:>4}  (too few slips)")
            return
        star = "*" if c["excludes_zero"] else " "
        print(f"    {name:<10} days {c['days']:>4}  hits {c['hits']:>4}  "
              f"claimed {100*c['claimed']:6.2f}%  realised {100*c['realised']:6.2f}%  "
              f"gap {100*c['gap']:+6.2f} [{100*c['ci'][0]:+6.2f},{100*c['ci'][1]:+6.2f}]{star}")
    for split in ("pooled", "saturday"):
        print(f"\n  {split}:")
        for name, c in results[split].items():
            line(name, c)
    print("\n  by division (k=2):")
    for div, cells in results["by_division"].items():
        for name, c in cells.items():
            line(f"{div} {name[3:]}", c)
    ctl = results["control"]
    print(f"\n  control (same match twice, r=0.80): n {ctl['n']}  expected "
          f"+{100*ctl['expected']:.2f}  gap {100*ctl['gap']:+.2f} "
          f"[{100*ctl['ci'][0]:+.2f},{100*ctl['ci'][1]:+.2f}]  "
          f"{'FIRED' if ctl['fired'] else 'DEAD'}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="docs/b24_results.json")
    parser.add_argument("--dry-run", action="store_true",
                        help="print and write JSON, but record no ledger row")
    args = parser.parse_args(argv)

    conn = db.connect()
    frame = load(conn)
    joint = joint_of(frame)
    probs = probs_1x2(joint)
    p_dog15 = b21.dog15_probs(joint, probs)
    market, claims = b21.recommend(probs, p_dog15)
    won = b21.won(market, frame, probs).astype(float)
    print(f"{len(frame):,} matches, {frame.season.min()} -> {frame.season.max()}, "
          f"{frame.division.nunique()} divisions")

    results = probe(frame, claims, won)
    results["verdict"] = verdicts(results)
    _print(results)
    print("  predictions: " + ", ".join(
        f"{k} {'OK' if v else 'NO'}" for k, v in results["verdict"].items()))

    if args.dry_run:
        print("  [dry-run] ledger row NOT written (0 configurations)")
    else:
        ledger.record(
            conn, kind=ledger.PROBE, name="b24_parlay_independence", purpose="dev",
            seasons=DEV_SEASONS, divisions=SERVED_DIVISIONS,
            detail={"pooled_k2_r80": results["pooled"]["k2_r0.8"],
                    "saturday_k3_r0": results["saturday"]["k3_r0"],
                    "control": results["control"],
                    "verdict": results["verdict"]},
            reason="PARLAY_PLAN.md section 3 probe, amended 2026-09-04 before the "
                   "run. The parlay page shows the product of the top-k published "
                   "calls' claims; this row measures realised versus product per "
                   "matchday slip on the dev corpus, with a planted dependent-pair "
                   "control. Re-aggregates outcomes read for gate row 110; no arm, "
                   "no selection -- 0 configurations.")
        print("  [ledger] probe:b24_parlay_independence  (0 configurations)")

    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(results, handle, indent=2, default=str)
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
