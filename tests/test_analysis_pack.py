"""The evidence pack against a real store (`services/analysis/pack.py`).

The calls here are made by the shipped rule itself (`engine.serve.tips.select`
on served-shape predictions), so "the pack's menu reproduces the published
call" is tested against the code that publishes, not against a restatement
of it. The season's games, last season's division, the meetings and the
league come from seeded rows, with the traps the reads claim to handle: a
void call, a call settled without a score, a fixture with no call, last
season's games, and a meeting stored in both `matches` and `tips`.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from api import teams
from engine import db
from engine.eval import metrics
from engine.serve import tips
from services.analysis.pack import build_pack

TEAMS = {1: "Leeds", 2: "Hull", 3: "Stoke", 4: "Wrexham", 5: "Luton", 6: "Derby"}

#: fixture_id: (date, home, away, lam_h, lam_a). 10-12 are the fixtures
#: under test; their lambdas give one call each of H, an underdog +1.5 and
#: `12` under the shipped rule (asserted below, not assumed).
FIXTURES = {
    10: ("2026-10-03", 1, 2, 2.8, 0.6),
    11: ("2026-10-03", 3, 4, 1.4, 1.2),
    12: ("2026-10-03", 5, 6, 1.0, 1.0),
    # Leeds's season before fixture 10, oldest first.
    20: ("2026-08-09", 1, 3, 1.5, 1.0),     # W 2-0
    21: ("2026-08-16", 4, 1, 1.2, 1.3),     # D 1-1, Leeds away
    22: ("2026-08-23", 1, 5, 1.6, 1.0),     # void: postponed, no score
    23: ("2026-08-30", 6, 1, 1.1, 1.4),     # L 2-0, Leeds away
    24: ("2026-09-06", 1, 4, 1.7, 0.9),     # no call at all
    # Hull's season: one game settled without a score.
    30: ("2026-08-09", 2, 5, 1.3, 1.1),     # settled, score missing
    31: ("2026-08-16", 6, 2, 1.2, 1.2),     # D 0-0, Hull away
    # Last season (before 1 July): never in this season's windows.
    40: ("2026-04-18", 1, 2, 1.5, 1.1),     # Leeds 3-1 Hull, called and scored
}

#: fixture_id: (outcome, fthg, ftag) for the season's settled calls.
SETTLED = {20: ("win", 2, 0), 21: ("win", 1, 1), 22: ("void", None, None),
           23: ("lose", 2, 0), 30: ("win", None, None), 31: ("win", 0, 0),
           40: ("win", 3, 1)}

#: Corpus rows: last season's division for each club, and two old meetings
#: of Leeds and Hull -- one of which repeats fixture 40.
MATCHES = [
    ("m1", "202526", "E1", "2026-04-18", 1, 2, 3, 1),
    ("m2", "202425", "E1", "2025-01-11", 2, 1, 2, 2),
    ("m3", "202526", "E1", "2025-10-01", 3, 5, 1, 0),
    ("m4", "202526", "E2", "2025-10-01", 4, 6, 0, 0),
]


@pytest.fixture
def store(database_url):
    conn = db.connect(database_url)
    for team_id, name in TEAMS.items():
        conn.execute("INSERT INTO teams (team_id, canonical_name) VALUES (%s, %s)",
                     (team_id, name))
    for fid, (date, home, away, _, _) in FIXTURES.items():
        conn.execute(
            "INSERT INTO fixtures (fixture_id, division, match_date, kickoff_time,"
            " home_team_id, away_team_id, avg_h, avg_d, avg_a, source_file)"
            " VALUES (%s, 'E1', %s, '15:00', %s, %s, 1.9, 3.5, 4.2, 't')",
            (fid, date, home, away))
    for match_id, season, division, date, home, away, fthg, ftag in MATCHES:
        conn.execute(
            "INSERT INTO matches (match_id, season, division, match_date, home_team_id,"
            " away_team_id, fthg, ftag, odds_era, source_file)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'market', 't')",
            (match_id, season, division, date, home, away, fthg, ftag))

    called = [fid for fid in FIXTURES if fid != 24]
    lam_h = np.array([FIXTURES[f][3] for f in called])
    lam_a = np.array([FIXTURES[f][4] for f in called])
    probs = metrics.model_probs(lam_h, lam_a)
    served = pd.DataFrame({
        "fixture_id": called, "prediction_id": called, "lam_h": lam_h, "lam_a": lam_a,
        "p_home": probs.p_h, "p_draw": probs.p_d, "p_away": probs.p_a,
        **{c: np.nan for c in ("max_h", "max_d", "max_a", "avg_h", "avg_d", "avg_a")}})
    for r in served.itertuples():
        conn.execute(
            "INSERT INTO predictions (prediction_id, fixture_id, model_version, information_set,"
            " lam_h, lam_a, p_home, p_draw, p_away, p_over25, p_under25)"
            " VALUES (%s, %s, 'test-model', 'pre_close', %s, %s, %s, %s, %s, 0.5, 0.5)",
            (r.prediction_id, r.fixture_id, r.lam_h, r.lam_a, r.p_home, r.p_draw, r.p_away))
    tips.publish(conn, tips.select(served))
    for fid, (outcome, fthg, ftag) in SETTLED.items():
        conn.execute(
            f"UPDATE tips SET settled_at = {db.NOW_TEXT}, outcome = %s, fthg = %s, ftag = %s"
            " WHERE fixture_id = %s", (outcome, fthg, ftag, fid))
    conn.commit()
    yield conn
    conn.close()


def name(team_id: int) -> str:
    """The display name the pack prints (`api/teams.py`, D12)."""
    return teams.display_name(TEAMS[team_id])


def facts_of(pack) -> dict:
    return {f.id: f.value for f in pack.facts}


def test_the_menu_reproduces_each_published_call(store):
    published = {r["fixture_id"]: r for r in store.execute(
        "SELECT fixture_id, side, model_prob FROM tips WHERE fixture_id IN (10, 11, 12)")}
    assert {fid: r["side"] for fid, r in published.items()} == {10: "H", 11: "A+1.5", 12: "12"}
    for fid, tip in published.items():
        pack = build_pack(store, fid, data_as_of="2026-10-03 06:00:00")
        (line,) = [m for m in pack.menu if m.is_call]
        assert pack.call.side == line.side == tip["side"]
        assert pack.call.model_prob == line.p_model == round(100 * tip["model_prob"], 1)
        assert line.eligible
        # The home side is favoured in all three, so the underdog is away.
        assert {m.side for m in pack.menu} == {"H", "D", "A", "1X", "X2", "12", "A+1.5"}


def test_menu_roles_follow_the_rule(store):
    pack = build_pack(store, 11, data_as_of="x")       # Stoke favoured: Wrexham +1.5
    roles = {m.side: (m.role, m.eligible) for m in pack.menu}
    assert roles["H"][0] == "outright" and not roles["H"][1]   # below the 55% floor
    assert roles["D"] == ("off_menu", False) and roles["A"] == ("off_menu", False)
    assert "H+1.5" not in roles                                # the favourite's is on no menu
    assert pack.call.means == f"{name(4)} must not lose by 2 or more goals"


def test_no_call_and_an_older_rule_are_refused(store):
    with pytest.raises(LookupError):
        build_pack(store, 24)
    store.execute("UPDATE tips SET rule_version = 'confidence-v2' WHERE fixture_id = 12")
    with pytest.raises(ValueError, match="confidence-v2"):
        build_pack(store, 12)


def test_a_tampered_call_is_refused(store):
    store.execute("UPDATE tips SET side = 'X2' WHERE fixture_id = 12")
    with pytest.raises(ValueError, match="was published"):
        build_pack(store, 12)


def test_season_games_skip_voids_uncalled_and_last_season(store):
    pack = build_pack(store, 10, data_as_of="x")
    v = facts_of(pack)
    # 20 W 2-0, 21 D 1-1, 23 L 0-2: the void (22), the uncalled (24) and
    # last season's 40 are not games.
    assert v["HOME_FORM_SEASON"] == "WDL"
    assert v["HOME_GAMES_VENUE"] == 1 and v["HOME_FORM_VENUE"] == "W"
    assert v["HOME_DIVISION_LAST_SEASON"] == "Championship"
    assert any("1 earlier fixture(s) this season have no call" in o for o in pack.omitted)
    assert ("small_sample", "home") in {(f.code, f.side) for f in pack.flags}
    assert ("new_to_division", "home") not in {(f.code, f.side) for f in pack.flags}


def test_a_call_settled_without_a_score_is_a_gap(store):
    pack = build_pack(store, 10, data_as_of="x")
    v = facts_of(pack)
    assert "AWAY_GAMES_SEASON" not in v                    # Hull's first game has no score
    assert ("results_gap", "away") in {(f.code, f.side) for f in pack.flags}


def test_meetings_merge_the_corpus_and_the_calls(store):
    v = facts_of(build_pack(store, 10, data_as_of="x"))
    assert v["H2H_GAMES_L5"] == 2                          # fixture 40 and m1 are one game
    assert v["H2H_MATCH_1"] == f"2026-04-18, {name(1)} 3-1 {name(2)}, Championship"
    assert v["H2H_MATCH_2"] == f"2025-01-11, {name(2)} 2-2 {name(1)}, Championship"
    assert (v["H2H_HOME_WINS_L5"], v["H2H_DRAWS_L5"], v["H2H_AWAY_WINS_L5"]) == (1, 1, 0)


def test_new_to_division_reads_last_seasons_corpus(store):
    flags = {(f.code, f.side) for f in build_pack(store, 11, data_as_of="x").flags}
    assert ("new_to_division", "away") in flags            # Wrexham were in E2
    assert ("new_to_division", "home") not in flags        # Stoke were in E1


def test_league_context_counts_scored_games_this_season(store):
    v = facts_of(build_pack(store, 10, data_as_of="x"))
    # 20, 21, 23, 31: scored, this season, before 3 October.
    assert v["LEAGUE_GAMES_SEASON"] == 4
    assert v["LEAGUE_GOALS_PG_SEASON"] == 1.5              # (2 + 2 + 2 + 0) / 4


def test_the_pack_is_deterministic(store):
    first = build_pack(store, 11, data_as_of="2026-10-03 06:00:00").model_dump_json()
    assert build_pack(store, 11, data_as_of="2026-10-03 06:00:00").model_dump_json() == first
