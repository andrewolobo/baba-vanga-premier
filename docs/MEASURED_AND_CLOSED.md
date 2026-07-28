# Measured and closed

Results with their numbers, including the nulls. A result is only "closed" here
if it was measured on this corpus; nothing is inherited from
`../baba.vanga.gtleague` without re-measurement.

Reproduce with `python -m engine.eval.dispersion`. Every entry is recorded in
`gate_ledger`, which is what gives later deflated-performance work a real trial
count.

---

## P0-1 · Distribution family for totals — **CLOSED: Poisson is correct**

**Decision: do not change the distribution family. Serve O/U off the Poisson pmf.**

Measured 2026-07-28 on 24,167 development-set matches (2011-08 to 2023-05, E0–E3),
using out-of-sample λ from a walk-forward ridge Poisson refit fortnightly.

| statistic | value | 95% CI |
| --- | --- | --- |
| `Var(total \| λ) / E[λ]` | **1.0130** | [0.9943, 1.0346] |
| home side | 0.9952 | |
| away side | 1.0093 | |
| residual correlation | **+0.0115** | |

The interval contains 1.0, so there is no evidence of over-dispersion at the
total. Per division: E0 1.0222 · E1 1.0139 · E2 1.0136 · E3 1.0046.

**The conclusion transfers but the mechanism does not, and that matters.**
gtleague reached its 0.978 through two large effects cancelling — side-level
under-dispersion of 0.84 against a residual correlation of +0.166. Here both
legs sit at ~1.0 individually and the correlation is +0.0115, i.e. forty times
smaller. English match sides are close to genuinely independent, whereas
gtleague's were strongly coupled and merely looked independent at the total.
Anything that relies on the *sides* being independent — and the margin pmf does
— is therefore on much firmer ground here than the shared headline number would
suggest. It would have been wrong to inherit the 0.978 and assume the same
structure underneath.

> **ORIGINAL (wrong): "dispersion worsens at low λ, where English mass sits".**
>
> Stratifying by predicted total produced a clean monotone gradient — 1.1434 in
> the lowest quartile falling to 0.9531 in the highest — which reads as exactly
> the low-λ breakdown SPEC §2.4 anticipated. **It is an artifact of stratifying
> on an estimate that carries error.** Matches sorted into the low bucket are
> disproportionately those whose λ was under-estimated, so they out-score their
> prediction; the high bucket is the mirror image.
>
> Planting goals that are *exactly* independent Poisson and stratifying on a λ
> carrying log-scale noise of sd 0.20 reproduces the gradient almost exactly:
> quartiles 1.1550 / 1.0260 / 1.0148 / 0.9622, spread +0.193, against the real
> +0.190. Pinned as a permanent test
> (`test_lambda_quartile_gradient_appears_under_a_pure_poisson_null`).
>
> Note the corollary: the same noise inflates the *overall* ratio to 1.0229 under
> a pure-Poisson null, above the 1.0130 actually measured. The measured figure is
> an upper bound on true over-dispersion, not a point estimate of it.

---

## P0-2 · Draw mass and the Dixon–Coles τ — **CLOSED: do not add the diagonal**

**Decision: do not implement the Dixon–Coles τ correction.** The draw deficit is
real; τ is the wrong instrument for it and buys nothing on either served market.

| | value | 95% CI |
| --- | --- | --- |
| realised draws | 26.26% | |
| independent Poisson expects | 25.39% | |
| **deficit** | **+0.87 pts** | [+0.32, +1.41] |
| fitted ρ | −0.0146 | **[−0.0283, +0.0005]** |
| Δ logloss, 1X2 | −0.000093 | |
| Δ logloss, O/U 2.5 | **0.000000** | |

Low-score cells, observed against expected:

| cell | observed | expected | ratio |
| --- | --- | --- | --- |
| 0-0 | 1,868 | 1,915.5 | 0.975 |
| 1-0 | 2,559 | 2,583.9 | 0.990 |
| 0-1 | 2,063 | 2,147.1 | 0.961 |
| 1-1 | 2,960 | 2,841.7 | **1.042** |

Four independent reasons not to ship it:

1. **ρ's confidence interval contains zero.** The point estimate has the
   expected negative sign, but it is not distinguishable from no effect.
2. **The 1X2 gain is −0.000093 logloss.** gtleague declined a correction worth
   −0.0004 as not worth serving; this is four times smaller than that.
3. **The O/U gain is exactly zero, structurally.** τ redistributes mass between
   the 0-0, 1-0, 0-1 and 1-1 cells, whose totals are 0, 1, 1 and 2 — all below
   the 2.5 line. No redistribution among them can move a 2.5 probability by any
   amount. τ is incapable of affecting the market SPEC §OPEN-7 prioritises.
4. **It does not even fix the thing it is for.** Applying the fitted ρ lifts
   predicted draws from 25.39% to 25.74% against a realised 26.26% — closing
   about 40% of a gap that is itself under one point.

**The deficit is real and remains unexplained**, and it is not uniform:

| division | realised | expected | deficit | 95% CI |
| --- | --- | --- | --- | --- |
| E0 | 23.44% | 23.66% | **−0.22 pts** | [−1.43, +0.96] |
| E1 | 26.91% | 25.69% | +1.21 pts | [+0.23, +2.24] |
| E2 | 26.65% | 25.51% | +1.15 pts | [+0.14, +2.15] |
| E3 | 27.18% | 26.19% | +0.99 pts | [−0.01, +2.07] |

**The Premier League has no draw deficit at all**; the effect lives entirely in
the three lower divisions, where it is around +1 point and consistent. This is a
population fact, not a distribution-family fact, and a score-cell correction is
the wrong shape of tool for it — the natural candidates are behavioural (game
state late in low-scoring matches) and belong in P4, gated on top of the P1+P3
base. **Feeds OPEN-6 directly**: E0 and E1–E3 differ on a measurable axis before
any calibration is fitted, which is evidence against pooling them.

Contradicted expectation: SPEC §2.4 predicted "a larger deficit at lower λ" than
gtleague's +1.13 points. The pooled deficit is **+0.87**, smaller — and at E0,
the lowest-scoring-variance population, it is zero.

---

## P0-3 · Margin dispersion — **CLOSED: the veto does NOT transfer**

**Decision: lift the standing veto on Asian handicap and correct score.** Both
may be priced off this pmf, subject to the same per-population calibration
everything else gets.

| | value | 95% CI |
| --- | --- | --- |
| `Var(margin \| λ) / E[λ]` | **0.9900** | [0.9702, 1.0095] |

Tail mass, observed against independent-Poisson expectation:

| threshold | observed | expected | ratio |
| --- | --- | --- | --- |
| \|margin\| ≥ 3 | 13.167% | 13.646% | 0.965 |
| \|margin\| ≥ 4 | 4.279% | 4.570% | 0.936 |
| \|margin\| ≥ 5 | **1.374%** | **1.365%** | **1.006** |
| \|margin\| ≥ 6 | 0.372% | 0.374% | 0.995 |

This is the sharpest reversal of the three. gtleague measured independent
Poisson **over-dispersing the margin by ~29%**, predicting 3.4% of mass on
\|margin\| ≥ 5 against 1.1% realised, and made that a standing veto on every
market priced off the pmf's tails. Here the ratio is 0.990 with an interval
containing 1.0, and the ≥ 5 tail is accurate to within 0.01 percentage points.

The reason is visible in P0-1: gtleague's veto was a consequence of its +0.166
residual correlation, which fattens the total but is *subtracted* at the margin.
With correlation at +0.0115 here, the mechanism that produced the veto is
essentially absent, so the veto has nothing to stand on.

**Caveat, and it is not a formality.** \|margin\| ≥ 3 and ≥ 4 are mildly
over-predicted (0.965 and 0.936). Those are the region most Asian handicap lines
actually sit in, so "the veto is lifted" means the pmf is structurally sound
enough to price from — not that AH prices are ready to serve. Calibration per
division and information set still applies, and an AH head needs its own gate.

---

## Instrument used for all three

A time-decayed ridge Poisson (`engine/models/poisson.py`), fitted jointly across
E0–E3, refit fortnightly, predicting only matches after the fit window. **Its
hyperparameters were frozen, not swept**: half-life 200 days (mid-range of the
defensible [100, 300] window in SPEC §3.2) and ridge α = 1.0. Sweeping them here
would have spent trials against the development set to tune a measuring device.

Calibration on the measurement set: mean predicted total 2.603 against 2.594
realised, over 24,167 matches.

The harness itself is validated against data with known answers before being
believed — exactly-Poisson corpora must measure as Poisson, and planted
over-dispersion, planted draw inflation and planted side-correlation must each
be detected (`tests/test_dispersion.py`). A 60-corpus study put the estimator at
mean 1.00020 (sd 0.0088) for n=30k under a true-Poisson null, with bootstrap CI
coverage 40/40 against a nominal 95%.
