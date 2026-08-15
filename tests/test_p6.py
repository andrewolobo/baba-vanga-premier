"""Criterion 1's column set, its aggregation, its row and its audit.

The matrix itself needs the database and thirty-eight walk-forwards, and none of
that is exercised here. What is, is everything that would change the number
without changing anything visible in the output: a configuration counted twice,
a zero-weight arm that fails to dedup onto the head it is bit-for-bit identical
to, a period axis that is not the bootstrap's, a ledger row that accidentally
declares configurations Decision 8 says it did not spend, and a gate added after
`DEFLATION.md` §9 was written slipping through the audit unclassified.

Nothing here opens the real database or writes a ledger row -- the audit reads
its rows through `conn.execute`, so a fake standing in for the connection is
enough, and using one keeps the suite honest about never looking at the corpus.
"""

from __future__ import annotations

import json
from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from engine.eval import metrics, p6, trials


# --- the column set --------------------------------------------------------


def test_the_column_set_is_the_thirty_eight_of_decision_9():
    columns = p6.build_columns()
    assert len(columns) == 38
    assert len({c.key for c in columns}) == 38, "a duplicate identity survived dedup"


def test_the_base_head_appears_exactly_once():
    """It is the h3 (400, 0.1) column, and both weight sweeps hang off it."""
    columns = p6.build_columns()
    head = [c for c in columns if c.key == p6.identity(p6.HEAD)]

    assert len(head) == 1
    assert set(head[0].grids) == {"h3_alpha", "h14_squad_prior", "h20_shots_blend"}


def test_the_half_life_grid_is_the_union_of_both_runs():
    """Decision 4: the pre-widening run's configurations were still spent."""
    h2 = [c for c in p6.build_columns() if "h2_half_life" in c.grids]

    assert sorted(c.cfg.half_life for c in h2) == [
        100, 130, 160, 200, 240, 270, 300, 400, 500, 650, 800]
    assert {c.cfg.alpha for c in h2} == {1.0}, "h2 swept at BASE's default alpha"


def test_the_alpha_families_sit_at_each_run_s_chosen_half_life():
    families: dict[float, list[float]] = {}
    for column in p6.build_columns():
        if "h3_alpha" in column.grids:
            families.setdefault(column.cfg.half_life, []).append(column.cfg.alpha)

    assert {k: sorted(v) for k, v in families.items()} == {
        300.0: [0.25, 0.5, 1.0, 2.0, 5.0],
        500.0: [0.02, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0],
        400.0: [0.02, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0],
    }


def test_the_grid_views_are_the_sizes_the_addendum_expects():
    """§9's companion views: three of the four share columns with another grid,
    and the sharing is membership rather than a second copy of the column."""
    columns = p6.build_columns()
    sizes = {grid: sum(1 for c in columns if grid in c.grids) for grid in p6.GRIDS}

    assert sizes == {"h2_half_life": 11, "h3_alpha": 21,
                     "h14_squad_prior": 5, "h20_shots_blend": 6}
    assert sum(sizes.values()) > len(columns), "the views must overlap, not tile"


def test_only_the_four_prior_columns_carry_a_ridge_target():
    carrying = [c for c in p6.build_columns() if c.with_prior]

    assert sorted(c.cfg.squad_prior for c in carrying) == [0.25, 0.5, 0.75, 1.0]


# --- the normalisation that makes the dedup exact --------------------------


def test_a_zero_weight_arm_is_the_base_head():
    """`walkforward` guarantees w=0 is bit-for-bit the head, so the two sweeps'
    zero arms are the same column and must not appear as three."""
    head = p6.identity(p6.HEAD)

    assert p6.identity(replace(p6.HEAD, squad_prior=0.0), with_prior=True) == head
    assert p6.identity(replace(p6.HEAD, shots_blend=0.0)) == head
    assert p6.identity(replace(p6.HEAD, squad_prior=None), with_prior=True) == head


def test_a_non_zero_weight_is_a_column_of_its_own():
    head = p6.identity(p6.HEAD)

    assert p6.identity(replace(p6.HEAD, squad_prior=0.25), with_prior=True) != head
    assert p6.identity(replace(p6.HEAD, shots_blend=0.15)) != head


# --- weekly aggregation ----------------------------------------------------


def _scored(rows) -> pd.DataFrame:
    """A walk-forward output: goalless matches, so deviance is lam_h + lam_a."""
    frame = pd.DataFrame(rows, columns=["match_date", "home_team", "away_team",
                                        "lam_h", "lam_a"])
    frame["match_date"] = pd.to_datetime(frame["match_date"])
    return frame.assign(fthg=0, ftag=0)


#: Three ISO weeks, two matches each. Saturday/Sunday pairs, so each pair falls
#: inside one `to_period("W")` block.
_WEEKS = [("2021-08-07", "a", "b"), ("2021-08-08", "c", "d"),
          ("2021-08-14", "e", "f"), ("2021-08-15", "g", "h"),
          ("2021-08-21", "i", "j"), ("2021-08-22", "k", "l")]


def test_the_matrix_is_negated_weekly_means_one_row_per_block():
    """Every match is 0-0, so its deviance is lam_h + lam_a exactly."""
    flat = _scored([(*m, 0.5, 0.5) for m in _WEEKS])
    lumpy = _scored([(*_WEEKS[0], 0.5, 0.5), (*_WEEKS[1], 1.5, 1.5),
                     (*_WEEKS[2], 1.0, 1.0), (*_WEEKS[3], 1.0, 1.0),
                     (*_WEEKS[4], 0.5, 0.5), (*_WEEKS[5], 0.5, 0.5)])

    matrix, n_matches = p6.weekly_matrix({"flat": flat, "lumpy": lumpy})

    assert matrix.shape == (3, 2)
    assert n_matches == 6
    assert list(matrix["flat"]) == [-1.0, -1.0, -1.0]
    assert list(matrix["lumpy"]) == [-2.0, -2.0, -1.0]


def test_the_rows_are_chronological():
    """CSCV cuts the period axis into contiguous blocks, so the axis has to be
    in time order or the blocks are not periods at all."""
    shuffled = _scored([(*m, 0.5, 0.5) for m in reversed(_WEEKS)])

    matrix, _ = p6.weekly_matrix({"a": shuffled, "b": shuffled})

    assert list(matrix.index) == sorted(matrix.index)


def test_columns_are_aligned_to_their_common_match_set():
    """A column that reached further does not get to be scored on more."""
    short = _scored([(*m, 0.5, 0.5) for m in _WEEKS])
    long = _scored([(*m, 0.5, 0.5) for m in
                    [*_WEEKS, ("2021-08-28", "m", "n")]])

    matrix, n_matches = p6.weekly_matrix({"short": short, "long": long})

    assert n_matches == 6
    assert matrix.shape == (3, 2), "the unmatched week must not become a row"


def test_the_period_axis_is_the_bootstrap_s_own_blocking():
    """§3's reason for weeks: the dependence structure the paired bootstrap
    respects has to be respected here too, so the axis is the same function."""
    frame = _scored([(*m, 0.5, 0.5) for m in _WEEKS])

    matrix, _ = p6.weekly_matrix({"a": frame, "b": frame})

    from engine.eval import bootstrap
    assert list(matrix.index) == sorted(set(bootstrap.week_blocks(frame["match_date"])))


def test_the_matrix_negates_the_loss():
    """`cscv_pbo` wants higher-is-better and deviance is a loss; negating it in
    the wrong place would silently invert every verdict."""
    frame = _scored([(*m, 0.5, 0.5) for m in _WEEKS])

    matrix, _ = p6.weekly_matrix({"a": frame, "b": frame})

    assert (matrix.to_numpy() < 0).all()
    assert matrix.iloc[0, 0] == pytest.approx(-metrics.goal_deviance(frame).mean())


# --- the ledger row --------------------------------------------------------


def _result(*, pbo: float, spread: float) -> trials.PBOResult:
    return trials.PBOResult(pbo=pbo, degradation=-0.0004, spread=spread,
                            n_trials=38, n_splits=12870,
                            logits=np.zeros(12870))


def _detail(result: trials.PBOResult) -> dict:
    columns = p6.build_columns()
    return p6.build_detail(
        result, {grid: result for grid in p6.GRIDS}, columns,
        {"h15_channels": {"rows": (48,), "configs": 5, "condition": "1 -- diagnostic"}},
        n_weeks=490, n_matches=21_000, unattributed=57)


def _mentions(obj, key: str) -> bool:
    if isinstance(obj, dict):
        return key in obj or any(_mentions(v, key) for v in obj.values())
    if isinstance(obj, list):
        return any(_mentions(v, key) for v in obj)
    return False


def test_the_row_declares_no_configurations():
    """Decision 8: this probe spends none. `count_configurations` reads any
    `arms` key as configurations spent, so one anywhere in the payload -- nested
    included -- would make a probe that counts nothing count thirty-eight."""
    detail = _detail(_result(pbo=0.05, spread=0.01))

    assert not _mentions(detail, "arms")
    assert trials._arm_list(detail) is None
    assert _mentions(detail, "columns"), "the labels still have to be recorded"


def test_the_row_survives_the_ledger_s_own_serialisation():
    """`ledger.record` json-dumps the detail; a numpy scalar reaching it raises
    at the write, which is after the look has been taken."""
    detail = _detail(_result(pbo=0.05, spread=0.01))

    assert json.loads(json.dumps(detail, sort_keys=True)) == detail


def test_the_excluded_table_is_recorded_beside_the_result():
    """Decision 9: everything excluded is published with its count and reason,
    because 'narrow the field' is exactly the shape a rationalisation takes."""
    detail = _detail(_result(pbo=0.05, spread=0.01))

    assert detail["excluded"] == {
        "h15_channels": {"configs": 5, "condition": "1 -- diagnostic"}}
    assert detail["unattributed"] == 57


# --- the verdict, in §5's and §6's terms ------------------------------------


def test_a_low_pbo_on_distinguishable_trials_passes():
    result = _result(pbo=0.05, spread=0.01)

    assert result.choice_mattered
    assert p6.verdict(result)["passes"]
    assert p6.verdict(result)["basis"] == "pbo"


def test_a_high_pbo_on_distinguishable_trials_fails():
    result = _result(pbo=0.42, spread=0.01)

    assert p6.verdict(result)["passes"] is False
    assert "FAILS" in p6.verdict(result)["statement"]


def test_an_uninformative_grid_passes_on_the_negligible_spread():
    """§6's proviso, and why it is not a loophole: a coin-flip PBO across
    configurations that differ by less than a paired SE reflects there being
    nothing to choose, not overfitting."""
    result = _result(pbo=0.50, spread=1e-5)

    assert not result.choice_mattered
    assert p6.verdict(result)["passes"]
    assert p6.verdict(result)["basis"] == "negligible spread"


def test_the_bar_is_inclusive_at_the_pre_committed_threshold():
    assert p6.verdict(_result(pbo=0.20, spread=0.01))["passes"]
    assert not p6.verdict(_result(pbo=0.201, spread=0.01))["passes"]


# --- the audit -------------------------------------------------------------


class _FakeLedger:
    """Enough of a connection for the audit: it only ever selects rows."""

    def __init__(self, rows):
        self._rows = rows

    def execute(self, _query):
        return list(self._rows)


def _row(row_id: int, name: str, detail: dict) -> dict:
    return {"id": row_id, "name": name, "detail": detail}


def test_an_armed_row_the_audit_does_not_classify_stops_the_run():
    """A gate added after §9 was written has to be judged by a human against
    the five conditions. Silently dropping it -- or silently admitting it -- is
    the after-the-fact choice the whole document exists to prevent."""
    conn = _FakeLedger([_row(104, "h99_new_gate", {"arms": [{"value": 1},
                                                            {"value": 2}]})])

    with pytest.raises(ValueError, match="h99_new_gate"):
        p6.audit(conn)


def test_a_row_carrying_no_arm_list_needs_no_classification():
    """Decision 6's rows: they cannot be reconstructed into columns at all, so
    they are the reported undercount rather than an audit failure."""
    conn = _FakeLedger([_row(1, "p1_base_score", {"rows": [], "h9_breaches": []})])

    assert p6.audit(conn) == {}


def test_the_included_grids_are_not_reported_as_excluded():
    conn = _FakeLedger([
        _row(9, "h2_half_life", {"arms": [{"value": 100}, {"value": 130}]}),
        _row(48, "h15_channels", {"arms": [{"value": "a"}, {"value": "b"}]}),
    ])

    audited = p6.audit(conn)

    assert set(audited) == {"h15_channels"}
    assert audited["h15_channels"] == {
        "rows": (48,), "configs": 2, "condition": p6.EXCLUDED["h15_channels"]}


def test_the_configuration_count_collapses_identical_re_runs():
    """The per-name count is `count_configurations`' own, so `p5_meta_arms`'
    four byte-identical implementation runs are four configurations and not
    sixteen (META.md §9)."""
    arms = [{"arm": "A", "score": 0.1}, {"arm": "B", "score": 0.2},
            {"arm": "C", "score": 0.3}, {"arm": "D", "score": 0.4}]
    conn = _FakeLedger([_row(i, "p5_meta_arms", {"arms": arms})
                        for i in (83, 84, 85, 86)])

    audited = p6.audit(conn)

    assert audited["p5_meta_arms"]["configs"] == 4
    assert audited["p5_meta_arms"]["rows"] == (83, 84, 85, 86)


def test_every_pinned_exclusion_names_a_condition():
    """The table is the report. An entry with no reason is an exclusion nobody
    can check, which is the same as no rule at all."""
    assert set(p6.EXCLUDED) & set(p6.GRIDS) == set()
    for name, condition in p6.EXCLUDED.items():
        assert condition[0] in "12345", f"{name} names no §9.2 condition"
