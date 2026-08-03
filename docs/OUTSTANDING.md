# Outstanding

**Cross-thread tracker.** This file is the handover point between working
sessions on this project. A thread picking up work should read this first, and
should update it before finishing. Anything not written down here does not
survive the end of a session.

Last updated **2026-08-03**, at the end of the P2 session.

Companion documents, in reading order:
`SPEC.md` (methodology authority, includes refuted parts) →
`PLAN.md` (architecture, phases, open-decision register) →
`FINDINGS.md` (what was learned, assumed → true → changed) →
`MEASURED_AND_CLOSED.md` (P0 results with numbers) →
`P1_PLAN.md` (P1 pre-registration, left unedited) →
`BASELINE.md` (P1 results and the base score) →
`P3_PLAN.md` / `CALIBRATION.md` (calibration, ablation, the launch decision) →
`P2_PLAN.md` / `PLAYER_PRIOR.md` (the player prior, and why it is descoped).

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
| P4 / P5 / P6         | Not started.                                                         |

**Frozen base head:** `H400 / a0.1 / weekly / E0+E1+E2+E3+EC`, no season-boundary
shrink, no squad prior, COVID window embargoed from scoring. Artifact
`p1-36d44c72db18b384`. 233 tests pass. Gate ledger holds **51 recorded trials**.

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

### 3.2 How should the inflated trial count feed deflation?

51 trials, but they are not 51 independent hypotheses — they are ~13 distinct
questions asked up to 3 times each after defects were found. Treating re-runs as
independent trials over-deflates; treating them as one under-deflates.

One entry is explicitly post-hoc and labelled as such in the ledger
(`probe:h19_alpha_interaction`) — a hypothesis invented after seeing H17's
result. Whatever scheme is chosen must not treat it as pre-registered.

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
