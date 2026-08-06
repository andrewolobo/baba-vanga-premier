# The kickoff slot — measured, and not measurable

Measured **2026-08-04**. Code `engine/eval/tod.py`, results
`docs/tod_slot_results.json`, ledger rows `h26`–`h29`.

Answers SPEC §3.6, which asked for gtleague's proof method with the feature
replaced: subtract per-team expectation, then test the residual by slot. If it
survives it is a slot effect; if not it was composition.

**It is neither.** A slot effect survives the residual test, and survives a
control the source document did not have. It is then worth **−0.00067
[−0.00216, +0.00079]** on goal deviance — and H29 shows this corpus could not
have detected an effect that size even if it were real, so that interval is an
underpowered instrument rather than a measured null.

---

## 1. The constraint that decides everything

`Time` is absent from football-data.co.uk before 2019-20. Coverage is a clean
switch, not a ragged one — 0% through 2018-19, 100% from 2019-20 — so nothing
here is a parsing artifact.

After the holdout is sealed and the COVID window is embargoed from scoring:

| | matches |
| --- | --- |
| dev, served divisions, scored by the frozen head | 21,896 |
| …of those, carrying a kickoff time | **5,644 (25.8%)** |
| seasons available | 2019-20 (truncated 13 Mar), 2021-22, 2022-23 |

2020-21 is gone entirely — it is inside the COVID embargo. The usable corpus is
**2.6 seasons**, and that number, not the effect size, is what this document is
ultimately about.

**This limits measurement, not serving.** Every future fixture carries a kickoff
time, so a slot feature would apply to 100% of served matches. The corpus is
thin only for deciding whether to build it.

## 2. The raw effect reproduces gtleague's, at almost the same magnitude

Slots are one categorical over weekday and hour, per SPEC §2.4. Weekday 15:00 is
its own level: **every such date in the corpus is a public holiday** (Boxing
Day, New Year, Good Friday, Easter Monday, the May and coronation bank
holidays). That is a full fixture round, not a broadcast pick, and folding it
into Monday-night football would have mixed two populations that share nothing
but a clock.

Raw mean total goals swing **2.468 → 3.171 = 0.703 goals**. gtleague reported
3.51 → 4.22 = 0.71. Nearly identical spread on a league scoring 2.58 rather
than 3.9.

## 3. Composition explains most of it, but not all

| control | what it removes | ANOVA on the residual |
| --- | --- | --- |
| none | — | swing 0.703 goals |
| per-team mean, home/away apart, leave-one-out | marginal team quality | p = 0.001 |
| **the frozen head's λ** | team quality, **opponent**, decay, division, as-of | p = 0.00115 |

The literal port is the weaker of the two and it is worth saying why: per-team
means remove marginal team quality but **not matchup**, and broadcast selection
picks fixtures, not teams. The λ control is the one that decides it, and the
effect survives it — permutation p = **0.0020** with slot labels shuffled
within season, so it is not season-level scoring drift either.

Division composition is severe and is exactly what the λ control absorbs:
`sat_late` is 82.6% Premier League, `sat_15` is 11.3%, and E0 outscores E3 by
0.37 goals a match.

## 4. What survives, and how little of the corpus it covers

λ residual, positive = more goals than the head expects. Nine slots were tested,
so the honest intervals are Bonferroni-corrected at 99.44%:

| slot | n | residual | 95% | 99.44% |
| --- | --- | --- | --- | --- |
| `sun_late` | 193 | **+0.426** | [+0.200, +0.676] | [+0.087, +0.770] **survives** |
| `holiday_15` | 261 | +0.151 | [+0.029, +0.289] | [−0.021, +0.335] |
| `sat_late` | 109 | −0.360 | [−0.642, −0.079] | [−0.720, +0.054] |

One slot of nine survives correction. Signs agree across all three seasons for
both `sun_late` (+0.31 / +0.84 / +0.14) and `sat_late` (−0.29 / −0.26 / −0.52),
and `sun_late` is positive in all four divisions, so neither is one season or
one division. Within Sunday the effect is confined to the late kickoffs —
+0.45 at 15:00 and +0.44 at 16:30, against −0.01 at 14:00 and +0.01 at 12:00 —
which is a coherent shape rather than a scattered one.

**The two flagged slots hold 302 matches, 5.4% of the measurable corpus.** That
is the whole problem with §5.

## 5. The market misses the same two slots, in the same direction

Market residual is the realised over-2.5 rate minus the de-vigged average price.

| slot | model residual | market residual |
| --- | --- | --- |
| `sun_late` | +0.426 | **+0.0943 [+0.0203, +0.1761]** |
| `sat_late` | −0.360 | **−0.1015 [−0.1821, −0.0128]** |

Both intervals exclude zero, and no other slot's does. This is the only version
of the finding that could ever have been worth money — a slot the book prices
correctly is one the model should simply learn. It is also 302 matches and was
selected after seeing §4, so it is a lead, not a result.

## 6. On the selection metric it is worth nothing measurable

Slot factors fitted **leave-one-season-out** and applied multiplicatively to λ,
so this is what the feature would have been worth served, not the in-sample fit
that cannot lose. Negative = the slot term is better.

| arm | goal deviance | O/U 2.5 log-loss |
| --- | --- | --- |
| all nine slots | −0.00067 [−0.00216, +0.00079] · 0.9 SE | −0.00039 · 0.6 SE |
| `sun_late` + `sat_late` (post-hoc) | −0.00086 [−0.00206, +0.00029] · 1.4 SE | −0.00057 · 1.0 SE |
| `sun_late` only (post-hoc) | −0.00048 [−0.00150, +0.00051] · 0.9 SE | −0.00037 · 0.7 SE |

Every interval contains zero. For scale, the adopted shots channel was
**−0.00422 [−0.00535, −0.00307]** at 7.3 paired SE.

## 7. The positive control, and why §6 is not a null

Convention §7.8: a null without a planted positive control is not a result.
Goals were redrawn from the head's own λ times a known slot factor, so the
effect is present by construction and nothing else is.

| planted | deviance delta | detected (6 draws) |
| --- | --- | --- |
| ×0 — nothing | **+0.00112** | 0/6 |
| ×0.5 | +0.00018 | 0/6 |
| **×1.0 — the size actually present** | **−0.00097 · 0.9 SE** | **2/6** |
| ×1.5 | −0.00397 · 2.4 SE | 3/6 |
| ×2.0 | −0.00750 · 3.5 SE | 6/6 |
| ×3.0 | −0.01730 · 4.1 SE | 6/6 |

**At the size actually present the instrument finds it in a third of draws.**
§6 is therefore not evidence of no effect; it is evidence that this corpus
cannot resolve one. The threshold sits between ×1.5 and ×2.0.

The ×0 row is worth its own line: a nine-level slot term fitted to pure noise
costs **+0.00112 nats**. The measured −0.00067 is consistent with a small real
effect roughly cancelling that overfit cost, which is a second reason the point
estimate is not informative.

### What it would take

To reach 1.96 SE at the effect size present requires **≈28,400 matches, 5.0× the
present corpus — about ten further seasons.**

Unsealing the *entire* holdout — all three sealed seasons, the project's most
expensive single act — reaches n ≈ 12,200 and **1.3 SE. Still short.** There is
no version of spending the holdout that answers this question.

## 8. Verdict

**Not measurable on this corpus. Do not build it, and do not spend the holdout
trying.** The correct reading is "underpowered", not "null" — the distinction
matters because the two justify different future actions:

- A **null** would say the feature is dead. It is not dead; one slot clears a
  Bonferroni-corrected interval, its sign is stable across three seasons and
  four divisions, and the market misses it in the same direction.
- **Underpowered** says the question is well-posed and the corpus is too small.
  It becomes answerable only with roughly a decade more data, or by a design
  that does not spend its power on nine levels covering 5% of matches.

If it is ever revisited, the cheap version is the two-level contrast
(`sun_late` and `sat_late` against everything else) pre-registered *before*
looking, which is the arm §6 shows is strongest and which §4 admits was chosen
post-hoc here. That does not fix the power problem — 1.4 SE is not 2 — but it
stops spending degrees of freedom on levels no one has a hypothesis about.

**Do not** re-litigate with finer time buckets, per-division slot terms, or
interactions with team strength. All of those *increase* the parameter count
against a corpus that cannot afford the nine already tried.

## 9. The power problem is the slot's, not the SPEC's

SPEC §3.6 did not ask for the slot to be kept. It asked for it to be **replaced**
by four analogues gtleague could not have: days since last match and the
differential between the sides, fixture congestion in the trailing 14 days, away
travel distance, and match stakes.

**Only the slot is limited to 2019-20 onward.** Rest and congestion derive from
`match_date`, which every row has:

| feature | usable scored matches | vs the slot |
| --- | --- | --- |
| kickoff slot | 5,644 | — |
| rest days / congestion | **21,896** | **3.9×** |
| travel distance | ~~blocked — no stadium coordinate table~~ **21,896** — table built 2026-08-06 | **3.9×** |
| stakes | blocked — needs as-of league tables (OPEN-4) | — |

Rest has real spread to work with: median 7 days, 10th percentile 3, 90th
percentile 13. On §7's arithmetic a 3.9× larger corpus turns a 0.9 SE
measurement into roughly 1.8 SE **at the same effect size** — still short of
2, but it is a different question with a different answer, and it costs no new
data acquisition.

So the correct reading of this document is narrow: **the kickoff slot is
unmeasurable here.** It says nothing about context features in general, and the
ones the SPEC actually preferred are not subject to the constraint that killed
this one.

**Rest was measured next, and the prediction above held.** On 21,425 matches the
instrument caught a planted effect 6 times out of 6 where this one managed 2,
and returned a bounded null rather than an unresolvable interval — `REST.md`.
It also found a *different* limitation that this document did not anticipate:
the corpus is league-only, so rest and congestion cannot see midweek cup or
European fixtures at all.

**Travel followed, and SPEC §3.6 is now closed** (`TRAVEL.md`, 2026-08-06). It
ran on the full 21,896 and returned a bounded null at ~3.7% per 500 km. Two
things in it bear directly on this document:

- **A control can fail because the statistic is wrong, not because the corpus
  is small.** Travel's pre-registered deviance-delta criterion missed a planted
  5% effect 0 times in 6; a Poisson score test caught it 5 of 6 on the same
  frames. Re-reading §7 with that statistic, `sun_late`'s planted +0.18 is
  **t = 4.14** — so what was underpowered here was the *deviance value*, never
  the effect's reality, which §4's permutation p = 0.0020 had already
  established. `engine/eval/power.py`, ledger `h35_power_revisit`.
- **The verdict is unchanged.** Five of the nine slots resolve only 7.6–12%
  even under the better statistic, which is a second and independent reason the
  nine-level arm was the wrong instrument. §8 stands.
