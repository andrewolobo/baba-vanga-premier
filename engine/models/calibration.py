"""Per-population calibration, and the market-blend ablation.

Two fits, deliberately the same shape so they can be compared arm to arm:

    calibration   eta_k = a_k * log(p_model_k) + b_k
    blend         eta_k = a   * log(p_model_k) + c * log(p_market_k) + b_k

`a` in the blend is the whole question of P3: what the model adds *once the
market is already in the equation*. If it is zero, the head has nothing the
price does not already carry, and no selective rule built on it can beat the
close.

Everything here is fitted walk-forward by season -- fit on strictly earlier
seasons, apply to the held-out one. A calibration fitted in-sample would report
whatever improvement it was asked to produce, which is why SPEC §P3 insists on
the raw basis and the poison test.

Probabilities are taken from stored **lambdas**, never from stored probability
columns. Calibrating an already-calibrated input compounds silently and looks
fine on every diagnostic.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import optimize
from scipy.special import logsumexp

#: Below this many rows a population is not fitted; the identity map is used and
#: the caller is told. Six parameters need more than a few hundred matches.
MIN_FIT_ROWS = 500

_EPS = 1e-12


def _safe_log(p) -> np.ndarray:
    return np.log(np.clip(np.asarray(p, dtype=float), _EPS, 1.0))


def logit(p) -> np.ndarray:
    p = np.clip(np.asarray(p, dtype=float), _EPS, 1.0 - _EPS)
    return np.log(p / (1.0 - p))


# --- 1X2: vector scaling ---------------------------------------------------


@dataclass(frozen=True)
class VectorScaling:
    """Per-class slope and bias on log-probabilities, softmax-renormalised.

    Richer than a single temperature, which can only sharpen or flatten the
    whole distribution: the measured defect on this corpus is specifically a
    draw deficit in E1-E3, which needs the draw class to move on its own.
    """

    slopes: np.ndarray          # (3,)
    biases: np.ndarray          # (3,), last fixed at 0 -- softmax is shift-invariant
    n_train: int
    fitted: bool = True

    def apply(self, probs: np.ndarray) -> np.ndarray:
        eta = self.slopes * _safe_log(probs) + self.biases
        return np.exp(eta - logsumexp(eta, axis=1, keepdims=True))

    @classmethod
    def identity(cls) -> "VectorScaling":
        return cls(np.ones(3), np.zeros(3), 0, fitted=False)


def fit_vector_scaling(probs: np.ndarray, outcomes) -> VectorScaling:
    """Fit per-class slope/bias. Falls back to identity on too little data.

    Five free parameters: three slopes and two biases. The third bias is fixed
    at zero because softmax is shift-invariant, so leaving it free would make
    the fit unidentified rather than more flexible.
    """
    probs = np.asarray(probs, dtype=float)
    y = _onehot(outcomes)
    if len(probs) < MIN_FIT_ROWS:
        return VectorScaling.identity()

    log_p = _safe_log(probs)

    def objective(params):
        eta = params[:3] * log_p + np.concatenate([params[3:5], [0.0]])
        return -np.sum(y * (eta - logsumexp(eta, axis=1, keepdims=True)))

    result = optimize.minimize(objective, np.array([1.0, 1.0, 1.0, 0.0, 0.0]),
                               method="L-BFGS-B", options={"maxiter": 500})
    return VectorScaling(result.x[:3], np.concatenate([result.x[3:5], [0.0]]),
                         len(probs))


def _onehot(outcomes) -> np.ndarray:
    outcomes = np.asarray(outcomes)
    return np.stack([(outcomes == label).astype(float) for label in ("H", "D", "A")], axis=1)


# --- O/U: binary Platt -----------------------------------------------------


@dataclass(frozen=True)
class PlattScaling:
    slope: float
    bias: float
    n_train: int
    fitted: bool = True

    def apply(self, p) -> np.ndarray:
        z = self.slope * logit(p) + self.bias
        return 1.0 / (1.0 + np.exp(-z))

    @classmethod
    def identity(cls) -> "PlattScaling":
        return cls(1.0, 0.0, 0, fitted=False)


def fit_platt(p, y) -> PlattScaling:
    p, y = np.asarray(p, dtype=float), np.asarray(y, dtype=float)
    if len(p) < MIN_FIT_ROWS:
        return PlattScaling.identity()
    z = logit(p)

    def objective(params):
        eta = params[0] * z + params[1]
        return float(np.sum(np.logaddexp(0.0, eta) - y * eta))

    result = optimize.minimize(objective, np.array([1.0, 0.0]), method="L-BFGS-B",
                               options={"maxiter": 500})
    return PlattScaling(float(result.x[0]), float(result.x[1]), len(p))


# --- the blend: model + market --------------------------------------------


@dataclass(frozen=True)
class Blend1X2:
    """eta_k = a*log(p_model_k) + c*log(p_market_k) + b_k.

    `model_weight` is the coefficient the whole phase turns on.
    """

    model_weight: float
    market_weight: float
    biases: np.ndarray
    n_train: int
    fitted: bool = True

    def apply(self, model_probs, market_probs) -> np.ndarray:
        eta = (self.model_weight * _safe_log(model_probs)
               + self.market_weight * _safe_log(market_probs) + self.biases)
        return np.exp(eta - logsumexp(eta, axis=1, keepdims=True))

    @classmethod
    def identity(cls) -> "Blend1X2":
        return cls(0.0, 1.0, np.zeros(3), 0, fitted=False)


def fit_blend_1x2(model_probs, market_probs, outcomes) -> Blend1X2:
    model_probs = np.asarray(model_probs, dtype=float)
    market_probs = np.asarray(market_probs, dtype=float)
    y = _onehot(outcomes)
    if len(model_probs) < MIN_FIT_ROWS:
        return Blend1X2.identity()

    log_model, log_market = _safe_log(model_probs), _safe_log(market_probs)

    def objective(params):
        a, c = params[0], params[1]
        biases = np.concatenate([params[2:4], [0.0]])
        eta = a * log_model + c * log_market + biases
        return -np.sum(y * (eta - logsumexp(eta, axis=1, keepdims=True)))

    result = optimize.minimize(objective, np.array([0.1, 1.0, 0.0, 0.0]),
                               method="L-BFGS-B", options={"maxiter": 500})
    return Blend1X2(float(result.x[0]), float(result.x[1]),
                    np.concatenate([result.x[2:4], [0.0]]), len(model_probs))


@dataclass(frozen=True)
class BlendBinary:
    model_weight: float
    market_weight: float
    bias: float
    n_train: int
    fitted: bool = True

    def apply(self, model_p, market_p) -> np.ndarray:
        eta = (self.model_weight * logit(model_p)
               + self.market_weight * logit(market_p) + self.bias)
        return 1.0 / (1.0 + np.exp(-eta))

    @classmethod
    def identity(cls) -> "BlendBinary":
        return cls(0.0, 1.0, 0.0, 0, fitted=False)


def fit_blend_binary(model_p, market_p, y) -> BlendBinary:
    model_p = np.asarray(model_p, dtype=float)
    market_p = np.asarray(market_p, dtype=float)
    y = np.asarray(y, dtype=float)
    if len(model_p) < MIN_FIT_ROWS:
        return BlendBinary.identity()
    zm, zk = logit(model_p), logit(market_p)

    def objective(params):
        eta = params[0] * zm + params[1] * zk + params[2]
        return float(np.sum(np.logaddexp(0.0, eta) - y * eta))

    result = optimize.minimize(objective, np.array([0.1, 1.0, 0.0]),
                               method="L-BFGS-B", options={"maxiter": 500})
    return BlendBinary(float(result.x[0]), float(result.x[1]), float(result.x[2]),
                       len(model_p))
