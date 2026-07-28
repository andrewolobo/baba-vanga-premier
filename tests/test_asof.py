"""The leak canary must catch a feature that reads the future, and must clear
one that does not.

A canary that only ever passes is worse than none, so the leaky-feature case is
tested as carefully as the clean one.
"""

from __future__ import annotations

import pandas as pd
import pytest

from engine.asof import (
    AsOf,
    InformationSet,
    assert_no_future_dependence,
    corrupt_future,
    feature,
    player_seasons_visible_at,
    unknowable_columns,
)

CUTOFF = AsOf(pd.Timestamp("2011-01-01"), InformationSet.PRE_CLOSE)


@pytest.fixture
def frame():
    return pd.DataFrame(
        {
            "match_id": [f"m{i}" for i in range(6)],
            "match_date": pd.to_datetime(
                ["2010-09-01", "2010-10-01", "2010-11-01",
                 "2011-02-01", "2011-03-01", "2011-04-01"]
            ),
            "home_team": ["A", "B", "A", "B", "A", "B"],
            "fthg": pd.array([1, 2, 0, 3, 1, 2], dtype="Int64"),
            "ftag": pd.array([0, 1, 0, 1, 2, 2], dtype="Int64"),
            "ftr": ["H", "H", "D", "H", "A", "D"],
            "close_ps_h": [1.8, 2.0, 2.5, 1.6, 3.0, 2.2],
        }
    )


# --- a clean feature clears the canary ------------------------------------


@feature("mean_goals_before_cutoff", InformationSet.PRE_CLOSE)
def mean_goals_before_cutoff(frame: pd.DataFrame, asof: AsOf) -> float:
    past = frame[~asof.is_future(frame["match_date"])]
    return float(past["fthg"].sum())


def test_clean_feature_passes(frame):
    assert_no_future_dependence(mean_goals_before_cutoff, frame, CUTOFF)


def test_declaration_is_recorded():
    spec = mean_goals_before_cutoff.spec
    assert spec.name == "mean_goals_before_cutoff"
    assert spec.information_set is InformationSet.PRE_CLOSE


# --- a leaky feature is caught --------------------------------------------


def leaky_total_goals(frame: pd.DataFrame, asof: AsOf) -> float:
    """Sums the whole column, including matches that have not been played."""
    return float(frame["fthg"].sum())


def leaky_closing_price(frame: pd.DataFrame, asof: AsOf) -> float:
    """Reads the closing price of a match not yet played -- the pre-close
    information set cannot see it (SPEC §4.1)."""
    future = frame[asof.is_future(frame["match_date"])]
    return float(future["close_ps_h"].mean())


@pytest.mark.parametrize("fn", [leaky_total_goals, leaky_closing_price])
def test_leaky_features_are_caught(frame, fn):
    with pytest.raises(AssertionError, match="reading the future"):
        assert_no_future_dependence(fn, frame, CUTOFF)


def test_closing_price_is_visible_to_the_closing_information_set(frame):
    """The same feature is legitimate at the closing timestamp. The rule is
    about the information set, not about the column."""
    at_close = AsOf(CUTOFF.moment, InformationSet.CLOSING)
    assert_no_future_dependence(leaky_closing_price, frame, at_close)


# --- the canary refuses to pass vacuously ---------------------------------


def test_corruption_with_no_future_rows_raises(frame):
    late = AsOf(pd.Timestamp("2030-01-01"), InformationSet.PRE_CLOSE)
    with pytest.raises(ValueError, match="vacuously"):
        corrupt_future(frame, late)


def test_corruption_actually_changes_values(frame):
    corrupted = corrupt_future(frame, CUTOFF, seed=0)
    future = CUTOFF.is_future(frame["match_date"])
    assert not corrupted.loc[future, "fthg"].equals(frame.loc[future, "fthg"])
    # Fixture identity survives: the fixture list genuinely is known in advance.
    assert corrupted["home_team"].equals(frame["home_team"])
    assert corrupted["match_date"].equals(frame["match_date"])
    # The past is untouched.
    assert corrupted.loc[~future, "fthg"].equals(frame.loc[~future, "fthg"])


# --- information sets differ ----------------------------------------------


def test_pre_close_cannot_see_closing_prices():
    pre = unknowable_columns(InformationSet.PRE_CLOSE)
    close = unknowable_columns(InformationSet.CLOSING)
    assert "close_ps_h" in pre
    assert "close_ps_h" not in close
    assert "fthg" in pre and "fthg" in close


# --- the player-layer season rule -----------------------------------------


def test_player_data_stops_at_the_previous_season():
    """OPEN-1 resolved to per-season aggregates, so a prediction in season N may
    read files up to N-1 only; season N's file is embargoed whole."""
    visible = player_seasons_visible_at("202526")
    assert "202425" in visible
    assert "202526" not in visible
    assert player_seasons_visible_at("201011") == ()
