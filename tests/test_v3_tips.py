"""confidence-v3: the underdog +1.5 in the serving path (`V3_ADOPTION_PLAN.md`).

The invariant under protection is B8's, extended: the number the gate measured
and the number the product settles are the same code. So the tests pin (1) the
new settlement function against the old one and against the gate's own
`b21.won`, (2) `tips.select` against the gate's `b21.recommend` via the
fav-relative -> concrete side mapping, (3) migration 005, and (4) the referee
reconciliation the adoption was conditioned on.
"""

from __future__ import annotations

import itertools

import numpy as np
import pandas as pd
import pytest

from engine import db
from engine.eval import b21, selection
from engine.eval.dispersion import outcome_probs, score_matrix
from engine.serve import tips


# --- settlement ------------------------------------------------------------


def test_won_from_score_agrees_with_won_on_every_measured_side():
    """Exhaustive over the five measured markets x scores 0-3: the wrapper may
    add sides but must never re-decide one the gates settled."""
    scores = list(itertools.product(range(4), range(4)))
    fthg = np.array([s[0] for s in scores], dtype=float)
    ftag = np.array([s[1] for s in scores], dtype=float)
    ftr = np.where(fthg > ftag, "H", np.where(fthg < ftag, "A", "D"))
    for side in ("H", "A", "1X", "X2", "12"):
        market = np.full(len(scores), side)
        assert (selection.won_from_score(market, fthg, ftag)
                == selection._won(market, ftr)).all(), side


def test_the_handicap_settles_on_the_margin_alone():
    # A+1.5: away with the start -- loses only when away loses by 2+.
    scores = [(2, 0), (3, 1), (1, 0), (0, 0), (0, 1), (0, 2)]
    fthg, ftag = np.array([s[0] for s in scores]), np.array([s[1] for s in scores])
    a = selection.won_from_score(np.full(len(scores), "A+1.5"), fthg, ftag)
    assert list(a) == [False, False, True, True, True, True]
    # H+1.5 is the mirror: loses only when home loses by 2+.
    h = selection.won_from_score(np.full(len(scores), "H+1.5"), fthg, ftag)
    assert list(h) == [True, True, True, True, True, False]


def test_concrete_sides_settle_identically_to_the_gates_fav_relative_label():
    """The gate measured `D+1.5` relative to the model favourite; the product
    stores `H+1.5`/`A+1.5`. Same mapping, same outcome, on random data."""
    rng = np.random.default_rng(21)
    n = 500
    lam_h = np.exp(rng.normal(np.log(1.4), 0.3, n))
    lam_a = np.exp(rng.normal(np.log(1.1), 0.3, n))
    frame = pd.DataFrame({"fthg": rng.poisson(lam_h), "ftag": rng.poisson(lam_a)})
    frame["ftr"] = np.where(frame.fthg > frame.ftag, "H",
                            np.where(frame.fthg < frame.ftag, "A", "D"))
    probs = np.column_stack(outcome_probs(score_matrix(lam_h, lam_a)))
    fav_home = probs[:, 0] >= probs[:, 2]
    concrete = np.where(fav_home, "A+1.5", "H+1.5")
    via_gate = b21.won(np.full(n, b21.DOG15), frame, probs)
    via_serve = selection.won_from_score(concrete, frame.fthg, frame.ftag)
    assert (via_gate == via_serve).all()


# --- selection -------------------------------------------------------------


def _predictions(lam_pairs):
    lam_h = np.array([p[0] for p in lam_pairs], dtype=float)
    lam_a = np.array([p[1] for p in lam_pairs], dtype=float)
    probs = np.column_stack(outcome_probs(score_matrix(lam_h, lam_a)))
    frame = pd.DataFrame({
        "fixture_id": range(1, len(lam_pairs) + 1),
        "prediction_id": range(100, 100 + len(lam_pairs)),
        "lam_h": lam_h, "lam_a": lam_a,
        "p_home": probs[:, 0], "p_draw": probs[:, 1], "p_away": probs[:, 2],
    })
    for side, col in (("h", "p_home"), ("d", "p_draw"), ("a", "p_away")):
        frame[f"max_{side}"] = 1.0 / frame[col]
        frame[f"avg_{side}"] = frame[f"max_{side}"] * 0.97
    return frame


def test_select_is_the_measured_rule_with_sides_made_concrete():
    """`tips.select` == `b21.recommend` + the D1 mapping, match for match."""
    rng = np.random.default_rng(22)
    lam_pairs = list(zip(np.exp(rng.normal(np.log(1.4), 0.35, 300)),
                         np.exp(rng.normal(np.log(1.1), 0.35, 300))))
    frame = _predictions(lam_pairs)
    out = tips.select(frame, floor=0.55, ceiling=0.85)

    probs = frame[["p_home", "p_draw", "p_away"]].to_numpy(float)
    joint = score_matrix(frame.lam_h.to_numpy(float), frame.lam_a.to_numpy(float))
    market, prob = b21.recommend(probs, b21.dog15_probs(joint, probs),
                                 floor=0.55, ceiling=0.85)
    fav_home = probs[:, 0] >= probs[:, 2]
    expected = np.where(market == b21.DOG15,
                        np.where(fav_home, "A+1.5", "H+1.5"), market)
    assert (out.side.to_numpy() == expected).all()
    assert np.allclose(out.model_prob.to_numpy(), prob)
    assert out.rule_version.eq("confidence-v3").all()


def test_with_the_handicap_never_eligible_the_rule_is_exactly_v2():
    """Composition pin: a zero handicap probability can never win the fallback
    argmax, and then `b21.recommend` must be `selection.recommend` verbatim."""
    raw = np.random.default_rng(23).dirichlet((4, 3, 3), size=2000)
    market, prob = b21.recommend(raw, np.zeros(len(raw)), floor=0.55, ceiling=0.85)
    v2_market, v2_prob = selection.recommend(raw, 0.55, 0.85, allow_12=True)
    assert (market == v2_market).all()
    assert np.allclose(prob, v2_prob)


def test_a_handicap_tip_carries_no_price():
    """No feed price, no derivable one (D2): NULL, never a guess."""
    frame = _predictions([(1.5, 1.1)])          # weak favourite -> fallback
    out = tips.select(frame, floor=0.55, ceiling=0.85)
    assert out.side.iloc[0] == "A+1.5"
    assert pd.isna(out.best_price.iloc[0]) and pd.isna(out.avg_price.iloc[0])


# --- migration 005 ---------------------------------------------------------


def test_migration_005_accepts_the_handicap_and_still_refuses_nonsense(tmp_path):
    conn = db.connect(tmp_path / "m005.db")
    db.migrate(conn)
    conn.execute("INSERT INTO teams (team_id, canonical_name) VALUES (1, 'A'),"
                 " (2, 'B')")
    conn.execute("INSERT INTO fixtures (fixture_id, division, match_date,"
                 " home_team_id, away_team_id, source_file)"
                 " VALUES (1, 'E0', date('now'), 1, 2, 't')")
    conn.execute("INSERT INTO predictions (prediction_id, fixture_id,"
                 " model_version, information_set, served_at, lam_h, lam_a,"
                 " p_home, p_draw, p_away, p_over25, p_under25)"
                 " VALUES (10, 1, 'v1', 'pre_close', '2026-08-19', 1.5, 1.0,"
                 " 0.4, 0.3, 0.3, 0.5, 0.5)")
    conn.execute("INSERT INTO tips (prediction_id, fixture_id, side, model_prob,"
                 " floor, rule_version) VALUES (10, 1, 'A+1.5', 0.79, 0.55, 'confidence-v3')")
    import sqlite3
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO tips (prediction_id, fixture_id, side,"
                     " model_prob, floor, rule_version)"
                     " VALUES (10, 1, 'H-1.5', 0.5, 0.55, 'confidence-v3')")
    conn.close()


# --- the referee -----------------------------------------------------------


def test_referee_gap_is_zero_when_model_and_market_agree():
    """Odds planted vig-free from the model's own probabilities: the market
    lambda fit recovers the model's lambdas and the gap must vanish."""
    frame = _predictions([(1.5, 1.1), (1.3, 1.2)])
    for side in ("h", "d", "a"):                 # no vig: avg == fair
        frame[f"avg_{side}"] = frame[f"max_{side}"]
    out = tips.select(frame, floor=0.55, ceiling=0.85)
    assert set(out.side) <= {"H+1.5", "A+1.5"}, "both must reach the handicap"
    n, gap = tips.referee_gap(out, frame)
    assert n == 2
    assert abs(gap) < 1e-3


def test_referee_gap_excludes_fixtures_without_odds_and_low_claims():
    frame = _predictions([(1.5, 1.1)])
    out = tips.select(frame, floor=0.55, ceiling=0.85)
    no_odds = frame.copy()
    no_odds[["avg_h", "avg_d", "avg_a"]] = np.nan
    assert tips.referee_gap(out, no_odds) == (0, None)
    low = out.copy()
    low["model_prob"] = 0.60                     # below REFEREE_MIN_CLAIM
    assert tips.referee_gap(low, frame) == (0, None)


def test_referee_gap_ignores_priced_sides():
    frame = _predictions([(2.6, 0.7)])           # strong favourite -> outright
    out = tips.select(frame, floor=0.55, ceiling=0.85)
    assert out.side.iloc[0] == "H"
    assert tips.referee_gap(out, frame) == (0, None)


# --- the cycle step --------------------------------------------------------


def _serving_db(tmp_path, avg_odds):
    """One weak-favourite fixture today, its prediction stored with lambdas
    (1.5, 1.0) -- the v3 rule publishes `A+1.5` at ~0.754 -- and the fixture
    priced at `avg_odds` (h, d, a)."""
    conn = db.connect(tmp_path / "cycle.db")
    db.migrate(conn)
    conn.execute("INSERT INTO teams (team_id, canonical_name) VALUES (1, 'A'),"
                 " (2, 'B')")
    conn.execute(
        "INSERT INTO fixtures (fixture_id, division, match_date, home_team_id,"
        " away_team_id, avg_h, avg_d, avg_a, source_file)"
        " VALUES (1, 'E0', date('now'), 1, 2, ?, ?, ?, 't')", avg_odds)
    conn.execute(
        "INSERT INTO predictions (prediction_id, fixture_id, model_version,"
        " information_set, served_at, lam_h, lam_a, p_home, p_draw, p_away,"
        " p_over25, p_under25) VALUES (10, 1, 'v1', 'pre_close', '2026-08-19',"
        " 1.5, 1.0, 0.488, 0.260, 0.252, 0.5, 0.5)")
    conn.commit()
    return conn


def test_step_tips_reports_the_referee_gap_and_stays_quiet_in_band(tmp_path):
    from services import run_cycle

    # Odds planted vig-free from the model's own probabilities: gap ~ 0.
    conn = _serving_db(tmp_path, (1.0 / 0.488, 1.0 / 0.260, 1.0 / 0.252))
    step = run_cycle.step_tips(conn, dry_run=False)

    assert conn.execute("SELECT side FROM tips").fetchone()[0] == "A+1.5"
    assert "referee gap" in step.detail
    assert step.status is run_cycle.Status.OK, step.detail
    conn.close()


def test_step_tips_flags_attention_when_the_model_leaves_the_market(tmp_path):
    from services import run_cycle

    # The market prices a heavy home favourite the prediction does not see:
    # market-implied A+1.5 sits far below the model's 0.754 claim.
    conn = _serving_db(tmp_path, (1.20, 6.5, 12.0))
    step = run_cycle.step_tips(conn, dry_run=False)

    assert "referee gap" in step.detail
    assert step.status is run_cycle.Status.ATTENTION, step.detail
    assert "market-implied" in step.detail
    conn.close()


def test_step_tips_survives_a_fixture_without_odds(tmp_path):
    from services import run_cycle

    conn = _serving_db(tmp_path, (None, None, None))
    step = run_cycle.step_tips(conn, dry_run=False)

    assert conn.execute("SELECT COUNT(*) FROM tips").fetchone()[0] == 1
    assert step.status is not run_cycle.Status.FAILED, step.detail
    assert "referee gap" not in step.detail
    conn.close()
