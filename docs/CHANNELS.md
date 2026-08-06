# P4-channels pre-gate results — the in-store channels are not exhausted

Run **2026-08-06** against the pre-registration in `P4_CHANNELS_PREGATE.md`.
Ledger row `probe:p4_channels_pregate` (76). Reproduce with
`python -m engine.eval.channels --stage all`.

**Headline: a third and a fourth channel add as much split-half reliability as
the shots channel did, and a noise control says the instrument is not inflating.
The pre-gate says run the gate.** It got there by refuting two of its own three
predictions and voiding one of its own stop rules.

Configuration count is **unchanged at 149** — this is a probe with no arm list,
the same accounting `OUTSTANDING.md` §0 applies to the travel controls.

---

## 1. M4 — the cell row 53 never measured

Leave-one-season-out split-half reliability, 1,103 team-seasons, E0–E3, COVID
embargoed. Higher is better.

| predictor set | → goals for | → goals against |
| --- | --- | --- |
| goals | 0.5282 | 0.4391 |
| sot | 0.3938 | 0.3485 |
| shots | 0.4609 | 0.4261 |
| corners | 0.4305 | 0.3847 |
| **goals+sot** (shipped) | **0.5426** | **0.4621** |
| goals+sot+shots | 0.5719 | 0.5045 |
| goals+sot+corners | 0.5768 | 0.4961 |
| **goals+sot+shots+corners** | **0.5916** | **0.5161** |
| goals+sot+NOISE | 0.5418 | 0.4621 |

Gain over the shipped pair, as (attack, defence):

| added | attack | defence |
| --- | --- | --- |
| shots | +0.0293 | +0.0424 |
| corners | +0.0342 | +0.0340 |
| **shots + corners** | **+0.0490** | **+0.0540** |
| NOISE (control) | −0.0008 | +0.0000 |

**For scale:** row 53 measured adding *sot to goals* at +0.039 attack / +0.060
defence, and that channel cashed out at −0.00422 nats and shipped. The two
unused in-store channels are worth the same order of magnitude.

**Shots and corners are complementary, not redundant** — together (+0.049,
+0.054) they beat either alone, sub-additively.

## 2. The negative control is what makes §1 readable

Adding any predictor can only raise in-sample multiple R, so a third channel
would appear to help by construction. Leave-one-season-out bounds that without
proving it is zero, which is why a Poisson noise channel — matched to the
corners rate, independent of every match, seed `20260806` — runs alongside.

It gains **−0.0008 / +0.0000**. The instrument does not inflate, and the +0.03
to +0.05 gains are the data rather than the arithmetic. Convention 8 in reverse:
a positive result needs a planted *negative* as much as a null needs a planted
positive.

## 3. What was wrong, and it matters

**Corners was struck from the candidate list on the wrong statistic.** Per-match
same-side correlation with goals is **0.021**, which reads as a dud. At the level
the model actually works — a team-season mean over 19–23 matches — it is
**+0.418**. Match noise dilutes the per-match figure by a factor of twenty, and
the strength layer never sees per-match values. Corners then turned out to be the
*best* single addition on attack.

**M5's stop rule was void, and its own control says so.** The rule was "sot and
total-shots coefficients above 0.95 collinear ⇒ no third channel". Measured:

| | att | dfn |
| --- | --- | --- |
| sot ~ shots | +0.9748 | +0.9607 |
| **goals ~ sot** (the adopted channel) | **+0.9712** | **+0.9743** |

The threshold vetoes the feature that shipped and works. Every channel's att/dfn
vector is dominated by the same between-club quality ordering, so coefficient
correlation cannot discriminate between "duplicate" and "complementary". On
defence, shots is *less* redundant with sot (0.961) than sot is with goals
(0.974).

This is the second time a coefficient diagnostic has given the wrong answer
about this exact feature — `SHOTS_TARGET.md` §4 records the first, where it
"would have killed a feature that works". The lesson did not transfer because it
was written as a note about one diagnostic rather than as a rule about the class.
**Reliability-on-held-out-matches is the statistic that has been right both
times.**

## 4. M6 — the per-side weight is not identified

The 2-D surface `D(w_att, w_dfn)` has six quadratic parameters and the ledger
supplies five constraints: H20's diagonal (rows at w = 0, .15, .30, .45, .60,
.80) and H21's three single-side arms. The free parameter is
`t = Haa/(Haa+Hdd)`, the split of curvature between the two sides.

| | value |
| --- | --- |
| diagonal vertex | w\* = 0.3413 (grid chose 0.30) |
| gain from the diagonal refinement alone | −0.0000627, **0.22 paired SE** |
| cross term `Had` | −0.009478 — H21's super-additivity, quantified |
| over-determined consistency residual | −5.8e−6 |
| gain over admissible `t`, optimum inside the measured box | −0.00006 to −0.00096 |
| | **0.22 to 3.37 paired SE** |

**The pre-registered stop rule does not fire, and neither does a licence to
sweep.** A (w_att, w_dfn) grid at six points each is 36 configurations — a
quarter of everything spent so far. `t` is identified by **one extra single-side
arm at a second weight**: att-only at w = 0.60 pins `ga` and `Haa` against the
existing w = 0.30 arm. **2 configurations, not 36.**

Values of `t` whose implied optimum escapes the measured box are reported as
out-of-range rather than as gains — a quadratic fitted on w ∈ [0, 0.8] says
nothing at w_dfn = 2.7, and reading it would have manufactured a 37-SE result.

## 5. Prediction scorecard

| # | prediction | outcome |
| --- | --- | --- |
| M4 | `goals+shots+sot` beats `goals+sot` by < 0.005 attack, < 0.010 defence | **wrong** — +0.029 and +0.042, out by 6× and 4× |
| M5 | sot and total-shots `dfn_s` > 0.90 collinear | **right numerically** (0.961) and **void as a rule** — §3 |
| M6 | best per-side gain < 0.0005 deviance | **wrong** — 0.22 to 3.37 SE, and unidentified |

One of three, and the one that held was the one that turned out not to mean
anything. The consistent error is the opposite of P1's and P3's: there I kept
expecting the corpus to yield more than it does, and here I expected it to yield
less. Both are the same failure to let the measurement decide.

## 6. What this does and does not license

**It licenses a gate**, pre-registered separately, on `shots` and `corners` as
additional channels — and per §4, an att-only arm at a second weight to identify
the surface before any 2-D sweep is contemplated.

**It does not predict the gate passes.** Split-half reliability is not deviance,
and `SHOTS_TARGET.md` §7 already records over-estimating how cleanly that
mapping runs. Row 53's +0.039/+0.060 became −0.00422 nats; nothing here says
+0.049/+0.054 becomes anything in particular.

**It does not touch the book.** `CALIBRATION.md` §5 stands: the pooled deficit is
+0.01230 against a vig of 0.02122 at average prices, and per `OUTSTANDING.md`
§2.3 nats and de-vigged probability do not net. A second shots-sized channel
closes about an eighth of the gap.

## 7. Two things found on the way that are not results

**Row 53 is not reproducible.** The pre-gate that produced `SHOTS_TARGET.md` §1's
M1/M2/M3 table was never committed — `p4_shots.py` holds only H20/H21/H22/H25,
and nothing in `engine/` computes split-half reliability. This is the one P4
artifact that cannot be re-run, against the posture `SHOTS_TARGET.md` §6 states
for `p2.py`, `p3.py` and `p4_shots.py`.

M4 is therefore a rebuild, not a re-run, and **it disagrees with row 53 on the
comparison that motivated the shots channel**: row 53 put sot (0.446) above goals
(0.441) on attack, and this harness puts goals (0.528) well above sot (0.394).
The disagreement is unresolvable without the lost code. It does **not** unsettle
the shots channel — that was established by H20's gate at −0.00422 and 7.3 paired
SE, not by the pre-gate — but it does mean §1's absolute values sit on a
different footing from row 53's, and only the within-run contrasts and the noise
control carry weight here.

**FBref cannot supply xG through the built path.** Verified 2026-08-06: date
pages carry no xG column for any of 60 competitions, and neither does the
Premier League comp-season schedule page for 2022-23 *or* the current season —
zero `xg` data-stats in 628 KB, comments included. The remaining route is
per-match report pages, ~26,000 requests against a 10 req/min policy. **xG is
not gated on a session refresh; it is unreachable here.** That is what promotes
the in-store channels from "probably overtaken" to the live question, and it is
why this pre-gate was worth running.
