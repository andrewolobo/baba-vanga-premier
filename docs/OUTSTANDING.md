# Outstanding

**Cross-thread tracker.** This file is the handover point between working
sessions on this project. A thread picking up work should read this first, and
should update it before finishing. Anything not written down here does not
survive the end of a session.

Last updated **2026-08-11**, after the **linearity control** (§9.11) — which
**refuted its own test for 0 configurations**: over-shrinkage and a tail step
produce curvature only **1.46σ / 1.67σ** apart against a single measurement's
noise, so the corpus cannot decide the mechanism, and closing it would take
**1.38× the corpus — the entire holdout, clearing by 135 matches**. §3's
"flat then a step" reading is weakened on two counts and corrected in place.
**§9.7 item 4 is all that remains.**

Before that, **2026-08-11**, after measuring the separation slope's **away
leg** for the first time (§9.10) — which found it is the **larger error and the
better-resolved one** (−6.12 ✱ at 3.5σ against home's +5.66 at 2.7σ), that the
**two legs have different division profiles** so §9.6's "the slope lives in
E1–E3" is home-leg only, that **Bonferroni across the eight cells kills home
E2** — a cell `SEPARATION_SLOPE.md` §1 published as resolved — and that the
**blind sham moves the slope further than the real defect on both legs**. Gate,
**3 configurations by owner decision, 189 → 192**.

Before that, **2026-08-11**, after committing the separation slope's two
missing controls (§9.9) — which found the estimator **unbiased on both legs**,
`slope_ci`'s coverage **nominal at 4/80**, the noise ladder's **sign reproduced
and its magnitudes 2.6× smaller** than §9.6's prose, and step 2's headline
re-read as **2.77 null sd rather than ~4σ**. Probe row, 0 configurations, 189
unchanged. `SEPARATION_SLOPE.md` §2 has it.

Before that, **2026-08-11**, after a review of whether the head's
hyperparameters were tuned blind to the product (§9.8) — which found that
**every sweep already recorded `ll_1x2` on every arm**, so the counterfactual
needed no new measurement; that **three of the four named parameters have both
objectives choosing the same arm**; and that on the fourth, `H`, the **two
served markets sit on opposite sides of the deviance choice**, so re-selecting
on 1X2 trades O/U away rather than fixing an error. Nothing was measured; no
ledger row. `SELECTION_OBJECTIVE.md` has it.

Before that, **2026-08-11**, after a review of §9.6's separation slope (§9.7) —
which found that the **controls licensing it exist only as prose in this file
and cannot be re-run**, that on the home leg the effect is a **top-quintile step
rather than a gradient**, that the away leg has never had an interval at all,
and that the slope and **B13 are the same decision**. Nothing was measured;
no ledger row. `SEPARATION_SLOPE.md` has it.

Before that, **2026-08-10**, after the B12 channels gate (§1.12) — which found
that **shots and corners are worth −0.00217, about half what was predicted and
55% of their own measured ceiling**, that **corners does 90% of the work while
total shots is nearly redundant**, and that the gate's own positive control
**fired its stop rule on a bar that had been mis-derived**. The gate ran past it
by owner decision and its three rows are registered post-hoc. Read §1.12 before
treating any of it as pre-registered.

Before that, **2026-08-10**, after re-reading the closed decisions against the
tipster objective that replaced the one they were closed under (§9) — which
found that **P0-2's decisive argument is scoped to a market that is now 0% of
the product**, and that the number 85.6% of the output depends on has never been
calibration-checked.

**§9.6 then tried to fix what §9.5 found and refuted two of its own
conclusions along the way** — E0 cannot adjudicate a fix on its own data, its
defect is a level offset rather than the separation effect that drives E1–E3,
and B2's existing calibration moves one recommendation in five for **no change
in strike rate** while making E0 worse. §9.5's *verdict* stands; the
*explanation* attached to it does not, and is flagged in place. Read §9.6's
correction blocks before building on either section.

Before that, **2026-08-08**, after the deployment assessment (§4.4) — which
found that **everything customer-facing is still uncommitted**, that a public
host would publish a return through a page B7's honesty test does not cover,
and that the hero image ships a green matte fringe.

Before that, **2026-08-07**, after the customer-facing surface shipped (§1.11) —
which closed B6, put a hard no-P&L rule on the wire for B7, and turned up an API
concurrency defect that every existing test was structurally unable to see.

Before that, **2026-08-06**: the P4-channels pre-gate — which found the in-store
channels are *not* exhausted, and that FBref cannot supply xG — and a full
documentation audit (§8) that corrected four numeric defects and made the
launch-bar vig reproducible for the first time.

Companion documents, in reading order.
**For product work start at `PRODUCT.md` → `BACKLOG.md` instead** — they carry
the app's goal, the one decision blocking it, and the trackable list. The chain
below is the measurement history behind them.

`SPEC.md` (methodology authority, includes refuted parts) →
`PLAN.md` (architecture, phases, open-decision register) →
`FINDINGS.md` (what was learned, assumed → true → changed) →
`MEASURED_AND_CLOSED.md` (P0 results with numbers) →
`P1_PLAN.md` (P1 pre-registration, left unedited) →
`BASELINE.md` (P1 results and the base score) →
`P3_PLAN.md` / `CALIBRATION.md` (calibration, ablation, the launch decision) →
`P2_PLAN.md` / `PLAYER_PRIOR.md` (the player prior, and why it is descoped) →
`RUNBOOK.md` (how the thing is actually operated) →
`DEFLATION.md` (multiple-testing treatment, pre-committed before the P6 read) →
`P4_SHOTS_PLAN.md` / `SHOTS_TARGET.md` (the shots channel — the first feature that works) →
`TOD_SLOT.md` (the kickoff slot — real, and not measurable on this corpus) →
`REST.md` (days since last match — a bounded null, and where §3.6 goes next) →
`P4_TRAVEL_PLAN.md` / `TRAVEL.md` (travel — pre-registration, §8 on why the
detection statistic changed after the control and not after the result, and the
bounded null that closes SPEC §3.6) →
`P4_CHANNELS_PREGATE.md` / `CHANNELS.md` (the in-store channels — a pre-gate
that refuted two of its own three predictions, voided one of its own stop
rules, and says run the gate) →
`P4_CHANNELS_PLAN.md` / `CHANNELS_GATE.md` (the gate itself — real at −0.00217
but half the predicted size, carried almost entirely by **corners**, with §8 of
the plan recording why its stop rule fired and why it was run past anyway) →
`P5_META_PLAN.md` / `META.md` (the meta-label — pre-registration with §1
reproducible as committed code, and the result: **a market follower**, where
BOOK's apparent edge turns out to be cross-book price dispersion rather than
forecasting, and `choice_mattered` is shown to have a hole) →
`SEPARATION_SLOPE.md` (review of §9.6's λ → outcome defect — the finding
survives, its controls are not reproducible, and on the home leg it is a
top-quintile step rather than the gradient it is written up as) →
`SELECTION_OBJECTIVE.md` (review of the claim that the head was tuned blind to
the product — the counterfactual was already recorded in every sweep, three of
the four hyperparameters have both objectives choosing the same arm, and on the
fourth the two served markets pull in opposite directions) →
`DEPLOY.md` (hosting on one Azure Ubuntu VM by `git pull`: the three blockers,
what does not fit a public single-VM deployment, and the fault-tolerance
build-out `RUNBOOK.md` §8 leaves open).

---

## 0. Where the project is

| phase                | state                                                                |
| -------------------- | -------------------------------------------------------------------- |
| P0 data spine        | Complete. Loaders, holdout guard, as-of harness, team bridge.        |
| P0 dispersion        | Complete and **re-measured on the corrected corpus** — §2.1.         |
| P1 Track M           | **Complete.** Base head frozen, base score published, all gates run. |
| P1 Track A (serving) | **Built and tested; not turned on** — see §1.0.                      |
| P2 player prior      | **Complete and descoped.** Null on five arms — §1.2.                 |
| P3 calibration       | **P3-lite complete.** Calibration null/negative; book off — §1.0.    |
| P4 shots channel     | **Measured and positive** — first feature that works. §1.3.          |
| P4 TOD slot          | **Real, but not resolvable on this corpus** — §1.4.                  |
| P4 rest              | **Measured null, bounded at ~3.5%** — §1.5.                          |
| P4 travel            | **Measured null, bounded at ~3.7%/500km** — §1.6.                     |
| P4 congestion/stakes | Not started. **Both blocked**, and §1.6 closes SPEC §3.6.            |
| P4 channels          | **Gate run. Real at −0.00217; corners carries it. Not adopted.** §1.12 |
| P5 meta-label        | **Run. Market follower — do not adopt.** §1.9.                        |
| Customer surface     | **Built to the owner's design — §1.11.** B6 done, B7 part done.      |
| Hosting              | **Planned and agreed, not executed** — `DEPLOY.md`. §4.4.            |
| P6                   | Not started. Not a launch gate — `DEFLATION.md` §8.                  |

**Frozen base head:** `H400 / a0.1 / weekly / E0+E1+E2+E3+EC / sot0.3` — the
shots channel adopted 2026-08-04 (§1.3). No season-boundary shrink, no squad
prior, COVID window embargoed from scoring. Artifact
`p1-3a38e9d6ef1ca7ee` — **unchanged by §1.12**, which measured on a subclass of
the served config precisely so the version string would not move. **484 tests
pass, all green** (2026-08-11; re-run `pytest -q` rather than trusting this line
— it has been stale twice). The two calendar-time-bomb failures found earlier
on 2026-08-10 are fixed — §6. Gate ledger holds
**101 runs / 58 questions / at least 192 configurations** — the last is the
number that feeds deflation, and §3.2 explains why the other two mislead.
§9.5 spent 4, §9.6 spent 6 (its step 1 probe spent none), §1.12 spent 13,
**§9.9 spent none** — a probe on synthetic outcomes, which is why runs and
questions moved and configurations did not — **§9.10 spent 3 by owner
decision**, where `SEPARATION_SLOPE.md` §8 had named 0 or 1, and **§9.11 spent
none**, another synthetic-outcome probe.

**Three of §1.12's four rows are post-hoc** and are named in
`trials.POST_HOC_TRIALS` alongside `h19_alpha_interaction` and
`p5_book_no_arb`. `count_configurations` reports them, so a future P6 read gets
the warning without needing this paragraph — but the *reason* is only here and
in `CHANNELS_GATE.md` §2: the gate's positive control missed a mis-derived bar,
its stop rule fired, and it was run past by owner decision with real outcomes
already in view.
**The 87 / 45 / 167 this line used to carry did not reproduce**: re-derived
immediately before §9.5 the true figure was 90 / 47 / **166**, so the run count
was three low and the configuration count one high. §4.4 already quoted 90 rows
against §0's 87 and the disagreement was not chased. §9.5 then added exactly the
4 it declared. **The audit in §8 added
no ledger rows**: `engine.odds.vig_per_leg` reads prices only, so it spends no
information about any outcome, on the same accounting as `power.py`.

**The P5 rows (§1.9) split three ways on this accounting.** `p5_grounding` (×3)
reads prices and λ coverage only and `p5_control` (×3) runs on synthetic
targets, so **neither moves the configuration count** — the same rule as
`power.py` and `travel.py`'s `h34_travel_power`. Nothing in
`engine/eval/meta.py` reads a match outcome at any stage, and `drop_outcomes`
makes that a property of the data rather than a claim about the code.
`p5_meta_arms` (×4) **does** spend: 16 by the mechanical count, against §5's
declared budget of 12. The four runs are byte-identical in every arm result, so
4 configurations were chosen among; `META.md` §9 records both numbers and why.
`p5_book_no_arb` (×1) adds 2 and is **post-hoc** — `count_configurations` names
it. `meta.py` now has a `--dry-run` flag so development costs no rows; use it.

**The configuration count did not move for §1.7**, for the same reason it did
not move for the travel controls: a probe carrying no arm list is a row that
spends no information about a real answer. Note `count_configurations` needs
`conn.row_factory = sqlite3.Row` and dies with an opaque `ValueError` without
it — worth knowing, since this file tells you to call it.

Eight of those runs are §1.5, which was run twice: once before and once after a
correctness fix to how rest is computed. Both are recorded, per §7.5 — a trial
spends against the development set whether or not its result was superseded.

**Two of them are §1.6**, which was also run twice: once on the detection
statistic the plan pre-registered and once on the one that replaced it. Both
stand, for the same reason. Note the configuration count did **not** move —
both runs are planted controls on synthetic outcomes, which spend no
information about a real answer, and `count_configurations` reads them as rows
carrying no arm list.

**The count this file used to carry (52 / 24 / 133) was already stale when it
was written.** It predates the seven rows the shots channel itself added, so
§0 quoted a ledger state older than the result on the same page; §1.4 then
added four more. Re-derive it with `trials.count_configurations(conn)` instead
of trusting the prose — the figures above are that call's output, and it is the
only way this number should ever be quoted.

---

## 1. Blocking / do first

### 1.0 The book stays off at launch — decided, with numbers

**Resolved 2026-08-03 by P3-lite.** Full results in `CALIBRATION.md`.

The flat-EV rule was backtested three ways (uncalibrated, calibrated, blended)
against the de-vigged close, at both average and best-available prices. **No
stratum is profitable at either price level.** The market ablation (H12) found
the model's weight given the price is small, inconsistent in sign, and negative
in five of eight cells; the blend never beats the market in any division on
either market.

Three things worth carrying forward:

- **The pre-registered bar was wrong.** "CLV ≥ 0 with CI excluding zero" passed
  two strata that lose 7.6% and 10.0%. CLV must exceed the **vig**, not zero.
- **Positive CLV at average prices was an artifact** of comparing a wide-margin
  consensus against a sharp close. Re-priced like-for-like at Max, CLV is zero.
- **Vig is the binding constraint on any future edge.** At average prices a
  strategy needs 8x the current signal to break even; at best-available, ~1x.
  Best-price capture is a prerequisite, not an optimisation.

**Ships regardless:** fixture sync, predictions, CLV grading, API, frontend.
Opening-weekend prediction data is irrecoverable and the CLV series is the
instrument that detects a real edge if one appears.

**Do not** re-litigate with more calibration, blending or thresholds. All
measured, all null or negative, all in the ledger (45 trials).

### 1.1 The entire P1 workstream is uncommitted

**Resolved 2026-08-03** — P1 committed as `244ca18`. Track A **and P2** are now
the uncommitted work: `db/migrations/002_serving.sql`, `services/`, `api/`,
`web/`, `engine/serve/{cycle,book}.py`, `engine/models/{calibration,squad}.py`,
`engine/eval/{p2,p3}.py`, `docs/{P2_PLAN,P3_PLAN,PLAYER_PRIOR,CALIBRATION}.md`
and six new test modules.

### 1.2 The player prior is descoped — decided, with numbers

**Resolved 2026-08-03 by P2.** Full results in `PLAYER_PRIOR.md`.

Five arms, all null on goal deviance: the SPEC §3.3 weight sweep spans 0.00002
nats and the 1-SE rule selects weight 0; every channel set matches a control
prior containing **no player data at all** to five decimal places; the
division-change population moves +0.00045 [−0.00036, +0.00123].

Three things worth carrying forward:

- **There is no cold start to fix.** Minimum decayed evidence behind any scored
  club is **25.8 effective matches**, median 65.2. SPEC §3.3 imported a doctrine
  about clubs decayed to ~1% weight; that population does not exist here,
  **because P1's NEW-1 joint fit already removed it.**
- **The 0.058 nats that motivated P2 was never the player layer's.** It is the
  value of lower-division match history (`BASELINE.md` §3), and P1 banked it.
- **α and the ridge target are coupled and were tuned as if they were not.** A
  *perfect* prior is worth −0.00018 at α=0.1 but −0.00694 at α=5. P1 swept α
  with the target pinned at zero. The follow-up was run (H19): no legal prior
  beats the frozen head at any α, and α=0.1 now survives a test it had not
  previously faced.

**Do not** re-litigate with a per-player ratings model, an age curve, market
values, or more channels. The constraint is that the N−1 roster *is* the club
(0.980 collinear) and that season N's squad is unknowable as-of. Only **dated
transfer data** would change it — `data/transfer-history/` is empty.

### 1.3 The shots channel works — **ADOPTED 2026-08-04**

**Measured and shipped 2026-08-04.** Results in `SHOTS_TARGET.md`,
pre-registration in `P4_SHOTS_PLAN.md`. **Six of seven predictions right.**

A second Poisson fit on shots-on-target, blended into the goal-fitted strengths
at `w = 0.3`, improves goal deviance by **−0.00422** [−0.00535, −0.00307] —
7.3 paired SE, interior optimum, uncensored grid. Negative in all four served
divisions with every interval excluding zero. 1X2 −0.00179, O/U −0.00140.

**Everything that had to move, moved:**

- head `H400/a0.1/weekly/E0+E1+E2+E3+EC/**sot0.3**`, artifact
  **`p1-3a38e9d6ef1ca7ee`** (`p1-36d44c72db18b384` retired)
- `BASELINE.md` §1–2 re-issued by the same `h9_baseline` code; **H9 still holds**
- pooled deficit **+0.01419 [+0.01239, +0.01609] → +0.01230 [+0.01041, +0.01419]**
- `DEFLATION.md` §5 criterion 2 restated against the new interval, holdout still
  sealed, reason recorded — a restatement, not a relaxation
- share of market edge: E0 0.89→**0.909**, E1 0.62→**0.654**, E2 0.64→**0.674**,
  E3 0.51→**0.598**

`p2.py`, `p3.py` and `p4_shots.py` pin the head as it stood when they ran, so
they still reproduce their own documents. **Serving moves forward; history does
not.** Any future head change must do the same five things or the documents
drift out of agreement with the code.

Three things worth carrying forward:

- **It does not turn the book on.** Deficit +0.01230 against a vig of 0.02122.
  Still behind the market in every division. `CALIBRATION.md` §5 stands.
- **The positive control failed first, and it was my error.** The oracle was
  built from goals scored alone, so its `dfn` had nothing to fit; attack
  improved and defence was destroyed and the two cancelled. Rebuilt two-sided,
  it passed at −0.01636. The stop condition held — no other arm ran until it did.
- **The coefficient diagnostic contradicted the pre-gate** and would have killed
  a feature that works. Raw within-season team rates and opponent-adjusted
  decayed coefficients measure different things; the blend helps because it
  combines two imperfect estimates rather than replacing one.

### 1.4 The kickoff slot is real and not measurable — **MEASURED 2026-08-04**

Results in `TOD_SLOT.md`, code `engine/eval/tod.py`, ledger `h26`–`h29`.
Answers SPEC §3.6. **This is not a null, and the difference is the finding.**

A slot effect survives the residual test the SPEC asked for, and survives a
control gtleague did not have — the frozen head's opponent-adjusted λ.
Permutation p **0.0020** with labels shuffled within season. `sun_late` clears a
Bonferroni-corrected interval at **+0.426 [+0.087, +0.770]**, holds its sign in
all three seasons and all four divisions, and the market **misses it in the same
direction** (+0.094 [+0.020, +0.176]).

It is then worth **−0.00067 [−0.00216, +0.00079]** on goal deviance — and H29
shows the instrument recovers a planted effect of exactly that size in **2 draws
out of 6**. The interval is underpowered, not empty.

Three things worth carrying forward:

- **`Time` does not exist before 2019-20.** After the holdout and the COVID
  embargo that leaves **5,644 of 21,896 scored matches — 2.6 seasons.** This
  limits *measurement only*; every future fixture has a kickoff time, so the
  feature would apply to 100% of served matches if it were ever built.
- **No amount of holdout spending answers it.** Reaching 1.96 SE needs ≈28,400
  matches, 5× the corpus, about ten further seasons. Unsealing **all three**
  sealed seasons reaches 1.3 SE. The most expensive act available to this
  project does not buy the answer, which is worth knowing before someone
  proposes it.
- **Nine levels fitted to noise cost +0.00112 nats**, measured on the planted
  ×0 arm. The −0.00067 point estimate is consistent with a small real effect
  roughly cancelling that overfit cost, which is a second and independent
  reason not to read the sign.

**Do not** re-litigate with finer time buckets, per-division slot terms, or
interactions with team strength — every one of those spends *more* degrees of
freedom on a corpus that cannot afford the nine already tried. If it is ever
revisited the only defensible arm is the two-level contrast, pre-registered
before looking; `TOD_SLOT.md` §8 explains why that still does not reach 2 SE.

**This closes the slot, not SPEC §3.6.** The SPEC asked for the slot to be
*replaced* by rest days, congestion, travel and stakes — and **only the slot is
limited to 2019-20**. Rest and congestion come from `match_date`, so they run on
**21,896 scored matches, 3.9× this sample** (median rest 7 days, p10 3, p90 13),
and cost no new data. Travel is blocked on a stadium coordinate table, stakes on
OPEN-4. `TOD_SLOT.md` §9 has the arithmetic. **That is where §3.6 resumes** —
the constraint that killed the slot does not apply to the features the SPEC
actually preferred.

### 1.5 Rest is a measured null, and it is bounded — **MEASURED 2026-08-04**

Results in `REST.md`, code `engine/eval/rest.py`, ledger `h30`–`h33`. The first
of SPEC §3.6's replacement analogues, picked up from `TOD_SLOT.md` §9.

**Unlike the kickoff slot, this corpus could answer the question.** Rest comes
from `match_date`, so the arm runs on **21,425 matches / 42,850 match-sides**
across eleven seasons rather than 5,644.

Neither form of the feature works. Six rest bands cost **+0.00017 [+0.00000,
+0.00035]** on goal deviance, and the differential the SPEC actually asked for
is flat at **r = −0.0040, p = 0.562** and costs +0.00003 as a fitted slope.
H33 catches a planted 5% attacking deficit **6 times out of 6** and puts the
resolution threshold near **3.5%**.

Three things worth carrying forward:

- **The null has a size attached.** Fitting six bands to data with no rest
  effect by construction costs +0.00020; the real corpus returned +0.00017. The
  measurement is not "not significant", it is the number the arm produces when
  the effect does not exist. **Any true rest effect on scoring is below ~3.5%
  of a goal rate.**
- **The corpus is league-only, and that is the standing limitation.** No FA Cup,
  League Cup or European ties, so measured rest is an *upper bound* on true
  rest. All ten dates contributing the most long gaps are FIFA windows or FA Cup
  third-round weekends; long gaps are 20.9% of match-sides in November against
  0.3% in August. A congestion effect driven by midweek European football is not
  refuted here — it is unmeasurable, because those matches are not in the data.
- **The one apparent signal was multiplicity.** Conceding on ≤3 days' rest
  cleared an uncorrected interval, in the wrong direction (tired teams conceding
  *fewer*), and vanished under Bonferroni across the twelve cells tested. Worth
  recording because it is exactly the shape a false positive takes.

**Do not** re-litigate with finer bands, per-division rest terms, or a rest ×
strength interaction. The differential is the form the SPEC preferred, it was
measured on one parameter, and it is flat.

**Travel distance is the best remaining §3.6 candidate.** Congestion inherits
the same league-only hole and inherits it *worse* — it is precisely a count of
the midweek ties the corpus lacks — and stakes is blocked on OPEN-4. Travel
needs one static table of stadium coordinates, applies to every match in the
corpus, and its confounds are the kind λ already absorbs. `REST.md` §7 has the
comparison. **The "~92 clubs" this paragraph used to quote was wrong** — 92 is
the size of the Premier League plus EFL at one instant, not the club universe
of a sixteen-season corpus. Measured against `teams`: **151 clubs, 108 of them
in E0–E3.** The table is built (§1.6).

### 1.6 Travel is a measured null, bounded at ~3.7% per 500 km — **MEASURED 2026-08-06**

Results in `TRAVEL.md`, pre-registration `P4_TRAVEL_PLAN.md`, code
`engine/eval/travel.py`, retriever `services/stadium_coords/`, ledger
`h34_travel_power` (×2) and `h36_travel_arms`. **Do not adopt.**

Score coefficient **β = −0.0147, t = 0.98** — not resolved. A1 (one slope)
**+0.00008 [−0.00010, +0.00026]** on goal deviance, negative in **1 of 4**
divisions against a §7 bar of 3. A2 (five bands) +0.00007. The point estimate
is in the predicted direction at 1.47% per 500 km — 0.51% at the median trip —
and **40% of the resolution threshold**. Resolving an effect that size needs
**4.0× this corpus (~86,800 matches, ~43 seasons)**; unsealing all three
holdout seasons moves t from 0.98 to **1.15**, so the most expensive act
available does not buy it.

**A1 also makes the served O/U market measurably worse** — +0.00018
[+0.00008, +0.00029] — while goal deviance is flat. Recorded per convention 2;
it does not change a decision that was already against adoption.

`reference/stadiums.csv` holds **151 of 151 clubs, every one verified** against
an independent geocode — Wikidata `P115`/`P625` as the source, LocationIQ as the
check, nothing recalled. 100% coverage of all 33,158 dev match-sides.

**The feature is identified, which was the thing worth checking first.** After
removing both home and away club fixed effects, **70% of the variance in
away-trip distance survives** (sd 85.6 km of 102.3). λ's club coefficients do
not absorb it. Median trip 176 km, p10 53, p90 321, max 537.

Four things worth carrying forward:

- **The pre-registered detection statistic was the wrong one, and the control
  is what caught it.** The deviance delta recovered a planted 5%-at-500km
  deficit **0 times in 6**; a Poisson score coefficient test on the identical
  frames recovered it **5 of 6** at t = 2.68 with **0/6 false positives** at
  zero. Thresholds 13.5% against **3.7%** — 3.6× on the same data. The
  amendment and its reasoning are `P4_TRAVEL_PLAN.md` §8.
- **Amending after a control is not the thing `CALIBRATION.md` §1 forbids.**
  That bar moved after seeing *real* results. This one moved after seeing
  Poisson-resampled synthetic outcomes carrying no information about the real
  answer — which is the whole reason the control is specified to run first and
  alone. The distinction is which numbers were in view, and it is the reason
  the plan says the control runs before anything else.
- **Adoption still runs on goal Poisson deviance.** Convention 2 is untouched.
  The coefficient test answers "can the corpus see an effect this size"; it
  never decides whether a feature goes in the head. Both are reported for every
  arm, and the gap between them is itself a finding — real-but-not-adoptable is
  exactly the §1.4 shape.
- **Resolution: 3.7% at 500 km, ~1.3% at the median trip.** That is what the
  real arms will be able to say something about, and it is the number any null
  from them must be reported against.

**§1.4 and §1.5 have been re-evaluated under the new statistic — both stand.**
`engine/eval/power.py`, ledger `h35_power_revisit`. It reads **no match
outcomes** — Fisher information for a Poisson rate is `Σλx²`, which needs only
the fitted λs — so closed gates were re-examined without being reopened, no
information was spent, and the configuration count is unchanged.

| gate | stated bound | score test says | verdict |
| ---- | ------------ | --------------- | ------- |
| §1.5 rest, differential | ~3.5% | **3.99%** over a 7-day gap | stands |
| §1.5 rest, ≤3 vs 7-day band | ~3.5% | **2.28%** | mildly conservative |
| §1.4 slot, `sun_late` +0.18 | 2/6 detected | **t = 4.14** | see below |

**Rest is confirmed, and the interesting half is that it barely moved.** The
form the SPEC preferred — one parameter on the differential — resolves 3.99%,
against the 3.5% `REST.md` claimed. The band contrast is tighter at 2.28%, so
the null is if anything slightly stronger than published, and nothing in §1.5
needs rewriting.

**The slot needs a distinction it already drew, and this sharpens it.** Under
the score test `sun_late` is a **4.1σ** effect and `sat_late` 2.5σ, so the
*reality* of the slot was never the underpowered part — `TOD_SLOT.md` had
already established that by permutation at p = 0.0020. What H29 found
unresolvable at 2/6 was its **worth on goal deviance**, and that is unchanged:
the deviance value is the adoption question, and it still needs ≈28,400 matches.
The re-evaluation adds a second, independent reason the nine-level arm was the
wrong instrument — **five of the nine slots resolve only 7.6–12%**
(`mon_eve` 11.95%, `sat_late` 11.16%, `fri_eve` 10.14%), so most of the
degrees of freedom were being spent where nothing could be seen. `holiday_15`
at +0.06 sits below 1.96 either way.

**This is the real-but-not-adoptable shape, and it now has two statistics
saying so rather than one.** Do not read it as a reason to revisit §1.4's
closure.

### 1.7 The in-store channels are not exhausted — **PRE-GATE RUN 2026-08-06**

Results in `CHANNELS.md`, pre-registration `P4_CHANNELS_PREGATE.md`, code
`engine/eval/channels.py`, ledger `p4_channels_pregate` (row 76). **A gate is
licensed. It is not written, and nothing is adopted.**

Leave-one-season-out split-half reliability over 1,103 team-seasons, gain over
the shipped `goals+sot`, as (attack, defence):

| added channel | attack | defence |
| ------------- | ------ | ------- |
| shots | +0.0293 | +0.0424 |
| corners | +0.0342 | +0.0340 |
| **shots + corners** | **+0.0490** | **+0.0540** |
| NOISE (negative control) | −0.0008 | +0.0000 |

Row 53 measured adding *sot to goals* at +0.039/+0.060, and that became −0.00422
nats and shipped. The two unused in-store channels are the same order of
magnitude, and they are complementary rather than redundant.

Four things worth carrying forward:

- **A positive result needs a planted negative, exactly as a null needs a
  planted positive.** Adding any predictor raises in-sample multiple R, and
  leave-one-season-out bounds that without proving it zero. The noise channel
  gains −0.0008. Without it, §1.7 would be an artifact claim. Convention 8
  should be read as covering both directions.
- **Corners was struck from the candidate list on the wrong statistic.**
  Per-match correlation with same-side goals is 0.021 and reads as a dud; at
  team-season level, which is the only level the strength layer sees, it is
  **+0.418**. It then turned out to be the best single addition on attack.
- **A coefficient diagnostic gave the wrong answer about this feature for the
  second time.** M5's pre-registered 0.95 collinearity veto fires on
  `goals ~ sot` at 0.9712 — the adopted channel. `SHOTS_TARGET.md` §4 recorded
  the first instance and the lesson did not transfer, because it was written as
  a note about one diagnostic rather than a rule about the class.
  **Reliability on held-out matches has been right both times.**
- **The per-side blend weight is unidentified, and identifying it costs 2
  configurations, not 36.** H20 + H21 give five constraints for six quadratic
  parameters; the free one is the curvature split between att and dfn. One
  att-only arm at a second weight pins it. A 6x6 grid would be a quarter of the
  ledger for a question one arm answers.

**Do not** read this as a result about the head. Split-half reliability is not
deviance, `SHOTS_TARGET.md` §7 already records over-estimating that mapping
once, and no arm has been run. It also does not touch the book — §2.3 stands.

**Row 53 is not reproducible, and that is a standing defect.** The pre-gate
behind `SHOTS_TARGET.md` §1 was never committed; `p4_shots.py` holds only
H20/H21/H22/H25 and nothing in `engine/` computes split-half reliability. M4 is
a rebuild, and it **disagrees with row 53 on the comparison that motivated the
shots channel** — row 53 put sot above goals on attack (0.446 vs 0.441), this
harness puts goals well above sot (0.528 vs 0.394). Unresolvable without the
lost code. It does not unsettle the shots channel, which was established by
H20's gate rather than by the pre-gate, but only the within-run contrasts and
the noise control carry weight in `CHANNELS.md` §1.

### 1.12 The channels gate is real, half-sized, and it is corners — **MEASURED 2026-08-10**

Results in `CHANNELS_GATE.md`, pre-registration `P4_CHANNELS_PLAN.md`, code
`engine/eval/channels_gate.py`, tests `tests/test_channel_blend.py`, ledger
`h37_channels_oracle_control` (probe, 2), `h38_channel_blend` (5),
`h39_channel_decomposition` (6), `h40_channels_divisions` (0). **13
configurations, exactly as declared; 176 → 189.** The gate §1.7 licensed.
**Nothing is adopted.**

Against the shipped head, at the selected w = 0.30, on 21,896 matches:

| arm | vs shipped | paired SE |
| --- | --- | --- |
| `+shots` | −0.00095 [−0.00143, −0.00048] | 4.0 |
| **`+corners`** | **−0.00196** [−0.00276, −0.00116] | 4.7 |
| **`+both`** | **−0.00217** [−0.00285, −0.00146] | 6.0 |
| `+noise ×2` (control) | **+0.02101** [+0.01811, +0.02387] | 14.6 |
| oracle ceiling | −0.00396 [−0.00477, −0.00320] | 9.9 |

**Five of thirteen predictions right, and all eight misses are over-optimistic
in the same direction.**

Five things worth carrying forward:

- **The stop rule fired on a mis-derived bar, and continuing cost the gate its
  pre-registration.** H37's bar of ≤ −0.008 was copied from H25's sot oracle
  without adjusting for H25 running at **w = 0.6** against a **goals-only**
  baseline where H37 runs at **w = 0.3** against a baseline that already carries
  real sot. At −0.00396 and 9.9 SE the instrument was plainly alive, so the
  rule fired for a condition it was not written to detect — but the decision to
  continue was taken with **real outcomes in view**, which is §1.6's line, so
  `h38`/`h39`/`h40` are in `trials.POST_HOC_TRIALS`. The override is a
  command-line flag, `--past-failed-control`, rather than a relaxed threshold,
  so continuing past a stop rule is a recorded act.
- **Reliability was over-read as deviance for the third time, and the bound was
  available for 2 configurations.** `SHOTS_TARGET.md` §7 recorded it,
  `CHANNELS.md` §6 warned about it explicitly, and `P4_CHANNELS_PLAN.md` §1 did
  it again — extrapolating +0.0490/+0.0540 to −0.012 and discounting only to
  −0.008 against a measured answer of −0.00217. **The fix is not another
  caution.** Run the oracle first and read every prediction against the ceiling
  it produces; here that would have refuted the headline prediction before any
  real arm ran, which is exactly what it did once the order was forced.
- **`CHANNELS.md` §1's "complementary, not redundant" does not survive the
  translation to deviance.** Corners is worth **2.1×** shots, and adding shots
  on top of corners is worth −0.00021 — smaller than the paired SE of either
  arm. `goals + sot + corners` captures **90%** of the gain with one fewer
  channel and is the version to consider if the head is ever changed. Note the
  paired comparison between `+corners` and `+both` was **not** run, so that is a
  point estimate, not a measured null.
- **E3 does not resolve** — −0.00088 [−0.00208, +0.00030] — breaking both the
  "all four divisions" prediction and the 3× spread bar (3.23×). It is also the
  division where the head captures least of the market's edge, so the division
  with the most room gains least. §3.1's asymmetry gets a fourth measurement
  and no explanation.
- **The served head did not move, by construction.** The k-channel blend is
  carried on a `ChannelBlendConfig` subclass because `artifact.freeze` hashes
  `cfg.__dict__`, so a defaulted field on the served config would have retired
  `p1-3a38e9d6ef1ca7ee` with no coefficient change — the thing `0c9eb06`
  declined to do. Verified bit-for-bit against the pre-change module over all
  27,815 walk-forward λs, and the `sot @ 0.3` arm reproduces the shipped head at
  **exactly +0.00000** in the gate's own output.

**Do not** re-litigate with per-channel weights, a per-side weight, fouls or
cards, or a joint α sweep. The ceiling is −0.00396 and the arm reached 55% of
it; the remaining headroom in this mechanism is under two thousandths of a nat,
and `P4_CHANNELS_PLAN.md` §7 records what was held fixed.

**It does not touch the book.** Pooled deficit +0.01230 → +0.01177, 4.3% of a
gap whose vig is 0.02122 at average prices. `CALIBRATION.md` §5 stands.

**Adoption is open and is the owner's.** It costs the five steps of §1.3,
including re-running `engine/eval/tips.py`'s claims block, because the published
strike rate is a property of the head rather than of the rule.

### 1.10 The product is a strike-rate tipster — **DECIDED AND WIRED 2026-08-06**

Owner decision, taken after §1.9 closed the model-picks-bets path. The product
is sold on **strike rate**, not on return. Code `engine/serve/tips.py` (the
rule), `engine/eval/tips.py` (what it delivers), migration `003_tips.sql`,
`step_tips` in `services/run_cycle.py`, ledger `tips_confidence_rule`
(5 configurations — the threshold grid; this reads outcomes and spends).

The cycle is now **sync → serve → tips → grade**. Shipped threshold 0.55.

| threshold | tips/week | claimed | **actual strike** | ROI @ avg prices |
| --- | --- | --- | --- | --- |
| 0.55 | 7.9 | 62.7% | **65.5%** | −0.75% [−3.17, +1.72] |
| 0.60 | 4.2 | 67.7% | **70.5%** | −1.29% [−4.50, +1.73] |
| 0.70 | 1.3 | 76.1% | **82.0%** | +3.03% [−0.87, +6.89] |

Four things worth carrying forward:

- **The strike rate is honest and the return is not, and the code says so.**
  `engine/eval/tips.py` ends with a claims block printing which of three
  statements are supported: strike rate HONEST, return NOT SUPPORTED, model
  beats market favourite NOT SUPPORTED. **Re-run it after any head change** —
  the numbers above are properties of the frozen head, not of the rule.
- **The model is not producing the strike rate.** At every sellable threshold
  it names the market favourite and the paired difference against simply
  backing that favourite is **~0.00%**. What it genuinely adds is that it can
  rank a fixture *before a price exists*, which the market favourite cannot.
- **The head is under-confident on its own favourites**, in every bucket, by up
  to 5.9 points (claims 76.1%, delivers 82.0% ± 3.3). So the advertised number
  is conservative. This is a real property of an independent-Poisson 1X2 fit
  and is worth remembering before anyone "fixes" calibration.
- **`step_grade` used to short-circuit on `paper_bets` alone.** The book is off,
  so there are never unsettled bets, so the step returned early — which was
  correct until tips shipped and would then have left every tip ungraded
  forever while the cycle reported success. The pending query now unions both
  tables. **This is the shape to watch for whenever a second thing needs
  settling.**

**An earlier number in this thread was wrong and is corrected here.** The
customer loss was quoted at ~2% per bet at best prices and ~5% at typical ones.
Those were the *model's own* expected values and the all-matches figure. Because
the head is under-confident, realised losses at the tipping thresholds are
around **1%**, and no interval excludes zero.

**The customer-facing surface was built 2026-08-07 — §1.11.** It publishes no
P&L, by construction rather than by convention, and a test fails if any profit
field reaches the wire. Still not built: any check that the *published* strike
rate agrees with the out-of-sample one `engine/eval/tips.py` measures. The
regulatory exposure of advertising a 65% strike rate alongside a product that
does not measurably profit is **the owner's, and is recorded as flagged**.

**Product scope is now larger than what is served, and it is blocked on one
decision.** `PRODUCT.md` records the goal — one recommendation per match from a
menu of 1X2, double chance and goal lines 0.5–5.5 — and `BACKLOG.md` tracks the
work. Every probability on that menu is already computable; **the blocker is
that "likeliest" is degenerate.** Measured on 19,884 matches, recommending the
menu maximum says *under 5.5* in 74.2% of matches and *over 0.5* in the other
25.8%, and **nothing else, ever**. A second criterion has to be chosen — a
probability ceiling, a price floor, or a fixed preference order — and it is an
owner decision (`BACKLOG.md` B0). Double chance and the extra goal lines are
special cases of it and cannot be specified until it is settled.

**A second constraint worth knowing before planning:** the schema carries prices
for 1X2 and Over/Under **2.5 only**. On the other five goal lines the app can
predict but cannot measure itself — no return, no CLV, no market comparison.
Survivable for a strike-rate product, and it is also the one place identified so
far where the model beats reading the odds, because it can rank a line before a
price exists.

### 1.11 The customer surface is built — **SHIPPED 2026-08-07**

B6 closed. Code `api/main.py` (`/tips`, `/tips/results`, `/tips/record`) and
`web/`, rebuilt to the owner's design at `docs/ui/Baba Vanga.dc.html`.
`BACKLOG.md` B6/B7 has the full account of what the design asked for and could
not be supported. No ledger row: nothing here reads a match outcome to make a
decision, it only displays what the cycle already stored.

Four things worth carrying forward:

- **The API was broken for any page that fetched two endpoints at once, and no
  test could see it.** FastAPI runs a sync generator dependency's setup, the
  endpoint body and its teardown as three separate threadpool hand-offs, which
  need not land on the same worker — so `get_conn`'s connection was created on
  one thread and used on another, and sqlite3 refused it. It survived because
  the old frontend fetched **one endpoint per page**: serialised requests reuse
  a single worker and the hand-off never crosses threads. **`TestClient` also
  reuses one worker**, so the whole existing suite passed against a live API
  that 500s on every load. Fixed with `check_same_thread=False`, scoped to
  `api.main` alone via a new kwarg on `db.connect`; the guard stays on for the
  cycle, the grader and the gates, where a connection crossing threads is a real
  bug. The regression test asserts the kwarg at the call site, because asserting
  it through the app is exactly what does not work.
- **A design mockup is a claim about the data, and this one made four the
  project has refuted.** Level-stakes profit, a green-week streak, a "model
  edge" percentage and a bet slip — all of them `book.py`'s value rule or a
  return, both measured negative. They were dropped rather than filled with
  something plausible. The same file also listed the wrong four divisions and
  promised "no hedging" from a rule that hedges in 85.6% of matches. **Read a
  design against `PRODUCT.md` before building it.**
- **The tipster vocabulary problem is real and is now solved in one place.**
  `tips.side` is `12`/`1X`/`X2` in most matches and `recommend()` can never emit
  `D`. `web/src/lib/api.js:callLabel` is the single mapping to words; anything
  else rendering a tip must use it, or the site and the graded record will say
  different things about the same match.
- **FT scores of graded fixtures are stored nowhere.** `002_serving.sql` says
  the grader "writes the result into `matches` and links back by fixture_id" —
  it does not, and `matches` has no `fixture_id` column. `csv_grader.grade`
  settles from the result and discards the goals. So the result cards show
  outcome only. Anything wanting scorelines needs a migration and a grader
  change first; this is a **documentation defect in the migration**, not just a
  missing feature.

### 1.9 The meta-label is a market follower — **MEASURED 2026-08-06**

Results in `META.md`, pre-registration `P5_META_PLAN.md`, code
`engine/eval/meta.py`, ledger `p5_grounding` / `p5_control` / `p5_meta_arms`.
**Do not adopt.** §6's second branch, and §7's expected finding.

On 46,149 out-of-sample legs, top-10% weekly selection: **BOOK +0.00762**
(3.8× the Max vig), MODEL +0.00061, FULL +0.00744, NOISE +0.00759.
**MODEL − BOOK = −0.00702 [−0.00803, −0.00599]**, wrong sign in **4 of 4**
divisions. The football model adds nothing given the price — and it was handed
`edge = m_prob − 1/Max` by §4's own feature list, so it had a price and still
lost by 0.007. NOISE gains −0.00003 over BOOK, so this is not the instrument
inflating. **Four of five §7 predictions right.**

Four things worth carrying forward:

- **BOOK's edge is price dispersion, not forecasting, and the profile says so.**
  **65.3% of its selected legs come from matches whose best-available 1X2 book
  sums to under 1**, against 23.7% in the pool. Backing every leg of one of
  those is a profit before any forecast. Its top coefficient is `max_spread`,
  not `sharp_spread`. This is best-price capture — `CALIBRATION.md` §5's
  *prerequisite* arriving as a *result* — and `P5_META_PLAN.md` §8's exclusion
  of execution and limits is doing far more work than it was written to do. **Do
  not read "+0.00762 clears the vig" as an edge that could be traded.**
- **It survives with those matches removed, and that is POST-HOC.** `META.md` §8,
  ledger `p5_book_no_arb`, registered in `trials.POST_HOC_TRIALS`. Dropping every
  sub-1-overround match from training and scoring keeps 76.3% of legs and moves
  the pinned mean to −0.00318, a *harder* bar. BOOK still returns **+0.00397**,
  **+0.00196 [+0.00115, +0.00276] above the vig**, clearing in **all four
  divisions**, against a BLIND control at −0.00223. So there is something beyond
  arbitrage. **But the mechanism barely moved** — `max_spread` is still the top
  coefficient and BOOK's picks still carry a 29% wider best-price spread than the
  pool. The edge halved and stayed execution-dependent. **The next question is
  not a modelling one:** can the outlier price be taken at stake? `RUNBOOK.md`
  does not capture Max at bet time, so nothing here can answer it.
  **`NOISE` was the wrong control for that question and `BLIND` is the right
  one** — NOISE contains every BOOK feature, so it tests dimensionality; BLIND
  has no price information and shows the harness is not manufacturing edge.
- **`choice_mattered` has a hole, and this is the first gate to expose it.**
  `DEFLATION.md` §6 guards against reading PBO ≈ 0.5 as overfitting when arms
  are interchangeable. Its test is the spread across *all* trials, so **one
  clearly losing arm makes the field look separable** while the arms that could
  actually be chosen are not: PBO 0.631 on all four, but 0.863 at spread
  0.000149 on {BOOK, FULL, NOISE} — which the tool itself flags uninformative —
  and **0.000 on {BOOK, MODEL}**, the only comparison that decides anything.
  §6's criterion 4 fails literally and passes on the comparison it was for.
  **Fix this in `DEFLATION.md` §6, not here.**
- **A seed collision nearly inverted the positive control.** The reference arm's
  random prediction and the synthetic target were both standard normals of the
  same length from colliding seeds, making the reference an exact oracle on one
  draw. The only symptom was a control reporting 5/6 recovered *and* a negative
  mean lift — incoherent, but invisible in either number alone. Per-draw lifts
  are now recorded. **Report a control's spread, not just its count.**
- **BOOK is one price level plus spreads, and that was forced by the data.** The
  four bookmakers' break-even probabilities correlate at 0.997–0.999; a design
  matrix of the levels has condition number **2×10¹⁵**, singular to working
  precision. Reparameterised, 2.8. Chosen on conditioning before any target was
  fitted, and it is the difference between a fit and arithmetic noise.

**Budget: §5 declared ≤12 configurations; the mechanical count is 16**, because
the gate wrote a ledger row on each of four implementation runs. The arm results
are **byte-identical across all four**, so 4 configurations were chosen among
and 16 rows record it. `META.md` §8 puts both numbers on the record; the choice
is the owner's. The process fix is to write to a scratch path until the code is
final.

**Do not** re-litigate with more features, a non-linear family, or a different
selection fraction. MODEL failed by 0.007 against a bar of 0.002 with the price
in its own feature set, in every division, with a control proving the instrument
recovers 99% of a planted edge of the size that would matter.

### 1.8 xG is unreachable through FBref — **VERIFIED 2026-08-06**

Not a decision awaiting anyone; a closed door, recorded so it is not reopened
speculatively. FBref **date pages carry no xG column for any of 60
competitions**, and neither does the Premier League **comp-season schedule
page** for 2022-23 or for the current season — zero `xg` data-stats in 628 KB,
HTML comments included. The remaining route is per-match report pages: ~26,000
requests against a 10 req/min policy, roughly 43 hours of continuous scraping.

Two side findings:

- **The session does not survive two days unattended.** The one minted
  2026-08-04 was refused on first use on 2026-08-06. A third independent reason
  the §4.1 shelving decision was right.
- **Comp ids for E0–E3 remain unverified** (`FBREF_SCRAPER.md` §4). The five
  cached date pages carry 34, 514 and 690 but none of 9/10/15/16, because those
  seasons had not started.

**This is what promotes §1.7 from "probably overtaken" to the live question.**
The argument for xG was that it is a better-measured version of the channel that
worked; it is not available, so the in-store channels are what remains.

---

## 2. Known-stale results

Things that are written down as settled but were measured on data now known to
be wrong.

### 2.1 The three P0 dispersion measurements — **RE-MEASURED 2026-07-28, all decisions hold**

Re-run on the complete thirteen seasons with the instrument unchanged (frozen
H=200, α=1.0, fortnightly refit), so the only difference was the data.

| result                 | re-measured                   | originally                        | decision              |
| ---------------------- | ----------------------------- | --------------------------------- | --------------------- |
| P0-1 totals dispersion | 1.0103 [0.9915, 1.0313]       | 1.0130                            | **holds** — keep Poisson |
| P0-2 draw deficit      | +0.90 pts [+0.34, +1.49]      | +0.87                             | **holds** — no τ      |
| P0-2 fitted ρ          | **−0.0213 [−0.0343, −0.0070]** | −0.0146 [−0.0283, **+0.0005**]   | see below             |
| P0-3 margin dispersion | 0.9909 [0.9715, 1.0101]       | 0.9900                            | **holds** — veto lifted |

**One supporting argument flipped.** ρ's interval no longer contains zero, so the
original first reason for declining τ — "not distinguishable from no effect" —
is dead, and has been struck in `MEASURED_AND_CLOSED.md` rather than reworded
away. The decision survives on three arguments, carried by the structural one:
τ only moves cells totalling 0, 1, 1 and 2, so it cannot affect an O/U 2.5 price
by any amount whatever the data says. That is exactly why it was worth having an
argument no measurement could touch.

**Two things improved.** The Asian-handicap caveat roughly halved — \|margin\| ≥ 3
and ≥ 4 are over-predicted by 1.6% and 3.5%, against 3.5% and 6.4% before. And
E0's draw deficit is now **+0.01 points**, as close to exactly zero as this
measurement resolves.

**New evidence for OPEN-6 (§3.3).** E0 now separates from E1–E3 on three
independent measurements, none of them designed to test pooling: the draw deficit
(+0.01 vs ~+1.1 pts), the share of market edge captured (0.89 vs 0.51–0.64), and
the sign of the season-boundary shrink. Converging evidence from unrelated
measurements is much stronger than any single test, and it points at **E0 as its
own calibration population** before P3 fits anything.

### 2.2 The gate ledger contains trials against corrupted data

**41 recorded trials**, of which the P0 measurements (×3 runs) and the first two
full P1 sequences were run against the bad corpus. The count is deliberately left
inflated — a trial spends against the development set whether or not its result
was later discarded. Any PBO/CSCV deflation should use 41, not a tidied number.
See §3.2 for the open question about how to treat this.

---

### 2.3 CALIBRATION.md's numbers predate the shots channel — **decision holds**

**Flagged 2026-08-04.** Every figure in `CALIBRATION.md` §2–4 was measured on
the head *before* the shots channel was adopted (§1.3). `engine/eval/p3.py`
pins that old config on purpose so the document stays reproducible, which is
also what makes its numbers stale relative to what is served.

**Not re-measured. The book stays off anyway**, on two arguments that do not
depend on the head:

- §1's bar — CLV must exceed the **vig**, not zero — is arithmetic about margin.
- H12's ablation is structural: the blend weights the model only if it adds
  information *given the price*, and the re-issued base score confirms **H9
  still holds**, the head is behind the market in all four divisions on both
  markets.

**What must not be done:** netting the head's 0.00179 nats of 1X2 improvement
against the 0.0186 CLV shortfall. Different units — nats versus de-vigged
probability. A new number requires re-running P3, which is a new measurement and
a new ledger row.

Re-running P3 on the current head is **not scheduled**; it would spend trials to
confirm a decision that is already carried by structure. Revisit only if a head
change is ever large enough to make the model competitive with the price.

## 3. Decisions awaiting the owner

### 3.1 P2 ordering — E3-first or E0-first? **MOOT, 2026-08-03**

The question presupposed a player layer worth ordering. P2 ran on all four
served divisions at once (the fit is joint, so a per-division build was never
the cheaper option) and returned null in every one — E0 +0.00008, E1 +0.00012,
E2 −0.00029, E3 +0.00013. No ordering decision is needed for work that is not
happening. **Closed, not deferred.**

The underlying asymmetry it was about is still live and still unexplained:

| division | share of the market's edge the base head captures |
| -------- | ------------------------------------------------- |
| E0       | 0.89                                              |
| E1       | 0.62                                              |
| E2       | 0.64                                              |
| E3       | **0.51**                                          |

That belongs to §3.3 (OPEN-6) now, not to P2.

### 3.2 How should the inflated trial count feed deflation? — **DECIDED 2026-08-04**

Written up in `docs/DEFLATION.md`, with the holdout still sealed. Machinery in
`engine/eval/trials.py`, planted-control tests in `tests/test_trials.py`.

**The question was on the wrong unit.** "51 trials or 13 questions" are both too
small: the ledger stores one row per *run*, and a sweep row holds a whole grid.
Counted mechanically — **52 runs / 24 questions / 133 configurations**, and 133
is a floor because 28 rows record no arm list. Counting rows *understates*
multiplicity by ~2.5×.

**The counting argument dissolves rather than being settled.** Primary statistic
is PBO via CSCV, which **takes no trial count as input** — it consumes a
weeks × configurations matrix and handles correlated trials by construction.
Deflated Sharpe is explicitly not used, because it needs the effective-N this
project cannot establish honestly. There is also no return series to deflate:
the book is off, so what P6 adjudicates is forecast quality, not profit.

**Measured, not asserted:** on P1's α grid (490 weeks × 8 configs),
**PBO 0.022**, degradation +0.000431, spread 0.00882 — the ridge selection is
not overfit. Three planted regimes (real skill / pure noise / designed overfit)
are asserted in tests, on the P2 principle that a null without a positive
control is not a result.

**The pre-committed criterion is in `DEFLATION.md` §5.** Read it before
unsealing, not after. Note §6's trap: PBO ≈ 0.5 on near-identical grids means
the choice was inconsequential, not overfit — handled explicitly by
`choice_mattered` rather than left to memory.

**P6 is not a launch gate**, and §8 says do not run it yet: no pending decision
turns on it, and it can be spent only once.

### 3.3 OPEN-6 — is the information-set split worth its cost?

P3 plans to split every calibration population by pre-close vs closing. H10
measured that axis for the first time:

| division | closing − pre-close (negative = closing sharper) |
| -------- | ------------------------------------------------ |
| pooled   | −0.00246 [−0.00335, −0.00160]                    |
| E0       | −0.00250 [−0.00441, −0.00060]                    |
| E1       | −0.00122 [−0.00269, +0.00024] —**no difference** |
| E2       | −0.00351 [−0.00507, −0.00185]                    |
| E3       | −0.00265 [−0.00435, −0.00098]                    |

Real but small, absent in E1, and largest in E2 rather than E0 as predicted.
Splitting halves the sample behind each Platt fit. Decide by
`y ~ logit(p) * information_set` in P3 rather than inheriting the SPEC's
assumption.

### 3.4 P5 meta-label — which product is being built? **ANSWERED 2026-08-06**

**The fork resolved itself, and not in favour of either product.** §1.9 has the
result. (A), a gate on the football model, is dead: MODEL − BOOK is −0.00702
with the wrong sign in all four divisions. (B), a line-movement predictor,
**looked** alive at +0.00762 — until the selection profile showed 65.3% of its
picks come from matches whose best-available book already sums to under 1. That
is not a line-movement model, it is an odds-comparison screen, and whether it is
worth anything is a question about **execution and limits at the Max price**,
which no gate here has touched.

So the owner decision below is no longer "which product" but a narrower one:
**is best-price execution worth investigating at all?** That is a question for
`RUNBOOK.md` and the feed, not for a model. The original framing is kept below
because the reasoning that produced it still stands.

---

Plan in `P5_META_PLAN.md`, grounded 2026-08-06. **No arm run.** §1's grounding
is now committed code — `engine/eval/meta.py`, tests `tests/test_meta.py`,
results `docs/p5_grounding_results.json`, ledger `p5_grounding`. It reads
prices and λ coverage only, no match outcome, so it carries no arm list and the
**configuration count stays at 149**. The grounding inverted the prior this
project had been carrying, so the decision is not the one that was expected.

**Building it corrected three things in §1, which is why it was worth building
before the arms rather than after:**

- **§1.2's division row was on a different basis.** Its cells summed to 22,113
  against a scored corpus of 21,896 — price availability alone, before the COVID
  embargo and before a walk-forward λ. Corrected to E0 3,708 / E1 5,412 /
  E2 5,366 / E3 5,398, which sums to the 19,884 headline. `meta.py` reports both
  so the old figure stays attributable.
- **§1.6's headline spread was one leg.** −0.01017 / 0.00755 is the home leg;
  over all three it is **−0.01097 / 0.00712**. §4 builds the feature per leg, so
  the all-leg figure is the one that describes it. No conclusion moves.
- **§1.5's stratum table is 1.56× optimistic**, and this is the one that
  matters. The design effect of 0.68 comes from the three legs of a match
  cancelling; a selection takes one leg per match, where measured design effect
  is **1.06**. The 2% stratum resolves 0.00134, not 0.00085, against a Max vig
  of 0.00201. **Power is still not the constraint** — but the margin at thin
  volume is half what was published, and §5's ≤12-configuration budget should be
  read against the wider column.

**Power is not the constraint — that was wrong when I last reviewed it.**
sd(CLV) is 0.0222 over 59,652 legs in 408 week blocks; the block-bootstrap SE of
the mean is 0.00006, and even a **2% stratum (1,193 legs) resolves 0.00085**
against a Max vig of 0.00201. The binding constraint is **multiplicity**, which
needs a different control — PBO/CSCV, a declared ≤12-configuration budget, and a
planted negative per §1.7.

Three other grounded facts that scope it:

- **1X2 only.** The 1X2 CLV basis is 19,884 matches / 59,652 legs from 2012-13;
  the O/U basis is **5,638 matches from 2019-20** — within six of the 5,644 that
  made the kickoff slot unresolvable, and the same cause. O/U also costs 3.6×
  more at best price.
- **The mean is mechanically pinned.** The three 1X2 legs of a match have CLVs
  summing to −0.00577, the Max overround. Betting every leg returns −0.00192/leg
  **by construction**. A meta-label can only help by *ranking*; any evaluation
  reporting a mean over all legs is measuring the overround.
- **The basis is clean.** `predictions`, `paper_bets` and `clv_grades` are all
  empty, so SPEC §3.8's "all leans, never surfaced picks" holds by construction
  and the survivorship loop cannot exist yet. **Keep it that way when the book
  turns on.**

**The decision, and it is not a modelling one.** There are two products under
"meta-model": **(A)** a gate on the football model, and **(B)** a line-movement
predictor. The most informative feature available — the sharp-vs-consensus
spread, −0.01017 at 99.8% coverage — is pure price, so (B) is what the data
readily supports and (A) is what SPEC §3.8 wants. The plan tests (A) and uses
(B) as the ablation that tells them apart, with **`MODEL − BOOK` as the decision
statistic rather than a footnote**.

Whether (B) is worth pursuing on its own is the owner's call. It would reopen
§1.0 on a *new* instrument rather than re-litigating the old one, and it should
be decided in the open rather than arriving as a good AUC.

---

## 4. Work not started

### 4.1 Track A — the serving path (Week 1 + Week 2 scope, none of it built)

The head is frozen and `engine/serve/artifact.py` produces auditable, reloadable
artifacts, so this is plumbing:

1. `api/` — FastAPI `/fixtures`, `/predictions`, `/book`, `/health`. Artifact
   loaded by version string, never re-fitted per request.
2. `services/fixture_sync` — football-data.org free tier for E0; the
   football-data.co.uk fixtures CSV for E1–E3 and current prices.
   **Availability of that CSV has never been verified** — fallback is a manual
   entry UI.
   **New option (2026-08-03):** `services/fbref_scraper/` is built, tested and
   working — one fbref date page carries every competition, so a week of E0–EC
   fixtures costs 7 requests. Probe results, architecture and caveats in
   `docs/FBREF_SCRAPER.md`. No prices on fbref, so it covers fixtures/results
   only, not the CLV feed. Unverified: comp ids for E0–E3 in the example TOML
   (only 34/514/690 confirmed live), and the practical Cloudflare session
   refresh cadence.
   **SHELVED 2026-08-04 by owner decision.** Not wired into the serving path
   and not to be enabled without a recorded decision. It is the fallback if
   English rows never appear in the football-data.co.uk feed (§1.2), not the
   default. Two reasons beyond the decision itself: it needs a *headed* browser
   on a live desktop to refresh the Cloudflare session, which does not compose
   with an unattended scheduled cycle (§4.3); and it carries no odds, so
   `fixture_sync` is still required for CLV grading either way.
3. `predictions` table writer — λ stored raw, pmf-derived 1X2 + O/U, version
   string, information-set tag, served-at.
4. `web/` — SvelteKit fixture cards.
5. `paper_bets` writer — flat stake, EV vs **raw `1/odds`** (vig-inclusive).
6. `services/csv_grader` — weekly result grading + retrospective CLV.

### 4.2 P3-lite calibration (Week 3 scope)

Per-population Platt recal fitted from stored λs with the poison test; OPEN-6
interaction test (§3.3); CLV harness de-vigging PSCH with AvgCH fallback,
backtested on dev seasons.

### 4.3 Opening-weekend runbook — **BUILT 2026-08-04**

`docs/RUNBOOK.md`, with `services/run_cycle.py` and `scripts/run_cycle.ps1`.

The orchestrator runs sync → serve → grade as **independent** steps and always
writes a `serving_state` row, including on failure. Three exit codes, and the
distinction is load-bearing:

    0  clean      2  ran but needs a look      1  a step failed

`2` covers the failures that neither raise nor succeed — empty feed, unbridged
club, unpriceable fixture, stale artifact. Collapsing `2` into `1` means being
paged all summer for an out-of-season feed and then not reading the alerts.

Two behaviours worth knowing about:

- **The artifact refreezes itself** past `REFIT_AFTER_DAYS` (7), so a missed run
  cannot leave a stale head pricing a weekend.
- **`cycle.serve` now skips clubs the artifact has never seen** instead of
  raising (`cycle.servable`). One National League newcomer used to take the
  whole matchday down, Premier League included. Unknown clubs are still never
  given a silent league average — they are reported by name and left unpriced.

Verified against the live feed: `exit 2`, `NO ENGLISH ROWS`, which is the
correct answer out of season and confirms the detector while it is cheap to
confirm. **Still not done: alerting, hosting, DB backup** — all three are now
planned in `DEPLOY.md` and tracked at §4.4.

### 4.4 Hosting — planned 2026-08-08, agreed, partly started

Plan in `docs/DEPLOY.md`: one Azure VM, Ubuntu 24.04 LTS, updated by `git pull`,
owner-operated. Measured first — the refit is **1.5 s at 167 MB RSS**, so the
machine is small and sizing is not the question. **437 tests pass.**

**Three blockers. The first is closed by `ccb6f8e`; the other two are
groundwork, now laid.** Everything customer-facing was uncommitted — and
`origin/main` was at **`244ca18`, the first commit**, five behind local `main`.
GitHub was missing P2, the runbook, all the controls and the whole customer
surface: **a `git pull` on a fresh server would have fetched the data spine and
nothing else.** The other two are that the database and the frontend build are
both gitignored (both rebuildable on the server — verified 2026-08-08 that a
clean `engine.ingest.build` applies all four migrations and passes every
integrity check, and that `npm run build` yields a published root of
`index.html`, `_app/` and one 127 KB image), and that the `/api` rewrite existed
only in Vite's dev proxy.

**Done 2026-08-08:** `requirements.lock` (§3.5 — a pinned closure, because
`pandas>=2.0` plus `filterwarnings=["error::FutureWarning"]` makes an unpinned
server install a test failure waiting to happen), `deploy/nginx/*.template`
(the `/api` rewrite, the SPA fallback, and basic auth on the two internal
endpoints), `.gitignore` for `web/static/*.rar`, and the hero image de-fringed
and cut 2.72 MB → 127 KB.

**Also done: the Linux operational layer** — `scripts/run_cycle.sh`,
`scripts/deploy.sh`, `deploy/systemd/{bvp-api.service,bvp-cycle.service,
bvp-cycle.timer}`, and a `.gitattributes` pinning `eol=lf` on everything Linux
consumes. `run_cycle.sh` is verified against the live feed at `exit 2`,
`NO ENGLISH ROWS` — `RUNBOOK.md` §3's T-7 check, now passing through the shell
script that will actually run it.

**Four things worth carrying forward:**

- **A public host would publish a return, through a page B7 does not guard.**
  `/performance` returns `pnl` and `roi` and `/book` returns `paper_bets.*`;
  `test_the_record_publishes_no_profit_figure` covers `/tips/record` **only**,
  and both are linked from the public footer. Empty today because the book is
  off, so the exposure is conditional — but it is the same shape as
  `step_grade`'s short-circuit in §1.10: **a check that was correct until a
  second thing needed covering.** nginx basic auth is the deployment
  mitigation; the real fix is inverting the test to "no *public* endpoint
  carries P&L", which is small and is not deployment work.
- **WAL decides the storage, and it rules things out.** `engine/db.py` needs
  shared memory, so the database cannot live on Azure Files or NFS —
  local disk or an attached managed disk only. That also rules out any
  two-VM shared-database design without real work. `RUNBOOK.md` §8 called this
  before the target was chosen and it turned out to be the binding constraint.
- **The hero image was published-ready and wrong.** 54,696 pixels — 2.17% —
  are green, and **every one is semi-transparent**: a keyed background that was
  never de-fringed. Invisible against white, which is how it survived review,
  and `.hero` is orange, so it would have gone live with a lime halo. Found by
  measuring the asset rather than by looking at it. `DEPLOY.md` §2.6.
- **`httpx` was an undeclared dependency, and it is the second instance of the
  same defect.** `fastapi.testclient` imports it; it was present on the
  development machine as a transitive of something unrelated, so 437 passed
  here and a clean Ubuntu install **could not collect `tests/test_api.py` at
  all** — a collection error, so zero tests ran. `pyproject.toml`'s `serve`
  block already carries a comment recording exactly this from 2026-08-04
  (*"present in the development environment but undeclared"*), and the lesson
  did not transfer because it was written as a note about `fastapi` rather than
  as a rule about the class. **`requirements.lock` could not catch it** — the
  lock is computed from what pyproject declares, so it inherited the omission.
  It pins versions; it does not discover dependencies.
- **The gate ledger exists on one machine, gitignored, with no backup.** Found
  by asking why one test fails on a fresh store. The 90 rows behind §0's
  `87 runs / 45 questions / 167 configurations` live in `db/premier.db` **here
  and nowhere else**; `engine.ingest.build` rebuilds `matches` and
  `player_seasons` from the tracked CSVs and cannot rebuild the ledger, because
  it is **a record of what was measured, not a function of the data**.
  `DEFLATION.md` reads it, §0 tells every future thread to re-derive from it
  rather than trust the prose — which makes it the authority — and the
  pre-committed P6 read depends on it. `DEPLOY.md` §6.1 now covers **two**
  machines, and says do this one first: the server does not exist yet, and this
  asset is older and equally irreplaceable.
- **One test could not pass on the server, and it was the acceptance gate that
  found it.** `test_the_real_ledger_holds_more_configurations_than_rows` opens
  the real `db/premier.db` and asserts `configurations >= 133`; a rebuilt store
  has an empty ledger, so `pytest -q` was **436 passed, 1 failed** on a
  server-like database. It now skips where there is no ledger to guard — narrow
  enough that a ledger which *exists* and has regressed still fails. A gate
  known to fail is not a gate, on the same argument `RUNBOOK.md` §7 makes about
  tolerated warnings.
- **`git push` over SSH does not work from this machine.** `github.com:22`
  times out; the network blocks it. GitHub's port-443 endpoint authenticates
  fine, so `origin` is now `ssh://git@ssh.github.com:443/...`. **Check the
  server's egress during `DEPLOY.md` §5.4**, not mid-deploy. The permanent form
  is a `Host github.com / Port 443` block in `~/.ssh/config`.
- **systemd closes "no lock file" for free**, and `SuccessExitStatus=2` is
  load-bearing. systemd will not run two instances of one unit, which is the
  gap `RUNBOOK.md` §8 lists and Task Scheduler covered only by configuration.
  But systemd treats every non-zero as failure, so without `SuccessExitStatus=2`
  the cycle is marked failed every day of the close season and the alerts stop
  being read — the exact failure the three exit codes exist to prevent.

**Not started: §6, the fault-tolerance build-out** — `VACUUM INTO` backups to
Blob with a restore drill, and alerting on all three conditions including a
**dead-man's switch**, which is the one `OnFailure` structurally cannot provide:
if the VM is off, nothing fires and the first symptom is a lost matchday.
Also not started: `RUNBOOK.md` §0.2/§2 still document Task Scheduler on Windows,
so an operator following it against the Ubuntu VM finds half its commands do not
exist.

---

## 5. Deferred by decision (not forgotten)

| item                              | where it went                     | why                                                                                                                                                  |
| --------------------------------- | --------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| **OPEN-2** form leg               | In-season                         | H2 put the decay optimum at 400 days, the opposite end of the timescale axis from where a short-memory leg lives.                                    |
| **OPEN-3** season-boundary shrink | P4, as a population-specific gate | Helps lower-division O/U, degrades E0 1X2 (+0.00259 [+0.00121, +0.00389]). Not a global hyperparameter.                                              |
| **OPEN-4** stakes definition      | P4                                | Needs as-of league-table reconstruction.                                                                                                             |
| Market-value snapshot             | **Dropped**                       | Single undated snapshot. P2 measured that a *perfect* prior is worth 0.0002 nats at the served α; a noisier one cannot be worth more.                |
| **Dated transfer data**           | Blocked on acquisition            | `data/transfer-history/` is empty. The one input that would make the player layer buildable — it makes season-N squads legally knowable (`PLAYER_PRIOR.md` §5). |
| Asian handicap / correct score    | Post-launch                       | Veto lifted in P0-3 (pending §2.1 re-check), but\|margin\| 3–4 is over-predicted by 3–6% and that is exactly where AH lines sit. Needs its own gate. |

---

## 6. Code debt

- **`poisson.walk_forward_lambdas` is superseded** by
  `engine/eval/walkforward.py` but deliberately kept so the P0 dispersion
  results stay reproducible. `test_reproduces_the_p0_harness_exactly` pins the
  two together to 1e-9. **Delete it once §2.1 is re-run through the new
  harness** — `dispersion.py:338` is the only remaining production caller.
- **The `test_run_cycle.py` calendar time bomb — FIXED 2026-08-10.** Two tests
  began failing on 2026-08-09 without any code changing. They were the only ones
  in the file calling `run_cycle.run()` **without pinning `today=`**, so they ran
  `pd.Timestamp.now()` against an artifact fixture frozen at
  `fitted_at="2026-08-01"`; once the wall clock passed `REFIT_AFTER_DAYS = 7`,
  `_stale()` fired, serve refroze and published nothing, and tips reported
  `no untipped predictions`. **Nothing in the product was ever broken** — the
  staleness rule was working and the tests had aged out. Fixed with a named
  constant `FRESH_ARTIFACT_DAY` and three call sites (the third was a
  prophylactic pin on the one remaining unpinned call). **458 tests pass.**
  Two things worth keeping:
  - **A speculative second fix was measured and withdrawn.** `step_grade` is not
    given the cycle's `today` and bounds on SQL `date('now')`, so a fixture dated
    inside the real calendar eventually reads as played. That looked like a
    second bomb due on 2026-08-15. Simulating it — setting `add_fixture`'s
    default to a date already past — left **all 15 tests passing**, so the
    grading path tolerates it and the "fix" was scope with nothing behind it. It
    was reverted rather than kept as insurance.
  - **The asymmetry itself is real and is left alone.** `run()` takes `today` and
    threads it to `step_serve` but not to `step_grade`, so a cycle run with an
    explicit `today` is only partly deterministic. Harmless today. The structural
    fix is to thread `today` through, which is a production change and wants its
    own decision rather than arriving inside a test repair.
- `engine/eval/p1.py` trips a cognitive-complexity lint in `h9_baseline` and
  carries two duplicated string literals. Cosmetic.
- `db/artifacts/` is gitignored as reproducible output. If artifacts that
  actually served a bet need retaining for audit, that decision has not been
  made.

---

## 7. Conventions a new thread must not break

These are load-bearing and were each established for a reason that is not
obvious from the code alone.

1. **The holdout stays sealed.** 2023-24, 2024-25, 2025-26. `resolve_seasons`
   raises rather than filtering; every unseal writes a ledger row. Serving reads
   sealed seasons under `purpose=live`, which is not a gate and must never be
   used to measure anything.
2. **Selection metric is goal Poisson deviance.** 1X2 and O/U are reported, not
   selected on. When they disagree with deviance, that is a finding to write
   down — and in OPEN-3's case it overturned the literal rule, with the reason
   recorded.
3. **Compare arms with the PAIRED standard error, never the marginal one.** On
   this corpus they differ by 29× and using the marginal one makes any 1-SE rule
   vacuous. This shipped as a real bug and changed a gate's verdict.
4. **`breakeven_prob` (raw 1/odds, vig-inclusive) and `devig_probs` (normalised)
   are never interchangeable.** Betting decisions use the former, scoring the
   latter. `engine/eval/metrics.py` does not import the former at all.
5. **The gate ledger is append-only and records re-runs.** No helper exists to
   update or delete, and adding one would defeat the purpose.
6. **`build.validate()` must pass before any number is trusted.** Two defects on
   this corpus — numpy scalars stored as BLOBs, and a duplicated season — both
   left row counts perfect and content wrong.
7. **A boundary optimum is not an optimum.** `SweepResult.censored` flags it;
   widen the grid rather than reporting the edge.
8. **A null needs a positive control or it is not a result.** P2's arms were all
   null; what makes them mean "no signal" rather than "no instrument" is H17,
   which planted a prior that knew the answer. It is the same discipline as the
   planted defects in `test_calibration.py`, and it is what turned P2 from a
   null into a diagnosis. Every future gate expecting a null should carry one.
9. **Hyperparameters chosen under an assumption inherit it.** P1 selected α=0.1
   with the ridge target pinned at zero, which silently decided how much any
   future prior could ever matter (`PLAYER_PRIOR.md` §2). Before sweeping a
   parameter, write down what is being held fixed and whether the two interact.

---

## 8. Documentation audit — 2026-08-06

Every file in `docs/` was read and its numeric and structural claims checked
against the code and the database. **No decision changed.** Recorded because
this project's failure mode is documents drifting from the results they cite,
and §0 already carries one instance of it.

### 8.1 Four numeric defects, corrected in place with the reason kept

| file | defect | status |
| --- | --- | --- |
| `REST.md` §3 | band table was from the **pre-fix** of the two runs §1.5 records — counts summed to 42,778 against the 42,850 in its own §1, and three bands were wrong in value too (`7` was 14,524, not 14,591). `rest_results.json` was correct throughout. | corrected |
| `PLAN.md` §3 | **contradicted itself**: OPEN-2 said the decay optimum was 500 days, NEW-4 in the same table recorded the 500 → 400 correction | corrected |
| `MEASURED_AND_CLOSED.md` P0-2 | quoted the deficit range 0.0117–0.0155, the value *before* the shots channel; now 0.0098–0.0141 | corrected |
| `DEFLATION.md` §1, §4 | counts 52 / 24 / 133 and "28 rows" were 2026-08-04 values; live is 76 / 41 / 149 and 47 | both dates now shown, with a re-derive instruction |

None moves a verdict. `REST.md`'s largest cell shifts 0.5% and its ANOVA is
unchanged at p = 0.591.

### 8.2 The launch bar was not reproducible, and now is

**Nothing in `engine/` computed an overround on the corpus.** The
`0.65% / 0.00217 / 6.37% / 0.02122` figures under `CALIBRATION.md` §4 — the
arithmetic behind "CLV must exceed the vig" — were written into prose with no
code behind them. `p3.py` never calculated them, so re-running it could not
check them. Same defect class as `CHANNELS.md` §7's row 53, under a more
consequential number.

`engine.odds.vig_per_leg` is now committed and tested. Re-derived:

| basis | 1X2 @avg | 1X2 @max | O/U @avg | O/U @max |
| --- | --- | --- | --- | --- |
| all scored (21,896) | 0.02107 | **0.00201** | 0.03041 | 0.00718 |
| H13's 1X2 basis (19,887) | 0.02067 | **0.00192** | 0.03010 | 0.00719 |

The published figures are **8–12% higher than any subset reproduces**, so the
stated bar is conservative and §1/§4/§5 all hold. Two things the single pooled
figure concealed: **O/U costs 3.6× more than 1X2 at best price**, and
best-available pricing removes **90%** of the 1X2 margin — which is the
arithmetic behind "best-price capture is a prerequisite, not an optimisation".

**Use the re-derived table for new work.** `P5_META_PLAN.md` §1.3 already does.

### 8.3 Staleness banners added

- **`SPEC.md`** read *"DRAFT for re-review. Nothing built. No code written."* —
  at the top of the first file the reading order sends people to, with the
  system built and 360 tests passing. Banner now lists the seven refuted
  sections so nobody re-derives them.
- **`FBREF_SCRAPER.md`** still read "Verdict: feasible" with no record that it
  was shelved 2026-08-04 and its xG premise refuted 2026-08-06 (§1.8).
- **`PLAN.md`** and **`FINDINGS.md`** dated 2026-07-28 with no scope marker.
- **`TOD_SLOT.md`** §9 and **`REST.md`** §7 still listed travel as blocked.

### 8.4 Checked and clean

Every cross-document reference resolves (`META.md` is a forward reference from
`P5_META_PLAN.md`). Every code path cited in docs exists. `OUTSTANDING.md` §6's
`dispersion.py:338` pointer is exact. `BASELINE.md` §2's n differing from
`SHOTS_TARGET.md` §3 is **not** a defect — BASELINE requires prices. Stale
figures inside `BASELINE.md` §3+ and `P3_PLAN.md` are correct to leave: both are
explicitly unedited so their predictions can still be scored.

---

## 9. Re-review under the tipster objective — 2026-08-10

P0–P5 answered *"can this beat the book"*. §1.10 replaced that objective with a
strike-rate tipster and §1.11 shipped it. This section re-reads the closed
decisions against the objective that replaced the one they were closed under.

**No decision is reversed here.** Three items are arguments that have partly
expired; the fourth is a priority, not a finding.

**The bars that closed things were beat-the-book bars.** Three were used, and
only the third has a live consequence:

1. **"Does it add information *given the price*?"** — H12's ablation (§1.0),
   §1.9's `MODEL − BOOK`. A tipster competes with nothing, so the bar does not
   apply — but nothing was closed on it that a tipster wants back. §1.9 and §1.0
   stay closed on their own terms.
2. **"Is it worth enough against the gap to the market?"** — P0-2's first reason
   scales τ's −0.000145 against the head's 0.0098–0.0141 nat deficit
   (`MEASURED_AND_CLOSED.md` P0-2, reason 1). That deficit is a beat-the-book
   yardstick. It does not follow that the effect is negligible in the product's
   own units, which are one 0/1 call per match.
3. **"Does it move 1X2 or O/U 2.5?"** — the served markets *at the time*. The
   product now publishes five and **85.6% of its output is double chance**.
   This is where the re-review earns its keep.

### 9.1 P0-2's decisive argument is scoped to a market that is now 0% of output

`MEASURED_AND_CLOSED.md` P0-2 declines the Dixon–Coles τ on three reasons, and
flags reason 2 as **"the one argument no re-measurement can touch"**: τ
redistributes mass among the 0-0, 1-0, 0-1 and 1-1 cells, whose totals are 0, 1,
1 and 2, all below the 2.5 line, so no redistribution among them can move an
O/U 2.5 probability by any amount.

**That is correct, and it is exclusively true of O/U 2.5.** Against the menu
`engine/serve/tips.py` actually publishes:

| menu item | cells τ touches | moves? |
| --- | --- | --- |
| O/U 2.5 | all four, adjustments sum to zero | **no** — as documented |
| **draw, and `12`** | 0-0, 1-1 | **yes** |
| **`1X` / `X2`** | 0-0, 1-1, and one of 1-0 / 0-1 | **yes** |
| **O/U 0.5, 1.5** (B4) | 0-0; 0-0 + 1-0 + 0-1 | **yes** |

`score_matrix(..., rho)` already implements τ (`engine/eval/dispersion.py:50`)
and the whole served path calls it at `rho=0`, through `metrics.model_probs`
(`engine/eval/metrics.py:75`) for the `predictions` table and
`selection.raw_probs` (`engine/eval/selection.py:82`) for the tip rule.

**The sharp version: `12` loses if and only if the match is a draw, and `12` is
65.0% of all recommendations.** Two thirds of the product is a pure draw
forecast, and the draw is the one quantity P0-2 measured the head getting wrong:

| division | draw deficit (P0 instrument) | 95% CI |
| --- | --- | --- |
| E0 | **+0.01 pts** | [−1.19, +1.18] |
| E1 | +1.24 pts | [+0.24, +2.33] |
| E2 | +0.96 pts | [−0.11, +1.94] |
| E3 | +1.13 pts | [+0.13, +2.22] |

The direction is the unhelpful one — the head **under-predicts draws**, so it
**over-states P(`12`)**, the product's largest market. Neither this nor the
under-confidence of §1.10 is **visible in goal Poisson deviance**, which is what
convention 2 selects on. *(§9.5 measured this. The draw error is real and
pooled-resolved, the per-division split does not reproduce on the served head,
and the draw turns out not to be the largest error in the vector.)*

**Reason 3 survives and now argues the other way.** P0-2 rejected τ partly
because τ is global while the deficit is not, which would impose a diagonal
correction on E0 where there is nothing to correct. Under a per-division served
product that is an argument for a **per-division** ρ, not against a correction.

**Two things make this a measurement rather than a conclusion:**

- **The deficit has never been measured on the served head.** P0-2 ran on the P0
  instrument — frozen H=200, α=1.0, fortnightly refit — not on
  `H400/a0.1/weekly/E0+E1+E2+E3+EC/sot0.3`. Same staleness §2.3 flags for
  `CALIBRATION.md`, under a number the product now depends on.
- **The union has never been calibration-checked at all.** `BACKLOG.md` B3's own
  scoping note asked "whether the head is calibrated on the *union* `p_h + p_d`"
  and B2's asked the same. Neither is in `engine/eval/selection.py` or
  `docs/selection_results.json` — the only calibration table there is the pooled
  1X2 argmax, and there is no per-division breakdown of anything.

**Expect the effect to be small.** τ at ρ = −0.0213 moves P(draw) by about
+0.5 points, which closes 56% of a deficit that is itself around 1 point. On a
72.5% realised strike rate that is not where a product is won. What it changes
with certainty is **what the product can honestly claim**, which is B7's open
half; what it changes uncertainly is **selection at the floor and the ceiling**,
where a 1-point shift moves fixtures across a boundary.

#### Pre-registered, before the diagnostic ran

Written 2026-08-10 ahead of `engine/eval/draws.py`. Four arms declared:
`rho=0` (shipped), pooled walk-forward ρ, per-division walk-forward ρ, and a
planted ρ as the positive control convention 8 requires — a null on the first
three means nothing without evidence the instrument can see a draw correction at
all.

1. The draw deficit **survives on the served head** at ≥ +0.5 pts pooled, and
   the E0-versus-E1–E3 split survives with E0 inside [−0.5, +0.5].
2. Walk-forward ρ on the served head lands within P0-2's [−0.0343, −0.0070].
3. **`12` is over-confident** — claims more than it delivers — and `1X`/`X2` are
   under-confident, in E1–E3 and not in E0.
4. Applying ρ **changes fewer than 5% of recommendations** at the shipped floor
   0.55 / ceiling 0.85.
5. Strike rate moves by **less than the ~0.7 pt** that population resolves, so
   the honest read will be a calibration result and not a strike-rate result.
6. The planted control **does** move recommendations, at a rate the fitted arms
   do not reach.

Results in §9.5. **Cost: 4 configurations**, declared here before running.

### 9.5 The draw-mass diagnostic — **MEASURED 2026-08-10. P0-2 stands.**

Code `engine/eval/draws.py`, tests `tests/test_draws.py`, results
`docs/draw_mass_results.json`, ledger `draw_mass_tipster` (4 configurations,
166 → **170**). 15,824 out-of-sample matches, 2014-15 → 2022-23 — the same
population B2 and B3 report on. **Five of six predictions right, and the sixth
is the one worth reading.**

**Do not adopt τ.** The decision P0-2 reached survives, and it now survives a
test aimed at the objective that replaced its own.

#### ρ reproduces; the division story does not

Walk-forward ρ on the served head is stable across all eight folds (−0.0147 to
−0.0286) and the full-sample fit is **−0.02539**, against P0-2's −0.0213
[−0.0343, −0.0070] on the P0 instrument. Prediction 2 right.

| division | deficit, served head | 95% block CI | (P0-2, P0 instrument) |
| --- | --- | --- | --- |
| pooled | **+0.75 pts** | [+0.03, +1.43] ✱ | +0.90 |
| E0 | +0.40 | [−1.17, +1.96] | **+0.01** |
| E1 | +1.19 | [−0.20, +2.51] | +1.24 |
| E2 | +0.75 | [−0.51, +2.03] | +0.96 |
| E3 | +0.55 | [−0.77, +1.78] | +1.13 |

The pooled deficit survives and resolves. **The per-division split does not.**
No division's deficit excludes zero, and the gradient that P0-2 made OPEN-6's
third line of evidence — *"the Premier League has no draw deficit at all"* — is
flat on the served head: E0 +0.40 against E3 +0.55. Prediction 1 passes on its
literal wording (pooled ≥ 0.5, E0 within ±0.5) and **the claim behind it does
not**. Recorded rather than reworded, per the P0-2 precedent.

#### The draw is not the largest error in the vector — and nobody had looked

The first outcome-level decomposition of the served head. Delivered minus
claimed, ✱ = excludes zero:

| population | home | draw | away |
| --- | --- | --- | --- |
| pooled | +0.33 | +0.75 ✱ | **−1.07 ✱** |
| E0 | **+1.77 ✱** | +0.40 | **−2.17 ✱** |
| E1 | +0.38 | +1.19 | −1.56 ✱ |
| E2 | +0.23 | +0.75 | −0.98 |
| E3 | −0.61 | +0.55 | +0.07 |

**The away win is over-predicted by −1.07 points, and it is the largest resolved
miscalibration the head has.** τ is a diagonal correction and cannot address it.
This is the substantive answer to §9.1: the draw is not what is most wrong with
the 1X2 vector, it is what P0-2 happened to ask about, and a union table read on
its own cannot tell the two apart because `1X`, `X2` and `12` count every
outcome twice and their three gaps must sum to zero. `test_draws.py` pins that
identity.

**E0 is the most miscalibrated division, not the cleanest.** Its home and away
errors are the largest in the corpus and both resolve, and they **nearly cancel
inside `12`** (+1.77 − 2.17 = −0.40), which is why `12` reads calibrated there.
P0-2's "E0 has no draw deficit" was true and misleading. **This corrects
OPEN-6's third line of evidence** (§2.1, §3.3): E0 *is* a separate population,
and the axis is the result, not the draw.

#### The union markets, calibrated for the first time

`BACKLOG.md` B2 and B3 both asked for this and neither delivered it. Pooled,
with the paired block bootstrap rather than the binomial half-width
`selection.calibration_table` uses:

| market | share of output | claims | delivers | gap | verdict |
| --- | --- | --- | --- | --- | --- |
| **`12`** | **65.0%** | 74.39% | 73.64% | **−0.75** [−1.43, −0.02] | **over-confident** |
| **`1X`** | 17.6% | 68.64% | 69.72% | **+1.07** [+0.37, +1.78] | under-confident |
| `X2` | 3.0% | 56.97% | 56.64% | −0.33 [−1.15, +0.45] | calibrated |

**The product's two largest markets are miscalibrated in opposite directions**,
and `12` — two thirds of what ships — is the one that over-claims. Prediction 3
right. Per division only the pooled figures resolve; `1X` also resolves in E0
(+2.16) and E1 (+1.56), and `X2` is over-confident in E0 (−1.77).

This is the number **B7 is still missing** (§1.11, `BACKLOG.md` B7). It is small
and it is in the direction that matters for a published claim.

#### The strike-rate gain is real, and it is not τ's

At the shipped floor 0.55 / ceiling 0.85, against the shipped arm, **paired**
per convention 3 — the marginal CIs are ~2.4× wider and make every comparison
here vacuous:

| arm | recommendations changed | strike | vs shipped, paired | mix `12`/`1X` |
| --- | --- | --- | --- | --- |
| ρ = 0 (shipped) | — | 72.49% | — | 65.0 / 17.6 |
| ρ pooled | 6.29% | 72.78% | +0.291 [−0.000, +0.576] | 59.3 / 22.7 |
| ρ per-division | 6.41% | 72.83% | **+0.341 [+0.045, +0.637] ✱** | 59.4 / 22.5 |
| **ρ planted (−0.10)** | **27.62%** | **73.12%** | **+0.626 [+0.019, +1.199] ✱** | 39.4 / 38.9 |

**Prediction 4 was wrong** — 6.29% of recommendations change, not under 5%. A
correction worth half a point of draw probability moves one call in sixteen,
because the fallback comparison `1X` beats `12` iff `p_d > p_a` sits close to
the margin for a lot of fixtures.

**And prediction 6 is right in a way that kills the result.** Strike rate is
**monotone in |ρ| well past the fitted value**: the planted ρ, five times too
large and fitted to nothing, is the *best* arm. If the gain came from ρ being
correct, an over-large ρ would be worse. So it is not a draw correction that is
being measured — but **what it is instead is now an open question, not the
answer originally written here.**

> **Correction 2026-08-10, from §9.6 step 3.** This section attributed the gain
> to the fallback ordering shifting from `12` to `1X`, on the reasoning that
> `12` carries the over-predicted away win while `1X` carries the two
> under-predicted outcomes. **That explanation is not supported.** B2's
> calibration shifts the same mix **three times harder** — `12` 65.0% → 47.7%, a
> 17.3-point move against τ's 5.7 — and returns **+0.088 [−0.410, +0.556]**,
> unresolved. A larger shift through the same channel should have paid more.
> **The verdict below is unaffected** — τ stays declined, on the stronger ground
> that a 5×-wrong ρ was the best arm — but why strike rate is monotone in |ρ|
> is **unexplained**. Do not build on the mechanism as stated.

**Four things worth carrying forward:**

- **A planted control protects a positive, not only a null.** Convention 8 was
  written so a null could not be confused with a dead instrument. Here the arms
  were positive and the control showed the positive is **not attributable to the
  mechanism under test**. §1.7 recorded the mirror image — a positive result
  needing a planted negative — and said the lesson should be read as covering
  both directions. **This is the first time the control caught a live
  misattribution rather than a hypothetical one**, and convention 8 should be
  restated as: every gate carries the control that could falsify the result it
  actually got.
- **Adopting τ here would bank an ordering effect under a distributional
  label.** The +0.341 is real and it would be logged as "the Dixon–Coles
  correction is worth a third of a point". The next head change would move it
  unpredictably and nothing would explain why.
- **The defect worth fixing is `12`-versus-`1X`, and it is a new question.** The
  head over-states `12` by 0.75 points and under-states `1X` by 1.07, and the
  rule picks between them on a margin. That should be pre-registered on its own
  terms — not smuggled in as a τ result — and it interacts with the `ALLOW_12`
  owner decision, which the strike numbers above suggest is costing strike rate
  rather than only specificity (`BACKLOG.md` B3).
- **P0-2's reason 2 is still exactly true and is now pinned in code.**
  `test_tau_cannot_move_an_over_under_2_5_probability` asserts it to 1e-12, and
  a companion test asserts that τ *does* move the 0.5 and 1.5 lines B4 wants to
  publish. The argument was never wrong; it was scoped, and the scope is now a
  test rather than a paragraph.

**Do not** re-litigate τ with a finer ρ grid, a per-season ρ, or a ρ × division
interaction. The instrument resolves the effect, the effect is present, and the
measured benefit is attributable to something else — which more ρ arms cannot
fix and would spend the budget hiding.

### 9.6 The E0 follow-up — **MEASURED 2026-08-10. Three steps, two of my own conclusions refuted.**

Code `engine/eval/home_term.py`, results `docs/home_term_results.json` /
`home_term_step2.json` / `home_term_step3.json`, ledger `home_term_power`
(probe, 0 configurations), `home_term_dispersion` (3) and
`b2_calibration_in_product` (3). **170 → 176.**

§9.5 found E0 under-predicting home wins by +1.77 pts and over-predicting away
by −2.17, both resolved, and called E0 "the most miscalibrated division". This
is the attempt to fix it. **Nothing is adopted, and the most useful output is
the list of things that turned out not to be true.**

#### Step 1 — E0 cannot adjudicate its own fix (0 configurations)

Poisson score information on the fitted λs, no outcomes read, same licence as
`power.py`:

| correction | required | resolvable (contrast) | t |
| --- | --- | --- | --- |
| home rate alone | 5.30% | 4.38% | **1.21** |
| tilt (home up, away down) | 3.14% | 4.38% | **0.72** |

Both under 1.96; even the optimistic "everything else fixed" bound (2.94%) only
reaches t = 1.80. **E0's 2,948 matches cannot resolve a home-term fix of the
size its own gap implies.** Note the tilt scores *worse* because it is the more
efficient correction — a smaller parameter change does the same job, so it is
harder to see. This is the §1.4 shape, caught for nothing before spending.

> **Correction: step 1's second conclusion was over-confident, and is
> withdrawn.** It reported that neither parameterisation reproduces E0's
> three-cell geometry, on residuals of +0.96 (home-only) and +0.58 (tilt)
> against a **±0.5 pt** threshold. E0's measured draw gap is +0.40 **[−1.17,
> +1.95]** — a measurement CI of ±1.5 pts. A 0.5-pt threshold on a 1.5-pt
> measurement decides nothing. **The home-term explanation was never actually
> refuted**; it was declared dead on a bar the data cannot support.

#### Step 2 — the dispersion hypothesis: half right, and my reading of it was wrong

The successor hypothesis was that a global ridge α over-shrinks strength
dispersion, worst where true dispersion is widest. A stretch on the **centred**
separation `d = (log λ_h − log λ_a)/2` tests it while holding home advantage and
the total goal rate fixed, so a positive result could not be step 1 returning
under another name.

**The separation-dependence is real.** The home calibration gap rises with how
lopsided the fixture is predicted to be — pooled slope **+5.66 [+1.7, +9.4]** pts
per unit d, sign flipping in away-leaning fixtures. *(Step 2 first reported
+6.58 from a `polyfit` over five bucket means with no interval. The per-match
regression with a block-bootstrap CI, added in step 3, is the figure to quote.)*

**The shrinkage explanation is not.** The deviance-optimal stretch is ~1.05
pooled, and **E0 wants the least of the four** — E0 ~1.02, E1 ~1.12, E2 ~1.13,
E3 **~0.95** (compression). Applying any arm leaves every gap where it was:
E0's home +1.77 → +1.74. The λs are correctly scaled *for goals*; the defect is
in the λ → outcome mapping, which convention 2's metric is structurally blind to.

> **Correction: "E0 is not special, it just has more spread" is refuted.** I
> claimed E0 sits further out on a curve everyone is on. The decomposition says
> otherwise:
>
> | | E0 | E1 | E2 | E3 |
> | --- | --- | --- | --- | --- |
> | **mean d** | **+0.102** | +0.101 | +0.101 | +0.102 |
> | sd(d) | 0.315 | 0.148 | 0.150 | 0.125 |
> | intercept | **+1.69** | −0.32 | −1.00 | −2.22 |
> | slope | **+0.79** | +6.85 | +12.22 | +15.73 |
>
> **Mean separation is identical in all four divisions**, so a slope acting on
> `d` cannot produce a division-specific mean gap — arithmetic, no interval
> needed. E0 has the *flattest* slope, not the steepest, and applying the E1–E3
> curve to E0's own fixtures predicts **+0.00** against **+1.77** measured.
> **E0's defect is a level offset; the separation slope lives in E1–E3.**
> `OPEN-6` (§3.3) is reinstated, not replaced.

#### The control step 2 should have carried, run afterwards

Step 2 produced a positive and shipped without the control §9.5 itself says
every gate needs. Run during a grounding pass, on synthetic outcomes, so it
spends nothing:

- **Null A** — goals simulated from the served λs, mapping correct by
  construction: slope **+0.10 ± 1.49**. The instrument returns zero when nothing
  is wrong, so the measured +5.66 is ~4σ out.
- **The P0-1 artifact sweep** — stratifying on a λ carrying log-noise, the exact
  trap P0-1 fell into. Home slope at noise 0.00 / 0.05 / 0.10 / 0.15 / 0.20:
  **−0.27 / −3.82 / −14.26 / −27.57 / −53.12**. **Monotonically negative at
  every level**, so λ noise can only ever *mask* a positive slope, never
  manufacture one. The finding is not the P0-1 artifact and is if anything
  understated.

**Do not skip this control if the slope is ever revisited.** It is the second
time this project has had to ask whether a clean monotone gradient was an
artifact of stratifying on an estimate, and the answer differed both times.

#### Step 3 — B2's calibration already exists. Wiring it in buys nothing.

The shipped tip rule runs on the **raw** pmf: `tips.py` reads `predictions`,
which `metrics.model_probs` fills uncalibrated. B2's walk-forward vector scaling
is built, tested and unused, and it halves the separation slope. Three arms —
raw, calibrated, and a magnitude-matched sham blind to every outcome.

| arm | changed | strike | vs shipped, **paired** |
| --- | --- | --- | --- |
| raw (shipped) | — | 72.49% | — |
| **B2 calibrated** | **18.42%** | 72.58% | **+0.088 [−0.410, +0.556]** |
| sham (control) | 18.42% | 67.76% | −4.733 [−5.08, −4.37] ✱ |

**It moves one recommendation in five and the strike rate does not move.**

**It relocates the miscalibration rather than removing it.** Pooled, delivered
minus claimed:

| | home | draw | away | `12` | `1X` | `X2` |
| --- | --- | --- | --- | --- | --- | --- |
| raw | +0.33 | +0.75 ✱ | −1.07 ✱ | −0.75 ✱ | +1.07 ✱ | −0.33 |
| calibrated | **+1.17 ✱** | −0.66 | −0.51 | +0.66 | +0.51 | **−1.17 ✱** |

Four resolved gaps become two — it fixes the draw, away, `12` and `1X`, and
**breaks home and `X2`, which were fine.** It does remove the separation
slope (+5.66 ✱ → +2.36, no longer resolved; E3 stays resolved at +12.13).

**And it makes E0 worse** — home **+1.77 ✱ → +2.37 ✱**, `X2` −1.77 ✱ → −2.37 ✱.
Expected, once E0's defect is known to be a level offset in the opposite
direction to what a pooled fit learns from E1–E3.

**Three things worth carrying forward:**

- **The published number is already honest.** Delivered minus claimed on the
  actual published pick is **−0.06 pts** raw (claims 72.55%, delivers 72.49%);
  calibrated it becomes +0.50. The market-level gaps largely cancel in the
  published mix. That is the number **B7** needs and it is currently fine —
  which is a different claim from "the head is calibrated", and the difference
  should not be blurred when B7 is closed.
- **The only real change is the mix**, and it is an owner decision rather than a
  measurement. `12` — the least specific thing the product can say — falls from
  **65.0% to 47.7%**, and `1X` rises 17.6% → 30.5%, at no cost in strike rate or
  honesty. `BACKLOG.md` B3 recorded the `12`-heavy mix as a knowing trade; this
  is the price of reversing it, and the price is approximately zero.
- **The control was weaker than it should have been.** The sham matched the
  18.42% change rate but moved the mix toward **H** (11.8 → 27.5), not toward
  `1X`. It decisively rules out "any perturbation of this size helps"; it does
  **not** isolate the `12`→`1X` confound §9.5 named. A properly matched control
  would move the mix the same way and differ only in carrying no information.

> **This undercuts §9.5's explanation, and the flag belongs there as well.**
> §9.5 attributed τ's strike gain to the fallback shifting `12` → `1X`. B2
> shifts that mix **three times harder** (17.3 points against τ's 5.7) and gains
> **+0.088, unresolved**. If the mechanism were the one §9.5 named, the larger
> shift should have paid more. **§9.5's verdict stands and its explanation does
> not** — τ is still declined, on the stronger ground that a 5×-wrong ρ was the
> best arm. Why strike rate was monotone in |ρ| is **unexplained and open**.

#### Where this leaves E0

**Real, marginal, and not adjudicable on E0's own data.** The gap is +1.77
[+0.05, +3.43] — barely resolved — step 1 puts any one-parameter fix at
t = 0.72–1.80, and the one correction already built makes it worse. The
home-term explanation is **reopened** by step 1's withdrawn verdict and is the
natural shape for a level offset, but it cannot be settled here.

**Do not** spend further configurations on E0 in isolation. If it is revisited,
the only defensible route is a **per-division intercept fitted pooled** — where
the information exists — with the geometry check from step 1 rerun against a
threshold the measurement can actually support.

### 9.7 The separation slope, reviewed — **2026-08-11. No measurement, no row.**

Full account in `SEPARATION_SLOPE.md`. §9.6 step 2's finding — the λ → outcome
mapping is miscalibrated in predicted separation, and goal deviance is
structurally blind to it — **survives review**. Its framing does not.

- ~~**The controls are not reproducible.**~~ **FIXED 2026-08-11 — see §9.9.**
  Null A and the P0-1 noise sweep existed **only** in §9.6's prose, which was
  §1.7's row-53 defect landing on the control that licenses the project's only
  live modelling finding. Both are now committed as `--step 4`, ledger
  `home_term_slope_controls`, **0 configurations**. The finding survives; two of
  §9.6's numbers do not.
- **On the home leg it is a step, not a gradient.** The five bucket means are
  −0.26, −0.86, −0.44, +0.08, **+3.12 ✱** — four flat and unresolved, the fifth
  jumping. Dropping the top quintile takes step 2's polyfit slope from **+6.58
  to +0.80**. Over-shrinkage predicts a smooth gradient; this is *the most
  lopsided fifth of fixtures under-predicts home wins by ~3.1 points, and the
  rest is calibrated*. Different mechanism, different fix. (Shape diagnostic on
  the interval-free estimator, not a test — §3 of the doc is explicit.)
  > **Weakened 2026-08-11 by §9.11.** The buckets are **unevenly spaced** in `d`
  > (0.172 / 0.082 / 0.082 / 0.169), so a pure gradient already yields a
  > flat-middle, jumping-ends profile; and the residuals from the full line are
  > **+1.08, −0.65, −0.77, −0.79, +1.13**, which is **convexity, not a step**.
  > All of it sits inside the bucket CIs, and §9.11 shows the corpus **cannot
  > resolve** gradient from tail effect. Read this bullet as "the linear reading
  > is unsafe", not as "it is a step".
- ~~**The away leg has never had an interval.**~~ **MEASURED 2026-08-11 —
  §9.10.** It is the larger error and the better-resolved one, exactly as this
  bullet predicted: **−6.12 [−9.8, −2.4] ✱ at 3.5σ** against home's +5.66 at
  2.7σ. What was not predicted is that **the two legs have different division
  profiles** — home rises monotonically E0 → E3, away peaks at E2 and collapses
  at E3.
- **"No stretch fixes it" was never tested.** `fit_stretch` minimises goal
  deviance by design, so step 2 refuted the *deviance-optimal* stretch, not all
  stretches. The sham control drives the pooled slope to **−14.65 ✱** carrying
  no outcome information, so a zero crossing exists — which also means zeroing
  the slope proves nothing. Price the zeroing stretch in deviance as a
  *diagnostic*; do not fit a fourth dial to it.
- **The slope and B13 are the same decision.** The published claim is honest
  (−0.06 pts) because `12` = home + away **cancels the two legs**, and `12` is
  65% of output. B13 cuts `12` to 47.7%, which stops the cancellation: honesty
  gap −0.06 → +0.50, pooled slope +5.66 ✱ → +2.36, **E3 still resolved at
  +12.13 ✱**. Recorded in `BACKLOG.md` B13.

Two smaller corrections: the per-division slopes are **uncorrected** across
eight cells and Bonferroni **has not been checked** (§1.5's precedent), and
scaled by each division's own sd(d) the E0-to-E3 gradient is **8×, not 20×**.
§9.6's "E0 is a level offset, the slope lives in E1–E3" stands, noting E1 does
not resolve. *(Bonferroni checked 2026-08-11 — §9.10. **Home E2 does not
survive it**, and §9.6's E1–E3 claim turns out to be home-leg only.)*

**Do not** attempt a fix before the linearity test. Three arms have moved this
dial and none bought strike rate; a fourth needs a reason the first three
lacked. *(Updated 2026-08-11 — §9.11. **The linearity test cannot be run.** It
was going to supply that reason and this corpus cannot resolve it, so the case
for a fix is now weaker, not stronger. Item 4, the zeroing stretch, is all that
remains.)*

### 9.8 Was the head tuned blind to the product? — **2026-08-11. No measurement, no row.**

Full account in `SELECTION_OBJECTIVE.md`. The claim under review: `H=400`,
`α=0.1`, the sot weight `0.3` and EC inclusion were each chosen on goal
deviance under the beat-the-book objective, convention 9 is exactly that
warning, and re-sweeping them under a loss sensitive to the λ → outcome mapping
is the highest-ceiling lever available. **The premise is right on the facts and
the conclusion does not follow.**

- **The counterfactual was already recorded.** `sweep.run` computes `ll_1x2` on
  every arm of every sweep (`sweep.py:183`), by design. "Chosen on deviance" is
  true of *selection* and false of *measurement*. Reading the column nobody had
  ranked costs 0 configurations.
- **Three of the four named parameters have both objectives choosing the same
  arm.** α: both argmin 0.05, the chosen 0.1 costs **+0.000018** ll_1x2. Both
  blend weights: deviance choice *is* the 1X2 argmin, checked twice in
  independent gates — and in h38 the 1-SE rule pulled 0.45 back to 0.30, which
  is the 1X2 optimum, so convention 2's shrinkage preference has been doing the
  1X2 objective's work for free. EC agrees on all three metrics and resolves.
- **`H` disagrees, it replicates across three sweeps, and it is a trade rather
  than a gain.** ll_1x2 wants ~300, deviance 400, ll_ou25 ~650 — **the two
  served markets sit on opposite sides of the deviance choice.** H 400 → 300
  buys −0.00029 on 1X2 and costs +0.00068 on O/U. Goal deviance is not blind to
  the mapping; it is the joint objective over both count margins and it lands
  between the two markets it induces. Re-selecting on 1X2 alone is §9.4's
  problem — it needs convention 2 amended, which is an owner decision.
- **The class of change cannot reach the defect that motivates it.** All four
  parameters move λ; the mapping is fixed at `rho=0`. The dedicated dial on that
  axis is `home_term.stretch`, whose own docstring declines the 1X2-fitted
  version on convention 2 grounds, and §9.6 step 2 showed the deviance-fitted
  version moves no gap. The untested arm is `SEPARATION_SLOPE.md` §5's
  zeroing stretch, **already pre-registered at ~1 configuration**.
- **The ceiling is one thousandth of a nat**, against a shots channel that
  shipped for −0.00179 and a market gap of +0.01410. Best case ~7% of the gap,
  half of it handed back on O/U.
- **The strike-rate exchange rate is unmeasured and the nearest datapoint is
  null.** B2's vector scaling *is* multiclass-log-loss optimisation, applied at
  the mapping level where leverage is highest: 18.42% of recommendations changed
  for **+0.088 [−0.410, +0.556]**. Three arms have now moved this mapping and
  none bought strike rate.

**Two things do survive, and neither is the objective.** **(a)** `H=400` was
swept at **α=1.0** and **before the sot channel shipped**, and h2 has never been
re-run on the served head — that is convention 9's real complaint and it applies
to goal deviance too. **(b)** **No hyperparameter arm anywhere carries an
interval on `ll_1x2`** — `sweep.py:177` bootstraps deviance only, in both `run`
and `compare` — so every 1X2 figure above is a bare point estimate and may be
noise. The machinery exists at `p3.py:168`.

**Do not** sweep the four jointly: 9 × 8 × 5 × 2 = **720 configurations**
against a ledger of 189.

### 9.9 The separation slope's controls, committed — **MEASURED 2026-08-11. It survives.**

Code `engine/eval/home_term.py --step 4`, tests `tests/test_home_term.py`,
results `docs/home_term_step4.json`, ledger `home_term_slope_controls` (probe).
**Runs 98 → 99, questions 55 → 56, configurations 189 → 189** — verified with
`trials.count_configurations` after the run rather than asserted before it.
`SEPARATION_SLOPE.md` §2 has the full account. **§9.7's item 1, and the first
thing in that document's recommended order.**

Every outcome is Poisson-resampled from the fitted λs, so this reads no real
match outcome and spends nothing — the same licence as `power.py`,
`h34_travel_power` and step 1. `test_the_controls_read_no_real_match_outcome`
makes that a property of the data rather than a claim about the code: corrupt
every `ftr` in the frame and every number is identical.

**Null A — the instrument is unbiased on both legs**, over 40 draws: home
**−0.01 ± 2.05** (sem 0.32), away **+0.00 ± 1.79** (sem 0.28). §9.6 step 2's
positive is not the instrument.

**Four things worth carrying forward:**

- **The published interval is honest, and nobody had checked.** §9.6 asked only
  whether the slope was zero under the null. Running `slope_ci` on every null
  draw makes coverage measurable: **4/80 false positives across both legs, 5.0%
  against a nominal 5%**, with the sd the interval implies matching the true
  null spread at 0.90 (home) and 1.00 (away). **The intervals in §9.6, §9.7 and
  step 3 are not too narrow.** This was a live possibility and it is now closed.
- **The headline is resolved by a second route, and it is smaller than §9.6
  claimed.** Step 2's pooled home slope of +5.66 is **2.77 null sd** — resolved
  without leaning on the block bootstrap at all, but well short of the "~4σ"
  §9.6's prose derived from ±1.49. **The true null sd is wider than that figure
  implied.** Real, and nearer the boundary than advertised.
- **The noise sweep reproduces its sign and not its magnitudes.** Home slope at
  noise 0.00 / 0.05 / 0.10 / 0.15 / 0.20 is **+0.39 / −1.55 / −6.75 / −13.64 /
  −20.45**, strictly decreasing as claimed, against §9.6's −0.27 / −3.82 /
  −14.26 / −27.57 / **−53.12** — **2.6× smaller at the top**. The load-bearing
  claim is the *sign*: λ noise can only **mask** a positive slope, never
  manufacture one. That holds. Per §1.7's row-53 precedent **§9.6's quoted
  magnitudes stay unattributable** and only this run's own contrasts count.
- **Six draws would have produced a false alarm, and nearly did.** The first run
  used this project's usual six. Draw 0 came in at +5.95 — the maximum of the
  eventual 40 — with an interval excluding zero, which reads as *the instrument
  fires under a correct-by-construction null*. Six draws also put the null sd at
  2.89 against a true 2.05. **Null A estimates a distribution, not a mean**, and
  the six-draw convention that serves `REST.md` H33 and `TRAVEL.md` H34 is the
  wrong size for it. `NULL_DRAWS = 40`.

**This licenses §9.7's item 2.** The away leg now has a reference distribution
before it is ever measured on real data — unbiased, null sd **1.79**, honest
intervals — where previously it had none.

### 9.10 The away leg — **MEASURED 2026-08-11. It is the larger error.**

Code `engine/eval/home_term.py --step 5`, results `docs/home_term_step5.json`,
ledger `home_term_away_leg` (gate, **3 configurations, 189 → 192**).
`SEPARATION_SLOPE.md` §9 has the full account. §9.7's item 2, licensed by §9.9.

**The accounting was an owner decision and is recorded as one.**
`SEPARATION_SLOPE.md` §8 item 2 named 0 or 1; the owner chose **3** — one per
arm, symmetric with `b2_calibration_in_product` costing the identical three arms
on the home leg. More than either figure the document named, which is §2.2's
inflating direction. The arm list is **one entry per arm, not per reported
cell**: 3 arms × 2 legs × 5 populations would have booked **30**, and
`count_configurations` sums `len(arms)` with no guard against that.
`test_the_away_leg_ledger_row_carries_one_entry_per_arm` now is the guard.

The shipped arm, both legs, with σ against a per-population null sd from 200
synthetic draws:

| leg | pooled | E0 | E1 | E2 | E3 |
| --- | --- | --- | --- | --- | --- |
| home | **+5.66** ✱ (2.7σ) | +0.79 | +6.85 | +12.22 ✱ | **+15.73** ✱ |
| **away** | **−6.12** ✱ **(3.5σ)** | −2.36 | −8.25 | **−14.80** ✱ **(3.3σ)** | −7.01 |

**Four things worth carrying forward:**

- **§9.7's prediction holds and the home leg reproduces exactly.** Away is the
  larger error and resolves more strongly. All five home figures match step 3 to
  the last decimal, which is what says nothing else moved.
- **The two legs have different division profiles, and nobody had looked.** Home
  rises monotonically E0 → E3. Away peaks at **E2** and **collapses at E3**
  (−7.01, unresolved, below E1). **§9.6's "the separation slope lives in E1–E3"
  is a home-leg statement**; on away it is an E2 statement. Any mechanism story
  has to explain both profiles, and none currently does.
- **Bonferroni costs a published cell.** Across the eight division × leg cells,
  **home E3 and away E2 survive; home E2 does not** ([−1.45, +25.97]).
  `SEPARATION_SLOPE.md` §1 published E2 as resolved and is corrected in place.
  §6 guessed the intervals were "wide enough that they plausibly do" survive —
  wrong, and §1.5's ≤3-days-rest precedent was the right one to cite. Pooled is
  a single pre-specified test and both legs resolve there.
- **The blind sham beats the real defect on both legs.** Home **−14.65
  (−7.1σ)**, away **+11.79 (+5.5σ)** — a temperature sharpener carrying no
  outcome information moves the slope *further* than the miscalibration actually
  present. This is the strongest form yet of `SEPARATION_SLOPE.md` §5's warning:
  **zeroing the slope is not evidence of having found the mechanism.**

**B2's calibration removes the resolved pooled slope on both legs** — home +2.36
(1.1σ), away −2.71 (−1.6σ) — while leaving E3 home (+12.13 ✱) and E2 away
(−10.85 ✱). No change to B13; §9.7's coupling note stands.

**Do not** read the away result as a new lead. Nothing here moved strike rate,
nothing was adopted, and §9.7's closing warning is unchanged: three arms have
moved this dial and none bought anything. **Item 3 — the linearity test — is
still the next thing, and it now has two legs to test rather than one.**

### 9.11 The linearity test — **CONTROLLED 2026-08-11. Do not run it.**

Code `engine/eval/home_term.py --step 6`, results `docs/home_term_step6.json`,
ledger `linearity_controls` (probe, **0 configurations, 192 unchanged**).
`SEPARATION_SLOPE.md` §10 has the full account. §9.7's item 3.

**The control refuted the test before it ran, for nothing.** §8 item 3 priced a
linearity test at ~1 configuration and said it would decide whether the
separation defect is over-shrinkage or a tail effect. **It would not.** Planted
at the level that reproduces the observed +5.66 home slope:

| leg | shrinkage implies | step implies | apart | null sd | σ |
| --- | --- | --- | --- | --- | --- |
| home | +0.20 | +6.38 | 6.18 | 4.24 | **1.46** |
| away | **+4.39** | **−3.57** | 7.96 | 4.76 | **1.67** |

Neither reaches 1.96, so **one real measurement cannot tell the two mechanisms
apart.** The statistic is sound — C1 returns +0.45 ± 4.24 (home) and −0.32 ±
4.76 (away) under a correct mapping, with coverage nominal at 5/80 — it simply
has no resolution here, because **the quadratic's null sd is ~2.8× the
linear's**. Asking about shape costs a lot more than asking about direction.

**Four things worth carrying forward:**

- **This is §1.12's lesson working, and it is the first time it has paid in
  advance.** H37 refuted B12's headline prediction *after* the plan was written
  and the stop rule had been mis-derived. Here the control ran first and alone,
  and killed the measurement before a configuration was spent.
- **The away leg is the better instrument and the two mechanisms have opposite
  signs on it** — shrinkage +4.39 against a step's −3.57, where on home both are
  positive. If this is ever revisited, **the away quadratic is the statistic and
  its sign is the read.** §3 of `SEPARATION_SLOPE.md` is a home-leg argument and
  would not have suggested it.
- **Closing it costs exactly the whole holdout.** σ scales as √n, so 1.96 needs
  **1.38× this corpus — 21,797 matches against 15,824, i.e. 5,973 more.** The
  three sealed seasons are 2,036 each, **6,108 total**: unsealing all of them
  crosses the threshold with **135 matches to spare**. The most expensive act
  available, spent on a diagnostic that decides no adoption. Unlike §1.4, where
  the same act does not reach the answer at all, here it technically does — and
  the answer is still not worth it.
- **§3's "flat then a step" reading is weaker than it looked, on two counts.**
  The five quantile buckets are **unevenly spaced** in `d` (0.172 / 0.082 /
  0.082 / 0.169), so a pure gradient already produces a flat-middle,
  jumping-ends profile. And the residuals from the full line are **+1.08, −0.65,
  −0.77, −0.79, +1.13** — both ends high, which is **convexity, not a step**.
  Both sit inside the bucket CIs. Corrected in place in §3.

**The honest statement of the home leg is now weaker:** the gap rises with
predicted separation, and whether that is a gradient or a tail effect **is not
resolvable on this corpus**.

**This leaves §9.7 item 4 as the only remaining item** — the zeroing stretch,
priced in goal deviance. §10 confirms it does not depend on item 3.

### 9.2 The goal-line tails were validated for markets the product does not serve

**Not measured yet. This is the second-priority diagnostic and it blocks B4.**

`BACKLOG.md` B4 extends over/under to 0.5–5.5. The pmf's fitness for that was
established by two P0 results, and both were scoped elsewhere:

- **P0-1 closed "keep Poisson" on a variance ratio** — 1.0103 [0.9915, 1.0313]
  — which is a statement about dispersion near the mode. It is not a statement
  about tail fit at over 4.5 or under 1.5.
- **P0-3's caveat was filed as an Asian handicap problem.** \|margin\| ≥ 3 and
  ≥ 4 are over-predicted at 0.984 and 0.965, and the note reads *"those
  thresholds are the region most Asian handicap lines actually sit in"*. AH is
  not served and is deferred post-launch (§5), so the caveat went with it — but
  the same tail is what over 3.5 and over 4.5 are priced from.

**P0-1 also supplies the mechanism**, though not the magnitude. It showed that
λ estimation noise alone reproduces the λ-quartile dispersion gradient
(1.1550 / 1.0260 / 1.0148 / 0.9622) under a pure-Poisson null, which was
recorded as a reason *not* to read over-dispersion into the data. The corollary
was never drawn: **λ noise biases tail-line probabilities harder than central
ones**, because the tail of a Poisson pmf is convex in λ, and the lines B4 wants
to publish are exactly the tails.

> **Correction, 2026-08-10.** An earlier draft of this section said P0-1
> *measured* the served λ as carrying log-scale noise of **sd 0.20**. It did
> not. That figure is a parameter of P0-1's synthetic demonstration
> (`test_lambda_quartile_gradient_appears_under_a_pure_poisson_null`), chosen
> alongside a true log-λ sd of 0.33 to reproduce the observed gradient — a
> reliability of about 0.73. **The served head's actual `Var(log λ_h)` is
> 0.0453**, so sd-0.20 noise would imply 88% of its spread is error, which is
> absurd. The noise level the served λ really carries is **not measured
> anywhere**, and that strengthens rather than weakens B11: the tail bias cannot
> be reasoned about from a number that does not exist, so it has to be measured
> against realised results.

**And nothing downstream can catch it.** The five new lines are unpriced
(`PRODUCT.md` §2), so there is no CLV, no return and no market comparison — the
only honesty instrument available is claimed-versus-delivered against the
result. **That check should run before B4 ships, not after.**

Cheap: bucket by predicted probability at each of the six lines, per division,
on stored λs. No new fit, no new data.

### 9.3 §1.7's closing demerit does not count against a tipster

**Not a mis-context, a mis-priority.** `CHANNELS.md` and §1.7 close with *"it
also does not touch the book — §2.3 stands"*. That was the right thing to say to
a project trying to beat the book, and it is why a licensed, positive, unwritten
gate has sat behind hosting and surface work.

Under a tipster it is not a demerit at all. Shots + corners gains
**+0.0490 / +0.0540** split-half reliability over the shipped `goals+sot`,
against a NOISE control at −0.0008 — the same order as the addition that became
−0.00422 nats and shipped (§1.3). A better λ improves **every item on the
menu at once**: the 1X2 outrights, all three double chances (which are marginals
of the same joint), and all six goal lines.

**It is the largest measured prediction gain available to the product**, and the
argument that deprioritised it was an argument about a market that is switched
off. §1.7's own cautions stand unchanged — split-half reliability is not
deviance, and the per-side blend weight costs 2 configurations rather than 36.

### 9.4 OPEN-3's rejection was a single-head objection — weakest of the four

The season-boundary shrink helps lower-division O/U and degrades E0 1X2
(+0.00259 [+0.00121, +0.00389]), and §5 deferred it as *"not a global
hyperparameter"*. That is a constraint on a single head serving a single market.
A product that picks one item per match from a five-item menu can in principle
scope adoption per division and per market.

**Listed for completeness, and not recommended.** It would require amending
convention 2, it multiplies the configuration count by the number of
populations, and §1.7 is a better use of the same budget. Revisit only if §1.7
is done and the division asymmetry (§3.1) is still unexplained.
