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
