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

**Amendment 2026-09-04, written before the run** (owner approved §8's
extension and D8–D11 the same day): the grid gains **k ∈ {5, 8, 10, 15,
20} and the full-day slip at r = 0**, pooled and on Saturdays, for the
same 0 configurations. The unit is stated precisely: a **slip** is the
top-k calls by claim within one matchday (ties by corpus order — the dev
corpus has one call per match and nothing kicked off, so this is the
page's selector restated); realised = every leg won, claimed = the
product; the statistic is mean(realised − claimed) over slips,
`bootstrap.paired` over ISO-week blocks of matchdays; positive =
under-claim, the safe direction. Two predictions join P1–P3: **P4** — at
r = 0, pooled, no k ≤ 10 reads a resolved *negative* gap (the leg-level
under-claim compounds; a resolved negative would mean top-k selection
finds over-claimed legs, and caps the slider). **P5** — at k ≥ 15 the
all-win count implied by the claims themselves is single digits (~5
Saturdays at k = 20, ~0 at full day), so those cells are **reported, and
carry no calibration verdict**; the long end of the slider ships as
labelled theory whatever they show.

### Result — **MEASURED 2026-09-04. The product is calibrated; no consequence fires.**

Ledger row **113** `probe:b24_parlay_independence`, **0 configurations —
113 / 70 / 202**, ledger re-exported, `--check` clean. Results
`docs/b24_results.json`; code `engine/eval/b24.py`, tests
`tests/test_b24.py` (5, planted). **The control fired**: the same match
entered twice reads +14.33 [+13.43, +15.16] ✱ against an expected +14.59,
so the instrument sees dependence when it is there and the table is a
result.

Scorecard: **P1 missed on the point, unresolved** — pooled k = 2 at
r = 0.80 reads −1.49 [−4.97, +2.23] against the predicted [−1.0, +3.0];
the CI covers zero comfortably, and the point sits where top-2-of-a-thin-
midweek-pool selection would put it. **P2 held** (no division resolved
negative at k = 2; E0–E3 gaps −1.0 to +1.4, none resolved). **P3 held**
(Saturday k = 3 realised **60.50%**, inside [56, 63]). **P4 held** (no
resolved negative anywhere k ≤ 10 at r = 0; gaps −1.8 to +2.6, all
unresolved). **P5 as pre-stated**: k = 15 and 20 read gaps of +0.0
[−2.0, +2.2] and +0.0 [−1.2, +1.6] — realised hits 18/386 and 5/319
against claims of 4.65% and 1.52% — and the Saturday full-day cell
(claimed 0.05%, 0 hits in 319) reads "resolved −0.05" only because a
fraction of a hit cannot be delivered; the claim itself implies 0.16 hits
in the sample, so zero observed is what calibration looks like there.

**Reading:** realised tracks the product within ±2 pts at every size with
data, nine seasons, 964 matchdays. The independence assumption holds to
the precision available, the pre-registered consequence (an offset or a
lower cap on a *resolved* negative at k = 2 or 3) does **not** fire, and
the page's combined figure stays the raw product, labelled "claimed".

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


---

## 8. Second assessment — 2026-09-04: call-type selection, and a slider to the full matchday

Owner request: assess (not build) two additions — a selection of call
options ("1X2, over/under, straight wins and so on") and a legs slider
scaling to the full number of games available that day. λ-only scan on the
dev corpus (claims only, no outcomes read, no ledger row — 112 / 69 / 202
unchanged), run on the Postgres store the day of the cutover.

### 8.1 Call-type selection — feasible as a filter over the three
published groups; over/under is blocked by measurement, not code

A parlay leg is a published call, so the honest menu is the three groups
the rule actually publishes, plus "Any call":

| group | share of calls | claims p50 | Saturday pool | Sat top-2 | Sat top-3 | matchdays with ≥ 2 |
| --- | --- | --- | --- | --- | --- | --- |
| Straight wins (`H`/`A`) | 14.4% | 0.605 | ~4 | **0.458** | 0.289 | 33% |
| Double chance (`1X`/`X2`/`12`) | 21.8% | 0.765 | ~8 | 0.613 | 0.472 | 37% |
| Handicap (`H+1.5`/`A+1.5`) | 63.8% | 0.805 | ~24 | 0.708 | 0.591 | 50% |

Build is ~½ day on clean seams: a `sides` filter parameter on
`select_legs` (pure; one group constant), a query parameter on
`GET /parlay`, a chips row on the page, tests. The scarcity sentences
(`pool` / `available`) already handle the thin pools. Note **a straight-wins
double is below even (46%) on a typical Saturday** — a type filter makes the
warning's fixed-legs trigger wrong (§8.2, D11).

**Over/under cannot be offered by a page change.** The rule publishes no
O/U call: B4 (extend the menu to goal lines) was **measured and closed**
2026-08-16 — every shape inert, collapsed, or landing on the line the head
gets most wrong — and B11 measured the popular unders **over-claiming by
4–9 pts in E1–E3** (worst on the priced 2.5 line); B23 closed BTTS the
same way. Offering an O/U leg is publishing an O/U call — ungraded, on a
market the head is measured to be wrong on outside E0, and multiplied into
other legs. That requires reopening B4 with a measured gate (a head fix
first — B17/B18/B19 territory), not a parlay feature. Same for the draw
and literal "1X2": the rule never publishes `D`.

### 8.2 The slider — mechanically small; the number collapses fast and
the long end is unverifiable

Saturday top-k product of claims (319 Saturdays, ≥ 20 fixtures; sizes p50
39, max 46):

| k | 2 | 3 | 4 | 5 | 8 | 10 | 15 | 20 | 30 | full day |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| claimed | 0.709 | 0.592 | 0.493 | 0.41 | 0.23 | 0.15 | 0.050 | 0.015 | 0.0012 | **~0.000043 (≈ 1 in 23,000, median)** |

Build is ~½–1 day, also on clean seams — `pool` is already on the wire, so
the slider's maximum is free and clamps when a filter shrinks the pool.
What has to change: `MAX_LEGS` becomes a hard server cap (46, the largest
matchday in the corpus) with the request clamped to the day's pool; the
2 / 3 / 4 buttons are replaced by the slider; the fixed `WARN_LEGS = 4`
retires in favour of a server flag `below_even` (`claimed < 0.5`) — with a
type filter the leg count no longer determines the risk; the combined
figure needs odds formatting at the long end (`pct(x, 0)` prints **0%**
from k ≈ 15, and the page must never show a claim of zero — "about 1 in
N" from ~5% down); and the `LEGS` mirror pin in `tests/test_parlay.py`
changes shape.

**The measurement condition.** The §3 probe grid extends to the slider's
range for the same 0 configurations — but beyond k ≈ 10 the product is
unverifiable in sample: at k = 20 the claim implies ~5 all-win Saturdays
in nine seasons, at full day ~0. The long end ships as labelled theory
("assuming the games are independent"), and a per-leg bias of ±1 pt
compounds to ×0.6–1.7 on a 40-leg product, which is exactly why the probe
(now overdue twice over — D7 went first) should run before this ships.

### Decisions this needs (D8–D11)

- **D8** — which type filters: recommend **Straight wins / Double chance /
  Handicap / Any**; O/U only via reopening B4 (recommend not now).
- **D9** — slider ceiling: recommend **the day's full pool** as asked
  (hard cap 46), odds-formatted at the long end.
- **D10** — the slider **replaces** the 2/3/4 buttons (one control).
- **D11** — warning keys on **`below_even`**, not a fixed leg count.

**Decided 2026-09-04 (owner): D8 without over/unders, D9–D11 as
recommended, probe first. Built the same day, after the probe (§3 result):**
`SIDE_GROUPS` + `sides` filter and `MAX_LEGS = 46` + `below_even` in
`engine/serve/parlay.py` (WARN_LEGS retired), `sides` on `GET /parlay`,
type chips (labelled **All types** — the risk preset already owns "Any
call") and the pool-bounded slider on the page (the choice clamps down
when a filter shrinks the pool, and disables at the minimum),
`claimLabel` in `$lib/parlay.js` (whole percents to 5%, one decimal to
0.5%, "about 1 in N" below — the figure can never read 0%). Verified:
**663 pass** (full suite, no failures), 25 web tests, build clean, and a
17-check Playwright click-through on a seeded `bvp_scratch` Postgres
database (dropped after).

**D8 amended 2026-09-04 (owner, later the same day): the type filter is
multi-select** — the chips are toggles and any mix of the three groups can
be on, never none (the last chip refuses to turn off). On the wire `sides`
is a comma-separated key list, normalised to canonical order and to
`"any"` when all three are named (`parse_sides` in
`engine/serve/parlay.py`); the pool and the slider's ceiling follow the
union. The "All types" chip is gone — all-on is the default and means the
same thing. Verified: 46 selector/API tests, 25 web tests, build clean,
and the click-through extended to 21 checks (toggling down to one type,
the last-chip guard, a two-type mix on the wire, all-on normalising back
to `any`).

Effort ~1–1.5 days including tests and click-through. No schema, rule,
cycle or ledger change; the probe stays the only ledger row in sight.
Postgres did not move this seam: the selector is pure and untouched, the
endpoint is ported, the page is unchanged.


---

## 9. Third assessment — 2026-09-04: the type control as a market selector, not a filter

Owner clarification, assessed and **not built**: selecting Double chance on
a game whose published call is a straight win should show that game's
double-chance option, not drop the game. That is a different feature from
D8-as-built (a filter over published calls): the type control becomes a
**market selector** that re-derives a leg of the chosen type for every
live game. λ-only scan (claims only, no outcomes, no ledger row).

**Feasible, ~1–1.5 days, from numbers already stored and served.** Every
tip row already carries the model's view behind the call (B22:
`p_home/p_draw/p_away`, the three double-chance sums, both +1.5
marginals), so the derived leg is arithmetic over fields the endpoint
already fetches. Derived-leg claims (published call kept where its type is
selected, else the likeliest option of the type):

| type | leg claims p25/50/75 | > 0.85 | Sat top-2 | top-3 | top-5 | top-10 |
| --- | --- | --- | --- | --- | --- | --- |
| Straight wins | 0.402 / 0.447 / 0.507 | 0.2% | 0.441 | 0.263 | 0.084 | 0.003 |
| Double chance | 0.730 / 0.745 / 0.766 | 4.7% | 0.738 | 0.605 | 0.387 | 0.108 |
| Handicap +1.5 | 0.734 / 0.783 / 0.816 | 2.4% | 0.718 | 0.602 | 0.418 | 0.156 |

The feared near-certainty flood does not happen — most games are close, so
the derived double chance sits ~0.74; a 0.85 ceiling veto would drop 0.0%
of double-chance games and 2.4% of handicap games (nearly moot). A
straight-wins parlay is honest and brutal: a double claims 44%, a treble
26% — `below_even` will be on almost always, correctly.

**The one real cost: a derived leg is not a published call.** It is not
graded — the record grades `tips.side` and nothing else, one call per
fixture — so the page's core sentence ("every leg is one of today's
published calls") no longer holds for narrowed selections and the legs
must say so (the B22 pattern: shown as what it is). Existing calibration
evidence is directionally comforting (favourites under-claim by up to 5.9
pts §1.10; `1X` +1.07 ✱; `dog +1.5` +0.32; the one over-claimer is `12`
at −0.75 ✱) but was measured on *published* populations — a derived-leg
population is a different selection, so a **pre-registered
0-configuration probe** (claimed vs delivered per derived type, slip
products under the new leg rule, planted control) goes before the ship,
exactly as row 113 did for the published-call product. Row 113 stays
valid for the default view.

**Decisions this needs:**

- **D12 — semantics**: per game, the **published call when its type is
  selected** (it is the graded one), else the likeliest option among the
  selected types. With all three types on this reproduces today's page
  exactly — the default is unchanged; only narrowed selections change
  meaning. Recommended.
- **D13 — near-certainties**: (a) **no veto — every live game appears**
  (recommended; it is the behaviour the owner asked for, and only ~5% of
  double-chance legs would show above 0.85), or (b) the rule's 0.85
  ceiling as a veto, which drops almost nothing but reproduces the
  complaint on the rare lopsided game.
- **D14 — labelling**: derived legs carry a "not our call" tag naming the
  published call beside it, and §5's copy becomes "legs marked as our
  call are graded on the record; the rest are the model's view of the
  market you chose, and are not graded". Not optional; the wording is the
  owner's.

Unchanged: the record, the rule, the schema, the slider/risk/below-even
machinery, and probe row 113 for the default view.

### Pre-registration — `probe:b24_market_legs`, written 2026-09-04 before the run

Owner decision (same day): **D12–D14 as recommended.** Before the build,
the derived legs' honesty is measured on the dev corpus — the populations
differ from the published ones every prior number was read on.

- **The leg, per type t** (the D12 rule, fav-relative for the handicap):
  the published call where its group is t, else the likeliest option of t
  — favourite for `win`; argmax of `1X`/`X2`/`12` (ties to the earlier)
  for `dc`; the underdog +1.5 (`D+1.5`) for `ah`. D13: no veto.
- **Statistics**: per type, delivered − claimed over all legs and over the
  **derived-only** subset (the new population), `bootstrap.paired` on
  ISO-week blocks; a 0.1-bucket table (n ≥ 300) reported, not verdicted;
  and per-type matchday slip products (top-k by claim, k ∈ {2, 3, 5, 10},
  pooled and Saturdays) — realised vs product, the row-113 statistic on
  the new legs.
- **Controls (convention 8)**: the row-113 dependent pair must fire
  positive on the products, and a planted **+5-pt shift** of every claim
  must read a resolved *negative* calibration gap, or the instrument
  cannot see over-claiming and the table is not a result.
- **Predictions**: **M1** `win` legs deliver above their claims — pooled
  gap in **[+0.5, +5.0] pts, resolved positive** (§1.10: the head
  under-claims its favourites by up to 5.9 pts; most derived win legs are
  favourites below the floor). **M2** `dc` legs in **[−1.0, +2.0]** (`1X`
  under-claims +1.07 ✱, `12` over-claims −0.75 ✱; the argmax mixes them).
  **M3** `ah` legs in **[−1.0, +1.5]** (published `D+1.5` +0.32; the
  below-0.70 region is the unmeasured part). **M4** no per-type slip
  product at k ∈ {2, 3} reads a resolved negative. **M5** both controls
  fire. A resolved negative on M2/M3, or M4, is the finding and adds the
  pre-registered consequence: an offset on the shown claim or a veto on
  that type's derived legs.
- **Cost**: 0 configurations, one probe row (re-aggregates outcomes read
  for rows 110/113). Code `engine/eval/b24_market.py`, tests
  `tests/test_b24_market.py` (planted), results
  `docs/b24_market_results.json`; authority machine, ledger re-exported.

### §9 result and build — **MEASURED AND BUILT 2026-09-04**

Ledger row **114** `probe:b24_market_legs`, **0 configurations —
114 / 71 / 202**, ledger re-exported, `--check` clean; results
`docs/b24_market_results.json`, code `engine/eval/b24_market.py`, tests
`tests/test_b24_market.py` (4, planted). **All three planted +5-pt
over-claim controls fired** (−4.4 to −5.2 ✱), so the calibrated verdicts
are results. **M2–M5 held; M1 missed benignly**: the win legs are
*calibrated* rather than under-claiming (+0.61 [−0.20, +1.37], derived-only
+0.14) — the §1.10 favourite under-confidence did not carry to this
population, the third time a mechanism carried across populations has
failed, this time in the harmless direction. No cell resolves negative:
dc all-legs −0.23, derived-only −0.61 [−1.35, +0.15]; ah all-legs −0.09,
derived-only −0.81 [−2.08, +0.38]; slip products at k = 2/3 read no
resolved negative (win k = 2 under-claims resolved, +4.6 ✱, the safe
direction). **The weakest region, recorded**: derived +1.5 legs claiming
under 0.70 over-claim by 2–4.5 pts in the point estimate (n 459–1,724,
unresolved). **No pre-registered consequence fires** — no offset, no
per-type veto.

**Built the same day** (D12–D14 as recommended): `derive_leg` +
`parse_sides` returning group keys in `engine/serve/parlay.py` — the
published call whenever its type is chosen (it outranks even a likelier
option of another chosen type, pinned by test), else the likeliest option
of the chosen types, the +1.5 always the underdog's; a row missing its
model view grows no leg. Every live game is the pool now, so the slider
runs to the whole matchday for any selection. The page marks derived legs
"Not our call · ours: {phrase}" (D14) and the honesty copy says only
published calls are graded; scarcity sentences now count games, not
calls. With all three types on, the leg rule reproduces the published tip
list exactly — the default view is unchanged, pinned by test. Verified:
**673 pass** (full suite), 25 web tests, build clean, 22-check Playwright
click-through on a seeded `bvp_scratch` (a ten-favourite slip reads
"about 1 in 3,840", nine marks, no game dropped; dropped after).
