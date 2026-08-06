"""Slot classification and the slot arm, checked against planted answers.

Two properties carry the P4-TOD result. The arm must nest its own baseline
exactly, or a measured difference is a reimplementation rather than a feature
(the same assertion `test_shots_blend.py` makes for the shots channel). And the
power curve must be monotone in planted effect size, because `TOD_SLOT.md` §7
reads "underpowered" rather than "null" straight off it -- if a larger planted
effect did not come back larger, that reading would be unsupported.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from engine.eval import metrics, tod


SLOTS = ("sat_15", "sat_early", "sat_late", "sun_early", "sun_late",
         "mon_eve", "fri_eve", "midweek_eve", "holiday_15")


def frame(n: int = 600, seed: int = 3, slots=SLOTS) -> pd.DataFrame:
    """A corpus with no slot effect: lambda is independent of the slot."""
    rng = np.random.default_rng(seed)
    days = pd.Timestamp("2021-08-07") + pd.to_timedelta(
        rng.integers(0, 600, n), unit="D")
    f = pd.DataFrame({
        "match_date": days,
        "season": np.where(days < pd.Timestamp("2022-06-01"), "202122", "202223"),
        "slot": rng.choice(list(slots), n),
        "lam_h": rng.uniform(0.8, 2.2, n),
        "lam_a": rng.uniform(0.6, 1.8, n),
    })
    f["fthg"] = rng.poisson(f.lam_h)
    f["ftag"] = rng.poisson(f.lam_a)
    f["total"] = f.fthg + f.ftag
    f["expected"] = f.lam_h + f.lam_a
    return f


# --- slot classification ---------------------------------------------------


@pytest.mark.parametrize("day,kickoff,expected", [
    ("Sat", "15:00", "sat_15"),
    ("Sat", "12:30", "sat_early"),
    ("Sat", "17:30", "sat_late"),
    ("Sun", "16:30", "sun_late"),
    ("Sun", "14:00", "sun_early"),
    ("Tue", "19:45", "midweek_eve"),
    ("Mon", "20:00", "mon_eve"),
    ("Fri", "19:45", "fri_eve"),
])
def test_slots_land_where_intended(day, kickoff, expected):
    assert tod.slot_of(day, kickoff) == expected


@pytest.mark.parametrize("day", ["Mon", "Tue", "Wed", "Thu", "Fri"])
def test_weekday_three_oclock_is_the_holiday_level_not_an_evening_one(day):
    """Every weekday 15:00 date in the corpus is a public holiday -- a full
    fixture round rather than a broadcast pick. Merging it into `mon_eve` would
    pool two populations sharing nothing but a clock."""
    assert tod.slot_of(day, "15:00") == "holiday_15"
    assert tod.slot_of(day, "19:45") != "holiday_15"


def test_saturday_and_sunday_three_oclock_are_not_the_holiday_level():
    assert tod.slot_of("Sat", "15:00") == "sat_15"
    assert tod.slot_of("Sun", "15:00") == "sun_late"


# --- the arm nests its baseline -------------------------------------------


def test_pinning_every_slot_leaves_lambda_bit_for_bit_unchanged():
    """The empty slot set is the baseline, exactly. Without this, any measured
    delta could be a reimplementation of the head rather than the feature."""
    f = frame()
    lam_h, lam_a = tod.slot_arm(f, slots=set())

    assert np.array_equal(lam_h, f.lam_h.to_numpy())
    assert np.array_equal(lam_a, f.lam_a.to_numpy())


def test_a_pinned_slot_does_not_move_while_an_unpinned_one_does():
    f = frame()
    lam_h, _ = tod.slot_arm(f, slots={"sun_late"})
    pinned = (f.slot != "sun_late").to_numpy()

    assert np.array_equal(lam_h[pinned], f.lam_h.to_numpy()[pinned])
    assert not np.allclose(lam_h[~pinned], f.lam_h.to_numpy()[~pinned])


def test_factors_are_fitted_out_of_sample():
    """A season's factor must come from the other seasons. If it were fitted
    in-sample the arm could not lose, and H28 would be meaningless."""
    f = frame()
    f.loc[f.season == "202223", "fthg"] *= 3      # a huge effect in one season
    f["total"] = f.fthg + f.ftag

    lam_h, _ = tod.slot_arm(f)
    inflated = (f.season == "202223").to_numpy()
    # The inflated season is scored with factors that never saw it, so its
    # lambdas stay near the untouched baseline.
    assert np.allclose(lam_h[inflated], f.lam_h.to_numpy()[inflated], rtol=0.25)


# --- the planted control behaves --------------------------------------------


def _delta(work: pd.DataFrame) -> float:
    base = metrics.goal_deviance(work)
    lam_h, lam_a = tod.slot_arm(work)
    arm = metrics.goal_deviance(pd.DataFrame({
        "lam_h": lam_h, "lam_a": lam_a,
        "fthg": work.fthg, "ftag": work.ftag}))
    return float(arm.mean() - base.mean())


def _planted(f: pd.DataFrame, scale: float, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    work = f.copy()
    mult = work.slot.map({"sun_late": 1.0 + 0.18 * scale}).fillna(1.0)
    work["fthg"] = rng.poisson(work.lam_h.to_numpy() * mult.to_numpy())
    work["ftag"] = rng.poisson(work.lam_a.to_numpy() * mult.to_numpy())
    work["total"] = work.fthg + work.ftag
    return work


def test_a_slot_term_fitted_to_pure_noise_costs_deviance():
    """`TOD_SLOT.md` §7's x0 row: nine levels on a corpus this size cost
    +0.00112 nats before any real effect exists, which is why the measured
    -0.00067 is not read as a small win."""
    costs = [_delta(_planted(frame(n=600, seed=s), 0.0, s)) for s in range(5)]

    assert np.mean(costs) > 0, "nine levels fitted to noise should not pay"


def test_a_planted_slot_effect_grows_with_its_size():
    """The monotonicity `TOD_SLOT.md` §7 reads its verdict off. If a larger
    planted effect did not come back larger, "underpowered" would be
    unsupported and the honest reading would be that the arm is broken."""
    f = frame(n=4000, seed=9)
    deltas = [_delta(_planted(f, scale, 0)) for scale in (2.0, 4.0)]

    assert deltas[1] < deltas[0] < 0, "a bigger planted effect must come back bigger"
