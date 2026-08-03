"""Calibrate the bootstrap before trusting any interval it produces.

Two properties, both checked by repetition rather than by argument: under a
true null the interval must cover zero about 95% of the time, and a planted
effect must be detected. A bootstrap that has never been shown a known answer
is a confidence generator.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from engine.eval import bootstrap


def correlated_pair(rng, n_blocks=400, per_block=10, offset=0.0, block_sd=0.5,
                    diff_block_sd=0.0):
    """Losses with a shared per-block shock -- the structure real matchweeks have.

    `diff_block_sd` additionally makes the two arms differ *by block*. That is
    the correlation blocking actually defends against: a common shock cancels
    in the paired difference, but two arms with different half-lives really do
    diverge week by week (a break, a regime change, a congested fixture list),
    and that does not cancel.
    """
    shock = rng.normal(0, block_sd, n_blocks).repeat(per_block)
    blocks = np.arange(n_blocks).repeat(per_block)
    base = shock + rng.normal(0, 1.0, n_blocks * per_block)
    drift = rng.normal(0, diff_block_sd, n_blocks).repeat(per_block) if diff_block_sd else 0.0
    partner = base - offset + drift + rng.normal(0, 0.3, n_blocks * per_block)
    return base, partner, blocks


# --- coverage under the null ----------------------------------------------


def test_covers_zero_about_95_percent_of_the_time_under_a_true_null():
    rng = np.random.default_rng(101)
    covered = 0
    trials = 200
    for _ in range(trials):
        a, b, blocks = correlated_pair(rng, offset=0.0)
        result = bootstrap.paired(a, b, blocks, reps=400, rng=rng)
        covered += not result.excludes_zero
    # 95% nominal; binomial sd over 200 trials is ~1.5 trials, so this window
    # is wide enough not to flake and tight enough to catch a broken interval.
    assert 0.90 <= covered / trials <= 0.99, f"coverage was {covered / trials}"


def test_identical_arms_produce_a_zero_delta():
    rng = np.random.default_rng(102)
    a, _, blocks = correlated_pair(rng)
    result = bootstrap.paired(a, a, blocks, reps=200, rng=rng)
    assert result.delta == pytest.approx(0.0)
    assert not result.excludes_zero
    assert result.verdict == "no difference"


# --- power against a planted effect ---------------------------------------


def test_a_planted_offset_is_detected_with_the_right_sign():
    rng = np.random.default_rng(103)
    a, b, blocks = correlated_pair(rng, offset=0.15)
    result = bootstrap.paired(a, b, blocks, reps=1000, rng=rng)
    # a = b + 0.15, so a is the WORSE arm (losses).
    assert result.delta == pytest.approx(0.15, abs=0.05)
    assert result.excludes_zero
    assert result.verdict == "second arm better"


def test_the_sign_convention_is_negative_means_first_arm_better():
    rng = np.random.default_rng(104)
    a, b, blocks = correlated_pair(rng, offset=-0.15)
    result = bootstrap.paired(a, b, blocks, reps=1000, rng=rng)
    assert result.delta < 0
    assert result.verdict == "first arm better"


def test_detection_rate_rises_with_effect_size():
    rng = np.random.default_rng(105)
    rates = []
    # The paired standard error here is ~0.0064, so these offsets span roughly
    # 0, 1 and 3 SE. Larger effects saturate at 100% detection and would make
    # the ordering trivially true rather than informative.
    for offset in (0.0, 0.006, 0.020):
        hits = sum(
            bootstrap.paired(*correlated_pair(rng, n_blocks=200, offset=offset),
                             reps=300, rng=rng).excludes_zero
            for _ in range(40)
        )
        rates.append(hits / 40)
    assert rates[0] < rates[1] < rates[2]
    assert rates[0] < 0.20
    assert rates[2] > 0.8


# --- blocking is not decorative -------------------------------------------


def test_ignoring_block_structure_would_understate_the_interval():
    """The reason blocks exist. Treating correlated matches as independent
    narrows the interval; if it did not, blocking would be pointless ceremony
    and this test would be the place to find that out.

    Note what the correlation has to be in: a shock common to both arms cancels
    in the paired difference and blocking buys nothing. It is week-to-week
    divergence BETWEEN the arms that inflates the true uncertainty."""
    rng = np.random.default_rng(106)
    a, b, blocks = correlated_pair(rng, offset=0.0, diff_block_sd=0.8)
    # Same data, but every match declared its own block.
    blocked = bootstrap.paired(a, b, blocks, reps=1000, rng=np.random.default_rng(1))
    unblocked = bootstrap.paired(a, b, np.arange(len(a)), reps=1000,
                                 rng=np.random.default_rng(1))
    assert blocked.stderr > 2 * unblocked.stderr


def test_blocking_is_neutral_when_the_arms_differ_only_by_noise():
    """The complement of the test above, so the claim stays precise: when the
    per-block shock is common to both arms, pairing has already removed it and
    blocking neither helps nor hurts."""
    rng = np.random.default_rng(108)
    a, b, blocks = correlated_pair(rng, block_sd=1.5, offset=0.0)
    blocked = bootstrap.paired(a, b, blocks, reps=1000, rng=np.random.default_rng(1))
    unblocked = bootstrap.paired(a, b, np.arange(len(a)), reps=1000,
                                 rng=np.random.default_rng(1))
    assert blocked.stderr == pytest.approx(unblocked.stderr, rel=0.15)


def test_week_blocks_group_by_calendar_week():
    """Weeks run Monday to Sunday, which is exactly the serving cycle: refit on
    Monday, predict the following seven days. So a Saturday and the Sunday after
    it share a block, and the Tuesday after that does not."""
    dates = pd.Series(pd.to_datetime([
        "2015-08-08",   # Saturday
        "2015-08-09",   # Sunday, same Mon-Sun week
        "2015-08-11",   # Tuesday, the NEXT week
        "2015-08-15",   # Saturday, same week as the Tuesday
    ]))
    blocks = bootstrap.week_blocks(dates)
    assert blocks[0] == blocks[1]
    assert blocks[2] == blocks[3]
    assert blocks[0] != blocks[2]


def test_mismatched_arms_are_refused():
    with pytest.raises(ValueError, match="same matches"):
        bootstrap.paired(np.zeros(10), np.zeros(9), np.zeros(10))


# --- single-arm standard error --------------------------------------------


def test_standard_error_shrinks_with_more_blocks():
    rng = np.random.default_rng(107)
    small, _, small_blocks = correlated_pair(rng, n_blocks=50)
    large, _, large_blocks = correlated_pair(rng, n_blocks=800)
    se_small = bootstrap.standard_error(small, small_blocks, reps=500, rng=rng)
    se_large = bootstrap.standard_error(large, large_blocks, reps=500, rng=rng)
    assert se_large < se_small
