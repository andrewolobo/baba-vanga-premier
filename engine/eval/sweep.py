"""Sweep runner, the 1-SE selection rule, and the ledger writes.

Selection is on **goal Poisson deviance** -- the model's own out-of-sample
objective, two count-valued observations per match. 1X2 and O/U 2.5 logloss are
computed on the same runs and reported, never used to choose. If they rank the
grid differently that is written down as a finding rather than used to break a
tie in whichever direction looks better.

The choice rule is the **1-SE rule**: take the most-regularised setting whose
score is within one standard error of the best. On a flat surface plain argmin
lets sampling noise pick the hyperparameter, and it picks a different one every
time the seed changes. Preferring shrinkage on a tie is the whole point.

**The standard error must be the PAIRED one.** Arms are evaluated on the same
matches, so almost all of the variance in a single arm's mean loss is match
difficulty common to every arm, and it cancels in the comparison. On this
corpus the marginal block-bootstrap SE of one arm's mean deviance is ~0.0072
while the paired SE of the difference between two arms is ~0.00025 -- a factor
of twenty-nine. Thresholding on the marginal SE declares every arm tied with
every other, which does not make the rule conservative: it makes it vacuous,
handing the decision to the tie-break regardless of the evidence. That error
was live in the first P1 run and it chose alpha=2.0 over an alpha=0.25 that a
paired comparison separates decisively.


Every sweep writes one `gate_ledger` row carrying its full grid, so the trial
count that later feeds PBO deflation is real rather than reconstructed.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from typing import Any

import numpy as np
import pandas as pd

from engine.eval import bootstrap, metrics
from engine.eval.walkforward import WalkForwardConfig, walk_forward


@dataclass(frozen=True)
class ArmResult:
    value: Any
    config: WalkForwardConfig
    n: int
    deviance: float
    marginal_stderr: float   # precision of this arm's absolute score
    paired_stderr: float     # precision of its difference from the best arm
    ll_1x2: float
    ll_ou25: float

    def as_dict(self) -> dict:
        return {"value": self.value, "n": self.n, "deviance": self.deviance,
                "marginal_stderr": self.marginal_stderr,
                "paired_stderr": self.paired_stderr,
                "ll_1x2": self.ll_1x2, "ll_ou25": self.ll_ou25}


@dataclass(frozen=True)
class SweepResult:
    parameter: str
    arms: tuple[ArmResult, ...]
    chosen: ArmResult
    best: ArmResult
    rule: str

    @property
    def spread(self) -> float:
        """Deviance range across the grid. A flat sweep is a weak sweep, and
        knowing that is more useful than the winner."""
        scores = [a.deviance for a in self.arms]
        return max(scores) - min(scores)

    @property
    def chose_the_best(self) -> bool:
        return self.chosen.value == self.best.value

    @property
    def censored(self) -> str | None:
        """Whether the optimum sits on a grid boundary.

        A boundary optimum is not an optimum, it is a grid that stopped too
        early -- and reporting it as a chosen value would be the difference
        between "the data prefers 300" and "the data prefers at least 300".
        """
        values = [a.value for a in self.arms]
        if self.best.value == values[0]:
            return "lower"
        if self.best.value == values[-1]:
            return "upper"
        return None

    def table(self) -> pd.DataFrame:
        frame = pd.DataFrame([a.as_dict() for a in self.arms])
        frame["chosen"] = [a.value == self.chosen.value for a in self.arms]
        return frame

    def as_detail(self) -> dict:
        return {"parameter": self.parameter, "rule": self.rule,
                "chosen": self.chosen.value, "best": self.best.value,
                "spread": self.spread, "censored": self.censored,
                "arms": [a.as_dict() for a in self.arms]}


def one_se_rule(values: Sequence, scores: Sequence[float],
                paired_stderrs: Sequence[float], *, more_regularised) -> int:
    """Index of the most-regularised arm within one PAIRED SE of the best.

    `paired_stderrs[i]` is the standard error of arm i's difference from the
    best arm -- not the standard error of arm i's own mean. See the module
    docstring: on paired data the two differ by more than an order of
    magnitude, and using the wrong one makes the rule vacuous.

    `more_regularised(value) -> sort key`, ascending, so the last eligible arm
    in that order is the most shrunk.
    """
    scores = np.asarray(scores, dtype=float)
    best = int(np.argmin(scores))
    eligible = [i for i in range(len(scores))
                if scores[i] - scores[best] <= paired_stderrs[i]]
    return max(eligible, key=lambda i: more_regularised(values[i]))


def _align(scored: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Restrict every arm to the matches all of them scored.

    Arms can differ in coverage -- a longer decay horizon reaches the minimum
    training size on a different date -- and comparing means over different
    samples is not a paired test at all.
    """
    keyed = {name: out.set_index(["match_date", "home_team", "away_team"])
             for name, out in scored.items()}
    shared = None
    for out in keyed.values():
        shared = out.index if shared is None else shared.intersection(out.index)
    return {name: out.loc[shared].sort_index() for name, out in keyed.items()}


def run(frame: pd.DataFrame, parameter: str, values: Sequence,
        base: WalkForwardConfig, *, more_regularised: Callable[[Any], float] | None = None,
        reps: int = bootstrap.DEFAULT_REPS,
        score_filter: Callable[[pd.DataFrame], pd.DataFrame] | None = None) -> SweepResult:
    """Evaluate one hyperparameter across `values` and apply the 1-SE rule."""
    more_regularised = more_regularised or (lambda v: float(v))

    scored = {}
    configs = {}
    for value in values:
        cfg = replace(base, **{parameter: value})
        out = walk_forward(frame, cfg)
        if score_filter is not None:
            out = score_filter(out)
        scored[str(value)] = out
        configs[str(value)] = cfg
    aligned = _align(scored)

    any_arm = next(iter(aligned.values()))
    blocks = bootstrap.week_blocks(any_arm.index.get_level_values("match_date"))
    losses = {name: metrics.goal_deviance(out) for name, out in aligned.items()}
    means = {name: float(loss.mean()) for name, loss in losses.items()}
    best_name = min(means, key=means.get)

    arms: list[ArmResult] = []
    for value in values:
        name = str(value)
        out = aligned[name]
        probs = metrics.model_probs(out["lam_h"], out["lam_a"])
        paired = (0.0 if name == best_name else
                  bootstrap.paired(losses[name], losses[best_name], blocks, reps=reps).stderr)
        arms.append(ArmResult(
            value=value, config=configs[name], n=len(out),
            deviance=means[name],
            marginal_stderr=bootstrap.standard_error(losses[name], blocks, reps=reps),
            paired_stderr=paired,
            ll_1x2=float(metrics.logloss_1x2(probs, out["ftr"]).mean()),
            ll_ou25=float(metrics.logloss_binary(
                probs["p_over"], metrics.over_outcome(out)).mean()),
        ))

    best = next(a for a in arms if str(a.value) == best_name)
    chosen = arms[one_se_rule([a.value for a in arms], [a.deviance for a in arms],
                              [a.paired_stderr for a in arms],
                              more_regularised=more_regularised)]
    return SweepResult(parameter, tuple(arms), chosen, best, rule="1-SE (paired)")


def compare(frame: pd.DataFrame, arms: dict[str, WalkForwardConfig], reference: str,
            *, reps: int = bootstrap.DEFAULT_REPS,
            score_filter: Callable[[pd.DataFrame], pd.DataFrame] | None = None,
            score_on: Callable[[pd.DataFrame], pd.DataFrame] | None = None) -> dict:
    """Paired comparison of named arms against `reference`, on shared matches.

    Arms can produce different match sets (a different fit population may pass
    the burn-in at a different time), so the comparison is restricted to the
    matches every arm scored. Comparing means over different samples would not
    be a paired test at all.
    """
    scored = {}
    for name, cfg in arms.items():
        out = walk_forward(frame, cfg)
        if score_filter is not None:
            out = score_filter(out)
        if score_on is not None:
            out = score_on(out)
        scored[name] = out
    aligned = _align(scored)

    ref = aligned[reference]
    blocks = bootstrap.week_blocks(ref.index.get_level_values("match_date"))
    ref_loss = metrics.goal_deviance(ref)

    results = {"n": len(ref), "reference": reference, "arms": {}}
    for name, out in aligned.items():
        loss = metrics.goal_deviance(out)
        probs = metrics.model_probs(out["lam_h"], out["lam_a"])
        entry = {"deviance": float(loss.mean()),
                 "ll_1x2": float(metrics.logloss_1x2(probs, out["ftr"]).mean()),
                 "ll_ou25": float(metrics.logloss_binary(
                     probs["p_over"], metrics.over_outcome(out)).mean())}
        if name != reference:
            entry["vs_reference"] = bootstrap.paired(
                loss, ref_loss, blocks, reps=reps).as_dict()
        results["arms"][name] = entry
    return results
