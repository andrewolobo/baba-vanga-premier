"""P4-TOD: is there a kickoff-slot effect, or is it fixture composition?

    python -m engine.eval.tod --stage all

SPEC 3.6 asks for gtleague's proof method with the feature replaced: subtract
per-team expectation, then test the residual by slot. If it survives it is a
slot effect; if not it was composition.

The answer here is neither of those. A slot effect does survive the residual
test -- and survives a control the source doc did not have, the frozen head's
opponent-adjusted lambda -- but it lands in slots holding 5% of the corpus, and
H29 shows this corpus cannot resolve an effect of that size on goal deviance.
The result is an underpowered instrument, not a measured null, and H29 is what
distinguishes the two (OUTSTANDING.md 7.8).

`Time` is absent before 2019-20, so every measurement here runs on 5,644
matches rather than the 21,896 the rest of the project scores on.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import replace

import numpy as np
import pandas as pd
from scipy import stats

from engine import db, ledger, store
from engine.eval import bootstrap, metrics
from engine.eval.p1 import BASE, served
from engine.eval.walkforward import walk_forward
from engine.seasons import DEV_SEASONS, SERVED_DIVISIONS

#: The adopted head in measurement form -- COVID embargoed from scoring.
HEAD = replace(BASE, half_life=400.0, alpha=0.1, shots_blend=0.3,
               embargo_regimes=("covid_empty_stadiums",))

#: Effect sizes for the planted control, as multiples of the size H26 measured.
PLANT_SCALES = (0.0, 0.5, 1.0, 1.5, 2.0, 3.0)

#: Index into PLANT_SCALES of the multiple that reproduces the measured effect.
#: The sample-size arithmetic keys off this row, so it is named rather than
#: recovered by comparing floats.
PLANT_AS_MEASURED = 2

#: The slot factors H26 found, planted by H29 to test whether they are findable.
PLANTED = {"sun_late": 0.18, "sat_late": -0.14, "holiday_15": 0.06}


def slot_of(day_name: str, kickoff: str) -> str:
    """One categorical over weekday and kickoff hour (SPEC 2.4).

    Weekday 15:00 is its own level rather than part of the evening slots: every
    such date in the corpus is a public holiday (Boxing Day, New Year, Good
    Friday, Easter Monday, the May and coronation bank holidays), which is a
    full fixture round and not a broadcast pick.
    """
    hour = int(kickoff[:2]) + int(kickoff[3:]) / 60.0
    if day_name in ("Mon", "Tue", "Wed", "Thu", "Fri") and 14.5 <= hour < 16.0:
        return "holiday_15"
    if day_name == "Sat":
        if hour < 14.0:
            return "sat_early"
        return "sat_15" if hour < 16.0 else "sat_late"
    if day_name == "Sun":
        return "sun_early" if hour < 14.5 else "sun_late"
    return {"Fri": "fri_eve", "Mon": "mon_eve"}.get(day_name, "midweek_eve")


def load(conn) -> tuple[pd.DataFrame, int]:
    """Scored matches that carry a kickoff time, and how many were scored.

    The head is fitted on the whole dev corpus and only *scored* on the seasons
    with a `Time` column, so the strength estimates behind these residuals have
    the same history behind them as every other measurement.
    """
    frame = store.read_matches(conn, seasons=DEV_SEASONS).for_measurement()
    scored = served(walk_forward(frame, HEAD))
    f = scored[scored["kickoff_time"].notna()].copy()
    dow = f["match_date"].dt.day_name().str[:3]
    f["slot"] = [slot_of(d, t) for d, t in zip(dow, f["kickoff_time"])]
    f["total"] = f["fthg"] + f["ftag"]
    f["expected"] = f["lam_h"] + f["lam_a"]
    f["resid"] = f["total"] - f["expected"]
    return f.reset_index(drop=True), len(scored)


def _log(conn, kind, name, detail, reason):
    ledger.record(conn, kind=kind, name=name, purpose="dev", seasons=DEV_SEASONS,
                  divisions=SERVED_DIVISIONS, detail=detail, reason=reason)
    print(f"  [ledger] {kind}:{name}")


def _mean_ci(values, dates, alpha: float = 0.05):
    values = np.asarray(values, dtype=float)
    return bootstrap.paired(values, np.zeros_like(values),
                            bootstrap.week_blocks(dates), alpha=alpha)


def _team_expectation(f: pd.DataFrame) -> pd.Series:
    """gtleague's control: per-team mean, home and away kept apart.

    Leave-one-out, so a match never contributes to its own expectation; with
    cells this small the self-contribution would shrink the residual toward zero
    exactly where the test is weakest.
    """
    h_sum = f.groupby("home_team").fthg.transform("sum")
    h_cnt = f.groupby("home_team").fthg.transform("count")
    a_sum = f.groupby("away_team").ftag.transform("sum")
    a_cnt = f.groupby("away_team").ftag.transform("count")
    return (h_sum - f.fthg) / (h_cnt - 1) + (a_sum - f.ftag) / (a_cnt - 1)


def _by_slot(f: pd.DataFrame, column: str, alpha: float = 0.05) -> pd.DataFrame:
    rows = []
    for slot, sub in f.groupby("slot"):
        cmp = _mean_ci(sub[column], sub["match_date"], alpha)
        rows.append({"slot": slot, "n": len(sub), "value": cmp.delta,
                     "ci_low": cmp.ci[0], "ci_high": cmp.ci[1],
                     "excludes_zero": cmp.ci[0] > 0 or cmp.ci[1] < 0})
    return pd.DataFrame(rows).sort_values("value").reset_index(drop=True)


def _show(frame: pd.DataFrame) -> None:
    print(frame.to_string(index=False, float_format=lambda v: f"{v:+.4f}"))


# --- H26: the residual test, against two controls --------------------------


def h26_residual(conn, f: pd.DataFrame) -> dict:
    """Raw slot means, then the same means after each control."""
    print("\nH26  slot effect, before and after controlling for composition")

    raw = _by_slot(f, "total")
    print("\n  raw mean total goals by slot")
    _show(raw)
    swing = raw.value.max() - raw.value.min()
    print(f"  swing {raw.value.min():.3f} -> {raw.value.max():.3f} = {swing:.3f} goals")

    ported = f.assign(port_resid=f.total - _team_expectation(f))
    print("\n  residual after per-team expectation (the literal port)")
    port = _by_slot(ported, "port_resid")
    _show(port)

    print("\n  residual after the frozen head's lambda (opponent-adjusted)")
    lam = _by_slot(f, "resid")
    _show(lam)

    groups = [g.resid.to_numpy() for _, g in f.groupby("slot")]
    fstat, pval = stats.f_oneway(*groups)
    print(f"\n  one-way ANOVA on the lambda residual: F={fstat:.3f}  p={pval:.4g}")

    out = {"raw": raw.to_dict("records"), "ported": port.to_dict("records"),
           "lambda": lam.to_dict("records"), "swing": float(swing),
           "anova_f": float(fstat), "anova_p": float(pval), "n": len(f)}
    _log(conn, ledger.PROBE, "h26_tod_slot_residual", out,
         "SPEC 3.6's residual test, run against both gtleague's per-team control "
         "and the stronger lambda control. Per-team means remove marginal team "
         "quality but not matchup, and broadcast selection picks fixtures rather "
         "than teams, so the lambda control is the one that decides it.")
    return out


# --- H27: is the survivor stable, and does the market see it? --------------


def h27_stability(conn, f: pd.DataFrame) -> dict:
    """Per-season signs, a multiplicity correction, and the market's own miss."""
    print("\nH27  stability, multiplicity, and whether the market misses it too")

    print("\n  lambda residual by season")
    rows = []
    for slot, sub in f.groupby("slot"):
        row = {"slot": slot, "n": len(sub)}
        for season, s in sub.groupby("season"):
            row[season] = round(float(s.resid.mean()), 4)
        signs = {np.sign(row[s]) for s in sub.season.unique() if s in row}
        row["signs_agree"] = len(signs) == 1
        rows.append(row)
    season_frame = pd.DataFrame(rows).sort_values("slot")
    print(season_frame.to_string(index=False))

    n_slots = f.slot.nunique()
    alpha = 0.05 / n_slots
    print(f"\n  {n_slots} slots were tested, so intervals at "
          f"{100 * (1 - alpha):.2f}% (Bonferroni)")
    corrected = _by_slot(f, "resid", alpha=alpha)
    _show(corrected)
    survivors = corrected[corrected.excludes_zero].slot.tolist()
    print(f"  survives correction: {survivors or 'none'}")

    obs = stats.f_oneway(*[g.resid.to_numpy() for _, g in f.groupby("slot")])[0]
    rng = np.random.default_rng(0)
    reps, hits = 2000, 0
    for _ in range(reps):
        perm = f.groupby("season", group_keys=False).slot.apply(
            lambda s: pd.Series(rng.permutation(s.to_numpy()), index=s.index))
        hits += stats.f_oneway(
            *[g.to_numpy() for _, g in f.resid.groupby(perm)])[0] >= obs
    perm_p = (hits + 1) / (reps + 1)
    print(f"  permutation p {perm_p:.4f} ({reps} shuffles within season)")

    priced = f.dropna(subset=["avg_over25", "avg_under25"]).copy()
    p_over, _ = metrics.devig_probs(priced.avg_over25, priced.avg_under25)
    priced["mkt_resid"] = metrics.over_outcome(priced) - p_over
    print(f"\n  the market's own residual, same slots (n={len(priced):,})")
    mkt = _by_slot(priced, "mkt_resid")
    _show(mkt)

    out = {"per_season": season_frame.to_dict("records"),
           "corrected": corrected.to_dict("records"), "survivors": survivors,
           "permutation_p": float(perm_p), "market": mkt.to_dict("records")}
    _log(conn, ledger.PROBE, "h27_tod_slot_stability", out,
         "Nine slots were tested and the survivors were chosen after seeing the "
         "data, so the uncorrected intervals in H26 overstate the case. The "
         "market residual is reported because a slot the book also misprices is "
         "the only version of this finding that could ever be worth money.")
    return out


# --- H28: what it is worth on the selection metric -------------------------


def slot_arm(f: pd.DataFrame, slots: set[str] | None = None):
    """Leave-one-season-out multiplicative slot factors applied to lambda.

    Factors are fitted on the other seasons and applied to the held-out one, so
    this is what the feature would have been worth served rather than the
    in-sample fit, which cannot lose. `slots` pins every other level at 1.0.
    """
    lam_h = f.lam_h.to_numpy(dtype=float)
    lam_a = f.lam_a.to_numpy(dtype=float)
    out_h, out_a = lam_h.copy(), lam_a.copy()
    for season in sorted(f.season.unique()):
        train = f[f.season != season]
        factor = (train.groupby("slot").total.sum()
                  / train.groupby("slot").expected.sum())
        if slots is not None:
            factor = factor.where(factor.index.isin(slots), 1.0)
        idx = (f.season == season).to_numpy()
        mult = f.loc[idx, "slot"].map(factor).fillna(1.0).to_numpy()
        out_h[idx] = lam_h[idx] * mult
        out_a[idx] = lam_a[idx] * mult
    return out_h, out_a


def _deviance_delta(f, lam_h, lam_a, base):
    arm = metrics.goal_deviance(pd.DataFrame({
        "lam_h": lam_h, "lam_a": lam_a,
        "fthg": f.fthg.to_numpy(), "ftag": f.ftag.to_numpy()}))
    return bootstrap.paired(arm, base, bootstrap.week_blocks(f.match_date))


def h28_deviance(conn, f: pd.DataFrame) -> dict:
    """Goal deviance, plus O/U 2.5 reported alongside (convention 7.2)."""
    print("\nH28  what a slot term is worth on goal Poisson deviance")
    base = metrics.goal_deviance(f)
    arms = {"all slots": None, "sun_late + sat_late": {"sun_late", "sat_late"},
            "sun_late only": {"sun_late"}}

    out = {}
    for label, slots in arms.items():
        cmp = _deviance_delta(f, *slot_arm(f, slots), base)
        out[label] = cmp.as_dict()
        print(f"  {label:22s} {cmp.delta:+.5f} [{cmp.ci[0]:+.5f}, "
              f"{cmp.ci[1]:+.5f}]  {abs(cmp.delta) / cmp.stderr:.1f} SE")

    print("\n  O/U 2.5 log-loss (reported, never selected on)")
    y = metrics.over_outcome(f)
    p0, _ = metrics.over_under_probs(
        metrics.score_matrix(f.lam_h.to_numpy(), f.lam_a.to_numpy()))
    ll0 = metrics.logloss_binary(p0, y)
    for label, slots in arms.items():
        h, a = slot_arm(f, slots)
        p, _ = metrics.over_under_probs(metrics.score_matrix(h, a))
        cmp = bootstrap.paired(metrics.logloss_binary(p, y), ll0,
                               bootstrap.week_blocks(f.match_date))
        out[f"ou_{label}"] = cmp.as_dict()
        print(f"  {label:22s} {cmp.delta:+.5f} [{cmp.ci[0]:+.5f}, "
              f"{cmp.ci[1]:+.5f}]  {abs(cmp.delta) / cmp.stderr:.1f} SE")

    _log(conn, ledger.GATE, "h28_tod_slot_deviance", out,
         "The decision metric. A slot term fitted leave-one-season-out and "
         "scored on goal deviance. Restricted arms are post-hoc -- the two "
         "slots were chosen after H26 -- and are reported as such.")
    return out


# --- H29: the positive control, and the power it implies -------------------


def h29_power(conn, f: pd.DataFrame, seeds: int = 6) -> dict:
    """Plant a slot effect of known size and ask whether H28 recovers it.

    H28 returned an interval containing zero. That is only a null if the
    instrument could have seen an effect this size, and this is the arm that
    decides which of the two it is.
    """
    print("\nH29  positive control: plant a known slot effect, try to recover it")
    print(f"  goals redrawn from the head's lambda times a slot factor, "
          f"{seeds} seeds per point")
    rows, measured = [], None
    for position, scale in enumerate(PLANT_SCALES):
        deltas, errs, hits = [], [], 0
        for seed in range(seeds):
            rng = np.random.default_rng(1000 + seed)
            work = f.copy()
            mult = work.slot.map(
                {k: 1.0 + v * scale for k, v in PLANTED.items()}).fillna(1.0)
            work["fthg"] = rng.poisson(work.lam_h.to_numpy() * mult.to_numpy())
            work["ftag"] = rng.poisson(work.lam_a.to_numpy() * mult.to_numpy())
            work["total"] = work.fthg + work.ftag
            base = metrics.goal_deviance(work)
            cmp = _deviance_delta(work, *slot_arm(work), base)
            deltas.append(cmp.delta)
            errs.append(cmp.stderr)
            hits += cmp.delta < 0 and abs(cmp.delta) / cmp.stderr > 1.96
        delta, err = float(np.mean(deltas)), float(np.mean(errs))
        row = {"planted_x": scale, "delta": delta, "stderr": err,
               "se_ratio": abs(delta) / err, "detected": f"{hits}/{seeds}"}
        rows.append(row)
        if position == PLANT_AS_MEASURED:
            measured = row
        print(f"  planted x{scale:<4} {delta:+.5f}  se {err:.5f}  "
              f"{abs(delta) / err:4.1f} SE  detected {hits}/{seeds}")

    needed = (1.96 * measured["stderr"] / abs(measured["delta"])) ** 2 * len(f)
    per_season = len(f) / 2.6  # 2019-20 truncated by COVID, plus 21-22 and 22-23
    print(f"\n  at the size actually present: {measured['se_ratio']:.1f} SE "
          f"on n={len(f):,}")
    print(f"  n needed for 1.96 SE: {needed:,.0f} ({needed / len(f):.1f}x), "
          f"about {(needed - len(f)) / per_season:.0f} further seasons")
    reach = len(f) + 3 * per_season
    print(f"  unsealing the entire holdout reaches n={reach:,.0f} = "
          f"{measured['se_ratio'] * np.sqrt(reach / len(f)):.1f} SE -- still short")

    out = {"curve": rows, "n": len(f), "n_required": float(needed),
           "seasons_required": float((needed - len(f)) / per_season),
           "holdout_would_reach": float(
               measured["se_ratio"] * np.sqrt(reach / len(f)))}
    _log(conn, ledger.PROBE, "h29_tod_slot_power", out,
         "The control that makes H28 interpretable. At the effect size actually "
         "present the arm detects it in a minority of draws, so H28 is an "
         "underpowered instrument and not a measured null. The x0 row also "
         "prices the overfit cost of a nine-level term fitted to noise.")
    return out


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", default="all",
                        choices=["all", "h26", "h27", "h28", "h29"])
    parser.add_argument("--seeds", type=int, default=6,
                        help="draws per point on the H29 power curve")
    parser.add_argument("--out", default="docs/tod_slot_results.json")
    args = parser.parse_args(argv)

    conn = db.connect()
    f, n_scored = load(conn)
    print(f"{len(f):,} of {n_scored:,} scored matches carry a kickoff time "
          f"({100 * len(f) / n_scored:.1f}%)")
    print(f"seasons: {', '.join(sorted(f.season.unique()))}")

    results = {}
    if args.stage in ("all", "h26"):
        results["h26"] = h26_residual(conn, f)
    if args.stage in ("all", "h27"):
        results["h27"] = h27_stability(conn, f)
    if args.stage in ("all", "h28"):
        results["h28"] = h28_deviance(conn, f)
    if args.stage in ("all", "h29"):
        results["h29"] = h29_power(conn, f, seeds=args.seeds)

    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(results, handle, indent=2, default=str)
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
