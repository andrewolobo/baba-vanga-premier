# META — the P5 meta-label, measured

Run **2026-08-06**. Pre-registration in `P5_META_PLAN.md`, written before any arm
was fitted and left unedited except for the three §1 corrections its own
grounding code forced. Code `engine/eval/meta.py`, tests `tests/test_meta.py`,
results `docs/p5_results.json`, ledger `p5_grounding` / `p5_control` /
`p5_meta_arms`.

**Verdict: market follower. Do not adopt a meta-label on the football model.**
This is §6's second branch and §7's first two predictions, and it is the outcome
the plan expected. The interesting part is not that BOOK won — it is *how* it
won, which §3 below shows is not forecasting.

---

## 1. What ran

| | |
| --- | --- |
| basis | 58,143 legs / 19,381 matches, E0–E3, 2012-13 → 2022-23 |
| scored out of sample | **46,149 legs**, 2014-15 → 2022-23 |
| target | CLV = `devig(closing Pinnacle) − 1/Max`, per §2.3 |
| model family | least squares, weekly expanding walk-forward, 3 seasons burn-in |
| selection | top **10%** of each week, pre-committed in §7 |
| bar | Max vig **0.00201** (`OUTSTANDING.md` §8.2) |

The basis is 97.5% of §1.2's 19,884 matches. It loses 498 to rest's
first-match-of-season burn-in, 38 to a missing Pinnacle pre-close price, and 5
to a B365 price stored as **0** — which passes a null check and becomes an
infinity on conversion, so the filter runs on `breakeven_prob`'s output rather
than on `notna`.

---

## 2. The arms

Mean CLV on selected volume. Random selection at the same volume returns the
pinned mean of §1.4, −0.00195.

| arm | features | mean CLV | vs random | clears vig? |
| --- | --- | --- | --- | --- |
| **BOOK** | 9 | **+0.00762** | +0.00957 | **yes, 3.8×** |
| MODEL | 24 | +0.00061 | +0.00256 | no |
| FULL | 31 | +0.00744 | +0.00939 | yes |
| NOISE | 17 | +0.00759 | +0.00954 | yes |

Paired per leg, block-bootstrapped over ISO weeks:

| contrast | lift | 95% CI | reading |
| --- | --- | --- | --- |
| **MODEL − BOOK** | **−0.00702** | [−0.00803, −0.00599] | BOOK better, decisively |
| FULL − BOOK | −0.00018 | [−0.00070, +0.00035] | no difference |
| NOISE − BOOK | −0.00003 | [−0.00024, +0.00017] | no difference |
| MODEL − NOISE | −0.00699 | [−0.00802, −0.00590] | BOOK-plus-noise better |

**MODEL − BOOK is negative in all four divisions** — E0 −0.01287, E1 −0.00749,
E2 −0.00431, E3 −0.00523 — so §6's criterion 3 fails in the strongest possible
way. It is worth stating plainly that **MODEL is not worthless**: it beats
random selection by +0.00256, so the head does carry *some* ranking information
about price error. It does not come close to the vig, and it is dominated by the
price it is being asked to add to.

**MODEL contains a price and still lost, which strengthens the finding.** §4
lists `edge = m_prob − 1/Max` under MODEL, so the sets are not disjoint as §4
claims: MODEL was given a price-relative feature and BOOK was not given anything
model-derived. That asymmetry favours MODEL, and MODEL lost by 0.007 anyway.

### §6's four criteria, as pre-committed

1. `MODEL − BOOK` improves with a CI excluding zero — **fails**, the interval is
   entirely on the wrong side of zero.
2. Selected-volume CLV exceeds 0.00201 — **fails for MODEL** (+0.00061), passes
   for BOOK.
3. Sign holds in ≥3 of 4 divisions — **fails**, wrong sign in 4 of 4.
4. PBO < 0.5 with `choice_mattered` — **fails as written** (0.631); §4 below is
   why that number does not mean what it looks like.

---

## 3. What BOOK is actually buying — the finding that matters

BOOK clears the vig by 3.8×, which is large enough to demand a mechanism before
it is believed: +0.00762 is 0.34 sd of a single leg. The selection profile is
unambiguous, and it fits nothing.

| | pool | BOOK's selection | MODEL's selection |
| --- | --- | --- | --- |
| `max_spread` (1/Max − 1/Avg) | −0.01808 | **−0.02549** | −0.01841 |
| Max overround | 1.00585 | **0.99599** | 1.00172 |
| **share from matches with Max overround < 1** | **23.7%** | **65.3%** | 39.3% |
| draw legs | 33% | 13.6% | 0.4% |

**65.3% of BOOK's selected legs come from matches whose best-available 1X2 book
sums to under 1**, against 23.7% in the pool — 2.8×. Backing all three legs of
such a match returns a profit before any forecast is made at all. BOOK's top
standardised coefficient is `max_spread` (−0.00433), ahead of `sharp_spread`
(+0.00329) and `be_max` (−0.00276).

So BOOK is not predicting line movement so much as **locating cross-book price
dispersion**. That is genuine CLV — those prices really do beat the close — but
it is the best-price-capture phenomenon `CALIBRATION.md` §5 already named as a
prerequisite, arriving as a result. And a sub-1 overround across the whole book
is precisely the condition under which a real bookmaker limits, voids, or has
already moved: `P5_META_PLAN.md` §8 excludes execution, limits and price
availability at Max from this gate, and **that exclusion is doing far more work
here than it was written to do.**

`sharp_spread` being second, and BOOK's selection sitting *closer* to consensus
on it (−0.00403 vs a pool of −0.01016), says the Pinnacle-versus-consensus
signal §1.6 identified is real but is not the main driver.

---

## 4. PBO, and a hole in `choice_mattered`

| field | arms | PBO | spread | `choice_mattered` |
| --- | --- | --- | --- | --- |
| all | BOOK, MODEL, FULL, NOISE | 0.631 | 0.006729 | true |
| contenders | BOOK, FULL, NOISE | 0.863 | 0.000149 | **false** |
| **decision** | **BOOK, MODEL** | **0.000** | 0.006597 | true |

**`choice_mattered` can be satisfied by the wrong thing, and this is the first
gate to show it.** `DEFLATION.md` §6 guards against reading PBO ≈ 0.5 as
overfitting when the arms are interchangeable. The mirror-image failure is here:
its test is the spread of mean performance across *all* trials, so **one clearly
losing arm makes the whole field look separable** while every arm that could
plausibly be chosen is interchangeable. Drop MODEL and the tool flags itself
uninformative at a spread of 0.000149.

Read on the comparison that decides anything — BOOK against MODEL — PBO is
**0.000 with degradation +0.0033**: the in-sample winner is the out-of-sample
winner in every one of 12,870 splits. Criterion 4's literal failure is an
artefact of pooling a decided comparison with an undecidable one.

**This is a defect in the deflation machinery, not in this gate**, and it should
be fixed there rather than remembered here. `DEFLATION.md` §6 needs the same
caveat in the other direction.

---

## 5. Controls

**Positive control (§5), run first and alone.** A planted CLV edge on the top
20% of `lam_total` — a stratum only MODEL can see — at four sizes. Perfect
ranking has a ceiling of `δ × (1 − stratum share)` = 0.8δ, so recovery is
quantitative rather than a sign test.

| planted δ | recovered | mean lift | vs ceiling |
| --- | --- | --- | --- |
| 0.00000 | 1/6 | −0.00001 | — |
| 0.00250 | 6/6 | +0.00182 | 91% |
| **0.00500** | **6/6** | **+0.00397** | **99%** |
| 0.01000 | 6/6 | +0.00810 | 101% |

The stop condition passed and the arms ran. One false positive in six at δ = 0
is within binomial noise for a 95% interval, and is recorded rather than
smoothed.

**Negative control (§5).** NOISE gains **−0.00003** over BOOK, against §7's
threshold of 0.0002. Seventeen features including eight drawn independently rank
no better than nine real ones, so BOOK's result is not the instrument inflating.

**A seed collision nearly inverted the control, and the per-draw range caught
it.** The reference arm's "random" prediction and the synthetic target were both
standard normals of the same length drawn from colliding seeds, making the
reference an exact oracle on draw 0. The symptom was a control reporting 5/6
recovered *and* a negative mean lift — an incoherence invisible in either number
alone. Fixed by disjoint streams; the per-draw lifts are now recorded so a
single anomalous draw cannot hide inside an average.

---

## 6. Predictions, scored

`P5_META_PLAN.md` §7, written before any arm was fitted. **Four of five right.**

| # | prediction | outcome |
| --- | --- | --- |
| 1 | BOOK beats MODEL on selected-volume CLV | **right** — +0.00762 vs +0.00061 |
| 2 | MODEL − BOOK does not clear criterion 1 | **right** — −0.00702, wrong sign entirely |
| 3 | BOOK alone clears the Max vig on its top decile | **right** — 3.8× the bar |
| 4 | control ≥5 of 6; NOISE gains < 0.0002 | **right** on both — 6/6, −0.00003 |
| 5 | PBO < 0.2 with `choice_mattered` true | **wrong** — 0.631, for the §4 reason |

Prediction 5 is the informative miss: it was wrong because the plan assumed
three disjoint feature sets would be three distinguishable arms, and two of them
turned out to be the same arm with decoration.

---

## 7. What this does not say

- **Nothing about turning the book on.** `CALIBRATION.md` §5 and `OUTSTANDING.md`
  §2.3 stand. BOOK's CLV is measured at a Max price whose availability at stake
  is not modelled, and §3 shows the selection concentrates exactly where
  availability is least plausible.
- **Nothing about the head.** A meta-label sits above the served pipeline and
  changes no λ. MODEL lost, so there is no follow-up question about moving a
  feature into the head.
- **Nothing about profit.** No match outcome was read at any stage — CLV is a
  function of two prices — so realised ROI is not computed here at all.
- **Nothing about the holdout.** Sealed.
- **Nothing about O/U**, excluded by §2 on 5× less data and 3.6× more vig.

---

## 8. The arbitrage-excluded re-test — **POST-HOC, and it survives**

Run after §3, to separate the part of BOOK's edge that is cross-book dispersion
from the part that might be information. **Every match whose best-available 1X2
book sums to under 1 was removed from training and from scoring**, at a threshold
of exactly 1.0 — the point where the book is beatable outright, and the only
value there that is not a tuned parameter.

**The subgroup was chosen after seeing the result.** Ledger `p5_book_no_arb`, in
`trials.POST_HOC_TRIALS` alongside `h19_alpha_interaction`. It can motivate a
pre-registered follow-up. It cannot substitute for one.

| | |
| --- | --- |
| kept | 44,391 of 58,143 legs (**76.3%**), 14,797 matches |
| pinned mean | **−0.00192 → −0.00318** — the bar got *harder* |

| arm | mean CLV | vs random | clears vig? |
| --- | --- | --- | --- |
| **BOOK** | **+0.00397** | +0.00715 | **yes** |
| BLIND | −0.00223 | +0.00095 | no |

- **BOOK selected CLV minus the vig: +0.00196 [+0.00115, +0.00276]** — excludes
  zero, out of sample, walk-forward.
- **BOOK − BLIND: +0.00615 [+0.00503, +0.00730].**
- **Clears the vig in all four divisions** — E0 +0.00447, E1 +0.00317,
  E2 +0.00363, E3 +0.00479.

**BLIND is the control this question needed, and §2's NOISE was not it.** NOISE
contains every BOOK feature, so it answers "do eight useless columns change
anything" — the right control for `MODEL − BOOK` and the wrong one for "is
BOOK's *level* real". BLIND has no price information at all: side indicators and
eight independent normals. It selects 98.4% away legs, lands at −0.00223 — the
pinned mean plus the structural side effect — and stays below the vig. The
harness is not manufacturing edge.

**But the mechanism has not changed as much as the number suggests.**
`max_spread` is still the largest coefficient (−0.00356), only just ahead of
`sharp_spread` (+0.00332), and BOOK's picks still carry a `max_spread` 29% wider
than the pool it drew from (−0.02236 against −0.01732). So this is still
substantially *the best available price is unusually far from consensus*. What
changed is that it no longer requires the whole book to be beatable — one
outlier leg is enough.

**Reading.** The edge is roughly halved (+0.00762 → +0.00397) on a harder bar,
and it holds. There is something here beyond arbitrage. It is still an
execution-dependent signal rather than a forecasting one, and the honest next
question is not a modelling question: **can you take the outlier price at
stake?** `RUNBOOK.md` does not capture Max at bet time, so nothing in this
project can currently answer it.

---

## 9. Ledger, and an overspend to record

§5 declared a budget of **≤12 configurations**. The arms cost **16** mechanically
and the §8 re-test a further **2** (one run, under `--dry-run` until it was
final). On the arms,
and the reason is a process error rather than a modelling one: the gate wrote a
ledger row on each of four runs during implementation, as reporting was added.
**The arm results are byte-identical across all four** — same seeds, same
features, same fits, same numbers to five decimals — so the runs added
diagnostics, not selection opportunities.

Both numbers are on the record and the choice between them is the owner's:

- **16** by `trials.count_configurations`, which counts rows and cannot know two
  rows are the same computation. Convention 5 keeps it that way deliberately.
- **4** distinct configurations, which is what multiplicity means — BOOK, MODEL,
  FULL, NOISE, chosen among once.

The controls spend nothing on either count: `p5_grounding` reads prices only and
`p5_control` runs on synthetic targets, the same accounting as `power.py` and
`travel.py`'s `h34_travel_power`.

**The honest lesson is to write to a scratch path until the code is final.**
`p3.py` and `travel.py` avoid this by having been finished before they were run.
`meta.py` now carries a `--dry-run` flag that prints and writes JSON but records
no ledger row; §8 was developed under it and cost one row.
