"""Paired block bootstrap over calendar weeks.

Two arms are compared on the *same* matches, so the statistic is the mean of
the per-match difference in loss. Pairing removes match difficulty from the
comparison, which is most of the variance.

Blocks matter more here than pairing does. Matches in the same week share
teams, share a fitted artifact, and share whatever the league was doing that
weekend, so their losses are correlated. Resampling matches independently would
treat n=24,000 correlated observations as 24,000 independent ones and narrow
every interval in this project -- which is exactly the direction that turns
noise into a shipped decision. Weeks are resampled whole instead.

Sign convention throughout: **negative means the first arm is better**, because
every metric here is a loss.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

DEFAULT_REPS = 2000
RNG_SEED = 20260728


@dataclass(frozen=True)
class Comparison:
    """The difference between two arms, with its uncertainty."""
    delta: float           # mean(loss_a) - mean(loss_b); negative => a better
    ci: tuple[float, float]
    stderr: float
    n: int
    n_blocks: int

    @property
    def excludes_zero(self) -> bool:
        return self.ci[0] > 0.0 or self.ci[1] < 0.0

    @property
    def verdict(self) -> str:
        if not self.excludes_zero:
            return "no difference"
        return "first arm better" if self.delta < 0 else "second arm better"

    def as_dict(self) -> dict:
        return {"delta": self.delta, "ci_low": self.ci[0], "ci_high": self.ci[1],
                "stderr": self.stderr, "n": self.n, "n_blocks": self.n_blocks,
                "excludes_zero": self.excludes_zero, "verdict": self.verdict}


def week_blocks(dates: pd.Series) -> np.ndarray:
    """Integer block id per match: ISO week of the match date."""
    days = pd.to_datetime(pd.Series(dates).reset_index(drop=True))
    return days.dt.to_period("W").astype("int64").to_numpy()


def _block_sums(values: np.ndarray, blocks: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Per-block sum and count, indexed by dense block position."""
    _, positions = np.unique(blocks, return_inverse=True)
    n_blocks = positions.max() + 1
    return (np.bincount(positions, values, minlength=n_blocks),
            np.bincount(positions, minlength=n_blocks).astype(float))


def paired(loss_a, loss_b, blocks, *, reps: int = DEFAULT_REPS,
           alpha: float = 0.05, rng: np.random.Generator | None = None) -> Comparison:
    """Bootstrap the mean paired difference, resampling whole blocks."""
    loss_a = np.asarray(loss_a, dtype=float)
    loss_b = np.asarray(loss_b, dtype=float)
    if loss_a.shape != loss_b.shape:
        raise ValueError("arms must be scored on the same matches to be paired")
    diff = loss_a - loss_b
    blocks = np.asarray(blocks)

    sums, counts = _block_sums(diff, blocks)
    n_blocks = len(sums)
    rng = rng or np.random.default_rng(RNG_SEED)
    draws = rng.integers(0, n_blocks, size=(reps, n_blocks))
    means = sums[draws].sum(axis=1) / counts[draws].sum(axis=1)

    lo, hi = np.quantile(means, [alpha / 2, 1 - alpha / 2])
    return Comparison(
        delta=float(diff.mean()),
        ci=(float(lo), float(hi)),
        stderr=float(means.std(ddof=1)),
        n=len(diff),
        n_blocks=n_blocks,
    )


def standard_error(loss, blocks, *, reps: int = DEFAULT_REPS,
                   rng: np.random.Generator | None = None) -> float:
    """Block-bootstrap standard error of a single arm's mean loss.

    This is what the 1-SE selection rule in `sweep` is measured against.
    """
    loss = np.asarray(loss, dtype=float)
    sums, counts = _block_sums(loss, np.asarray(blocks))
    rng = rng or np.random.default_rng(RNG_SEED)
    draws = rng.integers(0, len(sums), size=(reps, len(sums)))
    means = sums[draws].sum(axis=1) / counts[draws].sum(axis=1)
    return float(means.std(ddof=1))
