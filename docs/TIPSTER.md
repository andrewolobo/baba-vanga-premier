# P7 results — the tipster's own numbers

Run **2026-08-16** against the pre-registration in `P7_TIPSTER_PLAN.md`, which
was left unedited. Code `engine/eval/p7.py`, tests `tests/test_p7.py` (planted
data only), results `docs/p7_results.json`. Ledger rows **105–108**:
`gate:p7_v2_return` (4 configurations), `probe:p7_line_calibration_control`
(0), `probe:p7_line_calibration` (0 — the drop rule did not fire),
`probe:p7_menu_shapes` (0). **197 → 201 configurations**, exactly as declared.

Population: **15,824** out-of-sample matches, 2014-15 → 2022-23, E0–E3, the
same frame `selection.py` published B3 on. 15,818 carry a price.

Scorecard against the plan's predictions: **A 4 of 7, B 0 of 4, C 2 of 4.**
The misses are the findings.

---

## Part A — the shipped rule's return

| floor | strike | ROI @ avg (derived) | ROI @ best (derived) | model rule − market rule @ best | agree |
| --- | --- | --- | --- | --- | --- |
| 0.45 | 63.5% | **−4.39%** [−5.69, −3.16] ✱ | +0.01% [−1.34, +1.29] | −0.54% [−1.38, +0.22] | 71.6% |
| 0.50 | 69.3% | **−4.32%** [−5.38, −3.25] ✱ | +0.25% [−0.88, +1.37] | −0.70% [−1.60, +0.21] | 65.4% |
| **0.55** | **72.5%** | **−4.56%** [−5.56, −3.60] ✱ | **+0.11%** [−0.94, +1.10] | **−0.57%** [−1.49, +0.32] | **63.5%** |
| 0.60 | 74.0% | **−4.83%** [−5.73, −3.95] ✱ | −0.11% [−1.06, +0.82] | −0.43% [−1.31, +0.47] | 65.7% |

✱ = interval excludes zero. Every price on a double chance is *derived* from
the 1X2 legs and is an **upper bound** on what a customer gets; real
double-chance markets carry their own margin, so the true figures are worse.

**A1 — wrong on magnitude, right on sign.** Predicted [−4.0%, −1.0%] at avg
prices; delivered **−4.56%, resolved negative**. The v1 outright rule lost
−0.75% at the same floor (`tips_results.json`); v2 loses six times that. The
mechanism is arithmetic: v1 backed favourites, which the favourite–longshot
bias prices tightly; v2 backs `12`/`1X` unions in 85.6% of matches, and a
union of two vigged legs pays the book's full margin. −4.3 to −4.8% is what
a 1X2 overround of ~5% costs someone who is exactly as good as the market.

**A2 — held.** At best-available derived prices the return is **+0.11%
[−0.94, +1.10]**: zero, unresolved, at every floor.

**A3 — wrong on magnitude, right on resolution.** Predicted |Δ| < 0.5 pts;
delivered **−0.43 to −0.70 pts** at every floor, none resolved. The model rule
returns slightly *less* than the market rule; the interval includes zero. **The
sentence "the model adds ~0.00%" is corrected in place**: the model rule sits
about half a point behind the market rule and the difference is unresolved.

**The number the plan did not predict and should have: agreement is 63.5%,
not ~87%.** The 86.6% figure (`BACKLOG.md` B1) is which *side* is favourite.
Under v2 the recommendation also depends on the *level* — clears the floor,
name the team; does not, hedge — and the head is under-confident on its own
favourites (`OUTSTANDING.md` §1.10). So the model hedges to `12` in matches
where the market's probability would name the team. **The market rule at the
same floor names a team more often and returns half a point more.** That is
B13's mechanism seen from the return side, and it is worth knowing before
anyone says the head is "conservative": conservative on the claim, hedging on
the call.

**A4 — held loosely.** −4.39 → −4.32 → −4.56 → −4.83; one step improves by
0.07 pts inside a 2-pt interval. Not resolved either way, as pre-stated.

**A5 — held.** 99.96% priced overall; 99.9% in the market era.

### What changes

Text. `PRODUCT.md` §5 and `STATE.md` now cite **v2's** figures (the site's
paragraph is unchanged by owner decision): at average prices the rule loses **~4.6% of stakes,
resolved**; at the best price available it is indistinguishable from zero.
The site continues to publish no return. B7's open gap — "the return claim
was measured on a rule that does not ship" — is **closed**. Nothing here can
turn the book on (`CALIBRATION.md` §5): a derived DC price is an upper bound
and the return at it is zero.

---

## Part B — B11, calibration of the six goal lines

**Control passed, 5 of 6.** λ jittered by exp(N(0, 0.25)) reads
*overconfident* in the top bucket at 0.5, 1.5, 2.5, 3.5 and 4.5 (gaps −1.6 to
−22 pts). At 5.5 the top bucket sits at 95% and saturates. The instrument sees
the defect it exists to find; the table below is a result.

Pooled, likelier side of each line, buckets with n ≥ 200 verdicted:

| line | bucket | n | claims | delivers | verdict |
| --- | --- | --- | --- | --- | --- |
| 0.5 | [0.80,0.90) | 2,620 | 88.7 | 90.7 ± 1.1 | under-confident |
| 0.5 | [0.90,1.01) | 13,204 | 92.8 | 92.6 ± 0.4 | calibrated |
| 1.5 | [0.60,0.70) | 4,977 | 66.6 | 70.6 ± 1.3 | under-confident |
| 1.5 | [0.70,0.80) | 9,340 | 74.4 | 74.2 ± 0.9 | calibrated |
| 1.5 | [0.80,0.90) | 1,304 | 82.5 | 81.0 ± 2.1 | calibrated |
| **2.5** | [0.50,0.60) | 12,731 | 54.4 | 53.2 ± 0.9 | **overconfident** |
| **2.5** | [0.60,0.70) | 3,024 | 63.1 | **58.2** ± 1.8 | **overconfident** |
| 3.5 | [0.60,0.70) | 3,471 | 66.5 | 68.8 ± 1.5 | under-confident |
| 3.5 | [0.70,0.80) | 9,435 | 75.1 | 74.8 ± 0.9 | calibrated |
| **3.5** | [0.80,0.90) | 2,511 | 82.4 | **78.1** ± 1.6 | **overconfident** |
| 4.5 | [0.70,0.80) | 768 | 77.2 | 81.5 ± 2.8 | under-confident |
| 4.5 | [0.80,0.90) | 10,005 | 86.5 | 86.9 ± 0.7 | calibrated |
| **4.5** | [0.90,1.01) | 5,008 | 91.9 | **90.3** ± 0.8 | **overconfident** |
| 5.5 | [0.80,0.90) | 569 | 87.9 | 92.6 ± 2.1 | under-confident |
| 5.5 | [0.90,1.01) | 15,246 | 95.2 | 95.5 ± 0.3 | calibrated |

**All four predictions failed, and they failed the same way.** B1 (2.5
calibrated), B2 (no top-bucket over-claim), B3 (tails under-claim) and B4
(divisions agree with pooled) all assumed the 1X2 signature — an
under-dispersed head that under-claims its extremes — carries over to totals.
**It does not.** Where the pmf is *most* confident about a **low** total —
under 2.5 at 63%, under 3.5 at 82%, under 4.5 at 92% — more goals arrive than
it says, by **1.6 to 4.9 pts, resolved**. Where it is confident about a
**high** total (over 0.5, over 1.5) it under-claims. The pmf's confident
"under" is the defect, and the 2.5 line — **the one line with a price, and
the one a customer would recognise** — is the worst of them.

**And it is a lower-division defect.** Top bucket per division:

| line | E0 | E1 | E2 | E3 |
| --- | --- | --- | --- | --- |
| 2.5 [0.6,0.7) | −0.1 calibrated | **−6.6** ✱ | **−8.6** ✱ | **−4.6** ✱ |
| 3.5 [0.8,0.9) | −1.4 calibrated | **−4.1** ✱ | **−5.7** ✱ | **−4.7** ✱ |
| 4.5 [0.9,1.0) | −2.2 calibrated | −0.9 calibrated | **−2.6** ✱ | −1.3 calibrated |

**E0 is calibrated at every line. E1–E3 over-claim their confident unders by
4–9 points.** This is the third time a lower-division-only defect has surfaced
on this head — the draw deficit (`FINDINGS.md` §4.3) and the home leg of the
separation slope (`OUTSTANDING.md` §9.6, §9.10) are the other two — and it
is the largest of the three in the product's own currency.

**The drop rule did not fire.** It required the top *two* buckets to over-claim
by > 2 pts; at 2.5 the [0.50,0.60) gap is −1.2. So by the pre-committed rule
no line leaves the menu, and this row spends **0**. That the rule was one
bucket short of firing on the priced line is stated here so nobody reads
"did not fire" as "is fine".

**A hypothesis, not a finding.** The head is fitted jointly across divisions
with one intercept; if lower-division totals are more dispersed than
Premier-League totals — the P0-1 ratio of 1.013 was pooled — the pmf's low-λ
tail is too thin exactly where E1–E3 supply low-λ fixtures. Testable for 0
configurations (variance ratio per division on stored λ). Not run here; it is
outside this plan.

---

## Part C — B4, what each shape would publish (λ only)

Floor 0.55, `12` on. 85.6% of matches reach the fallback.

| ceiling | C1 fires | C2 goals call — top three | C2 mean p | C3: line displaces DC | C3 names a team | C3 publishes a line |
| --- | --- | --- | --- | --- | --- | --- |
| 0.75 | **0.00%** | O1.5 52% · U3.5 39% · U2.5 6% | 0.693 | 21% | 14.4% | 18.2% |
| 0.80 | **0.00%** | O1.5 45% · U3.5 44% · U2.5 6% | 0.743 | 64% | 14.4% | 54.6% |
| 0.85 | **0.00%** | U3.5 55% · O1.5 26% · U4.5 17% | 0.783 | 83% | 14.4% | 71.0% |
| 0.90 | **0.00%** | U4.5 62% · O0.5 16% · U3.5 16% | 0.856 | 99% | 14.4% | 84.9% |

**C1-a held, and it is decisive: the third tier never fires.** Not once in
15,824 matches at any ceiling. Whenever every double chance breaches the
ceiling, every goal line under it is itself unavailable or the veto has
already been taken. **B4 as a fallback below the fallback is not a product.**
It is inert, and it cost nothing to find out.

**C3-a held: the specificity rule is the ceiling-as-selector, again.** At 0.85
the goal line displaces the double chance in 83% of the fallback and the
product publishes a goal line in 71% of matches while naming a team in 14.4%.
`PRODUCT.md` §3a's refutation reproduces on the fallback population.

**C2-a and C2-b failed, both in the direction that matters.** A separate goals
call is **under 3.5 or over 1.5 in 78–90% of matches at every ceiling**. At
0.85 it is under 3.5 in 55% (predicted 40–55). At 0.75 the modal call is
**over 1.5 at 52%**, not the 2.5 line (6%); lowering the ceiling does not
spread the mix, it swaps one wide line for the other. **The 2.5 line — the
priced one — is chosen in ≤ 8% of matches under any ceiling.** A "goals call"
built this way says "over 1.5 / under 3.5" at 69–86% confidence, which is
`12`'s low-information problem in a second currency.

### The owner decision, with the numbers in front of it

The plan promised a decision on shape after the probe. Of the three shapes:

- **C1** is inert — not an option.
- **C3** is the ceiling-as-selector — already refuted, reproduced.
- **C2** is a two-line product ("over 1.5" / "under 3.5") at ~75% claimed and
  Part B says those confident unders **over-claim by 4–5 pts in E1–E3**.

**A fourth shape the plan did not list falls out of Parts B and C together:
a fixed 2.5-line goals call** — always over/under 2.5, the market every
customer knows, the only one with a price (so return is measurable), claimed
in the 54–63% range. Against it: it is the **worst-calibrated line in E1–E3**
(over 2.5 / under 2.5 top bucket claims 63%, delivers 58%), so it would need
per-division calibration before its confidence figure could be shown, and its
strike rate would be ~55%, which is not a strike-rate product.

**Recommendation: do not extend the menu on this head.** Every shape either
never fires, collapses into two wide lines, or lands on the one line the head
gets most wrong outside E0. The thing to fix first is Part B's finding — the
lower-division under-dispersion — and that is a modelling item on the head,
not a product item on the menu. C′ is not scheduled; if the owner wants a
shape measured anyway, the addendum to `P7_TIPSTER_PLAN.md` is where its
predictions go, and it costs 1 configuration per ceiling.

---

## What this closes and opens

| item | state after P7 |
| --- | --- |
| **B7** honesty gap | **closed** — v2's return is measured: −4.6% ✱ at avg, ~0 at best |
| **B11** per-line calibration | **measured** — E0 calibrated; E1–E3 over-claim confident unders by 4–9 pts; 2.5 worst |
| **B4** goal-line menu | **closed 2026-08-16 — owner decision: do not extend on this head** |
| **B1** agreement filter | note: v2 agreement with the market rule is 63.5%, not 86.6%; the arms B1 scoped need re-stating on the v2 rule |
| new | **B17 lower-division totals** — dispersion or level? pre-registered as a 0-configuration probe (`BACKLOG.md` B17) |

Nothing here changes `confidence-v2` or the book. **Nothing customer-visible
changes**: the owner kept the site's honesty paragraph as it was (still true —
"does not make money to any degree we can demonstrate"); the numbers live here,
in `PRODUCT.md` §5 and `STATE.md`.

---

## B17 follow-up — the mechanism behind Part B — **MEASURED 2026-08-16**

Pre-registration `BACKLOG.md` B17 (with its dated amendment to the statistic),
code `engine/eval/b17.py`, tests `tests/test_b17.py` (three planted
mechanisms: clean, level, dispersion — each named correctly), results
`docs/b17_results.json`, ledger row **109** `probe:b17_totals_mechanism`,
**0 configurations — 109 / 66 / 201.**

| div | n | dispersion ratio (level-corrected) | relative level, all | residual, all | residual, P(under 2.5) ∈ [0.6,0.7) |
| --- | --- | --- | --- | --- | --- |
| E0 | 2,948 | 0.946 [0.897, 0.997] | +0.0% [−2.1, +2.2] | +0.00 [−0.06, +0.06] | −0.02 [−0.19, +0.13] n=310 |
| E1 | 4,308 | 0.951 [0.913, 0.991] | +1.4% [−0.5, +3.2] | +0.04 [−0.01, +0.08] | **+0.24 [+0.15, +0.33]** n=843 |
| E2 | 4,264 | 0.967 [0.926, 1.008] | +0.9% [−1.0, +2.8] | +0.02 [−0.03, +0.07] | **+0.26 [+0.10, +0.41]** n=467 |
| E3 | 4,304 | 0.961 [0.923, 1.000] | +0.5% [−1.4, +2.4] | +0.01 [−0.04, +0.06] | **+0.21 [+0.10, +0.32]** n=701 |

Predictions: **P1 held** (control clean on the stated bucket), **P2 held**
(all three lower divisions resolved positive at +0.21 to +0.26 goals — the
top of the predicted band), **P3 held** (ratio gaps 0.005–0.021), P4 not
triggered. The mechanical reading is **LEVEL**. **The tables say something
sharper, and it changes the fix.**

**It is not a per-division level.** The relative level of every division is
zero to within 2 pts and every "residual, all" interval covers zero. A
per-division intercept — the fix B17 named for LEVEL — would move nothing,
because there is nothing overall to move.

**It is a conditional level: the pmf's total-goal expectation is too extreme
in E1–E3.** Where the head expects few goals (P(under 2.5) 60–70%, λ ≈ 2.2)
the truth is **+0.2 to +0.3 goals higher**; where it expects many (E2's
confident-over bucket, n=113) the truth is **−0.55 [−0.81, −0.30] lower**.
Low predictions too low, high predictions too high, level right on average:
that is regression to the mean on an estimate carrying noise, and it is the
same defect family as the separation slope (`SEPARATION_SLOPE.md`), on the
**totals axis** (att + dfn sums) instead of the margin axis. Note the two axes
point in **opposite** directions on this head — margins are under-spread
(§9.12: ~10% under-dispersed, the 1X2 under-confidence), totals are
over-spread. One ridge penalty on `att` and `dfn` cannot get both right; that
is a finding about the parameterisation, not about a division.

**E0 is not entirely clean either.** Its [0.5,0.6) under bucket reads
+0.13 [+0.03, +0.24] on n=985. P1 was stated on [0.6,0.7) and passed there;
the neighbouring bucket did not, and that is written here rather than left in
the JSON.

**The level-corrected dispersion ratio sits below 1 everywhere** (0.95–0.97,
resolved below in E0 and E1). Given the level, outcomes are slightly *less*
variable than the pmf's mixture — which is what an over-spread λ̂ produces,
because `var(cλ̂)` over-states `var(λ_true)` and is subtracted. Consistent
with the reading above; not a second defect.

### The fix that follows, and whether to run it

The fix is **shrinkage on the totals axis, per division** — pull
`log(λ_h + λ_a)` toward the division's running mean by a factor fitted
walk-forward (a P3-shaped calibration on totals; one β per division, or one
pooled with E0 checked separately). It would repair Part B's over-claiming
unders and is expected to be **worth nothing to the shipped product**, which
sells 1X2 and double chance and whose margin axis is *under*-spread. It only
matters if goal lines return to the menu, and **B4 is closed**.

**Recommendation: record, do not gate.** Open a backlog item for the totals
shrink, gated on B4 being reopened. The finding that earns its keep is the
opposite-sign spread on the two axes: it says the next head change worth
pre-registering is a **separate penalty for the sum and the difference of
`att`/`dfn`**, which would address §9.12's under-dispersion and this at once.
That is a P1-scale question, and it is the owner's whether to spend on it.
