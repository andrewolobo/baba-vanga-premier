"""B21: the dog +1.5 fallback candidate, on planted data.

The arm extends the shipped fallback stack by one candidate, so the tests pin:
the settlement of the new market (both favourite sides), that every difference
from the shipped rule is a fallback pick becoming DOG15, that the ceiling still
vetoes it, and that on a calibrated simulation the realised paired delta
tracks the implied one.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from engine.eval import b21, selection
from engine.eval.dispersion import outcome_probs, score_matrix
from tests.test_p7 import simulate


def probs(rows):
    return np.array(rows, dtype=float)


def frame_of(scores, fav_home):
    """Planted matches with the favourite on the stated side."""
    fthg, ftag = zip(*scores)
    ftr = ["H" if h > a else "A" if h < a else "D" for h, a in scores]
    return pd.DataFrame({"fthg": fthg, "ftag": ftag, "ftr": ftr}), np.array(
        [[0.5, 0.2, 0.3] if fh else [0.3, 0.2, 0.5] for fh in fav_home])


def test_dog15_wins_unless_the_favourite_wins_by_two():
    # Home favourite: away is the dog. 2-0 and 3-1 lose; 1-0, 0-0, 0-1 win.
    frame, p = frame_of([(2, 0), (3, 1), (1, 0), (0, 0), (0, 1)], [True] * 5)
    market = np.array([b21.DOG15] * 5)
    assert list(b21.won(market, frame, p)) == [False, False, True, True, True]
    # Away favourite: home is the dog. 0-2 loses; 0-1, 1-1, 2-0 win.
    frame, p = frame_of([(0, 2), (0, 1), (1, 1), (2, 0)], [False] * 4)
    market = np.array([b21.DOG15] * 4)
    assert list(b21.won(market, frame, p)) == [False, True, True, True]


def test_dog15_probability_is_one_minus_fav_by_two():
    lam_h = np.array([1.8, 0.9])
    lam_a = np.array([1.0, 1.6])   # home favourite, then away favourite
    joint = score_matrix(lam_h, lam_a)
    p = np.column_stack(outcome_probs(joint))
    got = b21.dog15_probs(joint, p)
    n = joint.shape[1]
    margin = np.arange(n)[:, None] - np.arange(n)[None, :]
    assert np.isclose(got[0], 1.0 - joint[0][margin >= 2].sum())
    assert np.isclose(got[1], 1.0 - joint[1][margin <= -2].sum())


def test_every_difference_from_the_shipped_rule_is_a_fallback_pick_becoming_dog15():
    rng = np.random.default_rng(4)
    raw = rng.dirichlet((4, 3, 3), size=3000)
    p_dog15 = np.clip(raw[:, [0, 2]].max(axis=1) + rng.uniform(0, 0.4, 3000), 0, 0.99)
    base, _ = selection.recommend(raw, selection.SHIPPED_FLOOR, allow_12=True)
    market, _ = b21.recommend(raw, p_dog15)
    moved = market != base
    assert (market[moved] == b21.DOG15).all()
    assert (np.isin(base[moved], ["1X", "X2", "12"])).all(), "outrights untouched"


def test_the_ceiling_still_vetoes_dog15():
    # Fallback reached (fav 0.50 < 0.55). dog +1.5 at 0.90 breaches 0.85, so
    # the shipped pick (12 = 0.80) stands; at 0.84 it is taken.
    p = probs([(0.50, 0.20, 0.30), (0.50, 0.20, 0.30)])
    market, prob = b21.recommend(p, np.array([0.90, 0.84]))
    assert list(market) == ["12", b21.DOG15]
    assert np.allclose(prob, [0.80, 0.84])


def test_on_a_calibrated_simulation_the_realised_delta_tracks_the_implied_one():
    frame = simulate(n=6000)
    joint = score_matrix(frame.lam_h.to_numpy(float), frame.lam_a.to_numpy(float))
    p = np.column_stack(outcome_probs(joint))
    p_dog15 = b21.dog15_probs(joint, p)
    out = b21.gate(frame, p, p_dog15)
    _, base_p = selection.recommend(p, selection.SHIPPED_FLOOR, allow_12=True)
    _, arm_p = b21.recommend(p, p_dog15)
    implied = float((arm_p - base_p).mean())
    assert out["vs_shipped_ci"][0] <= out["vs_shipped"] <= out["vs_shipped_ci"][1]
    assert abs(out["vs_shipped"] - implied) < 0.02
