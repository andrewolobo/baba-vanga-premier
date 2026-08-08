"""Trial accounting and backtest-overfitting probability, for the P6 read.

Two jobs, deliberately kept apart.

**Counting.** How many configurations were tried against the development set is
a question of fact, so it is derived from the ledger by `count_configurations`
rather than argued in a document. `OUTSTANDING.md` §3.2 framed this as "51
trials or 13 distinct questions?" -- both wrong, and wrong in the same
direction. The ledger stores one row per *run*, and a run of a sweep holds a
whole grid: `h2_half_life` alone is nine configurations in one row. The count
that matters is arms, and it is larger than either number under debate.

**Deflating.** `cscv_pbo` implements Combinatorially Symmetric Cross-Validation
(Bailey, Borwein, Lopez de Prado & Zhu, 2016). Its virtue here is that **it does
not take a trial count as an input.** It consumes the per-period performance of
every configuration and estimates directly how often the in-sample winner lands
below the out-of-sample median. Correlated trials -- and ours are nearly
collinear, a whole alpha grid spanning 0.0085 nats -- are handled by
construction rather than by an effective-N fudge factor. That is what makes the
"how do we count re-runs" argument dissolve instead of needing a verdict.

**A trap worth naming before anyone reads the output.** PBO near 0.5 means the
in-sample winner is no better than a coin flip out of sample. When the
configurations are genuinely different that is damning. When they are nearly
identical it is *inevitable and harmless*, because there is nothing to choose
between them. So `PBOResult` reports `degradation` alongside: how much
performance the in-sample winner actually gives up. PBO answers "was the choice
lucky"; degradation answers "did the choice matter". Neither is interpretable
without the other, so neither is returned without the other.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from itertools import combinations

import numpy as np
import pandas as pd

#: Blocks the period axis is cut into. C(16, 8) = 12,870 splits, which is ample
#: and still runs in seconds. Must be even.
DEFAULT_BLOCKS = 16


# --- counting --------------------------------------------------------------


@dataclass(frozen=True)
class TrialCount:
    """What was spent against the development set."""

    runs: int                 # ledger rows
    questions: int            # distinct hypothesis names
    configurations: int       # arms -- the number that matters
    unattributed: int         # rows whose detail records no arm list
    post_hoc: tuple[str, ...] # named, and excluded from pre-registration claims
    repeats: int = 0          # rows collapsed as the same computation re-run

    def describe(self) -> str:
        repeated = f", {self.repeats} repeat run(s) collapsed" if self.repeats else ""
        return (f"{self.runs} runs / {self.questions} distinct questions / "
                f"**{self.configurations} configurations** "
                f"({self.unattributed} rows carry no arm list{repeated}); "
                f"post-hoc: {', '.join(self.post_hoc) or 'none'}")


#: Recorded as post-hoc at the time it was run. Excluded from any claim that the
#: selection was pre-registered; see `docs/DEFLATION.md` §4.
POST_HOC_TRIALS: tuple[str, ...] = ("h19_alpha_interaction", "p5_book_no_arb")


def _arms_in(detail) -> int | None:
    """Number of configurations a ledger row scored, if it recorded them."""
    if isinstance(detail, str):
        try:
            detail = json.loads(detail)
        except (TypeError, ValueError):
            return None
    if not isinstance(detail, dict):
        return None
    arms = detail.get("arms")
    if isinstance(arms, (list, dict)):
        return len(arms)
    return None


def _arm_list(detail):
    """The recorded arm list as a sequence of arms, or None."""
    if isinstance(detail, str):
        try:
            detail = json.loads(detail)
        except (TypeError, ValueError):
            return None
    if not isinstance(detail, dict):
        return None
    arms = detail.get("arms")
    if isinstance(arms, dict):
        return list(arms.values())
    return arms if isinstance(arms, list) else None


#: Fields that name an arm rather than report what it did. A run whose arms
#: carry nothing else cannot be shown to have reproduced an earlier one, so it
#: is never collapsed -- `b2_b3_selection` recorded bare names and two runs that
#: really did differ would otherwise have merged. Silence is not agreement.
_IDENTITY_KEYS = frozenset({"arm", "name", "label", "value"})


def _signature(arms, shared: frozenset) -> tuple:
    """A comparable form of one run's arms, over the fields every run recorded.

    Restricted to `shared` because a gate re-run with an extra *reporting* field
    is the same computation, and a digest over the raw payload would call it a
    new one. What survives is the part every run of that name agreed to record,
    which is exactly the claim "these produced the same numbers".
    """
    out = []
    for arm in arms:
        if isinstance(arm, dict):
            out.append(tuple(sorted(
                (k, json.dumps(v, sort_keys=True, default=str))
                for k, v in arm.items() if k in shared)))
        else:
            out.append(json.dumps(arm, sort_keys=True, default=str))
    return tuple(out)


def count_configurations(conn) -> TrialCount:
    """Count what the ledger actually records. Derived, never negotiated.

    **Re-running the identical computation does not spend again.** Multiplicity
    is the number of configurations chosen among, and four runs of one gate that
    produced identical numbers offered one chance to be fooled, not four. This
    happened for real: `p5_meta_arms` wrote a row on each of four implementation
    runs as reporting was added, byte-identical in every arm result
    (`META.md` §9).

    **A re-run whose numbers changed still spends**, and must: `OUTSTANDING.md`
    §7.5 records the rest gate running before and after a correctness fix, and
    both rows count because both were real attempts at the answer. The line is
    whether the results moved, not whether the code did.
    """
    rows = [dict(r) for r in conn.execute("SELECT name, detail FROM gate_ledger")]
    by_name: dict[str, list] = {}
    for row in rows:
        arms = _arm_list(row["detail"])
        if arms is not None:
            by_name.setdefault(row["name"], []).append(arms)

    configurations, repeats = 0, 0
    for runs in by_name.values():
        shared = frozenset.intersection(*[
            frozenset(a) for run in runs for a in run if isinstance(a, dict)
        ]) if any(isinstance(a, dict) for run in runs for a in run) else frozenset()
        if not (shared - _IDENTITY_KEYS):
            configurations += sum(len(arms) for arms in runs)
            continue
        seen = {}
        for arms in runs:
            seen.setdefault(_signature(arms, shared), len(arms))
        configurations += sum(seen.values())
        repeats += len(runs) - len(seen)

    return TrialCount(
        runs=len(rows),
        questions=len({r["name"] for r in rows}),
        configurations=configurations,
        unattributed=sum(1 for r in rows if _arm_list(r["detail"]) is None),
        post_hoc=tuple(sorted({r["name"] for r in rows} & set(POST_HOC_TRIALS))),
        repeats=repeats,
    )


# --- CSCV ------------------------------------------------------------------


@dataclass(frozen=True)
class PBOResult:
    """PBO with the companion statistic that makes it readable."""

    pbo: float             # P(in-sample winner ranks below the OOS median)
    degradation: float     # OOS performance of the IS winner, minus the OOS median
    spread: float          # best minus worst mean performance across trials
    n_trials: int
    n_splits: int
    logits: np.ndarray

    @property
    def choice_mattered(self) -> bool:
        """Whether the trials are distinguishable enough for PBO to mean anything.

        The threshold is the paired standard error scale on this corpus: below
        roughly 0.001 nats the configurations are interchangeable and a PBO of
        0.5 reflects that, not overfitting.
        """
        return self.spread > 1e-3

    def describe(self) -> str:
        verdict = ("informative" if self.choice_mattered else
                   "UNINFORMATIVE -- trials are near-identical, so PBO ~ 0.5 is "
                   "expected and does not indicate overfitting")
        return (f"PBO {self.pbo:.3f} over {self.n_splits:,} splits of "
                f"{self.n_trials} trials\n"
                f"  degradation {self.degradation:+.6f}  "
                f"spread {self.spread:.6f}  -> {verdict}")


def cscv_pbo(performance: pd.DataFrame, *, blocks: int = DEFAULT_BLOCKS) -> PBOResult:
    """Probability of backtest overfitting, by combinatorially symmetric CV.

    `performance` is periods (rows) x configurations (columns), **higher is
    better**. Goal deviance and logloss are losses, so negate them before
    calling; doing that here would silently invert a caller who had already
    remembered.

    The period axis must be something that blocks meaningfully -- ISO week, to
    match `bootstrap.week_blocks`, so that the dependence structure the paired
    bootstrap respects is respected here too.
    """
    if blocks % 2:
        raise ValueError(f"blocks must be even for a symmetric split, got {blocks}")
    matrix = performance.to_numpy(dtype=float)
    n_periods, n_trials = matrix.shape
    if n_trials < 2:
        raise ValueError("PBO needs at least two configurations to choose between")
    if n_periods < blocks:
        raise ValueError(f"{n_periods} periods cannot be cut into {blocks} blocks")

    parts = np.array_split(np.arange(n_periods), blocks)
    logits, shortfalls = [], []
    for chosen in combinations(range(blocks), blocks // 2):
        in_rows = np.concatenate([parts[b] for b in chosen])
        out_rows = np.concatenate([parts[b] for b in range(blocks)
                                   if b not in chosen])
        best = int(np.argmax(matrix[in_rows].mean(axis=0)))
        oos = matrix[out_rows].mean(axis=0)
        # Relative rank of the in-sample winner among out-of-sample results.
        rank = float((oos <= oos[best]).sum())
        w = rank / (n_trials + 1.0)
        w = min(max(w, 1e-9), 1 - 1e-9)
        logits.append(np.log(w / (1 - w)))
        # What the choice actually cost, in the metric's own units: the winner's
        # out-of-sample performance against the field's median. Measured per
        # split rather than on full-sample means, which would compare the
        # in-sample winner with itself.
        shortfalls.append(oos[best] - np.median(oos))

    logits = np.asarray(logits)
    means = matrix.mean(axis=0)
    return PBOResult(
        pbo=float((logits <= 0).mean()),
        degradation=float(np.mean(shortfalls)),
        spread=float(means.max() - means.min()),
        n_trials=n_trials,
        n_splits=len(logits),
        logits=logits,
    )
