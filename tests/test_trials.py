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

import importlib.util

import numpy as np
import pandas as pd
import pytest

from engine import config, db, ledger
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
    """Guards the finding itself against a future refactor quietly reverting it.

    **Skipped where there is no ledger to guard.** `db/premier.db` is gitignored
    and the store is rebuilt from the tracked CSVs by `engine.ingest.build`,
    which loads `matches` and `player_seasons` and *not* `gate_ledger`. So a
    fresh checkout -- and every deployed server -- has zero rows here, and this
    was the one test in 437 that failed on a server-like database
    (`docs/DEPLOY.md` §5.4). Asserting against an empty ledger would make
    `pytest -q` fail on the serving host for a reason with nothing to do with
    serving, and an acceptance gate that is known to fail is not a gate.

    The skip is narrow on purpose: it fires only when the ledger is *empty*, so
    a ledger that exists and has regressed still fails. What it cannot catch is
    the ledger being wiped, which would present as a skip -- but that is a
    catastrophe with much louder symptoms, and it is why `DEPLOY.md` §6.1 treats
    this file as irreplaceable rather than reproducible.
    """
    count = trials.count_configurations(db.connect())
    if count.runs == 0:
        pytest.skip("no gate ledger in this database -- nothing to guard")
    assert count.configurations > count.runs
    assert count.configurations >= 133


def test_the_ledger_export_is_current():
    """The backup is only a backup while it is current, and nothing enforced it.

    `docs/gate_ledger.jsonl` is the *only* off-machine copy of `gate_ledger`
    (`DEPLOY.md` §6.1): the rest of `db/premier.db` rebuilds from the tracked
    CSVs, and this table does not, because it records which measurements were
    run rather than anything about the corpus. Keeping it current was a manual
    step -- "run it after any gate" -- and it was missed twelve times running,
    leaving rows 91-102 on one gitignored file with no second copy for four
    days. A convention that has already failed is not a control.

    Skipped on an empty ledger for the same reason as the test above: a fresh
    checkout and every deployed server have no rows here, and `pytest -q` must
    not go red on the serving host over a development-machine backup.

    **This test is expected to fail on this machine after a gate runs**, until
    `python scripts/export_ledger.py` is re-run and the diff committed. That is
    the point -- the red is the reminder that the manual step did not fire.
    """
    conn = db.connect()
    if trials.count_configurations(conn).runs == 0:
        pytest.skip("no gate ledger in this database -- nothing to back up")

    export = _export_ledger_module()
    expected = export.render(export.rows(conn))
    assert export.OUT.exists(), f"{config.relpath(export.OUT)} is missing"
    # Deliberately not re-deriving *how* it differs. `--check` already separates
    # the file merely being BEHIND from it DISAGREEING on rows it already had --
    # the append-only violation -- and duplicating that here would give two
    # accounts of the same thing, free to drift apart.
    assert export.OUT.read_text(encoding="utf-8") == expected, (
        f"{config.relpath(export.OUT)} no longer matches gate_ledger. Run "
        f"`python scripts/export_ledger.py --check` for the shape of the "
        f"difference, then re-export and commit the diff.")


def _export_ledger_module():
    """`scripts/` is not a package and the script is invoked by path, so it is
    loaded by location. Importing it rather than re-implementing the comparison
    is what stops the test and the export drifting apart."""
    path = config.REPO_ROOT / "scripts" / "export_ledger.py"
    spec = importlib.util.spec_from_file_location("export_ledger", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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
