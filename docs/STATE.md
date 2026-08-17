# STATE — one screen

**Read this first.** It says what ships, what is open with the owner, and what
must never happen. `OUTSTANDING.md` is the journal behind it and stays the
authority on *why*; when the two disagree, `OUTSTANDING.md` is right and this
file is stale — fix this file. Updated **2026-08-17**.

---

## What ships

A **strike-rate tipster** for E0–E3. One recommendation per fixture, published
on matchday, never revised, graded from football-data results.

| piece | what | where |
| --- | --- | --- |
| head | ridge Poisson, `H400 / a0.1 / weekly / E0+E1+E2+E3+EC / sot0.3`, refrozen ≤ 7 days | `engine/serve/cycle.py` |
| rule | `confidence-v2`: outright if p ≥ **0.55**, else likeliest double chance ≤ **0.85**, else outright | `engine/serve/tips.py` |
| cycle | sync → calendar → serve → tips → results → grade; exit **0** clean / **2** look / **1** failed. `results` (BBC full-time scores, `BVP_BBC_RESULTS=1`) settles tips before football-data's file exists; `grade` reconciles once it does | `services/run_cycle.py` |
| API | read-only; `/tips`, `/tips/results`, `/tips/record` (no P&L on the wire, per-rule-version headline) | `api/main.py` |
| site | one page: calls, last results, record | `web/` |
| server | one Azure Ubuntu VM, `git pull`, systemd timer + service + nginx | `DEPLOY.md`, `RUNBOOK.md` |

**Measured, out of sample, 15,824 matches over 9 scored seasons:** strike rate
**72.5%** at floor 0.55 on 100% of matches (`engine/eval/selection.py`).
Published mix **65% `12`, 17.6% `1X`, 11.8% `H`, 3.0% `X2`, 2.5% `A`** — the
product names a team in 14.3% of matches. The model names the market favourite
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
| B10 `12` vs `1X` | open, downgraded | — |
| B15 half-life `H` | open, gated | — |
| B1 agreement filter | open, deprioritised | — |
| B9 best-price execution | parked until a graded season | — |

**Declined / closed:** B13 (calibrated probabilities in the rule — no), B14
(corners channel — do not adopt), B16 (per-version record — shipped), **B7
(v2 return measured — done 2026-08-16)**, **B11 (measured 2026-08-16)**, **B17 (measured 2026-08-16)**,
**B4 (goal-line menu — measured, do not extend on this head, 2026-08-16)**.

## Numbers that must be re-derived, not quoted

- Gate ledger: `trials.count_configurations(conn)` — **109 / 66 / 201** at last
  read (2026-08-17, on the authority machine after `--restore` appended P7 and
  B17's five rows, which had been written on a second machine). `docs/gate_ledger.jsonl` is the off-machine copy; the test
  `test_the_ledger_export_is_current` goes red until it is re-exported after a
  gate. `scripts/export_ledger.py --restore` loads it into an empty ledger, or
  appends what an exact-prefix ledger lacks; `--check` names which of the two
  is behind.
- Tests: `pytest -q` — **563 pass** at last run (2026-08-17, Python 3.11); the
  prose has been stale before.

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
