"""B17: lower-division totals -- is the pmf thin (dispersion) or low (level)?

    python -m engine.eval.b17 --dry-run
    python -m engine.eval.b17

Pre-registration is `BACKLOG.md` B17, written 2026-08-16 before this ran.
`TIPSTER.md` Part B found E0 calibrated at every goal line and E1-E3
over-claiming their confident *unders* by 4-9 points. Two mechanisms produce
that, and they need different fixes:

  level       the joint fit's single intercept centres lower-division low-lambda
              fixtures too low. Signature: a POSITIVE mean residual
              total - (lam_h + lam_a) in the low-lambda buckets, and a
              variance ratio near 1. Fix: a per-division intercept.
  dispersion  lower-division totals are more variable than independent Poisson.
              Signature: mean residual near zero, variance ratio above 1.
              Fix: a dispersion term or a different head.

Everything is on stored walk-forward lambdas -- no refit, no arm, no choice.
Reads outcomes for a diagnostic; **0 configurations**. E0 is the negative
control: it must read clean, or the instrument is not reading the defect.

The dispersion statistic is `(var(total) - var(c*lam)) / mean(c*lam)` with
`c = mean(total)/mean(lam)` -- lambda rescaled to the observed level first.
Under a Poisson mixture with per-match rate c*lam, var(total) = E[c lam] +
var(c lam), so this is 1 when the pmf's SPREAD is right, whatever its level
and however much lambda itself varies across matches. Without the rescaling a
pure level shift of 8% reads as a ratio of ~1.1 (planted and seen in
`tests/test_b17.py`), and the two mechanisms cannot be told apart. `c - 1` is
reported as the relative level; the raw var/mean of totals is shown beside
both but is inflated by heterogeneity and is not the test.

The mechanism is read off intervals, not point estimates: LEVEL when at least
two of E1-E3 have a resolved-positive low-lambda residual and no resolved
excess dispersion; DISPERSION when the reverse; BOTH or NEITHER otherwise. The
numeric predictions in `BACKLOG.md` B17 are scored separately.
"""

from __future__ import annotations

import argparse
import json

import numpy as np
import pandas as pd

from engine import db, ledger
from engine.eval import bootstrap, p7
from engine.eval.dispersion import over_under_probs
from engine.seasons import DEV_SEASONS, SERVED_DIVISIONS

#: The confident-under region Part B measured, in P(under 2.5).
UNDER_BUCKETS = ((0.50, 0.60), (0.60, 0.70), (0.70, 1.01))
#: The bucket P2 is stated on: Part B's [0.60, 0.70) under-2.5 bucket.
P2_BUCKET = (0.60, 0.70)
#: And the mirror, so a one-signed level defect can be told from a symmetric one.
OVER_BUCKETS = ((0.60, 0.70), (0.70, 1.01))

CONTROL = "E0"
REPS = 2000
SEED = 17


def _block_ci(fn, blocks: np.ndarray, *arrays, reps: int = REPS, seed: int = SEED):
    """Block bootstrap of an arbitrary statistic `fn(*arrays)`."""
    keys, positions = np.unique(blocks, return_inverse=True)
    members = [np.flatnonzero(positions == k) for k in range(len(keys))]
    rng = np.random.default_rng(seed)
    point = float(fn(*arrays))
    draws = np.empty(reps)
    for r in range(reps):
        pick = rng.integers(0, len(members), len(members))
        idx = np.concatenate([members[i] for i in pick])
        draws[r] = fn(*[a[idx] for a in arrays])
    lo, hi = np.quantile(draws, [0.025, 0.975])
    return {"value": round(point, 4), "ci_low": round(float(lo), 4),
            "ci_high": round(float(hi), 4)}


def dispersion_ratio(total: np.ndarray, lam: np.ndarray) -> float:
    scaled = lam * (total.mean() / lam.mean())
    return float((total.var(ddof=1) - scaled.var(ddof=1)) / scaled.mean())


def relative_level(total: np.ndarray, lam: np.ndarray) -> float:
    return float(total.mean() / lam.mean() - 1.0)


def raw_ratio(total: np.ndarray, lam: np.ndarray) -> float:  # noqa: ARG001
    return float(total.var(ddof=1) / total.mean())


def mean_residual(total: np.ndarray, lam: np.ndarray) -> float:
    return float((total - lam).mean())


def diagnose(frame: pd.DataFrame, joint: np.ndarray) -> dict:
    total = (frame.fthg + frame.ftag).to_numpy(float)
    lam = (frame.lam_h + frame.lam_a).to_numpy(float)
    p_over, p_under = over_under_probs(joint, 2.5)
    divisions = frame.division.to_numpy()
    blocks_all = bootstrap.week_blocks(frame.match_date)

    print(f"\nB17  totals: dispersion or level?  ({len(frame):,} matches)")
    print(f"    {'div':>4} {'n':>6} {'disp ratio (level-corr)':>24} {'rel level':>22} "
          f"{'resid, all':>22} {'resid, P(under) .6-.7':>26}")
    out = {}
    for d in SERVED_DIVISIONS:
        sel = divisions == d
        t, l, b = total[sel], lam[sel], blocks_all[sel]
        row = {
            "n": int(sel.sum()),
            "dispersion_ratio": _block_ci(dispersion_ratio, b, t, l),
            "relative_level": _block_ci(relative_level, b, t, l),
            "raw_var_over_mean": _block_ci(raw_ratio, b, t, l),
            "residual_all": _block_ci(mean_residual, b, t, l),
            "residual_by_under_bucket": {},
            "residual_by_over_bucket": {},
        }
        for lo, hi in UNDER_BUCKETS:
            m = sel & (p_under >= lo) & (p_under < hi)
            row["residual_by_under_bucket"][f"[{lo:.2f},{hi:.2f})"] = (
                {"n": int(m.sum()), **_block_ci(mean_residual, blocks_all[m], total[m], lam[m])}
                if m.sum() >= 50 else {"n": int(m.sum())})
        for lo, hi in OVER_BUCKETS:
            m = sel & (p_over >= lo) & (p_over < hi)
            row["residual_by_over_bucket"][f"[{lo:.2f},{hi:.2f})"] = (
                {"n": int(m.sum()), **_block_ci(mean_residual, blocks_all[m], total[m], lam[m])}
                if m.sum() >= 50 else {"n": int(m.sum())})
        out[d] = row
        p2 = row["residual_by_under_bucket"][f"[{P2_BUCKET[0]:.2f},{P2_BUCKET[1]:.2f})"]
        f = lambda c: f"{c['value']:+.3f} [{c['ci_low']:+.3f},{c['ci_high']:+.3f}]"  # noqa: E731
        p2_cell = (f(p2) + f" n={p2['n']:,}") if "value" in p2 else "n<50"
        print(f"    {d:>4} {row['n']:>6,} {f(row['dispersion_ratio']):>24} "
              f"{f(row['relative_level']):>22} {f(row['residual_all']):>22} "
              f"{p2_cell:>26}")

    key = f"[{P2_BUCKET[0]:.2f},{P2_BUCKET[1]:.2f})"
    ctl = out[CONTROL]
    names = [d for d in SERVED_DIVISIONS if d != CONTROL]
    lower = [out[d] for d in names]

    def covers(ci, lo, hi):
        return ci["ci_low"] <= hi and ci["ci_high"] >= lo

    # P1: the control is not resolved away from clean on either statistic.
    p1 = (covers(ctl["dispersion_ratio"], 0.98, 1.04)
          and covers(ctl["residual_by_under_bucket"][key], -0.05, 0.05))
    p2_cis = [r["residual_by_under_bucket"][key] for r in lower]
    level_hits = [c for c in p2_cis if "value" in c and c["ci_low"] > 0]
    p2 = sum(1 for c in level_hits if 0.10 <= c["value"] <= 0.25) >= 2
    gaps = [r["dispersion_ratio"]["value"] - ctl["dispersion_ratio"]["value"] for r in lower]
    disp_hits = [r for r, g in zip(lower, gaps)
                 if r["dispersion_ratio"]["ci_low"] > 1.0 and g >= 0.05]
    p3 = all(g < 0.05 for g in gaps)
    p4 = len(level_hits) == 0 and len(disp_hits) >= 2
    level_signal = len(level_hits) >= 2
    dispersion_signal = len(disp_hits) >= 2
    verdict = {"P1_control_clean": p1,
               "P2_lower_low_lambda_residual_positive_10_to_25": p2,
               "P3_ratio_gap_under_0_05": p3,
               "P4_alternative_dispersion": p4,
               "level_signal_divisions": len(level_hits),
               "dispersion_signal_divisions": len(disp_hits),
               "ratio_gap_vs_control": {d: round(g, 4) for d, g in zip(names, gaps)}}
    mechanism = ("instrument not clean on the control" if not p1
                 else "LEVEL (per-division intercept is the fix to gate)"
                 if level_signal and not dispersion_signal
                 else "DISPERSION (a model change is the fix to gate)"
                 if dispersion_signal and not level_signal
                 else "BOTH -- level and dispersion each resolved"
                 if level_signal and dispersion_signal
                 else "NEITHER resolved -- read the tables")
    verdict["mechanism"] = mechanism
    print("    predictions: " + ", ".join(f"{k} {'OK' if v else 'NO'}"
                                          for k, v in verdict.items() if isinstance(v, bool)))
    print(f"    reading: {mechanism}")
    return {"by_division": out, "verdict": verdict}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="docs/b17_results.json")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    conn = db.connect()
    frame = p7.load(conn)
    joint = p7.joint_of(frame)
    results = diagnose(frame, joint)

    if args.dry_run:
        print("  [dry-run] probe:b17_totals_mechanism NOT written")
    else:
        ledger.record(
            conn, kind=ledger.PROBE, name="b17_totals_mechanism", purpose="dev",
            seasons=DEV_SEASONS, divisions=SERVED_DIVISIONS, detail=results,
            reason="BACKLOG.md B17. Per-division dispersion ratio and mean residual of "
                   "totals on stored walk-forward lambdas, E0 as the negative control, "
                   "to tell a level defect from a dispersion defect behind TIPSTER.md "
                   "Part B. Diagnostic; no arm list; zero configurations. The fix, "
                   "whichever it is, needs its own gate.")
        print("  [ledger] probe:b17_totals_mechanism  (0 configurations)")
    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(results, handle, indent=2, default=str)
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
