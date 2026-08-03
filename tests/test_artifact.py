"""Frozen artifacts and their version strings.

The version is the whole point: a prediction stored against version X must be
reproducible from version X, months later, without trusting anyone's memory of
what was deployed. So the tests are about identity, in both directions -- same
inputs must give the same string, and any change to any input must change it.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from engine.eval.walkforward import WalkForwardConfig
from engine.serve import artifact as art
from tests.test_walkforward_harness import synthetic_corpus

CUTOFF = pd.Timestamp(2014, 1, 6)


@pytest.fixture(scope="module")
def corpus():
    return synthetic_corpus(n_seasons=5, n_teams=20, seed=12)


@pytest.fixture(scope="module")
def frozen(corpus):
    return art.freeze(corpus, CUTOFF, WalkForwardConfig())


# --- identity --------------------------------------------------------------


def test_freezing_twice_gives_the_same_version(corpus, frozen):
    again = art.freeze(corpus, CUTOFF, WalkForwardConfig())
    assert again.version == frozen.version
    assert again.corpus_digest == frozen.corpus_digest


def test_row_order_does_not_change_identity(corpus, frozen):
    shuffled = corpus.sample(frac=1.0, random_state=3)
    assert art.freeze(shuffled, CUTOFF, WalkForwardConfig()).version == frozen.version


@pytest.mark.parametrize("cfg", [
    WalkForwardConfig(half_life=150.0),
    WalkForwardConfig(alpha=2.0),
    WalkForwardConfig(season_boundary_shrink=0.9),
    WalkForwardConfig(fit_divisions=("E0",)),
])
def test_any_hyperparameter_change_changes_the_version(corpus, frozen, cfg):
    assert art.freeze(corpus, CUTOFF, cfg).version != frozen.version


def test_a_different_cutoff_changes_the_version(corpus, frozen):
    assert art.freeze(corpus, CUTOFF + pd.Timedelta(days=7),
                      WalkForwardConfig()).version != frozen.version


def test_changing_a_training_result_changes_the_version(corpus, frozen):
    """The digest has to cover the data, not just the settings. Otherwise a
    re-fit on corrected results would silently reuse the old version string."""
    edited = corpus.copy()
    early = edited["match_date"] < CUTOFF
    edited.loc[early, "fthg"] = edited.loc[early, "fthg"] + 1
    assert art.freeze(edited, CUTOFF, WalkForwardConfig()).version != frozen.version


def test_changing_data_after_the_cutoff_does_NOT_change_the_version(corpus, frozen):
    """The mirror image, and the one that matters for leakage: an artifact must
    not depend on anything that happened after it was frozen."""
    edited = corpus.copy()
    later = edited["match_date"] >= CUTOFF
    edited.loc[later, "fthg"] = 7
    edited.loc[later, "ftag"] = 3
    assert art.freeze(edited, CUTOFF, WalkForwardConfig()).version == frozen.version


# --- round trip ------------------------------------------------------------


def test_save_and_load_round_trip(frozen, tmp_path):
    path = frozen.save(tmp_path)
    loaded = art.Artifact.load(path)
    assert loaded.version == frozen.version
    assert loaded.teams == frozen.teams
    assert loaded.n_train == frozen.n_train
    assert np.allclose(loaded.att, frozen.att)


def test_predictions_survive_the_round_trip(frozen, tmp_path):
    loaded = art.Artifact.load(frozen.save(tmp_path))
    home = list(frozen.teams[:5])
    away = list(frozen.teams[5:10])
    original = frozen.predict(home, away)
    restored = loaded.predict(home, away)
    assert np.array_equal(original[0], restored[0])
    assert np.array_equal(original[1], restored[1])


def test_an_edited_artifact_file_is_refused(frozen, tmp_path):
    """A version string you can edit is a version string that will eventually
    name the wrong model in an audit."""
    path = frozen.save(tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["att"][0] += 0.01
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="edited since it was frozen"):
        art.Artifact.load(path)


# --- serving behaviour -----------------------------------------------------


def test_an_unknown_club_raises_rather_than_averaging(frozen):
    with pytest.raises(KeyError, match="never seen"):
        frozen.predict(["Newly Promoted FC"], [frozen.teams[0]])


def test_artifact_predictions_match_the_harness(corpus, frozen):
    """The frozen artifact and the walk-forward harness must agree, or the
    backtest measured something other than what will be served."""
    from engine.eval import walkforward as wf
    served = wf.lambdas_at(corpus, CUTOFF, WalkForwardConfig())
    subset = served.head(20)
    lam_h, lam_a = frozen.predict(list(subset["home_team"]), list(subset["away_team"]))
    assert np.allclose(lam_h, subset["lam_h"].to_numpy())
    assert np.allclose(lam_a, subset["lam_a"].to_numpy())


def test_fitted_at_is_the_cutoff_not_wall_clock(frozen):
    assert frozen.fitted_at.startswith("2014-01-06")


def test_freeze_refuses_when_there_is_no_history(corpus):
    with pytest.raises(ValueError, match="not enough history"):
        art.freeze(corpus, pd.Timestamp(2010, 8, 12), WalkForwardConfig())
