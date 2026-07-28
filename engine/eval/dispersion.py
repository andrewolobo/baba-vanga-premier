"""The three dispersion measurements, and the Dixon-Coles decision.

gtleague closed all three at its own scoring rates (3.5-4.2 goals/match) and
SPEC §2.4 is explicit that the harness transfers but the conclusions must not:
English football scores ~2.6, which puts far more mass in the 0-0/1-0/0-1/1-1
cells that the Dixon-Coles tau correction exists to fix. So the measurements
are re-run here rather than inherited.

  1. Totals dispersion   Var(total | lambda) / E[lambda]. Poisson says 1.0.
                         Decomposed into side-level dispersion and the
                         correlation between the two sides' residuals, because
                         at gtleague those two cancelled almost exactly and a
                         single ratio would have hidden it.

  2. Draw mass           Realised draws against what independent Poisson
                         predicts, per low-score cell, and the tau that best
                         repairs the gap -- then whether that tau is worth
                         anything on the markets actually served.

  3. Margin dispersion   Var(margin | lambda) / E[lambda]. Governs the standing
                         veto on Asian handicap and correct score, both of
                         which are priced off the tails of this pmf and both of
                         which are in the dataset and therefore tempting.

Everything is measured on out-of-sample lambdas from a walk-forward fit, on the
development set only, and every measurement is recorded in the gate ledger.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy import optimize, stats

from engine import db, ledger, store
from engine.ingest.holdout import Purpose
from engine.models import poisson as poisson_model

MAX_GOALS = 15
BOOTSTRAP_REPS = 1000
RNG_SEED = 20260728


# --- score matrices --------------------------------------------------------


def score_matrix(lam_h: np.ndarray, lam_a: np.ndarray, rho: float = 0.0) -> np.ndarray:
    """P(home=x, away=y) for each match, optionally Dixon-Coles adjusted.

    The tau adjustments sum to exactly zero over the four cells, so the pmf
    still integrates to 1 and no renormalisation is needed.
    """
    k = np.arange(MAX_GOALS + 1)
    ph = stats.poisson.pmf(k[None, :], lam_h[:, None])
    pa = stats.poisson.pmf(k[None, :], lam_a[:, None])
    joint = ph[:, :, None] * pa[:, None, :]
    if rho:
        joint[:, 0, 0] *= 1.0 - lam_h * lam_a * rho
        joint[:, 0, 1] *= 1.0 + lam_h * rho
        joint[:, 1, 0] *= 1.0 + lam_a * rho
        joint[:, 1, 1] *= 1.0 - rho
    return joint


def outcome_probs(joint: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(home, draw, away) from a score matrix."""
    n = joint.shape[1]
    x = np.arange(n)[:, None]
    y = np.arange(n)[None, :]
    home = joint[:, x > y].sum(axis=1)
    draw = joint[:, x == y].sum(axis=1)
    away = joint[:, x < y].sum(axis=1)
    return home, draw, away


def over_under_probs(joint: np.ndarray, line: float = 2.5) -> tuple[np.ndarray, np.ndarray]:
    n = joint.shape[1]
    total = np.arange(n)[:, None] + np.arange(n)[None, :]
    over = joint[:, total > line].sum(axis=1)
    return over, 1.0 - over


def margin_pmf(joint: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """(margins, P(margin)) marginalised over the score matrix."""
    n = joint.shape[1]
    diff = np.arange(n)[:, None] - np.arange(n)[None, :]
    margins = np.arange(-(n - 1), n)
    probs = np.stack([joint[:, diff == m].sum(axis=1) for m in margins], axis=1)
    return margins, probs


# --- measurement 1: totals -------------------------------------------------


@dataclass
class Dispersion:
    label: str
    n: int
    total_ratio: float
    home_ratio: float
    away_ratio: float
    residual_corr: float
    total_ci: tuple[float, float] = (np.nan, np.nan)


def _variance_ratio(observed: np.ndarray, expected: np.ndarray) -> float:
    return float(np.mean((observed - expected) ** 2) / np.mean(expected))


def measure_totals(frame: pd.DataFrame, label: str = "all", *, rng=None) -> Dispersion:
    lam_h = frame["lam_h"].to_numpy()
    lam_a = frame["lam_a"].to_numpy()
    goals_h = frame["fthg"].to_numpy(dtype=float)
    goals_a = frame["ftag"].to_numpy(dtype=float)
    total = goals_h + goals_a
    lam_total = lam_h + lam_a

    resid_h = (goals_h - lam_h) / np.sqrt(lam_h)
    resid_a = (goals_a - lam_a) / np.sqrt(lam_a)

    result = Dispersion(
        label=label,
        n=len(frame),
        total_ratio=_variance_ratio(total, lam_total),
        home_ratio=_variance_ratio(goals_h, lam_h),
        away_ratio=_variance_ratio(goals_a, lam_a),
        residual_corr=float(np.corrcoef(resid_h, resid_a)[0, 1]),
    )

    if rng is not None:
        draws = []
        for _ in range(BOOTSTRAP_REPS):
            pick = rng.integers(0, len(frame), len(frame))
            draws.append(_variance_ratio(total[pick], lam_total[pick]))
        result.total_ci = tuple(np.percentile(draws, [2.5, 97.5]))
    return result


# --- measurement 2: draw mass and tau -------------------------------------


@dataclass
class DrawMass:
    n: int
    realised: float
    expected: float
    deficit_pts: float
    deficit_ci: tuple[float, float]
    cells: pd.DataFrame
    rho: float
    rho_ci: tuple[float, float]
    delta_logloss_1x2: float
    delta_logloss_ou: float
    expected_with_rho: float


def _tau_loglik(rho: float, cells: np.ndarray, lam_h: np.ndarray, lam_a: np.ndarray) -> float:
    """Log-likelihood contribution of tau. Only the four cells depend on rho."""
    tau = np.ones(len(cells))
    m00, m01, m10, m11 = (cells == 0), (cells == 1), (cells == 2), (cells == 3)
    tau[m00] = 1.0 - lam_h[m00] * lam_a[m00] * rho
    tau[m01] = 1.0 + lam_h[m01] * rho
    tau[m10] = 1.0 + lam_a[m10] * rho
    tau[m11] = 1.0 - rho
    if np.any(tau <= 0):
        return -np.inf
    return float(np.sum(np.log(tau)))


def _cell_codes(goals_h: np.ndarray, goals_a: np.ndarray) -> np.ndarray:
    """0 for 0-0, 1 for 0-1, 2 for 1-0, 3 for 1-1, -1 otherwise."""
    codes = np.full(len(goals_h), -1)
    codes[(goals_h == 0) & (goals_a == 0)] = 0
    codes[(goals_h == 0) & (goals_a == 1)] = 1
    codes[(goals_h == 1) & (goals_a == 0)] = 2
    codes[(goals_h == 1) & (goals_a == 1)] = 3
    return codes


def fit_rho(frame: pd.DataFrame) -> float:
    """MLE for the Dixon-Coles dependence parameter, respecting positivity."""
    lam_h = frame["lam_h"].to_numpy()
    lam_a = frame["lam_a"].to_numpy()
    codes = _cell_codes(frame["fthg"].to_numpy(), frame["ftag"].to_numpy())

    lower = max(-1.0 / lam_h.max(), -1.0 / lam_a.max())
    upper = min(1.0 / (lam_h * lam_a).max(), 1.0)
    margin = 1e-6
    result = optimize.minimize_scalar(
        lambda r: -_tau_loglik(r, codes, lam_h, lam_a),
        bounds=(lower + margin, upper - margin),
        method="bounded",
    )
    return float(result.x)


def _logloss_1x2(joint: np.ndarray, ftr: np.ndarray) -> float:
    home, draw, away = outcome_probs(joint)
    chosen = np.where(ftr == "H", home, np.where(ftr == "D", draw, away))
    return float(-np.mean(np.log(np.clip(chosen, 1e-12, None))))


def _logloss_ou(joint: np.ndarray, total: np.ndarray, line: float = 2.5) -> float:
    over, under = over_under_probs(joint, line)
    chosen = np.where(total > line, over, under)
    return float(-np.mean(np.log(np.clip(chosen, 1e-12, None))))


def measure_draw_mass(frame: pd.DataFrame, *, rng) -> DrawMass:
    lam_h = frame["lam_h"].to_numpy()
    lam_a = frame["lam_a"].to_numpy()
    goals_h = frame["fthg"].to_numpy()
    goals_a = frame["ftag"].to_numpy()
    ftr = frame["ftr"].to_numpy()
    total = goals_h + goals_a

    joint = score_matrix(lam_h, lam_a)
    _, draw_prob, _ = outcome_probs(joint)
    realised = float(np.mean(ftr == "D"))
    expected = float(np.mean(draw_prob))

    deficits = []
    is_draw = (ftr == "D").astype(float)
    for _ in range(BOOTSTRAP_REPS):
        pick = rng.integers(0, len(frame), len(frame))
        deficits.append(np.mean(is_draw[pick]) - np.mean(draw_prob[pick]))
    deficit_ci = tuple(np.percentile(deficits, [2.5, 97.5]) * 100)

    rows = []
    for name, (x, y) in {"0-0": (0, 0), "1-0": (1, 0), "0-1": (0, 1), "1-1": (1, 1)}.items():
        rows.append({
            "cell": name,
            "observed": int(np.sum((goals_h == x) & (goals_a == y))),
            "expected": float(np.sum(joint[:, x, y])),
        })
    cells = pd.DataFrame(rows)
    cells["ratio"] = cells["observed"] / cells["expected"]

    rho = fit_rho(frame)
    boot_rho = []
    for _ in range(200):  # rho refits are the expensive part; fewer reps
        pick = rng.integers(0, len(frame), len(frame))
        boot_rho.append(fit_rho(frame.iloc[pick]))
    rho_ci = tuple(np.percentile(boot_rho, [2.5, 97.5]))

    joint_rho = score_matrix(lam_h, lam_a, rho)
    _, draw_rho, _ = outcome_probs(joint_rho)

    return DrawMass(
        n=len(frame),
        realised=realised * 100,
        expected=expected * 100,
        deficit_pts=(realised - expected) * 100,
        deficit_ci=deficit_ci,
        cells=cells,
        rho=rho,
        rho_ci=rho_ci,
        delta_logloss_1x2=_logloss_1x2(joint_rho, ftr) - _logloss_1x2(joint, ftr),
        delta_logloss_ou=_logloss_ou(joint_rho, total) - _logloss_ou(joint, total),
        expected_with_rho=float(np.mean(draw_rho)) * 100,
    )


# --- measurement 3: margin -------------------------------------------------


@dataclass
class Margin:
    n: int
    ratio: float
    ratio_ci: tuple[float, float]
    tail_observed: float
    tail_expected: float
    by_abs: pd.DataFrame = field(default_factory=pd.DataFrame)


def measure_margin(frame: pd.DataFrame, *, rng) -> Margin:
    """Independent Poisson predicts Var(margin) = lambda_h + lambda_a, because
    the variances add even though the mean difference does not."""
    lam_h = frame["lam_h"].to_numpy()
    lam_a = frame["lam_a"].to_numpy()
    observed = (frame["fthg"] - frame["ftag"]).to_numpy(dtype=float)
    expected_mean = lam_h - lam_a
    expected_var = lam_h + lam_a

    ratio = float(np.mean((observed - expected_mean) ** 2) / np.mean(expected_var))
    draws = []
    for _ in range(BOOTSTRAP_REPS):
        pick = rng.integers(0, len(frame), len(frame))
        draws.append(
            np.mean((observed[pick] - expected_mean[pick]) ** 2) / np.mean(expected_var[pick])
        )
    ratio_ci = tuple(np.percentile(draws, [2.5, 97.5]))

    joint = score_matrix(lam_h, lam_a)
    margins, probs = margin_pmf(joint)
    abs_margin = np.abs(observed)

    rows = []
    for threshold in (3, 4, 5, 6):
        rows.append({
            "|margin| >=": threshold,
            "observed %": float(np.mean(abs_margin >= threshold)) * 100,
            "expected %": float(np.mean(probs[:, np.abs(margins) >= threshold].sum(axis=1))) * 100,
        })
    by_abs = pd.DataFrame(rows)
    by_abs["ratio"] = by_abs["observed %"] / by_abs["expected %"]

    tail = np.abs(margins) >= 5
    return Margin(
        n=len(frame),
        ratio=ratio,
        ratio_ci=ratio_ci,
        tail_observed=float(np.mean(abs_margin >= 5)) * 100,
        tail_expected=float(np.mean(probs[:, tail].sum(axis=1))) * 100,
        by_abs=by_abs,
    )


# --- runner ----------------------------------------------------------------


def run(conn, divisions=("E0", "E1", "E2", "E3")) -> dict:
    corpus = store.read_matches(conn, purpose=Purpose.DEV, divisions=divisions)
    frame = corpus.for_measurement()
    frame = frame.dropna(subset=["fthg", "ftag", "ftr"]).copy()
    frame["fthg"] = frame["fthg"].astype(int)
    frame["ftag"] = frame["ftag"].astype(int)

    print(f"development set: {len(frame)} matches, "
          f"{frame['season'].nunique()} seasons, divisions {list(divisions)}")
    print(f"scoring rate: {(frame['fthg'] + frame['ftag']).mean():.3f} goals/match\n")

    print("fitting walk-forward lambdas (out-of-sample, refit fortnightly)...")
    scored = poisson_model.walk_forward_lambdas(frame)
    print(f"  {len(scored)} matches with out-of-sample lambdas "
          f"({scored['match_date'].min().date()} to {scored['match_date'].max().date()})")
    predicted = scored["lam_h"] + scored["lam_a"]
    actual = scored["fthg"] + scored["ftag"]
    print(f"  mean predicted total {predicted.mean():.3f} vs realised {actual.mean():.3f}\n")

    rng = np.random.default_rng(RNG_SEED)
    results = {
        "scored": scored,
        "totals": measure_totals(scored, "all", rng=rng),
        "totals_by_division": [
            measure_totals(scored[scored["division"] == d], d)
            for d in divisions
        ],
        "draw": measure_draw_mass(scored, rng=rng),
        "draw_by_division": [
            (d, measure_draw_mass(scored[scored["division"] == d], rng=rng))
            for d in divisions
        ],
        "margin": measure_margin(scored, rng=rng),
    }

    quartiles = pd.qcut(predicted, 4, labels=["Q1 low", "Q2", "Q3", "Q4 high"])
    results["totals_by_lambda"] = [
        measure_totals(scored[quartiles == q], str(q)) for q in quartiles.cat.categories
    ]
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=None)
    args = parser.parse_args()

    conn = db.connect(args.db)
    results = run(conn)

    totals: Dispersion = results["totals"]
    draw: DrawMass = results["draw"]
    margin: Margin = results["margin"]

    print("=" * 72)
    print("1. TOTALS DISPERSION   Var(total | lambda) / E[lambda]; Poisson says 1.000")
    print("=" * 72)
    print(f"  total          {totals.total_ratio:.4f}  "
          f"95% CI [{totals.total_ci[0]:.4f}, {totals.total_ci[1]:.4f}]   n={totals.n}")
    print(f"  home side      {totals.home_ratio:.4f}")
    print(f"  away side      {totals.away_ratio:.4f}")
    print(f"  residual corr  {totals.residual_corr:+.4f}")
    print("\n  by division:")
    for d in results["totals_by_division"]:
        print(f"    {d.label}  total {d.total_ratio:.4f}  sides "
              f"{d.home_ratio:.4f}/{d.away_ratio:.4f}  corr {d.residual_corr:+.4f}  n={d.n}")
    print("\n  by predicted-total quartile:")
    for d in results["totals_by_lambda"]:
        print(f"    {d.label:8} total {d.total_ratio:.4f}  corr {d.residual_corr:+.4f}  n={d.n}")

    print("\n" + "=" * 72)
    print("2. DRAW MASS and the Dixon-Coles tau")
    print("=" * 72)
    print(f"  realised draws   {draw.realised:.2f}%")
    print(f"  independent Poisson expects {draw.expected:.2f}%")
    print(f"  deficit          {draw.deficit_pts:+.2f} pts  "
          f"95% CI [{draw.deficit_ci[0]:+.2f}, {draw.deficit_ci[1]:+.2f}]")
    print("\n  low-score cells (the ones tau modifies):")
    shown = draw.cells.copy()
    shown["expected"] = shown["expected"].map(lambda v: f"{v:.1f}")
    shown["ratio"] = shown["ratio"].map(lambda v: f"{v:.3f}")
    print(shown.to_string(index=False))
    print("\n  draw deficit by division:")
    for label, sub in results["draw_by_division"]:
        print(f"    {label}  realised {sub.realised:.2f}%  expected {sub.expected:.2f}%  "
              f"deficit {sub.deficit_pts:+.2f} pts "
              f"CI [{sub.deficit_ci[0]:+.2f}, {sub.deficit_ci[1]:+.2f}]  n={sub.n}")
    print(f"\n  fitted rho       {draw.rho:+.4f}  "
          f"95% CI [{draw.rho_ci[0]:+.4f}, {draw.rho_ci[1]:+.4f}]")
    print(f"  draws with rho   {draw.expected_with_rho:.2f}% "
          f"(realised {draw.realised:.2f}%)")
    print(f"  delta logloss 1X2  {draw.delta_logloss_1x2:+.6f}  (negative = better)")
    print(f"  delta logloss O/U  {draw.delta_logloss_ou:+.6f}")

    print("\n" + "=" * 72)
    print("3. MARGIN DISPERSION   Var(margin | lambda) / E[lambda]")
    print("=" * 72)
    print(f"  ratio            {margin.ratio:.4f}  "
          f"95% CI [{margin.ratio_ci[0]:.4f}, {margin.ratio_ci[1]:.4f}]")
    print(f"  |margin| >= 5    observed {margin.tail_observed:.2f}%  "
          f"expected {margin.tail_expected:.2f}%")
    print()
    print(margin.by_abs.to_string(index=False, float_format=lambda v: f"{v:.3f}"))

    for name, detail in (
        ("totals_dispersion", {"ratio": totals.total_ratio, "home": totals.home_ratio,
                               "away": totals.away_ratio, "corr": totals.residual_corr,
                               "n": totals.n}),
        ("draw_mass", {"realised": draw.realised, "expected": draw.expected,
                       "deficit_pts": draw.deficit_pts, "rho": draw.rho,
                       "d_logloss_1x2": draw.delta_logloss_1x2,
                       "d_logloss_ou": draw.delta_logloss_ou, "n": draw.n}),
        ("margin_dispersion", {"ratio": margin.ratio, "tail_obs": margin.tail_observed,
                               "tail_exp": margin.tail_expected, "n": margin.n}),
    ):
        ledger.record(conn, kind=ledger.PROBE, name=f"p0_{name}", purpose=str(Purpose.DEV),
                      detail=detail,
                      reason="SPEC 2.4: re-measure gtleague's closed results at English lambda")
    print(f"\nrecorded 3 probes in the gate ledger "
          f"(trial count now {ledger.trial_count(conn)})")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
