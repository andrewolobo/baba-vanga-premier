"""B20: the `12`-only eligibility window, on planted probabilities.

The arm is a composition over the shipped rule, so the tests pin the two
things that matter: the shipped window is the shipped rule, and a vetoed `12`
becomes exactly what the shipped rule publishes with `12` disallowed.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from engine.eval import selection, window12
from tests.test_p7 import simulate


def probs(rows):
    return np.array(rows, dtype=float)


def test_the_shipped_window_is_the_shipped_rule():
    raw = np.random.default_rng(1).dirichlet((4, 3, 3), size=2000)
    market, p = window12.recommend(raw, *window12.ARMS[window12.SHIPPED_ARM])
    shipped_market, shipped_p = selection.recommend(raw, selection.SHIPPED_FLOOR)
    assert (market == shipped_market).all()
    assert np.allclose(p, shipped_p)


def test_a_ceiling_vetoes_the_surest_12_into_the_named_double_chance():
    # p_h 0.50, p_d 0.20, p_a 0.30: 12 = 0.80, 1X = 0.70. Under 0.85 the shipped
    # rule says 12; a 12-ceiling of 0.75 vetoes it and 1X takes over.
    frame = probs([(0.50, 0.20, 0.30)])
    market, p = window12.recommend(frame, 0.0, 0.75)
    assert market[0] == "1X" and p[0] == 0.70


def test_a_floor_vetoes_the_least_sure_12_and_keeps_the_surest():
    frame = probs([(0.42, 0.30, 0.28),    # 12 = 0.70 -> below a 0.75 floor
                   (0.50, 0.20, 0.30)])   # 12 = 0.80 -> kept
    market, _ = window12.recommend(frame, 0.75, 0.85)
    assert list(market) == ["1X", "12"]


def test_a_vetoed_12_never_falls_to_a_union_weaker_than_the_outright():
    # 1X 0.92 (breaches 0.85), X2 0.46, 12 0.62, H 0.54. With 12 vetoed the
    # only eligible union is X2 at 0.46 -- less likely than the outright it
    # would replace. `recommend(allow_12=False)` publishes it; B20 does not.
    frame = probs([(0.54, 0.38, 0.08)])
    assert selection.recommend(frame, 0.55, allow_12=False)[0][0] == "X2"
    market, p = window12.recommend(frame, 0.0, 0.60)
    assert market[0] == "H" and p[0] == 0.54


def test_outrights_and_named_unions_are_never_touched():
    raw = np.random.default_rng(2).dirichlet((4, 3, 3), size=3000)
    base, _ = window12.recommend(raw, 0.0, 0.85)
    for lo, hi in window12.ARMS.values():
        market, _ = window12.recommend(raw, lo, hi)
        moved = market != base
        assert (base[moved] == "12").all(), "only a 12 may be vetoed"


def test_the_probe_reads_no_outcome():
    frame = simulate(n=3000).drop(columns=["fthg", "ftag", "ftr"])
    probs_ = window12.probs_1x2(window12.joint_of(frame))
    out = window12.probe(probs_)
    assert set(out["arms"]) == set(window12.ARMS)
    shipped = out["arms"][window12.SHIPPED_ARM]
    assert shipped["shifted_share"] == 0.0
    assert shipped["model_implied_strike_delta"] == 0.0


def test_the_gate_pairs_every_arm_against_the_shipped_one():
    frame = simulate(n=4000)
    probs_ = window12.probs_1x2(window12.joint_of(frame))
    out = window12.gate(frame, probs_, ("ceiling 0.75",))
    shipped = out["arms"][window12.SHIPPED_ARM]
    assert shipped["vs_shipped"] == 0.0
    arm = out["arms"]["ceiling 0.75"]
    assert arm["vs_shipped_ci"][0] <= arm["vs_shipped"] <= arm["vs_shipped_ci"][1]
    # A calibrated head, simulated: the realised change tracks the implied one.
    implied = window12.probe(probs_)["arms"]["ceiling 0.75"]["model_implied_strike_delta"]
    assert abs(arm["vs_shipped"] - implied) < 0.02
