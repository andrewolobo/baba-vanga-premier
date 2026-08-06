# Measured and closed

Results with their numbers, including the nulls. A result is only "closed" here
if it was measured on this corpus; nothing is inherited from
`../baba.vanga.gtleague` without re-measurement.

Reproduce with `python -m engine.eval.dispersion`. Every entry is recorded in
`gate_ledger`, which is what gives later deflated-performance work a real trial
count.

> **Re-measured 2026-07-28 on the corrected corpus.** The original run had
> 2015-16 missing and 2014-15 double-weighted (`BASELINE.md` §4.2). All three
> measurements were re-run on the complete thirteen seasons with the instrument
> unchanged — same frozen H=200, α=1.0, fortnightly refit — so the only
> difference is the data. **All three decisions stand.** One supporting argument
> under P0-2 did not: ρ's confidence interval no longer contains zero, and that
> reason has been struck rather than quietly reworded. Figures below are the
> re-measured ones; the originals are shown alongside where they moved.

---

## P0-1 · Distribution family for totals — **CLOSED: Poisson is correct**

**Decision: do not change the distribution family. Serve O/U off the Poisson pmf.**

Measured 2026-07-28 on 24,167 development-set matches (2011-08 to 2023-05, E0–E3),
using out-of-sample λ from a walk-forward ridge Poisson refit fortnightly.
Re-measured the same day on the corrected corpus; figures below are the re-run.

| statistic | value | 95% CI | (originally) |
| --- | --- | --- | --- |
| `Var(total \| λ) / E[λ]` | **1.0103** | [0.9915, 1.0313] | 1.0130 |
| home side | 0.9920 | | 0.9952 |
| away side | 1.0112 | | 1.0093 |
| residual correlation | **+0.0098** | | +0.0115 |

The interval contains 1.0, so there is no evidence of over-dispersion at the
total. Per division: E0 1.0247 · E1 0.9986 · E2 1.0156 · E3 1.0062.

**The conclusion transfers but the mechanism does not, and that matters.**
gtleague reached its 0.978 through two large effects cancelling — side-level
under-dispersion of 0.84 against a residual correlation of +0.166. Here both
legs sit at ~1.0 individually and the correlation is +0.0098, i.e. seventeen
times smaller. English match sides are close to genuinely independent, whereas
gtleague's were strongly coupled and merely looked independent at the total.
Anything that relies on the *sides* being independent — and the margin pmf does
— is therefore on much firmer ground here than the shared headline number would
suggest. It would have been wrong to inherit the 0.978 and assume the same
structure underneath.

> **ORIGINAL (wrong): "dispersion worsens at low λ, where English mass sits".**
>
> Stratifying by predicted total produced a clean monotone gradient — 1.1177 in
> the lowest quartile falling to 0.9544 in the highest — which reads as exactly
> the low-λ breakdown SPEC §2.4 anticipated. **It is an artifact of stratifying
> on an estimate that carries error.** Matches sorted into the low bucket are
> disproportionately those whose λ was under-estimated, so they out-score their
> prediction; the high bucket is the mirror image.
>
> Planting goals that are *exactly* independent Poisson and stratifying on a λ
> carrying log-scale noise of sd 0.20 reproduces the gradient almost exactly:
> quartiles 1.1550 / 1.0260 / 1.0148 / 0.9622, spread +0.193, against the real
> +0.163. Pinned as a permanent test
> (`test_lambda_quartile_gradient_appears_under_a_pure_poisson_null`).
>
> Note the corollary: the same noise inflates the *overall* ratio to 1.0229 under
> a pure-Poisson null, above the 1.0130 actually measured. The measured figure is
> an upper bound on true over-dispersion, not a point estimate of it.

---

## P0-2 · Draw mass and the Dixon–Coles τ — **CLOSED: do not add the diagonal**

**Decision: do not implement the Dixon–Coles τ correction.** The draw deficit is
real; τ is the wrong instrument for it and buys nothing on either served market.

| | value | 95% CI | (originally) |
| --- | --- | --- | --- |
| realised draws | 26.35% | | 26.26% |
| independent Poisson expects | 25.45% | | 25.39% |
| **deficit** | **+0.90 pts** | [+0.34, +1.49] | +0.87 |
| fitted ρ | **−0.0213** | **[−0.0343, −0.0070]** | −0.0146 [−0.0283, +0.0005] |
| Δ logloss, 1X2 | −0.000145 | | −0.000093 |
| Δ logloss, O/U 2.5 | **0.000000** | | 0.000000 |

Low-score cells, observed against expected:

| cell | observed | expected | ratio |
| --- | --- | --- | --- |
| 0-0 | 1,885 | 1,907.3 | 0.988 |
| 1-0 | 2,557 | 2,581.0 | 0.991 |
| 0-1 | 2,027 | 2,147.3 | 0.944 |
| 1-1 | 2,969 | 2,854.4 | **1.040** |

> **Struck on re-measurement.** The original first reason was *"ρ's confidence
> interval contains zero — the point estimate has the expected negative sign but
> is not distinguishable from no effect."* **That is no longer true.** On the
> corrected corpus ρ = −0.0213 [−0.0343, −0.0070], which excludes zero. The
> Dixon–Coles dependence is real on this data. The decision does not change, but
> it now rests on three arguments rather than four, and the reason is recorded
> here rather than reworded away.

Three independent reasons not to ship it:

1. **The 1X2 gain is −0.000145 logloss.** gtleague declined a correction worth
   −0.0004 as not worth serving; this is still nearly three times smaller than
   that. For scale, the served head trails the market by **0.0098–0.0141 nats**
   (`BASELINE.md` §2), so τ would close about 1% of the gap it actually needs to
   close. *(Corrected 2026-08-06: this read 0.0117–0.0155, the range before the
   shots channel was adopted. The argument is unaffected — a smaller gap makes
   τ's share smaller still.)*
2. **The O/U gain is exactly zero, structurally.** τ redistributes mass between
   the 0-0, 1-0, 0-1 and 1-1 cells, whose totals are 0, 1, 1 and 2 — all below
   the 2.5 line. No redistribution among them can move a 2.5 probability by any
   amount. τ is incapable of affecting the market SPEC §OPEN-7 prioritises.
   **This is the one argument no re-measurement can touch**, and it is why the
   decision survived a result that moved against it.
3. **It does not fix the thing it is for, and it would misfire where there is
   nothing to fix.** Applying the fitted ρ lifts predicted draws from 25.45% to
   25.95% against a realised 26.35% — closing 56% of a gap that is itself under
   one point. Worse, τ is global while the deficit is not: **E0's deficit is
   +0.01 points.** A single ρ fitted across all four divisions would impose a
   diagonal correction on the Premier League, where the independent Poisson draw
   rate is already correct to within a hundredth of a point.

**The deficit is real and remains unexplained**, and it is not uniform:

| division | realised | expected | deficit | 95% CI |
| --- | --- | --- | --- | --- |
| E0 | 23.75% | 23.74% | **+0.01 pts** | [−1.19, +1.18] |
| E1 | 27.12% | 25.88% | +1.24 pts | [+0.24, +2.33] |
| E2 | 26.55% | 25.59% | +0.96 pts | [−0.11, +1.94] |
| E3 | 27.21% | 26.08% | +1.13 pts | [+0.13, +2.22] |

**The Premier League has no draw deficit at all** — on the corrected corpus it
is +0.01 points, which is as close to exactly zero as this measurement can
resolve. The effect lives entirely in the three lower divisions, where it is
around +1 point and consistent. This is a population fact, not a
distribution-family fact, and a score-cell correction is the wrong shape of tool
for it — the natural candidates are behavioural (game state late in low-scoring
matches) and belong in P4, gated on top of the P1+P3 base.

**Feeds OPEN-6 directly, and it is now the third independent line of evidence.**
E0 differs from E1–E3 on the draw rate (+0.01 vs ~+1.1 points), on how much of
the market's edge the base head captures (0.89 vs 0.51–0.64, `BASELINE.md` §2),
and on the sign of the season-boundary shrink (harms E0 1X2, helps E1–E3 O/U,
`BASELINE.md` §5). Three different measurements, none of them designed to test
pooling, all separating E0 from the rest. That is much stronger than any one of
them.

Contradicted expectation: SPEC §2.4 predicted "a larger deficit at lower λ" than
gtleague's +1.13 points. The pooled deficit is **+0.90**, smaller — and at E0,
the lowest-scoring-variance population, it is zero.

---

## P0-3 · Margin dispersion — **CLOSED: the veto does NOT transfer**

**Decision: lift the standing veto on Asian handicap and correct score.** Both
may be priced off this pmf, subject to the same per-population calibration
everything else gets.

| | value | 95% CI | (originally) |
| --- | --- | --- | --- |
| `Var(margin \| λ) / E[λ]` | **0.9909** | [0.9715, 1.0101] | 0.9900 |

Tail mass, observed against independent-Poisson expectation:

| threshold | observed | expected | ratio | (originally) |
| --- | --- | --- | --- | --- |
| \|margin\| ≥ 3 | 13.278% | 13.499% | **0.984** | 0.965 |
| \|margin\| ≥ 4 | 4.320% | 4.478% | **0.965** | 0.936 |
| \|margin\| ≥ 5 | **1.332%** | **1.321%** | **1.009** | 1.006 |
| \|margin\| ≥ 6 | 0.372% | 0.357% | 1.044 | 0.995 |

This is the sharpest reversal of the three. gtleague measured independent
Poisson **over-dispersing the margin by ~29%**, predicting 3.4% of mass on
\|margin\| ≥ 5 against 1.1% realised, and made that a standing veto on every
market priced off the pmf's tails. Here the ratio is 0.990 with an interval
containing 1.0, and the ≥ 5 tail is accurate to within 0.01 percentage points.

The reason is visible in P0-1: gtleague's veto was a consequence of its +0.166
residual correlation, which fattens the total but is *subtracted* at the margin.
With correlation at +0.0115 here, the mechanism that produced the veto is
essentially absent, so the veto has nothing to stand on.

**Caveat, and it is not a formality — though it is milder than first reported.**
\|margin\| ≥ 3 and ≥ 4 are still over-predicted, at 0.984 and 0.965, but the
re-measurement roughly halved the error (it was 0.965 and 0.936 on the corrupted
corpus). Those thresholds are the region most Asian handicap lines actually sit
in, so "the veto is lifted" means the pmf is structurally sound enough to price
from — not that AH prices are ready to serve. Calibration per division and
information set still applies, and an AH head needs its own gate.

The ≥ 6 tail moved the other way, 0.995 → 1.044, but that bucket holds 0.37% of
matches (~90 of 24,167) and the movement is well inside what that sample
supports.

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
