"""B24 probe instrument, on planted data only.

Nothing here reads the database: the slip machinery is handed arrays whose
truth is known -- independent outcomes must read no gap, and the planted
dependent pair must read the positive gap its arithmetic implies, or the
instrument could not see the defect it exists to find.
"""

from __future__ import annotations

import numpy as np
import pytest

from engine.eval.b24 import cell, dependent_control, slip_table


def _days(n_days, legs_per_day, seed=0):
    """Planted corpus: `legs_per_day` calls a day, claims 0.60-0.90."""
    rng = np.random.default_rng(seed)
    dates = np.repeat(np.datetime64("2020-01-04") + 7 * np.arange(n_days),
                      legs_per_day).astype("datetime64[D]").astype(str)
    claims = rng.uniform(0.60, 0.90, size=n_days * legs_per_day)
    return dates, claims, rng


def test_the_slip_is_the_pages_selection():
    dates = ["2020-01-04"] * 4
    claims = [0.9, 0.8, 0.7, 0.6]
    won = [1.0, 1.0, 0.0, 1.0]
    two = slip_table(dates, claims, won, k=2, r=0.0)
    assert len(two) == 1
    assert two.claimed.iloc[0] == pytest.approx(0.72)
    assert two.hit.iloc[0] == 1.0            # both top legs won
    three = slip_table(dates, claims, won, k=3, r=0.0)
    assert three.claimed.iloc[0] == pytest.approx(0.504)
    assert three.hit.iloc[0] == 0.0          # the 0.7 leg lost
    # The threshold selects before the cut, exactly as the page does.
    assert slip_table(dates, claims, won, k=2, r=0.75).claimed.iloc[0] == pytest.approx(0.72)


def test_a_day_short_of_legs_contributes_nothing():
    dates = ["2020-01-04"] * 2
    claims, won = [0.9, 0.8], [1.0, 1.0]
    assert slip_table(dates, claims, won, k=3, r=0.0).empty
    assert slip_table(dates, claims, won, k=2, r=0.85).empty   # one clears
    # The full-day slip needs at least two qualifying legs.
    assert slip_table(["2020-01-04"], [0.9], [1.0], k=None, r=0.0).empty
    assert len(slip_table(dates, claims, won, k=None, r=0.0)) == 1


def test_independent_planted_outcomes_read_no_gap():
    dates, claims, rng = _days(500, 6, seed=11)
    won = (rng.uniform(size=len(claims)) < claims).astype(float)
    slips = slip_table(dates, claims, won, k=3, r=0.0)
    assert len(slips) == 500
    read = cell(slips)
    assert abs(read["gap"]) < 0.04
    assert not read["excludes_zero"]


def test_the_planted_dependent_pair_fires():
    """The control: the same match twice claims p^2 but delivers p, so the
    gap must read ~= mean p(1-p), resolved positive."""
    dates, claims, rng = _days(500, 6, seed=7)
    won = (rng.uniform(size=len(claims)) < claims).astype(float)
    ctl = dependent_control(dates, claims, won, r=0.0)
    assert ctl["fired"] is True
    assert ctl["gap"] == pytest.approx(ctl["expected"], abs=0.03)


def test_groups_split_a_date_without_losing_its_week_block():
    """The division split slips within division-day; the date column stays
    the real date so the bootstrap still blocks by week."""
    dates = ["2020-01-04"] * 4
    groups = ["E0|2020-01-04", "E0|2020-01-04", "E1|2020-01-04", "E1|2020-01-04"]
    claims, won = [0.9, 0.8, 0.7, 0.6], [1.0, 1.0, 1.0, 0.0]
    slips = slip_table(dates, claims, won, k=2, r=0.0, groups=groups)
    assert len(slips) == 2
    assert list(slips.claimed.round(3)) == [0.72, 0.42]
    assert list(slips.hit) == [1.0, 0.0]
    assert set(slips.date) == {"2020-01-04"}
