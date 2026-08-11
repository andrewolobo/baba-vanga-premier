# B12 gate results — shots and corners in the strength layer

Run **2026-08-10** against the pre-registration in `P4_CHANNELS_PLAN.md`. Code
`engine/eval/channels_gate.py`, tests `tests/test_channel_blend.py`, results
`docs/channels_gate_results.json`. Ledger `h37_channels_oracle_control` (probe,
2), `h38_channel_blend` (5), `h39_channel_decomposition` (6),
`h40_channels_divisions` (0). **176 → 189 configurations**, exactly the declared
13. Reproduce with
`python -m engine.eval.channels_gate --stage all --past-failed-control`.

**Headline: the channel is real and it is worth about half what was predicted.
Adding shots and corners to the shipped head improves goal deviance by −0.00217
[−0.00285, −0.00146], 6.0 paired SE, on 21,896 out-of-sample matches — and
almost all of it is corners. Total shots is nearly redundant with the channel
already shipped.** Eight of thirteen predictions were wrong, every one of them
in the same direction.

**Nothing is adopted here.** A head change owes the five things
`OUTSTANDING.md` §1.3 lists, and that is a separate decision.

---

## 1. The verdict, in one table

Against the shipped head `H400/a0.1/weekly/E0+E1+E2+E3+EC/sot0.3`, at the
selected composite weight w = 0.30, on 21,896 matches / 447 week blocks.
Negative is better.

| arm | channels | deviance | vs shipped | paired SE |
| --- | --- | --- | --- | --- |
| shipped | `sot` @ 0.30 | 2.87819 | — | — |
| `sot @ 0.3` | `sot` @ 0.30 | 2.87819 | **+0.00000** | exact |
| `+shots` | `sot, shots` | 2.87724 | −0.00095 [−0.00143, −0.00048] | 4.0 |
| **`+corners`** | `sot, corners` | 2.87623 | **−0.00196** [−0.00276, −0.00116] | 4.7 |
| **`+both`** | `sot, shots, corners` | 2.87602 | **−0.00217** [−0.00285, −0.00146] | 6.0 |
| `+noise ×2` (control) | `sot, noise1, noise2` | 2.89920 | **+0.02101** [+0.01811, +0.02387] | 14.6 |
| — oracle ceiling (H37) | `sot, shots*, corners*` | 2.87423 | −0.00396 [−0.00477, −0.00320] | 9.9 |

For scale: the shots channel that shipped is worth **−0.00422** on the same
instrument. This is **51%** of it, and **55%** of its own ceiling.

**The `sot @ 0.3` arm returning exactly +0.00000 is not filler.** It is the
nesting property checked in production rather than only in tests: the
generalised k-channel blend reproduces the served head bit for bit, so the
−0.00217 is the extra channels and not a reimplementation. The arm was in the
pre-registration to separate "the weight moved" from "the channels were added";
the weight did not move, so it became a determinism check instead.

## 2. The stop rule fired, and the gate ran anyway

**H37, the positive control, returned −0.00396 against a pre-registered bar of
≤ −0.008.** `P4_CHANNELS_PLAN.md` §4 says that stops the gate. It was continued
by owner decision, and `h38`/`h39`/`h40` are registered in
`trials.POST_HOC_TRIALS`. **No claim of pre-registration is made for them.**

The full account is `P4_CHANNELS_PLAN.md` §8, appended before H38 ran. In
short:

- **The bar was mis-derived.** It was copied from H25's sot oracle (−0.01636)
  without adjusting for two differences, both pushing the same way: H25 ran its
  oracle at **w = 0.6** where H37 runs at the shipped **w = 0.3**, and H25's
  baseline was **goals only** where H37's already carries a real sot channel.
- **The stop rule's stated reason was false.** §4 justifies stopping with *"the
  instrument is broken and that is the whole result"*. At 9.9 paired SE the
  instrument is not broken.
- **But real outcomes were in view when the decision was taken**, which is the
  line `OUTSTANDING.md` §1.6 draws between a legitimate amendment and the one
  `CALIBRATION.md` §1 forbids. Hence the conservative treatment rather than an
  argument that it did not matter.
- **The override is a command-line flag, not a relaxed threshold.**
  `--past-failed-control` leaves the check in the code and makes continuing a
  recorded act.

## 3. H37 — the ceiling, and why it is the most useful number here

Shots and corners replaced by low-noise reads of each club's season-long rates,
two-sided, `sot` left real, blended through the identical code path.

**A perfectly-measured shots+corners pair is worth −0.00396 on top of the
shipped head.** That is 94% of what the *real* sot channel was worth on top of
goals, so it is a coherent ceiling rather than a degenerate one.

**It refuted §3's H39 prediction before H39 ran.** The plan predicted the real
arm at −0.003 to −0.008; the ceiling is −0.004, so most of the predicted band
lay above what a perfect version of the feature could deliver. The prediction
was internally inconsistent and only running the control first exposed it.

**This is the third recorded instance of over-reading split-half reliability as
deviance.** `SHOTS_TARGET.md` §7 is the first, `CHANNELS.md` §6 warns about it
explicitly, and `P4_CHANNELS_PLAN.md` §1 did it again anyway — extrapolating
the within-harness ratio to −0.012 and discounting only to −0.008. The measured
answer is −0.00217. **The lesson has now failed to transfer twice, in both
cases because it was written as a caution rather than as an arithmetic bound.**
The bound exists and is cheap: run the oracle first and read every prediction
against it.

## 4. H38 — the weight did not move

`w ∈ {0, 0.15, 0.30, 0.45, 0.60}` on the three-channel composite.

| w | deviance | paired SE | 1X2 | O/U 2.5 |
| --- | --- | --- | --- | --- |
| 0.00 (goals only) | 2.88241 | 0.00097 | 1.04032 | 0.69194 |
| 0.15 | 2.87823 | 0.00064 | 1.03873 | 0.69058 |
| **0.30 ← 1-SE choice** | **2.87602** | 0.00032 | 1.03800 | 0.68980 |
| 0.45 (best) | 2.87581 | 0.00000 | 1.03813 | 0.68963 |
| 0.60 | 2.87761 | 0.00033 | 1.03914 | 0.69008 |

**Interior optimum, `censored: None`, spread 0.00661.** The 1-SE rule selects
**0.30 — the weight already shipped** — with 0.45 the raw best and inside one
paired SE of it. Predicted "w\* ≥ 0.30 and interior": right on both, though the
interesting part is that a composite of three channels wants no more weight
than one channel did.

**A free reproduction check.** Goals-only to shipped is **−0.00422** on this
run, which is `SHOTS_TARGET.md`'s published figure for the shots channel to five
decimal places, measured by different code three weeks later. Goals-only to the
full three-channel head is **−0.00639**, so the whole auxiliary layer is worth
about half as much again as it currently is.

## 5. H39 — corners does the work, and shots is nearly redundant

**This is the finding, and it contradicts the pre-gate.**

| | attack | defence | deviance |
| --- | --- | --- | --- |
| pre-gate split-half gain (`CHANNELS.md` §1) | | | |
| shots | +0.0293 | +0.0424 | **−0.00095** |
| corners | +0.0342 | +0.0340 | **−0.00196** |
| shots + corners | +0.0490 | +0.0540 | **−0.00217** |

- **Corners is worth 2.1× shots**, on channels the pre-gate ranked as roughly
  equal — and shots was the one it ranked *better on defence*, which is where
  the shipped channel is strongest.
- **Adding shots on top of corners is worth −0.00021**, smaller than the paired
  SE of either arm against the shipped head (0.00024–0.00042). *The paired
  comparison between `+corners` and `+both` specifically was not run*, so this
  is a point estimate rather than a measured null — but nothing here resolves
  it, and `goals + sot + corners` captures **90%** of the full gain with one
  fewer channel.
- **`CHANNELS.md` §1's "complementary, not redundant" does not survive the
  translation to deviance.** It was true of split-half reliability and it is
  not true of the objective the head is selected on. M5's collinearity
  measurement — `sot ~ shots` at 0.9748 attack / 0.9607 defence — turns out to
  have been pointing at something real after all, even though `CHANNELS.md` §3
  correctly voided it *as a veto rule*. The diagnostic was right about shots
  and would still have been wrong about the gate, since it also fires on
  `goals ~ sot` at 0.9712.

**The negative control is emphatic and it matters.** Two channels carrying no
information, entering the composite exactly as the real ones do, make the head
**+0.02101 worse** — 14.6 SE in the wrong direction, and ten times the size of
the real effect. The composite arithmetic manufactures nothing. This is the
control `P4_CHANNELS_PLAN.md` §2 built the renormalisation for: because the
composite is rescaled to the goal-fit's dispersion whatever the channel count,
the noise arm differs from the real arm **only** in carrying no information,
which is the property `OUTSTANDING.md` §9.6 records a previous control failing.

## 6. H40 — per division, the markets, and the gap

| division | n | vs shipped | 95% block CI | deficit before → after |
| --- | --- | --- | --- | --- |
| pooled | 21,896 | **−0.00217** | [−0.00285, −0.00146] ✱ | +0.01230 → **+0.01177** |
| E0 | 4,088 | −0.00223 | [−0.00405, −0.00030] ✱ | +0.00976 → +0.00931 |
| E1 | 5,952 | −0.00285 | [−0.00416, −0.00152] ✱ | +0.01272 → +0.01186 |
| E2 | 5,908 | −0.00273 | [−0.00403, −0.00153] ✱ | +0.01409 → +0.01342 |
| **E3** | 5,948 | **−0.00088** | **[−0.00208, +0.00030]** | +0.01185 → +0.01174 |

**E3 does not resolve, and it breaks two predictions at once**: the effect is
not present in all four divisions, and the largest is **3.23×** the smallest
against a pre-registered bar of 3×. The point estimate is still negative.

**E3 being the weakest is worth recording rather than explaining away.** It is
also the division where the head captures least of the market's edge (0.598
against E0's 0.909, `OUTSTANDING.md` §1.3), so the division with the most room
is the one this channel helps least. Nothing here says why, and §3.1's
unexplained division asymmetry gains a fourth measurement rather than an answer.

**Markets, reported and never selected on.** 1X2 improves **0.00053** and O/U
2.5 improves **0.00074**, both against a predicted 0.001–0.003. Both move the
same way as deviance, so there is no OPEN-3-style disagreement to write down.

**The book stays off and this is not close.** The pooled deficit moves +0.01230
→ +0.01177 — **4.3% of the gap** — against a vig of 0.02122 at average prices
and 0.00201 at best available. `CALIBRATION.md` §5 stands untouched, and per
`OUTSTANDING.md` §2.3 nats and de-vigged probability do not net.

## 7. Prediction scorecard

Five right, eight wrong, **and every wrong one is over-optimistic in the same
direction**.

| # | prediction | outcome |
| --- | --- | --- |
| H37 | oracle ≤ −0.008, CI excluding zero | **wrong** — −0.00396 (CI does exclude zero) |
| H38 | 1-SE rule selects w\* ≥ 0.30 | right — 0.30 |
| H38 | optimum interior | right — `censored: None` |
| H39 | `+both` improves −0.003 to −0.008 | **wrong** — −0.00217, below the band |
| H39 | both singles negative | right |
| H39 | `+both` beats either single | right |
| H39 | `+both` sub-additive | right — −0.00217 against a sum of −0.00291 |
| H39 | `+noise ×2` not negative | right — +0.02101 |
| H40 | negative in all four divisions, every CI excluding zero | **wrong** — E3 [−0.00208, +0.00030] |
| H40 | largest division effect < 3× smallest | **wrong** — 3.23× |
| H40 | 1X2 improves 0.001–0.003 | **wrong** — 0.00053 |
| H40 | O/U improves 0.001–0.003 | **wrong** — 0.00074 |
| H40 | deficit lands in +0.008 to +0.011, not zero | **wrong on the band** (+0.01177); right that it does not reach zero |

**The errors are not independent — they are one error propagating.** Every
miss follows from the size of the effect being half what §1 extrapolated, and
that extrapolation is the reliability→deviance mapping §3 above says is now
mis-read for the third time. `CHANNELS.md` §5 recorded the pre-gate's error as
*expecting the corpus to yield less than it does*; this gate made the opposite
error on the same feature. The common cause is that neither was anchored to a
measured bound, and one was available for two configurations.

## 8. What this licenses, and what it does not

**It licenses an adoption decision, and nothing more.** The effect is real,
resolved at 6.0 paired SE, negative in all four divisions and resolved in three
of them, improves both reported markets, and survives a negative control that
fails by ten times the effect size. Under the tipster objective a better λ
improves every item on the published menu at once (`OUTSTANDING.md` §9.3), so
this is not scoped to a market that is switched off.

**Against adopting it:** it is half the size of the channel already shipped, it
costs a head change and therefore the five steps of §1.3 — including re-running
`engine/eval/tips.py`'s claims block, because the published strike rate is a
property of the head, not of the rule — and 90% of it is available from corners
alone, which is a smaller change.

**A leaner arm exists and was measured**: `goals + sot + corners` at −0.00196.
If the head is changed at all, that is the version to consider first, and it
needs no further gate — it is arm 4 of `h39_channel_decomposition`.

**It does not touch the book** (§6), it does not bear on the `12`-versus-`1X`
question (`BACKLOG.md` B10), and **it is not evidence about B11's goal-line
tails.** A better-centred λ says nothing about tail calibration, which is
measured against realised results and is still unrun.

## 9. Two things found on the way that are not results

**`p4_shots.HEAD` is the head as it stood *before* the shots channel was
adopted**, and taking it for the served head is a silent, symmetric mistake:
every arm loses the sot channel together, so they still differ from each other
and the gate returns a plausible-looking null. It was caught by a four-season
smoke run during development, before any ledger row existed — disclosed here
because that run scored real outcomes, so it is information seen before the
gate. `rest.py`, `tod.py`, `travel.py` and `meta.py` each write the served head
out in full for this reason; `channels_gate.py` now does too, with the reason in
a comment rather than in a document.

**The blend's arithmetic is one ulp away from not nesting.** `w * att_c * scale`
and `w * (att_c * scale)` are different floating-point expressions, and the
first refactor of `_blend_channels` picked the second. The served head's λs then
moved in the last bits across all 27,815 matches. The unit test asserting
bit-for-bit nesting **passed anyway**, because the discrepancy is usually
absorbed by the `(1-w)·base` term it is added to. `auxiliary_term` is now
module-level and pinned by a test on the expression itself rather than through
a fit. **A property that only sometimes shows up in a test is not tested**, and
this is the second time on this project that a test could not see the thing it
was written to guard (`OUTSTANDING.md` §1.11's API concurrency defect is the
first).
