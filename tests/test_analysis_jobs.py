"""The analysis as a stored job, the cycle step and the signed-in route
(`services/analysis/jobs.py`, `services/run_cycle.step_analysis`,
`GET /fixture/{id}/analysis`).

The model is a stateless responder, never the network. It answers each
request from the request itself, because the job runs fixtures in parallel
and a scripted queue would hand one fixture's answer to another. The calls
are made by the shipped rule (`tips.select`), so every pack builds.

What is pinned:

- the store's safety property: one ok and one fallback per fixture and
  prompt version, an ok never replaced, a fallback superseded once;
- the Stage A cache surviving a run;
- the time budget turning into stored fallbacks;
- the step being off by default and costing nothing on a dry run;
- the route being signed-in only.
"""

from __future__ import annotations

import json
import threading
from types import SimpleNamespace

import numpy as np
import pandas as pd
import psycopg
import pytest

from engine import config, db
from engine.eval import metrics
from engine.serve import tips
from services import run_cycle
from services.analysis import jobs, llm
from services.analysis.analyse import OUT_OF_TIME
from services.analysis.schemas import MatchAnalysis, Pick, TeamSummary
from tests.conftest import relative_date
from tests.test_auth import auth_client, sign_in  # noqa: F401

TEAMS = {1: "Leeds", 2: "Hull", 3: "Stoke", 4: "Wrexham"}
#: fixture_id: (days from today, home, away, lam_h, lam_a)
FIXTURES = {10: (0, 1, 2, 2.6, 0.7), 11: (0, 3, 4, 1.4, 1.2), 12: (-2, 1, 3, 1.5, 1.1)}


def seed(url: str) -> None:
    conn = db.connect(url)
    db.migrate(conn)
    for team_id, name in TEAMS.items():
        conn.execute("INSERT INTO teams (team_id, canonical_name) VALUES (%s, %s)",
                     (team_id, name))
    for team_id in TEAMS:
        # Last season's division: every side has at least one fact.
        conn.execute(
            "INSERT INTO matches (match_id, season, division, match_date, home_team_id,"
            " away_team_id, fthg, ftag, odds_era, source_file)"
            " VALUES (%s, '202526', 'E1', '2026-03-01', %s, %s, 1, 0, 'market', 't')",
            (f"m{team_id}", team_id, 1 + team_id % 4))
    for fid, (offset, home, away, _, _) in FIXTURES.items():
        conn.execute(
            "INSERT INTO fixtures (fixture_id, division, match_date, kickoff_time,"
            " home_team_id, away_team_id, source_file) VALUES (%s, 'E1', %s, '15:00', %s, %s, 't')",
            (fid, relative_date(offset), home, away))
    ids = list(FIXTURES)
    lam_h = np.array([FIXTURES[f][3] for f in ids])
    lam_a = np.array([FIXTURES[f][4] for f in ids])
    probs = metrics.model_probs(lam_h, lam_a)
    served = pd.DataFrame({
        "fixture_id": ids, "prediction_id": ids, "lam_h": lam_h, "lam_a": lam_a,
        "p_home": probs.p_h, "p_draw": probs.p_d, "p_away": probs.p_a,
        **{c: np.nan for c in ("max_h", "max_d", "max_a", "avg_h", "avg_d", "avg_a")}})
    for r in served.itertuples():
        conn.execute(
            "INSERT INTO predictions (prediction_id, fixture_id, model_version, information_set,"
            " lam_h, lam_a, p_home, p_draw, p_away, p_over25, p_under25)"
            " VALUES (%s, %s, 'test-model', 'pre_close', %s, %s, %s, %s, %s, 0.5, 0.5)",
            (r.prediction_id, r.fixture_id, r.lam_h, r.lam_a, r.p_home, r.p_draw, r.p_away))
    tips.publish(conn, tips.select(served))
    conn.commit()
    conn.close()


@pytest.fixture
def store(database_url):
    seed(database_url)
    conn = db.connect(database_url)
    yield conn
    conn.close()


class Responder:
    """`client.responses.parse`, answering each request from its own content."""

    def __init__(self, answer):
        self.answer = answer
        self.requests = []
        self.responses = self
        self._lock = threading.Lock()

    def parse(self, **kwargs):
        with self._lock:
            self.requests.append(kwargs)
        item = self.answer(kwargs)
        return SimpleNamespace(output_parsed=item, output_text=item.model_dump_json(),
                               usage=SimpleNamespace(input_tokens=1000, output_tokens=200))


def good(kwargs):
    """A valid answer to any request: cites a fact that exists, quotes no number."""
    payload = json.loads(kwargs["input"][0]["content"])
    if kwargs["text_format"] is TeamSummary:
        fact = next(f["id"] for f in payload["facts"] if f["id"].endswith("_DIVISION_LAST_SEASON"))
        return TeamSummary(narrative=f"{payload['team']} have a division on record.",
                           strengths=[], weaknesses=[], trend="stable", cited_facts=[fact])
    call = next(m for m in payload["menu"] if m["is_call"])
    return MatchAnalysis(
        preview="The rule weighed the menu.", risk_commentary="Few games so far.",
        call=Pick(side=payload["call"]["side"], rationale="The likeliest eligible market.",
                  supporting_facts=[call["id"]], contradicting_facts=[]))


def invents_a_number(kwargs):
    answer = good(kwargs)
    if kwargs["text_format"] is MatchAnalysis:
        return answer.model_copy(update={"risk_commentary": "They win 64% of the time."})
    return answer


def rows(conn, sql="SELECT fixture_id, status FROM match_analyses ORDER BY analysis_id"):
    return [tuple(r.values()) for r in conn.execute(sql)]


# --- the job -------------------------------------------------------------- #


def test_pending_is_todays_calls_without_an_analysis(store):
    assert jobs.pending(store) == [10, 11]                 # 12 was played two days ago
    jobs.run(store, [10], Responder(good), llm_model="m")
    assert jobs.pending(store) == [11]


def test_a_run_stores_text_summaries_and_its_cost(store):
    report = jobs.run(store, [10, 11], Responder(good), llm_model="gpt-test")
    assert (report.count("ok"), report.written) == (2, 2)
    row = store.execute("SELECT * FROM match_analyses WHERE fixture_id = 10").fetchone()
    assert row["status"] == "ok" and row["llm_model"] == "gpt-test"
    assert row["analysis"]["call"]["side"] == row["evidence_pack"]["call"]["side"]
    assert set(row["summaries"]) == {"home", "away"}
    assert (row["input_tokens"], row["output_tokens"]) == (3000, 600)
    assert [a["stage"] for a in row["attempts"]] == ["summary_home", "summary_away", "analysis"]
    assert db.scalar(store, "SELECT COUNT(*) FROM team_summaries") == 4


def test_an_ok_is_never_replaced(store):
    jobs.run(store, [10], Responder(good), llm_model="m")
    again = jobs.run(store, [10], Responder(good), llm_model="m")
    assert again.written == 0
    assert rows(store) == [(10, "ok")]


def test_a_fallback_is_superseded_once_and_never_duplicated(store):
    first = jobs.run(store, [10], Responder(invents_a_number), llm_model="m")
    assert first.count("fallback") == 1 and first.written == 1
    assert jobs.run(store, [10], Responder(invents_a_number), llm_model="m").written == 0
    assert jobs.run(store, [10], Responder(good), llm_model="m").written == 1
    assert rows(store) == [(10, "fallback"), (10, "ok")]
    row = store.execute("SELECT * FROM match_analyses WHERE status = 'fallback'").fetchone()
    assert row["analysis"] is None and row["summaries"] is None
    assert "64%" in json.dumps(row["attempts"])


def test_the_store_refuses_text_on_a_fallback_and_an_ok_without_text(store):
    for status, analysis in (("ok", None), ("fallback", '{"preview": "x"}')):
        with pytest.raises(psycopg.errors.CheckViolation):
            store.execute(
                "INSERT INTO match_analyses (fixture_id, tip_id, prompt_version, llm_model,"
                " model_version, status, evidence_pack, analysis, attempts, warnings,"
                " input_tokens, output_tokens) VALUES (10, 1, 'v', 'm', 'm', %s, '{}', %s,"
                " '[]', '[]', 0, 0)", (status, analysis))
        store.rollback()


def test_stored_summaries_are_the_next_runs_cache(store):
    jobs.run(store, [10], Responder(invents_a_number), llm_model="m")   # summaries pass
    api = Responder(good)
    jobs.run(store, [10], api, llm_model="m")
    assert [r["text_format"] for r in api.requests] == [MatchAnalysis]   # Stage B only


def test_an_exhausted_budget_stores_fallbacks_without_asking(store):
    api = Responder(good)
    report = jobs.run(store, [10, 11], api, llm_model="m", budget=0)
    assert api.requests == []
    assert (report.count("fallback"), report.written) == (2, 2)
    assert OUT_OF_TIME in json.dumps(store.execute(
        "SELECT attempts FROM match_analyses WHERE fixture_id = 10").fetchone()["attempts"])


def test_a_dry_run_asks_and_stores_nothing(store):
    report = jobs.run(store, [10], Responder(good), llm_model="m", dry_run=True)
    assert report.count("ok") == 1 and report.written == 0
    assert rows(store) == []


def test_rerun_only_retries_a_fallback_before_kick_off(store):
    assert "no fallback" in jobs.rerunnable(store, 10)
    jobs.run(store, [10], Responder(invents_a_number), llm_model="m")
    assert jobs.rerunnable(store, 10) is None
    jobs.run(store, [10], Responder(good), llm_model="m")
    assert "never replaced" in jobs.rerunnable(store, 10)
    store.execute(
        "INSERT INTO match_analyses (fixture_id, tip_id, prompt_version, llm_model,"
        " model_version, status, evidence_pack, attempts, warnings, input_tokens,"
        " output_tokens) SELECT 12, tip_id, %s, 'm', 'm', 'fallback', '{}', '[]', '[]', 0, 0"
        " FROM tips WHERE fixture_id = 12", (jobs.ANALYSIS_PROMPT,))
    assert "was played" in jobs.rerunnable(store, 12)
    assert "does not exist" in jobs.rerunnable(store, 999)


# --- the cycle step ------------------------------------------------------- #


def test_the_step_is_off_unless_enabled(store):
    step = run_cycle.step_analysis(store, dry_run=False)
    assert step.status == run_cycle.Status.OK and "disabled" in step.detail
    assert rows(store) == []


@pytest.fixture
def enabled(monkeypatch):
    def use(answer):
        api = Responder(answer)
        monkeypatch.setattr(config, "ANALYSIS_ENABLED", True)
        monkeypatch.setattr(config, "AZURE_MODEL", "gpt-test")
        monkeypatch.setattr(llm, "client", lambda: api)
        return api
    return use


def test_the_step_analyses_todays_calls(store, enabled):
    enabled(good)
    step = run_cycle.step_analysis(store, dry_run=False)
    assert step.status == run_cycle.Status.OK
    assert step.detail.startswith("2 call(s): 2 ok, 0 fallback, 2 stored")
    assert rows(store) == [(10, "ok"), (11, "ok")]


def test_a_fallback_asks_for_a_look_and_names_the_rerun(store, enabled):
    enabled(invents_a_number)
    step = run_cycle.step_analysis(store, dry_run=False)
    assert step.status == run_cycle.Status.ATTENTION
    assert "rerun --fixture" in step.detail


def test_a_dry_cycle_costs_nothing(store, enabled):
    api = enabled(good)
    step = run_cycle.step_analysis(store, dry_run=True)
    assert step.detail == "2 call(s) would be analysed"
    assert api.requests == [] and rows(store) == []


# --- the signed-in route -------------------------------------------------- #


def test_the_route_is_signed_in_only_and_404_before_an_analysis(auth_client):  # noqa: F811
    client, url = auth_client
    seed(url)
    assert client.get("/fixture/10/analysis").status_code == 401
    sign_in(client)
    assert client.get("/fixture/10/analysis").status_code == 404


def test_the_route_serves_the_ok_with_its_evidence_resolved(auth_client):  # noqa: F811
    client, url = auth_client
    seed(url)
    conn = db.connect(url)
    jobs.run(conn, [10], Responder(invents_a_number), llm_model="m")   # a fallback first
    jobs.run(conn, [10], Responder(good), llm_model="m")
    conn.close()
    sign_in(client)
    body = client.get("/fixture/10/analysis").json()
    assert body["status"] == "ok"
    assert body["generated_at"].endswith("Z")
    call = body["analysis"]["call"]
    assert call["side"] == body["evidence_pack"]["call"]["side"]
    (cited,) = call["supporting"]
    assert cited["unit"] == "%" and cited["value"] == body["evidence_pack"]["call"]["model_prob"]
    assert set(body["summaries"]) == {"home", "away"}


def test_the_route_serves_a_fallback_as_numbers_only(auth_client):  # noqa: F811
    client, url = auth_client
    seed(url)
    conn = db.connect(url)
    jobs.run(conn, [11], Responder(invents_a_number), llm_model="m")
    conn.close()
    sign_in(client)
    body = client.get("/fixture/11/analysis").json()
    assert body["status"] == "fallback"
    assert body["analysis"] is None and body["summaries"] is None
    assert body["evidence_pack"]["facts"] and body["evidence_pack"]["menu"]


def test_the_public_fixture_says_only_whether_an_analysis_exists(auth_client):  # noqa: F811
    client, url = auth_client
    seed(url)
    assert client.get("/fixture/10").json()["has_analysis"] is False
    conn = db.connect(url)
    jobs.run(conn, [10], Responder(good), llm_model="m")
    conn.close()
    body = client.get("/fixture/10").json()                 # signed out
    assert body["has_analysis"] is True
    assert "The rule weighed the menu" not in json.dumps(body)


# --- the metrics ---------------------------------------------------------- #


def test_metrics_count_the_writing_not_the_calls(store):
    from services.analysis import metrics

    jobs.run(store, [10], Responder(good), llm_model="m")
    jobs.run(store, [11], Responder(invents_a_number), llm_model="m")
    (s,) = metrics.compute(store, price_in=1.0, price_out=10.0)
    assert (s["fixtures"], s["ended_ok"], s["ended_fallback"]) == (2, 1, 1)
    assert s["fallback_rate"] == 0.5 and s["first_pass_ok"] == 1
    # 10: two summaries and one analysis. 11: two summaries, then the analysis
    # three times, each rejected for the invented 64%.
    assert (s["requests"], s["retries"]) == (3 + 5, 2)
    assert s["rejections"] == {"number not in the evidence": 3}
    assert (s["tokens_in"], s["tokens_out"]) == (8000, 1600)
    assert s["cost"] == round((8000 * 1.0 + 1600 * 10.0) / 1e6, 4)

    jobs.run(store, [11], Responder(good), llm_model="m")      # the fallback, re-run
    (s,) = metrics.compute(store)
    assert (s["ended_ok"], s["fallbacks_superseded"]) == (2, 1)
    assert "cost" not in s                                    # no price, no cost
    assert metrics.compute(store, since="2999-01-01") == []


def test_metrics_name_an_unknown_error_rather_than_drop_it():
    from services.analysis import metrics

    assert metrics.rule_of("analysis", "call.side: X2 is not the published call 12") == \
        "explained another call"
    assert metrics.rule_of("api", "APIConnectionError: down") == "API error"
    assert metrics.rule_of("analysis", "something new") == "other"
