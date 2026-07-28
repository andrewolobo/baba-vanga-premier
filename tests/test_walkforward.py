"""A synthetic walk-forward over a realistic feature.

The toy cases in test_asof.py prove the canary reacts. This proves it works on
the shape of feature the engine will actually carry in P1: a time-decayed
per-team attack rate, refit at each matchday, of exactly the kind that produces
a beautiful fictional backtest when it accidentally averages in results that
have not happened yet.

P0's verification criterion is "zero leakage in a synthetic walk-forward"; this
is that criterion, executed.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from engine.asof import AsOf, InformationSet, assert_no_future_dependence, feature

HALF_LIFE_DAYS = 200.0  # inside the defensible [100, 300] range of SPEC §3.2


@pytest.fixture
def season():
    """One synthetic season: 6 teams, home and away, spread across the year."""
    rng = np.random.default_rng(7)
    teams = [f"T{i}" for i in range(6)]
    rows = []
    day = pd.Timestamp("2015-08-08")
    for home in teams:
        for away in teams:
            if home == away:
                continue
            rows.append(
                {
                    "match_id": f"{home}-{away}",
                    "match_date": day,
                    "home_team": home,
                    "away_team": away,
                    "fthg": rng.integers(0, 4),
                    "ftag": rng.integers(0, 4),
                    "ftr": "H",
                    "close_ps_h": float(rng.uniform(1.5, 5.0)),
                }
            )
            day += pd.Timedelta(days=7)
    frame = pd.DataFrame(rows)
    frame["fthg"] = frame["fthg"].astype("Int64")
    frame["ftag"] = frame["ftag"].astype("Int64")
    return frame


@feature("decayed_attack_rate", InformationSet.PRE_CLOSE,
         "Exponentially decayed goals-per-match per team, from played matches only.")
def decayed_attack_rate(frame: pd.DataFrame, asof: AsOf) -> pd.Series:
    """The correct construction: filter to played matches first, then weight."""
    played = frame[~asof.is_future(frame["match_date"])]
    age_days = (asof.moment - played["match_date"]).dt.days
    weight = np.power(0.5, age_days / HALF_LIFE_DAYS)

    totals: dict[str, float] = {}
    counts: dict[str, float] = {}
    for side, goals in (("home_team", "fthg"), ("away_team", "ftag")):
        for team, value, w in zip(played[side], played[goals], weight):
            totals[team] = totals.get(team, 0.0) + float(value) * w
            counts[team] = counts.get(team, 0.0) + w
    return pd.Series(
        {team: totals[team] / counts[team] for team in sorted(totals)}, dtype=float
    )


def leaky_decayed_attack_rate(frame: pd.DataFrame, asof: AsOf) -> pd.Series:
    """The same feature with the filter forgotten -- weights are computed against
    every fixture, so unplayed matches contribute with a weight above 1."""
    age_days = (asof.moment - frame["match_date"]).dt.days
    weight = np.power(0.5, age_days / HALF_LIFE_DAYS)

    totals: dict[str, float] = {}
    counts: dict[str, float] = {}
    for side, goals in (("home_team", "fthg"), ("away_team", "ftag")):
        for team, value, w in zip(frame[side], frame[goals], weight):
            totals[team] = totals.get(team, 0.0) + float(value) * w
            counts[team] = counts.get(team, 0.0) + w
    return pd.Series(
        {team: totals[team] / counts[team] for team in sorted(totals)}, dtype=float
    )


def matchdays(frame: pd.DataFrame) -> list[pd.Timestamp]:
    """Cutoffs with matches on both sides, so no canary passes vacuously."""
    days = sorted(frame["match_date"].unique())
    return [pd.Timestamp(d) for d in days[5:-5]]


def test_walk_forward_is_leak_free_at_every_matchday(season):
    for moment in matchdays(season):
        assert_no_future_dependence(
            decayed_attack_rate, season, AsOf(moment, InformationSet.PRE_CLOSE)
        )


def test_the_same_walk_forward_catches_the_forgotten_filter(season):
    """One missing line is the whole difference between a real feature and a
    fictional one, and it is invisible in the output values alone."""
    caught = 0
    for moment in matchdays(season):
        try:
            assert_no_future_dependence(
                leaky_decayed_attack_rate, season, AsOf(moment, InformationSet.PRE_CLOSE)
            )
        except AssertionError:
            caught += 1
    assert caught == len(matchdays(season))


def test_decay_actually_discriminates_recent_from_old(season):
    """A canary-passing feature that returns a constant would also pass, so the
    feature is checked to be doing something."""
    early = decayed_attack_rate(season, AsOf(matchdays(season)[0]))
    late = decayed_attack_rate(season, AsOf(matchdays(season)[-1]))
    assert not np.allclose(early.reindex(late.index).values, late.values, equal_nan=True)
