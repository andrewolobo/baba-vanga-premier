# P3-lite results — and the launch decision

Run 2026-08-03 against the pre-registration in `P3_PLAN.md`. Every result is in
`gate_ledger`; the ledger stood at **45 trials** when this was written.

> **STALE NUMBERS, STANDING DECISION — flagged 2026-08-04.**
>
> Every figure below was measured on the head as it was that day:
> `H400 / a0.1 / weekly / E0+E1+E2+E3+EC`, **without** the shots channel. The
> head was re-frozen on 2026-08-04 to adopt it (`SHOTS_TARGET.md`), so §2, §3
> and §4 describe a model that is no longer served. `engine/eval/p3.py` pins the
> old config deliberately so this document stays reproducible; re-running it
> against the new head is a **new measurement** needing its own ledger row.
>
> **The decision in §5 is not stale.** Two reasons, neither of which is an
> arithmetic patch:
>
> - §1's finding — that CLV must exceed the **vig**, not zero — is arithmetic
>   about margin and holds for any head. So is §4's finding that positive CLV at
>   average prices was an artifact of pricing a wide-margin consensus against a
>   sharp close.
> - §3's argument is structural, not marginal. The blend gives the model weight
>   only if it adds information *given the price*, and the re-issued base score
>   confirms **H9 still holds**: the head remains behind the market in every
>   division on both served markets. A head still behind the price still earns
>   near-zero weight beside it.
>
> **What cannot be claimed** is that the shortfall shrank by a computable
> amount. The head improved by 0.00179 nats of 1X2 logloss; the shortfall is
> 0.0186 in de-vigged probability. Those are different units and do not net off.
> Anyone wanting the new number has to re-run P3, not subtract.

**Headline: the book stays off at launch.** The head carries no exploitable
information beyond the market price. That is now measured four independent
ways rather than assumed, and the pre-registered decision bar turned out to be
the wrong bar — which is itself the most important finding here.

---

## 1. The bar was wrong, and here is why that matters

`P3_PLAN.md` pre-committed: *book ON for a stratum iff walk-forward CLV ≥ 0
with a CI excluding zero.* Two strata passed it — E1 1X2 (CLV +0.00603
[+0.00224, +0.00946]) and E2 1X2 (+0.00582 [+0.00290, +0.00884]).

**Both would have lost money.** E1 ROI −7.59%, E2 ROI −9.99% [−19.09%, −0.67%].

The bar embodied the standard sports-betting heuristic that positive CLV implies
eventual profit. That heuristic silently assumes the CLV is large relative to
the margin paid. Here it was not, by a factor of eight:

| | value |
| --- | --- |
| blend's mean CLV at average prices | **+0.00262** |
| vig per leg at average prices | **0.02122** |
| shortfall | **−0.01860** |

Beating the close by a quarter of a point while paying two points of margin is
a losing bet that looks early. **The correct bar is CLV > vig, not CLV > 0**, and
following the letter of the pre-registration would have turned on a book that
was measured-negative on the metric that pays.

Recorded rather than quietly amended, because a bar that moves after seeing the
numbers is not a bar.

## 2. H11 — calibration: wrong prediction, and it makes things worse

**Predicted:** 1X2 improves 0.001–0.004 in E1–E3, ≤0.001 in E0; O/U improves
0.000–0.002 everywhere. Sign convention below: **negative = calibration better.**

| division | n | Δ logloss 1X2 | Δ logloss O/U |
| --- | --- | --- | --- |
| E0 | 3,420 | +0.00147 [−0.00127, +0.00422] | −0.00048 [−0.00269, +0.00195] |
| E1 | 4,968 | +0.00026 [−0.00129, +0.00185] | **−0.00305** [−0.00549, −0.00055] |
| E2 | 4,815 | +0.00075 [−0.00044, +0.00192] | **−0.00221** [−0.00429, −0.00006] |
| E3 | 4,851 | **+0.00149** [+0.00013, +0.00293] | −0.00084 [−0.00309, +0.00155] |

**Wrong on 1X2, right on O/U.** Calibration helps O/U in E1 and E2 exactly as
predicted — the lower divisions, where P0-2 found the draw deficit. But on 1X2
it helps nowhere and **significantly hurts E3**.

The likely mechanism is non-stationarity: a correction fitted on seasons 1..N−1
and applied to season N is stale if the miscalibration itself moves. On O/U the
defect is a persistent scoring-rate offset and the correction transfers; on 1X2
it apparently does not.

Consequence: **calibration is not wired into serving.** `calibrated` stays 0.

## 3. H12 — the market ablation: the model adds nothing

The decisive measurement. Fit out-of-sample by season, `a` = model weight once
the market price is already in the equation.

| division | 1X2 model weight | 1X2 market | O/U model weight | O/U market |
| --- | --- | --- | --- | --- |
| E0 | +0.121 (sd 0.078) | 0.969 | +0.153 (sd 0.086) | 0.881 |
| E1 | −0.070 (sd 0.080) | 1.172 | −0.026 (sd 0.033) | 1.025 |
| E2 | −0.115 (sd 0.129) | 1.213 | +0.140 (sd 0.079) | 0.935 |
| E3 | **−0.253** (sd 0.043) | 1.250 | −0.017 (sd 0.074) | 0.940 |

Market weight ≈ 1 everywhere, as expected. Model weight is small, inconsistent
in sign, and **negative in five of eight cells** — a negative weight means the
head is mildly *anti*-informative given the price.

And the blend never beats the market (positive = market better):

| division | blend vs market, 1X2 | blend vs market, O/U |
| --- | --- | --- |
| E0 | +0.00098 [−0.00035, +0.00225] | +0.00050 [−0.00046, +0.00147] |
| E1 | +0.00022 [−0.00083, +0.00122] | **+0.00042** [+0.00002, +0.00082] |
| E2 | +0.00025 [−0.00094, +0.00161] | +0.00067 [−0.00001, +0.00135] |
| E3 | −0.00027 [−0.00150, +0.00098] | **+0.00087** [+0.00011, +0.00160] |

Not one cell where the blend beats the market. Two where the market beats the
blend with a CI excluding zero. **This is the stop condition `P3_PLAN.md` named:
no rule built on this head can beat the close.**

## 4. H13 — the rule re-backtested, and what best-price execution changes

CLV against the de-vigged Pinnacle close, walk-forward:

| basis | min_edge | bets | mean CLV | beat close | ROI |
| --- | --- | --- | --- | --- | --- |
| uncalibrated | 0.00 | 22,153 | −0.00160 | 44.7% | −8.21% |
| **calibrated** | 0.00 | 19,508 | **−0.00230** | 43.8% | −8.92% |
| blended | 0.00 | 2,220 | **+0.00262** | 54.4% | −4.75% |

Calibration makes CLV *worse*, consistent with §2. The blend's positive CLV
looked like the first real signal in the project — 9 of 10 seasons positive.

**It was largely an artifact, and finding that out is the most useful thing in
this document.** `bet_prob` was de-vigged from the *average* market; `close_prob`
from Pinnacle's close. Margin is not distributed proportionally across outcomes,
so de-vigging does not fully equalise a wide-margin consensus against a sharp
one. Much of that +0.0026 was measuring that Pinnacle's close is sharper than
the average pre-close — which H10 already established at 0.0025 nats — not our
skill.

Re-priced consistently at **best-available (Max)** odds, where the market is
nearly fair and the comparison is like-for-like:

| | average prices | best-available prices |
| --- | --- | --- |
| overround (1X2) | 6.37% | **0.65%** |
| vig per leg | 0.02122 | **0.00217** |
| blend mean CLV | +0.00262 | **+0.00000** |
| blend ROI, min_edge 0 | −4.75% | **−1.31%** [−2.97%, +0.36%] |
| blend ROI, min_edge 0.02 | −1.97% | +2.95% [−1.31%, +7.43%] |
| seasons profitable | — | **4 / 9** |

**Removing the vig removes the losses; it does not reveal a profit.** ROI moves
from roughly −6% to −1.3%, and every interval spans zero. Four of nine seasons
profitable is a coin flip, and the worst seasons (−6.1%, −5.8%) are larger than
the best (+2.9%, +2.1%). CLV at Max is **exactly zero** — which is the same
conclusion as H12, arrived at from the price side.

The +2.95% at min_edge 0.02 is the kind of number that gets a strategy shipped.
It rests on 2,658 bets with a CI from −1.3% to +7.4%, selected after looking at
five thresholds. It is noise around zero.

## 5. The launch decision

**Book OFF for every stratum.** Not one passes a bar of "CLV > vig" or "ROI
interval excluding zero", at either price level.

**Everything else ships**: fixture sync, predictions, CLV grading of the served
probabilities, the API and the frontend. Opening-weekend prediction data is
irrecoverable, and the CLV series is the instrument that will detect a real edge
if one ever appears.

What would change the answer, in order of expected value:

1. **P2 player prior.** The National League gate found promoted clubs predicted
   0.058 nats better when the fit had seen their lower-division matches
   (`BASELINE.md` §3) — roughly twenty times the blend's entire contribution.
   Information, not tuning, is the binding constraint.
2. **Best-price execution as a prerequisite, not an optimisation.** At average
   prices a strategy needs 8× the current signal to break even; at best-available
   it needs about 1×. Any future edge is only harvestable with real price
   shopping, so the odds feed should capture Max from day one — it already does.
3. **P4 context features**, on top of P1+P3, each gated the same way.

What will not change it: more calibration, more blending, more thresholds. Those
are all measured, all null or negative, all recorded.

## 6. Prediction scorecard

| # | prediction | outcome |
| --- | --- | --- |
| H11 | 1X2 improves 0.001–0.004 in E1–E3 | **wrong** — no improvement; significantly worse in E3 |
| H11 | O/U improves 0.000–0.002 | **right** — −0.0031 E1, −0.0022 E2, both excluding zero |
| H12 | model weight ∈ [0.00, 0.15], CI excluding zero on O/U | **wrong** — negative in 5 of 8 cells; blend never beats market |
| H13 | calibration moves CLV −0.0016 → ~−0.0005 | **wrong** — moved the wrong way, to −0.0023 |
| H13 | blend reaches CLV ≥ 0 in at most two strata | **right in letter** (E1, E2 1X2) but the CLV was an artifact |
| H13 | whatever turns positive bets < 5% of legs | **right** — blend at min_edge 0 fires on 3.6% |

Six predictions, two right. The consistent error is the same one as in P1: I
keep expecting this corpus to yield more than it does.
