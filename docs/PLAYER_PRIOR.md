# P2 results — the player prior is descoped

Run 2026-08-03 against the pre-registration in `P2_PLAN.md`. Reproduce with
`python -m engine.eval.p2 --stage all`. Every arm is in `gate_ledger`, which
stands at **51 trials**.

**Headline: the player layer does not work on this corpus, and it is now
diagnosed rather than guessed.** Four pre-registered arms are null at the metric
that selects. The positive control proves the instrument could have seen a prior
had there been one — and in proving it, moved the finding somewhere more useful
than "players don't help".

---

## 1. The four pre-registered arms, all null

Scored on 2014-15 → 2022-23 (the seasons a prior exists for; the coefficient map
needs three finished seasons behind it) — 15,824 matches, E0–E3.
**Negative = the prior helps.**

### H14 — the SPEC §3.3 prior-anchored ridge, weight swept

| weight | deviance | paired SE | 1X2 |
| --- | --- | --- | --- |
| **0.00** | 2.87390 | 0.00002 | 1.03699 | ← chosen by the 1-SE rule |
| 0.25 | 2.87389 | 0.00000 | 1.03698 | ← best |
| 0.50 | 2.87390 | 0.00002 | 1.03698 |
| 0.75 | 2.87390 | 0.00003 | 1.03697 |
| 1.00 | 2.87391 | 0.00005 | 1.03697 |

**The whole sweep spans 0.00002 nats.** The rule selects weight 0 — the model
without the feature. Predicted `w ≤ 0.25` and `|Δ| < 0.0005`: right, by a factor
of twenty.

### H15 — which channel carries anything. None of them.

| arm | deviance | vs baseline |
| --- | --- | --- |
| baseline | 2.87390 | — |
| **control** (no player data at all) | 2.87391 | +0.00001 [−0.00011, +0.00013] |
| level (`sq_att`, `sq_dfn`) | 2.87391 | +0.00001 [−0.00012, +0.00013] |
| orthogonal (`sq_age`, `sq_churn`) | 2.87391 | +0.00001 [−0.00012, +0.00013] |
| all six channels | 2.87391 | +0.00001 [−0.00012, +0.00013] |

**This is the arm that closes the question.** The control prior contains no
player data whatsoever, and every player arm matches it to five decimal places.
44,720 player-seasons, six channels, and the answer is identical to not opening
the files.

### H16 — the population the feature was designed for

First 45 days of a season, either club having changed division. n=1,196.

    level vs baseline   +0.00045 [−0.00036, +0.00123]   no difference

Predicted `|Δ| < 0.002` with the CI spanning zero: right.

### H18 — per division

| division | n | Δ deviance |
| --- | --- | --- |
| E0 | 2,948 | +0.00008 [−0.00017, +0.00031] |
| E1 | 4,308 | +0.00012 [−0.00010, +0.00033] |
| **E2** | 4,264 | **−0.00029** [−0.00056, −0.00003] |
| E3 | 4,304 | +0.00013 [−0.00006, +0.00031] |

Predicted `|Δ| < 0.001` everywhere: right. Predicted E3 as the likeliest to
move: wrong, it was E2. E2's interval excludes zero, and it is one division of
four tested at 95% with an effect of 0.0003 nats against a 0.0142 deficit to the
market. Recorded, not shipped.

---

## 2. H17 — the positive control, and the finding that actually matters

The oracle prior hands the fit the club's **realised season-N strength**, fitted
after the season was played. It is unknowable at the decision moment, never
served, and marks the ceiling: no legal prior can beat it.

| ridge α | no prior | oracle prior | oracle's gain |
| --- | --- | --- | --- |
| **0.1** (P1's chosen value) | 2.87390 | −0.00018 [−0.00031, −0.00005] | 0.00018 |
| 1.0 | +0.00199 | −0.00161 [−0.00176, −0.00146] | 0.00360 |
| 5.0 | +0.00938 | −0.00694 [−0.00742, −0.00647] | 0.01632 |

**Predicted the oracle would be worth ≤ −0.010 at α=0.1. It is worth −0.00018 —
fifty times smaller.** Wrong, and wrong in the informative direction.

At α=5 a perfect prior is worth **0.0069 nats, half the head's entire deficit to
the market**. So the ridge target is a real channel. What closes it is the
penalty: at α=0.1 the likelihood swamps the prior and even a perfect one barely
moves the fit.

**α and the ridge target were tuned as if independent, and they are not.** P1's
H3 swept α with the target pinned at zero — where hard shrinkage is obviously
wrong, because "league average" is a bad thing to be pulled toward, and the
surface was monotone increasing past 0.05. With a good target, hard shrinkage
becomes right. The sweep answered the question it was asked; the question
assumed no prior existed.

---

## 3. H19 — post-hoc: can a legal prior use that channel?

**Not pre-registered.** Asked because H17 made it well-posed. Labelled rather
than folded in, because a hypothesis invented after seeing the data is not the
same object as one committed to before.

| α | no prior | control (no players) | level (players) | oracle |
| --- | --- | --- | --- | --- |
| 0.1 | **2.87390** (ref) | — | — | −0.00018 |
| 1.0 | +0.00199 | +0.00022 | +0.00021 | −0.00161 |
| 2.0 | +0.00460 | +0.00050 | +0.00047 | — |
| 5.0 | +0.00938 | +0.00106 | +0.00103 | −0.00694 |

Three readings, in order of how much they matter.

**The legal prior never beats the frozen head.** Every legal arm is positive —
worse — against `base a0.1`, and every interval excludes zero. The best is
+0.00021 at α=1. There is no cell of this grid worth shipping.

**The players contribute 0.00003 nats.** `level` minus `control` is 0.00001 at
α=1, 0.00003 at α=2, 0.00003 at α=5. That is the entire measured value of the
player corpus, at the ridge strength most favourable to it.

**The prior mechanism works; the prior is the problem.** At α=5, shrinking
toward zero costs +0.00938 and shrinking toward the control prior costs
+0.00106 — the reshaping recovers 89% of the damage. So priors transmit exactly
as designed. But the gap between the legal prior (+0.00103) and the oracle
(−0.00694) is 0.00797, and the legal prior captures **none** of it. Everything
the oracle is worth lies in knowing the season-N result, and no construction
from season N−1 approximates that.

Confirmed directly: the fitted prior's correlation with the club's realised
end-of-season strength is 0.934 / 0.952 / 0.966 / 0.970 across sampled seasons,
against 0.936 / 0.945 / 0.970 / 0.968 for the club's own pre-season `att`. **The
squad-augmented prior predicts where a club ends up no better than the club's own
decayed match history already does.**

One genuine positive: **α = 0.1 survives a test it had not previously faced.**
P1 chose it against a target of zero; it now also beats every prior-anchored
alternative offered. That is a stronger result than the one BASELINE.md records.

---

## 4. Why it failed — three independent causes, none of them fixable by effort

1. **There is no cold start.** The minimum decayed training weight behind any
   scored club at its own fit cutoff is **25.8 effective matches**; the 1st
   percentile is 33.3, the median 65.2. SPEC §3.3 imported gtleague's finding
   that 82.5% of post-rotation rows were clubs decayed to ~1% weight. That
   population does not exist here — **because P1's NEW-1 decision already fixed
   it.** Fitting all five divisions jointly means promotion is not entity
   rotation; the club never leaves the pool.
2. **The legal aggregate is the club restated.** The N−1 roster plays 52–75% of
   the club's own N−1 minutes, so a squad aggregate built from it correlates
   0.980 with the club's fitted `att` within division. There is nothing left in
   the residual — with `att_pre` and `dfn_pre` both in the baseline, no channel
   adds more than +0.016 R² anywhere, on 260 division-changing club-seasons.
3. **The as-of rule removes the only genuinely new information.** What would
   help is knowing season N's actual squad — who was bought, who left. Reading
   it requires season N's player file, which encodes both the transfer and the
   survivorship (`asof.PLAYER_SEASON_RULE`). The honest construction is the N−1
   roster, and the N−1 roster is the club.

**The 0.058 nats that motivated P2 was never the player layer's to collect.**
`BASELINE.md` §3 measured that clubs promoted out of the National League are
predicted 0.058 nats better when the fit has seen their EC matches. It has been
carried since as evidence that player-level information was worth twenty times
the blend's contribution. It is the value of *lower-division match history*, and
P1 banked it in July.

---

## 5. Decision

**P2 is descoped. The player layer does not ship.**

The code stays: `engine/models/squad.py`, the `prior_att`/`prior_dfn` arguments
on `poisson.fit`, and the `squad_prior` arm. Deleting them would leave this
document unreproducible, and the ridge-target argument is a genuine
generalisation of the model whose default is exactly the old behaviour — asserted
bit-for-bit in `test_a_zero_prior_is_bit_for_bit_the_old_fit`.

**Nothing in serving changes.** `squad_prior` stays `None`. The frozen head is
still `H400 / a0.1 / weekly / E0+E1+E2+E3+EC`.

**Do not re-litigate with:** a per-player ratings model, an age curve, market
values, or a longer channel list. The binding constraint is not the quality of
the aggregate — it is that the club's own match history already contains what
the aggregate can legally see (§4.2), and that the ridge at α=0.1 transmits
0.0002 nats even from a perfect prior (§2). A better aggregate improves neither.

**What would change the answer**, in the only order the evidence supports:

1. **Dated transfer data.** `data/transfer-history/` is empty. With arrival and
   departure dates the season-N squad becomes legally knowable, and §4.3 — the
   binding constraint — dissolves. This is the one thing that would make the
   player layer buildable, and it is a data acquisition problem, not a modelling
   one.
2. **Per-match appearances.** OPEN-1's case (a), still unavailable. Would make
   injury and rotation state readable and remove the season-boundary refresh.
3. Nothing else. Not more channels, not more weights, not more α.

---

## 6. Prediction scorecard

| # | prediction | outcome |
| --- | --- | --- |
| H14 | chosen w ≤ 0.25, \|Δ\| < 0.0005 at every weight | **right** — chosen w=0, whole sweep spans 0.00002 |
| H15 | all \|Δ\| < 0.0005 | **right** — every arm +0.00001, and identical to the no-player control |
| H16 | \|Δ\| < 0.002, CI spans zero, n ≈ 1,500 | **right** — +0.00045 [−0.00036, +0.00123], n=1,196 |
| H17 | oracle ≤ −0.010 at α=0.1, CI excluding zero | **wrong on size** — −0.00018, fifty times smaller. Right on sign |
| H18 | \|Δ\| < 0.001 everywhere; E3 likeliest to move | **right on size, wrong on location** — E2 moved, −0.00029 |

Five predictions, three fully right, one right-on-size-wrong-on-location, one
badly wrong on magnitude.

The magnitude miss is the useful one, and it is the *opposite* of P1's and P3's
pattern. There I kept expecting the corpus to yield more than it did. Here I
expected a perfect oracle to be worth 0.010 and it was worth 0.0002 — I
over-estimated how much the **ridge** transmits, not how much the **data**
contains. Two different errors that look the same from the outside: both are
"predicted effect too large", but one is about the world and the other about my
own instrument. Worth separating before P4.

The §4 arithmetic in `P2_PLAN.md` predicted ~0.0003 nats from ΔR² ≈ 0.01. The
measured value was 0.00003 — an order of magnitude smaller, for the same reason.
The envelope calculation modelled the information and ignored the penalty that
gates it.
