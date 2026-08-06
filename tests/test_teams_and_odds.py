"""The team bridge and the two odds conversions.

Both encode a specific way the project has been told it can go wrong: silent
sample loss through unbridged names (SPEC §0.2), and an EV read flattered by
confusing a break-even with a de-vigged probability (SPEC §3.8).
"""

from __future__ import annotations

import numpy as np
import pytest

from engine import odds
from engine.ingest.teams import FBREF, FOOTBALL_DATA, BridgeReport, TeamBridge, UnbridgedTeam


# --- bridge ---------------------------------------------------------------


def test_two_aliases_resolve_to_one_club(bridge):
    """fbref renamed Torquay United to Torquay in 2019-20; both are one club."""
    assert bridge.resolve(FBREF, "Torquay United") == bridge.resolve(FBREF, "Torquay")


def test_football_data_self_alias_resolves(bridge):
    """football-data itself writes AFC Telford United in 2011-12 and Telford
    United afterwards."""
    assert bridge.resolve(FOOTBALL_DATA, "AFC Telford United") == "Telford United"


def test_near_identical_clubs_stay_separate(bridge):
    """Oxford City is not Oxford United. A fuzzy matcher would merge them, which
    is why the runtime does pure lookup and never normalises."""
    assert bridge.resolve(FBREF, "Oxford United") != bridge.resolve(FBREF, "Oxford City FC")


def test_unbridged_name_raises_carrying_the_name(bridge):
    with pytest.raises(UnbridgedTeam, match="Sheffield Weds"):
        bridge.resolve(FOOTBALL_DATA, "Sheffield Weds")
    assert bridge.try_resolve(FOOTBALL_DATA, "Sheffield Weds") is None


def test_cp1252_apostrophe_survives(bridge):
    """King's Lynn carries a 0x92 curly apostrophe that raises under UTF-8."""
    assert bridge.resolve(FOOTBALL_DATA, "King’s Lynn") == "King's Lynn"


def test_report_counts_misses_by_name():
    report = BridgeReport()
    report.record(FOOTBALL_DATA, "Nowhere FC")
    report.record(FOOTBALL_DATA, "Nowhere FC")
    assert not report.clean
    assert "Nowhere FC" in report.describe()
    assert "2 rows excluded" in report.describe()


def test_team_ids_are_stable_and_one_based(bridge):
    """Ids come from the alphabetical canonical list, so they are reproducible
    across rebuilds rather than depending on insertion order."""
    ids = bridge.team_ids()
    assert min(ids.values()) == 1
    assert sorted(ids) == list(bridge.canonical_names)
    assert ids == bridge.team_ids()


# --- odds era mapping -----------------------------------------------------


def test_era_detection(bridge):
    assert odds.detect_era(["Div", "BbAvH", "BbMxH"]) == odds.BETBRAIN_ERA
    assert odds.detect_era(["Div", "AvgH", "MaxH"]) == odds.MARKET_ERA


def test_era_detection_refuses_the_impossible():
    with pytest.raises(ValueError, match="both"):
        odds.detect_era(["BbAvH", "AvgH"])
    with pytest.raises(ValueError, match="neither"):
        odds.detect_era(["Div", "Date"])


def test_both_eras_map_onto_the_same_field_names():
    """Betbrain aggregates and market Avg/Max are the same quantity under two
    names; downstream code must not have to know which era a row came from."""
    old = odds.column_map(odds.BETBRAIN_ERA)
    new = odds.column_map(odds.MARKET_ERA)
    assert set(old) == set(new)
    assert old["avg_h"] == "BbAvH" and new["avg_h"] == "AvgH"
    assert old["avg_over25"] == "BbAv>2.5" and new["avg_over25"] == "Avg>2.5"


# --- the vig trap ---------------------------------------------------------


def test_breakeven_is_raw_and_overround_exceeds_one():
    """1/odds is what a bet must beat. Across a book these sum above 1, and that
    excess is the vig -- it is not an error to be normalised away here."""
    assert odds.breakeven_prob(2.0) == pytest.approx(0.5)
    total = odds.overround(2.0, 3.5, 4.0)
    assert total > 1.0


def test_vig_per_leg_is_the_overround_split_across_legs():
    """A 6% three-way book costs 2% per leg -- the bar CLV has to clear."""
    assert odds.vig_per_leg(2.0, 3.5, 4.0) == pytest.approx(
        (odds.overround(2.0, 3.5, 4.0) - 1.0) / 3.0)


def test_vig_per_leg_is_zero_on_a_fair_book():
    """Two legs at evens carry no margin, so there is nothing to beat."""
    assert odds.vig_per_leg(2.0, 2.0) == pytest.approx(0.0)


def test_vig_per_leg_drops_incomplete_markets_rather_than_undercounting():
    """A market missing one price would otherwise read as a *negative* vig.

    Summing 1/odds over the two legs that are present gives a total below 1,
    which is the shape of a free bet. Dropping the row is the only safe
    treatment, and it is why this is not a one-line expression at the call site.
    """
    home = np.array([2.0, 2.0])
    draw = np.array([3.5, np.nan])
    away = np.array([4.0, 4.0])
    both = odds.vig_per_leg(home, draw, away)
    only_complete = odds.vig_per_leg(home[:1], draw[:1], away[:1])
    assert both == pytest.approx(only_complete)
    assert both > 0.0


def test_devig_sums_to_one_and_differs_from_breakeven():
    home, draw, away = odds.devig_probs(2.0, 3.5, 4.0)
    assert float(home + draw + away) == pytest.approx(1.0)
    # The two conversions must not be interchangeable; conflating them flattered
    # every EV read in gtleague by roughly five points per side.
    assert float(home) < float(odds.breakeven_prob(2.0))


def test_conversions_handle_missing_prices():
    assert np.isnan(odds.breakeven_prob(np.nan))
    assert np.isnan(odds.breakeven_prob(0.0))


def test_closing_preference_falls_back_from_pinnacle():
    """Pinnacle closing collapses mid-2025-26, so the CLV anchor needs a chain
    rather than a single column."""
    first, second, _ = odds.CLOSING_1X2_PREFERENCE
    assert first == ("close_ps_h", "close_ps_d", "close_ps_a")
    assert second == ("close_avg_h", "close_avg_d", "close_avg_a")
