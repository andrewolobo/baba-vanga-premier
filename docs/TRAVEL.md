# Travel distance — a bounded null, and the bound is real this time

Run 2026-08-06 against the pre-registration in `P4_TRAVEL_PLAN.md`. Ledger rows
`h34_travel_power` (×2) and `h36_travel_arms`. The third of SPEC §3.6's
replacement analogues, after the kickoff slot (unresolvable) and rest (bounded
null).

**Headline: travel distance does not improve the head, and unlike the kickoff
slot this corpus was able to ask the question.** The positive control passed
before any arm touched a real outcome, so the null carries a size rather than
being the absence of a finding.

---

## 1. The result

| statistic | value |
| --- | --- |
| score coefficient β | **−0.0147** (se 0.0149, **t = 0.98**) — not resolved |
| point estimate | 1.47% less away scoring per 500 km; **0.51% at the median trip** |
| resolution threshold | **3.7% per 500 km** (control, H34) |
| A1 — one slope, goal deviance | **+0.00008** [−0.00010, +0.00026] |
| A2 — five bands, goal deviance | +0.00007 [−0.00010, +0.00025] |
| A1 — O/U 2.5 log-loss | **+0.00018** [+0.00008, +0.00029] |

Sign convention: positive = worse than the frozen head.

**Decision, by the §7 rule: do not adopt.** A1's interval does not exclude zero,
and the sign holds negative in **1 of 4** divisions against a bar of 3.

| division | n | A1 delta |
| --- | --- | --- |
| E0 | 4,088 | −0.00029 [−0.00072, +0.00016] |
| E1 | 5,952 | +0.00005 [−0.00028, +0.00037] |
| E2 | 5,908 | +0.00025 [−0.00009, +0.00062] |
| E3 | 5,948 | +0.00020 [−0.00019, +0.00058] |

E0 is the only division where the arm helps at all, which is the opposite of the
prior in SPEC §3.8 — the Premier League has the least real geography and the
sharpest market. On 4,088 matches with an interval spanning zero it is noise, and
it is recorded rather than read.

## 2. What the null bounds

The control detects a planted 5%-per-500km deficit **5 times in 6** at t = 2.68,
with **no false positive in 6 draws** at zero, and the estimator returns −0.05186
± 0.00179 against a planted −0.0500 over 60 draws. The instrument works.

So: **any true per-match effect of travel distance on away scoring is smaller
than roughly 3.7% per 500 km** — about 1.3% at the median trip. That is the
claim, and it is the kind `REST.md` §1 makes rather than the kind `TOD_SLOT.md`
§8 was forced into.

**The point estimate is in the predicted direction and too small to see.** 1.47%
per 500 km is 40% of the resolution threshold. Resolving an effect *of that size*
needs **4.0× this corpus — about 86,800 matches, roughly 43 seasons of four
divisions.** Unsealing all three holdout seasons adds 7,764 and moves t from 0.98
to **1.15**, so the most expensive act available does not buy the answer. That is
the same arithmetic `TOD_SLOT.md` §8 ran, reaching the same place by a different
route, and it is worth knowing before anyone proposes the unseal.

## 3. Three things worth carrying forward

- **The pre-registered detection statistic was wrong, and the control is what
  caught it.** The deviance delta recovered a planted 5% effect **0 times in 6**;
  a Poisson score test on the identical frames recovered it 5 of 6. Thresholds
  13.5% against 3.7%. Had the control not run first, this gate would have
  reported "underpowered" on an instrument that was simply the wrong one, and
  the stadium table would have been blamed. `P4_TRAVEL_PLAN.md` §8 records the
  amendment and why amending after a *control* is not what `CALIBRATION.md` §1
  forbids: no real outcome was in view.

- **The two statistics disagree in a way that is itself the finding.** The score
  test says the corpus cannot see an effect; deviance says an arm fitted to it
  costs +0.00008. Both point away from adoption, so nothing turns on the
  disagreement here — but the pair is what separates `REST` (bounded null) from
  `TOD_SLOT` (real, unadoptable), and reporting only one of them is how a gate
  loses that distinction. Adoption stays on deviance per convention 2.

- **A1 makes the served O/U market measurably worse** — +0.00018 with an interval
  excluding zero — while goal deviance is flat. Convention 2 says a disagreement
  between the selection metric and the served markets is written down. It does
  not change the decision, both being against adoption, but a feature that is
  free on deviance and costly on O/U is not free.

## 4. What this does not test

**The corpus is league-only.** No FA Cup, League Cup or European ties, so the
trips to those fixtures are absent entirely. This gate measures the per-match
effect of the distance travelled *to the fixture being played*. A **cumulative
mileage or fatigue** effect is neither tested nor refuted here, and it is the
form in which travel is most often claimed to matter. Congestion inherits the
same hole and inherits it worse.

**Two stated approximations, neither tuned** (`P4_TRAVEL_PLAN.md` §2): distance
is great-circle rather than road, which understates journeys worst exactly where
the road network is worst — Plymouth, Norwich, Carlisle; and the stadium table
is static, so eight in-corpus ground moves are applied to the whole period. Only
Rotherham changes town. Both biases point toward measuring *less* than is really
there, so neither manufactures the null. **`reconcile.KNOWN_MOVES` remains the
one unverified input in the chain** — recalled, not sourced.

## 5. Prediction scorecard

The §6 predictions were all about the control, and were scored there: **one of
five right**. Prediction 2 is the informative one — "2–6% at 500 km" was right
about the corpus and wrong about the instrument, which is exactly the error §8
corrects.

**The plan made no prediction about the arms themselves, and it should have.**
That is a gap in the pre-registration, not a result: with no recorded
expectation there is nothing to be wrong about, and the discipline that made
`SHOTS_TARGET` readable (six of seven called in advance) was unavailable here.
Any future §3.6 gate should predict the arm outcome as well as the control's.

## 6. Where §3.6 goes now

Travel is measured and closed. Of the SPEC's four replacement analogues:

| analogue | state |
| --- | --- |
| kickoff slot | real, unresolvable — `TOD_SLOT.md` |
| rest | bounded null at ~3.5% (score test: 3.99%) — `REST.md` |
| **travel** | **bounded null at ~3.7% per 500 km — this document** |
| congestion | blocked: it is a count of the midweek ties the corpus lacks |
| stakes | blocked on OPEN-4, as-of table reconstruction |

**Do not** re-litigate travel with road distances, per-division slopes, a
travel × midweek interaction, or cumulative mileage over a trailing window. The
first three spend degrees of freedom on a corpus that resolves 3.7% and saw
1.47%; the fourth is the one live question, and it needs cup and European
fixtures that `data/` does not contain. Acquiring those is the decision that
would reopen this, not another arm.
