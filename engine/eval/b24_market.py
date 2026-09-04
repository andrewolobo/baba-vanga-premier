"""B24 market-legs probe: do the parlay page's *derived* legs deliver?

    python -m engine.eval.b24_market --dry-run   # printed, no ledger row
    python -m engine.eval.b24_market             # probe row, 0 configurations

Pre-registration is `docs/PARLAY_PLAN.md` §9 (2026-09-04, written before
this ran). The type control is becoming a market selector (D12): a game
whose published call is not of the chosen type contributes its likeliest
option *of* that type instead. Those derived legs are a different
population from anything measured before -- favourites below the floor,
unions on games the rule called outright, the +1.5 on games it hedged --
so their claimed-versus-delivered is read here, per type, before the page
ships them. Row 113 measured the published-call product and stands for the
default view; this row measures the new legs and their products.

Controls (convention 8): the row-113 dependent pair must fire on the
products, and a planted +5-pt shift of every claim must read a resolved
negative calibration gap, or the instrument cannot see over-claiming.

**0 configurations, one probe row.** Outcomes were read for rows 110/113;
every statistic here re-aggregates the same matches' outcomes, and nothing
is selected from the result -- the pre-registered consequence of a bad
read is an offset or a per-type veto on the page, not a choice of arm.
"""

from __future__ import annotations

import argparse
import json

import numpy as np
import pandas as pd

from engine import db, ledger
from engine.eval import b21, bootstrap
from engine.eval.b24 import SATURDAY_MIN, cell, slip_table
from engine.eval.p7 import joint_of, load, probs_1x2
from engine.seasons import DEV_SEASONS, SERVED_DIVISIONS

GROUP = {"H": "win", "A": "win", "1X": "dc", "X2": "dc", "12": "dc",
         b21.DOG15: "ah"}
SLIP_K = (2, 3, 5, 10)
BUCKETS = tuple((lo / 10, lo / 10 + 0.1) for lo in range(3, 10))
MIN_BUCKET = 300


def type_leg(t: str, probs: np.ndarray, p_dog15: np.ndarray,
             pub_market: np.ndarray, pub_p: np.ndarray):
    """(side, claim, derived?) per match for market type `t` -- the D12 rule.

    The published call where its group is `t`; else the likeliest option of
    `t`: the favourite for `win`, the best of `1X`/`X2`/`12` (ties to the
    earlier) for `dc`, the underdog +1.5 (fav-relative `D+1.5`) for `ah`.
    D13: no veto -- every match contributes a leg.
    """
    ph, pd_, pa = probs[:, 0], probs[:, 1], probs[:, 2]
    if t == "win":
        d_side = np.where(ph >= pa, "H", "A")
        d_p = np.maximum(ph, pa)
    elif t == "dc":
        stack = np.column_stack([ph + pd_, pa + pd_, ph + pa])
        names = np.array(["1X", "X2", "12"])
        best = stack.argmax(axis=1)
        d_side = names[best]
        d_p = stack[np.arange(len(stack)), best]
    else:
        d_side = np.full(len(probs), b21.DOG15)
        d_p = p_dog15
    published = np.array([GROUP[m] for m in pub_market]) == t
    return (np.where(published, pub_market, d_side),
            np.where(published, pub_p, d_p),
            ~published)


def calibration(won: np.ndarray, claims: np.ndarray, dates) -> dict:
    cmp = bootstrap.paired(won, claims, bootstrap.week_blocks(dates))
    return {"n": int(len(won)),
            "claimed": round(float(claims.mean()), 5),
            "delivered": round(float(won.mean()), 5),
            "gap": round(float(cmp.delta), 5),
            "ci": [round(cmp.ci[0], 5), round(cmp.ci[1], 5)],
            "excludes_zero": bool(cmp.excludes_zero)}


def buckets(won: np.ndarray, claims: np.ndarray) -> list[dict]:
    rows = []
    for lo, hi in BUCKETS:
        m = (claims >= lo) & (claims < hi)
        if m.sum() >= MIN_BUCKET:
            rows.append({"bucket": f"[{lo:.1f},{hi:.1f})", "n": int(m.sum()),
                         "claimed": round(float(claims[m].mean()), 4),
                         "delivered": round(float(won[m].mean()), 4)})
    return rows


def probe(frame: pd.DataFrame, probs: np.ndarray, p_dog15: np.ndarray,
          pub_market: np.ndarray, pub_p: np.ndarray) -> dict:
    dates = frame.match_date.to_numpy()
    day_size = pd.Series(dates).map(pd.Series(dates).value_counts()).to_numpy()
    saturday = day_size >= SATURDAY_MIN
    out = {"n": int(len(frame)), "types": {}}
    for t in ("win", "dc", "ah"):
        side, claim, derived = type_leg(t, probs, p_dog15, pub_market, pub_p)
        won = b21.won(side, frame, probs).astype(float)
        products = {}
        for k in SLIP_K:
            products[f"k{k}"] = cell(slip_table(dates, claim, won, k=k, r=0.0))
            products[f"k{k}_saturday"] = cell(slip_table(
                dates[saturday], claim[saturday], won[saturday], k=k, r=0.0))
        out["types"][t] = {
            "derived_share": round(float(derived.mean()), 4),
            "all": calibration(won, claim, dates),
            "derived_only": calibration(won[derived], claim[derived],
                                        dates[derived]),
            "buckets_derived": buckets(won[derived], claim[derived]),
            "products": products,
        }
        # The planted over-claim: +5 pts on every claim must read resolved
        # negative, or over-claiming is invisible to this instrument.
        shifted = calibration(won, np.clip(claim + 0.05, 0.0, 1.0), dates)
        out["types"][t]["shift_control"] = {
            "gap": shifted["gap"], "ci": shifted["ci"],
            "fired": bool(shifted["excludes_zero"] and shifted["gap"] < 0)}
    return out


def verdicts(results: dict) -> dict:
    t = results["types"]

    def resolved_negative(c):
        return c["excludes_zero"] and c["gap"] < 0

    m4 = all(not resolved_negative(t[typ]["products"][f"k{k}"])
             for typ in t for k in (2, 3))
    return {
        "M1_win_gap_p05_to_p50_resolved": bool(
            0.005 <= t["win"]["all"]["gap"] <= 0.050
            and t["win"]["all"]["excludes_zero"] and t["win"]["all"]["gap"] > 0),
        "M2_dc_gap_m10_to_p20": bool(-0.010 <= t["dc"]["all"]["gap"] <= 0.020),
        "M3_ah_gap_m10_to_p15": bool(-0.010 <= t["ah"]["all"]["gap"] <= 0.015),
        "M4_no_resolved_negative_product_k2_k3": bool(m4),
        "M5_shift_controls_fired": bool(all(
            t[typ]["shift_control"]["fired"] for typ in t)),
    }


def _print(results: dict) -> None:
    for typ, r in results["types"].items():
        star = lambda c: "*" if c["excludes_zero"] else " "
        a, d = r["all"], r["derived_only"]
        print(f"\n  {typ}  (derived {100*r['derived_share']:.1f}% of matches)")
        for name, c in (("all legs", a), ("derived only", d)):
            print(f"    {name:<13} n {c['n']:>6}  claimed {100*c['claimed']:6.2f}%  "
                  f"delivered {100*c['delivered']:6.2f}%  gap {100*c['gap']:+6.2f} "
                  f"[{100*c['ci'][0]:+6.2f},{100*c['ci'][1]:+6.2f}]{star(c)}")
        for b in r["buckets_derived"]:
            print(f"      {b['bucket']}  n {b['n']:>5}  claims {100*b['claimed']:5.1f}"
                  f"  delivers {100*b['delivered']:5.1f}")
        for k in SLIP_K:
            c = r["products"][f"k{k}"]
            if "gap" in c:
                print(f"    product k={k:<2} days {c['days']:>4}  claimed "
                      f"{100*c['claimed']:6.2f}%  realised {100*c['realised']:6.2f}%  "
                      f"gap {100*c['gap']:+6.2f} [{100*c['ci'][0]:+6.2f},"
                      f"{100*c['ci'][1]:+6.2f}]{star(c)}")
        ctl = r["shift_control"]
        print(f"    +5pt shift control: gap {100*ctl['gap']:+.2f} "
              f"{'FIRED' if ctl['fired'] else 'DEAD'}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="docs/b24_market_results.json")
    parser.add_argument("--dry-run", action="store_true",
                        help="print and write JSON, but record no ledger row")
    args = parser.parse_args(argv)

    conn = db.connect()
    frame = load(conn)
    joint = joint_of(frame)
    probs = probs_1x2(joint)
    p_dog15 = b21.dog15_probs(joint, probs)
    pub_market, pub_p = b21.recommend(probs, p_dog15)
    print(f"{len(frame):,} matches, {frame.season.min()} -> {frame.season.max()}")

    results = probe(frame, probs, p_dog15, pub_market, pub_p)
    results["verdict"] = verdicts(results)
    _print(results)
    print("\n  predictions: " + ", ".join(
        f"{k} {'OK' if v else 'NO'}" for k, v in results["verdict"].items()))

    if args.dry_run:
        print("  [dry-run] ledger row NOT written (0 configurations)")
    else:
        ledger.record(
            conn, kind=ledger.PROBE, name="b24_market_legs", purpose="dev",
            seasons=DEV_SEASONS, divisions=SERVED_DIVISIONS,
            detail={typ: {"all": results["types"][typ]["all"],
                          "derived_only": results["types"][typ]["derived_only"],
                          "shift_control": results["types"][typ]["shift_control"]}
                    for typ in results["types"]} | {"verdict": results["verdict"]},
            reason="PARLAY_PLAN.md section 9 pre-registration, written before the "
                   "run. The parlay page's type control becomes a market selector "
                   "(D12): derived legs are a new population, and this row reads "
                   "their claimed-versus-delivered per type plus their slip "
                   "products, with a planted +5-pt over-claim control per type. "
                   "Re-aggregates outcomes read for rows 110/113; no arm, no "
                   "selection -- 0 configurations.")
        print("  [ledger] probe:b24_market_legs  (0 configurations)")

    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(results, handle, indent=2, default=str)
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
