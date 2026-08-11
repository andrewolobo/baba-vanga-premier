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
