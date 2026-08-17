"""B17 on planted mechanisms: the diagnostic must tell level from dispersion.

Three heads are simulated against outcomes with a known defect and the
instrument has to name it. A calibrated head reads clean; a head whose lambda
is centred low reads LEVEL with a positive residual and a ratio near 1; a head
whose outcomes are over-dispersed reads DISPERSION with a ratio above 1 and a
residual near zero. E0 is always the honest control.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from engine.eval import b17, p7


def simulate(n: int = 16000, *, level: float = 0.0, extra_var: float = 0.0,
             seed: int = 5) -> pd.DataFrame:
    """`level` scales the TRUE rate in E1-E3 above what the head reports.
    `extra_var` mixes a gamma multiplier into E1-E3 outcomes (over-dispersion)."""
    rng = np.random.default_rng(seed)
    division = rng.choice(["E0", "E1", "E2", "E3"], n)
    lower = division != "E0"
    lam_h = np.exp(rng.normal(np.log(1.4), 0.3, n))
    lam_a = np.exp(rng.normal(np.log(1.1), 0.3, n))
    truth_h, truth_a = lam_h.copy(), lam_a.copy()
    truth_h[lower] *= 1.0 + level
    truth_a[lower] *= 1.0 + level
    if extra_var:
        g = rng.gamma(1.0 / extra_var, extra_var, n)
        truth_h[lower] *= g[lower]
        truth_a[lower] *= g[lower]
    fthg, ftag = rng.poisson(truth_h), rng.poisson(truth_a)
    dates = pd.Timestamp("2015-08-01") + pd.to_timedelta(rng.integers(0, 3 * 365, n), "D")
    return pd.DataFrame({"lam_h": lam_h, "lam_a": lam_a, "fthg": fthg, "ftag": ftag,
                         "division": division, "match_date": dates})


def _run(frame):
    return b17.diagnose(frame, p7.joint_of(frame))


def test_a_calibrated_head_reads_clean_everywhere():
    out = _run(simulate())
    v = out["verdict"]
    assert v["P1_control_clean"]
    assert not v["P2_lower_low_lambda_residual_positive_10_to_25"]
    assert not v["P4_alternative_dispersion"]
    for d in ("E1", "E2", "E3"):
        r = out["by_division"][d]["dispersion_ratio"]
        assert r["ci_low"] < 1.0 < r["ci_high"]


def test_a_level_defect_is_named_level():
    out = _run(simulate(level=0.08))
    v = out["verdict"]
    assert v["P1_control_clean"]
    assert v["mechanism"].startswith("LEVEL"), v
    for d in ("E1", "E2", "E3"):
        assert out["by_division"][d]["residual_all"]["ci_low"] > 0


def test_a_dispersion_defect_is_named_dispersion():
    out = _run(simulate(extra_var=0.12))
    v = out["verdict"]
    assert v["P1_control_clean"]
    assert v["mechanism"].startswith("DISPERSION"), v
    for d in ("E1", "E2", "E3"):
        assert out["by_division"][d]["dispersion_ratio"]["ci_low"] > 1.0
        # over-dispersion with the mean preserved leaves the residual at zero
        r = out["by_division"][d]["residual_all"]
        assert r["ci_low"] < 0 < r["ci_high"]


def test_a_level_defect_does_not_read_as_dispersion():
    """The statistic that made this necessary: an uncorrected variance ratio
    reads an 8% level shift as ~1.1. Level-corrected, it must sit at 1."""
    out = _run(simulate(level=0.08))
    for d in ("E1", "E2", "E3"):
        r = out["by_division"][d]["dispersion_ratio"]
        assert r["ci_low"] < 1.0 < r["ci_high"], (d, r)
        assert out["by_division"][d]["relative_level"]["ci_low"] > 0.03
