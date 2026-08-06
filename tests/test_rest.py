"""Rest-day construction and the rest arm, checked against planted answers.

`attach_rest` is the part most likely to be wrong in a way no summary statistic
would reveal: it has to look back per club per season across a frame that holds
both sides of every fixture, and an off-by-one there would shift every band
without changing a single row count -- which `MEMORY` and OUTSTANDING §7.6 both
warn is exactly how the defects on this corpus have presented.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from engine.eval import metrics, rest


def fixtures(rows) -> pd.DataFrame:
    """rows: (season, date, home, away)."""
    f = pd.DataFrame(rows, columns=["season", "match_date", "home_team",
                                    "away_team"])
    f["match_date"] = pd.to_datetime(f.match_date)
    f["match_id"] = range(len(f))
    return f


# --- the rest calculation --------------------------------------------------


def test_rest_counts_days_since_that_club_last_played():
    f = fixtures([
        ("2122", "2021-08-07", "Arsenal", "Brentford"),
        ("2122", "2021-08-14", "Arsenal", "Chelsea"),      # 7 days
        ("2122", "2021-08-17", "Brentford", "Arsenal"),    # Arsenal 3, Brent 10
    ])
    out = rest.attach_rest(f).set_index("match_id")

    assert pd.isna(out.loc[0, "rest_home"]), "no previous match to count from"
    assert out.loc[1, "rest_home"] == 7
    assert out.loc[2, "rest_away"] == 3, "Arsenal played 3 days earlier"
    assert out.loc[2, "rest_home"] == 10, "Brentford played 10 days earlier"


def test_rest_is_counted_per_club_not_per_fixture():
    """Two clubs in the same match usually have different rest; if the lookup
    were per fixture rather than per club they would always agree."""
    f = fixtures([
        ("2122", "2021-08-07", "Arsenal", "Brentford"),
        ("2122", "2021-08-10", "Chelsea", "Arsenal"),
        ("2122", "2021-08-14", "Arsenal", "Brentford"),
    ])
    out = rest.attach_rest(f).set_index("match_id")

    assert out.loc[2, "rest_home"] == 4    # Arsenal last played 10 Aug
    assert out.loc[2, "rest_away"] == 7    # Brentford last played 7 Aug


def test_rest_does_not_reach_across_a_season_boundary():
    """A summer gap is not rest, it is a new squad."""
    f = fixtures([
        ("2122", "2022-05-22", "Arsenal", "Everton"),
        ("2223", "2022-08-06", "Arsenal", "Leeds"),
    ])
    out = rest.attach_rest(f).set_index("match_id")

    assert pd.isna(out.loc[1, "rest_home"]), "first match of a season has no rest"


@pytest.mark.parametrize("days,expected", [
    (2, "<=3"), (3, "<=3"), (4, "4"), (5, "5-6"), (6, "5-6"),
    (7, "7"), (9, "8-11"), (11, "8-11"), (12, ">=12"), (30, ">=12"),
])
def test_bands_split_where_intended(days, expected):
    assert rest.bands(pd.Series([days]))[0] == expected


# --- the arm ---------------------------------------------------------------


def frame(n: int = 3000, seed: int = 5) -> pd.DataFrame:
    """Matches whose lambda is independent of either side's rest."""
    rng = np.random.default_rng(seed)
    days = pd.Timestamp("2015-08-08") + pd.to_timedelta(
        rng.integers(0, 900, n), unit="D")
    f = pd.DataFrame({
        "match_date": days,
        "season": np.where(days < pd.Timestamp("2016-06-01"), "201516", "201617"),
        "lam_h": rng.uniform(0.8, 2.2, n),
        "lam_a": rng.uniform(0.6, 1.8, n),
        "rest_home": rng.choice([3, 4, 7, 14], n),
        "rest_away": rng.choice([3, 4, 7, 14], n),
    })
    f["band_h"] = rest.bands(f.rest_home)
    f["band_a"] = rest.bands(f.rest_away)
    f["diff"] = f.rest_home - f.rest_away
    f["fthg"] = rng.poisson(f.lam_h)
    f["ftag"] = rng.poisson(f.lam_a)
    return f


def test_a_flat_corpus_leaves_lambda_essentially_untouched():
    """With no rest effect the fitted factors sit near 1, so the arm must not
    move lambda much. Without this, a null could be an arm that does nothing.

    Asserted on the aggregate and the worst single factor rather than every
    element: with two seasons behind each fit the individual band factors carry
    real sampling noise, and demanding they all land within a few percent would
    be testing the random seed."""
    f = frame(n=12000, seed=11)
    lam_h, lam_a = rest.band_arm(f)

    assert lam_h.mean() == pytest.approx(f.lam_h.mean(), rel=0.02)
    assert lam_a.mean() == pytest.approx(f.lam_a.mean(), rel=0.02)
    assert np.abs(lam_h / f.lam_h.to_numpy() - 1.0).max() < 0.10


def test_each_side_is_scaled_by_its_own_rest_not_its_opponents():
    """The whole hypothesis is that a tired team plays worse, so the home
    lambda must respond to the home band. Crossing the two would still produce
    a plausible-looking null."""
    f = frame()
    f.loc[:, "rest_home"] = 3
    f.loc[:, "rest_away"] = 7
    f["band_h"] = rest.bands(f.rest_home)
    f["band_a"] = rest.bands(f.rest_away)
    # A real deficit for the home side only.
    rng = np.random.default_rng(1)
    f["fthg"] = rng.poisson(f.lam_h * 0.6)
    f["ftag"] = rng.poisson(f.lam_a)

    lam_h, lam_a = rest.band_arm(f)

    assert lam_h.mean() < f.lam_h.mean() * 0.8, "home lambda should be pulled down"
    assert np.allclose(lam_a, f.lam_a, rtol=0.05), "away lambda should not move"


def test_a_planted_rest_deficit_is_recovered_and_grows_with_its_size():
    """The monotonicity H33 reads its bound off. If a larger planted deficit
    did not come back larger, "a 5% effect would have been caught" would be
    unsupported and the null would carry no bound at all."""
    f = frame(n=8000, seed=2)
    deltas = []
    for scale in (0.0, 2.0, 4.0):
        rng = np.random.default_rng(3)
        factors = {k: 1.0 + v * scale for k, v in rest.PLANTED.items()}
        work = f.copy()
        mh = work.band_h.map(factors).astype(float).fillna(1.0).to_numpy()
        ma = work.band_a.map(factors).astype(float).fillna(1.0).to_numpy()
        work["fthg"] = rng.poisson(work.lam_h.to_numpy(float) * mh)
        work["ftag"] = rng.poisson(work.lam_a.to_numpy(float) * ma)

        base = metrics.goal_deviance(work)
        lam_h, lam_a = rest.band_arm(work)
        arm = metrics.goal_deviance(pd.DataFrame({
            "lam_h": lam_h, "lam_a": lam_a,
            "fthg": work.fthg, "ftag": work.ftag}))
        deltas.append(float(arm.mean() - base.mean()))

    assert deltas[2] < deltas[1] < 0, "a bigger planted deficit must come back bigger"
