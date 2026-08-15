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

| unit | count **as at 2026-08-04** | count **as at 2026-08-06** |
| --- | --- | --- |
| ledger rows ("trials") | 52 | **76** |
| distinct questions | 24 | **41** |
| **configurations actually scored** | **133** | **149** |
| rows recording no arm list | 28 | **47** |

The count is a floor, not a total: rows recording no arm list each scored at
least one configuration.

> **These numbers move, and that is the point of Decision 1.** The left column
> is what was on the table when this decision was taken and is kept so the
> decision can be read in its own context; the right is the count at the last
> revision of this file. **Neither is authoritative at P6.** Re-derive with
> `count_configurations` immediately before reading the holdout — quoting a
> figure from prose is exactly the failure `OUTSTANDING.md` §0 records itself
> committing. Note the call needs `conn.row_factory = sqlite3.Row` or it raises
> an opaque `ValueError`.

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

**Decision 6 — unattributed rows.** The rows carrying no arm list (28 when this
was written, **47** at the last revision — §1) are reported as a known
undercount, never silently treated as one configuration each. Any P6 statement
of the count carries the phrase "at least", and re-derives the figure rather
than quoting this one.

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

> **Amended 2026-08-15, before any pooled PBO was computed.** `META.md` §8
> exposed a hole in this guard that `OUTSTANDING.md` §1.9 directed be fixed
> here: `choice_mattered` tests the spread across **all** columns, so one
> clearly losing arm makes a field look separable while the arms that could
> actually have been chosen are not — P5 measured PBO 0.631 on all four arms
> and 0.000 on the only comparison that decided anything. The fix is not a new
> statistic but a reporting rule: **any pooled PBO is reported together with
> PBO on each selection grid separately** — the decision-relevant subsets,
> since every selection this project made was within one grid — and all of
> them are published regardless of what they show. A pooled matrix that mixes
> grids of very different quality can only have its PBO read against those
> per-grid views. This rule is fixed now, with §10's matrix defined but no
> number yet computed.

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

> **Scoped by §9 (2026-08-15).** "It" in this section is the **holdout read** —
> criterion 2 and the unseal. **Criterion 1 is dev-side and is not deferred by
> this section**; see Decision 8. A thread arriving here and stopping would
> defer a measurement that costs nothing.

## 9. Addendum — criterion 1 is separable, and what its columns are

Added **2026-08-15**, with the holdout still sealed and no P6 read performed.
**Nothing above is relaxed or restated.** This section resolves two things §3
and §8 left implicit, and which a thread picking up criterion 1 would otherwise
have to decide for itself — possibly after seeing a number.

### 9.1 The two criteria have different costs, and §8 priced them as one

§5's criterion 1 — PBO on the selection matrix — is computed **entirely on the
development set**. `cscv_pbo` consumes a weeks × configurations matrix of dev
performance; no sealed season enters it. That the instrument validation run
(`probe:deflation_instrument_validation`) is recorded against `purpose: dev`,
seasons 2010-11…2022-23, is not incidental. It is all the statistic needs.

Criterion 2 needs the holdout by construction.

§8 says "not yet", and its reasons — no pending decision turns on it, the
holdout can be spent only once — **are reasons about criterion 2**. They were
applied to the whole of P6 because the two criteria were written as one
procedure. Criterion 1 spends nothing and can be run at any time.

**Decision 8.** Criterion 1 may be computed and reported **independently of, and
before, any holdout read**. §8's "not yet" is scoped to criterion 2 and to the
unseal, not to the PBO computation.

The ordering then follows rather than being a preference: **if PBO exceeds 0.20
with `choice_mattered` true, P6 fails on criterion 1 and the holdout read is
pointless.** Running criterion 1 first can only save the holdout; it cannot cost
it.

Two accounting notes for whoever runs it:

- **It adds no configurations.** Re-scoring configurations already counted is
  the identical computation on the same data, which Decision 4 and
  `count_configurations` both treat as not spending again.
- **It still gets a ledger row**, as a probe, on the convention that recorded
  the instrument validation: every look at the dev set is recorded, including
  one that changes no decision. Reading the ledger in order to *count* is not
  such a look and needs no row.

### 9.2 What the columns are

§3 says the columns are "every distinct configuration in the selection grids".
**The ledger carries no flag for "selection grid"**, so that phrase does not
resolve to a query, and the choice would otherwise be made by whoever writes the
first one.

**Decision 9.** A configuration is a column if and only if all of:

1. it belongs to a grid from which a selection was actually made;
2. it is scored as **mean goal Poisson deviance** — the selection metric;
3. on the **common dev scoring population**: E0–E3, COVID window embargoed from
   scoring;
4. re-scored on the **final corpus** (Decision 4); and
5. it is not named in `POST_HOC_TRIALS` (Decision 5).

Conditions 2 and 3 do most of the work, and they are mechanical rather than a
matter of taste: CSCV compares columns against one another on a shared period
axis, so a configuration scored on a different metric or a different population
is not a worse column — it is **not commensurable** and cannot be one. B14, which
was measured in strike rate, is excluded by condition 2 for that reason and not
because of what it found.

Everything excluded is **reported with its count and its reason**, in the same
spirit as Decision 6.

**The risk this rule accepts, stated plainly.** A narrower, more homogeneous
column set can produce a *lower* PBO than a wider one, because a lucky in-sample
winner is likelier when the field is heterogeneous. So Decision 9 is not
obviously conservative, and "narrow the field" is exactly the shape a
rationalisation would take. Three things bound it: the rule is mechanical, it is
fixed here **before the matrix is built and before any PBO is computed**, and the
excluded set is published beside the result rather than dropped. That is a
defence, not a proof — the same standing as Decision 4's.

### 9.3 The counts in §1 are stale, as §1 predicted

Re-derived from the ledger on **2026-08-15** by `count_configurations`:

| unit | §1, as at 2026-08-06 | **as at 2026-08-15** |
| --- | --- | --- |
| ledger rows ("trials") | 76 | **103** |
| distinct questions | 41 | **60** |
| **configurations actually scored** | **149** | **197** |
| rows recording no arm list | 47 | **57** |

Post-hoc and quarantined by Decision 5: **24 configurations** across the five
named trials. By ledger kind, the configurations that recorded an arm list split
**62 sweep / 78 gate / 75 probe** — the 62 sweep configurations are the clearest
reading of "selection grids", and Decision 9 is what decides the rest.

**57 rows carry no arm list, and their configurations cannot be reconstructed
into columns at all.** That is permanent: the matrix under-represents
multiplicity by an amount no re-run recovers. Decision 6 already requires the
phrase "at least"; this is why.

This table is not authoritative either. **Re-derive again immediately before
building the matrix** — and note `count_configurations` needs
`conn.row_factory = sqlite3.Row`, per §1.

## 10. Criterion 1 executed — the column audit, fixed before the number

Added **2026-08-15**, in two stages, and the order is the point: **§10.1–10.3
were written with the matrix defined but no PBO computed**; §10.4 records the
result afterwards. The holdout is untouched throughout. Code:
`engine/eval/p6.py`, tests `tests/test_p6.py`.

### 10.1 The condition-1 sub-rule Decision 9 needed

Decision 9's condition 1 — "a grid from which a selection was actually made" —
still required a reading for gates. The reading fixed here, before computing:
**a selection was actually made iff the run's recorded detail designates a
chosen arm via a comparative selection rule** (the sweeps' `chosen` under the
1-SE rule). Gates that adjudicated a pre-registered accept/reject bar selected
nothing among alternatives — a null kept the prior default — so they are not
selection grids, and their multiplicity remains under Decision 6's "at least".
This lands exactly on §9.3's "the 62 sweep configurations are the clearest
reading of 'selection grids'".

**The most contestable exclusion under this sub-rule is
`h5_new1_ec_inclusion`**: EC-in-the-fit is a component of the served head and
the gate compared two full configurations. It is excluded because its verdict
mechanism was a pre-registered null bar, not a performance argmax — the default
would have been kept at any point estimate inside the bar. If the owner rules
the other way it adds 3 non-duplicate columns and the matrix is cheap to
rebuild; recorded here so the call is visible rather than buried in code.

### 10.2 The columns — 38, fixed

Every distinct configuration from the non-post-hoc selection grids, re-scored
on the final corpus (Decision 4), deduplicated on the bit-for-bit-identity
rule (`squad_prior` and `shots_blend` of 0.0 equal None):

- **h2_half_life, 11 columns** — H ∈ {100, 130, 160, 200, 240, 270, 300, 400,
  500, 650, 800} at α = 1.0 (the default the sweep ran at). Union of the
  pre-widening run-1 grid (rows 9) and the widened grid (rows 19, 30).
- **h3_alpha, 18 further columns** — the run-1 grid {0.25, 0.5, 1.0, 2.0, 5.0}
  at H = 300, and the widened grid {0.02, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0}
  at H = 500 (row 20) and H = 400 (row 31); the three α = 1.0 members are h2
  columns already.
- **h14_squad_prior, 4 columns** — w ∈ {0.25, 0.5, 0.75, 1.0} on the frozen
  head with the level prior rebuilt by `p2.py`'s own machinery. Selected on
  the prior-seasons subset; commensurable as columns because the λs are
  defined on the whole population and identical to the base head where no
  prior exists.
- **h20_shots_blend, 5 columns** — w ∈ {0.15, 0.3, 0.45, 0.6, 0.8} on the
  frozen head.

The base head itself is the h3 (H400, α0.1) column. The excluded set — every
armed ledger row not above, each with its configuration count and its Decision
9 condition — is printed by the run and recorded in the ledger row's detail;
headline exclusions: `h38_channel_blend` (5, condition 5),
`h19_alpha_interaction` (11, condition 5), every oracle/control (condition 1),
every product-currency gate (condition 2, B14's reasoning), and the 57
unattributed rows as Decision 6's permanent undercount.

One row needed a classification the first draft of this audit missed, and the
run's own completeness check found it before any number was computed:
**`h2_covid_guard`** (rows 12/22/33, 25 configurations) records a `chosen` arm,
so it passes the condition-1 sub-rule — its exclusion rests on **condition 3
alone**: the guard scores with 2020-21 and 2021-22 dropped, which is not the
common dev scoring population. The near-miss is worth keeping: an audit table
plus a fail-loud check caught what the table alone would not have.

### 10.3 What is reported

Primary: `cscv_pbo` on the pooled 38-column weekly matrix — §5 criterion 1,
verdict by §5/§6 as written. Companion, per §6's 2026-08-15 amendment:
per-grid PBO on the h2 (11), h3 (21), h14 (5, with base) and h20 (6, with
base) subsets of the same aligned matrix, all published regardless of outcome.
One ledger probe row (`p6_criterion1_pbo`), which by Decision 8 spends no
configurations and therefore carries no `arms` key.

### 10.4 Result — criterion 1 PASSES

Run **2026-08-15**, ledger row **104** (`probe:p6_criterion1_pbo`, written
before the number was printed). Matrix: **447 weeks × 38 columns**, aligned on
**21,896 matches** — the full common scoring population — over 12,870 splits.

**Pooled: PBO 0.000, degradation +0.005013, spread 0.027723 — informative.**
The in-sample winner lands below the out-of-sample median in none of the
12,870 splits, and sits **above** it by 0.005 nats on average. The selection
of the frozen head was not overfit; it is the α-grid validation's picture
(0.022) reproduced on the full field.

The per-grid companion (§6, as pre-declared in §10.3):

| grid | PBO | spread | reading |
| --- | --- | --- | --- |
| h2_half_life | 0.002 | 0.021730 | informative, passes |
| h3_alpha | 0.036 | 0.009673 | informative, passes |
| h20_shots_blend | 0.038 | 0.008696 | informative, passes |
| h14_squad_prior | 0.902 | **0.000018** | **uninformative** — §6's trap, arriving in the first real read |

Two things the pooled 0.000 must be read with:

- **Part of it is heterogeneity.** Columns like α = 5 or H = 100 are poor in
  every split, which depresses the out-of-sample median the winner is ranked
  against. That is exactly why §6's amendment requires the per-grid views —
  and each grid a choice was actually made within clears the bar on its own,
  at 0.038 or better. The pass does not lean on the pooling.
- **h14 at PBO 0.902 is not a failure**, and reading it as one would be the
  §6 error in mirror image: its spread is 0.000018 nats — eighteen
  *millionths* — so its five columns are indistinguishable and the 1-SE rule's
  choice of w = 0 could not have overfitted to anything. It is satisfied on
  the negligible spread, per the branch §6 fixed in advance.

**What this resolves:** half of P6 is now done, for nothing — no holdout
spent, no configuration added (104 runs / 61 questions / 197 configurations
after the row; the count did not move, per Decision 8). The excluded 140
configurations across 24 names are recorded in the row's detail with their
conditions. **Criterion 2 — the holdout read — remains sealed and governed by
§8 exactly as before**: run it when a decision turns on it, and re-read §5
first. What has changed is that the read is no longer hostage to an
uncomputed dev-side statistic: if it is ever run, it cannot be wasted on a
selection that criterion 1 would have failed.
