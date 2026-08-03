# P3-lite pre-registration — calibration, ablation, and the launch decision

**Written 2026-08-03 before any of it was run.** Predictions are numeric so they
can be wrong. Results land in `CALIBRATION.md`; this file is not edited
afterwards.

The question this phase answers is not "is the model good" — P1 settled that, at
0.0117–0.0155 nats behind the market. It is **"do the model's disagreements with
the market carry information?"** If they do, a selective rule can beat the close
even though the model loses to it globally. If they do not, no rule built on this
head can, and the book stays off at launch.

---

## The launch bar

**Book ON for a division × market stratum iff its walk-forward CLV is ≥ 0 with a
paired-bootstrap CI excluding zero.** Decided per stratum, not globally, and
pre-committed here so the threshold cannot move after the numbers arrive.

Everything else ships regardless: fixture sync, predictions, CLV grading of the
served probabilities. Opening-weekend data is irrecoverable.

---

## H11 — Per-population Platt calibration

**Claim.** Calibrating raw pmf output improves logloss, most in E1–E3 where P0-2
found a ~+1 point draw deficit, least in E0 where the deficit is +0.01.

**Method.** Walk-forward by season with a 3-season burn-in: fit on all seasons
strictly earlier, apply to the held-out season. Never in-sample. 1X2 gets vector
scaling (per-class slope and bias on log-probabilities, softmax-renormalised);
O/U 2.5 gets standard binary Platt on the logit. Populations: E0 separate,
E1/E2/E3 separate, plus a pooled E1–E3 arm to settle OPEN-6.

**Poison test.** The fit must derive from the stored **λ**, not from stored
probability columns. Corrupt the probability columns; the calibration must be
bit-identical. A calibration fitted on already-calibrated inputs would compound
silently and look fine.

**Prediction.** 1X2 logloss improves by 0.001–0.004 in E1–E3, ≤ 0.001 in E0.
O/U improves by 0.000–0.002 everywhere. **Calibration does not close the gap to
the market** — it fixes level, and the gap is information.

**OPEN-6 sub-prediction.** Pooled E1–E3 is within 0.0005 nats of separate fits
(poolable); E0 pooled with them is worse by > 0.001 (not poolable).

## H12 — The market ablation, run early

**Claim.** This is the decisive measurement. Fit, out-of-sample by season:

```
1X2 :  eta_k = a * log(p_model_k) + c * log(p_market_k) + b_k
O/U :  logit(y) = a * logit(p_model) + c * logit(p_market) + b
```

`a` is what the model adds *once the market is already in the equation*.

**Prediction.** `c` ≈ 1 and highly significant everywhere. **`a` ∈ [0.00, 0.15]
pooled, with the CI excluding zero on O/U 2.5 and spanning zero on 1X2.**
Rationale: P0-1 confirmed the totals distribution is Poisson and the model's
scoring-rate estimate is a genuinely different basis from the market's, whereas
on 1X2 the market prices team strength directly and better than we do.

**Falsifier / stop condition.** If `a` is indistinguishable from zero in every
stratum, **no rule built on this head can beat the close**, the book stays off,
and the honest conclusion is that P2 information — not tuning — is the path.

**Note on purity.** Using market prices as a model input makes the blend a
market-aware head. That is legitimate for serving at the pre-close information
set (the price is knowable then) and it is exactly the ablation SPEC §P5
mandates. The pure head remains the P1 artifact; the blend is a separate,
labelled arm and never overwrites it.

## H13 — The bet rule re-backtested

**Claim.** Re-run yesterday's losing rule with (a) calibrated and (b) blended
probabilities, scoring CLV against the de-vigged Pinnacle close, per division ×
market.

**Baseline to beat** (uncalibrated, `OUTSTANDING.md` §1.0): mean CLV −0.00163 at
min_edge 0, worsening to −0.00171 at 0.02, against −0.00000 for no filter at all.

**Prediction.** Calibration alone moves CLV from −0.0016 to roughly −0.0005 but
**does not reach zero** — it removes level error, not the anti-informativeness.
The blend reaches CLV ≥ 0 in **at most two strata**, most likely O/U 2.5 in E1–E3
where the market is thinnest and the model's scoring-rate basis is most
independent. Pooled CLV stays ≤ 0.

**Prediction on volume.** Whatever turns positive will bet **under 5% of legs**,
not the 19% the uncalibrated rule fired at. A rule with a real edge on this
corpus must be rare.

---

## Trial budget

| kind | name | arms |
| --- | --- | --- |
| GATE | h11_platt_calibration | 5 populations × 2 markets |
| PROBE | h11_open6_pooling | 2 |
| GATE | h12_market_ablation | 5 × 2 |
| GATE | h13_clv_rule_backtest | 3 bases × 5 thresholds |
| GATE | p3_launch_decision | 1 |

Five entries. Ledger stands at 41 before this phase.
