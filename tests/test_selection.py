"""The recommendation rule from PRODUCT.md 3a.

This is the rule a customer sees, so its edge cases are product behaviour rather
than implementation detail. The ceiling is the part most likely to be
"simplified" later into a selector, which measurement showed makes outrights
unreachable and turns the product into a goal-line tipster.
"""

from __future__ import annotations

import numpy as np
import pytest

from engine.eval import selection


def probs(rows):
    """rows: (p_h, p_d, p_a)."""
    return np.array(rows, dtype=float)


def test_a_confident_outright_is_recommended_outright():
    market, p = selection.recommend(probs([(0.62, 0.24, 0.14)]), floor=0.55)

    assert market[0] == "H"
    assert p[0] == pytest.approx(0.62)


def test_a_weak_outright_steps_down_to_double_chance():
    market, p = selection.recommend(probs([(0.40, 0.30, 0.30)]), floor=0.55)

    assert market[0] == "1X"
    assert p[0] == pytest.approx(0.70), "double chance is the favourite plus the draw"


def test_the_away_side_steps_down_to_x2_not_1x():
    """Crossing these would publish the wrong recommendation on every away
    fixture while leaving the strike rate plausible."""
    market, _ = selection.recommend(probs([(0.25, 0.30, 0.45)]), floor=0.55)

    assert market[0] == "X2"


def test_the_ceiling_vetoes_a_near_certain_fallback():
    """A fallback that is 92% likely is not worth publishing. The rule falls
    back to the outright, which is the more informative call, rather than to
    nothing -- every match must carry a recommendation.

    Every fallback has to breach for the veto to bite, so this fixture makes 1X
    0.92, X2 0.46 and 12 0.62 -- and the ceiling is set below all three."""
    market, p = selection.recommend(probs([(0.54, 0.38, 0.08)]),
                                    floor=0.55, ceiling=0.40)

    assert market[0] == "H", "no fallback survives a 0.40 ceiling here"
    assert p[0] == pytest.approx(0.54)


def test_the_least_specific_fallback_wins_when_12_is_allowed():
    """The owner enabled `12` on 2026-08-06 knowing it takes 65% of published
    recommendations. It beats 1X whenever p_away > p_draw, which is most of the
    fallback population, so this is the shipped behaviour and not a defect."""
    frame = probs([(0.40, 0.22, 0.38)])

    with_12 = selection.recommend(frame, floor=0.55, allow_12=True)[0]
    without = selection.recommend(frame, floor=0.55, allow_12=False)[0]

    assert with_12[0] == "12", "0.40 + 0.38 beats 1X's 0.62"
    assert without[0] == "1X"


def test_the_ceiling_never_selects_a_market():
    """The measured failure of ceiling-as-selector: outrights become unreachable
    because wide markets sit closest under the cap. Raising the ceiling must
    never change an outright recommendation into something else."""
    frame = probs([(0.62, 0.24, 0.14), (0.40, 0.30, 0.30), (0.54, 0.38, 0.08)])

    low = selection.recommend(frame, floor=0.55, ceiling=0.70)[0]
    high = selection.recommend(frame, floor=0.55, ceiling=0.99)[0]

    assert list(low[[0]]) == list(high[[0]]) == ["H"]
    # Only the fallback may move, and only within the double-chance family.
    assert set(low) | set(high) <= {"H", "A", "1X", "X2", "12"}


def test_every_match_gets_exactly_one_recommendation():
    rng = np.random.default_rng(3)
    raw = rng.dirichlet([4.0, 3.0, 3.5], 500)

    market, p = selection.recommend(raw, floor=0.55)

    assert len(market) == len(raw) == len(p)
    assert set(market) <= {"H", "A", "1X", "X2", "12"}
    assert np.isfinite(p).all()


def test_a_lower_floor_never_produces_more_double_chance():
    """The monotonicity B3 reads its table off. If it failed, "raising the floor
    hedges more often" would be unsupported and the trade-off would not exist."""
    rng = np.random.default_rng(7)
    raw = rng.dirichlet([4.0, 3.0, 3.5], 2000)

    shares = [np.isin(selection.recommend(raw, floor=f)[0],
                      ["1X", "X2", "12"]).mean()
              for f in (0.45, 0.50, 0.55, 0.60)]

    assert shares == sorted(shares)


@pytest.mark.parametrize("market,ftr,expected", [
    ("H", "H", True), ("H", "D", False), ("A", "A", True),
    ("1X", "H", True), ("1X", "D", True), ("1X", "A", False),
    ("X2", "A", True), ("X2", "D", True), ("X2", "H", False),
    ("12", "H", True), ("12", "A", True), ("12", "D", False),
])
def test_settlement_of_each_market(market, ftr, expected):
    assert selection._won(np.array([market]), np.array([ftr]))[0] == expected
