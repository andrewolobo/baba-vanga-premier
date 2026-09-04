"""B24 market-legs probe instrument, on planted data only.

The leg rule and the calibration read are pinned against arrays whose truth
is known; the planted over-claim must be visible or the instrument could
not find the defect it exists to find.
"""

from __future__ import annotations

import numpy as np
import pytest

from engine.eval import b21
from engine.eval.b24_market import calibration, type_leg


def _match(ph, pd_, pa):
    return [ph, pd_, pa]


PROBS = np.array([
    _match(0.60, 0.25, 0.15),   # published H (outright cleared the floor)
    _match(0.46, 0.27, 0.27),   # published D+1.5 (a fallback pick)
    _match(0.30, 0.28, 0.42),   # published 12
])
P_DOG = np.array([0.75, 0.84, 0.80])
PUB_MARKET = np.array(["H", b21.DOG15, "12"])
PUB_P = np.array([0.60, 0.84, 0.72])


def test_the_leg_is_published_first_then_the_likeliest_of_the_type():
    side, p, derived = type_leg("win", PROBS, P_DOG, PUB_MARKET, PUB_P)
    assert list(side) == ["H", "H", "A"]          # match 1 keeps its call
    assert list(np.round(p, 2)) == [0.60, 0.46, 0.42]
    assert list(derived) == [False, True, True]

    side, p, derived = type_leg("dc", PROBS, P_DOG, PUB_MARKET, PUB_P)
    # match 1 derives (its call is the H): 1X 0.85 beats 12 0.75; match 2:
    # 1X 0.73 ties 12 0.73 and the earlier candidate wins; match 3 keeps its
    # published 12.
    assert list(side) == ["1X", "1X", "12"]
    assert list(np.round(p, 2)) == [0.85, 0.73, 0.72]
    assert list(derived) == [True, True, False]

    side, p, derived = type_leg("ah", PROBS, P_DOG, PUB_MARKET, PUB_P)
    assert list(side) == [b21.DOG15] * 3
    assert list(np.round(p, 2)) == [0.75, 0.84, 0.80]
    assert list(derived) == [True, False, True]


def test_dc_derivation_marks_published_dc_as_not_derived():
    _, _, derived = type_leg("dc", PROBS, P_DOG, PUB_MARKET, PUB_P)
    assert bool(derived[2]) is False              # the 12 was published


def _planted(seed, n=3000):
    rng = np.random.default_rng(seed)
    dates = np.repeat(np.datetime64("2020-01-04") + 7 * np.arange(n // 6),
                      6).astype("datetime64[D]").astype(str)
    claims = rng.uniform(0.4, 0.9, size=len(dates))
    won = (rng.uniform(size=len(dates)) < claims).astype(float)
    return dates, claims, won


def test_calibrated_planted_outcomes_read_no_gap():
    dates, claims, won = _planted(3)
    read = calibration(won, claims, dates)
    assert abs(read["gap"]) < 0.03
    assert not read["excludes_zero"]


def test_the_planted_over_claim_is_visible():
    """The +5-pt shift control: claims inflated by 5 pts must read a
    resolved negative gap of about -5."""
    dates, claims, won = _planted(5)
    read = calibration(won, np.clip(claims + 0.05, 0.0, 1.0), dates)
    assert read["excludes_zero"] and read["gap"] < 0
    assert read["gap"] == pytest.approx(-0.05, abs=0.02)
