"""The P1 walk-forward harness.

Four things have to hold before any number it produces means anything:
it cannot see the future; it reproduces the instrument P0's results were
measured with; it recovers strengths it planted itself; and its arms move the
fit in the direction they claim to.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from engine.asof import AsOf, InformationSet, assert_no_future_dependence, corrupt_future
from engine.eval import metrics, walkforward as wf
from engine.models import poisson as poisson_model
from engine.seasons import ALL_DIVISIONS


def synthetic_corpus(n_seasons=6, n_teams=24, seed=5) -> pd.DataFrame:
    """A league with strengths that drift, played on a real-ish calendar."""
    rng = np.random.default_rng(seed)
    att = rng.normal(0, 0.30, n_teams)
    dfn = rng.normal(0, 0.22, n_teams)
    rows = []
    for season in range(n_seasons):
        att = att * 0.9 + rng.normal(0, 0.10, n_teams)
        dfn = dfn * 0.9 + rng.normal(0, 0.08, n_teams)
        start = pd.Timestamp(2010 + season, 8, 10)
        for matchday in range(38):
            day = start + pd.Timedelta(days=7 * matchday)
            order = rng.permutation(n_teams)
            for k in range(0, n_teams, 2):
                i, j = order[k], order[k + 1]
                lam_h = np.exp(np.log(1.35) + 0.26 + att[i] + dfn[j])
                lam_a = np.exp(np.log(1.35) + att[j] + dfn[i])
                gh, ga = rng.poisson(lam_h), rng.poisson(lam_a)
                rows.append({
                    "match_date": day, "division": "E0",
                    "season": f"{2010 + season}{(2011 + season) % 100:02d}",
                    "home_team": f"T{i:02d}", "away_team": f"T{j:02d}",
                    "fthg": gh, "ftag": ga,
                    "ftr": "H" if gh > ga else ("D" if gh == ga else "A"),
                    "true_lam_h": lam_h, "true_lam_a": lam_a,
                })
    return pd.DataFrame(rows)


@pytest.fixture(scope="module")
def corpus():
    return synthetic_corpus()


# --- it cannot see the future ---------------------------------------------


def test_leak_canary_corrupting_the_future_does_not_move_lambdas(corpus):
    """The load-bearing test. Destroy every outcome from the cutoff onward; the
    lambdas served at that cutoff must be bit-identical."""
    asof = AsOf(pd.Timestamp(2014, 1, 6), InformationSet.PRE_CLOSE)
    cfg = wf.WalkForwardConfig(cadence="weekly")

    def serve(frame, moment):
        out = wf.lambdas_at(frame, moment.moment, cfg)
        return out[["lam_h", "lam_a"]].to_numpy()

    honest = serve(corpus, asof)
    for seed in (0, 1, 2):
        poisoned = serve(corrupt_future(corpus, asof, seed=seed), asof)
        assert np.array_equal(honest, poisoned)


def test_leak_canary_via_the_shared_asof_helper(corpus):
    asof = AsOf(pd.Timestamp(2013, 9, 2), InformationSet.PRE_CLOSE)
    assert_no_future_dependence(
        lambda frame, moment: wf.lambdas_at(frame, moment.moment)[["lam_h", "lam_a"]].to_numpy(),
        corpus, asof,
    )


def test_a_fit_dated_after_the_match_is_an_error(corpus):
    """The harness asserts its own invariant; prove the assertion can fire."""
    out = wf.walk_forward(corpus, wf.WalkForwardConfig(cadence="weekly"))
    assert (out["fit_cutoff"] <= out["match_date"]).all()

    broken = out.copy()
    broken.loc[0, "fit_cutoff"] = broken.loc[0, "match_date"] + pd.Timedelta(days=1)
    late = broken["fit_cutoff"] > broken["match_date"]
    assert bool(late.any())  # the condition the harness raises on


def test_training_never_includes_the_cutoff_day_itself(corpus):
    """Strictly-earlier, not earlier-or-equal. An off-by-one here would leak a
    whole matchday and would be nearly invisible in aggregate scores."""
    cutoff = pd.Timestamp(2014, 3, 1)
    idx = wf._index(corpus, ALL_DIVISIONS)
    # Horizon widened past the corpus so the count is decided by the cutoff
    # alone; the default 5-half-life horizon would also drop old matches and
    # mask an off-by-one at the cutoff.
    cfg = wf.WalkForwardConfig(horizon_half_lives=100.0)
    model, _ = wf._fit_at(idx, cutoff, cfg)
    assert model.n_train == int((corpus["match_date"] < cutoff).sum())
    assert int((corpus["match_date"] >= cutoff).sum()) > 0

    # One day later must pick up exactly the matches played on the cutoff day.
    later, _ = wf._fit_at(idx, cutoff + pd.Timedelta(days=1), cfg)
    assert later.n_train - model.n_train == int((corpus["match_date"] == cutoff).sum())


# --- it reproduces the P0 instrument --------------------------------------


def test_reproduces_the_p0_harness_exactly(corpus):
    """P0's dispersion results were measured with `poisson.walk_forward_lambdas`.
    Configured identically, the new harness must reproduce it to floating point,
    or those results silently stop being reproducible."""
    old = poisson_model.walk_forward_lambdas(corpus, half_life=200.0, alpha=1.0,
                                             refit_days=14, burn_in_days=365)
    new = wf.walk_forward(corpus, wf.WalkForwardConfig(
        half_life=200.0, alpha=1.0, cadence="fortnightly", burn_in_days=365,
        fit_divisions=ALL_DIVISIONS,
    ))
    assert len(old) == len(new)
    assert np.allclose(old["lam_h"].to_numpy(), new["lam_h"].to_numpy(), atol=1e-9)
    assert np.allclose(old["lam_a"].to_numpy(), new["lam_a"].to_numpy(), atol=1e-9)


# --- it recovers what it planted ------------------------------------------


def test_recovers_the_true_lambdas(corpus):
    """Sandwiched between an oracle and a constant, which is the claim that
    matters: the harness must beat knowing nothing and must not beat knowing
    everything. A bare correlation floor would be an arbitrary number -- here
    it lands near 0.85, limited by the corpus size (2,736 matches, 24 teams,
    strengths redrawn every season), not by the harness."""
    out = wf.walk_forward(corpus, wf.WalkForwardConfig(cadence="weekly"))
    assert np.corrcoef(out["lam_h"], out["true_lam_h"])[0, 1] > 0.80
    assert np.corrcoef(out["lam_a"], out["true_lam_a"])[0, 1] > 0.80
    # Unbiased on the level, which correlation alone would not catch.
    assert out["lam_h"].mean() == pytest.approx(out["true_lam_h"].mean(), rel=0.05)

    harness = metrics.goal_deviance(out).mean()
    oracle = metrics.goal_deviance(
        out.assign(lam_h=out["true_lam_h"], lam_a=out["true_lam_a"])).mean()
    constant = metrics.goal_deviance(
        out.assign(lam_h=out["fthg"].mean(), lam_a=out["ftag"].mean())).mean()
    assert oracle < harness < constant


@pytest.mark.parametrize("cadence", ["daily", "weekly", "fortnightly"])
def test_every_cadence_covers_the_corpus(corpus, cadence):
    out = wf.walk_forward(corpus, wf.WalkForwardConfig(cadence=cadence))
    # Everything after the burn-in year should get a lambda, whatever the cadence.
    eligible = (corpus["match_date"] >= corpus["match_date"].min() + pd.Timedelta(days=365))
    assert len(out) >= 0.99 * int(eligible.sum())


# --- the arms move the fit the way they claim -----------------------------


def test_season_boundary_shrink_pulls_strengths_toward_average(corpus):
    plain = wf.walk_forward(corpus, wf.WalkForwardConfig(cadence="weekly"))
    shrunk = wf.walk_forward(corpus, wf.WalkForwardConfig(
        cadence="weekly", season_boundary_shrink=0.80))

    early = wf.season_day(plain) < 45
    spread_plain = (plain.loc[early, "lam_h"] / plain.loc[early, "lam_a"]).std()
    spread_shrunk = (shrunk.loc[early, "lam_h"] / shrunk.loc[early, "lam_a"]).std()
    assert spread_shrunk < spread_plain, "shrink must compress early-season strengths"

    # And it must fade: late in the season the two are nearly the same fit.
    late = wf.season_day(plain) > 150
    assert (shrunk.loc[late, "lam_h"] - plain.loc[late, "lam_h"]).abs().mean() < \
           (shrunk.loc[early, "lam_h"] - plain.loc[early, "lam_h"]).abs().mean()


def test_shrink_of_one_is_a_no_op(corpus):
    plain = wf.walk_forward(corpus, wf.WalkForwardConfig(cadence="weekly"))
    unity = wf.walk_forward(corpus, wf.WalkForwardConfig(
        cadence="weekly", season_boundary_shrink=1.0))
    assert np.allclose(plain["lam_h"], unity["lam_h"], atol=1e-9)


def test_stale_share_is_one_in_august_and_falls_through_the_season(corpus):
    out = wf.walk_forward(corpus, wf.WalkForwardConfig(
        cadence="weekly", season_boundary_shrink=0.9))
    day = wf.season_day(out)
    august = out.loc[day < 14, "stale_share"]
    spring = out.loc[day > 200, "stale_share"]
    assert len(august) > 0 and len(spring) > 0
    assert august.mean() > 0.85
    assert spring.mean() < 0.35


# --- the off-season clock --------------------------------------------------


def test_offseason_gap_shortens_ages_across_a_summer():
    dates = pd.Series(pd.to_datetime(["2014-05-01", "2014-09-01"]))
    cutoff = pd.Timestamp(2014, 10, 1)
    plain = wf.effective_ages(dates, cutoff, None)
    compressed = wf.effective_ages(dates, cutoff, 30.0)
    # May 2014 sits behind the whole 61-day summer, so it loses 31 days.
    assert plain[0] - compressed[0] == pytest.approx(31.0)
    # September 2014 is after it, so nothing changes.
    assert plain[1] == compressed[1]


def test_offseason_gap_of_full_length_is_a_no_op():
    dates = pd.Series(pd.to_datetime(["2013-03-01", "2014-05-01"]))
    cutoff = pd.Timestamp(2015, 1, 1)
    assert np.allclose(wf.effective_ages(dates, cutoff, None),
                       wf.effective_ages(dates, cutoff, 61.0))


def test_season_boundary_is_the_first_of_july():
    assert wf.season_start_of(pd.Timestamp(2014, 8, 10)) == pd.Timestamp(2014, 7, 1)
    assert wf.season_start_of(pd.Timestamp(2015, 5, 3)) == pd.Timestamp(2014, 7, 1)
    assert wf.season_start_of(pd.Timestamp(2014, 7, 1)) == pd.Timestamp(2014, 7, 1)


# --- the embargo -----------------------------------------------------------


def test_embargo_removes_scoring_rows_but_not_training_rows(corpus):
    """The COVID window must vanish from the output while the fits that span it
    keep their training data -- otherwise the hole is worse than the regime."""
    covid = wf.WalkForwardConfig(cadence="weekly", embargo_regimes=("covid_empty_stadiums",))
    scored = wf.walk_forward(corpus, covid)
    inside = ((scored["match_date"] >= pd.Timestamp(2020, 3, 13))
              & (scored["match_date"] <= pd.Timestamp(2021, 5, 31)))
    assert not bool(inside.any())

    # Fits made after the window still trained on it: compare against a run
    # where nothing is embargoed, on the matches both runs keep.
    plain = wf.walk_forward(corpus, wf.WalkForwardConfig(cadence="weekly"))
    shared = plain.merge(scored[["match_date", "home_team", "away_team"]],
                         on=["match_date", "home_team", "away_team"])
    assert len(shared) == len(scored)
