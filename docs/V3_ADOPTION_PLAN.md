# V3 adoption plan — the underdog +1.5 fallback (`confidence-v3`)

Written **2026-08-19**, after the owner decided to adopt B21's measured arm.
The measurement is done and lives in `BACKLOG.md` B21 (gate row 110, referee
probe row 111); **this is a build plan, not a gate** — no outcome is read, no
configuration spent, the ledger does not move. The plan's verification is
tests and a deploy checklist, not predictions.

**The rule being shipped** (measured 2026-08-19, `engine/eval/b21.py`):
the v2 rule with the underdog +1.5 Asian handicap added to the fallback
candidate set — outright favourite if ≥ **0.55**, else the likeliest of
`1X` / `X2` / `12` / `dog +1.5` at or under **0.85**, else the outright.
Floor, ceiling and the outright tier are untouched. Measured out of sample:
**77.86% strike vs 72.49%, +5.365 [+4.474, +6.260] ✱ paired**; publishes the
handicap in 63.8% of matches; claims under-state delivery by +0.95.

---

## 0. Design decisions (owner sign-off before Phase 1)

| # | decision | recommendation | why |
| --- | --- | --- | --- |
| D1 | **Side encoding in `tips.side`** | **`H+1.5` / `A+1.5`** (concrete team side), not the eval code's fav-relative `D+1.5` | Settlement becomes self-contained: side + final score → outcome, no join back to the prediction to recover who the underdog was. Mirrors how `1X`/`X2` already encode the side. The eval label maps exactly: model favourite home ⇒ `A+1.5`, favourite away ⇒ `H+1.5` — a test pins the equivalence to `b21.won`. |
| D2 | **Prices on handicap tips** | `best_price`/`avg_price` **NULL**, and `step_tips`' missing-price ATTENTION **must exempt structurally unpriceable sides** | No +1.5 price exists in the feed and none is derivable from 1X2 legs (unlike double chance). `settle_tips` already settles priceless tips (outcome never depends on a price). Without the exemption the cycle would flag ATTENTION on ~64% of tips every matchday — alarm fatigue that buries real gaps on the priced legs. |
| D3 | **Site wording** | `H+1.5` → “Brentford +1.5”, with the explainer “Brentford must not lose by 2 or more” | The call phrase names the team; the `callMeans` line carries the mechanics, same pattern as `1X`/`12` today. Owner may reword; the mapping lives in one place (`web/src/lib/api.js`). |
| D4 | **Referee alert threshold** | flag ATTENTION when the matchday mean model−referee gap on published handicap tips leaves **[−1.23, +0.77]** (historical −0.23 ± 1 pt), publication-window claims only | The probe's stability band (R5: seasons ranged −0.6 … +0.2). Recompute-on-demand from stored `fixtures.avg_*` — no new table. |
| D5 | **Switchover** | deploy between matchdays; **do not re-tip fixtures already tipped under v2 that day** | `RUNBOOK.md` §0's existing rule. Re-tipping *later* fixtures under v3 is allowed per schema (owner decision 2026-08-15); same-matchday double calls are not. |

---

## 1. Phase 1 — engine: one settlement truth, one rule truth

**Goal: the number the gate measured and the number the product settles
cannot drift** — the invariant B8 established via `selection._won`, extended
to a market `_won` cannot express (it reads `ftr` only; a handicap needs the
margin).

1. **`engine/eval/selection.py`: add `won_from_score(side, fthg, ftag)`** —
   settles every publishable side (`H A 1X X2 12 H+1.5 A+1.5`, plus `D` for
   completeness) from the final score alone. Internally derives `ftr` and
   delegates to `_won` for the existing five, so the two functions cannot
   disagree; handles the two handicap sides directly (`H+1.5` wins iff
   `ftag − fthg < 1.5`, `A+1.5` iff `fthg − ftag < 1.5`; half line — no
   push, no `void`).
2. **`engine/serve/tips.py`: the v3 selector.** `select()` gains the
   handicap candidate by *composing over the measured code*: compute
   `p_dog15` from the prediction's stored `lam_h`/`lam_a` via
   `score_matrix` + `b21.dog15_probs`, call **`b21.recommend`** (the exact
   function the gate ran), then map its `D+1.5` to `H+1.5`/`A+1.5` by the
   favourite's side. `RULE_VERSION = "confidence-v3"`. The `UNTIPPED` query
   gains `p.lam_h, p.lam_a`. `COMPONENTS`/`derived_price` untouched;
   handicap sides get NULL prices (D2).

**Tests (planted, no DB):**
- `won_from_score` vs `selection._won` agree on every non-handicap side ×
  every result (exhaustive).
- Handicap settlement truth table: 2-0 / 3-1 lose for `A+1.5`; 1-0, 0-0,
  0-1 win; mirrored for `H+1.5`.
- **Equivalence to the gate:** on simulated fixtures, `tips.select`'s v3
  picks and settlements equal `b21.recommend` + `b21.won` after the
  fav-relative → concrete mapping, match for match.
- v2 invariance: with the handicap candidate off, `select` output is
  byte-identical to today's (regression pin).

**Verify:** new tests pass; full suite green.

## 2. Phase 2 — migration 005

`db/migrations/005_tips_handicap.sql`, the 004 rebuild pattern (SQLite
cannot alter a CHECK): rebuild `tips` with
`side IN ('H','D','A','1X','X2','12','H+1.5','A+1.5')`, copy all rows
unchanged, recreate both indexes and the `UNIQUE (fixture_id, rule_version)`
key. Forward-only; v2 rows untouched.

**Verify:** migration test (fresh DB migrates; a `H+1.5` row inserts; an
unknown side still raises); existing migration tests green.

## 3. Phase 3 — grading, both feeds

1. `services/csv_grader.py`: `settle_tips` and `reconcile_tips` route
   through `selection.won_from_score(side, result["fthg"], result["ftag"])`
   instead of `_won(side, ftr)`. Both fields are already in every `result`
   dict (the O/U path uses them today). `services/bbc_results.py` needs **no
   change** — it settles through `csv_grader.settle_tips`.
2. **Note for the record:** handicap outcomes are *margin*-sensitive where
   1X2 outcomes are not — a BBC score wrong by one goal (2-0 vs 2-1) flips
   an `A+1.5` settlement while leaving `H` intact. `reconcile_tips` already
   exists to catch exactly this (§4.8); its test set gains a margin-flip
   case.

**Tests:** settle a planted `H+1.5`/`A+1.5` tip through `settle_tips` both
ways; reconcile flags a margin-only disagreement; a priceless handicap tip
settles with NULL P&L.

## 4. Phase 4 — cycle: `step_tips` and the referee

1. `services/run_cycle.py` `step_tips`: missing-price ATTENTION exempts
   `H+1.5`/`A+1.5` (D2); mix line in `step.detail` now shows the handicap
   share.
2. **Referee reconciliation** (the adoption condition): after publishing, for
   each handicap tip with stored fixture `avg_h/avg_d/avg_a`, fit market λs
   (`b21_referee.fit_market_lambdas`), compute market-implied `D+1.5`, and
   report the mean model−referee gap in `step.detail`; flag ATTENTION outside
   D4's band. Claims below 0.70 are excluded per the probe's condition (in
   practice v3 publishes almost none). Label in all output: **“derived from
   1X2 prices — a reference, never a price.”** No schema change: the gap is
   recomputable later from persisted `fixtures.avg_*` + `tips.model_prob`.

**Tests:** planted cycle test — a published handicap tip produces a gap line;
an out-of-band gap flags ATTENTION; missing odds on the fixture degrade to
“referee unavailable”, not a crash.

## 5. Phase 5 — API and site

1. `api/main.py`: docstrings/enumerations for `side` gain the two codes
   (`/tips`, `/tips/results`). **No logic change**: `/tips/record` already
   scopes its headline to the newest published `rule_version` and reports
   every version in `by_rule` (B16) — verify, don't rebuild.
2. `web/src/lib/api.js`: `callLabel` gains `'H+1.5': `${home} +1.5``,
   `'A+1.5': `${away} +1.5``; `callMeans` gains “{team} must not lose by 2
   or more goals” (D3 wording, owner may adjust). The per-version record
   table renders automatically once a second version exists (B16) — verify.
3. The site's honesty paragraph is the **owner's text and does not change**
   without their say-so (P7 precedent).

**Tests:** `cd web && npm test` — label cases for both codes; API smoke test
returns the new sides.

## 6. Phase 6 — deploy and switchover

Per `DEPLOY.md` / `RUNBOOK.md`: commit (with the re-exported ledger already
current — no gate here, nothing moves), `git pull` on the VM; `db.migrate`
applies 005 on the next cycle run. **Sequence (D5):**

1. Deploy on a day with no remaining untipped fixtures, after that day's
   cycle has run (or disable the timer for the window).
2. First v3 cycle: confirm in logs — migration applied; v3 tips published
   with handicap sides and NULL prices; **no ATTENTION from the price
   exemption**; referee gap line present and in-band.
3. First graded v3 matchday: confirm BBC settlement of a handicap tip, then
   football-data reconciliation a fortnight later settles quiet.
4. `/tips/record`: headline switches to `confidence-v3` (small n at first —
   the site shows per-version history, so the v2 record remains visible);
   site renders both codes correctly on `/`.

**Rollback:** revert the code deploy (`RULE_VERSION` back to v2). Migration
005 stays — it only *widens* the CHECK, v2 never emits the new sides, and
already-published v3 tips remain, settle, and are reported under `by_rule`
(append-only: **published v3 tips are never deleted**).

## 7. Documentation updates (same change, not afterthoughts)

- `STATE.md` “what ships”: rule line becomes v3 with the measured 77.9% /
  mix / honesty numbers; B21 row closes.
- `engine/serve/tips.py` docstring: v3 rule, measured numbers, the referee
  note.
- `RUNBOOK.md` §0: the bump note gains “migration 005 applies on first run”.
- `PRODUCT.md` §5: one paragraph — the fallback menu gained the handicap,
  measured under B21; strike/return caveats restated unchanged.
- `BACKLOG.md` B21: “adopted, see `V3_ADOPTION_PLAN.md`”; **B20 closes** as
  overtaken (the content-free `12`s are displaced; `12` falls to ~10% of
  output) — 0 configurations spent on it.
- `OUTSTANDING.md`: header entry on ship day.

## 8. What must not happen (inherited, restated for this change)

1. **No gate, no ledger row** — this plan reads no outcomes. The measured
   numbers quoted are rows 110–111; do not re-derive them casually.
2. **No backfill**: v3 tips exist only from deploy forward. Past fixtures
   are never re-tipped.
3. **No same-matchday double call** (D5 / `RUNBOOK.md` §0).
4. **The book stays off.** Nothing here touches `book.py` or `paper_bets`.
5. **The referee is a reference, never a price** — every surface that shows
   it must carry the label; it never enters selection.
6. **v2 history is never rewritten** — per-version record only.

## 9. Order of work and size

| phase | touches | size | blocked by |
| --- | --- | --- | --- |
| 1 engine | `selection.py`, `serve/tips.py`, tests | ~150 lines + tests | D1 |
| 2 migration | `005_tips_handicap.sql`, test | ~50 lines | D1 |
| 3 grading | `csv_grader.py`, tests | ~20 lines + tests | 1, 2 |
| 4 cycle + referee | `run_cycle.py`, tests | ~60 lines + tests | 1, 3 |
| 5 API + site | `api/main.py` docs, `web/src/lib/api.js`, tests | ~30 lines | D3 |
| 6 deploy | VM, checklist above | — | 1–5, D5 |
| 7 docs | six files | — | 6 |

Phases 1–5 are one working session; everything is testable locally against
planted data before the VM sees any of it. The full suite (603 today) must be
green at every phase boundary.
