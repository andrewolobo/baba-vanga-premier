"""What the tip list actually delivers: strike rate, volume, and return.

    python -m engine.eval.tips
    python -m engine.eval.tips --dry-run

Measures `engine/serve/tips.py`'s confidence rule on the dev corpus. The product
is sold on strike rate, so the first job is to check the advertised number is
true; the second is to record what the same tips return, because a strike rate
and a return are different claims and only one of them is about money.

**This is the first thing in the P5 line to read match outcomes.** Strike rate
and ROI are both functions of what happened, so unlike `meta.py` this spends
information about a real answer and carries an arm list.

Three results the product depends on, all measured here:

  - **The advertised strike rate is honest**, and slightly conservative. The
    head is under-confident on its own favourites in every bucket.
  - **The return is not.** At average prices -- what a customer without a dozen
    accounts faces -- no threshold resolves and the sellable ones are negative.
  - **The model is not the source of either.** At every threshold that produces
    a sellable strike rate, the model names the market's favourite and the
    paired difference against simply backing that favourite is ~0.00%.
"""

from __future__ import annotations

import argparse
import json

import numpy as np
import pandas as pd

from engine import db, ledger, store
from engine.eval import bootstrap, metrics
from engine.eval.p1 import served
from engine.eval.travel import HEAD
from engine.eval.walkforward import walk_forward
from engine.odds import devig_probs
from engine.seasons import DEV_SEASONS, SERVED_DIVISIONS
from engine.serve.tips import DEFAULT_THRESHOLD

#: Thresholds reported. A grid, so it spends five configurations and says so --
#: and so the multiplicity is visible rather than hidden behind whichever
#: threshold happened to look best. `CALIBRATION.md` §1 records a positive ROI
#: on this corpus turning out to be an artifact once already.
THRESHOLDS = (0.50, 0.55, 0.60, 0.65, 0.70)

#: Matches per division-season, for turning tip counts into a weekly rate.
MATCHDAYS_PER_SEASON = 38

OUTCOME_INDEX = {"H": 0, "D": 1, "A": 2}
PRICE_BEST = ["max_h", "max_d", "max_a"]
PRICE_AVG = ["avg_h", "avg_d", "avg_a"]


def load(conn) -> pd.DataFrame:
    raw = store.read_matches(conn, seasons=DEV_SEASONS).for_measurement()
    frame = served(walk_forward(raw, HEAD)).reset_index(drop=True)
    return frame.dropna(subset=PRICE_BEST + PRICE_AVG + ["ftr"]).reset_index(drop=True)


def _picks(frame: pd.DataFrame):
    """Model and market favourite per match, with the outcome that happened."""
    model = metrics.model_probs(frame.lam_h, frame.lam_a)[
        ["p_h", "p_d", "p_a"]].to_numpy()
    market = np.column_stack(devig_probs(*[frame[c].to_numpy() for c in PRICE_AVG]))
    outcome = frame.ftr.map(OUTCOME_INDEX).to_numpy()
    return model, market, outcome


def _pnl(pick, odds, outcome):
    """Flat-stake profit per unit: the price minus the stake, or the stake."""
    taken = odds[np.arange(len(pick)), pick]
    return np.where(pick == outcome, taken - 1.0, -1.0)


def _roi(pnl, dates):
    """Mean return with a block-bootstrap interval, negated for the loss convention."""
    cmp = bootstrap.paired(-pnl, np.zeros(len(pnl)), bootstrap.week_blocks(dates))
    return {"roi": round(-float(cmp.delta), 5),
            "ci_low": round(-cmp.ci[1], 5), "ci_high": round(-cmp.ci[0], 5),
            "profitable": bool(cmp.ci[1] < 0)}


def strike_and_return(frame: pd.DataFrame) -> dict:
    model, market, outcome = _picks(frame)
    best = frame[PRICE_BEST].to_numpy(dtype=float)
    avg = frame[PRICE_AVG].to_numpy(dtype=float)
    rows = np.arange(len(frame))
    m_pick, k_pick = model.argmax(axis=1), market.argmax(axis=1)
    p = model[rows, m_pick]
    seasons = frame.season.nunique()

    agree = float((m_pick == k_pick).mean())
    print(f"{len(frame):,} matches, {seasons} seasons. Model and market name the "
          f"same favourite in {100*agree:.1f}% of them.\n")
    print(f"{'threshold':>10} {'tips':>6} {'/week':>6} {'claimed':>8} {'ACTUAL':>7} "
          f"{'ROI@best':>9} {'ROI@avg':>18} {'vs mkt favourite':>18}")

    out = []
    for threshold in THRESHOLDS:
        sel = np.flatnonzero(p >= threshold)
        if len(sel) < 200:
            continue
        dates = frame.loc[sel, "match_date"]
        blocks = bootstrap.week_blocks(dates)
        model_pnl = _pnl(m_pick[sel], best[sel], outcome[sel])
        market_pnl = _pnl(k_pick[sel], best[sel], outcome[sel])
        versus = bootstrap.paired(-model_pnl, -market_pnl, blocks)

        entry = {
            "threshold": threshold, "tips": int(len(sel)),
            "tips_per_week": round(len(sel) / seasons / MATCHDAYS_PER_SEASON, 1),
            "claimed_strike": round(float(p[sel].mean()), 4),
            "actual_strike": round(float((m_pick[sel] == outcome[sel]).mean()), 4),
            "roi_best": _roi(model_pnl, dates),
            "roi_avg": _roi(_pnl(m_pick[sel], avg[sel], outcome[sel]), dates),
            "vs_market_favourite": {"delta": round(-float(versus.delta), 5),
                                    "beats": bool(versus.ci[1] < 0)},
        }
        out.append(entry)
        print(f"{threshold:>10.2f} {entry['tips']:>6,} {entry['tips_per_week']:>6.1f} "
              f"{100*entry['claimed_strike']:>7.1f}% {100*entry['actual_strike']:>6.1f}% "
              f"{100*entry['roi_best']['roi']:>+8.2f}% "
              f"{100*entry['roi_avg']['roi']:>+8.2f}% "
              f"[{100*entry['roi_avg']['ci_low']:>+6.2f},"
              f"{100*entry['roi_avg']['ci_high']:>+6.2f}] "
              f"{100*entry['vs_market_favourite']['delta']:>+8.2f}%")
    return {"agreement_with_market": round(agree, 4), "rows": out}


def calibration(frame: pd.DataFrame) -> list[dict]:
    """Does the head deliver the confidence it claims? The advertised number."""
    model, _, outcome = _picks(frame)
    pick = model.argmax(axis=1)
    p = model[np.arange(len(frame)), pick]
    won = (pick == outcome)

    print("\ncalibration where the tips live -- is the advertised number true?")
    out = []
    for lo, hi in ((0.50, 0.55), (0.55, 0.60), (0.60, 0.65), (0.65, 0.70), (0.70, 1.01)):
        sel = (p >= lo) & (p < hi)
        if sel.sum() < 50:
            continue
        actual = float(won[sel].mean())
        half = 1.96 * float(np.sqrt(actual * (1 - actual) / sel.sum()))
        claimed = float(p[sel].mean())
        verdict = ("overconfident" if actual < claimed - half
                   else "under-confident" if actual > claimed + half else "calibrated")
        out.append({"bin": [lo, hi], "n": int(sel.sum()),
                    "claimed": round(claimed, 4), "actual": round(actual, 4),
                    "half_width": round(half, 4), "verdict": verdict})
        print(f"  p in [{lo:.2f},{hi:.2f})  n={sel.sum():>5,}  claims "
              f"{100*claimed:.1f}%  delivers {100*actual:.1f}% +/- {100*half:.1f}"
              f"   {verdict}")
    return out


def market_favourite_only(frame: pd.DataFrame) -> list[dict]:
    """The same product with the model deleted. The comparison that matters."""
    _, market, outcome = _picks(frame)
    best = frame[PRICE_BEST].to_numpy(dtype=float)
    pick = market.argmax(axis=1)
    q = market[np.arange(len(frame)), pick]

    print("\nthe same product with no model at all -- back the market favourite:")
    out = []
    for threshold in THRESHOLDS:
        sel = np.flatnonzero(q >= threshold)
        if len(sel) < 200:
            continue
        roi = _roi(_pnl(pick[sel], best[sel], outcome[sel]), frame.loc[sel, "match_date"])
        entry = {"threshold": threshold, "tips": int(len(sel)),
                 "actual_strike": round(float((pick[sel] == outcome[sel]).mean()), 4),
                 "roi_best": roi}
        out.append(entry)
        print(f"  {threshold:.2f}  {len(sel):>6,} tips  strike "
              f"{100*entry['actual_strike']:>5.1f}%  ROI@best "
              f"{100*roi['roi']:>+6.2f}% [{100*roi['ci_low']:>+6.2f},"
              f"{100*roi['ci_high']:>+6.2f}]")
    return out


def headline(results: dict) -> dict:
    """The two sentences the product may and may not say."""
    row = next(r for r in results["strike"]["rows"]
               if r["threshold"] == DEFAULT_THRESHOLD)
    sellable = [r for r in results["strike"]["rows"] if r["threshold"] >= 0.55]
    out = {
        "default_threshold": DEFAULT_THRESHOLD,
        "advertisable_strike": row["actual_strike"],
        "tips_per_week": row["tips_per_week"],
        "strike_claim_is_honest": all(
            b["verdict"] != "overconfident" for b in results["calibration"]),
        "any_threshold_profitable_at_avg_prices": any(
            r["roi_avg"]["profitable"] for r in results["strike"]["rows"]),
        "model_beats_market_favourite_anywhere": any(
            r["vs_market_favourite"]["beats"] for r in sellable),
    }
    print("\n--- what the product may claim ---")
    print(f"  strike rate {100*out['advertisable_strike']:.1f}% at threshold "
          f"{DEFAULT_THRESHOLD}, {out['tips_per_week']} tips/week: "
          f"{'HONEST' if out['strike_claim_is_honest'] else 'NOT SUPPORTED'}")
    print(f"  a return at prices customers actually get: "
          f"{'supported' if out['any_threshold_profitable_at_avg_prices'] else 'NOT SUPPORTED'}")
    print(f"  the model beating the market favourite: "
          f"{'supported' if out['model_beats_market_favourite_anywhere'] else 'NOT SUPPORTED'}")
    return out


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="docs/tips_results.json")
    parser.add_argument("--dry-run", action="store_true",
                        help="print and write JSON, but record no ledger row")
    args = parser.parse_args(argv)

    conn = db.connect()
    frame = load(conn)
    results = {"strike": strike_and_return(frame),
               "calibration": calibration(frame),
               "market_favourite_only": market_favourite_only(frame)}
    results["headline"] = headline(results)

    if args.dry_run:
        print("\n  [dry-run] ledger row NOT written")
    else:
        ledger.record(
            conn, kind=ledger.GATE, name="tips_confidence_rule", purpose="dev",
            seasons=DEV_SEASONS, divisions=SERVED_DIVISIONS,
            detail={"arms": results["strike"]["rows"], **results},
            reason="Strike rate, volume and return of engine/serve/tips.py's "
                   "confidence rule, over a five-threshold grid. Reads match "
                   "outcomes, so it spends five configurations. Records the "
                   "market-favourite comparison because a strike rate that the "
                   "market reproduces for free is a property of short odds, not "
                   "of the model.")
        print("\n  [ledger] gate:tips_confidence_rule  (5 configurations)")

    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(results, handle, indent=2, default=str)
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
