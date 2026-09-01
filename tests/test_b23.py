"""B23: Both Teams To Score, on planted data.

The line is a marginal of the score matrix, so the tests pin: the closed form
on the independent pmf and the direction a Dixon-Coles tau moves it, the
settlement truth table, that the scan reads no outcome column, that a
calibrated head reads calibrated on both sides while a jittered one is caught
by the control, that the skill comparison sees a real head beat a base rate,
and that the base rate is walk-forward.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from engine.eval import b23
from engine.eval.dispersion import score_matrix
from tests.test_p7 import simulate


def test_btts_is_one_minus_zero_rows_plus_the_nil_nil_cell():
    lam_h = np.array([1.8, 0.9, 0.4])
    lam_a = np.array([1.0, 1.6, 0.5])
    got = b23.btts_probs(score_matrix(lam_h, lam_a))
    closed = (1 - np.exp(-lam_h)) * (1 - np.exp(-lam_a))
    assert np.allclose(got, closed, atol=1e-9)


def test_a_negative_rho_raises_btts_yes():
    """The measured rho is negative (draw_mass_results.json): tau adds mass to
    0-0 and 1-1 and takes it from 1-0 and 0-1, which nets to *less* BTTS-no.
    The pre-registration leans on this direction, so it is pinned."""
    lam_h, lam_a = np.array([1.4, 1.1]), np.array([1.1, 1.3])
    plain = b23.btts_probs(score_matrix(lam_h, lam_a))
    tau = b23.btts_probs(score_matrix(lam_h, lam_a, rho=-0.025))
    assert (tau > plain).all()
    assert (tau - plain).max() < 0.01


def test_settlement_truth_table():
    fthg = np.array([1, 1, 0, 2, 0])
    ftag = np.array([1, 0, 0, 3, 4])
    assert list(b23.btts_won(fthg, ftag)) == [True, False, False, True, False]


def test_the_scan_reads_no_outcome():
    frame = simulate(n=3000).drop(columns=["fthg", "ftag", "ftr"])
    joint = b23.joint_of(frame)
    out = b23.scan(frame, joint, b23.probs_1x2(joint))
    assert out["n"] == 3000
    assert 0.0 <= out["yes_likelier_share"] <= 1.0
    assert out["wins_v3_fallback_share"] <= out["beats_v3_claim_share"] + 1e-9


def test_a_calibrated_head_reads_calibrated_on_both_sides():
    frame = simulate(n=12000)
    p_yes = b23.btts_probs(b23.joint_of(frame))
    out = b23.calibration(frame, p_yes, "planted")
    for side in b23.SIDES:
        assert not out[side]["pooled"]["excludes_zero"], out[side]["pooled"]
        verdicts = [r["verdict"] for r in out[side]["table"] if r["n"] >= b23.MIN_BUCKET]
        assert verdicts, "a bucket must be verdictable"
        assert sum(v != "calibrated" for v in verdicts) <= 1


def test_a_jittered_head_is_caught_by_the_control():
    frame = simulate(n=20000)
    assert b23.control(frame)["passes"]


def test_the_head_beats_a_base_rate_and_matches_a_referee_at_the_truth():
    frame = simulate(n=12000)
    p_yes = b23.btts_probs(b23.joint_of(frame))
    y = b23.btts_won(frame.fthg, frame.ftag)
    base = np.full(len(frame), y.mean())
    priced = np.ones(len(frame), bool)
    out = b23.skill(frame, p_yes, base, p_yes.copy(), priced)
    assert out["base_rate"]["model_minus_base_logloss"]["delta"] < 0
    assert out["base_rate"]["model_minus_base_logloss"]["ci"][1] < 0
    assert out["referee"]["model_minus_referee_logloss"]["delta"] == 0.0
    assert out["referee"]["claim_gap"]["delta"] == 0.0


def test_the_base_rate_is_walk_forward_per_division():
    history = pd.DataFrame({
        "season": ["201011"] * 4 + ["201112"] * 4,
        "division": ["E0", "E0", "E1", "E1"] * 2,
        "fthg": [1, 0, 1, 1, 2, 2, 0, 0], "ftag": [1, 0, 1, 0, 2, 1, 0, 0]})
    frame = pd.DataFrame({"season": ["201112", "201112", "201213"],
                          "division": ["E0", "E1", "E0"]})
    got = b23.walk_forward_base_rate(history, frame)
    # E0 2011-12 sees only E0 2010-11 (1 of 2); E1 sees E1 2010-11 (1 of 2);
    # E0 2012-13 sees both E0 seasons (3 of 4).
    assert got.tolist() == pytest.approx([0.5, 0.5, 0.75])
    with pytest.raises(ValueError):
        b23.walk_forward_base_rate(history, pd.DataFrame({"season": ["201011"],
                                                          "division": ["E0"]}))


def test_the_tipster_table_is_monotone_in_coverage():
    frame = simulate(n=6000)
    p_yes = b23.btts_probs(b23.joint_of(frame))
    rows = b23.tipster(frame, p_yes)["rows"]
    coverage = [r["coverage"] for r in rows]
    assert coverage == sorted(coverage, reverse=True)
    assert coverage[0] == 1.0
