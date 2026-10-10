"""The analysis as a scheduled job: which calls, in what order, and where it lands.

One trigger (D6): **a tip was published**. The cycle's `analysis` step runs
`run()` over `pending()` right after the day's calls are out, and never on a
page load.

**Stored once, append-only.** Writes go into `match_analyses` (migration
004), whose unique indexes allow one `ok` and one `fallback` per fixture
and prompt version. A re-run can turn a fallback into an ok; nothing can
replace an ok. Team summaries go into `team_summaries` as the Stage A
cache, so a club's profile is written once per state of its record.

**Bounded in time.** A Saturday has about 46 calls at about 25 s each. Run
one after another that is close to the cycle unit's 30-minute timeout,
before counting the steps ahead of this one. So the fixtures run
`WORKERS` at a time against one shared deadline. A fixture the deadline
cuts off is stored as a fallback with the reason in its attempts; the
page then shows the numbers-only card rather than nothing.

The database is touched only from the calling thread. The workers make
network requests and nothing else.
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from psycopg.types.json import Jsonb

from engine import db
from engine.serve import tips
from services.analysis.analyse import (
    ANALYSIS_PROMPT, SUMMARY_PROMPT, Outcome, analyse, dossier, dossier_hash,
)
from services.analysis.pack import build_pack
from services.analysis.schemas import EvidencePack, TeamSummary

#: Fixtures in flight at once. Four keeps a full Saturday to a few minutes
#: without leaning on the deployment's rate limit; a 429 is retried by the SDK.
WORKERS = 4
#: The step's whole time budget, in seconds. With the other steps it keeps the
#: cycle well inside `TimeoutStartSec=30min`, and it finishes the cycle before
#: the 07:00 results run waits on the same lock.
BUDGET_SECONDS = 15 * 60

#: Today's published calls under the current rule that have no analysis under
#: the current prompt. Calls publish on matchday only (`tips.PUBLISH_WITHIN_DAYS`),
#: so this never reaches a match already played.
PENDING = """
    SELECT DISTINCT ON (t.fixture_id) t.fixture_id
    FROM tips t
    JOIN fixtures f ON f.fixture_id = t.fixture_id
    WHERE f.match_date >= %s AND t.rule_version = %s
      AND NOT EXISTS (SELECT 1 FROM match_analyses a
                      WHERE a.fixture_id = t.fixture_id AND a.prompt_version = %s)
    ORDER BY t.fixture_id, t.tip_id DESC
"""


def pending(conn: db.Connection, today: str | None = None) -> list[int]:
    return [r["fixture_id"] for r in conn.execute(
        PENDING, (today or db.today(), tips.RULE_VERSION, ANALYSIS_PROMPT))]


def rerunnable(conn: db.Connection, fixture_id: int) -> str | None:
    """Why `fixture_id` cannot be re-run, or None when it can: it must have a
    fallback under the current prompt, no ok, and not have been played."""
    row = conn.execute(
        "SELECT f.match_date,"
        " bool_or(a.status = 'ok') AS has_ok, bool_or(a.status = 'fallback') AS has_fallback"
        " FROM fixtures f LEFT JOIN match_analyses a"
        "   ON a.fixture_id = f.fixture_id AND a.prompt_version = %s"
        " WHERE f.fixture_id = %s GROUP BY f.match_date",
        (ANALYSIS_PROMPT, fixture_id)).fetchone()
    if row is None:
        return f"fixture {fixture_id} does not exist"
    if row["has_ok"]:
        return f"fixture {fixture_id} already has an analysis; an ok is never replaced"
    if not row["has_fallback"]:
        return f"fixture {fixture_id} has no fallback to re-run; the cycle writes first analyses"
    if row["match_date"] < db.today():
        return f"fixture {fixture_id} was played on {row['match_date']}"
    return None


def load_cache(conn: db.Connection, pack: EvidencePack) -> dict[str, TeamSummary]:
    """The stored profiles for this pack's two dossiers, keyed as Stage A
    looks them up."""
    keys = [dossier_hash(name, dossier(pack, side))
            for side, name in (("home", pack.home), ("away", pack.away))]
    return {r["dossier_hash"]: TeamSummary.model_validate(r["summary"]) for r in conn.execute(
        "SELECT dossier_hash, summary FROM team_summaries"
        " WHERE dossier_hash = ANY(%s) AND prompt_version = %s", (keys, SUMMARY_PROMPT))}


def save(conn: db.Connection, pack: EvidencePack, outcome: Outcome, *, llm_model: str) -> bool:
    """Store the outcome. True when a row landed, False when the unique
    indexes dropped it (an ok already there, or a second fallback)."""
    for side, team_id, name in (("home", pack.home_team_id, pack.home),
                                ("away", pack.away_team_id, pack.away)):
        summary = outcome.summaries.get(side)
        asked = [a for a in outcome.attempts if a.stage == f"summary_{side}"]
        if summary is None or not asked:     # failed, or came from the cache
            continue
        conn.execute(
            "INSERT INTO team_summaries (team_id, dossier_hash, prompt_version, summary,"
            " llm_model, input_tokens, output_tokens) VALUES (%s, %s, %s, %s, %s, %s, %s)"
            " ON CONFLICT DO NOTHING",
            (team_id, dossier_hash(name, dossier(pack, side)), SUMMARY_PROMPT,
             Jsonb(summary.model_dump()), llm_model,
             sum(a.input_tokens for a in asked), sum(a.output_tokens for a in asked)))
    written = conn.execute(
        "INSERT INTO match_analyses (fixture_id, tip_id, prompt_version, llm_model,"
        " model_version, status, evidence_pack, analysis, summaries, attempts, warnings,"
        " input_tokens, output_tokens)"
        " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
        " ON CONFLICT DO NOTHING",
        (pack.fixture_id, pack.call.tip_id, ANALYSIS_PROMPT, llm_model, pack.model_version,
         outcome.status, Jsonb(pack.model_dump()),
         Jsonb(outcome.analysis.model_dump()) if outcome.analysis else None,
         Jsonb({s: v.model_dump() for s, v in outcome.summaries.items()})
         if outcome.status == "ok" else None,
         Jsonb([vars(a) for a in outcome.attempts]), Jsonb(outcome.warnings),
         outcome.input_tokens, outcome.output_tokens)).rowcount
    conn.commit()
    return written == 1


@dataclass
class RunReport:
    outcomes: dict[int, Outcome] = field(default_factory=dict)
    #: Fixtures no pack could be built for, with the reason (no call, an
    #: older rule, or a menu that does not reproduce the call).
    refused: dict[int, str] = field(default_factory=dict)
    written: int = 0

    def count(self, status: str) -> int:
        return sum(o.status == status for o in self.outcomes.values())

    @property
    def tokens(self) -> tuple[int, int]:
        return (sum(o.input_tokens for o in self.outcomes.values()),
                sum(o.output_tokens for o in self.outcomes.values()))


def run(conn: db.Connection, fixture_ids: list[int], api, *, llm_model: str,
        workers: int = WORKERS, budget: float = BUDGET_SECONDS,
        dry_run: bool = False) -> RunReport:
    """Pack, analyse and store each fixture. `dry_run` asks the model and
    stores nothing."""
    report = RunReport()
    packs: dict[int, EvidencePack] = {}
    for fixture_id in fixture_ids:
        try:
            packs[fixture_id] = build_pack(conn, fixture_id)
        except (LookupError, ValueError) as exc:
            report.refused[fixture_id] = str(exc)
    caches = {fixture_id: load_cache(conn, pack) for fixture_id, pack in packs.items()}
    deadline = time.monotonic() + budget
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {fixture_id: pool.submit(analyse, pack, api, caches[fixture_id],
                                           deadline=deadline)
                   for fixture_id, pack in packs.items()}
    report.outcomes = {fixture_id: future.result() for fixture_id, future in futures.items()}
    if not dry_run:
        report.written = sum(save(conn, packs[fixture_id], report.outcomes[fixture_id],
                                  llm_model=llm_model)
                             for fixture_id in sorted(report.outcomes))
    return report
