"""What effect size a gate could have resolved, by Poisson score information.

    python -m engine.eval.power          # re-evaluate REST and TOD_SLOT

Adopted in `P4_TRAVEL_PLAN.md` §8 after the travel control showed the
deviance-delta criterion missing a planted effect it was demonstrably shown to
contain. This module applies the same statistic backwards, to the two gates
that stated bounds under the weaker one.

**Nothing here reads a match outcome.** Every quantity is a function of the
fitted λs and the feature alone -- Fisher information for a Poisson rate is
`Σλx²`, which needs no goals. So this re-evaluation spends no information about
any real answer and adds no configuration to the deflation count. That is the
whole reason it can be run on closed gates without reopening them.

**It answers the resolution question only.** Adoption stays on goal Poisson
deviance per convention 2. A gate whose bound moves here has not changed its
verdict; it has changed the size of the claim its null can support.
"""

from __future__ import annotations

import json

import numpy as np

from engine import db, ledger
from engine.seasons import DEV_SEASONS, SERVED_DIVISIONS

Z = 1.96


def score_se(lam, x) -> float:
    """Standard error of a multiplicative slope on `x`, for Poisson rates `lam`.

    For a rate `lam*(1 + b*x)` the score information is `Σ lam x²`, so the
    standard error is closed-form. No fit, and therefore none of the
    refit noise that dominates a leave-one-season-out deviance delta.
    """
    lam = np.asarray(lam, dtype=float)
    x = np.asarray(x, dtype=float)
    fisher = float((lam * x * x).sum())
    return 1.0 / np.sqrt(fisher) if fisher > 0 else float("inf")


def resolvable_pct(lam) -> float:
    """Smallest multiplicative effect on a group of rates detectable at 1.96 SE.

    The `x = 1 on this group` case of `score_se`, which is what a per-band or
    per-slot factor actually estimates.
    """
    total = float(np.asarray(lam, dtype=float).sum())
    return 100.0 * Z / np.sqrt(total) if total > 0 else float("inf")


def by_group(lam, groups, *, min_n: int = 30) -> list[dict]:
    lam = np.asarray(lam, dtype=float)
    groups = np.asarray(groups)
    rows = []
    for name in sorted(set(groups.tolist())):
        mask = groups == name
        if mask.sum() < min_n:
            continue
        rows.append({"group": str(name), "n": int(mask.sum()),
                     "lam_sum": float(lam[mask].sum()),
                     "resolvable_pct": resolvable_pct(lam[mask])})
    return rows


def revisit_rest(conn) -> dict:
    from engine.eval import rest as rest_module

    f = rest_module.load(conn)
    lam_h = f.lam_h.to_numpy(float)
    lam_a = f.lam_a.to_numpy(float)
    diff = f["diff"].to_numpy(float)

    # `rest.diff_arm` splits one slope across the two lambdas as +-slope*d/2.
    se = score_se(lam_h + lam_a, diff / 2.0)
    mean_lam = float(np.mean([lam_h.mean(), lam_a.mean()]))
    over_a_week = 100.0 * Z * se * 7.0 / mean_lam

    sides = rest_module.sides_of(f)
    bands = by_group(sides.lam, sides.band.astype(str))
    reference = next(b for b in bands if b["group"] == "7")
    for band in bands:
        band["vs_7day_pct"] = float(np.hypot(band["resolvable_pct"],
                                             reference["resolvable_pct"]))

    print(f"\nREST  n={len(f):,} matches, differential sd {diff.std():.2f} days")
    print(f"  differential slope resolvable at 1.96 SE: {over_a_week:.2f}% of "
          f"rate over a 7-day gap  (REST.md stated ~3.5%)")
    print("  per-band, and as a contrast against the 7-day reference:")
    for band in bands:
        print(f"    {band['group']:>6}  n={band['n']:6,}  alone "
              f"{band['resolvable_pct']:5.2f}%   vs 7-day {band['vs_7day_pct']:5.2f}%")
    return {"n": len(f), "differential_pct_over_7_days": over_a_week,
            "bands": bands, "stated_bound_pct": 3.5}


def revisit_tod(conn) -> dict:
    from engine.eval import tod as tod_module

    f, dropped = tod_module.load(conn)
    lam = np.concatenate([f.lam_h.to_numpy(float), f.lam_a.to_numpy(float)])
    slot = np.concatenate([f.slot.to_numpy(), f.slot.to_numpy()])
    slots = by_group(lam, slot)

    planted = []
    for name, size in tod_module.PLANTED.items():
        match = [s for s in slots if s["group"] == name]
        if not match:
            continue
        t = abs(size) / (1.0 / np.sqrt(match[0]["lam_sum"]))
        planted.append({"slot": name, "planted": size, "t": float(t),
                        "detectable": bool(t > Z)})

    print(f"\nTOD_SLOT  n={len(f):,} scored matches with a kickoff time "
          f"({dropped:,} dropped)")
    print("  per-slot resolvable multiplicative effect at 1.96 SE:")
    for s in slots:
        print(f"    {s['group']:<12} n={s['n']:6,}  {s['resolvable_pct']:5.2f}%")
    print("  the effects H29 planted, under the score test:")
    for p in planted:
        print(f"    {p['slot']:<12} {p['planted']:+.2f}  t={p['t']:5.2f}  "
              f"{'detectable' if p['detectable'] else 'below 1.96'}")
    return {"n": len(f), "slots": slots, "planted": planted}


def main(argv=None) -> int:
    conn = db.connect()
    out = {"rest": revisit_rest(conn), "tod": revisit_tod(conn)}

    ledger.record(
        conn, kind=ledger.PROBE, name="h35_power_revisit", purpose="dev",
        seasons=DEV_SEASONS, divisions=SERVED_DIVISIONS, detail=out,
        reason="Re-evaluates the bounds REST (section 1.5) and TOD_SLOT "
               "(section 1.4) stated under the deviance-delta criterion, using "
               "the Poisson score statistic adopted in P4_TRAVEL_PLAN.md "
               "section 8. Reads no match outcomes -- Fisher information for a "
               "Poisson rate needs only the fitted lambdas -- so it spends no "
               "information and adds no configuration to the deflation count. "
               "Neither verdict changes; what changes is the size of claim each "
               "null can support.")
    print("\n  [ledger] probe:h35_power_revisit")

    with open("docs/power_revisit.json", "w", encoding="utf-8") as handle:
        json.dump(out, handle, indent=2, default=str)
    print("wrote docs/power_revisit.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
