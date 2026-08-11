"""The draw-mass diagnostic, OUTSTANDING.md §9.1.

Two classes of property here. The first pins what P0-2's surviving argument
actually claims -- tau cannot move O/U 2.5 -- so that a later change which
quietly breaks it is caught rather than argued about. The second pins the
direction the whole §9.1 re-review rests on: a negative rho moves draw mass in
and `12` mass out. If those ever flip, the write-up is wrong rather than stale.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from engine.eval import draws
from engine.eval.dispersion import outcome_probs, over_under_probs, score_matrix

LAM_H = np.array([1.6, 1.2, 2.1, 0.9])
LAM_A = np.array([1.1, 1.4, 0.8, 1.3])


def frame(rho_seasons=None):
    n = len(LAM_H)
    return pd.DataFrame({
        "lam_h": LAM_H, "lam_a": LAM_A,
        "fthg": [1, 0, 2, 1], "ftag": [1, 1, 0, 2],
        "ftr": ["D", "A", "H", "A"],
        "season": rho_seasons or ["201112"] * n,
        "division": ["E0", "E1", "E0", "E1"],
    })


def test_the_grouped_path_reproduces_the_scalar_one_at_rho_zero():
    """`joint_with` exists only to allow a per-match rho. At rho 0 it must be
    the shipped pmf exactly, or the diagnostic is measuring its own plumbing."""
    got = draws.joint_with(frame(), np.zeros(len(LAM_H)))

    assert got == pytest.approx(score_matrix(LAM_H, LAM_A))


def test_the_grouped_path_reproduces_the_scalar_one_per_group():
    rho = np.array([-0.02, -0.02, -0.05, -0.05])
    got = draws.joint_with(frame(), rho)

    assert got[:2] == pytest.approx(score_matrix(LAM_H[:2], LAM_A[:2], -0.02))
    assert got[2:] == pytest.approx(score_matrix(LAM_H[2:], LAM_A[2:], -0.05))


def test_tau_cannot_move_an_over_under_2_5_probability():
    """P0-2's reason 2, and the one argument the tipster re-review did not
    overturn. The four cells tau touches total 0, 1, 1 and 2, all under the
    line, and its adjustments sum to zero across them."""
    base, _ = over_under_probs(score_matrix(LAM_H, LAM_A), line=2.5)
    shifted, _ = over_under_probs(score_matrix(LAM_H, LAM_A, -0.05), line=2.5)

    assert shifted == pytest.approx(base, abs=1e-12)


@pytest.mark.parametrize("line", [0.5, 1.5])
def test_tau_does_move_the_lines_b4_wants_to_publish(line):
    """The other half of §9.1: the same argument fails on every goal line whose
    cells tau does not straddle symmetrically."""
    base, _ = over_under_probs(score_matrix(LAM_H, LAM_A), line=line)
    shifted, _ = over_under_probs(score_matrix(LAM_H, LAM_A, -0.05), line=line)

    assert np.all(np.abs(shifted - base) > 1e-6)


def test_a_negative_rho_raises_the_draw_and_lowers_the_twelve():
    """The direction the product cares about. `12` loses if and only if the
    match is a draw, so these are the same statement seen twice."""
    plain = np.column_stack(outcome_probs(score_matrix(LAM_H, LAM_A)))
    tau = np.column_stack(outcome_probs(score_matrix(LAM_H, LAM_A, -0.05)))

    assert np.all(tau[:, 1] > plain[:, 1]), "draw mass rises"
    assert np.all(draws.market_probs(tau)["12"]
                  < draws.market_probs(plain)["12"]), "'12' falls by as much"


def test_the_three_union_gaps_sum_to_zero():
    """`1X`, `X2` and `12` count every outcome exactly twice, so their
    calibration gaps are not three independent numbers. This is why the
    outcome-level decomposition exists: a union table read alone will attribute
    to the draw an error that belongs to the away win."""
    probs = np.array([[0.45, 0.27, 0.28], [0.30, 0.30, 0.40]])
    markets = draws.market_probs(probs)

    assert sum(markets[m] for m in draws.UNION_MARKETS) == pytest.approx(2.0)


def test_walk_forward_rho_never_sees_the_season_it_prices():
    """The leakage guard. A rho fitted on the season it corrects would make the
    diagnostic report an in-sample fit as an out-of-sample improvement."""
    seasons = ["201112", "201213", "201314", "201415"]
    f = pd.concat([frame([s] * len(LAM_H)) for s in seasons], ignore_index=True)

    rho = draws.walk_forward_rho(f, by_division=False)

    burned = f.season.isin(seasons[:draws.BURN_IN_SEASONS]).to_numpy()
    assert np.all(np.isnan(rho[burned])), "no rho before the burn-in is over"
    assert np.all(np.isfinite(rho[~burned])), "and one for every season after"


def test_the_planted_control_is_inside_the_positivity_bound():
    """A planted rho that makes tau negative would produce negative
    probabilities and a control that fails for the wrong reason."""
    joint = score_matrix(LAM_H, LAM_A, draws.PLANTED_RHO)

    assert np.all(joint >= 0.0)
    assert joint.sum(axis=(1, 2)) == pytest.approx(1.0, abs=1e-6)
