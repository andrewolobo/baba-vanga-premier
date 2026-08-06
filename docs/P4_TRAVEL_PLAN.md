# P4-travel — pre-registration

Written **2026-08-06**, before any arm was fitted to real outcomes. Answers the
travel-distance clause of SPEC §3.6, picked up from `REST.md` §7, which named it
the best remaining candidate.

This document is written first and left unedited afterwards, in the manner of
`P1_PLAN.md`. Results go in `TRAVEL.md`.

---

## 1. Why this one, and what is different about it

`TOD_SLOT.md` closed the kickoff slot: the effect is real and this corpus cannot
resolve it, because `Time` does not exist before 2019-20 and only 5,644 scored
matches carry it. `REST.md` then measured the first replacement analogue and
returned a bounded null at ~3.5%.

Travel is the third. It has the property rest has and the slot does not — it
comes from data every row carries — and it needs one new input, now built:
`reference/stadiums.csv`, **151 clubs, 151 verified against an independent
geocode**, 100% coverage of all 33,158 dev match-sides.

**The feature is identified.** Measured before any arm: after removing both home
and away club fixed effects, **70% of the variance in away-trip distance
survives** (sd 85.6 km of 102.3 km). The club coefficients λ already fits do not
absorb it. Median trip 176 km, p10 53, p90 321, max 537.

## 2. What is held fixed

Per convention 9 — a hyperparameter chosen under an assumption inherits it — the
following are fixed before the sweep and are not tuned here:

- **Head**: `H400 / a0.1 / weekly / E0+E1+E2+E3+EC / sot0.3`, artifact
  `p1-3a38e9d6ef1ca7ee`, COVID embargoed from scoring. Unchanged from `REST`.
- **Selection metric**: goal Poisson deviance. 1X2 and O/U reported, never
  selected on.
- **Standard error**: paired bootstrap on ISO-week blocks. Never marginal.
- **Distance**: great-circle between home and away clubs' current grounds.
  Two stated approximations, neither tuned:
  1. **Great-circle, not road.** Newcastle–Plymouth is 538 km straight against
     roughly 660 by road, and the gap is widest exactly where the road network
     is worst — Plymouth, Norwich, Carlisle — which are the high-leverage rows.
  2. **The table is static.** Eight clubs changed ground inside the corpus
     (`reconcile.KNOWN_MOVES`). Only Rotherham changes town. This list is
     recalled, not verified, and is the weakest link in the input.
- **The travelling side is the away side.** Home travel is zero. Any effect is
  predicted on the away side's attacking rate.

## 3. The standing limitation, inherited from REST

The corpus is **league-only** — no FA Cup, League Cup or European ties. For rest
this made measured rest an *upper* bound. For travel it is milder and different:
the distance of every match in the corpus is correct, but total travel burden is
under-counted, because the trips to Cup and European away ties are missing
entirely. A cumulative-mileage or fatigue effect is therefore **not refuted by
this gate** and is not what it tests. What it tests is the per-match effect of
the distance a side travelled to the fixture being played.

## 4. Arms

| arm | parameters | form |
| --- | --- | --- |
| **A1 (primary)** | **1** | one fitted slope on away distance, applied to the away λ |
| A2 (secondary) | 5 | distance bands, multiplicative factor per band |

**A1 is primary and A2 is reported.** Two measured reasons, not a preference:
`TOD_SLOT` found nine fitted levels cost **+0.00112 nats** on the planted ×0 arm,
and `REST` found the one-parameter differential was both the form SPEC preferred
and the form whose null could not be blamed on spent degrees of freedom. A
corpus that punishes DOF should be asked the cheapest version of the question.

Both fitted **leave-one-season-out**, so every arm is out of sample.

## 5. The positive control, and the stop condition

Convention 8: a null needs a positive control or it is not a result. `REST`'s
H33 caught a planted 5% deficit **6 times out of 6**; `TOD_SLOT`'s H29 caught its
planted effect **2 of 6**, and that single number is what turned the slot from a
null into "underpowered", which is a different finding with a different action.

**The control runs first and alone.** It uses Poisson-resampled synthetic
outcomes, so it spends no information about the real answer. Planted effect: an
away attacking deficit **linear in distance**, `1 − p · d/500km`, at
`p ∈ {0, 2.5%, 5%, 10%}`.

**Stop condition — pre-committed.** If the ×1 plant (5% at 500 km) is not
recovered at ≥1.96 SE in **at least 4 of 6 draws**, the instrument is
underpowered and **A1 and A2 are not run on real outcomes.** The finding is then
the same shape as the kickoff slot — a real question this corpus cannot answer —
and it is reported as that, not as a null.

## 6. Predictions, recorded before running

Scored in `TRAVEL.md` §6, in the manner of `CALIBRATION.md` §6 and
`SHOTS_TARGET.md`.

1. **A1 recovers the ×1 plant (5% at 500 km) in ≥5 of 6 draws.**
2. The 1.96-SE resolution threshold lands **between 2% and 6%** at 500 km.
3. **A2 fitted to the ×0 plant costs between +0.0002 and +0.0010 nats** —
   between `REST`'s six-band +0.00020 and `TOD_SLOT`'s nine-level +0.00112.
4. **A1 fitted to the ×0 plant costs less than +0.0002 nats**, because one
   parameter cannot overfit the way five can.
5. The control passes the §5 stop condition, and the real arms become runnable.

## 7. Decision rule for the real arms, if they run

Pre-committed now so it cannot move after the numbers are seen:

- **Adopt** only if A1 improves goal deviance with a paired-bootstrap interval
  excluding zero, and the sign holds in at least three of the four served
  divisions. `SHOTS_TARGET` cleared a bar of this shape; nothing else has.
- **Bounded null** if A1 is flat and the control passed — report the effect size
  the corpus excludes, as `REST` §1.5 does.
- **Underpowered** if the control fails — report as `TOD_SLOT`, and do not
  spend more arms on it.

Whatever happens, the trials are recorded. A trial spends against the
development set whether or not its result is liked (§7.5).

---

## 8. AMENDMENT, 2026-08-06 — the detection statistic was the wrong one

Appended after the first control run, **before any arm touched real outcomes**.
Sections 1–7 above are left exactly as written.

**What happened.** The control failed its own stop condition: the ×1 plant (5%
at 500 km) was recovered **0 of 6** on the deviance-delta criterion, which put
the resolution threshold at 13.5%. Run on the identical planted frames, a direct
Poisson coefficient test recovers the same plant **6 of 6** at mean t = 3.35,
returns **β = −0.0499 against a planted −0.050**, and raises no false positive in
6 draws at ×0. Its threshold is **2.9% at 500 km** — 4.6× more sensitive on the
same data.

**Why the first choice was wrong.** A correctly-specified one-parameter fit
improves total deviance by about t²/2 ≈ 5.6 nats, spread across 21,896 matches:
0.00026 per match, against a paired-bootstrap standard error of ~0.00013 that is
dominated by the noise of the leave-one-season-out refit itself. For a *diffuse*
effect the deviance delta discards most of the signal. `REST`'s H33 passed 6/6 on
the same criterion because its plant was *concentrated* — 5% on a subpopulation,
applied to both sides — not because the criterion is generally adequate.

**Why amending is legitimate here, and what would have made it not.**
`CALIBRATION.md` §1 records a pre-registered bar that turned out wrong, and the
rule taken from it is that a bar which moves after seeing the numbers is not a
bar. The distinction is *which* numbers. That bar moved after seeing **real
results**. This one is being changed after seeing **Poisson-resampled synthetic
outcomes that carry no information about the real answer** — which is the entire
reason the control is specified to run first and alone. Discovering that the
instrument cannot see a known effect is the control working, not failing.

**The change, stated narrowly.**

- **The resolution question** — can this corpus see an effect of size X — is
  decided by the **coefficient test**. This governs the §5 stop condition and
  any bound reported for a null.
- **The adoption question** — is the feature worth putting in the head — remains
  **goal Poisson deviance**, per convention 2. Nothing about the selection metric
  changes, and no arm is adopted on a t-statistic.
- Both are reported for every arm. The gap between them is itself a finding:
  an effect that is real on the coefficient test and worthless on deviance is
  exactly the `TOD_SLOT` shape, and it should be visible rather than collapsed
  into one number.

**Predictions 1, 2, 3 and 5 in §6 stand as scored — one of five right.** They are
not rewritten. Prediction 2 is the informative one: "2–6% at 500 km" was right
about the corpus and wrong about the instrument, which is precisely the error
this amendment corrects.
