"""Time-decayed ridge Poisson: the joint attack/defence head.

    log lambda_home = c + home + att[i] + dfn[j]
    log lambda_away = c        + att[j] + dfn[i]

`att` is attacking strength and `dfn` defensive leakiness, both ridge-penalised
toward zero. The penalty is not optional: without it the parameterisation is
degenerate, since adding k to every `att` and subtracting it from every `dfn`
leaves every lambda unchanged. Shrinking to zero also gives an unseen team the
league-average profile, which is the correct cold-start prior and the exact
gap the P2 player layer is meant to fill.

Fitted jointly across divisions so promotion and relegation put every club on
one scale (SPEC §2.2). Division is deliberately NOT a feature: within a season
it is collinear with team identity, so it is unidentifiable rather than merely
unhelpful.

In P0 this is a *measurement instrument*. Its half-life and penalty are frozen
at defensible defaults; sweeping them is P1 work and would burn trials against
the development set before there is anything to spend them on.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import optimize

#: Mid-range of the defensible window in SPEC §3.2. English football supplies
#: ~0.15 matches per team per day, so parity with gtleague's 62 effective
#: matches needs ~287 days; Dixon-Coles' own fitted decay implies ~107.
DEFAULT_HALF_LIFE_DAYS = 200.0

#: Weak. The design matrix is far sparser than gtleague's, whose 0.01 will not
#: transfer, but the value only has to be sane for a measurement instrument.
DEFAULT_ALPHA = 1.0

#: Matches older than this contribute less than 3% weight; dropping them makes
#: several hundred refits tractable without changing the fit materially.
DECAY_HORIZON_HALF_LIVES = 5.0


@dataclass(frozen=True)
class PoissonFit:
    intercept: float
    home: float
    att: np.ndarray
    dfn: np.ndarray
    n_train: int

    def predict(self, home_idx: np.ndarray, away_idx: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """(lambda_home, lambda_away) for each fixture."""
        lam_h = np.exp(self.intercept + self.home + self.att[home_idx] + self.dfn[away_idx])
        lam_a = np.exp(self.intercept + self.att[away_idx] + self.dfn[home_idx])
        return lam_h, lam_a


def fit(
    home_idx: np.ndarray,
    away_idx: np.ndarray,
    home_goals: np.ndarray,
    away_goals: np.ndarray,
    weights: np.ndarray,
    n_teams: int,
    *,
    alpha: float = DEFAULT_ALPHA,
) -> PoissonFit:
    """Weighted penalised Poisson MLE.

    Each match contributes two observations (one per side), so the attacking
    and defensive coefficients are estimated from the same likelihood rather
    than from two separate fits.
    """
    attacker = np.concatenate([home_idx, away_idx])
    defender = np.concatenate([away_idx, home_idx])
    is_home = np.concatenate([np.ones_like(home_idx, dtype=float),
                              np.zeros_like(away_idx, dtype=float)])
    y = np.concatenate([home_goals, away_goals]).astype(float)
    w = np.concatenate([weights, weights]).astype(float)

    def unpack(params):
        return params[0], params[1], params[2:2 + n_teams], params[2 + n_teams:]

    def objective(params):
        c, h, att, dfn = unpack(params)
        eta = c + h * is_home + att[attacker] + dfn[defender]
        eta = np.clip(eta, -20.0, 5.0)
        lam = np.exp(eta)
        nll = float(np.sum(w * (lam - y * eta)))
        penalty = alpha * (float(att @ att) + float(dfn @ dfn))

        resid = w * (lam - y)
        grad = np.empty_like(params)
        grad[0] = resid.sum()
        grad[1] = float(resid @ is_home)
        grad[2:2 + n_teams] = np.bincount(attacker, resid, minlength=n_teams) + 2 * alpha * att
        grad[2 + n_teams:] = np.bincount(defender, resid, minlength=n_teams) + 2 * alpha * dfn
        return nll + penalty, grad

    x0 = np.zeros(2 + 2 * n_teams)
    x0[0] = np.log(max(y.mean(), 0.1))
    result = optimize.minimize(objective, x0, jac=True, method="L-BFGS-B",
                               options={"maxiter": 500})
    c, h, att, dfn = unpack(result.x)
    return PoissonFit(float(c), float(h), att.copy(), dfn.copy(), int(len(home_idx)))


def decay_weights(ages_days: np.ndarray, half_life: float = DEFAULT_HALF_LIFE_DAYS) -> np.ndarray:
    return np.power(0.5, ages_days / half_life)


def walk_forward_lambdas(
    frame,
    *,
    half_life: float = DEFAULT_HALF_LIFE_DAYS,
    alpha: float = DEFAULT_ALPHA,
    refit_days: int = 14,
    burn_in_days: int = 365,
):
    """Out-of-sample lambdas for every match, refitting as the season advances.

    Every prediction comes from a fit that saw only strictly earlier matches --
    the point of the exercise. Measuring dispersion on in-sample lambdas would
    understate it, because the fit absorbs the very variance being measured.

    Returns the frame with `lam_h`/`lam_a` attached, restricted to matches that
    had at least `burn_in_days` of history behind them.
    """
    import pandas as pd

    work = frame.sort_values("match_date").reset_index(drop=True)
    teams = sorted(set(work["home_team"]) | set(work["away_team"]))
    index = {name: i for i, name in enumerate(teams)}
    home_idx = work["home_team"].map(index).to_numpy()
    away_idx = work["away_team"].map(index).to_numpy()
    goals_h = work["fthg"].astype(int).to_numpy()
    goals_a = work["ftag"].astype(int).to_numpy()
    dates = work["match_date"].to_numpy()

    start = work["match_date"].min() + pd.Timedelta(days=burn_in_days)
    horizon = pd.Timedelta(days=half_life * DECAY_HORIZON_HALF_LIVES)

    lam_h = np.full(len(work), np.nan)
    lam_a = np.full(len(work), np.nan)

    cutoff = start
    end = work["match_date"].max()
    while cutoff <= end:
        window_end = cutoff + pd.Timedelta(days=refit_days)
        target = (work["match_date"] >= cutoff) & (work["match_date"] < window_end)
        if not target.any():
            cutoff = window_end
            continue

        train = (work["match_date"] < cutoff) & (work["match_date"] >= cutoff - horizon)
        if train.sum() < 200:
            cutoff = window_end
            continue

        ages = (cutoff - work.loc[train, "match_date"]).dt.days.to_numpy().astype(float)
        model = fit(
            home_idx[train.to_numpy()], away_idx[train.to_numpy()],
            goals_h[train.to_numpy()], goals_a[train.to_numpy()],
            decay_weights(ages, half_life), len(teams), alpha=alpha,
        )
        rows = target.to_numpy()
        lam_h[rows], lam_a[rows] = model.predict(home_idx[rows], away_idx[rows])
        cutoff = window_end

    work["lam_h"] = lam_h
    work["lam_a"] = lam_a
    return work[np.isfinite(lam_h)].reset_index(drop=True)
