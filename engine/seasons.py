"""Seasons, divisions and datable regime breaks.

This module is the single authority for what a division code means.
`data/play_history/mapping.txt` mislabels EC as "Championship" (duplicating E1);
EC is the National League. That file is never read by the engine.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

# --- Divisions -------------------------------------------------------------


@dataclass(frozen=True)
class Division:
    code: str
    name: str
    tier: int
    player_subdir: str  # relative to data/player-stats
    player_suffix: str  # League One files carry a .txt extension


DIVISIONS: dict[str, Division] = {
    "E0": Division("E0", "Premier League", 1, ".", ".csv"),
    "E1": Division("E1", "Championship", 2, "efl-championship", ".csv"),
    "E2": Division("E2", "League One", 3, "efl-league-one", ".txt"),
    "E3": Division("E3", "League Two", 4, "efl-league-two", ".csv"),
    "EC": Division("EC", "National League", 5, "national-league", ".csv"),
}

#: Divisions the engine serves markets for. EC is loaded and may enter the
#: joint strength fit (NEW-1) but is not a served market.
SERVED_DIVISIONS = ("E0", "E1", "E2", "E3")
ALL_DIVISIONS = tuple(DIVISIONS)


# --- Seasons ---------------------------------------------------------------


def season_code(start_year: int) -> str:
    """2010 -> '201011'."""
    return f"{start_year}{(start_year + 1) % 100:02d}"


def season_start_year(code: str) -> int:
    """'201011' -> 2010."""
    return int(code[:4])


def season_label(code: str) -> str:
    """'201011' -> '2010-11'."""
    return f"{code[:4]}-{code[4:]}"


FIRST_SEASON_YEAR = 2010
LAST_SEASON_YEAR = 2025  # 2025-26, the most recent complete season on disk

SEASONS: tuple[str, ...] = tuple(
    season_code(y) for y in range(FIRST_SEASON_YEAR, LAST_SEASON_YEAR + 1)
)

#: Sealed per OPEN-9. Never read by a gate, sweep or exploratory query.
#: Enforced structurally in `engine.ingest.holdout`, not by convention.
HOLDOUT_SEASONS: frozenset[str] = frozenset({"202324", "202425", "202526"})

#: Everything a gate may look at.
DEV_SEASONS: tuple[str, ...] = tuple(s for s in SEASONS if s not in HOLDOUT_SEASONS)


def is_holdout(code: str) -> bool:
    return code in HOLDOUT_SEASONS


# --- Regime breaks ---------------------------------------------------------


@dataclass(frozen=True)
class Regime:
    name: str
    start: dt.date
    end: dt.date | None  # None = still in force
    note: str


#: Datable breaks to embargo across in every walk-forward split.
#:
#: The SPEC planned to identify empty-stadium matches from an `Attendance`
#: column. That column is absent from all 80 source files, so the COVID regime
#: is a date window instead (NEW-3). Boundaries: football suspended 13 Mar 2020;
#: crowds returned in full for 2021-22.
REGIMES: tuple[Regime, ...] = (
    Regime(
        "covid_empty_stadiums",
        dt.date(2020, 3, 13),
        dt.date(2021, 5, 31),
        "Suspension, Project Restart and the behind-closed-doors 2020-21 season. "
        "Home advantage is not comparable across this boundary.",
    ),
    Regime(
        "var_e0",
        dt.date(2019, 8, 9),
        None,
        "VAR introduced in the Premier League from 2019-20. E0 only.",
    ),
)


def regimes_at(day: dt.date) -> tuple[str, ...]:
    """Names of regimes in force on `day`."""
    return tuple(
        r.name for r in REGIMES if r.start <= day and (r.end is None or day <= r.end)
    )


def crosses_regime_boundary(start: dt.date, end: dt.date) -> tuple[str, ...]:
    """Regimes whose start or end falls inside (start, end].

    A train/test split spanning any of these is embargoed.
    """
    out = []
    for r in REGIMES:
        if start < r.start <= end:
            out.append(r.name)
        elif r.end is not None and start < r.end <= end:
            out.append(r.name)
    return tuple(out)
