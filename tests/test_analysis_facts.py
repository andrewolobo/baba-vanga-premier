"""The Fact Builder's arithmetic and rules, from values (no database).

`services/analysis/facts.py` turns a side's games into facts the LLM must
quote exactly, so every number is pinned here against a hand count. The
reads are covered against a real store in `test_analysis_pack.py`.
"""

from __future__ import annotations

import re

from services.analysis.facts import (
    Game, h2h_facts, league_facts, season_start, team_facts,
)


def game(day: int, at_home: bool, scored: int | None, conceded: int | None,
         price: float | None = None, opponent_price: float | None = None) -> Game:
    return Game(f"2026-09-{day:02d}", at_home, scored, conceded, price, opponent_price)


#: Five games, oldest first: W 2-0 (h), D 1-1 (a), L 0-3 (h), W 3-2 (a), W 1-0 (h).
FIVE = [game(1, True, 2, 0), game(5, False, 1, 1), game(9, True, 0, 3),
        game(13, False, 3, 2), game(17, True, 1, 0)]


def values(facts) -> dict:
    return {f.id: f.value for f in facts}


def build(games, side="home", division="E1", last_division="E1", uncalled=0):
    return team_facts(side, "Leeds", games, division=division,
                      last_division=last_division, uncalled=uncalled)


def test_a_window_is_counted_by_hand():
    facts, _, _ = build(FIVE)
    v = values(facts)
    assert v["HOME_GAMES_SEASON"] == 5
    assert v["HOME_FORM_SEASON"] == "WDLWW"                 # oldest to latest
    assert (v["HOME_WON_SEASON"], v["HOME_DRAWN_SEASON"], v["HOME_LOST_SEASON"]) == (3, 1, 1)
    assert v["HOME_PPG_SEASON"] == 2.0                      # (3*3 + 1) / 5
    assert v["HOME_GF_PG_SEASON"] == 1.4                    # 7 / 5
    assert v["HOME_GA_PG_SEASON"] == 1.2                    # 6 / 5
    assert v["HOME_CS_PCT_SEASON"] == 40                    # 2-0, 1-0
    assert v["HOME_BTTS_PCT_SEASON"] == 40                  # 1-1, 3-2
    assert v["HOME_O25_PCT_SEASON"] == 40                   # 0-3, 3-2
    # L5 over exactly five games is the season.
    metrics = ("GAMES", "FORM", "WON", "DRAWN", "LOST", "PPG", "GF_PG", "GA_PG",
               "CS_PCT", "BTTS_PCT", "O25_PCT")
    assert [v[f"HOME_{m}_L5"] for m in metrics] == [v[f"HOME_{m}_SEASON"] for m in metrics]


def test_short_windows_wait_for_enough_games():
    facts, flags, omitted = build(FIVE[:4])
    v = values(facts)
    assert "HOME_GAMES_L5" not in v and "HOME_GAMES_L10" not in v
    assert v["HOME_GAMES_SEASON"] == 4
    assert any(o.startswith("HOME L5") for o in omitted)
    assert any(o.startswith("HOME L10") for o in omitted)
    assert ("small_sample", "home") in {(f.code, f.side) for f in flags}

    facts, flags, _ = build(FIVE)
    assert "HOME_GAMES_L5" in values(facts)
    assert "small_sample" not in {f.code for f in flags}


def test_an_unscored_game_drops_only_the_windows_that_span_it():
    twelve = [game(1, True, None, None)] + [
        game(2 + i, i % 2 == 0, 1, 0) for i in range(11)]
    facts, flags, omitted = build(twelve)
    v = values(facts)
    assert v["HOME_GAMES_L5"] == 5 and v["HOME_GAMES_L10"] == 10
    assert "HOME_GAMES_SEASON" not in v
    assert "HOME_GAMES_VENUE" not in v                      # the gap was at home
    assert not any("_FAV_" in k or "_DOG_" in k for k in v)
    assert {f.code for f in flags} == {"results_gap"}
    assert any("HOME SEASON: spans" in o for o in omitted)


def test_venue_is_this_fixtures_venue():
    home, _, _ = build(FIVE, side="home")
    away, _, _ = build(FIVE, side="away")
    assert values(home)["HOME_GAMES_VENUE"] == 3            # games 1, 3, 5
    assert values(home)["HOME_FORM_VENUE"] == "WLW"
    assert values(away)["AWAY_GAMES_VENUE"] == 2            # games 2, 4
    assert values(away)["AWAY_FORM_VENUE"] == "DW"


def test_market_record_counts_priced_games_only():
    games = [game(1, True, 2, 0, 1.5, 6.0),     # favourite, won
             game(2, False, 1, 1, 2.2, 3.1),    # favourite, drew
             game(3, True, 0, 1, 4.0, 1.8),     # underdog, lost
             game(4, False, 1, 0, 2.5, 2.5),    # level: neither
             game(5, True, 3, 0)]               # unpriced: neither
    v = values(build(games)[0])
    assert (v["HOME_FAV_GAMES_SEASON"], v["HOME_FAV_WON_SEASON"],
            v["HOME_FAV_DRAWN_SEASON"], v["HOME_FAV_LOST_SEASON"]) == (2, 1, 1, 0)
    assert (v["HOME_DOG_GAMES_SEASON"], v["HOME_DOG_WON_SEASON"],
            v["HOME_DOG_DRAWN_SEASON"], v["HOME_DOG_LOST_SEASON"]) == (1, 0, 0, 1)


def test_new_to_division():
    facts, flags, _ = build(FIVE, division="E3", last_division="EC")
    assert values(facts)["HOME_DIVISION_LAST_SEASON"] == "National League"
    assert "new_to_division" in {f.code for f in flags}

    _, flags, _ = build(FIVE, division="E3", last_division="E3")
    assert "new_to_division" not in {f.code for f in flags}

    facts, flags, omitted = build(FIVE, division="E3", last_division=None)
    assert "HOME_DIVISION_LAST_SEASON" not in values(facts)
    assert "new_to_division" in {f.code for f in flags}
    assert any("DIVISION_LAST_SEASON" in o for o in omitted)


def test_uncalled_fixtures_are_named_not_counted():
    facts, flags, omitted = build(FIVE, uncalled=1)
    assert values(facts)["HOME_GAMES_SEASON"] == 5
    assert "results_gap" not in {f.code for f in flags}
    assert any("1 earlier fixture(s) this season have no call" in o for o in omitted)


def test_ids_are_deterministic_unique_and_well_formed():
    first = build(FIVE)[0] + build(FIVE, side="away")[0]
    again = build(FIVE)[0] + build(FIVE, side="away")[0]
    assert first == again
    ids = [f.id for f in first]
    assert len(ids) == len(set(ids))
    assert all(re.fullmatch(r"(HOME|AWAY)_[A-Z0-9_]+", i) for i in ids)


MEETINGS = [  # newest first, as `facts.meetings` returns them
    {"match_date": "2026-02-01", "division": "E1", "home_team_id": 2, "fthg": 0, "ftag": 2},
    {"match_date": "2025-09-01", "division": "E1", "home_team_id": 1, "fthg": 1, "ftag": 1},
    {"match_date": "2024-03-01", "division": "E2", "home_team_id": 2, "fthg": 3, "ftag": 1},
]


def test_h2h_is_tallied_from_the_fixture_home_side():
    v = values(h2h_facts(MEETINGS, home_id=1, names={1: "Leeds", 2: "Hull"}))
    assert v["H2H_MATCH_1"] == "2026-02-01, Hull 0-2 Leeds, Championship"
    assert v["H2H_MATCH_3"] == "2024-03-01, Hull 3-1 Leeds, League One"
    assert (v["H2H_GAMES_L5"], v["H2H_HOME_WINS_L5"], v["H2H_DRAWS_L5"],
            v["H2H_AWAY_WINS_L5"]) == (3, 1, 1, 1)
    assert v["H2H_GOALS_PG_L5"] == 2.67                     # 8 / 3
    assert h2h_facts([], home_id=1, names={1: "Leeds", 2: "Hull"}) == []


def test_league_context():
    v = values(league_facts([(2, 0), (1, 1), (0, 3), (2, 1)], "E2"))
    assert v == {"LEAGUE_GAMES_SEASON": 4, "LEAGUE_GOALS_PG_SEASON": 2.5,
                 "LEAGUE_HOME_WIN_PCT_SEASON": 50}
    assert league_facts([], "E2") == []


def test_season_start_is_the_match_pages_rule():
    from api.main import _season_start
    for day in ("2026-07-01", "2026-06-30", "2026-12-31", "2027-01-01", "2026-08-14"):
        assert season_start(day) == _season_start(day)
