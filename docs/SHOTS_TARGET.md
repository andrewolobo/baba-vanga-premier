# P4-shots results — the first feature that works

Run 2026-08-04 against the pre-registration in `P4_SHOTS_PLAN.md`. Reproduce
with `python -m engine.eval.p4_shots --stage all`. Every arm is in
`gate_ledger`, which stands at **58 runs**.

**Headline: a shots-on-target channel improves the head by −0.00422 nats of
goal deviance, and the effect holds in all four served divisions with every
interval excluding zero.** After P0's nulls, P2's descope and P3's book-off,
this is the first thing measured on this corpus that does what it was supposed
to do.

It does **not** make the head beat the market, and §5 says so with numbers.

---

## 1. H20 — the blend sweep

| weight | deviance | paired SE | 1X2 |
| --- | --- | --- | --- |
| 0.00 | 2.88241 | 0.00058 | 1.04032 |
| 0.15 | 2.87947 | 0.00028 | 1.03912 |
| **0.30** | **2.87819** | — | **1.03853** | ← best, and the 1-SE choice |
| 0.45 | 2.87856 | 0.00029 | 1.03855 |
| 0.60 | 2.88060 | 0.00058 | 1.03919 |
| 0.80 | 2.88594 | 0.00101 | 1.04101 |

**−0.00422 nats at w = 0.30**, an interior optimum on an uncensored grid, and
7.3 paired standard errors from the baseline. Predicted `w ∈ [0.15, 0.45]` and
an improvement of 0.003–0.007: **both right**.

The shape matters as much as the optimum. Deviance falls to 0.3 and rises
again, so the channel is genuinely complementary rather than simply better —
at w = 0.8 the blend is *worse* than not using shots at all. This is the
"augment, not replace" prediction from the pre-gate, visible in the curve.

## 2. H21 — which side carries it

| arm | deviance | vs baseline |
| --- | --- | --- |
| baseline | 2.88241 | — |
| **both** | 2.87819 | **−0.00422** [−0.00535, −0.00307] |
| attack only | 2.88123 | −0.00118 [−0.00194, −0.00037] |
| defence only | 2.88022 | −0.00219 [−0.00319, −0.00120] |

**Half right.** Defence does carry more than attack (52% of the full effect
against 28%), as the pre-gate's split-half predicted directionally. But I
predicted defence would deliver **≥ 60%** and it delivered 52%. Wrong.

The more interesting number is one I did not predict: **attack and defence are
super-additive.** Separately they are worth 0.00118 + 0.00219 = 0.00337; together
they are worth 0.00422. Blending one side while leaving the other on goals
leaves the two coefficient sets on inconsistent footings — `att` and `dfn` are
jointly identified from the same likelihood, so improving one alone is worth
less than improving both.

## 3. H22 / H23 / H24 — divisions, markets, and the gap

| division | n | Δ deviance | deficit vs market |
| --- | --- | --- | --- |
| **pooled** | 21,896 | **−0.00422** [−0.00535, −0.00307] | **+0.01410 → +0.01230** |
| E0 | 4,088 | −0.00628 [−0.00952, −0.00314] | +0.01170 → **+0.00976** |
| E1 | 5,952 | −0.00347 [−0.00534, −0.00166] | +0.01396 → +0.01272 |
| E2 | 5,908 | −0.00273 [−0.00477, −0.00064] | +0.01549 → +0.01409 |
| E3 | 5,948 | −0.00504 [−0.00694, −0.00310] | +0.01452 → +0.01185 |

**Present and negative in all four, every interval excluding zero**, largest
2.3× the smallest — inside the predicted 3×. **Right.**

**H23:** 1X2 improves 0.00179 and O/U 2.5 improves 0.00140. Predicted
0.001–0.003 for both. **Right**, and the two markets agree with the selection
metric rather than fighting it — unlike OPEN-3, no disagreement to adjudicate.

**H24:** pooled deficit +0.01410 → **+0.01230**, predicted between +0.010 and
+0.013. **Right.** About 13% of the gap to the market, closed.

E0 is the biggest winner in both senses: largest deviance gain and a deficit
now under one hundredth of a nat. The division that already captured 0.89 of
the market's edge captures more.

## 4. H25 — the positive control, and the mistake it caught

The control ran first, by design. **It failed on the first attempt**, and the
failure was mine rather than the feature's — which is exactly the outcome a
control exists to produce.

Version one built the oracle shots column from each club's own goals *scored*.
`dfn_s` therefore had nothing real to fit:

| estimate at a 2022-01-01 cutoff | → future goals for | → future goals against |
| --- | --- | --- |
| goal fit | 0.270 | 0.195 |
| real sot fit | 0.269 | 0.139 |
| **oracle sot fit (v1)** | **0.423** | **0.019** |

Attack improved enormously and defence was destroyed; blending both sides
cancelled them, and H25 came back at +0.00042 — reading as "the channel does
not work" when it meant "the control was blind in one eye". Rebuilt with the
attack × defence structure the GLM expects:

    oracle sot   -0.01636 [-0.01767, -0.01509]    predicted <= -0.015

**Right**, and the stop condition in `P4_SHOTS_PLAN.md` §4 was honoured: no
other arm was run until the control passed.

Worth recording separately, because it nearly cost the whole result: the
diagnostic above shows the **real** sot fit tracking future goals-against
*worse* than the goal fit does (0.139 vs 0.195), which contradicted the
pre-gate's split-half reading (shots 0.458 vs goals 0.408). Both are true and
they measure different things — raw within-season team rates versus
opponent-adjusted decayed coefficients across a forward horizon. The blend
works anyway because it combines two imperfect estimates rather than replacing
one with the other. Had I trusted the coefficient diagnostic alone, I would have
abandoned a feature that works.

## 5. What this does not do

**It does not turn the book on.** `CALIBRATION.md` §5 stands unchanged:

| | value |
| --- | --- |
| deficit to market, before | +0.01410 |
| deficit to market, after | **+0.01230** |
| vig per leg at average prices | **0.02122** |

The head is still behind the market in every division, and the gap to
profitability is still an order of magnitude wider than the improvement. Any
proposal to re-open the book needs its own gate and its own pre-registration.

## 6. Shipping decision — **ADOPTED 2026-08-04**

`shots_blend = 0.3` is now the served head. Three things moved together, as they
had to:

| | before | after |
| --- | --- | --- |
| head | `H400/a0.1/weekly/E0+E1+E2+E3+EC` | `.../sot0.3` |
| artifact | `p1-36d44c72db18b384` | **`p1-3a38e9d6ef1ca7ee`** |
| pooled deficit | +0.01419 [+0.01239, +0.01609] | **+0.01230 [+0.01041, +0.01419]** |

- `BASELINE.md` §1–2 re-issued, measured by the same `h9_baseline` code that
  produced the previous table so the two are comparable line for line. **H9
  still holds** — the head is behind the market everywhere.
- `DEFLATION.md` §5 criterion 2 restated against the new interval, with the
  holdout still sealed and the reason recorded. A restatement, not a relaxation.
- Share of the market's edge captured: E0 0.89 → **0.909**, E1 0.62 → **0.654**,
  E2 0.64 → **0.674**, E3 0.51 → **0.598**. The channel bought most where P1's
  tuning did — the bottom division.

The evaluation modules deliberately do **not** follow. `p2.py`, `p3.py` and
`p4_shots.py` each pin the head as it stood when they ran, so re-running them
still reproduces `PLAYER_PRIOR.md`, `CALIBRATION.md` and this document. Serving
moves forward; history does not.

Two operational notes:

- **`MIN_SOT_EVIDENCE` matters live.** The National League has carried no shot
  statistics since 2016-17, so EC clubs are excluded from the blend and keep
  their goal-fitted strengths. A club promoted into E3 is therefore unaffected
  by the channel in its first season, by design — the alternative was inventing
  a shots strength for it.
- Fixtures have no shot data, and do not need any: the channel is built from
  *training* matches, so serving is unaffected.

## 7. Prediction scorecard

| # | prediction | outcome |
| --- | --- | --- |
| H20 | rule selects w ∈ [0.15, 0.45]; improvement 0.003–0.007 | **right** — w=0.30, −0.00422 |
| H21 | defence ≥ 60% of full effect | **wrong** — 52% |
| H21 | attack ≤ 50% of full effect | **right** — 28% |
| H22 | negative in all four; largest < 3× smallest | **right** — all four, 2.3× |
| H23 | 1X2 and O/U each improve 0.001–0.003 | **right** — 0.00179, 0.00140 |
| H24 | deficit moves to +0.010–+0.013, not zero | **right** — +0.01230 |
| H25 | oracle ≤ −0.015, CI excluding zero | **right** — −0.01636 (on the second construction) |

**Six of seven.** The first phase in this project where the predictions were
mostly right, and — not coincidentally — the first where the pre-gate said
build rather than stop.

The one miss is small and in an informative direction: I over-estimated how
cleanly the split-half reliability gain would map onto fitted coefficients.
That mapping is exactly what §4's contradiction is about, and it is worth
distrusting again next time.
