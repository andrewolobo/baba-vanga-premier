"""Scoring rules, and the market probabilities they are scored against.

Three deliberate separations live here, because collapsing any of them is how
this kind of evaluation goes quietly wrong:

*Selection metric vs served metric.* Hyperparameters are chosen on
`goal_deviance` -- the model's own out-of-sample Poisson logloss, two
count-valued observations per match. 1X2 and O/U 2.5 logloss are computed on
the same runs and reported, never used to select. If they disagree with the
deviance ranking that is a finding to write down, not a tie to break.

*Pre-close vs closing.* Two different market opinions from two different
information sets, and never mixed. `MARKET_COLUMNS` names them explicitly
rather than letting a caller reach for whichever odds column is populated.

*De-vigged vs break-even.* Scoring a market as a forecaster needs normalised
probabilities (`engine.odds.devig_probs`). Deciding whether a bet is worth
placing needs the raw vig-inclusive `1/odds`. This module only ever does the
former; it does not import `breakeven_prob` at all, so the two cannot be
crossed here.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from engine.eval.dispersion import outcome_probs, over_under_probs, score_matrix
from engine.odds import devig_probs

#: Odds columns per information set. Pre-close is the Friday/Tuesday afternoon
#: snapshot, before team news; closing is at kickoff, after it.
#:
#: The closing Avg/Max block only begins in 2019-20, so Pinnacle is the only
#: closing source that spans the development set (from 2012-13, 85% coverage).
#: `close_avg_*` is offered as a second closing variant for the seasons that
#: have it, not as a fallback -- silently swapping sources mid-corpus would put
#: two different books in one column.
MARKET_COLUMNS: dict[str, dict[str, tuple[str, ...]]] = {
    "pre_close": {
        "1x2": ("avg_h", "avg_d", "avg_a"),
        "ou25": ("avg_over25", "avg_under25"),
    },
    "closing": {
        "1x2": ("close_ps_h", "close_ps_d", "close_ps_a"),
        "ou25": ("close_avg_over25", "close_avg_under25"),
    },
    "closing_avg": {
        "1x2": ("close_avg_h", "close_avg_d", "close_avg_a"),
        "ou25": ("close_avg_over25", "close_avg_under25"),
    },
    #: Pinnacle pre-close, so that a like-for-like pre-close/closing comparison
    #: can be made within one book (H10). Comparing Avg pre-close against
    #: Pinnacle closing would confound information set with bookmaker.
    "pre_close_ps": {
        "1x2": ("ps_h", "ps_d", "ps_a"),
        "ou25": ("avg_over25", "avg_under25"),
    },
}

_EPS = 1e-12


# --- model probabilities ---------------------------------------------------


def model_probs(lam_h: np.ndarray, lam_a: np.ndarray, *, line: float = 2.5) -> pd.DataFrame:
    """1X2 and over/under probabilities from the Poisson pmf.

    Dixon-Coles tau is deliberately absent: P0-2 closed it, and on O/U it is
    incapable of moving the number at all (every cell it touches totals < 2.5).
    """
    joint = score_matrix(np.asarray(lam_h, dtype=float), np.asarray(lam_a, dtype=float))
    home, draw, away = outcome_probs(joint)
    over, under = over_under_probs(joint, line=line)
    return pd.DataFrame({"p_h": home, "p_d": draw, "p_a": away,
                         "p_over": over, "p_under": under})


def market_probs(frame: pd.DataFrame, information_set: str) -> pd.DataFrame:
    """De-vigged market probabilities, NaN wherever the odds are missing.

    NaN rather than a fallback: a match the book did not price is not a match
    the book priced badly, and quietly substituting another source would make
    the comparison population drift with coverage.
    """
    cols = MARKET_COLUMNS[information_set]
    h, d, a = (frame[c].to_numpy(dtype=float) for c in cols["1x2"])
    qh, qd, qa = devig_probs(h, d, a)
    o, u = (frame[c].to_numpy(dtype=float) for c in cols["ou25"])
    qo, qu = devig_probs(o, u)
    return pd.DataFrame({"p_h": qh, "p_d": qd, "p_a": qa, "p_over": qo, "p_under": qu},
                        index=frame.index)


# --- scoring rules ---------------------------------------------------------


def goal_deviance(frame: pd.DataFrame) -> np.ndarray:
    """Per-match Poisson logloss over both sides. THE SELECTION METRIC.

    Summed over the two sides rather than averaged, so one match contributes
    one number and the pairing in the bootstrap stays at match level. Constant
    terms in log(y!) are kept: they cancel in every comparison but their
    presence makes the absolute figure a real logloss rather than a
    proportional-to-one, which is what makes it comparable across runs.
    """
    lam_h = frame["lam_h"].to_numpy(dtype=float)
    lam_a = frame["lam_a"].to_numpy(dtype=float)
    y_h = frame["fthg"].to_numpy(dtype=float)
    y_a = frame["ftag"].to_numpy(dtype=float)
    from scipy.special import gammaln
    return ((lam_h - y_h * np.log(lam_h) + gammaln(y_h + 1))
            + (lam_a - y_a * np.log(lam_a) + gammaln(y_a + 1)))


def logloss_1x2(probs: pd.DataFrame, ftr: pd.Series) -> np.ndarray:
    """Per-match multiclass logloss."""
    outcome = np.asarray(ftr)
    taken = np.where(outcome == "H", probs["p_h"],
             np.where(outcome == "D", probs["p_d"], probs["p_a"])).astype(float)
    return -np.log(np.clip(taken, _EPS, 1.0))


def logloss_binary(p: np.ndarray, y: np.ndarray) -> np.ndarray:
    p = np.clip(np.asarray(p, dtype=float), _EPS, 1.0 - _EPS)
    y = np.asarray(y, dtype=float)
    return -(y * np.log(p) + (1.0 - y) * np.log(1.0 - p))


def brier_1x2(probs: pd.DataFrame, ftr: pd.Series) -> np.ndarray:
    """Per-match multiclass Brier: summed squared error over the three cells."""
    outcome = np.asarray(ftr)
    total = np.zeros(len(probs))
    for label, col in (("H", "p_h"), ("D", "p_d"), ("A", "p_a")):
        total += (probs[col].to_numpy(dtype=float) - (outcome == label)) ** 2
    return total


def brier_binary(p: np.ndarray, y: np.ndarray) -> np.ndarray:
    return (np.asarray(p, dtype=float) - np.asarray(y, dtype=float)) ** 2


def auc(p: np.ndarray, y: np.ndarray) -> float:
    """Rank AUC via the Mann-Whitney identity, ties counted as half.

    Reported for O/U only. On 1X2 it would need one-vs-rest and is the least
    informative of the three rules -- it is invariant to calibration, which is
    most of what this engine has to get right -- so no decision here uses it.
    """
    p = np.asarray(p, dtype=float)
    y = np.asarray(y, dtype=bool)
    n_pos, n_neg = int(y.sum()), int((~y).sum())
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    ranks = pd.Series(p).rank().to_numpy()
    return (ranks[y].sum() - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg)


# --- per-population scorecards ---------------------------------------------


@dataclass(frozen=True)
class Scorecard:
    """One row of the baseline table."""
    n: int
    deviance: float
    ll_1x2: float
    brier_1x2: float
    ll_ou25: float
    brier_ou25: float
    auc_ou25: float

    def as_dict(self) -> dict[str, float]:
        return {"n": self.n, "deviance": self.deviance,
                "ll_1x2": self.ll_1x2, "brier_1x2": self.brier_1x2,
                "ll_ou25": self.ll_ou25, "brier_ou25": self.brier_ou25,
                "auc_ou25": self.auc_ou25}


def over_outcome(frame: pd.DataFrame, line: float = 2.5) -> np.ndarray:
    return ((frame["fthg"].to_numpy(dtype=float)
             + frame["ftag"].to_numpy(dtype=float)) > line).astype(int)


def score(frame: pd.DataFrame, probs: pd.DataFrame, *, with_deviance: bool = True) -> Scorecard:
    """Aggregate a set of probabilities over a set of matches.

    `with_deviance=False` for the market, which has no lambda and therefore no
    goal deviance -- reporting a zero or a NaN there would invite a comparison
    that does not exist.
    """
    y_over = over_outcome(frame)
    return Scorecard(
        n=len(frame),
        deviance=float(goal_deviance(frame).mean()) if with_deviance else float("nan"),
        ll_1x2=float(logloss_1x2(probs, frame["ftr"]).mean()),
        brier_1x2=float(brier_1x2(probs, frame["ftr"]).mean()),
        ll_ou25=float(logloss_binary(probs["p_over"], y_over).mean()),
        brier_ou25=float(brier_binary(probs["p_over"], y_over).mean()),
        auc_ou25=auc(probs["p_over"].to_numpy(), y_over.astype(bool)),
    )


def base_rate_probs(frame: pd.DataFrame) -> pd.DataFrame:
    """The floor every model must clear: in-sample outcome frequencies.

    In-sample on purpose. It is an anchor for reading the table, not an arm --
    an out-of-sample base rate would be a (weak) model and would need a walk-
    forward of its own.
    """
    freq = frame["ftr"].value_counts(normalize=True)
    over = float(over_outcome(frame).mean())
    n = len(frame)
    return pd.DataFrame({
        "p_h": np.full(n, freq.get("H", 0.0)),
        "p_d": np.full(n, freq.get("D", 0.0)),
        "p_a": np.full(n, freq.get("A", 0.0)),
        "p_over": np.full(n, over),
        "p_under": np.full(n, 1.0 - over),
    }, index=frame.index)
