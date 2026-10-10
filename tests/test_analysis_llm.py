"""The analysis chain with the model mocked (`services/analysis/analyse.py`,
`llm.py`): retry with the errors fed back, then the fallback.

No test here reaches the network. The scripted fakes stand in for the
model's four ways to go wrong that the brief names: a hallucinated fact id,
an invented percentage, a call other than the published one, and a reply
that is not an answer at all. Each is checked through to its outcome.

One opt-in test (`RUN_LLM_TESTS=1`) runs a real fixture end to end against
the configured deployment and store.
"""

from __future__ import annotations

import os
from types import SimpleNamespace

import httpx
import openai
import pytest

from services.analysis import llm
from services.analysis.analyse import RETRIES, analyse, dossier_hash
from tests.test_analysis_validate import good_analysis, good_summary, make_pack


class FakeAPI:
    """`client.responses.parse`, answering from a script. A script entry is a
    model instance (the answer), None (a refusal), or an exception."""

    def __init__(self, *script):
        self.script = list(script)
        self.requests = []
        self.responses = self

    def parse(self, **kwargs):
        self.requests.append(kwargs)
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return SimpleNamespace(
            output_parsed=item, output_text="" if item is None else item.model_dump_json(),
            usage=SimpleNamespace(input_tokens=1000, output_tokens=200))


def away_summary():
    return good_summary(narrative="Hull City have taken 0.8 points per game in their last 5.",
                        strengths=[], weaknesses=["0.8 points per game"],
                        trend="declining", cited_facts=["AWAY_PPG_L5"])


def run(*script, cache=None):
    api = FakeAPI(*script)
    return analyse(make_pack(), api, {} if cache is None else cache), api


def test_a_valid_chain_is_ok_and_costed():
    outcome, api = run(good_summary(), away_summary(), good_analysis())
    assert outcome.status == "ok"
    assert outcome.analysis == good_analysis()
    assert set(outcome.summaries) == {"home", "away"}
    assert [a.stage for a in outcome.attempts] == ["summary_home", "summary_away", "analysis"]
    assert (outcome.input_tokens, outcome.output_tokens) == (3000, 600)
    # The fixed instructions travel separately from the data, every time.
    assert all(r["instructions"] for r in api.requests)


def test_a_hallucinated_fact_id_is_sent_back_and_fixed():
    bad = good_analysis(call={"supporting_facts": ["MENU_12", "HOME_XG_L5"]})
    outcome, api = run(good_summary(), away_summary(), bad, good_analysis())
    assert outcome.status == "ok"
    assert [a.errors for a in outcome.attempts if a.stage == "analysis"] == [
        ["call.supporting_facts: unknown id HOME_XG_L5"], []]
    retry = api.requests[-1]["input"]
    assert retry[-2] == {"role": "assistant", "content": bad.model_dump_json()}
    assert "HOME_XG_L5" in retry[-1]["content"] and retry[-1]["role"] == "user"


def test_an_invented_percentage_every_time_ends_in_the_fallback():
    bad = good_analysis(risk_commentary="Hull win 31% of away games.")
    outcome, api = run(good_summary(), away_summary(), *[bad] * (RETRIES + 1))
    assert outcome.status == "fallback" and outcome.analysis is None
    tries = [a for a in outcome.attempts if a.stage == "analysis"]
    assert len(tries) == RETRIES + 1
    assert all("31%" in a.errors[0] for a in tries)
    assert api.script == []                                 # no fourth request


def test_explaining_a_different_call_ends_in_the_fallback():
    bad = good_analysis(call={"side": "A+1.5"})
    outcome, _ = run(good_summary(), away_summary(), *[bad] * (RETRIES + 1))
    assert outcome.status == "fallback"
    assert outcome.attempts[-1].errors == ["call.side: A+1.5 is not the published call 12"]


def test_a_failed_summary_stops_the_chain_before_the_analysis():
    bad = good_summary(cited_facts=["NOPE"])
    outcome, api = run(*[bad] * (RETRIES + 1))
    assert outcome.status == "fallback"
    assert {a.stage for a in outcome.attempts} == {"summary_home"}
    assert len(api.requests) == RETRIES + 1


def test_a_refusal_or_unparseable_reply_is_a_rejected_attempt():
    outcome, _ = run(None, ValueError("bad json"), good_summary(), away_summary(),
                     good_analysis())
    assert outcome.status == "ok"
    assert [a.errors[0][:8] for a in outcome.attempts[:2]] == ["schema: ", "schema: "]


def test_an_api_error_is_a_fallback_not_a_crash():
    down = openai.APIConnectionError(request=httpx.Request("POST", "https://example.invalid"))
    outcome, _ = run(down)
    assert outcome.status == "fallback"
    assert outcome.attempts[-1].stage == "api"


def test_summaries_are_cached_by_their_facts():
    cache = {}
    run(good_summary(), away_summary(), good_analysis(), cache=cache)
    assert len(cache) == 2
    outcome, api = run(good_analysis(), cache=cache)        # only Stage B is asked
    assert outcome.status == "ok" and len(api.requests) == 1

    pack = make_pack()
    facts = [f for f in pack.facts if f.scope == "home_team"]
    assert dossier_hash("Leeds United", facts) == dossier_hash("Leeds United", facts[::-1])
    assert dossier_hash("Leeds United", facts) != dossier_hash("Leeds United", facts[1:])
    assert dossier_hash("Leeds United", facts) != dossier_hash("Leeds United", facts,
                                                               "team_summary_v2")


def test_the_base_url_is_trimmed_to_the_v1_root():
    assert llm.base_url("https://x.services.ai.azure.com/openai/v1/responses") == \
        "https://x.services.ai.azure.com/openai/v1/"
    assert llm.base_url("https://x.services.ai.azure.com/openai/v1/") == \
        "https://x.services.ai.azure.com/openai/v1/"


def test_an_unconfigured_client_says_what_is_missing(monkeypatch):
    monkeypatch.setattr(llm.config, "AZURE_FOUNDRY_KEY", "")
    with pytest.raises(RuntimeError, match="AZURE_FOUNDRY_KEY"):
        llm.client()


@pytest.mark.skipif(os.environ.get("RUN_LLM_TESTS") != "1",
                    reason="spends real tokens; set RUN_LLM_TESTS=1")
def test_a_real_fixture_end_to_end():
    """Against the store `BVP_DATABASE_URL` names, the latest v3 call (or
    `BVP_LLM_TEST_FIXTURE`), through the configured deployment."""
    from engine import db
    from services.analysis.pack import build_pack

    conn = db.connect()
    fixture = os.environ.get("BVP_LLM_TEST_FIXTURE") or db.scalar(
        conn, "SELECT fixture_id FROM tips WHERE rule_version = 'confidence-v3'"
              " ORDER BY tip_id DESC LIMIT 1")
    outcome = analyse(build_pack(conn, int(fixture)), llm.client(), {})
    assert outcome.status in ("ok", "fallback")
    assert outcome.input_tokens > 0
    if outcome.status == "ok":
        assert outcome.analysis.call.side == build_pack(conn, int(fixture)).call.side
