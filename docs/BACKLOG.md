# BACKLOG

Trackable work for the tipster product. Product definition and the open design
questions are in `PRODUCT.md`; measurement history and conventions are in
`OUTSTANDING.md`.

**Status values:** `open` · `blocked` · `in progress` · `done` · `dropped`.
**Cost** is in gate-ledger configurations, which is the budget that matters
(`DEFLATION.md`). Anything reading match outcomes spends; anything reading only
prices or λ coverage does not.

Last updated **2026-08-16**, after **P7 ran** (`P7_TIPSTER_PLAN.md` →
`TIPSTER.md`; ledger rows 105–108, **197 → 201 configurations**). **B7 closes**:
the shipped v2 rule loses **−4.56% [−5.56, −3.60]** at average derived prices
and returns **+0.11% [−0.94, +1.10]** at best — the site's no-return claim now
rests on the rule that ships. **B11 measured**: E0 is calibrated at every goal
line; **E1–E3 over-claim their confident unders by 4–9 pts**, worst on the 2.5
line — a third lower-division-only defect on this head. **B4 probed**: the
third-tier shape never fires, the specificity shape is the refuted
ceiling-as-selector, and a separate goals call is "over 1.5 / under 3.5" in
78–90% of matches; **recommendation is not to extend the menu on this head** —
**owner closed B4 the same day**. Free finding: the v2 rule agrees with the same rule on
the market's probabilities in only **63.5%** of matches and returns ~0.5 pts
less, unresolved. B1's arms need re-stating on v2.

Before that, **2026-08-15**, closing **B13 (declined — raw pmf stays)** and
**B16** — `/tips/record` now scopes its
headline and `by_division` to the newest published `rule_version` and reports
every version in `by_rule`; the page renders the per-version table only once a
second version exists. Two owner decisions taken the same day: the headline is
**per version, with history**, and re-tipping a fixture under a new version
stays **allowed, per the schema** — so `RUNBOOK.md` §0 now says not to bump and
re-run on one matchday. Also the same day: `engine/eval/tips.py` was found
un-importable since B8 (it named `DEFAULT_THRESHOLD`; fixed, and a test now
imports it) and its docstring corrected — **it measures the v1 outright rule;
the shipped v2 rule's return has never been measured**, which is B7's open gap.

Before that, earlier on **2026-08-15**, opening **B16** — the published strike
rate pools every `rule_version`, so the protection `run_cycle.py` promises
against mixing two products under one number is not actually implemented. Found
while tracing why the 2026-08-14 tip was ungraded (it is not related:
football-data has not published the 2026-27 files yet). No status changed.

Before that, **2026-08-12**, after **B14 was measured in strike rate and
closed** — the corners channel is worth **−0.095 [−0.352, +0.175]** points to
the product, an unresolved *negative*, against a blind control at −1.643 ✱ on
the identical change rate. **Do not adopt.** The same run found that what costs
strike rate is the published *mix*, not the change rate, which is free evidence
for **B10** and **B13**. Before that, **2026-08-12**, the honesty gap in
`home_term --step 3` gained a block-bootstrap interval: **both B13 arms are
unresolved and overlap**, so honesty is neutral to that decision.

Before that, **2026-08-11**, after the selection-objective review
(`SELECTION_OBJECTIVE.md`, `OUTSTANDING.md` §9.8), which opened **B15** and
changed no status. Before that, the separation-slope review
(`SEPARATION_SLOPE.md`, `OUTSTANDING.md` §9.7), which added a consideration to
**B13** and did not change any status. Before that, **2026-08-10**, after the
B12 channels gate (`OUTSTANDING.md`
§1.12) closed the highest-value open modelling item and opened B14, the owner
decision on whether to adopt it. Before that, the tipster re-review
(`OUTSTANDING.md` §9) and the draw-mass diagnostic (§9.5), which added B10–B12
and gated B4.

---

## Now

| id | item | status | cost | depends on |
| --- | --- | --- | --- | --- |
| **B0** | Selection rule — **probability ceiling, as a veto not a selector** | **done** 2026-08-06 | 0 | — |
| **B2** | Fix the under-confidence (recalibration) | **done — mostly null** | 2 spent | — |
| **B3** | Double chance below a threshold | **done** — floor **0.55**, `12` on | 4 spent | B0 |
| **B8** | Ship the B3 rule into `serve/tips.py` | **done** 2026-08-06 | 0 | — |
| **B1** | Agreement filter: tip only when model and market name the same side | open, **deprioritised** — re-scope on v2: agreement is 63.5%, not 86.6% (`TIPSTER.md` A) | ~2 | — |
| **B4** | Extend over/under to lines 0.5–5.5 | **closed 2026-08-16 — measured, do not extend on this head** (`TIPSTER.md` C); owner decision | 0 spent | B11 |
| **B10** | `12`-versus-`1X` ordering | open, **downgraded** — §9.6 | ~3 | — |
| **B11** | Per-line calibration for the six goal lines | **measured 2026-08-16** — E0 calibrated; E1–E3 over-claim confident unders 4–9 pts (`TIPSTER.md` B) | 0 spent | — |
| **B12** | Shots + corners channel gate (§1.7, licensed and unwritten) | **done — measured 2026-08-10, not adopted** | 13 spent | — |
| **B13** | Owner call: run the tip rule on B2's calibrated probabilities? | **declined** 2026-08-15 — keep raw pmf | 0 | — |
| **B14** | Owner call: adopt the corners channel into the head? | **closed 2026-08-12 — do not adopt.** Null in strike rate | 3 spent | B12 |
| **B15** | Half-life `H` — stale, and the one axis where the objectives disagree | open, **gated on paired ll_1x2 intervals** | ~0–1 then ~9 | — |
| **B17** | Lower-division totals — dispersion or level? diagnostic on stored λ | **measured 2026-08-16** — conditional level: totals over-spread in E1–E3, overall level ≈ 0 (`TIPSTER.md` B17) | 0 spent | — |
| **B18** | Totals-axis shrink, per division (the fix B17 implies) | **open, gated on B4 reopening** — worth nothing to the shipped product | ~1–2 | B17 |
| **B19** | Separate ridge on the sum and difference of `att`/`dfn` — margins under-spread, totals over-spread on one penalty | **open — owner decision to scope**; P1-scale | ~4–8 | B17, §9.12 |

## Later

| id | item | status | cost | depends on |
| --- | --- | --- | --- | --- |
| B5 | Acquire prices for goal lines other than 2.5 | open | 0 (acquisition) | — |
| **B6** | Customer-facing surface for the tip list | **done** 2026-08-07 | 0 | B0 |
| **B7** | Honesty check on how the strike rate is reported downstream | **done 2026-08-16** — v2 return measured, −4.56% ✱ at avg / ~0 at best (`TIPSTER.md` A) | 4 spent | B6 |
| **B16** | `/tips/record` pools every `rule_version` under one strike rate | **done** 2026-08-15 — per-version headline, `by_rule` history | 0 | B7 |
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

> **The union question went unanswered for four days and is now closed —
> `OUTSTANDING.md` §9.5.** Neither B2 nor B3 delivered it despite both scoping
> notes asking for it; the only calibration table either produced was on the
> 1X2 `argmax`. Measured 2026-08-10: **`12` over-confident −0.75 [−1.43, −0.02],
> `1X` under-confident +1.07 [+0.37, +1.78], `X2` calibrated.** The head is
> *not* calibrated on the union, the two largest markets are wrong in opposite
> directions, and that is B10.

**No double-chance prices exist**, but they are derivable from 1X2 as
`1/(1/o_h + 1/o_d)`. Real double-chance markets carry their own margin and are
usually worse than that combination, so a derived price is an **upper bound** on
what a customer could get — the safe direction, and it must be labelled.

## B4 — Extend over/under to 0.5–5.5 — **CLOSED 2026-08-16: do not extend on this head**

**Owner decision 2026-08-16**, on the probe below. The product stays 1X2 +
double chance. C′ never runs. Revisit only if the head changes in a way that
moves `TIPSTER.md` Part B or Part C — B17 is the item that could.

`TIPSTER.md` Part C, `probe:p7_menu_shapes`, 0 configurations. Three shapes on
a ceiling grid at the shipped floor: the third-tier fallback **fires in 0.00%**
of matches; specificity-wins is the ceiling-as-selector (line in 71%, team in
14.4%); a separate goals call is **over 1.5 / under 3.5 in 78–90%** and picks
the priced 2.5 line in ≤ 8%. A fourth shape — a fixed 2.5-line call — lands on
the line B11 found worst-calibrated outside E0 at ~55% strike. **Owner decision
pending; C′ (strike gate on a chosen shape) is not scheduled.** The modelling
item that has to come first is B11's lower-division finding. Original note:


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

## B10 — `12` versus `1X`, the defect §9.5 actually found

**This is the highest-value open modelling item, and it is not the one anyone
was looking for.** `OUTSTANDING.md` §9.5 decomposed the served head's 1X2 vector
for the first time. Delivered minus claimed, pooled, on 15,824 out-of-sample
matches:

| outcome | gap | resolves? |
| --- | --- | --- |
| home | +0.33 | no |
| draw | +0.75 | yes |
| **away** | **−1.07** | **yes** |

The away win is over-predicted and it is the largest miscalibration the head
has. It lands squarely on the product: **`12` = home + away carries it in full
and is 65.0% of output**, measured over-confident at −0.75 [−1.43, −0.02];
**`1X` = home + draw carries the two under-predicted outcomes** and is
under-confident at +1.07 [+0.37, +1.78]. The rule picks between them on the
margin `p_d > p_a`.

**Why this is a real lead and not a restatement of B2.** B2 fitted vector
scaling to the 1X2 argmax and moved the top bucket only; the defect here is on
the away leg across the whole distribution, and it is invisible to a table built
on `argmax`. It is also invisible to goal Poisson deviance, which convention 2
selects on.

> **Updated 2026-08-10 by `OUTSTANDING.md` §9.6, and the lead is weaker than
> this section first claimed.** The indirect evidence used to be "every
> perturbation shifting `12` toward `1X` raised strike rate, including a planted
> ρ five times too large." **§9.6 step 3 refutes that reading**: B2's
> calibration shifts the same mix three times harder and returns **+0.088
> [−0.410, +0.556]**, unresolved. So the ordering is *not* demonstrably
> mispriced, and why §9.5's arms were monotone in |ρ| is unexplained.
>
> **What survives is the calibration fact itself** — `12` over-confident −0.75,
> `1X` under-confident +1.07, pooled — and the fact that **no correction tried
> so far improves strike rate**. Treat B10 as an open question about the
> *published claim*, not as a strike-rate opportunity. Anyone reopening it
> should read §9.6 first: three arms have now failed to move strike rate, and a
> fourth needs a reason the first three did not have.

**Pre-register before running**, and state what a win is including the minimum
volume that is still a product. The tip population resolves roughly 1.5 points
(B1's note), and §9.5's effects are a third of that, so **this needs a paired
comparison against the shipped rule, never a marginal one** — the marginal CIs
there were 2.4× wider and would have called every arm a null.

**Carry the control forward.** §9.5's lesson is that a planted arm must be able
to falsify the result you actually got, not only the one you feared. Any arm
that improves strike rate here needs a planted counterpart showing the gain does
not also arrive from an unrelated perturbation of the same size.

## B13 — Run the tip rule on calibrated probabilities? — **DECLINED 2026-08-15**

**Owner decision 2026-08-15: keep the raw pmf.** No strike-rate gain
(+0.088, unresolved), an E0 cost, and a `RULE_VERSION` bump the customer would
not notice. The mix argument (less `12`, more `1X`) is real and is B10's to
carry, not a calibration change's. Nothing measured; no ledger row. The
original note follows.


**Measured in `OUTSTANDING.md` §9.6 step 3, ledger `b2_calibration_in_product`.
No further measurement is needed and none should be spent.** B2's walk-forward
vector scaling already exists and is tested; the shipped rule does not use it,
because `tips.py` reads the raw pmf from `predictions`.

What switching to it does, on 15,824 out-of-sample matches:

| | raw (shipped) | B2 calibrated |
| --- | --- | --- |
| strike rate | 72.49% | 72.58% — **+0.088 [−0.410, +0.556]**, unresolved |
| coverage | 100% | 100% |
| honesty gap on the published pick | **−0.06 pts** | +0.50 pts |
| `12` share | **65.0%** | **47.7%** |
| `1X` share | 17.6% | 30.5% |
| recommendations changed | — | 18.42% |

**The trade, stated plainly.** It costs nothing in strike rate and nothing in
honesty, and it cuts the least specific recommendation the product makes from
two thirds of output to under half. Against that: it makes **E0's** home
calibration worse (+1.77 → +2.37) and breaks two pooled gaps that were fine
(home, `X2`) while fixing four that were not.

**This is the same trade B3 already made once**, in the other direction, when
`12` was switched on and the mix went to 65% — recorded there as the owner's
call. B13 is that decision offered again with a price attached, and the price is
approximately zero.

> **Added 2026-08-11 by `SEPARATION_SLOPE.md` §7 — one consideration this item
> did not carry.** The price is approximately zero *in strike rate*. What the
> change also does is alter **why** the published claim is honest. The −0.06 pt
> honesty gap on the raw arm is a **cancellation**: `12` = home + away carries
> §9.5's two opposite-signed legs (home +0.33, away −1.07 ✱) and nets them out,
> and `12` is 65% of output. Cutting it to 47.7% stops that cancelling, and the
> claim starts resting on the calibrated mapping instead — which still carries a
> **resolved separation slope in E3 (+12.13 ✱)**.
>
> This is not obviously an argument against B13: +0.50 is small and it is the
> conservative direction (the product would deliver more than it claims).
> **Neither honesty gap has a confidence interval** — `home_term.step3` computes
> the point estimate only — so "−0.06 versus +0.50" is a comparison of two
> unbounded numbers. Worth knowing before deciding, not worth a new gate.

## B15 — The half-life, and the only objective disagreement in the ledger

`OUTSTANDING.md` §9.8, full account in `SELECTION_OBJECTIVE.md`. **Two separate
problems that happen to share a parameter. Neither is the "objective-blindness"
the item was raised as.**

**Problem 1 — `H=400` is stale, on goal deviance, never mind anything else.**
h2 swept the half-life at **α=1.0**, an order of magnitude more shrinkage than
the α=0.1 finally chosen; h3 then swept α at H=400. The only joint check is
h4's four-point star. And **h2 has never been re-run since the sot channel
shipped** — `p1_results_shots_head.json` carries `base_score` and
`pooled_deficit` only. This is convention 9 for real, and it needs no new
objective to justify: adding a channel changes the information content, which
is exactly what a decay horizon trades against.

**Problem 2 — it is the one parameter where the two objectives disagree, and
they disagree by trading the served markets against each other.**

| | deviance | ll_1x2 | ll_ou25 |
| --- | --- | --- | --- |
| argmin (h2) | **400** | **300** | **650** |
| argmin (h2-guard) | 300 | 240 | 650 |

Moving H 400 → 300 buys **−0.00029** on 1X2 and costs **+0.00068** on O/U.
`H330/a0.05` buys −0.00096 and costs +0.00059. **Goal deviance is landing
between the two markets it induces, not blind to them.** Re-selecting on 1X2
alone is a decision to prefer one served market, which needs convention 2
amended — `OUTSTANDING.md` §9.4's problem, and an owner call.

**The precondition, and it blocks both.** **No hyperparameter arm anywhere
carries a paired interval on `ll_1x2`** — `sweep.py:177` bootstraps goal
deviance only, in both `run` and `compare`. Every 1X2 number above is a bare
point estimate. The machinery is already used at `p3.py:168`. Until that runs on
the h4 star and the h2 grid, **problem 2 may not exist at all.**

**Cost.** The interval work re-scores grids already in the ledger, so the
accounting is the same owner call `SEPARATION_SLOPE.md` §8 item 2 raises —
arguably 0, arguably 1. A real re-sweep of `H` on the served head is the
9-point grid.

**Do not** sweep `H` × α × `w` × EC jointly — 720 configurations against a
ledger of 189 — and do not touch α, either blend weight, or EC on objective
grounds: §9.8 measured all four and the objectives agree on every one.

**Read `SELECTION_OBJECTIVE.md` §4 before framing this as a fix for the
separation slope.** All four parameters move λ; the mapping is fixed at
`rho=0`. Three arms have already moved that mapping and none bought strike rate.

## B11 — Per-line calibration for the six goal lines — **MEASURED 2026-08-16**

`TIPSTER.md` Part B, `probe:p7_line_calibration` after a passing jittered-λ
control, 0 configurations (the pre-committed drop rule did not fire — one
bucket short on the 2.5 line). **E0 is calibrated at every line. E1–E3
over-claim their confident unders**: 2.5-line top bucket claims 63%, delivers
56.6 / 54.0 / 58.3 in E1 / E2 / E3; 3.5-line top bucket −4.1 / −5.7 / −4.7.
The 1X2 under-confidence signature does **not** carry to totals. Hypothesis
(0-configuration check available): lower-division totals are more dispersed
than the pooled P0-1 ratio of 1.013 and the joint fit's low-λ tail is too
thin there. Original note:


`OUTSTANDING.md` §9.2. B4 publishes over/under 0.5–5.5, and the pmf's fitness
for those lines rests on two P0 results that were scoped elsewhere: P0-1 closed
"keep Poisson" on a **variance ratio**, which describes the mode rather than the
tails, and P0-3's over-prediction caveat at \|margin\| ≥ 3 and ≥ 4 was filed as
an **Asian handicap** problem and deferred with AH.

P0-1 supplies the mechanism but **not** the magnitude: tail probabilities are
convex in λ, so estimation noise biases the extreme lines harder than the
central one. **How much noise the served λ carries is not measured anywhere** —
the sd 0.20 an earlier draft of this item quoted is a parameter of P0-1's
synthetic control, not a property of the head (`OUTSTANDING.md` §9.2's
correction). Since the five new lines are **unpriced**, claimed-versus-delivered
against the result is the only honesty instrument available for them, and it is
the only way to find out.

**Cheap: bucket by predicted probability at each of the six lines, per division,
on stored λs. No new fit, no new data.** Run it before B4 ships, not after.

## B12 — The shots + corners channel gate — **MEASURED 2026-08-10**

Results in `CHANNELS_GATE.md`, pre-registration `P4_CHANNELS_PLAN.md`,
`OUTSTANDING.md` §1.12. **Real, and half the size this item predicted.**

| arm | vs the shipped head | |
| --- | --- | --- |
| `+shots` | −0.00095 [−0.00143, −0.00048] | 4.0 SE |
| **`+corners`** | **−0.00196** [−0.00276, −0.00116] | 4.7 SE |
| **`+both`** | **−0.00217** [−0.00285, −0.00146] | 6.0 SE |
| `+noise ×2` (control) | +0.02101 | fails by 10× the effect |
| oracle ceiling | −0.00396 | the arm reaches 55% of it |

**Three things this item got wrong**, kept rather than reworded:

- **"The same order as the addition that became −0.00422 and shipped."** It is
  **51%** of it. The +0.0490/+0.0540 split-half gain does not map to deviance at
  the rate this section assumed, and `CHANNELS_GATE.md` §3 records that as the
  third instance of the same over-reading.
- **"Cost is 2 configurations."** Corrected below before the gate ran; it cost
  **13**, and three of its four rows ended up **post-hoc** because the positive
  control fired a stop rule on a mis-derived bar.
- **"A better λ improves every item on the menu at once."** True in principle
  and small in practice: 1X2 improves 0.00053 and O/U 2.5 improves 0.00074.

**What survives, and it is the useful part: corners is the channel, not shots.**
Corners is worth 2.1× shots, and shots on top of corners adds −0.00021 —
smaller than the paired SE. `goals + sot + corners` gets **90%** of the gain
with one fewer channel, and it is already measured as arm 4 of
`h39_channel_decomposition`, so adopting it needs no further gate. **B14.**

**Do not** re-litigate with per-channel weights, a per-side weight, fouls or
cards, or a joint α sweep. The ceiling is −0.00396 and 55% of it is banked.

## B14 — Adopt the corners channel? **(owner decision)**

**No further measurement is needed and none should be spent.** B12 measured
both candidate heads out of sample; what remains is a judgement about whether
the gain is worth a head change.

| | shipped | `+corners` | `+both` |
| --- | --- | --- | --- |
| goal deviance vs shipped | — | **−0.00196** | **−0.00217** |
| divisions resolving | — | — | 3 of 4 (E3 does not) |
| 1X2 / O/U 2.5 | — | −0.00033 / −0.00074 | −0.00053 / −0.00074 |
| pooled deficit to the market | +0.01230 | — | +0.01177 |
| new data required | — | none | none |

**The price is not the code, it is the five steps of `OUTSTANDING.md` §1.3.** A
head change retires `p1-3a38e9d6ef1ca7ee`, re-issues `BASELINE.md` §1–2,
restates `DEFLATION.md` §5 criterion 2, updates the share-of-market-edge table,
and **re-runs `engine/eval/tips.py`'s claims block — because the published
strike rate is a property of the head, not of the tip rule.** That last one
touches what the customer is told, so it is not a silent upgrade.

**Recommendation: `+corners` rather than `+both`.** It is 90% of the gain, one
fewer channel, and one fewer thing to be wrong about later. `+both` is better by
−0.00021, which nothing measured here resolves.

> **Amended 2026-08-12. "No further measurement is needed" was wrong, and the
> reason is the one §9.12 raised against itself.** Everything above prices the
> channel in **goal deviance**. The product is sold on **strike rate**, and
> nothing has ever measured what this channel does to it. B12's own
> product-facing numbers are 1X2 −0.00033 and O/U −0.00074 for `+corners` — an
> order of magnitude below the channel that shipped — so "a better λ improves
> every item on the menu" is true and may be far too small to see. Settling an
> owner decision on a currency the product does not sell is the same error
> `OUTSTANDING.md` §9.12 recorded when it noted that **nothing was measured in
> the product's currency**. The gate below fixes that.

### Pre-registration — B14 in the product's currency

**Written 2026-08-12, before `channels_product.py` ran.** Population: the
15,824 out-of-sample matches of §9.5/§9.6, floor 0.55 / ceiling 0.85, `12`
enabled. Ledger `b14_corners_in_product`, **3 configurations by owner
decision** — one per arm, the same accounting `home_term_away_leg` used.

**A free probe ran first and alone**, per §9.11's precedent, comparing the two
recommendation vectors to each other without scoring either against a result.
It could have closed B14 for nothing and did not:

| | shipped | `+corners` | `+both` |
| --- | --- | --- | --- |
| recommendations changed | — | **6.914%** | 6.566% |
| mean \|Δp_home\| | — | 0.01103 | 0.01006 |
| claimed strike rate | 72.553% | **72.550%** | 72.566% |
| mix `12`/`1X` | 65.0 / 17.6 | 65.5 / 16.9 | 65.7 / 16.5 |

Two things it fixed before they became mistakes. **The claim side does not
move** (−0.003 pts), so this is purely a question about delivery — unlike B13,
where the honesty gap moved because the *claim* fell. And **a change-rate
matched control cannot be built by tuning the blend weight**: at w = 0.02–0.05
the arm differs from the shipped head both by carrying noise and by having
almost no auxiliary layer, so the change rate sits at ~8.8% for every weight in
that range. The matched control has to be the temperature sham.

| arm | what it is |
| --- | --- |
| **A1 `+corners`** | `sot+corners` @ w = 0.30, the adoption candidate |
| **C1 sham** | `home_term.matched_sham` tuned to A1's change rate, blind to every outcome |
| **C2 `+noise1`** | `sot+noise1` @ w = 0.30 — structural parallel, carries no information |

**Two controls because they fail in different ways.** C1 matches the
product-visible magnitude but perturbs probabilities rather than strengths; C2
is the exact structural parallel — same code path, same weight, same channel
count — but changes **23.3%** of recommendations against A1's 6.9%, because a
real channel is coherent with the existing head and noise scatters.

**Resolution, anchored and not analogised.** §9.5's τ arm changed **6.29%** of
recommendations, within a point of A1, and returned a half-width of **±0.29
points**. That is what this instrument resolves at this change rate.

**Four predictions, declared now:**

1. A1's paired delta lands in **[−0.10, +0.35]** and **does not resolve**.
   `+corners` improves 1X2 log loss by 0.00033 nats; B2's vector scaling, fitted
   directly on 1X2, moved 18.42% of recommendations for **+0.088** unresolved.
2. **C1 does not gain.** §9.6 step 3 refuted "any perturbation of this size
   raises strike rate" — B2 shifted the mix three times harder for nothing.
3. **C2 loses and resolves.** B12 measured the noise channel ten times worse
   than the real effect on goal deviance.
4. A1 beats both controls on the point estimate.

**The read, fixed in advance:**

| outcome | conclusion |
| --- | --- |
| A1 excludes zero **and** exceeds C1 | **GO** — adoption has a product-currency justification |
| A1 does not resolve | **NO-GO** — real in nats, not adoptable on the metric the product is sold on. The §1.4 shape, with a number |
| C1 also gains and resolves | **VOID** — the instrument measures perturbation, not information. Report and conclude nothing |

**A NO-GO is the predicted outcome and is still worth 3 configurations**: it
converts B14 from a judgement call into a bounded answer in the currency that
decides it, and §1.4 and §1.6 are both precedents for a measured null being the
useful output. **It does not retract B12** — the deviance gain is real, resolved
at 4.7 paired SE, and would stand.

### Result — **MEASURED 2026-08-12. NO-GO.**

Code `engine/eval/channels_product.py`, tests `tests/test_channels_product.py`,
results `docs/channels_product_results.json`, ledger `b14_corners_in_product`
(gate, **3 configurations, 194 → 197**, verified with
`trials.count_configurations` after the run). **Four of four predictions right**,
which has not happened before on this project.

| arm | changed | strike | vs shipped, **paired** | claimed | mix `12`/`1X`/H |
| --- | --- | --- | --- | --- | --- |
| shipped | — | 72.491% | — | 72.553% | 65.0 / 17.6 / 11.8 |
| **A1 `+corners`** | 6.914% | 72.396% | **−0.095 [−0.352, +0.175]** | 72.550% | 65.5 / 16.9 / 12.1 |
| C1 sham | 6.914% | 70.848% | **−1.643 [−1.857, −1.429] ✱** | 72.526% | 63.7 / 12.7 / 17.8 |
| C2 `+noise1` | 23.275% | 71.752% | **−0.739 [−1.220, −0.256] ✱** | 72.391% | 60.4 / 18.6 / 13.7 |

**The corners channel is worth nothing to the product, and the point estimate is
negative.** It does not resolve, so the honest statement is that its strike-rate
value is bounded within roughly ±0.35 points of zero.

**Four things worth carrying forward:**

- **This is a real null, not a dead instrument.** C1 moves the *same* 6.914% of
  recommendations and loses **1.643 points, resolved** — seventeen times what
  the real channel moved. The rule is highly sensitive to a perturbation of this
  size; corners simply is not one.
- **Change rate does not drive the damage — the published mix does, and this was
  free.** C1 changes 6.9% and loses 1.643; C2 changes **23.3%**, 3.4× as many,
  and loses only 0.739. The difference is where each pushes the mix: C1 is a
  sharpener and takes **H from 11.8% to 17.8%**, naming a team far more often,
  while C2 stays near the shipped shape. **Naming teams costs strike rate**,
  which is independent evidence on the `12`-versus-`1X` axis of **B10** and
  **B13**, arriving from a gate that was not about them.
- **§9.3's argument for this channel does not survive its own test.** It reads
  *"a better λ improves every item on the menu at once… the largest measured
  prediction gain available to the product"*. The first clause is true in
  deviance and the second is now measured at **−0.095 points, unresolved**. The
  step from "better λ" to "better product" had never been checked, and it is the
  same shape as the reliability→deviance over-reading `CHANNELS_GATE.md` §3
  records three times.
- **Deviance and strike rate rank the divisions differently.** B12 had E0
  resolved at −0.00223 and E3 weakest; here **E0 is the best cell (+0.509
  [−0.036, +1.082]) and E2/E3 are negative**. Nothing resolves and Bonferroni
  across four cells would remove anything that did, so this is a caution rather
  than a finding: **do not assume the deviance division profile transfers.**

**The published claim is untouched either way** — honesty gap −0.06 [−0.80,
+0.67] shipped against −0.15 [−0.87, +0.57] for A1.

**B14 settles: do not adopt.** Not because the channel is not real — B12 stands,
resolved at 4.7 paired SE — but because it buys nothing in the currency the
product is sold on, and adoption costs the five steps of `OUTSTANDING.md` §1.3
plus the `travel.HEAD` re-basing that §1.3 does not list. **This is the §1.4
shape for the third time**: real, measured, and not adoptable.

**`+both` was not measured in strike rate** and should not be. It changes 6.566%
of recommendations against A1's 6.914% and is a strictly larger head change for
a deviance difference of −0.00021 that nothing resolves.

## B17 — Lower-division totals: dispersion or level? — **MEASURED 2026-08-16**

Row 109, 0 configurations, `TIPSTER.md` "B17 follow-up". P1–P3 held; the
mechanical reading is LEVEL, and the tables refine it: **overall level is
zero in every division; the defect is conditional** — the pmf's totals are
too extreme in E1–E3 (+0.2–0.3 goals where it expects few, −0.55 where it
expects many). Regression to the mean on the totals axis; the margin axis is
under-spread (§9.12). A per-division intercept would fix nothing. Follow-ups
**B18** (totals shrink, gated on B4) and **B19** (separate sum/difference
penalty — the head-level question). Original pre-registration:


Opened 2026-08-16 from `TIPSTER.md` Part B. E0 is calibrated at every goal
line; E1–E3 over-claim their confident *unders* by 4–9 pts, worst on 2.5.
Before any fix is pre-registered, the mechanism has to be known, and it is
knowable for nothing.

**Two mechanisms, different fixes.**
- **Dispersion.** Lower-division totals are more variable than the pmf's
  independent Poisson (P0-1's ratio of 1.013 was pooled). Fix would be a
  per-division dispersion term or a negative-binomial head — a model change.
- **Level.** The joint fit's single intercept under-states lower-division
  scoring in low-λ fixtures; the pmf is centred low, not thin. Fix would be a
  per-division intercept — cheap, and OPEN-3-shaped.

**Diagnostic, per division, on the stored walk-forward λ (no refit):**
1. variance ratio `var(total) / mean(total)` and `var(total) / E[var under
   Poisson(λ_h+λ_a)]`, with block-bootstrap CI;
2. mean residual `total − (λ_h+λ_a)` in the same λ-buckets as Part B —
   a level defect shows as a positive residual in the low-λ buckets, a
   dispersion defect as a zero mean residual with excess variance;
3. the same two on **E0**, which is calibrated, as the negative control — both
   must read clean there or the instrument is not reading the defect.

**Predictions, written before it runs.**
- **P1.** E0's variance ratio is within **[0.98, 1.04]** and its low-λ mean
  residual within **±0.05** goals. *Basis:* Part B, E0 calibrated everywhere.
- **P2.** E1–E3's low-λ ([0.6,0.7) under-2.5 bucket) mean residual is
  **positive, +0.10 to +0.25 goals, resolved** in at least two of three.
  *Basis:* over-claiming "under" by 5–9 pts at λ ≈ 2.2 needs the truth to be
  ~0.15 goals higher, or a fatter tail; a level shift is the simpler reading of
  a bias that is one-signed.
- **P3.** E1–E3's variance ratio exceeds E0's by **< 0.05**. *Basis:* if P2
  holds the defect is mostly level, and dispersion has little left to explain.
- **P4 (the alternative).** If P2 fails — residual ≈ 0 — then P3 fails too and
  the ratio gap is **≥ 0.05**; the defect is dispersion and the fix is a model
  change, not an intercept.

**Cost 0.** Reads outcomes for a diagnostic, chooses among no arms, carries no
arm list. Ledger `probe:b17_totals_mechanism`. Whatever it says, the *fix* is
a gate with its own pre-registration and is not run from this item.

> **Amendment before the run, 2026-08-16 — the statistic, not the predictions.**
> Item 1 above said `var(total) / E[var under Poisson(λ)]`. Written as
> `(var(total) − var(λ)) / mean(λ)` and pointed at planted data
> (`tests/test_b17.py`), an **8% level shift with no excess dispersion read as
> a ratio of ~1.1** — because the true λ's variance is k² times the reported
> one. The two mechanisms could not have been told apart. The statistic is
> now **level-corrected**: λ is rescaled to the observed mean first,
> `(var(total) − var(cλ)) / mean(cλ)`, `c = mean(total)/mean(λ)`; a pure level
> shift reads 1, pure over-dispersion reads > 1, both planted and asserted.
> `c − 1` is reported as the relative level. The mechanism is read off
> intervals (≥ 2 of E1–E3 resolved) rather than point estimates; P1–P4 are
> scored as written. Same shape as `TRAVEL.md` §8: the detection statistic
> changed after the control and before the result.

## B12 (original scoping note)

Licensed by `CHANNELS.md` and `OUTSTANDING.md` §1.7 and never written. Split-half
reliability gain over the shipped `goals+sot` is **+0.0490 attack / +0.0540
defence**, against a NOISE control at −0.0008 — the same order as the addition
that became −0.00422 nats and shipped (§1.3).

**It was deprioritised on a beat-the-book argument that no longer applies**
(§9.3): §1.7 closes with *"it also does not touch the book"*, which was the
right thing to say to a project trying to beat the book and is not a demerit for
a tipster. A better λ improves **every item on the menu at once** — the
outrights, all three double chances, and all six goal lines, because they are
all marginals of the same joint.

**Cost is 13 configurations, pre-registered in `P4_CHANNELS_PLAN.md` §5.**

> **The "2 configurations" this item used to quote was a mis-transcription,
> corrected 2026-08-10.** It imported §1.7's fourth bullet, which prices
> identifying the **per-side** (att/dfn) weight for the *already-shipped* sot
> channel — a different question, and one this gate does not ask. Nothing had
> ever costed the shots+corners gate itself. The bullet's real instruction
> survives and is obeyed: **do not build a 6×6 grid.** The weight is a single
> 5-point sweep over one shared composite weight, and the per-side weight is
> explicitly not in the budget.

**Read §1.7's cautions first** — split-half reliability is not deviance,
`SHOTS_TARGET.md` §7 records over-estimating that mapping once, and row 53 is
not reproducible.

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

## B7 — The honesty check — **DONE 2026-08-16**

The remaining gap — the return claim was measured on the v1 rule — is closed
by `gate:p7_v2_return` (`TIPSTER.md` Part A, 4 configurations): at floor 0.55
the shipped rule returns **−4.56% [−5.56, −3.60]** at average derived prices
and **+0.11% [−0.94, +1.10]** at best; against the same rule on the market's
probabilities, **−0.57 pts [−1.49, +0.32]**. Site paragraph, `PRODUCT.md` §5
and `STATE.md` now cite these. Original note:


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

**And there is now a number on the claim itself.** §9.5 measured the head
over-stating `12` — 65.0% of everything published — by **0.75 points**, claiming
74.39% and delivering 73.64%. Small, resolved, and in the direction that
matters: the product's largest market over-claims rather than under-claims. The
B7 honesty argument to date has rested on the head being *under*-confident and
therefore conservative (§1.10), and **that is true of the outrights and false of
`12`**. Worth stating before any published confidence figure leans on it.

**A second gap, opened 2026-08-15 as B16**: the published number pools every
rule version, so the mixing this section exists to prevent is unguarded on the
one axis that was supposed to be guarded.

## B16 — The published strike rate pools every rule version — **DONE 2026-08-15**

**Decided and shipped.** Headline and `by_division` in `/tips/record` are the
newest published version's record only; `by_rule` carries every version, newest
first, held to the same no-P&L test as the rest of the payload. The page shows
the per-version table only when more than one version exists. "Current" is read
off the newest tip rather than imported from `engine.serve.tips`, so the API
still loads none of the serving stack. Re-tipping under a new version stays
allowed per the schema (owner call); the operational rule that follows — do not
bump and re-run on one matchday — is `RUNBOOK.md` §0. Tests:
`test_the_record_headline_is_the_current_rule_only`. The original note follows.

`services/run_cycle.py:66-67` states that changing `TIP_FLOOR` or `TIP_CEILING`
means bumping `tips.RULE_VERSION`, *"or the published history mixes two products
under one strike rate"*. **Bumping it does not prevent the mixing.**

`RECORD` (`api/main.py:228-242`) aggregates every row of `tips` with no
`rule_version` predicate, and `/tips/record` then reports the **most recent**
tip's rule beside the pooled figure (`api/main.py:263-265`). So the payload
labels an all-versions strike rate with one version's name. The column exists,
is written on every tip, is enforced by `UNIQUE (fixture_id, rule_version)` in
migrations 003 and 004, and is read by nothing that computes the claim.

**The version bump is not inert, which is what makes this a trap rather than an
omission.** `tips.UNTIPPED` excludes a fixture only for the *current* version, so
a bump re-opens every fixture inside the publish window. That window is
`PUBLISH_WITHIN_DAYS = 0`, so the blast radius is one matchday — but retune the
floor on a Saturday morning and the day's fixtures carry two live calls each,
both settle, and both land in the same denominator. The `UNIQUE` constraint does
not stop this; it is scoped per version by design.

**Harmless today**: all 33 published tips are `confidence-v2`, and nothing has
been graded yet. It goes live the first time the floor moves — which is **B10**
and **B13** territory, both open, and B13 is an owner decision that could be
taken at any time.

**What it needs is a decision before it needs code.** Is the published strike
rate per-rule-version, or all-time across versions? Per-version is the honest
default and is what `run_cycle.py`'s comment already promises. It costs a
`WHERE t.rule_version = ?` in `RECORD` — and an answer to the product question
that falls out of it: on the day of a bump the headline number resets to null
(`api/main.py:255-257`) and the graded history disappears from the surface.
Whether that is acceptable, or whether the old version's record should still be
shown beside the new one, is the owner's call and not a code one.

**Cost 0** — reads no match outcomes, so it does not spend against the ledger.

---

## Done

| id | item | where |
| --- | --- | --- |
| — | Tip rule, published and settled by the serving cycle | `OUTSTANDING.md` §1.10 |
| — | Strike rate / volume / return measured over 11 seasons — **v1 rule** | `engine/eval/tips.py` |
| B16 | Per-version strike rate on `/tips/record` | `api/main.py`, above |
| — | Meta-label on the football model — measured, do not adopt | `META.md` |
