"""As-of correctness: information sets, feature declarations, and the leak canary.

Lineup and team-news leakage is the single most common way a football model
produces an excellent fictional backtest (SPEC §7), and unlike gtleague's
domain there is no analogue to borrow a defence from. So the rule is made
mechanical rather than remembered:

    A feature evaluated at a decision moment may not depend on anything
    unknowable at that moment.

`assert_no_future_dependence` enforces it by corrupting the unknowable part of
the frame and asserting the feature's output does not move. A feature that
passes cannot be reading the future; a feature that fails is doing so, whatever
its author believed.

The two information sets are structural in the source, not hypothetical:
football-data collects pre-closing prices on Friday and Tuesday afternoons --
*before* team news -- and closing prices at kickoff, *after* it.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable

import numpy as np
import pandas as pd

from engine.seasons import season_code, season_start_year


class InformationSet(Enum):
    """What is knowable at the decision moment."""

    PRE_CLOSE = "pre_close"  # Friday/Tuesday PM. Before team news and lineups.
    CLOSING = "closing"      # At kickoff. After team news.

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class AsOf:
    """A decision point. Nothing dated at or after `moment` is knowable."""

    moment: pd.Timestamp
    information_set: InformationSet = InformationSet.PRE_CLOSE

    def __post_init__(self) -> None:
        object.__setattr__(self, "moment", pd.Timestamp(self.moment))

    def is_future(self, dates: pd.Series) -> pd.Series:
        return pd.to_datetime(dates) >= self.moment


# --- What each information set cannot see ---------------------------------

#: Settled at kickoff, so unknowable for any match not yet played.
OUTCOME_COLUMNS: tuple[str, ...] = (
    "fthg", "ftag", "ftr", "hthg", "htag", "htr",
    "home_shots", "away_shots", "home_sot", "away_sot",
    "home_corners", "away_corners", "home_fouls", "away_fouls",
    "home_yellow", "away_yellow", "home_red", "away_red",
)

#: Published at kickoff. Available for past matches; not for the one being priced.
CLOSING_ODDS_COLUMNS: tuple[str, ...] = (
    "close_ps_h", "close_ps_d", "close_ps_a",
    "close_b365_h", "close_b365_d", "close_b365_a",
    "close_avg_h", "close_avg_d", "close_avg_a",
    "close_max_h", "close_max_d", "close_max_a",
    "close_avg_over25", "close_avg_under25",
    "close_ah_line", "close_avg_ah_h", "close_avg_ah_a",
)


def unknowable_columns(information_set: InformationSet) -> tuple[str, ...]:
    """Columns a feature may not read for matches at or after the decision moment.

    Pre-closing prices are deliberately absent from both lists: they are
    collected before the decision moment for the matchday being priced, which
    is precisely what makes them usable. That holds for a matchday-frozen
    walk-forward; a feature reaching for pre-close prices of matches several
    weeks out would not be caught here and needs its own review.
    """
    if information_set is InformationSet.CLOSING:
        return OUTCOME_COLUMNS
    return OUTCOME_COLUMNS + CLOSING_ODDS_COLUMNS


# --- Feature declaration ---------------------------------------------------


@dataclass(frozen=True)
class FeatureSpec:
    name: str
    information_set: InformationSet
    description: str = ""


REGISTRY: dict[str, FeatureSpec] = {}


def feature(name: str, information_set: InformationSet, description: str = ""):
    """Declare a feature's information set.

    The declaration is what the walk-forward harness reads to decide which
    corruption to apply when canarying it, so an undeclared feature is one that
    cannot be checked.
    """

    def decorate(fn: Callable) -> Callable:
        spec = FeatureSpec(name, information_set, description or (fn.__doc__ or "").strip())
        if name in REGISTRY and REGISTRY[name] != spec:
            raise ValueError(f"feature {name!r} already declared differently")
        REGISTRY[name] = spec
        fn.spec = spec  # type: ignore[attr-defined]
        return fn

    return decorate


# --- The leak canary -------------------------------------------------------


def corrupt_future(frame: pd.DataFrame, asof: AsOf, *, seed: int = 0) -> pd.DataFrame:
    """Replace everything unknowable at `asof` with noise.

    Fixture identity (teams, dates, division) is preserved, because a fixture
    list genuinely is known weeks ahead. Only what is settled at kickoff is
    destroyed.
    """
    rng = np.random.default_rng(seed)
    out = frame.copy()
    if "match_date" not in out.columns:
        raise ValueError("frame needs a match_date column to locate the future")

    future = asof.is_future(out["match_date"])
    if not future.any():
        raise ValueError(
            f"no rows at or after {asof.moment}; the canary would pass vacuously"
        )

    changed = False
    for column in unknowable_columns(asof.information_set):
        if column not in out.columns:
            continue
        original = out.loc[future, column]
        if original.isna().all():
            continue
        if column in ("ftr", "htr"):
            replacement = rng.choice(["H", "D", "A"], size=int(future.sum()))
        elif pd.api.types.is_numeric_dtype(out[column]):
            replacement = rng.integers(0, 9, size=int(future.sum()))
            replacement = pd.array(replacement, dtype=out[column].dtype) \
                if str(out[column].dtype) == "Int64" else replacement
        else:
            replacement = rng.integers(0, 9, size=int(future.sum())).astype(str)
        out.loc[future, column] = replacement
        changed = True

    if not changed:
        raise ValueError(
            "nothing was corrupted; the frame carries no unknowable columns, so "
            "the canary would pass vacuously"
        )
    return out


def assert_no_future_dependence(
    fn: Callable[[pd.DataFrame, AsOf], object],
    frame: pd.DataFrame,
    asof: AsOf,
    *,
    seeds: tuple[int, ...] = (0, 1, 2),
) -> None:
    """Raise if `fn`'s output depends on data unknowable at `asof`.

    Several seeds because a single corruption can coincide with the truth.
    """
    baseline = fn(frame, asof)
    for seed in seeds:
        perturbed = fn(corrupt_future(frame, asof, seed=seed), asof)
        if not _equal(baseline, perturbed):
            raise AssertionError(
                f"{getattr(fn, 'spec', fn).__str__()}: output changed when data at or "
                f"after {asof.moment} was corrupted (seed={seed}). The feature is "
                f"reading the future."
            )


def _equal(a, b) -> bool:
    if isinstance(a, pd.DataFrame) and isinstance(b, pd.DataFrame):
        return a.equals(b)
    if isinstance(a, pd.Series) and isinstance(b, pd.Series):
        return a.equals(b)
    if isinstance(a, np.ndarray) and isinstance(b, np.ndarray):
        return np.array_equal(a, b, equal_nan=True)
    return bool(a == b)


# --- Player-layer as-of rule ----------------------------------------------

PLAYER_SEASON_RULE = """\
OPEN-1 resolved to per-season aggregates, so player features refresh at season
boundaries only. A prediction for a match in season N may read player files for
seasons <= N-1; season N's own file is embargoed in its entirety until the
season closes. Squad composition for season N is itself unavailable as-of --
knowing who plays for a club in season N requires reading the embargoed file,
and doing so encodes both the transfer and the survivorship. The honest
construction is a minutes-weighted aggregate over the club's season N-1 roster.
"""


def player_seasons_visible_at(season: str) -> tuple[str, ...]:
    """Season codes a prediction in `season` may read player data for: all <= N-1."""
    target = season_start_year(season)
    return tuple(season_code(y) for y in range(2010, target))
