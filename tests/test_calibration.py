"""Calibration and blend fitters, checked against planted answers.

A calibrator that has never been shown a known miscalibration will happily
report that everything is fine. So: perfectly calibrated input must come back
untouched, a planted defect must be recovered, and the blend must find a model
weight of zero when the model carries nothing the market does not.
"""

from __future__ import annotations

import numpy as np
import pytest

from engine.models import calibration as cal

RNG = np.random.default_rng(31)
N = 20_000


def draw_1x2(rng, n=N):
    """Well-specified 1X2 probabilities and outcomes drawn from them."""
    raw = rng.dirichlet([4.0, 3.0, 3.0], n)
    draws = np.array([rng.choice(3, p=row) for row in raw])
    outcomes = np.array(["H", "D", "A"])[draws]
    return raw, outcomes


# --- identity on well-calibrated input -------------------------------------


def test_calibrating_already_calibrated_1x2_barely_moves_it():
    """Asserted on the MAPPING, not the coefficients.

    With per-class slopes and one bias pinned for identifiability, the
    parameterisation has near-degenerate directions: a temperature change and a
    bias shift can trade off against each other, so individual coefficients
    wander even when the function they define does not. The claim that matters
    is that calibrated output is close to input and logloss does not move.

    Note the fit legitimately chases the *sample's* observed frequencies, which
    differ from the population by a fraction of a point at this n. That is
    correct behaviour, and is why the tolerance is on the order of 0.01 rather
    than machine precision.
    """
    probs, outcomes = draw_1x2(RNG)
    fit = cal.fit_vector_scaling(probs, outcomes)
    calibrated = fit.apply(probs)

    assert np.abs(calibrated - probs).mean() < 0.01
    assert np.abs(calibrated - probs).max() < 0.05

    index = np.array([{"H": 0, "D": 1, "A": 2}[o] for o in outcomes])[:, None]
    before = -np.log(np.take_along_axis(probs, index, 1)).mean()
    after = -np.log(np.take_along_axis(calibrated, index, 1)).mean()
    assert after == pytest.approx(before, abs=0.002)


def test_calibrating_already_calibrated_binary_barely_moves_it():
    rng = np.random.default_rng(5)
    p = rng.uniform(0.15, 0.85, N)
    y = (rng.random(N) < p).astype(float)
    fit = cal.fit_platt(p, y)
    assert fit.slope == pytest.approx(1.0, abs=0.08)
    assert fit.bias == pytest.approx(0.0, abs=0.05)


# --- planted defects are recovered ----------------------------------------


def test_a_planted_draw_deficit_is_corrected():
    """The defect P0-2 actually measured: E1-E3 draw more often than an
    independent Poisson says. Calibration must lift the draw class."""
    rng = np.random.default_rng(7)
    probs, _ = draw_1x2(rng)
    truth = probs.copy()
    truth[:, 1] += 0.03                      # 3 points more draws than predicted
    truth[:, 0] -= 0.015
    truth[:, 2] -= 0.015
    truth = np.clip(truth, 1e-6, 1)
    truth /= truth.sum(axis=1, keepdims=True)
    draws = np.array([rng.choice(3, p=row) for row in truth])
    outcomes = np.array(["H", "D", "A"])[draws]

    fit = cal.fit_vector_scaling(probs, outcomes)
    calibrated = fit.apply(probs)
    assert calibrated[:, 1].mean() > probs[:, 1].mean()
    assert calibrated[:, 1].mean() == pytest.approx(truth[:, 1].mean(), abs=0.01)


def test_a_planted_overconfidence_is_flattened():
    rng = np.random.default_rng(11)
    honest = rng.uniform(0.2, 0.8, N)
    y = (rng.random(N) < honest).astype(float)
    overconfident = 1 / (1 + np.exp(-1.6 * cal.logit(honest)))   # sharpened

    fit = cal.fit_platt(overconfident, y)
    assert fit.slope < 0.9, "must flatten an over-confident forecast"
    recovered = fit.apply(overconfident)
    assert np.corrcoef(recovered, honest)[0, 1] > 0.99
    assert np.abs(recovered - honest).mean() < 0.02


def test_calibration_improves_a_miscalibrated_forecast_on_logloss():
    rng = np.random.default_rng(13)
    honest = rng.uniform(0.2, 0.8, N)
    y = (rng.random(N) < honest).astype(float)
    bad = np.clip(honest * 0.8 + 0.15, 1e-6, 1 - 1e-6)

    def logloss(p):
        return -(y * np.log(p) + (1 - y) * np.log(1 - p)).mean()

    assert logloss(cal.fit_platt(bad, y).apply(bad)) < logloss(bad)


# --- the blend, which is the decisive measurement -------------------------


def test_blend_gives_the_model_zero_weight_when_it_adds_nothing():
    """The null this whole phase tests against. If the model is pure noise on
    top of a correct market price, `model_weight` must come back at zero --
    otherwise a positive weight proves nothing."""
    rng = np.random.default_rng(17)
    market, outcomes = draw_1x2(rng)
    noise = rng.dirichlet([3.0, 3.0, 3.0], N)      # unrelated to the outcome

    fit = cal.fit_blend_1x2(noise, market, outcomes)
    assert abs(fit.model_weight) < 0.05
    assert fit.market_weight == pytest.approx(1.0, abs=0.10)


def test_blend_gives_the_model_real_weight_when_it_carries_signal():
    """The mirror image: a model that sees something the market does not must
    earn a positive weight, or the ablation cannot detect a real edge."""
    rng = np.random.default_rng(19)
    truth, outcomes = draw_1x2(rng)
    # The market sees a blurred version; the model sees the truth.
    blur = np.clip(truth + rng.normal(0, 0.05, truth.shape), 1e-6, 1)
    blur /= blur.sum(axis=1, keepdims=True)

    fit = cal.fit_blend_1x2(truth, blur, outcomes)
    assert fit.model_weight > 0.2


def test_binary_blend_recovers_a_known_weight():
    rng = np.random.default_rng(23)
    market = rng.uniform(0.2, 0.8, N)
    model = np.clip(market + rng.normal(0, 0.10, N), 0.02, 0.98)
    # Truth depends on both, with the model carrying a genuine third of it.
    z = 0.7 * cal.logit(market) + 0.35 * cal.logit(model)
    y = (rng.random(N) < 1 / (1 + np.exp(-z))).astype(float)

    fit = cal.fit_blend_binary(model, market, y)
    assert fit.model_weight == pytest.approx(0.35, abs=0.12)
    assert fit.market_weight == pytest.approx(0.70, abs=0.15)


def test_binary_blend_gives_zero_weight_to_a_useless_model():
    rng = np.random.default_rng(29)
    market = rng.uniform(0.2, 0.8, N)
    y = (rng.random(N) < market).astype(float)
    useless = rng.uniform(0.2, 0.8, N)

    fit = cal.fit_blend_binary(useless, market, y)
    assert abs(fit.model_weight) < 0.06


# --- guards ----------------------------------------------------------------


def test_too_little_data_falls_back_to_identity_rather_than_overfitting():
    probs, outcomes = draw_1x2(RNG, n=100)
    fit = cal.fit_vector_scaling(probs, outcomes)
    assert not fit.fitted
    assert np.allclose(fit.apply(probs), probs, atol=1e-9)

    binary = cal.fit_platt(np.linspace(0.2, 0.8, 100), np.zeros(100))
    assert not binary.fitted
    assert binary.apply(np.array([0.4]))[0] == pytest.approx(0.4)


def test_calibrated_probabilities_stay_coherent():
    probs, outcomes = draw_1x2(RNG)
    calibrated = cal.fit_vector_scaling(probs, outcomes).apply(probs)
    assert np.allclose(calibrated.sum(axis=1), 1.0)
    assert (calibrated > 0).all()
