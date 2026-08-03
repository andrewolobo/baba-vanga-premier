"""Scoring rules checked against values computed by hand, not by the code.

A metric module that is only tested against itself will happily be wrong by a
constant, and a constant offset is invisible in every comparison until someone
quotes an absolute figure.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from engine.eval import metrics


@pytest.fixture
def four_matches():
    return pd.DataFrame({
        "fthg": [1, 0, 2, 3],
        "ftag": [1, 2, 0, 1],
        "ftr": ["D", "A", "H", "H"],
        "lam_h": [1.0, 1.0, 2.0, 2.0],
        "lam_a": [1.0, 2.0, 1.0, 1.0],
    })


# --- hand-computed values --------------------------------------------------


def test_goal_deviance_matches_hand_computation(four_matches):
    """Match 0: lambda 1.0 and 1.0, goals 1 and 1.

    Per side, -log P(y) = lam - y*log(lam) + log(y!) = 1 - 0 + 0 = 1.0.
    Both sides, so 2.0. And exp(-1.0) must equal the Poisson pmf at y=1.
    """
    dev = metrics.goal_deviance(four_matches)
    assert dev[0] == pytest.approx(2.0)
    assert math.exp(-1.0) == pytest.approx(1.0 * math.exp(-1.0))

    # Match 1: lam 1.0 vs y=0 -> 1.0 ; lam 2.0 vs y=2 -> 2 - 2*log2 + log2 = 2 - log4
    assert dev[1] == pytest.approx(1.0 + (2.0 - 2 * math.log(2.0) + math.log(2.0)))


def test_goal_deviance_is_minimised_at_the_true_rate():
    """The selection metric has to actually point at the truth."""
    rng = np.random.default_rng(7)
    y = rng.poisson(1.7, 40_000)
    frame = pd.DataFrame({"fthg": y, "ftag": y, "lam_h": 1.7, "lam_a": 1.7})
    best = metrics.goal_deviance(frame).mean()
    for wrong in (1.4, 1.55, 1.85, 2.1):
        frame["lam_h"] = frame["lam_a"] = wrong
        assert metrics.goal_deviance(frame).mean() > best


def test_logloss_and_brier_1x2_by_hand(four_matches):
    probs = pd.DataFrame({
        "p_h": [0.5, 0.2, 0.6, 0.6],
        "p_d": [0.25, 0.3, 0.2, 0.2],
        "p_a": [0.25, 0.5, 0.2, 0.2],
    })
    ll = metrics.logloss_1x2(probs, four_matches["ftr"])
    assert ll[0] == pytest.approx(-math.log(0.25))  # drew, p_d = 0.25
    assert ll[1] == pytest.approx(-math.log(0.50))  # away win, p_a = 0.50

    brier = metrics.brier_1x2(probs, four_matches["ftr"])
    # drew: (0.5-0)^2 + (0.25-1)^2 + (0.25-0)^2
    assert brier[0] == pytest.approx(0.25 + 0.5625 + 0.0625)


def test_binary_rules_by_hand():
    assert metrics.logloss_binary(np.array([0.8]), np.array([1]))[0] == pytest.approx(-math.log(0.8))
    assert metrics.logloss_binary(np.array([0.8]), np.array([0]))[0] == pytest.approx(-math.log(0.2))
    assert metrics.brier_binary(np.array([0.8]), np.array([1]))[0] == pytest.approx(0.04)


def test_auc_endpoints_and_ties():
    assert metrics.auc(np.array([0.1, 0.2, 0.8, 0.9]), np.array([0, 0, 1, 1])) == 1.0
    assert metrics.auc(np.array([0.9, 0.8, 0.2, 0.1]), np.array([0, 0, 1, 1])) == 0.0
    assert metrics.auc(np.array([0.5, 0.5, 0.5, 0.5]), np.array([0, 0, 1, 1])) == 0.5
    assert math.isnan(metrics.auc(np.array([0.3, 0.6]), np.array([1, 1])))


# --- the rules are proper --------------------------------------------------


def test_a_perfectly_calibrated_forecast_scores_at_its_own_entropy():
    """If the truth is generated from p, the logloss of p must equal H(p).

    This is what "proper scoring rule" means operationally, and it is the check
    that catches a rule wired to the wrong outcome column.
    """
    rng = np.random.default_rng(3)
    n = 200_000
    p = rng.uniform(0.2, 0.8, n)
    y = (rng.random(n) < p).astype(int)
    entropy = -(p * np.log(p) + (1 - p) * np.log(1 - p)).mean()
    assert metrics.logloss_binary(p, y).mean() == pytest.approx(entropy, abs=0.005)


def test_logloss_punishes_a_miscalibrated_forecast():
    rng = np.random.default_rng(4)
    n = 100_000
    p = rng.uniform(0.2, 0.8, n)
    y = (rng.random(n) < p).astype(int)
    honest = metrics.logloss_binary(p, y).mean()
    overconfident = metrics.logloss_binary(np.clip(p * 1.6 - 0.3, 0.01, 0.99), y).mean()
    assert overconfident > honest


# --- model and market probabilities ----------------------------------------


def test_model_probs_are_coherent():
    probs = metrics.model_probs(np.array([1.4, 0.9]), np.array([1.1, 1.7]))
    assert np.allclose(probs.p_h + probs.p_d + probs.p_a, 1.0, atol=1e-9)
    assert np.allclose(probs.p_over + probs.p_under, 1.0, atol=1e-9)
    # A stronger home side must be more likely to win.
    assert probs.p_h[0] > probs.p_a[0]
    assert probs.p_h[1] < probs.p_a[1]


def test_market_probs_are_devigged_not_break_even():
    """The distinction that must never collapse: these sum to 1, 1/odds does not."""
    frame = pd.DataFrame({
        "avg_h": [2.0], "avg_d": [4.0], "avg_a": [4.0],
        "avg_over25": [2.0], "avg_under25": [2.0],
    })
    probs = metrics.market_probs(frame, "pre_close")
    assert probs.p_h[0] + probs.p_d[0] + probs.p_a[0] == pytest.approx(1.0)
    # 1/2.0 + 1/4.0 + 1/4.0 = 1.0 exactly here, so de-vigged equals break-even
    # only because this book has no margin. Give it one and they must diverge.
    frame = pd.DataFrame({
        "avg_h": [1.9], "avg_d": [3.8], "avg_a": [3.8],
        "avg_over25": [1.9], "avg_under25": [1.9],
    })
    probs = metrics.market_probs(frame, "pre_close")
    assert probs.p_h[0] + probs.p_d[0] + probs.p_a[0] == pytest.approx(1.0)
    assert probs.p_h[0] < 1 / 1.9  # de-vigged is always below break-even


def test_market_probs_are_nan_when_unpriced_rather_than_substituted():
    frame = pd.DataFrame({
        "close_ps_h": [np.nan, 2.0], "close_ps_d": [np.nan, 4.0],
        "close_ps_a": [np.nan, 4.0],
        "close_avg_over25": [np.nan, 2.0], "close_avg_under25": [np.nan, 2.0],
    })
    probs = metrics.market_probs(frame, "closing")
    assert np.isnan(probs.p_h[0])
    assert probs.p_h[1] == pytest.approx(0.5)


def test_information_sets_read_different_columns():
    """Guards against the two sets silently pointing at the same odds."""
    pre = metrics.MARKET_COLUMNS["pre_close"]["1x2"]
    close = metrics.MARKET_COLUMNS["closing"]["1x2"]
    assert not set(pre) & set(close)


# --- scorecards ------------------------------------------------------------


def test_scorecard_omits_deviance_for_the_market(four_matches):
    probs = metrics.base_rate_probs(four_matches)
    card = metrics.score(four_matches, probs, with_deviance=False)
    assert math.isnan(card.deviance)
    assert card.n == 4
    assert card.ll_1x2 > 0


def test_base_rate_reproduces_the_observed_frequencies(four_matches):
    probs = metrics.base_rate_probs(four_matches)
    assert probs.p_h[0] == pytest.approx(0.5)   # 2 of 4 home wins
    assert probs.p_d[0] == pytest.approx(0.25)
    assert probs.p_over[0] == pytest.approx(0.25)  # totals 2, 2, 2, 4 -- one over 2.5
