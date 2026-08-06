# baba.vanga.premier — design specification

> **STATUS BANNER — added 2026-08-06. Read before anything below.**
>
> The line that stood here — *"DRAFT for re-review. Nothing built. No code
> written."* — was written 2026-07-28 and has been wrong for over a week. **The
> system is built**: P0–P4 complete, a frozen head serving, 357 tests passing,
> and 76 recorded gate-ledger runs. `OUTSTANDING.md` is the current state; this
> file is the *methodology authority and the historical record of what was
> assumed*, which is a different job.
>
> **This document contains refuted parts, deliberately kept.** The major ones,
> so nobody re-derives them:
>
> | SPEC section | what happened |
> | --- | --- |
> | §2.4 draw deficit "larger at lower λ" | **refuted** — pooled +0.90 pts, and E0 is +0.01 (`MEASURED_AND_CLOSED.md` P0-2) |
> | §2.4 Asian-handicap / correct-score veto | **lifted** — margin dispersion 0.9909 (P0-3) |
> | §3.2 half-life window [100, 300] days | **refuted** — optimum is **400** (`BASELINE.md` §1) |
> | §3.3 player-prior cold start | **refuted** — no such population exists (`PLAYER_PRIOR.md`) |
> | §3.6 kickoff slot + four analogues | **closed** — slot unresolvable, rest and travel bounded nulls, congestion and stakes blocked (`TOD_SLOT.md`, `REST.md`, `TRAVEL.md`) |
> | §3.7 substitute shots for the target | **refuted as written** — it is a *channel* at w = 0.3, not a replacement (`SHOTS_TARGET.md`) |
> | §3.8 meta-label | **planned, not run** — `P5_META_PLAN.md` |
>
> OPEN-1 through OPEN-9 are resolved or reassigned in `PLAN.md` §3; do not read
> their status from this file.

Every quantitative claim about the
gtleague(a separate prediction) engine is sourced to a doc in that repo (§Appendix A); every claim
about the input data is sourced to `data/notes.txt` (football-data.co.uk key)
or flagged as an assumption to be confirmed.

Nine decisions are open and marked **OPEN-n**. OPEN-1 is blocking for the
player layer and should be resolved before Phase 2 is scoped.

Purpose: predict 1X2 and Over/Under for the four English professional
divisions, reusing the methodology of the GT Leagues esoccer engine
(`../baba.vanga.gtleague`) where it transfers and explicitly refusing it where
it does not.

---

## 0. Scope and inputs

Two sources, radically asymmetric in how well understood they are.

### 0.1 Match + odds data — football-data.co.uk (well specified)

Divisions E0 (Premier League), E1 (Championship), E2 (League One), E3 (League
Two), 2010–11 through 2025–26 complete.

|                    |                                  |
| ------------------ | -------------------------------- |
| Matches per season | 380 + 552 + 552 + 552 =**2,036** |
| Seasons            | 16 complete                      |
| **Total corpus**   | **~32,600 matches**              |

Confirmed columns that carry design weight:

- **Results**: `FTHG`/`FTAG`/`FTR`, plus half-time `HTHG`/`HTAG`/`HTR`.
- **Kickoff `Time`** — the TOD analogue is at least testable (§3.6).
- **Match statistics** (where available): `HS`/`AS` shots, `HST`/`AST` shots on
  target, `HC`/`AC` corners, `HF`/`AF` fouls, `HO`/`AO` offsides, cards,
  `Referee`, **`Attendance`**.
- **Odds, pre-closing AND closing.** The closing set is the same schema with a
  `C` infix (`B365CH`, `PSCH`, `AvgCH`, `MaxCH`). Pinnacle (`PSH`/`PSCH`) and
  market `Avg`/`Max` are both present.
- **Odds collection timing, stated in the source notes**: _"weekend games are
  collected Friday afternoons, and on Tuesday afternoons for midweek games."_
  This is load-bearing — see §4.
- **Over/Under: the 2.5 line only** (`Avg>2.5`, `P>2.5`, `Max>2.5`, and closing
  equivalents). There is no line ladder.
- **Asian handicap** present (`AHh`, `AvgAHH`/`AvgAHA` and closing).

Four consequences fall straight out of that list:

1. **O/U is a single-line market.** gtleague prices a 2.5/3.5/4.5/5.5/6.5
   ladder and its recal layer exists largely to handle per-line miscalibration
   with a hierarchical shared slope across lines (docs/RECAL_SERVING.md). Here
   there is one line. Recal collapses to a per-population Platt fit with no
   hierarchy, and the tail-line problem — the original motivation for that
   whole layer — **does not exist**. This is a genuine simplification, not a
   deferral.

Developer Note (There is one line in the data but there will be multiple lines for the betting company for both over/under. That is 0.5 to 5.5/6.5)

1. **CLV is computable today.** Pre-closing and closing prices are both in the
   file. §5.1 makes this the primary metric, and it is available from day one
   rather than being an aspiration.
2. **There is no xG.** My initial recommendation to fit against xG is
   withdrawn — the data does not contain it. The available substitute is a
   shots-based proxy calibrated from `HS`/`HST` (§3.7). Weaker than true xG,
   still materially lower-variance than goals.
3. **`Attendance` makes the COVID regime break measurable rather than guessed.**
   Empty-stadium matches are identifiable from the data itself; the home
   advantage regime split does not need hardcoded dates (§4.3).

### 0.2 Player / squad data — source unspecified

The brief says _"player statistics for each player in those teams (squad
composition) to date."_ Nothing in `data/` describes it. The entire player
layer's feasibility turns on one property:

> **OPEN-1 (blocking for Phase 2): is the player data per-match, or a
> current-state snapshot?**
>
> - **(a) Per-match appearances with minutes, 2010→now.** The player layer is
>   buildable as specified in §3.3, and as-of correctness is achievable.
> - **(b) Current squad rosters + career/season aggregate statistics.** Then
>   every statistic is contaminated by matches occurring _after_ any historical
>   prediction date. Used naively in a backtest it is guaranteed leakage of the
>   worst kind — it will produce excellent, entirely fictional results. Usable
>   only for slowly-changing attributes (age, position, physicals) with the
>   contamination stated, or not at all.
>
> Phase 2 cannot be scoped until this is answered. If the answer is (b), the
> honest response is to descope the player layer to an age/position prior and
> re-plan, **not** to use the snapshot and hope.

Secondary: **team-name bridging** between the two sources. football-data uses
its own short names with known variants (`Nott'm Forest`, `Sheffield Weds`,
`Middlesboro`). gtleague hit exactly this problem bridging sofifa to its club
table and reached only 79 of 106 clubs
(`memory/team-ratings-scraper.md`). Assume a hand-maintained bridge table,
assume it is the boring long pole, and assume unbridged teams must be
_excluded by name_, never silently dropped.

---

## 1. The governing constraint: the data regime is inverted

gtleague processed 100,802 matches in eleven months
(docs/H2H_FEATURE.md:18) and banks ~317 gradeable priced rows per day
(docs/META_LABEL.md:44). This project's **entire 16-year corpus is 32,600
matches** — under four months of gtleague throughput — and accrues ~2,036 per
season, i.e. **~5.6/day averaged and violently bursty** around weekends.

Everything downstream follows from that inversion.

**What is gained.** Walk-forward validation across 16 seasons is available
immediately. gtleague spent weeks waiting for gates to accrue and repeatedly
had to judge on sign tests at n where the standard error was 3–4 ROI points
(docs/META_LABEL.md:212). That constraint is lifted for anything measurable
retrospectively.

**What is lost, and it is the important half.** The thing that actually
protected gtleague from overfitting was never discipline — it was that fresh
data arrived faster than anyone could torture the old data. Here the same
32,600 rows will be re-queried for every gate ever run. The failure mode
changes from _under-powered_ to _over-fitted_, and the defences must change
with it.

The arithmetic that settles the point, transposed from
docs/META_LABEL.md:118 (resolving a 2-point ROI edge at 2σ needs ~7,000
selected bets):

| selection                              | bets/season | seasons to resolve 2pt ROI at 2σ |
| -------------------------------------- | ----------- | -------------------------------- |
| every match, all four divisions        | 2,036       | 3.4                              |
| 10% pick rate (gtleague's priced rate) | ~204        | **34**                           |

**A live ROI-confirmed edge is not reachable on any planning horizon.** Two
non-optional consequences:

1. **Deep-freeze 2023–24, 2024–25 and 2025–26** (~6,100 matches). Untouched by
   any gate, sweep, or exploratory query until one final read. Everything
   before is the development set.
2. **CLV becomes the primary metric** (§5.1). It removes outcome variance
   entirely and resolves roughly an order of magnitude faster than ROI.
   gtleague's doctrine §3 — _judge value in ROI, not hit rate_ — becomes here
   **judge value in CLV, confirm direction in ROI, use hit rate only as a
   diagnostic.**

Third consequence, methodological: because a fixed corpus is being reused,
adopt López de Prado's _other_ contribution alongside meta-labeling — backtest
overfitting control (PBO via CSCV, deflated performance statistics). Keep a
`model_runs`-style append-only ledger recording **every gate ever run against
the development set**, so the deflation has a real trial count to work from.
gtleague has this table but let it go stale (docs/META_LABEL.md:76 — last
write 07-14, no writer in the cycle). Here it is load-bearing, not
bookkeeping.

---

## 2. Transfer ledger from baba.vanga.gtleague

### 2.1 Ports verbatim — architecture and doctrine

This is the most valuable inheritance, and none of it is about features.

| Inherited rule                                                                                                                                        | Why it is domain-independent                                                                                                                                                                                                                                                                                  |
| ----------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **§1 Fit from stored λs, never from served probabilities**, and carry the poison test (invert every stored probability, assert the fit does not move) | Pure feedback-loop hygiene. It caught two distinct failures in gtleague — recal consuming its own output, and a pick screen reading superseded generations (docs/RECAL_SERVING.md, docs/PICK_SCREEN.md). Any recal, stacker, or meta layer here needs it. "It only reads, it never writes" is not sufficient. |
| **§2 Populations are never pooled**                                                                                                                   | The axes differ (§4); the failure mode is identical. gtleague measured a Platt slope of 0.14 on one population and 1.30 on the other, and the pooled fit was near-identity that re-opened the exact hole recal existed to close (docs/POPULATION_SPLIT.md:28).                                                |
| **§4 Annotation, never mutation**                                                                                                                     | Screening layers write beside the pick;`pick`/`tier`/`confidence` stay pure model output. This is what keeps regen canaries verifiable. Inherit the live hazard too: the moment any UI or API _filters_ on a screen column, any breaker reading served outcomes begins measuring its own output.              |
| **§6 Re-sweep on regime change, never on a calendar, never automatically**                                                                            | Auto-refitting a hyperparameter on a flat plateau wanders on noise and pollutes every downstream fit window. Easier to honour here than there, because football's regimes are datable (§4.3).                                                                                                                 |
| Version string as serving contract; a new suffix per generation so results can be scored per generation                                               | gtleague can attribute any measurement to a generation because of this. Retrofitting it is not possible.                                                                                                                                                                                                      |
| One flag per feature, defaulting OFF; anything that deletes defaults off unconditionally with a`--dry-run` that reports regardless of the flag        | The 560k-row prune of 2026-07-26.                                                                                                                                                                                                                                                                             |
| Numbered forward-only migrations; annotation columns on prediction tables; side tables only when the shape genuinely differs                          |                                                                                                                                                                                                                                                                                                               |
| Offline fixture-backed tests; every rule must fire*and* self-skip; cold start passes everything; populations provably isolated                        |                                                                                                                                                                                                                                                                                                               |
| Docs keep the wrong hypothesis under an`ORIGINAL:` heading                                                                                            | docs/POPULATION_SPLIT.md:403 is the model: a dedup key that looked like 4.9 points of model decay and was an artifact. The wrong diagnosis is why the right one is trustworthy.                                                                                                                               |

### 2.2 Ports with modification

**Team strength — the joint decayed ridge Poisson.** gtleague's head is already
the right shape:
`log λ = c + home·is_home + att[entity] + dfn[opponent] (+ club + tod)`. Two
modifications:

- **Fit all four divisions in ONE model.** Promotion, relegation and the
  playoffs are the only edges linking divisions; a joint fit puts every team on
  a common scale automatically, and four separate fits do not. This also
  reframes a closed gtleague result rather than inheriting it: _competition as
  a GLM feature_ was measured null there because player and club entities
  absorbed it (TODO.md:610). Here it would be **unidentifiable** — within a
  season, division is collinear with team identity. Same action (do not add a
  division dummy), different reason, and the reason matters because the
  cross-division edges are what make a single scale possible at all.
- **The decay is ~40× slower.** §3.2 gives the arithmetic.

**Recal.** Keep the per-population Platt layer and the raw-basis fit rule.
Drop the per-line hierarchy — one O/U line (§0.1). Judge engaged maps with a
conditional evaluation, never against an unconditional walk-forward slope;
gtleague's live maps flatten to a ≈ 0.4 _by design_ on the book-conditional
population and that was mistaken for breakage more than once.

**TOD → rest, congestion, travel.** §3.6.

### 2.3 Do not port

**Head-to-head as pair identity.** docs/H2H_FEATURE.md is unusually explicit
about the precondition, and it is absent here.

|                                                     | gtleague              | E0–E3                                                                                     |
| --------------------------------------------------- | --------------------- | ----------------------------------------------------------------------------------------- |
| Median prior meetings for the same pair, at kickoff | **91**                | 2/season; ~32 across 16 years for a pair that never changed division, far fewer typically |
| Median rematch gap                                  | **~1 hour**           | ~5 months                                                                                 |
| Squad turnover between meetings                     | none (same operators) | complete, 3–4× over the window                                                            |

The pairwise term bought +2.85 AUC points there — _and survived a long-run
skill control arm_ (docs/H2H_FEATURE.md:68), which was the one confound that
could have killed it. That control is precisely what should be expected to eat
the entire effect here, because "prior meetings between these two clubs" is
mostly a proxy for a decade-old strength differential between teams that no
longer exist in any meaningful sense.

**Recommendation: run the gate anyway, with the skill control arm, and expect a
null** — the brief asks for H2H, so it earns a measurement and a line in
_Measured and closed_ rather than a silent omission. §3.4 gives the
reformulation that has real sample.

### 2.4 Closed gtleague results that must be RE-OPENED here

The _Measured and closed_ ledger (TODO.md:608) is domain-specific. Three
entries invert or need re-testing at English scoring rates (~2.6 goals/match
versus gtleague's 3.5–4.2).

| Closed there                                                                                                                                                                                                                                                                     | Status here                                                                                                                                                                                                                          |
| -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Distribution family for totals** — "Poisson is correct; stop re-opening this." Conditional `Var(total)/E[λ]` = 0.978, and side-level under-dispersion (0.84) cancels against positive residual correlation (+0.166) almost exactly at the total (TODO.md:614).                 | **Must be re-measured.** English mass sits in the 0-0/1-0/0-1/1-1 cells the Dixon–Coles τ correction exists for. Re-run all three of their measurements verbatim as Phase 0 — the harness design transfers, the conclusion must not. |
| **Draw mass** — realized 21.7% vs served 20.6%, real but not worth serving (best global inflation k=1.08 for −0.0004 logloss). "Do not add a Dixon-Coles diagonal." (TODO.md:638)                                                                                                | **Expect a larger deficit** at lower λ. Re-measure; the τ decision follows from it, not from precedent.                                                                                                                              |
| **Independence on the MARGIN** — independent Poisson over-disperses goal difference by ~29%; 3.4% mass on \|margin\| ≥ 5 against 1.1% realized. Immaterial for 1X2, but a _standing veto_ on Asian handicap, winning margin and correct score priced off that pmf (TODO.md:626). | **The veto probably transfers, and it now bites** — AH prices are in the dataset and will be tempting. Do not price AH off this pmf without re-measuring margin dispersion first.                                                    |

Two closed results that do transfer and save work: **club strength in
isolation / club Elo is redundant** given a joint fit (TODO.md:645) — do not
build a separate team Elo alongside the GLM; and **day-of-week carries nothing**
(docs/TOD_FEATURE.md:28), though here it is entangled with kickoff slot and
should be tested as one categorical.

---

## 3. Model architecture

### 3.1 Base head

One ridge Poisson GLM over all four divisions, time-decayed, refit per
matchday:

```
log λ_side = c + home·is_home + att[team] + dfn[opponent] + context
```

- `att`/`dfn` per team, ridge-penalised. Sweep α once; gtleague's 0.01 will not
  transfer — this design matrix is far sparser.
- Global `home` term. Team-specific home advantage is a plausible extension
  (Championship travel) but is mostly noise at 23 home matches/season; test it
  as an arm, do not assume it.
- Serve O/U 2.5 and 1X2 off the resulting pmf. **Nothing else** off that pmf
  until the margin measurement clears (§2.4).
- **OPEN-2**: gtleague blends `0.7·Poisson + 0.3·form` and measured that
  dropping the form leg costs 0.2–0.6 AUC points. Whether a separate form leg
  earns its place _here_ is genuinely unclear, because a decayed GLM already
  is a form model (§3.2). Test as an arm in Phase 1; default to no blend.

### 3.2 Decay — "team pace", and why it must be slow

The brief's instinct (_"these will be slow"_) is correct, and here is the
arithmetic behind it. Under exponential decay with half-life H days, effective
sample ≈ rate × H / ln 2.

|                                        | gtleague    | E0–E3                                |
| -------------------------------------- | ----------- | ------------------------------------ |
| matches per entity per day             | ~6.2        | ~0.15                                |
| half-life in use / implied             | 7 days      | —                                    |
| effective sample inside one half-life  | ~62 matches | —                                    |
| **H for equivalent effective sample**  | —           | **~287 days ≈ one season**           |
| Dixon–Coles' own fitted ξ ≈ 0.0065/day | —           | H ≈ 107 days (~23 effective matches) |

So the defensible sweep range is **H ∈ [100, 300] days**. Sweep once in Phase
1, record it in the ledger, freeze it, and re-sweep only on regime change.
gtleague's blend weight sits on a flat plateau and doctrine §6 exists because
auto-refitting it would wander on noise and pollute every downstream fit
window — the same applies here with more force, since a decay change is a
λ-regime switch that invalidates every recal window.

**The off-season problem, which gtleague cannot have.** Calendar decay across
a ~10-week summer break decays every team toward the prior while supplying no
new information. Three options:

- **(a)** Decay in _matches played_ rather than days.
- **(b)** Freeze decay during the off-season.
- **(c)** Let the calendar decay stand, and treat the resulting August
  uncertainty as exactly the window where the player-derived prior takes over
  (§3.3).

**(c) is the elegant answer and is the one I recommend testing first**, because
it makes the summer transfer window a _feature handoff_ rather than a
degradation — but it is a hypothesis, not a conclusion. **OPEN-3**: decide by
gate, not by taste.

### 3.3 Player layer — as a PRIOR, not an additive term

This is the highest-value transfer in the whole document and it comes from a
feature gtleague **built, gated, passed, and then shelved.**

Doctrine §7: the dominant effect of a club-pool rotation is _staleness, not
cold start_ — 82.5% of post-rotation rows were clubs that did have history,
decayed to ~1% weight, so the ridge pulled their coefficients to zero
(`memory/club-staleness-not-coldstart.md`). A **prior-anchored club ridge**
recovered 60–86% of the loss, +0.4 to +0.8 AUC points, with all 16 confidence
intervals excluding zero. It was not shipped because the warm-state control
said +0.03 and rotations there were rare — "ship only if rotations turn out
~6-weekly."

**English football rotates every August and every January, and 12 teams change
division every year.** The thing that repo put on the shelf for want of
frequency is the thing this project should ship first.

Design consequences:

- Player aggregates enter as a **prior on the team's `att`/`dfn` coefficient**,
  shrinking toward the squad-derived expectation in proportion to how little
  decayed team evidence exists. They do **not** enter as a competing additive
  term. A team with 46 matches of direct evidence needs no help; a
  newly-promoted team in August is nothing but prior.
- **Run the orthogonality pre-gate before building anything.** Regress fitted
  team `att`/`dfn` on the player aggregate. gtleague's sofifa pre-gate found
  R² ≈ 0.01 — orthogonal but useless. The likely failure here is the mirror
  image: R² high, meaning the aggregate re-derives what the GLM already knows,
  and the value lives only in the residual. Either result is cheap and saves
  the full gate.
- Measurement harness: the **gap-replay** design (docs/GAP_REPLAY.md).
  Inherit its corollary or the measurement is worthless — calibrate the
  synthetic gap against realized effective rows (`eff_rows_med`; the real
  event measured 4.9) or a near-zero ceiling gets measured on an effect that
  is genuinely there. And carry the **warm control arm**: without it, a
  cold-state-only fix reads as a general improvement.
- Gated on **OPEN-1**.

### 3.4 Head-to-head — reformulated as style, not identity

Pair identity has no sample (§2.3). The reformulation that does:

Project each team onto 2–4 style axes derived from data already present —
shots-per-match and shot conversion (`HS`/`HST`), fouls and cards as a press
proxy (`HF`/`HY`), corners as a set-piece-share proxy (`HC`) — and fit
interaction terms **on the axes**. That yields thousands of observations per
axis-pair instead of three, and it answers the brief's actual question
("how teams perform when paired with other teams") in the only form the data
can support.

It is a different feature from the one in the brief and needs its own gate,
against a base that already contains team strength. Prior: modest.
Two genuinely dyadic candidates worth the same harness, both low prior:
local derbies, and manager-versus-manager pairings.

### 3.5 Player pace

The most speculative item in the brief and the one I would descope first.

- **Age curves are the well-established part** — peak ~25–27, position
  dependent, decline accelerating past ~30. Model player ability as
  (career prior × age curve) with slow decay.
- **Within-season player form is mostly noise** at available sample. Even with
  per-match data, a striker takes ~30 shots across ten matches. Goal-based
  within-season form will be dominated by variance.
- Recommendation: build the age curve, be actively suspicious of anything
  faster, and require the fast component to clear a gate against a base that
  already has the age curve and team strength.

### 3.6 Context features — the TOD slot, replaced

docs/TOD*FEATURE.md holds up on its own terms: kickoff hour swings mean total
from 3.51 to 4.22, and the doc \_proves* it is not shift composition by
subtracting per-entity mean totals and re-testing the residual (ANOVA
p ≈ 5e-89). The effect is real because operator behaviour varies by hour.

Kickoff slot in English football is confounded with television selection (the
best matches get Sunday 16:30 and Monday night), midweek rotation, and season
phase. `Time` is in the data so it is testable — **keep their proof method,
replace the feature.** The residual test is the whole contribution: subtract
per-team expectation, then test by slot. If it survives it is a slot effect;
if not it was composition.

The stronger analogues, none of which gtleague can have:

- **Days since last match**, and the _differential_ between the two sides.
- **Fixture congestion**: matches in the trailing 14 days (Europe for E0
  sides, replays and playoffs elsewhere).
- **Away travel distance** — Championship, League One and League Two have real
  geography. Requires a stadium coordinate table.
- **Match stakes**: dead rubbers in May, relegation six-pointers, playoff
  races. No gtleague analogue at all, and a real football effect.

**OPEN-4**: stakes needs an operational definition (points-to-safety and
points-to-playoff at matchday N, computed from the table as-of, never from
final standings — that last clause is a leakage trap).

### 3.7 Shots-based intermediate target

No xG in the dataset. `HS`/`HST` support a calibrated proxy — fit
goals ~ f(shots, shots on target) and use the fitted expectation as a
lower-variance target for the strength and pace layers, while **evaluating
against goals**.

Availability is "where available" per the source notes, so coverage must be
audited by division and season before this is relied on. Lower divisions and
earlier seasons are the risk. **OPEN-5**: confirm `HS`/`HST` coverage for
E2/E3 across 2010–2016 before this becomes load-bearing.

### 3.8 Meta-label ("Le Prado")

Port docs/META_LABEL.md's design wholesale — it is the most directly reusable
document in the source repo — and port its warnings harder than its design.

- **Primary** = the full served pipeline; it owns the side.
- **Secondary** = P(primary correct | features known at decision time),
  consumed as an EV decision against the row's own break-even.
- **Training basis = all leans, never surfaced picks.** This is the structural
  defence against the survivorship loop: if the meta-model ever filters
  serving and is then retrained on served outcomes, it trains on its own
  survivors. Keep the basis at all-rows forever.
- **Break-even is `1/odds` — vig-inclusive.** gtleague's `implied_prob` column
  is de-vigged and conflating the two flatters every EV read by ~5 points per
  side (docs/META_LABEL.md:83). Whatever schema is built here, build the same
  trap awareness in: derive break-even from raw decimal odds.
- **Walk-forward by kickoff day with regime embargo**, never shuffled. Embargo
  season boundaries, transfer windows, manager changes, and the COVID window.
- **The finding to expect.** Probe C measured book-only AUC **0.5558 >
  full 11-feature 0.5516 > confidence-only 0.5416 > no-book 0.5388**
  (docs/META_LABEL.md:95). The meta-model's entire edge was reading the price.
  English football — especially E0 closing lines — is a far more efficient
  market than an esoccer book, so this risk is strictly higher here.
  **A book-feature ablation is a mandatory reported column on every meta
  gate.** If model-only AUC sits at chance, the artifact is a market follower
  with extra steps, and the correct action is to say so.
- Also inherited: their incumbent gate's `is_pick` carried a _negative_
  coefficient conditional on its own inputs — a fitted meta-model should
  **replace** a hand-tuned gate, not stack under it.

Where inefficiency plausibly survives, and therefore where to look: **E2/E3
over E0**, midweek fixtures, the Friday-afternoon pre-closing price before
sharp money arrives, and totals over 1X2.

---

## 4. Populations

Doctrine §2 is inherited; the axes are new.

### 4.1 Information set — pre-news vs closing

**This split is structural in the data, not hypothetical.** The source notes
state odds are collected Friday afternoon for weekend matches and Tuesday
afternoon for midweek. So:

|                  | timing                              | relative to team news |
| ---------------- | ----------------------------------- | --------------------- |
| pre-closing odds | Friday/Tuesday PM, ~T-1 to T-2 days | **before**            |
| closing odds     | at kickoff                          | **after**             |

Two different information sets, therefore two calibration populations, never
pooled. It also fixes the leakage rule: **a model predicting at the
pre-closing timestamp may not use any feature unknown at that timestamp** —
including lineups, and including anything derived from them.

Lineup leakage is the single most common way football models produce
excellent fictional backtests, and it has no gtleague analogue. The
20-minute publish lag in gtleague's walk-forward protocol is the generalizable
discipline: features come from the information set as of the decision, not as
of settlement.

### 4.2 Division

E0 through E3 differ in scoring rate, home advantage and — critically — market
efficiency. Separate recal populations. Note this is _not_ the same claim as
"division is a GLM feature" (§2.2): shared strength scale, separate
calibration.

### 4.3 Regime — measured, not assumed

`Attendance` identifies empty-stadium matches directly, so the COVID home
advantage break needs no hardcoded dates. Other datable breaks to embargo
across: VAR introduction in E0 (2019–20), the five-substitute rule, and each
season boundary.

### 4.4 What is NOT a population

Home/away is a model term. League/cup would be, but cup matches are not in
this dataset.

**OPEN-6**: whether E1/E2/E3 can share a recal population (thin per-division
n at 552 matches/season) or must stay separate. Decide by the same interaction
test gtleague used — `y ~ logit(p) * division` — not by convenience.

---

## 5. Evaluation and gates

### 5.1 CLV primary, ROI confirmatory

Per §1, ROI cannot resolve on any workable horizon. The metric stack:

1. **CLV against Pinnacle closing** (`PSCH`/`PSCD`/`PSCA`), de-vigged, as the
   primary go/no-go. Beating the closing line is the only edge statement this
   corpus can support at usable power.
2. **ROI at `Max`/`Avg` closing** as a directional confirmation with its sign
   reported and its standard error stated. Never as the gate.
3. **Hit rate as a diagnostic only.** gtleague learned this twice — a rule
   cleared a hit-rate bar (60.0% vs 64.4%) while standing down rows returning
   +14% ROI, because mean odds differ systematically between the buckets
   (docs/PICK_SCREEN.md, docs/VALUE_FLAG.md). Hit-rate comparisons are
   structurally blind to exactly the rule most likely to be wrong.
4. Calibration: Brier, reliability deciles per population, Platt slope.

### 5.2 Walk-forward protocol

Inherited from gtleague's standard protocol and non-negotiable: day-frozen
artifacts refit per matchday, cutoff-aware features, explicit publish lag,
paired bootstrap on identical rows for every ΔAUC claim with a 95% CI.

Every feature gate is measured **on top of the current served base score**,
never standalone. This is what made gtleague's H2H result trustworthy and its
sofifa result refutable.

### 5.3 Multiple-testing control

New requirement with no gtleague precedent (§1):

- Append-only ledger of every gate run against the development set.
- PBO/CSCV over the strategy set before any deployment claim.
- A gate that requires a _third_ look at the same rows is reported with its
  trial count attached, or not reported.

### 5.4 Holdout policy

2023–24 through 2025–26 frozen. Read once, at the end, by prior written
commitment as to what constitutes a pass. If the holdout is read and failed,
the honest options are to publish the failure or to start a new corpus —
**not** to re-tune and re-read.

### 5.5 Bands — a knowing deviation

Doctrine §5 says tier bands come from _served_ confidences with a
two-proportion z-test, never from the eval frame, and gtleague's 1X2 head
ships two bands rather than three precisely because lean→solid separated at
only z=1.4. At ~200 live picks/season that test is unavailable here for years.

**Bands will therefore be fit from backtest.** This is a deliberate deviation
from inherited doctrine, recorded here with the risk named — backtest bands
are an overfitting surface and belong under §5.3's trial count — rather than
being allowed to happen silently.

---

## 6. Serving and operational doctrine

Inherited from §2.1 without modification. The one gtleague hazard that does
_not_ transfer is its severity: this project has no live 5-minute scheduler, so
"anything on disk is effectively deployed" is not yet true. **It becomes true
the moment a scheduler is added, and the safety defaults belong in the design
before that happens, not after.** gtleague learned this by deleting 560k live
rows.

Persist per-cycle serving state from day one — recal parameters per
population, band definitions, the version string. gtleague's meta-label
plumbing audit found this family _unrecoverable after the fact_ and noted a
generation-contamination diagnosis that took days from residue and would have
taken minutes from snapshots (docs/META_LABEL.md:163). Append-only, flagged,
cheap.

---

## 7. Hazards ledger

| Hazard                                                           | Type                                | Defence                                                                 |
| ---------------------------------------------------------------- | ----------------------------------- | ----------------------------------------------------------------------- |
| **Lineup / team-news leakage**                                   | fatal, silent, no gtleague analogue | §4.1 information-set discipline; predict at the pre-closing timestamp   |
| **Player snapshot contamination** (OPEN-1b)                      | fatal, silent                       | Resolve OPEN-1 before Phase 2; descope rather than hope                 |
| **Standings-derived stakes computed from final tables**          | leakage                             | As-of table reconstruction only (§3.6)                                  |
| **Multiple testing over a fixed 32.6k corpus**                   | slow, invisible                     | §5.3 ledger + PBO; §5.4 holdout                                         |
| **Meta-model as market follower**                                | plausible-looking success           | Mandatory book ablation (§3.8)                                          |
| **Entity drift** — Wolves-2012 and Wolves-2025 share only a name | model spec                          | Decay slow enough to be useful, fast enough to forget: the §3.2 tension |
| **Team-name bridging failure**                                   | silent sample loss                  | Explicit bridge table; unbridged teams excluded by name and counted     |
| **`HS`/`HST` coverage gaps in E2/E3 early seasons**              | silent                              | OPEN-5 audit before §3.7 is load-bearing                                |
| **Pricing AH or correct score off the pmf**                      | wrong by inheritance                | §2.4 standing veto until re-measured                                    |
| **Recal feedback loop**                                          | wrong, self-reinforcing             | Raw-basis fit from stored λs + poison test (§2.1)                       |
| **Filtering on an annotation column**                            | breaker measures its own output     | Presentation-level enforcement; decide before any such flag is flipped  |

---

## 8. Phase plan

Each phase gates the next. Verification criteria are stated as checks, per
CLAUDE.md §4.

```
P0  Data spine
    - load E0-E3 2010->2026, bridge team names, audit stat coverage
    - as-of correctness harness; historical odds normalized (pre + closing)
    - re-run gtleague's three dispersion measurements at English lambda
    verify: zero leakage in a synthetic walk-forward; a stated tau decision;
            coverage table by division x season; holdout sealed

P1  Base head
    - joint 4-division time-decayed ridge Poisson; ONE decay sweep in
      [100,300] days, one alpha sweep, then frozen and logged
    - walk-forward harness with regime embargo; paired bootstrap
    verify: baseline AUC/Brier/logloss on O/U 2.5 and 1X2, per division;
            this becomes the base score every later gate sits on top of

P2  Player layer as prior anchoring          [BLOCKED on OPEN-1]
    - orthogonality pre-gate FIRST
    - prior-anchored ridge; gap-replay calibrated to eff_rows_med
    verify: August/January/promoted-team arms positive with CIs clear of
            zero AND a warm control arm near zero (cold-state fix, honestly
            labelled)

P3  Calibration and value
    - per-population recal (division x information-set); CLV harness
    verify: reliability deciles within tolerance per population; CLV sign
            and magnitude by division; ROI sign reported with its SE

P4  Context and the refusals
    - rest / congestion / travel / stakes, each gated on top of P1+P3
    - H2H gate WITH the skill control arm -- expect null, record it
    - style-axis interaction as the reformulation
    verify: each arm's CI; nulls written into Measured and closed with
            their numbers, not merely dropped

P5  Meta-label
    - all-leans basis, EV vs 1/odds, walk-forward with embargo
    verify: beats BOTH baselines (all leans, and the incumbent gate) on CLV
            with consistent sign across >=3 disjoint season windows, at
            volume >= 50% of the incumbent; book-ablation column reported

P6  Holdout read, once
```

**Scope recommendation, stated as a disagreement with the brief.** It lists
six model components. At 32,600 rows the marginal feature is far more likely to
be overfit than in a domain producing 100,000 matches a year. I would build
**two** properly — the joint decayed GLM (P1) and the player-prior anchoring
(P2) — and gate the rest hard, accepting that H2H and player pace may end up as
documented nulls. That is what gtleague's own ledger of nulls would predict:
of the features it explored, competition, club Elo, distribution family, draw
mass and team ratings all closed negative, and the ones that shipped were few.

---

## 9. Open decisions for re-review

| #          | Decision                                                                                       | Blocks          | Recommendation                                                                                                      |
| ---------- | ---------------------------------------------------------------------------------------------- | --------------- | ------------------------------------------------------------------------------------------------------------------- |
| **OPEN-1** | Player data: per-match with minutes, or current-state snapshot?                                | **P2 entirely** | Answer before scoping P2. If snapshot: descope to age/position prior, do not use aggregates                         |
| **OPEN-2** | Separate form leg on top of a decayed GLM?                                                     | P1              | Default to no; test as an arm                                                                                       |
| **OPEN-3** | Off-season decay: match-count units, freeze, or let it stand and hand off to the player prior? | P1/P2 interface | Test (c) first — it makes August a feature handoff — but decide by gate                                             |
| **OPEN-4** | Operational definition of match stakes                                                         | P4              | As-of table reconstruction; never final standings                                                                   |
| **OPEN-5** | `HS`/`HST` coverage in E2/E3, 2010–2016                                                        | P0 → §3.7       | Audit in P0; shots proxy is optional if coverage is poor                                                            |
| **OPEN-6** | Can E1/E2/E3 share a recal population?                                                         | P3              | Decide by`y ~ logit(p) * division` interaction test                                                                 |
| **OPEN-7** | Target market priority: O/U 2.5 first, or 1X2 first?                                           | P1 ordering     | **O/U 2.5** — single line, cleaner pmf, and gtleague's margin veto makes the 3-way head the more suspect of the two |
| **OPEN-8** | Is paper-trading/serving in scope at all, or is this a research artifact?                      | P6 and §6       | If research only, §6 is deferred and the scheduler hazards never arise                                              |
| **OPEN-9** | Does the frozen holdout include 2025–26, given it is the most regime-relevant season?          | §5.4            | Yes. Freezing the most relevant season is the point                                                                 |

---

## Appendix A — sources for every number used

From `../baba.vanga.gtleague`:

| Claim                                                                                                                                                                                                                     | Source                                                       |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------ |
| 100,802 matches, Aug 2025 – Jul 2026; 94 players; median 91 prior meetings; ~1h rematch gap; H2H +2.85 pts; skill control +0.67                                                                                           | docs/H2H_FEATURE.md:18, :68                                  |
| ~317 priced leans/day; book-only AUC 0.5558 > full 0.5516 > conf 0.5416 > no-book 0.5388;`is_pick` negative coefficient; ~7k selected n for 2pt ROI at 2σ; `implied_prob` de-vigged; family-3 serving state unrecoverable | docs/META_LABEL.md:44, :95, :99, :118, :83, :163             |
| Platt slope 0.14 priced vs 1.30 schedule; pooled fit near-identity; dedup key artifact worth 4.9 points                                                                                                                   | docs/POPULATION_SPLIT.md:28, :403                            |
| Mean total 3.51→4.22 by hour; residual ANOVA p≈5e-89; day-of-week null                                                                                                                                                    | docs/TOD_FEATURE.md:20, :22, :28                             |
| Poisson correct at high λ (var ratio 0.978); margin over-dispersed ~29%; draw deficit +1.13 pts; club Elo redundant; competition null                                                                                     | TODO.md:610, :614, :626, :638, :645                          |
| Staleness ≠ cold start: 82.5%, +0.4–0.8 pts, 16/16 CIs clear, warm control +0.03, not shipped                                                                                                                             | `memory/club-staleness-not-coldstart.md`, docs/GAP_REPLAY.md |
| sofifa bridging 79/106 clubs; pre-gate R²≈0.01                                                                                                                                                                            | `memory/team-ratings-scraper.md`                             |
| Hit-rate vs ROI blindness: 60.0% vs 64.4% while standing down +14% ROI                                                                                                                                                    | docs/PICK_SCREEN.md, docs/VALUE_FLAG.md                      |
| 560k-row prune, 2026-07-26                                                                                                                                                                                                | CLAUDE.md §The environment is live                           |

Derived here:

- 2,036 matches/season = 380 + 3×552; ×16 seasons ≈ 32,600.
- Decay equivalence: effective sample ≈ rate × H / ln 2. gtleague
  2×100,802/94 ÷ 347 days ≈ 6.2 matches/entity/day → ~62 effective at H=7.
  Football ~0.15/day → H ≈ 287 days for parity. Dixon–Coles ξ=0.0065/day
  → H = ln2/ξ ≈ 107 days.
- Seasons to resolve 2pt ROI at 2σ: 7,000 ÷ bets-per-season.
