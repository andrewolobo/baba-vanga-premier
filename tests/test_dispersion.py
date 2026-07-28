"""Validate the dispersion harness against data whose answer is known.

A measurement harness that has never been shown a case with a known answer is
an opinion generator. So: data drawn from independent Poisson must measure as
independent Poisson, and data drawn with a deliberate defect must measure as
defective. Only then is the reading on real matches worth anything.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from engine.eval import dispersion
from engine.models import poisson as poisson_model

N = 30_000
RNG = np.random.default_rng(11)


def synthetic(lam_h, lam_a, goals_h, goals_a) -> pd.DataFrame:
    ftr = np.where(goals_h > goals_a, "H", np.where(goals_h == goals_a, "D", "A"))
    return pd.DataFrame({
        "lam_h": lam_h, "lam_a": lam_a,
        "fthg": goals_h, "ftag": goals_a, "ftr": ftr,
        "division": "E0",
    })


@pytest.fixture(scope="module")
def independent_poisson():
    """Goals drawn from exactly the null the measurements test against."""
    lam_h = RNG.uniform(0.8, 2.4, N)
    lam_a = RNG.uniform(0.6, 2.0, N)
    return synthetic(lam_h, lam_a, RNG.poisson(lam_h), RNG.poisson(lam_a))


# --- the harness recovers the truth ---------------------------------------


def test_true_poisson_measures_as_unit_dispersion(independent_poisson):
    """Tolerance is 3 sd, not a guess.

    A separate 60-corpus study (scratchpad, 2026-07-28) put the estimator's
    sampling distribution at mean 1.00020 sd 0.0088 for n=30k and mean 0.99977
    sd 0.0046 for n=100k -- unbiased -- with bootstrap CI coverage 40/40 against
    a nominal 95%. Asserting `ci_low < 1.0 < ci_high` on one draw would flake
    one run in twenty by construction, so the assertion is on the point
    estimate, where the claim actually lives.
    """
    result = dispersion.measure_totals(independent_poisson, rng=np.random.default_rng(1))
    assert result.total_ratio == pytest.approx(1.0, abs=0.03)
    assert result.home_ratio == pytest.approx(1.0, abs=0.03)
    assert result.away_ratio == pytest.approx(1.0, abs=0.03)
    assert result.residual_corr == pytest.approx(0.0, abs=0.02)
    # The interval must at least bracket its own point estimate and be narrow
    # enough to discriminate the effect sizes being looked for.
    assert result.total_ci[0] <= result.total_ratio <= result.total_ci[1]
    assert result.total_ci[1] - result.total_ci[0] < 0.10


def test_true_poisson_has_no_draw_deficit(independent_poisson):
    result = dispersion.measure_draw_mass(independent_poisson, rng=np.random.default_rng(2))
    assert result.deficit_pts == pytest.approx(0.0, abs=0.6)
    assert result.deficit_ci[0] < 0.0 < result.deficit_ci[1]
    assert result.rho == pytest.approx(0.0, abs=0.03)
    for ratio in result.cells["ratio"]:
        assert ratio == pytest.approx(1.0, abs=0.10)


def test_true_poisson_has_unit_margin_dispersion(independent_poisson):
    result = dispersion.measure_margin(independent_poisson, rng=np.random.default_rng(3))
    assert result.ratio == pytest.approx(1.0, abs=0.03)
    assert result.tail_observed == pytest.approx(result.tail_expected, abs=0.3)


# --- the harness detects a planted defect ---------------------------------


def test_planted_draw_inflation_is_detected():
    """Move mass onto the diagonal and the harness must see it, with a negative
    rho -- the sign that boosts 0-0 and 1-1."""
    lam_h = RNG.uniform(0.8, 2.4, N)
    lam_a = RNG.uniform(0.6, 2.0, N)
    goals_h, goals_a = RNG.poisson(lam_h), RNG.poisson(lam_a)
    flip = (RNG.random(N) < 0.06) & (np.abs(goals_h - goals_a) == 1) & (goals_h + goals_a <= 2)
    goals_a = np.where(flip, goals_h, goals_a)

    result = dispersion.measure_draw_mass(synthetic(lam_h, lam_a, goals_h, goals_a),
                                          rng=np.random.default_rng(4))
    assert result.deficit_pts > 0.3
    assert result.deficit_ci[0] > 0.0
    assert result.rho < 0.0
    assert result.delta_logloss_1x2 < 0.0  # the correction earns its place here


def test_planted_overdispersion_is_detected():
    """Negative-binomial goals: same mean, fatter tails."""
    lam_h = RNG.uniform(0.8, 2.4, N)
    lam_a = RNG.uniform(0.6, 2.0, N)
    shape = 4.0
    goals_h = RNG.poisson(lam_h * RNG.gamma(shape, 1 / shape, N))
    goals_a = RNG.poisson(lam_a * RNG.gamma(shape, 1 / shape, N))

    result = dispersion.measure_totals(synthetic(lam_h, lam_a, goals_h, goals_a),
                                       rng=np.random.default_rng(5))
    assert result.total_ratio > 1.05
    assert result.total_ci[0] > 1.0


def test_planted_correlation_is_detected():
    """A shared match-level shock correlates the two sides' residuals."""
    lam_h = RNG.uniform(0.8, 2.4, N)
    lam_a = RNG.uniform(0.6, 2.0, N)
    shock = RNG.gamma(6.0, 1 / 6.0, N)
    result = dispersion.measure_totals(
        synthetic(lam_h, lam_a, RNG.poisson(lam_h * shock), RNG.poisson(lam_a * shock)),
        rng=np.random.default_rng(6),
    )
    assert result.residual_corr > 0.05


# --- the stratification artifact ------------------------------------------


def test_lambda_quartile_gradient_appears_under_a_pure_poisson_null():
    """Stratifying by a NOISY lambda manufactures a dispersion gradient.

    The real corpus shows dispersion falling monotonically from 1.143 in the
    lowest predicted-total quartile to 0.953 in the highest, which reads as
    "Poisson breaks down at low lambda" -- the SPEC's own hypothesis. It is an
    artifact. Matches sorted into the low bucket are disproportionately those
    whose lambda was UNDER-estimated, so they out-score their prediction and
    the ratio rises; the high bucket is the mirror image.

    This test plants exactly independent Poisson goals, stratifies on a lambda
    carrying estimation error, and asserts the gradient shows up anyway. If it
    ever stops showing up, the artifact explanation is wrong and the real
    gradient deserves another look.
    """
    rng = np.random.default_rng(4242)
    n = 24_000
    true_h = np.exp(rng.normal(np.log(1.40), 0.33, n))
    true_a = np.exp(rng.normal(np.log(1.20), 0.33, n))
    goals_h, goals_a = rng.poisson(true_h), rng.poisson(true_a)

    hat_h = true_h * np.exp(rng.normal(0, 0.20, n))
    hat_a = true_a * np.exp(rng.normal(0, 0.20, n))
    frame = synthetic(hat_h, hat_a, goals_h, goals_a)

    quartiles = pd.qcut(hat_h + hat_a, 4, labels=["Q1", "Q2", "Q3", "Q4"])
    ratios = [
        dispersion.measure_totals(frame[quartiles == q]).total_ratio
        for q in quartiles.categories
    ]
    assert ratios[0] > 1.08, "low-lambda bucket should look over-dispersed"
    assert ratios[-1] < 1.0, "high-lambda bucket should look under-dispersed"
    assert ratios[0] - ratios[-1] > 0.12, "the manufactured gradient should be large"

    # Measured without stratifying, the same data is unremarkable.
    assert dispersion.measure_totals(frame).total_ratio == pytest.approx(1.0, abs=0.05)


# --- pmf mechanics --------------------------------------------------------


def test_score_matrix_sums_to_one_with_and_without_tau():
    """Dixon-Coles tau adjustments cancel exactly across the four cells, so no
    renormalisation is needed. If that stopped holding, every probability the
    engine served would be quietly mis-scaled."""
    lam_h = np.array([1.4, 0.7, 2.2])
    lam_a = np.array([1.1, 1.9, 0.6])
    plain = dispersion.score_matrix(lam_h, lam_a)
    adjusted = dispersion.score_matrix(lam_h, lam_a, rho=-0.08)
    assert np.allclose(plain.sum(axis=(1, 2)), 1.0, atol=1e-9)
    assert np.allclose(adjusted.sum(axis=(1, 2)), 1.0, atol=1e-9)


def test_negative_rho_moves_mass_onto_the_diagonal():
    lam_h, lam_a = np.array([1.3]), np.array([1.1])
    plain = dispersion.score_matrix(lam_h, lam_a)
    adjusted = dispersion.score_matrix(lam_h, lam_a, rho=-0.10)
    assert adjusted[0, 0, 0] > plain[0, 0, 0]
    assert adjusted[0, 1, 1] > plain[0, 1, 1]
    assert adjusted[0, 0, 1] < plain[0, 0, 1]
    _, draw_plain, _ = dispersion.outcome_probs(plain)
    _, draw_adj, _ = dispersion.outcome_probs(adjusted)
    assert draw_adj[0] > draw_plain[0]


def test_outcome_and_ou_probabilities_are_coherent():
    lam_h = np.array([1.5, 0.9])
    lam_a = np.array([1.2, 1.6])
    joint = dispersion.score_matrix(lam_h, lam_a)
    home, draw, away = dispersion.outcome_probs(joint)
    over, under = dispersion.over_under_probs(joint)
    assert np.allclose(home + draw + away, 1.0, atol=1e-9)
    assert np.allclose(over + under, 1.0, atol=1e-9)


# --- the fitting instrument ------------------------------------------------


def test_poisson_fit_recovers_planted_strengths():
    """If the instrument cannot recover strengths it planted itself, the lambdas
    it feeds the measurements mean nothing."""
    rng = np.random.default_rng(21)
    n_teams, n_matches = 20, 20_000
    att = rng.normal(0, 0.35, n_teams)
    dfn = rng.normal(0, 0.25, n_teams)
    att -= att.mean()
    dfn -= dfn.mean()
    home_adv, base = 0.28, np.log(1.35)

    i = rng.integers(0, n_teams, n_matches)
    j = rng.integers(0, n_teams, n_matches)
    keep = i != j
    i, j = i[keep], j[keep]
    lam_h = np.exp(base + home_adv + att[i] + dfn[j])
    lam_a = np.exp(base + att[j] + dfn[i])

    model = poisson_model.fit(
        i, j, rng.poisson(lam_h), rng.poisson(lam_a),
        np.ones(len(i)), n_teams, alpha=0.5,
    )
    assert model.home == pytest.approx(home_adv, abs=0.05)
    assert np.corrcoef(model.att, att)[0, 1] > 0.95
    assert np.corrcoef(model.dfn, dfn)[0, 1] > 0.95
