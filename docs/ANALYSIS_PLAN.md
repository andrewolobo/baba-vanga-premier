# ANALYSIS_PLAN — written match analysis from an LLM

**Status (2026-10-10): Phase 0 is done and nothing is built.** The owner
approved every recommendation in §2. The same day the owner added two
things:

- **The provider is Azure (Microsoft) Foundry.** The model is OpenAI's
  `gpt-6-sol` / `gpt-6.1-sol`, not Claude. See D7.
- **The analysis is for signed-in readers only.** See D10.

The implementation is phased in §5. **All five phases are built
(2026-10-10, uncommitted).** What remains is the owner's: commit, deploy,
the credentials file and the drop-in on the VM (`DEPLOY.md` §5.3, the
analysis block), then a few matchdays read before the feature is
announced.

The brief is `docs/tipster-analysis-agent-prompt.md`. Its first principle
stands and suits this repo: **Python computes every number; the LLM only
explains.**

---

## 1. What the repo is

| brief asks | found |
| --- | --- |
| backend | **FastAPI** in one module, `api/main.py`, plus `api/auth.py`, `api/betpawa.py` and `api/teams.py`. It reads what the cycle wrote. Its only writes are three account routes, and `tests/test_api.py` pins that list |
| config and secrets | `engine/config.py` `setting(name)`: the environment first, then the gitignored `.env`, then the default. On the VM, secrets go in systemd drop-ins |
| DB / query layer | **PostgreSQL 16**, psycopg 3 and raw SQL, with **no ORM**. Migrations are forward-only files, `db/migrations/NNN_*.sql`. Timestamps are stored as UTC text |
| fixtures | `fixtures` holds ids, division, date and kickoff, team ids, and the `avg_*`/`max_*` 1X2, O/U 2.5 and AH prices |
| odds | **one pre-close snapshot per fixture, overwritten on every sync.** There is no history. `matches` carries pre-close and closing prices for the 2010-11 to 2025-26 corpus |
| results | history is in `matches` (40,922 rows, last one 2026-05-24). **This season's results exist only as `tips.fthg/ftag`**, the score each call was settled from |
| teams | `teams` and `team_aliases`. Display names and venues come from `api/teams.py` and `reference/` |
| H2H | there is no table. `api/main.py` `_meetings()` merges `matches` with the settled calls |
| standings | **none**, and there never have been |
| prediction model | ridge Poisson (`engine/models/poisson.py`), frozen weekly. Its output is `(lam_h, lam_a)`. `predictions` stores those plus the 1X2 and O/U 2.5 probabilities |
| what is published | **`tips`: one call per fixture per rule** (`UNIQUE (fixture_id, rule_version)`), under rule `confidence-v3`, on matchday only |
| scheduler | **systemd timers.** `bvp-cycle` runs daily at 06:00 UTC: sync → calendar → serve → tips → betpawa → results → grade. Exit codes are 0, 2 and 1. Optional steps sit behind `BVP_*=1` |
| frontend | **SvelteKit 2 and Svelte 5, server-rendered.** The fixture page is `routes/match/[match]/+page.svelte` and reads `GET /fixture/{id}` |
| tests | `pytest`, with a fresh Postgres clone of a migrated template per test, on synthetic data only. `npm test` runs on the pure `$lib/*.js` helpers. Click-throughs are run by hand with Playwright |
| LLM | none in the repo |

---

## 2. Decisions (all owner-approved 2026-10-10)

- **D1. No "best value" pick.** There is no edge, EV or odds in the pack or
  on the page. The book stays off, and no page shows a price
  (`CALIBRATION.md` §5, `PRODUCT.md` §6 D9).
- **D2. The analysis explains the published call.** It does not use a 1X2
  argmax. The pack carries the tip (`side`, `model_prob`, floor, ceiling)
  and the menu the rule chose from: H/D/A/1X/X2/12/+1.5, with model
  probabilities computed from the stored lambdas. That is the same set the
  call drawer shows (B22). An analysis exists only for a fixture with a
  published tip.
- **D3. No confidence tier.** The page already shows the claim and the
  record shows the strike rate.
- **D4. Flags are factual data caveats only:** `small_sample`,
  `new_to_division` and `results_gap`. `odds_moved_against` and
  `dead_rubber` cannot be built: there is no odds history and no
  standings.
- **D5. No admin API.** The analysis is generated once, in the cycle run
  that publishes the tip, and stored append-only. A `fallback` row may be
  superseded once by an `ok` row from a manual re-run. An `ok` row is never
  replaced. Regenerate and metrics are CLI commands.
- **D6. One trigger: tip published.** There is no odds-move trigger and no
  eager re-summary at settlement.
- **D7. Structured output against our Pydantic schema, then our own
  validator.** *The provider changed on approval:* Azure Foundry, using
  the settings `AZURE_FOUNDRY_URI`, `AZURE_FOUNDRY_KEY` and `AZURE_MODEL`
  (the owner's names, kept as they are).
  - The URI is a Foundry project endpoint on `…services.ai.azure.com`
    ending in `/openai/v1/responses`. That is the OpenAI-compatible v1
    route, so the client is the official `openai` Python SDK with
    `base_url` set to the URI minus `/responses`. Structured output goes
    through the Responses API's strict JSON-schema format.
  - Microsoft documents the client route. I found no Foundry example of
    structured outputs on it, so **Phase 2 opens with one probe call** to
    confirm it on the deployment. That call is the first spend.
  - The strict schema needs every field required, with optional fields
    expressed as nullable. Item and word limits are enforced by our own
    validator either way.
  - The same deployment serves both the team summaries and the match
    analysis, unless the measured cost argues for two.
- **D8. Not in the server HTML (follows from D10).** No crawler sees the
  text, so there is no SEO effect and no exposure to the scaled-content
  policy.
- **D9. One fixed line in the panel:** *"Written by an AI from the figures
  on this page. Analysis, not a guarantee."* The site footer already
  carries 18+ and the gambling-responsibly line.
- **D10. Signed-in readers only** (owner, 2026-10-10). This follows the
  `/betpawa/links` precedent:
  - The analysis has **its own route, `GET /fixture/{id}/analysis`, behind
    `require_user`**. It answers 401 when signed out and 404 before an
    analysis exists.
  - The browser fetches it after the page loads. The service worker
    already leaves unlisted `/api` paths uncached.
  - `/fixture/{id}` and the server HTML are unchanged, so no analysis text
    reaches a signed-out reader or a cache.
  - Signed out, the panel shows a sign-in card in its place, using the
    betPawa button's signed-out pattern.
  - *Assumption:* sign-in is enough and a phone number is not required.
    Say if it should be.

Also taken:

- **Windows are season-bounded**, matching the page's form card.
- **H2H uses 5 meetings**, the same 5 the page shows.
- **Thresholds are module constants** with a version bump when they
  change. Only the switch, the credentials and the model come from the
  environment.

---

## 3. Data gaps, measured on the production copy

The production copy was restored on 2026-10-10 into a separate local
database, **`bvp_prod`**. It is never `bvp`, which holds this machine's
gate ledger. Details:

- The dump was taken on the VM at 05:43 UTC.
- `users` and `user_sessions` were dumped as schema only, so their data
  stayed on the VM.
- Contents: 396 fixtures (2026-08-14 → 2026-10-15), 2,001 predictions, 338
  tips (all settled), 40,922 matches, migrations 001–003, and an empty
  ledger.
- Development runs point at it per command through `BVP_DATABASE_URL`. It
  never goes in `.env`.

1. **No standings.** Skipped and logged.
2. **This season's results come only from `tips`.** In production
   **every played fixture has a call** (0 uncalled across E0–E3), so form
   is complete apart from item 3. The local `bvp` store is the stale one.
3. **The 36 opening-weekend tips (14–17 Aug: E1 12, E2 12, E3 12) had no
   score.** They were settled before scores were stored.
   - **Fixed in production on 2026-10-10**: the owner ran
     `scripts/backfill_tip_scores.py` on the VM, which filled 36 and
     found no disagreements.
   - `bvp_prod` was dumped before the fix, so it still has the gap. That
     is useful for testing `results_gap` on real data.
   - Refresh the copy before Phase 3.
4. **No odds history and no stored closing prices.** Not needed under D1.
5. **Favourite/underdog record** comes from `matches.avg_*` and the last
   `fixtures.avg_*` snapshot. It is shown as a record, never as a price.
6. **No BTTS line** (B23). BTTS% as a team fact is fine.

---

## 4. Files

```
db/migrations/004_analysis.sql      match_analyses, team_summaries                       (Phase 3)
services/analysis/__init__.py
services/analysis/__main__.py       CLI: pack | run | --fixture N | --metrics | --dry-run
services/analysis/schemas.py        Pydantic: Fact, MenuLine, EvidencePack, TeamSummary, Pick, MatchAnalysis
services/analysis/facts.py          Fact Builder
services/analysis/pack.py           EvidencePack assembly; the numbers-only fallback card
services/analysis/llm.py            Foundry client (openai SDK), one structured-output request, usage
services/analysis/analyse.py        Stage A (cached) → Stage B, validation, retry with errors, fallback
services/analysis/validate.py       the brief's checks 1–7, with 4 reading "pick == the published call"
services/analysis/prompts/team_summary_v1.md, match_analysis_v1.md
services/run_cycle.py               + step_analysis after step_tips, behind BVP_ANALYSIS=1
engine/config.py, .env.example      + BVP_ANALYSIS, AZURE_FOUNDRY_URI, AZURE_FOUNDRY_KEY, AZURE_MODEL
pyproject.toml, requirements.lock   + extra `analysis = ["openai", "pydantic>=2"]`, pinned
api/main.py                         + GET /fixture/{id}/analysis behind require_user (D10)
web/src/lib/analysis.js (+ .test.js)
web/src/lib/MatchAnalysis.svelte
web/src/routes/match/[match]/+page.svelte   mounts the panel between the call box and MatchFacts
tests/test_analysis_{facts,pack,validate,llm,cycle,api}.py, tests/data/analysis/*.json
```

**Tables** (UTC-text timestamps):

- **`match_analyses`**: `analysis_id`, `fixture_id`, `tip_id`,
  `prompt_version`, `llm_model`, `model_version`, `status`
  (`ok`|`fallback`), `evidence_pack` JSONB, `analysis` JSONB, `rejections`
  JSONB, `input_tokens`, `output_tokens`, `created_at`. A partial unique
  index allows one `ok` per `(fixture_id, prompt_version)`.
- **`team_summaries`**: primary key `(team_id, dossier_hash,
  prompt_version)`; also `summary` JSONB, `llm_model`, the token columns
  and `created_at`.

---

## 5. Phases

Each phase ends at a review stop, and nothing in a phase ships before that
phase's exit check passes.

### Phase 1 — Evidence (no LLM, no schema change)

1. `schemas.py`: the Pydantic contracts, written to fit a strict JSON
   schema from the start.
2. `facts.py`:
   - L5, L10 and SEASON windows (season-bounded): form string, PPG, GF/GA
     per game.
   - The split for this fixture's venue.
   - CS%, BTTS% and O2.5%.
   - The record as market favourite and as underdog.
   - The last 5 H2H meetings and the aggregate.
   - League context.
   - IDs of the form `{SCOPE}_{METRIC}_{WINDOW}`.
   - The flags `small_sample`, `new_to_division` and `results_gap`.
3. `pack.py`:
   - The tip, plus the menu's model probabilities from the stored lambdas,
     using the same derivation B22's drawer uses.
   - The flags.
   - The numbers-only fallback card.
4. CLI `python -m services.analysis pack --fixture N` prints a pack.
5. Tests:
   - window arithmetic and season bounds;
   - ID determinism;
   - each flag, positive and negative;
   - the menu agrees with `/tips`.

**Exit:** the suite is green, and packs for three real fixtures on
`bvp_prod` have been checked fact by fact against their match pages. The
three are an E0 match, a promoted club, and an E1 club affected by the
missing opening-weekend score.

**Built 2026-10-10:** `services/analysis/{schemas,facts,pack,__main__}.py`,
`tests/test_analysis_{facts,pack}.py`; 21 tests; the full suite passes,
**819**. Checked on `bvp_prod`:

- **All 302 v3 calls build a pack.** For each one, the rule re-run on the
  stored prediction reproduces the published side and probability
  exactly.
- **Form and meetings match the match page's own data**: L5 form in 144
  cases and meetings in 278, with no differences.
- **The windows match football-data's independently published 2026-27
  results**: 498 window instances (SEASON 80, VENUE 274, L5 144) across
  all eight metrics, with no differences.
- **`new_to_division` fires on 23.5% of sides**, against about 24% of
  clubs changing division each season.

Packed for the owner's review: 307 (Bournemouth v Liverpool, E0), 336
(Rochdale v Swindon, Rochdale promoted from the National League) and 338
(West Ham v QPR, E1, with the opening-weekend gap).

Moved out of Phase 1:

- the numbers-only fallback card goes to Phase 3/4, where it is served and
  drawn;
- the LLM's output schemas go to Phase 2, once the strict-schema rules are
  confirmed.

Pydantic is imported but not yet declared; it is installed through FastAPI,
and the Phase 2 `analysis` extra declares it.

### Phase 2 — The model (no persistence)

1. The `analysis` extra and lockfile; config keys.
2. **One probe call** to confirm strict structured output on the
   deployment, and to record tokens and price.
3. `llm.py`: timeouts, the SDK's own retry on 429/5xx, and token logging
   per call. The Stage A cache sits behind a small lookup function that
   Phase 3 backs with the table.
4. Prompts v1, rewritten for D1/D2 from the brief's text. **The owner
   reviews the wording.**
5. `validate.py`:
   - schema;
   - every fact id exists;
   - the pick is the published call;
   - every number in the prose matches the pack (including `0.62` ↔ `62%`,
     `2.10` and `3-1`);
   - banned phrases;
   - word counts as soft warnings.

   A failed check is retried up to twice, with the errors fed back. After
   that the result is the fallback card.
6. Tests with a mocked client: valid output, a hallucinated fact id, an
   invented percentage, and a wrong pick, each through retry to fallback.
   One opt-in test runs only under `RUN_LLM_TESTS=1`.

**Exit:** the mocked suite is green. Five real fixtures generated from
`bvp_prod` (dry run, printed) are ready for the owner to read, with the
measured cost per fixture.

**Built 2026-10-10:**

- `services/analysis/{llm,validate,analyse}.py`, the prompts, the
  `analyse` CLI, the `analysis` extra (`openai>=1.91,<2`, pinned at 1.91.0)
  and `AZURE_*` in `engine.config`.
- Stage orchestration lives in `analyse.py`, so `llm.py` stays one request.
- 24 tests (validator rules both ways, number edge cases, the mocked chain
  through retry and fallback) plus one opt-in `RUN_LLM_TESTS=1` test. The
  full suite passes **843**, with 1 skipped (that opt-in test).

What the live calls showed:

- **The probe** passed first time: key auth, the strict schema and the
  `reasoning` setting were all accepted. One Stage A call took 6.7 s and
  1,904 / 294 tokens, and the validator passed it.
- **Five fixtures**, one per call type (307 `12`, 338 `H`, 327 `H+1.5`,
  329 `A+1.5`, 271 `X2`), **all `ok`**. One content retry: 338's rationale
  wrote the market code "12", which the number check rightly could not
  place. The prompt now asks for market labels instead of codes. v1 had
  never been stored, so it was edited in place; once Phase 3 stores a
  row, a prompt change means a v2 file.
- Claims built on text facts, which the validator cannot check, were
  checked by hand against the packs. All true.
- **Tokens per fixture**: 6.5k–11.1k in and 1.1k–1.7k out (mean 8.4k and
  1.3k, three calls). About 54 fixtures a week makes about 450k in and 70k
  out. The cost is those times the deployment's per-token price, which the
  owner has; the catalog page shows none.
- The samples are in `tmp/analysis_samples_v1.md` (untracked) for the
  owner to read.

**Carried to Phase 3:** `scripts/deploy.sh` installs `.[serve,dev]`. It
must add `analysis` when the cycle first imports the package.

### Phase 3 — Store, cycle, API

1. Migration 004.
2. `step_analysis` after `step_tips`, off unless `BVP_ANALYSIS=1`.
   Additive and never fatal; a fallback makes the cycle exit 2 (look).
3. CLI: `run` (today's tips), `--fixture N` (re-run a fallback only),
   `--dry-run`.
4. `GET /fixture/{id}/analysis` behind `require_user`. It serves the
   latest `ok`, or else the `fallback`, with fact ids resolved to label and
   value, and the team summaries inside.
5. Tests:
   - 401 when signed out, 200 when signed in, 404 before an analysis;
   - the write-surface pin unchanged;
   - the step is off by default;
   - one row per fixture per version;
   - a fallback can be superseded and an `ok` cannot.

**Exit:** the suite is green. The CLI has run end to end on `bvp_prod`
and the rows read back.

**Built 2026-10-10:**

- **Store and job.** `db/migrations/004_analysis.sql` (`team_summaries`,
  and `match_analyses` with one ok and one fallback per fixture and prompt
  version) and `services/analysis/jobs.py` (pending, rerunnable, the
  summary cache from the table, save, run).
- **Cycle step.** `run_cycle.step_analysis`, off unless `BVP_ANALYSIS=1`.
  It runs **last**, not straight after `tips`: it is the one slow step
  and nothing waits on it. A dry run asks the model nothing.
- **CLI.** `run` and `rerun`.
- **Route.** `GET /fixture/{id}/analysis` behind `require_user`.
- **Deploy.** `deploy.sh` installs the `analysis` extra, and the cycle
  unit carries `BVP_ANALYSIS=0` with a note on the credentials drop-in.
- **Tests.** 16 new; the full suite passes **859**, plus 1 opt-in skip.

**Bounded in time.** The cycle unit has `TimeoutStartSec=30min`, and a
full Saturday (about 46 calls at about 25 s) would come close to it run
one after another.

- Fixtures run 4 at a time against one 15-minute deadline
  (`jobs.BUDGET_SECONDS`). The deadline is checked before every request.
- A fixture the deadline cuts off is stored as a fallback, reason
  recorded, and can be re-run before kick-off.
- Each request is limited to 90 s, with 2 transport retries.

**End to end on `bvp_prod`:**

- migration 004 applied;
- fixture 336 written in three requests (6,772 in / 1,154 out, no
  retries), stored, and read back through `fixture_analysis` with every
  cited id resolved;
- `rerun` refuses it ("an ok is never replaced");
- `pending` is empty, because the copy has no call for today.

**A first analysis is only ever written for a match not yet played.**
`pending` reads today's calls, and `rerun` needs an existing fallback and
a fixture not yet played. Nothing can backfill an analysis for a match
already played, in the same spirit as never backfilling predictions or
tips.

### Phase 4 — The panel

1. `$lib/analysis.js`: the fetch and fact-id resolution, with tests.
2. `MatchAnalysis.svelte`:
   - **signed out:** the sign-in card;
   - **signed in:** the preview, the call card (side, claimed probability,
     the menu), the "Why?" toggle with supporting and contradicting facts,
     the team profiles, flags as badges, the fallback card, and the fixed
     D9 line.
3. Mounted on the match page and fetched in the browser only.

**Exit:** web tests pass, plus a Playwright click-through covering:

- signed out and signed in;
- upcoming, live and settled fixtures;
- `ok` and `fallback` rows;
- phone width;
- **the server HTML carries no analysis text.**

**Built 2026-10-10:**

- `web/src/lib/MatchAnalysis.svelte`, mounted on the match page between
  the call box and the form.
- `web/src/lib/analysis.js`, with 5 tests.
- An `account` context in `+layout.svelte`, read from the same `/me` as
  the betPawa store.
- `has_analysis` on the public `/fixture/{id}`: existence only, no text.
- Head-to-head fact labels made self-contained ("Arsenal wins in the last
  5 meetings"), because the "Why?" list shows them out of context.
- Python 860 (+1 opt-in skip), web 108; **26/26 click-through checks**.

**The panel opens on a click, not by itself.** This is a deliberate
change from the "Exit" sketch above.

- The server renders a fixed-size card ("Match analysis" and one
  button), only where an analysis exists.
- The text is fetched when a signed-in reader clicks.
- Growth that follows a click does not count as layout shift, so the
  match page keeps its CLS.
- Signed out, the button reads "Sign in to read the analysis" and opens
  Google sign-in. The text is never in the page.

**Click-through**, run on a scratch copy of the production data
(`bvp_p4`, now dropped):

- **The setup.** The copy's 40 calls for today were published by the
  real rule. One was analysed through Foundry (`ok`, three requests). One
  was forced into a fallback (budget 0). Rochdale v Swindon (settled) was
  analysed earlier.
- **Checked**:
  - the server HTML has the card and none of the text, even with a
    session cookie;
  - there is no card on a call without an analysis, or before the call;
  - signed out, the card offers sign-in and does not open;
  - signed in: preview, call card, a 7-market menu with the call marked,
    "Why?" listing every cited fact, two profiles and the fixed line;
  - a fallback shows the figures and no AI claim;
  - a settled match still opens;
  - at phone width, nothing overflows or is clipped.
- **The page's layout shift:** CLS 0.003 signed in. Signed out, the panel
  keeps its server height (134 → 134). The page totals 0.022, because
  **the existing betPawa "Sign in to bet" button (B26) appears in the
  call box after load** and pushes everything below it down 47 px. The
  same page without the panel already measures 0.014.
  - That is a B26 issue, left untouched: reserve the button's space while
    the account loads.
  - Both figures are well inside Google's "good" threshold of 0.1.

### Phase 5 — Metrics and ship

1. `--metrics`: rejections by rule, retries, fallback rate, and tokens and
   cost per fixture, per `prompt_version`.
2. `RUNBOOK.md` and `DEPLOY.md`: the `bvp-cycle` drop-in (`AZURE_*`,
   `BVP_ANALYSIS=1`), key rotation, reading the metrics.
3. Owner: commit, `deploy.sh` (migrate 004), enable the flag, then read a
   few matchdays before announcing it.

**Built 2026-10-10:**

- **`services/analysis/metrics.py`** and the CLI's `metrics`. Per prompt
  version and deployment it reports:
  - fixtures that ended ok or in a fallback, and fallbacks re-run to ok;
  - the first-pass rate;
  - requests per analysis and retries;
  - rejections by rule (an unrecognised error is counted as "other",
    never dropped);
  - word-count warnings;
  - tokens per fixture, and cost when `--price-in`/`--price-out` are
    given.

  It also writes JSON with `--json`. 2 tests; the full suite passes
  **862**. On `bvp_prod`: 1 fixture, ok, first pass, 6,772 / 1,154
  tokens.
- **`RUNBOOK.md`**: §0 gains the step, §5.12 is the step's playbook (each
  status line, reading a fallback's attempts, `rerun`, changing a prompt,
  turning it off), §6 gains the two tables, and §7 adds `metrics` to the
  weekly review.
- **`DEPLOY.md`**: §2.7's settings table and §5.3's analysis block (the
  credentials file, a printed analysis before anything depends on it, the
  drop-in, verification, the first run by hand, key rotation, turning it
  off).
- **The key lives in `/etc/bvp/analysis.env`** (root:bvp 0640), loaded by
  `EnvironmentFile=` in the drop-in, not in an `Environment=` line.
  `systemctl show` prints `Environment=` to any user on the VM, and the
  file also serves manual `rerun`s. The tracked unit's note says so.
- **Not built:** the brief's Svelte admin table. Metrics are a CLI, like
  every other measurement here (D5); an owner-only page can come later if
  wanted.

---

## 6. Owner to-dos, by when they block

- ~~Before Phase 2: save `AZURE_MODEL`; approve the probe call~~
  **Done 2026-10-10** (`AZURE_MODEL=gpt-6-sol`, the deployment's name;
  probe passed).
- ~~Before Phase 3: read the five samples and the two prompts~~ **Done
  2026-10-10** ("the samples look good"). **The prompts are now frozen as
  v1**: any change is a new `_v2` file.
- ~~Before Phase 3 ships: backfill the 36 opening-weekend scores on the
  VM~~ **Done 2026-10-10.**
- **To ship** (`DEPLOY.md` §5.3, the analysis block, has every command):
  1. Commit and push.
  2. `deploy.sh` on the VM. It installs the `analysis` extra and applies
     migration 004.
  3. Create `/etc/bvp/analysis.env` with the three `AZURE_*` values.
  4. One printed `analyse --fixture N` on the VM. This proves the key, the
     model name and the egress before the cycle depends on them.
  5. Copy the tracked cycle unit, add the drop-in, and `daemon-reload`.
  6. The next 06:00 cycle writes the day's analyses. Check the journal,
     `match_analyses` and `metrics`.
  7. Read a few matchdays on the site, signed in, before announcing it.
- **Separately:** the B26 betPawa sign-in button's layout shift on live
  match pages for signed-out readers (Phase 4's note).

## 7. What this does not change

No rule, threshold, ledger or measurement change. The book stays off. No
odds, return or P&L reaches a page. The API gains two read routes (the analysis, and §8's
trends) and no write route. The call is still made by `engine/serve/tips.py` alone; the
LLM explains it and cannot alter it.

## 8. Form trend on the listings (owner request, 2026-10-10)

The owner asked for an improving / stable / declining icon per team on the
tip and parlay listings, "already in the analysis". Assessed first:

- the analysis's `trend` is the LLM's reading. The prompt says "clearly
  better" with no threshold or named measure, and the validator never
  checks it;
- over the season's calls on the production copy, 75% of sides had five
  or fewer games on record, which the prompt's rule turns into "stable";
- all ten v1 sample profiles said "stable".

**Owner decisions:**

- **T1 Both, side by side.** The icon is calculated, and its note also
  shows the analysis's own word, which can differ from it. There is no
  prompt change; v1 stays frozen.
- **T2 The rule** (`facts.form_trend`):
  - points per game over the last 5 against the last 10, or against the
    season while the side has fewer than 10. These are the pack's
    `PPG_L5` and `PPG_L10`/`PPG_SEASON` windows and figures;
  - a difference of ±0.5 or more is a trend;
  - fewer than 6 games, or a missing score in the window, gives no icon,
    not "stable".
- **T3 Signed-in only**, as D10, though the calculated trend is not AI
  text. It is served by `GET /trends` behind `require_user` and fetched in
  the browser. Nothing goes into `/tips` or the server HTML.

**Built 2026-10-10, uncommitted:**

- `form_trend` and its two constants in `facts.py`;
- `GET /trends`;
- `$lib/trend.js` and `$lib/TrendMark.svelte`, a mark on the crest's
  corner:
  - it is absolutely positioned, so its arrival shifts nothing;
  - hover or tap opens a note with the two figures and the analysis's
    word;
  - a click on it never reaches the row's drawer;
- the mark on the front page and `/parlay`;
- tests: 4 for the rule, 2 for the route, 2 web;
- a 24/24 click-through on a scratch copy of production with 2026-10-10's
  calls published. Its AI words were faked.

**On that day's 40 calls**, with the opening-weekend scores backfilled:

| Sides | Count |
|---|---|
| Stable | 60 |
| Improving | 5 |
| Declining | 3 |
| No trend | 12 |

Most marks read "stable" until the windows separate, around November. The
route computes 41 fixtures in about 40 ms.
