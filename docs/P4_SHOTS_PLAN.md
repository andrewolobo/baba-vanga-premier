# P4-shots pre-registration — a shots channel in the strength layer

Written **2026-08-04**, before any arm is run. Predictions are numeric so they
can be wrong. Results will go in `SHOTS_TARGET.md`; this file stays unedited.

Follows the pre-gate recorded as `probe:p4_shots_target_pregate`, which passed
— and which refuted the SPEC's proposed mechanism on the way.

---

## 1. What the pre-gate established

| measurement | result | consequence |
| --- | --- | --- |
| M1 conversion persistence | r = **+0.098** year to year | conversion is near-noise, so shots-on-target reads underlying rate more cleanly than goals |
| M2 split-half, attack | goals 0.441 · sot 0.446 · **goals+sot 0.480** | shots *add*; they do not replace |
| M2 split-half, defence | goals 0.408 · shots 0.458 · **shots+sot 0.469** | the channel is strongest here |
| M3 headroom | oracle beats market by **−0.01154**; served is **+0.01419** behind | the functional form is not the limit — estimation precision is |

**SPEC §3.7 is refuted in its specifics and upheld in its motivation.** It
proposed *replacing* the fitted target with a shots-derived expectation. On
attack, `goals + sot` (0.480) beats `shots + sot` (0.459): dropping goals throws
away real information. The design below therefore **adds a channel** rather than
substituting a target, and that departure is recorded here rather than
discovered later.

## 2. The construction

A second Poisson fit on the identical design matrix, with shots-on-target as
the count instead of goals:

```
goals:  log E[g]   = c  + home·h  + att_g[i] + dfn_g[j]
sot:    log E[sot] = c' + home·h' + att_s[i] + dfn_s[j]
```

Both are log-link Poisson over the same teams at the same cutoff with the same
decay, so `att_s` and `att_g` live on the same log scale up to the intercept —
if conversion were constant, `log E[g] = log(conv) + log E[sot]` exactly. They
differ in magnitude because sot counts are ~3.5× higher and therefore take
relatively less shrinkage from the same ridge, so the blend rescales by the
ratio of their standard deviations:

```
att* = (1-w)·att_g + w·att_s·( sd(att_g) / sd(att_s) )
```

**Nesting is exact.** At `w = 0` this is `att_g` bit for bit, so the arm
contains its own baseline and any measured difference is the feature, not a
reimplementation. Asserted in tests, as for the P2 squad prior.

### 2.1 The National League hole

EC carries shot statistics for 2010-11 → 2015-16 and **none from 2016-17
onward** — the publisher stopped collecting them:

```
             E0     E1     E2     E3     EC
201516    100.0  100.0  100.0  100.0  100.0
201617    100.0  100.0  100.0  100.0    0.0
```

Left alone, EC clubs would take `att_s ≈ 0` from the ridge — not "average", but
*fabricated* — and a club promoted into E3 would carry that fabrication into the
division we actually price. So the blend applies **per team, only where that
team has real shots evidence**: below `MIN_SOT_EVIDENCE` decayed matches a club
keeps `att_g` untouched. A club we cannot measure is left alone rather than
averaged, the same rule `Artifact.predict` follows for unknown clubs.

## 3. Arms and predictions

Selection metric is goal Poisson deviance, on the frozen head
`H400 / a0.1 / weekly / E0+E1+E2+E3+EC`. Sign convention: **negative = the
blend is better.** Scored E0–E3, COVID embargoed, paired block bootstrap by ISO
week, 1-SE rule with the tie-break toward `w = 0`.

**H20 — the blend sweep.** `w ∈ {0, 0.15, 0.3, 0.45, 0.6, 0.8}`.
*Predict:* the rule selects `w ∈ [0.15, 0.45]`; deviance at the selected `w`
improves by **0.003 to 0.007**, CI excluding zero.
*Basis:* M2 closes ~7% of the attack reliability gap and ~10% of defence;
against M3's 0.057 nats of headroom that is 0.004–0.006.

**H21 — defence carries more than attack.** Blend `dfn` only, and `att` only.
*Predict:* dfn-only delivers **≥ 60%** of the full effect, att-only **≤ 50%**.
*Basis:* M2's defence gain (+0.060) is about 1.5× the attack gain (+0.039).

**H22 — per division.** *Predict:* the effect is present and negative in all
four, and the largest division effect is **< 3×** the smallest. No prediction
that lower divisions benefit more; the pre-gate did not measure that.

**H23 — the reported markets.** *Predict:* 1X2 improves **0.001–0.003** and
O/U 2.5 improves **0.001–0.003**. Reported, never selected on.

**H24 — the gap to the market.** *Predict:* the pooled 1X2 deficit moves from
**+0.01419** to between **+0.010 and +0.013**. It does **not** reach zero, and
nothing here should be read as beating the book.

**H25 — positive control.** An oracle blend whose `att_s`/`dfn_s` come from an
end-of-season sot fit must beat the legal blend by a wide margin.
*Predict:* oracle ≤ **−0.015** deviance against baseline, CI excluding zero.
*Why:* P2's null was only interpretable because H17 proved the harness could
see a real prior. If H25 fails, H20's result means nothing and must not be
reported as a null.

## 4. Stop conditions, committed in advance

- **If H25 fails**, nothing else is reported as a finding. The instrument is
  broken and that is the whole result.
- **If the 1-SE rule selects `w = 0`**, the channel does not ship. It will be
  recorded as a measured null, as P2 was.
- **If the sweep optimum is on a grid boundary**, the grid was too narrow —
  widen and re-run, per `SweepResult.censored`.
- **If deviance improves but 1X2 degrades**, that disagreement is the finding
  and gets written down before any ship decision, as OPEN-3 did.

## 5. What this cannot become

It cannot turn the book on. `CALIBRATION.md` §5 stands and this changes nothing
about it: closing a fifth of a 0.0142 gap leaves the head behind the market,
and the vig is 0.02122 at average prices. Any temptation to re-open the book
needs its own gate and its own pre-registration.
