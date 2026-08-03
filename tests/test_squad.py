"""The squad prior: nesting, as-of correctness, and a planted prior recovered.

Three things have to hold before any P2 number means anything.

* **The arm must nest its baseline.** At weight 0 the fit has to be bit-for-bit
  the pre-P2 one, not approximately it. A sweep whose zero-arm drifts is
  measuring the drift.
* **The prior must not read the future.** Season N's player file is embargoed
  entire (`asof.PLAYER_SEASON_RULE`), and the coefficient map may only be
  fitted on seasons that have already finished. Both are asserted by corrupting
  the part that must not matter and requiring the output not to move.
* **A real prior must be recovered.** P2's headline is expected to be a null,
  and a null from an instrument that cannot see anything is not a result. So a
  planted prior has to shift the fit in the direction it was planted.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from engine.models import poisson, squad


def _fixtures(n_teams=8, rounds=8, seed=0):
    """A round-robin whose true strengths are known."""
    rng = np.random.default_rng(seed)
    att = np.linspace(0.4, -0.4, n_teams)
    dfn = np.linspace(-0.3, 0.3, n_teams)
    home, away, gh, ga = [], [], [], []
    for _ in range(rounds):
        for i in range(n_teams):
            for j in range(n_teams):
                if i == j:
                    continue
                lam_h = np.exp(0.1 + 0.25 + att[i] + dfn[j])
                lam_a = np.exp(0.1 + att[j] + dfn[i])
                home.append(i)
                away.append(j)
                gh.append(rng.poisson(lam_h))
                ga.append(rng.poisson(lam_a))
    return (np.array(home), np.array(away), np.array(gh), np.array(ga),
            np.ones(len(home)), n_teams, att, dfn)


# --- the fit -------------------------------------------------------------


def test_a_zero_prior_is_bit_for_bit_the_old_fit():
    """The nesting property the whole sweep rests on."""
    h, a, gh, ga, w, n, *_ = _fixtures()
    old = poisson.fit(h, a, gh, ga, w, n, alpha=1.0)
    new = poisson.fit(h, a, gh, ga, w, n, alpha=1.0,
                      prior_att=np.zeros(n), prior_dfn=np.zeros(n))
    assert np.array_equal(old.att, new.att)
    assert np.array_equal(old.dfn, new.dfn)
    assert old.intercept == new.intercept


def test_a_planted_prior_pulls_the_fit_toward_it():
    """With little data and a strong penalty the prior should dominate."""
    h, a, gh, ga, w, n, *_ = _fixtures(rounds=1)
    planted = np.full(n, 0.5)
    free = poisson.fit(h, a, gh, ga, w, n, alpha=50.0)
    pulled = poisson.fit(h, a, gh, ga, w, n, alpha=50.0, prior_att=planted)

    assert pulled.att.mean() > free.att.mean() + 0.2
    assert pulled.att.mean() == pytest.approx(0.5, abs=0.15)
    # Defence was given no prior, so it must stay where it was.
    assert pulled.dfn.mean() == pytest.approx(free.dfn.mean(), abs=0.05)


def test_abundant_evidence_overrules_a_wrong_prior():
    """The property that makes P2 safe to ship even if the prior is bad --
    and, read the other way, the reason it cannot help much here."""
    h, a, gh, ga, w, n, att, _ = _fixtures(rounds=40)
    wrong = -np.asarray(att) * 3.0
    fitted = poisson.fit(h, a, gh, ga, w, n, alpha=0.1, prior_att=wrong)
    honest = poisson.fit(h, a, gh, ga, w, n, alpha=0.1)
    assert np.corrcoef(fitted.att, honest.att)[0, 1] > 0.99
    assert np.abs(fitted.att - honest.att).max() < 0.05


def test_a_mis_sized_prior_is_rejected_rather_than_broadcast():
    h, a, gh, ga, w, n, *_ = _fixtures()
    with pytest.raises(ValueError, match="one entry per team"):
        poisson.fit(h, a, gh, ga, w, n, prior_att=np.zeros(n - 1))


# --- the container -------------------------------------------------------


def test_priors_align_to_the_caller_s_team_order():
    """A positional store would assign one club's prior to another the moment
    the team index changed. It is aligned by name instead."""
    priors = squad.SquadPriors("t", {"201516": {"Arsenal": 1.0, "Bury": -2.0}},
                               {"201516": {"Arsenal": 0.5, "Bury": -0.5}})
    att, dfn = priors.at(pd.Timestamp("2016-01-09"), ("Bury", "Crewe", "Arsenal"))
    assert list(att) == [-2.0, 0.0, 1.0]
    assert list(dfn) == [-0.5, 0.0, 0.5]


def test_an_unknown_season_yields_no_prior_at_all():
    priors = squad.SquadPriors("t", {"201516": {"Arsenal": 1.0}}, {"201516": {"Arsenal": 1.0}})
    assert priors.at(pd.Timestamp("2011-01-09"), ("Arsenal",)) is None


@pytest.mark.parametrize("day,expected", [
    ("2015-08-01", "201516"),   # the boundary itself belongs to the new season
    ("2015-07-31", "201415"),   # July does not: the window is still open
    ("2016-05-30", "201516"),
    ("2016-01-01", "201516"),
])
def test_the_player_boundary_is_1_august_not_1_july(day, expected):
    """Deliberately later than `walkforward.SEASON_BOUNDARY`. That one only has
    to separate matches; this one waits for the transfer window."""
    assert squad.season_at(pd.Timestamp(day)) == expected


# --- as-of correctness ---------------------------------------------------


def _history(seasons=("201213", "201314", "201415", "201516", "201617")):
    rng = np.random.default_rng(3)
    rows = []
    for season in seasons:
        for i in range(20):
            att = rng.normal(0, 0.3)
            rows.append({
                "season": season, "division": "E1", "club": f"club{i}",
                "att_pre": att, "dfn_pre": rng.normal(0, 0.3),
                "att_end": att + rng.normal(0, 0.05),
                "dfn_end": rng.normal(0, 0.3),
                "sq_att": att + rng.normal(0, 0.1), "sq_dfn": rng.normal(0, 0.3),
                "sq_age": rng.normal(26, 2), "sq_churn": rng.uniform(0, 1),
                "sq_ga90": rng.uniform(0, 0.5), "sq_top11": rng.uniform(0.5, 0.9),
            })
    return pd.DataFrame(rows)


def test_the_map_never_sees_the_season_it_is_applied_to():
    """Corrupt every future season's outcome; the prior for the earliest fitted
    season must not move. This is `asof.assert_no_future_dependence` in the
    shape this module needs -- the frame is club-seasons, not matches."""
    history = _history()
    clean = squad.build(history, ("sq_att",), label="t")
    target = min(clean.att)

    poisoned = history.copy()
    later = poisoned["season"] >= target
    rng = np.random.default_rng(11)
    poisoned.loc[later, "att_end"] = rng.normal(0, 5, int(later.sum()))
    poisoned.loc[later, "dfn_end"] = rng.normal(0, 5, int(later.sum()))
    dirty = squad.build(poisoned, ("sq_att",), label="t")

    assert clean.att[target] == pytest.approx(dirty.att[target], abs=1e-12)
    assert clean.dfn[target] == pytest.approx(dirty.dfn[target], abs=1e-12)


def test_no_prior_is_emitted_before_there_is_enough_history():
    history = _history(seasons=("201213", "201314"))
    assert squad.build(history, ("sq_att",), label="t").att == {}


def test_the_roster_is_the_previous_season_never_the_current_one():
    """The rule that makes the whole layer honest: season N's file is embargoed
    entire, so changing it must not change season N's prior."""
    players = pd.DataFrame([
        {"season": "201314", "year": 2013, "club": "A", "player_id": "aaaaaaaa",
         "minutes": 3000, "age": 25, "goals_non_pk": 10, "assists": 5},
        {"season": "201415", "year": 2014, "club": "A", "player_id": "aaaaaaaa",
         "minutes": 3000, "age": 26, "goals_non_pk": 12, "assists": 4},
        {"season": "201516", "year": 2015, "club": "A", "player_id": "zzzzzzzz",
         "minutes": 3000, "age": 19, "goals_non_pk": 40, "assists": 40},
    ])
    att, dfn = {"A": 0.5}, {"A": -0.2}
    levels = squad.player_levels(players, 2015, att, dfn)
    before = squad.club_channels(players, 2015, levels)

    # A wildly different season 2015-16 must leave the 2015-16 prior untouched:
    # it is built from 2014-15 and earlier.
    moved = players.copy()
    moved.loc[moved.year == 2015, ["minutes", "goals_non_pk", "assists"]] = [90, 0, 0]
    after = squad.club_channels(players, 2015,
                                squad.player_levels(moved, 2015, att, dfn))
    pd.testing.assert_frame_equal(before, after)


def test_a_players_own_future_seasons_do_not_enter_his_level():
    players = pd.DataFrame([
        {"season": "201314", "year": 2013, "club": "A", "player_id": "aaaaaaaa",
         "minutes": 3000, "age": 25, "goals_non_pk": 10, "assists": 5},
        {"season": "201617", "year": 2016, "club": "B", "player_id": "aaaaaaaa",
         "minutes": 3000, "age": 28, "goals_non_pk": 30, "assists": 30},
    ])
    levels = squad.player_levels(players, 2015, {"A": 0.5, "B": -9.0},
                                 {"A": -0.2, "B": 9.0})
    assert levels.loc["aaaaaaaa", "p_att"] == pytest.approx(0.5)
    assert levels.loc["aaaaaaaa", "p_ga90"] == pytest.approx(90 * 15 / 3000)


# --- the aggregates ------------------------------------------------------


def test_minutes_weighting_follows_time_at_the_club_not_headcount():
    """A January arrival counts for the half-season he was there, not a full
    share -- five bit-part players must not outvote a regular."""
    players = pd.DataFrame(
        [{"season": "201415", "year": 2014, "club": "A", "player_id": f"reg{i:05d}",
          "minutes": 3000, "age": 25, "goals_non_pk": 0, "assists": 0} for i in range(1)]
        + [{"season": "201415", "year": 2014, "club": "A", "player_id": f"bit{i:05d}",
            "minutes": 90, "age": 25, "goals_non_pk": 0, "assists": 0} for i in range(5)]
    )
    levels = pd.DataFrame({"p_att": {"reg00000": 1.0}, "p_dfn": {"reg00000": 0.0},
                           "p_age": {"reg00000": 25.0}, "p_ga90": {"reg00000": 0.0}}
                          ).reindex([f"reg{i:05d}" for i in range(1)]
                                    + [f"bit{i:05d}" for i in range(5)])
    levels.loc[[f"bit{i:05d}" for i in range(5)], "p_att"] = 0.0
    channels = squad.club_channels(players, 2015, levels)
    assert channels.loc[0, "sq_att"] == pytest.approx(3000 / (3000 + 450), abs=1e-9)


def test_churn_is_the_share_of_minutes_played_by_someone_new():
    players = pd.DataFrame([
        {"season": "201314", "year": 2013, "club": "A", "player_id": "stayer00",
         "minutes": 1000, "age": 25, "goals_non_pk": 0, "assists": 0},
        {"season": "201415", "year": 2014, "club": "A", "player_id": "stayer00",
         "minutes": 3000, "age": 26, "goals_non_pk": 0, "assists": 0},
        {"season": "201415", "year": 2014, "club": "A", "player_id": "arrival0",
         "minutes": 1000, "age": 24, "goals_non_pk": 0, "assists": 0},
    ])
    levels = squad.player_levels(players, 2015, {"A": 0.0}, {"A": 0.0})
    channels = squad.club_channels(players, 2015, levels)
    assert channels.loc[0, "sq_churn"] == pytest.approx(1000 / 4000)


def test_the_control_arm_carries_no_player_data():
    """`channels=()` must produce a prior built only from what the GLM knows.
    Corrupting every squad channel must leave it identical, or the control is
    not a control."""
    history = _history()
    clean = squad.build(history, (), label="control")
    scrambled = history.copy()
    rng = np.random.default_rng(5)
    for column in squad.CHANNELS:
        scrambled[column] = rng.normal(0, 10, len(scrambled))
    dirty = squad.build(scrambled, (), label="control")
    for season, values in clean.att.items():
        assert values == pytest.approx(dirty.att[season])
