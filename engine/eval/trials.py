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

    def describe(self) -> str:
        return (f"{self.runs} runs / {self.questions} distinct questions / "
                f"**{self.configurations} configurations** "
                f"({self.unattributed} rows carry no arm list); "
                f"post-hoc: {', '.join(self.post_hoc) or 'none'}")


#: Recorded as post-hoc at the time it was run. Excluded from any claim that the
#: selection was pre-registered; see `docs/DEFLATION.md` §4.
POST_HOC_TRIALS: tuple[str, ...] = ("h19_alpha_interaction",)


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


def count_configurations(conn) -> TrialCount:
    """Count what the ledger actually records. Derived, never negotiated."""
    rows = [dict(r) for r in conn.execute("SELECT name, detail FROM gate_ledger")]
    arms = [_arms_in(r["detail"]) for r in rows]
    return TrialCount(
        runs=len(rows),
        questions=len({r["name"] for r in rows}),
        configurations=sum(a for a in arms if a),
        unattributed=sum(1 for a in arms if not a),
        post_hoc=tuple(sorted({r["name"] for r in rows} & set(POST_HOC_TRIALS))),
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
