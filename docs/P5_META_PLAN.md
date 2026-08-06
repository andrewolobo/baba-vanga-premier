# P5 meta-label — implementation plan

Written **2026-08-06**, before any arm is fitted. Answers SPEC §3.8 ("Le Prado").
Results will go in `META.md`.

Every number in §1 was measured before the strategy in §2 was chosen, and two of
them changed it. Nothing here has been fitted to an outcome.

---

## 1. What the data says

Measured on the frozen head (`H400/a0.1/weekly/sot0.3`, artifact
`p1-3a38e9d6ef1ca7ee`), dev seasons, E0–E3. Structure and power only — no
conditional performance was computed, because that is the gate.

### 1.1 The training basis has to be rebuilt, and that is good news

`predictions`, `paper_bets` and `clv_grades` are **all empty**. SPEC §3.8's
"train on all leans, never surfaced picks" is therefore satisfied by
construction rather than by discipline: there are no surfaced picks, the book
has never run, and the survivorship loop it warns about cannot exist yet. The
basis is reconstructed from a walk-forward replay.

**Keep it that way.** The moment the book turns on, the basis must stay
all-legs.

### 1.2 The CLV-gradable sample splits hard by market

| market | close basis (as `p3.py` uses) | matches | legs | seasons |
| --- | --- | --- | --- | --- |
| **1X2** | de-vigged Pinnacle `close_ps_*` | **19,884** | **59,652** | 2012-13 → |
| O/U 2.5 | de-vigged `close_avg_over25` | 5,638 | 11,276 | **2019-20 →** |

1X2 by division: E0 4,180 / E1 6,070 / E2 5,913 / E3 5,950.

**The O/U basis is the 2019-20 cliff again.** 5,638 matches is within six of the
5,644 that made the kickoff slot unresolvable, and for the same reason —
`close_avg_*`, `close_max_*` and `close_b365_*` all start in 2019-20, at 30.1%
of the dev corpus, while Pinnacle's close starts in 2012-13 at 84.4%.

### 1.3 Best-available prices are 10× cheaper, and O/U is 3.6× worse than 1X2

Measured overround, and the vig each leg must beat:

| market | level | overround | vig / leg |
| --- | --- | --- | --- |
| 1X2 | average | 6.32% | 0.02107 |
| **1X2** | **best (Max)** | **0.60%** | **0.00201** |
| O/U | average | 6.08% | 0.03041 |
| O/U | best (Max) | 1.44% | **0.00718** |

`CALIBRATION.md` §5 already established best-price capture as a prerequisite.
This adds that the two markets are not equally worth capturing.

### 1.4 The mean is pinned; only selection can move it

The three 1X2 legs of a match have CLVs summing to **−0.00577** (sd 0.00923) —
that is the Max overround, mechanically. **Betting every leg returns
−0.00192/leg by construction**, which is the vig to five decimals.

So a meta-label cannot help by being well-calibrated on average. Its entire
value is in **ranking**: pushing volume toward legs whose CLV is above that
pinned mean. Any evaluation that reports a mean over all legs is measuring the
overround, not the model.

### 1.5 Power is not the constraint — this is the finding that changed the plan

sd(CLV) = 0.02220 over 59,652 legs in 408 ISO-week blocks. Block-bootstrap SE
of the mean is **0.00006**, against a naive `sd/√n` of 0.00009 — a design effect
of **0.68**. Blocking *tightens* it, because the legs within a match are
anti-correlated by construction (§1.4).

| stratum | legs | 1.96 × block SE | vs Max vig 0.00201 |
| --- | --- | --- | --- |
| 100% | 59,652 | 0.00012 | resolves |
| 25% | 14,913 | 0.00024 | resolves |
| 10% | 5,965 | 0.00038 | resolves |
| 5% | 2,982 | 0.00054 | resolves |
| **2%** | **1,193** | **0.00085** | **resolves** |

Even a 2%-of-volume stratum resolves an edge well below the bar it has to clear.
**I expected the opposite** and said so when this was last reviewed: that a
meta-label here would be an underpowered fishing expedition. On CLV it is not.

**The binding constraint is therefore multiplicity, not power** — which is a
different problem with a different control, and §5 is that control.

### 1.6 Every candidate feature is available; the most informative one is a price

Coverage on the 19,884-match basis, at the pre-closing timestamp:

| feature family | coverage |
| --- | --- |
| consensus price `avg_*` | 100% |
| best price `max_*` | 100% |
| **sharp price `ps_*` (Pinnacle pre-close)** | **99.8%** |
| B365 price | 100% |
| model λ and derived probabilities | 100% |
| kickoff slot | **28.3%** — excluded, see §3 |

The sharp-versus-consensus spread (`1/ps − 1/avg`) is **−0.01017, sd 0.00755**:
well populated and clearly structured. It is also **pure price**, so it is
exactly what §4's book ablation removes.

**Leakage boundary.** `close_*`, `fthg`, `ftag`, `ftr` are label-side only. The
closing price is not known when the bet is placed; it appears in the target and
never in a feature.

---

## 2. The scope this forces

1. **1X2 only.** O/U has 5× less gradable data and 3.6× more vig at best price.
   Carrying it would spend configurations on the market least able to pay.
2. **Best-available (Max) prices only**, for both the bet and the bar.
   `CALIBRATION.md` §4 showed average prices need 8× the signal to break even.
3. **Target = CLV, not win/loss.** A departure from SPEC §3.8's literal
   `P(primary correct)`, taken deliberately: CLV has sd 0.0222 per leg against a
   Bernoulli outcome's ~0.45, and §1.0 already names the CLV series as the
   instrument that detects a real edge. Realised ROI is **reported**, never
   selected on — the same relationship 1X2/O/U have to goal deviance.
4. **19,884 matches / 59,652 legs**, 2012-13 → 2022-23. Holdout sealed.

---

## 3. The question this actually asks, and the fork in it

There are two different products hiding under "meta-model", and §1.6 is why
they must be separated before anything is fitted.

- **(A) A gate on the football model.** Does the head's edge concentrate in an
  identifiable stratum, even though H12 found its average weight given the price
  is negative in five of eight cells? Features: model-derived and contextual.
- **(B) A line-movement predictor.** Which pre-close best prices shorten by more
  than the vig? Features: prices. This is a market model. It has nothing to do
  with football, and it would be a different business.

**(B) is what the data most readily supports and it is not what SPEC §3.8 wants.**
§3.8's Probe C finding — book-only AUC 0.5558 > full 0.5516 > no-book 0.5388 —
says the meta-model's entire edge was reading the price, and warns that English
E0 closing lines are a *more* efficient market than the esoccer book that came
from.

**This plan tests (A), and uses (B) as the control that tells them apart.** If
the model-only arm adds nothing over the book-only arm, the honest report is
"market follower with extra steps", and §7 says so before the numbers exist.

Whether (B) is worth pursuing on its own is **an owner decision, not a modelling
one**, and it is outside this plan. It would reopen `CALIBRATION.md` §1.0 on a
new instrument rather than re-litigating the old one, and it should be decided
in the open rather than smuggled in as a good AUC.

---

## 4. Arms

Three arms, one model family, fitted walk-forward by kickoff day with season
boundaries and the COVID window embargoed. Feature sets are disjoint by design:

| arm | features | purpose |
| --- | --- | --- |
| **BOOK** | prices only: Max, consensus, sharp, their spreads, overround | the ablation baseline |
| **MODEL** | model probability, edge over Max break-even, λ total/margin, entropy, division, month, rest, travel | the question in §3(A) |
| **FULL** | both | does the pair beat either |

**The reported column that decides this gate is `MODEL − BOOK`, not `FULL`.**
SPEC §3.8 makes the book ablation mandatory on every meta gate; making it the
*decision* statistic rather than a footnote is the only way it can do its job.

Rest and travel are included because they are now measured, cheap, and known at
decision time. Both are bounded nulls on *goal deviance* (§1.5, §1.6) — that
does not preclude them carrying information about *price error*, which is a
different target, and this is the only place that costs nothing to test.

**Kickoff slot is excluded** at 28.3% coverage. Including it would silently
restrict the whole gate to 2019-20+, which is how the O/U basis and the kickoff
slot both became unanswerable.

---

## 5. Controls, and the multiplicity treatment

§1.5 says power is ample, so the risk is finding something that is not there.

- **Positive control.** Plant a known CLV edge on a known stratum, confirm the
  ranking recovers it. Stop condition as in `P4_TRAVEL_PLAN.md` §5: if the
  planted edge is not recovered, no arm runs on real targets.
- **Negative control.** A NOISE feature block of the same dimensionality, drawn
  independently. `OUTSTANDING.md` §1.7 established that a *positive* result needs
  a planted negative just as a null needs a planted positive; a meta-label with
  many features is precisely where that matters.
- **PBO via CSCV.** `trials.cscv_pbo` consumes a weeks × configurations matrix,
  which is the natural shape here — 408 week blocks against the arm grid. This
  is the first gate whose output feeds the deflation machinery natively. Watch
  `choice_mattered` (spread > 1e-3): PBO ≈ 0.5 on near-identical arms means the
  choice was inconsequential, not overfit (`DEFLATION.md` §6).
- **Budget: ≤ 12 configurations**, declared now. Three arms × one model family ×
  the control set. `OUTSTANDING.md` §0 stands at 149; this plan is a ~8% increase
  and that is the whole allowance. A hyperparameter sweep is not in it.

---

## 6. Decision rule, pre-committed

**Adopt a meta-label only if all four hold:**

1. `MODEL − BOOK` improves mean CLV on selected volume with a block-bootstrap
   interval excluding zero;
2. selected-volume mean CLV **exceeds the Max vig, 0.00201** — the bar
   `CALIBRATION.md` §1 established after "CLV ≥ 0" passed two losing strata;
3. the sign holds in at least three of four divisions;
4. PBO < 0.5 with `choice_mattered` true.

**Report as a market follower** if BOOK carries the result and MODEL adds
nothing — the §3.8 expected finding, and the action is to say so plainly.

**Report as a bounded null** if neither arm clears, with the effect size §1.5
excludes attached.

Nothing here turns the book on. That is `CALIBRATION.md` §5 and §2.3, and a
meta-label result would be an input to reopening it, not a reopening.

---

## 7. Predictions, recorded before running

Scored in `META.md`, per `SHOTS_TARGET.md` and `CALIBRATION.md` §6. `TRAVEL.md`
§5 recorded that its plan predicted the control but not the arms; this one
predicts both.

1. **BOOK beats MODEL on selected-volume CLV**, reproducing §3.8's Probe C
   ordering.
2. **MODEL − BOOK does not clear criterion 1**, i.e. the football model adds
   nothing given the price — H12 found its weight negative in five of eight
   cells and I expect that to survive conditioning.
3. **BOOK alone clears the Max vig** on its top-decile selection. The sharp-vs-
   consensus spread is a genuine predictor of line movement, and §1.5 says the
   corpus can see it.
4. The **positive control recovers a planted edge in ≥5 of 6 draws**, and the
   NOISE block gains less than 0.0002 in mean CLV.
5. **PBO < 0.2** with `choice_mattered` true — three disjoint feature sets are
   not near-identical arms.

If 1–3 all hold, this project has a market model and not a football edge, and
the interesting decision becomes the §3 fork rather than anything about the head.

---

## 8. What this does not test

- **Profit.** CLV above vig is necessary, not sufficient; execution, limits and
  price availability at Max are not modelled, and `RUNBOOK.md` does not capture
  Max at bet time today.
- **The holdout.** Sealed. P6 is not a launch gate (`DEFLATION.md` §8).
- **O/U.** Excluded by §2, recoverable only if pre-2019 closing prices for the
  totals market are ever acquired.
- **Anything about the head.** A meta-label sits above the served pipeline and
  changes no λ. If MODEL wins, the follow-up question is whether the feature
  belongs *in* the head instead — which is a P4 gate, not this one.
