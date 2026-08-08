"""Trial counting and PBO, checked against planted answers.

A deflation statistic that has never been shown a known overfit will report
whatever it is asked for, and it will be believed because it is the last number
anyone computes before unsealing a holdout. So the three regimes are planted
and asserted: real skill must come back clean, pure noise must come back at a
coin flip, and a construction that is overfit by design must be caught.

This is the same discipline as `test_calibration.py`'s planted defects and P2's
oracle arm -- a null is not a result without a positive control.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from engine import db, ledger
from engine.eval import trials

RNG = np.random.default_rng(11)
T, N = 320, 24


def frame(matrix) -> pd.DataFrame:
    return pd.DataFrame(matrix, columns=[f"c{i}" for i in range(matrix.shape[1])])


# --- the three regimes -----------------------------------------------------


def test_genuine_skill_is_not_flagged_as_overfitting():
    """One configuration is really better. PBO must be near zero, or the
    statistic would condemn every honest selection ever made."""
    matrix = RNG.normal(0, 1, (T, N))
    matrix[:, 7] += 0.8                      # a real, persistent edge
    result = trials.cscv_pbo(frame(matrix))

    assert result.pbo < 0.05
    assert result.degradation > 0, "the winner should be above the OOS median"
    assert result.choice_mattered


def test_pure_noise_lands_at_a_coin_flip():
    """Nothing to choose between: the in-sample winner is random, so it ranks
    below the out-of-sample median about half the time."""
    result = trials.cscv_pbo(frame(RNG.normal(0, 1, (T, N))))
    assert 0.35 < result.pbo < 0.65


def test_a_construction_that_is_overfit_by_design_is_caught():
    """Each trial spikes in exactly one block and is poor everywhere else.

    Whichever spike lands in-sample wins in-sample -- and is then below average
    out-of-sample, because its spike is spent. This is backtest overfitting in
    its purest form and PBO must be high on it.
    """
    blocks = 16
    matrix = RNG.normal(0, 0.25, (T, blocks))
    edges = np.array_split(np.arange(T), blocks)
    for i in range(blocks):
        matrix[edges[i], i] += 6.0           # all of trial i's merit, in block i
    result = trials.cscv_pbo(frame(matrix), blocks=blocks)

    assert result.pbo > 0.8, f"planted overfit not detected (PBO {result.pbo:.3f})"
    assert result.degradation < 0, "the winner should trail the OOS median"


# --- the interpretation trap ----------------------------------------------


def test_near_identical_trials_are_marked_uninformative():
    """The trap this corpus will actually spring.

    Our configurations differ by less than a paired standard error, so PBO will
    sit at 0.5 no matter what -- and reading that as 'overfit' would be wrong.
    The result must say so itself rather than relying on someone remembering.
    """
    base = RNG.normal(0, 1, (T, 1))
    matrix = base + RNG.normal(0, 1e-6, (T, N))    # indistinguishable
    result = trials.cscv_pbo(frame(matrix))

    assert not result.choice_mattered
    assert "UNINFORMATIVE" in result.describe()


def test_a_real_spread_is_marked_informative():
    matrix = RNG.normal(0, 1, (T, N))
    matrix[:, 3] += 0.5
    assert trials.cscv_pbo(frame(matrix)).choice_mattered


# --- guards ---------------------------------------------------------------


def test_odd_block_counts_are_refused():
    with pytest.raises(ValueError, match="even"):
        trials.cscv_pbo(frame(RNG.normal(0, 1, (T, N))), blocks=15)


def test_too_few_periods_to_block_is_refused():
    with pytest.raises(ValueError, match="cannot be cut"):
        trials.cscv_pbo(frame(RNG.normal(0, 1, (8, N))), blocks=16)


def test_a_single_configuration_is_refused():
    with pytest.raises(ValueError, match="at least two"):
        trials.cscv_pbo(frame(RNG.normal(0, 1, (T, 1))))


def test_the_split_count_is_the_symmetric_combination_count():
    from math import comb
    result = trials.cscv_pbo(frame(RNG.normal(0, 1, (T, N))), blocks=10)
    assert result.n_splits == comb(10, 5)


# --- counting -------------------------------------------------------------


def test_configurations_are_counted_from_arms_not_from_rows(tmp_path):
    """The §3.2 correction: one sweep row is a whole grid, and counting rows
    understates multiplicity rather than overstating it."""
    conn = db.connect(tmp_path / "t.db")
    db.migrate(conn)
    ledger.record(conn, kind=ledger.SWEEP, name="sweep_a", purpose="dev",
                  seasons=("202021",), divisions=("E0",),
                  detail={"arms": [{"value": v} for v in range(9)]}, reason="r")
    ledger.record(conn, kind=ledger.GATE, name="gate_b", purpose="dev",
                  seasons=("202021",), divisions=("E0",),
                  detail={"arms": {"x": {}, "y": {}}}, reason="r")
    ledger.record(conn, kind=ledger.PROBE, name="probe_c", purpose="dev",
                  seasons=("202021",), divisions=("E0",),
                  detail={"note": "no arms here"}, reason="r")

    count = trials.count_configurations(conn)
    assert count.runs == 3
    assert count.questions == 3
    assert count.configurations == 11, "9 + 2, not 3 rows"
    assert count.unattributed == 1


def test_the_post_hoc_trial_is_named_when_present(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    db.migrate(conn)
    ledger.record(conn, kind=ledger.PROBE, name="h19_alpha_interaction",
                  purpose="dev", seasons=("202021",), divisions=("E0",),
                  detail={"arms": [{}, {}]}, reason="post-hoc")
    assert trials.count_configurations(conn).post_hoc == ("h19_alpha_interaction",)


def test_the_real_ledger_holds_more_configurations_than_rows():
    """Guards the finding itself against a future refactor quietly reverting it."""
    count = trials.count_configurations(db.connect())
    assert count.configurations > count.runs
    assert count.configurations >= 133


# --- re-runs: which spend again, and which do not -------------------------


def _ledger(conn, rows):
    """rows: (name, arms). Writes one gate_ledger row each."""
    for name, arms in rows:
        ledger.record(conn, kind=ledger.GATE, name=name, detail={"arms": arms})


def test_an_identical_rerun_does_not_spend_again(conn):
    """Multiplicity is configurations chosen among. `p5_meta_arms` wrote four
    rows on four implementation runs with byte-identical results; that was one
    chance to be fooled, not four (META.md 9)."""
    arms = [{"arm": "A", "score": 0.1}, {"arm": "B", "score": 0.2}]
    _ledger(conn, [("g", arms), ("g", arms), ("g", arms)])

    count = trials.count_configurations(conn)

    assert count.runs == 3
    assert count.configurations == 2
    assert count.repeats == 2


def test_a_rerun_whose_numbers_moved_still_spends(conn):
    """OUTSTANDING 7.5: the rest gate ran before and after a correctness fix and
    both rows count, because both were real attempts at the answer."""
    _ledger(conn, [("g", [{"arm": "A", "score": 0.1}]),
                   ("g", [{"arm": "A", "score": 0.9}])])

    count = trials.count_configurations(conn)

    assert count.configurations == 2
    assert count.repeats == 0


def test_an_added_reporting_field_does_not_make_it_a_new_trial(conn):
    """The real shape of the p5 re-runs: same computation, extra column."""
    _ledger(conn, [("g", [{"arm": "A", "score": 0.1}]),
                   ("g", [{"arm": "A", "score": 0.1, "extra": 7}])])

    assert trials.count_configurations(conn).configurations == 1


def test_arms_that_record_only_names_are_never_collapsed(conn):
    """Silence is not agreement. `b2_b3_selection` recorded bare labels, and two
    runs that really did differ would otherwise have merged into one."""
    _ledger(conn, [("g", [{"arm": "A"}, {"arm": "B"}]),
                   ("g", [{"arm": "A"}, {"arm": "B"}])])

    count = trials.count_configurations(conn)

    assert count.configurations == 4, "cannot prove they matched, so both spend"
    assert count.repeats == 0
