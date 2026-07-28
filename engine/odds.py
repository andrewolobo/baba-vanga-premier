"""Odds: era-unified column mapping, and the two probability conversions.

Two things live here that must never be confused, so they are named so they
cannot be. gtleague conflated them and every EV read was flattered by roughly
five points per side (SPEC §3.8):

    breakeven_prob()  raw 1/odds, vig-INCLUSIVE. The bar an EV decision clears.
    devig_probs()     normalised to sum to 1. The market's opinion. For CLV.

Using devig_probs() as a break-even is the bug. Using breakeven_prob() as the
market's probability estimate is the same bug wearing a hat.
"""

from __future__ import annotations

import numpy as np

# --- Era-unified column mapping -------------------------------------------
#
# football-data replaced the Betbrain aggregates with market Avg/Max at exactly
# the 2018-19 -> 2019-20 boundary. No season carries both, so the era is
# detected from the header rather than hardcoded to a season.

_COMMON = {
    "b365_h": "B365H",
    "b365_d": "B365D",
    "b365_a": "B365A",
    "ps_h": "PSH",  # Pinnacle, from 2012-13
    "ps_d": "PSD",
    "ps_a": "PSA",
}

_BETBRAIN = {
    "avg_h": "BbAvH",
    "avg_d": "BbAvD",
    "avg_a": "BbAvA",
    "max_h": "BbMxH",
    "max_d": "BbMxD",
    "max_a": "BbMxA",
    "avg_over25": "BbAv>2.5",
    "avg_under25": "BbAv<2.5",
    "max_over25": "BbMx>2.5",
    "max_under25": "BbMx<2.5",
    "ah_line": "BbAHh",
    "avg_ah_h": "BbAvAHH",
    "avg_ah_a": "BbAvAHA",
}

_MARKET = {
    "avg_h": "AvgH",
    "avg_d": "AvgD",
    "avg_a": "AvgA",
    "max_h": "MaxH",
    "max_d": "MaxD",
    "max_a": "MaxA",
    "avg_over25": "Avg>2.5",
    "avg_under25": "Avg<2.5",
    "max_over25": "Max>2.5",
    "max_under25": "Max<2.5",
    "ah_line": "AHh",
    "avg_ah_h": "AvgAHH",
    "avg_ah_a": "AvgAHA",
}

#: Closing prices. Pinnacle closing reaches back to 2012-13; everything else
#: starts 2019-20. Pinnacle collapses mid-2025-26 (last E0 close 08/01/2026,
#: E2/E3 out by Nov 2025), so any Pinnacle-anchored metric needs the Avg
#: fallback -- see CLOSING_1X2_PREFERENCE.
_CLOSING = {
    "close_ps_h": "PSCH",
    "close_ps_d": "PSCD",
    "close_ps_a": "PSCA",
    "close_b365_h": "B365CH",
    "close_b365_d": "B365CD",
    "close_b365_a": "B365CA",
    "close_avg_h": "AvgCH",
    "close_avg_d": "AvgCD",
    "close_avg_a": "AvgCA",
    "close_max_h": "MaxCH",
    "close_max_d": "MaxCD",
    "close_max_a": "MaxCA",
    "close_avg_over25": "AvgC>2.5",
    "close_avg_under25": "AvgC<2.5",
    "close_ah_line": "AHCh",
    "close_avg_ah_h": "AvgCAHH",
    "close_avg_ah_a": "AvgCAHA",
}

#: Fallback chain for the CLV anchor, most-preferred first.
CLOSING_1X2_PREFERENCE = (
    ("close_ps_h", "close_ps_d", "close_ps_a"),
    ("close_avg_h", "close_avg_d", "close_avg_a"),
    ("close_max_h", "close_max_d", "close_max_a"),
)

BETBRAIN_ERA = "betbrain"
MARKET_ERA = "market"


def detect_era(columns) -> str:
    """Which odds-aggregate era a source file belongs to, from its header."""
    cols = set(columns)
    has_bb = "BbAvH" in cols
    has_mkt = "AvgH" in cols
    if has_bb and has_mkt:
        raise ValueError("file carries both Betbrain and market aggregates")
    if has_bb:
        return BETBRAIN_ERA
    if has_mkt:
        return MARKET_ERA
    raise ValueError("file carries neither BbAvH nor AvgH")


def column_map(era: str) -> dict[str, str]:
    """canonical field name -> source column name, for one file's era."""
    aggregates = _BETBRAIN if era == BETBRAIN_ERA else _MARKET
    return {**_COMMON, **aggregates, **_CLOSING}


ODDS_FIELDS: tuple[str, ...] = tuple(
    {**_COMMON, **_MARKET, **_CLOSING}
)  # canonical field names, order-stable


# --- Probability conversions ----------------------------------------------


def breakeven_prob(decimal_odds):
    """Raw 1/odds. VIG-INCLUSIVE.

    This is the bar a bet must clear to have positive EV at that price, and the
    only correct denominator for an EV decision. It is deliberately NOT a
    probability estimate: across a market these sum to more than 1.
    """
    odds = np.asarray(decimal_odds, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        out = np.where(odds > 0, 1.0 / odds, np.nan)
    return out if out.ndim else out.item()


def overround(*decimal_odds):
    """Sum of raw implied probabilities across a market. ~1.05 for a 1X2 book."""
    stacked = np.stack([np.asarray(o, dtype=float) for o in decimal_odds])
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.nansum(np.where(stacked > 0, 1.0 / stacked, np.nan), axis=0)


def devig_probs(*decimal_odds):
    """Normalised probabilities summing to 1. The market's opinion.

    Proportional (multiplicative) de-vigging: divide each raw implied
    probability by the overround. This is the standard baseline and it is
    known to under-price favourites relative to Shin's method; that bias is
    tolerable for CLV, where both sides of the comparison use the same method.
    Do not reuse this as a break-even.

    Returns a tuple of arrays in the same order as the inputs.
    """
    raws = [breakeven_prob(o) for o in decimal_odds]
    total = np.nansum(np.stack([np.asarray(r, dtype=float) for r in raws]), axis=0)
    with np.errstate(divide="ignore", invalid="ignore"):
        return tuple(
            np.where(total > 0, np.asarray(r, dtype=float) / total, np.nan) for r in raws
        )
