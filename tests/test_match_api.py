"""The match-page API (docs/SEO_PLAN.md 2.2): `/fixture/{id}`,
`/sitemap/entries` and the names, slugs and venues behind them (`api/teams.py`).

The page and the sitemap each decide which fixtures have a page (D8) -- one
in Python, one in SQL -- and a disagreement is silent: a sitemap URL that
404s, or a page no crawler is told about. So the two are compared over every
kind of fixture rather than trusted.

The form and meetings fixtures use fixed dates, because the season boundary
they test is a calendar fact; the upcoming, live and stale ones are dated
relative to today, because that split is what the rule keys on.
"""

from __future__ import annotations

import csv

import pytest
from fastapi.testclient import TestClient

from api import teams
from api.main import _season_start, app, get_conn
from engine import config, db
from tests.conftest import relative_date
from tests.test_api import _override

TEAMS = {1: "Man United", 2: "Nott'm Forest", 3: "Chelsea", 4: "Wigan",
         5: "Brighton", 6: "Sutton", 7: "Arsenal"}

# fixture_id: (division, date, home, away, first_seen_at)
FIXTURES = {
    # The settled page under test, and Manchester United's season before it.
    100: ("E0", "2026-09-12", 1, 2, "2026-09-09 06:00:00"),
    101: ("E0", "2026-08-16", 1, 3, "2026-08-14 06:00:00"),
    102: ("E0", "2026-08-23", 7, 1, "2026-08-20 06:00:00"),
    103: ("E0", "2026-08-30", 1, 5, "2026-08-27 06:00:00"),
    104: ("E0", "2026-09-02", 3, 1, "2026-08-30 06:00:00"),
    105: ("E0", "2026-09-06", 1, 7, "2026-09-03 06:00:00"),
    106: ("E0", "2026-09-09", 5, 1, "2026-09-06 06:00:00"),
    107: ("E0", "2026-09-15", 1, 4, "2026-09-12 06:00:00"),   # after 100: not its form
    90: ("E0", "2026-04-01", 2, 1, "2026-03-29 06:00:00"),    # last season
    # Relative to today: before the call, the call live, stale, not served.
    200: ("E0", relative_date(2), 1, 2, "2026-09-16 06:00:00"),
    201: ("E0", relative_date(0), 5, 3, "2026-09-16 06:00:00"),
    202: ("E1", relative_date(-3), 4, 3, "2026-09-10 06:00:00"),
    203: ("EC", relative_date(1), 6, 4, "2026-09-16 06:00:00"),
}

# tip_id, fixture_id, side, outcome, fthg, ftag, rule, published_at, settled_at
TIPS = [
    (1, 100, "A+1.5", "win", 2, 1, "confidence-v3", "2026-09-12 06:05:00", "2026-09-12 19:00:00"),
    (2, 101, "H", "win", 2, 0, "confidence-v3", "2026-08-16 06:05:00", "2026-08-16 19:00:00"),
    (3, 102, "12", "lose", 1, 1, "confidence-v3", "2026-08-23 06:05:00", "2026-08-23 19:00:00"),
    # Fixture 103 was called under two rule versions; the later call is the one shown.
    (4, 103, "1X", "lose", 0, 1, "confidence-v2", "2026-08-30 06:05:00", "2026-08-30 19:00:00"),
    (5, 103, "H+1.5", "win", 0, 1, "confidence-v3", "2026-08-30 06:06:00", "2026-08-30 19:00:00"),
    (6, 104, "X2", "win", 0, 3, "confidence-v3", "2026-09-02 06:05:00", "2026-09-02 19:00:00"),
    (7, 105, "1X", "win", 1, 1, "confidence-v3", "2026-09-06 06:05:00", "2026-09-06 19:00:00"),
    (8, 106, "12", "lose", 2, 2, "confidence-v3", "2026-09-09 06:05:00", "2026-09-09 19:00:00"),
    (9, 107, "H", "win", 3, 0, "confidence-v3", "2026-09-15 06:05:00", "2026-09-15 19:00:00"),
    (10, 90, "A", "lose", 1, 0, "confidence-v2", "2026-04-01 06:05:00", "2026-04-01 19:00:00"),
    (11, 201, "1X", None, None, None, "confidence-v3", "2026-09-18 06:05:00", None),
]

# Historical meetings (backtest inputs, never calls). The first repeats
# fixture 90, and one has no score.
MATCHES = [
    ("m1", "202526", "2026-04-01", 2, 1, 1, 0),
    ("m2", "202526", "2025-11-01", 1, 2, 2, 2),
    ("m3", "202324", "2024-02-03", 2, 1, 0, 2),
    ("m4", "202324", "2023-09-01", 1, 2, 3, 0),
    ("m5", "201819", "2019-01-01", 1, 2, None, None),
    ("m6", "201718", "2018-05-05", 2, 1, 1, 1),
    ("m7", "201112", "2012-01-01", 1, 2, 1, 0),
]


@pytest.fixture
def match_client(make_database):
    url = make_database()
    conn = db.connect(url)
    db.migrate(conn)
    for team_id, name in TEAMS.items():
        conn.execute("INSERT INTO teams (team_id, canonical_name) VALUES (%s, %s)", (team_id, name))
    for fid, (division, date, home, away, seen) in FIXTURES.items():
        conn.execute(
            "INSERT INTO fixtures (fixture_id, division, match_date, kickoff_time,"
            " home_team_id, away_team_id, avg_h, avg_d, avg_a, first_seen_at, source_file)"
            " VALUES (%s, %s, %s, '15:00', %s, %s, 1.9, 3.6, 4.0, %s, 't')",
            (fid, division, date, home, away, seen))
    for tip_id, fid, side, outcome, fthg, ftag, rule, published, settled in TIPS:
        conn.execute(
            "INSERT INTO predictions (prediction_id, fixture_id, model_version,"
            " information_set, lam_h, lam_a, p_home, p_draw, p_away, p_over25,"
            " p_under25) VALUES (%s, %s, %s, 'pre_close', 1.6, 1.1, 0.48, 0.26, 0.26,"
            " 0.52, 0.48)", (tip_id, fid, f"v{tip_id}"))
        conn.execute(
            "INSERT INTO tips (tip_id, prediction_id, fixture_id, side, model_prob,"
            " floor, ceiling, rule_version, published_at, settled_at, outcome, fthg, ftag)"
            " VALUES (%s, %s, %s, %s, 0.8, 0.55, 0.85, %s, %s, %s, %s, %s, %s)",
            (tip_id, tip_id, fid, side, rule, published, settled, outcome, fthg, ftag))
    for match_id, season, date, home, away, fthg, ftag in MATCHES:
        conn.execute(
            "INSERT INTO matches (match_id, season, division, match_date,"
            " home_team_id, away_team_id, fthg, ftag, odds_era, source_file)"
            " VALUES (%s, %s, 'E0', %s, %s, %s, %s, %s, 'market', 't')",
            (match_id, season, date, home, away, fthg, ftag))
    conn.commit()
    conn.close()

    app.dependency_overrides[get_conn] = _override(url)
    yield TestClient(app)
    app.dependency_overrides.clear()


# --- /fixture ------------------------------------------------------------- #


def test_a_settled_page_carries_its_call_score_and_display_names(match_client):
    body = match_client.get("/fixture/100").json()
    assert (body["home_name"], body["away_name"]) == ("Manchester United", "Nottingham Forest")
    assert (body["home_team"], body["away_team"]) == ("Man United", "Nott'm Forest")
    assert body["slug"] == "manchester-united-vs-nottingham-forest"
    assert body["venue"] == teams.venue("Man United") and body["venue"]
    tip = body["tip"]
    assert (tip["side"], tip["outcome"], tip["fthg"], tip["ftag"]) == ("A+1.5", "win", 2, 1)
    assert "p_a15" in tip                        # the /tips shape, handicap marginals included


def test_a_page_carries_no_fixture_prices(match_client):
    body = match_client.get("/fixture/100").json()
    assert not [k for k in body if k.startswith(("avg_", "max_", "ah_"))]


def test_form_is_this_seasons_last_five_before_the_match_with_the_latest_call(match_client):
    form = match_client.get("/fixture/100").json()["form"]
    home = form["home"]
    # Six earlier games this season; the newest five, newest first. Not 107,
    # which came after, and not 90, which was last season.
    assert [g["fixture_id"] for g in home] == [106, 105, 104, 103, 102]
    # W/D/L from Manchester United's side, home or away.
    assert [g["result"] for g in home] == ["D", "D", "W", "L", "D"]
    assert [g["at_home"] for g in home] == [False, True, False, True, False]
    # 103 was called twice; the later call is the one listed.
    g103 = home[3]
    assert (g103["side"], g103["outcome"]) == ("H+1.5", "win")
    assert (g103["home_name"], g103["away_name"]) == ("Manchester United", "Brighton & Hove Albion")
    # Forest's only game in the table is last season's.
    assert form["away"] == []


def test_meetings_are_scores_only_newest_first_and_listed_once(match_client):
    meetings = match_client.get("/fixture/100").json()["meetings"]
    assert [m["match_date"] for m in meetings] == [
        "2026-04-01", "2025-11-01", "2024-02-03", "2023-09-01", "2018-05-05"]
    first = meetings[0]
    assert (first["home_name"], first["fthg"], first["ftag"]) == ("Nottingham Forest", 1, 0)
    # Backtest rows were never calls, so no meeting carries one.
    assert not any({"side", "outcome"} & set(m) for m in meetings)


def test_an_upcoming_fixture_has_a_page_before_its_call(match_client):
    response = match_client.get("/fixture/200")
    assert response.status_code == 200
    assert response.json()["tip"] is None


def test_a_live_call_is_on_its_page(match_client):
    tip = match_client.get("/fixture/201").json()["tip"]
    assert (tip["side"], tip["settled_at"]) == ("1X", None)


@pytest.mark.parametrize("fixture_id, why", [
    (202, "date passed with no call"),
    (203, "National League, not served"),
    (99999, "no such fixture"),
])
def test_no_page(match_client, fixture_id, why):
    assert match_client.get(f"/fixture/{fixture_id}").status_code == 404, why


# --- /sitemap/entries ------------------------------------------------------ #


def test_the_sitemap_lists_exactly_the_fixtures_that_have_a_page(match_client):
    listed = {e["fixture_id"] for e in match_client.get("/sitemap/entries").json()}
    have_a_page = {fid for fid in FIXTURES
                   if match_client.get(f"/fixture/{fid}").status_code == 200}
    assert listed == have_a_page
    assert {202, 203}.isdisjoint(listed)


def test_sitemap_lastmod_is_the_last_visible_change(match_client):
    entries = {e["fixture_id"]: e for e in match_client.get("/sitemap/entries").json()}
    assert entries[100]["lastmod"] == "2026-09-12T19:00:00Z"      # settled after publishing
    assert entries[201]["lastmod"] == "2026-09-18T06:05:00Z"      # published, not settled
    assert entries[200]["lastmod"] == "2026-09-16T06:00:00Z"      # no call yet: first seen
    assert entries[100]["slug"] == "manchester-united-vs-nottingham-forest"


def test_sitemap_is_newest_first(match_client):
    ids = [e["fixture_id"] for e in match_client.get("/sitemap/entries").json()]
    dates = [FIXTURES[i][1] for i in ids]
    assert dates == sorted(dates, reverse=True)


# --- names, slugs, venues --------------------------------------------------- #


def _served_clubs() -> set[str]:
    """The 92 E0-E3 clubs, from the betPawa capture that bridged all of them."""
    with open(config.BETPAWA_TEAMS_CSV, encoding="utf-8", newline="") as f:
        return {r["canonical_name"] for r in csv.DictReader(f)}


def test_every_served_club_has_a_display_name():
    names = teams._names()
    assert len(_served_clubs()) == 92
    assert sorted(_served_clubs() - set(names)) == []


def test_display_name_slugs_are_unique():
    """Two clubs on one slug would give two fixtures the same words; the id
    keeps the URLs apart, but the titles would read as the same match."""
    slugs = [teams.slug(name) for name in teams._names().values()]
    assert len(slugs) == len(set(slugs))


def _venue_rows() -> list[dict]:
    with open(teams.VENUES_CSV, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def test_every_served_club_has_one_row_in_the_venue_list():
    """A club missing from the list prints no venue with no error anywhere."""
    clubs = [r["canonical_name"] for r in _venue_rows()]
    assert len(clubs) == len(set(clubs))
    assert sorted(_served_clubs() - set(clubs)) == []
    assert {r["status"] for r in _venue_rows()} <= {"ok", "check"}


def test_only_confirmed_venues_are_shown():
    for row in _venue_rows():
        shown = teams.venue(row["canonical_name"])
        assert shown == (row["venue"] if row["status"] == "ok" else None), row


@pytest.mark.parametrize("text, expected", [
    ("Brighton & Hove Albion", "brighton-hove-albion"),
    ("Nottingham Forest", "nottingham-forest"),
    ("Ümraniyespor Kulübü", "umraniyespor-kulubu"),
    ("  MK  Dons--", "mk-dons"),
])
def test_slug(text, expected):
    assert teams.slug(text) == expected


@pytest.mark.parametrize("date, start", [
    ("2026-09-12", "2026-07-01"),
    ("2027-05-20", "2026-07-01"),
    ("2027-07-01", "2027-07-01"),
    ("2026-06-30", "2025-07-01"),
])
def test_season_start(date, start):
    assert _season_start(date) == start
