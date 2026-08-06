"""P3-lite: calibration, the market ablation, and the launch decision.

    python -m engine.eval.p3

Runs the hypotheses pre-registered in `docs/P3_PLAN.md` and writes every result
to the gate ledger. The question is not whether the head is good -- P1 settled
that at 0.0117-0.0155 nats behind the market -- but whether its *disagreements*
with the market carry information. If they do, a selective rule can beat the
close despite losing to it globally; if not, no rule built on this head can.

Everything is walk-forward by season: fit on strictly earlier seasons, apply to
the held-out one. Calibration fitted in sample reports whatever improvement it
was asked for.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import replace

import numpy as np
import pandas as pd

from engine import db, ledger, store
from engine.eval import bootstrap, metrics
from engine.eval.p1 import BASE, served
from engine.eval.walkforward import walk_forward
from engine.models import calibration as cal
from engine.odds import breakeven_prob, devig_probs
from engine.seasons import DEV_SEASONS, SERVED_DIVISIONS

#: The head as it stood when P3 ran, pinned deliberately. Serving adopted the
#: shots channel on 2026-08-04 (`SHOTS_TARGET.md`) and this does not follow it:
#: `CALIBRATION.md`'s numbers were measured on the head below, so importing the
#: live config would silently invalidate them. A P3 re-run against the new head
#: is a new measurement and needs its own ledger row.
SERVING_CONFIG = replace(BASE, half_life=400.0, alpha=0.1, embargo_regimes=())

#: Seasons of history before a calibration is fitted at all.
BURN_IN_SEASONS = 3

#: Populations for calibration. E0 separate on the three-line OPEN-6 evidence.
POPULATIONS = ("E0", "E1", "E2", "E3")

EDGE_THRESHOLDS = (0.0, 0.02, 0.04, 0.06, 0.10)
OUTCOME_INDEX = {"H": 0, "D": 1, "A": 2}


# --- the scored corpus, once ----------------------------------------------


def build_frame(conn) -> pd.DataFrame:
    """Walk-forward lambdas plus model and market probabilities, dev set only."""
    frame = store.read_matches(conn, seasons=DEV_SEASONS).for_measurement()
    scored = served(walk_forward(frame, SERVING_CONFIG))
    scored = scored.dropna(subset=["avg_h", "avg_d", "avg_a", "avg_over25", "avg_under25"])

    model = metrics.model_probs(scored["lam_h"], scored["lam_a"])
    scored = scored.reset_index(drop=True)
    scored[["m_h", "m_d", "m_a"]] = model[["p_h", "p_d", "p_a"]].to_numpy()
    scored["m_over"] = model["p_over"].to_numpy()

    kh, kd, ka = devig_probs(scored.avg_h.to_numpy(), scored.avg_d.to_numpy(),
                             scored.avg_a.to_numpy())
    scored[["k_h", "k_d", "k_a"]] = np.column_stack([kh, kd, ka])
    ko, _ = devig_probs(scored.avg_over25.to_numpy(), scored.avg_under25.to_numpy())
    scored["k_over"] = ko

    scored["y_over"] = metrics.over_outcome(scored)
    return scored


def _seasons(frame) -> list[str]:
    return sorted(frame["season"].unique())


# --- H11: walk-forward calibration ----------------------------------------


def walk_forward_calibrate(frame: pd.DataFrame) -> pd.DataFrame:
    """Attach calibrated probabilities, fitted only on earlier seasons."""
    out = frame.copy()
    for column in ("c_h", "c_d", "c_a", "c_over"):
        out[column] = np.nan

    seasons = _seasons(frame)
    for division in POPULATIONS:
        rows = out["division"] == division
        for i, season in enumerate(seasons):
            if i < BURN_IN_SEASONS:
                continue
            train = rows & out["season"].isin(seasons[:i])
            test = rows & (out["season"] == season)
            if not test.any() or train.sum() < cal.MIN_FIT_ROWS:
                continue

            x2 = cal.fit_vector_scaling(
                out.loc[train, ["m_h", "m_d", "m_a"]].to_numpy(), out.loc[train, "ftr"])
            out.loc[test, ["c_h", "c_d", "c_a"]] = x2.apply(
                out.loc[test, ["m_h", "m_d", "m_a"]].to_numpy())

            ou = cal.fit_platt(out.loc[train, "m_over"], out.loc[train, "y_over"])
            out.loc[test, "c_over"] = ou.apply(out.loc[test, "m_over"].to_numpy())
    return out


def walk_forward_blend(frame: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    """Attach blended probabilities and report the model weight per fit."""
    out = frame.copy()
    for column in ("b_h", "b_d", "b_a", "b_over"):
        out[column] = np.nan
    weights = []

    seasons = _seasons(frame)
    for division in POPULATIONS:
        rows = out["division"] == division
        for i, season in enumerate(seasons):
            if i < BURN_IN_SEASONS:
                continue
            train = rows & out["season"].isin(seasons[:i])
            test = rows & (out["season"] == season)
            if not test.any() or train.sum() < cal.MIN_FIT_ROWS:
                continue

            x2 = cal.fit_blend_1x2(
                out.loc[train, ["m_h", "m_d", "m_a"]].to_numpy(),
                out.loc[train, ["k_h", "k_d", "k_a"]].to_numpy(),
                out.loc[train, "ftr"])
            out.loc[test, ["b_h", "b_d", "b_a"]] = x2.apply(
                out.loc[test, ["m_h", "m_d", "m_a"]].to_numpy(),
                out.loc[test, ["k_h", "k_d", "k_a"]].to_numpy())

            ou = cal.fit_blend_binary(out.loc[train, "m_over"], out.loc[train, "k_over"],
                                      out.loc[train, "y_over"])
            out.loc[test, "b_over"] = ou.apply(out.loc[test, "m_over"].to_numpy(),
                                               out.loc[test, "k_over"].to_numpy())
            weights.append({
                "division": division, "season": season, "n_train": int(train.sum()),
                "model_weight_1x2": x2.model_weight, "market_weight_1x2": x2.market_weight,
                "model_weight_ou": ou.model_weight, "market_weight_ou": ou.market_weight,
            })
    return out, weights


# --- scoring helpers -------------------------------------------------------


def _ll_1x2(frame, prefix) -> np.ndarray:
    index = frame["ftr"].map(OUTCOME_INDEX).to_numpy()[:, None]
    probs = frame[[f"{prefix}_h", f"{prefix}_d", f"{prefix}_a"]].to_numpy()
    return -np.log(np.clip(np.take_along_axis(probs, index, 1)[:, 0], 1e-12, 1))


def _ll_ou(frame, column) -> np.ndarray:
    return metrics.logloss_binary(frame[column].to_numpy(), frame["y_over"].to_numpy())


def h11_calibration(conn, calibrated: pd.DataFrame) -> dict:
    print("\nH11  per-population calibration (walk-forward)")
    graded = calibrated.dropna(subset=["c_h", "c_over"])
    rows = []
    for division in POPULATIONS:
        g = graded[graded.division == division]
        blocks = bootstrap.week_blocks(g["match_date"])
        raw_1x2, cal_1x2 = _ll_1x2(g, "m"), _ll_1x2(g, "c")
        raw_ou, cal_ou = _ll_ou(g, "m_over"), _ll_ou(g, "c_over")
        d1 = bootstrap.paired(cal_1x2, raw_1x2, blocks)
        d2 = bootstrap.paired(cal_ou, raw_ou, blocks)
        rows.append({"division": division, "n": len(g),
                     "d_ll_1x2": d1.delta, "ci_1x2": d1.ci,
                     "d_ll_ou": d2.delta, "ci_ou": d2.ci,
                     "market_ll_1x2": float(_ll_1x2(g, "k").mean()),
                     "cal_ll_1x2": float(cal_1x2.mean())})
        print(f"  {division}  n={len(g):5d}  1X2 {d1.delta:+.5f} "
              f"[{d1.ci[0]:+.5f}, {d1.ci[1]:+.5f}]   O/U {d2.delta:+.5f} "
              f"[{d2.ci[0]:+.5f}, {d2.ci[1]:+.5f}]")
    detail = {"rows": [{k: (list(v) if isinstance(v, tuple) else v)
                        for k, v in r.items()} for r in rows]}
    ledger.record(conn, kind=ledger.GATE, name="h11_platt_calibration", purpose="dev",
                  seasons=DEV_SEASONS, divisions=SERVED_DIVISIONS, detail=detail,
                  reason="Walk-forward per-population calibration. Predicted 1X2 gains "
                         "0.001-0.004 in E1-E3, <=0.001 in E0; does not close the "
                         "market gap.")
    return detail


def h12_ablation(conn, weights: list[dict], blended: pd.DataFrame) -> dict:
    print("\nH12  market ablation -- what does the model add given the price?")
    frame = pd.DataFrame(weights)
    rows = []
    for division in POPULATIONS:
        g = frame[frame.division == division]
        rows.append({
            "division": division, "fits": len(g),
            "model_weight_1x2": float(g.model_weight_1x2.mean()),
            "model_weight_1x2_sd": float(g.model_weight_1x2.std()),
            "market_weight_1x2": float(g.market_weight_1x2.mean()),
            "model_weight_ou": float(g.model_weight_ou.mean()),
            "model_weight_ou_sd": float(g.model_weight_ou.std()),
            "market_weight_ou": float(g.market_weight_ou.mean()),
        })
        print(f"  {division}  1X2 model {g.model_weight_1x2.mean():+.4f} "
              f"(sd {g.model_weight_1x2.std():.4f}) market {g.market_weight_1x2.mean():.3f}"
              f"   |  O/U model {g.model_weight_ou.mean():+.4f} "
              f"(sd {g.model_weight_ou.std():.4f}) market {g.market_weight_ou.mean():.3f}")

    # Does the blend actually beat the market out of sample?
    graded = blended.dropna(subset=["b_h", "b_over"])
    beats = []
    for division in POPULATIONS:
        g = graded[graded.division == division]
        blocks = bootstrap.week_blocks(g["match_date"])
        d1 = bootstrap.paired(_ll_1x2(g, "b"), _ll_1x2(g, "k"), blocks)
        d2 = bootstrap.paired(_ll_ou(g, "b_over"), _ll_ou(g, "k_over"), blocks)
        beats.append({"division": division, "n": len(g),
                      "blend_vs_market_1x2": d1.as_dict(),
                      "blend_vs_market_ou": d2.as_dict()})
        print(f"  {division}  blend vs market  1X2 {d1.delta:+.5f} "
              f"[{d1.ci[0]:+.5f}, {d1.ci[1]:+.5f}] {d1.verdict:<18}"
              f" O/U {d2.delta:+.5f} [{d2.ci[0]:+.5f}, {d2.ci[1]:+.5f}] {d2.verdict}")

    detail = {"weights": rows, "blend_vs_market": beats}
    ledger.record(conn, kind=ledger.GATE, name="h12_market_ablation", purpose="dev",
                  seasons=DEV_SEASONS, divisions=SERVED_DIVISIONS, detail=detail,
                  reason="Does the model add anything once the market price is in the "
                         "equation? Predicted model weight in [0.00, 0.15], excluding "
                         "zero on O/U and spanning zero on 1X2.")
    return detail


# --- H13: the rule, re-backtested -----------------------------------------


def _legs(frame, prefix, over_column):
    """(side, model probability, price, de-vigged bet prob, won) per leg."""
    out = []
    for side, column, price_column, market_column in (
        ("H", f"{prefix}_h", "avg_h", "k_h"),
        ("D", f"{prefix}_d", "avg_d", "k_d"),
        ("A", f"{prefix}_a", "avg_a", "k_a"),
    ):
        out.append(pd.DataFrame({
            "market": "1x2", "side": side, "division": frame["division"].to_numpy(),
            "match_date": frame["match_date"].to_numpy(),
            "prob": frame[column].to_numpy(), "price": frame[price_column].to_numpy(),
            "bet_prob": frame[market_column].to_numpy(),
            "won": (frame["ftr"].to_numpy() == side),
            "close_prob": frame[f"close_{side}"].to_numpy(),
        }))
    out.append(pd.DataFrame({
        "market": "ou25", "side": "over", "division": frame["division"].to_numpy(),
        "match_date": frame["match_date"].to_numpy(),
        "prob": frame[over_column].to_numpy(), "price": frame["avg_over25"].to_numpy(),
        "bet_prob": frame["k_over"].to_numpy(),
        "won": frame["y_over"].to_numpy().astype(bool),
        "close_prob": frame["close_over"].to_numpy(),
    }))
    return pd.concat(out, ignore_index=True)


def attach_closes(frame: pd.DataFrame) -> pd.DataFrame:
    """De-vigged Pinnacle close for 1X2, market-average close for O/U."""
    out = frame.copy()
    for column in ("close_H", "close_D", "close_A", "close_over"):
        out[column] = np.nan

    ok = out[["close_ps_h", "close_ps_d", "close_ps_a"]].notna().all(axis=1)
    if ok.any():
        h, d, a = devig_probs(out.loc[ok, "close_ps_h"].to_numpy(),
                              out.loc[ok, "close_ps_d"].to_numpy(),
                              out.loc[ok, "close_ps_a"].to_numpy())
        out.loc[ok, ["close_H", "close_D", "close_A"]] = np.column_stack([h, d, a])

    ok_ou = out[["close_avg_over25", "close_avg_under25"]].notna().all(axis=1)
    if ok_ou.any():
        over, _ = devig_probs(out.loc[ok_ou, "close_avg_over25"].to_numpy(),
                              out.loc[ok_ou, "close_avg_under25"].to_numpy())
        out.loc[ok_ou, "close_over"] = over
    return out


def h13_backtest(conn, frame: pd.DataFrame) -> dict:
    print("\nH13  the bet rule, re-backtested  (CLV vs the de-vigged close)")
    bases = {
        "uncalibrated": ("m", "m_over"),
        "calibrated": ("c", "c_over"),
        "blended": ("b", "b_over"),
    }
    results = {}
    for name, (prefix, over_column) in bases.items():
        usable = frame.dropna(subset=[f"{prefix}_h", over_column])
        legs = _legs(usable, prefix, over_column).dropna(subset=["close_prob"])
        legs["edge"] = legs["prob"] - breakeven_prob(legs["price"].to_numpy())
        legs["clv"] = legs["close_prob"] - legs["bet_prob"]
        legs["pnl"] = np.where(legs["won"], legs["price"] - 1.0, -1.0)

        table = []
        print(f"  --- {name} ---")
        for threshold in EDGE_THRESHOLDS:
            sel = legs[legs.edge > threshold]
            if len(sel) < 100:
                continue
            blocks = bootstrap.week_blocks(pd.Series(sel["match_date"].to_numpy()))
            clv = bootstrap.paired(sel["clv"].to_numpy(), np.zeros(len(sel)), blocks)
            table.append({"min_edge": threshold, "bets": len(sel),
                          "mean_clv": clv.delta, "clv_ci": list(clv.ci),
                          "beat_close": float((sel.clv > 0).mean()),
                          "roi": float(sel.pnl.mean())})
            print(f"    edge>{threshold:.2f}  n={len(sel):6,}  CLV {clv.delta:+.5f} "
                  f"[{clv.ci[0]:+.5f}, {clv.ci[1]:+.5f}]  beat {100*(sel.clv>0).mean():.1f}%"
                  f"  ROI {100*sel.pnl.mean():+.2f}%")
        results[name] = table
    return results


def h13_strata(conn, frame: pd.DataFrame, basis: str, over_column: str,
               threshold: float) -> dict:
    """CLV per division x market at the chosen basis -- the launch decision."""
    print(f"\nLaunch decision  ({basis} basis, min_edge {threshold})")
    usable = frame.dropna(subset=[f"{basis}_h", over_column])
    legs = _legs(usable, basis, over_column).dropna(subset=["close_prob"])
    legs["edge"] = legs["prob"] - breakeven_prob(legs["price"].to_numpy())
    legs["clv"] = legs["close_prob"] - legs["bet_prob"]
    legs["pnl"] = np.where(legs["won"], legs["price"] - 1.0, -1.0)
    sel = legs[legs.edge > threshold]

    decisions = []
    for (division, market), g in sel.groupby(["division", "market"]):
        if len(g) < 100:
            continue
        blocks = bootstrap.week_blocks(pd.Series(g["match_date"].to_numpy()))
        clv = bootstrap.paired(g["clv"].to_numpy(), np.zeros(len(g)), blocks)
        on = clv.delta >= 0 and clv.ci[0] > 0
        decisions.append({"division": division, "market": market, "bets": len(g),
                          "mean_clv": clv.delta, "clv_ci": list(clv.ci),
                          "roi": float(g.pnl.mean()), "book_on": bool(on)})
        print(f"  {division} {market:<5} n={len(g):5,}  CLV {clv.delta:+.5f} "
              f"[{clv.ci[0]:+.5f}, {clv.ci[1]:+.5f}]  ROI {100*g.pnl.mean():+.2f}%  "
              f"-> {'BOOK ON' if on else 'off'}")
    return {"basis": basis, "min_edge": threshold, "strata": decisions}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="docs/p3_results.json")
    args = parser.parse_args(argv)

    conn = db.connect()
    frame = build_frame(conn)
    print(f"scored corpus: {len(frame):,} fixtures, "
          f"{frame.season.min()}-{frame.season.max()}")

    frame = attach_closes(frame)
    calibrated = walk_forward_calibrate(frame)
    blended, weights = walk_forward_blend(calibrated)

    results = {"h11": h11_calibration(conn, calibrated),
               "h12": h12_ablation(conn, weights, blended),
               "h13": h13_backtest(conn, blended)}
    results["decision"] = h13_strata(conn, blended, "b", "b_over", 0.02)

    ledger.record(conn, kind=ledger.GATE, name="p3_launch_decision", purpose="dev",
                  seasons=DEV_SEASONS, divisions=SERVED_DIVISIONS,
                  detail=results["decision"],
                  reason="Book ON per stratum iff walk-forward CLV >= 0 with a CI "
                         "excluding zero. Bar pre-registered in docs/P3_PLAN.md.")

    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(results, handle, indent=2, default=str)
    print(f"\nwritten to {args.out}")
    print(f"recorded trials: {ledger.trial_count(conn)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
