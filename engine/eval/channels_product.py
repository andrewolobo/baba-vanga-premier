"""B14: what does the corners channel do to what the product actually publishes?

    python -m engine.eval.channels_product --probe      # free, reads no result
    python -m engine.eval.channels_product              # the gate, 3 configs

`CHANNELS_GATE.md` priced the channel in **goal deviance** and `BACKLOG.md` B14
then offered adoption as a judgement call on that number. The product is sold on
**strike rate**. B12's own product-facing figures for `+corners` are 1X2
-0.00033 and O/U -0.00074, an order of magnitude below the channel that shipped,
so "a better lambda improves every item on the menu" may be true and far too
small to see. Deciding on a currency the product does not sell is the error
`OUTSTANDING.md` §9.12 recorded against itself.

**The probe runs first and alone.** It compares the two recommendation vectors
to each other and never scores either against a result, so it carries no arm
list and spends nothing -- the same licence as `power.py` and `home_term`
step 1. A rule whose output does not move cannot move its strike rate, so the
probe can close B14 for free. It did not: 6.914% of recommendations change.

**Two controls, because they fail in different ways.** C1 is
`home_term.matched_sham`, tuned to the real arm's change rate but blind to every
outcome. C2 is the structural parallel -- same code path, same weight, same
channel count, no information -- which changes 23.3% of recommendations rather
than 6.9%, because a real channel is coherent with the existing head and noise
scatters. Neither alone answers "is it the information or the perturbation".

Pre-registration, including the four predictions and the read: `BACKLOG.md` B14.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import replace

import numpy as np

from engine import db, ledger, store
from engine.eval import bootstrap, selection
from engine.eval.channels_gate import SHIPPED, with_noise
from engine.eval.home_term import matched_sham, scored_mask
from engine.eval.p1 import served
from engine.eval.selection import (
    ALLOW_12,
    CEILING,
    SHIPPED_FLOOR,
    _won,
    recommend,
)
from engine.eval.walkforward import walk_forward
from engine.seasons import DEV_SEASONS, SERVED_DIVISIONS

#: The selected composite weight. Not swept here -- h38 chose it under the 1-SE
#: rule and `CHANNELS_GATE.md` §4 records the choice. Re-sweeping it against a
#: second objective is exactly the joint sweep §9.8 says not to run.
WEIGHT = 0.30

#: The adoption candidate. `BACKLOG.md` B14 recommends `+corners` over `+both`:
#: 90% of the deviance gain with one fewer channel.
CORNERS = replace(SHIPPED, shots_blend=WEIGHT, blend_channels=("sot", "corners"))

#: C2, the structural parallel. Identical in every respect except that the added
#: channel is Poisson noise at the corners rate, independent of every match.
NOISE = replace(SHIPPED, shots_blend=WEIGHT, blend_channels=("sot", "noise1"))


def read_verdict(a1: dict, c1: dict) -> str:
    """`BACKLOG.md` B14's read, fixed before the gate ran.

    Extracted so it is pinned by a test rather than by a paragraph. The VOID
    branch is checked FIRST and that ordering is the point: if a blind
    perturbation also gains, the instrument is measuring perturbation rather
    than information and A1's own interval says nothing -- which would otherwise
    read as a GO.
    """
    if c1["vs_shipped_excludes_zero"] and c1["vs_shipped"] > 0:
        return "VOID"
    if a1["vs_shipped_excludes_zero"] and a1["vs_shipped"] > c1["vs_shipped"]:
        return "GO"
    return "NO-GO"


def frame_for(raw, cfg):
    frame = served(walk_forward(raw, cfg)).reset_index(drop=True)
    return frame.dropna(subset=["ftr"]).reset_index(drop=True)


def probe(raw) -> dict:
    """Free: does the rule's output move at all? Reads no match result."""
    print("\nPROBE  does the corners head change what the product says? "
          "(no result read)")
    base = frame_for(raw, SHIPPED)
    idx = np.flatnonzero(scored_mask(base))
    base_probs = selection.raw_probs(base)
    base_market, _ = recommend(base_probs, SHIPPED_FLOOR, allow_12=ALLOW_12)

    out = {}
    print(f"  {'arm':>10} {'changed':>9} {'mean |dp_h|':>12} {'claimed':>9}"
          f"   mix 12/1X/X2/H/A")
    for name, cfg in (("shipped", SHIPPED), ("+corners", CORNERS)):
        frame = frame_for(raw, cfg)
        assert (frame.match_id.to_numpy() == base.match_id.to_numpy()).all()
        probs = selection.raw_probs(frame)
        market, p = recommend(probs, SHIPPED_FLOOR, allow_12=ALLOW_12)
        changed = float((market[idx] != base_market[idx]).mean())
        dp = np.abs(probs[idx, 0] - base_probs[idx, 0])
        mix = {m: round(float((market[idx] == m).mean()), 4)
               for m in ("12", "1X", "X2", "H", "A")}
        out[name] = {"changed_share": round(changed, 5),
                     "mean_abs_dp_home": round(float(dp.mean()), 5),
                     "claimed": round(float(p[idx].mean()), 5), "mix": mix}
        print(f"  {name:>10} {100*changed:>8.3f}% {dp.mean():>12.5f} "
              f"{100*out[name]['claimed']:>8.3f}%   "
              + " ".join(f"{100*v:.1f}" for v in mix.values()))
    return out


def gate(raw) -> dict:
    """A1 against two blind controls, paired on the shipped rule."""
    print("\nB14  the corners channel in the product's currency "
          f"(floor {SHIPPED_FLOOR}, ceiling {CEILING})")
    noisy = with_noise(raw)
    base = frame_for(raw, SHIPPED)
    scored = scored_mask(base)
    idx = np.flatnonzero(scored)
    ftr = base.ftr.to_numpy()
    blocks = bootstrap.week_blocks(base.match_date.iloc[idx])

    base_probs = selection.raw_probs(base)
    corners_probs = selection.raw_probs(frame_for(raw, CORNERS))
    noise_probs = selection.raw_probs(frame_for(noisy, NOISE))

    # C1 is tuned to A1's change rate and never sees a result -- `matched_sham`
    # fits `t` against the corners arm's recommendations, not against `ftr`.
    sham_probs, t = matched_sham(base, base_probs, corners_probs, scored)
    print(f"  control C1: temperature t = {t:.3f}, matched to the corners arm's "
          f"change rate and blind to every outcome")

    arms = {"shipped": base_probs, "A1 +corners": corners_probs,
            "C1 sham": sham_probs, "C2 +noise1": noise_probs}

    base_won = None
    rows = []
    print(f"\n  {'arm':>13} {'changed':>9} {'strike':>8} "
          f"{'vs shipped, PAIRED':>26} {'claimed':>9}   mix 12/1X/X2/H/A")
    for name, probs in arms.items():
        market, p = recommend(probs, SHIPPED_FLOOR, allow_12=ALLOW_12)
        won = _won(market, ftr).astype(float)
        if base_won is None:
            base_won, base_market = won, market
        cmp = bootstrap.paired(won[idx], base_won[idx], blocks)
        honesty = bootstrap.paired(won[idx], p[idx], blocks)
        mix = {m: round(float((market[idx] == m).mean()), 4)
               for m in ("12", "1X", "X2", "H", "A")}
        row = {"arm": name,
               "changed_share": round(float((market[idx] != base_market[idx]).mean()), 5),
               "strike": round(float(won[idx].mean()), 5),
               "claimed": round(float(p[idx].mean()), 5),
               "vs_shipped": round(100 * float(cmp.delta), 3),
               "vs_shipped_ci": [round(100 * cmp.ci[0], 3), round(100 * cmp.ci[1], 3)],
               "vs_shipped_excludes_zero": bool(cmp.excludes_zero),
               "honesty_gap": round(100 * float(honesty.delta), 2),
               "honesty_gap_ci": [round(100 * honesty.ci[0], 2),
                                  round(100 * honesty.ci[1], 2)],
               "mix": mix}
        rows.append(row)
        print(f"  {name:>13} {100*row['changed_share']:>8.3f}% "
              f"{100*row['strike']:>7.3f}% {row['vs_shipped']:>+8.3f} "
              f"[{row['vs_shipped_ci'][0]:>+6.3f},{row['vs_shipped_ci'][1]:>+6.3f}]"
              f"{'*' if row['vs_shipped_excludes_zero'] else ' '}"
              f"{100*row['claimed']:>8.3f}%   "
              + " ".join(f"{100*v:.1f}" for v in mix.values()))

    verdict = read_verdict(next(r for r in rows if r["arm"] == "A1 +corners"),
                           next(r for r in rows if r["arm"] == "C1 sham"))
    print(f"\n  pre-registered read: {verdict}")

    a1_market, _ = recommend(corners_probs, SHIPPED_FLOOR, allow_12=ALLOW_12)
    a1_won = _won(a1_market, ftr).astype(float)
    per_division = {}
    for division in SERVED_DIVISIONS:
        sel = scored & (base.division == division).to_numpy()
        j = np.flatnonzero(sel)
        cmp = bootstrap.paired(a1_won[j], base_won[j],
                               bootstrap.week_blocks(base.match_date.iloc[j]))
        per_division[division] = {
            "delta": round(100 * float(cmp.delta), 3),
            "ci": [round(100 * cmp.ci[0], 3), round(100 * cmp.ci[1], 3)],
            "excludes_zero": bool(cmp.excludes_zero), "n": int(len(j))}
    print("\n  A1 per division (paired, pts of strike rate)")
    for d, v in per_division.items():
        print(f"    {d}  n={v['n']:>5,}  {v['delta']:>+7.3f} "
              f"[{v['ci'][0]:>+6.3f},{v['ci'][1]:>+6.3f}]"
              f"{'*' if v['excludes_zero'] else ''}")

    return {"temperature": t, "verdict": verdict, "arms": rows,
            "per_division": per_division}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--probe", action="store_true",
                        help="the free control only; writes no ledger row")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--out", default="docs/channels_product_results.json")
    args = parser.parse_args(argv)

    conn = db.connect()
    raw = store.read_matches(conn, seasons=DEV_SEASONS).for_measurement()

    results = {"probe": probe(raw)}
    if args.probe:
        print("\n  [probe] no ledger row -- no result was scored")
    else:
        results["gate"] = gate(raw)
        arms = [{"arm": r["arm"], "strike": r["strike"],
                 "changed_share": r["changed_share"],
                 "vs_shipped": r["vs_shipped"]}
                for r in results["gate"]["arms"] if r["arm"] != "shipped"]
        if args.dry_run:
            print("\n  [dry-run] ledger row NOT written")
        else:
            ledger.record(
                conn, kind=ledger.GATE, name="b14_corners_in_product",
                purpose="dev", seasons=DEV_SEASONS, divisions=SERVED_DIVISIONS,
                detail={**results, "arms": arms},
                reason="BACKLOG.md B14, pre-registered before running. B12 "
                       "priced the corners channel in goal deviance and B14 "
                       "then offered adoption as a judgement on that number, "
                       "but the product is sold on STRIKE RATE and nothing had "
                       "measured it there -- the same criticism OUTSTANDING.md "
                       "9.12 made of itself. A free probe ran first and alone "
                       "and found 6.914% of recommendations change, so the "
                       "question was live. Three arms: the candidate head, a "
                       "temperature sham matched to its change rate, and the "
                       "structural-parallel noise channel. Three "
                       "configurations, one per arm, per the home_term_away_leg "
                       "accounting.")
            print("\n  [ledger] gate:b14_corners_in_product  (3 configurations)")

    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(results, handle, indent=2, default=str)
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
