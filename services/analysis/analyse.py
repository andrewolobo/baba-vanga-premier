"""Pack → team summaries → match analysis: validated, or the fallback.

**Stage A** (`summarise`) writes one profile per side from that side's
facts. It is cached by a hash of those facts and the prompt version, so a
club whose record has not changed since its last fixture costs nothing.

**Stage B** (`explain`) writes the preview and the explanation of the call,
from both profiles and the whole pack.

Each answer goes through `validate.py`. A rejected answer goes back to the
model with the errors, at most `RETRIES` times. The last failure, an API
error, or a passed `deadline` ends in the fallback: status "fallback", no
text, and the page draws the numbers-only card from the pack. **Unvalidated
text is never returned.**

The deadline is checked before each request, so one run cannot outlast the
cycle's own timeout however slow the provider is. Overshoot is bounded by
a single request's timeout (`llm.TIMEOUT_SECONDS`, times its transport
retries).
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import MutableMapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import openai

from services.analysis import llm, validate
from services.analysis.schemas import EvidencePack, Fact, MatchAnalysis, TeamSummary

PROMPTS = Path(__file__).parent / "prompts"
#: Prompt versions are the prompt files' names, stored with every output.
#: Changing a prompt means a new file and a new version, never an edit.
SUMMARY_PROMPT = "team_summary_v1"
ANALYSIS_PROMPT = "match_analysis_v1"
#: Content retries per stage after a rejection, with the errors fed back.
RETRIES = 2

FEEDBACK = ("Your answer failed these checks:\n{errors}\n\n"
            "Answer again in the same JSON format, fixing every one. Keep everything "
            "that was not flagged.")


@dataclass(frozen=True)
class Attempt:
    """One request, for the record: which stage, which try, what the
    validator said (empty when it passed), and what it cost."""

    stage: str
    attempt: int
    errors: list[str]
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class Outcome:
    status: Literal["ok", "fallback"]
    analysis: MatchAnalysis | None = None
    summaries: dict[str, TeamSummary] = field(default_factory=dict)
    attempts: list[Attempt] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def input_tokens(self) -> int:
        return sum(a.input_tokens for a in self.attempts)

    @property
    def output_tokens(self) -> int:
        return sum(a.output_tokens for a in self.attempts)


def prompt(version: str) -> str:
    return (PROMPTS / f"{version}.md").read_text(encoding="utf-8")


def dossier(pack: EvidencePack, side: str) -> list[Fact]:
    """One side's facts: Stage A's whole input besides the club's name."""
    return [f for f in pack.facts if f.scope == f"{side}_team"]


def dossier_hash(name: str, facts: list[Fact], version: str = SUMMARY_PROMPT) -> str:
    """The Stage A cache key: the same club, facts and prompt give the same
    profile, so they get the same key. Facts are sorted, so their order
    does not matter."""
    payload = {"team": name, "prompt": version,
               "facts": [f.model_dump() for f in sorted(facts, key=lambda f: f.id)]}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def _fact(f: Fact) -> dict:
    return f.model_dump(exclude_none=True)


#: What a request not made because the time ran out records as its error.
OUT_OF_TIME = "time budget exhausted before this request"


def _run(api, stage: str, version: str, payload: dict, schema, check,
         deadline: float | None = None):
    """Ask, validate, and retry with the errors: (answer or None, attempts,
    warnings from the answer that passed)."""
    instructions = prompt(version)
    messages = [{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}]
    attempts = []
    for n in range(1, RETRIES + 2):
        if deadline is not None and time.monotonic() >= deadline:
            attempts.append(Attempt(stage, n, [OUT_OF_TIME]))
            break
        reply = llm.ask(api, instructions, messages, schema)
        errors, warnings = ([f"schema: {reply.error}"], []) if reply.parsed is None \
            else check(reply.parsed)
        attempts.append(Attempt(stage, n, errors, reply.input_tokens, reply.output_tokens))
        if not errors:
            return reply.parsed, attempts, warnings
        if reply.raw:
            messages = messages + [{"role": "assistant", "content": reply.raw}]
        messages = messages + [{"role": "user", "content": FEEDBACK.format(
            errors="\n".join(f"- {e}" for e in errors))}]
    return None, attempts, []


def summarise(api, pack: EvidencePack, side: str,
              cache: MutableMapping[str, TeamSummary], deadline: float | None = None):
    """Stage A for one side: (profile or None, attempts, warnings)."""
    name = pack.home if side == "home" else pack.away
    facts = dossier(pack, side)
    if not facts:
        return None, [Attempt(f"summary_{side}", 0, ["no facts about this side"])], []
    key = dossier_hash(name, facts)
    if key in cache:
        return cache[key], [], []
    summary, attempts, warnings = _run(
        api, f"summary_{side}", SUMMARY_PROMPT,
        {"team": name, "facts": [_fact(f) for f in facts]},
        TeamSummary, lambda s: validate.check_summary(s, facts), deadline)
    if summary is not None:
        cache[key] = summary
    return summary, attempts, warnings


def explain(api, pack: EvidencePack, summaries: dict[str, TeamSummary],
            deadline: float | None = None):
    """Stage B: (analysis or None, attempts, warnings)."""
    payload = {
        "fixture": {"league": pack.division_name, "date": pack.match_date,
                    "home": pack.home, "away": pack.away},
        "call": pack.call.model_dump(exclude={"tip_id", "rule_version"}),
        "menu": [m.model_dump() for m in pack.menu],
        "flags": [f.model_dump() for f in pack.flags],
        "summaries": {side: s.model_dump(exclude={"cited_facts"})
                      for side, s in summaries.items()},
        "facts": [_fact(f) for f in pack.facts],
    }
    return _run(api, "analysis", ANALYSIS_PROMPT, payload, MatchAnalysis,
                lambda a: validate.check_analysis(a, pack), deadline)


def analyse(pack: EvidencePack, api, cache: MutableMapping[str, TeamSummary],
            *, deadline: float | None = None) -> Outcome:
    """The whole chain for one pack. Never raises on the model's account:
    every failure is an Outcome with status "fallback" and the reason in
    its attempts. `deadline` is a `time.monotonic()` value."""
    outcome = Outcome("fallback")
    try:
        for side in ("home", "away"):
            summary, attempts, warnings = summarise(api, pack, side, cache, deadline)
            outcome.attempts += attempts
            outcome.warnings += [f"summary_{side}: {w}" for w in warnings]
            if summary is None:
                return outcome
            outcome.summaries[side] = summary
        analysis, attempts, warnings = explain(api, pack, outcome.summaries, deadline)
    except openai.APIError as exc:
        outcome.attempts.append(Attempt("api", 0, [f"{type(exc).__name__}: {exc}"]))
        return outcome
    outcome.attempts += attempts
    outcome.warnings += [f"analysis: {w}" for w in warnings]
    if analysis is not None:
        outcome.status, outcome.analysis = "ok", analysis
    return outcome
