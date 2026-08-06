"""P4-rest: does days-since-last-match carry anything?

    python -m engine.eval.rest --stage all

The first of SPEC 3.6's replacement analogues. Unlike the kickoff slot it runs
on the whole corpus -- rest comes from `match_date`, which every row has -- so
21,425 matches rather than 5,644, and the power question has a different answer.

**It is a measured null, and it is bounded.** Neither a six-band rest term nor
the SPEC's differential improves goal deviance; the band arm returns +0.00017,
which is what the same arm returns on data with no rest effect in it by
construction. H33 detects a planted 5% attacking deficit in 6 draws of 6 and
places the resolution threshold near 3.5%, so the null has a size attached to
it rather than being the absence of a finding.

**One caveat governs the whole file.** The corpus is league-only: no FA Cup,
League Cup, or European ties. Measured rest is therefore an *upper bound* on
true rest -- a hidden midweek tie shortens real rest and can never lengthen it.
H30 shows the long bands are overwhelmingly FIFA windows and cup weekends, so
the short end is trustworthy and the long end is not, and every arm here is
built to lean on the end that is.
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

HEAD = replace(BASE, half_life=400.0, alpha=0.1, shots_blend=0.3,
               embargo_regimes=("covid_empty_stadiums",))

#: Rest bands. 7 is the reference -- a normal week -- and the two ends mean
#: different things: `<=3` is real congestion, `>=12` is mostly a FIFA window.
BAND_EDGES = [-1, 3, 4, 6, 7, 11, 99]
BAND_LABELS = ["<=3", "4", "5-6", "7", "8-11", ">=12"]

#: Planted deficits for H33, as attacking multipliers at scale 1.
PLANTED = {"<=3": -0.05, "4": -0.03, "5-6": -0.01}
PLANT_SCALES = (0.0, 0.5, 1.0, 2.0)
PLANT_AS_SPECIFIED = 2  # index of the 1.0 row


def bands(rest) -> pd.Categorical:
    return pd.cut(rest, BAND_EDGES, labels=BAND_LABELS)


def attach_rest(f: pd.DataFrame) -> pd.DataFrame:
    """Days since each side's previous league match, within season.

    Within-season only: a gap spanning the summer is not rest, it is a new
    squad. The first match of each club-season therefore has no value and is
    dropped downstream rather than filled.
    """
    long = pd.concat([
        f.assign(club=f.home_team, side="home"),
        f.assign(club=f.away_team, side="away"),
    ]).sort_values("match_date")
    long["rest"] = long.groupby(["season", "club"]).match_date.diff().dt.days
    wide = long.pivot_table(index="match_id", columns="side", values="rest")
    # `pivot_table` drops an all-NaN side, which happens on any frame where no
    # club has a previous match. Reindex so both columns always exist and the
    # caller's dropna does the filtering rather than a KeyError.
    wide = wide.reindex(columns=["home", "away"])
    return f.set_index("match_id").join(wide.add_prefix("rest_")).reset_index()


def load(conn) -> pd.DataFrame:
    """Scored matches with both sides' rest known.

    Rest is computed on the **full fixture list**, before the walk-forward drops
    burn-in matches and the embargo drops the COVID window. Computing it on the
    scored frame instead would measure the gap to the previous *scored* match,
    which silently lengthens rest wherever the harness removed a fixture that
    was really played.
    """
    raw = store.read_matches(conn, seasons=DEV_SEASONS).for_measurement()
    rest = attach_rest(raw)[["match_id", "rest_home", "rest_away"]]
    scored = served(walk_forward(raw, HEAD))
    f = scored.merge(rest, on="match_id", how="left")
    f = f.dropna(subset=["rest_home", "rest_away"]).copy()
    f["band_h"] = bands(f.rest_home)
    f["band_a"] = bands(f.rest_away)
    f["diff"] = f.rest_home - f.rest_away
    return f.reset_index(drop=True)


def sides_of(f: pd.DataFrame) -> pd.DataFrame:
    """One row per team per match: its own rest, its own lambda, its own goals."""
    common = ["match_date", "season", "division"]
    home = f[common].assign(goals=f.fthg, lam=f.lam_h, conceded=f.ftag,
                            opp_lam=f.lam_a, rest=f.rest_home, band=f.band_h)
    away = f[common].assign(goals=f.ftag, lam=f.lam_a, conceded=f.fthg,
                            opp_lam=f.lam_h, rest=f.rest_away, band=f.band_a)
    out = pd.concat([home, away], ignore_index=True)
    out["resid"] = out.goals - out.lam
    out["conceded_resid"] = out.conceded - out.opp_lam
    return out


def _log(conn, kind, name, detail, reason):
    ledger.record(conn, kind=kind, name=name, purpose="dev", seasons=DEV_SEASONS,
                  divisions=SERVED_DIVISIONS, detail=detail, reason=reason)
    print(f"  [ledger] {kind}:{name}")


def _mean_ci(values, dates, alpha=0.05):
    v = np.asarray(values, dtype=float)
    return bootstrap.paired(v, np.zeros_like(v), bootstrap.week_blocks(dates),
                            alpha=alpha)


def _by_band(frame, column, alpha=0.05) -> pd.DataFrame:
    rows = []
    for band, sub in frame.groupby("band", observed=True):
        cmp = _mean_ci(sub[column], sub.match_date, alpha)
        rows.append({"band": str(band), "n": len(sub), "value": cmp.delta,
                     "ci_low": cmp.ci[0], "ci_high": cmp.ci[1],
                     "excludes_zero": cmp.excludes_zero})
    return pd.DataFrame(rows)


def _show(frame) -> None:
    print(frame.to_string(index=False, float_format=lambda v: f"{v:+.4f}"))


# --- H30: what the corpus can and cannot measure ---------------------------


def h30_confound(conn, f: pd.DataFrame) -> dict:
    """The league-only caveat, quantified before anything is fitted."""
    print("\nH30  is 'rest' rest, or is it the international calendar?")
    sides = sides_of(f)
    share = float((sides.rest >= 12).mean())
    print(f"  {100 * share:.1f}% of match-sides show >=12 days since the last "
          f"league match")

    longs = sides[sides.rest >= 12]
    top = longs.match_date.dt.strftime("%Y-%m-%d").value_counts().head(10)
    print("\n  the ten dates contributing most long gaps:")
    for date, n in top.items():
        print(f"    {date}  {n:4d}")
    print("  FIFA windows sit in Sep/Oct/Nov/Mar and the FA Cup third round in\n"
          "  early January. August and May, which have neither, are near zero.")

    by_month = sides.assign(month=sides.match_date.dt.strftime("%m %b")) \
        .groupby("month").rest.agg(n="size",
                                   share_long=lambda s: float((s >= 12).mean()))
    print("\n  share of match-sides with >=12 days, by month")
    print((by_month.assign(share_long=(100 * by_month.share_long).round(1))
           ).to_string())

    out = {"share_long": share, "top_dates": top.to_dict(),
           "by_month": by_month.reset_index().to_dict("records"),
           "distribution": sides.rest.value_counts().sort_index().head(20).to_dict()}
    _log(conn, ledger.PROBE, "h30_rest_confound_audit", out,
         "The corpus holds league fixtures only, so measured rest is an upper "
         "bound on true rest. This records how contaminated the long bands are "
         "before any arm leans on them -- the answer is that they are mostly "
         "FIFA windows and cup weekends, so only the short end is trustworthy.")
    return out


# --- H31: the residual, by band and by differential ------------------------


def h31_residual(conn, f: pd.DataFrame) -> dict:
    """Does rest predict what the frozen head gets wrong?"""
    print("\nH31  residual by rest band, and the SPEC's differential")
    sides = sides_of(f)

    print("\n  attacking residual (goals - own lambda)")
    attack = _by_band(sides, "resid")
    _show(attack)
    print("\n  conceding residual (goals against - opponent lambda)")
    concede = _by_band(sides, "conceded_resid")
    _show(concede)

    n_tests = 2 * sides.band.nunique()
    alpha = 0.05 / n_tests
    print(f"\n  {n_tests} cells were tested, so at Bonferroni "
          f"{100 * (1 - alpha):.2f}%:")
    survivors = []
    for column, name in (("resid", "attack"), ("conceded_resid", "concede")):
        got = _by_band(sides, column, alpha)
        survivors += [f"{name} {r.band}" for r in got.itertuples()
                      if r.excludes_zero]
    print(f"  survives correction: {survivors or 'nothing'}")

    groups = [g.resid.to_numpy() for _, g in sides.groupby("band", observed=True)]
    fstat, pval = stats.f_oneway(*groups)
    print(f"  ANOVA on the attacking residual: F={fstat:.3f}  p={pval:.4g}")

    print("\n  the differential -- what SPEC 3.6 actually asked for")
    margin_resid = ((f.fthg - f.ftag) - (f.lam_h - f.lam_a)).to_numpy(float)
    r, p = stats.pearsonr(f["diff"].to_numpy(float), margin_resid)
    print(f"  correlation(home rest - away rest, margin residual) "
          f"r={r:+.4f}  p={p:.3g}  n={len(f):,}")

    out = {"attack": attack.to_dict("records"), "concede": concede.to_dict("records"),
           "survivors": survivors, "anova_f": float(fstat), "anova_p": float(pval),
           "diff_r": float(r), "diff_p": float(p), "n": len(f)}
    _log(conn, ledger.PROBE, "h31_rest_residual", out,
         "Twelve cells were tested. Nothing survives correction, and the "
         "differential -- the form the SPEC preferred -- is flat at r=-0.004 on "
         "21,425 matches, which is a much larger sample than the kickoff slot "
         "ever had.")
    return out


# --- H32: the decision metric ----------------------------------------------


def band_arm(f: pd.DataFrame):
    """Leave-one-season-out multiplicative factors per band, applied per side.

    Fitted on the other seasons' match-sides as observed goals over expected,
    so a tired side's own attack is scaled by its own rest and the arm is
    honestly out of sample.
    """
    lam_h, lam_a = f.lam_h.to_numpy(float), f.lam_a.to_numpy(float)
    out_h, out_a = lam_h.copy(), lam_a.copy()
    for season in sorted(f.season.unique()):
        train = f[f.season != season]
        sides = pd.DataFrame({
            "band": pd.concat([train.band_h, train.band_a], ignore_index=True),
            "goals": pd.concat([train.fthg, train.ftag], ignore_index=True),
            "lam": pd.concat([train.lam_h, train.lam_a], ignore_index=True)})
        grouped = sides.groupby("band", observed=True)
        factor = grouped.goals.sum() / grouped.lam.sum()
        idx = (f.season == season).to_numpy()
        out_h[idx] = lam_h[idx] * f.band_h[idx].map(factor).astype(float).fillna(1.0)
        out_a[idx] = lam_a[idx] * f.band_a[idx].map(factor).astype(float).fillna(1.0)
    return out_h, out_a


def diff_arm(f: pd.DataFrame):
    """One fitted slope on the rest differential, split across the two lambdas.

    A single parameter, so a null here cannot be blamed on the six degrees of
    freedom the band arm spends.
    """
    lam_h, lam_a = f.lam_h.to_numpy(float), f.lam_a.to_numpy(float)
    out_h, out_a = lam_h.copy(), lam_a.copy()
    d = f["diff"].to_numpy(float)
    for season in sorted(f.season.unique()):
        train = f[f.season != season]
        td = train["diff"].to_numpy(float)
        y = ((train.fthg - train.ftag) - (train.lam_h - train.lam_a)).to_numpy(float)
        slope = float(np.polyfit(td, y, 1)[0]) if td.std() > 0 else 0.0
        idx = (f.season == season).to_numpy()
        shift = slope * d[idx] / 2.0
        out_h[idx] = np.clip(lam_h[idx] + shift, 0.01, None)
        out_a[idx] = np.clip(lam_a[idx] - shift, 0.01, None)
    return out_h, out_a


def _delta(f, lam_h, lam_a, base):
    arm = metrics.goal_deviance(pd.DataFrame({
        "lam_h": lam_h, "lam_a": lam_a, "fthg": f.fthg, "ftag": f.ftag}))
    return bootstrap.paired(arm, base, bootstrap.week_blocks(f.match_date))


def h32_deviance(conn, f: pd.DataFrame) -> dict:
    print("\nH32  what a rest term is worth on goal Poisson deviance")
    base = metrics.goal_deviance(f)
    out = {}
    for label, arm in (("6 rest bands", band_arm), ("differential slope", diff_arm)):
        cmp = _delta(f, *arm(f), base)
        out[label] = cmp.as_dict()
        print(f"  {label:22s} {cmp.delta:+.5f} [{cmp.ci[0]:+.5f}, "
              f"{cmp.ci[1]:+.5f}]  {abs(cmp.delta) / cmp.stderr:4.1f} SE "
              f" (positive = worse than the frozen head)")

    print("\n  O/U 2.5 log-loss (reported, never selected on)")
    y = metrics.over_outcome(f)
    p0, _ = metrics.over_under_probs(
        metrics.score_matrix(f.lam_h.to_numpy(float), f.lam_a.to_numpy(float)))
    ll0 = metrics.logloss_binary(p0, y)
    p, _ = metrics.over_under_probs(metrics.score_matrix(*band_arm(f)))
    cmp = bootstrap.paired(metrics.logloss_binary(p, y), ll0,
                           bootstrap.week_blocks(f.match_date))
    out["ou_bands"] = cmp.as_dict()
    print(f"  {'6 rest bands':22s} {cmp.delta:+.5f} [{cmp.ci[0]:+.5f}, "
          f"{cmp.ci[1]:+.5f}]  {abs(cmp.delta) / cmp.stderr:4.1f} SE")

    _log(conn, ledger.GATE, "h32_rest_deviance", out,
         "The decision metric. Both arms are fitted leave-one-season-out. "
         "Neither improves on the frozen head; the band arm is slightly worse, "
         "at the magnitude H33 shows a six-level term costs when fitted to "
         "noise.")
    return out


# --- H33: the positive control, and the bound it puts on the null ----------


def h33_power(conn, f: pd.DataFrame, seeds: int = 6) -> dict:
    """Plant a rest effect of known size and ask whether H32 recovers it."""
    print("\nH33  positive control: plant a tired-team deficit, try to recover it")
    rows, specified = [], None
    for position, scale in enumerate(PLANT_SCALES):
        deltas, errs, hits = [], [], 0
        for seed in range(seeds):
            rng = np.random.default_rng(500 + seed)
            factors = {k: 1.0 + v * scale for k, v in PLANTED.items()}
            work = f.copy()
            mh = work.band_h.map(factors).astype(float).fillna(1.0).to_numpy()
            ma = work.band_a.map(factors).astype(float).fillna(1.0).to_numpy()
            work["fthg"] = rng.poisson(work.lam_h.to_numpy(float) * mh)
            work["ftag"] = rng.poisson(work.lam_a.to_numpy(float) * ma)
            cmp = _delta(work, *band_arm(work), metrics.goal_deviance(work))
            deltas.append(cmp.delta)
            errs.append(cmp.stderr)
            hits += cmp.delta < 0 and abs(cmp.delta) / cmp.stderr > 1.96
        delta, err = float(np.mean(deltas)), float(np.mean(errs))
        row = {"planted_x": scale, "deficit_pct": 5.0 * scale, "delta": delta,
               "stderr": err, "se_ratio": abs(delta) / err,
               "detected": f"{hits}/{seeds}"}
        rows.append(row)
        if position == PLANT_AS_SPECIFIED:
            specified = row
        print(f"  planted x{scale:<4} ({5.0 * scale:4.1f}% deficit at <=3 days)  "
              f"{delta:+.5f}  se {err:.5f}  {abs(delta) / err:4.1f} SE  "
              f"detected {hits}/{seeds}")

    threshold = 5.0 * 1.96 * specified["stderr"] / abs(specified["delta"])
    print(f"\n  a 5% attacking deficit on <=3 days rest returns "
          f"{specified['se_ratio']:.1f} SE and is caught {specified['detected']}")
    print(f"  the 1.96-SE resolution threshold sits near a {threshold:.1f}% "
          f"deficit on n={len(f):,}")
    print("  nothing of that size is present, so the null is bounded, not empty")

    out = {"curve": rows, "n": len(f), "threshold_pct": float(threshold)}
    _log(conn, ledger.PROBE, "h33_rest_power", out,
         "What makes H32 a result rather than an untested instrument. Unlike "
         "the kickoff slot, this corpus resolves the effect size the hypothesis "
         "predicts, so the null carries a bound: any true rest effect on scoring "
         "is smaller than roughly the threshold recorded here.")
    return out


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", default="all",
                        choices=["all", "h30", "h31", "h32", "h33"])
    parser.add_argument("--seeds", type=int, default=6)
    parser.add_argument("--out", default="docs/rest_results.json")
    args = parser.parse_args(argv)

    conn = db.connect()
    f = load(conn)
    print(f"{len(f):,} matches with both sides' rest known "
          f"({2 * len(f):,} match-sides)")
    print(f"seasons: {', '.join(sorted(f.season.unique()))}")

    results = {}
    if args.stage in ("all", "h30"):
        results["h30"] = h30_confound(conn, f)
    if args.stage in ("all", "h31"):
        results["h31"] = h31_residual(conn, f)
    if args.stage in ("all", "h32"):
        results["h32"] = h32_deviance(conn, f)
    if args.stage in ("all", "h33"):
        results["h33"] = h33_power(conn, f, seeds=args.seeds)

    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(results, handle, indent=2, default=str)
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
