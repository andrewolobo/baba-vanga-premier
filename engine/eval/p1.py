"""P1: freeze the base head, publish the base score.

Runs the hypotheses of `docs/P1_PLAN.md` in their pre-registered order and
writes every result -- including the nulls and including any prediction that
turned out wrong -- to the gate ledger.

    python -m engine.eval.p1 --stage all

Nothing here reads a sealed season: every corpus comes through
`store.read_matches` at `Purpose.DEV`, which raises rather than filters.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import replace

import numpy as np
import pandas as pd

from engine import db, ledger, store
from engine.eval import bootstrap, metrics, sweep
from engine.eval.walkforward import WalkForwardConfig, season_day, walk_forward
from engine.seasons import DEV_SEASONS, SERVED_DIVISIONS, ALL_DIVISIONS

#: Scored matches never include the National League (NEW-1) or the
#: empty-stadium window (H6). Both are training-set decisions, not scoring ones.
COVID = ("covid_empty_stadiums",)

#: The starting point for every arm. Hyperparameters are P0's frozen defaults
#: until H2/H3 replace them.
BASE = WalkForwardConfig(cadence="weekly", fit_divisions=ALL_DIVISIONS,
                         embargo_regimes=COVID)

#: Widened after the first P1 run put the optimum on the upper boundary of
#: SPEC 3.2's [100, 300] window. A boundary winner is a grid that stopped too
#: early, not a chosen value, so the grid follows the data rather than the
#: other way round.
HALF_LIFE_GRID = [100, 160, 200, 240, 300, 400, 500, 650, 800]

#: Likewise widened downward: the first run was monotone toward the smallest
#: penalty on the grid.
ALPHA_GRID = [0.02, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0]

#: Likewise: 0.85 beat 0.95 and was the strongest shrink offered.
SHRINK_GRID = [0.60, 0.70, 0.80, 0.85, 0.95]

#: Days into a division-season that count as "early". §2.5 of the plan.
EARLY_SEASON_DAYS = 45


def load(conn) -> pd.DataFrame:
    return store.read_matches(conn, seasons=DEV_SEASONS).for_measurement()


def served(frame: pd.DataFrame) -> pd.DataFrame:
    """Restrict scoring to the four divisions the engine sells markets on."""
    return frame[frame["division"].isin(SERVED_DIVISIONS)].reset_index(drop=True)


def _print_sweep(result, label: str) -> None:
    for arm in result.arms:
        mark = " <-- chosen" if arm.value == result.chosen.value else ""
        best = " (best)" if arm.value == result.best.value else ""
        print(f"  {label}={arm.value:<6} deviance {arm.deviance:.5f}  "
              f"paired se {arm.paired_stderr:.5f}  marginal se {arm.marginal_stderr:.5f}  "
              f"1X2 {arm.ll_1x2:.5f}{best}{mark}")
    print(f"  best {result.best.value}, 1-SE(paired) choice {result.chosen.value}, "
          f"spread {result.spread:.5f}, censored: {result.censored}")


def _log(conn, kind, name, detail, reason):
    ledger.record(conn, kind=kind, name=name, purpose="dev", seasons=DEV_SEASONS,
                  divisions=SERVED_DIVISIONS, detail=detail, reason=reason)
    print(f"  [ledger] {kind}:{name}")


# --- H1: cadence -----------------------------------------------------------


def h1_cadence(conn, frame) -> dict:
    print("\nH1  evaluation cadence")
    arms = {c: replace(BASE, cadence=c) for c in ("daily", "weekly", "fortnightly")}
    result = sweep.compare(frame, arms, reference="weekly", score_on=served)
    for name, entry in result["arms"].items():
        delta = entry.get("vs_reference", {}).get("delta")
        extra = "" if delta is None else f"  vs weekly {delta:+.5f}"
        print(f"  {name:12s} deviance {entry['deviance']:.5f}{extra}")
    _log(conn, ledger.PROBE, "h1_cadence", result,
         "Does scoring cadence change the base score, and what does weekly "
         "refitting cost against day-frozen? Predicted < 0.003 nats.")
    return result


# --- H2/H3: the sweeps -----------------------------------------------------


def h2_half_life(conn, frame, base) -> sweep.SweepResult:
    print("\nH2  half-life sweep")
    result = sweep.run(frame, "half_life", HALF_LIFE_GRID, base,
                       more_regularised=float, score_filter=served)
    _print_sweep(result, "H")
    _log(conn, ledger.SWEEP, "h2_half_life", result.as_detail(),
         "One decay sweep, selected on goal deviance by the 1-SE rule. "
         "Predicted optimum in [130, 240] and spread < 0.004 nats.")
    return result


def h3_alpha(conn, frame, base) -> sweep.SweepResult:
    print("\nH3  ridge alpha sweep")
    result = sweep.run(frame, "alpha", ALPHA_GRID, base,
                       more_regularised=float, score_filter=served)
    _print_sweep(result, "alpha")
    _log(conn, ledger.SWEEP, "h3_alpha", result.as_detail(),
         "One penalty sweep at the chosen half-life, same rule. "
         "Predicted optimum in [0.5, 2] and spread < 0.003 nats.")
    return result


def h4_interaction(conn, frame, base, half_life, alpha) -> dict:
    """Sequential sweeps are only valid on a separable surface."""
    print("\nH4  half-life x alpha interaction")
    grid = {"centre": (half_life, alpha)}
    h_lo, h_hi = max(HALF_LIFE_GRID[0], half_life - 70), min(HALF_LIFE_GRID[-1], half_life + 70)
    a_lo, a_hi = alpha / 2, alpha * 2
    for h in (h_lo, h_hi):
        for a in (a_lo, a_hi):
            grid[f"H{h:g}/a{a:g}"] = (h, a)
    arms = {name: replace(base, half_life=h, alpha=a) for name, (h, a) in grid.items()}
    result = sweep.compare(frame, arms, reference="centre", score_on=served)
    for name, entry in result["arms"].items():
        delta = entry.get("vs_reference", {})
        note = "" if not delta else f"  {delta['delta']:+.5f} [{delta['ci_low']:+.5f}, {delta['ci_high']:+.5f}]"
        print(f"  {name:14s} deviance {entry['deviance']:.5f}{note}")
    _log(conn, ledger.PROBE, "h4_h_alpha_interaction", result,
         "Do the two sweeps interact? Predicted no corner beats the centre "
         "beyond its bootstrap SE.")
    return result


# --- H6: the COVID scoring window ------------------------------------------


def h6_covid(conn, frame, base) -> dict:
    print("\nH6  COVID scoring window")
    scored = walk_forward(frame, replace(base, embargo_regimes=()))
    scored = served(scored)
    variants = {
        "all matches": np.ones(len(scored), dtype=bool),
        "covid window excluded": ~scored["match_date"].between(
            pd.Timestamp(2020, 3, 13), pd.Timestamp(2021, 5, 31)).to_numpy(),
        "covid window + 2021-22 excluded": (
            ~scored["match_date"].between(pd.Timestamp(2020, 3, 13), pd.Timestamp(2021, 5, 31))
            & (scored["season"] != "202122")).to_numpy(),
    }
    out = {}
    for name, mask in variants.items():
        subset = scored[mask]
        probs = metrics.model_probs(subset["lam_h"], subset["lam_a"])
        out[name] = {
            "n": int(len(subset)),
            "deviance": float(metrics.goal_deviance(subset).mean()),
            "ll_1x2": float(metrics.logloss_1x2(probs, subset["ftr"]).mean()),
            "home_margin_bias": float(
                ((subset["fthg"] - subset["ftag"]) - (subset["lam_h"] - subset["lam_a"])).mean()),
        }
        print(f"  {name:34s} n={out[name]['n']:6d} deviance {out[name]['deviance']:.5f} "
              f"bias {out[name]['home_margin_bias']:+.4f}")
    _log(conn, ledger.PROBE, "h6_covid_scoring_window", out,
         "How much of the base score is set by the empty-stadium regime? "
         "Predicted 0.002-0.008 nats for the window, < 0.003 more for 2021-22.")
    return out


def h2_covid_guard(conn, frame, base, chosen_half_life) -> dict:
    """The sweep's optimum must not be an artifact of one anomalous regime."""
    print("\nH2-guard  half-life sweep with 2020-21 and 2021-22 also excluded")

    def strict(scored):
        return served(scored[~scored["season"].isin(["202021", "202122"])])

    result = sweep.run(frame, "half_life", HALF_LIFE_GRID, base,
                       more_regularised=float, score_filter=strict)
    for arm in result.arms:
        print(f"  H={arm.value:<6} deviance {arm.deviance:.5f} "
              f"paired se {arm.paired_stderr:.5f}")
    moved = HALF_LIFE_GRID.index(result.chosen.value) - HALF_LIFE_GRID.index(chosen_half_life)
    print(f"  chosen {result.chosen.value} vs {chosen_half_life} -> {moved:+d} grid steps")
    detail = result.as_detail() | {"grid_steps_moved": moved,
                                   "main_sweep_choice": chosen_half_life}
    _log(conn, ledger.PROBE, "h2_covid_guard", detail,
         "Re-run of the decay sweep with the COVID seasons out of scoring. "
         "The optimum must not move by more than one grid step.")
    return detail


# --- H5: NEW-1, the National League ---------------------------------------


def _recent_ec_clubs(frame: pd.DataFrame) -> set[tuple[str, str]]:
    """(season, club) pairs for clubs that played in EC the season before.

    The specific population NEW-1 was supposed to help: a club promoted out of
    the National League has no E3 history, so if pooling the fit buys anything
    it should be visible here before anywhere else.
    """
    appearances = pd.concat([
        frame[["season", "division", "home_team"]].rename(columns={"home_team": "team"}),
        frame[["season", "division", "away_team"]].rename(columns={"away_team": "team"}),
    ]).drop_duplicates(["season", "team"])
    ec = appearances[appearances["division"] == "EC"]
    seasons = sorted(frame["season"].unique())
    following = {s: seasons[i + 1] for i, s in enumerate(seasons[:-1])}
    return {(following[s], t) for s, t in zip(ec["season"], ec["team"]) if s in following}


def h5_ec(conn, frame, base) -> dict:
    print("\nH5  NEW-1: National League in the joint fit")
    arms = {
        "E0-E3 only": replace(base, fit_divisions=SERVED_DIVISIONS),
        "E0-EC": replace(base, fit_divisions=ALL_DIVISIONS),
    }
    result = sweep.compare(frame, arms, reference="E0-E3 only", score_on=served)
    delta = result["arms"]["E0-EC"]["vs_reference"]
    print(f"  n={result['n']}  delta {delta['delta']:+.5f} "
          f"[{delta['ci_low']:+.5f}, {delta['ci_high']:+.5f}]  {delta['verdict']}")

    # Where any effect should concentrate, if there is one.
    per_division = {}
    scored = {name: served(walk_forward(frame, cfg)) for name, cfg in arms.items()}
    keys = ["match_date", "home_team", "away_team"]
    merged = scored["E0-E3 only"].merge(scored["E0-EC"], on=keys, suffixes=("_a", "_b"))
    for division, group in merged.groupby("division_a"):
        loss_a = metrics.goal_deviance(group.rename(
            columns={"lam_h_a": "lam_h", "lam_a_a": "lam_a", "fthg_a": "fthg", "ftag_a": "ftag"}))
        loss_b = metrics.goal_deviance(group.rename(
            columns={"lam_h_b": "lam_h", "lam_a_b": "lam_a", "fthg_b": "fthg", "ftag_b": "ftag"}))
        cmp = bootstrap.paired(loss_b, loss_a, bootstrap.week_blocks(group["match_date"]))
        per_division[division] = cmp.as_dict()
        print(f"  {division}  EC-included delta {cmp.delta:+.5f} "
              f"[{cmp.ci[0]:+.5f}, {cmp.ci[1]:+.5f}]")

    # The population the arm exists for: clubs promoted out of EC last season.
    promoted = _recent_ec_clubs(frame)
    involves = np.array([(s, h) in promoted or (s, a) in promoted
                         for s, h, a in zip(merged["season_a"], merged["home_team"],
                                            merged["away_team"])])
    subset = merged[involves]
    ec_promoted = None
    if len(subset) > 100:
        loss_a = metrics.goal_deviance(subset.rename(columns={
            "lam_h_a": "lam_h", "lam_a_a": "lam_a", "fthg_a": "fthg", "ftag_a": "ftag"}))
        loss_b = metrics.goal_deviance(subset.rename(columns={
            "lam_h_b": "lam_h", "lam_a_b": "lam_a", "fthg_b": "fthg", "ftag_b": "ftag"}))
        cmp = bootstrap.paired(loss_b, loss_a, bootstrap.week_blocks(subset["match_date"]))
        ec_promoted = cmp.as_dict()
        print(f"  clubs promoted from EC last season (n={len(subset)}): "
              f"delta {cmp.delta:+.5f} [{cmp.ci[0]:+.5f}, {cmp.ci[1]:+.5f}]  {cmp.verdict}")

    detail = result | {"per_division": per_division, "ec_promoted_clubs": ec_promoted}
    _log(conn, ledger.GATE, "h5_new1_ec_inclusion", detail,
         "Does adding National League matches to the joint fit help E0-E3? "
         "Predicted |delta| < 0.002 with CI containing zero; any effect in E3 "
         "and in clubs promoted across the E3/EC boundary.")
    return detail


# --- H8: OPEN-3, the off-season -------------------------------------------


def h8_offseason(conn, frame, base) -> dict:
    print("\nH8  OPEN-3: the off-season handoff")
    arms = {"calendar decay": base}
    for s in SHRINK_GRID:
        arms[f"shrink {s}"] = replace(base, season_boundary_shrink=s)
    arms["summer as 30 days"] = replace(base, offseason_gap_days=30.0)

    def early(scored):
        out = served(scored)
        return out[season_day(out) < EARLY_SEASON_DAYS].reset_index(drop=True)

    result = sweep.compare(frame, arms, reference="calendar decay", score_on=early)
    print(f"  early-season subset, n={result['n']}")
    for name, entry in result["arms"].items():
        delta = entry.get("vs_reference", {})
        note = "" if not delta else (f"  {delta['delta']:+.5f} "
                                     f"[{delta['ci_low']:+.5f}, {delta['ci_high']:+.5f}]"
                                     f"  {delta['verdict']}")
        print(f"  {name:20s} deviance {entry['deviance']:.5f}{note}")

    # An arm that helps in August must not cost anything over the full season.
    full = sweep.compare(frame, arms, reference="calendar decay", score_on=served)
    print("  full season:")
    for name, entry in full["arms"].items():
        delta = entry.get("vs_reference", {})
        note = "" if not delta else f"  {delta['delta']:+.5f}"
        print(f"    {name:20s} deviance {entry['deviance']:.5f}{note}")

    detail = {"early_season": result, "full_season": full,
              "early_season_days": EARLY_SEASON_DAYS}
    _log(conn, ledger.GATE, "h8_open3_offseason", detail,
         "Does shrinking strengths at the season boundary help the launch "
         "window? Predicted shrink 0.95 gains 0.005-0.015 nats early; the "
         "compressed-summer arm predicted to hurt.")
    return detail


# --- H10: is the information-set axis real? -------------------------------


def h10_information_set(conn, frame) -> dict:
    print("\nH10  is the pre-close/closing axis real?")
    both = frame.dropna(subset=["ps_h", "ps_d", "ps_a", "close_ps_h", "close_ps_d", "close_ps_a"])
    both = served(both).reset_index(drop=True)
    pre = metrics.market_probs(both, "pre_close_ps")
    close = metrics.market_probs(both, "closing")
    loss_pre = metrics.logloss_1x2(pre, both["ftr"])
    loss_close = metrics.logloss_1x2(close, both["ftr"])
    blocks = bootstrap.week_blocks(both["match_date"])

    out = {"pooled": bootstrap.paired(loss_close, loss_pre, blocks).as_dict(),
           "per_division": {}}
    print(f"  pooled n={len(both)}  closing - pre-close "
          f"{out['pooled']['delta']:+.5f} "
          f"[{out['pooled']['ci_low']:+.5f}, {out['pooled']['ci_high']:+.5f}]")
    for division, index in both.groupby("division").groups.items():
        rows = both.index.get_indexer(index)
        cmp = bootstrap.paired(loss_close[rows], loss_pre[rows], blocks[rows])
        out["per_division"][division] = cmp.as_dict() | {"n": len(rows)}
        print(f"  {division}  n={len(rows):5d}  {cmp.delta:+.5f} "
              f"[{cmp.ci[0]:+.5f}, {cmp.ci[1]:+.5f}]  {cmp.verdict}")
    _log(conn, ledger.PROBE, "h10_information_set_sharpness", out,
         "Pinnacle closing vs Pinnacle pre-close, same matches and same book. "
         "P3 splits every population on this axis; predicted closing sharper "
         "by 0.002-0.008 nats, largest in E0.")
    return out


# --- H9 and D5: the base score --------------------------------------------


def _h9_check(group, model, market, cell) -> list[str]:
    """Any cell where the model appears to beat the market gets a CI before it
    is called a breach.

    The hard stop covers both served markets, not just 1X2: the first P1 run
    produced a negative O/U gap in one cell that a 1X2-only check would have
    waved through. A point estimate on its own cannot distinguish a leak from
    a thousand-match sampling wobble, so it does not get to raise the alarm.
    """
    blocks = bootstrap.week_blocks(group["match_date"])
    y_over = metrics.over_outcome(group)
    candidates = {
        "1x2": (metrics.logloss_1x2(model, group["ftr"]),
                metrics.logloss_1x2(market, group["ftr"])),
        "ou25": (metrics.logloss_binary(model["p_over"], y_over),
                 metrics.logloss_binary(market["p_over"], y_over)),
    }
    breaches = []
    for name, (model_loss, market_loss) in candidates.items():
        if float(model_loss.mean() - market_loss.mean()) >= 0:
            continue
        cmp = bootstrap.paired(model_loss, market_loss, blocks)
        print(f"  model ahead of market in {cell}/{name}: {cmp.delta:+.5f} "
              f"[{cmp.ci[0]:+.5f}, {cmp.ci[1]:+.5f}]  {cmp.verdict}")
        if cmp.excludes_zero:
            breaches.append(f"{cell}/{name}")
        else:
            print("    CI spans zero -- sampling noise, not a breach.")
    return breaches


def h9_baseline(conn, frame, cfg) -> dict:
    print("\nH9/D5  the base score, against market and base rate")
    scored = served(walk_forward(frame, cfg))
    probs = metrics.model_probs(scored["lam_h"], scored["lam_a"])

    rows = []
    breaches = []
    for information_set in ("pre_close", "closing"):
        cols = metrics.MARKET_COLUMNS[information_set]
        needed = list(cols["1x2"]) + list(cols["ou25"])
        priced = scored.dropna(subset=needed)
        if priced.empty:
            continue
        market = metrics.market_probs(priced, information_set)
        model = probs.loc[priced.index]
        for division, group in priced.groupby("division"):
            index = group.index
            model_card = metrics.score(group, model.loc[index])
            market_card = metrics.score(group, market.loc[index], with_deviance=False)
            base_card = metrics.score(group, metrics.base_rate_probs(group),
                                      with_deviance=False)
            gap = model_card.ll_1x2 - market_card.ll_1x2

            breaches += _h9_check(group, model.loc[index], market.loc[index],
                                  f"{information_set}/{division}")
            rows.append({
                "information_set": information_set, "division": division,
                "n": len(group),
                "model_ll_1x2": model_card.ll_1x2, "market_ll_1x2": market_card.ll_1x2,
                "base_ll_1x2": base_card.ll_1x2, "gap_1x2": gap,
                "model_ll_ou25": model_card.ll_ou25, "market_ll_ou25": market_card.ll_ou25,
                "gap_ou25": model_card.ll_ou25 - market_card.ll_ou25,
                "model_brier_1x2": model_card.brier_1x2,
                "market_brier_1x2": market_card.brier_1x2,
                "model_auc_ou25": model_card.auc_ou25,
                "deviance": model_card.deviance,
                "share_of_market_edge": (base_card.ll_1x2 - model_card.ll_1x2)
                                        / (base_card.ll_1x2 - market_card.ll_1x2),
            })

    table = pd.DataFrame(rows)
    print(table.round(4).to_string(index=False))
    if breaches:
        print("\n  *** H9 BREACH: the model beat the market in "
              f"{', '.join(breaches)}. Halt and hunt a leak. ***")
    else:
        print("\n  H9 holds: the model is behind the market everywhere.")

    detail = {"config": cfg.label(), "rows": rows, "h9_breaches": breaches}
    _log(conn, ledger.GATE, "p1_base_score", detail,
         "The base score every later gate sits on. H9: a goals-and-dates head "
         "beating a closing line would be a leak, not a discovery.")
    return detail


# --- driver ----------------------------------------------------------------


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", default="all",
                        choices=["all", "h1", "sweeps", "rest",
                                 "h6", "h5", "h8", "h10", "baseline"])
    parser.add_argument("--out", default="docs/p1_results.json")
    # Frozen hyperparameters, so the stages after the sweeps can be run without
    # repeating them -- and so re-running a sweep is always a deliberate act
    # that appears in the ledger rather than a side effect of asking for
    # something else.
    parser.add_argument("--half-life", type=float)
    parser.add_argument("--alpha", type=float)
    parser.add_argument("--exclude-ec", action="store_true",
                        help="fit on E0-E3 only (the NEW-1 decision)")
    parser.add_argument("--shrink", type=float,
                        help="season-boundary shrink factor (the OPEN-3 decision)")
    args = parser.parse_args(argv)

    conn = db.connect()
    frame = load(conn)
    print(f"development corpus: {len(frame)} matches, "
          f"{frame.season.min()}-{frame.season.max()}, "
          f"{sorted(frame.division.unique())}")

    results: dict = {}
    base = BASE
    if args.half_life is not None:
        base = replace(base, half_life=args.half_life)
    if args.alpha is not None:
        base = replace(base, alpha=args.alpha)
    if args.exclude_ec:
        base = replace(base, fit_divisions=SERVED_DIVISIONS)
    if args.shrink is not None:
        base = replace(base, season_boundary_shrink=args.shrink)
    print(f"base config: {base.label()}")

    rest = ("all", "rest")
    if args.stage in ("all", "h1"):
        results["h1"] = h1_cadence(conn, frame)
    if args.stage in ("all", "sweeps"):
        h2 = h2_half_life(conn, frame, base)
        base = replace(base, half_life=float(h2.chosen.value))
        h3 = h3_alpha(conn, frame, base)
        base = replace(base, alpha=float(h3.chosen.value))
        results["h2"] = h2.as_detail()
        results["h3"] = h3.as_detail()
        results["h4"] = h4_interaction(conn, frame, base, h2.chosen.value, h3.chosen.value)
        results["h2_guard"] = h2_covid_guard(conn, frame, base, h2.chosen.value)
        results["chosen"] = {"half_life": base.half_life, "alpha": base.alpha}
    if args.stage in (*rest, "h5"):
        results["h5"] = h5_ec(conn, frame, base)
    if args.stage in (*rest, "h6"):
        results["h6"] = h6_covid(conn, frame, base)
    if args.stage in (*rest, "h8"):
        results["h8"] = h8_offseason(conn, frame, base)
    if args.stage in (*rest, "h10"):
        results["h10"] = h10_information_set(conn, frame)
    if args.stage in (*rest, "baseline"):
        results["baseline"] = h9_baseline(conn, frame, base)
    results["final_config"] = base.label()

    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(results, handle, indent=2, default=str)
    print(f"\nwritten to {args.out}")
    print(f"recorded trials: {ledger.trial_count(conn)}")


if __name__ == "__main__":
    main()
