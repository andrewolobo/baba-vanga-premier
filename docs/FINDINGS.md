# Findings

Everything established between the SPEC being written and P0 closing, in one
place. Written 2026-07-28.

Each finding is stated as *what was assumed → what is true → what changed*,
because in most cases the assumption was reasonable and the correction is only
interesting relative to it.

Companion documents: [SPEC.md](SPEC.md) is the methodology authority and is left
as the historical design record, including the parts this document refutes.
[PLAN.md](PLAN.md) carries the architecture and phase plan.
[MEASURED_AND_CLOSED.md](MEASURED_AND_CLOSED.md) carries the full numbers for
the three dispersion measurements summarised in §4.

---

## Contents

1. [Corpus shape](#1-corpus-shape)
2. [Match and odds data](#2-match-and-odds-data)
3. [Player data, and OPEN-1](#3-player-data-and-open-1)
4. [Model findings](#4-model-findings)
5. [Engineering findings](#5-engineering-findings)
6. [Open decisions: current status](#6-open-decisions-current-status)
7. [What still worries me](#7-what-still-worries-me)

---

## 1. Corpus shape

Loaded, reconciled and stored. `python -m engine.ingest.build` reproduces it.

| division | league | matches | player-seasons |
| --- | --- | --- | --- |
| E0 | Premier League | 6,080 | 8,786 |
| E1 | Championship | 8,832 | 12,048 |
| E2 | League One | 8,680 | 12,136 |
| E3 | League Two | 8,720 | 12,109 |
| EC | National League | 8,610 | 12,266 |
| | **total** | **40,922** | **57,345** |

- **E0–E3 is 32,312 matches, not the SPEC's ~32,600.** The 288-match gap is the
  COVID-curtailed 2019-20 season in E2 (400 matches played, not 552) and E3
  (440). E0 and E1 completed that season; E2, E3 and EC did not.
- **Development set: 26,204 matches** across 13 seasons (2010-11 → 2022-23).
  **Holdout: 6,108 matches** across 2023-24, 2024-25 and 2025-26, sealed.
- 151 canonical clubs across 305 source aliases; **zero unbridged names** on
  either source.
- Scoring rate **2.606 goals/match** pooled across E0–E3 — as the SPEC predicted
  (~2.6), and well below gtleague's 3.5–4.2. That gap is the entire reason its
  closed results had to be re-measured rather than inherited.

---

## 2. Match and odds data

### 2.1 `Attendance` does not exist — the COVID regime needs dates after all

**Assumed:** SPEC §0.1 and §4.3 treat `Attendance` as present and make it
load-bearing: *"empty-stadium matches are identifiable from the data itself; the
home advantage regime split does not need hardcoded dates."*

**True:** the column is **absent from all 80 source files**. Nothing in the
corpus marks a behind-closed-doors match.

**Changed:** the COVID regime is a hardcoded date window, 13 Mar 2020 →
31 May 2021, in `engine/seasons.py:REGIMES`. The boundaries are at least
derivable from the data's own curtailment gaps rather than guessed. Recorded as
NEW-3.

### 2.2 Shot statistics are complete — OPEN-5 closes clean

**Assumed:** OPEN-5 flagged `HS`/`HST` coverage in E2/E3 across 2010–2016 as a
risk that could make the shots-based xG proxy unusable.

**True:** `HS`/`AS`/`HST`/`AST`/`HC`/`AC`/`HF`/`AF` and all card columns are
**100% populated for E0–E3 in every one of the 16 seasons.** Exceptions total
three individual matches, plus `Referee` missing from the 2012-13 E1/E2/E3 files.

**Changed:** the shots proxy (SPEC §3.7) has no coverage caveat anywhere in the
served divisions. OPEN-5 closed.

**But EC is thinner:** from 2016-17 onward the National League files carry no
shots, corners or fouls columns at all — 5,298 matches with stats absent by
construction. EC keeps cards and referee throughout.

### 2.3 CLV reaches back to 2012-13, and Pinnacle fails in the live season

**Assumed:** closing odds arrive with the 2019-20 schema change, giving a
handful of CLV-scored seasons.

**True, and better than assumed:** Pinnacle closing (`PSCH`/`PSCD`/`PSCA`)
exists **from 2012-13**, ~100% populated through 2024-25 in all five divisions.
Market-consensus closing (`AvgCH`, `MaxCH`, `AvgC>2.5`, `AHCh`) starts 2019-20.

So: **11 CLV-scored development seasons** on the Pinnacle anchor, versus 4 on
the market-consensus anchor. Since CLV is the primary metric (SPEC §5.1) and ROI
cannot resolve on any workable horizon, this materially increases what P3 can
actually establish.

**True, and worse than assumed:** **Pinnacle collapses mid-2025-26.** Pooled
E0–E3 coverage falls to 39.9%. Last closing price: E0 08/01/2026, E1 05/01/2026,
E2 25/11/2025, E3 and EC 25/10/2025, with gaps starting earlier still.

**Changed:** the CLV anchor is a fallback chain, not a column
(`engine/odds.py:CLOSING_1X2_PREFERENCE`): Pinnacle → market average → market
max. Built in from the start rather than patched when it bites. Live
paper-trading must not assume a Pinnacle price exists.

### 2.4 Two odds eras with no overlap

**True:** football-data replaced the Betbrain aggregates (`BbAvH`, `BbMxH`,
`BbAv>2.5`, `BbAHh`, `BbAvAHH`) with market `Avg`/`Max`/`AHh` at exactly the
2018-19 → 2019-20 boundary. **No season carries both.**

**Changed:** `engine/odds.py` maps both eras onto one field set, with the era
detected from the header rather than hardcoded to a season, so nothing
downstream branches on it. Header width grows 62 → 133 columns across the
corpus as bookmakers come and go, which is why every column is selected by name
and never by position.

### 2.5 Kickoff `Time` only exists from 2019-20

**True:** absent for 2010-11 → 2018-19, then 100% populated for all five
divisions from 2019-20 onward.

**Changed:** the kickoff-slot test that replaces gtleague's TOD feature
(SPEC §3.6) has **7 seasons of sample, not 16** — and only 4 of those are in the
development set. Weak. The rest-and-congestion features, which need only dates,
are unaffected and are the stronger analogues anyway.

### 2.6 EC exists and the SPEC does not account for it

**True:** 8,610 National League matches with **full odds parity** including
closing prices, but no match statistics from 2016-17.

**Changed:** loaded and stored, but not a served market. Whether EC enters the
joint strength fit is **NEW-1**, open, to be gated in P1. The argument for
including it is that E3↔EC promotion and relegation edges anchor the bottom of
the strength scale, and the strength head needs only goals — which EC has
throughout. It costs nothing to test.

### 2.7 Small traps

- `data/play_history/mapping.txt` **labels EC "Championship"**, duplicating E1.
  It is wrong; EC is the National League. The engine never reads that file —
  `engine/seasons.py` is the authority. The source file is left as-is.
- The 2025-26 E3 file has **133 header fields for 132 columns** — a phantom
  trailing empty column. A non-event given name-based selection.
- 1XBet columns appear in 2024-25 only.

---

## 3. Player data, and OPEN-1

### 3.1 OPEN-1 resolves to a case the SPEC did not enumerate

The SPEC offered two possibilities and called the question blocking for the
whole player layer: **(a)** per-match appearances with minutes, or **(b)** a
current-state snapshot whose every statistic is contaminated by matches
occurring after any historical prediction date.

**The answer is neither. It is (c): per-season, per-player, per-club aggregates
of completed seasons** — FBref "Standard Stats" tables, one file per season per
division, with stable 8-hex player IDs, minutes, and per-90 columns.

This matters because the two cases had opposite consequences and (c) sits
between them:

- It is **not** the (b) disaster. Each file is that season's real, closed
  record — not a present-day roster projected backwards. The SPEC's prescription
  for (b) (*"descope to an age/position prior, do not use aggregates"*) is not
  required, and the player layer survives.
- It is **not** (a) either. There are no per-match rows and no dates, so
  **within-season as-of correctness is unachievable at any resolution finer than
  a season.**

### 3.2 The binding as-of rule that follows

Implemented as `engine/asof.py:PLAYER_SEASON_RULE` and
`player_seasons_visible_at()`:

1. A prediction for a match in season N may read player files for seasons
   **≤ N−1 only**. Season N's file is embargoed whole until the season closes.
2. Player features refresh **once, at the season boundary**, and stay frozen for
   all of season N. No mid-season update is legitimate — which **removes the
   January arm** from P2's verification plan, since no in-season data exists to
   serve it.
3. **Season-N squad composition is itself leakage.** Knowing who plays for a
   club in season N requires reading the embargoed file, and doing so encodes
   both the transfer and the survivorship — you only see players who went on to
   actually play. The honest construction is a **minutes-weighted aggregate of
   the club's season N−1 roster**, accepting that summer transfers are invisible.

That third point is the subtle one. A pipeline that attached N−1 statistics to
an N−1-derived roster is correct; one that attached N−1 statistics to the roster
named in the N file would look almost identical, pass every obvious check, and
leak.

### 3.3 Coverage is now complete across all five divisions

The initial audit found Premier League data only. Championship, League One,
League Two and National League folders were added mid-session and audited:
complete 16-season sets, same schema family, verified against actual league
membership and season-to-season continuity.

**The Championship addition is the one that mattered.** E1 is the tier that
feeds Premier League promotion, and without it every club promoted into E0 had
no player prior — blunting exactly the arm P2 was designed to win. E1→E0 hex-ID
carryover is verified: a median ~54% of a promoted squad's IDs reappear in the
E0 file the following season.

### 3.4 Identity hazards

- **National League IDs before 2018-19 are name slugs, not FBref IDs** — 1,605
  rows across 2010-11 → 2017-18, carrying blank Nation/Pos/Age/Born and appended
  as a second alphabetical block. They collide on common names and are not
  stable across seasons. Loaded and marked `player_id_kind='slug'`; **never
  joinable**. Any EC player-prior work effectively starts at 2018-19.
- **Leading-zero IDs** appear in 14 of 16 Championship files. Numeric coercion
  drops the zero and silently forks one player into two entities across a season
  boundary. IDs are read as text and zero-padded to 8 characters.
- **One ID is unrecoverable**: Julien Faubert, 2010-11 E0, rendered by Excel as
  `5.26E+05`. The digits are gone. Marked `corrupt` rather than guessed at.
- **Mid-season transfers are two rows sharing one ID**, 20–68 per file. Never
  group by name: the Championship alone contains three distinct Paul Robinsons
  in one season.

### 3.5 Two datasets that are not what they appear

- **`premier-league-2-division-1/` is the U21 academy league**, not a senior
  competition — squads are academy sides, seasons run 18–26 games, and the
  league was founded in 2016. It maps to no football-data division. Two files
  were misnamed off-by-one (`202122.csv` held 2020-21; `202221.csv` held
  2021-22); renamed. Parked as a possible future youth-pipeline feature, on no
  current path.
- **`market-value/premier_league_players.csv` is a genuine case (b) snapshot** —
  a single Transfermarkt-style capture from ~June/July 2025, top-500-by-value
  rather than full rosters (14–47 players per club), no IDs, no dates, 11
  duplicate rows. **Excluded from every backtest path**; usable only for live
  2026-27 inference, if at all. It cannot even supply squad composition.

---

## 4. Model findings

Full numbers in [MEASURED_AND_CLOSED.md](MEASURED_AND_CLOSED.md). Measured on
24,167 development matches with out-of-sample λ from a walk-forward ridge
Poisson refit fortnightly, hyperparameters frozen rather than swept.

### 4.1 Poisson is correct for totals — and the mechanism differs from gtleague's

`Var(total | λ) / E[λ]` = **1.0130**, 95% CI **[0.9943, 1.0346]**. Interval
contains 1.0. Per division: E0 1.0222 · E1 1.0139 · E2 1.0136 · E3 1.0046.

The same conclusion as gtleague, reached a completely different way, and the
difference is load-bearing. They got 0.978 from two large effects cancelling —
side-level under-dispersion of 0.84 against residual correlation of **+0.166**.
Here both sides sit at ~1.0 individually and the correlation is **+0.0115**,
forty times smaller.

**English match sides are close to genuinely independent; gtleague's were
strongly coupled and merely looked independent at the total.** Anything relying
on side independence — and the margin pmf does — stands on far firmer ground
here than the shared headline number would suggest. Inheriting the 0.978 would
have carried a false picture of the structure underneath it.

### 4.2 The τ decision: do not add the Dixon–Coles diagonal

Four independent reasons, any one sufficient:

1. Fitted ρ = **−0.0146** with 95% CI **[−0.0283, +0.0005]** — contains zero.
2. Δ logloss on 1X2 is **−0.000093**. gtleague declined a correction worth
   −0.0004; this is four times smaller than what was already judged not worth
   serving.
3. Δ logloss on O/U 2.5 is **exactly zero, structurally.** Every cell τ touches
   (0-0, 1-0, 0-1, 1-1) has a total of 0, 1, 1 or 2 — all below the 2.5 line. No
   redistribution among them can move a 2.5 probability by any amount. **τ is
   incapable of affecting the market prioritised for launch.**
4. It does not fix what it exists to fix: applying the fitted ρ lifts predicted
   draws from 25.39% to 25.74% against 26.26% realised — closing about 40% of a
   gap already under one point.

### 4.3 The draw deficit is real, unexplained, and a lower-division phenomenon

Pooled deficit **+0.87 pts** (realised 26.26% vs expected 25.39%), CI
**[+0.32, +1.41]** — excludes zero. But it is not uniform:

| division | realised | expected | deficit | 95% CI |
| --- | --- | --- | --- | --- |
| **E0** | 23.44% | 23.66% | **−0.22 pts** | [−1.43, +0.96] |
| E1 | 26.91% | 25.69% | +1.21 pts | [+0.23, +2.24] |
| E2 | 26.65% | 25.51% | +1.15 pts | [+0.14, +2.15] |
| E3 | 27.18% | 26.19% | +0.99 pts | [−0.01, +2.07] |

**The Premier League has no draw deficit at all.** The effect lives entirely in
the three lower divisions at a consistent ~+1 point.

This is a *population* fact, not a distribution-family fact, and a score-cell
correction is the wrong shape of tool for it. It **feeds OPEN-6 directly**: E0
differs from E1–E3 on a measured axis before any calibration is fitted, which is
evidence against pooling them; E1–E3 look alike on the same axis. The natural
explanations are behavioural (game state late in low-scoring matches) and belong
in P4, gated on top of the P1+P3 base.

It also **refutes a SPEC expectation**: §2.4 predicted a *larger* deficit than
gtleague's +1.13 points at English scoring rates. The pooled figure is smaller,
and in the division with the lowest scoring variance it is zero.

### 4.4 The Asian handicap veto does not transfer — lifted

`Var(margin | λ) / E[λ]` = **0.9900**, CI **[0.9702, 1.0095]**.
`|margin| ≥ 5`: observed **1.374%** vs expected **1.365%**.

The sharpest reversal of the three. gtleague measured independent Poisson
**over-dispersing the margin by ~29%**, predicting 3.4% of mass on |margin| ≥ 5
against 1.1% realised, and made that a standing veto on Asian handicap, winning
margin and correct score.

§4.1 explains why it does not transfer: their veto was a downstream consequence
of the +0.166 residual correlation, which fattens the total but is *subtracted*
at the margin. With correlation near zero here, the mechanism that produced the
veto is absent.

**Caveat that is not a formality:** |margin| ≥ 3 and ≥ 4 are mildly
over-predicted (ratios 0.965 and 0.936). That is precisely the region most Asian
handicap lines occupy. The veto being lifted means the pmf is structurally sound
enough to price from — not that AH is ready to serve. An AH head still needs its
own calibration and its own gate.

### 4.5 A refuted hypothesis, kept

> **ORIGINAL (wrong): dispersion worsens at low λ, where English mass sits.**

Stratifying by predicted total produced a clean monotone gradient — **1.1434**
in the lowest quartile falling to **0.9531** in the highest — reading as exactly
the low-λ breakdown SPEC §2.4 anticipated.

**It is an artifact of stratifying on an estimate that carries error.** Matches
sorted into the low bucket are disproportionately those whose λ was
*under*-estimated, so they out-score their prediction and the ratio rises; the
high bucket is the mirror image.

Planting goals that are *exactly* independent Poisson and stratifying on a λ
carrying log-scale noise of sd 0.20 reproduces it almost exactly: quartiles
1.1550 / 1.0260 / 1.0148 / 0.9622, spread **+0.193** against the real **+0.190**.
Pinned as a permanent test.

**Corollary worth carrying:** the same noise inflates the *overall* ratio to
1.0229 under a pure-Poisson null — above the 1.0130 actually measured. The
headline figure is an **upper bound** on true over-dispersion, not a point
estimate of it. If anything the corpus is marginally *under*-dispersed.

---

## 5. Engineering findings

### 5.1 A silent corruption that row counts could never have caught

**The most important engineering finding of the session.** pandas hands out
`numpy.int64` from every nullable-integer column, and `sqlite3` does not
recognise numpy scalars — so it stored the **raw 8-byte buffer as a BLOB**. This
hit every integer column in both tables: goals, minutes, shots, `fthg`/`ftag`.

Row counts were perfect. The build reported success. Every reconciliation
against the audits passed. And `SUM()` over the affected columns silently
returned **0**.

It surfaced only because E0 minutes were checked against a *known quantity* —
20 clubs × 38 matches × 11 players × 90 minutes ≈ 418 team-90s per season — and
came back as 0.1.

**Fixed** by registering adapters globally in `engine/db.py`, and guarded
permanently by `engine.ingest.build.validate()`, which now fails the build on
out-of-band aggregates, plus a parameterised regression test.

**The lesson is in PLAN.md and worth repeating: row-count reconciliation is not
integrity. Assert on values against quantities known independently of the
pipeline.** Had this survived, every model in P1 would have trained on zeros
while every count in every report looked correct.

### 5.2 Mixed encodings

Match files are **cp1252**; player files are **UTF-8**. `King's Lynn` carries a
0x92 curly apostrophe that raises under UTF-8 decoding. The loaders differ
deliberately, and the bridge table carries the curly-apostrophe form.

### 5.3 Blank rows are not what they look like

pandas skips truly-empty lines before the loader sees them. The 24 rows dropped
from the real corpus are **comma-only rows** — a full set of empty fields, which
read as a row and would otherwise have become matches with no teams and no date.
Worth distinguishing, because the fixture that tests it has to contain the right
kind of blank.

### 5.4 The team bridge

**151 canonical clubs, 305 aliases** (152 football-data, 153 fbref), generated
by `scripts/build_team_aliases.py` and checked in at
`reference/team_aliases.csv`.

**Runtime does pure dictionary lookup — no normalisation, no fuzzy matching.**
The normaliser exists only as a one-off authoring tool whose output a human
reviewed once. This is what keeps `Oxford City` and `Oxford United` apart; a
fuzzy matcher would merge them, and both are real clubs that have appeared in
the National League.

Three many-to-one cases, all resolved against their season ranges:

| club | aliases |
| --- | --- |
| Telford United | football-data writes `AFC Telford United` (2011-12) **and** `Telford United` (2012-13 on) |
| Torquay | fbref writes `Torquay United` (to 2017-18) then `Torquay` (2019-20 on) |
| Kidderminster | fbref writes `Harriers` (to 2015-16) then `Kidderminster` (2023-24) |

### 5.5 File-shape traps

- **League One player files carry a `.txt` extension.** A `*.csv` glob silently
  drops the entire E2 tier. The extension lives in the division registry.
- Two files carry a **three-line preamble** instead of two
  (`efl-league-one/201112.txt`, `efl-league-two/201314.csv`). The header is
  located by scanning for the row starting `Rk,` rather than assuming a line
  number.
- `national-league/201213.csv` was originally a **byte-identical duplicate** of
  the 2011-12 file. Re-scraped and verified genuine against actual 2012-13
  Conference membership.

### 5.6 A structural distinction the SPEC did not draw: fitting is not measuring

Enforcing the holdout naïvely would make the engine unservable. Serving 2026-27
legitimately requires 2023-26 match data to know where teams currently stand;
refusing that is refusing to have a model. But those seasons must never reach a
*metric*, because that is what burns the holdout's ability to adjudicate.

So loaders return a `Corpus` carrying its `Purpose` rather than a bare
DataFrame:

- **`DEV`** — gates, sweeps, probes. Stops at 2022-23, and **raises** on a
  sealed season rather than filtering it out. Returning 13 seasons to someone
  who asked for 16 is how a holdout gets believed in but not enforced.
- **`LIVE`** — fits the served artifact, sees everything, and its corpus
  **refuses `for_measurement()`**.
- **`HOLDOUT_READ`** — requires a written reason and a database connection,
  because every unseal writes to the gate ledger.

The store carries the identical guard, since the database deliberately holds
sealed seasons. A seal enforced on the CSV path but open on the path people
actually use would be worse than no seal, because it looks safe.

---

## 6. Open decisions: current status

| # | Status |
| --- | --- |
| **OPEN-1** player data granularity | **RESOLVED — case (c)**, per-season aggregates. Player layer survives with the season-boundary rule (§3.2). January arm dropped |
| OPEN-2 separate form leg | Open. Test as a P1 arm; default to no blend |
| OPEN-3 off-season decay | Open. Test the hand-off-to-player-prior option first, decide by gate |
| OPEN-4 stakes definition | Open. P4; as-of table reconstruction only, never final standings |
| **OPEN-5** shot coverage | **RESOLVED — clean.** 100% across E0–E3, all seasons. No caveat on the shots proxy |
| OPEN-6 recal pooling | Open, **with new evidence.** The draw deficit is ~+1 pt in E1/E2/E3 and −0.22 pts (CI spanning zero) in E0. Prior shifts to "E0 separate, E1–E3 possibly poolable"; still decide by the interaction test in P3 |
| **OPEN-7** market priority | **DECIDED — both**, off one pmf, calibrated as separate populations |
| **OPEN-8** serving in scope | **DECIDED — yes.** Full stack including paper-trading at MVP |
| **OPEN-9** holdout | **DECIDED — three seasons sealed**, enforced at the loader rather than by convention |
| **NEW-1** EC in the joint fit | Open. Gate in P1. Costs nothing to test; the strength head needs only goals, which EC has throughout |
| **NEW-2** Championship player source | **RESOLVED.** Scraped, audited, verified. Player coverage complete across all five divisions |
| **NEW-3** COVID regime window | **RESOLVED by necessity** — date window, because `Attendance` does not exist |
| **P0 τ decision** | **CLOSED — do not add the Dixon–Coles diagonal** (§4.2) |
| **P0 AH/correct-score veto** | **CLOSED — lifted** (§4.4), with a calibration caveat |

---

## 7. What still worries me

Stated plainly, because the SPEC's own doctrine is that the wrong diagnosis is
what makes the right one trustworthy.

1. **The draw deficit is real and unexplained.** +1 point across three
   divisions, robust, and not fixed by the tool built for it. Until it has an
   explanation it is a known miscalibration sitting under every 1X2 price the
   engine will serve in E1–E3. It needs a P4 feature, not a pmf patch.

2. **The λ-quartile artifact will recur in a different costume.** It looked
   exactly like the SPEC's own hypothesis, which is the dangerous kind of
   wrong — a confirmatory-looking result nobody scrutinises. Every future
   stratification on a fitted quantity needs the same pure-null replication
   check before it is believed. That is now a standing hazard in PLAN.md.

3. **Kickoff-slot analysis has 4 development seasons of `Time`.** Underpowered
   for a real effect and a soft target for over-fitting. Rest, congestion and
   travel are the stronger analogues and need only dates.

4. **The player layer cannot refresh mid-season, ever.** Not a limitation of the
   implementation but of the data. August cold-start is genuinely served;
   January is not, and no amount of engineering changes that.

5. **`|margin|` 3–4 over-prediction sits exactly where AH lines live.** The
   veto is lifted on the family, not on the calibration. It would be easy to
   read "veto lifted" as "AH is free" and price straight off the pmf.

6. **Pinnacle's live collapse is unhandled beyond the fallback chain.** The
   fallback exists, but market-average closing is a materially different anchor
   from Pinnacle closing, and CLV measured against the two is not directly
   comparable. P3 needs to establish the offset rather than assume it is zero.

7. **Six trials are on the ledger and the corpus is fixed.** The count only goes
   up from here, and every future result carries the multiple-testing burden of
   everything run before it. That is what the ledger and the sealed holdout are
   for, and neither works if entries stop being written.
