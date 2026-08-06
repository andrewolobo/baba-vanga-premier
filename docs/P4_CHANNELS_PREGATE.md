# P4-channels pre-gate — is there a second channel worth a gate?

Written **2026-08-06**, before any arm is run. This is a **pre-gate, not a
pre-registration**: it decides whether a full gate deserves a ledger row at all.
Modelled on `probe:p4_shots_target_pregate` (row 53), which played the same
role for the shots channel and refuted the SPEC's mechanism on the way.

Nothing here selects a hyperparameter or touches a served head. If it says
stop, the result is one probe row and no gate.

---

## 1. Why a pre-gate and not a plan

`P4_SHOTS_PLAN.md`'s predictions were numeric because row 53 had already
measured split-half reliability, conversion persistence and oracle headroom.
Without that basis, predictions are decoration. The equivalent basis for a
second channel does not exist yet, because row 53's M2 table measured only
**pairs**:

| predicting | goals | goals+sot | shots | shots+sot | **goals+shots+sot** |
| --- | --- | --- | --- | --- | --- |
| goals_for (attack) | 0.441 | **0.480** | — | 0.459 | **not measured** |
| goals_against (defence) | 0.408 | 0.468 | 0.458 | **0.469** | **not measured** |

`goals+sot` is what shipped. Two cells are blank and one knob was never swept.

## 2. What is being asked

**Q1 — does total shots add a third channel, or is it redundant with sot?**
Shot counts strictly contain shots on target, so the two are heavily
correlated. Row 53 shows shots reads *defence* much better than goals (0.458 vs
0.408) — a larger single-channel jump than sot gives attack — but `shots+sot`
(0.469) and `goals+sot` (0.468) are a dead heat, so *substituting* buys nothing.
Whether *adding* buys anything is unmeasured.

**Q2 — should the blend weight differ by side?** `walkforward.py` folds a single
`cfg.shots_blend` into whichever sides `shots_blend_sides` enables, so H21's
att-only / dfn-only / both arms all ran at a shared `w = 0.30`. M2 puts the
defence reliability gain at ~1.5x the attack gain (+0.060 vs +0.039) and H21
measured 52% vs 28% of the full effect. A per-side weight has never been tried.

**Q3 — is the remaining headroom in *channels* at all?** Row 53's M3 measured an
end-of-season oracle of the same model family at **−0.05705** deviance, against
a served deficit of +0.01419 — the functional form was never the limit,
estimation precision was. The oracle *sot* blend reached −0.01636 (row 55) and
the real one −0.00422. That ratio is the quantity that says whether a
better-measured channel is worth acquiring, and it is the argument for xG.

## 3. Measurements

Development set only, E0–E3 scored, COVID embargoed, frozen head
`H400 / a0.1 / weekly / E0+E1+E2+E3+EC / sot0.3`. No arm is fitted to a
selection metric here; these are reliability and headroom diagnostics.

**M4 — the missing split-half cells.** Same harness as M2, filling
`goals+shots+sot` on both sides, plus the two asymmetric singles row 53 skipped
(`shots→goals_for`, `sot→goals_against`).

**M5 — channel collinearity.** Correlation between `att_s` fitted on sot and
`att_s` fitted on total shots, at a fixed cutoff, and the same for `dfn_s`. A
third channel that is 0.95+ collinear with the second cannot be worth a gate,
and this is the cheapest way to find out.

**M6 — per-side curvature.** The existing H20 sweep re-read at the two
neighbouring grid points, to estimate how much a per-side weight could buy
given a 1-D interior optimum at 0.30. Reads stored sweep output; fits nothing.

## 4. The stop rule, committed in advance

- **If M5 shows sot and total-shots coefficients above 0.95 collinear**, Q1 is
  answered: no third channel, no gate, and the ledger takes one probe row.
- **If M4's `goals+shots+sot` fails to beat `goals+sot` by at least 0.005 of
  split-half r on either side**, the same. The shipped channel bought 0.039
  (attack) and 0.060 (defence); a third channel worth under a tenth of that
  cannot survive the deviance noise floor.
- **If M6 puts the achievable per-side gain below one paired SE (~0.0003)**,
  Q2 is answered and no sweep is run. Coding it is cheap; the ledger row is not.
- **If all three stop**, that is the finding: the in-store channels are
  exhausted, and the next real move is acquisition (xG), not another arm.

## 5. What this cannot become

It cannot turn the book on, and it is not a licence to sweep. `CALIBRATION.md`
§5 stands: the pooled deficit is +0.01230 against a vig of 0.02122, and a second
channel of the first one's size closes about an eighth of that. Per
`OUTSTANDING.md` §2.3, nats and de-vigged probability do not net — anyone
wanting the new number re-runs P3.

**Multiplicity is the real cost.** `DEFLATION.md` counts configurations, not
intentions, and the ledger stands at 75 runs / 40 questions / ≥149
configurations. A sweep over `(w_att, w_dfn)` on a 6-point grid is 36
configurations — a quarter of everything spent so far — for an effect this
pre-gate exists to show is probably sub-SE.

## 6. Predictions

Numeric, so they can be wrong.

| # | prediction |
| --- | --- |
| M4 | `goals+shots+sot` beats `goals+sot` by **< 0.005** on attack and **< 0.010** on defence |
| M5 | sot and total-shots `dfn_s` are **> 0.90** collinear |
| M6 | best per-side gain over shared `w = 0.30` is **< 0.0005** deviance |

If all three land, this closes the in-store channel question the way `REST.md`
closed rest: a null with a size attached, rather than an absence of a finding.

## 7. What it does not test

**xG is not in the corpus and cannot be probed from it.** FBref date pages carry
no xG column for any of 60 competitions (verified 2026-08-06 against the five
cached pages in `data/fbref/raw/`); the schedule schema is round, start_time,
home_team, score, away_team, attendance, venue, referee, match_report, notes,
gameweek. xG lives on comp-season schedule pages, which `parse.py` does not
handle and which need a live session — the one minted 2026-08-04 was refused on
first use two days later, and refreshing it needs headed Chrome on a desktop.

Backfilling 13 dev seasons x 4 divisions from comp-season pages is **52
requests**, about six minutes at the 6 s throttle. Coverage by division is
unknown and is the first thing to establish: FBref's xG is Opta-derived and may
not reach E2/E3. **That probe costs no development-set information at all** —
it reads a website, not the corpus — which makes it strictly cheaper than
anything in §3, and it is the one input M3 says has real headroom behind it.
