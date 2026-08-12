"""The E0 follow-up, OUTSTANDING.md §9.6.

These pin the algebra three recorded gates rest on. The separation coordinates
are the load-bearing part: §9.6's whole argument is that a correction can move
home and away apart **without** moving the total goal rate, and that the centred
stretch leaves home advantage alone. Both are properties of the transform, so
they belong in tests rather than in a paragraph.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from engine.eval import home_term

LAM_H = np.array([1.6, 1.2, 2.1, 0.9, 1.35])
LAM_A = np.array([1.1, 1.4, 0.8, 1.3, 1.35])


def test_separation_coordinates_round_trip():
    level, d = home_term.separation(LAM_H, LAM_A)

    assert np.exp(level + d) == pytest.approx(LAM_H)
    assert np.exp(level - d) == pytest.approx(LAM_A)


def test_a_stretch_of_one_is_the_identity():
    """s = 1 must be the shipped head exactly, or every arm is measured against
    a baseline that is already perturbed."""
    _, d = home_term.separation(LAM_H, LAM_A)
    lh, la = home_term.stretch(LAM_H, LAM_A, 1.0, float(d.mean()))

    assert lh == pytest.approx(LAM_H)
    assert la == pytest.approx(LAM_A)


@pytest.mark.parametrize("s", [0.8, 1.25, 1.6])
def test_the_stretch_holds_the_total_goal_rate(s):
    """It moves the two rates apart around their geometric mean, so the level is
    untouched. This is what makes it a test of dispersion rather than a second
    bite at step 1's home-term hypothesis."""
    _, d = home_term.separation(LAM_H, LAM_A)
    lh, la = home_term.stretch(LAM_H, LAM_A, s, float(d.mean()))

    assert lh * la == pytest.approx(LAM_H * LAM_A)


def test_the_stretch_leaves_the_mean_separation_alone():
    """Home advantage is `mean(d)`; only the spread around it may move, or a
    positive result could not be attributed to shrinkage."""
    _, d = home_term.separation(LAM_H, LAM_A)
    d_bar = float(d.mean())
    lh, la = home_term.stretch(LAM_H, LAM_A, 1.5, d_bar)
    _, moved = home_term.separation(lh, la)

    assert float(moved.mean()) == pytest.approx(d_bar)
    assert moved.std() > d.std(), "the spread is what a stretch is for"


def test_a_tilt_moves_home_and_away_in_opposite_directions():
    """Step 1's second parameterisation. A pure home-rate shift cannot separate
    the two without eating the draw; the tilt is what can."""
    plain = home_term.outcome_shift(LAM_H, LAM_A, 1.05, tilt=False)
    tilt = home_term.outcome_shift(LAM_H, LAM_A, 1.05, tilt=True)

    assert plain["home"] > 0 and tilt["home"] > 0
    assert tilt["away"] < plain["away"], "the tilt takes more from away"
    assert abs(tilt["draw"]) < abs(plain["draw"]), "and less from the draw"


def test_no_shift_is_no_change():
    shift = home_term.outcome_shift(LAM_H, LAM_A, 1.0)

    assert all(v == pytest.approx(0.0, abs=1e-12) for v in shift.values())


def test_temperature_of_one_is_the_identity_and_rows_stay_normalised():
    probs = np.array([[0.45, 0.27, 0.28], [0.30, 0.30, 0.40]])

    assert home_term.temperature(probs, 1.0) == pytest.approx(probs)
    assert home_term.temperature(probs, 1.4).sum(axis=1) == pytest.approx(1.0)


def test_sharpening_raises_the_largest_probability():
    """The control in step 3 is a sharpener, so this is the property that makes
    it a perturbation of the right kind rather than noise."""
    probs = np.array([[0.45, 0.27, 0.28]])
    sharper = home_term.temperature(probs, 1.5)

    assert sharper[0, 0] > probs[0, 0]
    assert sharper[0, 1] < probs[0, 1]


def test_the_honesty_gap_interval_bounds_the_number_step_3_publishes():
    """The gap and its interval must be the same statistic.

    Step 3 publishes `honesty_gap` as a plain difference of means and bounds it
    with `bootstrap.paired`, and `BACKLOG.md` B13 turns on comparing two of them.
    If `paired`'s point estimate ever stops reproducing that difference -- a
    trimmed or median estimator would do it -- the published number and its
    interval would describe different quantities and nothing else would say so.
    """
    won = np.array([1.0, 0.0, 1.0, 1.0, 0.0, 1.0, 1.0, 0.0])
    claimed = np.array([0.72, 0.68, 0.81, 0.75, 0.60, 0.77, 0.70, 0.66])
    blocks = np.repeat([0, 1, 2, 3], 2)

    cmp = home_term.bootstrap.paired(won, claimed, blocks)

    assert 100 * cmp.delta == pytest.approx(
        (won.mean() - claimed.mean()) * 100)
    assert cmp.ci[0] <= cmp.delta <= cmp.ci[1]


def test_the_scored_mask_drops_exactly_the_burn_in_seasons():
    """The §9.5 population. If this drifts, every gap in §9.6 is measured on a
    different set of matches from the one it is compared against."""
    seasons = ["201112", "201213", "201314", "201415", "201516"]
    frame = pd.DataFrame({"season": np.repeat(seasons, 3)})

    mask = home_term.scored_mask(frame)

    assert not mask[frame.season.isin(seasons[:home_term.BURN_IN_SEASONS])].any()
    assert mask[frame.season.isin(seasons[home_term.BURN_IN_SEASONS:])].all()


def test_the_slope_recovers_a_planted_one():
    """`slope_ci` replaced a five-point polyfit that carried no interval. A
    slope estimator that cannot recover a known slope is not an improvement."""
    rng = np.random.default_rng(11)
    n = 4000
    d = rng.normal(0.1, 0.19, n)
    gap = 6.0 * d + rng.normal(0, 3.0, n)
    blocks = np.repeat(np.arange(n // 20), 20)

    slope, (lo, hi) = home_term.slope_ci(d, gap, blocks, reps=200)

    assert slope == pytest.approx(6.0, abs=0.8)
    assert lo < 6.0 < hi


# --- step 4, the controls (SEPARATION_SLOPE.md §8 item 1) ------------------


def _control_frame(n=3000, seed=5):
    """A frame with the columns step 4 reads, and a deliberately wrong `ftr`."""
    rng = np.random.default_rng(seed)
    lam_h = np.exp(rng.normal(0.30, 0.30, n))
    lam_a = np.exp(rng.normal(0.10, 0.30, n))
    return pd.DataFrame({
        "season": np.repeat(["201213", "201314", "201415", "201516",
                             "201617", "201718"], n // 6),
        "match_date": pd.to_datetime("2014-01-01")
                      + pd.to_timedelta(np.repeat(np.arange(n // 10) * 7, 10), "D"),
        "lam_h": lam_h, "lam_a": lam_a,
        # Every match a home win. If any step-4 number moves when this changes,
        # the control is reading a real outcome and its licence is void.
        "ftr": np.full(n, "H"),
    })


def test_the_seed_streams_never_collide():
    """§1.9's seed collision made a reference arm an exact oracle and the only
    symptom was an incoherent control. Distinct purposes must never share a
    stream."""
    draws = [home_term._rng(kind, draw, extra).normal(size=8)
             for kind in (0, 1, 2) for draw in (0, 1) for extra in (0, 1)]

    for i, a in enumerate(draws):
        for b in draws[i + 1:]:
            assert not np.allclose(a, b)


def test_simulated_outcomes_follow_the_lambdas_that_made_them():
    """Null A is only a null if the resampler actually draws from the head's own
    distribution. If it does not, a zero slope proves nothing."""
    rng = np.random.default_rng(3)
    lam_h = np.full(20000, 1.55)
    lam_a = np.full(20000, 1.15)

    ftr = home_term.simulate_ftr(lam_h, lam_a, rng)
    expected = home_term.outcome_probs(home_term.score_matrix(lam_h, lam_a))

    assert (ftr == "H").mean() == pytest.approx(expected[0].mean(), abs=0.02)
    assert (ftr == "D").mean() == pytest.approx(expected[1].mean(), abs=0.02)


def test_the_null_control_returns_a_zero_slope():
    """The load-bearing property. Step 2's +5.66 is a finding only if a head
    whose lambda -> outcome mapping is correct by construction produces none."""
    frame = _control_frame()
    scored = home_term.scored_mask(frame)
    lam_h = frame.lam_h.to_numpy()[scored]
    lam_a = frame.lam_a.to_numpy()[scored]
    _, d = home_term.separation(lam_h, lam_a)
    probs = np.column_stack(
        home_term.outcome_probs(home_term.score_matrix(lam_h, lam_a)))

    slopes = [home_term._leg_slope(
        d, home_term.simulate_ftr(lam_h, lam_a, home_term._rng(0, i)),
        probs, "H", 0) for i in range(12)]

    assert np.mean(slopes) == pytest.approx(0.0, abs=2.0)


def test_lambda_noise_biases_the_separation_slope_negative():
    """The P0-1 sweep's whole point, planted. Noise in the stratifying lambda
    must push the home slope DOWN -- that is what makes it incapable of
    manufacturing step 2's positive result."""
    frame = _control_frame()
    scored = home_term.scored_mask(frame)
    lam_h = frame.lam_h.to_numpy()[scored]
    lam_a = frame.lam_a.to_numpy()[scored]
    ftr = home_term.simulate_ftr(lam_h, lam_a, home_term._rng(1, 0))

    def slope_at(sigma, seed):
        eps = np.random.default_rng(seed)
        noisy_h = lam_h * np.exp(eps.normal(0.0, sigma, len(lam_h)))
        noisy_a = lam_a * np.exp(eps.normal(0.0, sigma, len(lam_a)))
        _, d_hat = home_term.separation(noisy_h, noisy_a)
        probs = np.column_stack(
            home_term.outcome_probs(home_term.score_matrix(noisy_h, noisy_a)))
        return home_term._leg_slope(d_hat, ftr, probs, "H", 0)

    clean = slope_at(0.0, 7)
    noisy = slope_at(0.20, 7)

    assert noisy < clean
    assert noisy < -5.0, "the bias must be large enough to be the P0-1 trap"


def test_the_away_leg_ledger_row_carries_one_entry_per_arm():
    """`count_configurations` sums `len(arms)`, so handing it every reported
    cell would book 30 configurations for a gate that ran three arms. This is
    the guard on the accounting, not on the statistics."""
    slopes = [{"arm": arm, "leg": leg, "population": pop, "slope": 1.0,
               "excludes_zero": False}
              for arm in ("raw (shipped)", "B2 calibrated", "sham (control)")
              for leg in ("home", "away")
              for pop in home_term.POPULATIONS]

    arms = home_term.away_leg_arms({"slopes": slopes})

    assert len(arms) == 3
    assert {a["arm"] for a in arms} == {"raw (shipped)", "B2 calibrated",
                                        "sham (control)"}
    assert all(a["leg"] == "away" for a in arms)


def test_a_division_null_sd_is_wider_than_the_pooled_one(monkeypatch):
    """Why step 4's pooled figure cannot be reused per division: E0 is a fifth
    of the corpus, so its null spread is much wider and a sigma reading built on
    the pooled sd would overstate every division cell."""
    monkeypatch.setattr(home_term, "NULL_SD_DRAWS", 25)
    frame = _control_frame(n=3000)
    frame = frame.assign(division=np.tile(["E0", "E1", "E2", "E3"], 750))
    scored = home_term.scored_mask(frame)

    null_sd = home_term.null_sd_by_population(frame, scored)

    for div in ("E0", "E1", "E2", "E3"):
        assert null_sd[div]["home"] > null_sd["pooled"]["home"]
        assert null_sd[div]["away"] > null_sd["pooled"]["away"]


def test_the_null_sd_reads_no_real_match_outcome(monkeypatch):
    """Step 5 reads real outcomes for its slopes and is costed for them, but the
    yardstick it reads them against must not -- or the control is contaminated
    by the thing it is controlling."""
    monkeypatch.setattr(home_term, "NULL_SD_DRAWS", 15)
    frame = _control_frame(n=1200)
    frame = frame.assign(division=np.tile(["E0", "E1", "E2", "E3"], 300))
    scored = home_term.scored_mask(frame)
    corrupted = frame.assign(ftr=np.full(len(frame), "A"))

    assert (home_term.null_sd_by_population(frame, scored)
            == home_term.null_sd_by_population(corrupted, scored))


def test_bonferroni_widens_the_interval():
    """§6's correction, threaded through `slope_ci`'s alpha. If it did not
    widen, the survives/lost verdict would be meaningless."""
    rng = np.random.default_rng(19)
    n = 3000
    d = rng.normal(0.1, 0.19, n)
    gap = 6.0 * d + rng.normal(0, 30.0, n)
    blocks = np.repeat(np.arange(n // 20), 20)

    _, (lo, hi) = home_term.slope_ci(d, gap, blocks, reps=200)
    _, (blo, bhi) = home_term.slope_ci(
        d, gap, blocks, reps=200, alpha=0.05 / home_term.BONFERRONI_CELLS)

    assert blo < lo and bhi > hi


def test_curvature_recovers_a_planted_quadratic():
    """The whole of step 6 rests on this coefficient meaning what it says."""
    rng = np.random.default_rng(23)
    n = 20000
    d = rng.normal(0.1, 0.19, n)
    dc = d - d.mean()
    gap = 4.0 * dc + 30.0 * dc**2 + rng.normal(0, 2.0, n)

    lin, quad = home_term.curvature(d, gap)

    assert lin == pytest.approx(4.0, abs=0.5)
    assert quad == pytest.approx(30.0, abs=3.0)


def test_curvature_is_zero_on_a_flat_gap():
    """Under a correct mapping the gap has no structure in d at all, so both
    coefficients must vanish -- otherwise C1 could never be a null."""
    rng = np.random.default_rng(29)
    d = rng.normal(0.1, 0.19, 20000)
    gap = rng.normal(0, 40.0, 20000)

    lin, quad = home_term.curvature(d, gap)

    assert lin == pytest.approx(0.0, abs=3.0)
    assert quad == pytest.approx(0.0, abs=20.0)


def test_a_stretch_of_one_leaves_the_planted_truth_alone():
    """C2's level 1.0 must be C1. If it is not, the shrinkage family does not
    start from the null and its levels are not interpretable."""
    lh, la = home_term._shrunk_truth(LAM_H, LAM_A, 1.0)

    assert lh == pytest.approx(LAM_H)
    assert la == pytest.approx(LAM_A)


def test_the_planted_step_touches_only_the_top_quintile():
    """C3 is a TAIL effect by construction. If it leaks into the rest of the
    distribution it is a gradient and the two controls stop being distinct."""
    rng = np.random.default_rng(31)
    lam_h = np.exp(rng.normal(0.30, 0.30, 5000))
    lam_a = np.exp(rng.normal(0.10, 0.30, 5000))
    _, d = home_term.separation(lam_h, lam_a)
    top = d >= np.quantile(d, home_term.TOP_QUINTILE)

    out_h, out_a = home_term._stepped_truth(lam_h, lam_a, 3.0)

    assert out_h[~top] == pytest.approx(lam_h[~top])
    assert out_a[~top] == pytest.approx(lam_a[~top])
    assert (out_h[top] > lam_h[top]).all()
    assert (out_a[top] < lam_a[top]).all()


def test_the_linearity_controls_read_no_real_match_outcome(monkeypatch):
    """Step 6 is a probe at 0 configurations and that licence rests on it never
    touching a result. Same discipline as step 4."""
    monkeypatch.setattr(home_term, "NULL_DRAWS", 3)
    monkeypatch.setattr(home_term, "MECHANISM_DRAWS", 2)
    monkeypatch.setattr(home_term, "CONTROL_REPS", 40)
    monkeypatch.setattr(home_term, "SHRINK_LEVELS", (1.10,))
    monkeypatch.setattr(home_term, "STEP_LEVELS", (3.0,))
    frame = _control_frame()
    scored = home_term.scored_mask(frame)
    corrupted = frame.assign(ftr=np.full(len(frame), "A"))

    assert (home_term.step6(frame, scored)
            == home_term.step6(corrupted, scored))


def test_a_stretch_of_one_leaves_goal_deviance_alone():
    """s = 1 must price identically to the shipped head, or every delta in step
    7 is measured against a baseline that is already perturbed."""
    rng = np.random.default_rng(37)
    n = 500
    lam_h = np.exp(rng.normal(0.30, 0.30, n))
    lam_a = np.exp(rng.normal(0.10, 0.30, n))
    goals_h = rng.poisson(lam_h).astype(float)
    goals_a = rng.poisson(lam_a).astype(float)
    _, d = home_term.separation(lam_h, lam_a)

    stretched = home_term._stretched_deviance(
        lam_h, lam_a, float(d.mean()), goals_h, goals_a, 1.0)
    plain = home_term.metrics.goal_deviance(pd.DataFrame({
        "lam_h": lam_h, "lam_a": lam_a, "fthg": goals_h, "ftag": goals_a}))

    assert np.asarray(stretched) == pytest.approx(np.asarray(plain))


def test_the_zeroing_stretch_recovers_a_planted_under_dispersion():
    """The load-bearing property of step 7. If the head's separation is a factor
    `s` too small, the stretch that zeroes the slope must be about `s` -- fitted
    on the SLOPE, with no reference to goal deviance anywhere."""
    rng = np.random.default_rng(41)
    n = 30000
    lam_h = np.exp(rng.normal(0.30, 0.32, n))
    lam_a = np.exp(rng.normal(0.10, 0.32, n))
    _, d = home_term.separation(lam_h, lam_a)
    d_bar = float(d.mean())

    planted = 1.15
    truth_h, truth_a = home_term.stretch(lam_h, lam_a, planted, d_bar)
    ftr = home_term.simulate_ftr(truth_h, truth_a, np.random.default_rng(43))

    found = home_term.zeroing_stretch(lam_h, lam_a, d, d_bar, ftr, "H", 0)

    assert found == pytest.approx(planted, abs=0.04)


def test_the_zeroing_stretch_actually_zeroes_the_slope():
    """Round trip: whatever it returns must leave no slope behind."""
    rng = np.random.default_rng(47)
    n = 20000
    lam_h = np.exp(rng.normal(0.30, 0.32, n))
    lam_a = np.exp(rng.normal(0.10, 0.32, n))
    _, d = home_term.separation(lam_h, lam_a)
    d_bar = float(d.mean())
    truth_h, truth_a = home_term.stretch(lam_h, lam_a, 1.12, d_bar)
    ftr = home_term.simulate_ftr(truth_h, truth_a, np.random.default_rng(53))

    s = home_term.zeroing_stretch(lam_h, lam_a, d, d_bar, ftr, "H", 0)
    probs = home_term._stretched_probs(lam_h, lam_a, d_bar, s)

    assert home_term._leg_slope(d, ftr, probs, "H", 0) == pytest.approx(0.0, abs=0.05)


def test_the_controls_read_no_real_match_outcome(monkeypatch):
    """`SEPARATION_SLOPE.md` §8 item 1 prices both controls at 0 configurations,
    and that licence rests on them never touching a result. Corrupting every
    real outcome in the frame must leave every number identical -- the
    `drop_outcomes` discipline `META.md` §1 uses, as a property of the data
    rather than a claim about the code."""
    monkeypatch.setattr(home_term, "NULL_DRAWS", 3)
    monkeypatch.setattr(home_term, "SWEEP_DRAWS", 2)
    monkeypatch.setattr(home_term, "CONTROL_REPS", 40)
    frame = _control_frame()
    scored = home_term.scored_mask(frame)
    corrupted = frame.assign(ftr=np.full(len(frame), "A"))

    honest = home_term.step4(frame, scored)
    against = home_term.step4(corrupted, scored)

    assert honest == against
