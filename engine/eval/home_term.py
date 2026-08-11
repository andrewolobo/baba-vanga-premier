"""E0's home/away miscalibration: can it be resolved, and is it the home term?

    python -m engine.eval.home_term --step 1     # power. Reads no outcomes.

`OUTSTANDING.md` §9.5 decomposed the served head's 1X2 vector and found E0
under-predicting home wins by +1.77 pts and over-predicting away wins by
−2.17 pts, both resolved, on the smallest division sample in the corpus. The
head fits **one scalar home coefficient** shared across all divisions
(`poisson.py:98`, `eta = c + h*is_home + att + dfn`), so a pooled `h` that is
too small for the Premier League is the leading explanation.

**Step 1 reads no match outcome.** Fisher information for a Poisson rate is
`Σλx²`, so both the resolution bound and the geometry check below are functions
of the fitted λs alone. This is the same licence `power.py` runs under, and the
reason a closed question can be sized before deciding whether to spend on it.

**What step 1 can and cannot say.** It answers *"could E0 see a home-term shift
of the size the gap implies"*. It does **not** decide adoption -- that stays on
goal Poisson deviance per convention 2, and `P4_TRAVEL_PLAN.md` §8 is explicit
that the coefficient test and the deviance test answer different questions. The
§1.4 shape (real, and not adoptable) is a live possibility here.
"""

from __future__ import annotations

import argparse
import json

import numpy as np
import pandas as pd
from scipy import optimize

from engine import db, ledger
from engine.eval import bootstrap, metrics, selection
from engine.eval.dispersion import outcome_probs, score_matrix
from engine.eval.draws import UNION_MARKETS, market_probs
from engine.eval.power import Z, resolvable_pct
from engine.eval.selection import (
    ALLOW_12,
    BURN_IN_SEASONS,
    CEILING,
    SHIPPED_FLOOR,
    _won,
    load,
    recommend,
)
from engine.seasons import DEV_SEASONS, SERVED_DIVISIONS

#: The gaps §9.5 measured, in points of outcome probability. Targets, not
#: inputs: step 1 asks what multiplicative home-rate shift would close the home
#: gap, then checks what that same shift does to the other two outcomes.
MEASURED_GAP = {"home": 1.77, "draw": 0.40, "away": -2.17}


def scored_mask(frame) -> np.ndarray:
    """The §9.5 population: everything after the walk-forward burn-in.

    Reproduces `draws.walk_forward_rho`'s NaN mask without fitting anything, so
    the numbers here describe the same matches the gap was measured on.
    """
    seasons = sorted(frame.season.unique())
    return (~frame.season.isin(seasons[:BURN_IN_SEASONS])).to_numpy()


def outcome_shift(lam_h, lam_a, multiplier: float, *, tilt: bool = False) -> dict:
    """What moving the home rate by `multiplier` does to (H, D, A), in points.

    Two parameterisations, and the distinction turned out to matter. `tilt=False`
    scales the home rate alone, which is what raising `h` does with the
    intercept held fixed. `tilt=True` scales home up and away down by the same
    factor, which is what raising `h` does when `c` re-fits to hold the total
    goal rate -- and a joint refit always does re-fit `c`. The first cannot move
    home and away apart without eating into the draw; the second can.
    """
    base = np.column_stack(outcome_probs(score_matrix(lam_h, lam_a)))
    moved = np.column_stack(outcome_probs(score_matrix(
        lam_h * multiplier, lam_a / multiplier if tilt else lam_a)))
    delta = 100.0 * (moved.mean(axis=0) - base.mean(axis=0))
    return {"home": float(delta[0]), "draw": float(delta[1]),
            "away": float(delta[2])}


def multiplier_closing_home(lam_h, lam_a, target_pts: float, *,
                            tilt: bool = False) -> float:
    """The multiplier that moves P(home) by `target_pts`."""
    return float(optimize.brentq(
        lambda m: outcome_shift(lam_h, lam_a, m, tilt=tilt)["home"] - target_pts,
        1.0, 2.0, xtol=1e-8))


def power(frame, scored) -> dict:
    """Resolution and geometry for a one-parameter home-rate shift, per division."""
    print(f"\nSTEP 1  power for a home-term shift  "
          f"({int(scored.sum()):,} matches, no outcomes read)")
    print(f"    {'div':>4} {'n':>6} {'required':>9} {'resolvable':>11} "
          f"{'contrast':>9} {'t':>6}  geometry of that shift (H/D/A pts)")

    rows = []
    for div in sorted(frame.division.unique()):
        sel = scored & (frame.division == div).to_numpy()
        lam_h = frame.lam_h.to_numpy(float)[sel]
        lam_a = frame.lam_a.to_numpy(float)[sel]

        # What the gap asks for, under both parameterisations.
        multiplier = multiplier_closing_home(lam_h, lam_a, MEASURED_GAP["home"])
        tilt_m = multiplier_closing_home(lam_h, lam_a, MEASURED_GAP["home"],
                                         tilt=True)
        required_pct = 100.0 * (multiplier - 1.0)
        tilt_pct = 100.0 * (tilt_m - 1.0)

        # What the data can see. `resolvable_pct` is the "everything else held
        # fixed" bound; the contrast form is the conservative one, because `h`
        # is identified against the away rate rather than in isolation.
        alone = resolvable_pct(lam_h)
        contrast = float(np.hypot(alone, resolvable_pct(lam_a)))
        shift = outcome_shift(lam_h, lam_a, multiplier)
        tilt_shift = outcome_shift(lam_h, lam_a, tilt_m, tilt=True)

        rows.append({
            "division": div, "n": int(sel.sum()),
            "required_pct": round(required_pct, 3),
            "required_tilt_pct": round(tilt_pct, 3),
            "resolvable_pct": round(alone, 3),
            "contrast_pct": round(contrast, 3),
            "t": round(required_pct / contrast, 3),
            "t_tilt": round(tilt_pct / contrast, 3),
            "resolves": bool(required_pct / contrast > Z),
            "resolves_tilt": bool(tilt_pct / contrast > Z),
            "shift": {k: round(v, 3) for k, v in shift.items()},
            "tilt_shift": {k: round(v, 3) for k, v in tilt_shift.items()},
        })
        r = rows[-1]
        print(f"    {div:>4} {r['n']:>6,} {r['required_pct']:>8.2f}% "
              f"{r['resolvable_pct']:>10.2f}% {r['contrast_pct']:>8.2f}% "
              f"{r['t']:>6.2f}  "
              f"H {shift['home']:+.2f}  D {shift['draw']:+.2f}  "
              f"A {shift['away']:+.2f}"
              f"{'   <- E0' if div == 'E0' else ''}")
    print("\n    same, as a tilt (home up and away down, total rate held):")
    print(f"    {'div':>4} {'required':>9} {'contrast':>9} {'t':>6}  "
          f"geometry (H/D/A pts)")
    for r in rows:
        t = r["tilt_shift"]
        print(f"    {r['division']:>4} {r['required_tilt_pct']:>8.2f}% "
              f"{r['contrast_pct']:>8.2f}% {r['t_tilt']:>6.2f}  "
              f"H {t['home']:+.2f}  D {t['draw']:+.2f}  A {t['away']:+.2f}"
              f"{'   <- E0' if r['division'] == 'E0' else ''}")
    return {"rows": rows, "measured_gap": MEASURED_GAP}


def read_geometry(result) -> dict:
    """Does a pure home-rate shift reproduce §9.5's E0 gap in all three cells?

    The single-parameter hypothesis makes a falsifiable prediction the λs alone
    can check: closing +1.77 on home should also deliver about −2.17 on away and
    leave the draw roughly alone. If the shift instead dumps its mass on the
    draw, `h` is the wrong parameter and no amount of fitting it will help.
    """
    e0 = next(r for r in result["rows"] if r["division"] == "E0")
    gap = result["measured_gap"]
    out = {}

    print("\n  does a one-parameter home correction reproduce the measured E0 gap?")
    print(f"    {'':>10} {'measured':>9} {'home-only':>11} {'residual':>9}"
          f" {'tilt':>9} {'residual':>9}")
    for cell in ("home", "draw", "away"):
        print(f"    {cell:>10} {gap[cell]:>+8.2f} {e0['shift'][cell]:>+10.2f} "
              f"{gap[cell] - e0['shift'][cell]:>+8.2f} "
              f"{e0['tilt_shift'][cell]:>+8.2f} "
              f"{gap[cell] - e0['tilt_shift'][cell]:>+8.2f}")

    # Away is the discriminating cell: home is closed by construction under
    # both, so each hypothesis lives or dies on whether away follows without
    # having been asked to.
    for name, key in (("home-only", "shift"), ("tilt", "tilt_shift")):
        residual = {k: round(gap[k] - e0[key][k], 3) for k in gap}
        ok = abs(residual["away"]) < 0.5 and abs(residual["draw"]) < 0.5
        out[name] = {"residual": residual, "suffices": bool(ok)}
        print(f"    -> {name:>10}: {'EXPLAINS' if ok else 'does NOT explain'} "
              f"the E0 gap (away residual {residual['away']:+.2f})")
    return out


# --- step 2: is it the strength dispersion? --------------------------------


def separation(lam_h, lam_a):
    """(level, half-log-ratio) for each fixture.

    `level` is the geometric mean of the two rates and `d` is what separates
    them. Working in these coordinates is what lets a correction move home and
    away apart **without touching the total goal rate**, which is the geometry
    step 1 said the E0 gap needs and neither home-term parameterisation could
    supply.
    """
    log_h, log_a = np.log(lam_h), np.log(lam_a)
    return (log_h + log_a) / 2.0, (log_h - log_a) / 2.0


def stretch(lam_h, lam_a, s: float, d_bar: float):
    """Scale the *centred* separation by `s`, holding level and home advantage.

    `d` carries both the home term and the strength difference:
    `d = (h + att_i - att_j + dfn_j - dfn_i)/2`. Over a balanced schedule the
    strength part averages to zero, so `mean(d)` is the home advantage and
    `d - mean(d)` is the strength spread alone. Stretching only the centred part
    is therefore a test of the ridge's shrinkage, not a second bite at step 1's
    home-term hypothesis -- which matters, because the two would otherwise be
    confounded and a positive result unattributable.
    """
    level, d = separation(lam_h, lam_a)
    moved = d_bar + s * (d - d_bar)
    return np.exp(level + moved), np.exp(level - moved)


def _deviance(lam_h, lam_a, goals_h, goals_a) -> float:
    return float(metrics.goal_deviance(pd.DataFrame({
        "lam_h": lam_h, "lam_a": lam_a,
        "fthg": goals_h, "ftag": goals_a})).mean())


def fit_stretch(train) -> tuple[float, float]:
    """The stretch minimising goal Poisson deviance -- convention 2's metric.

    Fitted on goals rather than on outcomes deliberately: the selection metric
    is goal deviance, so a stretch chosen on 1X2 would be optimising one thing
    and adjudicated on another.
    """
    lam_h = train.lam_h.to_numpy(float)
    lam_a = train.lam_a.to_numpy(float)
    goals_h = train.fthg.to_numpy(float)
    goals_a = train.ftag.to_numpy(float)
    _, d = separation(lam_h, lam_a)
    d_bar = float(d.mean())

    result = optimize.minimize_scalar(
        lambda s: _deviance(*stretch(lam_h, lam_a, s, d_bar), goals_h, goals_a),
        bounds=(0.5, 2.0), method="bounded")
    return float(result.x), d_bar


def walk_forward_stretch(frame, *, by_division: bool):
    """One (s, d_bar) per match, fitted only on strictly earlier seasons."""
    seasons = sorted(frame.season.unique())
    s_out = np.full(len(frame), np.nan)
    d_out = np.full(len(frame), np.nan)
    for i, season in enumerate(seasons):
        if i < BURN_IN_SEASONS:
            continue
        train = frame.season.isin(seasons[:i]).to_numpy()
        test = (frame.season == season).to_numpy()
        groups = ([(frame.division == d).to_numpy()
                   for d in sorted(frame.division.unique())]
                  if by_division else [np.ones(len(frame), bool)])
        for g in groups:
            s_out[test & g], d_out[test & g] = fit_stretch(frame[train & g])
    return s_out, d_out


def gap_by_separation(frame, scored, *, buckets: int = 5) -> dict:
    """Calibration gap against how separated the fixture is predicted to be.

    **This is step 2's discriminating statistic.** Over-shrunk strengths make
    the error grow with predicted separation and change sign with it: strong
    home favourites under-called, strong away favourites under-called the other
    way. A home-advantage error is flat in separation -- a level shift. The two
    hypotheses make different shapes here, which is what a single pooled gap
    cannot tell apart.
    """
    lam_h = frame.lam_h.to_numpy(float)[scored]
    lam_a = frame.lam_a.to_numpy(float)[scored]
    ftr = frame.ftr.to_numpy()[scored]
    dates = frame.match_date[scored]
    _, d = separation(lam_h, lam_a)
    probs = np.column_stack(outcome_probs(score_matrix(lam_h, lam_a)))

    edges = np.quantile(d, np.linspace(0, 1, buckets + 1))
    edges[0], edges[-1] = -np.inf, np.inf
    which = np.digitize(d, edges[1:-1])

    print(f"\n  gap by predicted separation ({buckets} buckets of "
          f"half-log-ratio d; higher = stronger home favourite)")
    print(f"    {'bucket':>7} {'n':>6} {'mean d':>8} {'home':>18} {'away':>18}")
    rows = []
    for b in range(buckets):
        sel = which == b
        blocks = bootstrap.week_blocks(dates[sel])
        cell = {"bucket": b, "n": int(sel.sum()), "mean_d": round(float(d[sel].mean()), 4)}
        text = []
        for name, code, col in (("home", "H", 0), ("away", "A", 2)):
            cmp = bootstrap.paired((ftr[sel] == code).astype(float),
                                   probs[sel, col], blocks)
            cell[name] = round(100 * float(cmp.delta), 3)
            cell[f"{name}_ci"] = [round(100 * cmp.ci[0], 2), round(100 * cmp.ci[1], 2)]
            cell[f"{name}_excludes_zero"] = bool(cmp.excludes_zero)
            text.append(f"{cell[name]:>+6.2f} [{cell[f'{name}_ci'][0]:>+5.1f},"
                        f"{cell[f'{name}_ci'][1]:>+5.1f}]"
                        f"{'*' if cmp.excludes_zero else ' '}")
        rows.append(cell)
        print(f"    {b:>7} {cell['n']:>6,} {cell['mean_d']:>8.3f} "
              + " ".join(text))

    # Over-shrinkage predicts a positive slope on home and a negative one on
    # away across the buckets. A level error predicts neither.
    x = np.array([r["mean_d"] for r in rows])
    slopes = {name: float(np.polyfit(x, [r[name] for r in rows], 1)[0])
              for name in ("home", "away")}
    print(f"    slope across buckets:  home {slopes['home']:+.2f}"
          f"   away {slopes['away']:+.2f}  pts per unit d")
    return {"rows": rows, "slopes": slopes}


def step2(frame, scored) -> dict:
    """Fit the stretch, and see whether it closes what step 1 could not."""
    print(f"\nSTEP 2  the dispersion hypothesis "
          f"({int(scored.sum()):,} matches)")
    diagnostic = gap_by_separation(frame, scored)

    s_pooled, d_pooled = walk_forward_stretch(frame, by_division=False)
    s_div, d_div = walk_forward_stretch(frame, by_division=True)

    lam_h = frame.lam_h.to_numpy(float)
    lam_a = frame.lam_a.to_numpy(float)
    arms = {
        "s = 1 (shipped)": (lam_h, lam_a),
        "s fitted pooled": stretch(lam_h, lam_a, s_pooled, d_pooled),
        "s per-division": stretch(lam_h, lam_a, s_div, d_div),
    }

    print("\n  fitted stretch, walk-forward (s > 1 = the head is over-shrunk):")

    def _fmt(values):
        return "  ".join(f"{v:.3f}" for v in sorted({round(float(x), 3)
                                                     for x in values}))

    print(f"    pooled: {_fmt(s_pooled[scored])}")
    for div in sorted(frame.division.unique()):
        sel = scored & (frame.division == div).to_numpy()
        print(f"    {div:>6}: {_fmt(s_div[sel])}")

    print("\n  outcome gaps after each arm (delivered minus claimed, pts):")
    print(f"    {'arm':>17} {'population':>10} {'home':>8} {'draw':>8} {'away':>8}")
    rows = []
    ftr = frame.ftr.to_numpy()
    for name, (lh, la) in arms.items():
        probs = np.column_stack(outcome_probs(score_matrix(lh, la)))
        for label, sel in (("pooled", scored),
                           ("E0", scored & (frame.division == "E0").to_numpy())):
            idx = np.flatnonzero(sel)
            blocks = bootstrap.week_blocks(frame.match_date.iloc[idx])
            cell = {"arm": name, "population": label}
            for cname, code, col in (("home", "H", 0), ("draw", "D", 1),
                                     ("away", "A", 2)):
                cmp = bootstrap.paired((ftr[idx] == code).astype(float),
                                       probs[idx, col], blocks)
                cell[cname] = round(100 * float(cmp.delta), 3)
                cell[f"{cname}_excludes_zero"] = bool(cmp.excludes_zero)
            rows.append(cell)
            print(f"    {name:>17} {label:>10} "
                  + " ".join(f"{cell[c]:>+7.2f}"
                             f"{'*' if cell[f'{c}_excludes_zero'] else ' '}"
                             for c in ("home", "draw", "away")))

    return {"diagnostic": diagnostic, "gaps": rows,
            "s_pooled": sorted({round(float(x), 4) for x in s_pooled[scored]}),
            "s_by_division": {
                div: sorted({round(float(x), 4) for x in
                             s_div[scored & (frame.division == div).to_numpy()]})
                for div in sorted(frame.division.unique())}}


# --- step 3: what does B2's existing calibration do to the product? --------


def slope_ci(d, gap, blocks, *, reps: int = 2000, alpha: float = 0.05):
    """Block-bootstrapped slope of `gap` on `d`.

    Step 2 reported this slope from a `polyfit` over five bucket means with no
    interval at all, which is the same over-reading the §9.2 correction calls
    out elsewhere. Resampling whole weeks keeps the dependence structure the
    paired bootstrap respects, and fits the slope per match rather than per
    bucket so the answer does not depend on where the bucket edges fell.
    """
    d = np.asarray(d, float)
    gap = np.asarray(gap, float)
    _, pos = np.unique(np.asarray(blocks), return_inverse=True)
    by_block = [np.flatnonzero(pos == b) for b in range(pos.max() + 1)]

    rng = np.random.default_rng(bootstrap.RNG_SEED)
    draws = rng.integers(0, len(by_block), size=(reps, len(by_block)))
    out = []
    for row in draws:
        idx = np.concatenate([by_block[b] for b in row])
        out.append(np.polyfit(d[idx], gap[idx], 1)[0])
    lo, hi = np.quantile(out, [alpha / 2, 1 - alpha / 2])
    return float(np.polyfit(d, gap, 1)[0]), (float(lo), float(hi))


def temperature(probs: np.ndarray, t: float) -> np.ndarray:
    """Sharpen (t>1) or flatten (t<1) without using any outcome information."""
    powered = np.clip(probs, 1e-12, None) ** t
    return powered / powered.sum(axis=1, keepdims=True)


def matched_sham(frame, raw, calibrated, scored) -> tuple[np.ndarray, float]:
    """A perturbation the same product-visible size as calibration, but blind.

    **§9.5's lesson, applied before the fact.** Any perturbation that moves
    recommendations from `12` to `1X` raised strike rate there -- a planted rho
    five times too large was the best arm. So a strike-rate gain from
    calibration means nothing until a change of the same magnitude, carrying no
    fitted information about outcomes, has been shown not to buy the same thing.
    `t` is chosen to match the share of recommendations that move, and is fitted
    to the calibrated arm rather than to any result.
    """
    target = _changed_share(raw, calibrated, scored)

    def miss(t):
        return _changed_share(raw, temperature(raw, t), scored) - target

    # Sharpening moves `12` toward `1X` the same way calibration does; search
    # upward from 1 until the change rate brackets the target.
    hi = 1.05
    while miss(hi) < 0 and hi < 4.0:
        hi += 0.05
    t = float(optimize.brentq(miss, 1.0, hi, xtol=1e-4)) if miss(hi) >= 0 else hi
    return temperature(raw, t), t


def _changed_share(a: np.ndarray, b: np.ndarray, scored) -> float:
    ma, _ = recommend(a, SHIPPED_FLOOR, allow_12=ALLOW_12)
    mb, _ = recommend(b, SHIPPED_FLOOR, allow_12=ALLOW_12)
    return float((ma[scored] != mb[scored]).mean())


def step3(frame, scored) -> dict:
    """Raw versus B2's calibration versus a magnitude-matched blind control."""
    print(f"\nSTEP 3  B2's calibration against the shipped product "
          f"({int(scored.sum()):,} matches, floor {SHIPPED_FLOOR}, "
          f"ceiling {CEILING})")

    raw = selection.raw_probs(frame)
    cal = selection.walk_forward_calibrate(frame, raw)
    sham, t = matched_sham(frame, raw, cal, scored)
    print(f"  control: temperature t = {t:.3f}, chosen to match calibration's "
          f"recommendation-change rate and blind to every outcome")
    arms = {"raw (shipped)": raw, "B2 calibrated": cal, "sham (control)": sham}

    ftr = frame.ftr.to_numpy()
    lam_h = frame.lam_h.to_numpy(float)
    lam_a = frame.lam_a.to_numpy(float)
    _, d_all = separation(lam_h, lam_a)
    idx = np.flatnonzero(scored)
    blocks = bootstrap.week_blocks(frame.match_date.iloc[idx])

    print("\n  separation slope on the home gap, per division "
          "(pts per unit d, 95% block CI)")
    print(f"    {'arm':>15} " + " ".join(f"{d:>20}" for d in
                                         ["pooled", "E0", "E1", "E2", "E3"]))
    slopes = []
    for name, probs in arms.items():
        cells = []
        for label in ("pooled", "E0", "E1", "E2", "E3"):
            sel = scored if label == "pooled" else (
                scored & (frame.division == label).to_numpy())
            j = np.flatnonzero(sel)
            gap = (ftr[j] == "H").astype(float) - probs[j, 0]
            b, (lo, hi) = slope_ci(d_all[j], 100 * gap,
                                   bootstrap.week_blocks(frame.match_date.iloc[j]))
            slopes.append({"arm": name, "population": label,
                           "slope": round(b, 3), "ci": [round(lo, 2), round(hi, 2)],
                           "excludes_zero": bool(lo > 0 or hi < 0)})
            cells.append(f"{b:>+6.2f} [{lo:>+5.1f},{hi:>+5.1f}]")
        print(f"    {name:>15} " + " ".join(f"{c:>20}" for c in cells))

    print("\n  calibration of what is published (delivered minus claimed, pts)")
    print(f"    {'arm':>15} {'pop':>7} {'home':>8} {'draw':>8} {'away':>8} "
          f"{'12':>8} {'1X':>8} {'X2':>8}")
    gaps = []
    for name, probs in arms.items():
        markets = market_probs(probs)
        for label in ("pooled", "E0"):
            sel = scored if label == "pooled" else (
                scored & (frame.division == "E0").to_numpy())
            j = np.flatnonzero(sel)
            blk = bootstrap.week_blocks(frame.match_date.iloc[j])
            cell = {"arm": name, "population": label}
            for cname, code, col in (("home", "H", 0), ("draw", "D", 1),
                                     ("away", "A", 2)):
                cmp = bootstrap.paired((ftr[j] == code).astype(float),
                                       probs[j, col], blk)
                cell[cname] = round(100 * float(cmp.delta), 2)
                cell[f"{cname}_sig"] = bool(cmp.excludes_zero)
            for m in UNION_MARKETS:
                won = _won(np.full(len(frame), m), ftr).astype(float)
                cmp = bootstrap.paired(won[j], markets[m][j], blk)
                cell[m] = round(100 * float(cmp.delta), 2)
                cell[f"{m}_sig"] = bool(cmp.excludes_zero)
            gaps.append(cell)
            print(f"    {name:>15} {label:>7} " + " ".join(
                f"{cell[c]:>+7.2f}{'*' if cell[f'{c}_sig'] else ' '}"
                for c in ("home", "draw", "away", "12", "1X", "X2")))

    print("\n  the product at the shipped setting")
    print(f"    {'arm':>15} {'changed':>8} {'strike':>7} "
          f"{'vs shipped, PAIRED':>26} {'claimed':>8} {'mix 12/1X/X2/H/A':>24}")
    base_won = None
    product = []
    for name, probs in arms.items():
        market, p = recommend(probs, SHIPPED_FLOOR, allow_12=ALLOW_12)
        won = _won(market, ftr).astype(float)
        if base_won is None:
            base_won, base_market = won, market
        cmp = bootstrap.paired(won[idx], base_won[idx], blocks)
        mix = {m: round(float((market[idx] == m).mean()), 4)
               for m in ("12", "1X", "X2", "H", "A")}
        row = {"arm": name,
               "changed_share": round(float((market[idx] != base_market[idx]).mean()), 4),
               "strike": round(float(won[idx].mean()), 4),
               "claimed": round(float(p[idx].mean()), 4),
               "vs_shipped": round(float(cmp.delta), 5),
               "vs_shipped_ci": [round(cmp.ci[0], 5), round(cmp.ci[1], 5)],
               "vs_shipped_excludes_zero": bool(cmp.excludes_zero),
               "honesty_gap": round(float(won[idx].mean() - p[idx].mean()) * 100, 2),
               "mix": mix}
        product.append(row)
        print(f"    {name:>15} {100*row['changed_share']:>7.2f}% "
              f"{100*row['strike']:>6.2f}% {100*row['vs_shipped']:>+8.3f} "
              f"[{100*row['vs_shipped_ci'][0]:>+6.3f},"
              f"{100*row['vs_shipped_ci'][1]:>+6.3f}]"
              f"{'*' if row['vs_shipped_excludes_zero'] else ' '}"
              f"{100*row['claimed']:>8.2f}% "
              + " ".join(f"{100*v:.1f}" for v in mix.values()))
    print("\n    honesty gap = delivered minus claimed on the published pick:")
    for row in product:
        print(f"      {row['arm']:>15} {row['honesty_gap']:>+6.2f} pts")

    return {"temperature": t, "slopes": slopes, "gaps": gaps,
            "product": product}


# --- step 4: the controls step 2 should have carried -----------------------

#: Draws for the noise ladder. Six is this project's control size (`REST.md`
#: H33, `TRAVEL.md` H34, `TOD_SLOT.md` H29) and the effect there is large and
#: monotone, so six resolves it.
SWEEP_DRAWS = 6

#: Draws for Null A, which is doing a harder job: it has to estimate the null
#: *distribution* of the slope, not just show that its mean is zero. Six draws
#: put a 30% error on an sd, and the sd is what step 2's interval has to be read
#: against. Every draw's own slope is reported rather than a count of how many
#: "passed", because §1.9's seed collision was invisible in the count and
#: obvious in the spread.
NULL_DRAWS = 40

#: Draws behind the per-population null sd in step 5. Far more than NULL_DRAWS
#: because these are point slopes with no bootstrap behind them, so they cost
#: almost nothing -- and the sd is being used as a yardstick, where 40 draws
#: leave ~11% on it and a sigma reading inherits that.
NULL_SD_DRAWS = 200

#: Bootstrap replicates behind each null draw's interval. Named so the
#: false-positive check tests the *published* estimator at its real setting, and
#: so tests can turn it down without changing what is being tested.
CONTROL_REPS = bootstrap.DEFAULT_REPS

#: What step 2 measured on real outcomes, for the sigma comparison below. Not an
#: input to anything -- the controls never see it.
STEP2_POOLED_HOME_SLOPE = 5.66

#: Log-scale noise on the lambda the arm predicts with and stratifies on. P0-1's
#: demonstration ran at 0.20; the ladder is what turns "could this be that
#: artifact" into a signed answer.
NOISE_LEVELS = (0.00, 0.05, 0.10, 0.15, 0.20)

CONTROL_SEED = 20260811

#: What `OUTSTANDING.md` §9.6 claims in prose, carried here so a rebuild is read
#: against it rather than quietly replacing it. `CHANNELS.md` §7's row 53 is the
#: precedent: a lost harness rebuilt is a new measurement until it reproduces.
QUOTED_NULL_A = 0.10
QUOTED_NOISE_HOME = (-0.27, -3.82, -14.26, -27.57, -53.12)


def _rng(kind: int, draw: int, extra: int = 0):
    """A distinct stream per (purpose, draw, level).

    §1.9's seed collision made a reference arm an exact oracle because two
    series were drawn from colliding seeds, and the only symptom was a control
    that was incoherent rather than wrong-looking. Keying the stream on all
    three indices makes the collision impossible rather than unlikely.
    """
    return np.random.default_rng([CONTROL_SEED, kind, draw, extra])


def simulate_ftr(lam_h, lam_a, rng) -> np.ndarray:
    """Poisson goals from the given rates, as a 1X2 label."""
    goals_h = rng.poisson(lam_h)
    goals_a = rng.poisson(lam_a)
    return np.where(goals_h > goals_a, "H", np.where(goals_h == goals_a, "D", "A"))


def _leg_slope(d, ftr, probs, code: str, col: int) -> float:
    """Point slope of the calibration gap on `d`, in points per unit d."""
    gap = 100.0 * ((ftr == code).astype(float) - probs[:, col])
    return float(np.polyfit(d, gap, 1)[0])


#: Both legs, because `home_term.py`'s step 3 regresses the home gap only and
#: `SEPARATION_SLOPE.md` §4 argues the away leg is the larger error and the
#: likelier true gradient. On synthetic outcomes the second leg costs nothing.
LEGS = (("home", "H", 0), ("away", "A", 2))


def _summarise(per_draw: list[float]) -> dict:
    values = np.asarray(per_draw, float)
    return {"per_draw": [round(v, 3) for v in per_draw],
            "mean": round(float(values.mean()), 3),
            "sd": round(float(values.std(ddof=1)), 3)}


def null_a(lam_h, lam_a, blocks) -> dict:
    """Goals drawn from the served lambdas, so the mapping is right by construction.

    Two questions, and §9.6 only asked the first.

    **Is the estimator unbiased?** The instrument must return zero here. Step
    2's +5.66 is a finding only if a head whose lambda -> outcome mapping is
    correct produces no slope.

    **Is the estimator's published interval honest?** `slope_ci` is the interval
    step 2 and step 3 both quote. Running it on every null draw turns that into
    a measurable false-positive rate: under a correct-by-construction mapping it
    should exclude zero in about 5% of draws. If it does so far more often, the
    interval is too narrow and every slope this module has published is
    over-resolved. Nothing outside this control can detect that, which is
    exactly the argument for having the control.
    """
    _, d = separation(lam_h, lam_a)
    probs = np.column_stack(outcome_probs(score_matrix(lam_h, lam_a)))
    outcomes = [simulate_ftr(lam_h, lam_a, _rng(0, i)) for i in range(NULL_DRAWS)]

    print(f"\n  NULL A  goals drawn from the served lambdas -- mapping correct "
          f"by construction ({NULL_DRAWS} draws)")
    print(f"    {'leg':>5} {'slope: mean +/- sd':>22} {'min':>8} {'max':>8} "
          f"{'mean CI half-width':>20} {'excludes zero':>15}")

    out = {}
    for name, code, col in LEGS:
        per_draw, half_widths, false_positives = [], [], 0
        for ftr in outcomes:
            gap = 100.0 * ((ftr == code).astype(float) - probs[:, col])
            b, (lo, hi) = slope_ci(d, gap, blocks, reps=CONTROL_REPS)
            per_draw.append(b)
            half_widths.append((hi - lo) / 2.0)
            false_positives += int(lo > 0 or hi < 0)

        cell = _summarise(per_draw)
        cell["min"] = round(min(per_draw), 3)
        cell["max"] = round(max(per_draw), 3)
        cell["mean_ci_half_width"] = round(float(np.mean(half_widths)), 3)
        # The interval the estimator claims, against the spread it actually has.
        cell["implied_sd_from_ci"] = round(cell["mean_ci_half_width"] / Z, 3)
        cell["false_positive_rate"] = round(false_positives / NULL_DRAWS, 3)
        cell["false_positives"] = false_positives
        out[name] = cell
        print(f"    {name:>5} {cell['mean']:>+13.2f} +/-{cell['sd']:>6.2f} "
              f"{cell['min']:>+8.2f} {cell['max']:>+8.2f} "
              f"{cell['mean_ci_half_width']:>20.2f} "
              f"{false_positives:>8}/{NULL_DRAWS}"
              f"{'  <- nominal is 5%' if false_positives > 0.05 * NULL_DRAWS else ''}")

    print(f"\n    the published interval against the spread it should cover:")
    for name in ("home", "away"):
        cell = out[name]
        print(f"      {name:>5}  slope_ci implies sd {cell['implied_sd_from_ci']:>5.2f}"
              f"   true null sd {cell['sd']:>5.2f}"
              f"   ratio {cell['implied_sd_from_ci'] / cell['sd']:>5.2f}")
    sigma = STEP2_POOLED_HOME_SLOPE / out["home"]["sd"]
    out["step2_home_slope_in_null_sd"] = round(float(sigma), 2)
    print(f"      step 2's pooled home slope {STEP2_POOLED_HOME_SLOPE:+.2f} is "
          f"{sigma:.2f} null sd -- {'resolved' if sigma > Z else 'NOT resolved'} "
          f"against this control")
    return out


def noise_sweep(lam_h, lam_a, blocks) -> dict:
    """Stratify on a lambda carrying log-noise -- the exact trap P0-1 fell into.

    Outcomes come from the CLEAN lambdas; the noisy lambda is what the arm both
    predicts with and stratifies on, which is the real situation -- an estimate
    is used for both at once. Regression to the mean then inflates the estimated
    separation in the top bucket, so P(home) is over-stated exactly where the
    measured effect is positive.

    The outcome draw is held fixed across the ladder and only the noise moves,
    so the levels are paired and the trend is not reading a different sample at
    each step. If the slope runs negative with noise, lambda noise can only
    *mask* step 2's positive finding, never manufacture it.
    """
    print("\n  P0-1 ARTIFACT SWEEP  stratifying on a lambda carrying log-noise")
    print(f"    {'noise':>6} {'home, mean +/- sd':>22} {'away, mean +/- sd':>22}"
          f"   {'quoted (home)':>14}")

    rows = []
    for level_index, sigma in enumerate(NOISE_LEVELS):
        legs = {}
        for name, code, col in LEGS:
            per_draw = []
            for i in range(SWEEP_DRAWS):
                ftr = simulate_ftr(lam_h, lam_a, _rng(1, i))
                eps = _rng(2, i, level_index)
                noisy_h = lam_h * np.exp(eps.normal(0.0, sigma, len(lam_h)))
                noisy_a = lam_a * np.exp(eps.normal(0.0, sigma, len(lam_a)))
                _, d_hat = separation(noisy_h, noisy_a)
                probs = np.column_stack(
                    outcome_probs(score_matrix(noisy_h, noisy_a)))
                per_draw.append(_leg_slope(d_hat, ftr, probs, code, col))
            legs[name] = _summarise(per_draw)
        rows.append({"noise": sigma, **legs})
        print(f"    {sigma:>6.2f} {legs['home']['mean']:>+15.2f} "
              f"+/-{legs['home']['sd']:>5.2f} {legs['away']['mean']:>+15.2f} "
              f"+/-{legs['away']['sd']:>5.2f}   "
              f"{QUOTED_NOISE_HOME[level_index]:>+13.2f}")

    home_means = [r["home"]["mean"] for r in rows]
    monotone = all(b < a for a, b in zip(home_means, home_means[1:]))
    print(f"    -> home slope strictly decreasing in noise: "
          f"{'YES' if monotone else 'NO'}")
    return {"rows": rows, "home_monotone_decreasing": bool(monotone)}


def step4(frame, scored) -> dict:
    """The two controls `OUTSTANDING.md` §9.6 describes and never committed.

    **No real match outcome is read.** Every outcome below is Poisson-resampled
    from the fitted lambdas, so this runs under the same licence as step 1,
    `power.py` and `h34_travel_power`, and spends no configuration.
    """
    print(f"\nSTEP 4  the controls step 2 should have carried "
          f"({int(scored.sum()):,} matches, synthetic outcomes throughout)")

    lam_h = frame.lam_h.to_numpy(float)[scored]
    lam_a = frame.lam_a.to_numpy(float)[scored]
    blocks = bootstrap.week_blocks(frame.match_date[scored])

    a = null_a(lam_h, lam_a, blocks)
    sweep_result = noise_sweep(lam_h, lam_a, blocks)

    # --- what the controls establish, stated as pass/fail ------------------
    # Standard error of the mean over the draws, which is the right yardstick
    # for "is the estimator centred on zero" -- not the per-draw sd, which is
    # the yardstick for "is a single measured slope large".
    verdicts = {}
    for name in ("home", "away"):
        cell = a[name]
        sem = cell["sd"] / np.sqrt(NULL_DRAWS)
        verdicts[name] = {
            "unbiased": bool(abs(cell["mean"]) <= Z * sem),
            "interval_honest": bool(cell["false_positive_rate"] <= 0.15),
            "sem": round(float(sem), 3)}

    print("\n  what the controls establish:")
    for name in ("home", "away"):
        v, cell = verdicts[name], a[name]
        print(f"    {name:>5}  unbiased: {'YES' if v['unbiased'] else 'NO'}"
              f" (mean {cell['mean']:+.2f}, sem {v['sem']:.2f})"
              f"   interval honest: {'YES' if v['interval_honest'] else 'NO'}"
              f" ({cell['false_positives']}/{NULL_DRAWS} at nominal 5%)")

    # Read the rebuild against the prose it reconstructs rather than letting a
    # new number silently replace a quoted one. CHANNELS.md §7's row 53 is the
    # precedent for what happens when nobody does this.
    consistent = abs(a["home"]["mean"] - QUOTED_NULL_A) <= a["home"]["sd"]
    magnitudes = [r["home"]["mean"] for r in sweep_result["rows"]]
    ratio = magnitudes[-1] / QUOTED_NOISE_HOME[-1]
    print("\n  against OUTSTANDING.md §9.6's prose:")
    print(f"    Null A home slope   quoted {QUOTED_NULL_A:+.2f} +/- 1.49   "
          f"rebuilt {a['home']['mean']:+.2f} +/- {a['home']['sd']:.2f}   "
          f"-> {'consistent' if consistent else 'DOES NOT REPRODUCE'}")
    print(f"    noise ladder sign   quoted monotonically negative   "
          f"rebuilt {'monotonically negative' if sweep_result['home_monotone_decreasing'] else 'NOT monotone'}"
          f"   -> {'reproduces' if sweep_result['home_monotone_decreasing'] else 'DOES NOT'}")
    print(f"    noise ladder size   quoted {QUOTED_NOISE_HOME[-1]:+.2f} at 0.20   "
          f"rebuilt {magnitudes[-1]:+.2f}   -> {1 / ratio:.1f}x SMALLER, "
          f"magnitudes do NOT reproduce")
    print("    the load-bearing claim is the SIGN -- lambda noise biases the "
          "slope negative, so it can only mask step 2's positive finding, never")
    print("    manufacture it. That reproduces. The quoted magnitudes do not, "
          "and per CHANNELS.md §7 they stay unattributable.")

    return {"null_a": a, "noise_sweep": sweep_result, "verdicts": verdicts,
            "quoted": {"null_a_home": QUOTED_NULL_A,
                       "noise_home": list(QUOTED_NOISE_HOME)},
            "null_a_consistent_with_quoted": bool(consistent),
            "noise_magnitudes_reproduce": False,
            "reads_real_outcomes": False}


# --- step 5: the away leg, which has never had an interval -----------------

POPULATIONS = ("pooled", "E0", "E1", "E2", "E3")

#: §6 of SEPARATION_SLOPE.md: four divisions x two legs is eight cells, and
#: whether E2 and E3 survive correction has never been checked. `REST.md` §1.5's
#: <=3-days-rest finding is the precedent for this going the other way. Pooled is
#: a single pre-specified test and is deliberately NOT in the family.
BONFERRONI_CELLS = 8


def _population_mask(frame, scored, label):
    return scored if label == "pooled" else (
        scored & (frame.division == label).to_numpy())


def null_sd_by_population(frame, scored) -> dict:
    """Null sd of the slope per population and leg, from synthetic outcomes.

    Step 4 established the pooled null spread. A division holds a fifth of the
    corpus or less, so its null sd is much wider and the pooled figure cannot be
    reused -- E0 is 2,948 matches against 15,824. Reads no real outcome, so this
    is free and rides along with the gate rather than needing its own row.
    """
    out = {}
    for label in POPULATIONS:
        sel = _population_mask(frame, scored, label)
        lam_h = frame.lam_h.to_numpy(float)[sel]
        lam_a = frame.lam_a.to_numpy(float)[sel]
        _, d = separation(lam_h, lam_a)
        probs = np.column_stack(outcome_probs(score_matrix(lam_h, lam_a)))
        cell = {}
        for name, code, col in LEGS:
            slopes = [_leg_slope(d, simulate_ftr(lam_h, lam_a, _rng(3, i)),
                                 probs, code, col)
                      for i in range(NULL_SD_DRAWS)]
            cell[name] = round(float(np.std(slopes, ddof=1)), 3)
        out[label] = cell
    return out


def step5(frame, scored) -> dict:
    """`slope_ci` on BOTH legs, for the three arms step 3 already ran.

    `home_term.py`'s step 3 regresses the home gap only, so the away leg has
    never carried an interval in any division for any arm -- while §9.5 makes it
    the *larger* error (pooled −1.07 resolved, against home +0.33 unresolved)
    and `SEPARATION_SLOPE.md` §4 argues it is the real gradient. The arms are
    not re-chosen: they are exactly step 3's raw / B2-calibrated / matched sham.

    Home is recomputed alongside, which doubles as a reproduction check on step
    3 -- if those numbers move, something else changed.
    """
    print(f"\nSTEP 5  the away leg ({int(scored.sum()):,} matches, "
          f"floor {SHIPPED_FLOOR}, ceiling {CEILING})")

    raw = selection.raw_probs(frame)
    cal = selection.walk_forward_calibrate(frame, raw)
    sham, t = matched_sham(frame, raw, cal, scored)
    print(f"  arms are step 3's, unchanged: raw, B2 calibrated, sham at t = {t:.3f}")

    null_sd = null_sd_by_population(frame, scored)
    print("\n  null sd of the slope per population (synthetic outcomes, "
          f"{NULL_SD_DRAWS} draws) -- the yardstick each cell is read against")
    print(f"    {'':>10} " + " ".join(f"{p:>8}" for p in POPULATIONS))
    for leg in ("home", "away"):
        print(f"    {leg:>10} " + " ".join(f"{null_sd[p][leg]:>8.2f}"
                                           for p in POPULATIONS))

    ftr = frame.ftr.to_numpy()
    lam_h = frame.lam_h.to_numpy(float)
    lam_a = frame.lam_a.to_numpy(float)
    _, d_all = separation(lam_h, lam_a)

    rows = []
    for arm_name, probs in (("raw (shipped)", raw), ("B2 calibrated", cal),
                            ("sham (control)", sham)):
        print(f"\n  {arm_name}  (slope, 95% block CI, and slope in null sd)")
        print(f"    {'leg':>5} " + " ".join(f"{p:>26}" for p in POPULATIONS))
        for leg, code, col in LEGS:
            cells = []
            for label in POPULATIONS:
                j = np.flatnonzero(_population_mask(frame, scored, label))
                blocks = bootstrap.week_blocks(frame.match_date.iloc[j])
                gap = 100.0 * ((ftr[j] == code).astype(float) - probs[j, col])
                b, (lo, hi) = slope_ci(d_all[j], gap, blocks)
                sigma = b / null_sd[label][leg]
                row = {"arm": arm_name, "leg": leg, "population": label,
                       "slope": round(b, 3), "ci": [round(lo, 2), round(hi, 2)],
                       "excludes_zero": bool(lo > 0 or hi < 0),
                       "null_sd": null_sd[label][leg], "sigma": round(sigma, 2)}
                # The correction §6 flags as unchecked, on the family it names.
                if arm_name == "raw (shipped)" and label != "pooled":
                    _, (blo, bhi) = slope_ci(d_all[j], gap, blocks,
                                             alpha=0.05 / BONFERRONI_CELLS)
                    row["bonferroni_ci"] = [round(blo, 2), round(bhi, 2)]
                    row["survives_bonferroni"] = bool(blo > 0 or bhi < 0)
                rows.append(row)
                cells.append(f"{b:>+6.2f} [{lo:>+5.1f},{hi:>+5.1f}]"
                             f"{'*' if row['excludes_zero'] else ' '}"
                             f"{sigma:>+5.1f}s")
            print(f"    {leg:>5} " + " ".join(f"{c:>26}" for c in cells))

    print(f"\n  Bonferroni across the {BONFERRONI_CELLS} division x leg cells "
          f"of the shipped arm (SEPARATION_SLOPE.md §6)")
    print(f"    {'leg':>5} {'div':>5} {'slope':>8} {'uncorrected':>18} "
          f"{'corrected':>18} {'survives':>9}")
    survivors = []
    for row in rows:
        if "bonferroni_ci" not in row:
            continue
        if row["excludes_zero"]:
            survivors.append((row["leg"], row["population"],
                              row["survives_bonferroni"]))
        print(f"    {row['leg']:>5} {row['population']:>5} "
              f"{row['slope']:>+8.2f} "
              f"[{row['ci'][0]:>+6.2f},{row['ci'][1]:>+6.2f}] "
              f"[{row['bonferroni_ci'][0]:>+6.2f},{row['bonferroni_ci'][1]:>+6.2f}] "
              f"{'YES' if row['survives_bonferroni'] else 'no':>9}")
    kept = [f"{leg} {div}" for leg, div, ok in survivors if ok]
    lost = [f"{leg} {div}" for leg, div, ok in survivors if not ok]
    print(f"    -> survive: {', '.join(kept) if kept else 'none'}")
    print(f"    -> lost to correction: {', '.join(lost) if lost else 'none'}")

    return {"temperature": t, "null_sd": null_sd, "slopes": rows,
            "bonferroni_cells": BONFERRONI_CELLS,
            "survives_bonferroni": kept, "lost_to_bonferroni": lost}


def away_leg_arms(result: dict) -> list[dict]:
    """The ledger arm list for step 5: ONE ENTRY PER ARM, not per cell.

    `trials.count_configurations` sums `len(arms)` over a row, so handing it all
    30 leg x population cells would book 30 configurations against a gate that
    ran three arms. `b2_calibration_in_product` recorded these same three for the
    home leg and cost 3; this is the away leg at the same rate. The pooled away
    slope is what carries each arm's identity into the ledger.
    """
    return [{"arm": r["arm"], "leg": r["leg"], "slope": r["slope"],
             "excludes_zero": r["excludes_zero"]}
            for r in result["slopes"]
            if r["population"] == "pooled" and r["leg"] == "away"]


# --- step 6: is the gap linear in d? the controls ---------------------------

#: Draws per control cell. The output is a CONTRAST between two planted
#: mechanisms, so each planted mean has to be pinned tightly enough that the
#: contrast is not mostly draw noise -- at 12 draws the per-cell sem was ~1.2
#: against a contrast of ~5.8, which is not good enough to decide whether a test
#: is worth running.
MECHANISM_DRAWS = 40

#: Over-shrinkage levels. `s` is the factor by which TRUE centred separation
#: exceeds the head's, so outcomes are drawn from stretched lambdas and scored
#: against unstretched ones -- the defect §9.6 step 2 hypothesised, planted.
#: 1.12 is in the grid so a level lands near the observed slope without
#: interpolating between two coarse ones.
SHRINK_LEVELS = (1.05, 1.10, 1.12, 1.15, 1.20)

#: Top-quintile step sizes, in points of home probability. The competing
#: mechanism §3 of SEPARATION_SLOPE.md describes: the most lopsided fifth of
#: fixtures is mis-mapped and the rest is fine.
STEP_LEVELS = (1.0, 2.0, 3.0, 4.0, 4.5)

TOP_QUINTILE = 0.8


def curvature(d, gap):
    """(linear, quadratic) coefficients of `gap` on CENTRED d.

    Centred so the two coefficients are near-orthogonal: on raw d the quadratic
    term is strongly collinear with the linear one and the split between them
    stops meaning anything. Fitted per match, which is also what makes this
    immune to the uneven bucket spacing that makes the five-point diagnostic in
    `SEPARATION_SLOPE.md` §3 hard to read -- the top and bottom buckets are
    ~0.17 wide in d and the middle three ~0.08.
    """
    dc = np.asarray(d, float) - float(np.mean(d))
    quad, lin, _ = np.polyfit(dc, np.asarray(gap, float), 2)
    return float(lin), float(quad)


def curvature_ci(d, gap, blocks, *, reps: int = bootstrap.DEFAULT_REPS,
                 alpha: float = 0.05):
    """Block-bootstrapped interval on the quadratic coefficient."""
    d = np.asarray(d, float)
    gap = np.asarray(gap, float)
    _, pos = np.unique(np.asarray(blocks), return_inverse=True)
    by_block = [np.flatnonzero(pos == b) for b in range(pos.max() + 1)]

    rng = np.random.default_rng(bootstrap.RNG_SEED)
    draws = rng.integers(0, len(by_block), size=(reps, len(by_block)))
    out = []
    for row in draws:
        idx = np.concatenate([by_block[b] for b in row])
        out.append(curvature(d[idx], gap[idx])[1])
    lo, hi = np.quantile(out, [alpha / 2, 1 - alpha / 2])
    return curvature(d, gap), (float(lo), float(hi))


def _gap_vs(ftr, probs, code, col):
    return 100.0 * ((ftr == code).astype(float) - probs[:, col])


def _shrunk_truth(lam_h, lam_a, s: float):
    """Lambdas whose centred separation is `s` times the head's."""
    _, d = separation(lam_h, lam_a)
    return stretch(lam_h, lam_a, s, float(d.mean()))


def _stepped_truth(lam_h, lam_a, target_pts: float):
    """Lambdas tilted in the top quintile of d only, by `target_pts` of P(home)."""
    _, d = separation(lam_h, lam_a)
    top = d >= np.quantile(d, TOP_QUINTILE)
    m = multiplier_closing_home(lam_h[top], lam_a[top], target_pts, tilt=True)
    out_h, out_a = lam_h.copy(), lam_a.copy()
    out_h[top] *= m
    out_a[top] /= m
    return out_h, out_a


def _mechanism_cell(lam_h, lam_a, truth_h, truth_a, kind: int, level_index: int):
    """(linear, quadratic) per leg, averaged over draws, for one planted truth.

    Outcomes come from the planted TRUTH; the gap is measured against the head's
    own unperturbed probabilities, which is what a real defect looks like.
    """
    _, d = separation(lam_h, lam_a)
    probs = np.column_stack(outcome_probs(score_matrix(lam_h, lam_a)))
    cell = {}
    for name, code, col in LEGS:
        lin, quad = [], []
        for i in range(MECHANISM_DRAWS):
            ftr = simulate_ftr(truth_h, truth_a, _rng(kind, i, level_index))
            b, c = curvature(d, _gap_vs(ftr, probs, code, col))
            lin.append(b)
            quad.append(c)
        cell[name] = {"linear": round(float(np.mean(lin)), 2),
                      "linear_sd": round(float(np.std(lin, ddof=1)), 2),
                      "quadratic": round(float(np.mean(quad)), 2),
                      "quadratic_sd": round(float(np.std(quad, ddof=1)), 2)}
    return cell


def step6(frame, scored) -> dict:
    """Can the curvature statistic tell over-shrinkage from a tail effect?

    **This is the control, and it runs alone and first.** §1.12's lesson is that
    a ceiling read before any real arm refutes bad predictions for free; here the
    question is sharper than a ceiling, because the two candidate mechanisms make
    *different* predictions and the whole value of item 3 is telling them apart.
    If both produce the same curvature signature the test cannot discriminate and
    should not be run on real data at all.

    No real match outcome is read: every outcome is Poisson-resampled from a
    planted truth. Same licence as steps 1 and 4.
    """
    print(f"\nSTEP 6  linearity controls "
          f"({int(scored.sum()):,} matches, synthetic outcomes throughout)")

    lam_h = frame.lam_h.to_numpy(float)[scored]
    lam_a = frame.lam_a.to_numpy(float)[scored]
    blocks = bootstrap.week_blocks(frame.match_date[scored])
    _, d = separation(lam_h, lam_a)
    probs = np.column_stack(outcome_probs(score_matrix(lam_h, lam_a)))

    # C1 -- the null. Both coefficients must be zero, and the interval on the
    # quadratic must have honest coverage or a curvature finding means nothing.
    print(f"\n  C1 NULL  correct mapping ({NULL_DRAWS} draws)")
    print(f"    {'leg':>5} {'linear':>18} {'quadratic':>18} "
          f"{'quad excludes zero':>20}")
    null = {}
    for name, code, col in LEGS:
        lin, quad, fp = [], [], 0
        for i in range(NULL_DRAWS):
            ftr = simulate_ftr(lam_h, lam_a, _rng(4, i))
            gap = _gap_vs(ftr, probs, code, col)
            (b, c), (lo, hi) = curvature_ci(d, gap, blocks, reps=CONTROL_REPS)
            lin.append(b)
            quad.append(c)
            fp += int(lo > 0 or hi < 0)
        null[name] = {
            "linear": round(float(np.mean(lin)), 2),
            "linear_sd": round(float(np.std(lin, ddof=1)), 2),
            "quadratic": round(float(np.mean(quad)), 2),
            "quadratic_sd": round(float(np.std(quad, ddof=1)), 2),
            "false_positives": fp, "draws": NULL_DRAWS}
        n = null[name]
        print(f"    {name:>5} {n['linear']:>+10.2f} +/-{n['linear_sd']:>5.2f} "
              f"{n['quadratic']:>+10.2f} +/-{n['quadratic_sd']:>5.2f} "
              f"{fp:>13}/{NULL_DRAWS}")

    families = {}
    for label, kind, levels, build in (
            ("C2 OVER-SHRINKAGE", 5, SHRINK_LEVELS,
             lambda v: _shrunk_truth(lam_h, lam_a, v)),
            ("C3 TOP-QUINTILE STEP", 6, STEP_LEVELS,
             lambda v: _stepped_truth(lam_h, lam_a, v))):
        print(f"\n  {label}  ({MECHANISM_DRAWS} draws per level)")
        print(f"    {'level':>6} {'home linear':>16} {'home quad':>16} "
              f"{'away linear':>16} {'away quad':>16}")
        rows = []
        for j, value in enumerate(levels):
            truth_h, truth_a = build(value)
            cell = _mechanism_cell(lam_h, lam_a, truth_h, truth_a, kind, j)
            rows.append({"level": value, **cell})
            print(f"    {value:>6.2f} "
                  f"{cell['home']['linear']:>+10.2f} +/-{cell['home']['linear_sd']:>4.2f} "
                  f"{cell['home']['quadratic']:>+10.2f} +/-{cell['home']['quadratic_sd']:>4.2f} "
                  f"{cell['away']['linear']:>+10.2f} +/-{cell['away']['linear_sd']:>4.2f} "
                  f"{cell['away']['quadratic']:>+10.2f} +/-{cell['away']['quadratic_sd']:>4.2f}")
        families[label] = rows

    # The discriminating read: at the level that reproduces the OBSERVED linear
    # slope, what curvature does each mechanism imply?
    print(f"\n  discrimination -- matched on the observed home linear slope "
          f"{STEP2_POOLED_HOME_SLOPE:+.2f}")
    print(f"    {'mechanism':>22} {'level':>7} {'home linear':>13} "
          f"{'home quadratic implied':>24}")
    implied = {}
    for label, rows in families.items():
        best = min(rows, key=lambda r: abs(r["home"]["linear"]
                                           - STEP2_POOLED_HOME_SLOPE))
        implied[label] = {"level": best["level"],
                          "home_linear": best["home"]["linear"],
                          "home_quadratic": best["home"]["quadratic"],
                          "away_linear": best["away"]["linear"],
                          "away_quadratic": best["away"]["quadratic"]}
        print(f"    {label:>22} {best['level']:>7.2f} "
              f"{best['home']['linear']:>+13.2f} "
              f"{best['home']['quadratic']:>+24.2f}")

    # A real run yields ONE measurement, so the yardstick is the null sd of a
    # single draw -- not the sem of the planted means, which more draws can
    # always shrink. This is the question "could one measurement tell these
    # apart", and it is the one that decides whether to spend.
    print(f"\n    could ONE real measurement tell the two apart?")
    print(f"    {'leg':>5} {'shrinkage':>11} {'step':>11} {'apart':>8} "
          f"{'null sd':>9} {'sigma':>7} {'verdict':>18}")
    discrimination = {}
    for leg in ("home", "away"):
        shrink = implied["C2 OVER-SHRINKAGE"][f"{leg}_quadratic"]
        stepped = implied["C3 TOP-QUINTILE STEP"][f"{leg}_quadratic"]
        apart = abs(shrink - stepped)
        sd = null[leg]["quadratic_sd"]
        sigma = apart / sd
        discrimination[leg] = {
            "shrinkage_quadratic": shrink, "step_quadratic": stepped,
            "apart": round(float(apart), 2), "null_sd": sd,
            "sigma": round(float(sigma), 2), "separates": bool(sigma > Z)}
        print(f"    {leg:>5} {shrink:>+11.2f} {stepped:>+11.2f} "
              f"{apart:>8.2f} {sd:>9.2f} {sigma:>7.2f} "
              f"{('SEPARATES' if sigma > Z else 'cannot separate'):>18}")

    # What would close it. Sigma scales as sqrt(n), so the corpus multiple is
    # (Z/sigma)^2 -- the same arithmetic §1.4 and §1.6 report for their nulls.
    n = int(scored.sum())
    best = max(discrimination.values(), key=lambda v: v["sigma"])
    multiple = (Z / best["sigma"]) ** 2
    discrimination["required_corpus_multiple"] = round(float(multiple), 2)
    discrimination["required_matches"] = int(round(n * multiple))
    print(f"\n    what would close it: {multiple:.2f}x this corpus "
          f"({n * multiple:,.0f} matches against {n:,}), i.e. "
          f"{n * multiple - n:,.0f} more")

    any_leg = any(v["separates"] for v in discrimination.values()
                  if isinstance(v, dict) and "separates" in v)
    print(f"\n    -> the curvature test {'IS' if any_leg else 'IS NOT'} worth "
          f"running on real data")
    if not any_leg:
        print("       Both mechanisms produce the same curvature to within the "
              "noise of a single measurement. Running it would spend a")
        print("       configuration on a statistic that cannot answer the "
              "question it was designed for. This is the §1.4 shape, caught")
        print("       for 0 configurations -- exactly what §1.12 says a control "
              "run first is for.")

    return {"null": null, "families": families, "implied": implied,
            "discrimination": discrimination,
            "worth_running": bool(any_leg),
            "reads_real_outcomes": False}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--step", type=int, default=1)
    parser.add_argument("--out", default="docs/home_term_results.json")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    conn = db.connect()
    frame = load(conn)
    scored = scored_mask(frame)

    if args.step == 1:
        results = {"step1": power(frame, scored)}
        results["step1"]["geometry"] = read_geometry(results["step1"])
        row = {
            "kind": ledger.PROBE, "name": "home_term_power",
            "reason":
                   "OUTSTANDING.md §9.5 follow-up, step 1 of 4. Sizes a "
                   "one-parameter home-rate shift against what each division "
                   "can resolve, and checks on the lambdas alone whether a "
                   "single home coefficient reproduces the E0 gap in all three "
                   "outcome cells. Reads no match outcome -- Fisher information "
                   "for a Poisson rate needs only the fitted lambdas -- so it "
                   "carries no arm list and adds no configuration, on the same "
                   "accounting as power.py and h34_travel_power."}
        cost = "0 configurations"
    elif args.step == 4:
        results = {"step4": step4(frame, scored)}
        row = {
            "kind": ledger.PROBE, "name": "home_term_slope_controls",
            "reason":
                   "SEPARATION_SLOPE.md §8 item 1. Step 2 shipped a positive "
                   "result without the control §9.5 says every gate needs, and "
                   "the two controls run afterwards were never committed -- they "
                   "exist only as prose in OUTSTANDING.md §9.6, so the one live "
                   "modelling finding this project has is licensed by numbers "
                   "nobody can re-derive. This commits both. Null A resamples "
                   "goals from the served lambdas, making the lambda -> outcome "
                   "mapping correct by construction, so the instrument must "
                   "return a zero slope. The P0-1 artifact sweep stratifies on a "
                   "lambda carrying log-noise, which is the trap P0-1 fell into "
                   "once already, and establishes the SIGN of that bias. Both "
                   "legs are reported, because step 3 regresses the home gap "
                   "only and the away leg has never had an interval. Reads no "
                   "real match outcome -- every outcome is Poisson-resampled "
                   "from fitted lambdas -- so it carries no arm list and adds no "
                   "configuration, on the same accounting as power.py, "
                   "h34_travel_power and step 1."}
        cost = "0 configurations"
    elif args.step == 6:
        results = {"step6": step6(frame, scored)}
        row = {
            "kind": ledger.PROBE, "name": "linearity_controls",
            "reason":
                   "SEPARATION_SLOPE.md §8 item 3, the control that runs first "
                   "and alone. Item 3 asks whether the separation gap is linear "
                   "in d or a tail effect, because the two imply different "
                   "mechanisms and different fixes. This checks the statistic "
                   "can tell them apart BEFORE it is pointed at real outcomes: "
                   "C1 plants a correct mapping and requires both coefficients "
                   "zero with honest coverage on the quadratic, C2 plants the "
                   "over-shrinkage §9.6 step 2 hypothesised at four levels, and "
                   "C3 plants a top-quintile step at four sizes. The read is the "
                   "curvature each mechanism implies AT THE LEVEL THAT "
                   "REPRODUCES THE OBSERVED LINEAR SLOPE -- if they agree there, "
                   "the test cannot discriminate and should not be run at all. "
                   "§1.12's lesson, applied before the fact. Reads no real match "
                   "outcome: every outcome is Poisson-resampled from a planted "
                   "truth, so it carries no arm list and adds no configuration, "
                   "on the same accounting as power.py, step 1 and step 4."}
        cost = "0 configurations"
    elif args.step == 5:
        results = {"step5": step5(frame, scored)}
        arms = away_leg_arms(results["step5"])
        row = {
            "kind": ledger.GATE, "name": "home_term_away_leg",
            "detail_extra": {"arms": arms},
            "reason":
                   "SEPARATION_SLOPE.md §8 item 2. `home_term.py` step 3 "
                   "regresses the HOME calibration gap only, so the away leg has "
                   "never carried an interval in any division for any arm -- "
                   "while §9.5 makes it the larger error (pooled -1.07 resolved "
                   "against home +0.33 unresolved) and §4 of that document argues "
                   "it is the real gradient while home is a top-quintile step. "
                   "This runs `slope_ci` on both legs for the three arms step 3 "
                   "already ran; the arms are inherited, not re-chosen. It also "
                   "closes §6's open question by applying Bonferroni across the "
                   "eight division x leg cells, which had never been checked, "
                   "and reads every slope against a per-population null sd from "
                   "synthetic outcomes -- the pooled figure from step 4 cannot be "
                   "reused because a division is a fifth of the corpus or less. "
                   "ACCOUNTING: §8 item 2 left this an owner call between 0 (a "
                   "re-report of `b2_calibration_in_product`'s arms under a "
                   "second statistic) and 1. The owner chose THREE, 2026-08-11 "
                   "-- one per arm, symmetric with how `b2_calibration_in_product` "
                   "costed the identical three arms on the home leg. That is "
                   "more than either figure §8 named and is the inflating "
                   "direction, per §2.2. The arm list is one entry per ARM, not "
                   "per reported cell: 3 arms x 2 legs x 5 populations would "
                   "otherwise book 30."}
        cost = "3 configurations (owner decision -- see the reason field)"
    elif args.step == 3:
        results = {"step3": step3(frame, scored)}
        arms = [{"arm": r["arm"], "strike": r["strike"],
                 "changed_share": r["changed_share"],
                 "honesty_gap": r["honesty_gap"]}
                for r in results["step3"]["product"]]
        row = {
            "kind": ledger.GATE, "name": "b2_calibration_in_product",
            "detail_extra": {"arms": arms},
            "reason":
                   "OUTSTANDING.md §9.5 follow-up, step 3. The shipped tip rule "
                   "runs on the RAW pmf -- `tips.py` reads `predictions`, which "
                   "`metrics.model_probs` fills uncalibrated -- while B2's "
                   "walk-forward vector scaling already exists, is tested, and "
                   "halves the separation slope. This measures what simply "
                   "using it would do to what the product publishes: the union "
                   "calibration gaps, the per-division separation slope with a "
                   "block-bootstrap CI, and strike rate paired against the "
                   "shipped rule. The third arm is a magnitude-matched sham "
                   "that carries no outcome information, because §9.5 showed "
                   "any perturbation shifting `12` toward `1X` raises strike "
                   "rate on its own. Three configurations."}
        cost = "3 configurations"
    else:
        results = {"step2": step2(frame, scored)}
        # Arms carry their results, not just their names -- `trials` can only
        # collapse a re-run when it can see the numbers matched.
        arms = [{"arm": g["arm"], **{c: g[c] for c in ("home", "draw", "away")}}
                for g in results["step2"]["gaps"] if g["population"] == "pooled"]
        row = {
            "kind": ledger.GATE, "name": "home_term_dispersion",
            "detail_extra": {"arms": arms},
            "reason":
                   "OUTSTANDING.md §9.5 follow-up, step 2 of 4. Step 1 refuted "
                   "the home-coefficient explanation on the lambdas alone -- "
                   "neither a home-rate shift nor a tilt reproduces the E0 "
                   "geometry -- and showed E0 cannot resolve a fix of that size "
                   "on its own. This tests the successor hypothesis pooled: "
                   "that a global ridge alpha over-shrinks strength dispersion, "
                   "worst where true dispersion is widest. The stretch acts on "
                   "the CENTRED separation only, so home advantage is held "
                   "fixed and a positive result cannot be step 1's hypothesis "
                   "returning under another name. Three configurations."}
        cost = "3 configurations"

    if args.dry_run:
        print("\n  [dry-run] ledger row NOT written")
    else:
        detail = {**results, **row.pop("detail_extra", {})}
        ledger.record(conn, purpose="dev", seasons=DEV_SEASONS,
                      divisions=SERVED_DIVISIONS, detail=detail, **row)
        print(f"\n  [ledger] {row['kind']}:{row['name']}  ({cost})")

    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(results, handle, indent=2, default=str)
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
