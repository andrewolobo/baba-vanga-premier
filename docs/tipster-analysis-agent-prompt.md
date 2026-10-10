# Task: Build the LLM Match-Analysis Component

You are working in an existing tipster/punter web application. The frontend is **Svelte**, the backend is **Python**. The database already holds fixtures, odds history, match results and scorelines, head-to-head records, and (possibly) league standings. There is an existing statistical prediction model (Poisson-based) that produces outcome probabilities.

Your job is to add an **analytical component** that:
1. Builds a factual dossier for each team and fixture.
2. Uses an LLM (Claude via the Anthropic Python SDK) to write team summaries and a match analysis.
3. Produces a structured recommendation covering the **most likely outcome** and, separately, the **best-value selection**.
4. Validates, stores, serves and later evaluates every recommendation.

---

## Non-negotiable design principle

**Python computes every number. The LLM only interprets and explains.**

- The LLM must never generate, estimate or adjust a probability, odds value, edge or EV.
- The LLM may only recommend selections from a pre-computed candidate list.
- Every claim in LLM prose must cite a fact ID that exists in the input.
- `confidence_tier` is computed in code. The LLM explains it but does not set it.

If you find yourself writing code where the LLM's output decides a number, stop and redesign.

---

## Phase 0: Discover before you build (do this first, then stop)

Explore the repo and report back **before writing any code**:

- Backend framework (FastAPI / Flask / Django?), project layout, how config and secrets are loaded.
- DB engine and ORM / query layer. List the tables or models for fixtures, odds, results, teams, H2H and standings, with their key columns.
- Where the existing prediction model lives, its entry point, its inputs, and the shape of its output (which markets, which probabilities).
- Any existing background job / scheduler mechanism (Celery, APScheduler, cron, none).
- Svelte structure: SvelteKit or plain Svelte, how pages fetch data, where a fixture detail view lives.
- Existing test setup.

Then propose a concrete file plan that maps the architecture below onto *this* codebase, using its conventions rather than the generic layout. List any gaps (e.g. "no standings table", "odds stored only as closing price") and how you'd handle them. **Wait for my approval before Phase 1.**

---

## Architecture

```
Fixtures + odds + results DB
        │
 1. Fact Builder (deterministic)      → TeamDossier ×2, H2HDossier
 2. Probability adapter (existing)    → p_model per market/selection
 3. Market layer                      → p_market (de-vigged), edge, EV, candidates
 4. Evidence Pack assembler           → EvidencePack (all facts carry IDs)
        │
 5. LLM Stage A: TeamSummary          (per team, cached)
 6. LLM Stage B: MatchAnalysis        (per fixture, structured output)
        │
 7. Validator → retry (max 2) → fallback "numbers-only" card
 8. Persist → API → Svelte
 9. Settlement + evaluation
```

Suggested module layout (adapt to repo conventions):

```
analysis/
  facts.py          # Fact Builder
  model_adapter.py  # thin wrapper over the existing model
  market.py         # de-vig, edge, EV, candidate rules, confidence tier
  pack.py           # EvidencePack assembly
  schemas.py        # all Pydantic models below
  llm/
    client.py       # Anthropic client, structured output, retries, token/cost logging
    prompts/
      team_summary_v1.md
      match_analysis_v1.md
    validate.py
  jobs.py           # triggers
  eval.py           # settlement + metrics
  config.py         # thresholds, model names, versions (env-overridable)
```

---

## 1. Fact Builder (`facts.py`)

Produce `Fact` objects with stable, human-readable IDs. Use fixed windows so teams are comparable.

Per team (scope `home_team` / `away_team`), for windows L5, L10 and season:
- Form string (e.g. `WWDLW`), points per game, goals for/against per game.
- Home/away split, applied to the venue of this fixture.
- Clean-sheet %, BTTS %, Over 2.5 %.
- Record as market favourite vs underdog (from historical odds).
- League position, points, gap to the position above/below, games played. Skip if no standings data, and log it.

H2H (scope `h2h`): last N meetings (configurable, default 6) with date, venue and score, plus aggregate W/D/L and average goals.

League context (scope `league`): league average goals, home win rate.

**ID convention:** `{SCOPE}_{METRIC}_{WINDOW}`, e.g. `HOME_PPG_L5`, `AWAY_CS_PCT_SEASON`, `H2H_MATCH_3`. IDs must be deterministic for the same input.

Return **values only**, never prose interpretations.

---

## 2–3. Probability adapter and market layer (`model_adapter.py`, `market.py`)

- Wrap the existing model. Do not modify its internals.
- For every available market/selection with odds, compute:
  - `p_market`: proportional de-vig, `p_i = (1/o_i) / Σ(1/o_j)` within the market. Keep the de-vig method pluggable so Shin's method can be added later.
  - `edge = p_model − p_market`
  - `ev = p_model × odds − 1`
- **Candidate rule** (all thresholds in `config.py`): `is_candidate = edge ≥ MIN_EDGE (0.03) and ev ≥ MIN_EV (0.05) and sample_size ≥ MIN_SAMPLE (8)`.
- **Most likely** = argmax of `p_model` within the primary market (1X2 by default). Computed in code.
- **Confidence tier**: a deterministic function of edge size, sample size, and whether H2H direction agrees with the model. Document the formula in a docstring and make it configurable.
- **Risk flags**, also computed in code where possible:
  - `small_sample`
  - `h2h_conflicts_form`
  - `odds_moved_against` (if opening vs current odds are available)
  - `dead_rubber` (if standings make the match meaningless)
  - `model_market_disagree_large` (|edge| > 0.15)

---

## Data contracts (`schemas.py`)

~~~python
class Fact(BaseModel):
    id: str
    label: str
    value: str | float | int
    scope: Literal["home_team", "away_team", "h2h", "league", "market"]

class MarketLine(BaseModel):
    market: Literal["1X2", "OU_2.5", "BTTS", "AH"]   # extend to what the DB has
    selection: str
    odds: float
    p_market: float
    p_model: float
    edge: float
    ev: float
    is_candidate: bool

class EvidencePack(BaseModel):
    fixture_id: str
    kickoff: datetime
    home: str
    away: str
    facts: list[Fact]
    markets: list[MarketLine]
    most_likely: MarketLine          # computed in code
    confidence_tier: Literal["low", "medium", "high"]
    risk_flags: list[str]
    model_version: str
    data_as_of: datetime

class TeamSummary(BaseModel):
    team: str
    narrative: str                   # 80–120 words
    strengths: list[str]             # max 3
    weaknesses: list[str]            # max 3
    trend: Literal["improving", "stable", "declining"]
    cited_facts: list[str]

class Pick(BaseModel):
    market: str
    selection: str
    rationale: str                   # 40–80 words
    supporting_facts: list[str]
    contradicting_facts: list[str]

class MatchAnalysis(BaseModel):
    fixture_id: str
    preview: str                     # 120–180 words
    most_likely: Pick                # must match EvidencePack.most_likely
    value_pick: Pick | None          # must be an is_candidate line, or None
    risk_commentary: str             # explains code-computed flags + tier
~~~

Persisted record (DB table, e.g. `match_analyses`): `fixture_id`, `evidence_pack` (JSONB), `analysis` (JSONB, nullable), `status` (`ok` | `fallback` | `failed`), `model_version`, `prompt_version`, `llm_model`, `odds_at_publish`, `closing_odds` (filled later), `input_tokens`, `output_tokens`, `created_at`, `settled_at`, `outcome`. Also `team_summaries` keyed by `(team_id, dossier_hash, prompt_version)`.

---

## 5–6. LLM client and prompts (`llm/`)

**Client**
- Use the official `anthropic` Python SDK. Read the API key from env/existing secrets handling and never hard-code it.
- Enforce structured output by defining a tool whose `input_schema` is the Pydantic model's JSON schema, and forcing that tool via `tool_choice`. Parse the tool input back into the Pydantic model.
- Model names come from config (`LLM_MODEL_SUMMARY`, `LLM_MODEL_ANALYSIS`). Use a fast, cheap model for summaries and a stronger one for match analysis. Check current model IDs in the Anthropic docs rather than guessing.
- Use temperature 0 or low. Set timeouts, retry with backoff on 429/5xx, and log tokens per call.
- Put the static system prompt first so prompt caching can apply.

**Stage A: Team summary**
- Input: one team's facts (as JSON) plus team name.
- Cache by `sha256(sorted facts JSON) + prompt_version`. Only call the LLM on a cache miss.

**Stage B: Match analysis**
- Input: both TeamSummaries, the H2H and league facts, the full market table (with `is_candidate`), `most_likely`, `confidence_tier`, and `risk_flags`.

Create the two prompt files with the content below. Prompts are versioned files, and the version string is stored with every output.

### `prompts/team_summary_v1.md`

~~~
You are a football analyst writing a concise team profile for a betting-tips website.

You will receive a JSON list of facts about one team. Each fact has an id, label and value.

Rules:
- Use ONLY the facts provided. Do not use outside knowledge about the team, players, managers or news.
- Every statement must be supported by at least one fact. List every fact id you relied on in cited_facts.
- You may quote numbers only if they appear exactly in the facts. Do not calculate new statistics, percentages or probabilities.
- Describe the trend as "improving", "stable" or "declining" by comparing short windows (L5) against longer ones (L10/season).
- Neutral, analytical tone. No hype, no slang, no betting advice in this step.
- narrative: 80–120 words. strengths and weaknesses: at most 3 each, short phrases.

Return your answer by calling the provided tool.
~~~

### `prompts/match_analysis_v1.md`

~~~
You are a football analyst writing a match preview and recommendation for a betting-tips website.

You will receive:
- Two team summaries
- Head-to-head and league facts (each with an id)
- A market table: every selection's odds, model probability (p_model), market probability (p_market), edge, EV and an is_candidate flag
- most_likely: the selection the statistical model rates most probable
- confidence_tier and risk_flags, computed by the system

Your job is to EXPLAIN the numbers, not to produce new ones.

Rules:
1. Use only the information provided. No outside knowledge, injuries, news or player names unless they appear in the facts.
2. Never state a probability, percentage, odds value, edge or EV that is not in the input. Never compute new ones.
3. most_likely: you MUST use the selection given in most_likely. Explain why the data supports it.
4. value_pick: you may only choose a selection where is_candidate is true. If none exist, or the evidence clearly undermines every candidate, set value_pick to null and explain why in risk_commentary.
5. For each pick, list supporting_facts AND contradicting_facts (fact ids). Always look for evidence against your pick. Leave contradicting_facts empty only if there genuinely is none.
6. Make clear that "most likely" and "best value" are different questions: a likely outcome can be poor value at short odds.
7. risk_commentary: explain the confidence_tier and each risk flag in plain language. Do not change the tier.
8. Never use guarantee language ("lock", "banker", "sure win", "can't lose"). This is analysis, not a promise.
9. preview: 120–180 words. Each rationale: 40–80 words.

Return your answer by calling the provided tool.
~~~

---

## 7. Validator (`llm/validate.py`)

Reject the output and retry (max 2 retries, feeding the validation errors back into the next attempt) if any of these fail:

1. Schema validation (Pydantic).
2. Every cited fact ID (in `cited_facts`, `supporting_facts`, `contradicting_facts`) exists in the pack.
3. `most_likely.market/selection` equals `EvidencePack.most_likely`.
4. `value_pick` is either `None` or matches a `MarketLine` with `is_candidate=True`.
5. **Number check:** extract all numbers from the prose fields (regex covering decimals, percentages and odds formats). Each must match a value in the pack within a small tolerance (handle `0.62` ↔ `62%`). Whitelist trivial numbers (match-count words, years in dates present in facts).
6. Banned-phrase check (the guarantee language list, configurable).
7. Word-count bounds (soft: log warnings, don't reject).

After the final failure, store `status="fallback"` and serve a numbers-only card built from the EvidencePack. Never serve unvalidated LLM text.

---

## 8. Jobs and API

**Triggers** (`jobs.py`, using whatever scheduler the repo already has, or a minimal one if none):
- **Fixture published / due within N hours:** build the pack, run Stage A (cache-aware), Stage B, validate, persist.
- **Odds move:** if any primary-market price moves more than `ODDS_MOVE_THRESHOLD` (default 5%) since `odds_at_publish`, rebuild the pack and rerun Stage B only.
- **Result settled:** run Stage A for both teams (the dossier hash changes) and settle stored analyses.
- **Never** call the LLM on a user page load.

**API** (match existing router conventions):
- `GET /fixtures/{id}/analysis` returns `{ analysis, evidence_pack, status, prompt_version, generated_at }`.
- `GET /teams/{id}/summary`
- `POST /admin/analysis/{fixture_id}/regenerate` (admin-auth only)
- `GET /admin/analysis/metrics?prompt_version=&from=&to=`

---

## Svelte UI

Add an analysis panel to the existing fixture detail view:
- Preview text.
- Two cards: **Most likely** and **Best value**. The value card shows a "No value pick" state when `value_pick` is null.
- For each pick, show odds, p_model, p_market and edge from the **evidence pack** (not from LLM text), and the confidence tier and risk flags as badges.
- A "Why?" toggle that expands the supporting and contradicting facts, resolved from IDs to label/value.
- A fallback rendering for `status="fallback"`.
- A **fixed, templated footer** (hard-coded in the component, not generated): "Analysis, not a guarantee. Bet responsibly. 18+." Adjust the wording to the site's jurisdiction.
- Match the existing styling and component conventions.

---

## 9. Evaluation (`eval.py`)

After settlement, compute per `prompt_version` and `model_version`:
- `value_pick`: count, hit rate, flat-stake ROI, average edge at publish.
- **CLV**: `odds_at_publish / closing_odds − 1` averaged over value picks. This is the key early signal.
- `most_likely`: hit rate, Brier score, log loss.
- Fallback / validator-rejection rate, and average tokens and cost per fixture.

Expose these via the admin metrics endpoint. A simple admin table in Svelte is enough.

---

## Testing requirements

- **Unit tests:**
  - de-vig sums to 1
  - edge/EV arithmetic
  - candidate rules at threshold boundaries
  - confidence tier function
  - fact ID determinism
  - every validator rule, including a positive and negative case each
  - number-extraction edge cases (`62%`, `0.62`, `2.10`, `3-1` scorelines)
- **LLM tests:** mock the Anthropic client. Include fixtures for a valid response, a hallucinated fact ID, an invented percentage, and a non-candidate value pick, and assert retry then fallback behaviour.
- **One opt-in integration test** (skipped unless `RUN_LLM_TESTS=1`) that runs a real fixture end to end.
- **No real API calls** in the default test run.

---

## Working rules for you (the agent)

- Complete Phase 0 and wait for approval. After that, work in this order, pausing for review after each step:
  1. schemas + facts + market (with tests)
  2. LLM client + prompts + validator (with mocked tests)
  3. persistence + jobs + API
  4. Svelte UI
  5. eval
- Follow existing code style, linting, typing and migration tooling. Add DB changes as proper migrations.
- Do not modify the existing prediction model's logic.
- All thresholds, model names and versions live in config, not in code.
- If the data needed for a fact or market doesn't exist, skip it gracefully and log it rather than inventing a substitute.
- If any instruction here conflicts with what you find in the codebase, flag it and propose an alternative rather than guessing.
