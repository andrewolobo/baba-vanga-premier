"""The full weekly cycle on a synthetic matchday: sync → predict → bet → grade.

This is the rehearsal PLAN §Week 3 asks for. Each piece is unit-tested
elsewhere; what this proves is that they compose -- that a fixture pulled from
the feed ends up as a graded bet with CLV attached, without anyone joining the
steps by hand.

It runs entirely offline against a fixed feed and a fixed result sheet, so it
is the check that can be run on the morning of opening weekend to confirm the
pipeline is sound before any real fixture arrives.
"""

from __future__ import annotations

import pandas as pd
import pytest

from engine import db
from engine.serve import book, cycle
from engine.serve.artifact import Artifact, _version_string
from services import csv_grader, fixture_sync

FEED = (
    "Div,Date,Time,HomeTeam,AwayTeam,AvgH,AvgD,AvgA,MaxH,MaxD,MaxA,"
    "Avg>2.5,Avg<2.5,AHh,AvgAHH,AvgAHA\n"
    "E0,15/08/2026,15:00,Arsenal,Chelsea,2.60,3.50,2.70,2.70,3.60,2.80,"
    "1.95,1.90,0.00,1.95,1.95\n"
    "E2,15/08/2026,15:00,Luton,Barnsley,2.50,3.40,2.80,2.60,3.50,2.90,"
    "2.00,1.85,0.00,1.92,1.98\n"
)

RESULTS = (
    "Div,Date,HomeTeam,AwayTeam,FTHG,FTAG,FTR,"
    "AvgH,AvgD,AvgA,Avg>2.5,Avg<2.5,"
    "PSCH,PSCD,PSCA,AvgCH,AvgCD,AvgCA,AvgC>2.5,AvgC<2.5\n"
    # Arsenal win 3-1: home bet wins, over 2.5 wins. Home shortened 2.60 -> 2.30
    # so CLV is positive; the over drifted 1.95 -> 2.05 so its CLV is negative.
    "E0,15/08/2026,Arsenal,Chelsea,3,1,H,"
    "2.60,3.50,2.70,1.95,1.90,"
    "2.30,3.60,3.10,2.32,3.55,3.05,2.05,1.80\n"
    "E2,15/08/2026,Luton,Barnsley,0,0,D,"
    "2.50,3.40,2.80,2.00,1.85,"
    "2.55,3.35,2.75,2.58,3.30,2.72,1.98,1.86\n"
)


@pytest.fixture
def conn(tmp_path):
    connection = db.connect(tmp_path / "e2e.db")
    db.migrate(connection)
    for i, name in enumerate(["Arsenal", "Barnsley", "Chelsea", "Luton"], start=1):
        connection.execute("INSERT INTO teams (team_id, canonical_name) VALUES (?, ?)",
                           (i, name))
    connection.commit()
    return connection


@pytest.fixture
def artifact():
    """Strengths chosen so both fixtures produce a bettable edge somewhere."""
    teams = ("Arsenal", "Barnsley", "Chelsea", "Luton")
    att = (0.40, -0.25, 0.05, 0.20)
    dfn = (-0.30, 0.25, 0.00, -0.10)
    config = {"label": "e2e"}
    version = _version_string(config, "2026-08-10", teams, "digest", 0.30, 0.25, att, dfn)
    return Artifact(version=version, fitted_at="2026-08-10", config=config, teams=teams,
                    intercept=0.30, home=0.25, att=att, dfn=dfn, n_train=1000,
                    corpus_digest="digest")


def test_a_full_weekly_cycle(conn, artifact):
    # 1. the feed lands
    sync = fixture_sync.sync(conn, FEED, "e2e-feed")
    assert sync.inserted == 2
    assert sync.report.clean

    # 2. the head prices every fixture
    cycle.register(conn, artifact)
    served = cycle.serve(conn, artifact)
    assert len(served) == 2
    assert conn.execute("SELECT COUNT(*) FROM predictions").fetchone()[0] == 2

    # 3. the rule turns some of them into bets
    bets = book.run(conn)
    assert len(bets) > 0, "the synthetic strengths should produce at least one edge"
    for row in bets.itertuples():
        assert row.model_prob > row.breakeven_prob
        assert row.breakeven_prob == pytest.approx(1 / row.price)

    # 4. results arrive; bets settle and CLV is graded
    report = csv_grader.grade(conn, csv_grader.parse_results(RESULTS))
    assert report.settled == len(bets)
    assert report.graded > 0

    settled = conn.execute(
        "SELECT * FROM paper_bets WHERE settled_at IS NOT NULL").fetchall()
    assert len(settled) == len(bets)
    for row in settled:
        assert row["outcome"] in ("win", "lose")
        assert row["pnl"] is not None

    # 5. the record is complete and internally consistent
    graded = conn.execute(
        "SELECT b.price, b.side, b.market, g.* FROM clv_grades g"
        " JOIN paper_bets b ON b.bet_id = g.bet_id").fetchall()
    for row in graded:
        assert row["clv_pct"] == pytest.approx(row["bet_price"] / row["close_price"] - 1)
        # CLV and price movement must agree in sign: a shortening price means
        # the market moved toward us, which is positive CLV.
        assert (row["clv"] > 0) == (row["bet_price"] > row["close_price"])
        # Both legs are de-vigged probabilities, so neither equals 1/price.
        assert row["bet_prob"] != pytest.approx(1 / row["bet_price"])


def test_the_cycle_is_idempotent_end_to_end(conn, artifact):
    """Re-running every step must not double-count anything. A cron that fires
    twice, or an operator re-running after a network blip, is normal."""
    fixture_sync.sync(conn, FEED, "e2e-feed")
    cycle.serve(conn, artifact)
    book.run(conn)
    csv_grader.grade(conn, csv_grader.parse_results(RESULTS))

    counts = lambda: tuple(  # noqa: E731
        conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        for t in ("fixtures", "predictions", "paper_bets", "clv_grades")
    )
    before = counts()

    fixture_sync.sync(conn, FEED, "e2e-feed")
    cycle.serve(conn, artifact)
    book.run(conn)
    csv_grader.grade(conn, csv_grader.parse_results(RESULTS))

    assert counts() == before


def test_pnl_and_clv_disagree_at_least_once_in_the_rehearsal(conn, artifact):
    """A sanity check on the rehearsal itself rather than the code.

    If every winning bet also had positive CLV, the fixture data would be too
    agreeable to exercise the distinction the whole design rests on: a bet can
    win and still have been a bad price, and lose while having been a good one.
    """
    fixture_sync.sync(conn, FEED, "e2e-feed")
    cycle.serve(conn, artifact)
    book.run(conn)
    csv_grader.grade(conn, csv_grader.parse_results(RESULTS))

    rows = conn.execute(
        "SELECT b.outcome, g.clv FROM paper_bets b"
        " JOIN clv_grades g ON g.bet_id = b.bet_id").fetchall()
    signs = {(r["outcome"] == "win", r["clv"] > 0) for r in rows}
    assert len(signs) > 1, f"rehearsal data is too uniform to be a real test: {signs}"


def test_a_matchday_with_no_fixtures_is_a_no_op(conn, artifact):
    """The international break. Every step must run clean rather than error."""
    empty = FEED.split("\n")[0] + "\n"
    assert fixture_sync.sync(conn, empty, "empty").inserted == 0
    assert cycle.serve(conn, artifact).empty
    assert book.run(conn).empty
    assert csv_grader.grade(conn, csv_grader.parse_results(RESULTS)).settled == 0
