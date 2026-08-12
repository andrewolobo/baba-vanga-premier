# The selection objective — was the head tuned blind to the product?

Written **2026-08-11**. **This is a review, not a gate.** Nothing was run
against a match outcome. Every number below is read out of the committed
`docs/p1_results.json`, `docs/p4_shots_results.json` and
`docs/channels_gate_results.json`. **No ledger row, no configurations spent,
189 unchanged.**

Subject: the claim that the frozen head's hyperparameters — `H=400`, `α=0.1`,
the sot blend weight `0.3`, and EC inclusion — were each chosen on goal Poisson
deviance under the *beat-the-book* objective, that convention 9 is exactly this
warning, and that re-sweeping them under a loss sensitive to the λ → outcome
mapping (multiclass log loss / Brier on the 1X2 vector, strike rate
confirmatory) is the highest-ceiling lever available.

**Headline: the premise is right on the facts and the conclusion does not
follow. The counterfactual was already recorded. `sweep.run` computes `ll_1x2`
for every arm of every sweep, so "chosen on deviance" is true of *selection* and
false of *measurement* — and on the recorded numbers three of the four named
parameters have the two objectives choosing the same arm. The fourth, `H`, does
disagree, and it disagrees by trading the 1X2 market against the O/U market with
goal deviance sitting between them.**

Re-derive the whole table with:

```
python -c "
import json
p1=json.load(open('docs/p1_results.json'))
for b in ('h2','h3'):
    a={x['value']:x for x in p1[b]['arms']}
    print(b, 'dev', min(a,key=lambda k:a[k]['deviance']),
             '1x2', min(a,key=lambda k:a[k]['ll_1x2']),
             'ou25', min(a,key=lambda k:a[k]['ll_ou25']))"
```

---

## 1. The check was already paid for

[`engine/eval/sweep.py:183`](../engine/eval/sweep.py#L183) records `ll_1x2` and
`ll_ou25` on every arm of every sweep, and
[`sweep.compare`](../engine/eval/sweep.py#L229) does the same for every named
comparison. This is deliberate — the module docstring says so, and so does
[`metrics.py`](../engine/eval/metrics.py#L5): *"1X2 and O/U 2.5 logloss are
computed on the same runs and reported, never used to select. If they rank the
grid differently that is written down as a finding rather than used to break a
tie."*

So the question "would a 1X2-sensitive loss have chosen differently?" needs no
new arms. It needs the committed JSON read in a column nobody had ranked.

| parameter | chosen | deviance argmin | **ll_1x2 argmin** | cost of the chosen value, on ll_1x2 |
| --- | --- | --- | --- | --- |
| α (ridge), h3 | 0.1 | 0.05 | **0.05** | **+0.000018** |
| sot blend `w`, h20 | 0.3 | 0.3 | **0.3** | **0.000000** |
| channel blend `w`, h38 | 0.3 | 0.45 | **0.3** | **0.000000** |
| EC inclusion, h5 | in | in | **in** | **0** — agrees, and resolves |
| **half-life `H`, h2** | **400** | 400 | **300** | **+0.000290** |
| **half-life `H`, h2-guard** | **400** | 300 | **240** | **+0.001836** |

**α is not a live lever.** Both objectives pick 0.05, the 1-SE rule took 0.1,
and the whole difference is 0.000018 nats of 1X2 logloss — four orders of
magnitude below the gap to the market. `DEFLATION.md` separately measured
**PBO 0.022** on this exact grid, so the selection is also not overfit.

**Neither blend weight is a live lever, and this was checked twice in
independent gates.** h20 (the sot weight, `SHOTS_TARGET.md`) and h38 (the
channel weight, `CHANNELS_GATE.md`) both put the deviance choice and the 1X2
argmin on the same arm. h38 is the interesting one: deviance's argmin is 0.45,
the **1-SE rule pulled it back to 0.30 — which is exactly the 1X2 optimum**. The
regularisation preference convention 2 carries has been doing the 1X2
objective's work for free.

**EC inclusion agrees on every metric and re-sweeping it could only do harm.**
`E0-EC` beats `E0-E3 only` by −0.00272 on deviance (resolved), −0.00106 on
ll_1x2 and −0.00104 on ll_ou25, with the promoted-club population at −0.0576.
There is no objective under which this arm flips.

---

## 2. `H` is the one live axis, and the disagreement replicates

Three sweeps, run at different times on different populations, all say the same
thing: **the 1X2 optimum sits at a shorter half-life than the deviance
optimum.**

| sweep | population | deviance argmin | ll_1x2 argmin | ll_ou25 argmin |
| --- | --- | --- | --- | --- |
| h2 | 21,896, α=1.0 | 400 | **300** | 650 |
| h2-guard | 19,860, both COVID seasons out | 300 | **240** | 650 |
| h4 (2D star) | 21,896, around (400, 0.1) | — | **H330** | H470 |

h4 is the local refinement around the chosen centre and it is the sharpest
version:

| arm | deviance | vs centre (deviance) | ll_1x2 | ll_ou25 |
| --- | --- | --- | --- | --- |
| centre `H400/a0.1` | 2.882412 | — | 1.040321 | 0.691943 |
| **`H330/a0.05`** | 2.882143 | −0.00027 [−0.00071, +0.00020] — **no difference** | **1.039362** | 0.692533 |
| `H330/a0.2` | 2.882313 | −0.00010 [−0.00059, +0.00040] — no difference | 1.039564 | 0.692416 |
| `H470/a0.05` | 2.882969 | +0.00056 [+0.00020, +0.00093] ✱ — centre better | 1.041191 | 0.691663 |
| `H470/a0.2` | 2.883060 | +0.00065 [+0.00027, +0.00104] ✱ — centre better | 1.041282 | 0.691591 |

`H330/a0.05` is **−0.000958** better on ll_1x2 than the served centre while
deviance calls it a tie. On the face of it that is the lever, and it is the
largest objective disagreement anywhere in the ledger.

---

## 3. It is a trade between the two served markets, not a free gain

This is the finding that kills the framing. Along `H`, the two outcome markets
have their optima **on opposite sides of the deviance choice**, and goal
deviance lands between them:

```
ll_1x2  wants H ≈ 300      deviance wants H = 400      ll_ou25 wants H ≈ 650
```

Priced as a trade against the served head:

| move | ll_1x2 | ll_ou25 |
| --- | --- | --- |
| H 400 → 300 | **−0.000290** | **+0.000677** — net worse |
| H 400 → 650 | +0.001799 | −0.000457 |
| `H330/a0.05` vs centre | **−0.000958** | **+0.000590** — net +0.00037 |

**Goal deviance is not blind to the mapping. It is the joint objective over both
count margins, and the two outcome markets it induces disagree with each other
by about as much as either disagrees with it.** Selecting on the 1X2 vector
alone is not "fixing an objective error", it is choosing one served market over
the other — and `BACKLOG.md` B4 wants to *expand* the goal-line half of the menu
to six lines.

α shows the same conflict in a form convention 7 forbids reading: ll_ou25 is
monotone in α right out to **5.0, the grid edge** (0.691995 → 0.690745). The
O/U preference for shrinkage is **censored**, so it cannot be quoted as an
optimum at all, only as "at least 5".

**This is `OUTSTANDING.md` §9.4's problem, arriving from a new direction.**
Scoping selection per market would require amending convention 2, which is an
owner decision rather than a measurement.

---

## 4. The class of change cannot reach the defect that motivates it

The proposal's stated target is the λ → outcome mapping — the defect
`SEPARATION_SLOPE.md` documents. `H`, `α`, `w` and EC all move **λ**. The
mapping is a fixed independent-Poisson score matrix at `rho=0`
(`selection.raw_probs` → `dispersion.score_matrix`), and none of these four
parameters touches it.

What they *can* do is change the dispersion of predicted separation
`d = (log λ_h − log λ_a)/2`. That axis already has a dedicated, maximally
efficient single dial —
[`home_term.stretch`](../engine/eval/home_term.py#L200), which scales centred
`d` while holding home advantage and the goal level fixed — and
[`fit_stretch`](../engine/eval/home_term.py#L222) already declines the
1X2-fitted version in its own docstring, on convention 2 grounds:

> Fitted on goals rather than on outcomes deliberately: the selection metric is
> goal deviance, so a stretch chosen on 1X2 would be optimising one thing and
> adjudicated on another.

**§9.6 step 2 ran the deviance-fitted version and it moved nothing** — optimal
stretch ~1.05 pooled, and applying it leaves every calibration gap where it was
(pooled home +0.33 → +0.32, E0 +1.77 ✱ → +1.74 ✱).

> **Correction 2026-08-11, from `OUTSTANDING.md` §9.12.** That is not what step
> 2 established. The stretch is **centred**, so it cannot move a *mean*, and the
> gaps quoted above are means — step 2 never computed the **slope** under a
> stretched head. Measured: the deviance-optimal stretch is **1.0936**, not
> ~1.05, and it takes the home slope from **+5.66 to +0.83**. **The class of
> change CAN reach the defect**, and this section's mechanism argument is wrong
> as stated.
>
> **The parameter verdicts in §§1–3 are unaffected**, and the reason matters:
> what works is a **post-hoc stretch on centred separation**, not a re-sweep of
> α, either blend weight, or EC. The α grid is flat and both objectives pick the
> same arm, so lowering α is not the dial — §1's table stands as measured.
>
> **What it changes is §7's direction.** The head is roughly **10%
> under-dispersed** in strength, and §2's H disagreement — 1X2 wanting a shorter
> half-life, i.e. more responsive and more dispersed strengths, than goal
> deviance does — is the **same fact by a second route**. Two independent
> measurements now put the dispersion axis where the outcome-level objectives
> and goal deviance part company. **That is the defensible residue of the
> "objective-blindness" criticism this document was written to assess** — and it
> is not any of the four hyperparameters the criticism named.

`SEPARATION_SLOPE.md` §5 names the untested arm precisely: the stretch that
**zeroes** the slope, priced in goal deviance, as a **diagnostic**. It also
records why fitting to it is a trap — the sham in §9.6 step 3, a temperature
sharpener carrying **no outcome information at all**, drives the pooled slope to
−14.65 ✱. A zero crossing exists and reaching it proves nothing.

**A 1X2-selected hyperparameter sweep is the expensive, indirect, multiplicity-
heavy version of an arm that is already pre-registered at ~1 configuration.**
Convention from §1.12 applies directly: run the cheap ceiling first and read
every prediction against it.

---

## 5. The exchange rate into strike rate is unmeasured, and the one datapoint is null

The proposal makes strike rate confirmatory. Nothing in this project has ever
measured what a nat of 1X2 logloss is worth in strike rate, and the nearest
evidence says approximately nothing.

**B2's vector scaling *is* multiclass-log-loss optimisation** — five parameters
fitted by likelihood on the 1X2 vector — applied at the mapping level, where
leverage is highest rather than lowest. §9.6 step 3 measured it in the product:

| arm | recommendations changed | strike | vs shipped, paired |
| --- | --- | --- | --- |
| raw (shipped) | — | 72.49% | — |
| B2 calibrated | **18.42%** | 72.58% | **+0.088 [−0.410, +0.556]** |

**One recommendation in five changed and strike rate did not move.** The tip
population resolves roughly 1.5 points (`BACKLOG.md` B1); this is a fifteenth of
that.

Counting τ (§9.5), B2 (§9.6 step 3) and the deviance-optimal stretch (§9.6 step
2), **three arms have now moved this mapping and none bought strike rate.**
`SEPARATION_SLOPE.md` §8's closing warning covers a fourth: it needs a reason
the first three lacked.

---

## 6. Sizing the ceiling

Every figure measured, all on ll_1x2, all committed:

| quantity | ll_1x2 |
| --- | --- |
| **H re-sweep, the whole available disagreement** | **−0.00029 to −0.00096** |
| channels gate `+both` (measured, not adopted) | −0.00053 |
| shots channel (measured, **shipped**) | −0.00179 |
| shots+corners **oracle ceiling** | −0.00149 |
| sot **oracle ceiling** | −0.00656 |
| **model-to-market 1X2 gap, pooled (n = 21,890)** | **+0.01410** |

Best case the lever is **~7% of the gap to the market**, roughly half the shots
channel, and half of it is handed back on O/U.

---

## 7. What the criticism gets right, and it is not the objective

Two things survive, and neither is the one that was argued.

**`H=400` inherits two assumptions, and convention 9 is about that.** h2 swept
the half-life at **α=1.0** — an order of magnitude more shrinkage than the
α=0.1 eventually chosen — and h3 then swept α at H=400. The only joint check is
h4's four-point star. And **h2 has never been re-run since the sot channel
shipped**: `p1_results_shots_head.json` carries `base_score` and
`pooled_deficit` only. So H=400 was chosen under a different α *and* under a
head with no shots channel. **That is convention 9's actual complaint, it is
live, and it applies to goal deviance too — it is not an objective question at
all.**

**No hyperparameter arm anywhere carries an interval on `ll_1x2`.**
[`sweep.py:177`](../engine/eval/sweep.py#L177) bootstraps goal deviance and
nothing else, in both `run` and `compare`. Every 1X2 figure in this document is
a bare point estimate, including the −0.000958 that §2 leans on, and it may be
noise. The machinery exists and is already used elsewhere —
[`p3.py:168`](../engine/eval/p3.py#L168) block-bootstraps a paired ll_1x2
difference. **Nothing in §1 or §2 should be treated as resolved until that runs.**

---

## 8. Recommended order, with costs

1. **`SEPARATION_SLOPE.md` §8 item 1 first — 0 configurations.** Null A and the
   P0-1 noise sweep exist only as prose in `OUTSTANDING.md` §9.6 and cannot be
   re-run. Everything in §4 above about the mapping defect rests on controls
   nobody can check. Synthetic outcomes throughout.
2. **Paired ll_1x2 intervals on arms already run** — the h4 star and the h2
   grid. This decides whether §2's disagreement is real at all. **Accounting is
   an owner call**, the same one `SEPARATION_SLOPE.md` §8 item 2 raises: the
   grids are already in the ledger and the outcome information was spent when
   they ran, so arguably 0, arguably 1.
3. **The zeroing-stretch diagnostic — ~1 configuration**
   (`SEPARATION_SLOPE.md` §8 item 4). The cheap, isolated, already-pre-registered
   version of this lever. It prices the whole family before anything expensive
   runs.
4. **Only if 2 and 3 both come back positive: pre-register `H` alone, on the
   shipped head.** Not four parameters. Fixing `H`'s staleness (§7) is defensible
   on deviance grounds by itself; re-selecting it on 1X2 is not, until §3's trade
   against O/U has an owner decision behind it.

**Do not** sweep the four parameters jointly. The grid is 9 × 8 × 5 × 2 =
**720 configurations** against a ledger of **189**, for a lever whose ceiling
§6 bounds at one thousandth of a nat.

**Do not** treat this document as licensing a head change. Nothing here was
measured, and `OUTSTANDING.md` §1.3 lists the five things a head change owes.
