"""The holdout guard.

OPEN-9 seals 2023-24, 2024-25 and 2025-26. A policy that lives only in a
document gets violated by accident, so it lives here instead, at the one place
data enters the engine.

The distinction that makes this workable: **fitting is not measuring.**

Serving predictions for 2026-27 legitimately requires match data from 2023-26 --
a model cannot know a team's current strength without it. What must never
happen is a *measurement* touching those seasons, because that is what burns the
holdout's ability to adjudicate. So loaders return a `Corpus` that carries its
own purpose, and anything that computes a metric takes the corpus (not a bare
DataFrame) and calls `for_measurement()`, which refuses a LIVE corpus.

    Purpose.DEV           gates, sweeps, probes. Seasons <= 2022-23. The default.
    Purpose.LIVE          fitting the served artifact. All seasons. Never scored.
    Purpose.HOLDOUT_READ  the single P6 read. Needs a reason and a ledger write.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import pandas as pd

from engine import db, ledger
from engine.seasons import DEV_SEASONS, HOLDOUT_SEASONS, SEASONS


class Purpose(Enum):
    DEV = "dev"
    LIVE = "live"
    HOLDOUT_READ = "holdout_read"

    def __str__(self) -> str:
        return self.value


class HoldoutViolation(RuntimeError):
    """An attempt to read sealed seasons without going through the unseal path."""


class MeasurementOnLiveCorpus(RuntimeError):
    """An attempt to score a corpus that was loaded for fitting, not evaluation."""


@dataclass(frozen=True)
class Corpus:
    """A frame plus the provenance that decides what may be done with it."""

    frame: pd.DataFrame
    purpose: Purpose
    seasons: tuple[str, ...]
    divisions: tuple[str, ...]

    def __len__(self) -> int:
        return len(self.frame)

    @property
    def touches_holdout(self) -> bool:
        return bool(set(self.seasons) & HOLDOUT_SEASONS)

    def for_measurement(self) -> pd.DataFrame:
        """The frame, for anything that computes a metric.

        Every evaluation entry point must go through here rather than reading
        `.frame`, so that a corpus loaded for live fitting cannot be scored.
        """
        if self.purpose is Purpose.LIVE:
            raise MeasurementOnLiveCorpus(
                "this corpus was loaded with Purpose.LIVE for fitting the served "
                "artifact and includes sealed seasons; measuring on it would burn "
                "the holdout. Reload with Purpose.DEV to measure."
            )
        return self.frame


def resolve_seasons(
    purpose: Purpose,
    requested: tuple[str, ...] | None,
    *,
    conn: db.Connection | None = None,
    unseal_reason: str | None = None,
    name: str = "unnamed",
) -> tuple[str, ...]:
    """Which seasons this purpose may see, refusing the sealed ones for DEV.

    A DEV read that explicitly names a sealed season raises rather than quietly
    dropping it: silently returning 13 seasons to someone who asked for 16 is
    how a holdout gets believed-in but not enforced.
    """
    if purpose is Purpose.DEV:
        if requested is None:
            return DEV_SEASONS
        sealed = sorted(set(requested) & HOLDOUT_SEASONS)
        if sealed:
            raise HoldoutViolation(
                f"seasons {sealed} are sealed by OPEN-9 and unavailable to "
                f"Purpose.DEV. To fit a serving artifact use Purpose.LIVE; to "
                f"perform the one-time P6 read use Purpose.HOLDOUT_READ with a "
                f"reason and a database connection."
            )
        return tuple(requested)

    if purpose is Purpose.LIVE:
        return tuple(requested) if requested is not None else SEASONS

    # HOLDOUT_READ: deliberate, reasoned and recorded.
    if conn is None or not unseal_reason:
        raise HoldoutViolation(
            "Purpose.HOLDOUT_READ requires both a database connection and an "
            "unseal_reason, because every unseal is written to the gate ledger."
        )
    seasons = tuple(requested) if requested is not None else SEASONS
    ledger.record(
        conn,
        kind=ledger.HOLDOUT_UNSEAL,
        name=name,
        purpose=str(purpose),
        seasons=seasons,
        reason=unseal_reason,
    )
    return seasons
