"""P4-channels pre-gate: is a second in-store channel worth a gate?

    python -m engine.eval.channels --stage all

Runs the measurements pre-registered in `docs/P4_CHANNELS_PREGATE.md`. This is
a pre-gate, not a gate: it selects nothing and never touches the served head.
Its output is a decision about whether a full gate deserves a ledger row.

The row-53 pre-gate that played this role for the shots channel was never
committed, so M4 rebuilds its split-half harness rather than reusing it. Row
53's published cells are a behavioural check, not a reproduction target -- what
M4 needs is a *within-run* contrast, which does not depend on matching them.

One departure from row 53, and it is load-bearing. In-sample multiple R rises
whenever a predictor is added, useless or not, so a third channel would appear
to help by construction. Every reliability figure here is therefore
**leave-one-season-out**, which is the only version of the number that can
answer "does shots add anything to goals+sot".
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
from dataclasses import replace

import numpy as np
import pandas as pd

from engine import db, ledger, store
from engine.eval.p4_shots import HEAD
from engine.eval.walkforward import MIN_SOT_EVIDENCE, _index
from engine.models import poisson as poisson_model
from engine.seasons import DEV_SEASONS, SERVED_DIVISIONS
from engine.eval.walkforward import effective_ages

COVID = (dt.date(2020, 3, 13), dt.date(2021, 5, 31))

#: Channels available in the store, as (per-match "for" column, "against").
CHANNELS = {
    "goals": ("fthg", "ftag"),
    "sot": ("home_sot", "away_sot"),
    "shots": ("home_shots", "away_shots"),
    "corners": ("home_corners", "away_corners"),
}

#: The predictor sets M4 compares. `goals+sot` is what shipped; `goals+shots+sot`
#: is the cell row 53 never measured; `goals+sot+corners` is the placebo.
#:
#: The placebo is load-bearing. Adding any predictor raises in-sample multiple R
#: whether or not it carries information, and leave-one-season-out only bounds
#: that -- it does not prove the third channel is doing work. Corners is a real
#: in-store channel that correlates 0.021 with same-side goals, so if it gains
#: as much as shots does, the instrument is inflating and M4 says nothing.
SETS = (
    ("goals", ("goals",)),
    ("sot", ("sot",)),
    ("shots", ("shots",)),
    ("corners", ("corners",)),
    ("goals+sot", ("goals", "sot")),
    ("shots+sot", ("shots", "sot")),
    ("goals+sot+shots", ("goals", "sot", "shots")),
    ("goals+sot+corners", ("goals", "sot", "corners")),
    ("goals+sot+shots+corners", ("goals", "sot", "shots", "corners")),
    ("goals+sot+NOISE", ("goals", "sot", "noise")),
)

#: Seed for the negative control. Fixed so the recorded number is reproducible.
NOISE_SEED = 20260806


def load(conn) -> pd.DataFrame:
    return store.read_matches(conn, seasons=DEV_SEASONS).for_measurement()


def _log(conn, kind, name, detail, reason):
    ledger.record(conn, kind=kind, name=name, purpose="dev", seasons=DEV_SEASONS,
                  divisions=SERVED_DIVISIONS, detail=detail, reason=reason)
    print(f"  [ledger] {kind}:{name}")


# --- M4: split-half reliability, the cells row 53 left blank ---------------


def _sides(frame: pd.DataFrame) -> pd.DataFrame:
    """One row per team per match: what that team did and had done to it."""
    served = frame[frame["division"].isin(SERVED_DIVISIONS)]
    date = pd.to_datetime(served["match_date"]).dt.date
    served = served[~((date >= COVID[0]) & (date <= COVID[1]))]

    out = []
    for home in (True, False):
        part = pd.DataFrame({
            "season": served["season"].to_numpy(),
            "team": served["home_team" if home else "away_team"].to_numpy(),
            "date": pd.to_datetime(served["match_date"]).to_numpy(),
        })
        for name, (hcol, acol) in CHANNELS.items():
            f_col, a_col = (hcol, acol) if home else (acol, hcol)
            part[f"{name}_for"] = pd.to_numeric(served[f_col], errors="coerce").to_numpy()
            part[f"{name}_against"] = pd.to_numeric(served[a_col], errors="coerce").to_numpy()
        out.append(part)
    sides = pd.concat(out, ignore_index=True).dropna()

    # The negative control, and the reason M4 is interpretable. Adding any
    # predictor can only raise in-sample multiple R, and leave-one-season-out
    # bounds that without proving it is zero. This channel is Poisson noise
    # matched to the corners rate and independent of every match, so whatever
    # it "gains" is the instrument talking rather than the data.
    rng = np.random.default_rng(NOISE_SEED)
    for side in ("for", "against"):
        sides[f"noise_{side}"] = rng.poisson(sides[f"corners_{side}"].mean(), len(sides))
    return sides


def _halves(sides: pd.DataFrame) -> pd.DataFrame:
    """Per team-season, the mean of each channel over odd and over even matches.

    Alternating by date is deterministic -- no seed, so the number does not move
    between runs -- and it splits home and away roughly evenly, which a
    first-half/second-half cut would not.
    """
    sides = sides.sort_values(["season", "team", "date"])
    sides["parity"] = sides.groupby(["season", "team"]).cumcount() % 2
    cols = [c for c in sides.columns if c.endswith(("_for", "_against"))]
    grouped = sides.groupby(["season", "team", "parity"])[cols].agg(["mean", "size"])
    wide = grouped.unstack("parity")
    wide.columns = [f"{c}_{stat}_{p}" for c, stat, p in wide.columns]
    wide = wide.dropna()
    # Both halves need enough matches for a mean to mean anything.
    keep = (wide[f"{cols[0]}_size_0"] >= 8) & (wide[f"{cols[0]}_size_1"] >= 8)
    return wide[keep]


def _loso_r(wide: pd.DataFrame, predictors: tuple[str, ...], target: str) -> float:
    """Leave-one-season-out correlation between prediction and outcome.

    Fitted on half 0, scored on half 1 and vice versa, so every team-season
    contributes both ways and neither half is privileged.
    """
    seasons = wide.index.get_level_values("season").to_numpy()
    preds, actuals = [], []
    for train_half, test_half in ((0, 1), (1, 0)):
        X = np.column_stack([wide[f"{p}_mean_{train_half}"].to_numpy() for p in predictors])
        X = np.column_stack([np.ones(len(X)), X])
        y = wide[f"{target}_mean_{test_half}"].to_numpy()
        for season in np.unique(seasons):
            test = seasons == season
            beta, *_ = np.linalg.lstsq(X[~test], y[~test], rcond=None)
            preds.append(X[test] @ beta)
            actuals.append(y[test])
    p, a = np.concatenate(preds), np.concatenate(actuals)
    return float(np.corrcoef(p, a)[0, 1])


def m4_split_half(frame) -> dict:
    wide = _halves(_sides(frame))
    print(f"\nM4  split-half reliability, leave-one-season-out "
          f"({len(wide):,} team-seasons)")
    out = {"n_team_seasons": int(len(wide)), "r": {}}
    for target, label in (("goals_for", "attack"), ("goals_against", "defence")):
        print(f"  predicting {target} ({label})")
        for name, channels in SETS:
            side = "for" if target == "goals_for" else "against"
            predictors = tuple(f"{c}_{side}" for c in channels)
            r = _loso_r(wide, predictors, target)
            out["r"][f"{name}->{target}"] = round(r, 4)
            print(f"    {name:18s} {r:.4f}")
    base_a = out["r"]["goals+sot->goals_for"]
    base_d = out["r"]["goals+sot->goals_against"]
    out["gain_over_shipped"] = {
        name: [round(out["r"][f"{name}->goals_for"] - base_a, 4),
               round(out["r"][f"{name}->goals_against"] - base_d, 4)]
        for name, _ in SETS if name.startswith("goals+sot+")
    }
    print("  gain over the shipped goals+sot, as (attack, defence):")
    for name, (ga, gd) in out["gain_over_shipped"].items():
        flag = "   <- negative control" if name.endswith("NOISE") else ""
        print(f"    {name:26s} {ga:+.4f}  {gd:+.4f}{flag}")
    noise = out["gain_over_shipped"]["goals+sot+NOISE"]
    out["control_passed"] = bool(abs(noise[0]) < 0.005 and abs(noise[1]) < 0.005)
    print(f"  negative control {'PASSED' if out['control_passed'] else 'FAILED'} "
          f"-- an uninformative third channel gains {noise[0]:+.4f}/{noise[1]:+.4f}")
    return out


# --- M5: are the sot and total-shots channels the same channel? -----------


def _fit_channel(idx, rows, weights, channel: str, frame, cfg):
    """The same second-Poisson `_blend_channels` runs, on an arbitrary channel."""
    hcol, acol = CHANNELS[channel]
    h = pd.to_numeric(frame[hcol], errors="coerce").to_numpy(dtype=float)
    a = pd.to_numeric(frame[acol], errors="coerce").to_numpy(dtype=float)
    ok = ~(np.isnan(h) | np.isnan(a))
    usable = rows & ok
    w = weights[ok[rows]]
    fit = poisson_model.fit(
        idx.home_idx[usable], idx.away_idx[usable],
        np.nan_to_num(h)[usable], np.nan_to_num(a)[usable],
        w, len(idx.teams), alpha=cfg.alpha,
    )
    evidence = (np.bincount(idx.home_idx[usable], w, minlength=len(idx.teams))
                + np.bincount(idx.away_idx[usable], w, minlength=len(idx.teams)))
    return fit, evidence >= MIN_SOT_EVIDENCE


def m5_collinearity(frame, cutoff="2022-01-01") -> dict:
    """Correlate the strengths sot and total shots produce at one cutoff.

    A third channel that is near-collinear with the second cannot be worth a
    gate, and this is the cheapest way to find out -- one fit per channel at one
    date, rather than a walk-forward.
    """
    cfg = HEAD
    idx = _index(frame, cfg.fit_divisions)
    when = pd.Timestamp(cutoff)
    horizon = pd.Timedelta(days=cfg.half_life * cfg.horizon_half_lives)
    train = ((idx.dates < when) & (idx.dates >= when - horizon)
             & pd.Series(idx.in_fit_divisions, index=idx.dates.index))
    rows = train.to_numpy()
    weights = poisson_model.decay_weights(
        effective_ages(idx.dates[train], when, cfg.offseason_gap_days), cfg.half_life)

    fits, measured = {}, {}
    for channel in CHANNELS:
        fits[channel], measured[channel] = _fit_channel(
            idx, rows, weights, channel, frame, cfg)

    both = measured["sot"] & measured["shots"] & measured["goals"]
    print(f"\nM5  channel collinearity at {cutoff} ({both.sum()} clubs measured)")
    out = {"cutoff": cutoff, "n_clubs": int(both.sum()), "corr": {}}
    for side in ("att", "dfn"):
        for a, b in (("sot", "shots"), ("goals", "sot"), ("goals", "shots")):
            r = float(np.corrcoef(getattr(fits[a], side)[both],
                                  getattr(fits[b], side)[both])[0, 1])
            out["corr"][f"{side}:{a}~{b}"] = round(r, 4)
            print(f"  {side}  {a:6s} ~ {b:6s}  {r:+.4f}")
    return out


# --- M6: what the existing ledger already says about a per-side weight ----


def m6_curvature(conn) -> dict:
    """Re-reads rows 56 and 57. Fits nothing and spends no information."""
    sweep_row = conn.execute(
        "SELECT detail FROM gate_ledger WHERE name='h20_shots_blend'").fetchone()
    sides_row = conn.execute(
        "SELECT detail FROM gate_ledger WHERE name='h21_shots_sides'").fetchone()
    sweep = json.loads(sweep_row["detail"])
    sides = json.loads(sides_row["detail"])
    d = {a["value"]: a["deviance"] for a in sweep["arms"]}
    se = {a["value"]: a["paired_stderr"] for a in sweep["arms"]}

    h = 0.15
    d1 = (d[0.45] - d[0.15]) / (2 * h)
    d2 = (d[0.15] - 2 * d[0.30] + d[0.45]) / h**2
    base = sides["arms"]["baseline"]["deviance"]
    f_att = sides["arms"]["att only"]["deviance"] - base
    f_dfn = sides["arms"]["dfn only"]["deviance"] - base
    f_both = sides["arms"]["both"]["deviance"] - base

    had = (f_both - f_att - f_dfn) / 0.09
    hsum = d2 - 2 * had
    gsum = d1 - 0.30 * hsum - 0.60 * had
    # The surface is fitted from the diagonal plus the cross term, so the two
    # single-side arms are an over-determined check it was never given.
    residual = (0.30 * gsum + 0.045 * hsum) - (f_att + f_dfn)

    gains = []
    for t in np.linspace(0.05, 0.95, 19):
        haa, hdd = hsum * t, hsum * (1 - t)
        ga, gd = (f_att - 0.045 * haa) / 0.30, (f_dfn - 0.045 * hdd) / 0.30
        hess = np.array([[haa, had], [had, hdd]])
        if np.linalg.det(hess) <= 0:
            continue
        a, dd = np.linalg.solve(hess, [-ga, -gd])
        # The grid ran to 0.8 on the diagonal; a quadratic fitted there says
        # nothing at w = 2.7, so an escaping optimum is not a measurement.
        if not (0 <= a <= 0.60 and 0 <= dd <= 0.60):
            continue
        f_opt = (ga * a + gd * dd + .5 * haa * a * a + .5 * hdd * dd * dd + had * a * dd)
        gains.append((round(f_opt - f_both, 7), round(float(t), 2),
                      round(float(a), 3), round(float(dd), 3)))

    out = {
        "diagonal_vertex": round(0.30 - d1 / d2, 4),
        "diagonal_gain": round(-d1**2 / (2 * d2), 7),
        "paired_se": round(se[0.45], 6),
        "cross_term": round(had, 6),
        "consistency_residual": round(residual, 9),
        "identified": False,
        "in_box_gain_range": [min(g[0] for g in gains), max(g[0] for g in gains)],
        "in_box_se_range": [round(abs(min(g[0] for g in gains)) / se[0.45], 2),
                            round(abs(max(g[0] for g in gains)) / se[0.45], 2)],
        "n_admissible": len(gains),
    }
    print(f"\nM6  per-side weight, from rows 56 and 57 (no new fit)")
    print(f"  diagonal vertex w*={out['diagonal_vertex']}, gain "
          f"{out['diagonal_gain']:+.7f} ({abs(out['diagonal_gain'])/se[0.45]:.2f} SE)")
    print(f"  cross term {out['cross_term']:+.6f} (H21's super-additivity)")
    print(f"  gain over the unidentified split: {out['in_box_gain_range'][1]:+.7f} to "
          f"{out['in_box_gain_range'][0]:+.7f}")
    print(f"  = {out['in_box_se_range'][1]} to {out['in_box_se_range'][0]} paired SE "
          f"-- NOT identified by the ledger")
    return out


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", default="all", choices=["all", "m4", "m5", "m6"])
    parser.add_argument("--out", default="docs/channels_pregate_results.json")
    args = parser.parse_args(argv)

    conn = db.connect()
    results = {}
    if args.stage in ("all", "m6"):
        results["m6"] = m6_curvature(conn)
    if args.stage in ("all", "m4", "m5"):
        frame = load(conn)
        if args.stage in ("all", "m4"):
            results["m4"] = m4_split_half(frame)
        if args.stage in ("all", "m5"):
            results["m5"] = m5_collinearity(frame)

    if args.stage == "all":
        _log(conn, "probe", "p4_channels_pregate", json.dumps(results),
             "Pre-gate for a second in-store channel. M4 leave-one-season-out "
             "split-half for goals+shots+sot, the cell row 53 left blank; M5 "
             "collinearity of the sot and total-shots strength fits; M6 what "
             "rows 56/57 already imply about a per-side blend weight.")
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(results, fh, indent=2)
        print(f"\nwrote {args.out}")
    else:
        print("\n(stage run -- no ledger row written; use --stage all)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
