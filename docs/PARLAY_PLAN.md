# PARLAY_PLAN — the parlay page

Written **2026-09-01**, before anything was built. Owner request: a separate
page where a reader generates a parlay (accumulator) from the upcoming
games, choosing **league**, **risk threshold** and **number of games**, and
which opens on the recommended settings. This file is the plan; nothing in
it has run. The assessment it rests on (2026-09-01, λ-only scan, no ledger
row) is summarised in §1 so the plan stands on its own.

Reading order for a thread picking this up: `STATE.md` → this file →
`BACKLOG.md` B24 → `engine/serve/tips.py` (what a leg is) → `api/main.py`
`/tips` (what the page already gets).

---

## 0. What is being built, in one paragraph

A page at **`/parlay`** that takes the day's **published** tips — the same
rows `/tips` serves, one call per fixture, `confidence-v3` — filters them by
league and by a minimum claimed probability, ranks what is left by claim,
and shows the top *k* as one parlay with its combined claimed probability
(the product of the legs' claims). **It is a view over calls that already
exist.** It publishes no new call, changes no rule, and in phase 1 grades
nothing: every leg is a single that the record already grades, and the
parlay is the reader's combination of them. On launch it shows **all
leagues, the "Safer" threshold (claim ≥ 0.80), 2 legs**.

## 1. The numbers behind the defaults

From the v3 rule run over the 15,824-match dev corpus (2014-15 → 2022-23,
E0–E3), claims only, no outcomes read, 2026-09-01:

- **The 0.85 ceiling caps every fallback leg.** 64% of calls are the
  underdog +1.5 (claims ~0.80, delivered 80.6% at gate row 110); no fallback
  claim can exceed 0.85, and only 0.18% of calls (outrights) do. On a
  Saturday the best leg claims 0.845 and the fifth-best 0.827. There is no
  pool of 0.90+ "bankers" to build an accumulator from.
- **Matchdays are small.** Median E0–E3 matchday has 3 fixtures (p75 17,
  p90 39). Of 1,450 dev matchdays, 964 have ≥ 2 tips, 776 ≥ 3, 660 ≥ 4. A
  parlay is a Saturday product; midweek the page will often have fewer
  legs than asked for and must say so rather than pad.
- **Top-*k* legs by claim, product of claims** (legs are distinct matches,
  so independence is the first approximation; the rule's ~+1 pt under-claim
  makes these slightly conservative):

  | k | mean, all matchdays | Saturdays (≥ 20 fixtures) | k-th best leg claims |
  | --- | --- | --- | --- |
  | 1 | 0.804 | 0.845 | 0.845 |
  | **2** | 0.656 | **0.709** | 0.839 |
  | **3** | 0.536 | **0.592** | 0.835 |
  | 4 | 0.445 | 0.492 | 0.831 |
  | 5 | 0.374 | 0.407 | 0.827 |
  | 6 | 0.307 | 0.336 | 0.824 |

  Any *k* tips rather than the best *k*: 0.59 / 0.46 / 0.35 at k = 2 / 3 / 4.

**So: default 2 legs, maximum 3.** Three is the last *k* at which the
parlay is likelier to win than lose on a Saturday; four is below a coin
flip even with the best legs of the day. A 3-leg parlay strikes ~55–59%
against the 78% the site sells for singles, and at one Saturday parlay a
week its record carries ±8 pts of noise over a season — which is why phase
1 grades nothing and §3 measures before the page is linked.

**No price, no return.** ~64% of legs are handicaps with NULL prices
(`engine/serve/tips.py` `UNPRICEABLE_SIDES`), so the page cannot show
parlay odds or a payout, and the measured per-leg return (−4.6% at average
prices, `TIPSTER.md` A) *compounds*: ~−13% on a treble. The page's honesty
copy has to say both (§5).

## 2. Decisions for the owner

Each with the recommendation the build below assumes. A different answer
changes the build in the way stated.

| # | decision | recommendation | why |
| --- | --- | --- | --- |
| **D1** | Where the selection runs | **Server: `GET /parlay`, selector in `engine/serve/parlay.py`.** Alternative: a pure JS function over `/tips` in the browser | `web/src/lib/api.js` states the site "never recomputes a probability … so that what a user sees is provably what was stored"; the combined claim is a new probability. One server function also serves any future stored parlay (D6) and is tested in pytest against the same rows the API serves. Client-side is ~40 fewer lines and one fewer endpoint; it breaks the convention |
| **D2** | What "risk threshold" means | **Minimum claimed probability per leg**, three presets: **Safer ≥ 0.80**, **Balanced ≥ 0.70**, **Any call** (no floor beyond what the rule published). Alternative: a target *combined* probability | Same currency the rule's floor/ceiling use, and every leg stays an individually published call. A combined target makes *k* and risk interact (raising *k* silently drops the threshold) and the page would have to explain that |
| **D3** | Legs offered | Recommended **2 or 3; default 2.** **Owner chose 2026-09-01: 2 to 4, with a warning at 4** — the page labels a 4-leg parlay "more likely to lose than win"; `MAX_LEGS = 4`, `WARN_LEGS = 4`, `size_warning` on the wire | §1: 4 is below 50% on the best day of the week. Offered anyway, labelled |
| **D4** | The pool | **Every unplayed published tip** (`/tips`'s own predicate), minus fixtures whose kick-off has passed; no same-day constraint | With `PUBLISH_WITHIN_DAYS = 0` the pool is today's fixtures anyway. Kicked-off games must go: `/tips` keeps a 15:00 game "upcoming" at 17:00, which is harmless in a list and wrong in a parlay someone might place |
| **D5** | Fewer than *k* legs clear the threshold | **Show what clears, say "2 of 3 calls clear this threshold today", never pad from below it** | Padding would put a 0.58 leg in a "Safer" parlay |
| **D6** | Is the recommended parlay recorded and graded? | **Not in phase 1.** Phase D (§4) stores the launch-default parlay per matchday and grades it — decide after the probe (§3) and a few Saturdays of use | A stored parlay needs a migration, a cycle step, settlement rules and RUNBOOK discipline; its record is noisy (§1). The singles record already grades every leg |
| **D7** | When it is linked from the nav | Recommended **route first, nav link after the probe reads clean.** **Owner chose 2026-09-01 (after Phase B): link now** — a solid accent-orange "Build a parlay" button beside the header's red "This week's calls" CTA (`+layout.svelte`; owner asked for it to stand out), `aria-current` on `/parlay` softens it to `--accent-soft` | The combined claim is a claim the site has not measured yet; the probe (§3) is now the first thing to run *after* the link, not before it |

**Decided 2026-09-01 (owner, before Phase A): D1 server · D2 per-leg, three
presets · D3 2–4 legs with a warning at 4 · D4 exclude kicked-off · D5 as
stated.** **D7 decided after Phase B: linked now.** D6 stays open until the probe.

## 3. Measurement before launch — `probe:b24_parlay_independence`

**Pre-registration, to be completed (predictions filled in) before it runs.**
The page will show a combined claim. Each leg's calibration is measured
(gate row 110: v3 claims 76.9, delivers 77.9; `D+1.5` claims 80.3, delivers
80.6). The **product** of legs is not: it assumes the legs are independent
and that selecting the *top-k by claim* on a day does not select
over-claiming legs (the B11 pattern on totals was exactly that). This probe
measures the one thing the page adds.

- **Population:** the dev corpus, v3 rule (`engine/eval/b21.recommend`),
  per matchday, top-*k* by claim with threshold *r*, for k ∈ {2, 3, 4} and
  r ∈ {0.80, 0.70, 0}; a matchday contributes only where ≥ *k* legs clear
  *r*. Split: all matchdays; Saturdays (≥ 20 fixtures); per division.
- **Statistic:** realised P(all legs win) − mean product of claims, with a
  week-block bootstrap CI (`engine/eval/bootstrap.week_blocks`). Not paired
  against another arm — there is no other arm; it is a calibration read
  on the same outcomes gate row 110 already read.
- **Control (convention 8):** a planted *dependent* parlay — the same
  match entered twice as two legs — must read realised − product resolved
  **positive** (≈ p(1−p) at the leg's claim). If the instrument cannot see
  dependence when it is planted, the table is not a result.
- **Predictions (fill in before running — starting points):** P1 at k = 2,
  r = 0.80, realised − product in **[−1.0, +3.0] pts** (per-leg under-claim
  compounds, small selection effect against it). P2 no division resolved
  negative at k = 2. P3 Saturday k = 3 realised in **[56, 63]%**. A resolved
  negative pooled gap at k = 2 or 3 lowers the maximum in D3 or adds an
  offset to the shown claim; either is the finding.
- **Cost:** 0 configurations, one probe row (re-aggregates outcomes already
  read for row 110, the footing B17/B20/B23 used). Run **on the authority
  machine only** (`dev-environment` rule), then `python
  scripts/export_ledger.py` and commit `docs/gate_ledger.jsonl` in the same
  commit. Code `engine/eval/b24.py`, tests `tests/test_b24.py` on planted
  data (independent legs read zero; the planted dependent pair reads
  positive), results `docs/b24_results.json`.

## 4. Build

Each step ends with the check that says it is done.

### Phase A — selector and endpoint (backend, ~½ day)

1. **`engine/serve/parlay.py`** — `select_legs(tips, *, legs, min_claim,
   now)`: a pure function over the dict rows `/tips` serves. Drops rows
   below `min_claim` and rows whose `match_date` + `kickoff_time` (UK
   wall-clock, `services/bbc_calendar.py`) is before `now` in
   `Europe/London`; sorts by claim desc, kickoff asc, `fixture_id` asc;
   returns the first `legs` and their product. Constants `DEFAULT_LEGS =
   2`, `MAX_LEGS = 4`, `WARN_LEGS = 4`, `PRESETS = {"safer": 0.80,
   "balanced": 0.70, "any": 0.0}`. **Built 2026-09-01** — one leg per
   fixture added (two rule versions on one match must not become two legs),
   `available` is the uncapped count of qualifying fixtures, `claimed` is
   None rather than 0 on an empty pool. **No import from `engine.eval`** — the API must keep loading
   without the measurement stack (`api/main.py` restates `MAX_GOALS` for
   this reason).
   → verify: `tests/test_parlay.py` — threshold applied, order and tie-break
   pinned, product equals the legs' claims multiplied, short pool returns
   what clears and reports `available`, a kicked-off fixture is excluded,
   same input → same output.
2. **`api/main.py`** — `GET /parlay?division=&legs=2&min_claim=0.80`,
   built on `TIP_SELECT` + `_with_handicap` (so each leg carries the same
   fields as a `/tips` row and the page can reuse every helper). Returns
   `{legs: [...], claimed, requested, available, min_claim, division,
   size_warning}`. **Built 2026-09-01**; the UK clock is `_london_now()`,
   pinned by monkeypatch in the test.
   400 on an unknown division (existing `_check_division`), `legs` outside
   `2..MAX_LEGS`, `min_claim` outside `[0, 1]`. Read-only; no P&L, no
   price on the parlay (legs keep their own NULL/derived prices, labelled
   as `/tips` labels them).
   → verify: `tests/test_api.py` additions on the `tips_client` fixture —
   contract of the body, the two 400s, only unplayed fixtures, `available
   < requested` when the fixture has one qualifying tip.
3. `pytest -q` green apart from the pre-existing date-dependent failure
   (`test_a_failing_results_source_does_not_stop_the_cycle`, noted in
   `STATE.md`).

### Phase B — the page (frontend, ~1 day) — **BUILT 2026-09-01**

As planned, with three notes: the API also returns `pool` (live calls
before the threshold), which the page needs to tell "no calls live" from
"none clears this bar"; `$lib/parlay.js` returns `{head, body}` sentences
for the three short states rather than one string; and the nav link went
in the same day by owner decision (D7): a solid accent-orange "Build a
parlay" button beside the header CTA. Verified:
24 web tests, `npm run build` clean, and a Playwright click-through of 17
checks against a seeded scratch database (owner's visual check still
open).

4. **`web/src/lib/api.js`** — `getParlay(division, legs, minClaim)` and the
   preset list (`RISK_PRESETS`, labels + values, mirroring `PRESETS`).
5. **`web/src/lib/parlay.js`** — display helpers only: the "n of k calls
   clear this threshold" sentence and the combined-claim label. No
   arithmetic on probabilities (the product arrives from the API). Tests
   in `parlay.test.js`, `node --test`, the pattern `view.js` / `owner.js`
   use because the runner cannot load a `.svelte` file.
6. **`web/src/routes/parlay/+page.svelte`** — new route. Controls: league
   (`DIVISIONS`, the `.tabs` pattern from the main page), risk (three
   `.switch` presets), legs (2 / 3). State → refetch `$effect`, as the
   settled section does. Body: the legs as cards reusing `callLabel`,
   `callCode`, `callMeans`, `fixtureBadges`, `localKickoff`; the combined
   claim; the copy in §5. Empty states: no published tips yet ("calls
   publish on matchday"), and `available < requested`. On launch: All /
   Safer / 2 — the URL carries no state in phase 1.
7. **`web/src/routes/+layout.svelte`** — `internal` is currently
   `pathname !== '/'`, which would put the "Internal view … uncalibrated"
   banner and narrow shell on `/parlay`. Change it to name the two internal
   routes (`/book`, `/performance`). Nav entry `Parlay → /parlay` — per D7,
   added when the probe reads clean.
8. nginx needs nothing: `adapter-static` with `fallback: 'index.html'`
   already serves any client route (`DEPLOY.md`, the `/book` note).
   → verify: `cd web && npm test` (existing 20 + new) and `npm run build`
   clean; a click-through in the running app (`vite dev` against the local
   API) covering each control, the short-pool state and a kicked-off
   fixture; the visual check is the owner's.

### Phase C — documents and deploy (~½ day)

9. `BACKLOG.md` B24 (this plan's summary, decisions as taken, probe
   result), `PRODUCT.md` §6 "the parlay page" (what it is and is not),
   `STATE.md` site row, `OUTSTANDING.md` entry, `RUNBOOK.md` (nothing new
   to operate — no cycle step, no migration — say so). Deploy is the
   standard sequence (`DEPLOY.md`): `git pull`, `npm ci && npm run build`,
   `systemctl restart bvp-api`. Between matchdays, as v3's deploy is.

### Phase D — optional, on D6: the recorded parlay (~1 day, not scheduled)

Store the launch-default parlay (All / Safer / 2) per matchday and grade
it: migration `007_parlays.sql` (`parlays` + `parlay_legs`, `UNIQUE
(match_date, rule_version, legs, min_claim)`), a `parlay` step after
`tips` in `services/run_cycle.py` calling the same `select_legs`,
settlement from the legs' outcomes (all `win` → win; any `lose` → lose;
a `void` leg drops out; a parlay left with one leg is void), `GET
/parlay/record`, a record block on the page. Append-only like tips: once
written, never revised. Only worth building if the owner wants a graded
parlay record on the site, knowing its noise.

## 5. What the page must say

Plain text near the parlay, kept as short as the main page's honesty line:

- **"Claimed"** on the combined figure, as on the settled cards, and one
  sentence: it is the legs' claimed probabilities multiplied, on the
  assumption the games are independent.
- **Each leg is one of today's published calls and is graded on its own
  on the record. The parlay is not graded** (phase 1).
- **No return.** The site publishes none for singles; a parlay compounds
  whatever the singles return, so it would be worse, not better.
- The footer's 18+ / begambleaware line already applies.

## 6. Effort

Probe ½ day · Phase A ½ day · Phase B 1 day · Phase C ½ day — about **2½
days** to a linked page, plus Phase D (1 day) if D6 is yes.

## 7. What this does not change

The rule (`confidence-v3`), the tip list, the cycle, the schema (phase
1), the record, the book (off), and the ledger except for the one probe
row in §3.
