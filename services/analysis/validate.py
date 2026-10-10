"""The validator: nothing the LLM wrote is served until it passes here.

The brief's checks (`docs/tipster-analysis-agent-prompt.md` §7), as they
apply under D1/D2:

1. Schema. Done by the structured-output parse before this module sees
   anything.
2. Every cited id exists.
3. The explanation is about the published call.
4. *(The brief's value-pick check has nothing to check: D1.)*
5. Every number in the prose is in the evidence.
6. No banned phrase.
7. Word counts. These are warnings, never a rejection.

Plus the limits a strict schema cannot carry: at most three strengths and
three weaknesses, and at least one citation.

**The number check.** A number in the prose (`62%`, `0.62`, `2.10`, either
side of `3-1`) must equal a value from the evidence, rounded to the
precision the prose uses: 76.9 may be written 77% or 76.9%, 2.83 may be
written 2.8. Whole numbers without a % match only whole values, so 2.83
goals cannot become "3 goals" and a count cannot be a rounded average.
`0.62` and `62%` are the same number. Numbers spelled out in words are not
checked.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from services.analysis.facts import H2H_MEETINGS, WINDOWS
from services.analysis.schemas import EvidencePack, Fact, MatchAnalysis, TeamSummary

#: Guarantee language (the brief's list, rule 8 of the prompt), and the
#: price and return words the site does not use (D1). Whole words, any case.
BANNED = ("lock", "banker", "sure win", "sure thing", "can't lose", "cannot lose",
          "guaranteed", "nailed on", "dead cert", "odds", "price", "prices",
          "value bet", "good value", "profit", "stake", "staking")

#: Soft bounds, in words: outside them is a warning, not a rejection.
WORDS = {"narrative": (80, 120), "preview": (120, 180), "rationale": (40, 80)}

#: Hard limit on strengths and weaknesses (the brief's schema: max 3).
MAX_POINTS = 3

#: Numbers the prose may use without a fact behind them: the window sizes
#: the labels name, and the goal line of "over 2.5".
STANDING_NUMBERS = (*WINDOWS, H2H_MEETINGS, 2.5)

_NUMBER = re.compile(r"(?<![A-Za-z0-9.])(\d+(?:\.\d+)?)(%?)(?![A-Za-z0-9])")
_BANNED = re.compile(r"\b(" + "|".join(re.escape(p).replace("'", "['’]") for p in BANNED)
                     + r")\b", re.IGNORECASE)


@dataclass(frozen=True)
class Number:
    text: str
    value: float
    decimals: int
    percent: bool


def numbers_in(text: str) -> list[Number]:
    """Every number written in digits, with its precision and any % sign."""
    found = []
    for match in _NUMBER.finditer(text):
        digits, pct = match.groups()
        decimals = len(digits.split(".")[1]) if "." in digits else 0
        found.append(Number(match.group(0), float(digits), decimals, pct == "%"))
    return found


def _values(text: str) -> list[float]:
    return [n.value for n in numbers_in(text)]


def allowed_numbers(facts: list[Fact], pack: EvidencePack | None = None) -> set[float]:
    """Every number the prose may quote: the facts' values (and the dates and
    scores inside text values), plus, for a whole pack, the call and menu."""
    allowed: set[float] = set(STANDING_NUMBERS)
    for fact in facts:
        if isinstance(fact.value, str):
            allowed.update(_values(fact.value))
        else:
            allowed.add(float(fact.value))
    if pack is not None:
        call = pack.call
        allowed.update((call.model_prob, call.floor, call.ceiling))
        for text in (call.label, call.means or ""):
            allowed.update(_values(text))
        for line in pack.menu:
            allowed.add(line.p_model)
            allowed.update(_values(line.label))
    return allowed


def _matches(number: Number, value: float) -> bool:
    for candidate in (value, value * 100, value / 100):
        if number.decimals == 0 and not number.percent and candidate != int(candidate):
            continue
        if abs(round(candidate, number.decimals) - number.value) < 1e-9:
            return True
    return False


def unknown_numbers(text: str, allowed: set[float]) -> list[str]:
    """The numbers in `text` that match nothing in `allowed`."""
    return [n.text for n in numbers_in(text) if not any(_matches(n, v) for v in allowed)]


def _prose_checks(fields: dict[str, str], allowed: set[float]) -> list[str]:
    errors = []
    for name, text in fields.items():
        for token in unknown_numbers(text, allowed):
            errors.append(f"{name}: the number {token} is not in the evidence")
        for phrase in sorted({m.group(0).lower() for m in _BANNED.finditer(text)}):
            errors.append(f"{name}: banned phrase '{phrase}'")
    return errors


def _word_warnings(fields: dict[str, str]) -> list[str]:
    warnings = []
    for name, text in fields.items():
        bounds = WORDS.get(name.split(".")[-1])
        if bounds and not bounds[0] <= len(text.split()) <= bounds[1]:
            warnings.append(f"{name}: {len(text.split())} words, outside {bounds[0]}-{bounds[1]}")
    return warnings


def check_summary(summary: TeamSummary, facts: list[Fact]) -> tuple[list[str], list[str]]:
    """(errors, warnings) for one team's profile, against that team's facts."""
    ids = {f.id for f in facts}
    errors = [f"cited_facts: unknown id {i}" for i in summary.cited_facts if i not in ids]
    if not summary.cited_facts:
        errors.append("cited_facts: empty; every statement must cite a fact")
    for name, points in (("strengths", summary.strengths), ("weaknesses", summary.weaknesses)):
        if len(points) > MAX_POINTS:
            errors.append(f"{name}: {len(points)} items, at most {MAX_POINTS}")
    fields = {"narrative": summary.narrative,
              **{f"strengths[{i}]": s for i, s in enumerate(summary.strengths)},
              **{f"weaknesses[{i}]": w for i, w in enumerate(summary.weaknesses)}}
    errors += _prose_checks(fields, allowed_numbers(facts))
    return errors, _word_warnings({"narrative": summary.narrative})


def check_analysis(analysis: MatchAnalysis, pack: EvidencePack) -> tuple[list[str], list[str]]:
    """(errors, warnings) for the match analysis, against the whole pack."""
    errors = []
    if analysis.call.side != pack.call.side:
        errors.append(f"call.side: {analysis.call.side} is not the published call"
                      f" {pack.call.side}")
    ids = {f.id for f in pack.facts} | {m.id for m in pack.menu}
    for name in ("supporting_facts", "contradicting_facts"):
        errors += [f"call.{name}: unknown id {i}"
                   for i in getattr(analysis.call, name) if i not in ids]
    if not analysis.call.supporting_facts:
        errors.append("call.supporting_facts: empty; the explanation must cite its evidence")
    fields = {"preview": analysis.preview, "call.rationale": analysis.call.rationale,
              "risk_commentary": analysis.risk_commentary}
    errors += _prose_checks(fields, allowed_numbers(pack.facts, pack))
    return errors, _word_warnings(fields)
