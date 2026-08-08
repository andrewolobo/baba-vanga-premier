# BACKLOG

Trackable work for the tipster product. Product definition and the open design
questions are in `PRODUCT.md`; measurement history and conventions are in
`OUTSTANDING.md`.

**Status values:** `open` · `blocked` · `in progress` · `done` · `dropped`.
**Cost** is in gate-ledger configurations, which is the budget that matters
(`DEFLATION.md`). Anything reading match outcomes spends; anything reading only
prices or λ coverage does not.

Last updated **2026-08-06**.

---

## Now

| id | item | status | cost | depends on |
| --- | --- | --- | --- | --- |
| **B0** | Selection rule — **probability ceiling, as a veto not a selector** | **done** 2026-08-06 | 0 | — |
| **B2** | Fix the under-confidence (recalibration) | **done — mostly null** | 2 spent | — |
| **B3** | Double chance below a threshold | **done** — floor **0.55**, `12` on | 4 spent | B0 |
| **B8** | Ship the B3 rule into `serve/tips.py` | **done** 2026-08-06 | 0 | — |
| **B1** | Agreement filter: tip only when model and market name the same side | open, **deprioritised** | ~2 | — |
| **B4** | Extend over/under to lines 0.5–5.5 | open | ~4 | B0 (now unblocked) |

## Later

| id | item | status | cost | depends on |
| --- | --- | --- | --- | --- |
| B5 | Acquire prices for goal lines other than 2.5 | open | 0 (acquisition) | — |
| **B6** | Customer-facing surface for the tip list | **done** 2026-08-07 | 0 | B0 |
| **B7** | Honesty check on how the strike rate is reported downstream | **part done** — see below | 0 | B6 |
| **B9** | **Best-price execution — is it reachable?** | **scheduled: after B8 ships and a full season of tips is graded** | 0 (not modelling) | B8 |

## Scheduled, not now

**B9 — best-price execution.** The only measured edge the P5 line produced
(`META.md` §8): +0.00397 CLV per leg above the vig, clearing in all four
divisions, surviving the removal of every sub-1-overround match. It is **not a
modelling question** and no further gate will advance it. What it needs is:

1. a live multi-book odds feed (the corpus carries Max only after the fact);
2. accounts at enough books to take an outlier price;
3. evidence that the price survives long enough to bet, and that stake is not
   cut once it is used.

**Deliberately deferred until B8 has shipped and one season of tips is graded.**
Two reasons. The tipster product is the decided direction and needs no
best-price capture to work — it is sold on strike rate, and `engine/eval/tips.py`
shows return is not a supportable claim at any price level. And the honest
version of B9 starts with live price capture rather than analysis, which is
weeks of feed work that would stall the product for a question about a different
business (`OUTSTANDING.md` §3.4's fork).

**Revisit trigger:** a graded season of tips exists, *or* the tipster product is
abandoned. Not sooner.

---

## B0 — Decide the selection rule **(blocking)**

**Why it blocks.** Measured on 19,884 matches: if the app recommends the
likeliest item on the full menu, it says *under 5.5* in 74.2% of matches and
*over 0.5* in the other 25.8%, and **nothing else, ever**. Excellent strike rate,
worthless product. `PRODUCT.md` §3 has the table and the three candidate rules.

**Recommendation: the probability ceiling.** It is the only one of the three that
applies to the five unpriced goal lines, it is price-free in a product
deliberately built to ignore price, and it is one number to measure rather than a
policy to assert.

**This is not a modelling decision and no measurement will make it.** B3 and B4
are both special cases of it and cannot be specified until it is settled.

## B1 — Agreement filter

Tip only where the model's favourite and the market's favourite are the same
side and both clear the bar. The two agree on **86.6%** of matches, so there is
real disagreement at threshold 0.55 to act on, and the hypothesis is clean:
disagreement marks an unreliable pick.

**What is already known.** Backing the market favourite alone gives **66.5%**
strike on **4,062** tips against the model's **65.5%** on **3,307** — better and
higher volume. So the honest arms are three, not two: model-only, market-only,
and agreement.

**Expect it to trade volume for strike rate**, which may be the wrong trade at
7.9 tips/week. Pre-register what a win looks like before running it, including
the minimum volume that is still a product.

**Watch for:** the tip population resolves roughly **1.5 points** of strike rate
(n ≈ 3,300 at 65%). An improvement smaller than that is not measurable here, and
a grid over thresholds × arms will find one by chance if allowed to.

## B2 — Fix the under-confidence — **MEASURED 2026-08-06, mostly null**

Code `engine/eval/selection.py`, results `docs/selection_results.json`, ledger
`b2_b3_selection`. Walk-forward pooled vector scaling, 3-season burn-in, on
15,824 out-of-sample matches.

**It fixes the tail and nothing else.** The top bucket went from under-confident
(claims 76.4%, delivers 81.8%) to **calibrated** (claims 77.0%, delivers 78.8%).
The [0.55, 0.60) bucket is **unchanged and still under-confident** — 57.2%
claimed against 60.4% delivered, before and after.

**The volume it was built for did not arrive: +2.8%, against a pre-registered
prediction of more than 20%.** Strike rate at the shipped threshold moved
66.4% → 66.1%.

Why: vector scaling has five parameters fitted to the overall likelihood across
all three classes, so it is dominated by the bulk of the distribution rather
than by the top end that decides tipping. It is the right shape for the defect
and the wrong loss for the objective.

**Do not re-litigate with isotonic regression or a per-division fit** before
reading B3 — the volume problem B2 existed to solve is solved an order of
magnitude better there, and a better calibration would be optimising a
constraint that is no longer binding.

## B2 (original scoping note)

The head systematically understates its own favourites, in every probability
bucket, by up to **5.9 points** (claims 76.1%, delivers 82.0% ± 3.3). This is a
real property of an independent-Poisson 1X2 fit, not noise.

**Correcting it raises volume, not strike rate.** Fixtures currently sitting at
0.53–0.55 move above the bar; the ones already above it do not become likelier to
win. At ~7.9 tips/week volume is plausibly the binding constraint, so this is
the higher-value of B1 and B2.

**Do not confuse this with P3 calibration.** That fitted a Platt/vector scaling
to improve *log loss* for a betting rule and came back null (`CALIBRATION.md`).
This is a different target — the accuracy of the top-end probability that decides
whether a fixture is tipped — and the P3 null does not settle it. Say so in the
pre-registration, or the ledger will look like a re-litigation.

**Check before building:** whether the under-confidence survives on the *union*
`p_h + p_d`, since B3 depends on that number rather than on the outright.

## B3 — Double chance below a threshold — **MEASURED 2026-08-06**

Rule as `PRODUCT.md` §3a, ceiling 0.85, on 15,824 out-of-sample matches. **Every
match gets a recommendation**, so coverage is 100% at every floor.

| floor | double chance | **strike rate** | 95% block CI |
| --- | --- | --- | --- |
| 0.45 | 51.4% | 61.7% | [61.0, 62.4] |
| 0.50 | 72.6% | **67.6%** | [66.9, 68.3] |
| 0.55 | 85.6% | **70.8%** | [70.1, 71.5] |
| 0.60 | 92.4% | **72.3%** | [71.6, 73.0] |
| — | outright only, no fallback | **47.3%** | — |

**This is the finding, and it reorders the backlog.** The shipped tip rule
covers **14.4%** of matches at **65.5%**. The B3 rule covers **100%** at
**67.6%** (floor 0.50) or **70.8%** (floor 0.55). That is roughly **seven times
the volume at a higher strike rate** — and volume was the binding product
constraint B2 was built to relieve by 2.8%.

**Calibration barely touches it**: 67.6% raw against 68.0% calibrated at floor
0.50. B3 works on the raw pmf, so it does not wait on B2.

### DECIDED 2026-08-06 — floor **0.55**, and `12` is on the menu

Re-measured with `12` (home or away, i.e. "not a draw") enabled. Strike rate at
floor 0.55 rises **70.8% → 72.5%**, and the published mix becomes:

| market | share of all recommendations |
| --- | --- |
| **12** | **65.0%** |
| 1X | 17.6% |
| H | 11.8% |
| X2 | 3.0% |
| A | 2.5% |

**`12` takes two thirds of the product, and that is arithmetic rather than a
quirk.** `1X` beats `12` only when `p_draw > p_away`, and `X2` only when
`p_draw > p_home` — both need a draw likelier than a result, which is rarest in
exactly the population that reaches the fallback, because a weak outright means
a live opponent. `recommend()` documents this and a test pins it.

**Worth stating plainly before launch:** at this setting the product names a
team in **14.3%** of matches and says "it won't be a draw" in 65%. The strike
rate is real and the highest measured, and `12` is the least specific
recommendation available. That trade is the owner's and is recorded here.

The original trade-off the floor was picked from (without `12`): a higher floor
hedges more often and is right more often; at 0.45 the mix is balanced and the
strike rate is 61.7%.

**Pre-registered prediction 4 was wrong**: floor 0.50 was predicted to clear
70% and delivered 67.6%. Floor 0.55 clears it. Prediction 5 (monotone in floor)
held, and is asserted in `tests/test_selection.py`.

## B8 — Ship the B3 rule — **DONE 2026-08-06**

`engine/serve/tips.py` publishes `confidence-v2`: floor 0.55, ceiling 0.85, `12`
enabled. Migration `004_tips_double_chance.sql` rebuilds `tips` for the wider
`side` CHECK and splits `threshold` into `floor` + `ceiling`.
`csv_grader.settle_tips` settles all five markets through `selection._won`, so
the number the gate measured and the number the product settles cannot drift.
Double-chance prices are derived as `1/(1/o_h + 1/o_d)` and labelled an **upper
bound** — real double-chance markets carry their own margin.

**Two bugs the wiring surfaced, both from v2 covering 100% of fixtures where v1
covered 14.4%:**

- **`step_grade` chased results for unplayed fixtures.** Every future fixture
  now carries an unsettled tip from the moment it is priced, so without a date
  bound the cycle would pull a results CSV for every division with an upcoming
  match, every run, all season. Fixed with `match_date <= date('now')`; a test
  fails if it regresses.
- **`settle_tips` used `csv_grader._won`, which only knows single outcomes.**
  A `1X` tip would have settled as a loss on a draw. Now routed through
  `selection._won`.

**Not done:** nothing reads the `tips` table for a customer (B6), and no check
exists that the strike rate is reported honestly downstream (B7).

## B3 (original scoping note)

**Measurable now, and worth folding into the same gate:** realised 1X/X2 strike
rate at each candidate T; how often double chance displaces an outright, per
division; and whether the head is calibrated on the union rather than the
outright.

**No double-chance prices exist**, but they are derivable from 1X2 as
`1/(1/o_h + 1/o_d)`. Real double-chance markets carry their own margin and are
usually worse than that combination, so a derived price is an **upper bound** on
what a customer could get — the safe direction, and it must be labelled.

## B4 — Extend over/under to 0.5–5.5 **(blocked by B0)**

Every probability is already computable: `over_under_probs(joint, line=…)` takes
any line and `score_matrix` gives the joint. No new model, no new fit, no new
data.

**The constraint is prices, not probabilities.** The schema carries Over/Under
**2.5 only**. On the other five lines the app can predict but cannot measure
itself — no return, no CLV, no market comparison. Since the product is sold on
strike rate, which needs only the result, that is survivable; it must be recorded
because every honesty check built so far leans on having a price.

**This is where the model earns its keep**, and the only place identified so far
that it does: it can rank a line before a price exists, which reading the odds
cannot.

## B5 — Prices for goal lines other than 2.5

Unblocks measurement for B4 and would let the whole menu be graded on the same
footing. football-data.co.uk's main files carry 2.5 only. **Do not reopen the
FBref route** — `OUTSTANDING.md` §1.8 verified it carries no xG and was shelved,
and it carries no odds at all.

## B6 — The surface — **DONE 2026-08-07**

Built to `docs/ui/Baba Vanga.dc.html`, the owner's design. `api/main.py` gains
`/tips`, `/tips/results` and `/tips/record`; `web/` is rebuilt around them as a
one-page tipster site with the internal `/book` and `/performance` views kept
behind footer links.

**Four things the design asked for that the data cannot support, and what
shipped instead.** Recorded because the mockup is still in the repo and someone
will otherwise try to build them again:

| mockup element | why not | shipped instead |
| --- | --- | --- |
| "+41.6u level-stakes profit", "9 green weeks in a row" | `engine/eval/tips.py` measures return as unsupportable at every sellable setting | strike rate, calls graded, calls live, matchweeks graded |
| "Bet of the week", "Model edge +14.2%", "Add to slip" | that is `book.py`'s **value** rule, measured null and switched off (`CALIBRATION.md` §5) | dropped |
| predicted scoreline ("called 2–0 · ft 3–0") | modal scorelines are not served, FT scores of graded fixtures are **stored nowhere**, and a modal score can contradict the call | outcome only on the result cards |
| league table | no standings in the schema or API at any point | dropped |

Two more corrections to the mockup. Its league tabs read *Premier League ·
League One · League Two · National League*; the served set is **E0–E3**, so
Championship was missing and National League is not served at all. And its
subhead promised "no hedging, no fence-sitting", which is the opposite of what
the rule does in 85.6% of matches — replaced with copy that says so.

**Club badges are generated, not real.** Nothing carries club identity beyond a
name, so `web/src/lib/badge.js` derives a three-letter code and picks a
decorative colour from a fixed palette. They are not crest colours and must not
be presented as them; the full club name renders beside every badge, which is
what keeps an imperfect code cosmetic. Real colours, if ever acquired, belong in
`reference/` keyed by canonical_name.

## B7 — The honesty check — **PART DONE 2026-08-07**

**What is enforced.** `/tips/record` returns strike rate, counts and coverage
and **no P&L at all**, even though `tips.pnl_best` and `tips.pnl_avg` exist and
are populated. Leaving profit off the wire means a surface cannot advertise a
return by accident rather than by decision. `test_the_record_publishes_no_profit_figure`
fails if any field whose name contains pnl/profit/roi/units/yield reaches the
payload, and the response carries `return_supported: false` explicitly. The page
states in two places that strike rate is not a return.

`strike_rate` is **null, never zero**, until something is graded, and every
headline tile falls back to an em dash rather than to `0` — a fresh install
otherwise renders "0 calls graded" beside a blank strike rate, which reads as a
record rather than as the absence of one.

**What is still open.** No check that the *published* strike rate matches what
`engine/eval/tips.py` measures out of sample — the site reports the live graded
population, which will be small and noisy for most of a first season, and
nothing stops the two being quoted interchangeably. `OUTSTANDING.md` §1.10
records that the regulatory exposure is the owner's and is flagged.

---

## Done

| id | item | where |
| --- | --- | --- |
| — | Tip rule, published and settled by the serving cycle | `OUTSTANDING.md` §1.10 |
| — | Strike rate / volume / return measured over 11 seasons | `engine/eval/tips.py` |
| — | Meta-label on the football model — measured, do not adopt | `META.md` |
