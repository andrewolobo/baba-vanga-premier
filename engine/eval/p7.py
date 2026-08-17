"""P7: the tipster's own numbers -- v2 return, goal-line calibration, menu shapes.

    python -m engine.eval.p7 --dry-run            # everything, no ledger rows
    python -m engine.eval.p7 --part A             # one part, ledger row written
    python -m engine.eval.p7                      # A, B, C in order

Pre-registration is `docs/P7_TIPSTER_PLAN.md`, written before any of this ran.
Results go to `docs/TIPSTER.md`. Three parts, three kinds of row:

  A  the shipped v2 rule's return at derived customer prices, and the paired
     difference against the same rule applied to the market's probabilities.
     Reads outcomes; **4 configurations** (the B3 floor grid).
  B  B11 -- claimed-versus-delivered at the six goal lines, per division, with a
     jittered-lambda positive control run first. Reads outcomes for a table,
     not a choice; **0 configurations** unless the pre-committed drop rule
     removes a line from the B4 menu (1 per line dropped).
  C  B4 -- the mixes three candidate menu shapes produce on a ceiling grid.
     Reads lambda only, **0 configurations**. Ends in an owner decision.

Everything is on the raw pmf (B13 declined) and on the same walk-forward frame
and population as `engine/eval/selection.py`, so the numbers sit beside B3's.
"""

from __future__ import annotations

import argparse
import json

import numpy as np
import pandas as pd

from engine import db, ledger, store
from engine.eval import bootstrap, selection
from engine.eval.dispersion import outcome_probs, over_under_probs, score_matrix
from engine.eval.p1 import served
from engine.eval.travel import HEAD
from engine.eval.walkforward import walk_forward
from engine.odds import devig_probs
from engine.seasons import DEV_SEASONS, SERVED_DIVISIONS
from engine.serve.tips import COMPONENTS, derived_price

#: The B3 grid, unchanged, so Part A's return sits beside B3's strike rate.
FLOORS = selection.FLOORS
CEILING = selection.CEILING
SHIPPED_FLOOR = selection.SHIPPED_FLOOR

#: Part B and C: the owner's menu of goal lines (`PRODUCT.md` §2).
LINES = (0.5, 1.5, 2.5, 3.5, 4.5, 5.5)
BUCKETS = ((0.50, 0.60), (0.60, 0.70), (0.70, 0.80), (0.80, 0.90), (0.90, 1.01))
MIN_BUCKET = 200

#: Part B's positive control: multiplicative noise on lambda, log-sd 0.25 --
#: a head that is deliberately more spread out than the truth, hence
#: over-confident at the tails. Seeded, so the control is reproducible.
CONTROL_JITTER_SD = 0.25
CONTROL_SEED = 7

#: The pre-committed drop rule (plan Part B): a line leaves the B4 menu iff its
#: top two pooled buckets both deliver below claimed by more than this, with
#: at least MIN_BUCKET matches each.
DROP_MARGIN = 0.02

#: Part C's ceiling grid, at the shipped floor.
CEILINGS = (0.75, 0.80, 0.85, 0.90)

PRICE_BEST = ["max_h", "max_d", "max_a"]
PRICE_AVG = ["avg_h", "avg_d", "avg_a"]


# --- harness ---------------------------------------------------------------


def load(conn) -> pd.DataFrame:
    """The population B3 measured on: dev seasons, served divisions, walk-forward
    lambdas, and the same three-season burn-in `selection.py` uses so the
    match count (15,824) is the one already published."""
    raw = store.read_matches(conn, seasons=DEV_SEASONS).for_measurement()
    frame = served(walk_forward(raw, HEAD)).reset_index(drop=True)
    frame = frame.dropna(subset=["ftr"]).reset_index(drop=True)
    seasons = sorted(frame.season.unique())
    scored = frame.season.isin(seasons[selection.BURN_IN_SEASONS:])
    return frame[scored].reset_index(drop=True)


def joint_of(frame: pd.DataFrame) -> np.ndarray:
    return score_matrix(frame.lam_h.to_numpy(float), frame.lam_a.to_numpy(float))


def probs_1x2(joint: np.ndarray) -> np.ndarray:
    return np.column_stack(outcome_probs(joint))


def _roi(pnl: np.ndarray, dates) -> dict:
    """Mean flat-stake return with a block-bootstrap CI (loss convention inside)."""
    cmp = bootstrap.paired(-pnl, np.zeros(len(pnl)), bootstrap.week_blocks(dates))
    return {"roi": round(-cmp.delta, 5), "ci_low": round(-cmp.ci[1], 5),
            "ci_high": round(-cmp.ci[0], 5), "n": int(len(pnl)),
            "resolved_positive": bool(cmp.ci[1] < 0),
            "resolved_negative": bool(cmp.ci[0] > 0)}


def _price_of(market: np.ndarray, prices: np.ndarray) -> np.ndarray:
    """The (derived, for a union) price of each recommended market."""
    out = np.full(len(market), np.nan)
    for side in np.unique(market):
        rows = np.flatnonzero(market == side)
        out[rows] = derived_price(prices[rows], COMPONENTS[str(side)])
    return out


def _pnl(won: np.ndarray, price: np.ndarray) -> np.ndarray:
    return np.where(won, price - 1.0, -1.0)


# --- Part A ----------------------------------------------------------------


def part_a(frame: pd.DataFrame, probs: np.ndarray) -> dict:
    """The v2 rule's return, and whether the model adds anything to it."""
    ftr = frame.ftr.to_numpy()
    best = frame[PRICE_BEST].to_numpy(float)
    avg = frame[PRICE_AVG].to_numpy(float)
    priced = np.isfinite(best).all(axis=1) & np.isfinite(avg).all(axis=1)
    market_era = (frame.season >= "201920").to_numpy()
    # The market rule: the same recommendation applied to the market's own
    # de-vigged probabilities. If the model adds nothing, the two agree.
    market_probs = np.column_stack(devig_probs(*[avg[:, i] for i in range(3)]))
    market_probs = np.where(np.isfinite(market_probs), market_probs, 0.0)

    print(f"\nPart A  the v2 rule's return  ({len(frame):,} matches, "
          f"{int(priced.sum()):,} priced; market era {int((priced & market_era).sum()):,} "
          f"of {int(market_era.sum()):,})")
    print(f"    {'floor':>6} {'strike':>7} {'ROI@avg':>22} {'ROI@best':>22} "
          f"{'vs market rule':>22}")
    rows = []
    for floor in FLOORS:
        market, prob = selection.recommend(probs, floor, CEILING, allow_12=selection.ALLOW_12)
        won = selection._won(market, ftr)
        idx = np.flatnonzero(priced)
        dates = frame.match_date.iloc[idx]
        pnl_avg = _pnl(won[idx], _price_of(market[idx], avg[idx]))
        pnl_best = _pnl(won[idx], _price_of(market[idx], best[idx]))
        mkt_market, _ = selection.recommend(market_probs, floor, CEILING,
                                            allow_12=selection.ALLOW_12)
        mkt_won = selection._won(mkt_market, ftr)
        mkt_pnl_best = _pnl(mkt_won[idx], _price_of(mkt_market[idx], best[idx]))
        versus = bootstrap.paired(-pnl_best, -mkt_pnl_best, bootstrap.week_blocks(dates))
        strike = float(won.mean())
        row = {
            "floor": floor, "strike": round(strike, 4),
            "priced_share": round(float(priced.mean()), 4),
            "priced_share_market_era": (round(float(priced[market_era].mean()), 4)
                                        if market_era.any() else None),
            "roi_avg": _roi(pnl_avg, dates), "roi_best": _roi(pnl_best, dates),
            "vs_market_rule": {"delta": round(-versus.delta, 5),
                               "ci_low": round(-versus.ci[1], 5),
                               "ci_high": round(-versus.ci[0], 5),
                               "resolved": bool(versus.ci[0] > 0 or versus.ci[1] < 0),
                               "agree_share": round(float((market == mkt_market).mean()), 4)},
            "mean_prob": round(float(prob.mean()), 4),
        }
        rows.append(row)
        a, b, v = row["roi_avg"], row["roi_best"], row["vs_market_rule"]
        mark = " <- SHIPPED" if floor == SHIPPED_FLOOR else ""
        print(f"    {floor:>6.2f} {100*strike:>6.1f}% "
              f"{100*a['roi']:>+7.2f}% [{100*a['ci_low']:>+6.2f},{100*a['ci_high']:>+6.2f}] "
              f"{100*b['roi']:>+7.2f}% [{100*b['ci_low']:>+6.2f},{100*b['ci_high']:>+6.2f}] "
              f"{100*v['delta']:>+7.2f}% [{100*v['ci_low']:>+6.2f},{100*v['ci_high']:>+6.2f}]"
              f"{mark}")

    shipped = next(r for r in rows if r["floor"] == SHIPPED_FLOOR)
    verdict = {
        "A1_roi_avg_in_band": bool(-0.04 <= shipped["roi_avg"]["roi"] <= -0.01),
        "A1_not_resolved_positive": not shipped["roi_avg"]["resolved_positive"],
        "A2_roi_best_in_band": bool(-0.025 <= shipped["roi_best"]["roi"] <= 0.01),
        "A2_unresolved": not (shipped["roi_best"]["resolved_positive"]
                              or shipped["roi_best"]["resolved_negative"]),
        "A3_all_floors_small_and_unresolved": all(
            abs(r["vs_market_rule"]["delta"]) < 0.005 and not r["vs_market_rule"]["resolved"]
            for r in rows),
        "A4_roi_avg_not_improving_with_floor": all(
            rows[i + 1]["roi_avg"]["roi"] <= rows[i]["roi_avg"]["roi"] + 1e-9
            for i in range(len(rows) - 1)),
        "A5_market_era_coverage_ge_95": bool((shipped["priced_share_market_era"] or 0) >= 0.95),
    }
    print("    predictions: " + ", ".join(f"{k} {'OK' if v else 'NO'}"
                                          for k, v in verdict.items()))
    return {"rows": rows, "verdict": verdict}


# --- Part B ----------------------------------------------------------------


def line_table(frame: pd.DataFrame, joint: np.ndarray, line: float,
               mask: np.ndarray | None = None) -> list[dict]:
    """Claimed versus delivered on the likelier side of one goal line."""
    over, under = over_under_probs(joint, line)
    pick_over = over >= under
    p = np.where(pick_over, over, under)
    total = (frame.fthg + frame.ftag).to_numpy(float)
    won = np.where(pick_over, total > line, total < line)
    sel_all = np.ones(len(frame), bool) if mask is None else mask
    rows = []
    for lo, hi in BUCKETS:
        sel = sel_all & (p >= lo) & (p < hi)
        n = int(sel.sum())
        if n == 0:
            rows.append({"bin": [lo, hi], "n": 0})
            continue
        actual = float(won[sel].mean())
        claimed = float(p[sel].mean())
        half = 1.96 * float(np.sqrt(max(actual * (1 - actual), 1e-12) / n))
        verdict = (None if n < MIN_BUCKET
                   else "overconfident" if actual < claimed - half
                   else "under-confident" if actual > claimed + half
                   else "calibrated")
        rows.append({"bin": [lo, hi], "n": n, "claimed": round(claimed, 4),
                     "actual": round(actual, 4), "half_width": round(half, 4),
                     "gap": round(actual - claimed, 4), "verdict": verdict})
    return rows


def _top_bucket(rows: list[dict]) -> dict | None:
    """The highest-probability bucket with enough matches to verdict."""
    for row in reversed(rows):
        if row["n"] >= MIN_BUCKET:
            return row
    return None


def _print_table(label: str, rows: list[dict]) -> None:
    print(f"    {label}")
    for r in rows:
        if r["n"] == 0:
            continue
        v = r["verdict"] or "(n<200)"
        print(f"      [{r['bin'][0]:.2f},{r['bin'][1]:.2f})  n={r['n']:>6,}  "
              f"claims {100*r['claimed']:>5.1f}%  delivers {100*r['actual']:>5.1f}% "
              f"+/- {100*r['half_width']:.1f}  {v}")


def part_b_control(frame: pd.DataFrame) -> dict:
    """A deliberately over-confident head. The table must catch it, or Part B
    has no instrument and reports nothing."""
    rng = np.random.default_rng(CONTROL_SEED)
    lam_h = frame.lam_h.to_numpy(float) * np.exp(rng.normal(0, CONTROL_JITTER_SD, len(frame)))
    lam_a = frame.lam_a.to_numpy(float) * np.exp(rng.normal(0, CONTROL_JITTER_SD, len(frame)))
    joint = score_matrix(lam_h, lam_a)
    print(f"\nPart B control  lambda jittered by exp(N(0, {CONTROL_JITTER_SD})) -- "
          "the table must say overconfident")
    flagged, tables = 0, {}
    for line in LINES:
        rows = line_table(frame, joint, line)
        top = _top_bucket(rows)
        hit = top is not None and top["verdict"] == "overconfident"
        flagged += int(hit)
        tables[str(line)] = {"top_bucket": top, "flagged": hit}
        print(f"    line {line}: top bucket "
              + (f"[{top['bin'][0]:.2f},{top['bin'][1]:.2f}) n={top['n']:,} "
                 f"gap {100*top['gap']:+.1f} -> {top['verdict']}" if top else "n<200"))
    passed = flagged >= 4
    print(f"    flagged {flagged}/6 lines -> control {'PASSES' if passed else 'FAILS'}")
    return {"jitter_sd": CONTROL_JITTER_SD, "seed": CONTROL_SEED,
            "flagged": flagged, "passes": passed, "lines": tables}


def part_b(frame: pd.DataFrame, joint: np.ndarray) -> dict:
    """B11: per-line calibration, pooled and per division, and the drop rule."""
    print("\nPart B  claimed versus delivered at each goal line")
    out = {"pooled": {}, "by_division": {}, "dropped": [], "verdict": {}}
    divisions = frame.division.to_numpy()
    for line in LINES:
        rows = line_table(frame, joint, line)
        out["pooled"][str(line)] = rows
        _print_table(f"line {line}, pooled", rows)
        out["by_division"][str(line)] = {
            d: line_table(frame, joint, line, mask=(divisions == d))
            for d in SERVED_DIVISIONS}
        # The drop rule, mechanical: top two verdictable buckets both over-claim
        # by more than DROP_MARGIN.
        able = [r for r in rows if r["n"] >= MIN_BUCKET]
        top_two = able[-2:] if len(able) >= 2 else []
        if len(top_two) == 2 and all(r["gap"] < -DROP_MARGIN for r in top_two):
            out["dropped"].append(line)
    if out["dropped"]:
        print(f"    DROP RULE FIRED: {out['dropped']} leave the B4 menu")
    else:
        print("    drop rule: no line removed")

    def top(line):
        return _top_bucket(out["pooled"][str(line)])

    b1 = all(r["verdict"] == "calibrated" for r in out["pooled"]["2.5"]
             if r["n"] >= MIN_BUCKET)
    b2 = all(top(l) is not None and top(l)["gap"] >= -0.01 for l in LINES)
    b3 = all(top(l) is not None and 0.005 <= top(l)["gap"] <= 0.03
             and top(l)["verdict"] == "under-confident" for l in (4.5, 5.5))
    disagreements = {}
    for d in SERVED_DIVISIONS:
        count = 0
        for l in LINES:
            pooled, div = top(l), _top_bucket(out["by_division"][str(l)][d])
            if pooled and div and div["verdict"] and div["verdict"] != pooled["verdict"]:
                count += 1
        disagreements[d] = count
    b4 = all(v <= 1 for v in disagreements.values())
    out["verdict"] = {"B1_line_25_calibrated": b1,
                      "B2_no_line_overclaims_top_bucket": b2,
                      "B3_tails_underclaim_by_half_to_three_points": b3,
                      "B4_divisions_agree_with_pooled": b4,
                      "division_disagreements": disagreements}
    print("    predictions: " + ", ".join(
        f"{k} {'OK' if v else 'NO'}" for k, v in out["verdict"].items()
        if isinstance(v, bool)))
    return out


# --- Part C ----------------------------------------------------------------


def _best_line(joint: np.ndarray, ceiling: float):
    """Per match: the likeliest (line, side) with p <= ceiling, or none.
    Returns (label array, probability array); label '' where nothing qualifies."""
    labels, stack = [], []
    for line in LINES:
        over, under = over_under_probs(joint, line)
        labels += [f"O{line}", f"U{line}"]
        stack += [over, under]
    stack = np.column_stack(stack)
    eligible = np.where(stack <= ceiling, stack, -1.0)
    best = eligible.argmax(axis=1)
    p = eligible[np.arange(len(stack)), best]
    label = np.where(p >= 0, np.array(labels)[best], "")
    return label, np.where(p >= 0, p, np.nan)


def _mix(values: np.ndarray) -> dict:
    total = max(len(values), 1)
    counts = pd.Series(values).value_counts()
    return {str(k): round(float(v) / total, 4) for k, v in counts.items()}


def part_c(frame: pd.DataFrame, joint: np.ndarray, probs: np.ndarray) -> dict:
    """B4: what each candidate shape would publish. Lambda only, no outcomes."""
    print("\nPart C  the goal-line menu -- what each shape publishes (no outcomes read)")
    p_h, p_d, p_a = probs[:, 0], probs[:, 1], probs[:, 2]
    home = p_h >= p_a
    outright_p = np.where(home, p_h, p_a)
    fallback_pop = outright_p < SHIPPED_FLOOR
    out = {"floor": SHIPPED_FLOOR, "fallback_population_share":
           round(float(fallback_pop.mean()), 4), "ceilings": {}}
    for ceiling in CEILINGS:
        v2_market, v2_p = selection.recommend(probs, SHIPPED_FLOOR, ceiling,
                                              allow_12=selection.ALLOW_12)
        line_label, line_p = _best_line(joint, ceiling)
        # C1: the veto case -- outright published below the floor because every
        # double chance breached the ceiling. The third tier offers a line there.
        vetoed = fallback_pop & np.isin(v2_market, ["H", "A"])
        c1_fires = vetoed & (line_label != "")
        c1_market = np.where(c1_fires, line_label, v2_market)
        c1_p = np.where(c1_fires, line_p, v2_p)
        # C2: a separate goals call on every match.
        c2_has = line_label != ""
        # C3: on the fallback population, the likelier of best DC and best line.
        dc_p = np.where(np.isin(v2_market, ["1X", "X2", "12"]), v2_p, -1.0)
        c3_line_wins = fallback_pop & (line_p > dc_p) & (line_label != "")
        c3_market = np.where(c3_line_wins, line_label, v2_market)
        c3_p = np.where(c3_line_wins, line_p, v2_p)
        line_labels = [f"{s}{l}" for l in LINES for s in "OU"]
        named = lambda m: float(np.isin(m, ["H", "A"]).mean())  # noqa: E731
        is_line = lambda m: float(np.isin(m, line_labels).mean())  # noqa: E731

        row = {
            "C1": {"fire_rate": round(float(c1_fires.mean()), 4),
                   "mix_when_fired": _mix(line_label[c1_fires]),
                   "mean_prob": round(float(np.nanmean(c1_p)), 4),
                   "team_named_share": round(named(c1_market), 4)},
            "C2": {"coverage": round(float(c2_has.mean()), 4),
                   "mix": _mix(line_label[c2_has]),
                   "mean_prob": round(float(np.nanmean(line_p[c2_has])), 4)},
            "C3": {"line_displaces_dc_in_fallback": round(
                        float(c3_line_wins[fallback_pop].mean()), 4),
                   "team_named_share": round(named(c3_market), 4),
                   "goal_line_share": round(is_line(c3_market), 4),
                   "mix": _mix(c3_market),
                   "mean_prob": round(float(np.nanmean(c3_p)), 4)},
            "v2_mean_prob": round(float(v2_p.mean()), 4),
        }
        out["ceilings"][str(ceiling)] = row
        c2_top = sorted(row["C2"]["mix"].items(), key=lambda kv: -kv[1])[:3]
        print(f"    ceiling {ceiling:.2f}: C1 fires {100*row['C1']['fire_rate']:.2f}% | "
              f"C2 top {', '.join(f'{k} {100*v:.0f}%' for k, v in c2_top)} "
              f"(mean p {row['C2']['mean_prob']:.3f}) | "
              f"C3 line displaces DC {100*row['C3']['line_displaces_dc_in_fallback']:.0f}%, "
              f"team named {100*row['C3']['team_named_share']:.1f}%, "
              f"line {100*row['C3']['goal_line_share']:.1f}%")

    at85 = out["ceilings"]["0.85"]
    at75 = out["ceilings"]["0.75"]
    top75 = max(at75["C2"]["mix"].values()) if at75["C2"]["mix"] else 0.0
    modal75 = max(at75["C2"]["mix"], key=at75["C2"]["mix"].get) if at75["C2"]["mix"] else ""
    out["verdict"] = {
        "C1a_third_tier_fires_under_3pct_everywhere": all(
            r["C1"]["fire_rate"] < 0.03 for r in out["ceilings"].values()),
        "C2a_under35_40_to_55_and_over15_15_to_30_at_085": bool(
            0.40 <= at85["C2"]["mix"].get("U3.5", 0) <= 0.55
            and 0.15 <= at85["C2"]["mix"].get("O1.5", 0) <= 0.30),
        "C2b_at_075_modal_is_25_line_and_no_line_over_35pct": bool(
            modal75 in ("U2.5", "O2.5") and top75 <= 0.35),
        "C3a_line_displaces_dc_over_70pct_named_under_15_line_over_55_at_085": bool(
            at85["C3"]["line_displaces_dc_in_fallback"] > 0.70
            and at85["C3"]["team_named_share"] < 0.15
            and at85["C3"]["goal_line_share"] > 0.55),
    }
    print("    predictions: " + ", ".join(f"{k} {'OK' if v else 'NO'}"
                                          for k, v in out["verdict"].items()))
    return out


# --- entry -----------------------------------------------------------------


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--part", choices=("A", "B", "C", "all"), default="all")
    parser.add_argument("--out", default="docs/p7_results.json")
    parser.add_argument("--dry-run", action="store_true",
                        help="print and write JSON, but record no ledger row")
    args = parser.parse_args(argv)

    conn = db.connect()
    frame = load(conn)
    joint = joint_of(frame)
    probs = probs_1x2(joint)
    print(f"{len(frame):,} matches, {frame.season.min()} -> {frame.season.max()}, "
          f"{frame.division.nunique()} divisions")
    parts = ("A", "B", "C") if args.part == "all" else (args.part,)
    results: dict = {}

    def row(kind, name, detail, reason, cost):
        if args.dry_run:
            print(f"  [dry-run] {kind}:{name} NOT written ({cost} configurations)")
            return
        ledger.record(conn, kind=kind, name=name, purpose="dev", seasons=DEV_SEASONS,
                      divisions=SERVED_DIVISIONS, detail=detail, reason=reason)
        print(f"  [ledger] {kind}:{name}  ({cost} configurations)")

    if "A" in parts:
        results["A"] = part_a(frame, probs)
        row(ledger.GATE, "p7_v2_return",
            {"arms": [{"arm": f"floor {r['floor']}", "roi_avg": r["roi_avg"]["roi"],
                       "roi_best": r["roi_best"]["roi"],
                       "vs_market": r["vs_market_rule"]["delta"]}
                      for r in results["A"]["rows"]], **results["A"]},
            "P7_TIPSTER_PLAN.md Part A. The shipped confidence-v2 rule's flat-stake "
            "return at derived avg/best prices on the B3 floor grid, and the paired "
            "difference against the same rule on the market's de-vigged "
            "probabilities. Reads outcomes; four configurations, declared before "
            "the run. Closes B7's gap: the site's no-return claim was measured on v1.",
            4)
    if "B" in parts:
        control = part_b_control(frame)
        results["B_control"] = control
        row(ledger.PROBE, "p7_line_calibration_control", control,
            "P7_TIPSTER_PLAN.md Part B control. Lambda jittered exp(N(0,0.25)); the "
            "per-line calibration table must flag overconfidence at >=4 of 6 lines "
            "or Part B reports nothing. Reads outcomes for a control, not a "
            "decision; no arm list, zero configurations.", 0)
        if control["passes"]:
            results["B"] = part_b(frame, joint)
            dropped = results["B"]["dropped"]
            row(ledger.GATE if dropped else ledger.PROBE, "p7_line_calibration",
                ({"arms": [{"arm": f"drop line {l}"} for l in dropped]} if dropped else {})
                | results["B"],
                "P7_TIPSTER_PLAN.md Part B (B11). Claimed-versus-delivered at goal lines "
                "0.5-5.5, pooled and per division, on the walk-forward pmf. The "
                "pre-committed drop rule " + ("FIRED" if dropped else "did not fire")
                + f"; {len(dropped)} configuration(s).", len(dropped))
        else:
            print("  Part B NOT RUN: the control failed, so there is no instrument")
    if "C" in parts:
        results["C"] = part_c(frame, joint, probs)
        row(ledger.PROBE, "p7_menu_shapes", results["C"],
            "P7_TIPSTER_PLAN.md Part C (B4). Mixes published by three candidate "
            "goal-line menu shapes on a ceiling grid at the shipped floor. Reads "
            "lambda only -- no outcome enters; zero configurations. Ends in an "
            "owner decision on shape before any strike rate is measured (C').", 0)

    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(results, handle, indent=2, default=str)
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
