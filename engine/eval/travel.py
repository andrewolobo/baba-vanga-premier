"""P4-travel: does away-travel distance carry anything?

    python -m engine.eval.travel --stage control     # the positive control, alone
    python -m engine.eval.travel --stage all

Pre-registration in `docs/P4_TRAVEL_PLAN.md`, written before any arm was fitted
to real outcomes. The third of SPEC 3.6's replacement analogues, after the
kickoff slot (unresolvable) and rest (bounded null).

**The control runs first and it runs alone.** `h34_power` plants an effect of
known size into Poisson-resampled outcomes, so it spends no information about
the real answer, and the plan's stop condition turns on it: if the instrument
cannot recover a 5% deficit in at least 4 draws of 6, the real arms are not run
at all and the finding is "this corpus cannot answer it", as it was for the
kickoff slot. That is a different result from a null, with a different action,
and the only thing that separates them is this stage.

Distance is great-circle between the two clubs' current grounds, from
`reference/stadiums.csv`. The two approximations that carries -- straight line
rather than road, and one static ground per club -- are stated in the plan
rather than fixed here, because neither is tunable and both bias toward
measuring less than is really there.
"""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

from engine import db, ledger, store
from engine.eval import bootstrap, metrics
from engine.eval.p1 import BASE, served
from engine.eval.walkforward import walk_forward
from engine.seasons import DEV_SEASONS, SERVED_DIVISIONS
from services.stadium_coords.reconcile import haversine_km

HEAD = replace(BASE, half_life=400.0, alpha=0.1, shots_blend=0.3,
               embargo_regimes=("covid_empty_stadiums",))

STADIUMS = Path("reference/stadiums.csv")

#: Distance bands for A2. Chosen from the measured distribution before any arm
#: was fitted -- median 176 km, p10 53, p90 321 -- so the edges sit at round
#: numbers spanning it rather than at quantiles of the outcome.
BAND_EDGES = [-1, 75, 150, 250, 350, 9999]
BAND_LABELS = ["<75", "75-150", "150-250", "250-350", ">350"]

#: The planted deficit is linear in distance and expressed at this reference,
#: which is near the longest trip in the corpus (537 km).
REFERENCE_KM = 500.0

#: Attacking deficit at REFERENCE_KM, as a fraction, before scaling.
PLANT_PCT = 0.05
PLANT_SCALES = (0.0, 0.25, 0.5, 1.0, 2.0)
PLANT_AS_SPECIFIED = 3  # index of the 1.0 row -- the plan's stop condition

ARM_SLOPE = "A1 slope"
ARM_BANDS = "A2 bands"


def load_stadiums(path: Path = STADIUMS) -> dict[str, tuple[float, float]]:
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found. Build it with `python -m services.stadium_coords`.")
    with path.open(encoding="utf-8", newline="") as handle:
        return {r["canonical_name"]: (float(r["lat"]), float(r["lon"]))
                for r in csv.DictReader(handle)}


def load(conn) -> pd.DataFrame:
    """Scored matches with the away side's travel distance attached.

    Unlike rest, distance needs no as-of reasoning and no within-season
    bookkeeping: it is a property of the fixture, known the moment the fixture
    list is published. There is correspondingly no leakage surface here, which
    is worth stating because it is the one context feature that has none.
    """
    coords = load_stadiums()
    raw = store.read_matches(conn, seasons=DEV_SEASONS).for_measurement()
    f = served(walk_forward(raw, HEAD)).copy()

    missing = ({*f.home_team, *f.away_team}) - set(coords)
    if missing:
        raise KeyError(
            f"{len(missing)} club(s) have no stadium coordinate: "
            f"{sorted(missing)[:8]}. A silently dropped club yields a feature "
            "that is null for every match it played.")

    f["distance"] = [haversine_km(coords[h], coords[a])
                     for h, a in zip(f.home_team, f.away_team)]
    f["band"] = pd.cut(f.distance, BAND_EDGES, labels=BAND_LABELS)
    return f.reset_index(drop=True)


def _log(conn, kind, name, detail, reason):
    ledger.record(conn, kind=kind, name=name, purpose="dev", seasons=DEV_SEASONS,
                  divisions=SERVED_DIVISIONS, detail=detail, reason=reason)
    print(f"  [ledger] {kind}:{name}")


# --- the arms ---------------------------------------------------------------


def slope_arm(f: pd.DataFrame):
    """A1: one fitted slope on away distance, applied to the away lambda.

    Fitted leave-one-season-out on the away attacking residual against distance
    in units of REFERENCE_KM, so the coefficient reads directly as "goals per
    500 km". Only the away lambda moves -- the home side did not travel, and an
    arm that moved both would be fitting a different hypothesis from the one
    the plan registered.
    """
    lam_h, lam_a = f.lam_h.to_numpy(float), f.lam_a.to_numpy(float)
    out_a = lam_a.copy()
    d = f.distance.to_numpy(float) / REFERENCE_KM
    for season in sorted(f.season.unique()):
        train = f[f.season != season]
        td = train.distance.to_numpy(float) / REFERENCE_KM
        y = (train.ftag - train.lam_a).to_numpy(float)
        slope = float(np.polyfit(td, y, 1)[0]) if td.std() > 0 else 0.0
        idx = (f.season == season).to_numpy()
        out_a[idx] = np.clip(lam_a[idx] + slope * d[idx], 0.01, None)
    return lam_h, out_a


def band_arm(f: pd.DataFrame):
    """A2: a multiplicative factor per distance band, on the away lambda."""
    lam_h, lam_a = f.lam_h.to_numpy(float), f.lam_a.to_numpy(float)
    out_a = lam_a.copy()
    for season in sorted(f.season.unique()):
        train = f[f.season != season]
        grouped = train.groupby("band", observed=True)
        factor = grouped.ftag.sum() / grouped.lam_a.sum()
        idx = (f.season == season).to_numpy()
        out_a[idx] = lam_a[idx] * f.band[idx].map(factor).astype(float).fillna(1.0)
    return lam_h, out_a


def _delta(f, lam_h, lam_a, base):
    arm = metrics.goal_deviance(pd.DataFrame({
        "lam_h": lam_h, "lam_a": lam_a, "fthg": f.fthg, "ftag": f.ftag}))
    return bootstrap.paired(arm, base, bootstrap.week_blocks(f.match_date))


def slope_coefficient(goals, lam_a, d_ref) -> tuple[float, float]:
    """Poisson score estimate of the multiplicative distance slope, and its SE.

    The **resolution** statistic, adopted in `P4_TRAVEL_PLAN.md` §8 after the
    deviance delta missed a planted effect it was shown to contain. For a rate
    `lam*(1 + b*x)` the score equation is linear in `b`, so both the estimate
    and its standard error are closed-form -- no fitting, no refit noise, and
    nothing to tune.

    This answers "can the corpus see an effect of this size". It does **not**
    decide adoption: convention 2 keeps that on goal Poisson deviance, and
    `_delta` above is still what any real arm is judged by.

    Checked over 60 planted draws rather than the control's 6, because six is
    not enough to claim either property: at a planted −0.0500 it returns
    −0.05186 ± 0.00179 (1.0 sem, unbiased) and at a planted zero −0.00108 ±
    0.00175. Empirical sd is 0.0139 against the analytic 0.0149, so the
    reported standard error is mildly **conservative** — the test understates
    its own power rather than overstating it, which is the safe direction.
    """
    lam_a = np.asarray(lam_a, dtype=float)
    x = np.asarray(d_ref, dtype=float)
    fisher = float((lam_a * x * x).sum())
    if fisher <= 0:
        return 0.0, float("inf")
    beta = float(((np.asarray(goals, dtype=float) - lam_a) * x).sum() / fisher)
    return beta, 1.0 / np.sqrt(fisher)


# --- H34: the positive control ----------------------------------------------


def _plant(f, lam_h, lam_a, d_ref, scale, seed):
    """One Poisson-resampled frame carrying a known distance effect."""
    rng = np.random.default_rng(700 + seed)
    work = f.copy()
    work["fthg"] = rng.poisson(lam_h)
    work["ftag"] = rng.poisson(lam_a * (1.0 - PLANT_PCT * scale * d_ref))
    return work


def _one_scale(f, lam_h, lam_a, d_ref, scale, seeds) -> dict:
    """Both statistics, over `seeds` draws at one planted effect size."""
    coef, deviance = [], {ARM_SLOPE: [], ARM_BANDS: []}
    hits = {"coefficient": 0, ARM_SLOPE: 0, ARM_BANDS: 0}
    for seed in range(seeds):
        work = _plant(f, lam_h, lam_a, d_ref, scale, seed)
        beta, se = slope_coefficient(work.ftag, lam_a, d_ref)
        coef.append((beta, se))
        hits["coefficient"] += abs(beta) / se > 1.96
        base = metrics.goal_deviance(work)
        for name, arm in ((ARM_SLOPE, slope_arm), (ARM_BANDS, band_arm)):
            cmp = _delta(work, *arm(work), base)
            deviance[name].append((cmp.delta, cmp.stderr))
            hits[name] += cmp.delta < 0 and abs(cmp.delta) / cmp.stderr > 1.96

    row = {"planted_x": scale, "deficit_pct_at_500km": 100 * PLANT_PCT * scale}
    beta, se = float(np.mean([b for b, _ in coef])), float(np.mean([s for _, s in coef]))
    row["coefficient"] = {"beta": beta, "stderr": se, "t": abs(beta) / se,
                          "detected": f"{hits['coefficient']}/{seeds}"}
    for name, pairs in deviance.items():
        delta = float(np.mean([d for d, _ in pairs]))
        err = float(np.mean([e for _, e in pairs]))
        row[name] = {"delta": delta, "stderr": err,
                     "se_ratio": abs(delta) / err if err else 0.0,
                     "detected": f"{hits[name]}/{seeds}"}
    return row


def h34_power(conn, f: pd.DataFrame, seeds: int = 6) -> dict:
    """Plant an away deficit linear in distance and ask whether it is recovered.

    **The stop condition runs on the coefficient test**, per the plan's §8
    amendment. The deviance delta is computed for both arms alongside it and is
    the adoption criterion for any real arm -- it is reported here so the gap
    between "the corpus can see it" and "it is worth having" stays visible.

    The ×0 row is not padding. For the coefficient test it is the false-positive
    check; for the deviance arms it measures what each costs when fitted to data
    with no effect in it by construction.
    """
    print("\nH34  positive control: plant an away travel deficit, try to recover it")
    print(f"     plant is 1 - p*(d/{REFERENCE_KM:.0f}km) on the away attack, "
          f"p = {PLANT_PCT:.1%} x scale")

    d_ref = f.distance.to_numpy(float) / REFERENCE_KM
    lam_h, lam_a = f.lam_h.to_numpy(float), f.lam_a.to_numpy(float)

    rows = [_one_scale(f, lam_h, lam_a, d_ref, scale, seeds) for scale in PLANT_SCALES]
    for row in rows:
        c = row["coefficient"]
        print(f"  x{row['planted_x']:<4} ({row['deficit_pct_at_500km']:4.1f}% at 500km)"
              f"  coef b {c['beta']:+.4f}  t {c['t']:5.2f}  detected {c['detected']}"
              f"   |  deviance A1 {row[ARM_SLOPE]['delta']:+.5f}"
              f" ({row[ARM_SLOPE]['detected']})"
              f"  A2 {row[ARM_BANDS]['delta']:+.5f} ({row[ARM_BANDS]['detected']})")

    specified = rows[PLANT_AS_SPECIFIED]
    primary = specified["coefficient"]
    threshold = (100 * PLANT_PCT * 1.96 / primary["t"]) if primary["t"] else float("inf")
    detected = int(primary["detected"].split("/")[0])
    passed = detected >= 4

    print(f"\n  coefficient test recovers the {100 * PLANT_PCT:.0f}% plant "
          f"{primary['detected']} at t = {primary['t']:.2f}")
    print(f"  estimate {primary['beta']:+.4f} against a planted {-PLANT_PCT:+.4f} "
          f"({seeds} draws -- see slope_coefficient on bias)")
    print(f"  false positives at x0: {rows[0]['coefficient']['detected']}")
    print(f"  1.96-SE resolution threshold: {threshold:.1f}% deficit at 500 km, "
          f"{threshold * f.distance.median() / REFERENCE_KM:.1f}% at the median "
          f"{f.distance.median():.0f} km trip, on n={len(f):,}")
    print(f"  overfit cost at x0 -- A1 {rows[0][ARM_SLOPE]['delta']:+.5f}, "
          f"A2 {rows[0][ARM_BANDS]['delta']:+.5f}")
    print(f"\n  STOP CONDITION: {'PASSED' if passed else 'FAILED'} "
          f"({detected}/{seeds}, plan requires >=4/6)")
    if not passed:
        print("  The real arms must NOT run. This is the kickoff-slot outcome:\n"
              "  a question the corpus cannot resolve, not a null.")

    out = {"curve": rows, "n": len(f), "threshold_pct_at_500km": float(threshold),
           "statistic": "poisson score coefficient (plan section 8)",
           "stop_condition_passed": bool(passed),
           "detected_at_specified": primary["detected"]}
    _log(conn, ledger.PROBE, "h34_travel_power", out,
         "The positive control, run before any arm touched real outcomes, per "
         "docs/P4_TRAVEL_PLAN.md sections 5 and 8. Plants an away attacking "
         "deficit linear in distance into Poisson-resampled goals. The stop "
         "condition runs on the Poisson score coefficient after the first run "
         "showed the deviance delta missed a planted effect it was shown to "
         "contain (0/6 at 5%); the deviance figures are retained here because "
         "adoption still turns on them. This is the second recorded run of this "
         "probe and both stand, per section 7.5.")
    return out


# --- H36: the real arms ------------------------------------------------------


def _per_division(f, lam_h, lam_a, base) -> list[dict]:
    """A1's delta inside each served division. Fitted globally, scored locally.

    The plan's §7 rule needs the sign to hold in at least three of four, so the
    arm is fitted once on the whole frame and then evaluated on each division's
    rows. Re-fitting per division would answer a different question and would
    spend four times the degrees of freedom to do it.
    """
    arm_loss = metrics.goal_deviance(pd.DataFrame({
        "lam_h": lam_h, "lam_a": lam_a, "fthg": f.fthg, "ftag": f.ftag}))
    rows = []
    for division in sorted(f.division.unique()):
        mask = (f.division == division).to_numpy()
        cmp = bootstrap.paired(arm_loss[mask], base[mask],
                               bootstrap.week_blocks(f.match_date[mask]))
        rows.append({"division": division, "n": int(mask.sum()),
                     **cmp.as_dict()})
    return rows


def h36_arms(conn, f: pd.DataFrame) -> dict:
    """The pre-registered arms, on real outcomes. This spends the dev set."""
    print("\nH36  the real arms -- A1 (one slope) and A2 (five bands)")
    d_ref = f.distance.to_numpy(float) / REFERENCE_KM
    base = metrics.goal_deviance(f)

    beta, se = slope_coefficient(f.ftag, f.lam_a, d_ref)
    t = abs(beta) / se
    print("\n  resolution statistic (score test on the away rate)")
    print(f"    beta {beta:+.4f}  se {se:.4f}  t {t:.2f}  "
          f"{'RESOLVED' if t > 1.96 else 'not resolved'}")
    print(f"    reads as a {-100 * beta:+.2f}% change in away scoring per 500 km")

    out = {"coefficient": {"beta": beta, "stderr": se, "t": t,
                           "resolved": bool(t > 1.96)}}

    print("\n  adoption statistic (goal Poisson deviance, positive = worse)")
    arms = {}
    for name, arm in ((ARM_SLOPE, slope_arm), (ARM_BANDS, band_arm)):
        lam_h, lam_a = arm(f)
        cmp = _delta(f, lam_h, lam_a, base)
        arms[name] = cmp.as_dict()
        print(f"    {name:9s} {cmp.delta:+.5f} [{cmp.ci[0]:+.5f}, {cmp.ci[1]:+.5f}]"
              f"  {abs(cmp.delta) / cmp.stderr:4.1f} SE")
        if name == ARM_SLOPE:
            arms[name]["by_division"] = _per_division(f, lam_h, lam_a, base)
    out["arms"] = arms

    print("\n  A1 by division")
    negative = 0
    for row in arms[ARM_SLOPE]["by_division"]:
        negative += row["delta"] < 0
        print(f"    {row['division']}  n={row['n']:6,}  {row['delta']:+.5f} "
              f"[{row['ci_low']:+.5f}, {row['ci_high']:+.5f}]")

    y = metrics.over_outcome(f)
    p0, _ = metrics.over_under_probs(
        metrics.score_matrix(f.lam_h.to_numpy(float), f.lam_a.to_numpy(float)))
    p1, _ = metrics.over_under_probs(metrics.score_matrix(*slope_arm(f)))
    ou = bootstrap.paired(metrics.logloss_binary(p1, y),
                          metrics.logloss_binary(p0, y),
                          bootstrap.week_blocks(f.match_date))
    out["ou_a1"] = ou.as_dict()
    print("\n  O/U 2.5 log-loss (reported, never selected on)")
    print(f"    {ARM_SLOPE:9s} {ou.delta:+.5f} [{ou.ci[0]:+.5f}, {ou.ci[1]:+.5f}]")

    primary = arms[ARM_SLOPE]
    improves = primary["delta"] < 0 and primary["ci_high"] < 0
    adopt = improves and negative >= 3
    out["decision"] = {"adopt": bool(adopt), "divisions_negative": int(negative),
                       "interval_excludes_zero": bool(primary["ci_high"] < 0)}
    print(f"\n  DECISION (plan section 7): {'ADOPT' if adopt else 'DO NOT ADOPT'}")
    print(f"    A1 interval excludes zero: {primary['ci_high'] < 0}   "
          f"negative in {negative}/4 divisions   (rule needs both, >=3/4)")

    _log(conn, ledger.GATE, "h36_travel_arms", out,
         "The pre-registered arms on real outcomes, per docs/P4_TRAVEL_PLAN.md "
         "sections 4 and 7, run only after the section 5 control passed at 5/6. "
         "Both statistics are reported: the score coefficient answers whether "
         "the corpus can see an effect, goal Poisson deviance decides adoption "
         "(convention 2). A1 is fitted once and scored per division; the rule "
         "needs an interval excluding zero and the sign holding in 3 of 4.")
    return out


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", default="control",
                        choices=["control", "arms", "all"])
    parser.add_argument("--seeds", type=int, default=6)
    parser.add_argument("--out", default="docs/travel_results.json")
    args = parser.parse_args(argv)

    conn = db.connect()
    f = load(conn)
    print(f"{len(f):,} scored matches, all with a travel distance")
    print(f"seasons: {', '.join(sorted(f.season.unique()))}")
    print(f"distance km: median {f.distance.median():.0f}  "
          f"p10 {f.distance.quantile(0.1):.0f}  p90 {f.distance.quantile(0.9):.0f}  "
          f"max {f.distance.max():.0f}")

    results = {}
    if args.stage in ("control", "all"):
        results["h34"] = h34_power(conn, f, seeds=args.seeds)

    if args.stage in ("arms", "all"):
        # The plan's stop condition is enforced here, not trusted to a reader.
        # `--stage arms` on its own re-reads the recorded control rather than
        # re-running it, so the gate cannot be reached by skipping the check.
        passed = results.get("h34", {}).get("stop_condition_passed")
        if passed is None:
            passed = ledger.last_detail(conn, "h34_travel_power") \
                .get("stop_condition_passed", False)
        if not passed:
            print("\nREFUSING to run the arms: the section 5 control has not "
                  "passed. Run --stage control first.")
            return 1
        results["h36"] = h36_arms(conn, f)

    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(results, handle, indent=2, default=str)
    print(f"\nwrote {args.out}")
    if "h34" in results and not results["h34"]["stop_condition_passed"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
