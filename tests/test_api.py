"""The serving API.

Read-only by contract: a request must never change what was served. If an
endpoint could fit, price or bet, then "what did we predict and when" would
have a different answer every time it was asked, and the stored record would
stop being evidence.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.main import app, get_conn
from engine import db


def _override(path):
    """A fresh connection per request, which is what production does.

    Reusing one connection across requests fails under TestClient because
    sqlite3 objects are bound to the thread that created them -- and it would
    be wrong in production too, where uvicorn serves from a thread pool.
    """
    def dependency():
        conn = db.connect(path)
        try:
            yield conn
        finally:
            conn.close()
    return dependency


@pytest.fixture
def client(tmp_path):
    path = tmp_path / "api.db"
    conn = db.connect(path)
    db.migrate(conn)
    for i, name in enumerate(["Arsenal", "Chelsea", "Luton", "Barnsley"], start=1):
        conn.execute("INSERT INTO teams (team_id, canonical_name) VALUES (?, ?)", (i, name))
    conn.execute(
        "INSERT INTO fixtures (fixture_id, division, match_date, kickoff_time,"
        " home_team_id, away_team_id, avg_h, avg_d, avg_a, avg_over25, avg_under25,"
        " source_file) VALUES (1,'E0','2026-08-15','15:00',1,2,1.90,3.80,4.20,1.95,1.90,'t')")
    conn.execute(
        "INSERT INTO fixtures (fixture_id, division, match_date, kickoff_time,"
        " home_team_id, away_team_id, avg_h, avg_d, avg_a, avg_over25, avg_under25,"
        " source_file) VALUES (2,'E2','2026-08-15','15:00',3,4,2.10,3.30,3.50,2.00,1.85,'t')")
    conn.execute(
        "INSERT INTO predictions (prediction_id, fixture_id, model_version,"
        " information_set, served_at, lam_h, lam_a, p_home, p_draw, p_away,"
        " p_over25, p_under25) VALUES"
        " (1,1,'v1','pre_close','2026-08-10 09:00:00',1.9,0.9,0.62,0.20,0.18,0.55,0.45)")
    conn.execute(
        "INSERT INTO predictions (prediction_id, fixture_id, model_version,"
        " information_set, served_at, lam_h, lam_a, p_home, p_draw, p_away,"
        " p_over25, p_under25) VALUES"
        " (2,1,'v2','pre_close','2026-08-12 09:00:00',2.0,0.8,0.66,0.19,0.15,0.57,0.43)")
    conn.execute(
        "INSERT INTO paper_bets (bet_id, prediction_id, fixture_id, market, side, price,"
        " price_source, model_prob, breakeven_prob, edge, expected_value, stake,"
        " rule_version, settled_at, outcome, pnl)"
        " VALUES (1,1,1,'1x2','H',1.90,'avg_h',0.62,0.5263,0.0937,0.178,1.0,'v1',"
        " '2026-08-15 18:00:00','win',0.90)")
    conn.execute(
        "INSERT INTO clv_grades (bet_id, bet_price, close_price, close_source,"
        " bet_prob, close_prob, clv, clv_pct)"
        " VALUES (1,1.90,1.75,'PSC',0.505,0.548,0.043,0.0857)")
    conn.execute(
        "INSERT INTO model_runs (model_version, fitted_at, config_label, n_train,"
        " n_teams, corpus_digest) VALUES ('v2','2026-08-10','H400/a0.1',13946,151,'abc')")
    conn.commit()
    conn.close()

    app.dependency_overrides[get_conn] = _override(path)
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_health_reports_state_not_just_liveness(client):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["counts"]["fixtures"] == 2
    assert body["counts"]["predictions"] == 2
    assert body["model"]["model_version"] == "v2"
    assert body["calibrated"] is False


def test_fixtures_lists_all_divisions_and_filters(client):
    assert len(client.get("/fixtures").json()) == 2
    only_e0 = client.get("/fixtures", params={"division": "E0"}).json()
    assert [f["division"] for f in only_e0] == ["E0"]
    assert only_e0[0]["home_team"] == "Arsenal"


def test_an_unknown_division_is_rejected_rather_than_returning_nothing(client):
    """Silently returning [] would read as 'no fixtures' rather than 'bad
    request', which is the kind of thing that hides a frontend typo for weeks."""
    assert client.get("/fixtures", params={"division": "E9"}).status_code == 400


def test_predictions_returns_only_the_latest_per_fixture(client):
    body = client.get("/predictions").json()
    assert len(body) == 1
    assert body[0]["model_version"] == "v2"
    assert body[0]["p_home"] == 0.66


def test_predictions_carry_their_provenance_and_calibration_flag(client):
    row = client.get("/predictions").json()[0]
    assert row["served_at"] == "2026-08-12 09:00:00"
    assert row["information_set"] == "pre_close"
    assert row["calibrated"] == 0
    # Raw lambdas travel too, so a client can re-derive any line it wants.
    assert row["lam_h"] == 2.0


def test_predictions_include_the_price_they_should_be_read_against(client):
    row = client.get("/predictions").json()[0]
    assert row["avg_h"] == 1.90
    assert row["p_home"] > 1 / row["avg_h"]      # the edge is visible client-side


def test_book_returns_bets_with_clv_attached(client):
    row = client.get("/book").json()[0]
    assert row["side"] == "H"
    assert row["outcome"] == "win"
    assert row["clv"] == pytest.approx(0.043)
    assert row["close_source"] == "PSC"


def test_book_filters_by_settlement(client):
    assert len(client.get("/book", params={"settled": True}).json()) == 1
    assert client.get("/book", params={"settled": False}).json() == []


def test_performance_leads_with_clv_not_roi(client):
    """CLV is the primary metric; ROI is confirmatory and hit rate diagnostic
    only (SPEC §5.1). All three are returned, in that order of prominence."""
    row = client.get("/performance").json()[0]
    assert row["mean_clv"] == pytest.approx(0.043)
    assert row["beat_close_rate"] == 1.0
    assert row["roi"] == pytest.approx(0.90)
    assert row["hit_rate"] == 1.0


def test_the_api_exposes_no_write_routes(client):
    """Read-only by contract, asserted against the route table rather than
    trusted -- a POST added later would otherwise pass unnoticed."""
    methods = {m for route in app.routes for m in getattr(route, "methods", set())}
    assert methods <= {"GET", "HEAD", "OPTIONS"}


def test_endpoints_survive_an_empty_database(tmp_path):
    """Opening day: the tables exist but nothing has run yet. Every endpoint
    must answer rather than 500, or the first health check of the season fails."""
    path = tmp_path / "empty.db"
    conn = db.connect(path)
    db.migrate(conn)
    conn.close()
    app.dependency_overrides[get_conn] = _override(path)
    try:
        empty = TestClient(app)
        assert empty.get("/health").json()["counts"]["fixtures"] == 0
        assert empty.get("/fixtures").json() == []
        assert empty.get("/predictions").json() == []
        assert empty.get("/book").json() == []
        assert empty.get("/performance").json() == []
    finally:
        app.dependency_overrides.clear()
