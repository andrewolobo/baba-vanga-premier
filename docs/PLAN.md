# baba.vanga.premier — architecture & implementation plan

Status: v1, 2026-07-28. Companion to [SPEC.md](SPEC.md). The SPEC remains the
methodology authority; this document records (1) discovery findings that
correct or resolve parts of the SPEC, (2) the decided open questions, (3) the
system architecture, and (4) the phased execution plan against the ~3-week
deadline to the 2026-27 opening weekend.

---

## 1. Decisions taken this session (owner-confirmed)

| Decision | Answer |
| --- | --- |
| MVP scope for opening weekend | **Full stack including paper-trading**: model + API + frontend + fixture ingestion + result grading + CLV tracking |
| OPEN-7 market priority | **Both** O/U 2.5 and 1X2 simultaneously, off the same pmf, calibrated as separate populations |
| Infra | **Local Windows + SQLite now**; repo structured (env-config, Docker-ready) so VPS + Postgres later is mechanical |
| OPEN-8 serving scope | Serving is in scope (implied by MVP choice); §6 of SPEC operational doctrine applies from day one |
| OPEN-9 holdout | **Freeze 2023-24, 2024-25, 2025-26** (6,108 E0–E3 matches). Dev set = 2010-11 → 2022-23 (26,204 matches). One pre-committed read at P6 |
| Fixtures/results source | **football-data.org free tier** (PL fixtures/results) + football-data.co.uk weekly CSVs for lower divisions, odds, and retrospective CLV grading |

## 2. Discovery findings (two Opus audits, 2026-07-28)

### 2.1 Match/odds corpus — corrections to SPEC §0.1

- **Corpus is 32,312 E0–E3 matches**, not ~32,600 (2019-20 E2/E3 COVID-curtailed:
  400/440 matches). Plus **8,610 EC (National League)** matches the SPEC ignores.
- **`Attendance` is absent from every file.** SPEC §0.1(4)/§4.3's plan to detect
  COVID empty-stadium matches from attendance is dead. Replace with **date-window
  embargo**: the curtailment boundaries are visible in the data itself
  (E2 last match 10/03/2020; 2020-21 largely behind closed doors → embargo
  window Mar 2020 – May 2021, hardcoded, documented).
- **OPEN-5 RESOLVED — clean.** `HS/AS/HST/AST/HC/AC/HF/AF/HY/AY/HR/AR` are 100%
  populated for E0–E3 in all 16 seasons. The shots proxy (§3.7) has no coverage
  caveat. (Exceptions: 3 individual matches; `Referee` missing from 2012-13
  E1/E2/E3.)
- **CLV reaches to 2012-13.** Pinnacle closing (`PSCH/PSCD/PSCA`) exists from
  2012-13 (~100% through 2024-25, all divisions) — 11 CLV-scored dev seasons,
  not the 1–2 the "closing starts 2019-20" assumption implied. Market-consensus
  closing (`AvgCH/MaxCH/AvgC>2.5`) starts 2019-20.
- **Pinnacle collapsed mid-2025-26** (last E0 close 08/01/2026; E2/E3 dropped
  out Oct–Nov 2025). CLV harness must anchor on `PSCH` **with `AvgCH` fallback**,
  and live paper-trading must not assume a Pinnacle price exists.
- **Odds-column era break at 2019-20**: Betbrain aggregates (`BbAvH`, `BbAv>2.5`,
  `BbAHh`) run 2010-11→2018-19; `Avg/Max/AHh` run 2019-20→now; no overlap
  season. Normalisation layer must unify these into one schema
  (avg_h, max_h, avg_over25, ah_line, …) with a source flag.
- **O/U odds before 2019-20 are Betbrain-era** (`BbAv>2.5`, `GB>2.5`,
  `B365>2.5`); closing O/U (`AvgC>2.5` etc.) only from 2019-20 → O/U CLV has 7
  scored seasons, 1X2 CLV has 14.
- **Kickoff `Time` exists only from 2019-20** (100% from then, all divisions).
  The TOD-slot test (§3.6) has 7 seasons of sample.
- **EC (National League)**: full odds parity with E0–E3 including closing;
  match stats (shots/corners/fouls) absent from 2016-17 onward. NEW-1 below.
- Traps: `data/play_history/mapping.txt` mislabels EC as "Championship" (fix);
  2025-26 E3 has a phantom trailing column; 1XBet columns exist in 2024-25 only;
  bookmaker column sets grow 62 → 132 over the corpus — load by name, never by
  position.
- **Team-name bridge = 108 distinct names E0–E3** (152 with EC), football-data
  short style (`Nott'm Forest`, `Bristol Rvs`, `Dag and Red`).

### 2.2 Player/squad data — OPEN-1 RESOLVED as (c)

Source is FBref "Standard Stats" per-season tables, **Premier League only**,
16 files 2010-11 → 2025-26 (all completed seasons), 8,786 rows, 2,780 distinct
players with **stable 8-hex FBref IDs** (last column, header-mangled).

**OPEN-1 = (c) per-season per-player per-club aggregates** — a case the SPEC
did not enumerate. Not per-match (a); not a contaminated snapshot (b). Columns:
identity + `MP/Starts/Min/90s` + `Gls/Ast/G+A/G-PK/PK/PKatt/CrdY/CrdR` + per-90
variants. No xG, no shots.

**Binding as-of rule for the player layer (P2):**

1. A prediction in season N may read player files **≤ N-1 only**. Season N's
   file is embargoed whole until the season closes.
2. Player-derived features refresh **once, at the season boundary**, frozen for
   all of season N. No mid-season update is legitimate — SPEC §3.3's January
   arm is dropped (no in-season data exists to serve it).
3. Season-N squad composition is itself leakage (the N file encodes transfers
   and survival). The honest construction: club prior = **minutes-weighted
   aggregate of the club's season-N-1 roster**. Summer transfers are invisible;
   accept it.
4. **Coverage: all five divisions E0/E1/E2/E3/EC** (see §2.3; E1 added and
   verified 2026-07-28, closing NEW-2). Every promotion/relegation boundary now
   has an N-1 player prior on both sides, including promoted-into-E0 — the arm
   P2 was designed to win. E1→E0 hex-ID carryover verified (median ~54% of a
   promoted squad's IDs reappear in the E0 file next season). Only residual
   gap: EC priors limited to 2018-19+ by the slug-ID problem.
5. Load hygiene: `header=1` (two header lines); **zero-pad IDs to 8 chars**
   (two IDs corrupted by numeric coercion in 201011.csv); mid-season transfers
   = 2 rows per player (3–22/season) — never `groupby(Player)` naively; five
   genuine namesake pairs — join on ID only.
6. FBref→football-data team bridge: 41 teams, 27 exact, 14 mapped (enumerated
   in the audit; closed set).

### 2.3 Lower-division player data (folders added, audited 2026-07-28)

Four subfolders under `data/player-stats/`, all FBref Standard Stats format,
same schema family as root (2 header lines, `Min`/`90s` present, 8-hex FBref
ID in the final column; pre-~2014 files merely lack the dead `Matches` column):

| Folder | Division | Seasons | Verdict (all re-audited 2026-07-28 after fixes) |
| --- | --- | --- | --- |
| `efl-championship/` | E1 | 16 (2010-11→2025-26) | Clean and complete. 12,048 rows, 99.97% real hex IDs, 2019-20 completed (Championship finished that season), squad membership + 18/24 season continuity + E1→E0 ID carryover all verified. |
| `efl-league-one/` | E2 | 16 | Clean. Files are CSV content with a `.txt` extension. |
| `efl-league-two/` | E3 | 16 | Clean. |
| `national-league/` | EC | 16 — `201213.csv` re-scraped and verified genuine 2012-13 Conference | 22–30% of rows in 2010-11→2017-18 carry name-slug pseudo-IDs (blank Nation/Pos/Age/Born, appended as a second alphabetical block) — not joinable identities; 100% clean hex from 2018-19. |
| `premier-league-2-division-1/` | — (U21 academy PL2) | 10 (2016-17→2025-26, complete — PL2 founded 2016) | Misnamed files renamed (`202122`→`202021`, `202221`→`202122`); contiguous set confirmed. Merged single-division PL2 from 2023-24. No senior-league use; possible future youth-pipeline feature, not on any current path. |

**Player coverage is now complete for all five football-data divisions.**
Cross-folder hash sweep: zero duplicate files; same-season squad sets disjoint
across all tiers in all 16 seasons.

Loader consequences (added to P0):
- Locate the header by scanning for the row starting `Rk` (two files have a
  3-line preamble: `efl-league-one/201112.txt`, `efl-league-two/201314.csv`);
  accept `.txt` as CSV — **a `*.csv` glob silently drops the entire E2 tier**.
- Read the ID column as string, zero-pad all-digit IDs to 8 chars — E1 has
  leading-zero IDs in 14 of 16 files (root E0 had 3 corrupted).
- Group by ID never by name (20–68 transfer-split rows per file; E1 confirms
  namesake collisions: 3 distinct Paul Robinsons in one season). One known
  hex+slug fork: Shaun Pearson, NL 2012-13 (two clubs, two ID forms).
- Treat NL pre-2018-19 slug IDs as unresolved identities, never
  cross-division joinable; tolerate blank Age/Born/Nation (slug rows, plus
  15–19 blank demographic rows in E1 2025-26).
- Club-name aliases within FBref across seasons: `Torquay United`↔`Torquay`,
  `Harriers`=Kidderminster. **`Oxford City FC` (NL 2023-24) is NOT Oxford
  United** — never fuzzy-merge those.

### 2.3b Market-value file — live-inference only

`data/market-value/premier_league_players.csv` is a **single Transfermarkt-style
snapshot ≈ late-June/July 2025**, top-500-by-value (not full rosters, 14–47
players/club), no IDs, no dates, 11 duplicate rows to dedupe, 72% exact-name
match to FBref. It is exactly the SPEC's (b) case: **excluded from every
backtest path; usable, if at all, only for live 2026-27 inference**, flagged
as such. Not on any critical path.

## 3. Open-decision register (updated)

| # | Status | Resolution / owner |
| --- | --- | --- |
| OPEN-1 | **RESOLVED (c)** | Per-season aggregates; as-of rule §2.2; P2 unblocked with reduced arms |
| OPEN-2 (form leg) | Open | Test as arm in P1; default no blend |
| OPEN-3 (off-season decay) | Open | Test (c) handoff first, decide by gate in P1/P2 |
| OPEN-4 (stakes definition) | Open | P4; as-of table reconstruction only |
| OPEN-5 (stat coverage) | **RESOLVED — clean** | No gap; shots proxy viable everywhere E0–E3 |
| OPEN-6 (recal pooling E1–E3) | Open | Decide by `y ~ logit(p) * division` interaction test in P3 |
| OPEN-7 (market priority) | **DECIDED: both** | Same pmf; separate calibration populations |
| OPEN-8 (serving in scope) | **DECIDED: yes** | Full stack incl. paper-trading at MVP |
| OPEN-9 (holdout) | **DECIDED: freeze 3 seasons** | 2023-24→2025-26 sealed; enforced in the loader |
| **NEW-1** EC in the joint fit? | Open | EC adds 8,610 matches + promotion/relegation edges anchoring E3's scale, at zero player/stat-proxy cost (strength head needs only goals). Default: include as a 5th division in the GLM, exclude from served markets. Gate in P1. |
| **NEW-2** Championship player source? | **RESOLVED** — owner scraped E1, audited clean 2026-07-28 (§2.3) | Player coverage complete for all five divisions; P2's promoted-into-E0 arm restored |
| **NEW-3** COVID embargo window | Decided by convention | Mar 2020 – May 2021 date window (attendance data does not exist); recorded in regime table |

## 4. Architecture

Monorepo. Mirrors gtleague's shape, smaller.

```
baba.vanga.premier/
├── data/                    # raw CSVs — read-only inputs, never written
├── db/
│   ├── premier.db           # SQLite (dev + local serving)
│   └── migrations/          # numbered, forward-only (001_..., 002_...)
├── engine/                  # Python package — research/model core
│   ├── ingest/              # CSV loaders (name-based cols), odds normalisation
│   │   │                    #   (Betbrain-era ↔ Avg/Max-era unified schema),
│   │   │                    #   team bridge, player loader (§2.2 hygiene),
│   │   │                    #   HOLDOUT GUARD (see below)
│   ├── features/            # decay machinery, context features, player prior,
│   │                        #   style axes; every feature cutoff-aware
│   ├── models/              # joint ridge Poisson head, (τ correction if the
│   │                        #   draw-mass measurement demands it), per-population
│   │                        #   Platt recal, meta-label (P5)
│   ├── eval/                # walk-forward harness (day-frozen refits, regime
│   │                        #   embargo, paired bootstrap), CLV calc
│   │                        #   (PSCH primary / AvgCH fallback), GATE LEDGER
│   │                        #   writer, PBO/CSCV
│   └── serve/               # artifact freeze/load, version strings, per-cycle
│                            #   serving-state snapshots
├── api/                     # FastAPI: /fixtures /predictions /book /health
├── web/                     # SvelteKit frontend
├── services/                # fixture_sync (football-data.org),
│                            #   csv_grader (weekly football-data.co.uk pull:
│                            #   results grading + retrospective CLV)
├── docs/                    # SPEC.md, PLAN.md, gate results,
│                            #   MEASURED_AND_CLOSED.md (nulls with numbers)
└── tests/                   # offline fixture-backed; rules fire AND self-skip;
                             #   cold start passes; populations provably isolated
```

**Holdout guard (structural, not procedural):** the loader refuses to yield any
E0–E3 row with season ≥ 2023-24 unless called with an explicit
`holdout_unseal=True` flag whose every use writes a row to the gate ledger.
The 2025-26 **player** file is likewise sealed (it is both holdout-adjacent and
the N-1 prior for live 2026-27 — the guard distinguishes `purpose="live"` from
`purpose="backtest"`).

**Core DB tables** (append-only where marked):

- `matches` — normalised corpus, unified odds schema, season/division/regime tags
- `teams`, `team_bridge` — canonical IDs; unbridged names excluded by name and counted
- `players`, `player_seasons` — FBref ID keyed
- `predictions` (append-only) — λs stored raw, pmf-derived probs for 1X2 + O/U,
  **version string**, information-set tag (pre-close vs closing), served-at
- `paper_bets` (append-only) — market, side, price at bet, stake basis,
  break-even = 1/odds vig-inclusive; graded columns written beside, never over
- `clv_grades` (append-only) — bet price vs de-vigged close (PSCH→AvgCH fallback), per population
- `gate_ledger` (append-only) — every gate/sweep/query against the dev set:
  hypothesis, arms, n, result, trial count; feeds PBO deflation
- `serving_state` (append-only) — per-cycle recal params per population, band
  defs, version, artifact hashes
- `model_runs` — artifact registry per generation

**Populations (recal + evaluation), per SPEC §4:** division (E0 | E1 | E2 | E3,
pooling of E1–E3 decided by OPEN-6 test) × information set (pre-close | closing)
× market (1X2 | O/U). Never pooled across axes. Regime table: COVID window
(NEW-3), VAR-E0 boundary (2019-20), five-sub rule, season boundaries — embargoed
in every walk-forward split.

**Serving flow (weekly cycle):**

1. `fixture_sync` pulls upcoming PL fixtures (football-data.org) + all-division
   fixtures/current odds from football-data.co.uk's fixtures CSV (verify
   availability in P0-app; fallback: manual entry UI in web/).
2. Engine refits day-frozen artifact (dev-set-trained hyperparams, frozen),
   serves 1X2 + O/U probs per fixture at the **pre-closing information set**,
   writes `predictions` with version string.
3. Paper-trade rule (MVP: flat-stake EV>0 vs available price; later P5
   meta-label replaces it — replaces, not stacks) writes `paper_bets`.
4. `csv_grader` pulls the updated football-data.co.uk CSVs post-matchday:
   grades results, computes CLV vs closing, writes `clv_grades`.
5. Frontend reads fixtures + predictions + book + running CLV/ROI per population.

**Config via env; SQLite behind a thin DAL** so the Postgres move is a
connection-string change plus migration replay. Dockerfiles from day one, run
locally without Docker.

## 5. Phased execution

Season 2026-27 opens ~mid-August (≈3 weeks). Two tracks run in parallel:
**Track M** (model/research, the SPEC's P0–P3) and **Track A** (app/integrations).
Track A is deliberately thin so Track M is never rushed — the SPEC's overfit
warnings outrank UI polish.

### Week 1 — P0 data spine + scaffold

**Track M status (2026-07-28): scaffold, loaders, holdout guard and as-of
harness are BUILT, tested and committed (`6c13a8e`).** 73 tests green.
Remaining for P0: the three dispersion measurements and the τ decision.

Facts established by building it, that the audits could not see:

- **Match files are cp1252, not UTF-8.** `King's Lynn` carries a 0x92 curly
  apostrophe that raises under UTF-8. Player files are UTF-8. Mixed-encoding
  corpus; the loaders differ deliberately.
- **The team bridge is 151 canonical clubs**, 152 football-data aliases, 153
  fbref aliases, generated by `scripts/build_team_aliases.py` and checked in at
  `reference/team_aliases.csv`. Runtime does pure dict lookup — no runtime
  normalisation, so an unknown name fails loudly instead of fuzzy-matching into
  the wrong club. Three many-to-one cases resolved: football-data writes both
  `AFC Telford United` (2011-12) and `Telford United` (later) for one club;
  fbref writes `Torquay United`→`Torquay` (2019-20) and `Harriers`→
  `Kidderminster` (2023-24). `Oxford City` and `Oxford United` stay separate.
- **The corpus reconciles exactly**: 40,922 matches (E0 6,080 · E1 8,832 ·
  E2 8,680 · E3 8,720 · EC 8,610), 57,345 player-seasons, **zero unbridged
  names on either side**, 24 comma-only rows dropped, 1,605 slug ids and 1
  unrecoverable id flagged.
- **A silent corruption was found and fixed by a value-level check.** numpy
  scalars reached sqlite3 unadapted, so every integer column stored as a raw
  8-byte BLOB: row counts were perfect and `SUM()` silently returned 0. Caught
  only because E0 minutes were checked against a known quantity (418 team-90s
  per season). Adapters are now registered globally and `engine.ingest.build.
  validate()` fails the build on out-of-band aggregates. **Lesson carried
  forward: row-count reconciliation is not integrity; assert on values.**
- Holdout enforcement needed a distinction the SPEC did not draw: **fitting is
  not measuring.** Serving 2026-27 legitimately requires 2023-26 match data.
  So `Purpose.LIVE` may read sealed seasons but its `Corpus` refuses
  `for_measurement()`; `Purpose.DEV` raises rather than silently filtering; the
  store carries the identical guard because it holds sealed seasons on purpose.

Added to the tree since §4: `reference/team_aliases.csv` (hand-maintained
bridge), `scripts/` (one-off authoring tools), `engine/store.py` (guarded
reads), `engine/ledger.py`, `engine/asof.py`, `engine/seasons.py`.


Track M:
- Repo scaffold, `pyproject.toml`, migrations 001-00x, tables above.
- Loaders: matches (name-based columns, era-unified odds, phantom-column and
  mapping.txt fixes), players (§2.2 hygiene), 108-name team bridge
  (hand-maintained, unbridged = excluded by name + counted).
- **Holdout guard in the loader**, tested.
- As-of harness: every feature declares its information set; synthetic
  walk-forward leak test (shuffle-future canary) in CI.
- **Re-run gtleague's three dispersion measurements at English λ** (SPEC §2.4):
  Var(total)/E[λ], draw mass vs independent-Poisson, margin dispersion.
  Output = the **τ (Dixon–Coles) decision** and the standing AH/correct-score
  veto status. Gate ledger's first three rows.
- Coverage table by division × season committed to docs (from the audits).

Track A:
- FastAPI + SvelteKit skeletons, `/health`, empty fixture list end-to-end.
- football-data.org client (PL fixtures); verify football-data.co.uk fixtures
  CSV for E1–E3 + current odds; decide fallback if absent.

Verify: leak canary green; τ decision written; holdout guard proven by test;
fixtures visible in the browser.

Status: leak canary green (a synthetic walk-forward over a decayed attack rate
catches one missing filter line at every matchday); holdout guard proven by
test including the store path; τ decision outstanding.

### Week 2 — P1 base head + serving path

Track M:
- Joint decayed ridge Poisson over E0–E3 (+EC arm per NEW-1):
  `log λ = c + home·is_home + att[team] + dfn[opponent]`.
- **One decay sweep H ∈ [100,300] days, one α sweep** on dev set only, via the
  walk-forward harness (day-frozen refits, regime embargo, paired bootstrap);
  frozen and ledgered. OPEN-2 (form-leg) and OPEN-3 (off-season decay) arms run
  here; NEW-1 EC-inclusion gate here.
- Baseline AUC/Brier/logloss for 1X2 and O/U 2.5, per division × information
  set — **the base score every later gate sits on top of.**
- Artifact freeze/load + version string; first real predictions served locally.

Track A:
- `/predictions` + `/fixtures` endpoints off `predictions` table; frontend
  fixture cards with probabilities; `paper_bets` writer with the vig-inclusive
  break-even rule.

Verify: baseline table per population committed; paired-bootstrap CIs on every
sweep decision; a 2026-27 fixture shows live model probabilities in the UI.

### Week 3 — P3-lite calibration + paper-trading loop + launch

Track M:
- Per-population Platt recal, **fit from stored λs, raw basis, with the poison
  test** (invert stored probs, assert fit unmoved). OPEN-6 interaction test →
  pooling decision for E1–E3.
- CLV harness: de-vig PSCH (AvgCH fallback), backtested CLV by population on
  dev seasons 2012-13→2022-23 — the dry-run of the exact code that will grade
  live paper bets.
- Reliability deciles per population within tolerance.

Track A:
- `csv_grader` service: weekly pull, result grading, retrospective CLV, book
  P&L per population in the UI.
- Serving-state snapshot per cycle; launch checklist (SPEC §6 defaults: flags
  OFF, dry-runs, append-only everywhere).

Verify: end-to-end rehearsal on a synthetic matchday (predict → bet → grade →
CLV renders); recal deciles in tolerance; **opening-weekend runbook written.**

### In-season (weeks 4+, gates in priority order)

- **P2 player prior (all divisions)** — orthogonality pre-gate first
  (regress fitted att/dfn on N-1 minutes-weighted aggregates); if it clears,
  prior-anchored ridge with gap-replay calibrated to realized effective rows +
  warm control arm. Arms: August cold-start (continuing clubs, warm control)
  and promoted/relegated clubs at every tier boundary including E1→E0 — the
  highest-value arm, now fully covered. EC arm limited to 2018-19+ by the
  slug-ID problem.
- **P4 context gates**, each on top of P1+P3 base: rest differential,
  congestion, travel (needs stadium coordinates table), stakes (OPEN-4, as-of
  tables), TOD slot (2019-20+ sample, residual method), **H2H with skill
  control arm — expect null, record it**, style-axis interactions.
- **P5 meta-label**: all-leans basis, EV vs 1/odds, walk-forward with embargo,
  **mandatory book-feature ablation column**; replaces the hand paper-trade
  rule only if it beats it on CLV across ≥3 disjoint windows at ≥50% volume.
- **P6 holdout read, once**, criteria pre-committed in writing before unsealing.

### Future integrations (design now, build later)

- **Results/fixtures API hardening**: paid tier or API-Football if lower-division
  live coverage disappoints.
- **Betting-company odds feed (multi-line O/U 0.5–6.5, per SPEC dev note):
  gated on the P0 dispersion measurements** — tail lines price off the pmf's
  tails, exactly where mis-dispersion bites; no ladder is served until the
  total-goals dispersion result clears, and AH/correct-score stay vetoed until
  the margin measurement clears. The gtleague BETPAWA_FEED.md is the reference
  implementation shape.

## 6. Standing risks

| Risk | Standing answer |
| --- | --- |
| 3-week full-stack is aggressive | Track A stays thin (no auth, no styling debt, manual-entry fallback); model discipline is never traded for UI |
| Lineup/team-news leakage | All serving at the pre-closing information set; no lineup-derived features exist anywhere yet |
| Fixed-corpus overfitting | Gate ledger from day one; PBO before any deployment claim; sealed holdout with loader-level guard |
| Live Pinnacle absence (2025-26 collapse) | CLV fallback chain PSCH → AvgCH → graded-when-CSV-lands is built into the harness, not patched later |
| Player-ID quality at the edges | All five divisions covered (§2.3); residuals: NL slug IDs pre-2018-19 (unresolved identities), blank demographics in E1 2025-26, leading-zero IDs corrupted by numeric coercion — all handled at the loader, tested |
| market-value snapshot leakage | Excluded from backtest paths at the loader level, same mechanism as the holdout guard |
