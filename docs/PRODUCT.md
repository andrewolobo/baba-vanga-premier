# PRODUCT — what the app recommends

Written **2026-08-06**, after the owner set the product direction: a
**strike-rate tipster**, judged on how often its recommendation is right rather
than on what it returns. `OUTSTANDING.md` §1.10 records that decision and its
measured basis; this file records what the app is meant to *do*, and the
questions that have to be answered before it can.

Backlog and status: `BACKLOG.md`.

---

## 1. The goal, as stated

> Predict the likeliest outcome for each match: home/away win, win-or-draw, or a
> pick from over/under between 0.5 and 5.5.

So each match yields **one recommendation**, chosen from a menu of markets
rather than from a single market. That is a larger surface than anything built:
the engine currently serves 1X2 and Over/Under 2.5 only.

## 2. The market menu

| group | items | derivable today? |
| --- | --- | --- |
| 1X2 | home win, draw, away win | **yes** — served now |
| double chance | 1X (home or draw), X2 (away or draw), 12 | **yes** — `p_h + p_d`, no new model |
| over/under | lines 0.5, 1.5, 2.5, 3.5, 4.5, 5.5 | **yes** — `over_under_probs(joint, line=…)` already takes any line |

**Every probability on this menu is already computable.** `score_matrix` returns
the full joint distribution over scorelines, and both double chance and any
goal line are marginals of it. No new model, no new fit, no new data.

**Prices are a different story**, and this is the constraint that shapes
everything below:

| market | price in the schema? |
| --- | --- |
| 1X2 | yes — `avg_*` and `max_*` |
| Over/Under **2.5** | yes — `avg_over25`, `max_over25`, … |
| Over/Under 0.5, 1.5, 3.5, 4.5, 5.5 | **no** |
| double chance | **no**, but derivable from 1X2 as `1/(1/o_h + 1/o_d)` |

For the five unpriced goal lines the app can **predict** but cannot **measure
itself**: no return, no CLV, no comparison against the market. Whatever is
published on those lines is unfalsifiable against a price until a source
carrying them is acquired. That is not a reason to exclude them — the product is
sold on strike rate, which needs only the result — but it must be stated, because
every honesty check built so far leans on having a price.

---

## 3. The blocking problem: "likeliest" is degenerate

**Measured on 19,884 dev matches.** If the app recommends the highest-probability
item on the menu, here is what it recommends:

| recommendation | share of matches | mean probability |
| --- | --- | --- |
| **under 5.5** | **74.2%** | 0.959 |
| **over 0.5** | **25.8%** | 0.949 |
| *everything else* | **0.0%** | — |

Not once in 19,884 matches is any other market the menu maximum. Home win peaks
at 0.564 in the 90th percentile; under 5.5 sits at 0.948 on average.

**So "predict the likeliest outcome" as literally stated produces two
recommendations forever, at ~95% confidence, and nobody would pay for it.** The
strike rate would be excellent and the product worthless. This is the same
mechanism as the earlier finding that strike rate is a dial you turn by picking
shorter odds — here it is turned all the way to the stop.

### What has to be decided

A selection rule needs a second criterion beyond "most likely". Three candidates,
and this is an owner decision because it is about what the product *is*:

**(a) A probability ceiling.** Recommend the likeliest item *below* some cap —
e.g. the most likely market under 0.80. Price-free, so it works on the five
unpriced goal lines, and it is one number to measure. **Recommended**, because
it is the only option that applies to the whole menu.

**(b) A price floor.** Recommend the likeliest item whose price clears, say,
1.30. More principled — it directly encodes "not worth a customer's stake" — and
customer-legible. But it **reintroduces price into a product deliberately built
to ignore it**, and it cannot be applied to the five unpriced lines at all.

**(c) A fixed market preference order.** Always 1X2 unless confidence is low,
then double chance, then goal lines. Simple and fully controllable, but the
ordering is asserted rather than measured, and it is what §4 already implies.

Until this is settled, **the extended menu cannot ship**, and the double-chance
threshold below is a special case of it rather than an independent question.

---

## 3a. B0 DECIDED — probability ceiling, as a veto rather than a selector

**Owner decision 2026-08-06: the probability ceiling.** Measuring it before
building revealed that a ceiling *alone* does not fix §3 — it relocates it.

Likeliest item below the ceiling, on 19,884 matches:

| ceiling | top recommendation | second |
| --- | --- | --- |
| 0.60 | under 2.5 — 30.1% | X2 — 24.6% |
| 0.70 | 1X — 21.4% | over 1.5 — 20.3% |
| 0.80 | under 3.5 — 35.8% | over 1.5 — 32.1% |
| 0.85 | under 3.5 — 46.3% | over 1.5 — 20.9% |

**Outrights are essentially unreachable under a pure ceiling.** Goal lines have
low dispersion (under 3.5: p10 0.651, p90 0.813) while outrights have high
dispersion (home win: p10 0.303, p90 0.564), so whichever wide goal line sits
just under the cap wins almost every match. At 0.80, two thirds of
recommendations are goal lines. A football tipster that never names a team is
the same failure as §3 wearing different clothes.

**So the ceiling is kept, as a veto on the fallback rather than as the
selector**, composed with the preference order the owner's own §4 request
implies. The rule:

    outright favourite (home or away win)
      if its probability >= FLOOR          -> recommend it
      else if double chance <= CEILING     -> recommend 1X or X2
      else                                 -> recommend the outright anyway

The ceiling does real work: it stops the fallback recommending a near-certainty.
It never selects, so it cannot collapse the menu into goal lines. **FLOOR is
B3's threshold** and is what gets measured.

**`12` (home or away) is excluded from the menu** unless the owner says
otherwise. It took 49.6% of recommendations at a 0.75 ceiling, it is not a
"win or draw" bet, and it was not clearly part of the stated goal.

**Goal lines other than 2.5 are deferred to B4** and are not in this rule.

### Pre-registered, before either gate ran

1. Vector scaling removes the under-confidence: every post-calibration bucket
   lands within its 1.96 SE band.
2. Calibration raises tip volume at threshold 0.55 by **more than 20%**.
3. Realised strike rate at 0.55 falls slightly after calibration — the added
   fixtures are weaker — but stays **above 62%**.
4. At FLOOR 0.50 the published list's strike rate exceeds **70%**.
5. The published strike rate rises monotonically with FLOOR, because double
   chance is a superset of the outright it replaces.

## 4. Double chance, and the threshold to measure

The owner's request: *recommend win-or-draw when confidence is below some
threshold.* The rule is

    if max(p_home, p_away) < T:  recommend 1X or X2 instead of the outright

and it is attractive for a strike-rate product because double chance is
mechanically far likelier — 1X averages **0.687** against home win's 0.432.

**T is not measurable without an objective**, which is §3's problem in miniature.
Raising T sends more matches to double chance, which raises strike rate and
lowers how interesting the recommendation is. There is no interior optimum until
something pushes back. Once §3 picks a criterion, T follows from it directly:
under a probability ceiling, T is whatever keeps the double-chance pick under the
cap; under a price floor, T is where the derived 1X price falls through it.

What **can** be measured now, and should be as part of the same gate:

- the realised strike rate of 1X and X2 at each candidate T, walk-forward;
- how often double chance would displace an outright, per division;
- whether the head is calibrated on the *sum* `p_h + p_d` — it is under-confident
  on 1X2 outrights (`OUTSTANDING.md` §1.10), and there is no reason to assume
  that carries over unchanged to a two-outcome union.

---

## 5. What is already true, and constrains all of this

Carried forward so the next thread does not re-derive it:

- **The strike rate is honest; a return is not.** The shipped v2 rule:
  **72.5%** strike at floor 0.55 on 100% of matches, 15,824 out of sample over
  nine seasons (`engine/eval/selection.py`). Its return, measured 2026-08-16
  (`TIPSTER.md` Part A): **−4.56% [−5.56, −3.60] at average derived prices —
  resolved negative** — and +0.11% [−0.94, +1.10] at best-available, zero and
  unresolved. Derived double-chance prices are an upper bound, so the truth is
  worse. (`engine/eval/tips.py` holds the v1 outright rule's figures: 65.5%
  strike, −0.75% at avg — v1 backed favourites, v2 backs unions that pay the
  full margin.)
- **The model is not the source of the strike rate.** It names the market
  favourite as the side essentially always. Under the v2 rule the *recommendation*
  agrees with the same rule on the market's own probabilities in only **63.5%**
  of matches — the under-confident head hedges to `12` where the market would
  name the team — and returns **−0.57 pts [−1.49, +0.32]** relative to it,
  unresolved. What the model adds is the ability to rank a fixture *before a
  price exists*. **The extended goal-line menu was measured 2026-08-16 and does
  not deliver on that** (`TIPSTER.md` Part C): every shape is inert, collapses
  into two wide lines, or lands on the line the head gets most wrong outside E0.
- **The head is under-confident on its own favourites**, by up to 5.9 points.
  Correcting it raises **volume**, not strike rate (`BACKLOG.md` B2).
- **Nothing here changes the book.** It stays off (`CALIBRATION.md` §5).
