"""The serving API.

Read-only by contract: a request must never change what was served. If an
endpoint could fit, price or bet, then "what did we predict and when" would
have a different answer every time it was asked, and the stored record would
stop being evidence.
"""

from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pytest
from fastapi.testclient import TestClient

from api.main import app, get_conn
from engine import db


def _override(path):
    """A fresh connection per request, which is what production does.

    Reusing one connection across requests fails under TestClient because
    sqlite3 objects are bound to the thread that created them -- and it would
    be wrong in production too, where uvicorn serves from a thread pool.

    `check_same_thread=False` mirrors `api.main.get_conn` exactly. It has to:
    without it this override is a *different* dependency from the one that
    ships, and the defect it guards against is invisible to every test here.
    """
    def dependency():
        conn = db.connect(path, check_same_thread=False)
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


# --- the tip list, which is the customer-facing product --------------------


@pytest.fixture
def tips_client(tmp_path):
    """A database with tips on both sides of today.

    Dates are relative to `date('now')` rather than fixed, because the split
    between what is published and what is settled is exactly what these
    endpoints key on -- a hard-coded date would make the suite start failing on
    a particular morning for reasons nobody would connect to this file.
    """
    path = tmp_path / "tips.db"
    conn = db.connect(path)
    db.migrate(conn)
    for i, name in enumerate(["Arsenal", "Chelsea", "Luton", "Barnsley"], start=1):
        conn.execute("INSERT INTO teams (team_id, canonical_name) VALUES (?, ?)", (i, name))
    for fixture_id, division, offset, home, away in (
        (1, "E0", "+5 days", 1, 2),
        (2, "E2", "+5 days", 3, 4),
        (3, "E0", "-4 days", 2, 1),
        (4, "E0", "-4 days", 1, 3),
    ):
        conn.execute(
            "INSERT INTO fixtures (fixture_id, division, match_date, kickoff_time,"
            " home_team_id, away_team_id, avg_h, avg_d, avg_a, source_file)"
            f" VALUES (?, ?, date('now', '{offset}'), '15:00', ?, ?, 1.9, 3.6, 4.0, 't')",
            (fixture_id, division, home, away),
        )
        conn.execute(
            "INSERT INTO predictions (prediction_id, fixture_id, model_version,"
            " information_set, lam_h, lam_a, p_home, p_draw, p_away, p_over25,"
            " p_under25) VALUES (?, ?, 'v2', 'pre_close', 1.6, 1.1,"
            " 0.48, 0.26, 0.26, 0.52, 0.48)",
            (fixture_id, fixture_id),
        )
    for tip_id, fixture_id, side, prob, settled, outcome, rule, fthg, ftag in (
        (1, 1, "12", 0.78, None, None, "confidence-v2", None, None),
        (2, 2, "H", 0.61, None, None, "confidence-v2", None, None),
        # A void under an EARLIER rule version, on a fixture the current rule
        # also tipped. Two jobs: the denominator can be checked against
        # something that must not count, and `/tips/record` can be checked
        # for pooling every version into the headline while still splitting
        # them in `by_rule` (B16, reversed 2026-08-21). It is the oldest settled row
        # because that is the real shape -- a superseded rule's tips precede
        # the current rule's, and "current" is read off the newest tip.
        # Settled before migration 006 recorded scores: fthg/ftag NULL, which
        # the API must serve as-is rather than invent (tip 3). Tips 4 and 5
        # carry the score they settled from.
        (3, 4, "X2", 0.66, "2026-01-01 12:00:00", "void", "confidence-v1", None, None),
        (4, 3, "1X", 0.72, "2026-01-01 12:00:00", "win", "confidence-v2", 2, 0),
        (5, 4, "A", 0.58, "2026-01-01 12:00:00", "lose", "confidence-v2", 2, 0),
    ):
        conn.execute(
            "INSERT INTO tips (tip_id, prediction_id, fixture_id, side, model_prob,"
            " floor, ceiling, best_price, avg_price, rule_version, settled_at,"
            " outcome, pnl_best, pnl_avg, fthg, ftag) VALUES (?, ?, ?, ?, ?, 0.55,"
            " 0.85, 1.35, 1.28, ?, ?, ?, 0.35, 0.28, ?, ?)",
            (tip_id, fixture_id, fixture_id, side, prob, rule, settled, outcome,
             fthg, ftag),
        )
    conn.commit()
    conn.close()

    app.dependency_overrides[get_conn] = _override(path)
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_tips_returns_only_unplayed_fixtures(tips_client):
    body = tips_client.get("/tips").json()
    assert {t["tip_id"] for t in body} == {1, 2}
    assert all(t["settled_at"] is None for t in body)


def test_tips_publishes_double_chance_sides_intact(tips_client):
    """85.6% of published calls are unions rather than a named team. An endpoint
    that dropped or rewrote them would hide most of the product."""
    sides = {t["side"] for t in tips_client.get("/tips").json()}
    assert "12" in sides


def test_tips_carry_the_model_view_behind_each_call(tips_client):
    """B22: the three outright probabilities and the three double-chance sums
    the call was chosen from ride beside it, summed server-side so the browser
    never forms a probability. `model_prob` on a `12` call equals `p_12`."""
    tip = next(t for t in tips_client.get("/tips").json() if t["tip_id"] == 1)
    assert (tip["p_home"], tip["p_draw"], tip["p_away"]) == (0.48, 0.26, 0.26)
    assert tip["p_1x"] == pytest.approx(0.74)
    assert tip["p_x2"] == pytest.approx(0.52)
    assert tip["p_12"] == pytest.approx(0.74)
    assert 0.0 < tip["p_a15"] < tip["p_h15"] < 1.0   # home is the favourite
    # Settled tips read the same shape.
    settled = tips_client.get("/tips/results").json()
    assert all("p_home" in t and "p_12" in t and "p_h15" in t for t in settled)


def test_the_api_handicap_is_the_rules_handicap():
    """`_with_handicap` restates the pmf rather than importing the eval stack,
    so it is pinned here against the function `engine.serve.tips.select`
    actually compares: `b21.dog15_probs` on `dispersion.score_matrix`."""
    from api.main import MAX_GOALS, _with_handicap
    from engine.eval import b21
    from engine.eval.dispersion import MAX_GOALS as EVAL_MAX_GOALS, score_matrix

    assert MAX_GOALS == EVAL_MAX_GOALS
    lam_h = np.array([1.9, 0.8, 1.3, 2.6])
    lam_a = np.array([0.7, 1.7, 1.3, 0.4])
    rows = _with_handicap([{"lam_h": h, "lam_a": a} for h, a in zip(lam_h, lam_a)])
    # `dog15_probs` reads the favourite off the 1X2 vector; mark it by hand.
    fav_home = np.array([True, False, True, True])
    probs = np.where(fav_home[:, None], [[0.5, 0.25, 0.25]], [[0.25, 0.25, 0.5]])
    expected = b21.dog15_probs(score_matrix(lam_h, lam_a), probs)
    served = np.array([r["p_a15"] if fav else r["p_h15"]
                       for r, fav in zip(rows, fav_home)])
    assert served == pytest.approx(expected, abs=1e-12)


def test_the_model_view_is_the_prediction_the_tip_was_made_from(tmp_path):
    """A fixture re-served after its tip was published has a newer prediction
    row. The tip is never revised, so the view shown behind it must be the row
    it was published from -- otherwise the page shows numbers the call was not
    chosen from, and the two can disagree."""
    path = tmp_path / "stale.db"
    conn = db.connect(path)
    db.migrate(conn)
    conn.execute("INSERT INTO teams (team_id, canonical_name) VALUES (1, 'Luton')")
    conn.execute("INSERT INTO teams (team_id, canonical_name) VALUES (2, 'Barnsley')")
    conn.execute(
        "INSERT INTO fixtures (fixture_id, division, match_date, kickoff_time,"
        " home_team_id, away_team_id, source_file)"
        " VALUES (1, 'E2', date('now', '+2 days'), '15:00', 1, 2, 't')")
    for prediction_id, served_at, p_home in ((1, "2026-01-01 06:00:00", 0.40),
                                             (2, "2026-01-02 06:00:00", 0.70)):
        conn.execute(
            "INSERT INTO predictions (prediction_id, fixture_id, served_at,"
            " model_version, information_set, lam_h, lam_a, p_home, p_draw,"
            " p_away, p_over25, p_under25)"
            " VALUES (?, 1, ?, 'v2', 'pre_close', 1.5, 1.1, ?, 0.25, ?, 0.5, 0.5)",
            (prediction_id, served_at, p_home, round(0.75 - p_home, 2)))
    conn.execute(
        "INSERT INTO tips (prediction_id, fixture_id, side, model_prob, floor,"
        " ceiling, rule_version) VALUES (1, 1, '12', 0.75, 0.55, 0.85, 'confidence-v2')")
    conn.commit()
    conn.close()

    app.dependency_overrides[get_conn] = _override(path)
    try:
        [tip] = TestClient(app).get("/tips").json()
    finally:
        app.dependency_overrides.clear()
    assert tip["p_home"] == 0.40, "the view must come from prediction 1, not the newer 2"
    assert tip["p_away"] == 0.35


def test_tips_filter_by_division_and_reject_unknown_ones(tips_client):
    only_e2 = tips_client.get("/tips", params={"division": "E2"}).json()
    assert [t["division"] for t in only_e2] == ["E2"]
    assert tips_client.get("/tips", params={"division": "EC"}).status_code == 400


def test_tip_results_are_settled_only_and_most_recent_first(tips_client):
    body = tips_client.get("/tips/results").json()
    assert {t["tip_id"] for t in body} == {3, 4, 5}
    assert all(t["outcome"] is not None for t in body)
    dates = [t["match_date"] for t in body]
    assert dates == sorted(dates, reverse=True)


def test_tip_results_carry_the_score_they_settled_from(tips_client):
    """Migration 006: the grader keeps the score beside the outcome and the
    endpoint serves it. A row settled before the column existed serves NULLs
    rather than a reconstruction."""
    body = {t["tip_id"]: t for t in tips_client.get("/tips/results").json()}
    assert (body[4]["fthg"], body[4]["ftag"]) == (2, 0)
    assert body[3]["fthg"] is None and body[3]["ftag"] is None


def test_the_record_excludes_voids_from_the_strike_rate(tips_client):
    """A void is not a loss. Counting it as one would understate the rule, and
    counting it as a win would overstate it; it leaves the denominator.

    The fixture's void is a `confidence-v1` tip, so it is checked where that
    version's record now lives -- `by_rule` -- rather than in the headline."""
    body = tips_client.get("/tips/record").json()
    v1 = next(r for r in body["by_rule"] if r["rule_version"] == "confidence-v1")
    assert v1["published"] == 1
    assert v1["graded"] == 0            # the void is not graded
    assert v1["strike_rate"] is None    # and does not read as 0%


def test_the_record_headline_pools_every_rule_version(tips_client):
    """`BACKLOG.md` B16, reversed 2026-08-21. The headline and `by_division`
    are the whole published history across rule versions: the v1 void counts
    in `published` (and stays out of `graded`), and `rule` names the version
    currently publishing rather than the version the headline is for. Every
    version is still reported, grouped, so the pooled number decomposes."""
    body = tips_client.get("/tips/record").json()
    assert body["rule"]["rule_version"] == "confidence-v2"
    assert body["published"] == 5       # the v1 tip is in the pool
    assert body["graded"] == 2          # win + lose; the void is not graded
    assert body["won"] == 1
    assert body["strike_rate"] == pytest.approx(0.5)
    assert body["upcoming"] == 2
    assert sum(d["published"] for d in body["by_division"]) == 5

    versions = [r["rule_version"] for r in body["by_rule"]]
    assert versions == ["confidence-v2", "confidence-v1"]   # newest first
    assert sum(r["published"] for r in body["by_rule"]) == 5


def test_the_record_publishes_no_profit_figure(tips_client):
    """The load-bearing honesty test (`BACKLOG.md` B7).

    The `tips` table carries `pnl_best` and `pnl_avg`, and the fixture above
    populates both. `engine/eval/tips.py` measured that the return at customer
    prices is negative at every sellable setting with no interval excluding
    zero, so the product is sold on strike rate alone. If P&L ever reaches this
    payload a surface can advertise a return without anyone deciding to.
    """
    body = tips_client.get("/tips/record").json()
    banned = ("pnl", "profit", "roi", "return_pct", "units", "yield")
    fields = [str(k).lower() for k in body]
    fields += [str(k).lower() for row in body["by_division"] for k in row]
    fields += [str(k).lower() for row in body["by_rule"] for k in row]
    assert not [f for f in fields if any(word in f for word in banned)]
    assert body["return_supported"] is False


def test_the_record_reports_no_strike_rate_rather_than_zero_when_nothing_is_graded(tmp_path):
    """Opening weekend. A zero would read as "we get everything wrong"."""
    path = tmp_path / "fresh.db"
    conn = db.connect(path)
    db.migrate(conn)
    conn.close()
    app.dependency_overrides[get_conn] = _override(path)
    try:
        body = TestClient(app).get("/tips/record").json()
        assert body["strike_rate"] is None
        assert body["published"] == 0
    finally:
        app.dependency_overrides.clear()


def test_the_dependency_survives_being_opened_and_used_on_different_threads(tmp_path):
    """The defect the tip page found, pinned at the level it actually occurs.

    FastAPI runs a sync generator dependency's setup, the endpoint body and its
    teardown as three separate threadpool hand-offs. They are not guaranteed to
    land on the same worker, so a per-request connection is routinely created on
    one thread and used on another. sqlite3 rejects that by default.

    It stayed hidden because the old frontend fetched one endpoint per page:
    with requests strictly serialised the pool reuses one worker and the hand-off
    is invisible. The tip page fetches three at once, and every load failed.
    """
    path = tmp_path / "threads.db"
    conn = db.connect(path)
    db.migrate(conn)
    conn.close()

    opened = db.connect(path, check_same_thread=False)
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            count = pool.submit(
                lambda: opened.execute("SELECT COUNT(*) FROM tips").fetchone()[0]
            ).result()
        assert count == 0
    finally:
        opened.close()

    # The guard is still on everywhere else, so a connection crossing threads
    # in the cycle or the grader remains the error it should be.
    guarded = db.connect(path)
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            with pytest.raises(sqlite3.ProgrammingError):
                pool.submit(lambda: guarded.execute("SELECT 1").fetchone()).result()
    finally:
        guarded.close()


def test_the_request_connection_is_opened_without_the_thread_guard(monkeypatch):
    """The half of the fix that lives in `api.main`, pinned directly.

    Asserting it through the app does not work: under `TestClient` the portal
    reuses a single worker, so the hand-off never crosses threads and the
    endpoints pass either way. That is precisely why this shipped -- a live
    uvicorn spreads the same dependency across a real pool and a TestClient
    does not. So the kwarg is checked at the call, which is deterministic.
    """
    seen = {}

    def fake_connect(path=None, **kwargs):
        seen.update(kwargs)
        return sqlite3.connect(":memory:")

    monkeypatch.setattr(db, "connect", fake_connect)
    generator = get_conn()
    next(generator)
    generator.close()
    assert seen.get("check_same_thread") is False


def test_concurrent_requests_all_succeed(tips_client):
    """A smoke test, not the guard above: the surface fetches three at once."""
    paths = ["/tips", "/tips/results", "/tips/record", "/health"] * 4
    with ThreadPoolExecutor(max_workers=8) as pool:
        codes = list(pool.map(lambda p: tips_client.get(p).status_code, paths))
    assert set(codes) == {200}


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
        assert empty.get("/tips").json() == []
        assert empty.get("/tips/results").json() == []
        assert empty.get("/tips/record").json()["published"] == 0
    finally:
        app.dependency_overrides.clear()


# --- the parlay, a view over the tip list ----------------------------------


def test_parlay_ranks_the_published_calls_by_claim_and_multiplies_them(tips_client):
    """B24: the legs are `/tips` rows, ordered by claim, and `claimed` is
    their product -- formed server-side, as every probability on the wire is."""
    body = tips_client.get("/parlay", params={"legs": 2, "min_claim": 0.5}).json()
    assert [t["tip_id"] for t in body["legs"]] == [1, 2]          # 0.78 then 0.61
    assert body["claimed"] == pytest.approx(0.78 * 0.61)
    assert (body["requested"], body["available"], body["pool"]) == (2, 2, 2)
    assert body["min_claim"] == 0.5 and body["division"] is None
    assert body["size_warning"] is False
    # Each leg carries the same shape as a `/tips` row, model view included.
    leg = body["legs"][0]
    assert leg["side"] == "12" and leg["home_team"] == "Arsenal"
    assert "p_12" in leg and "p_h15" in leg and leg["settled_at"] is None


def test_parlay_never_pads_below_the_threshold(tips_client):
    """Fewer calls clear the bar than legs asked for: the parlay is what
    cleared, and `available` says so. The default (0.80) clears nothing in
    this fixture and claims None -- never 0, which would read as certain to lose."""
    body = tips_client.get("/parlay", params={"legs": 2, "min_claim": 0.7}).json()
    assert [t["tip_id"] for t in body["legs"]] == [1]
    assert (body["requested"], body["available"]) == (2, 1)
    assert body["claimed"] == pytest.approx(0.78)
    default = tips_client.get("/parlay").json()
    assert default["legs"] == [] and default["claimed"] is None
    assert (default["requested"], default["min_claim"]) == (2, 0.80)


def test_parlay_filters_by_division_and_warns_at_four_legs(tips_client):
    body = tips_client.get("/parlay", params={"division": "E2", "min_claim": 0.5}).json()
    assert [t["tip_id"] for t in body["legs"]] == [2] and body["division"] == "E2"
    assert tips_client.get("/parlay", params={"legs": 4}).json()["size_warning"] is True
    assert tips_client.get("/parlay", params={"legs": 3}).json()["size_warning"] is False


def test_parlay_rejects_bad_sizes_thresholds_and_divisions(tips_client):
    assert tips_client.get("/parlay", params={"legs": 1}).status_code == 400
    assert tips_client.get("/parlay", params={"legs": 5}).status_code == 400
    assert tips_client.get("/parlay", params={"min_claim": 1.5}).status_code == 400
    assert tips_client.get("/parlay", params={"division": "EC"}).status_code == 400


def test_parlay_drops_fixtures_whose_kickoff_has_passed(tips_client, monkeypatch):
    """The pool is `/tips` minus anything already under way, on the UK clock.
    The clock is pinned rather than the fixture dated, so the test does not
    depend on the time of day it runs."""
    from datetime import datetime
    import api.main as main
    monkeypatch.setattr(main, "_london_now", lambda: datetime(2000, 1, 1, 12, 0))
    before = tips_client.get("/parlay", params={"min_claim": 0.5}).json()
    assert before["available"] == 2
    monkeypatch.setattr(main, "_london_now", lambda: datetime(2099, 1, 1, 12, 0))
    after = tips_client.get("/parlay", params={"min_claim": 0.5}).json()
    assert after["available"] == 0 and after["legs"] == [] and after["pool"] == 0
