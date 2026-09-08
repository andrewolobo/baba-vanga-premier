"""`GET /betpawa/links` and the pure host/URL module (docs/BETPAWA_PLAN.md, B26).

The endpoint is the gate: signed-in only, the country from the phone the
account captured, a host only where betPawa serves it. Tested against a real
clone with a planted tip and planted scrape rows, signing in through the same
stubbed Google flow `tests/test_auth.py` uses.
"""

from __future__ import annotations

import pytest

from api import betpawa
from engine import db
from tests.test_auth import GB_PHONE, KE_PHONE, auth_client, execute, sign_in  # noqa: F401

SOU_SWA = "37536526"
SWANSEA_PLUS_15 = "1539591711"


# --- the pure module ---------------------------------------------------------


def test_every_served_country_has_a_host_and_south_sudan_does_not():
    assert len(betpawa.HOSTS) == 17
    assert betpawa.host_for("KE") == "www.betpawa.co.ke"
    assert betpawa.host_for("UG") == "www.betpawa.ug"
    assert betpawa.host_for("CG") == "cg.betpawa.com"
    assert betpawa.host_for("SS") is None, "no host in betPawa's bundle; unverified"
    assert betpawa.host_for("GB") is None
    assert betpawa.host_for(None) is None


def test_the_prefill_link_is_the_verified_form():
    assert (betpawa.prefill_url("www.betpawa.ug", [SWANSEA_PLUS_15])
            == "https://www.betpawa.ug/external-prefill?selectionIds=1539591711")
    assert (betpawa.prefill_url("www.betpawa.co.ke", ["1", "2", "3"])
            == "https://www.betpawa.co.ke/external-prefill?selectionIds=1,2,3")
    with pytest.raises(ValueError):
        betpawa.prefill_url("www.betpawa.ug", [])


def test_the_event_link_opens_every_market():
    assert betpawa.event_url("www.betpawa.ug", SOU_SWA) == "https://www.betpawa.ug/event/37536526?filter=all"


# --- the endpoint ------------------------------------------------------------


def plant(url, *, today_offset=0, with_published_side=True):
    """One live tip -- Swansea +1.5, the owner-verified selection -- on a
    fixture the scrape matched, with the sides the book carried. Optionally
    the published side's line is missing: the one-sided ladder."""
    conn = db.connect(url)
    try:
        conn.execute("INSERT INTO teams (team_id, canonical_name) VALUES (1, 'Southampton'), (2, 'Swansea')")
        conn.execute(
            "INSERT INTO fixtures (fixture_id, division, match_date, kickoff_time,"
            " home_team_id, away_team_id, source_file)"
            " VALUES (1, 'E1', to_char(current_date + %s, 'YYYY-MM-DD'), '19:45', 1, 2, 't')",
            (today_offset,))
        conn.execute(
            "INSERT INTO predictions (prediction_id, fixture_id, model_version,"
            " information_set, served_at, lam_h, lam_a, p_home, p_draw, p_away,"
            " p_over25, p_under25) VALUES"
            " (1, 1, 'v', 'pre_close', '2026-09-08 06:00:00', 1.4, 1.1, 0.45, 0.27, 0.28, 0.5, 0.5)")
        conn.execute(
            "INSERT INTO tips (tip_id, prediction_id, fixture_id, side, model_prob, floor,"
            " ceiling, rule_version) VALUES (1, 1, 1, 'A+1.5', 0.81, 0.55, 0.85, 'confidence-v3')")
        conn.execute(
            "INSERT INTO betpawa_events (fixture_id, event_id, competition_id, start_time)"
            " VALUES (1, %s, '12101', '2026-09-08T18:45:00Z')", (SOU_SWA,))
        sides = [("H", "1537500854", 1.84), ("D", "1537500855", 3.81), ("A", "1537500856", 4.11),
                 ("1X", "1537500845", 1.25), ("X2", "1537500847", 1.91), ("12", "1537500846", 1.29)]
        if with_published_side:
            sides.append(("A+1.5", SWANSEA_PLUS_15, 1.32))
        conn.executemany(
            "INSERT INTO betpawa_selections (fixture_id, side, selection_id, odds)"
            " VALUES (1, %s, %s, %s)", sides)
        conn.commit()
    finally:
        conn.close()


def signed_in(client, phone, country):
    sign_in(client)
    response = client.post("/me/phone", json={"phone": phone, "country": country})
    assert response.status_code == 200, response.text
    return response.json()["user"]


def test_anonymous_is_401(auth_client):
    client, url = auth_client
    plant(url)
    assert client.get("/betpawa/links").status_code == 401


def test_a_served_country_gets_its_host_and_one_link_per_live_call(auth_client):
    client, url = auth_client
    plant(url)
    me = signed_in(client, KE_PHONE, "KE")
    assert me["phone_country"] == "KE"

    body = client.get("/betpawa/links").json()

    assert body["eligible"] is True
    assert body["country"] == "KE" and body["host"] == "www.betpawa.co.ke"
    assert len(body["links"]) == 1
    link = body["links"][0]
    assert link["fixture_id"] == 1 and link["event_id"] == SOU_SWA
    assert link["event_url"] == "https://www.betpawa.co.ke/event/37536526?filter=all"
    assert set(link["sides"]) == {"H", "D", "A", "1X", "X2", "12", "A+1.5"}
    assert link["sides"]["A+1.5"] == {
        "selection_id": SWANSEA_PLUS_15,
        "url": "https://www.betpawa.co.ke/external-prefill?selectionIds=1539591711",
    }
    assert "odds" not in link["sides"]["A+1.5"], "no price on the wire (D9)"


def test_an_unserved_country_is_not_eligible_and_gets_no_links(auth_client):
    client, url = auth_client
    plant(url)
    signed_in(client, GB_PHONE, "GB")

    body = client.get("/betpawa/links").json()

    assert body == {"eligible": False, "country": "GB", "host": None, "links": []}


def test_a_signed_in_account_without_a_phone_is_not_eligible_yet(auth_client):
    client, url = auth_client
    plant(url)
    sign_in(client)

    body = client.get("/betpawa/links").json()

    assert body["eligible"] is False and body["country"] is None and body["links"] == []


def test_a_missing_published_side_keeps_the_event_link(auth_client):
    """The one-sided ladder (plan 1.2, Wrexham v Burnley on the first live
    run): the fixture stays, with its event page and the sides it does have."""
    client, url = auth_client
    plant(url, with_published_side=False)
    signed_in(client, KE_PHONE, "KE")

    link = client.get("/betpawa/links").json()["links"][0]

    assert "A+1.5" not in link["sides"]
    assert "1X" in link["sides"]
    assert link["event_url"].endswith("/event/37536526?filter=all")


def test_a_settled_or_past_tip_has_no_link(auth_client):
    client, url = auth_client
    plant(url, today_offset=-1)
    signed_in(client, KE_PHONE, "KE")
    assert client.get("/betpawa/links").json()["links"] == []

    execute(url, "UPDATE fixtures SET match_date = to_char(current_date, 'YYYY-MM-DD')")
    assert len(client.get("/betpawa/links").json()["links"]) == 1
    execute(url, "UPDATE tips SET settled_at = '2026-09-08 22:00:00', outcome = 'win'")
    assert client.get("/betpawa/links").json()["links"] == []


def test_a_fixture_the_scrape_did_not_match_is_absent(auth_client):
    client, url = auth_client
    plant(url)
    execute(url, "DELETE FROM betpawa_events")
    signed_in(client, KE_PHONE, "KE")
    body = client.get("/betpawa/links").json()
    assert body["eligible"] is True and body["links"] == []


def test_the_route_is_a_read(auth_client):
    """The write-route pin in tests/test_api.py holds: this adds a GET only."""
    from api.main import app
    routes = {(r.path, m) for r in app.routes for m in getattr(r, "methods", ())}
    assert ("/betpawa/links", "GET") in routes
    assert ("/betpawa/links", "POST") not in routes
