"""B21 referee probe: a market-implied `D+1.5` probability from 1X2 prices.

    python -m engine.eval.b21_referee --dry-run   # no ledger row
    python -m engine.eval.b21_referee             # probe row, 0 configurations

Pre-registration is `docs/BACKLOG.md` B21 ("Referee probe"), written before
this ran. The +1.5 handicap has no corpus price (B5), so the B21 arm's calls
cannot be checked against the market directly. This probe builds the derived
referee: fit (lam_h, lam_a) to each match's devigged avg 1X2 prices -- two
parameters against two free targets, exactly identified -- and push them
through the same Poisson score matrix the model uses, giving a market-implied
`D+1.5` probability. Both sides are Poisson-mediated, so the pmf-shape bias
largely cancels and the gap isolates the lambdas.

Three parts, one probe row, 0 configurations:

  fit        Newton solve per match; convergence and residuals. Prices only.
  compare    model claim vs market-implied claim where the B21 arm publishes
             `D+1.5`; gap, week-block CI, per season and division; agreement
             of the v3 rule run on each side's probabilities. Prices + lambda.
  calibrate  the referee's own claim-versus-delivered, buckets on the pooled
             population -- a MARKET-defined quantity (market underdog, market
             probability; no model arm), the same footing as B20's base rate
             and B17's residual probe. Carries a planted control: market
             lambdas jittered by exp(N(0, 0.25)) must read overconfident.
"""

from __future__ import annotations

import argparse
import json

import numpy as np
import pandas as pd

from engine import db, ledger
from engine.eval import b21, bootstrap, selection
from engine.eval.dispersion import outcome_probs, score_matrix
from engine.eval.p7 import joint_of, load, probs_1x2
from engine.odds import devig_probs
from engine.seasons import DEV_SEASONS, SERVED_DIVISIONS

#: Newton fit controls. The map (log lam_h, log lam_a) -> (p_h, p_a) is smooth
#: and the targets are interior, so plain damped Newton with forward-difference
#: Jacobians is enough.
MAX_ITER = 40
EPS = 1e-5
STEP_CLIP = 0.5
TOL = 1e-6
LAM_LO, LAM_HI = 0.05, 8.0

BUCKETS = ((0.50, 0.60), (0.60, 0.70), (0.70, 0.80), (0.80, 0.90), (0.90, 1.01))
MIN_BUCKET = 200
CONTROL_JITTER_SD = 0.25
CONTROL_SEED = 7


def _ph_pa(lam_h: np.ndarray, lam_a: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    home, _, away = outcome_probs(score_matrix(lam_h, lam_a))
    return home, away


def _grid_init(q_h: np.ndarray, q_a: np.ndarray) -> np.ndarray:
    """Nearest coarse-grid (log lam_h, log lam_a) per match, so Newton starts
    near the answer everywhere and cannot be trapped at the box corner by the
    step clip on an extreme fixture."""
    g = np.log(np.geomspace(0.15, 6.0, 40))
    gh, ga = np.meshgrid(g, g, indexing="ij")
    cells = np.column_stack([gh.ravel(), ga.ravel()])
    c_h, c_a = _ph_pa(np.exp(cells[:, 0]), np.exp(cells[:, 1]))
    d = (c_h[None, :] - q_h[:, None]) ** 2 + (c_a[None, :] - q_a[:, None]) ** 2
    return cells[d.argmin(axis=1)].copy()


def fit_market_lambdas(q_h: np.ndarray, q_a: np.ndarray):
    """(lam_h, lam_a, residual) matching devigged (q_h, q_a) per match."""
    x = _grid_init(q_h, q_a)
    for _ in range(MAX_ITER):
        lam = np.exp(x)
        f_h, f_a = _ph_pa(lam[:, 0], lam[:, 1])
        r_h, r_a = f_h - q_h, f_a - q_a
        if max(np.abs(r_h).max(), np.abs(r_a).max()) < TOL:
            break
        # Forward-difference Jacobian in the log-lambda coordinates.
        g_h, g_a = _ph_pa(np.exp(x[:, 0] + EPS), lam[:, 1])
        j00, j10 = (g_h - f_h) / EPS, (g_a - f_a) / EPS
        g_h, g_a = _ph_pa(lam[:, 0], np.exp(x[:, 1] + EPS))
        j01, j11 = (g_h - f_h) / EPS, (g_a - f_a) / EPS
        det = j00 * j11 - j01 * j10
        det = np.where(np.abs(det) < 1e-12, 1e-12, det)
        dx0 = (j11 * r_h - j01 * r_a) / det
        dx1 = (j00 * r_a - j10 * r_h) / det
        x[:, 0] -= np.clip(dx0, -STEP_CLIP, STEP_CLIP)
        x[:, 1] -= np.clip(dx1, -STEP_CLIP, STEP_CLIP)
        x = np.clip(x, np.log(LAM_LO), np.log(LAM_HI))
    lam = np.exp(x)
    f_h, f_a = _ph_pa(lam[:, 0], lam[:, 1])
    residual = np.maximum(np.abs(f_h - q_h), np.abs(f_a - q_a))
    return lam[:, 0], lam[:, 1], residual


def referee_probs(lam_h: np.ndarray, lam_a: np.ndarray):
    """(1x2 probs, D+1.5 prob) from market lambdas, same pmf as the model."""
    joint = score_matrix(lam_h, lam_a)
    probs = np.column_stack(outcome_probs(joint))
    return probs, b21.dog15_probs(joint, probs)


def calibration_table(claim: np.ndarray, won: np.ndarray, label: str) -> list[dict]:
    print(f"\n  {label}")
    rows = []
    for lo, hi in BUCKETS:
        sel = (claim >= lo) & (claim < hi)
        if sel.sum() < MIN_BUCKET:
            continue
        actual = float(won[sel].mean())
        half = 1.96 * float(np.sqrt(actual * (1 - actual) / sel.sum()))
        claimed = float(claim[sel].mean())
        verdict = ("overconfident" if actual < claimed - half
                   else "under-confident" if actual > claimed + half
                   else "calibrated")
        rows.append({"bin": [lo, hi], "n": int(sel.sum()),
                     "claimed": round(claimed, 4), "actual": round(actual, 4),
                     "half_width": round(half, 4), "verdict": verdict})
        print(f"    [{lo:.2f},{hi:.2f})  n={sel.sum():>6,}  claims "
              f"{100*claimed:.1f}%  delivers {100*actual:.1f}% +/- {100*half:.1f}"
              f"   {verdict}")
    return rows


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="docs/b21_referee_results.json")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    conn = db.connect()
    frame = load(conn)
    priced = frame[["avg_h", "avg_d", "avg_a"]].notna().all(axis=1).to_numpy()
    joint = joint_of(frame)
    model_probs = probs_1x2(joint)
    model_d15 = b21.dog15_probs(joint, model_probs)
    print(f"{len(frame):,} matches, {int(priced.sum()):,} priced")

    # --- fit ---------------------------------------------------------------
    odds = frame.loc[priced, ["avg_h", "avg_d", "avg_a"]].to_numpy(float)
    q = np.column_stack(devig_probs(odds[:, 0], odds[:, 1], odds[:, 2]))
    lam_h, lam_a, residual = fit_market_lambdas(q[:, 0], q[:, 2])
    converged = residual < 1e-4
    fit = {"n_priced": int(priced.sum()),
           "share_converged_1e4": round(float(converged.mean()), 5),
           "max_residual": float(residual.max()),
           "median_lam_total": round(float(np.median(lam_h + lam_a)), 4)}
    print(f"\nfit  {100*fit['share_converged_1e4']:.2f}% of matches under 1e-4 "
          f"(max residual {fit['max_residual']:.2e}); "
          f"median market lam_h+lam_a {fit['median_lam_total']:.2f}")

    ref_probs, ref_d15 = referee_probs(lam_h, lam_a)

    # --- compare (prices + lambda only) ------------------------------------
    sub = frame[priced].reset_index(drop=True)
    m_probs, m_d15 = model_probs[priced], model_d15[priced]
    arm_market, _ = b21.recommend(m_probs, m_d15)
    ref_market, _ = b21.recommend(ref_probs, ref_d15)
    is_d = arm_market == b21.DOG15

    blocks = bootstrap.week_blocks(sub.match_date[is_d])
    cmp = bootstrap.paired(m_d15[is_d], ref_d15[is_d], blocks)
    by_season = {str(s): round(float((m_d15[is_d & (sub.season == s).to_numpy()]
                                      - ref_d15[is_d & (sub.season == s).to_numpy()]
                                      ).mean()), 5)
                 for s in sorted(sub.season.unique())}
    by_division = {d: round(float((m_d15[is_d & (sub.division == d).to_numpy()]
                                   - ref_d15[is_d & (sub.division == d).to_numpy()]
                                   ).mean()), 5)
                   for d in sorted(sub.division.unique())}
    compare = {
        "n_d15_published": int(is_d.sum()),
        "model_claim": round(float(m_d15[is_d].mean()), 5),
        "referee_claim": round(float(ref_d15[is_d].mean()), 5),
        "gap": round(float(cmp.delta), 5),
        "gap_ci": [round(cmp.ci[0], 5), round(cmp.ci[1], 5)],
        "gap_excludes_zero": bool(cmp.excludes_zero),
        "share_model_above": round(float((m_d15[is_d] > ref_d15[is_d]).mean()), 4),
        "gap_by_season": by_season,
        "gap_by_division": by_division,
        "referee_rule_d15_share": round(float((ref_market == b21.DOG15).mean()), 4),
        "pick_agreement": round(float((arm_market == ref_market).mean()), 4),
    }
    print(f"\ncompare  on {compare['n_d15_published']:,} D+1.5 calls: model claims "
          f"{100*compare['model_claim']:.2f}%, referee {100*compare['referee_claim']:.2f}%, "
          f"gap {100*compare['gap']:+.2f} [{100*compare['gap_ci'][0]:+.2f},"
          f"{100*compare['gap_ci'][1]:+.2f}]{'*' if compare['gap_excludes_zero'] else ''}")
    print(f"    by season  " + "  ".join(f"{s} {100*v:+.1f}" for s, v in by_season.items()))
    print(f"    by division " + "  ".join(f"{d} {100*v:+.1f}" for d, v in by_division.items()))
    print(f"    referee rule publishes D+1.5 in {100*compare['referee_rule_d15_share']:.1f}%; "
          f"pick agreement {100*compare['pick_agreement']:.1f}%")

    # --- calibrate (outcomes on a market-defined quantity) ------------------
    fav_home_ref = ref_probs[:, 0] >= ref_probs[:, 2]
    fav_margin = np.where(fav_home_ref,
                          sub.fthg.to_numpy(float) - sub.ftag.to_numpy(float),
                          sub.ftag.to_numpy(float) - sub.fthg.to_numpy(float))
    won = fav_margin < 1.5
    rows = calibration_table(ref_d15, won, "referee D+1.5, pooled (market-defined)")
    per_division = {d: calibration_table(ref_d15[(sub.division == d).to_numpy()],
                                         won[(sub.division == d).to_numpy()],
                                         f"referee D+1.5, {d}")
                    for d in sorted(sub.division.unique())}
    pooled_gap = float(won.mean() - ref_d15.mean())
    print(f"    pooled delivered - claimed {100*pooled_gap:+.2f}")

    rng = np.random.default_rng(CONTROL_SEED)
    j_h = lam_h * np.exp(rng.normal(0, CONTROL_JITTER_SD, len(lam_h)))
    j_a = lam_a * np.exp(rng.normal(0, CONTROL_JITTER_SD, len(lam_a)))
    _, jit_d15 = referee_probs(j_h, j_a)
    control_rows = calibration_table(jit_d15, won, "planted control (jittered lambdas)")
    top = [r for r in control_rows if r["bin"][0] >= 0.90] or control_rows[-1:]
    control_fires = bool(top and top[0]["verdict"] == "overconfident")
    print(f"    control top bucket overconfident: {control_fires}")

    calibrate = {"pooled": rows, "per_division": per_division,
                 "pooled_delivered_minus_claimed": round(pooled_gap, 5),
                 "control": control_rows, "control_fires": control_fires}

    # --- verdicts, against the pre-registration -----------------------------
    max_season_dev = max(abs(v - cmp.delta) for v in by_season.values())
    verdict = {
        "R1_fit_converges": fit["share_converged_1e4"] > 0.99,
        "R2_gap_minus1_to_plus05": -0.010 <= cmp.delta <= 0.005,
        "R3_referee_underclaims_0_to_1": 0.0 <= pooled_gap <= 0.010,
        "R4_share_55_75_agreement_70_85": (
            0.55 <= compare["referee_rule_d15_share"] <= 0.75
            and 0.70 <= compare["pick_agreement"] <= 0.85),
        "R5_every_season_within_1pt_of_pooled": max_season_dev <= 0.010,
        "control_fires": control_fires,
    }
    print("\npredictions: " + ", ".join(f"{k} {'OK' if v else 'NO'}"
                                        for k, v in verdict.items()))

    results = {"fit": fit, "compare": compare, "calibrate": calibrate,
               "verdict": verdict}

    if args.dry_run:
        print("  [dry-run] ledger row NOT written (0 configurations)")
    else:
        ledger.record(
            conn, kind=ledger.PROBE, name="b21_market_referee", purpose="dev",
            seasons=DEV_SEASONS, divisions=SERVED_DIVISIONS, detail=results,
            reason="BACKLOG.md B21 referee probe. Market-implied D+1.5 from "
                   "devigged avg 1X2 prices through the model's own pmf: fit, "
                   "model-vs-referee gap, and the referee's own calibration on a "
                   "market-defined quantity with a planted jitter control. No "
                   "model arm's outcomes are read; zero configurations.")
        print("  [ledger] probe:b21_market_referee  (0 configurations)")

    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(results, handle, indent=2, default=str)
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
