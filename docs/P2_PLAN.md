# P2 pre-registration — the player prior

Written 2026-08-03, **after** the SPEC §3.3 orthogonality pre-gate and **before**
any gate is run. Pre-gate numbers are in §1; they are measurements, not
predictions, and they are what makes the rest of this document look the way it
does. Predictions for the gates themselves are in §4 and are scored in
`PLAYER_PRIOR.md` without editing this file.

Reproduce with `python -m engine.eval.p2 --stage all`.

---

## 1. The pre-gate, which SPEC §3.3 requires before building anything

> "Run the orthogonality pre-gate before building anything. Regress fitted team
> `att`/`dfn` on the player aggregate. gtleague's sofifa pre-gate found
> R² ≈ 0.01 — orthogonal but useless. The likely failure here is the mirror
> image: R² high, meaning the aggregate re-derives what the GLM already knows,
> and the value lives only in the residual."

**The mirror image is what happened, and then some.** Three measurements, all on
the dev set (2012-13 → 2022-23, 1,231 club-seasons), everything z-scored inside
its own (season, division) cell so the cross-division scale cannot manufacture
a correlation.

### 1.1 The aggregate is the club

Minutes-weighted squad strength, built legally from the club's season N−1
roster:

| aggregate | corr with `att_pre` | corr with `dfn_pre` |
| --- | --- | --- |
| `sq_att` | **+0.980** | −0.342 |
| `sq_dfn` | −0.322 | **+0.982** |
| `sq_ga90` | +0.547 | −0.168 |
| `sq_churn` | −0.174 | +0.174 |
| `sq_age` | +0.015 | −0.143 |
| `sq_top11` | +0.032 | −0.059 |

This is not a surprise once the audit is read: the N−1 roster plays **52–75% of
the club's own N−1 minutes** (§2). A squad aggregate built from that roster is
a re-statement of the club's own results, which is exactly what the GLM fits.

### 1.2 The residual is empty

Target: the club's realised season-N goals per match, z-scored within
(season, division). Baseline is `att_pre` **and** `dfn_pre` — both, deliberately.
With `att_pre` alone, `sq_dfn` appears to add +0.124 R² on the division-change
population, which looks like a player finding and is not: `att_pre` alone is a
noisy measure of club quality, `dfn_pre` carries more of it, and any aggregate
correlated with overall quality inherits the omission.

| population | n | GLM R² | best ΔR², attack | best ΔR², defence |
| --- | --- | --- | --- | --- |
| all club-seasons | 1,231 | 0.216 / 0.201 | +0.006 (`top11`) | +0.006 (`top11`) |
| **changed division** | 260 | 0.250 / 0.204 | +0.011 (`sq_dfn`) | +0.016 (`sq_dfn`) |
| same division | 971 | 0.212 / 0.201 | +0.010 (`ga90`) | +0.008 (`churn`) |

Nothing clears +0.016, on the population the feature exists for, at n=260.

### 1.3 There is no cold start to fix — the finding that matters

SPEC §3.3 rests on a premise: *"A team with 46 matches of direct evidence needs
no help; a newly-promoted team in August is nothing but prior."* Measured:

**Decayed training weight standing behind the thinner of the two clubs, in units
of matches, at that match's own fit cutoff:**

| min | 1st pct | 10th pct | median | max |
| --- | --- | --- | --- | --- |
| **25.8** | 33.3 | 50.7 | 65.2 | 77.6 |

There is no thin tail. Not one scored match in thirteen seasons is played by a
club carrying fewer than **25.8 effective matches** of evidence. The imported
doctrine — gtleague's finding that 82.5% of post-rotation rows were clubs
decayed to ~1% weight — describes a population that does not exist here.

And the head's deficit to the market does not widen as evidence thins. It
narrows:

| evidence (effective matches) | n | model − market, 1X2 logloss |
| --- | --- | --- |
| 25.8 – 50.7 | 2,412 | **+0.01014** [+0.00356, +0.01736] |
| 50.7 – 57.9 | 3,619 | +0.01230 [+0.00747, +0.01709] |
| 57.9 – 65.2 | 6,032 | +0.01380 [+0.01014, +0.01728] |
| 65.2 – 69.3 | 6,030 | +0.01601 [+0.01210, +0.02000] |
| 69.3 – 77.6 | 6,032 | +0.01552 [+0.01158, +0.01942] |

Nor is a promoted club harder to price. Deficit to market, first 45 days of a
season: **+0.01513** [+0.00816, +0.02172] where either club changed division,
**+0.01318** [+0.00753, +0.01902] where both stayed put. The intervals sit on
top of each other.

### 1.4 Why the premise was wrong

**P1 already solved this, and the solution was NEW-1.** Fitting all five
divisions jointly means a division change is not an entity rotation — the club
never leaves the pool, it just meets different opponents. SPEC §3.3 read across
from a repo where rotation meant clubs *disappearing*, and English promotion is
not that.

`BASELINE.md` §3 measured the size of what NEW-1 bought: clubs promoted out of
the National League are predicted **0.058 nats better** when the fit has seen
their EC matches. That number has been carried since as P2's motivation. It is
better read as P2's obituary: **it is the value of lower-division history, and
P1 has already banked it.**

---

## 2. The audit the pre-gate rests on

`player_seasons` holds 57,345 rows, 16 seasons × 5 divisions, complete.

| property | measured |
| --- | --- |
| files present | 80 / 80 |
| rows with usable minutes | 57,344 / 57,345 |
| club-season minutes vs 11 × 90 × fixtures | ratio 0.997–0.998 in every division |
| ids joinable across seasons (hex) | 55,739; **1,605 slug**, all EC and all pre-2018-19 |
| a season's players seen in an earlier season | 78–85% |
| cross-division player moves per season | 989 – 1,440 |

**Roster continuity — the ceiling on anything an N−1 prior can know.** Share of
season N minutes played by players on that club's season N−1 roster:

| division | 25th | median | 75th |
| --- | --- | --- | --- |
| E0 | 0.661 | **0.746** | 0.814 |
| E1 | 0.532 | 0.624 | 0.711 |
| E2 | 0.458 | 0.546 | 0.646 |
| E3 | 0.416 | 0.520 | 0.628 |
| EC | 0.247 | 0.424 | 0.573 |

Two readings, and both matter. The share is high enough that the N−1 roster is
mostly the same club — which is §1.1. It is also low enough that half of E3's
minutes each season are played by someone the prior has never seen at that club,
which caps what the feature could deliver even if it worked.

**Target population:** 356 division changes + 56 clubs new to the corpus across
15 season transitions = **23.7% of club-seasons**. Large. It is the *evidence*
behind them that turns out not to be thin, not their number.

---

## 3. What is still worth building, and why bother

The pre-gate says stop. I am running one gate anyway, for three reasons:

1. **The instrument is indirect.** R² on club-season scoring rates is a proxy
   for match-level goal deviance, which is what selects. This project has twice
   found a proxy pointed the wrong way (the 1-SE marginal/paired bug reversed a
   gate verdict; the "positive CLV" in P3 was an artifact of mismatched price
   bases). A null on the metric that decides is worth more than a null on a
   proxy.
2. **A null needs a positive control to mean anything.** H17 exists to prove the
   harness can see a prior when there is one to see. Without it, "no effect"
   and "no instrument" are the same output.
3. **The build is small and the arm nests the baseline** at prior weight 0, so
   there is no risk of the comparison drifting on anything but the feature.

**Scope, deliberately narrow.** No age curve (SPEC §3.5), no per-player
ratings model, no gap-replay harness. Gap-replay exists to calibrate a
synthetic cold start against a real one; §1.3 says there is no real one to
calibrate against, so building it would be measuring an effect on a population
that does not exist.

### 3.1 Construction

Refresh at season boundaries only, per `asof.PLAYER_SEASON_RULE`. A prediction
in season N may read player files for seasons ≤ N−1; season N's file is
embargoed entire, because knowing who plays for a club in season N encodes both
the transfer and the survivorship.

At each 1 August:

1. Fit the frozen head on matches strictly before the boundary → `att`, `dfn`.
2. Player level = minutes-weighted mean of the current strength of every club
   the player has played for, over seasons ≤ N−1, decayed by 0.5 per season.
3. Club prior `m_att[C]`, `m_dfn[C]` = minutes-weighted mean over C's N−1
   roster, weighted by minutes played **for C** in N−1.
4. Ridge target moves from 0 to `w · m`, w swept. `w = 0` is today's model
   exactly.

Clubs with no N−1 roster keep a prior of 0, which is the current cold-start
behaviour and the correct one.

---

## 4. Hypotheses, with numbers

Selection metric is goal Poisson deviance; 1X2 and O/U reported, not selected
on. Sign convention throughout: **negative = the prior helps.** All comparisons
paired by ISO week.

**The arithmetic behind the predictions.** ΔR² of ~0.01 on a club-season target
whose z-scored sd is 1, at a club-season sd of log goals-per-match of ≈0.15,
is ≈0.015 in log λ. A squared-error reduction of 0.015² in log λ moves Poisson
deviance by roughly λ·0.000225/2 per side, ≈0.0003 nats per match. The paired
standard error on the full dev corpus is ≈0.00025. **The predicted effect and
the resolution of the instrument are the same size.** That is the honest prior
and every prediction below follows from it.

| # | hypothesis | prediction |
| --- | --- | --- |
| **H14** | Prior-anchored ridge, w ∈ {0, 0.25, 0.5, 0.75, 1.0} | Chosen w ≤ 0.25. \|Δ deviance\| < 0.0005 at every w, CI spans zero at w = 0.25 |
| **H15** | Orthogonal channels only (`sq_age`, `sq_churn`) as the prior | \|Δ\| < 0.0005, CI spans zero |
| **H16** | H14 restricted to the population it was designed for: first 45 days, either club changed division | \|Δ\| < 0.002, CI spans zero. n ≈ 1,500 |
| **H17** | **Positive control.** Prior = the club's realised season-N strength (an oracle; illegal, never served) | Δ ≤ **−0.010**, CI excludes zero. If this fails the other three results are void |
| **H18** | E3, where P1 captures the smallest share of the market's edge (0.51) | \|Δ\| < 0.001. If any division moves it is this one |

**Stop condition, pre-committed.** Ship the prior only if H14's chosen w > 0
with a paired CI excluding zero **and** the effect survives in E0–E3 separately
without a sign flip. Anything else: record the null, delete nothing, and write
down that the player layer is descoped.

**What would make me wrong, and I want it on the record:** if H17 passes big
and H14 lands at −0.001 with a CI excluding zero, then the aggregate is weak
rather than the idea, and the next move is a real per-player ratings model
rather than minutes-weighted club association. §1.3 is the reason I do not
expect that — the cold start is absent, not merely small.

---

## 5. Ledger

Every arm above, including H17, is recorded whatever it returns. The ledger
stands at 45 trials before this plan; P2 adds one per arm plus the sweep.
`OUTSTANDING.md` §3.2 — how re-runs feed PBO deflation — is still open and this
plan does not settle it.
