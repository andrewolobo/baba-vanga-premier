# STATE — one screen

**Read this first.** It says what ships, what is open with the owner, and what
must never happen. `OUTSTANDING.md` is the journal behind it and stays the
authority on *why*; when the two disagree, `OUTSTANDING.md` is right and this
file is stale — fix this file. Updated **2026-08-20**.

---

## What ships

A **strike-rate tipster** for E0–E3. One recommendation per fixture, published
on matchday, never revised, graded from football-data results.

| piece | what | where |
| --- | --- | --- |
| head | ridge Poisson, `H400 / a0.1 / weekly / E0+E1+E2+E3+EC / sot0.3`, refrozen ≤ 7 days | `engine/serve/cycle.py` |
| rule | `confidence-v3` (built 2026-08-19, **deploy pending** — the VM serves v2 until `V3_ADOPTION_PLAN.md` §6 runs): outright if p ≥ **0.55**, else likeliest of `1X`/`X2`/`12`/**underdog +1.5** ≤ **0.85**, else outright. Handicap tips carry NULL prices; honesty via the market-implied referee gap in the cycle | `engine/serve/tips.py` |
| cycle | sync → calendar → serve → tips → results → grade; exit **0** clean / **2** look / **1** failed. `results` (BBC full-time scores, `BVP_BBC_RESULTS=1`) settles tips before football-data's file exists; `grade` reconciles once it does | `services/run_cycle.py` |
| API | read-only; `/tips`, `/tips/results`, `/tips/record` (no P&L on the wire, per-rule-version headline; results carry the scoreline the grader settled from — migration 006) | `api/main.py` |
| site | one page: calls, last results, record; each call opens a drawer showing the next-likeliest markets behind it (B22, display only; the ranked-results reading was removed 2026-08-20); the settled list has its own league filter and last-12 ⇄ show-all toggle, and each settled card can show the score it was graded from plus the claimed probability — behind a "Scores & claims" toggle, off by default; the rule version and per-version table are owner-only via `/?owner=1` (`$lib/owner.js`, 2026-08-20) | `web/` |
| server | one Azure Ubuntu VM, `git pull`, systemd timer + service + nginx | `DEPLOY.md`, `RUNBOOK.md` |

**Measured, out of sample, 15,824 matches over 9 scored seasons:** v3 strike
rate **77.9%** at floor 0.55 on 100% of matches, **+5.37 ✱ paired over v2's
72.5%**, claims under-stating delivery by ~1 pt (`engine/eval/b21.py`, gate
row 110; v2: `engine/eval/selection.py`). v3 mix **63.8% underdog +1.5,
11.8% `H`, 10.2% `12`, 10.1% `1X`, 2.5% `A`, 1.5% `X2`** — the product
references a team in ~90% of matches (named winner in 14.3%, unchanged). The model names the market favourite
as the *side* essentially always; under the v2 rule its recommendation matches
the market's only 63.5% of the time (it hedges where the market would name),
and it does not out-return the market rule. What it adds is a ranking before a
price exists — and the goal-line menu that was meant to cash that in was
probed 2026-08-16 and does not deliver (`TIPSTER.md` C).

**Return is not a supportable claim** and the site does not make one.
Measured on the shipped v2 rule 2026-08-16 (`TIPSTER.md` A): **−4.56%
[−5.56, −3.60]** at average derived prices, **+0.11% [−0.94, +1.10]** at best.
The rule agrees with the same rule on the market's own probabilities in only
63.5% of matches and returns ~0.5 pts less, unresolved.

**The betting book is off.** Measured negative four ways (`CALIBRATION.md`).
`book.py` exists and is not wired into the cycle.

## Open with the owner

| item | state | next |
| --- | --- | --- |
| **B19** sum/difference penalty | B17 (2026-08-16): totals over-spread in E1–E3, margins under-spread (§9.12) — one ridge cannot get both right | owner decision whether to scope a head-level gate (~4–8 configs); B18 (totals shrink) parked until B4 reopens |
| **ops** | backup timer not enabled; no alerting; HTTP only | enable `bvp-backup.timer` + restore drill; dead-man's-switch ping from `run_cycle.sh` (owner supplies URL); TLS when a domain exists |
| **P6 criterion 2** | holdout still sealed; criterion 1 PASSED (PBO 0.000) | owner decides when to spend the one read; `DEFLATION.md` §8 |
| **B21** dog +1.5 → `confidence-v3` | **BUILT 2026-08-19** (D1–D5 approved): rule, migration 005, margin-aware settlement on both feeds, referee gap in the cycle, API + site labels — all tested (`tests/test_v3_tips.py`). Measurement: gate row 110 (+5.37 ✱), referee probe row 111 | **deploy per `V3_ADOPTION_PLAN.md` §6** — between matchdays, checklist in the plan |
| **B20** `12`-only window (ceiling or floor) | **overtaken by B21's adoption**: v3 displaces the content-free `12`s with the handicap (`12` falls to ~10% of output), which is what the floor was for | closes as scoped-not-spent (0 config) on v3 ship day (`V3_ADOPTION_PLAN.md` §7) |
| B10 `12` vs `1X` | open, downgraded | — |
| B15 half-life `H` | open, gated | — |
| B1 agreement filter | open, deprioritised | — |
| B9 best-price execution | parked until a graded season | — |

**Declined / closed:** B13 (calibrated probabilities in the rule — no), B14
(corners channel — do not adopt), B16 (per-version record — shipped), **B7
(v2 return measured — done 2026-08-16)**, **B11 (measured 2026-08-16)**, **B17 (measured 2026-08-16)**,
**B4 (goal-line menu — measured, do not extend on this head, 2026-08-16)**.

## Numbers that must be re-derived, not quoted

- Gate ledger: `trials.count_configurations(conn)` — **111 / 68 / 202** at last
  read (2026-08-19, on the authority machine, after `gate:b21_dog15` wrote row
  110 and `probe:b21_market_referee` row 111; re-exported the same session,
  `--check` clean. The other machine must
  `--restore` before any gate runs there). `docs/gate_ledger.jsonl` is the off-machine copy; the test
  `test_the_ledger_export_is_current` goes red until it is re-exported after a
  gate. `scripts/export_ledger.py --restore` loads it into an empty ledger, or
  appends what an exact-prefix ledger lacks; `--check` names which of the two
  is behind.
- Tests: `pytest -q` — **620 pass** at last run (2026-08-20, tip scores,
  Python 3.11), plus **20** in `cd web && npm test`; the prose has been stale
  before.

## What must never happen

1. **Do not turn the book on.** New measurement, not a flag.
2. **Do not measure on a serving corpus.** `Purpose.LIVE` is not a gate.
3. **Do not unseal the holdout** to explain a bad week. One pre-committed read.
4. **Do not backfill predictions or tips.** Append-only.
5. **Do not bump `RULE_VERSION` and re-run the cycle on one matchday** — two
   live calls per fixture (`RUNBOOK.md` §0).
6. **Do not commit a gate without re-exporting the ledger.**

## Where the rest is

`PRODUCT.md` (what the app recommends and why) → `BACKLOG.md` (trackable
items) → `OUTSTANDING.md` (the journal; §7 conventions) → `RUNBOOK.md`
(operating it) → `DEPLOY.md` (the server) → `SPEC.md` (methodology).
