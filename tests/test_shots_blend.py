"""The shots channel: nesting, evidence gating, and a planted signal.

Three things have to hold before any measurement using this arm means anything.
It must reduce to the frozen head exactly at weight zero, or a measured
difference is a reimplementation rather than a feature. It must refuse to move
a club it cannot measure, because the National League has no shot statistics
from 2016-17 and the ridge would otherwise fabricate a strength that a promoted
club carries into E3. And it must actually move the fit when the shots data
carries something goals do not -- the P2 lesson, where a null was only
interpretable because an oracle proved the harness could see a real effect.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from dataclasses import replace

from engine.eval import walkforward as wf
from engine.eval.walkforward import WalkForwardConfig, _fit_at, _index

BASE = WalkForwardConfig(half_life=400.0, alpha=0.1, cadence="weekly",
                         fit_divisions=("E0",), min_train_matches=50)
RNG = np.random.default_rng(5)


def synthetic(n_teams=14, rounds=12, *, sot_signal=0.0, sot_missing=(),
              seed=3) -> pd.DataFrame:
    """A league where sot optionally carries strength that goals under-report."""
    rng = np.random.default_rng(seed)
    teams = [f"T{i:02d}" for i in range(n_teams)]
    att = rng.normal(0, 0.25, n_teams)
    dfn = rng.normal(0, 0.25, n_teams)
    # The part of strength visible only through shots.
    hidden = rng.normal(0, 0.35, n_teams)

    rows, day = [], pd.Timestamp("2018-08-01")
    for _ in range(rounds):
        order = rng.permutation(n_teams)
        for h, a in zip(order[::2], order[1::2]):
            lam_h = np.exp(0.15 + 0.25 + att[h] + dfn[a])
            lam_a = np.exp(0.15 + att[a] + dfn[h])
            mu_h = np.exp(1.5 + 0.25 + att[h] + sot_signal * hidden[h] + dfn[a])
            mu_a = np.exp(1.5 + att[a] + sot_signal * hidden[a] + dfn[h])
            rows.append({
                "match_date": day, "division": "E0",
                "home_team": teams[h], "away_team": teams[a],
                "fthg": rng.poisson(lam_h), "ftag": rng.poisson(lam_a),
                "home_sot": rng.poisson(mu_h), "away_sot": rng.poisson(mu_a),
            })
            day += pd.Timedelta(days=1)
    frame = pd.DataFrame(rows)
    if sot_missing:
        blind = frame["home_team"].isin(sot_missing) | frame["away_team"].isin(sot_missing)
        frame.loc[blind, ["home_sot", "away_sot"]] = np.nan
    return frame.sort_values("match_date").reset_index(drop=True)


def fit(frame, cfg):
    idx = _index(frame, cfg.fit_divisions)
    model, _ = _fit_at(idx, frame["match_date"].max() + pd.Timedelta(days=1), cfg)
    return idx, model


# --- nesting ---------------------------------------------------------------


def test_weight_zero_is_bit_for_bit_the_frozen_head():
    """The property that makes any measured difference attributable."""
    frame = synthetic(sot_signal=1.0)
    _, plain = fit(frame, BASE)
    _, zero = fit(frame, replace(BASE, shots_blend=0.0))
    assert np.array_equal(plain.att, zero.att)
    assert np.array_equal(plain.dfn, zero.dfn)
    assert plain.intercept == zero.intercept and plain.home == zero.home


def test_none_is_also_the_frozen_head():
    frame = synthetic(sot_signal=1.0)
    _, plain = fit(frame, BASE)
    _, none = fit(frame, replace(BASE, shots_blend=None))
    assert np.array_equal(plain.att, none.att)


def test_a_nonzero_weight_actually_moves_the_fit():
    frame = synthetic(sot_signal=1.0)
    _, plain = fit(frame, BASE)
    _, blended = fit(frame, replace(BASE, shots_blend=0.5))
    assert not np.allclose(plain.att, blended.att)


# --- the evidence gate -----------------------------------------------------


def test_a_club_with_no_shot_data_is_left_alone_not_averaged():
    """The National League case, which is the reason the gate exists.

    A club the shots model cannot see would take `att_s ~ 0` from the ridge.
    That is not 'average', it is invented, and a promoted club would carry it
    into a division we price. Such a club must keep its goal-fitted strength.
    """
    blind = ("T00", "T01")
    frame = synthetic(sot_signal=1.0, sot_missing=blind)
    idx, plain = fit(frame, BASE)
    _, blended = fit(frame, replace(BASE, shots_blend=0.8))

    for club in blind:
        i = idx.teams.index(club)
        assert plain.att[i] == pytest.approx(blended.att[i]), \
            f"{club} has no shot data and must not be moved"

    seen = [i for i, t in enumerate(idx.teams) if t not in blind]
    assert not np.allclose(plain.att[seen], blended.att[seen]), \
        "clubs that DO have shot data should move"


def test_a_frame_without_shot_columns_is_a_no_op():
    frame = synthetic(sot_signal=1.0).drop(columns=["home_sot", "away_sot"])
    _, plain = fit(frame, BASE)
    _, blended = fit(frame, replace(BASE, shots_blend=0.6))
    assert np.array_equal(plain.att, blended.att)


def test_all_shot_data_missing_is_a_no_op():
    frame = synthetic(sot_signal=1.0)
    frame[["home_sot", "away_sot"]] = np.nan
    _, plain = fit(frame, BASE)
    _, blended = fit(frame, replace(BASE, shots_blend=0.6))
    assert np.array_equal(plain.att, blended.att)


# --- the positive control --------------------------------------------------


def test_a_planted_shots_only_signal_is_recovered():
    """P2's lesson. If the harness cannot see a strength that exists only in
    the shot data, a null from the real arm would mean nothing.

    Attack strength is planted so that shots report it and goals do not. The
    blended fit must track the truth better than the goal-only fit.
    """
    rng = np.random.default_rng(9)
    n = 14
    teams = [f"T{i:02d}" for i in range(n)]
    truth = rng.normal(0, 0.45, n)

    rows, day = [], pd.Timestamp("2018-08-01")
    for _ in range(26):
        order = rng.permutation(n)
        for h, a in zip(order[::2], order[1::2]):
            # Goals see the truth heavily diluted; shots see it clearly.
            rows.append({
                "match_date": day, "division": "E0",
                "home_team": teams[h], "away_team": teams[a],
                "fthg": rng.poisson(np.exp(0.2 + 0.2 * truth[h])),
                "ftag": rng.poisson(np.exp(0.1 + 0.2 * truth[a])),
                "home_sot": rng.poisson(np.exp(1.6 + truth[h])),
                "away_sot": rng.poisson(np.exp(1.5 + truth[a])),
            })
            day += pd.Timedelta(days=1)
    frame = pd.DataFrame(rows).sort_values("match_date").reset_index(drop=True)

    idx, plain = fit(frame, BASE)
    _, blended = fit(frame, replace(BASE, shots_blend=0.7))
    order = [teams.index(t) for t in idx.teams]

    r_plain = np.corrcoef(plain.att, truth[order])[0, 1]
    r_blend = np.corrcoef(blended.att, truth[order])[0, 1]
    assert r_blend > r_plain + 0.05, (
        f"blend did not recover the planted signal (plain {r_plain:.3f}, "
        f"blended {r_blend:.3f})")


# --- sides -----------------------------------------------------------------


def test_att_only_leaves_defence_untouched():
    frame = synthetic(sot_signal=1.0)
    _, plain = fit(frame, BASE)
    _, arm = fit(frame, replace(BASE, shots_blend=0.6, shots_blend_sides="att"))
    assert np.array_equal(plain.dfn, arm.dfn)
    assert not np.allclose(plain.att, arm.att)


def test_dfn_only_leaves_attack_untouched():
    frame = synthetic(sot_signal=1.0)
    _, plain = fit(frame, BASE)
    _, arm = fit(frame, replace(BASE, shots_blend=0.6, shots_blend_sides="dfn"))
    assert np.array_equal(plain.att, arm.att)
    assert not np.allclose(plain.dfn, arm.dfn)


def test_the_label_records_the_arm():
    assert "sot0.3" in replace(BASE, shots_blend=0.3).label()
    assert "sot0.3-dfn" in replace(BASE, shots_blend=0.3,
                                   shots_blend_sides="dfn").label()
    assert "sot" not in BASE.label()


def test_the_evidence_floor_is_documented_and_positive():
    assert wf.MIN_SOT_EVIDENCE > 0
