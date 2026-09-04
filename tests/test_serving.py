"""The serving cycle and the paper book.

The load-bearing test in this file is the break-even one. Comparing a model
probability against a DE-VIGGED market probability instead of raw 1/odds
manufactures an edge equal to the bookmaker's margin on every bet, and produces
a book that looks profitable while losing money. It is the single easiest way
to fake this system into working, so it is pinned twice.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from engine import db
from engine.odds import breakeven_prob, devig_probs
from engine.serve import book, cycle
from engine.serve.artifact import Artifact


@pytest.fixture
def conn(database_url):
    connection = db.connect(database_url)
    for i, name in enumerate(["Arsenal", "Chelsea", "Luton", "Barnsley"], start=1):
        connection.execute("INSERT INTO teams (team_id, canonical_name) VALUES (%s, %s)",
                           (i, name))
    connection.execute(
        "INSERT INTO fixtures (fixture_id, division, match_date, kickoff_time,"
        " home_team_id, away_team_id, avg_h, avg_d, avg_a, avg_over25, avg_under25,"
        " source_file) VALUES (1, 'E0', '2026-08-15', '15:00', 1, 2,"
        " 1.90, 3.80, 4.20, 1.95, 1.90, 'test')")
    connection.execute(
        "INSERT INTO fixtures (fixture_id, division, match_date, kickoff_time,"
        " home_team_id, away_team_id, avg_h, avg_d, avg_a, avg_over25, avg_under25,"
        " source_file) VALUES (2, 'E2', '2026-08-15', '15:00', 3, 4,"
        " 2.10, 3.30, 3.50, 2.00, 1.85, 'test')")
    connection.commit()
    return connection


@pytest.fixture
def artifact():
    """A hand-built artifact, so predictions are deterministic and checkable."""
    teams = ("Arsenal", "Barnsley", "Chelsea", "Luton")
    att = (0.35, -0.20, 0.10, -0.15)
    dfn = (-0.25, 0.20, -0.05, 0.15)
    from engine.serve.artifact import _version_string
    config = {"label": "test"}
    version = _version_string(config, "2026-08-10", teams, "digest", 0.30, 0.25, att, dfn)
    return Artifact(version=version, fitted_at="2026-08-10", config=config, teams=teams,
                    intercept=0.30, home=0.25, att=att, dfn=dfn, n_train=1000,
                    corpus_digest="digest")


# --- the break-even rule ---------------------------------------------------


def test_breakeven_is_raw_one_over_odds_not_the_devigged_probability():
    """The two must stay different, and break-even must always be the larger.

    A book with a 5% overround prices a true coin flip at 1.90 both sides:
    break-even 0.526 each, de-vigged 0.500 each. A model saying 0.51 has NO
    edge, but would look like a 1-point edge against the de-vigged number.
    """
    price = 1.90
    assert breakeven_prob(price) == pytest.approx(1 / 1.90)
    devigged, _ = devig_probs(np.array([1.90]), np.array([1.90]))
    assert devigged[0] == pytest.approx(0.50)
    assert breakeven_prob(price) > devigged[0]

    model_probability = 0.51
    assert model_probability < breakeven_prob(price)      # correctly no bet
    assert model_probability > devigged[0]                # the fictional edge


def test_the_book_does_not_bet_a_model_edge_that_only_exists_after_devigging(conn, artifact):
    """The end-to-end version of the test above: a prediction that beats the
    de-vigged market but not the price must produce no bet."""
    # avg_h 1.90 -> break-even 0.5263. Model says 0.54: real edge of 0.014,
    # which is below MIN_EDGE, so still no bet. Push it to 0.50 -- above the
    # de-vigged ~0.49 but below break-even -- and it must certainly not bet.
    conn.execute(
        "INSERT INTO predictions (prediction_id, fixture_id, model_version,"
        " information_set, lam_h, lam_a, p_home, p_draw, p_away, p_over25, p_under25)"
        " VALUES (1, 1, 'v1', 'pre_close', 1.5, 1.2, 0.50, 0.25, 0.25, 0.50, 0.50)")
    conn.commit()
    bets = book.candidates(book.unbet_predictions(conn))
    assert bets.empty


def test_a_genuine_edge_is_bet_and_recorded_with_its_justification(conn, artifact):
    conn.execute(
        "INSERT INTO predictions (prediction_id, fixture_id, model_version,"
        " information_set, lam_h, lam_a, p_home, p_draw, p_away, p_over25, p_under25)"
        " VALUES (1, 1, 'v1', 'pre_close', 1.9, 0.9, 0.62, 0.20, 0.18, 0.55, 0.45)")
    conn.commit()

    bets = book.candidates(book.unbet_predictions(conn))
    home = bets[bets.side == "H"].iloc[0]
    assert home.price == 1.90
    assert home.breakeven_prob == pytest.approx(1 / 1.90)
    assert home.edge == pytest.approx(0.62 - 1 / 1.90)
    assert home.expected_value == pytest.approx(0.62 * 1.90 - 1)
    assert home.price_source == "avg_h"

    assert book.place(conn, bets) == len(bets)
    stored = conn.execute("SELECT * FROM paper_bets").fetchall()
    assert len(stored) == len(bets)
    assert stored[0]["rule_version"] == book.RULE_VERSION
    assert stored[0]["settled_at"] is None      # grading is written beside, later


def test_prices_come_from_average_not_maximum_columns():
    """Max is the best price any book showed and is often unobtainable. Using
    it would flatter the book; Average biases it downward, which is safe."""
    assert all(column.startswith("avg_") for *_, column in book.LEGS)


def test_missing_or_nonsense_prices_never_produce_a_bet(conn):
    conn.execute("UPDATE fixtures SET avg_h = NULL, avg_d = 1.0 WHERE fixture_id = 1")
    conn.execute(
        "INSERT INTO predictions (prediction_id, fixture_id, model_version,"
        " information_set, lam_h, lam_a, p_home, p_draw, p_away, p_over25, p_under25)"
        " VALUES (1, 1, 'v1', 'pre_close', 1.9, 0.9, 0.99, 0.99, 0.01, 0.10, 0.90)")
    conn.commit()
    bets = book.candidates(book.unbet_predictions(conn))
    assert "H" not in set(bets.get("side", []))   # NULL price
    assert "D" not in set(bets.get("side", []))   # price of 1.0 is not a price


def test_a_prediction_is_only_bet_once(conn):
    conn.execute(
        "INSERT INTO predictions (prediction_id, fixture_id, model_version,"
        " information_set, lam_h, lam_a, p_home, p_draw, p_away, p_over25, p_under25)"
        " VALUES (1, 1, 'v1', 'pre_close', 1.9, 0.9, 0.62, 0.20, 0.18, 0.55, 0.45)")
    conn.commit()
    first = book.run(conn)
    second = book.run(conn)
    assert len(first) > 0
    assert second.empty


# --- the serving cycle -----------------------------------------------------


def test_serve_prices_every_pending_fixture(conn, artifact):
    served = cycle.serve(conn, artifact)
    assert len(served) == 2
    assert np.allclose(served.p_h + served.p_d + served.p_a, 1.0)
    assert np.allclose(served.p_over + served.p_under, 1.0)

    stored = conn.execute("SELECT * FROM predictions ORDER BY fixture_id").fetchall()
    assert len(stored) == 2
    assert stored[0]["model_version"] == artifact.version
    assert stored[0]["information_set"] == "pre_close"
    assert stored[0]["calibrated"] == 0          # honest until P3 exists


def test_lambdas_are_stored_raw_so_probabilities_can_be_rederived(conn, artifact):
    """Storing only probabilities would make any later pmf change -- a new line,
    a calibration -- unable to reconstruct what the model actually said."""
    served = cycle.serve(conn, artifact)
    row = conn.execute("SELECT * FROM predictions WHERE fixture_id = 1").fetchone()
    assert row["lam_h"] == pytest.approx(served.iloc[0].lam_h)

    from engine.eval import metrics
    rederived = metrics.model_probs(np.array([row["lam_h"]]), np.array([row["lam_a"]]))
    assert rederived.p_h[0] == pytest.approx(row["p_home"])


def test_rerunning_a_cycle_does_not_duplicate_predictions(conn, artifact):
    assert len(cycle.serve(conn, artifact)) == 2
    assert cycle.serve(conn, artifact).empty
    assert db.scalar(conn, "SELECT COUNT(*) FROM predictions") == 2


def test_force_reprices_without_overwriting_the_earlier_record(conn, artifact):
    """Append-only: a re-serve adds a row, it does not edit history."""
    cycle.serve(conn, artifact)
    cycle.serve(conn, artifact, force=True)
    rows = conn.execute("SELECT * FROM predictions WHERE fixture_id = 1").fetchall()
    assert len(rows) == 2


def test_dry_run_writes_no_predictions(conn, artifact):
    assert len(cycle.serve(conn, artifact, dry_run=True)) == 2
    assert db.scalar(conn, "SELECT COUNT(*) FROM predictions") == 0


def test_registering_an_artifact_is_idempotent(conn, artifact):
    cycle.register(conn, artifact)
    cycle.register(conn, artifact)
    rows = conn.execute("SELECT * FROM model_runs").fetchall()
    assert len(rows) == 1
    assert rows[0]["corpus_digest"] == artifact.corpus_digest


def test_serving_state_snapshot_records_the_cycle(conn, artifact):
    cycle.snapshot(conn, cycle_label="2026-08-15", version=artifact.version,
                   artifact_path=None, fixtures_seen=2, predictions_written=2,
                   bets_written=1, rule_version=book.RULE_VERSION)
    row = conn.execute("SELECT * FROM serving_state").fetchone()
    assert row["model_version"] == artifact.version
    assert row["bets_written"] == 1
