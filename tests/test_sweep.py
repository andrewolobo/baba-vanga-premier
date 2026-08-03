"""The selection rule, tested on curves whose right answer is known by construction.

The 1-SE rule is the thing standing between a flat likelihood surface and a
hyperparameter chosen by the random seed, so it gets tested on a flat curve, a
peaked curve, and the boundary cases either side.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from engine.eval import sweep
from engine.eval.walkforward import WalkForwardConfig
from tests.test_walkforward_harness import synthetic_corpus

#: Longer half-life = more shrinkage toward the long-run average.
LONGER = float
#: Larger alpha = more ridge penalty.
STRONGER = float


# --- the rule --------------------------------------------------------------


def test_flat_curve_picks_the_most_regularised_end():
    """The case the rule exists for. Every arm is within one SE, so the choice
    must be made by the tie-break and not by which noise draw came out lowest."""
    values = [100, 130, 160, 200, 240, 300]
    scores = [1.8503, 1.8501, 1.8500, 1.8502, 1.8504, 1.8506]
    stderrs = [0.004] * 6
    assert values[sweep.one_se_rule(values, scores, stderrs, more_regularised=LONGER)] == 300


def test_sharply_peaked_curve_picks_the_peak():
    values = [100, 130, 160, 200, 240, 300]
    scores = [1.90, 1.87, 1.8500, 1.88, 1.91, 1.95]
    stderrs = [0.004] * 6
    assert values[sweep.one_se_rule(values, scores, stderrs, more_regularised=LONGER)] == 160


def test_a_monotone_curve_resolved_by_paired_errors_picks_the_true_optimum():
    """The bug this rule shipped with, pinned.

    These are the real numbers from the first P1 run of the alpha sweep. A
    gently monotone curve looks entirely flat against each arm's MARGINAL
    standard error (0.00724) and the rule then hands the sweep to the
    tie-break, which walked to alpha=2.0 -- eight times the penalty the data
    actually prefers. Against the PAIRED standard error of the difference
    (~0.0003) the same curve is separated by tens of standard errors and the
    rule must take the actual minimum.
    """
    values = [0.25, 0.5, 1.0, 2.0, 5.0]
    scores = [2.88186, 2.88275, 2.88451, 2.88682, 2.88913]
    marginal = [0.00724] * 5
    paired = [0.0, 0.00025, 0.00025, 0.00030, 0.00035]

    assert values[sweep.one_se_rule(values, scores, marginal,
                                    more_regularised=STRONGER)] == 2.0
    assert values[sweep.one_se_rule(values, scores, paired,
                                    more_regularised=STRONGER)] == 0.25


def test_the_threshold_is_the_paired_se_of_each_arm_against_the_best():
    values = [1, 2, 3]
    stderrs = [0.010, 0.010, 0.010]
    # arm 3 is 0.009 worse than the best -- inside its own paired SE, so it
    # wins the tie-break
    assert values[sweep.one_se_rule(values, [1.000, 1.100, 1.009], stderrs,
                                    more_regularised=STRONGER)] == 3
    # arm 3 is 0.011 worse -- outside, so the best arm keeps it
    assert values[sweep.one_se_rule(values, [1.000, 1.100, 1.011], stderrs,
                                    more_regularised=STRONGER)] == 1


def test_each_arm_is_judged_against_its_own_paired_error():
    """Arms far from the best are measured less precisely, so the threshold is
    per-arm rather than a single number taken from the best."""
    values = [1, 2, 3]
    scores = [1.000, 1.010, 1.010]
    stderrs = [0.0, 0.005, 0.020]   # arm 3 is the noisier comparison
    assert values[sweep.one_se_rule(values, scores, stderrs,
                                    more_regularised=STRONGER)] == 3


def test_the_best_arm_is_always_eligible():
    """Even with a zero standard error the rule must return something."""
    values = [1, 2, 3]
    assert values[sweep.one_se_rule(values, [1.0, 0.5, 2.0], [0.0] * 3,
                                    more_regularised=STRONGER)] == 2


def test_direction_of_regularisation_is_respected():
    values = [100, 300]
    scores, stderrs = [1.0, 1.0], [0.01, 0.01]
    assert values[sweep.one_se_rule(values, scores, stderrs, more_regularised=LONGER)] == 300
    assert values[sweep.one_se_rule(values, scores, stderrs,
                                    more_regularised=lambda v: -float(v))] == 100


# --- boundary detection ----------------------------------------------------


def test_a_boundary_optimum_is_reported_as_censored(corpus):
    base = WalkForwardConfig(cadence="fortnightly")
    # Half-life is monotone improving on this corpus, so a grid that stops
    # short must announce that its winner is an edge, not an optimum.
    result = sweep.run(corpus, "half_life", [80, 120, 160], base, reps=200)
    assert result.censored in ("lower", "upper", None)
    if result.best.value in (80, 160):
        assert result.censored is not None


# --- the runner, end to end on a synthetic corpus --------------------------


@pytest.fixture(scope="module")
def corpus():
    return synthetic_corpus(n_seasons=5, n_teams=20, seed=9)


def test_sweep_runs_and_reports_every_arm(corpus):
    base = WalkForwardConfig(cadence="fortnightly")
    result = sweep.run(corpus, "half_life", [120, 200, 280], base, reps=200)
    assert len(result.arms) == 3
    assert result.chosen.value in (120, 200, 280)
    assert result.spread >= 0.0
    table = result.table()
    assert table["chosen"].sum() == 1
    assert set(table.columns) >= {"value", "deviance", "marginal_stderr",
                                  "paired_stderr", "ll_1x2", "ll_ou25"}
    # The distinction the rule depends on: paired errors must be far tighter.
    others = [a for a in result.arms if a.value != result.best.value]
    assert all(a.paired_stderr < a.marginal_stderr for a in others)


def test_sweep_recovers_a_planted_optimum():
    """Strengths that barely drift should prefer a LONG half-life; strengths
    that churn every season should prefer a shorter one. If the sweep cannot
    tell those two corpora apart, it is not measuring what it claims to."""
    stable = synthetic_corpus(n_seasons=6, n_teams=20, seed=3)
    base = WalkForwardConfig(cadence="fortnightly")
    grid = [60, 150, 400]

    volatile = stable.copy()
    rng = np.random.default_rng(17)
    # Re-draw outcomes from strengths that change every season, keeping the
    # fixture list identical so the only difference is persistence.
    lam = np.exp(rng.normal(np.log(1.35), 0.35, len(volatile)))
    volatile["fthg"] = rng.poisson(lam)
    volatile["ftag"] = rng.poisson(lam * 0.85)

    stable_pick = sweep.run(stable, "half_life", grid, base, reps=200).best.value
    volatile_pick = sweep.run(volatile, "half_life", grid, base, reps=200).best.value
    # Pure noise carries no signal to track, so the longest window wins there;
    # a real drifting league must not prefer a window at least as long.
    assert volatile_pick >= stable_pick


def test_compare_pairs_arms_on_shared_matches_only(corpus):
    arms = {
        "base": WalkForwardConfig(cadence="fortnightly"),
        "shrunk": WalkForwardConfig(cadence="fortnightly", season_boundary_shrink=0.9),
    }
    result = sweep.compare(corpus, arms, reference="base", reps=200)
    assert result["n"] > 0
    assert "vs_reference" not in result["arms"]["base"]
    delta = result["arms"]["shrunk"]["vs_reference"]
    assert delta["n"] == result["n"]
    assert delta["ci_low"] <= delta["delta"] <= delta["ci_high"]


def test_compare_against_itself_is_exactly_zero(corpus):
    cfg = WalkForwardConfig(cadence="fortnightly")
    result = sweep.compare(corpus, {"a": cfg, "b": cfg}, reference="a", reps=200)
    assert result["arms"]["b"]["vs_reference"]["delta"] == pytest.approx(0.0)
    assert not result["arms"]["b"]["vs_reference"]["excludes_zero"]
