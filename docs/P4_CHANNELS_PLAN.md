# P4-channels pre-registration — shots and corners in the strength layer (B12)

Written **2026-08-10**, before any arm is run and before the gate code exists.
Predictions are numeric so they can be wrong. Results will go in
`CHANNELS_GATE.md`; this file stays unedited.

Follows the pre-gate recorded as `probe:p4_channels_pregate` (row 76,
`CHANNELS.md`), which said run the gate. It is the gate `OUTSTANDING.md` §1.7
licensed and `BACKLOG.md` B12 tracks.

---

## 1. What the pre-gate established, and what it did not

Leave-one-season-out split-half reliability over 1,103 team-seasons, all figures
from the **same rebuilt harness** so the within-run contrasts are the ones that
carry weight (`CHANNELS.md` §7):

| predictor set | → goals for | → goals against |
| --- | --- | --- |
| goals | 0.5282 | 0.4391 |
| **goals+sot** (shipped) | 0.5426 | 0.4621 |
| goals+sot+shots | 0.5719 | 0.5045 |
| goals+sot+corners | 0.5768 | 0.4961 |
| **goals+sot+shots+corners** | **0.5916** | **0.5161** |
| goals+sot+NOISE (control) | 0.5418 | 0.4621 |

**The scale that matters is inside this table, not across documents.** The
channel that *shipped* — sot added to goals — gains **+0.0144 attack / +0.0230
defence** on this instrument, and cashed out at **−0.00422 nats**. Shots and
corners together gain **+0.0490 / +0.0540**, which is **3.4× / 2.3×** the
shipped channel's gain measured the same way.

**What the pre-gate did not establish** is that reliability maps to deviance at
any fixed rate. `SHOTS_TARGET.md` §7 records over-estimating that mapping once,
and §6 of `CHANNELS.md` says explicitly that nothing there predicts the gate
passes. The predictions below take the ratio seriously and discount it for
concavity; if they are wrong, that is the finding.

## 2. The construction

The shipped head already fits a second Poisson on the identical design matrix
with sot as the count, and folds its coefficients into the goal-fitted
strengths at `w = 0.3` (`P4_SHOTS_PLAN.md` §2). This gate generalises the fold
from one auxiliary channel to **k**:

```
att* = (1−w)·att_g + w·C_att
C    = mean over channels c of ( att_c · sd(att_g)/sd(att_c) ),
       renormalised to sd(att_g) when k > 1
```

Three properties, each deliberate:

- **Exact nesting at k = 1.** With one channel the expression is the shipped
  arithmetic term for term, so the served head is bit-for-bit unchanged and any
  measured difference is the extra channels rather than a reimplementation.
  Asserted in tests, as for the P2 squad prior and the shots channel.
- **The renormalisation is what makes the negative control matched.**
  Averaging k imperfectly-correlated standardised vectors shrinks the composite
  — and shrinkage alone can improve deviance. Without renormalising, the real
  arm (channels correlated ~0.96) and the noise arm (uncorrelated) would carry
  *different* aux dispersion, and the control would differ from the arm in two
  ways instead of one. `OUTSTANDING.md` §9.6 records a control that failed
  exactly this test and says a matched control must "differ only in carrying no
  information".
- **Equal weights inside the composite.** Per-channel weights are a 3-D grid
  and `CHANNELS.md` §4 forbids that class of sweep at this budget. §7 below
  records it as held fixed.

**The evidence gate is inherited unchanged.** Shots, sot and corners have
**identical availability** in this corpus — 100% of E0–E3 in all thirteen dev
seasons, 0% of EC from 2016-17 — so `MIN_SOT_EVIDENCE` gates all three at once
and no new data hole is opened. Verified before writing this file.

**The gate's config is carried on a subclass of `WalkForwardConfig`.**
`artifact.freeze` hashes `cfg.__dict__`, so adding even a *defaulted* field to
the served config would change the artifact version string with no model change
— retiring `p1-3a38e9d6ef1ca7ee`, which commit `0c9eb06` explicitly declined to
do. Promoting the field is part of adoption, not of measurement.

## 3. Arms and predictions

Selection metric is **goal Poisson deviance**, on the frozen head
`H400 / a0.1 / weekly / E0+E1+E2+E3+EC / sot0.3`, artifact
`p1-3a38e9d6ef1ca7ee`. Sign convention: **negative = better**. Scored E0–E3,
COVID embargoed, paired block bootstrap by ISO week, 1-SE rule with the
tie-break toward the smaller weight.

**The reference is the shipped head, not a goals-only fit.** B12's null
hypothesis is "one aux channel is enough", not "no aux channel".

### H37 — positive control, and it runs first

Shots and corners replaced by low-noise functions of each club's **season-long**
rates, the two-sided construction `p4_shots.py:_oracle_frame` uses; sot left
real. Blended through the identical code path at `w = 0.3`.

*Predict:* oracle ≤ **−0.008** deviance against the shipped head, CI excluding
zero.
*Why:* H25's sot oracle reached −0.01636 against a **goals-only** baseline. Here
the baseline already carries a real sot channel, so the headroom is smaller.
*Basis for the stop rule:* P2's null was interpretable only because H17 proved
the harness could see a real prior.

### H38 — the composite weight, swept

`w ∈ {0, 0.15, 0.30, 0.45, 0.60}` with channels `(sot, shots, corners)`.

*Predict:* the rule selects **w\* ≥ 0.30** and the optimum is **interior**
(`censored` is None).
*Why:* the shipped 1-channel optimum is 0.30 with a fitted diagonal vertex of
0.3413 (`CHANNELS.md` §4). A composite of three channels is a better-measured
read of the same quantity, so it should tolerate *more* weight, not less.

### H39 — which channel carries it, and the matched negative control

At the selected `w*`, against the shipped head:

| arm | channels |
| --- | --- |
| `shipped` (reference) | `(sot)` @ 0.30 |
| `sot @ w*` | `(sot)` @ w\* |
| `+shots` | `(sot, shots)` @ w\* |
| `+corners` | `(sot, corners)` @ w\* |
| `+both` | `(sot, shots, corners)` @ w\* |
| `+noise ×2` | `(sot, noise1, noise2)` @ w\* |

`sot @ w*` is present so that a difference between `shipped` and `+both` can be
attributed to the channels rather than to the weight moving.

*Predict:* `+both` improves by **−0.003 to −0.008**; both singles are negative;
`+both` beats either single and is **sub-additive** (better than either, worse
than their sum). `+noise ×2` is **not negative** — delta ≥ 0 against shipped.
*Why the band:* linear extrapolation of the within-harness reliability ratio
(§1) gives −0.012; the reliability→deviance map is concave and
`SHOTS_TARGET.md` §7 records over-reading it once, so the band is discounted
roughly two-fold and made wide enough to be falsifiable at both ends. Landing
above −0.002 says concavity dominates; landing below −0.010 says the mapping is
more linear than that section assumed.

### H40 — per division, the reported markets, and the gap

At the selected arm. Spends no configurations: it re-scores arms already run
and records no arm list, the accounting `h22_h24_shots_divisions` used.

*Predict:* the effect is present and **negative in all four divisions** with
every interval excluding zero, and the largest division effect is **< 3×** the
smallest. 1X2 improves **0.001–0.003** and O/U 2.5 improves **0.001–0.003**,
reported and never selected on. The pooled 1X2 deficit moves from **+0.01230**
to between **+0.008 and +0.011** and **does not reach zero**.

## 4. Stop conditions, committed in advance

- **If H37 fails**, nothing else is reported as a finding. The instrument is
  broken and that is the whole result.
- **If `+noise ×2` improves on the shipped head with a CI excluding zero**, the
  composite arithmetic is manufacturing gain and every other number here is
  void. This is the control that can falsify the result I expect to get, per
  `OUTSTANDING.md` §9.5's restatement of convention 8.
- **If the 1-SE rule selects `w = 0`**, the entire auxiliary channel layer is
  refuted on the current corpus — which contradicts §1.3 — and that
  contradiction is investigated before anything else is reported.
- **If the sweep optimum sits on a grid boundary**, the grid was too narrow.
  Widen and re-run, per `SweepResult.censored`; the re-run spends again.
- **If deviance improves but 1X2 degrades**, that disagreement is the finding
  and is written down before any ship decision, as OPEN-3's was.

## 5. Budget

**13 configurations**, declared before running: H37 2, H38 5, H39 6, H40 0.
The ledger stands at 94 runs / 51 questions / **176 configurations**, so this
takes it to **189**.

`BACKLOG.md` B12 recorded the cost as 2. That figure is a mis-transcription of
`OUTSTANDING.md` §1.7's fourth bullet, which prices identifying the **per-side**
(att/dfn) weight for the *already-shipped* sot channel — a different question,
not this gate, and not run here. Corrected in `BACKLOG.md` when this plan was
written, with the reason kept.

The gate module carries `--dry-run` from the first commit, so development costs
no rows. `META.md` §9's four byte-identical implementation rows are the reason.

## 6. What this cannot become

It cannot turn the book on. `CALIBRATION.md` §5 stands: the pooled deficit is
+0.01230 against a vig of 0.02122 at average prices, and per `OUTSTANDING.md`
§2.3 nats and de-vigged probability do not net. A second shots-sized channel
closes roughly an eighth of that gap.

**Nothing here adopts anything.** A positive result licenses a head change, and
a head change owes the five things `OUTSTANDING.md` §1.3 lists — new artifact
id, `BASELINE.md` §1–2 re-issued, `DEFLATION.md` §5 criterion 2 restated, the
share-of-market-edge table updated, and `engine/eval/tips.py`'s claims block
re-run because the published strike rate is a property of the head. That is a
separate piece of work and a separate decision.

## 7. Held fixed, and whether it interacts (convention 9)

P1 swept α with the ridge target pinned at zero and thereby fixed how much any
later prior could be worth (`PLAYER_PRIOR.md` §2). The same disclosure, made in
advance:

- **α = 0.1 and H = 400** are the frozen head's, selected when the fit carried
  goals alone. Each auxiliary channel is a separately-ridged Poisson at the same
  α, so a composite of three takes three doses of the same shrinkage. **These
  interact**, and the direction is knowable: if α is too strong for the
  composite, H38's optimum understates the channel's worth. Not swept — that is
  a joint grid, and it is not in this budget.
- **The composite's internal weights are equal.** Shots and corners contribute
  similarly in the pre-gate (+0.0293/+0.0424 and +0.0342/+0.0340), which is what
  makes equal weighting defensible rather than merely cheap. A per-channel
  weight is not identified by anything run here.
- **`shots_blend_sides = "both"`.** No per-side weight. `CHANNELS.md` §4 puts
  that at 2 further configurations and it is deliberately not in this budget.
- **The reference weight for the shipped head is 0.30**, chosen by H20 when sot
  was the only channel. H39's `sot @ w*` arm exists precisely so this
  assumption is visible in the results rather than buried in the comparison.

---

## 8. Amendment — H37 failed its bar and the gate ran anyway

**Appended 2026-08-10, after H37 and before H38. §1–7 above are unedited**: no
prediction, bar or arm definition has been changed, and H39's −0.003 to −0.008
band stands exactly as written even though §8 explains why it is wrong.
Recorded here rather than only in the results, on the `P4_TRAVEL_PLAN.md` §8
precedent, because a plan that does not say its stop rule fired is worse than
no plan.

**What happened.** H37 returned **−0.00396 [−0.00477, −0.00320]** against a §3
bar of **≤ −0.008**. The stop rule in §4 fired. The gate was continued by owner
decision, and H38/H39/H40 are registered in `trials.POST_HOC_TRIALS`.

**Why the bar was wrong, stated so it can be judged.** It was anchored on H25's
sot oracle at −0.01636 and adjusted only by intuition. Two differences were
missed, both pushing the same way:

| | H25 (shots gate) | H37 (this gate) |
| --- | --- | --- |
| oracle blend weight | **w = 0.6** | **w = 0.3** — the shipped weight |
| baseline it is measured against | goals only | goals **+ real sot at 0.3** |

So H37 measures a *tighter* quantity than H25 did, and the bar was copied from
the looser one.

**Why continuing is not the thing `CALIBRATION.md` §1 forbids — and why it is
still recorded as post-hoc.** §4's stop condition gives its own reason: *"The
instrument is broken and that is the whole result."* At −0.00396 with the
interval excluding zero by roughly ten paired standard errors, the instrument is
not broken; the rule fired for a condition it was not written to detect. But
unlike `P4_TRAVEL_PLAN.md` §8, where the statistic changed after seeing only
Poisson-resampled synthetic outcomes, **H37 is scored against real match
outcomes**. Real information was in view when the decision was taken.
`OUTSTANDING.md` §1.6 draws that line explicitly, so the conservative treatment
applies and no claim of pre-registration is made for H38–H40.

**The control also refutes §3's H39 prediction before H39 runs, and that is the
substantive finding here.** H39 predicted the real arm at −0.003 to −0.008. The
oracle bounds the mechanism at −0.004, so most of that band lies above what a
*perfectly measured* version of the feature can deliver. The prediction was
internally inconsistent, and only running the control first exposed it.

**What the ceiling means for reading H38/H39.** Two perfectly-measured extra
channels are worth **−0.00396** on top of the shipped head — about 94% of what
the real sot channel was worth on top of goals (−0.00422). That is a coherent
ceiling, not a degenerate one, and any real arm should be read as a fraction of
it. **`CHANNELS.md`'s +0.0490/+0.0540 reliability gain therefore cannot map to a
deviance gain of the size §1 extrapolated**, and the third recorded instance of
over-reading that mapping (`SHOTS_TARGET.md` §7 and `CHANNELS.md` §6 are the
first two) is this file's §1.

**Not done, and deliberately:** H37 was *not* re-run at w = 0.6 to match H25.
That would have bought comparability with H25 at 2 further configurations
without changing the ceiling that matters, which is the one at the weight the
head actually serves.
