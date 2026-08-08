"""B2 and B3: fix the under-confidence, and measure the double-chance floor.

    python -m engine.eval.selection --dry-run
    python -m engine.eval.selection

Pre-registration in `PRODUCT.md` §3a, written before either arm ran. Two gates
sharing one corpus because they share a dependency: B3's floor is measured on
whichever probabilities B2 leaves behind, so running them apart would measure
the floor on numbers that were about to change.

**B2 — the under-confidence.** The head understates its own favourites in every
bucket, by up to 5.9 points (`OUTSTANDING.md` §1.10). That is the signature of
an independent-Poisson 1X2 fit, which spreads mass across scorelines and
under-states extreme outcomes, and `calibration.fit_vector_scaling` is the
matching correction: a per-class slope on log-p, fitted walk-forward.

**This is not P3 re-litigated.** P3 fitted calibration to improve *log loss* for
a betting rule and came back null (`CALIBRATION.md`). The target here is the
accuracy of the top-end probability that decides whether a fixture is tipped at
all, and the payoff is expected in **volume** rather than in strike rate: a
fixture the head prices at 0.53 when the truth is 0.57 is a tip the product is
currently not making.

**B3 — the floor.** The rule is `PRODUCT.md` §3a: recommend the outright
favourite when it clears FLOOR, otherwise step down to double chance unless that
would breach CEILING. The ceiling is a veto, never a selector -- measured
beforehand, a ceiling used as the selector makes outrights unreachable and turns
the product into a goal-line tipster.
"""

from __future__ import annotations

import argparse
import json

import numpy as np
import pandas as pd

from engine import db, ledger, store
from engine.eval import bootstrap
from engine.eval.dispersion import outcome_probs, score_matrix
from engine.eval.p1 import served
from engine.eval.travel import HEAD
from engine.eval.walkforward import walk_forward
from engine.models import calibration as cal
from engine.seasons import DEV_SEASONS, SERVED_DIVISIONS

#: Seasons of history before the first calibration fit, as `p3.py`.
BURN_IN_SEASONS = 3

#: B3's grid. The floor is the thing being measured; the ceiling is reported at
#: one value because it is a veto, and a grid over it would spend configurations
#: on a parameter that changes almost nothing (double chance averages 0.687,
#: well under any sane cap).
FLOORS = (0.45, 0.50, 0.55, 0.60)
CEILING = 0.85

#: Owner decisions, 2026-08-06. The floor is the product's central setting; see
#: `BACKLOG.md` B3 for the strike-rate/hedging trade it was picked from.
SHIPPED_FLOOR = 0.55

#: `12` (home or away, i.e. "not a draw") on the fallback menu. Owner decision,
#: reversing the exclusion `PRODUCT.md` §3a shipped with. It is the least
#: specific of the three double chances -- it names no team -- and `recommend`
#: explains why it takes almost the whole fallback when allowed.
ALLOW_12 = True

#: Where the tip rule currently sits, so B2's volume claim is stated at the
#: threshold actually shipped.
SHIPPED_THRESHOLD = 0.55

BUCKETS = ((0.50, 0.55), (0.55, 0.60), (0.60, 0.65), (0.65, 0.70), (0.70, 1.01))


def load(conn) -> pd.DataFrame:
    raw = store.read_matches(conn, seasons=DEV_SEASONS).for_measurement()
    frame = served(walk_forward(raw, HEAD)).reset_index(drop=True)
    return frame.dropna(subset=["ftr"]).reset_index(drop=True)


def raw_probs(frame: pd.DataFrame) -> np.ndarray:
    joint = score_matrix(frame.lam_h.to_numpy(float), frame.lam_a.to_numpy(float))
    return np.column_stack(outcome_probs(joint))


def walk_forward_calibrate(frame: pd.DataFrame, probs: np.ndarray) -> np.ndarray:
    """Vector scaling fitted only on strictly earlier seasons.

    Pooled rather than per-division: the defect being corrected is a property of
    the Poisson likelihood, not of any league, and four populations would spend
    four times the data to fit the same shape.
    """
    seasons = sorted(frame.season.unique())
    out = np.full_like(probs, np.nan)
    for i, season in enumerate(seasons):
        if i < BURN_IN_SEASONS:
            continue
        train = frame.season.isin(seasons[:i]).to_numpy()
        test = (frame.season == season).to_numpy()
        fit = cal.fit_vector_scaling(probs[train], frame.ftr[train])
        out[test] = fit.apply(probs[test])
    return out


def calibration_table(frame, probs, scored, label: str) -> list[dict]:
    """Claimed versus delivered, in the buckets where the tips live."""
    pick = probs.argmax(axis=1)
    p = probs[np.arange(len(probs)), pick]
    won = (pick == frame.ftr.map({"H": 0, "D": 1, "A": 2}).to_numpy())

    print(f"\n  {label}")
    rows = []
    for lo, hi in BUCKETS:
        sel = scored & (p >= lo) & (p < hi)
        if sel.sum() < 50:
            continue
        actual = float(won[sel].mean())
        half = 1.96 * float(np.sqrt(actual * (1 - actual) / sel.sum()))
        claimed = float(p[sel].mean())
        verdict = ("overconfident" if actual < claimed - half
                   else "under-confident" if actual > claimed + half
                   else "calibrated")
        rows.append({"bin": [lo, hi], "n": int(sel.sum()),
                     "claimed": round(claimed, 4), "actual": round(actual, 4),
                     "half_width": round(half, 4), "verdict": verdict})
        print(f"    [{lo:.2f},{hi:.2f})  n={sel.sum():>5,}  claims "
              f"{100*claimed:.1f}%  delivers {100*actual:.1f}% +/- {100*half:.1f}"
              f"   {verdict}")
    return rows


def b2_calibration(frame, raw, calibrated, scored) -> dict:
    """Does the correction work, and what does it buy?"""
    print("\nB2  the under-confidence")
    before = calibration_table(frame, raw, scored, "before (raw pmf)")
    after = calibration_table(frame, calibrated, scored, "after (vector scaling)")

    won = frame.ftr.map({"H": 0, "D": 1, "A": 2}).to_numpy()
    out = {"before": before, "after": after, "volume": []}
    print(f"\n  volume and strike at the shipped threshold "
          f"{SHIPPED_THRESHOLD}, on {int(scored.sum()):,} scored matches:")
    for name, probs in (("raw", raw), ("calibrated", calibrated)):
        pick = probs.argmax(axis=1)
        p = probs[np.arange(len(probs)), pick]
        sel = scored & (p >= SHIPPED_THRESHOLD)
        strike = float((pick[sel] == won[sel]).mean())
        out["volume"].append({"probs": name, "tips": int(sel.sum()),
                              "share": round(float(sel.sum() / scored.sum()), 4),
                              "strike": round(strike, 4)})
        print(f"    {name:11s} {sel.sum():>6,} tips ({100*sel.sum()/scored.sum():.1f}% "
              f"of matches)  strike {100*strike:.1f}%")
    gain = out["volume"][1]["tips"] / max(out["volume"][0]["tips"], 1) - 1.0
    out["volume_gain"] = round(gain, 4)
    out["removes_underconfidence"] = all(r["verdict"] != "under-confident"
                                         for r in after)
    print(f"    volume {gain:+.1%}; under-confidence "
          f"{'REMOVED' if out['removes_underconfidence'] else 'STILL PRESENT'}")
    return out


def recommend(probs: np.ndarray, floor: float, ceiling: float = CEILING,
              *, allow_12: bool = True):
    """`PRODUCT.md` §3a. Returns (market, probability) per match.

    Outright if it clears `floor`; otherwise the likeliest double chance that
    does not breach `ceiling`; otherwise the outright anyway, so every match
    carries a recommendation.

    The ceiling vetoes a fallback that would be a near-certainty; it never
    selects across market families, so it cannot pull the recommendation into a
    wide goal line the way a ceiling-as-selector does.

    **`12` dominates the fallback when it is allowed, and that is arithmetic
    rather than a quirk.** `1X` beats `12` only when `p_d > p_a`, and `X2` beats
    it only when `p_d > p_h` -- both of which need a draw more likely than a
    result, which is rare anywhere and rarest in exactly the population that
    reaches the fallback (a weak outright means a live opponent). `allow_12` is
    an owner setting, on by decision of 2026-08-06.
    """
    p_h, p_d, p_a = probs[:, 0], probs[:, 1], probs[:, 2]
    home = p_h >= p_a
    outright_p = np.where(home, p_h, p_a)

    candidates = {"1X": p_h + p_d, "X2": p_a + p_d}
    if allow_12:
        candidates["12"] = p_h + p_a
    names = list(candidates)
    stack = np.column_stack([candidates[n] for n in names])
    # Only fallbacks under the ceiling are eligible; -1 makes a breach lose.
    eligible = np.where(stack <= ceiling, stack, -1.0)
    best = eligible.argmax(axis=1)
    fallback_p = eligible[np.arange(len(stack)), best]

    take_outright = (outright_p >= floor) | (fallback_p < 0)
    market = np.where(take_outright,
                      np.where(home, "H", "A"),
                      np.array(names)[best])
    probability = np.where(take_outright, outright_p, fallback_p)
    return market, probability


def _won(market: np.ndarray, ftr: np.ndarray) -> np.ndarray:
    return np.select(
        [market == "H", market == "A", market == "1X", market == "X2",
         market == "12"],
        [ftr == "H", ftr == "A", np.isin(ftr, ["H", "D"]),
         np.isin(ftr, ["A", "D"]), ftr != "D"],
        default=False)


def b3_floor(frame, probs, scored) -> dict:
    """What each floor publishes, and how often it is right."""
    ftr = frame.ftr.to_numpy()
    dates = frame.match_date
    print(f"\nB3  the double-chance floor (ceiling {CEILING}, "
          f"{int(scored.sum()):,} matches)")
    print(f"    {'floor':>6} {'double chance':>14} {'strike':>8} "
          f"{'[95% block CI]':>20} {'outright-only strike':>21}")

    rows = []
    for floor in FLOORS:
        market, _ = recommend(probs, floor, allow_12=ALLOW_12)
        won = _won(market, ftr)
        idx = np.flatnonzero(scored)
        blocks = bootstrap.week_blocks(dates.iloc[idx])
        cmp = bootstrap.paired(-won[idx].astype(float), np.zeros(len(idx)), blocks)
        dc_share = float(np.isin(market[idx], ["1X", "X2", "12"]).mean())
        mix = {m: round(float((market[idx] == m).mean()), 3)
               for m in ("H", "A", "1X", "X2", "12")}
        # The same population if the fallback were switched off, so the lift is
        # attributable to the rule rather than to the fixtures it happens to see.
        outright = np.where(probs[idx, 0] >= probs[idx, 2], "H", "A")
        rows.append({
            "floor": floor, "double_chance_share": round(dc_share, 4),
            "strike": round(-float(cmp.delta), 4),
            "ci_low": round(-cmp.ci[1], 4), "ci_high": round(-cmp.ci[0], 4),
            "outright_only_strike": round(float(_won(outright, ftr[idx]).mean()), 4),
            "mix": mix,
        })
        r = rows[-1]
        marker = " <- SHIPPED" if floor == SHIPPED_FLOOR else ""
        print(f"    {floor:>6.2f} {100*dc_share:>13.1f}% {100*r['strike']:>7.1f}% "
              f"[{100*r['ci_low']:>6.1f},{100*r['ci_high']:>6.1f}] "
              f"{100*r['outright_only_strike']:>20.1f}%{marker}")
        print("           mix " + "  ".join(f"{k} {100*v:.1f}%"
                                            for k, v in mix.items() if v > 0))

    monotone = all(rows[i]["strike"] <= rows[i + 1]["strike"]
                   for i in range(len(rows) - 1))
    out = {"ceiling": CEILING, "rows": rows, "monotone_in_floor": monotone}
    print(f"    strike rises monotonically with the floor: {monotone}")
    return out


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="docs/selection_results.json")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    conn = db.connect()
    frame = load(conn)
    raw = raw_probs(frame)
    calibrated = walk_forward_calibrate(frame, raw)
    scored = np.isfinite(calibrated).all(axis=1)
    print(f"{len(frame):,} matches, {int(scored.sum()):,} scored out of sample "
          f"({frame.season[scored].min()} -> {frame.season[scored].max()})")

    results = {"b2": b2_calibration(frame, raw, calibrated, scored)}
    results["b3_raw"] = b3_floor(frame, raw, scored)
    results["b3_calibrated"] = b3_floor(frame, calibrated, scored)

    if args.dry_run:
        print("\n  [dry-run] ledger row NOT written")
    else:
        ledger.record(
            conn, kind=ledger.GATE, name="b2_b3_selection", purpose="dev",
            seasons=DEV_SEASONS, divisions=SERVED_DIVISIONS,
            # Arms carry their results, not just their names. `trials`
            # deduplicates a re-run only when it can see the numbers matched,
            # and an arm list of bare labels is indistinguishable from a run
            # that produced something different.
            detail={"arms": [{"arm": f"B2 {v['probs']}", "strike": v["strike"],
                              "tips": v["tips"]}
                             for v in results["b2"]["volume"]]
                            + [{"arm": f"B3 floor {r['floor']}",
                                "strike": r["strike"],
                                "double_chance_share": r["double_chance_share"]}
                               for r in results["b3_calibrated"]["rows"]],
                    **results},
            reason="PRODUCT.md §3a. B2: walk-forward vector scaling against the "
                   "head's under-confidence on its own favourites -- a different "
                   "target from P3's log-loss calibration, and expected to pay in "
                   "volume rather than strike rate. B3: the double-chance floor "
                   "under the ceiling-as-veto rule. Six configurations.")
        print("\n  [ledger] gate:b2_b3_selection  (6 configurations)")

    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(results, handle, indent=2, default=str)
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
