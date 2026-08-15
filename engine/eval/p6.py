"""P6 criterion 1: PBO on the pooled selection matrix.

    python -m engine.eval.p6 [--dry-run]

This module exists to execute `docs/DEFLATION.md`, and nothing here is a fresh
judgement: §9's Decisions 8 and 9 fixed both *when* this runs and *what its
columns are*, before any number existed to be argued with.

**Decision 8 — why this runs now, with the holdout still sealed.** §5's
criterion 1 is computed entirely on the development set: `cscv_pbo` consumes a
weeks x configurations matrix of dev performance and no sealed season enters it.
§8's "not yet" is about criterion 2, which needs the holdout by construction.
The ordering then follows rather than being a preference -- if PBO exceeds 0.20
with `choice_mattered` true, P6 fails here and the holdout read is pointless, so
running criterion 1 first can only save the holdout.

**Decision 9 — which configurations are columns.** A configuration is a column
iff it belongs to a grid a selection was actually made from, is scored as mean
goal Poisson deviance on the common dev population (E0-E3, COVID embargoed), is
re-scored on the final corpus, and is not post-hoc. The audit that applies those
five conditions to the ledger as it stood on 2026-08-15 is pinned below as data,
so the printed report reproduces it rather than re-deriving it after the fact.

**The sub-rule condition 1 turns on.** A selection was "actually made" from a
grid iff the run's recorded detail designates a chosen arm via a comparative
selection rule -- the sweeps' `chosen` + `rule` fields. Gates that adjudicated a
pre-registered accept/reject bar chose nothing among alternatives; a null there
kept the prior default, so they are not selection grids and their multiplicity
stays under Decision 6's "at least".

**This probe spends no configurations.** Re-scoring configurations already
counted is the identical computation on the same data, which Decision 4 and
`count_configurations` both treat as not spending again. It still gets a ledger
row, on the convention that recorded the instrument validation: every look at
the dev set is recorded, including one that changes no decision.

Nothing here reads a sealed season: the corpus comes through `p1.load`, which is
`store.read_matches` at the dev seasons and raises rather than filters.
"""

from __future__ import annotations

import argparse
import sqlite3
from dataclasses import dataclass, replace

import pandas as pd

from engine import db, ledger
from engine.eval import bootstrap, metrics, trials
from engine.eval.p1 import BASE, load, served
from engine.eval.p2 import HEAD, build_history, load_players
# `_align` is module-private but this is the same package, and p2 already
# imports `walkforward._fit_at` on that footing. Re-implementing the alignment
# would be worse: the columns must share the exact match set the sweeps' own
# comparisons used, and two implementations of that are free to drift.
from engine.eval.sweep import _align
from engine.eval.walkforward import WalkForwardConfig, walk_forward
from engine.ingest import build
from engine.models import squad
from engine.seasons import DEV_SEASONS, SERVED_DIVISIONS

LEDGER_NAME = "p6_criterion1_pbo"

#: §5's bar. PBO at or below this, with the trials distinguishable, is a pass.
PBO_THRESHOLD = 0.20

#: `PBOResult.choice_mattered`'s threshold: the paired standard-error scale on
#: this corpus. §6 settles the other branch of the criterion on it.
SPREAD_FLOOR = 1e-3

#: 16 blocks -> C(16, 8) = 12,870 splits, as §3 specifies.
BLOCKS = trials.DEFAULT_BLOCKS


# --- the columns, pinned by Decision 9 -------------------------------------

#: The four ledger names whose grids supply the columns (rows 9, 10, 19, 20, 30,
#: 31, 47, 56). Every other armed row is excluded, with its reason, below.
GRIDS: tuple[str, ...] = ("h2_half_life", "h3_alpha", "h14_squad_prior",
                          "h20_shots_blend")

#: Union of the pre-widening run-1 grid (row 9) and the widened grid (rows 19,
#: 30). Decision 4 counts a superseded run's configurations -- a look is spent
#: whether or not its result survived -- and re-scores them on the final corpus.
#: Alpha sits at BASE's default 1.0 throughout, as it did in those runs.
H2_HALF_LIVES: tuple[float, ...] = (100.0, 130.0, 160.0, 200.0, 240.0, 270.0,
                                    300.0, 400.0, 500.0, 650.0, 800.0)

#: h3 ran three times, each at the half-life its own h2 run had just chosen:
#: row 10 at H=300 on the narrow alpha grid, rows 20 and 31 at H=500 and H=400
#: on the widened one. The three (H, alpha=1.0) members are the same
#: configurations as h2 columns and dedup onto them.
H3_FAMILIES: tuple[tuple[float, tuple[float, ...]], ...] = (
    (300.0, (0.25, 0.5, 1.0, 2.0, 5.0)),
    (500.0, (0.02, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0)),
    (400.0, (0.02, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0)),
)

#: h14 and h20 both swept a weight whose zero arm is bit-for-bit the base head
#: (`walkforward`'s docstring guarantees it), so w=0.0 is omitted here and the
#: head itself joins both views as the h3 (400, 0.1) column.
H14_PRIOR_WEIGHTS: tuple[float, ...] = (0.25, 0.5, 0.75, 1.0)
H20_BLEND_WEIGHTS: tuple[float, ...] = (0.15, 0.3, 0.45, 0.6, 0.8)

#: 11 half-lives + 18 new alphas + 4 priors + 5 blends. Asserted, not trusted.
N_COLUMNS = 38

#: Decision 9's audit, performed on 2026-08-15 against the ledger as it then
#: stood: every armed row that is *not* one of `GRIDS`, and the §9.2 condition
#: that excludes it. This is historical fact and is pinned rather than
#: re-derived -- but the rows themselves are read live, so a gate added after
#: this was written appears as an unclassified name and stops the run.
EXCLUDED: dict[str, str] = {
    "h38_channel_blend": "5 -- post-hoc (trials.POST_HOC_TRIALS)",
    "h19_alpha_interaction": "5 -- post-hoc",
    "p5_book_no_arb": "5 -- post-hoc (also 2: not goal deviance)",
    "h39_channel_decomposition": "5 -- post-hoc",
    "h1_cadence": "1 -- probe; weekly is P0's default, kept, no selection rule",
    "h4_h_alpha_interaction": "1 -- separability probe, nothing selected",
    # Records `chosen` + `rule`, so it passes the condition-1 sub-rule -- its
    # exclusion rests on condition 3 alone: the guard scores with 2020-21 and
    # 2021-22 dropped, which is not the common dev scoring population. (The
    # main sweep's choice also governed; the guard only checked it held.)
    "h2_covid_guard": "3 -- scored with 2020-21/2021-22 excluded, not the "
                      "common population",
    # The most contestable call in this table, and it is recorded as such:
    # H5 adjudicated a pre-registered accept/reject bar, and the null kept the
    # default rather than choosing between alternatives.
    "h5_new1_ec_inclusion": "1 -- accept/reject gate; the null kept the default",
    "h15_channels": "1 -- diagnostic after h14 chose w=0",
    "h16_cold_population": "1 and 3 -- population contrast, not head configs",
    "h17_oracle_control": "1 -- oracle; never a candidate",
    "h25_shots_oracle_control": "1 -- oracle",
    "h37_channels_oracle_control": "1 -- oracle",
    "h21_shots_sides": "1 -- decomposition diagnostic; 'both' was the "
                       "pre-registered form",
    "h36_travel_arms": "1 -- accept/reject bar; nothing adopted",
    "p5_meta_arms": "2 -- scored in selected-leg return",
    "tips_confidence_rule": "2 -- strike rate",
    "b2_b3_selection": "2 -- product currency",
    "draw_mass_tipster": "2 -- product currency",
    "b2_calibration_in_product": "2 -- product currency",
    "b14_corners_in_product": "2 -- strike rate (the doc's own worked example)",
    "home_term_dispersion": "1 -- measurement gate",
    "home_term_away_leg": "1 -- measurement gate",
    "slope_zeroing_stretch": "1 -- accept/reject; not adopted",
}


@dataclass(frozen=True)
class Column:
    """One configuration in the pooled matrix, and the grid views it sits in."""

    key: str
    cfg: WalkForwardConfig
    with_prior: bool
    grids: tuple[str, ...]


def _normalise(cfg: WalkForwardConfig) -> WalkForwardConfig:
    """Fold the arms whose zero setting is bit-for-bit the head they nest.

    `walkforward` guarantees that `squad_prior` at 0 (or with no priors) and
    `shots_blend` at 0 leave the fit unchanged. Those arms are therefore the
    *same column* as the base head, and folding them here is what makes the
    dedup exact rather than a judgement about how close is close enough.
    """
    if cfg.squad_prior in (None, 0.0):
        cfg = replace(cfg, squad_prior=None)
    if cfg.shots_blend in (None, 0.0):
        cfg = replace(cfg, shots_blend=None)
    return cfg


def identity(cfg: WalkForwardConfig, with_prior: bool = False) -> str:
    """The dedup key: the normalised label, plus whether a prior is attached.

    Two configurations with the same label differ only if one of them carries a
    ridge target and the other does not, so the marker is the rest of the
    identity. `cfg.label()` carries everything else that varies here.
    """
    cfg = _normalise(cfg)
    carries = bool(with_prior) and cfg.squad_prior is not None
    return f"{cfg.label()}|prior_object={carries}"


def build_columns() -> tuple[Column, ...]:
    """The 38 distinct configurations of Decision 9, in a stable order."""
    out: dict[str, Column] = {}

    def add(cfg: WalkForwardConfig, grid: str, *, with_prior: bool = False) -> None:
        key = identity(cfg, with_prior)
        seen = out.get(key)
        if seen is None:
            out[key] = Column(key, _normalise(cfg), with_prior=with_prior,
                              grids=(grid,))
        elif grid not in seen.grids:
            out[key] = replace(seen, grids=(*seen.grids, grid))

    for half_life in H2_HALF_LIVES:
        add(replace(BASE, half_life=half_life), "h2_half_life")
    for half_life, alphas in H3_FAMILIES:
        for alpha in alphas:
            add(replace(BASE, half_life=half_life, alpha=alpha), "h3_alpha")
    # The base head joins both weight sweeps as their w=0 arm.
    add(HEAD, "h14_squad_prior")
    for weight in H14_PRIOR_WEIGHTS:
        add(replace(HEAD, squad_prior=weight), "h14_squad_prior", with_prior=True)
    add(HEAD, "h20_shots_blend")
    for weight in H20_BLEND_WEIGHTS:
        add(replace(HEAD, shots_blend=weight), "h20_shots_blend")

    assert len(out) == N_COLUMNS, f"{len(out)} columns, Decision 9 says {N_COLUMNS}"
    return tuple(out.values())


# --- the excluded table, derived live from the ledger -----------------------


class _LedgerSubset:
    """Feeds a subset of ledger rows to `trials.count_configurations`.

    Reusing that function rather than re-deriving a count keeps the per-name
    figure on Decision 1's mechanical rule -- including the repeat collapse that
    makes `p5_meta_arms` four configurations across four rows and not sixteen.
    A second implementation of that rule would be free to disagree with it.
    """

    def __init__(self, rows):
        self._rows = list(rows)

    def execute(self, _query):
        return self._rows


def _configurations_of(rows) -> int:
    return trials.count_configurations(_LedgerSubset(rows)).configurations


def audit(conn) -> dict[str, dict]:
    """The excluded table: rows read live, reasons pinned by Decision 9.

    Fails loudly on an armed row `EXCLUDED` does not classify. A gate added
    after §9 was written has to be judged by a human against the five
    conditions; silently dropping it -- or silently admitting it -- is exactly
    the after-the-fact choice this document exists to prevent.
    """
    armed: dict[str, list[dict]] = {}
    for row in conn.execute("SELECT id, name, detail FROM gate_ledger"):
        row = dict(row)
        if trials._arm_list(row["detail"]) is not None:
            armed.setdefault(row["name"], []).append(row)

    unclassified = sorted(set(armed) - set(GRIDS) - set(EXCLUDED))
    if unclassified:
        raise ValueError(
            f"armed ledger rows no Decision 9 audit covers: {', '.join(unclassified)}. "
            f"Classify each against docs/DEFLATION.md §9.2's five conditions -- "
            f"into GRIDS if a selection was made from it, otherwise into "
            f"EXCLUDED with its condition -- and record the judgement.")

    return {name: {"rows": tuple(r["id"] for r in rows),
                   "configs": _configurations_of(rows),
                   "condition": EXCLUDED[name]}
            for name, rows in sorted(armed.items()) if name in EXCLUDED}


# --- the matrix -------------------------------------------------------------


def level_priors(conn, matches: pd.DataFrame) -> squad.SquadPriors:
    """The h14 ridge target, rebuilt exactly as `p2.main` builds it.

    Imported from p2 rather than copied, so the prior these four columns carry
    is the one H14 actually swept and not a second implementation of it.
    """
    players = load_players(conn)
    history = build_history(matches, players, HEAD)
    return squad.build(history, ("sq_att", "sq_dfn"), label="level")


def score_columns(frame: pd.DataFrame, columns, priors) -> dict[str, pd.DataFrame]:
    """One walk-forward per column, restricted to the served divisions.

    The COVID scoring embargo comes from the config, so every column is on the
    common dev scoring population Decision 9's condition 3 requires.
    """
    scored = {}
    for position, column in enumerate(columns, 1):
        print(f"  [{position:2d}/{len(columns)}] {column.cfg.label()}"
              + ("  +level prior" if column.with_prior else ""))
        out = walk_forward(frame, column.cfg, priors if column.with_prior else None)
        scored[column.key] = served(out)
    return scored


def weekly_matrix(scored: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, int]:
    """Align the columns, then aggregate their loss to week blocks.

    Returns the weeks x columns matrix CSCV consumes and the size of the common
    match set. Two things are load-bearing:

    - alignment, because columns can differ in coverage (a longer decay horizon
      reaches the minimum training size on a different date) and CSCV compares
      column means against one another on a shared period axis;
    - `bootstrap.week_blocks` as the period axis, so the dependence structure
      the paired bootstrap respects is respected here too (§3).

    Values are **negated** mean deviance: deviance is a loss and `cscv_pbo`
    wants higher-is-better.
    """
    aligned = _align(scored)
    any_column = next(iter(aligned.values()))
    blocks = bootstrap.week_blocks(any_column.index.get_level_values("match_date"))
    losses = {key: metrics.goal_deviance(out) for key, out in aligned.items()}
    matrix = -pd.DataFrame(losses).groupby(blocks).mean()
    matrix.index.name = "week_block"
    return matrix, len(any_column)


def per_grid(matrix: pd.DataFrame, columns) -> dict[str, trials.PBOResult]:
    """PBO on each grid on its own, for §6's choice_mattered-hole check.

    Computed and reported unconditionally, in the same run as the pooled
    statistic: a per-grid view produced only once the pooled one had been seen
    would be a second look chosen after the first one's answer.
    """
    return {grid: trials.cscv_pbo(
                matrix[[c.key for c in columns if grid in c.grids]], blocks=BLOCKS)
            for grid in GRIDS}


# --- the verdict and the row ------------------------------------------------


def verdict(result: trials.PBOResult) -> dict:
    """Criterion 1, in §5's and §6's own terms.

    §5 asks for PBO <= 0.20 *provided* `choice_mattered` is true. §6 settles the
    other branch in advance, and that is why the proviso is not a loophole: when
    `choice_mattered` is false the spread is below the paired standard-error
    scale, PBO is uninterpretable, and the criterion is satisfied by the spread
    being negligible -- a selection among indistinguishable options cannot have
    overfitted to anything. `choice_mattered` is exactly `spread > 1e-3`, so the
    two branches are complete and disjoint.
    """
    if not result.choice_mattered:
        return {"passes": True, "basis": "negligible spread",
                "statement": (f"spread {result.spread:.6f} <= {SPREAD_FLOOR:g}: the "
                              f"configurations are indistinguishable, PBO "
                              f"{result.pbo:.3f} is uninterpretable, and "
                              f"DEFLATION.md §6 satisfies criterion 1 on the "
                              f"spread")}
    passes = result.pbo <= PBO_THRESHOLD
    return {"passes": passes, "basis": "pbo",
            "statement": (f"PBO {result.pbo:.3f} {'<=' if passes else '>'} "
                          f"{PBO_THRESHOLD:.2f} with the trials distinguishable "
                          f"(spread {result.spread:.6f}): criterion 1 "
                          f"{'holds' if passes else 'FAILS'}")}


def build_detail(result: trials.PBOResult, grids: dict, columns, audited: dict, *,
                 n_weeks: int, n_matches: int, unattributed: int) -> dict:
    """The ledger row's `detail`.

    **No key named `arms`, here or nested, and that is a constraint rather than
    a style choice.** `trials.count_configurations` reads any `arms` key as
    configurations the row spent, and Decision 8 says this probe spends none:
    re-scoring configurations already counted is the identical computation on
    the same data. The column labels go under `columns` for that reason.
    """
    return {
        "pbo": result.pbo,
        "degradation": result.degradation,
        "spread": result.spread,
        "n_trials": result.n_trials,
        "n_splits": result.n_splits,
        "n_weeks": n_weeks,
        "n_matches_aligned": n_matches,
        "per_grid": {name: {"pbo": grid.pbo, "degradation": grid.degradation,
                            "spread": grid.spread, "n_trials": grid.n_trials}
                     for name, grid in grids.items()},
        "columns": [column.cfg.label() for column in columns],
        # `rows` is dropped rather than carried: §9's detail shape is configs
        # and condition, and the row ids are in the printed report.
        "excluded": {name: {"configs": entry["configs"],
                            "condition": entry["condition"]}
                     for name, entry in audited.items()},
        "unattributed": unattributed,
        "verdict": verdict(result),
    }


REASON = (
    "DEFLATION.md Decision 8: criterion 1 is computed entirely on the "
    "development set and is ordered before any holdout read, so a PBO above "
    "0.20 with choice_mattered true fails P6 without the holdout being spent. "
    "First PBO on the pooled selection matrix -- the instrument-validation "
    "probe (row 52, deflation_instrument_validation) covered only P1's 8-arm "
    "alpha grid. Columns fixed by Decision 9; the excluded grids and their "
    "conditions are recorded alongside, per Decision 6's spirit. Re-scoring "
    "configurations already counted spends none, so this row records no arm "
    "list."
)


# --- driver -----------------------------------------------------------------


DRY_RUN_HELP = (
    "build the matrix and print the audit, but compute no PBO and write no "
    "ledger row -- a dry run that showed the number would be an unrecorded "
    "look at the dev set, and the p5 lesson (META.md §9) is that development "
    "runs must not write rows"
)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help=DRY_RUN_HELP)
    args = parser.parse_args(argv)

    conn = db.connect()
    # DEFLATION.md §1: `count_configurations` raises an opaque ValueError
    # without this. `db.connect` sets it already; stated here because the
    # requirement belongs to this module rather than to that one.
    conn.row_factory = sqlite3.Row

    failures = build.validate(conn)
    if failures:
        print("corpus integrity check failed -- no number here would be trusted:")
        for failure in failures:
            print(f"  {failure}")
        return 1

    # The audit runs before the corpus is touched: an unclassified gate must
    # cost seconds, not thirty-eight walk-forwards.
    count = trials.count_configurations(conn)
    audited = audit(conn)
    print(f"trial accounting, re-derived now: {count.describe()}")

    print("\nexcluded from the selection matrix (DEFLATION.md §9.2):")
    for name, entry in audited.items():
        rows = ",".join(str(i) for i in entry["rows"])
        print(f"  {name:28s} rows {rows:16s} {entry['configs']:3d} configs"
              f"  condition {entry['condition']}")
    print(f"  and {count.unattributed} rows carry no arm list: their "
          f"configurations cannot be reconstructed into columns at all, so "
          f"every statement of the count reads 'at least' (Decision 6)")

    columns = build_columns()
    print(f"\n{len(columns)} columns (Decision 9):")
    for column in columns:
        print(f"  {column.cfg.label():44s} {'+'.join(column.grids)}")

    frame = load(conn)
    print(f"\ndevelopment corpus: {len(frame):,} matches, "
          f"{frame.season.min()}-{frame.season.max()}, "
          f"{sorted(frame.division.unique())}")
    priors = level_priors(conn, frame)
    print(f"  level prior built for {len(priors.att)} seasons")

    scored = score_columns(frame, columns, priors)
    matrix, n_matches = weekly_matrix(scored)
    print(f"\nmatrix {matrix.shape[0]} weeks x {matrix.shape[1]} columns, "
          f"aligned on {n_matches:,} matches")

    if args.dry_run:
        print("\ndry run: no PBO computed, no ledger row written.")
        return 0

    result = trials.cscv_pbo(matrix, blocks=BLOCKS)
    grids = per_grid(matrix, columns)
    detail = build_detail(result, grids, columns, audited,
                          n_weeks=matrix.shape[0], n_matches=n_matches,
                          unattributed=count.unattributed)

    # Recorded before it is read. A crash between the look and the record would
    # otherwise leave a look at the dev set that no ledger row accounts for.
    row_id = ledger.record(conn, kind=ledger.PROBE, name=LEDGER_NAME,
                           purpose="dev", seasons=DEV_SEASONS,
                           divisions=SERVED_DIVISIONS, detail=detail,
                           reason=REASON)
    print(f"\n  [ledger] {ledger.PROBE}:{LEDGER_NAME} #{row_id}")

    print(f"\n{result.describe()}")
    print("\nper grid:")
    for name, grid in grids.items():
        print(f"  {name}")
        print(f"    {grid.describe()}")
    print(f"\ncriterion 1: {'PASS' if detail['verdict']['passes'] else 'FAIL'} -- "
          f"{detail['verdict']['statement']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
