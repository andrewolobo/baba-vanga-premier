# Outstanding

**Cross-thread tracker.** This file is the handover point between working
sessions on this project. A thread picking up work should read this first, and
should update it before finishing. Anything not written down here does not
survive the end of a session.

Last updated **2026-08-08**, after the deployment assessment (§4.4) — which
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
`P5_META_PLAN.md` / `META.md` (the meta-label — pre-registration with §1
reproducible as committed code, and the result: **a market follower**, where
BOOK's apparent edge turns out to be cross-book price dispersion rather than
forecasting, and `choice_mattered` is shown to have a hole) →
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
| P4 channels          | **Pre-gate run and positive — a gate is licensed, not written.** §1.7 |
| P5 meta-label        | **Run. Market follower — do not adopt.** §1.9.                        |
| Customer surface     | **Built to the owner's design — §1.11.** B6 done, B7 part done.      |
| Hosting              | **Planned and agreed, not executed** — `DEPLOY.md`. §4.4.            |
| P6                   | Not started. Not a launch gate — `DEFLATION.md` §8.                  |

**Frozen base head:** `H400 / a0.1 / weekly / E0+E1+E2+E3+EC / sot0.3` — the
shots channel adopted 2026-08-04 (§1.3). No season-boundary shrink, no squad
prior, COVID window embargoed from scoring. Artifact
`p1-3a38e9d6ef1ca7ee`. **437 tests pass** (2026-08-07; the 379 this line used to
quote was stale — re-run `pytest -q` rather than trusting it). Gate ledger holds **87 runs / 45
questions / at least 167 configurations** — the last is the number that feeds
deflation, and §3.2 explains why the other two mislead. **The audit in §8 added
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
