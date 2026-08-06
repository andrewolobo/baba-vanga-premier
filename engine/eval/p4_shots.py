"""P4-shots: does a shots-on-target channel improve the strength layer?

    python -m engine.eval.p4_shots --stage all

Runs the arms pre-registered in `docs/P4_SHOTS_PLAN.md` in order and writes
every result -- including nulls -- to the gate ledger. H25 runs first: it is the
positive control, and if a shots channel built from end-of-season data cannot
move the fit, nothing else here is interpretable.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import replace

import numpy as np
import pandas as pd

from engine import db, ledger, store
from engine.eval import bootstrap, metrics, sweep
from engine.eval.p1 import BASE, served
from engine.eval.walkforward import walk_forward
from engine.seasons import DEV_SEASONS, SERVED_DIVISIONS

HEAD = replace(BASE, half_life=400.0, alpha=0.1, embargo_regimes=("covid_empty_stadiums",))

#: Pre-registered in P4_SHOTS_PLAN.md §3. Zero first so the sweep contains its
#: own baseline and the 1-SE tie-break can land on "no feature".
BLEND_GRID = [0.0, 0.15, 0.3, 0.45, 0.6, 0.8]


def load(conn) -> pd.DataFrame:
    return store.read_matches(conn, seasons=DEV_SEASONS).for_measurement()


def _log(conn, kind, name, detail, reason):
    ledger.record(conn, kind=kind, name=name, purpose="dev", seasons=DEV_SEASONS,
                  divisions=SERVED_DIVISIONS, detail=detail, reason=reason)
    print(f"  [ledger] {kind}:{name}")


def _show(result) -> None:
    ref = result["reference"]
    for name, arm in result["arms"].items():
        line = (f"  {name:22s} deviance {arm['deviance']:.5f}  "
                f"1X2 {arm['ll_1x2']:.5f}  OU {arm['ll_ou25']:.5f}")
        cmp = arm.get("vs_reference")
        if cmp:
            line += (f"  {cmp['delta']:+.5f} "
                     f"[{cmp['ci_low']:+.5f}, {cmp['ci_high']:+.5f}]")
        print(line + ("   <- reference" if name == ref else ""))


# --- H25: the positive control, first -------------------------------------


def h25_oracle(conn, frame) -> dict:
    """A shots channel fitted with the season already played.

    Not servable and never served. It exists to prove the arm can move the fit
    when the shot data genuinely carries something -- P2's H17 lesson, where a
    null only became a finding because an oracle had shown the harness could
    see a real effect.
    """
    print("\nH25  positive control: an oracle in the shots column")
    arms = {"baseline": HEAD, "oracle sot": replace(HEAD, shots_blend=0.6)}
    result = sweep.compare(_oracle_frame(frame), arms, reference="baseline",
                           score_on=served)
    _show(result)
    _log(conn, ledger.PROBE, "h25_shots_oracle_control", result,
         "Positive control for P4-shots. If a shots channel built with the "
         "season already played cannot move the fit, H20's result is not a "
         "null but a broken instrument, and P4_SHOTS_PLAN.md 4 says stop.")
    return result


def _oracle_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """The corpus with the shots column replaced by a low-noise oracle.

    Shots-on-target is overwritten by a low-noise function of each club's
    **season-long** rates, so `att_s` and `dfn_s` become near-noiseless reads of
    true season strength -- what a perfect shots proxy would deliver -- while
    travelling through the identical code path the real arm uses. A difference
    here is therefore the channel working, not a second implementation.

    **The oracle must carry both sides.** A first version built it from each
    club's goals scored alone; `dfn_s` then had nothing real to fit, so blending
    improved attack (correlation with future goals-for 0.270 -> 0.423) and
    destroyed defence (0.195 -> 0.019), and the two cancelled to nothing. That
    read as "the channel does not work" when it meant "the control was blind in
    one eye". The column below has the attack x defence structure the GLM
    expects.

    Not servable: season rates are unknown mid-season and include the match
    being priced. Both make this an upper bound, which is what a ceiling is for.
    """
    work = frame.copy()
    rng = np.random.default_rng(0)

    # Season-long scoring and conceding rates per club, on one long frame.
    long = pd.concat([
        work.assign(_club=work["home_team"], _gf=work["fthg"], _ga=work["ftag"]),
        work.assign(_club=work["away_team"], _gf=work["ftag"], _ga=work["fthg"]),
    ])
    rates = long.groupby(["season", "_club"]).agg(gf=("_gf", "mean"),
                                                  ga=("_ga", "mean"))
    league = long.groupby("season")["_gf"].mean()

    def rate_of(season, club, column):
        return rates[column].reindex(
            pd.MultiIndex.from_arrays([season, club])).to_numpy()

    for side, other in (("home", "away"), ("away", "home")):
        attack = rate_of(work["season"], work[f"{side}_team"], "gf")
        defence = rate_of(work["season"], work[f"{other}_team"], "ga")
        mean = work["season"].map(league).to_numpy()
        expected = np.nan_to_num(attack * defence / np.where(mean > 0, mean, 1.0),
                                 nan=1.0)
        # x10 so the oracle sits at realistic sot counts and the Poisson fit
        # sees comparable dispersion to the column it replaces.
        work[f"{side}_sot"] = rng.poisson(np.clip(10.0 * expected, 0.1, None))
    return work


# --- H20: the sweep --------------------------------------------------------


def h20_blend_sweep(conn, frame) -> sweep.SweepResult:
    print("\nH20  shots blend weight, swept")
    result = sweep.run(frame, "shots_blend", BLEND_GRID, HEAD,
                       more_regularised=lambda v: -float(v), score_filter=served)
    for arm in result.arms:
        mark = " <-- chosen" if arm.value == result.chosen.value else ""
        best = " (best)" if arm.value == result.best.value else ""
        print(f"  w={arm.value:<5} deviance {arm.deviance:.5f}  "
              f"paired se {arm.paired_stderr:.5f}  1X2 {arm.ll_1x2:.5f}"
              f"{best}{mark}")
    print(f"  best {result.best.value}, 1-SE choice {result.chosen.value}, "
          f"censored: {result.censored}")
    _log(conn, ledger.SWEEP, "h20_shots_blend", result.as_detail(),
         "Pre-registered: rule selects w in [0.15, 0.45], deviance improves "
         "0.003-0.007 with CI excluding zero. Tie-break toward w=0.")
    return result


# --- H21: which side carries it -------------------------------------------


def h21_sides(conn, frame, weight: float) -> dict:
    print(f"\nH21  which side carries the channel (w={weight:g})")
    arms = {
        "baseline": HEAD,
        "both": replace(HEAD, shots_blend=weight),
        "att only": replace(HEAD, shots_blend=weight, shots_blend_sides="att"),
        "dfn only": replace(HEAD, shots_blend=weight, shots_blend_sides="dfn"),
    }
    result = sweep.compare(frame, arms, reference="baseline", score_on=served)
    _show(result)
    _log(conn, ledger.GATE, "h21_shots_sides", result,
         "Pre-registered: dfn-only delivers >= 60% of the full effect, "
         "att-only <= 50%, from the pre-gate's 0.060 vs 0.039 split-half gain.")
    return result


# --- H22 / H23 / H24: divisions, markets, the gap -------------------------


def h22_h24_divisions(conn, frame, weight: float) -> dict:
    print(f"\nH22/H23/H24  per division, and the gap to the market (w={weight:g})")
    base = served(walk_forward(frame, HEAD))
    arm = served(walk_forward(frame, replace(HEAD, shots_blend=weight)))
    key = ["match_date", "home_team", "away_team"]
    merged = base.set_index(key).join(arm.set_index(key), rsuffix="_s", how="inner")

    out = {}
    for division in ("pooled", *SERVED_DIVISIONS):
        sub = merged if division == "pooled" else merged[merged["division"] == division]
        if len(sub) < 200:
            continue
        left = metrics.goal_deviance(sub)
        right = metrics.goal_deviance(pd.DataFrame({
            "lam_h": sub["lam_h_s"], "lam_a": sub["lam_a_s"],
            "fthg": sub["fthg"], "ftag": sub["ftag"]}))
        dates = sub.index.get_level_values("match_date")
        blocks = bootstrap.week_blocks(dates)
        cmp = bootstrap.paired(right, left, blocks)
        row = cmp.as_dict() | {"n": len(sub)}

        priced = sub.dropna(subset=["avg_h", "avg_d", "avg_a"])
        if len(priced) > 500:
            market = metrics.market_probs(priced, "pre_close")
            base_p = metrics.model_probs(priced["lam_h"], priced["lam_a"])
            arm_p = metrics.model_probs(priced["lam_h_s"], priced["lam_a_s"])
            ll_m = metrics.logloss_1x2(market, priced["ftr"])
            b = bootstrap.week_blocks(priced.index.get_level_values("match_date"))
            row["deficit_base"] = bootstrap.paired(
                metrics.logloss_1x2(base_p, priced["ftr"]), ll_m, b).delta
            row["deficit_arm"] = bootstrap.paired(
                metrics.logloss_1x2(arm_p, priced["ftr"]), ll_m, b).delta
        out[division] = row
        print(f"  {division:8s} n={len(sub):6,}  {cmp.delta:+.5f} "
              f"[{cmp.ci[0]:+.5f}, {cmp.ci[1]:+.5f}]  {cmp.verdict}"
              + (f"   deficit {row['deficit_base']:+.5f} -> {row['deficit_arm']:+.5f}"
                 if "deficit_arm" in row else ""))
    _log(conn, ledger.GATE, "h22_h24_shots_divisions", out,
         "Pre-registered: effect present and negative in all four divisions, "
         "largest < 3x smallest; pooled 1X2 deficit moves from +0.01419 to "
         "between +0.010 and +0.013 and does not reach zero.")
    return out


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", default="all",
                        choices=["all", "h25", "h20", "h21", "h22"])
    parser.add_argument("--weight", type=float,
                        help="blend weight for H21/H22 (default: H20's choice)")
    parser.add_argument("--out", default="docs/p4_shots_results.json")
    args = parser.parse_args(argv)

    conn = db.connect()
    frame = load(conn)
    print(f"{len(frame):,} matches, dev set")

    results, weight = {}, args.weight
    if args.stage in ("all", "h25"):
        results["h25"] = h25_oracle(conn, frame)
    if args.stage in ("all", "h20"):
        chosen = h20_blend_sweep(conn, frame)
        results["h20"] = chosen.as_detail()
        weight = weight or float(chosen.chosen.value)
    weight = weight or 0.3
    if args.stage in ("all", "h21"):
        results["h21"] = h21_sides(conn, frame, weight)
    if args.stage in ("all", "h22"):
        results["h22"] = h22_h24_divisions(conn, frame, weight)

    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(results, handle, indent=2, default=str)
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
