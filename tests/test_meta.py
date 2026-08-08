"""The P5 grounding, checked against planted answers.

Three of these guard claims `P5_META_PLAN.md` §1 makes as arithmetic rather than
as measurement, which is exactly the kind that gets reimplemented wrongly and
still looks plausible:

  §1.4  the three legs of a match sum to minus the Max overround. This holds
        only because the bet side is raw `1/odds` and the close side is
        normalised. Swap either and the identity breaks -- and OUTSTANDING §7.4
        records that confusion as a shipped bug worth five points a side.
  §1.5  blocking *tightens* the interval, a design effect below 1. That is the
        finding that inverted the plan's prior about power, so it is asserted
        as a property of anti-correlated legs rather than left as a number.
  §1    the document's published values. A grounding that recomputes without
        checking is what `CHANNELS.md` §7 already has one of.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from engine.eval import meta
from engine.odds import overround


def basis(n: int = 400, seed: int = 7, margin: float = 0.006) -> pd.DataFrame:
    """Matches carrying a closing Pinnacle price and a Max price to bet at.

    The Max book is built from a true probability vector inflated by `margin`,
    so the overround is known exactly and §1.4's identity has something to be
    checked against.
    """
    rng = np.random.default_rng(seed)
    p = rng.dirichlet([6.0, 4.0, 5.0], n)
    close = rng.dirichlet([6.0, 4.0, 5.0], n)     # a different, unrelated close
    max_prices = 1.0 / (p * (1.0 + margin))
    close_prices = 1.0 / (close * 1.03)           # any overround; de-vigged away

    days = pd.Timestamp("2015-08-08") + pd.to_timedelta(
        rng.integers(0, 700, n), unit="D")
    frame = pd.DataFrame({
        "match_date": days,
        "season": "201516",
        "division": rng.choice(["E0", "E1"], n),
    })
    for i, col in enumerate(meta.PRICE_1X2):
        frame[col] = max_prices[:, i]
    for i, col in enumerate(meta.CLOSE_1X2):
        frame[col] = close_prices[:, i]
    return frame


# --- the outcome guard -----------------------------------------------------


def test_drop_outcomes_removes_every_post_kickoff_column():
    frame = pd.DataFrame({"match_date": [1], "max_h": [2.0], "fthg": [1],
                          "ftag": [0], "ftr": ["H"], "home_sot": [4]})
    out = meta.drop_outcomes(frame)

    assert set(out.columns) == {"match_date", "max_h"}


def test_the_outcome_list_covers_every_post_kickoff_column_in_the_schema():
    """The drop is only as good as the list. Anything the store carries that is
    knowable only after kickoff must be named, or it silently stays available
    to a later edit."""
    from engine.ingest.build import MATCH_COLUMNS
    from engine.odds import ODDS_FIELDS

    known_safe = {"match_id", "season", "division", "match_date", "kickoff_time",
                  "home_team_id", "away_team_id", "odds_era", "source_file"}
    post_kickoff = set(MATCH_COLUMNS) - known_safe - set(ODDS_FIELDS)

    assert post_kickoff <= set(meta.OUTCOME_COLUMNS)


# --- §1.4: the identity that makes ranking the only product ---------------


@pytest.mark.parametrize("margin", [0.0, 0.006, 0.02, 0.06])
def test_three_legs_sum_to_minus_the_max_overround(margin):
    """§1.4's 'by construction'. The closing prices are unrelated to the Max
    book here, so if this held for a reason other than the arithmetic it would
    not survive changing the margin."""
    frame = basis(margin=margin)
    clv, _ = meta.clv_legs(frame)

    expected = -(overround(*[frame[c].to_numpy() for c in meta.PRICE_1X2]) - 1.0)
    assert clv.sum(axis=1) == pytest.approx(expected, abs=1e-12)
    assert clv.mean() == pytest.approx(expected.mean() / 3.0, abs=1e-12)


def test_the_identity_breaks_if_the_bet_side_is_de_vigged():
    """The bug OUTSTANDING §7.4 forbids, made visible. De-vigging the price
    taken pins every match at exactly zero, which would read as 'no vig to
    beat' and quietly delete the bar the whole gate is measured against."""
    from engine.odds import devig_probs

    frame = basis(margin=0.02)
    close = np.column_stack(devig_probs(*[frame[c].to_numpy() for c in meta.CLOSE_1X2]))
    wrong = np.column_stack(devig_probs(*[frame[c].to_numpy() for c in meta.PRICE_1X2]))

    assert (close - wrong).sum(axis=1) == pytest.approx(0.0, abs=1e-12)
    assert meta.clv_legs(frame)[0].sum(axis=1).mean() < -0.01


# --- the basis ------------------------------------------------------------


def test_a_row_needs_both_a_close_and_a_price_to_be_gradable():
    frame = basis(n=10)
    frame.loc[0, "close_ps_h"] = np.nan     # close missing: nothing to grade against
    frame.loc[1, "max_d"] = np.nan          # price missing: nothing was bettable

    assert len(meta.clv_basis(frame)) == 8


# --- §1.5: blocking tightens, and why -------------------------------------


def test_blocking_tightens_because_the_legs_of_a_match_cancel():
    """The design effect below 1 is not a quirk of the corpus -- it follows from
    the legs of a match summing to a near-constant. Asserted both ways: with the
    cancellation available it must tighten, and with one leg per match, which is
    what a real selection takes, it must not."""
    out = meta.g5_power(basis(n=1500, seed=3))

    assert out["design_effect"] < 0.9, "anti-correlated legs must tighten the SE"
    assert out["one_leg_design_effect"] == pytest.approx(1.0, abs=0.15), (
        "one leg per match has no within-match cancellation to exploit")


def test_strata_half_widths_scale_as_one_over_root_n():
    out = meta.g5_power(basis(n=1500, seed=3))
    rows = {r["fraction"]: r["half_width"] for r in out["strata"]}

    assert rows[0.25] == pytest.approx(2.0 * rows[1.00], rel=1e-6)
    assert rows[0.05] == pytest.approx(rows[1.00] / np.sqrt(0.05), rel=1e-6)


# --- the reproduction check itself ----------------------------------------


def results_matching_published() -> dict:
    """A results dict carrying exactly what the document publishes."""
    p = {k: v for k, (v, _) in meta.PUBLISHED.items()}
    return {
        "g2": {"matches_1x2": p["g2.matches_1x2"], "legs_1x2": p["g2.legs_1x2"],
               "matches_ou": p["g2.matches_ou"], "legs_ou": p["g2.legs_ou"]},
        "g3": {k.split(".")[1]: p[k] for k in p if k.startswith("g3.")},
        "g4": {k.split(".")[1]: p[k] for k in p if k.startswith("g4.")},
        "g5": {k.split(".")[1]: p[k] for k in p if k.startswith("g5.")},
        "g6": {"coverage": {"ps": p["g6.coverage_ps"],
                            "kickoff": p["g6.coverage_kickoff"]}},
    }


def test_the_check_passes_when_the_document_is_right():
    out = meta.check_published(results_matching_published())

    assert out["all_reproduce"]
    assert len(out["rows"]) == len(meta.PUBLISHED)


# --- the arms --------------------------------------------------------------


def legs(n_weeks: int = 60, per_week: int = 40, seed: int = 4) -> pd.DataFrame:
    """A leg frame with the columns the arms need and no signal in any of them."""
    rng = np.random.default_rng(seed)
    n = n_weeks * per_week
    week = np.repeat(np.arange(n_weeks), per_week)
    start = pd.Timestamp("2014-08-09")
    frame = pd.DataFrame({
        "week": week,
        "match_date": start + pd.to_timedelta(week * 7, unit="D"),
        "match_id": np.arange(n) // 3,
        "division": rng.choice(list(meta.SERVED_DIVISIONS), n),
        "side": np.tile(["H", "D", "A"], n // 3 + 1)[:n],
        "clv": rng.normal(-0.00192, 0.0222, n),
    })
    frame["season"] = np.where(frame.week < n_weeks // 3, "201415",
                               np.where(frame.week < 2 * n_weeks // 3,
                                        "201516", "201617"))
    frame["is_draw"] = (frame.side == "D").astype(float)
    frame["is_away"] = (frame.side == "A").astype(float)
    for name in meta.BOOK_FEATURES + meta.MODEL_FEATURES + meta.CONTEXT_FEATURES:
        frame[name] = rng.normal(size=n)
    return meta.noise_block(frame)


def test_a_fit_cannot_see_its_own_week_or_any_later_one():
    """The property the whole harness depends on. Asserted by corrupting the
    future: if predictions for early weeks move when late targets are replaced,
    the walk-forward is reading forward and every number downstream is void."""
    frame = legs()
    features = meta.SHARED + meta.BOOK_FEATURES
    target = frame.clv.to_numpy()

    before = meta.walk_forward_predict(frame, features, target)

    cutoff = 45
    poisoned = target.copy()
    poisoned[frame.week.to_numpy() >= cutoff] += 100.0
    after = meta.walk_forward_predict(frame, features, poisoned)

    early = frame.week.to_numpy() < cutoff
    assert np.allclose(before[early], after[early], equal_nan=True), (
        "predictions before the cutoff moved when only later targets changed")
    assert not np.allclose(before[~early], after[~early], equal_nan=True), (
        "the poison must land somewhere, or the test proves nothing")


def test_the_first_seasons_are_never_scored():
    """MIN_TRAIN_SEASONS of history before the first fit, so early weeks have
    no prediction at all rather than one from a single season's price regime."""
    frame = legs()
    pred = meta.walk_forward_predict(frame, meta.SHARED + meta.BOOK_FEATURES,
                                     frame.clv.to_numpy())

    scored_seasons = set(frame.season[np.isfinite(pred)])
    assert scored_seasons == {"201617"}, scored_seasons


def test_full_is_rank_deficient_but_its_predictions_are_not():
    """`edge = m_prob - be_max`, so BOOK u MODEL carries an exact linear
    dependence. lstsq's pseudo-inverse must give the same fitted values as the
    de-duplicated feature set, or FULL's ranking is arbitrary."""
    frame = legs()
    frame["edge"] = frame.m_prob - frame.be_max
    target = frame.clv.to_numpy()

    full = meta.walk_forward_predict(frame, meta.FEATURE_SETS["FULL"], target)
    deduped = tuple(f for f in meta.FEATURE_SETS["FULL"] if f != "edge")
    without = meta.walk_forward_predict(frame, deduped, target)

    assert np.allclose(full, without, equal_nan=True, atol=1e-9)


def test_selection_takes_the_top_fraction_of_every_week():
    frame = legs(n_weeks=6, per_week=100)
    frame["_scored"] = True
    prediction = np.arange(len(frame), dtype=float)

    chosen = meta.select(frame, prediction, 0.10)

    counts = frame.assign(c=chosen).groupby("week").c.sum()
    assert set(counts) == {10}
    # Highest predictions only, and within each week rather than pooled.
    assert frame.assign(c=chosen).groupby("week").apply(
        lambda g: bool(g.c.to_numpy()[-10:].all()), include_groups=False).all()


def test_leg_values_average_to_the_mean_clv_on_the_selection():
    """The estimator that makes two arms comparable: a per-leg quantity defined
    on every scored leg whose mean is the selected-volume mean."""
    frame = legs(n_weeks=6, per_week=100)
    frame["_scored"] = True
    target = frame.clv.to_numpy()
    chosen = meta.select(frame, np.arange(len(frame), dtype=float), 0.10)

    values = meta.leg_values(frame, chosen, target, 0.10)

    assert np.nanmean(values) == pytest.approx(target[chosen].mean(), rel=1e-9)


def test_the_noise_block_matches_model_dimensionality_and_carries_nothing():
    frame = legs()

    assert len(meta.NOISE_FEATURES) == len(meta.MODEL_FEATURES)
    for name in meta.NOISE_FEATURES:
        r = np.corrcoef(frame[name], frame.clv)[0, 1]
        assert abs(r) < 0.05, f"{name} correlates with the target at {r:+.3f}"


def test_an_arm_given_the_target_beats_one_given_noise():
    """The instrument must be able to rank at all. Without this, MODEL losing to
    BOOK could mean the pipeline never ranks anything."""
    frame = legs()
    frame["be_max"] = frame.clv + np.random.default_rng(0).normal(0, 0.001, len(frame))
    target = frame.clv.to_numpy()

    oracle = meta.score_arm(frame, meta.SHARED + ("be_max",), target)
    blind = meta.score_arm(frame, meta.SHARED + meta.NOISE_FEATURES, target)

    assert oracle["mean_clv_selected"] > blind["mean_clv_selected"] + 0.01


def test_the_check_catches_a_number_that_has_drifted():
    """Without this the harness recomputes without confirming, which is the
    state `CHANNELS.md` §7 records for row 53."""
    results = results_matching_published()
    results["g5"]["sd_clv"] += 0.001

    out = meta.check_published(results)

    assert not out["all_reproduce"]
    assert out["failed"] == ["g5.sd_clv"]
