# P1 Track M — implementation plan

> **Status: EXECUTED.** Results, the prediction scorecard and the decisions taken
> are in **[BASELINE.md](BASELINE.md)**. This document is the plan as
> pre-registered and is left unedited below, so the predictions can be read
> against what happened. Five of ten were wrong.

Written 2026-07-28, after four read-only grounding probes against the
development set (2010-11 → 2022-23, E0–EC).

P1 produces **the base score**: the number every later gate — player prior,
context features, calibration, meta-label — has to beat. If the base score is
wrong, every subsequent decision is wrong in the same direction and nothing
downstream will reveal it. So this phase is mostly measurement discipline, not
modelling.

---

## Contents

1. [What P1 must produce](#1-what-p1-must-produce)
2. [Evidence gathered before planning](#2-evidence-gathered-before-planning)
3. [Pre-registered hypotheses](#3-pre-registered-hypotheses)
4. [Build order](#4-build-order)
5. [Trial budget](#5-trial-budget)
6. [Out of scope](#6-out-of-scope)
7. [Decisions I need](#7-decisions-i-need)

---

## 1. What P1 must produce

| # | Deliverable | Done when |
| --- | --- | --- |
| D1 | Walk-forward harness with day-frozen refits, regime embargo, leak canary | Canary green; reproduces the P0 λs exactly when configured identically |
| D2 | Metric layer: logloss, Brier, AUC for 1X2 and O/U 2.5; market probabilities per information set | Unit-tested against hand-computed values |
| D3 | Paired block bootstrap | Calibrated on planted offsets and on identical arms |
| D4 | Half-life and α frozen by a pre-registered rule, ledgered | Both sweeps recorded with grids and CIs |
| D5 | **Baseline table** per division × market × information set, against market and base-rate anchors | Committed to `docs/BASELINE.md` |
| D6 | NEW-1 (EC) and OPEN-3 (off-season) decided with numbers, nulls included | Each written up whichever way it lands |
| D7 | Artifact freeze/load + version string | λ round-trips bit-identical; Track A can consume it |

---

## 2. Evidence gathered before planning

Four probes, read-only, dev set only, frozen P0 hyperparameters. These shaped
the plan below; they are not results and are not ledgered as trials.

### 2.1 Cost is not a constraint

One fit of the joint head on a typical 1,000-day window (6,586 matches, 147
teams, 296 parameters) takes **25 ms**.

| cadence | refits over the dev set | wall clock per arm |
| --- | --- | --- |
| day-frozen (every distinct match date) | 2,336 | **1.0 min** |
| weekly | 494 | 0.2 min |
| fortnightly (P0 setting) | 247 | 0.1 min |

A seven-point half-life sweep at day-frozen cadence costs about seven minutes.
**Every cost-driven compromise in the P0 harness can be dropped.** This is worth
stating plainly because it removes the usual excuse for evaluating at a coarser
cadence than you serve at.

### 2.2 The closing information set only exists from 2019-20 — except via Pinnacle

| column block | first dev season | dev coverage |
| --- | --- | --- |
| `avg_*`, `avg_over25` (pre-close) | 2010-11 | 100% |
| `close_ps_*` (Pinnacle closing) | 2012-13 | 84.6% |
| `close_avg_*`, `close_avg_over25` | **2019-20** | 29–31% |

So the information-set axis is constructible across the dev set **only through
Pinnacle**; the Avg/Max closing block covers four dev seasons. This constrains
D5's shape and is the reason H10 below exists — the axis is load-bearing for
P3's population design and has never been shown to be real on this corpus.

### 2.3 COVID moved home advantage, and the model bled it forward

| period | n | home win % | home goal advantage |
| --- | --- | --- | --- |
| pre-COVID | 25,309 | 43.24 | **0.287** |
| COVID window | 2,719 | 40.68 | **0.136** |
| post-COVID | 5,130 | 43.57 | **0.271** |

E0 alone is starker: 0.369 → **0.081** → 0.312.

The model's own error tells the more useful story:

| period | predicted margin | observed margin | bias |
| --- | --- | --- | --- |
| pre-COVID | 0.285 | 0.282 | −0.003 |
| COVID | 0.210 | 0.136 | **−0.074** |
| post-COVID | 0.232 | 0.271 | **+0.039** |

Decay dragged the home coefficient down during the empty-stadium window and
then took months to bring it back, so **the contamination shows up after the
regime ends, not during it**. Pre-COVID bias is −0.003; post-COVID is +0.039,
thirteen times larger.

**The important consequence is about measurement, not serving.** At a 200-day
half-life with a 5-half-life horizon, a fit made in August 2026 trains on data
back to roughly November 2023 — it never sees COVID. The live model is clean.
What is contaminated is the *backtest*, and therefore the base score and any
gate whose evaluation window sits in 2020-21 or 2021-22. That reframes the
embargo as a scoring-set question first (H6).

### 2.4 The base head loses to the market everywhere — the canary is green

Frozen defaults (H=200, α=1.0, fortnightly refit), scored against the de-vigged
pre-close market. Positive gap = market wins.

| division | n | model 1X2 | market 1X2 | gap | model O/U | market O/U | gap |
| --- | --- | --- | --- | --- | --- | --- | --- |
| E0 | 4,560 | 0.9726 | 0.9539 | **+0.0187** | 0.6881 | 0.6790 | +0.0091 |
| E1 | 6,623 | 1.0581 | 1.0408 | +0.0173 | 0.6959 | 0.6879 | +0.0080 |
| E2 | 6,471 | 1.0579 | 1.0365 | +0.0214 | 0.6973 | 0.6902 | +0.0071 |
| E3 | 6,507 | 1.0709 | 1.0536 | +0.0173 | 0.6929 | 0.6863 | +0.0066 |
| EC | 6,370 | 1.0424 | 1.0250 | +0.0174 | 0.6985 | 0.6892 | +0.0093 |

The model is behind the market in every division and every market, by a
remarkably stable ~0.018 nats on 1X2. **That is the correct and healthy result**
— a head that sees only goals and dates should not beat a closing line — and it
makes the anchor usable as a leak detector (H9).

The decomposition against a per-division base rate is more interesting than the
headline, and it changes what I expect from P2:

| division | base rate | model | market | share of market's edge captured |
| --- | --- | --- | --- | --- |
| E0 | 1.0624 | 0.9726 | 0.9539 | **83%** |
| E1 | 1.0781 | 1.0581 | 1.0408 | 54% |
| E2 | 1.0789 | 1.0579 | 1.0365 | 50% |
| E3 | 1.0807 | 1.0709 | 1.0536 | **36%** |
| EC | 1.0747 | 1.0424 | 1.0250 | 65% |

In the Premier League a bare Poisson strength model already recovers most of
what the market knows. In League Two it recovers barely a third. Either
lower-division team strength is genuinely less persistent, or the market there
is pricing something this head cannot see. **That gap, not E0's, is where the
headroom is** — and it is directly relevant to whether the player prior should
be built E0-first or E3-first.

### 2.5 The off-season costs accuracy but not calibration

| days into season | n | Poisson logloss | goal-margin bias | predicted total | observed total |
| --- | --- | --- | --- | --- | --- |
| 0–21 | 3,067 | **1.9085** | −0.013 | 2.612 | 2.607 |
| 22–45 | 2,607 | 1.8768 | +0.004 | 2.635 | 2.667 |
| 46–90 | 4,794 | 1.8757 | −0.026 | 2.627 | 2.666 |
| 91+ | 20,101 | **1.8506** | +0.004 | 2.631 | 2.604 |

Early season is 0.058 nats worse than late season. But the level is *right* —
bias −0.013 goals, predicted total 2.612 against 2.607 observed. **The
off-season problem is not that strengths drift; it is that they are less
certain and the model does not say so.** That reshapes OPEN-3: the candidate
fix is shrinkage toward the mean at the season boundary, not a change to how
calendar time is counted (H8).

Matches involving a promoted or relegated club, in those same first 21 days:
logloss 1.9225 against 1.9022 for the rest — worse by 0.020, with totals
essentially unbiased (2.572 predicted, 2.569 observed). The cross-division
scale is working; the residual is about *which* team is better, not how many
goals get scored. That sizes the P2 promoted-club arm honestly: it is real but
it is 0.020 nats on 5% of matches, not a headline effect.

---

## 3. Pre-registered hypotheses

Each carries a numeric prediction so it can be wrong. Predictions are written
before running anything; whatever happens gets recorded, including the nulls.

### H1 — Evaluation cadence should match serving cadence, and the staleness cost is small

**Claim.** Scoring at day-frozen cadence overstates what a weekly-refit serving
loop will achieve, by less than 0.003 nats.
**Test.** Same arm at daily, weekly and fortnightly refit; paired bootstrap.
**Prediction.** Daily − weekly ∈ [0.000, 0.003]; weekly − fortnightly ∈ [0.000, 0.003].
**Decision.** Score at **weekly** cadence (the serving reality per PLAN §4),
report the daily figure alongside as the ceiling. If the staleness cost exceeds
0.005 nats, refit daily in production — it costs 25 ms.

### H2 / H3 — Half-life and α sweeps, with an anti-overfit selection rule

**Grid.** H ∈ {100, 130, 160, 200, 240, 270, 300} at α=1.0; then α ∈ {0.25, 0.5,
1, 2, 5} at H*. Sequential, not a product grid.
**Selection rule, pre-committed:** the **1-SE rule** — take the *most
regularised* setting (longest half-life; largest α) whose score is within one
paired-bootstrap standard error of the best. Argmin alone would let sampling
noise choose, and the curve is expected to be flat.
**Prediction.** H* ∈ [130, 240]; the whole [100,300] range spans < 0.004 nats.
α* ∈ [0.5, 2]; the range spans < 0.003 nats.
**Guard.** Re-run the H sweep with 2020-21 and 2021-22 excluded from scoring. If
H* moves by more than one grid step, the optimum was set by the COVID regime and
the un-embargoed sweep is void. This protects the single most consequential
number in P1 from one anomalous window.

### H4 — H and α do not interact

**Test.** Evaluate the four corners around (H*, α*) after both sweeps.
**Prediction.** No corner beats (H*, α*) by more than its bootstrap SE.
**Why it matters.** Two sequential sweeps are only valid if the surface is
separable. Untested, that is an assumption dressed as a method.

### H5 — NEW-1: including EC in the fit is free, and helps E3 slightly if it helps anything

**Test.** Fit on E0–E3 vs E0–EC; score on E0–E3 only; paired block bootstrap.
**Prediction.** Pooled effect |Δ| < 0.002 nats with CI containing zero; any real
effect concentrates in E3 and in matches involving clubs that moved across the
E3/EC boundary.
**Decision.** Include EC if the pooled effect is non-negative — it anchors the
E3 scale for live serving, where E3↔EC movement is a live cold-start problem, at
no cost. Exclude EC from every served market and from every scoring set
regardless of outcome.

### H6 — COVID is a scoring-set problem, not a training-set problem

**Primary treatment, pre-committed:** exclude 2020-03-13 → 2021-05-31 from
**scoring**; retain it in **training**.
**Why not exclude from training.** It would leave a 15-month hole that decay
must bridge, so 2021-22 predictions would be made from February 2020 form. That
is a worse distortion than the one being fixed, and — per §2.3 — the live model
never sees the window anyway.
**Test.** Report the base score three ways: all matches; COVID window excluded;
COVID window and all of 2021-22 excluded.
**Prediction.** Excluding the window moves the pooled base score by 0.002–0.008
nats. Additionally excluding 2021-22 moves it by < 0.003 more.
**Falsifier.** If the third variant differs materially from the second, the
post-COVID bleed is large enough to need explicit handling, and I will say so
rather than pick the flattering number.

### H7 — OPEN-2: the form leg — **deferred to in-season (§7)**

Not run in P1. §2.5 shows no mis-calibration a short-timescale leg would fix,
and H2's sweep already searches the timescale axis it lives on. Kept here so the
deferral is a recorded decision rather than an omission; the arm as designed was
a blend of log-λ from a short half-life (H*/4) at weight w ∈ {0.15, 0.30}.
**Standing prediction, to be tested when it runs: null**, |Δ| < 0.002 nats.

### H8 — OPEN-3: the off-season needs shrinkage, not a different clock

**Grounded in §2.5:** early-season predictions are *unbiased but uncertain*, so
the candidate is not a change to how calendar time is counted.
**Arms.** (a) incumbent calendar decay; (b) off-season gap compressed to 30
days — included specifically because I expect it to *hurt*, and an arm you
expect to lose is what keeps the comparison honest; (c) att/dfn multiplied by
s ∈ {0.85, 0.95} at each season boundary.
**Evaluation set.** First 45 days of each season (n ≈ 5,674), per division.
**Prediction.** (c) at s=0.95 improves early-season logloss by 0.005–0.015;
(c) at s=0.85 over-shrinks and helps less or hurts; (b) hurts by > 0.01.
**Decision.** Adopt (c) only if it clears zero on paired bootstrap over the
early-season subset **and** does not degrade the full-season score.
**Launch relevance.** The engine's first served predictions are August 2026
matches. This is the one arm whose evaluation window is the launch window.

### H9 — The base head must stay behind the market (hard stop)

**Rule.** If any arm beats the de-vigged closing market on 1X2 in any division,
**halt P1 and hunt a leak.** A head with no features beyond goals and dates
cannot outprice a closing line; that result is a bug report, not a discovery.
**Prediction.** Post-sweep the gap narrows from ~0.018 to no better than 0.014
nats, and remains positive in all five divisions.

### H10 — The information-set axis is real

**Why this is here.** P3 splits every calibration population by pre-close vs
closing. That split is load-bearing across the whole design and has never been
verified on this corpus. If closing odds are no sharper than pre-close odds, the
axis is a fiction and P3 is fitting noise into twice as many populations as it
needs.
**Test.** Pinnacle `ps_*` vs `close_ps_*`, 2012-13 → 2022-23, per division,
paired on the same matches.
**Prediction.** Closing beats pre-close by 0.002–0.008 nats in every division,
with the gap largest in E0 (most team-news-sensitive, most liquid).
**Falsifier.** A gap indistinguishable from zero in E1–E3 would mean the axis is
real only in the Premier League — which would be a finding worth having before
P3 rather than after.

---

## 4. Build order

Each step names its verification. Nothing proceeds on an unverified step.

**1. `engine/eval/metrics.py`** — 1X2 and O/U 2.5 logloss, Brier, AUC;
market probabilities per information set; per-population aggregation.
*Verify:* hand-computed values on a 4-row fixture; a perfectly-calibrated
synthetic must score at its entropy; AUC on separable and on random labels.
*Note:* AUC on 1X2 requires one-vs-rest and is the weakest of the three — it
will be reported but not used for any decision.

**2. `engine/eval/walkforward.py`** — the real harness. Day-frozen refits at
configurable cadence, regime embargo, optional season-boundary shrink, returns λ
plus each fit's cutoff and training row count.
*Verify:* (a) **leak canary** via `engine.asof.assert_no_future_dependence` —
corrupt every future outcome, λ must not move; (b) an assertion inside the
harness that no prediction ever comes from a fit whose cutoff ≥ the match date;
(c) a synthetic corpus with known time-varying strengths → recovered λ
correlation > 0.95; (d) **configured as P0 was, it must reproduce
`poisson.walk_forward_lambdas` to 1e-9.** The P0 function stays untouched until
that passes, so the dispersion results remain reproducible.

**3. `engine/eval/bootstrap.py`** — paired block bootstrap, blocks = ISO week.
*Why blocks:* matches in a week share teams and share a fitted artifact, so
per-match resampling would understate every CI in this document.
*Verify:* planted constant offsets of known size must be detected at the
expected rate; two identical arms must produce CIs covering zero ≈ 95% of the
time over repeated draws.

**4. `engine/eval/sweep.py`** — sweep runner, 1-SE selection rule, ledger writes.
*Verify:* the 1-SE rule unit-tested on synthetic score curves, including a flat
curve (must pick the most-regularised end) and a sharply peaked one (must pick
the peak).

**5. Run the hypotheses** in order H1 → H2/H3 → H4 → H6 guard → H5 → H8 → H10,
then H9 as the closing check over everything.

**6. `engine/serve/artifact.py`** — freeze/load, version string over (code
revision, hyperparameters, training cutoff, corpus digest).
*Verify:* λ round-trips bit-identical; the version string changes when any input
changes and only then.

**7. `docs/BASELINE.md`** — D5, plus every hypothesis result including nulls,
plus a scorecard of predictions above against what actually happened.

---

## 5. Trial budget

Ledger discipline is the point of the ledger, so the budget is declared up front.

| kind | name | grid |
| --- | --- | --- |
| PROBE | cadence sensitivity | 3 |
| SWEEP | half_life | 7 |
| SWEEP | alpha | 5 |
| PROBE | h_alpha_interaction | 4 |
| PROBE | covid_scoring_window | 3 |
| GATE | new1_ec_inclusion | 2 |
| GATE | open3_offseason | 4 |
| PROBE | information_set_sharpness | 1 |
| GATE | p1_base_score | 1 |

**Nine entries, 30 arms.** Added to P0's three, the corpus has seen 12 recorded
trials when P1 closes. Each entry stores its grid and CIs so PBO/CSCV deflation
later has a real count rather than a reconstructed one.

## 6. Out of scope

Player features (P2), context features (P4), calibration and recalibration (P3),
the meta-label (P5), any Asian handicap or correct-score head, and the Dixon–Coles
τ (closed in P0-2). No holdout season is touched.

## 7. Decisions taken

Settled 2026-07-28 before any P1 code was written.

**Selection metric: out-of-sample Poisson deviance on goals.** The sweeps in H2
and H3 are decided on the model's native objective — two count-valued
observations per match, so the most power available and no tie to one market.
1X2 and O/U 2.5 logloss are computed on the same runs and reported as
confirmatory. **If the served-market ranking contradicts the deviance ranking,
that is recorded as a finding in `BASELINE.md`, not quietly resolved in favour
of whichever looks better.**

**Arm scope: OPEN-3 and NEW-1 run in P1; OPEN-2 deferred to in-season.** The
off-season arm runs because its evaluation window is literally the launch
window. The EC gate runs because it is cheap and affects the live E3 scale. The
form leg is deferred on the evidence in §2.5 and the overlap with H2 — recorded
as a deferral in H7, not dropped.

**The E0/E3 headroom asymmetry (§2.4) does not redirect P2 yet.** It is recorded
in `BASELINE.md` as evidence and re-measured after the sweeps. One probe at
frozen hyperparameters is not enough to re-point a phase, and the Premier League
remains the product.
