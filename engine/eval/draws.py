"""§9.1: the draw-mass decision, re-read under the tipster objective.

    python -m engine.eval.draws --dry-run
    python -m engine.eval.draws

Pre-registration in `OUTSTANDING.md` §9.1, written before this ran.

**Why the closed decision is worth re-measuring and not re-litigating.** P0-2
declined the Dixon-Coles tau on three reasons, and flagged the second -- that tau
cannot move an O/U 2.5 probability, because all four cells it touches lie below
the line -- as the one no re-measurement could touch. That is correct and it is
exclusively true of O/U 2.5. `12` loses if and only if the match is a draw and
takes 65% of what the product publishes, so the same four cells decide two
thirds of the output. P0-2's reason 1 (the gain is small against the head's
deficit to the market) is a beat-the-book yardstick. Its reason 3 -- tau is
global, the deficit is not -- survives intact, and under a per-division product
it argues for a per-division rho rather than against a correction.

**This is a diagnostic, not a gate.** Nothing here proposes adoption. What it
answers is whether the deficit survives on the served head, whether the union
markets the product actually sells are calibrated, and whether a correction
would change any recommendation. Convention 8 still applies: a null on the
fitted arms means nothing without evidence the instrument can see a draw
correction at all, so a planted rho runs alongside.

**Claimed-versus-delivered is measured with the paired block bootstrap**, not the
binomial half-width `selection.calibration_table` uses. The two quantities are
scored on the same matches, so the comparison is paired by construction, and
convention 3 exists because the difference is large on this corpus.
"""

from __future__ import annotations

import argparse
import json

import numpy as np
import pandas as pd

from engine import db, ledger
from engine.eval import bootstrap
from engine.eval.dispersion import fit_rho, outcome_probs, score_matrix
from engine.eval.selection import (
    BURN_IN_SEASONS,
    CEILING,
    SHIPPED_FLOOR,
    ALLOW_12,
    _won,
    load,
    recommend,
)
from engine.seasons import DEV_SEASONS, SERVED_DIVISIONS

#: The positive control convention 8 requires. Roughly 5x the rho P0-2 fitted,
#: and well inside the positivity bound (-1/max(lambda) = -0.27 on this corpus),
#: so tau stays a probability. Nobody would ship it; it exists to show the
#: instrument can see a draw correction when one is there.
PLANTED_RHO = -0.10

#: The three double chances. `12` first because it is 65% of what ships.
UNION_MARKETS = ("12", "1X", "X2")

#: Arm names. The shipped arm is listed first and every other arm is compared
#: against it, so the order here is load-bearing rather than presentational.
SHIPPED_ARM = "rho 0 (shipped)"
POOLED_ARM = "rho pooled"
PER_DIVISION_ARM = "rho per-division"
PLANTED_ARM = "rho planted"

_OUTCOME = {"H": 0, "D": 1, "A": 2}


# --- rho, fitted walk-forward ----------------------------------------------


def walk_forward_rho(frame: pd.DataFrame, *, by_division: bool) -> np.ndarray:
    """One rho per match, fitted only on strictly earlier seasons.

    P0-2 fitted rho on the whole development corpus, which is the right thing
    for a distributional question and the wrong thing for a served correction:
    the product would have to pick rho before seeing the season it prices. The
    burn-in matches `selection.walk_forward_calibrate` so the scored population
    is the same one B2 and B3 report on.
    """
    seasons = sorted(frame.season.unique())
    out = np.full(len(frame), np.nan)
    for i, season in enumerate(seasons):
        if i < BURN_IN_SEASONS:
            continue
        train = frame.season.isin(seasons[:i]).to_numpy()
        test = (frame.season == season).to_numpy()
        if by_division:
            for div in sorted(frame.division.unique()):
                d = (frame.division == div).to_numpy()
                out[test & d] = fit_rho(frame[train & d])
        else:
            out[test] = fit_rho(frame[train])
    return out


def joint_with(frame: pd.DataFrame, rho: np.ndarray) -> np.ndarray:
    """Score matrices under a per-match rho, via the tested scalar path.

    Grouped by value rather than re-deriving the tau algebra here: there are at
    most seasons x divisions distinct values, and duplicating `score_matrix`
    would put the correction in two places.
    """
    lam_h = frame.lam_h.to_numpy(float)
    lam_a = frame.lam_a.to_numpy(float)
    out = score_matrix(lam_h, lam_a)
    for value in np.unique(rho[np.isfinite(rho) & (rho != 0.0)]):
        sel = rho == value
        out[sel] = score_matrix(lam_h[sel], lam_a[sel], float(value))
    return out


def probs_for(frame: pd.DataFrame, rho: np.ndarray) -> np.ndarray:
    return np.column_stack(outcome_probs(joint_with(frame, rho)))


def market_probs(probs: np.ndarray) -> dict[str, np.ndarray]:
    p_h, p_d, p_a = probs[:, 0], probs[:, 1], probs[:, 2]
    return {"12": p_h + p_a, "1X": p_h + p_d, "X2": p_a + p_d}


# --- measurement 1: does the deficit survive on the served head? -----------


def draw_deficit(frame, probs, scored) -> dict:
    """Realised draws against what the served pmf expects, per division."""
    print(f"\n1  the draw deficit on the served head "
          f"({int(scored.sum()):,} matches)")
    print(f"    {'':>8} {'n':>7} {'realised':>10} {'expected':>10} "
          f"{'deficit':>9} {'[95% block CI]':>18}")

    is_draw = (frame.ftr.to_numpy() == "D").astype(float)
    p_draw = probs[:, 1]
    rows = []
    for label, sel in [("pooled", scored)] + [
            (d, scored & (frame.division == d).to_numpy())
            for d in sorted(frame.division.unique())]:
        idx = np.flatnonzero(sel)
        blocks = bootstrap.week_blocks(frame.match_date.iloc[idx])
        cmp = bootstrap.paired(is_draw[idx], p_draw[idx], blocks)
        rows.append({
            "population": label, "n": len(idx),
            "realised_pct": round(100 * float(is_draw[idx].mean()), 3),
            "expected_pct": round(100 * float(p_draw[idx].mean()), 3),
            "deficit_pts": round(100 * float(cmp.delta), 3),
            "ci_low": round(100 * cmp.ci[0], 3),
            "ci_high": round(100 * cmp.ci[1], 3),
            "excludes_zero": bool(cmp.excludes_zero),
        })
        r = rows[-1]
        print(f"    {label:>8} {r['n']:>7,} {r['realised_pct']:>9.2f}% "
              f"{r['expected_pct']:>9.2f}% {r['deficit_pts']:>+8.2f} "
              f"[{r['ci_low']:>+6.2f},{r['ci_high']:>+6.2f}]"
              f"{'  *' if r['excludes_zero'] else ''}")
    return {"rows": rows}


# --- measurement 2: is the union calibrated? -------------------------------


def outcome_calibration(frame, probs, scored) -> dict:
    """Delivered minus claimed for H, D and A separately.

    The three union gaps are determined by these and must sum to zero -- `1X`,
    `X2` and `12` between them count every outcome twice -- so a union table
    read on its own will attribute to the draw an error that belongs somewhere
    else. This is what says whether the draw is the biggest thing wrong with the
    1X2 vector or merely the thing P0-2 happened to look at.
    """
    print("\n2a  outcome calibration: delivered minus claimed")
    print(f"    {'':>8} {'home':>22} {'draw':>22} {'away':>22}")
    ftr = frame.ftr.to_numpy()
    rows = []
    for label, sel in [("pooled", scored)] + [
            (d, scored & (frame.division == d).to_numpy())
            for d in sorted(frame.division.unique())]:
        idx = np.flatnonzero(sel)
        blocks = bootstrap.week_blocks(frame.match_date.iloc[idx])
        row = {"population": label, "n": len(idx)}
        cells = []
        for name, code in (("home", "H"), ("draw", "D"), ("away", "A")):
            won = (ftr == code).astype(float)
            cmp = bootstrap.paired(won[idx], probs[idx, _OUTCOME[code]], blocks)
            row[name] = round(100 * float(cmp.delta), 3)
            row[f"{name}_ci"] = [round(100 * cmp.ci[0], 3),
                                 round(100 * cmp.ci[1], 3)]
            row[f"{name}_excludes_zero"] = bool(cmp.excludes_zero)
            cells.append(f"{row[name]:>+6.2f} [{100*cmp.ci[0]:>+5.2f},"
                         f"{100*cmp.ci[1]:>+5.2f}]"
                         f"{'*' if cmp.excludes_zero else ' '}")
        rows.append(row)
        print(f"    {label:>8} " + " ".join(cells))
    return {"rows": rows}


def union_calibration(frame, probs, scored) -> dict:
    """Claimed against delivered for the three double chances, per division.

    Unconditional -- over every scored match, not only the ones the rule
    publishes -- because this is a property of the head rather than of the rule,
    and `BACKLOG.md` B3 asked the question in that form.
    """
    print("\n2  union calibration: claimed vs delivered "
          "(positive = delivers more than it claims)")
    ftr = frame.ftr.to_numpy()
    markets = market_probs(probs)
    rows = []
    for market in UNION_MARKETS:
        print(f"    {market}")
        p = markets[market]
        won = _won(np.full(len(frame), market), ftr).astype(float)
        for label, sel in [("pooled", scored)] + [
                (d, scored & (frame.division == d).to_numpy())
                for d in sorted(frame.division.unique())]:
            idx = np.flatnonzero(sel)
            blocks = bootstrap.week_blocks(frame.match_date.iloc[idx])
            cmp = bootstrap.paired(won[idx], p[idx], blocks)
            verdict = ("calibrated" if not cmp.excludes_zero
                       else "under-confident" if cmp.delta > 0
                       else "OVER-CONFIDENT")
            rows.append({
                "market": market, "population": label, "n": len(idx),
                "claimed_pct": round(100 * float(p[idx].mean()), 2),
                "delivered_pct": round(100 * float(won[idx].mean()), 2),
                "gap_pts": round(100 * float(cmp.delta), 2),
                "ci_low": round(100 * cmp.ci[0], 2),
                "ci_high": round(100 * cmp.ci[1], 2),
                "verdict": verdict,
            })
            r = rows[-1]
            print(f"      {label:>8} n={r['n']:>6,}  claims {r['claimed_pct']:>5.2f}%"
                  f"  delivers {r['delivered_pct']:>5.2f}%  "
                  f"{r['gap_pts']:>+6.2f} [{r['ci_low']:>+5.2f},{r['ci_high']:>+5.2f}]"
                  f"  {r['verdict']}")
    return {"rows": rows}


# --- measurement 3: would a correction change any recommendation? ----------


def rule_effect(frame, arms: dict[str, np.ndarray], scored) -> dict:
    """What each rho does to the shipped rule, against the shipped arm."""
    print(f"\n3  effect on the shipped rule "
          f"(floor {SHIPPED_FLOOR}, ceiling {CEILING}, allow_12={ALLOW_12})")
    print(f"    {'arm':>16} {'changed':>8} {'strike':>7} "
          f"{'vs shipped, PAIRED':>26} {'claimed':>8} {'mix 12/1X/X2/H/A':>24}")

    ftr = frame.ftr.to_numpy()
    idx = np.flatnonzero(scored)
    blocks = bootstrap.week_blocks(frame.match_date.iloc[idx])
    baseline = base_won = None
    rows = []
    for name, probs in arms.items():
        market, p = recommend(probs, SHIPPED_FLOOR, allow_12=ALLOW_12)
        won = _won(market, ftr).astype(float)
        if baseline is None:
            baseline, base_won = market, won
        # Convention 3: arms are scored on the same matches, so the difference
        # between them is paired. The marginal CI on each arm's strike rate is
        # ~20x wider here and makes every comparison vacuous.
        against = bootstrap.paired(won[idx], base_won[idx], blocks)
        changed = float((market[idx] != baseline[idx]).mean())
        mix = {m: round(float((market[idx] == m).mean()), 4)
               for m in ("12", "1X", "X2", "H", "A")}
        rows.append({
            "arm": name, "changed_share": round(changed, 4),
            "strike": round(float(won[idx].mean()), 4),
            "vs_shipped": round(float(against.delta), 5),
            "vs_shipped_ci": [round(against.ci[0], 5), round(against.ci[1], 5)],
            "vs_shipped_excludes_zero": bool(against.excludes_zero),
            "claimed": round(float(p[idx].mean()), 4),
            "mix": mix,
        })
        r = rows[-1]
        print(f"    {name:>16} {100*changed:>7.2f}% {100*r['strike']:>6.2f}% "
              f"{100*r['vs_shipped']:>+8.3f} "
              f"[{100*r['vs_shipped_ci'][0]:>+6.3f},"
              f"{100*r['vs_shipped_ci'][1]:>+6.3f}]"
              f"{'*' if r['vs_shipped_excludes_zero'] else ' '}"
              f"{100*r['claimed']:>8.2f}% "
              + " ".join(f"{100*v:.1f}" for v in mix.values()))
    return {"floor": SHIPPED_FLOOR, "ceiling": CEILING, "rows": rows}


# --- the claims block ------------------------------------------------------


def claims(deficit, calibration, effect, rhos) -> dict:
    """Which of §9.1's pre-registered predictions the numbers support.

    Printed rather than asserted: this is a diagnostic, so a prediction going
    the other way is a finding to write down, not a failure to stop on.
    """
    by = {(r["market"], r["population"]): r for r in calibration["rows"]}
    dev = {r["population"]: r for r in deficit["rows"]}
    arms = {r["arm"]: r for r in effect["rows"]}
    lower = [d for d in ("E1", "E2", "E3")]

    out = {
        "1_deficit_survives": (dev["pooled"]["deficit_pts"] >= 0.5
                               and abs(dev["E0"]["deficit_pts"]) <= 0.5),
        "2_rho_within_p0_2_interval": all(
            -0.0343 <= v <= -0.0070 for v in rhos["pooled_by_season"].values()),
        "3_twelve_overconfident_in_lower": (
            all(by[("12", d)]["gap_pts"] < 0 for d in lower)
            and by[("12", "E0")]["verdict"] == "calibrated"),
        "4_changes_under_5pct": arms[POOLED_ARM]["changed_share"] < 0.05,
        "5_strike_move_under_0_7pt": abs(arms[POOLED_ARM]["vs_shipped"]) < 0.007,
        "6_control_moves_more": (arms[PLANTED_ARM]["changed_share"]
                                 > arms[POOLED_ARM]["changed_share"]),
    }
    print("\n  pre-registered predictions (OUTSTANDING.md §9.1):")
    for key, supported in out.items():
        print(f"    {'RIGHT' if supported else 'WRONG':>5}  {key}")
    return out


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="docs/draw_mass_results.json")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    conn = db.connect()
    frame = load(conn)

    pooled = walk_forward_rho(frame, by_division=False)
    per_div = walk_forward_rho(frame, by_division=True)
    scored = np.isfinite(pooled) & np.isfinite(per_div)
    print(f"{len(frame):,} matches, {int(scored.sum()):,} scored out of sample "
          f"({frame.season[scored].min()} -> {frame.season[scored].max()})")

    zero = np.zeros(len(frame))
    planted = np.full(len(frame), PLANTED_RHO)
    arms = {
        SHIPPED_ARM: probs_for(frame, zero),
        POOLED_ARM: probs_for(frame, pooled),
        PER_DIVISION_ARM: probs_for(frame, per_div),
        PLANTED_ARM: probs_for(frame, planted),
    }

    rhos = {
        "planted": PLANTED_RHO,
        "full_sample": round(fit_rho(frame), 5),
        "pooled_by_season": {
            s: round(float(pooled[(frame.season == s).to_numpy()][0]), 5)
            for s in sorted(frame.season[scored].unique())},
        "per_division_last_season": {
            d: round(float(per_div[((frame.season == frame.season[scored].max())
                                    & (frame.division == d)).to_numpy()][0]), 5)
            for d in sorted(frame.division.unique())},
    }
    print(f"\n0  rho: P0-2 fitted -0.0213 [-0.0343, -0.0070] on the P0 instrument")
    print(f"    full-sample on the served head: {rhos['full_sample']:+.5f}")
    print("    walk-forward, pooled: "
          + "  ".join(f"{s} {v:+.4f}" for s, v in rhos["pooled_by_season"].items()))
    print("    walk-forward, per division (last fold): "
          + "  ".join(f"{d} {v:+.4f}"
                      for d, v in rhos["per_division_last_season"].items()))

    results = {"rho": rhos, "n_scored": int(scored.sum())}
    results["deficit"] = draw_deficit(frame, arms[SHIPPED_ARM], scored)
    results["outcomes"] = outcome_calibration(frame, arms[SHIPPED_ARM], scored)
    results["calibration"] = union_calibration(frame, arms[SHIPPED_ARM], scored)
    results["effect"] = rule_effect(frame, arms, scored)
    results["claims"] = claims(results["deficit"], results["calibration"],
                               results["effect"], rhos)

    if args.dry_run:
        print("\n  [dry-run] ledger row NOT written")
    else:
        ledger.record(
            conn, kind=ledger.GATE, name="draw_mass_tipster", purpose="dev",
            seasons=DEV_SEASONS, divisions=SERVED_DIVISIONS,
            detail={"arms": [{"arm": r["arm"], "strike": r["strike"],
                              "changed_share": r["changed_share"]}
                             for r in results["effect"]["rows"]],
                    **results},
            reason="OUTSTANDING.md §9.1. Diagnostic, not an adoption gate. P0-2 "
                   "declined the Dixon-Coles tau on an argument scoped to O/U "
                   "2.5; `12` loses only on a draw and is 65% of what ships, so "
                   "the same four cells decide two thirds of the product. "
                   "Re-measures the deficit on the served head, calibrates the "
                   "union markets for the first time, and asks whether a "
                   "walk-forward rho changes any recommendation. Four "
                   "configurations, one of them a planted positive control.")
        print("\n  [ledger] gate:draw_mass_tipster  (4 configurations)")

    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(results, handle, indent=2, default=str)
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
