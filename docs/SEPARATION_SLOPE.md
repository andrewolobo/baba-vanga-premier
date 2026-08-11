# The separation slope — review of the one resolved, controlled, unfixed defect

Written **2026-08-11** as a review; **§2's item was then executed the same day**
and that section now carries a result. Nothing here was run against a *real*
match outcome. Every number is quoted from `OUTSTANDING.md` §9.6, re-derived
from the committed `docs/home_term_step2.json` / `docs/home_term_step3.json`,
or — in §2 — produced by `--step 4` on **synthetic** outcomes. **§9 is the
exception and is a real gate**: `--step 5` reads real outcomes on the away leg,
booked by the owner at 3 configurations. Ledger: `home_term_slope_controls`
(probe, 0) and `home_term_away_leg` (gate, 3). **189 → 192.**

Subject: the finding in `OUTSTANDING.md` §9.6 step 2 — that the head's outcome
probabilities are miscalibrated as a function of how lopsided the fixture is
predicted to be, and that the λs themselves are correctly scaled *for goals*.
Code `engine/eval/home_term.py`, ledger `home_term_power` (probe, 0),
`home_term_dispersion` (3), `b2_calibration_in_product` (3).

**Headline: the finding survives review and the framing does not. "Resolved,
controlled, unfixed" is right on two of three words — the controls that license
it exist only as prose in `OUTSTANDING.md` and cannot be re-run. Separately, on
the home leg the effect is not a gradient at all: four fifths of the data are
flat and the top separation quintile carries it, which is a different mechanism
from the over-shrinkage story attached to it.**

Re-derive the shape argument with:

```
python -c "
import json, numpy as np
r=json.load(open('docs/home_term_step2.json'))['step2']['diagnostic']['rows']
x=np.array([c['mean_d'] for c in r]); h=np.array([c['home'] for c in r])
print(np.polyfit(x,h,1)[0], np.polyfit(x[:4],h[:4],1)[0])"
```

---

## 1. What the defect is

The served head produces `(λ_h, λ_a)` per fixture and maps them to `(H, D, A)`
through an independent-Poisson score matrix at `rho=0`
(`selection.raw_probs` → `dispersion.score_matrix`). Write the fixture's
predicted separation as

```
d = (log λ_h − log λ_a) / 2
```

so that `mean(d)` is home advantage and `d − mean(d)` is the strength spread
(`home_term.separation`, pinned by `test_separation_coordinates_round_trip`).

Regressing the home calibration gap — delivered minus claimed, in points — on
`d` per match, with a week-block bootstrap, on 15,824 out-of-sample matches
(2014-15 → 2022-23):

| population | slope, pts per unit d | 95% block CI | resolves? |
| --- | --- | --- | --- |
| **pooled** | **+5.66** | [+1.71, +9.41] | **✱** |
| E0 | +0.79 | [−3.90, +5.54] | no |
| E1 | +6.85 | [−2.42, +16.00] | no |
| **E2** | **+12.22** | [+2.58, +21.62] | ✱ — **but see below** |
| **E3** | **+15.73** | [+5.62, +26.15] | **✱** |

> **Corrected 2026-08-11 by §9.** All five figures reproduce exactly under
> `--step 5`. But the division cells are **uncorrected**, as §6 flagged, and
> **E2 does not survive Bonferroni** across the eight-cell family: corrected
> interval **[−1.45, +25.97]**. Of the eight division × leg cells only **home E3
> and away E2** survive. Read the ✱ on E2 as uncorrected-only.

The λs are not the problem. The deviance-optimal stretch of the centred
separation is ~1.05 pooled, and applying it leaves every gap where it was —
pooled home +0.33 → +0.32, E0 home +1.77 ✱ → +1.74 ✱. E3, which has the
steepest outcome slope, wants λ **compression** on goals (s ~0.95). The two
metrics point in opposite directions in the same division.

**That is the whole finding: the defect is in the λ → outcome mapping, and goal
Poisson deviance — convention 2's selection metric — is structurally blind to
it.** It is the reason this survived every gate the project has run.

---

## 2. The control was not reproducible — **FIXED 2026-08-11**

> **Item 1 is done.** `engine/eval/home_term.py --step 4`, tests in
> `tests/test_home_term.py`, results `docs/home_term_step4.json`, ledger
> `home_term_slope_controls` (probe). **Runs 98 → 99, questions 55 → 56,
> configurations 189 → 189** — verified with `trials.count_configurations`
> after the run, not asserted before it. **The finding survives, with one
> partial reproduction and one new result the original control did not
> produce.** The section below records what was wrong and what the rebuild
> found.

### What was wrong

`OUTSTANDING.md` §9.6 recorded two controls run during a grounding pass after
step 2 shipped without one — Null A at **+0.10 ± 1.49**, and a P0-1 noise sweep
at **−0.27 / −3.82 / −14.26 / −27.57 / −53.12**. **Neither existed as code.**
`home_term.py` had steps 1, 2 and 3 and nothing else, `tests/test_home_term.py`
did not contain them, no JSON held them, and the ledger had no row between
`home_term_dispersion` (2026-08-10 14:51) and `b2_calibration_in_product`
(15:20). That is `OUTSTANDING.md` §1.7's row-53 defect landing on the control
that licenses the project's only live modelling finding, and §9.6's *"do not
skip this control if the slope is ever revisited"* could not be obeyed.

### What the rebuild found

**Null A — the instrument is unbiased on both legs.** 40 draws, goals
Poisson-resampled from the served λs so the λ → outcome mapping is correct by
construction:

| leg | slope, mean ± sd | min | max | sem |
| --- | --- | --- | --- | --- |
| home | **−0.01 ± 2.05** | −3.39 | +5.95 | 0.32 |
| away | **+0.00 ± 1.79** | −5.97 | +2.49 | 0.28 |

**And a second question §9.6 never asked: is the published interval honest?**
`slope_ci` is the estimator step 2 and step 3 both quote, so running it on every
null draw turns coverage into a measurable false-positive rate. It is nominal —
**3/40 on home, 1/40 on away, 4/80 = 5.0% against a nominal 5%** — and the sd
the interval implies matches the true null spread at a ratio of **0.90 (home)
and 1.00 (away)**. The intervals in §9.6, §9.7 and step 3 are not too narrow.

**This gives the headline a second, bootstrap-free reading.** Step 2's pooled
home slope of **+5.66 is 2.77 null sd**. Resolved, and by a route that does not
depend on the block bootstrap at all. Note this is **less** than the "~4σ"
§9.6's prose claimed from ±1.49 — the true null sd is wider than that figure
implied, so the finding is real but nearer the boundary than advertised.

**The noise sweep reproduces its sign and not its magnitudes.** Outcomes from
the clean λs; the noisy λ̂ is what the arm both predicts with and stratifies on,
which is the real situation. The outcome draw is held fixed across the ladder so
the levels are paired.

| noise | home, mean ± sd | away, mean ± sd | §9.6 quoted (home) |
| --- | --- | --- | --- |
| 0.00 | +0.39 ± 2.81 | +0.85 ± 2.67 | −0.27 |
| 0.05 | −1.55 ± 2.38 | +2.69 ± 2.65 | −3.82 |
| 0.10 | −6.75 ± 2.55 | +7.25 ± 1.90 | −14.26 |
| 0.15 | −13.64 ± 2.29 | +13.38 ± 2.56 | −27.57 |
| 0.20 | **−20.45 ± 1.39** | +19.02 ± 1.90 | **−53.12** |

**Strictly decreasing in noise, as claimed — and 2.6× smaller than quoted at the
top of the ladder.** The load-bearing claim is the *sign*: λ noise pushes the
home slope negative, so it can only ever **mask** step 2's positive finding,
never manufacture it. That reproduces. The magnitudes do not, and per
`CHANNELS.md` §7's row-53 precedent **§9.6's quoted numbers stay
unattributable** — only this run's own contrasts carry weight.

### What this changes for item 2

The away leg now has a **reference distribution before it is ever measured on
real data**: unbiased, null sd **1.79**, honest intervals. Item 2 was previously
a measurement with no evidence the estimator behaved on that leg. It is now
licensed.

### Two process notes

**A 6-draw version of this control would have produced a false alarm.** The
first run used the project's usual six draws; draw 0 came in at +5.95 — the
maximum of the eventual 40 — and its interval excluded zero, which reads as *the
instrument fires under a correct-by-construction null*. Six draws also put the
null sd at 2.89 against a true 2.05. **Null A is estimating a distribution, not
a mean, and six draws cannot do it.** `NULL_DRAWS = 40`, and the reason is in
the constant's docstring.

**Related, and unchanged:** the entire §9.5/§9.6/B12 workstream is still
uncommitted to git — `engine/eval/draws.py`, `engine/eval/home_term.py`,
`engine/eval/channels_gate.py`, their tests and six result JSONs.
`OUTSTANDING.md` §1.1's shape, recurring.

---

## 3. On the home leg it is a top-quintile effect, not a gradient

This is the substantive correction. `gap_by_separation` reports five equal-count
buckets of `d`, and the profile is not what a slope implies:

| bucket | n | mean d | home gap | away gap |
| --- | --- | --- | --- | --- |
| 0 | 3,165 | −0.152 | −0.26 [−1.89, +1.40] | +0.57 [−1.14, +2.34] |
| 1 | 3,165 | +0.020 | −0.86 [−2.52, +0.77] | +0.01 [−1.59, +1.72] |
| 2 | 3,164 | +0.102 | −0.44 [−2.18, +1.27] | −2.24 [−3.82, −0.56] ✱ |
| 3 | 3,165 | +0.184 | +0.08 [−1.64, +1.77] | −0.87 [−2.44, +0.65] |
| **4** | 3,165 | +0.353 | **+3.12 [+1.51, +4.75] ✱** | −2.85 [−4.01, −1.63] ✱ |

Four buckets sit flat around zero, none of them resolving and with no monotone
trend among them, and the fifth jumps by three points. Re-fitting step 2's
polyfit over the bucket means:

| buckets used | home slope | away slope |
| --- | --- | --- |
| all five (as published) | **+6.58** | −6.64 |
| **drop the top bucket** | **+0.80** | −6.11 |
| drop the bottom bucket | +12.17 | −6.80 |

**Removing one fifth of the data takes the home slope from +6.58 to +0.80.**

Over-shrinkage of strength dispersion predicts a smooth gradient across all of
`d`, positive at the home-favoured end and sign-flipping at the away-leaning
end. What the data shows on the home leg is **flat, then a step in the most
lopsided 20% of fixtures**. Those are different mechanisms and they imply
different fixes: a global stretch cannot produce a step, and a fix aimed at the
tail of `d` is not a shrinkage correction.

**The honest one-line statement of the home leg is therefore: *the head
under-predicts home wins by ~3.1 points in the most lopsided fifth of fixtures,
and is calibrated everywhere else.*** That is narrower than "the calibration gap
rises with separation", and it is more useful, because it names the population.

**Caveat, stated plainly.** The published +5.66 is a per-match regression with a
block-bootstrap CI; the +6.58/+0.80 contrast above is step 2's five-point
polyfit, which carries no interval — that is precisely the estimator §9.6
replaced. Bucket-drop arithmetic is a diagnostic of shape, **not** a test. It
is strong enough to say the linear reading is unsafe and to justify testing
non-linearity properly; it is not itself the test. See §7 item 3.

> **Two corrections, 2026-08-11, from §10.**
>
> **The buckets are unevenly spaced and this section reads them as if they were
> not.** Widths in `d` are 0.172, 0.082, 0.082, 0.169 — the top and bottom
> quintiles reach much further out than the middle three, so a *pure gradient*
> already produces a bucket profile that looks flat in the middle and jumps at
> the ends. Some of the "step" is that.
>
> **And the residual pattern is not a step.** Against the full five-bucket line
> the home residuals are **+1.08, −0.65, −0.77, −0.79, +1.13** — both ends
> above, middle below, which is **convexity**, not flat-then-jump. Away's are
> −0.03, +0.54, −1.16, +0.76, −0.10, with no pattern. Every one of these sits
> inside the bucket CIs (~±1.65), so neither reading is established.
>
> **§10 then establishes that this corpus cannot settle it**, so the honest
> statement of the home leg is weaker than the one below: *the gap rises with
> separation, and whether that is a gradient or a tail effect is not
> resolvable here.*

---

## 9. The away leg, measured — **2026-08-11. §4's prediction holds.**

`--step 5`, ledger `home_term_away_leg` (gate, **3 configurations**, 189 → 192),
results `docs/home_term_step5.json`. Item 2 of §8. Same three arms as step 3 —
raw, B2 calibrated, matched sham — inherited rather than re-chosen. **The home
leg reproduces step 3 to the last decimal in all five populations**, which is
the check that nothing else moved.

Every slope is also read against a **per-population null sd** from 200 synthetic
draws (`null_sd_by_population`, reads no real outcome). Step 4's pooled figure
cannot be reused per division — E0 is 2,948 matches against 15,824 — and the two
independently-seeded pooled estimates agree at **2.07 / 1.73** here against
**2.05 / 1.79** in step 4.

**The shipped arm, both legs:**

| leg | pooled | E0 | E1 | E2 | E3 |
| --- | --- | --- | --- | --- | --- |
| home | **+5.66** ✱ (2.7σ) | +0.79 | +6.85 | +12.22 ✱ | **+15.73** ✱ |
| **away** | **−6.12** ✱ **(3.5σ)** | −2.36 | −8.25 | **−14.80** ✱ **(3.3σ)** | −7.01 |

**§4 was right: the away leg is the larger error and it resolves more strongly**
— −6.12 [−9.8, −2.4] against home's +5.66, at 3.5σ against 2.7σ.

**But the two legs do not have the same division profile, and that is new.**
Home rises monotonically E0 → E3. Away does not: **E2 carries it at −14.80 and
E3 collapses to −7.01**, below E1. §9.6's "the separation slope lives in E1–E3"
is a **home-leg** statement. On the away leg it is an **E2** statement, and E3 —
the steepest division on home — is unresolved on away.

**Bonferroni, which §6 flagged as unchecked.** Across the eight division × leg
cells of the shipped arm:

| survives | lost to correction |
| --- | --- |
| **home E3** [+1.39, +29.79], **away E2** [−26.17, −2.87] | **home E2** [−1.45, +25.97] |

So §6's worry was half-justified: one of the three uncorrected-significant cells
does not survive, and it is one this document published as resolved. Pooled is a
single pre-specified test and is unaffected — both legs resolve there.

**The sham beats the real defect on both legs, and this is the sharpest form of
§5's warning.** A temperature sharpener carrying **no outcome information at
all** produces home **−14.65 (−7.1σ)** and away **+11.79 (+5.5σ)** — larger, on
both legs, than the miscalibration actually present. Whatever the separation
slope is, a blind perturbation moves it further than the real thing does.
**Zeroing it is not evidence of anything.**

**B2's calibration removes the resolved pooled slope on both legs** — home +2.36
(1.1σ), away −2.71 (−1.6σ), neither resolving — while leaving **E3 home
(+12.13 ✱)** and **E2 away (−10.85 ✱)** in place. Consistent with §7.

---

## 10. The linearity test — **CONTROLLED 2026-08-11. Do not run it.**

`--step 6`, ledger `linearity_controls` (probe, **0 configurations**, 192
unchanged), results `docs/home_term_step6.json`. Item 3 of §8.

**The control refuted the test before it ran.** §8 item 3 priced the linearity
test at ~1 configuration and said it "decides whether the mechanism is
shrinkage or a tail effect". It does not, because **on this corpus the two
mechanisms produce the same curvature to within the noise of a single
measurement.**

### The design

Per-match regression of the calibration gap on **centred** `d`, quadratic:
`gap ~ a + b·d + c·d²`. Fitted per match rather than over bucket means, which
also removes the problem that makes §3 hard to read — the five quantile buckets
are unevenly spaced in `d` (widths 0.172, 0.082, 0.082, 0.169), so the top and
bottom buckets sit much further out than the middle three and a pure gradient
already produces uneven bucket means.

Three planted truths, all on synthetic outcomes:

- **C1 null** — correct mapping. Both coefficients must vanish.
- **C2 over-shrinkage** — outcomes drawn from λs whose centred separation is
  `s×` the head's, scored against the head's own. §9.6 step 2's hypothesis,
  planted, at s = 1.05 / 1.10 / 1.12 / 1.15 / 1.20.
- **C3 top-quintile step** — outcomes tilted in the top quintile of `d` only,
  by 1.0 / 2.0 / 3.0 / 4.0 / 4.5 pts of P(home). §3's hypothesis, planted.

### C1 — the statistic is honest, and curvature is much harder to see than slope

| leg | linear | quadratic | quad excludes zero |
| --- | --- | --- | --- |
| home | +0.07 ± 1.70 | +0.45 ± **4.24** | 2/40 |
| away | −0.25 ± 1.47 | −0.32 ± **4.76** | 3/40 |

Unbiased, coverage nominal (5/80 = 6.25%). But **the quadratic's null sd is
~2.8× the linear's** — the price of asking about shape rather than direction,
and it is what sinks the test.

### The discriminating read

Matched at the level that reproduces the **observed** home slope of +5.66:

| leg | shrinkage implies | step implies | apart | null sd | σ | |
| --- | --- | --- | --- | --- | --- | --- |
| home | +0.20 | +6.38 | 6.18 | 4.24 | **1.46** | cannot separate |
| away | **+4.39** | **−3.57** | 7.96 | 4.76 | **1.67** | cannot separate |

**Neither leg reaches 1.96.** A single real measurement could not tell an
over-shrunk head from a tail-mis-mapped one.

**Three things worth carrying forward:**

- **The away leg is the better instrument, and the two mechanisms have opposite
  signs there** — shrinkage +4.39, step −3.57, against home's +0.20 / +6.38
  where both are positive. If this is ever revisited, **the away quadratic is
  the statistic and its sign is the read.** Nobody would have guessed that from
  §3, which is a home-leg argument.
- **What would close it is exactly the whole holdout, and that is the point.**
  σ scales as √n, so reaching 1.96 needs **1.38× this corpus — 21,797 matches
  against 15,824, or 5,973 more.** The three sealed seasons are 2,036 each,
  **6,108 in total.** Unsealing the entire holdout would cross the threshold
  with **135 matches to spare.** That is the most expensive act available to this
  project buying a bare threshold crossing on a diagnostic that decides no
  adoption. Compare §1.4, where the same act does not reach the answer at all.
- **This is §1.12's lesson working.** The control ran first and alone, and
  refuted the plan for **0 configurations** — the same shape as H37 refuting
  B12's headline prediction, except here it arrived in time to prevent the
  spend rather than after it.

**Do not** re-attempt with a cubic, finer buckets, or a per-division split. All
three spend more degrees of freedom on a statistic whose null sd is already the
binding constraint, and §1.4's closure is the precedent.

**What this does to item 4.** The zeroing-stretch diagnostic does **not** depend
on knowing the shape — it prices a stretch in goal deviance and tests the "the
λs are fine, the mapping is broken" conclusion directly. It is now the only
remaining item in §8 and it stands on its own.

---

## 4. The two legs behave differently, and only one has ever had an interval

The away leg does *not* collapse when the top bucket is dropped (−6.64 → −6.11),
and two of its five buckets resolve against one of the home leg's. On the
evidence available, **the away leg looks like the gradient and the home leg
looks like the tail effect.**

This matters because the away leg is the larger error. From §9.5's pooled
decomposition: away **−1.07 ✱**, home +0.33 (unresolved), draw +0.75 ✱. The away
win is the largest resolved miscalibration the head has.

And [`home_term.py:467`](../engine/eval/home_term.py#L467) computes the slope on
the home gap only:

```python
gap = (ftr[j] == "H").astype(float) - probs[j, 0]
```

So `slope_ci` has never been run on the away leg — no interval, in any
division, for any of the three arms. §9.6 and `OUTSTANDING.md` both speak of
"the separation slope" as a single quantity. It is two quantities, they have
different shapes, and the one with an interval is the smaller of the two.

> **DONE 2026-08-11 — §9 has it.** Away pooled is **−6.12 [−9.8, −2.4] ✱**
> against home's +5.66, at **3.5σ against 2.7σ**. This section's claim that away
> is the larger error and the better-resolved one is confirmed. What it did not
> anticipate: **the division profiles differ**. Home rises monotonically E0 → E3;
> away peaks at **E2 (−14.80 ✱)** and collapses at **E3 (−7.01, unresolved)**.

---

## 5. "No stretch fixes it" was never tested

[`fit_stretch`](../engine/eval/home_term.py#L222) minimises **goal Poisson
deviance**, deliberately and correctly — a stretch chosen on 1X2 would be
optimised on one metric and adjudicated on another. Step 2's three arms are
`s = 1`, `s` fitted pooled, and `s` fitted per division.

What that establishes is that the **deviance-optimal** stretch does not move the
outcome gap. It does not establish that no stretch does, and the documents state
the stronger claim.

Step 3's own control settles the direction. The three arms give a monotone dial
on the pooled slope:

| arm | pooled slope | resolves? |
| --- | --- | --- |
| raw (shipped) | **+5.66** [+1.71, +9.41] | ✱ |
| B2 calibrated | +2.36 [−1.61, +6.08] | no |
| sham (temperature sharpening, blind) | **−14.65** [−18.61, −10.90] | ✱ |

A mapping-level perturbation carrying **no outcome information at all** drives
the slope well past zero. So a zero crossing exists, it is between B2's
calibration and the sham, and nobody has looked for it.

**This cuts both ways and the second edge is sharper.** That a blind sharpener
can zero the slope means zeroing the slope is *not* evidence of having found the
mechanism — it is a dial, and this project has now watched three dials move
these gaps around while buying nothing. §9.5's planted ρ was the best arm at
five times the fitted value; B2's calibration shifts the `12`/`1X` mix three
times harder than τ and returns +0.088, unresolved. **Fitting a fourth dial to
the slope would repeat that pattern, not break it.**

The useful version of this arm is therefore diagnostic, not corrective: find the
stretch that zeroes the slope and **price it in goal deviance**. If it costs
little, the "the λs are fine and the mapping is broken" conclusion is wrong and
the defect is in λ where deviance simply cannot see it. If it costs a lot, the
conclusion is confirmed and has a number attached for the first time.

---

## 6. Two smaller things

**The per-division split is uncorrected.** Four divisions × two legs is eight
cells; E2 and E3 exclude zero at uncorrected 95%. **Whether they survive
Bonferroni has not been checked** — the intervals are wide enough that they
plausibly do, but `OUTSTANDING.md` §1.5's ≤3-days-rest finding is the precedent
for this going the other way, and it is the shape a false positive takes here.
The pooled +5.66 is a single test and is unaffected.

> **CHECKED 2026-08-11 — §9. The guess in this paragraph was wrong.** "The
> intervals are wide enough that they plausibly do" — one of them does not.
> Across the eight cells, **home E3 and away E2 survive; home E2 does not**
> ([−1.45, +25.97]). §1's table is corrected in place. The §1.5 precedent was
> the right one to cite.

**Scaled by each division's own spread the gradient is real but smaller than the
raw slopes suggest.** Mean `d` is identical across divisions (+0.101 to +0.102),
which is §9.6's arithmetic for why a slope cannot produce a division-specific
mean gap. The spreads are not:

| division | slope | sd(d) | pts per 1 sd of d |
| --- | --- | --- | --- |
| E0 | +0.79 | 0.315 | +0.25 |
| E1 | +6.85 | 0.148 | +1.01 |
| E2 | +12.22 | 0.150 | +1.83 |
| E3 | +15.73 | 0.125 | +1.97 |

E0 flattest and E3 steepest survives; the ratio is **8×, not 20×**. §9.6's
"E0's defect is a level offset; the separation slope lives in E1–E3" stands,
with the qualification that E1 does not resolve, so "E1–E3" means E2 and E3
uncorrected.

**Minor process note.** The estimator changed from a five-point polyfit to a
per-match block-bootstrapped regression *after* the real result was seen. It
moved in the direction of rigour and the point estimate barely moved
(+6.58 → +5.66), so this is not `CALIBRATION.md` §1's failure — but by the
precedent `P4_TRAVEL_PLAN.md` §8 sets, a detection statistic that changes after
real numbers are in view is worth naming rather than leaving implicit.

---

## 7. What this is worth, and the coupling nobody had drawn

**The published claim is honest, and the reason is a cancellation.** The honesty
gap on the actual published pick is **−0.06 pts** raw (claims 72.55%, delivers
72.49%). The slope is real and the headline number is fine, because `12` = home
+ away carries the two opposite-signed legs and cancels them — and `12` is
**65.0%** of output.

**So the separation slope and B13 are the same decision.** Switching the tip rule
to B2's calibrated probabilities cuts `12` from 65.0% to **47.7%** and raises
`1X` from 17.6% to **30.5%**:

| | raw (shipped) | B2 calibrated |
| --- | --- | --- |
| strike rate | 72.49% | 72.58% — +0.088 [−0.410, +0.556], unresolved |
| honesty gap on the published pick | **−0.06** | **+0.50** |
| pooled separation slope | +5.66 ✱ | +2.36, not resolved |
| E3 separation slope | +15.73 ✱ | **+12.13 ✱** |
| `12` / `1X` share | 65.0 / 17.6 | 47.7 / 30.5 |

`BACKLOG.md` B13 currently frames this as *"the price is approximately zero"*.
The price is approximately zero **in strike rate**. What the change also does is
stop the published claim resting on a cancellation inside `12` and start it
resting on the calibrated mapping — which still carries a resolved slope in E3.
Neither honesty gap has a confidence interval; `home_term.step3` computes the
point estimate only.

**That belongs in B13 before the decision is taken.** It does not obviously
argue against B13 — +0.50 is small and in the conservative direction — but it is
a consideration the item does not currently carry, and B13 is an owner call.

---

## 8. Recommended order, with costs

1. ~~**Commit the two controls as code.**~~ **DONE 2026-08-11 — §2.**
   `--step 4`, ledger `home_term_slope_controls`, 0 configurations, 189
   unchanged. Both legs unbiased, `slope_ci`'s coverage nominal, the noise
   ladder's sign reproduced and its magnitudes not. Step 2's +5.66 re-read as
   **2.77 null sd** rather than the ~4σ §9.6 claimed.
2. ~~**Run `slope_ci` on the away leg.**~~ **DONE 2026-08-11 — §9.** Ledger
   `home_term_away_leg`. **The owner booked it at 3 configurations** — one per
   arm, symmetric with `b2_calibration_in_product` on the home leg, and more
   than either figure this item named. **189 → 192.** Away pooled −6.12 ✱ at
   3.5σ, the larger and better-resolved leg; the division profiles differ; and
   Bonferroni costs home E2.
3. ~~**Test the home leg's linearity.**~~ **CONTROLLED AND DROPPED
   2026-08-11 — §10.** Ledger `linearity_controls`, probe, **0 configurations**.
   The control refuted the test: over-shrinkage and a tail step produce
   curvature only **1.46σ (home) / 1.67σ (away)** apart against the noise of a
   single measurement, so the statistic cannot decide the mechanism. Closing it
   needs 1.38× this corpus, and the entire holdout clears that by 135 matches.
   **The real measurement was never run and should not be.**
4. **Find the stretch that zeroes the slope and price it in goal deviance.**
   **~1 configuration.** Diagnostic, per §5 — it tests the "the mapping is
   broken, not the λs" conclusion rather than attempting a correction. **Now the
   only remaining item**, and §10 confirms it does not depend on item 3: it
   prices a stretch in deviance rather than needing the defect's shape.

**Do not** reach for a fix. Three arms have now moved this dial and none bought
strike rate — the deviance-optimal stretch, B2's calibration, and τ — and §9.5's
monotone-in-|ρ| result is still unexplained. A fourth arm needs a reason the
first three did not have. **Knowing the shape of the defect was going to be that
reason, and §10 establishes that this corpus cannot supply it** — which makes
the case for a fix weaker than when this document was written, not stronger.

**Do not** treat this document as licensing a head change. `OUTSTANDING.md`
§1.3 lists what a head change owes. §§2, 9 and 10 are measurements; the rest of
this document is review.
