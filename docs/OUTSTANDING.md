# Outstanding

**Cross-thread tracker.** This file is the handover point between working
sessions on this project. A thread picking up work should read this first, and
should update it before finishing. Anything not written down here does not
survive the end of a session.

Last updated **2026-07-28**, end of the P1 Track M session.

Companion documents, in reading order:
`SPEC.md` (methodology authority, includes refuted parts) →
`PLAN.md` (architecture, phases, open-decision register) →
`FINDINGS.md` (what was learned, assumed → true → changed) →
`MEASURED_AND_CLOSED.md` (P0 results with numbers) →
`P1_PLAN.md` (P1 pre-registration, left unedited) →
`BASELINE.md` (P1 results and the base score).

---

## 0. Where the project is

| phase                | state                                                                |
| -------------------- | -------------------------------------------------------------------- |
| P0 data spine        | Complete. Loaders, holdout guard, as-of harness, team bridge.        |
| P0 dispersion        | Complete and **re-measured on the corrected corpus** — §2.1.         |
| P1 Track M           | **Complete.** Base head frozen, base score published, all gates run. |
| P1 Track A (serving) | **Not started.**                                                     |
| P2 player prior      | Not started. Unblocked; ordering decision open (§3.1).               |
| P3 calibration       | Not started.                                                         |
| P4 / P5 / P6         | Not started.                                                         |

**Frozen base head:** `H400 / a0.1 / weekly / E0+E1+E2+E3+EC`, no season-boundary
shrink, COVID window embargoed from scoring. Artifact
`p1-36d44c72db18b384`. 154 tests pass. Gate ledger holds **41 recorded trials**.

---

## 1. Blocking / do first

### 1.1 The entire P1 workstream is uncommitted

`git status` shows every P1 module and test as untracked, plus modified
`build.py`, `PLAN.md`, `.gitignore`, `test_seasons_and_db.py` and the five
replaced 2015-16 CSVs. **Nothing from this session is in git.**

Untracked: `engine/eval/{metrics,walkforward,bootstrap,sweep,p1}.py`,
`engine/serve/`, `tests/test_{metrics,walkforward_harness,bootstrap,sweep,artifact}.py`,
`docs/{BASELINE,P1_PLAN,OUTSTANDING}.md`, `docs/p1_results.json`.

A single commit for the P1 head plus a separate one for the 2015-16 data fix
would keep the data correction independently revertable.

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

## 3. Decisions awaiting the owner

### 3.1 P2 ordering — E3-first or E0-first?

Deferred once already ("note it now, decide in P2"). The evidence got stronger,
not weaker, so it is worth revisiting before P2 starts.

| division | share of the market's edge the base head captures |
| -------- | ------------------------------------------------- |
| E0       | 0.89                                              |
| E1       | 0.62                                              |
| E2       | 0.64                                              |
| E3       | **0.51**                                          |

And the National League gate found that clubs promoted out of EC are predicted
**0.058 nats better** when the fit has seen their EC matches — roughly fourteen
times the size of the entire E0 improvement P1 achieved.

**Against E3-first:** the Premier League is the product, and lower-division
player data is the weaker source (NL pre-2018-19 has slug IDs that are not
cross-division joinable).

### 3.2 How should the inflated trial count feed deflation?

38 trials, but they are not 38 independent hypotheses — they are ~10 distinct
questions asked up to 3 times each after defects were found. Treating re-runs as
independent trials over-deflates; treating them as one under-deflates.

No decision needed until P6, but it should be made **before** the holdout read,
in writing, not after seeing the result.

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
3. `predictions` table writer — λ stored raw, pmf-derived 1X2 + O/U, version
   string, information-set tag, served-at.
4. `web/` — SvelteKit fixture cards.
5. `paper_bets` writer — flat stake, EV vs **raw `1/odds`** (vig-inclusive).
6. `services/csv_grader` — weekly result grading + retrospective CLV.

### 4.2 P3-lite calibration (Week 3 scope)

Per-population Platt recal fitted from stored λs with the poison test; OPEN-6
interaction test (§3.3); CLV harness de-vigging PSCH with AvgCH fallback,
backtested on dev seasons.

### 4.3 Opening-weekend runbook

Not written. Launch checklist per SPEC §6: flags off, dry-runs, append-only
everywhere.

---

## 5. Deferred by decision (not forgotten)

| item                              | where it went                     | why                                                                                                                                                  |
| --------------------------------- | --------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| **OPEN-2** form leg               | In-season                         | H2 put the decay optimum at 400 days, the opposite end of the timescale axis from where a short-memory leg lives.                                    |
| **OPEN-3** season-boundary shrink | P4, as a population-specific gate | Helps lower-division O/U, degrades E0 1X2 (+0.00259 [+0.00121, +0.00389]). Not a global hyperparameter.                                              |
| **OPEN-4** stakes definition      | P4                                | Needs as-of league-table reconstruction.                                                                                                             |
| Market-value snapshot             | Live inference only, if ever      | Single undated Transfermarkt-style snapshot; excluded from every backtest path.                                                                      |
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
