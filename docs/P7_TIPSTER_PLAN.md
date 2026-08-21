# P7 pre-registration — the tipster's own numbers

Written **2026-08-15**, before any arm is run. Predictions are numeric so they
can be wrong. Results will go in `TIPSTER.md`; this file stays unedited.

Owner decisions that opened it, all 2026-08-15: measure the **shipped v2
rule's return** (the site's "no return" claim was measured on v1); pre-register
**B11 then B4** (the goal-line menu — the one place the model does something
the odds cannot); B13 declined, so every measurement here is on the **raw pmf**.

Three parts, run in order, each with its own ledger row. **Part C is a probe
that ends in an owner decision, not a gate** — the shape of the goal-line
product is not a thing a measurement can choose, and B0 already showed what
happens when one is asked to (`PRODUCT.md` §3).

---

## 0. Harness, shared by all three parts

Corpus and head as `engine/eval/selection.py`: `DEV_SEASONS`, walk-forward on
`travel.HEAD` (the frozen serving head), `served()` to E0–E3, COVID embargoed
from scoring, **15,824 out-of-sample matches** after three burn-in seasons.
Probabilities are the raw pmf from `score_matrix`. Intervals are the paired
block bootstrap by ISO week (`bootstrap.paired`, `week_blocks`) — never the
marginal SE (`OUTSTANDING.md` §7.3).

**Prices.** Only 1X2 and O/U 2.5 carry a price. Double-chance prices are
**derived**, `1/(1/o_h + 1/o_d)`, and are an **upper bound** on what a
customer gets (`tips.derived_price`). Return is measured on the subset with a
price; strike rate on everything. Every return figure below is therefore
flattering, and that direction is stated wherever it is shown.

**Accounting** (`DEFLATION.md` §4, `BACKLOG.md` header): a row spends one
configuration per arm whose *outcome-derived* number is chosen among or acted
on. Reading λ, prices or mixes spends nothing. Planted controls on synthetic
outcomes spend nothing.

---

## Part A — the shipped rule's return (closes B7's gap)

**Question.** At prices a customer gets, what does `confidence-v2` return, and
does the model add anything over applying the same rule to the market's own
probabilities?

**Arms.** The B3 floor grid `{0.45, 0.50, 0.55, 0.60}` at ceiling 0.85 with
`12` on — the four recommendation sets `selection.recommend` already produces.
Per arm, three numbers, each with a block-bootstrap CI:

- **A-ROI@avg** — flat stake, `avg_*` prices, DC derived from them;
- **A-ROI@best** — same, `max_*` prices;
- **A-vs-market** — the paired difference in ROI@best against the **market
  rule**: `recommend()` applied to the de-vigged `avg_*` probabilities instead
  of the model's. Same floor, same ceiling, same fixtures.

**Cost: 4 configurations** (the floor grid; price level and comparator are
reporting axes on the same four recommendation sets). The claim is about the
shipped floor 0.55; the other three are shown so the multiplicity is visible
rather than hidden, exactly as B3 showed them.

### Predictions

- **A1.** ROI@avg at floor 0.55 is **negative**, point estimate in
  **[−4.0%, −1.0%]**, and its CI **does not exclude zero on the positive side**.
  *Basis:* the rule names the market favourite (§1.10); a favourite-backer's
  return is ≈ −vig, and vig per leg at average prices is 0.02122
  (`CALIBRATION.md` §1); `12` is 65% of output at a derived price that
  understates the real margin; the head **over**-claims `12` by 0.75 pts (§9.5).
- **A2.** ROI@best at floor 0.55 sits in **[−2.5%, +1.0%]** and is unresolved.
  *Basis:* v1's ROI@best was ~1–2 pts above ROI@avg at every threshold.
- **A3.** A-vs-market at every floor is **|Δ| < 0.5 pts** and unresolved.
  *Basis:* the paired difference under v1 was ~0.00%; nothing in v2 changes
  which side is favourite, only how often it hedges.
- **A4.** ROI@avg does **not** improve as the floor rises 0.45 → 0.60. *Basis:*
  a higher floor sends more matches to `12` at shorter derived prices; strike
  rises but the price falls faster. Not a resolved-sign prediction — the
  differences between adjacent floors will be inside their CIs.
- **A5.** Price coverage of the recommendation set is **≥ 95%** in the market
  era (2019-20 →) and lower before it. Reported so the return's denominator is
  visible.

### Stop conditions

- If **A1's CI excludes zero on the positive side** at any floor, the finding is
  written up as "the v2 rule shows a positive return at derived prices" **and
  nothing else changes**: the site continues to publish no return, because a
  derived DC price is an upper bound and a return needs its own gate against a
  real DC price (B5). It does not turn the book on (`CALIBRATION.md` §5).
- If **A3 resolves in either direction**, the "model adds ~0.00%" sentence in
  `PRODUCT.md` §5, `serve/tips.py` and `STATE.md` is corrected before anything
  else is done.

### What ships from Part A

Text only. `PRODUCT.md` §5, `STATE.md` and the site's honesty paragraph cite
v2's numbers instead of v1's. `engine/eval/tips.py` is left as the v1 record.

---

## Part B — B11, per-line calibration of the six goal lines

**Question.** On stored walk-forward λ, does the pmf deliver what it claims at
each of over/under **0.5, 1.5, 2.5, 3.5, 4.5, 5.5**, per division and pooled?
This is the only honesty instrument available for the five unpriced lines.

**Construction.** For each line, `over_under_probs(joint, line)` gives
`p_over`; bucket by `max(p_over, p_under)` in
`[0.50,0.60) [0.60,0.70) [0.70,0.80) [0.80,0.90) [0.90,1.01)`; report claimed
mean, delivered rate, half-width, verdict, `n` — the same table shape as
`selection.calibration_table`. Buckets with `n < 200` are shown but not
verdicted.

**Positive control (B-ctl).** The same table on λ **jittered** by
`exp(N(0, 0.25))` per match — a deliberately over-confident head. The table
must return **overconfident** in the top bucket at ≥ 4 of 6 lines. If it does
not, the instrument cannot see the defect it exists to find and Part B reports
nothing. Synthetic outcomes are not needed — jittering λ against real outcomes
is enough — but **this arm reads outcomes for a control, not a decision**, and
spends nothing (`travel.py`'s `h34_travel_power` precedent).

**Cost: 0 configurations** *provided the B4 menu is fixed in advance* (Part
C). If a line is **dropped from the menu because of this table**, that drop is
a decision read off outcomes and spends **1 per line dropped**. The
pre-committed drop rule is below, so the drop is mechanical rather than chosen.

### Predictions

- **B1.** The 2.5 line is **calibrated** in every bucket with `n ≥ 200`.
  *Basis:* P0-1 (Poisson correct for totals, ratio 1.013) and the O/U 2.5
  reliability P3 already reported.
- **B2.** In the top bucket at every line, delivered **≥ claimed − 1.0 pt**:
  the pmf is not over-confident on totals. *Basis:* the head is ~10%
  under-dispersed (§9.12) — extreme λ are shrunk toward the mean, which makes
  the extreme lines **under**-claim, the same signature as the 1X2 favourites.
- **B3.** At **4.5 and 5.5**, the top bucket delivers **more** than claimed by
  **0.5–3.0 pts** (under-confidence, resolved at pooled `n`). *Basis:* B2's
  mechanism is strongest where the probability is most convex in λ.
- **B4.** No division differs from the pooled verdict at more than **one** line
  in the top bucket. *Basis:* the effect is a property of the likelihood, not
  of a league (`selection.walk_forward_calibrate`'s reasoning).
- **B5.** The control flags overconfidence at **≥ 4 of 6** lines in the top
  bucket.

### Drop rule, committed before the table exists

A line is **excluded from the B4 menu** iff, pooled, its top two buckets both
deliver **< claimed − 2.0 pts** with `n ≥ 200` — a resolved over-claim on the
buckets a confident tipster would publish from. Nothing else drops a line.
Under-confidence never drops a line: it is the conservative direction.

---

## Part C — B4, the shape of the goal-line product

**This is a probe ending in an owner decision.** B0 measured that "likeliest
item on the menu" degenerates to under 5.5 / over 0.5, and that a ceiling used
as a selector turns the product into a goal-line tipster that never names a
team (`PRODUCT.md` §3, §3a). Both were mix measurements — λ only, no outcomes,
**0 configurations** — and that is what Part C is: the mixes the candidate
shapes produce, so the owner can choose a shape with numbers rather than
adjectives. **Strike rate is not measured in Part C.** It is measured once, on
the chosen shape, as Part C′.

### The candidate shapes

- **C1 — third tier.** `outright ≥ FLOOR → double chance ≤ CEILING → likeliest
  goal line ≤ CEILING → outright anyway`. B4 as a fallback below the fallback.
- **C2 — a second call.** Every match keeps its v2 result call **and** gains a
  separate *goals call*: the likeliest line with `p ≤ CEILING`. Two records,
  never one strike rate.
- **C3 — specificity wins.** Between the double chance and the best goal line
  under the ceiling, publish whichever is likelier. (Included as the control
  that is expected to fail: it is the ceiling-as-selector §3a already refuted,
  restricted to the fallback population.)

Each on the ceiling grid `{0.75, 0.80, 0.85, 0.90}`, floor 0.55, `12` on.

### Predictions

- **C1-a.** The third tier fires in **< 3%** of matches at every ceiling.
  *Basis:* double chance averages 0.687 and breaches 0.85 in a small minority;
  the tier is reachable only where DC is a near-certainty, and then the goal
  line under the ceiling is usually itself over it. **If this holds, C1 is
  inert and B4-as-a-fallback-tier is not a product**; that is a finding worth
  0 configurations.
- **C2-a.** The goals call at ceiling 0.85 is **under 3.5 in 40–55%** of
  matches and **over 1.5 in 15–30%**, with the remaining lines sharing < 35%.
  *Basis:* §3a's table at 0.80/0.85. **A goals call that is "under 3.5" half
  the time is the same low-information problem as `12` at 65%**, and the owner
  should see that number before choosing C2.
- **C2-b.** Lowering the ceiling to 0.75 moves the modal line to **under 2.5 or
  over 2.5** and spreads the mix (no line > 35%). Reported so the ceiling's
  effect on the product is visible.
- **C3-a.** At ceiling 0.85, the goal line displaces the double chance in
  **> 70%** of fallback matches; the product names a team in **< 15%** and a
  goal line in **> 55%**. *Basis:* §3a. This is the refutation, re-shown on the
  fallback population only.
- **C-mean.** For every shape and ceiling, the mean published probability is
  reported — the number the site would show as "CONF".

### Part C′ — the gate, after the owner chooses

One shape, one ceiling (or a grid of ≤ 3 ceilings if the owner wants one
measured), strike rate with block CI, per division, plus for the **2.5** line
only a return at avg/best prices (reporting). **Cost: 1 per ceiling
measured**, declared in the ledger row before it runs. Predictions for C′ are
written **after** the owner's choice and **before** the run, as an addendum to
this file dated and signed — the one edit this file will take.

**Pre-committed for C′ regardless of shape:** the goals-call strike rate is
published on its own record (`rule_version` distinct from `confidence-v2`,
`/tips/record` `by_rule` keeps them apart — B16), never pooled with the result
call. *Note 2026-08-21: B16's headline now pools every `rule_version`, so a
goals call needs a product key the record groups on, not just a version, before
it is published — see the B16 amendment in `BACKLOG.md`.*

---

## 4. Order, stop conditions across parts, and cost

| step | reads outcomes | cost | stops if |
| --- | --- | --- | --- |
| A | yes | **4** | A1's CI is positive → write-up changes, product does not |
| B-ctl | yes (control) | 0 | control fails → Part B reports nothing |
| B | yes | **0** (+1 per line the drop rule removes) | — |
| C | **no** | 0 | C1-a holds → C1 is not offered to the owner as an option |
| owner decision | — | — | owner may stop here |
| C′ | yes | 1 per ceiling | — |

Ledger rows: `gate:p7_v2_return`, `probe:p7_line_calibration_control`,
`probe:p7_line_calibration` (kind becomes `gate` if the drop rule fires),
`probe:p7_menu_shapes`, then `gate:p7_menu_strike` after the decision.
`docs/gate_ledger.jsonl` is re-exported in the same commit as each row.

**Nothing here can turn the book on**, and nothing here changes
`confidence-v2`. If Part A finds a positive return it is recorded and B5 (real
DC prices) becomes the gate that would have to clear before a return is ever
claimed. If Part C′ ships a goals call it is a **second product on its own
record**, not a change to the first.

## 5. What is deliberately not measured

- **The v2 return on calibrated probabilities.** B13 is declined.
- **A floor other than the B3 grid.** Choosing a fifth floor here would be
  choosing among more arms than declared.
- **Goal-line prices other than 2.5.** There are none in the schema (B5).
- **Any joint 1X2 × O/U selection** ("home win and under 2.5"). Not on the
  owner's menu; a different product.
