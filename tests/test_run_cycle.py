"""The unattended cycle, tested on the ways it can quietly do nothing.

An orchestrator is easy to test on the happy path and that is not where the
risk is. The cases that matter are the ones that neither raise nor succeed:
an empty feed, a club nobody has bridged, a fixture the artifact cannot price,
an artifact too old to be serving. Each must come back as `exit 2` and say
which, because a scheduled job reports only its exit code.
"""

from __future__ import annotations

import sqlite3

import pandas as pd
import pytest

from engine import db
from engine.serve import cycle
from engine.serve.artifact import Artifact
from services import run_cycle
from services.run_cycle import Status

FEED_HEADER = ("Div,Date,Time,HomeTeam,AwayTeam,AvgH,AvgD,AvgA,MaxH,MaxD,MaxA,"
               "Avg>2.5,Avg<2.5,AHh,AvgAHH,AvgAHA")


@pytest.fixture
def conn(tmp_path):
    connection = db.connect(tmp_path / "t.db")
    db.migrate(connection)
    connection.executemany(
        "INSERT INTO teams (team_id, canonical_name) VALUES (?, ?)",
        [(1, "Arsenal"), (2, "Chelsea"), (3, "Aldershot")])
    connection.commit()
    return connection


@pytest.fixture
def artifact():
    """A two-club artifact. 'Aldershot' is deliberately outside it."""
    return Artifact(
        version="test-0001", fitted_at="2026-08-01T00:00:00", config="test",
        teams=["Arsenal", "Chelsea"], intercept=0.0, home=0.25,
        att=[0.1, -0.1], dfn=[-0.05, 0.05], n_train=500, corpus_digest="d",
    )


#: A `today` close enough to the `artifact` fixture's `fitted_at` (2026-08-01)
#: that `_stale` does not fire. **Any test reaching `step_serve` with a real
#: artifact must pin this.** Two did not, and began failing on 2026-08-09 when
#: the wall clock passed `REFIT_AFTER_DAYS`: serve refroze the stub, published
#: nothing, and tips reported "no untipped predictions". Nothing was broken in
#: the product -- the staleness rule was working and the tests had aged out.
FRESH_ARTIFACT_DAY = pd.Timestamp("2026-08-02")


def add_fixture(conn, division, home_id, away_id, date="2026-08-15"):
    conn.execute(
        "INSERT INTO fixtures (division, match_date, home_team_id, away_team_id,"
        " source_file) VALUES (?, ?, ?, ?, 'test')", (division, date, home_id, away_id))
    conn.commit()


def feed(rows: str = "") -> str:
    return FEED_HEADER + "\n" + rows


# --- the silent failures ---------------------------------------------------


def test_an_empty_feed_is_attention_not_success(conn, tmp_path, monkeypatch):
    """Today's actual situation: HTTP 200, zero English rows. Nothing raises."""
    monkeypatch.setattr(cycle, "latest_artifact", lambda *a, **k: None)
    monkeypatch.setattr(run_cycle.cycle, "build_artifact",
                        lambda *a, **k: (_stub_artifact(), None))
    path = tmp_path / "empty.csv"
    path.write_text(feed("SC0,08/08/2026,15:00,Celtic,Rangers,2,3,4,2,3,4,2,2,0,2,2"),
                    encoding="utf-8")

    report = run_cycle.run(conn, file=path, dry_run=True,
                           today=FRESH_ARTIFACT_DAY)
    sync = next(s for s in report.steps if s.name == "sync")
    assert sync.status is Status.ATTENTION
    assert "NO ENGLISH ROWS" in sync.detail
    assert report.status.exit_code == 2


def test_a_club_the_artifact_never_saw_does_not_take_the_matchday_down(
        conn, artifact, monkeypatch):
    """One National League newcomer must not cost the Premier League its prices."""
    monkeypatch.setattr(cycle, "latest_artifact", lambda *a, **k: artifact)
    add_fixture(conn, "E0", 1, 2)          # priceable
    add_fixture(conn, "EC", 3, 1)          # Aldershot: unknown to the artifact

    report = run_cycle.run(conn, file=_empty_feed(), today=pd.Timestamp("2026-08-02"))

    serve = next(s for s in report.steps if s.name == "serve")
    assert serve.status is Status.ATTENTION
    assert "Aldershot" in serve.detail
    assert report.predictions_written == 1, "the known fixture must still be priced"
    assert report.status.exit_code == 2

    priced = conn.execute(
        "SELECT f.division FROM predictions p JOIN fixtures f USING (fixture_id)"
    ).fetchall()
    assert [r[0] for r in priced] == ["E0"]


def test_an_unbridged_club_name_is_attention(conn, tmp_path, artifact, monkeypatch):
    monkeypatch.setattr(cycle, "latest_artifact", lambda *a, **k: artifact)
    path = tmp_path / "f.csv"
    path.write_text(
        feed("E0,15/08/2026,15:00,Nowhere United,Chelsea,2,3,4,2,3,4,2,2,0,2,2"),
        encoding="utf-8")

    report = run_cycle.run(conn, file=path, today=pd.Timestamp("2026-08-02"))
    sync = next(s for s in report.steps if s.name == "sync")
    assert sync.status is Status.ATTENTION
    assert "unbridged" in sync.detail


def test_a_stale_artifact_is_refrozen_rather_than_served(conn, artifact, monkeypatch):
    """A missed run must not leave last month's head pricing this week."""
    monkeypatch.setattr(cycle, "latest_artifact", lambda *a, **k: artifact)
    built = {}

    def fake_build(connection, *a, **k):
        built["called"] = True
        return artifact, None

    monkeypatch.setattr(run_cycle.cycle, "build_artifact", fake_build)
    # artifact.fitted_at is 2026-08-01; ask on 2026-09-01, well past REFIT_AFTER_DAYS
    report = run_cycle.run(conn, file=_empty_feed(), today=pd.Timestamp("2026-09-01"))

    assert built.get("called"), "a stale artifact must trigger a refit"
    assert "refroze" in next(s for s in report.steps if s.name == "serve").detail


def test_a_fresh_artifact_is_reused(conn, artifact, monkeypatch):
    monkeypatch.setattr(cycle, "latest_artifact", lambda *a, **k: artifact)
    monkeypatch.setattr(run_cycle.cycle, "build_artifact",
                        lambda *a, **k: pytest.fail("must not refit a fresh artifact"))
    report = run_cycle.run(conn, file=_empty_feed(), today=pd.Timestamp("2026-08-03"))
    assert "reused" in next(s for s in report.steps if s.name == "serve").detail


# --- step isolation --------------------------------------------------------


def test_a_dead_feed_does_not_stop_serving_or_grading(conn, artifact, monkeypatch):
    """The steps are independent on purpose; assert it rather than trust it."""
    monkeypatch.setattr(cycle, "latest_artifact", lambda *a, **k: artifact)

    def explode(*a, **k):
        raise OSError("feed unreachable")

    monkeypatch.setattr(run_cycle.fixture_sync, "fetch", explode)
    add_fixture(conn, "E0", 1, 2)

    report = run_cycle.run(conn, today=pd.Timestamp("2026-08-02"))
    names = {s.name: s.status for s in report.steps}
    assert names["sync"] is Status.FAILED
    assert names["serve"] is Status.OK, "serving must survive a dead feed"
    assert names["grade"] is Status.OK
    assert report.predictions_written == 1
    assert report.status.exit_code == 1


def test_a_failing_step_keeps_its_traceback(conn, monkeypatch):
    monkeypatch.setattr(run_cycle.fixture_sync, "fetch",
                        lambda *a, **k: (_ for _ in ()).throw(ValueError("boom")))
    monkeypatch.setattr(cycle, "latest_artifact", lambda *a, **k: None)
    monkeypatch.setattr(run_cycle.cycle, "build_artifact",
                        lambda *a, **k: (_stub_artifact(), None))
    report = run_cycle.run(conn, dry_run=True, today=pd.Timestamp("2026-08-02"))
    sync = next(s for s in report.steps if s.name == "sync")
    assert sync.status is Status.FAILED
    assert "ValueError: boom" in sync.detail
    assert sync.trace and "ValueError" in sync.trace


# --- the audit trail -------------------------------------------------------


def test_every_run_records_a_serving_state_row_even_when_it_fails(
        conn, artifact, monkeypatch):
    """A run that left no trace is indistinguishable from one that never started."""
    monkeypatch.setattr(cycle, "latest_artifact", lambda *a, **k: artifact)
    monkeypatch.setattr(run_cycle.fixture_sync, "fetch",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("down")))

    run_cycle.run(conn, today=pd.Timestamp("2026-08-02"))
    rows = conn.execute("SELECT * FROM serving_state").fetchall()
    assert len(rows) == 1
    assert rows[0]["rule_version"] == "book-off"
    assert rows[0]["bets_written"] == 0
    assert "sync=FAILED" in rows[0]["notes"]


def test_dry_run_writes_nothing(conn, artifact, monkeypatch):
    monkeypatch.setattr(cycle, "latest_artifact", lambda *a, **k: artifact)
    add_fixture(conn, "E0", 1, 2)
    run_cycle.run(conn, file=_empty_feed(), dry_run=True,
                  today=pd.Timestamp("2026-08-02"))
    assert conn.execute("SELECT COUNT(*) FROM predictions").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM serving_state").fetchone()[0] == 0


def test_rerunning_is_idempotent(conn, artifact, monkeypatch):
    """Task Scheduler retries. A second run must not double-price a fixture."""
    monkeypatch.setattr(cycle, "latest_artifact", lambda *a, **k: artifact)
    add_fixture(conn, "E0", 1, 2)
    for _ in range(2):
        run_cycle.run(conn, file=_empty_feed(), today=pd.Timestamp("2026-08-02"))
    assert conn.execute("SELECT COUNT(*) FROM predictions").fetchone()[0] == 1


def test_exit_codes_do_not_collide(conn):
    """ATTENTION must not be 1: a scheduler cannot distinguish 'look at this'
    from 'this broke' if both report the same failure code."""
    assert Status.OK.exit_code == 0
    assert Status.FAILED.exit_code == 1
    assert Status.ATTENTION.exit_code == 2
    assert Status.ATTENTION > Status.OK and Status.FAILED > Status.ATTENTION


# --- helpers ---------------------------------------------------------------


def _stub_artifact() -> Artifact:
    return Artifact(version="stub", fitted_at="2026-08-01T00:00:00", config="c",
                    teams=[], intercept=0.0, home=0.0, att=[], dfn=[],
                    n_train=0, corpus_digest="d")


def _empty_feed(tmp=[]):  # noqa: B006 -- module-local cache, not user-facing
    import tempfile
    from pathlib import Path
    if not tmp:
        path = Path(tempfile.mkdtemp()) / "empty.csv"
        path.write_text(feed(), encoding="utf-8")
        tmp.append(path)
    return tmp[0]


# --- the tip step ----------------------------------------------------------


def test_the_cycle_publishes_tips_for_the_fixtures_it_just_priced(
        conn, artifact, monkeypatch, tmp_path):
    """serve -> tips in one pass: a fixture priced this cycle is tippable this
    cycle, not next week.

    The floor is lowered to 0.50 because the stub artifact prices this fixture
    at about 0.53; at the shipped 0.55 it would fall back to double chance,
    which is correct behaviour and a less direct thing to assert. Patching the
    module constant also checks the cycle reads it rather than hard-coding one.
    """
    monkeypatch.setattr(cycle, "latest_artifact", lambda *a, **k: artifact)
    monkeypatch.setattr(run_cycle, "TIP_FLOOR", 0.50)
    add_fixture(conn, "E0", 1, 2)
    conn.execute("UPDATE fixtures SET max_h=1.5, max_d=4.0, max_a=7.0,"
                 " avg_h=1.45, avg_d=3.9, avg_a=6.8 WHERE 1=1")
    conn.commit()
    path = tmp_path / "feed.csv"
    path.write_text(feed(), encoding="utf-8")

    report = run_cycle.run(conn, file=path, today=FRESH_ARTIFACT_DAY)

    step = next(s for s in report.steps if s.name == "tips")
    published = conn.execute("SELECT COUNT(*) FROM tips").fetchone()[0]
    assert step.status is not Status.FAILED, step.detail
    assert published == 1, step.detail
    row = conn.execute("SELECT side, floor FROM tips").fetchone()
    assert row["side"] == "H"
    assert row["floor"] == 0.50, "the cycle must read TIP_FLOOR"


def test_a_fixture_below_the_floor_falls_back_rather_than_going_untipped(
        conn, artifact, monkeypatch, tmp_path):
    """v2 covers every fixture. The stub prices this at ~0.53, below the shipped
    0.55, so the cycle must publish a double chance rather than nothing -- v1
    published nothing here, and that 14.4% coverage is what B8 replaced."""
    monkeypatch.setattr(cycle, "latest_artifact", lambda *a, **k: artifact)
    add_fixture(conn, "E0", 1, 2)
    conn.execute("UPDATE fixtures SET max_h=1.9, max_d=3.6, max_a=4.2,"
                 " avg_h=1.85, avg_d=3.5, avg_a=4.1")
    conn.commit()
    path = tmp_path / "feed.csv"
    path.write_text(feed(), encoding="utf-8")

    report = run_cycle.run(conn, file=path, today=FRESH_ARTIFACT_DAY)

    step = next(s for s in report.steps if s.name == "tips")
    assert step.status is Status.OK, step.detail
    assert conn.execute("SELECT COUNT(*) FROM predictions").fetchone()[0] == 1
    side = conn.execute("SELECT side FROM tips").fetchone()[0]
    assert side in {"1X", "X2", "12"}, f"expected a fallback, got {side}"


def test_grading_does_not_chase_results_for_unplayed_fixtures(conn, monkeypatch):
    """v2 tips every fixture the moment it is priced, so without a date bound
    the cycle would pull a results CSV for every upcoming match, every run, all
    season -- fetching files that cannot contain the result yet."""
    add_fixture(conn, "E0", 1, 2, date="2099-01-01")
    fixture_id = conn.execute("SELECT fixture_id FROM fixtures").fetchone()[0]
    conn.execute(
        "INSERT INTO predictions (prediction_id, fixture_id, model_version,"
        " information_set, served_at, lam_h, lam_a, p_home, p_draw, p_away,"
        " p_over25, p_under25) VALUES (1, ?, 'v1', 'pre_close', '2026-08-10',"
        " 1.5, 1.0, 0.62, 0.24, 0.14, 0.5, 0.5)", (fixture_id,))
    conn.execute(
        "INSERT INTO tips (prediction_id, fixture_id, side, model_prob, floor,"
        " best_price, avg_price, rule_version) VALUES (1, ?, 'H', 0.62, 0.55,"
        " 1.6, 1.5, 'confidence-v2')", (fixture_id,))
    conn.commit()

    def explode(*a, **k):
        raise AssertionError("must not fetch results for an unplayed fixture")

    monkeypatch.setattr(run_cycle.csv_grader, "fetch", explode)

    step = run_cycle.step_grade(conn, dry_run=True)

    assert step.status is Status.OK
    assert step.detail == "nothing unsettled"


def test_grading_still_runs_when_only_tips_are_unsettled(conn, monkeypatch):
    """The book is off, so `paper_bets` is always empty. Before the tip step
    shipped, `step_grade` short-circuited on that and would have left every tip
    ungraded forever while reporting success."""
    add_fixture(conn, "E0", 1, 2, date="2020-01-01")
    fixture_id = conn.execute("SELECT fixture_id FROM fixtures").fetchone()[0]
    conn.execute(
        "INSERT INTO predictions (prediction_id, fixture_id, model_version,"
        " information_set, served_at, lam_h, lam_a, p_home, p_draw, p_away,"
        " p_over25, p_under25) VALUES (1, ?, 'v1', 'pre_close', '2026-08-10',"
        " 1.5, 1.0, 0.62, 0.24, 0.14, 0.5, 0.5)", (fixture_id,))
    conn.execute(
        "INSERT INTO tips (prediction_id, fixture_id, side, model_prob, floor,"
        " best_price, avg_price, rule_version) VALUES (1, ?, 'H', 0.62, 0.55,"
        " 1.6, 1.5, 'confidence-v2')", (fixture_id,))
    conn.commit()

    seen = {}

    def fake_fetch(division, season, **kwargs):
        seen["called"] = True
        return ""

    monkeypatch.setattr(run_cycle.csv_grader, "fetch", fake_fetch)
    monkeypatch.setattr(run_cycle.csv_grader, "parse_results", lambda text: [])

    step = run_cycle.step_grade(conn, dry_run=True)

    assert seen.get("called"), "an unsettled tip must pull the results feed"
    assert step.status is not Status.FAILED, step.detail
