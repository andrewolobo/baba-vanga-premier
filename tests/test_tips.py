"""The tip selection rule.

The property worth protecting is that this rule **ignores price**. It sits next
to `book.py`, which is a value rule and does the opposite, and the two produce
almost disjoint fixtures -- value lives on longshots, confidence on favourites.
An "improvement" that quietly added an EV filter here would change the product
from the one that was chosen while leaving every test about probabilities green.
"""

from __future__ import annotations

import pandas as pd
import pytest

from engine.serve import tips


def predictions(rows) -> pd.DataFrame:
    """rows: (fixture_id, p_home, p_draw, p_away, max_h, max_d, max_a)."""
    frame = pd.DataFrame(rows, columns=["fixture_id", "p_home", "p_draw", "p_away",
                                        "max_h", "max_d", "max_a"])
    frame["prediction_id"] = range(100, 100 + len(frame))
    for side in ("h", "d", "a"):
        frame[f"avg_{side}"] = frame[f"max_{side}"] * 0.95
    return frame


def test_a_confident_outright_is_recommended_outright():
    out = tips.select(predictions([
        (1, 0.60, 0.25, 0.15, 1.70, 4.0, 7.0),
        (2, 0.20, 0.20, 0.60, 7.0, 4.0, 1.70),
    ]), floor=0.55)

    assert list(out.side) == ["H", "A"]
    assert list(out.model_prob) == [0.60, 0.60]


def test_a_weak_outright_falls_back_to_double_chance():
    """v1 published nothing here. v2 covers every fixture, which is the whole
    point of B8: 14.4% coverage became 100%."""
    out = tips.select(predictions([
        (1, 0.54, 0.26, 0.20, 1.85, 3.6, 5.0),
        (2, 0.56, 0.24, 0.20, 1.80, 3.6, 5.0),
    ]), floor=0.55)

    assert list(out.fixture_id) == [1, 2]
    assert out.side.iloc[0] in {"1X", "12"}, "0.54 is below the floor"
    assert out.side.iloc[1] == "H", "0.56 clears it"


def test_exactly_one_recommendation_per_fixture():
    """Three legs go in, one comes out. A fixture appearing twice would double
    count in every strike-rate figure the product is sold on."""
    out = tips.select(predictions([(1, 0.60, 0.25, 0.15, 1.70, 4.0, 7.0)]),
                      floor=0.55)

    assert len(out) == 1


def test_the_rule_ignores_price_entirely():
    """The whole difference from `book.py`. Two identical fixtures, one priced
    generously and one atrociously, must both be tipped -- a confidence rule
    does not care, and if this ever fails the product has silently become a
    value rule with a different strike rate."""
    out = tips.select(predictions([
        (1, 0.60, 0.25, 0.15, 3.00, 4.0, 7.0),   # way above break-even
        (2, 0.60, 0.25, 0.15, 1.10, 4.0, 7.0),  # far below it
    ]), floor=0.55)

    assert set(out.fixture_id) == {1, 2}


def test_the_carried_price_belongs_to_the_tipped_side():
    """Reporting reads these columns, so a mismatch would misstate the return
    of every tip while leaving the strike rate correct."""
    out = tips.select(predictions([
        (1, 0.60, 0.25, 0.15, 1.70, 4.0, 7.0),
        (2, 0.20, 0.20, 0.60, 7.0, 4.0, 1.65),
    ]), floor=0.55).set_index("fixture_id")

    assert out.loc[1, "best_price"] == pytest.approx(1.70)
    assert out.loc[2, "best_price"] == pytest.approx(1.65)
    assert out.loc[2, "avg_price"] == pytest.approx(1.65 * 0.95)


def test_a_double_chance_price_is_derived_from_its_legs():
    """No feed carries double-chance odds. `1/(1/o_h + 1/o_d)` is the fair
    combination and an UPPER BOUND on what a customer could get, because real
    double-chance markets carry their own margin on top."""
    out = tips.select(predictions([(1, 0.40, 0.30, 0.30, 2.50, 4.00, 4.00)]),
                      floor=0.55).set_index("fixture_id")

    assert out.loc[1, "side"] in {"1X", "12"}
    expected = 1.0 / (1.0 / 2.50 + 1.0 / 4.00)
    assert out.loc[1, "best_price"] == pytest.approx(expected)


@pytest.mark.parametrize("bad", [0.0, 1.0, -0.1, 1.5])
def test_a_floor_outside_zero_to_one_is_refused(bad):
    with pytest.raises(ValueError, match="probability"):
        tips.select(predictions([(1, 0.6, 0.25, 0.15, 1.7, 4.0, 7.0)]), floor=bad)


def test_the_honesty_check_still_imports_and_covers_the_shipped_floor():
    """`engine/eval/tips.py` is what the product's claims lean on, and nothing
    imported it. It shipped importing a name `serve/tips.py` no longer defined
    (`DEFAULT_THRESHOLD`, renamed at B8), so "re-run it after any head change"
    was an instruction to run a module that could not load. Importing it here
    keeps that from recurring, and the second assertion is `headline`'s own
    precondition: it looks the shipped setting up on the threshold grid and
    raises `StopIteration` if it is not there."""
    from engine.eval import tips as honesty

    assert tips.DEFAULT_FLOOR in honesty.THRESHOLDS


def test_the_published_columns_are_stable():
    out = tips.select(predictions([(1, 0.40, 0.35, 0.25, 2.4, 3.2, 4.0)]),
                      floor=0.55)

    assert list(out.columns) == ["fixture_id", "prediction_id", "side",
                                 "model_prob", "rule_version", "floor",
                                 "ceiling", "best_price", "avg_price"]


# --- the database path -----------------------------------------------------


@pytest.fixture
def conn(tmp_path):
    """Two fixtures, both priced, both predicted, neither tipped.

    Both are dated **today**: the rule publishes on matchday only
    (`tips.PUBLISH_WITHIN_DAYS`), so a fixed future date would make every test
    below assert on an empty frame rather than on the tip rule.
    """
    from engine import db

    connection = db.connect(tmp_path / "tips.db")
    db.migrate(connection)
    for i, name in enumerate(["Arsenal", "Chelsea", "Luton", "Barnsley"], start=1):
        connection.execute("INSERT INTO teams (team_id, canonical_name) VALUES (?, ?)",
                           (i, name))
    for fid, home, away, prices in ((1, 1, 2, (1.60, 4.00, 6.00)),
                                    (2, 3, 4, (2.40, 3.30, 3.10))):
        connection.execute(
            "INSERT INTO fixtures (fixture_id, division, match_date, home_team_id,"
            " away_team_id, max_h, max_d, max_a, avg_h, avg_d, avg_a, source_file)"
            " VALUES (?, 'E0', date('now'), ?, ?, ?, ?, ?, ?, ?, ?, 'test')",
            (fid, home, away, *prices, *[p * 0.95 for p in prices]))
    for pid, fid, probs in ((10, 1, (0.62, 0.24, 0.14)), (11, 2, (0.44, 0.28, 0.28))):
        connection.execute(
            "INSERT INTO predictions (prediction_id, fixture_id, model_version,"
            " information_set, served_at, lam_h, lam_a, p_home, p_draw, p_away,"
            " p_over25, p_under25) VALUES (?, ?, 'v1', 'pre_close', '2026-08-10',"
            " 1.5, 1.0, ?, ?, ?, 0.5, 0.5)", (pid, fid, *probs))
    connection.commit()
    yield connection
    connection.close()


def test_a_fixture_beyond_the_publish_window_is_not_tipped_yet(conn):
    """The gate a second fixture calendar makes necessary.

    A tip is published once and never revised, so publishing weeks early locks
    in a call from an artifact that refreezes every 7 days. While the only
    source was football-data's rolling window this bounded itself; a forward
    calendar removes that bound and this restores it.
    """
    conn.execute("UPDATE fixtures SET match_date = date('now', '+6 days')")
    conn.commit()

    assert tips.untipped(conn).empty
    assert len(tips.untipped(conn, within_days=7)) == 2


def test_a_fixture_already_played_is_never_tipped(conn):
    """The lower bound. A missed cycle must not publish a call on a match whose
    result is already known -- unreachable before a forward calendar existed."""
    conn.execute("UPDATE fixtures SET match_date = date('now', '-1 day')")
    conn.commit()

    assert tips.untipped(conn).empty
    assert tips.untipped(conn, within_days=30).empty, "a wider window must not reach back"


def test_untipped_returns_predictions_joined_to_their_prices(conn):
    pending = tips.untipped(conn)

    assert set(pending.fixture_id) == {1, 2}
    assert pending.set_index("fixture_id").loc[1, "max_h"] == 1.60


def test_publishing_then_re_running_produces_no_second_tip(conn):
    """A cycle that has already published is a normal state to re-enter."""
    first = tips.publish(conn, tips.select(tips.untipped(conn)))

    assert first == 2, "v2 covers every fixture"
    assert tips.untipped(conn).empty
    assert tips.publish(conn, tips.select(tips.untipped(conn))) == 0


def test_the_database_refuses_a_second_tip_on_the_same_fixture(conn):
    """The safety property, enforced in migration 003 rather than in Python: a
    tipster publishing two recommendations for one match has no strike rate."""
    import sqlite3

    tips.publish(conn, tips.select(tips.untipped(conn)))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO tips (prediction_id, fixture_id, side, model_prob,"
            " floor, rule_version) VALUES (10, 1, 'A', 0.9, 0.55, ?)",
            (tips.RULE_VERSION,))


def test_a_missing_price_is_stored_as_null_not_nan(conn):
    conn.execute("UPDATE fixtures SET max_h = NULL WHERE fixture_id = 1")
    tips.publish(conn, tips.select(tips.untipped(conn)))

    row = conn.execute("SELECT best_price, avg_price FROM tips"
                       " WHERE fixture_id = 1").fetchone()
    assert row["best_price"] is None
    assert row["avg_price"] is not None, "only the missing column is null"


def test_dry_run_publishes_nothing(conn):
    assert tips.publish(conn, tips.select(tips.untipped(conn)), dry_run=True) == 0
    assert conn.execute("SELECT COUNT(*) FROM tips").fetchone()[0] == 0


# --- settlement ------------------------------------------------------------


def result(ftr: str) -> dict:
    return {"ftr": ftr, "fthg": 2, "ftag": 0}


def test_settling_records_the_outcome_and_both_price_levels(conn):
    from services import csv_grader

    tips.publish(conn, tips.select(tips.untipped(conn)))
    settled = csv_grader.settle_tips(conn, 1, result("H"))
    conn.commit()

    row = conn.execute("SELECT * FROM tips WHERE fixture_id = 1").fetchone()
    assert settled == 1
    assert row["outcome"] == "win"
    assert row["pnl_best"] == pytest.approx(0.60)          # 1.60 - 1
    assert row["pnl_avg"] == pytest.approx(1.60 * 0.95 - 1)


def test_a_losing_tip_loses_one_unit_at_both_price_levels(conn):
    from services import csv_grader

    tips.publish(conn, tips.select(tips.untipped(conn)))
    csv_grader.settle_tips(conn, 1, result("A"))
    conn.commit()

    row = conn.execute("SELECT * FROM tips WHERE fixture_id = 1").fetchone()
    assert row["outcome"] == "lose"
    assert row["pnl_best"] == -1.0
    assert row["pnl_avg"] == -1.0


def test_a_tip_with_no_price_still_settles_its_outcome(conn):
    """Strike rate is the product's headline and must never depend on the feed
    having carried odds. P&L stays NULL rather than being guessed."""
    from services import csv_grader

    conn.execute("UPDATE fixtures SET max_h = NULL, avg_h = NULL WHERE fixture_id = 1")
    tips.publish(conn, tips.select(tips.untipped(conn)))
    csv_grader.settle_tips(conn, 1, result("H"))
    conn.commit()

    row = conn.execute("SELECT * FROM tips WHERE fixture_id = 1").fetchone()
    assert row["outcome"] == "win"
    assert row["pnl_best"] is None and row["pnl_avg"] is None


def test_settling_is_not_repeated_on_the_next_cycle(conn):
    from services import csv_grader

    tips.publish(conn, tips.select(tips.untipped(conn)))
    csv_grader.settle_tips(conn, 1, result("H"))
    conn.commit()

    assert csv_grader.settle_tips(conn, 1, result("H")) == 0
