"""B12: do total shots and corners add a third and fourth strength channel?

    python -m engine.eval.channels_gate --stage all --dry-run   # costs nothing
    python -m engine.eval.channels_gate --stage all             # spends 13

Runs the arms pre-registered in `docs/P4_CHANNELS_PLAN.md` in order and writes
every result -- including nulls -- to the gate ledger. H37 runs first: it is the
positive control, and if channels built with the season already played cannot
move the fit, nothing after it is interpretable.

The reference throughout is the **shipped head**, `sot` at w = 0.3, not a
goals-only fit. B12's null hypothesis is "one auxiliary channel is enough".

`--dry-run` writes no ledger row and no document. `META.md` 9 records four
byte-identical implementation runs that each cost a row; this flag exists so
that cannot happen again.
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
from engine.eval.walkforward import ChannelBlendConfig, walk_forward
from engine.seasons import DEV_SEASONS, SERVED_DIVISIONS

#: The **served** head, `H400/a0.1/weekly/E0+E1+E2+E3+EC/sot0.3`, expressed so
#: the channel list can be varied. At the default `("sot",)` it is the plain
#: `WalkForwardConfig` bit for bit -- asserted in `tests/test_channel_blend.py`.
#:
#: Written out rather than imported from `p4_shots.HEAD`, which is the head as
#: it stood *before* the shots channel was adopted (`shots_blend=None`) and is
#: the baseline that gate measured against. Taking it by mistake gives arms
#: that differ from each other and from nothing else, which is exactly the
#: null this gate would then have reported. Matches `rest.py`, `tod.py`,
#: `travel.py` and `meta.py`, which each pin the same served head.
SHIPPED = ChannelBlendConfig(**replace(
    BASE, half_life=400.0, alpha=0.1, shots_blend=0.3,
    embargo_regimes=("covid_empty_stadiums",)).__dict__)

#: The channels the gate is about, in the order the pre-gate ranked them.
FULL = ("sot", "shots", "corners")

#: Pre-registered in P4_CHANNELS_PLAN.md 3. Zero first so the sweep contains a
#: goals-only fit and the tie-break can land on "no auxiliary layer at all".
BLEND_GRID = [0.0, 0.15, 0.30, 0.45, 0.60]

#: Fixed so the recorded control is reproducible.
NOISE_SEED = 20260810
ORACLE_SEED = 0


def load(conn) -> pd.DataFrame:
    return store.read_matches(conn, seasons=DEV_SEASONS).for_measurement()


def _log(conn, kind, name, detail, reason, *, dry_run: bool) -> None:
    if dry_run:
        print(f"  [dry-run] would record {kind}:{name}")
        return
    ledger.record(conn, kind=kind, name=name, purpose="dev", seasons=DEV_SEASONS,
                  divisions=SERVED_DIVISIONS, detail=detail, reason=reason)
    print(f"  [ledger] {kind}:{name}")


def _show(result) -> None:
    ref = result["reference"]
    for name, arm in result["arms"].items():
        line = (f"  {name:24s} deviance {arm['deviance']:.5f}  "
                f"1X2 {arm['ll_1x2']:.5f}  OU {arm['ll_ou25']:.5f}")
        cmp = arm.get("vs_reference")
        if cmp:
            line += (f"  {cmp['delta']:+.5f} "
                     f"[{cmp['ci_low']:+.5f}, {cmp['ci_high']:+.5f}]")
        print(line + ("   <- reference" if name == ref else ""))


# --- the two synthetic corpora ---------------------------------------------


def _mirror_presence(values: np.ndarray, source: pd.Series) -> np.ndarray:
    """Blank the synthetic column wherever the real one is blank.

    Without this a synthetic channel is observed everywhere, including the
    National League from 2016-17, so the arm using it would blend a different
    set of clubs from the arm it is being compared with -- and the control
    would differ from the real arm in two ways rather than one.
    """
    out = values.astype(float)
    out[pd.to_numeric(source, errors="coerce").isna().to_numpy()] = np.nan
    return out


def with_noise(frame: pd.DataFrame) -> pd.DataFrame:
    """Two channels carrying no information, matched to the real ones.

    Poisson draws at the shots and corners rates, independent of every match.
    They enter the composite exactly as the real channels do, so the arm using
    them isolates what the *arithmetic* of averaging k channels is worth --
    which, because the composite is renormalised, should be nothing.
    """
    work = frame.copy()
    rng = np.random.default_rng(NOISE_SEED)
    for name, source in (("noise1", "shots"), ("noise2", "corners")):
        for side in ("home", "away"):
            column = frame[f"{side}_{source}"]
            rate = float(pd.to_numeric(column, errors="coerce").mean())
            work[f"{side}_{name}"] = _mirror_presence(
                rng.poisson(rate, len(frame)), column)
    return work


def oracle_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """The corpus with shots and corners replaced by low-noise oracles.

    Each is overwritten by a low-noise function of the two clubs' **season-long**
    rates, so `att_c` and `dfn_c` become near-noiseless reads of true season
    strength -- what a perfectly-measured channel would deliver -- while
    travelling through the identical code path the real arms use.

    **Both sides, deliberately.** `SHOTS_TARGET.md` 2 records the first version
    of this control being built from goals scored alone: `dfn` then had nothing
    real to fit, attack improved, defence was destroyed, and the two cancelled
    to nothing. That read as "the channel does not work" when it meant "the
    control was blind in one eye".

    `sot` is left real, because the reference arm is the shipped head and the
    question is what *these two* channels could be worth on top of it.

    Not servable: season rates are unknown mid-season and include the match
    being priced. Both make this an upper bound, which is what a ceiling is for.
    """
    work = frame.copy()
    rng = np.random.default_rng(ORACLE_SEED)

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

    for channel in ("shots", "corners"):
        # Scaled to the channel's own observed rate, so the Poisson fit sees
        # dispersion comparable to the column it replaces.
        scale = float(pd.to_numeric(work[f"home_{channel}"], errors="coerce").mean())
        for side, other in (("home", "away"), ("away", "home")):
            attack = rate_of(work["season"], work[f"{side}_team"], "gf")
            defence = rate_of(work["season"], work[f"{other}_team"], "ga")
            mean = work["season"].map(league).to_numpy()
            expected = np.nan_to_num(attack * defence / np.where(mean > 0, mean, 1.0),
                                     nan=1.0)
            work[f"{side}_{channel}"] = _mirror_presence(
                rng.poisson(np.clip(scale * expected, 0.1, None)),
                frame[f"{side}_{channel}"])
    return work


# --- H37: the positive control, first --------------------------------------


def h37_oracle(conn, frame, *, dry_run: bool) -> dict:
    print("\nH37  positive control: oracles in the shots and corners columns")
    arms = {"shipped": SHIPPED,
            "oracle shots+corners": replace(SHIPPED, blend_channels=FULL)}
    result = sweep.compare(oracle_frame(frame), arms, reference="shipped",
                           score_on=served)
    _show(result)
    _log(conn, ledger.PROBE, "h37_channels_oracle_control", result,
         "Positive control for B12. If channels built with the season already "
         "played cannot move the fit against the shipped head, H38/H39 are not "
         "a null but a broken instrument, and P4_CHANNELS_PLAN.md 4 says stop.",
         dry_run=dry_run)
    return result


# --- H38: the composite weight ---------------------------------------------


def h38_blend_sweep(conn, frame, *, dry_run: bool) -> sweep.SweepResult:
    print("\nH38  composite weight for sot+shots+corners, swept")
    base = replace(SHIPPED, blend_channels=FULL)
    result = sweep.run(frame, "shots_blend", BLEND_GRID, base,
                       more_regularised=lambda v: -float(v), score_filter=served)
    for arm in result.arms:
        mark = " <-- chosen" if arm.value == result.chosen.value else ""
        best = " (best)" if arm.value == result.best.value else ""
        print(f"  w={arm.value:<5} deviance {arm.deviance:.5f}  "
              f"paired se {arm.paired_stderr:.5f}  1X2 {arm.ll_1x2:.5f}"
              f"{best}{mark}")
    print(f"  best {result.best.value}, 1-SE choice {result.chosen.value}, "
          f"censored: {result.censored}")
    _log(conn, ledger.SWEEP, "h38_channel_blend", result.as_detail(),
         "Pre-registered: the rule selects w >= 0.30 and the optimum is "
         "interior. Tie-break toward w=0.", dry_run=dry_run)
    return result


# --- H39: which channel carries it, and the matched control ----------------


def h39_decomposition(conn, frame, weight: float, *, dry_run: bool) -> dict:
    print(f"\nH39  which channel carries it, and the noise control (w={weight:g})")
    arms = {
        "shipped": SHIPPED,
        f"sot @ {weight:g}": replace(SHIPPED, shots_blend=weight),
        "+shots": replace(SHIPPED, shots_blend=weight,
                          blend_channels=("sot", "shots")),
        "+corners": replace(SHIPPED, shots_blend=weight,
                            blend_channels=("sot", "corners")),
        "+both": replace(SHIPPED, shots_blend=weight, blend_channels=FULL),
        "+noise x2": replace(SHIPPED, shots_blend=weight,
                             blend_channels=("sot", "noise1", "noise2")),
    }
    result = sweep.compare(with_noise(frame), arms, reference="shipped",
                           score_on=served)
    _show(result)
    _log(conn, ledger.GATE, "h39_channel_decomposition", result,
         "Pre-registered: +both improves 0.003-0.008 with CI excluding zero; "
         "both singles negative; +both sub-additive; +noise x2 not negative. "
         "The `sot @ w` arm separates the weight moving from the channels.",
         dry_run=dry_run)
    return result


# --- H40: per division, the markets, and the gap ---------------------------


def h40_divisions(conn, frame, weight: float, *, dry_run: bool) -> dict:
    print(f"\nH40  per division, and the gap to the market (w={weight:g})")
    base = served(walk_forward(frame, SHIPPED))
    arm = served(walk_forward(frame, replace(SHIPPED, shots_blend=weight,
                                             blend_channels=FULL)))
    key = ["match_date", "home_team", "away_team"]
    merged = base.set_index(key).join(arm.set_index(key), rsuffix="_c", how="inner")

    out = {}
    for division in ("pooled", *SERVED_DIVISIONS):
        sub = merged if division == "pooled" else merged[merged["division"] == division]
        if len(sub) < 200:
            continue
        left = metrics.goal_deviance(sub)
        right = metrics.goal_deviance(pd.DataFrame({
            "lam_h": sub["lam_h_c"], "lam_a": sub["lam_a_c"],
            "fthg": sub["fthg"], "ftag": sub["ftag"]}))
        dates = sub.index.get_level_values("match_date")
        blocks = bootstrap.week_blocks(dates)
        cmp = bootstrap.paired(right, left, blocks)
        row = cmp.as_dict() | {"n": len(sub)}

        priced = sub.dropna(subset=["avg_h", "avg_d", "avg_a"])
        if len(priced) > 500:
            market = metrics.market_probs(priced, "pre_close")
            base_p = metrics.model_probs(priced["lam_h"], priced["lam_a"])
            arm_p = metrics.model_probs(priced["lam_h_c"], priced["lam_a_c"])
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
    _log(conn, ledger.GATE, "h40_channels_divisions", out,
         "Pre-registered: effect present and negative in all four divisions, "
         "largest < 3x smallest; pooled 1X2 deficit moves from +0.01230 to "
         "between +0.008 and +0.011 and does not reach zero. Records no arm "
         "list: it re-scores arms H38/H39 already spent.", dry_run=dry_run)
    return out


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", default="all",
                        choices=["all", "h37", "h38", "h39", "h40"])
    parser.add_argument("--weight", type=float,
                        help="composite weight for H39/H40 (default: H38's choice)")
    parser.add_argument("--dry-run", action="store_true",
                        help="run the arms, write no ledger row and no document")
    parser.add_argument("--past-failed-control", action="store_true",
                        help="run H38-H40 even though H37 missed its bar. "
                             "Requires that the resulting rows be registered in "
                             "trials.POST_HOC_TRIALS; see CHANNELS_GATE.md 2.")
    parser.add_argument("--out", default="docs/channels_gate_results.json")
    args = parser.parse_args(argv)

    conn = db.connect()
    frame = load(conn)
    print(f"{len(frame):,} matches, dev set"
          + ("   [DRY RUN -- nothing is recorded]" if args.dry_run else ""))

    results, weight = {}, args.weight
    if args.stage in ("all", "h37"):
        results["h37"] = h37_oracle(conn, frame, dry_run=args.dry_run)
        control = results["h37"]["arms"]["oracle shots+corners"]["vs_reference"]
        if not (control["delta"] <= -0.008 and control["excludes_zero"]):
            print("\n  H37 FAILED the pre-registered bar (<= -0.008, CI excluding "
                  "zero). P4_CHANNELS_PLAN.md 4: nothing after this is reported "
                  "as a finding.")
            # The override is a flag rather than an edit to this condition, so
            # that continuing past a stop rule is a recorded act at the command
            # line instead of a silently relaxed threshold. CALIBRATION.md 1 is
            # about bars that move after real results are in view; this one did.
            if args.stage == "all" and not args.past_failed_control:
                print("  Pass --past-failed-control to continue anyway. Doing so "
                      "makes H38-H40 post-hoc: register them in "
                      "trials.POST_HOC_TRIALS before publishing anything.")
                return 1
            if args.past_failed_control:
                print("  --past-failed-control given: continuing. H38-H40 are "
                      "POST-HOC and are registered as such.")
    if args.stage in ("all", "h38"):
        chosen = h38_blend_sweep(conn, frame, dry_run=args.dry_run)
        results["h38"] = chosen.as_detail()
        weight = weight if weight is not None else float(chosen.chosen.value)
    weight = 0.30 if weight is None else weight
    if args.stage in ("all", "h39"):
        results["h39"] = h39_decomposition(conn, frame, weight, dry_run=args.dry_run)
    if args.stage in ("all", "h40"):
        results["h40"] = h40_divisions(conn, frame, weight, dry_run=args.dry_run)

    if args.dry_run:
        print("\n(dry run -- no ledger row written, no results file)")
        return 0
    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(results, handle, indent=2, default=str)
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
