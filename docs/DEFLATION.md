# Deflation decision — written before the holdout is read

Resolves `OUTSTANDING.md` §3.2. Decided **2026-08-04**, with the holdout still
sealed and no P6 read performed.

This document exists so that the treatment of multiple testing is fixed *before*
anyone sees the holdout number. A deflation scheme chosen after the result is
not a deflation scheme, it is a rationalisation, and the whole point of sealing
three seasons is to have one number that cannot be argued with afterwards.

---

## 1. The question §3.2 asked was on the wrong unit

§3.2 framed the choice as: *"51 trials, but they are ~13 distinct questions
asked up to 3 times each. Treating re-runs as independent over-deflates;
treating them as one under-deflates."*

**Both numbers are wrong, and wrong in the same direction — they are too small.**
The ledger stores one row per *run*, and a run of a sweep contains an entire
grid. `h2_half_life` is nine configurations recorded as one row. Counting rows
does not over-deflate; it **understates** multiplicity by a factor of about
two and a half.

Counted mechanically by `engine.eval.trials.count_configurations`:

| unit | count |
| --- | --- |
| ledger rows ("trials") | 52 |
| distinct questions | 24 |
| **configurations actually scored** | **133** |
| rows recording no arm list | 28 |

The 133 is a floor, not a total: 28 rows record no arm list, and every one of
those scored at least one configuration.

**Decision 1.** The unit of multiplicity is the **configuration**, not the
ledger row and not the question. The count is derived from the ledger by
`count_configurations`, so it is a fact to be recomputed rather than a number to
be negotiated at P6.

## 2. What is being deflated — and what is not

The deflation literature this project borrowed from (Bailey, Borwein, López de
Prado & Zhu) is about selecting an investment strategy by Sharpe ratio from a
pool of candidates. **That is not what happens here**, and applying it without
saying so would be a category error:

- **The book is off.** There is no return series to deflate. `CALIBRATION.md` §5.
- The selection metric is **goal Poisson deviance**, a strictly proper scoring
  rule, not a return.
- Selection used a **1-SE rule biased toward more regularisation**, not
  `argmax`. Picking the best of 133 is where overfitting bites; picking the most
  regularised configuration within one paired standard error of the best is
  materially more conservative, and that is what was actually done.

**Decision 2.** What P6 adjudicates is a **forecast-quality** claim: that the
frozen head's dev-set score transfers to unseen seasons. Deflation is applied to
the *selection* of the head, not to a profit claim, because there is no profit
claim to make.

## 3. The procedure — CSCV, which needs no trial count

**Decision 3.** Primary statistic is **PBO via Combinatorially Symmetric
Cross-Validation**, implemented in `engine.eval.trials.cscv_pbo`.

Its decisive property for this project: **it does not take a trial count as an
input.** It consumes a periods × configurations matrix of performance and
estimates directly how often the in-sample winner lands below the out-of-sample
median. Correlated trials — and ours are nearly collinear — are handled by
construction rather than by an effective-N fudge factor.

That is why the "how do we count re-runs?" argument does not need a verdict:
**it dissolves.** Re-runs of an identical configuration on identical data
produce an identical column and are de-duplicated exactly. Nothing has to be
judged.

The matrix:

- **rows** = ISO week, matching `bootstrap.week_blocks`, so the dependence
  structure the paired bootstrap respects is respected here too
- **columns** = every distinct configuration in the selection grids
- **values** = mean goal deviance, **negated** (CSCV wants higher-is-better)
- 16 blocks → C(16,8) = 12,870 splits

**Deflated Sharpe is explicitly not used.** It requires an effective trial
count, which is the exact quantity this project cannot establish honestly.

## 4. Three accounting rules

**Decision 4 — re-runs after a data defect.** The CSCV matrix contains each
distinct configuration **once, scored on the final corpus**. Earlier runs used
data now known to be wrong (the duplicated 2015-16 season; the marginal-SE bug),
and their results were discarded rather than selected on.

The risk this rule accepts, stated plainly: "re-run until the answer improves"
is a real forking path, and this rule would not catch it. The defence is that
both defects were found by mechanisms **independent of the results** — an
`IndexError` on fixture alignment, and a contradiction between H4's paired
bootstrap and the 1-SE rule — not by disliking an outcome. That is documented in
`BASELINE.md` §4. It is a defence, not a proof, and it is recorded as such.

Superseded runs are still counted in `runs` and reported alongside. **A look is
spent whether or not its result survived.**

**Decision 5 — post-hoc trials are quarantined.** `h19_alpha_interaction` was
invented after seeing H17 and is named in `trials.POST_HOC_TRIALS`. It is
excluded from any claim that selection was pre-registered. It returned a null
(no legal prior beats the frozen head at any α) and therefore changed nothing
P6 will read. Any future post-hoc trial must be added to that tuple **when it is
run**, not when it is reported.

**Decision 6 — unattributed rows.** The 28 rows carrying no arm list are
reported as a known undercount, never silently treated as one configuration
each. Any P6 statement of the count carries the phrase "at least".

## 5. The pre-committed criterion

**Decision 7.** P6 passes if **both** hold:

1. **PBO ≤ 0.20** on the pooled selection matrix, *provided*
   `PBOResult.choice_mattered` is true (see §6 for why that proviso is not a
   loophole).
2. The holdout pooled **1X2 deficit-vs-market** confidence interval **overlaps
   the dev-set interval `[+0.01041, +0.01419]`** (`BASELINE.md` §2).

   > **Restated 2026-08-04.** The head was re-frozen to adopt the shots channel
   > (`SHOTS_TARGET.md`), moving the pooled deficit from
   > `+0.01419 [+0.01239, +0.01609]` to `+0.01230 [+0.01041, +0.01419]`. The
   > criterion is stated against the head that will actually be read, so it
   > moved with it. **This is a restatement, not a relaxation** — it was made
   > with the holdout still sealed, before any read, and for a reason unrelated
   > to the outcome. Any future change to the head must restate it the same way
   > and record why; a criterion revised after a read is not a criterion.

Criterion 2 is stated as interval overlap deliberately, so that it needs no
arbitrary tolerance. If the two intervals are disjoint and the holdout is worse,
the dev-set estimate did not transfer, and that is the finding.

Reported alongside, not as pass/fail: holdout goal deviance, per-division
deficits, and the same figures for the last two dev seasons (already measured:
pooled **+0.01505 [+0.01073, +0.01943]**, showing no drift).

**P6 is not a launch gate.** Launch is decided (`CALIBRATION.md` §5) and does
not depend on this number. P6 establishes whether the dev-set measurements can
be trusted as the reference against which the live CLV series is later judged.
Saying so now prevents the result being retrofitted into a launch argument.

## 6. Evidence the instrument works

A deflation statistic that has never been shown a known overfit will report
whatever it is asked for, and it will be believed because it is the last number
computed before a holdout is unsealed. Same discipline as P2's oracle arm.

Three regimes planted in `tests/test_trials.py`:

| planted | required | measured |
| --- | --- | --- |
| one genuinely superior configuration | PBO ≈ 0 | < 0.05 |
| pure noise, nothing to choose | PBO ≈ 0.5 | 0.35–0.65 |
| each trial spikes in one block only | PBO high | > 0.8 |

**And measured on a real grid.** P1's α sweep, 490 weeks × 8 configurations,
recorded as `probe:deflation_instrument_validation`:

```
PBO 0.022 over 12,870 splits of 8 trials
degradation +0.000431    spread 0.008820    -> informative
```

**PBO 0.022 — the ridge-penalty selection is not overfit.** The deviance surface
is monotone past α = 0.05 rather than eight interchangeable candidates, so the
in-sample winner is consistently also the out-of-sample winner, and the winner
sits *above* the out-of-sample median by 0.0004 nats.

### The trap, and why the §5 proviso is not a loophole

PBO near 0.5 means the in-sample winner is a coin flip out of sample. When
configurations genuinely differ, that is damning. When they are nearly
identical, it is **inevitable and harmless** — there is nothing to choose
between them, so the choice cannot be lucky or unlucky.

Several of our grids are in exactly that regime: the H14 squad-prior sweep spans
0.00002 nats end to end. Reading PBO ≈ 0.5 there as "overfit" would be wrong.

So `cscv_pbo` returns `spread` and `choice_mattered` and refuses to be read
without them. The threshold is 0.001 nats, the paired standard-error scale on
this corpus. **When `choice_mattered` is false, PBO is reported as
uninterpretable and criterion 1 is satisfied by the spread being negligible** —
because a selection among indistinguishable options cannot have overfitted to
anything. That is a substantive claim, written down now rather than discovered
convenient later.

## 7. What this does not claim

- It does not establish that the head beats the market. It does not
  (`BASELINE.md` §2), and P6 will not change that.
- It does not deflate a profit or Sharpe claim; there is none.
- It does not correct for the **live** series. Once serving begins, the live
  CLV series is independent evidence and needs its own treatment.
- It does not remove the forking-path risk described in §4, only bounds and
  documents it.

## 8. When to run it

**Not yet.** No pending decision turns on the number, launch does not depend on
it, and the holdout can be spent only once. Its value grows as the live series
accumulates independent evidence to compare against.

Run it when there is a decision that the answer would change — and re-read §5
before looking, not after.
