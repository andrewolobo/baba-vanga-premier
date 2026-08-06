# Rest — days since last match, measured and bounded

Measured **2026-08-04**. Code `engine/eval/rest.py`, results
`docs/rest_results.json`, ledger rows `h30`–`h33`.

The first of SPEC §3.6's replacement analogues, taken up where `TOD_SLOT.md` §9
left it. **This one is a real null, and it comes with a bound.**

Neither a six-band rest term nor the differential the SPEC actually asked for
improves goal deviance. The band arm returns **+0.00017** — worse than the
frozen head, and indistinguishable from the **+0.00020** the same arm returns on
data built with no rest effect in it at all. H33 catches a planted 5% attacking
deficit in 6 draws of 6 and puts the resolution threshold near **3.5%**.

Unlike the kickoff slot, this corpus was big enough to answer the question.

---

## 1. This one is not sample-limited

Rest comes from `match_date`, which every row has, so none of the 2019-20
constraint that killed the slot applies:

| | matches | match-sides |
| --- | --- | --- |
| kickoff slot (`TOD_SLOT.md`) | 5,644 | — |
| **rest** | **21,425** | **42,850** |

Eleven seasons: 2011-12 through 2022-23. Two are absent for reasons that are
not defects — 2010-11 is walk-forward burn-in, and 2020-21 is inside the COVID
embargo. 97.7% of matches have a previous league fixture for both sides; the
rest are opening weekends, where rest is undefined rather than missing.

Rest is computed on the **full fixture list**, before the harness drops burn-in
and embargoed matches. Computing it on the scored frame instead would have
measured the gap to the previous *scored* match and silently lengthened rest
wherever a real fixture had been removed.

## 2. The caveat that shapes every arm

**The corpus is league-only.** Five division files per season, no FA Cup, no
League Cup, no European ties. So "days since last match" is really "days since
last *league* match", and that makes measured rest an **upper bound on true
rest** — a hidden midweek tie shortens real rest and can never lengthen it.

The contamination is not evenly spread. Of the ten dates contributing the most
long gaps, **all ten** are FIFA international windows or FA Cup third-round
weekends:

```
2011-11-19  84    2019-11-23  53    2021-10-16  49    2014-09-13  48
2018-01-13  54    2021-09-11  53    2021-11-20  49    2018-10-20  48
2017-01-14  50                      2012-01-14  48
```

The monthly pattern says the same thing. Long gaps are 20.9% of match-sides in
November, 11.8% in September, 11.3% in October and 11.4% in January — the FIFA
windows and the cup — against **0.3% in August and 0.1% in May**, which have
neither.

So the short end of the scale is trustworthy and the long end is not. A club
measured at 3 days' rest really did play 3 days ago. A club measured at 14 days
may have played a European tie, a cup replay, or sent nine players on
international duty. Every arm below leans on the end that means something.

## 3. Nothing in the residual

Attacking residual is goals minus the side's own λ from the frozen head;
conceding residual is goals against minus the opponent's λ.

| band | n | attack | concede |
| --- | --- | --- | --- |
| `<=3` | 9,304 | −0.0147 [−0.0378, +0.0094] | −0.0295 [−0.0503, −0.0083] |
| `4` | 7,626 | −0.0019 [−0.0288, +0.0261] | +0.0158 [−0.0125, +0.0444] |
| `5-6` | 3,948 | −0.0114 [−0.0455, +0.0229] | −0.0106 [−0.0474, +0.0240] |
| `7` | 14,524 | +0.0126 [−0.0064, +0.0320] | +0.0149 [−0.0048, +0.0332] |
| `8-11` | 3,553 | +0.0044 [−0.0350, +0.0434] | −0.0013 [−0.0401, +0.0395] |
| `>=12` | 3,823 | +0.0083 [−0.0268, +0.0422] | +0.0048 [−0.0311, +0.0397] |

ANOVA on the attacking residual: F = 0.743, **p = 0.591**.

One cell — conceding on `<=3` days — clears an uncorrected 95% interval. **It
does not survive correction.** Twelve cells were tested; at Bonferroni 99.58%
nothing survives, and the direction is wrong anyway: it says tired teams concede
*fewer* goals. Read as a match-level effect it is the more sensible statement
that congested midweek fixtures are slightly low-scoring, and even that is
−0.0165 [−0.0520, +0.0203] on total goals when both sides are short-rested,
against +0.0288 [−0.0133, +0.0714] when both are on a normal week. Neither is
distinguishable from zero.

### The differential is flat

SPEC §3.6 asked specifically for "the *differential* between the two sides".

**r = −0.0040, p = 0.562, n = 21,425.**

The banded view is non-monotone — the only cell clearing zero is `-2..-1` at
+0.1196, with `>=3` at −0.0235 and `<=-3` at −0.0259 — which is the shape of
noise, not of an effect. It is also worth knowing that the differential is
**exactly zero in the majority of matches** (median 0, interquartile range
[0, 0]); only 13.2% of fixtures have a gap of 3 days or more either way.

## 4. On the selection metric, both arms cost

Fitted **leave-one-season-out** over eleven seasons. Positive = worse than the
frozen head.

| arm | goal deviance | O/U 2.5 log-loss |
| --- | --- | --- |
| 6 rest bands, per side | **+0.00017 [+0.00000, +0.00035]** · 1.9 SE | +0.00008 · 1.2 SE |
| differential slope (1 parameter) | +0.00003 [−0.00003, +0.00008] · 1.0 SE | — |

The fitted differential slope is −0.00327 goals per rest-day. Over the whole
observed range of the differential that is worth a few hundredths of a goal, and
it does not survive contact with the metric.

The one-parameter arm matters: a null on the six-band version could be blamed on
spending six degrees of freedom, and this removes that explanation.

## 5. The positive control, and the bound

Goals redrawn from the head's own λ times a planted band factor, so the effect
is present by construction and nothing else is. Scale 1 plants a 5% attacking
deficit at `<=3` days, 3% at `4`, 1% at `5-6`.

| planted | deficit at `<=3` | deviance delta | detected (6 draws) |
| --- | --- | --- | --- |
| ×0 | 0% | **+0.00020** | 0/6 |
| ×0.5 | 2.5% | −0.00010 · 0.5 SE | 1/6 |
| **×1.0** | **5%** | **−0.00094 · 2.8 SE** | **6/6** |
| ×2.0 | 10% | −0.00366 · 5.9 SE | 6/6 |

**The instrument works here.** A 5% deficit is caught every time; the 1.96-SE
resolution threshold sits near a **3.5%** deficit.

The ×0 row is the one to hold next to §4. Fitting six bands to data with no rest
effect costs **+0.00020**, and the real corpus returned **+0.00017**. The
measured result is not merely "not significant" — it is the number this arm
produces when the effect it is looking for does not exist.

## 6. Verdict

**Measured null, bounded at roughly 3.5%. Do not build it.**

This is a stronger statement than the kickoff slot's, and the contrast is the
useful part:

| | kickoff slot | rest |
| --- | --- | --- |
| sample | 5,644 | 21,425 |
| planted effect of the predicted size | caught 2/6 | caught 6/6 |
| what the interval means | cannot tell | **no effect of this size exists** |

Carrying forward:

- **Any true rest effect on scoring is smaller than about 3.5% of a goal rate**,
  and the differential is flat at r = −0.004. That is a bound, not an absence.
- **The league-only corpus is the standing limitation.** What was tested is
  rest-from-league-fixtures. A genuine congestion effect driven by European and
  cup football is *not* ruled out by this — it is unmeasurable here, because the
  matches that would create it are not in the data. Acquiring a full
  all-competitions fixture list is the only thing that would reopen it, and it
  would also be the input `TOD_SLOT.md` could not get.
- **The one apparent signal was multiplicity.** Twelve cells, one clearing an
  uncorrected interval, in the wrong direction, gone under Bonferroni. Worth
  recording because it is exactly the shape a false positive takes.

**Do not** re-litigate with finer bands, per-division rest terms, or a rest ×
strength interaction. The differential is the form the SPEC preferred and it is
the one measured most cleanly, on one parameter, at r = −0.004.

## 7. Where §3.6 goes next

Two analogues remain, and both are blocked on data rather than on power:

| analogue | state |
| --- | --- |
| **congestion** (matches in the trailing 14 days) | Same league-only limitation as §2, and it bites *harder* — congestion is precisely the count of the midweek ties the corpus does not hold. Not worth running before a fixture list exists. |
| **travel distance** | ~~Blocked on a stadium coordinate table.~~ **Table built 2026-08-06** — `reference/stadiums.csv`, **151 clubs** (not the 92 this row originally claimed; 92 is the Premier League plus EFL at one instant, not a sixteen-season club universe), every row verified against an independent geocode. The only one of the four with no confound of this kind. See `OUTSTANDING.md` §1.6. |
| **stakes** | Blocked on as-of league-table reconstruction (OPEN-4). |

Travel is the one to do next: it needs one small static table, it applies to
every match in the corpus, and its confounds (E1–E3 geography) are the kind λ
already absorbs rather than the kind that contaminates the feature itself.
