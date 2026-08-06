# P1 base score

The number every later gate has to beat. Measured 2026-07-28 on the development
set (2010-11 → 2022-23, E0–E3 scored, EC in the fit only), against the plan
pre-registered in `P1_PLAN.md`.

> **Re-issued 2026-07-28 on the complete corpus.** The 2015-16 season was
> missing when P1 first ran (§4.2); the genuine files have since been added and
> every hypothesis re-run on all thirteen seasons. **One decision moved — the
> half-life, 500 → 400 days.** Every other decision held, and two results got
> cleaner: the H4 interaction is no longer significant, and the H2 COVID guard
> now moves zero grid steps instead of one. All figures below are from the
> complete-corpus run.

Reproduce with `python -m engine.eval.p1 --stage all`. Every result below is in
`gate_ledger`.

---

## Contents

1. [The frozen head](#1-the-frozen-head)
2. [The base score](#2-the-base-score)
3. [Prediction scorecard](#3-prediction-scorecard)
4. [Two defects found on the way](#4-two-defects-found-on-the-way)
5. [Decisions taken](#5-decisions-taken)
6. [What still worries me](#6-what-still-worries-me)

---

> **RE-ISSUED 2026-08-04 — the head now carries the shots channel.** P4-shots
> (`SHOTS_TARGET.md`) measured a shots-on-target blend worth **−0.00422**
> [−0.00535, −0.00307] of goal deviance, negative in all four served divisions
> with every interval excluding zero. It was adopted, the head re-frozen as
> `p1-3a38e9d6ef1ca7ee`, and the base score below re-measured by the same
> `h9_baseline` code that produced the previous one. **§1 and §2 are current.**
> Everything from §3 onward describes the P1 run that produced the earlier head
> and is left unedited, so its predictions can still be scored.

## 1. The frozen head

```
H400 / a0.1 / weekly / E0+E1+E2+E3+EC / sot0.3
```

| setting | value | how it was chosen |
| --- | --- | --- |
| half-life | **400 days** | H2 sweep, interior optimum, 1-SE (paired) |
| ridge α | **0.1** | H3 sweep, interior optimum, 1-SE (paired) |
| refit cadence | **weekly** (Monday, predicting 7 days) | H1: matches serving; day-frozen is worth 0.00007 nats |
| fit population | **E0–EC** | H5 gate: including the National League helps |
| **shots blend** | **0.30** | H20 sweep, interior optimum, 1-SE (paired) — `SHOTS_TARGET.md` |
| season-boundary shrink | **not adopted** | H8 gate: improves goal deviance, but measurably harms E0 on both served markets — §5 |
| squad prior | **not adopted** | P2: null on five arms — `PLAYER_PRIOR.md` |
| scoring embargo | COVID window (2020-03-13 → 2021-05-31) | H6: excluded from scoring, retained in training |

**The shots blend is the newest change.** A second Poisson fit on
shots-on-target over the identical design matrix, folded into the goal-fitted
strengths at weight 0.3. It is a *channel*, not a replacement target: at weight
0.8 the blend is worse than not using shots at all, which is why SPEC §3.7's
proposal to substitute the target was refuted rather than implemented. Clubs
with no shot evidence — the whole National League since 2016-17 — are left on
their goal-fitted strengths rather than given an invented one.

**The half-life is the headline change.** SPEC §3.2 proposed a defensible window
of [100, 300] days and P0 froze the instrument at 200. The data wants **400** —
outside the SPEC's window, and the sweep only revealed it because the grid was
extended after 300 came back as a boundary winner. English club strength is far
more persistent than the SPEC assumed: at a 400-day half-life a match from the
previous season still carries around 55% of the weight of a match from last
month.

The corrupted corpus put this at 500, the complete one at 400. That region is
genuinely flat — H300 through H500 span 0.0009 nats, against a 0.0216 spread
across the whole grid — so the exact value matters far less than the fact that
it lands well beyond the SPEC's upper bound either way.

The ridge moved the same way, from 1.0 to 0.1. Both point at one conclusion —
**this corpus supports a much longer memory and a much lighter hand than the
design anticipated**, and the frozen P0 defaults were over-regularised on both
axes.

Cost is not a constraint anywhere in here: one fit takes 25 ms, a day-frozen
walk-forward over the whole corpus takes a minute, and a nine-point sweep takes
under ten.

## 2. The base score

Out-of-sample, walk-forward, COVID window excluded from scoring. Positive gap
means the market wins, which it does everywhere.

**Pre-close information set** (`Avg` columns, full coverage):

| division | n | model 1X2 | market 1X2 | base rate | gap | model O/U | market O/U | gap | model Brier | AUC O/U |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| E0 | 4,088 | 0.9650 | 0.9552 | 1.0627 | **+0.0098** | 0.6802 | 0.6788 | +0.0014 | 0.5717 | 0.586 |
| E1 | 5,952 | 1.0537 | 1.0410 | 1.0777 | +0.0127 | 0.6936 | 0.6888 | +0.0048 | 0.6351 | 0.539 |
| E2 | 5,907 | 1.0485 | 1.0344 | 1.0776 | +0.0141 | 0.6949 | 0.6901 | +0.0048 | 0.6316 | 0.530 |
| E3 | 5,943 | 1.0639 | 1.0520 | 1.0815 | +0.0119 | 0.6903 | 0.6883 | +0.0020 | 0.6423 | 0.541 |

Every gap narrowed, and the pooled 1X2 deficit moved **+0.01419 [+0.01239,
+0.01609] → +0.01230 [+0.01041, +0.01419]**. Those two intervals overlap
heavily, which is exactly why the adoption decision rests on the *paired*
comparison in `SHOTS_TARGET.md` (−0.00422, 7.3 paired SE) and not on this
table — the marginal and paired standard errors differ by ~29× on this corpus
(`OUTSTANDING.md` §7.3).

**Closing information set** (Pinnacle `PSC` for 1X2; `close_avg` for O/U, which
only exists from 2019-20, hence the smaller n):

| division | n | model 1X2 | market 1X2 | base rate | gap | model O/U | market O/U | gap |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| E0 | 1,048 | 0.9757 | 0.9580 | 1.0622 | +0.0177 | 0.6719 | 0.6748 | −0.0029 |
| E1 | 1,548 | 1.0564 | 1.0483 | 1.0779 | +0.0081 | 0.6895 | 0.6868 | +0.0027 |
| E2 | 1,502 | 1.0277 | 1.0007 | 1.0701 | +0.0270 | 0.6964 | 0.6888 | +0.0076 |
| E3 | 1,541 | 1.0655 | 1.0476 | 1.0830 | +0.0180 | 0.6813 | 0.6798 | +0.0015 |

The one negative cell — closing/E0 on O/U — was put through a paired bootstrap
before being called anything: **−0.00294 [−0.00880, +0.00308]**, an interval
three times wider than the point estimate. It is noise, not an edge, and saying
so required the CI rather than the table. Worth noting that the H9 hard stop as
originally written only covered 1X2; this cell would have passed unexamined, so
the check now covers both served markets. **H9 holds: the model is behind the
market everywhere it is measurably anywhere.**

### Share of the market's edge captured

The most useful reading of the table. The market beats a per-division base rate
by some amount; this is the fraction of that the head recovers.

| division | before P1 (H200, α1) | after P1 | **after the shots channel** |
| --- | --- | --- | --- |
| E0 | 0.83 | 0.89 | **0.909** |
| E1 | 0.54 | 0.62 | **0.654** |
| E2 | 0.50 | 0.64 | **0.674** |
| E3 | 0.36 | 0.51 | **0.598** |

Tuning bought the most where the model was weakest: League One improved by
fourteen points and League Two by fifteen, the Premier League by six. The shots
channel then bought the most in the same place again — **E3 gained nine points,
E0 two.**

**The asymmetry is narrowing but has not closed.** E3 has gone from recovering
a third of what the market knows to recovering three-fifths; E0 sits at
nine-tenths. Whatever the lower-division market prices that this head cannot see
is still worth about four times as much there as in the Premier League.

Recorded originally as evidence for P2's ordering. P2 returned null and the
ordering question is closed (`OUTSTANDING.md` §3.1), so this asymmetry is now
unexplained rather than pending — it belongs to OPEN-6.

## 3. Prediction scorecard

Every hypothesis carried a numeric prediction written before the run. Five of
ten were wrong, and two of those were wrong in ways that changed the build.

| # | prediction | outcome | verdict |
| --- | --- | --- | --- |
| H1 | cadence worth < 0.003 nats | daily−weekly 0.00026, weekly−fortnightly 0.00133 | **held** |
| H2 | H\* ∈ [130, 240], spread < 0.004 | H\* = **400**, spread **0.022** | **wrong** — 5× the spread, optimum outside SPEC's window |
| H3 | α\* ∈ [0.5, 2], spread < 0.003 | α\* = **0.1** (argmin 0.05), spread 0.009 | **wrong** — wants an eighth the penalty |
| H4 | no corner beats the centre | best corner −0.00027 [−0.00071, +0.00020], CI spans zero | **held** on complete data (it failed on the corrupted corpus) |
| H5 | \|Δ\| < 0.002, CI spans zero, effect in E3 | −0.00272 [−0.00384, −0.00165]; **E3 −0.0100**, EC-promoted clubs **−0.0576** | **wrong on size, right on location** |
| H6 | window worth 0.002–0.008 nats | 0.00063 | **wrong** — an order of magnitude smaller |
| H8 | shrink 0.95 gains 0.005–0.015; 0.85 over-shrinks; summer arm hurts > 0.01 | optimum **0.80–0.85** gaining 0.0025 on deviance but **harming E0 1X2**; summer arm −0.00000, no effect | **wrong on all three** |
| H9 | model stays behind market, gap ≥ 0.014 | behind everywhere; E0 pre-close gap **0.0117** | **held, but the gap prediction was wrong** — tuning closed more than I allowed for |
| H10 | closing sharper by 0.002–0.008, largest in E0 | pooled −0.00246; largest in **E2**; E1 no difference | **half wrong** |
| H2-guard | optimum moves ≤ 1 grid step without COVID seasons | moved **0** steps (400 → 400) | **held** |

The pattern is consistent and worth naming: **I systematically predicted that
this corpus would behave like the SPEC's priors, and it does not.** Persistence
is longer, regularisation should be lighter, regime effects are smaller, and
cross-division pooling is worth more than expected. The one place I was too
pessimistic rather than too optimistic — H5 — is the one that changed a shipped
decision.

### H5 deserves its own note

The National League gate reversed between the two runs of P1:

| config | pooled effect of including EC |
| --- | --- |
| H300 / α2.0 (from the buggy 1-SE rule) | **+0.00143** — EC *hurts*, CI excludes zero |
| H400 / α0.1 (corrected) | **−0.00272** — EC *helps*, CI excludes zero |

Same data, same code, opposite conclusion, both "significant". At α=2.0 the
ridge crushed the extra teams' strengths toward zero, so the National League
contributed nothing but a drag on the shared intercept. At α=0.1 those
strengths survive and the promotion/relegation edges do their work. The effect
lands exactly where the mechanism says it should:

| population | effect of including EC |
| --- | --- |
| E0 | −0.00017 [−0.00037, +0.00004] |
| E1 | −0.00001 [−0.00021, +0.00018] |
| E2 | +0.00014 [−0.00031, +0.00054] |
| **E3** | **−0.01003** [−0.01447, −0.00615] |
| **clubs promoted from EC last season** (n=970) | **−0.05760** [−0.08296, −0.03347] |

A club that came up from the National League is predicted **0.058 nats better**
when the fit has seen its National League matches. That is roughly fourteen
times the size of the E0 gap this whole phase moved. It is also a direct preview
of what the P2 player prior is for: cold-start clubs are where the information
is.

## 4. Two defects found on the way

### 4.1 The 1-SE rule was calibrated against the wrong standard error

The selection rule compared arms using each arm's **marginal** block-bootstrap
standard error (~0.0072 on this corpus) when the quantity that governs a
comparison between arms scored on the same matches is the **paired** standard
error (~0.00025). A factor of twenty-nine.

The consequence is not that the rule was conservative. It is that **every arm
was inside one SE of every other**, so the rule never looked at the evidence at
all — it silently handed each sweep to its tie-break and walked to the most
regularised end of the grid. It chose α = 2.0 where the paired comparison
separates α = 0.1 by tens of standard errors.

It surfaced because H4 existed. The interaction probe compared the chosen centre
against its neighbours with a *paired* bootstrap and reported that (H300, α1.0)
beat the chosen (H300, α2.0) with a CI excluding zero — which is impossible if
the rule that chose the centre were calibrated. Pinned as
`test_a_monotone_curve_resolved_by_paired_errors_picks_the_true_optimum`, using
the real numbers from the failed run.

### 4.2 `data/play_history/201516/` was a byte-identical copy of `201415/` — **fixed**

All five division files. The 2015-16 season is **absent from the corpus** and
2014-15 is **counted twice** — 2,588 matches missing, 2,588 duplicated, and a
fifteen-month hole in real coverage between 2015-05-24 and 2016-08-05.

Every integrity check in `build.validate()` passed. The per-division row counts
were exactly right (2,588 per season either way), every value was individually
valid, goals per match was normal, and the odds columns were populated. This is
the same shape as the P0 BLOB defect: **the aggregate looked perfect and the
content was wrong.** It surfaced only because a paired comparison tried to align
two arms on fixture identity and found 4,072 rows where it expected unique keys.

Two checks now cover it, both in `validate()`, both pinned by tests:

- no `(match_date, home_team, away_team)` may appear twice
- each season's matches must fall inside that season's own calendar window

**Every P1 decision was re-run on a de-duplicated corpus and none of them move:**

**Resolved.** The genuine 2015-16 files were supplied and the store rebuilt:
2015-16 now runs 2015-08-07 → 2016-05-17, zero duplicate fixtures, all integrity
checks pass. Semantic confirmation beyond the row counts — Leicester tops E0
2015-16 with 23 wins, which is the one thing about that season nobody has to
look up. (E0's replacement file uses four-digit years where the other four use
two; the loader's `dd/mm/%Y`-then-`dd/mm/%y` fallback absorbed it and dropped
no rows.)

Every hypothesis was re-run on all thirteen seasons. Three snapshots:

| decision | corrupted corpus | de-duplicated (12 seasons) | **complete (13 seasons)** |
| --- | --- | --- | --- |
| half-life | 500 | 500 | **400** |
| α (1-SE choice) | 0.1 | 0.1 | **0.1** (argmin 0.05) |
| EC inclusion | −0.00290 | −0.00284 | **−0.00272**, include |
| shrink early-season deviance | −0.00246 | −0.00222 | **−0.00252** |
| H4 interaction | significant | — | **not significant** |
| H2 COVID guard | 1 grid step | — | **0 grid steps** |

**Only the half-life moved**, and it moved within the flat region rather than
across it. Two results improved: the apparent violation of sweep separability
(H4) disappears on clean data, and the decay optimum is now completely
insensitive to dropping the COVID seasons. Both were artifacts of the duplicated
season, which is a useful reminder that a corrupted corpus does not only add
noise — it manufactures structure.

## 5. Decisions taken

| decision | outcome |
| --- | --- |
| **OPEN-3** (off-season) | **Not adopted in the base head** — see below. Improves goal deviance (−0.00222 early-season) but harms the Premier League on both served markets. Handed to P4 as a population-specific candidate. The "compress the summer" arm does nothing (+0.00015, CI spans zero) and is rejected outright. |
| **NEW-1** (National League) | **Include EC in the joint fit**, excluded from every served market and every scoring set. Driven by E3 and by clubs promoted out of EC. |
| **OPEN-2** (form leg) | Deferred to in-season, as agreed before the run. H2 searched the timescale axis and found the optimum at 500 days — the opposite end from where a short-memory form leg lives, which weakens the case further. |
| **OPEN-6** (recal pooling) | New evidence, not yet a decision. H10 finds the closing/pre-close gap real pooled (−0.00207) but **absent in E1** and largest in **E2**, not E0 as predicted. The information-set axis is real but small; doubling the population count for 0.002 nats needs justifying in P3 rather than assuming. |
| **H6** (COVID) | Embargo from **scoring only**; retain in training. Worth 0.00043 nats, an order of magnitude less than predicted. |

### The selection metric and the served markets disagree — and I did not follow the letter of the rule

Pre-registration said hyperparameters are selected on goal deviance, and that a
contradiction with the served markets is *recorded* rather than resolved in
whichever direction looks better. H8's own rule said adopt if the early-season
subset clears zero and the full season does not degrade. On goal deviance, both
conditions hold, so the literal rule adopts the shrink.

The served markets say otherwise, and not marginally. Sign convention: **positive
means the shrink is worse.**

| population | full season | first 45 days (the launch window) |
| --- | --- | --- |
| pooled goal deviance | −0.00086 [−0.00139, −0.00032] | −0.00252 [−0.00427, −0.00079] |
| pooled 1X2 | **+0.00075** [+0.00037, +0.00115] | +0.00010 [−0.00087, +0.00113] |
| pooled O/U 2.5 | −0.00091 [−0.00116, −0.00066] | −0.00128 [−0.00209, −0.00048] |
| **E0 1X2** | **+0.00259** [+0.00121, +0.00389] | +0.00370 [−0.00055, +0.00774] |
| E0 O/U 2.5 | +0.00006 [−0.00080, +0.00092] | +0.00196 [−0.00047, +0.00447] |
| E2 1X2 | **+0.00087** [+0.00030, +0.00142] | +0.00046 [−0.00097, +0.00197] |
| E1 O/U 2.5 | −0.00134 [−0.00174, −0.00093] | −0.00257 [−0.00409, −0.00123] |
| E2 O/U 2.5 | −0.00115 [−0.00159, −0.00072] | −0.00226 [−0.00381, −0.00063] |
| E3 O/U 2.5 | −0.00090 [−0.00125, −0.00054] | −0.00117 [−0.00226, −0.00012] |

**Correction from the pre-complete-data run.** I previously wrote that the shrink
harms E0 "on both served markets, in the launch window, with intervals excluding
zero." On the complete corpus that overstates it: the E0 early-season intervals
now both span zero (1X2 +0.00370 [−0.00055, +0.00774]; O/U +0.00196 [−0.00047,
+0.00447]). What survives is the **full-season E0 1X2 degradation, +0.00259
[+0.00121, +0.00389]**, plus a smaller one in E2 1X2. The launch-window
direction is unchanged and consistent, but it is no longer significant on its
own, and the argument now rests on the full-season result.

**The pattern is unchanged: the shrink costs 1X2 where strength differences are
real, and buys O/U in the lower divisions.** The mechanism is legible — pulling
attack and defence toward the league average compresses exactly the strength
differences 1X2 is about, and those differences are largest and most genuine in
E0. Goal deviance pools both sides of that trade into one number and reports the
net, which is why it preferred a change that regresses the flagship market.

**Decision: do not ship it.** This is a deliberate departure from the literal
pre-registered rule, and the reason is that the rule's proxy metric turned out
to average over a division-dependent effect it cannot see. Shipping a measured
regression in the Premier League on the strength of a proxy would be following
the letter of the pre-registration against its purpose.

What it is instead: evidence that **the off-season correction is real but
population-specific**, worth ~0.002 nats on lower-division O/U and negative in
E0. That is a P4 shape — a context gate fitted per population on top of the P1
base — not a global hyperparameter. Recorded, not discarded.

### Trial count

The plan budgeted nine ledger entries. The corpus has now seen **38 recorded
trials**: the 1-SE defect forced one full re-run and the missing season forced
another, and every re-run was recorded rather than replacing its predecessor.

The inflated count is the honest number and it is the one PBO/CSCV deflation
should use. A re-run against the same development set spends a trial whether or
not the first attempt was discarded as buggy, and whether or not the data was
later found to be wrong — that is precisely the accounting the ledger exists to
stop anyone quietly avoiding. Note that the P0 dispersion results were also
measured on the corrupted corpus and have **not** been re-measured; that is a
known outstanding item, though the τ decision rested on four independent
arguments and is unlikely to be sensitive to one duplicated season.

## 6. What still worries me

1. **A 400-day half-life is a long memory, and the region around it is flat.**
   H300–H500 span 0.0009 nats. The corrupted corpus chose 500 and the complete
   one chose 400, which is reassuring about the conclusion (roughly double the
   SPEC's window) and unhelpful about the value. Nothing downstream should treat
   400 as precise.

2. **The closing information set is thin.** 1,048 E0 matches, and the O/U side
   depends on columns that only start in 2019-20. Every closing-set conclusion
   here is drawn from four seasons, one of which is partly embargoed. The
   closing-E2 gap of +0.0264 against a pre-close +0.0155 is probably this rather
   than anything real.

3. **The E0/E3 asymmetry did not close.** Tuning moved E3 from 0.36 to 0.51 of
   the market's edge and E0 from 0.83 to 0.89. The gap between divisions is
   still the largest unexplained structure in the table.

4. **The shrink decision rests on a full-season result, not the launch window.**
   The launch-window intervals span zero on complete data. The direction is
   consistent across every cut, but the case for *not* shipping it is now
   carried by the full-season E0 1X2 number alone.

5. **Two of the corrupted corpus's findings were manufactured, not merely
   noisy** — a spurious H4 interaction and a spurious COVID sensitivity in the
   decay optimum. Both looked like real structure with intervals excluding zero.
   That is a caution about every gate this project will run: a data defect does
   not announce itself as variance.

6. **Nothing here is calibrated yet.** These are raw pmf probabilities. Every
   number in §2 is a pre-calibration score, and P3 sits between it and anything
   that should be priced.
