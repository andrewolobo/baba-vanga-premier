"""B12: the blend generalised from one auxiliary channel to k.

Four things have to hold before any number from the channels gate means
anything.

It must reduce to the *shipped* blend exactly at one channel -- not merely
"close" -- because otherwise a measured difference between the shipped head and
a three-channel arm is partly a reimplementation. It must leave the served
config untouched, since `serve.artifact.freeze` hashes `cfg.__dict__` and a
defaulted field there would retire an artifact the documents cite. It must hold
auxiliary dispersion constant as channels are added, or the negative control
differs from the real arm in two ways instead of one. And it must recover a
strength that only the second channel can see -- the P2 lesson, where a null was
interpretable only because an oracle proved the harness could see a real effect.
"""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from engine.eval import walkforward as wf
from engine.eval.walkforward import (ChannelBlendConfig, WalkForwardConfig,
                                     _fit_at, _index)

BASE = ChannelBlendConfig(half_life=400.0, alpha=0.1, cadence="weekly",
                          fit_divisions=("E0",), min_train_matches=50)


def synthetic(n_teams=14, rounds=20, *, corner_signal=0.0, seed=3,
              blind=(), blind_channel="corners") -> pd.DataFrame:
    """A league where corners optionally carry strength nothing else reports.

    `sot` always tracks the same attack strength goals do, so a gain from
    adding `corners` cannot come from the second channel duplicating the first.
    """
    rng = np.random.default_rng(seed)
    teams = [f"T{i:02d}" for i in range(n_teams)]
    att = rng.normal(0, 0.25, n_teams)
    dfn = rng.normal(0, 0.25, n_teams)
    hidden = rng.normal(0, 0.40, n_teams)

    rows, day = [], pd.Timestamp("2018-08-01")
    for _ in range(rounds):
        order = rng.permutation(n_teams)
        for h, a in zip(order[::2], order[1::2]):
            rows.append({
                "match_date": day, "division": "E0",
                "home_team": teams[h], "away_team": teams[a],
                "fthg": rng.poisson(np.exp(0.15 + 0.25 + att[h] + dfn[a])),
                "ftag": rng.poisson(np.exp(0.15 + att[a] + dfn[h])),
                "home_sot": rng.poisson(np.exp(1.5 + 0.25 + att[h] + dfn[a])),
                "away_sot": rng.poisson(np.exp(1.5 + att[a] + dfn[h])),
                "home_corners": rng.poisson(
                    np.exp(1.6 + 0.2 + att[h] + corner_signal * hidden[h] + dfn[a])),
                "away_corners": rng.poisson(
                    np.exp(1.6 + att[a] + corner_signal * hidden[a] + dfn[h])),
            })
            day += pd.Timedelta(days=1)
    frame = pd.DataFrame(rows)
    if blind:
        hit = frame["home_team"].isin(blind) | frame["away_team"].isin(blind)
        frame.loc[hit, [f"home_{blind_channel}", f"away_{blind_channel}"]] = np.nan
    return frame.sort_values("match_date").reset_index(drop=True)


def fit(frame, cfg):
    idx = _index(frame, cfg.fit_divisions, wf._channels_of(cfg))
    model, _ = _fit_at(idx, frame["match_date"].max() + pd.Timedelta(days=1), cfg)
    return idx, model


# --- nesting, and the artifact-hash guard ----------------------------------


def test_one_channel_is_bit_for_bit_the_shipped_blend():
    """The property that makes a k-channel result attributable to the channels.

    `ChannelBlendConfig` at its default channel list must reproduce the plain
    `WalkForwardConfig` exactly, or the comparison between the shipped head and
    a three-channel arm measures a rewrite as well as a feature.
    """
    frame = synthetic(corner_signal=1.0)
    plain = WalkForwardConfig(half_life=400.0, alpha=0.1, cadence="weekly",
                              fit_divisions=("E0",), min_train_matches=50,
                              shots_blend=0.3)
    _, shipped = fit(frame, plain)
    _, generalised = fit(frame, replace(BASE, shots_blend=0.3))
    assert np.array_equal(shipped.att, generalised.att)
    assert np.array_equal(shipped.dfn, generalised.dfn)


def test_the_served_config_carries_no_channel_field():
    """`serve.artifact.freeze` hashes `cfg.__dict__` into the version string, so
    a defaulted field on the served config would retire an artifact whose
    coefficients had not moved. B12 measures on a subclass for that reason."""
    assert "blend_channels" not in WalkForwardConfig().__dict__
    assert "blend_channels" in ChannelBlendConfig().__dict__
    assert wf._channels_of(WalkForwardConfig()) == wf.DEFAULT_BLEND_CHANNELS


def test_a_second_channel_moves_the_fit():
    frame = synthetic(corner_signal=1.0)
    _, one = fit(frame, replace(BASE, shots_blend=0.3))
    _, two = fit(frame, replace(BASE, shots_blend=0.3,
                                blend_channels=("sot", "corners")))
    assert not np.allclose(one.att, two.att)


def test_the_single_channel_term_keeps_the_shipped_association_order():
    """`w*x*s` and `w*(x*s)` differ by one ulp, and the served head must not
    move by even that much -- otherwise the shipped-versus-k-channel comparison
    carries a rewrite as well as a feature.

    Asserted on the expression rather than through a fit. Whether a synthetic
    corpus exposes the difference is luck: it is usually absorbed by the
    `(1-w)·base` term, and an earlier version of this file passed while the
    association was in fact wrong.
    """
    rng = np.random.default_rng(4)
    base = rng.normal(0, 0.25, 40)
    other = rng.normal(0, 3.4, 40)          # a channel on a very different scale
    measured = rng.random(40) > 0.2
    weight = 0.3

    scale = base[measured].std() / other[measured].std()
    shipped = weight * other[measured] * scale
    assert np.array_equal(
        wf.auxiliary_term(base, [other], measured, weight), shipped)
    # The property is only meaningful if the two orders really do differ here.
    assert not np.array_equal(shipped, weight * (other[measured] * scale))


def test_the_multi_channel_term_holds_its_dispersion():
    rng = np.random.default_rng(6)
    base = rng.normal(0, 0.25, 60)
    others = [rng.normal(0, s, 60) for s in (3.4, 0.8, 12.0)]
    measured = rng.random(60) > 0.1
    for k in (1, 2, 3):
        term = wf.auxiliary_term(base, others[:k], measured, 0.5)
        assert (term / 0.5).std() == pytest.approx(base[measured].std(), rel=1e-12)


def test_a_duplicated_channel_changes_nothing():
    """Averaging a channel with itself must be the identity.

    This is the sharp test of the renormalisation: the raw mean of two copies
    of one standardised vector is that vector, so any drift here would be the
    composite silently rescaling the auxiliary contribution.
    """
    frame = synthetic(corner_signal=1.0)
    frame["home_dup"] = frame["home_sot"]
    frame["away_dup"] = frame["away_sot"]
    _, one = fit(frame, replace(BASE, shots_blend=0.45))
    _, doubled = fit(frame, replace(BASE, shots_blend=0.45,
                                    blend_channels=("sot", "dup")))
    assert one.att == pytest.approx(doubled.att, abs=1e-12)
    assert one.dfn == pytest.approx(doubled.dfn, abs=1e-12)


# --- the dispersion invariant ----------------------------------------------


def _composite_of(base_model, arm_model, weight):
    """Recover the blended-in composite from `att* = (1-w)·att + w·C`."""
    return (arm_model.att - (1.0 - weight) * base_model.att) / weight


def test_auxiliary_dispersion_does_not_depend_on_how_many_channels():
    """What makes the noise control a *matched* control.

    Averaging k imperfectly-correlated vectors shrinks the result, and
    shrinkage alone moves deviance. If the composite were not renormalised, a
    three-channel arm and a one-channel arm would differ in auxiliary
    dispersion as well as in information, and `OUTSTANDING.md` 9.6 records a
    control that failed exactly that test.
    """
    frame = synthetic(corner_signal=1.0)
    rng = np.random.default_rng(11)
    frame["home_noise"] = rng.poisson(5.0, len(frame))
    frame["away_noise"] = rng.poisson(5.0, len(frame))

    weight = 0.4
    _, plain = fit(frame, BASE)
    spreads = {}
    for channels in (("sot",), ("sot", "corners"), ("sot", "noise"),
                     ("sot", "corners", "noise")):
        _, arm = fit(frame, replace(BASE, shots_blend=weight,
                                    blend_channels=channels))
        spreads[channels] = _composite_of(plain, arm, weight).std()

    target = plain.att.std()
    for channels, spread in spreads.items():
        assert spread == pytest.approx(target, rel=1e-6), (
            f"{channels} blended in a composite of sd {spread:.6f} against "
            f"{target:.6f} -- the channel count is changing the shrinkage")


# --- the evidence gate ------------------------------------------------------


def test_a_club_missing_any_one_channel_is_left_alone():
    """The National League rule, tightened to the intersection.

    A club measured on sot but not on corners has no corner strength the ridge
    would not invent, so it keeps its goal-fitted strength rather than taking a
    fabricated one into a division we price.
    """
    dark = ("T00", "T01")
    frame = synthetic(corner_signal=1.0, blind=dark, blind_channel="corners")
    idx, plain = fit(frame, BASE)
    _, arm = fit(frame, replace(BASE, shots_blend=0.6,
                                blend_channels=("sot", "corners")))
    for club in dark:
        i = idx.teams.index(club)
        assert plain.att[i] == pytest.approx(arm.att[i]), \
            f"{club} has no corner data and must not be moved"

    seen = [i for i, t in enumerate(idx.teams) if t not in dark]
    assert not np.allclose(plain.att[seen], arm.att[seen])


def test_a_channel_with_no_columns_at_all_is_a_no_op():
    """A requested channel the frame cannot supply leaves the fit alone rather
    than quietly blending the subset that happens to be present."""
    frame = synthetic(corner_signal=1.0)
    _, plain = fit(frame, BASE)
    _, arm = fit(frame, replace(BASE, shots_blend=0.6,
                                blend_channels=("sot", "absent")))
    assert np.array_equal(plain.att, arm.att)


# --- the controls, at unit-test scale --------------------------------------


def test_a_signal_only_the_second_channel_can_see_is_recovered():
    """Convention 8. If the harness cannot see a strength that lives only in
    the corner data, a null from the real arm would mean nothing."""
    rng = np.random.default_rng(9)
    n = 14
    teams = [f"T{i:02d}" for i in range(n)]
    truth = rng.normal(0, 0.45, n)

    rows, day = [], pd.Timestamp("2018-08-01")
    for _ in range(30):
        order = rng.permutation(n)
        for h, a in zip(order[::2], order[1::2]):
            # Goals and sot see the truth heavily diluted; corners see it clearly.
            rows.append({
                "match_date": day, "division": "E0",
                "home_team": teams[h], "away_team": teams[a],
                "fthg": rng.poisson(np.exp(0.2 + 0.2 * truth[h])),
                "ftag": rng.poisson(np.exp(0.1 + 0.2 * truth[a])),
                "home_sot": rng.poisson(np.exp(1.6 + 0.2 * truth[h])),
                "away_sot": rng.poisson(np.exp(1.5 + 0.2 * truth[a])),
                "home_corners": rng.poisson(np.exp(1.7 + truth[h])),
                "away_corners": rng.poisson(np.exp(1.6 + truth[a])),
            })
            day += pd.Timedelta(days=1)
    frame = pd.DataFrame(rows).sort_values("match_date").reset_index(drop=True)

    idx, _ = fit(frame, BASE)
    order = [teams.index(t) for t in idx.teams]
    _, one = fit(frame, replace(BASE, shots_blend=0.7))
    _, two = fit(frame, replace(BASE, shots_blend=0.7,
                                blend_channels=("sot", "corners")))

    r_one = np.corrcoef(one.att, truth[order])[0, 1]
    r_two = np.corrcoef(two.att, truth[order])[0, 1]
    assert r_two > r_one + 0.05, (
        f"the corner channel added nothing (sot only {r_one:.3f}, "
        f"sot+corners {r_two:.3f})")


def test_an_uninformative_second_channel_does_not_help():
    """The mirror of the test above, and the one the gate's negative control
    scales up. A channel carrying no information must not improve recovery
    just by being averaged in."""
    frame = synthetic(corner_signal=1.0, seed=17)
    rng = np.random.default_rng(23)
    frame["home_noise"] = rng.poisson(5.0, len(frame))
    frame["away_noise"] = rng.poisson(5.0, len(frame))

    idx, plain = fit(frame, BASE)
    _, one = fit(frame, replace(BASE, shots_blend=0.5))
    _, noisy = fit(frame, replace(BASE, shots_blend=0.5,
                                  blend_channels=("sot", "noise")))
    # Against the goal-only fit, which carries the strength both are estimating.
    r_one = np.corrcoef(one.att, plain.att)[0, 1]
    r_noisy = np.corrcoef(noisy.att, plain.att)[0, 1]
    assert r_noisy < r_one, (
        f"diluting sot with noise tracked the goal fit better ({r_noisy:.4f} "
        f"vs {r_one:.4f}), which the composite must not reward")


def test_the_label_records_the_channels():
    arm = replace(BASE, shots_blend=0.3, blend_channels=("sot", "shots", "corners"))
    assert "sot0.3/sot+shots+corners" in arm.label()
    assert replace(BASE, shots_blend=0.3).label() == \
        WalkForwardConfig(half_life=400.0, alpha=0.1, cadence="weekly",
                          fit_divisions=("E0",), min_train_matches=50,
                          shots_blend=0.3).label()
