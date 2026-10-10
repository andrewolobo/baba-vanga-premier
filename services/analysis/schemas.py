"""The evidence pack's data contracts (docs/ANALYSIS_PLAN.md §4).

Pydantic rather than the dataclasses `engine/` uses, because the pack is
serialised twice -- into the prompt and into a JSONB column -- and the LLM's
own output contracts, which arrive in Phase 2 once the provider's strict
schema rules are confirmed, need a JSON schema generated from the type.

Probabilities and percentages are carried as **percent** (78.1, not 0.781):
it is how the page prints them, so a figure the LLM quotes can be checked
against the pack without a unit conversion it might get wrong.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Fact(_Frozen):
    """One value, with a stable id the prose must cite (`HOME_PPG_L5`)."""

    id: str
    label: str
    value: str | int | float
    #: "%", "games", "pts/game", "goals/game", or None for text. Lets the
    #: validator read 62 as 62% and never as 0.62.
    unit: str | None = None
    scope: Literal["home_team", "away_team", "h2h", "league"]


class MenuLine(_Frozen):
    """One market the rule weighed, with the model's probability for it.

    `role` is the rule's own structure (`engine.eval.b21.recommend`): the
    favourite's outright is taken at `floor` or above; the four fallbacks are
    eligible at `ceiling` or below; the draw and the underdog's outright are
    never on the menu. `eligible` is computed here, not by the LLM.
    """

    id: str
    side: str
    label: str
    p_model: float
    role: Literal["outright", "fallback", "off_menu"]
    eligible: bool
    is_call: bool


class Call(_Frozen):
    """The published tip: what the analysis explains and may not change."""

    tip_id: int
    side: str
    label: str
    #: What has to happen for it to come in, for the codes that need it.
    means: str | None
    model_prob: float
    floor: float
    ceiling: float
    rule_version: str


class Flag(_Frozen):
    """A data caveat on one side (D4). Every flag is a fact, not a forecast."""

    code: Literal["small_sample", "new_to_division", "results_gap"]
    side: Literal["home", "away"]


class EvidencePack(_Frozen):
    """Everything the analysis may say about one fixture, as code computed it.

    `match_date` and `kickoff_time` are the fixture's own text (UK time, as
    published) rather than a datetime: converting them would be the one
    number in the pack this module made up. `omitted` names every fact left
    out and why -- the brief's "skip it gracefully and log it".
    """

    fixture_id: int
    division: str
    division_name: str
    match_date: str
    kickoff_time: str | None
    home: str
    away: str
    home_team_id: int
    away_team_id: int
    call: Call
    menu: list[MenuLine]
    facts: list[Fact]
    flags: list[Flag]
    omitted: list[str]
    model_version: str
    data_as_of: str


# --- what the LLM returns (structured output, strict) ----------------------- #
#
# Every field required and no defaults: the provider's strict JSON-schema
# mode refuses anything else. Limits the schema cannot carry -- three
# strengths at most, word counts -- are checked by `validate.py`. Neither
# model repeats what the pack already knows (the team, the fixture), so
# there is nothing for it to get wrong there.


class TeamSummary(_Frozen):
    narrative: str
    strengths: list[str]
    weaknesses: list[str]
    trend: Literal["improving", "stable", "declining"]
    cited_facts: list[str]


# No docstrings on the output models: a docstring becomes the schema's
# `description` and is sent to the model as part of its instructions.


class Pick(_Frozen):
    # `side` is echoed back and must equal the call's: a cheap check that the
    # prose is about the published call and not another.
    side: str
    rationale: str
    supporting_facts: list[str]
    contradicting_facts: list[str]


class MatchAnalysis(_Frozen):
    preview: str
    call: Pick
    risk_commentary: str
