"""P7 harness on planted data: the pieces have to see what they are for.

None of this reads the corpus. Lambdas and outcomes are simulated so each
instrument can be pointed at a known answer -- an honest head must read as
calibrated, a jittered one must read as over-confident, a union's price must
be the union's price, and Part C must never touch an outcome column.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from engine.eval import p7, selection

RNG = np.random.default_rng(3)


def simulate(n: int = 6000, *, lam_noise: float = 0.0, seed: int = 3) -> pd.DataFrame:
    """Matches whose outcomes are drawn from the very lambdas the head reports.
    `lam_noise` > 0 makes the head report *jittered* lambdas while the truth
    stays put -- a deliberately over-confident head."""
    rng = np.random.default_rng(seed)
    lam_h = np.exp(rng.normal(np.log(1.45), 0.35, n))
    lam_a = np.exp(rng.normal(np.log(1.15), 0.35, n))
    fthg = rng.poisson(lam_h)
    ftag = rng.poisson(lam_a)
    ftr = np.where(fthg > ftag, "H", np.where(fthg < ftag, "A", "D"))
    reported_h = lam_h * np.exp(rng.normal(0, lam_noise, n))
    reported_a = lam_a * np.exp(rng.normal(0, lam_noise, n))
    dates = pd.Timestamp("2015-08-01") + pd.to_timedelta(rng.integers(0, 3 * 365, n), "D")
    # Prices from the truth with a 5% overround, so the market "knows".
    joint = p7.score_matrix(lam_h, lam_a)
    truth = np.column_stack(p7.outcome_probs(joint))
    fair = 1.0 / truth
    frame = pd.DataFrame({
        "lam_h": reported_h, "lam_a": reported_a, "fthg": fthg, "ftag": ftag,
        "ftr": ftr, "match_date": dates,
        "season": np.where(dates < pd.Timestamp("2016-07-01"), "201516",
                           np.where(dates < pd.Timestamp("2017-07-01"), "201617", "201718")),
        "division": rng.choice(["E0", "E1", "E2", "E3"], n),
    })
    for i, side in enumerate("hda"):
        frame[f"avg_{side}"] = fair[:, i] / 1.05
        frame[f"max_{side}"] = fair[:, i] / 1.02
    return frame


def test_a_calibrated_head_reads_as_calibrated_at_every_line():
    """Thirty 95% intervals on a head that IS the truth: a couple miss by
    chance, none by much. The instrument must not call an honest head
    dishonest more often than its own interval promises."""
    frame = simulate(n=12000)
    joint = p7.joint_of(frame)
    verdicts, big_gaps = [], []
    for line in p7.LINES:
        for r in p7.line_table(frame, joint, line):
            if r["n"] >= p7.MIN_BUCKET:
                verdicts.append(r["verdict"])
            if r["n"] >= 1000:
                big_gaps.append(abs(r["gap"]))
    assert len(verdicts) >= 20
    assert sum(v != "calibrated" for v in verdicts) <= 3, verdicts
    assert max(big_gaps) < 0.025


def test_a_jittered_head_is_caught_by_the_control():
    """The control has to see the defect it exists to find, on planted data,
    before it is trusted on the corpus."""
    frame = simulate(lam_noise=0.35)
    control = p7.part_b_control(frame)
    # `part_b_control` jitters again on top; either way the table must say so.
    assert control["passes"]


def test_the_drop_rule_fires_only_on_a_resolved_over_claim():
    frame = simulate(n=8000)
    joint = p7.joint_of(frame)
    honest = p7.part_b(frame, joint)
    assert honest["dropped"] == []


def test_the_recommended_market_gets_the_union_price():
    prices = np.array([[2.0, 3.0, 6.0]])
    assert p7._price_of(np.array(["H"]), prices)[0] == pytest.approx(2.0)
    assert p7._price_of(np.array(["1X"]), prices)[0] == pytest.approx(1 / (1 / 2 + 1 / 3))
    assert p7._price_of(np.array(["12"]), prices)[0] == pytest.approx(1 / (1 / 2 + 1 / 6))


def test_part_a_return_against_a_fair_market_is_the_overround():
    """When the head IS the truth and prices carry a 5% overround, the return
    at avg prices must be about -5%, and the model cannot beat the market
    rule because they are the same rule on the same numbers."""
    frame = simulate(n=12000)
    probs = p7.probs_1x2(p7.joint_of(frame))
    out = p7.part_a(frame, probs)
    shipped = next(r for r in out["rows"] if r["floor"] == p7.SHIPPED_FLOOR)
    assert -0.09 < shipped["roi_avg"]["roi"] < -0.01
    assert not shipped["roi_avg"]["resolved_positive"]
    assert abs(shipped["vs_market_rule"]["delta"]) < 0.01
    assert shipped["vs_market_rule"]["agree_share"] > 0.9


def test_part_c_reads_no_outcome():
    """Part C is a probe by construction: strip every outcome column and it
    must still run. If it ever needed one, its ledger accounting would be a lie."""
    frame = simulate(n=3000).drop(columns=["fthg", "ftag", "ftr"])
    joint = p7.joint_of(frame)
    probs = p7.probs_1x2(joint)
    out = p7.part_c(frame, joint, probs)
    assert set(out["ceilings"]) == {str(c) for c in p7.CEILINGS}
    for row in out["ceilings"].values():
        assert 0.0 <= row["C1"]["fire_rate"] <= 1.0
        assert row["C2"]["coverage"] > 0.9


def test_best_line_respects_the_ceiling():
    frame = simulate(n=2000)
    joint = p7.joint_of(frame)
    label, p = p7._best_line(joint, 0.80)
    assert np.all(p[np.isfinite(p)] <= 0.80)
    assert set(np.unique(label[label != ""])) <= {
        f"{s}{l}" for l in p7.LINES for s in "OU"}


def test_c3_is_the_ceiling_as_selector_on_the_fallback_only():
    """C3 may only ever change a match that reached the fallback; a confident
    outright must survive it untouched."""
    frame = simulate(n=3000)
    joint = p7.joint_of(frame)
    probs = p7.probs_1x2(joint)
    out = p7.part_c(frame, joint, probs)
    v2, _ = selection.recommend(probs, p7.SHIPPED_FLOOR, 0.85)
    outright_share = float(np.isin(v2, ["H", "A"]).mean())
    strong = float((np.maximum(probs[:, 0], probs[:, 2]) >= p7.SHIPPED_FLOOR).mean())
    assert out["ceilings"]["0.85"]["C3"]["team_named_share"] >= strong - 1e-9
    assert out["ceilings"]["0.85"]["C3"]["team_named_share"] <= outright_share + 1e-9
