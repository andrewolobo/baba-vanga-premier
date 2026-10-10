"""How the written analysis is doing, per prompt version (docs/ANALYSIS_PLAN.md, Phase 5).

    python -m services.analysis metrics
    python -m services.analysis metrics --since 2026-10-01 --price-in 1.25 --price-out 10

**What the brief's evaluation becomes under D1/D2.**

- There is no value pick, so there is no CLV or ROI to compute.
- The call's strike rate is the tip record (`/tips/record`), measured
  there and not restated here.

**What is measured here is the writing**, from `match_analyses` alone:

- how often the model's first answer passes;
- which checks reject it;
- how many requests a fixture takes;
- how often a fixture ends with the numbers-only card;
- what it costs.

Prices are per million tokens and come from the command line, because the
deployment's price is the owner's contract, not a constant. Without prices,
cost is reported in tokens only.
"""

from __future__ import annotations

from collections import Counter, defaultdict

from engine import db
from services.analysis.analyse import OUT_OF_TIME

#: A validator error to the rule it broke, by the wording `validate.py` and
#: `analyse.py` use. First match wins; anything else is counted as "other",
#: so a new kind of error shows up instead of vanishing.
RULES = (
    ("unknown id", "cited id does not exist"),
    ("is not in the evidence", "number not in the evidence"),
    ("banned phrase", "banned phrase"),
    ("is not the published call", "explained another call"),
    ("empty;", "nothing cited"),
    ("items, at most", "too many strengths or weaknesses"),
    ("schema:", "no structured answer"),
    (OUT_OF_TIME, "time budget"),
    ("no facts about this side", "no facts about a side"),
)


def rule_of(stage: str, error: str) -> str:
    if stage == "api":
        return "API error"
    return next((rule for marker, rule in RULES if marker in error), "other")


def compute(conn: db.Connection, since: str | None = None, until: str | None = None,
            price_in: float | None = None, price_out: float | None = None) -> list[dict]:
    """One summary per (prompt version, deployment), newest prompt first.
    `since`/`until` are dates, inclusive, on the row's creation (UTC)."""
    rows = conn.execute(
        "SELECT fixture_id, prompt_version, llm_model, status, attempts, warnings,"
        " input_tokens, output_tokens FROM match_analyses"
        " WHERE created_at >= %s AND created_at < %s ORDER BY analysis_id",
        (since or "0000-01-01", (until or "9999-12-30") + " 99")).fetchall()
    groups: dict[tuple[str, str], list] = defaultdict(list)
    for row in rows:
        groups[(row["prompt_version"], row["llm_model"])].append(row)

    out = []
    for (version, model), group in sorted(groups.items(), reverse=True):
        statuses = defaultdict(set)
        for row in group:
            statuses[row["fixture_id"]].add(row["status"])
        fixtures = len(statuses)
        ended_ok = sum("ok" in s for s in statuses.values())
        superseded = sum(s == {"ok", "fallback"} for s in statuses.values())
        requests = [a for row in group for a in row["attempts"] if a["attempt"] > 0]
        rejections = Counter(rule_of(a["stage"], e) for row in group for a in row["attempts"]
                             for e in a["errors"])
        first_pass = sum(row["status"] == "ok" and not any(a["errors"] for a in row["attempts"])
                         for row in group)
        tokens_in = sum(row["input_tokens"] for row in group)
        tokens_out = sum(row["output_tokens"] for row in group)
        summary = {
            "prompt_version": version,
            "llm_model": model,
            "fixtures": fixtures,
            "ended_ok": ended_ok,
            "ended_fallback": fixtures - ended_ok,
            "fallback_rate": round((fixtures - ended_ok) / fixtures, 4),
            "fallbacks_superseded": superseded,
            "first_pass_ok": first_pass,
            "first_pass_rate": round(first_pass / len(group), 4),
            "requests": len(requests),
            "requests_per_analysis": round(len(requests) / len(group), 2),
            "retries": sum(a["attempt"] > 1 for a in requests),
            "rejections": dict(rejections.most_common()),
            "warnings": dict(Counter(w.split(":")[0] for row in group for w in row["warnings"])
                             .most_common()),
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "tokens_per_fixture": [round(tokens_in / fixtures), round(tokens_out / fixtures)],
        }
        if price_in is not None and price_out is not None:
            cost = (tokens_in * price_in + tokens_out * price_out) / 1e6
            summary["cost"] = round(cost, 4)
            summary["cost_per_fixture"] = round(cost / fixtures, 5)
        out.append(summary)
    return out


def describe(summaries: list[dict]) -> str:
    if not summaries:
        return "no analyses in the window"
    lines = []
    for s in summaries:
        lines += [
            f"{s['prompt_version']} on {s['llm_model']}: {s['fixtures']} fixture(s), "
            f"{s['ended_ok']} ok, {s['ended_fallback']} fallback "
            f"({100 * s['fallback_rate']:.1f}%), {s['fallbacks_superseded']} fallback(s) re-run to ok",
            f"  first answer passed in {100 * s['first_pass_rate']:.1f}% of analyses; "
            f"{s['requests']} request(s), {s['requests_per_analysis']} per analysis, "
            f"{s['retries']} retr{'y' if s['retries'] == 1 else 'ies'}",
            "  rejections: " + (", ".join(f"{k} {v}" for k, v in s["rejections"].items()) or "none"),
            "  warnings: " + (", ".join(f"{k} {v}" for k, v in s["warnings"].items()) or "none"),
            f"  tokens: {s['tokens_in']} in / {s['tokens_out']} out; per fixture "
            f"{s['tokens_per_fixture'][0]} / {s['tokens_per_fixture'][1]}"
            + (f"; cost {s['cost']:.4f}, {s['cost_per_fixture']:.5f} per fixture"
               if "cost" in s else ""),
        ]
    return "\n".join(lines)
