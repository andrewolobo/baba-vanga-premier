"""B21 referee probe, on planted data.

The referee is a fit plus a read-through of the model's own pmf, so the tests
pin: the fit inverts the forward map (lambdas in, lambdas back), the referee's
D+1.5 agrees with the model's when the lambdas agree, and the calibration
instrument reads a calibrated truth as calibrated and a jittered one as
overconfident -- the planted control the probe relies on.
"""

from __future__ import annotations

import numpy as np

from engine.eval import b21, b21_referee
from engine.eval.dispersion import outcome_probs, score_matrix


def test_the_fit_inverts_the_forward_map():
    rng = np.random.default_rng(11)
    lam_h = np.exp(rng.normal(np.log(1.45), 0.35, 400))
    lam_a = np.exp(rng.normal(np.log(1.15), 0.35, 400))
    p_h, _, p_a = outcome_probs(score_matrix(lam_h, lam_a))
    got_h, got_a, residual = b21_referee.fit_market_lambdas(p_h, p_a)
    assert residual.max() < 1e-4
    assert np.allclose(got_h, lam_h, rtol=1e-2)
    assert np.allclose(got_a, lam_a, rtol=1e-2)


def test_matching_lambdas_give_a_zero_gap():
    rng = np.random.default_rng(12)
    lam_h = np.exp(rng.normal(np.log(1.4), 0.3, 200))
    lam_a = np.exp(rng.normal(np.log(1.1), 0.3, 200))
    joint = score_matrix(lam_h, lam_a)
    probs = np.column_stack(outcome_probs(joint))
    model_d15 = b21.dog15_probs(joint, probs)
    ref_probs, ref_d15 = b21_referee.referee_probs(lam_h, lam_a)
    assert np.allclose(ref_probs, probs)
    assert np.allclose(ref_d15, model_d15)


def test_the_calibration_instrument_and_its_planted_control():
    rng = np.random.default_rng(13)
    n = 20000
    lam_h = np.exp(rng.normal(np.log(1.45), 0.35, n))
    lam_a = np.exp(rng.normal(np.log(1.15), 0.35, n))
    fthg, ftag = rng.poisson(lam_h), rng.poisson(lam_a)
    _, d15 = b21_referee.referee_probs(lam_h, lam_a)
    probs = np.column_stack(outcome_probs(score_matrix(lam_h, lam_a)))
    fav_home = probs[:, 0] >= probs[:, 2]
    fav_margin = np.where(fav_home, fthg - ftag, ftag - fthg)
    won = fav_margin < 1.5
    clean = b21_referee.calibration_table(d15, won, "clean")
    assert all(r["verdict"] == "calibrated" for r in clean)
    # Jittered lambdas: same truth, sharper claims -- must read overconfident
    # in at least one high bucket, or the control is dead.
    j_h = lam_h * np.exp(rng.normal(0, 0.25, n))
    j_a = lam_a * np.exp(rng.normal(0, 0.25, n))
    _, jit = b21_referee.referee_probs(j_h, j_a)
    control = b21_referee.calibration_table(jit, won, "jittered")
    high = [r for r in control if r["bin"][0] >= 0.80]
    assert any(r["verdict"] == "overconfident" for r in high)
