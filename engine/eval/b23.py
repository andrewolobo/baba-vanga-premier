"""B23 probe: can the head predict Both Teams To Score, and how well?

    python -m engine.eval.b23 --scan      # lambda only: no outcome read, no row
    python -m engine.eval.b23 --dry-run   # everything printed, no ledger row
    python -m engine.eval.b23             # probe row, 0 configurations

Pre-registration is `docs/BACKLOG.md` B23, written after the scan and before
the probe ran. The line is a marginal of the same score matrix every other
market comes from:

    P(BTTS yes) = 1 - P(home 0) - P(away 0) + P(0-0)

which on the served independent-Poisson pmf is (1 - e^-lam_h)(1 - e^-lam_a).
The line has no corpus price (football-data carries none, B5), so the
referee is B21's: market lambdas fitted to the devigged avg 1X2 prices and
pushed through the same pmf, so the pmf-shape bias cancels and the gap
isolates the lambdas.

Four parts, one probe row, **0 configurations**:

  scan        lambda only. Where the claim sits, which side is likelier, and
              whether the line could ever displace the v3 rule's pick.
  calibrate   claimed versus delivered on each side's calls, bucketed, pooled
              and per division, with a week-block paired gap. Carries the B11
              planted control: lambda jittered by exp(N(0, 0.25)) must read
              overconfident on both sides or the table is not a result.
  skill       log loss and Brier of the model's P(yes), paired by ISO week
              against (a) a walk-forward per-division base rate that knows no
              lambda and (b) the market-implied referee. Reads outcomes to
              score one quantity of the shipped head -- no grid, no choice.
  tipster     what "the likelier BTTS side" would publish: strike, claim and
              coverage at a few confidence thresholds. Descriptive; nothing is
              chosen from it.

No arm list is recorded and no menu decision is read off this row (the B11
footing). A BTTS candidate on a rule would be its own pre-registered gate.
"""

from __future__ import annotations

import argparse
import json

import numpy as np
import pandas as pd

from engine import db, ledger, store
from engine.eval import b21, bootstrap, selection
from engine.eval.b21_referee import fit_market_lambdas
from engine.eval.dispersion import score_matrix
from engine.eval.p7 import joint_of, load, probs_1x2
from engine.odds import devig_probs
from engine.seasons import DEV_SEASONS, SERVED_DIVISIONS

FLOOR = selection.SHIPPED_FLOOR
CEILING = selection.CEILING

SIDES = ("yes", "no")
BUCKETS = ((0.50, 0.60), (0.60, 0.70), (0.70, 0.80), (0.80, 0.90), (0.90, 1.01))
MIN_BUCKET = 200
THRESHOLDS = (0.50, 0.55, 0.60, 0.65)

#: The B11 positive control: multiplicative noise on lambda, log-sd 0.25 -- a
#: head more spread out than the truth, hence over-confident at both ends.
CONTROL_JITTER_SD = 0.25
CONTROL_SEED = 7

EPS = 1e-9


# --- the line ----------------------------------------------------------------


def btts_probs(joint: np.ndarray) -> np.ndarray:
    """P(both teams score) from the score matrix, whatever its rho."""
    return (1.0 - joint[:, 0, :].sum(axis=1) - joint[:, :, 0].sum(axis=1)
            + joint[:, 0, 0])


def btts_won(fthg, ftag) -> np.ndarray:
    return (np.asarray(fthg, dtype=float) > 0) & (np.asarray(ftag, dtype=float) > 0)


def side_claims(p_yes: np.ndarray, side: str) -> tuple[np.ndarray, np.ndarray]:
    """(claimed probability, is this side the call) for one side of the line."""
    if side == "yes":
        return p_yes, p_yes >= 0.5
    return 1.0 - p_yes, p_yes < 0.5


# --- scan: lambda only ---------------------------------------------------------


def scan(frame: pd.DataFrame, joint: np.ndarray, probs: np.ndarray) -> dict:
    """Where the line's claim sits, and whether it could ever be published.

    Reads no outcome column -- `tests/test_b23.py` strips them and this must
    still run, or the probe's accounting would be a lie.
    """
    p_yes = btts_probs(joint)
    likelier = np.maximum(p_yes, 1.0 - p_yes)
    p_h, p_d, p_a = probs[:, 0], probs[:, 1], probs[:, 2]
    p_dog15 = b21.dog15_probs(joint, probs)
    _, v3_claim = b21.recommend(probs, p_dog15)

    # Would the likelier BTTS side ever win the v3 fallback argmax if it were
    # added to the candidate set? Only matches reaching the fallback count.
    reaches_fallback = np.maximum(p_h, p_a) < FLOOR
    stack = np.column_stack([p_h + p_d, p_a + p_d, p_h + p_a, p_dog15])
    fallback_best = np.where(stack <= CEILING, stack, -1.0).max(axis=1)
    wins_fallback = reaches_fallback & (likelier <= CEILING) & (likelier > fallback_best)

    divisions = frame.division.to_numpy()
    q10, q50, q90 = np.quantile(p_yes, [0.10, 0.50, 0.90])
    out = {
        "n": int(len(frame)),
        "p_yes": {"mean": round(float(p_yes.mean()), 4), "p10": round(float(q10), 4),
                  "p50": round(float(q50), 4), "p90": round(float(q90), 4)},
        "yes_likelier_share": round(float((p_yes >= 0.5).mean()), 4),
        "likelier_claim_mean": round(float(likelier.mean()), 4),
        "claim_at_or_above": {str(t): round(float((likelier >= t).mean()), 4)
                              for t in THRESHOLDS},
        "by_division": {
            d: {"n": int((divisions == d).sum()),
                "p_yes_mean": round(float(p_yes[divisions == d].mean()), 4),
                "yes_likelier_share": round(float((p_yes[divisions == d] >= 0.5).mean()), 4)}
            for d in SERVED_DIVISIONS},
        "v3_claim_mean": round(float(v3_claim.mean()), 4),
        "beats_v3_claim_share": round(float((likelier > v3_claim).mean()), 4),
        "wins_v3_fallback_share": round(float(wins_fallback.mean()), 4),
    }
    print(f"\nscan  BTTS on the served pmf ({len(frame):,} matches, lambda only)")
    print(f"    P(yes) mean {out['p_yes']['mean']:.3f}  p10 {q10:.3f}  p50 {q50:.3f}  "
          f"p90 {q90:.3f};  yes is the likelier side in "
          f"{100*out['yes_likelier_share']:.1f}%")
    print(f"    likelier side claims {100*out['likelier_claim_mean']:.1f}% on average; "
          + "  ".join(f">= {t}: {100*v:.1f}%" for t, v in out["claim_at_or_above"].items()))
    print("    per division P(yes): " + "  ".join(
        f"{d} {100*v['p_yes_mean']:.1f}% (yes likelier {100*v['yes_likelier_share']:.0f}%)"
        for d, v in out["by_division"].items()))
    print(f"    v3 rule claims {100*out['v3_claim_mean']:.1f}% on average; BTTS beats "
          f"the v3 pick's claim in {100*out['beats_v3_claim_share']:.2f}% of matches and "
          f"would win the v3 fallback argmax in {100*out['wins_v3_fallback_share']:.2f}%")
    return out


# --- calibration ---------------------------------------------------------------


def side_table(p_yes: np.ndarray, won_yes: np.ndarray, side: str,
               mask: np.ndarray | None = None) -> list[dict]:
    """Claimed versus delivered on one side's calls, by claimed bucket."""
    claim, call = side_claims(p_yes, side)
    won = won_yes if side == "yes" else ~won_yes
    sel_all = call if mask is None else call & mask
    rows = []
    for lo, hi in BUCKETS:
        sel = sel_all & (claim >= lo) & (claim < hi)
        n = int(sel.sum())
        if n == 0:
            rows.append({"bin": [lo, hi], "n": 0})
            continue
        actual = float(won[sel].mean())
        claimed = float(claim[sel].mean())
        half = 1.96 * float(np.sqrt(max(actual * (1 - actual), 1e-12) / n))
        verdict = (None if n < MIN_BUCKET
                   else "overconfident" if actual < claimed - half
                   else "under-confident" if actual > claimed + half
                   else "calibrated")
        rows.append({"bin": [lo, hi], "n": n, "claimed": round(claimed, 4),
                     "actual": round(actual, 4), "half_width": round(half, 4),
                     "gap": round(actual - claimed, 4), "verdict": verdict})
    return rows


def top_bucket(rows: list[dict]) -> dict | None:
    """The highest-claim bucket with enough matches to verdict."""
    for row in reversed(rows):
        if row["n"] >= MIN_BUCKET:
            return row
    return None


def paired_gap(claim: np.ndarray, won: np.ndarray, dates) -> dict:
    """Delivered minus claimed with a week-block interval (the OUTSTANDING 9.5 form)."""
    cmp = bootstrap.paired(np.asarray(won, dtype=float), np.asarray(claim, dtype=float),
                           bootstrap.week_blocks(dates))
    return {"n": int(cmp.n), "claimed": round(float(np.mean(claim)), 5),
            "delivered": round(float(np.mean(won)), 5), "gap": round(float(cmp.delta), 5),
            "ci": [round(cmp.ci[0], 5), round(cmp.ci[1], 5)],
            "excludes_zero": bool(cmp.excludes_zero)}


def _print_table(label: str, rows: list[dict]) -> None:
    print(f"    {label}")
    for r in rows:
        if r["n"] == 0:
            continue
        v = r["verdict"] or "(n<200)"
        print(f"      [{r['bin'][0]:.2f},{r['bin'][1]:.2f})  n={r['n']:>6,}  "
              f"claims {100*r['claimed']:>5.1f}%  delivers {100*r['actual']:>5.1f}% "
              f"+/- {100*r['half_width']:.1f}  {v}")


def calibration(frame: pd.DataFrame, p_yes: np.ndarray, label: str) -> dict:
    """Each side's calls: pooled paired gap, bucket table, and both per division."""
    won_yes = btts_won(frame.fthg, frame.ftag)
    divisions = frame.division.to_numpy()
    print(f"\ncalibration  {label} ({len(frame):,} matches)")
    out = {}
    for side in SIDES:
        claim, call = side_claims(p_yes, side)
        won = won_yes if side == "yes" else ~won_yes
        idx = np.flatnonzero(call)
        pooled = paired_gap(claim[idx], won[idx], frame.match_date.iloc[idx])
        by_division = {}
        for d in SERVED_DIVISIONS:
            sel = np.flatnonzero(call & (divisions == d))
            by_division[d] = {
                "gap": paired_gap(claim[sel], won[sel], frame.match_date.iloc[sel]),
                "table": side_table(p_yes, won_yes, side, mask=(divisions == d))}
        out[side] = {"share": round(float(call.mean()), 4), "pooled": pooled,
                     "table": side_table(p_yes, won_yes, side),
                     "by_division": by_division}
        star = " *" if pooled["excludes_zero"] else ""
        print(f"  {side.upper():<4} calls in {100*out[side]['share']:.1f}%  claims "
              f"{100*pooled['claimed']:.2f}%  delivers {100*pooled['delivered']:.2f}%  "
              f"gap {100*pooled['gap']:+.2f} [{100*pooled['ci'][0]:+.2f},"
              f"{100*pooled['ci'][1]:+.2f}]{star}")
        _print_table("pooled", out[side]["table"])
        for d, r in by_division.items():
            g = r["gap"]
            star = " *" if g["excludes_zero"] else ""
            print(f"      {d}: n={g['n']:>5,} gap {100*g['gap']:+.2f} "
                  f"[{100*g['ci'][0]:+.2f},{100*g['ci'][1]:+.2f}]{star}")
    return out


def control(frame: pd.DataFrame) -> dict:
    """A deliberately over-confident head. The table must catch it on both
    sides, or the calibration has no instrument and is not reported."""
    rng = np.random.default_rng(CONTROL_SEED)
    lam_h = frame.lam_h.to_numpy(float) * np.exp(rng.normal(0, CONTROL_JITTER_SD, len(frame)))
    lam_a = frame.lam_a.to_numpy(float) * np.exp(rng.normal(0, CONTROL_JITTER_SD, len(frame)))
    p_yes = btts_probs(score_matrix(lam_h, lam_a))
    won_yes = btts_won(frame.fthg, frame.ftag)
    print(f"\ncontrol  lambda jittered by exp(N(0, {CONTROL_JITTER_SD})) -- "
          "both sides must read overconfident")
    sides = {}
    for side in SIDES:
        top = top_bucket(side_table(p_yes, won_yes, side))
        hit = top is not None and top["verdict"] == "overconfident"
        sides[side] = {"top_bucket": top, "flagged": hit}
        print(f"    {side}: top bucket "
              + (f"[{top['bin'][0]:.2f},{top['bin'][1]:.2f}) n={top['n']:,} "
                 f"gap {100*top['gap']:+.1f} -> {top['verdict']}" if top else "n<200"))
    passes = all(s["flagged"] for s in sides.values())
    print(f"    control {'PASSES' if passes else 'FAILS'}")
    return {"jitter_sd": CONTROL_JITTER_SD, "seed": CONTROL_SEED,
            "passes": passes, "sides": sides}


# --- skill ----------------------------------------------------------------------


def walk_forward_base_rate(history: pd.DataFrame, frame: pd.DataFrame) -> np.ndarray:
    """Per-division BTTS-yes rate over strictly earlier seasons. Knows no lambda.

    `history` is the whole development corpus (burn-in seasons included), so
    the first scored season has four seasons of prior behind it.
    """
    hist = history.dropna(subset=["fthg", "ftag"])
    hist = hist[hist.division.isin(SERVED_DIVISIONS)]
    yes = btts_won(hist.fthg, hist.ftag)
    h_season, h_div = hist.season.to_numpy(), hist.division.to_numpy()
    out = np.full(len(frame), np.nan)
    for (season, division), rows in frame.groupby(["season", "division"]).indices.items():
        prior = (h_season < season) & (h_div == division)
        if not prior.any():
            raise ValueError(f"no prior seasons for {division} {season}")
        out[rows] = yes[prior].mean()
    return out


def _logloss(p: np.ndarray, y: np.ndarray) -> np.ndarray:
    p = np.clip(p, EPS, 1 - EPS)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def _brier(p: np.ndarray, y: np.ndarray) -> np.ndarray:
    return (p - y) ** 2


def _versus(model: np.ndarray, reference: np.ndarray, blocks) -> dict:
    """model minus reference, paired; negative means the model is better."""
    cmp = bootstrap.paired(model, reference, blocks)
    return {"delta": round(float(cmp.delta), 6),
            "ci": [round(cmp.ci[0], 6), round(cmp.ci[1], 6)],
            "excludes_zero": bool(cmp.excludes_zero)}


def skill(frame: pd.DataFrame, p_yes: np.ndarray, base: np.ndarray,
          ref_p_yes: np.ndarray, priced: np.ndarray) -> dict:
    """Does the head's P(yes) beat a lambda-free base rate, and the market?"""
    y = btts_won(frame.fthg, frame.ftag).astype(float)
    blocks = bootstrap.week_blocks(frame.match_date)
    idx = np.flatnonzero(priced)
    p_blocks = bootstrap.week_blocks(frame.match_date.iloc[idx])
    out = {
        "n": int(len(frame)), "n_priced": int(len(idx)),
        "model": {"logloss": round(float(_logloss(p_yes, y).mean()), 5),
                  "brier": round(float(_brier(p_yes, y).mean()), 5)},
        "base_rate": {
            "logloss": round(float(_logloss(base, y).mean()), 5),
            "brier": round(float(_brier(base, y).mean()), 5),
            "model_minus_base_logloss": _versus(_logloss(p_yes, y), _logloss(base, y), blocks),
            "model_minus_base_brier": _versus(_brier(p_yes, y), _brier(base, y), blocks)},
        "referee": {
            "logloss": round(float(_logloss(ref_p_yes[idx], y[idx]).mean()), 5),
            "brier": round(float(_brier(ref_p_yes[idx], y[idx]).mean()), 5),
            "model_logloss_priced": round(float(_logloss(p_yes[idx], y[idx]).mean()), 5),
            "model_minus_referee_logloss": _versus(_logloss(p_yes[idx], y[idx]),
                                                   _logloss(ref_p_yes[idx], y[idx]), p_blocks),
            "model_minus_referee_brier": _versus(_brier(p_yes[idx], y[idx]),
                                                 _brier(ref_p_yes[idx], y[idx]), p_blocks),
            "claim_gap": _versus(p_yes[idx], ref_p_yes[idx], p_blocks)},
    }
    m, b, r = out["model"], out["base_rate"], out["referee"]
    vb, vr, cg = (b["model_minus_base_logloss"], r["model_minus_referee_logloss"],
                  r["claim_gap"])
    print(f"\nskill  P(yes) scored on {len(frame):,} matches ({len(idx):,} priced)")
    print(f"    model      logloss {m['logloss']:.5f}  brier {m['brier']:.5f}")
    print(f"    base rate  logloss {b['logloss']:.5f}  brier {b['brier']:.5f}   "
          f"model - base {vb['delta']:+.5f} [{vb['ci'][0]:+.5f},{vb['ci'][1]:+.5f}]"
          f"{' *' if vb['excludes_zero'] else ''} nats")
    print(f"    referee    logloss {r['logloss']:.5f}  brier {r['brier']:.5f}   "
          f"model - referee {vr['delta']:+.5f} [{vr['ci'][0]:+.5f},{vr['ci'][1]:+.5f}]"
          f"{' *' if vr['excludes_zero'] else ''} nats; claim gap "
          f"{100*cg['delta']:+.2f} [{100*cg['ci'][0]:+.2f},{100*cg['ci'][1]:+.2f}] pts")
    return out


# --- tipster --------------------------------------------------------------------


def tipster(frame: pd.DataFrame, p_yes: np.ndarray) -> dict:
    """The likelier side as a call: what it would publish at each threshold."""
    won_yes = btts_won(frame.fthg, frame.ftag)
    claim = np.maximum(p_yes, 1.0 - p_yes)
    won = np.where(p_yes >= 0.5, won_yes, ~won_yes)
    blocks = bootstrap.week_blocks(frame.match_date)
    rows = []
    print(f"\ntipster  the likelier BTTS side as a call ({len(frame):,} matches)")
    print(f"    {'claim >=':>9} {'coverage':>9} {'strike':>8} {'[95% block CI]':>18} "
          f"{'claimed':>8} {'yes share':>10}")
    for t in THRESHOLDS:
        sel = np.flatnonzero(claim >= t)
        if len(sel) == 0:
            rows.append({"threshold": t, "coverage": 0.0})
            continue
        cmp = bootstrap.paired(-won[sel].astype(float), np.zeros(len(sel)), blocks[sel])
        rows.append({"threshold": t, "coverage": round(float(len(sel) / len(frame)), 4),
                     "strike": round(-float(cmp.delta), 4),
                     "ci_low": round(-cmp.ci[1], 4), "ci_high": round(-cmp.ci[0], 4),
                     "claimed": round(float(claim[sel].mean()), 4),
                     "yes_share": round(float((p_yes[sel] >= 0.5).mean()), 4)})
        r = rows[-1]
        print(f"    {t:>9.2f} {100*r['coverage']:>8.1f}% {100*r['strike']:>7.1f}% "
              f"[{100*r['ci_low']:>6.1f},{100*r['ci_high']:>6.1f}] {100*r['claimed']:>7.1f}% "
              f"{100*r['yes_share']:>9.1f}%")
    return {"rows": rows}


# --- verdict against the pre-registration --------------------------------------


def verdict(results: dict) -> dict:
    """The B23 predictions, evaluated mechanically. Bands are in BACKLOG.md."""
    cal = results.get("calibration", {})
    skl = results["skill"]
    ref = results.get("referee_calibration", {})
    yes_gap = cal.get("yes", {}).get("pooled", {})
    no_gap = cal.get("no", {}).get("pooled", {})
    vs_base = skl["base_rate"]["model_minus_base_logloss"]
    vs_ref = skl["referee"]["model_minus_referee_logloss"]
    claim_gap = skl["referee"]["claim_gap"]
    first = results["tipster"]["rows"][0]

    lower_no_tops = ({d: (top_bucket(cal["no"]["by_division"][d]["table"]) or {}).get("verdict")
                      for d in ("E1", "E2", "E3")} if cal else {})
    out = {
        "C0_control_fires": bool(results["control"]["passes"]),
        "C1_yes_underclaims_0_5_to_3_0_resolved": bool(
            yes_gap and 0.005 <= yes_gap["gap"] <= 0.030 and yes_gap["ci"][0] > 0),
        "C2_no_gap_in_minus_2_5_to_plus_0_5": bool(
            no_gap and -0.025 <= no_gap["gap"] <= 0.005),
        "C3_model_beats_base_rate_by_3_to_15_millinats_resolved": bool(
            -0.015 <= vs_base["delta"] <= -0.003 and vs_base["ci"][1] < 0),
        "C4_model_vs_referee_within_2_millinats_unresolved": bool(
            abs(vs_ref["delta"]) < 0.002 and not vs_ref["excludes_zero"]),
        "C5_claim_gap_vs_referee_within_1_pt": bool(abs(claim_gap["delta"]) <= 0.01),
        "C6_referee_yes_underclaims_same_direction": bool(
            ref and ref["yes"]["pooled"]["gap"] > 0),
        "C7_likelier_side_strike_54_to_58": bool(0.54 <= first.get("strike", -1) <= 0.58),
        "no_side_top_bucket_lower_divisions": lower_no_tops,
    }
    print("\n    predictions: " + ", ".join(
        f"{k} {'OK' if v else 'NO'}" for k, v in out.items() if isinstance(v, bool)))
    return out


# --- main ----------------------------------------------------------------------


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="docs/b23_results.json")
    parser.add_argument("--scan", action="store_true",
                        help="lambda only: the scan, no outcome read, no ledger row")
    parser.add_argument("--dry-run", action="store_true",
                        help="print and write JSON, but record no ledger row")
    args = parser.parse_args(argv)

    conn = db.connect()
    frame = load(conn)
    joint = joint_of(frame)
    probs = probs_1x2(joint)
    p_yes = btts_probs(joint)
    print(f"{len(frame):,} matches, {frame.season.min()} -> {frame.season.max()}, "
          f"{frame.division.nunique()} divisions")

    results = {"scan": scan(frame, joint, probs)}
    if args.scan:
        with open(args.out, "w", encoding="utf-8") as handle:
            json.dump(results, handle, indent=2, default=str)
        print(f"  [scan] no outcome read, no ledger row; wrote {args.out}")
        return 0

    results["control"] = control(frame)
    if results["control"]["passes"]:
        results["calibration"] = calibration(frame, p_yes, "model")
    else:
        print("  calibration NOT REPORTED: the control failed, so there is no instrument")

    history = store.read_matches(conn, seasons=DEV_SEASONS).for_measurement()
    base = walk_forward_base_rate(history, frame)
    priced = frame[["avg_h", "avg_d", "avg_a"]].notna().all(axis=1).to_numpy()
    odds = frame.loc[priced, ["avg_h", "avg_d", "avg_a"]].to_numpy(float)
    q = np.column_stack(devig_probs(odds[:, 0], odds[:, 1], odds[:, 2]))
    lam_h, lam_a, residual = fit_market_lambdas(q[:, 0], q[:, 2])
    ref_p_yes = np.full(len(frame), np.nan)
    ref_p_yes[priced] = btts_probs(score_matrix(lam_h, lam_a))
    results["referee_fit"] = {"n_priced": int(priced.sum()),
                              "converged_share": round(float((residual < 1e-4).mean()), 5)}

    results["skill"] = skill(frame, p_yes, base, ref_p_yes, priced)
    if results["control"]["passes"]:
        results["referee_calibration"] = calibration(
            frame[priced].reset_index(drop=True), ref_p_yes[priced], "market-implied referee")
    results["tipster"] = tipster(frame, p_yes)
    results["verdict"] = verdict(results)

    if args.dry_run:
        print("  [dry-run] ledger row NOT written (0 configurations)")
    else:
        ledger.record(
            conn, kind=ledger.PROBE, name="b23_btts", purpose="dev",
            seasons=DEV_SEASONS, divisions=SERVED_DIVISIONS,
            detail=dict(results),
            reason="BACKLOG.md B23 probe. Both Teams To Score as a marginal of the "
                   "served pmf: claimed-versus-delivered on each side's calls with "
                   "the jittered-lambda control, log loss and Brier paired against a "
                   "walk-forward base rate and the B21 market-implied referee, and "
                   "what the likelier side would publish. Reads outcomes to score one "
                   "quantity of the shipped head and for tables, not a choice; no arm "
                   "list, zero configurations. No menu decision is read off this row.")
        print("  [ledger] probe:b23_btts  (0 configurations)")

    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(results, handle, indent=2, default=str)
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
