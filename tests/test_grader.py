"""Result grading and CLV.

The two rules that must not be swapped, both pinned here:

  bet decision  -> RAW 1/odds        (vig-inclusive; the bar to clear)
  CLV           -> DE-VIGGED probs   (two market opinions, margin removed)

Using 1/odds for CLV builds the bookmaker's margin into every grade and makes a
flat book read as a winner. That error was live in this module during
development, which is why it gets an explicit test rather than a comment.
"""

from __future__ import annotations

import urllib.error

import pytest

from engine import db
from services import csv_grader

HEADER = ("Div,Date,HomeTeam,AwayTeam,FTHG,FTAG,FTR,"
          "AvgH,AvgD,AvgA,Avg>2.5,Avg<2.5,"
          "PSCH,PSCD,PSCA,AvgCH,AvgCD,AvgCA,AvgC>2.5,AvgC<2.5")

# Arsenal beat Chelsea 2-1. Home closed SHORTER than we took it (1.75 vs 1.90),
# so the market moved toward our side: positive CLV.
ARSENAL_WIN = ("E0,15/08/2026,Arsenal,Chelsea,2,1,H,"
               "1.90,3.80,4.20,1.95,1.90,"
               "1.75,3.90,4.80,1.78,3.85,4.70,1.90,1.95")


def results(*rows: str) -> str:
    return "\n".join([HEADER, *rows]) + "\n"


@pytest.fixture
def conn(database_url):
    connection = db.connect(database_url)
    for i, name in enumerate(["Arsenal", "Chelsea"], start=1):
        connection.execute("INSERT INTO teams (team_id, canonical_name) VALUES (%s, %s)",
                           (i, name))
    connection.execute(
        "INSERT INTO fixtures (fixture_id, division, match_date, home_team_id,"
        " away_team_id, avg_h, avg_d, avg_a, avg_over25, avg_under25, source_file)"
        " VALUES (1, 'E0', '2026-08-15', 1, 2, 1.90, 3.80, 4.20, 1.95, 1.90, 'test')")
    connection.execute(
        "INSERT INTO predictions (prediction_id, fixture_id, model_version,"
        " information_set, lam_h, lam_a, p_home, p_draw, p_away, p_over25, p_under25)"
        " VALUES (1, 1, 'v1', 'pre_close', 1.9, 0.9, 0.62, 0.20, 0.18, 0.55, 0.45)")
    connection.commit()
    return connection


def _bet(conn, market="1x2", side="H", price=1.90):
    conn.execute(
        "INSERT INTO paper_bets (prediction_id, fixture_id, market, side, price,"
        " price_source, model_prob, breakeven_prob, edge, expected_value, stake,"
        " rule_version) VALUES (1, 1, %s, %s, %s, 'avg', 0.62, %s, %s, %s, 1.0, 'test')",
        (market, side, price, 1 / price, 0.62 - 1 / price, 0.62 * price - 1))
    conn.commit()


# --- settlement ------------------------------------------------------------


def test_a_winning_bet_settles_with_the_right_pnl(conn):
    _bet(conn)
    report = csv_grader.grade(conn, csv_grader.parse_results(results(ARSENAL_WIN)))
    assert report.settled == 1

    row = conn.execute("SELECT * FROM paper_bets").fetchone()
    assert row["outcome"] == "win"
    assert row["pnl"] == pytest.approx(0.90)      # stake 1.0 at 1.90
    assert row["settled_at"] is not None


def test_a_losing_bet_settles_at_minus_stake(conn):
    _bet(conn, side="A")
    csv_grader.grade(conn, csv_grader.parse_results(results(ARSENAL_WIN)))
    row = conn.execute("SELECT * FROM paper_bets").fetchone()
    assert row["outcome"] == "lose"
    assert row["pnl"] == pytest.approx(-1.0)


def test_over_under_settles_on_the_total_not_the_result(conn):
    _bet(conn, market="ou25", side="over", price=1.95)   # 2-1 = 3 goals, over wins
    csv_grader.grade(conn, csv_grader.parse_results(results(ARSENAL_WIN)))
    assert db.scalar(conn, "SELECT outcome FROM paper_bets") == "win"

    conn.execute("DELETE FROM clv_grades")
    conn.execute("UPDATE paper_bets SET settled_at=NULL, side='under', outcome=NULL")
    conn.commit()
    csv_grader.grade(conn, csv_grader.parse_results(results(ARSENAL_WIN)))
    assert db.scalar(conn, "SELECT outcome FROM paper_bets") == "lose"


def test_grading_does_not_overwrite_the_bet_that_was_placed(conn):
    """Grading columns are written beside the bet. The price and probability
    that justified it must survive whatever happened next."""
    _bet(conn)
    csv_grader.grade(conn, csv_grader.parse_results(results(ARSENAL_WIN)))
    row = conn.execute("SELECT * FROM paper_bets").fetchone()
    assert row["price"] == 1.90
    assert row["model_prob"] == 0.62
    assert row["breakeven_prob"] == pytest.approx(1 / 1.90)


# --- CLV -------------------------------------------------------------------


def test_clv_uses_devigged_probabilities_not_raw_one_over_odds(conn):
    """The error this module shipped with, pinned.

    Bet at Avg 1.90/3.80/4.20 (overround ~5%), closing Pinnacle 1.75/3.90/4.80.
    Raw 1/price would put bet_prob at 0.5263. De-vigged it is meaningfully
    lower, because the margin is removed. If bet_prob ever equals 1/price
    again, the margin is back in every CLV figure.
    """
    _bet(conn)
    csv_grader.grade(conn, csv_grader.parse_results(results(ARSENAL_WIN)))
    grade = conn.execute("SELECT * FROM clv_grades").fetchone()

    assert grade["bet_prob"] != pytest.approx(1 / 1.90)
    assert grade["bet_prob"] < 1 / 1.90
    assert grade["close_prob"] != pytest.approx(1 / 1.75)
    assert grade["close_prob"] < 1 / 1.75
    # Both are genuine probabilities, so both sit strictly inside (0, 1).
    assert 0.0 < grade["bet_prob"] < 1.0
    assert 0.0 < grade["close_prob"] < 1.0


def test_clv_is_positive_when_the_market_moves_toward_our_side(conn):
    """We took 1.90; it closed at 1.75. Being early on a shortening price is
    exactly what CLV is meant to detect."""
    _bet(conn)
    csv_grader.grade(conn, csv_grader.parse_results(results(ARSENAL_WIN)))
    grade = conn.execute("SELECT * FROM clv_grades").fetchone()
    assert grade["clv"] > 0
    assert grade["clv_pct"] == pytest.approx(1.90 / 1.75 - 1)
    assert grade["close_source"] == "PSC"


def test_clv_is_negative_when_the_price_drifts_out(conn):
    drifted = ARSENAL_WIN.replace("1.75,3.90,4.80", "2.20,3.60,3.40")
    _bet(conn)
    csv_grader.grade(conn, csv_grader.parse_results(results(drifted)))
    grade = conn.execute("SELECT * FROM clv_grades").fetchone()
    assert grade["clv"] < 0
    assert grade["clv_pct"] < 0


def test_pinnacle_is_preferred_and_the_source_is_recorded(conn):
    """Pinnacle and the market average are different books with different
    margins. Blending them would make a CLV series that drifts with coverage."""
    _bet(conn)
    csv_grader.grade(conn, csv_grader.parse_results(results(ARSENAL_WIN)))
    assert db.scalar(conn, "SELECT close_source FROM clv_grades") == "PSC"

    no_pinnacle = ARSENAL_WIN.replace("1.75,3.90,4.80", ",,")
    conn.execute("DELETE FROM clv_grades")
    conn.execute("UPDATE paper_bets SET settled_at=NULL")
    conn.commit()
    csv_grader.grade(conn, csv_grader.parse_results(results(no_pinnacle)))
    assert db.scalar(conn, "SELECT close_source FROM clv_grades") == "AvgC"


def test_a_bet_is_graded_only_once(conn):
    _bet(conn)
    first = csv_grader.grade(conn, csv_grader.parse_results(results(ARSENAL_WIN)))
    conn.execute("UPDATE paper_bets SET settled_at = NULL")
    conn.commit()
    csv_grader.grade(conn, csv_grader.parse_results(results(ARSENAL_WIN)))
    assert first.graded == 1
    assert db.scalar(conn, "SELECT COUNT(*) FROM clv_grades") == 1


# --- plumbing --------------------------------------------------------------


def test_dry_run_settles_nothing(conn):
    _bet(conn)
    report = csv_grader.grade(conn, csv_grader.parse_results(results(ARSENAL_WIN)),
                              dry_run=True)
    assert report.settled == 1
    assert db.scalar(conn, "SELECT settled_at FROM paper_bets") is None
    assert db.scalar(conn, "SELECT COUNT(*) FROM clv_grades") == 0


def test_a_result_with_no_matching_fixture_is_ignored(conn):
    _bet(conn)
    other = ARSENAL_WIN.replace("15/08/2026", "22/08/2026")
    report = csv_grader.grade(conn, csv_grader.parse_results(results(other)))
    assert report.settled == 0


def _tip(conn, side="H", outcome=None):
    conn.execute(
        "INSERT INTO tips (prediction_id, fixture_id, side, model_prob, floor,"
        " rule_version, settled_at, outcome) VALUES (1, 1, %s, 0.62, 0.55, 'test', %s, %s)",
        (side, "2026-08-16" if outcome else None, outcome))
    conn.commit()


def test_a_tip_settled_elsewhere_that_this_feed_agrees_with_is_left_alone(conn):
    """`services/bbc_results.py` settles at full time, days before this file
    exists. Arsenal won; the tip says win; nothing to report, nothing rewritten."""
    _tip(conn, "H", outcome="win")
    report = csv_grader.grade(conn, csv_grader.parse_results(results(ARSENAL_WIN)))
    assert report.disagreed == [] and report.tips_settled == 0
    assert db.scalar(conn, "SELECT settled_at FROM tips") == "2026-08-16"


def test_a_tip_settled_elsewhere_that_this_feed_contradicts_is_named_not_rewritten(conn):
    """The timely source said lose; the authority says Arsenal won. The record
    is not silently corrected -- the site already showed the call -- but the
    disagreement is surfaced, because a wrong score in the timely source is
    the failure that would otherwise be invisible."""
    _tip(conn, "H", outcome="lose")
    report = csv_grader.grade(conn, csv_grader.parse_results(results(ARSENAL_WIN)))
    tip_id = db.scalar(conn, "SELECT tip_id FROM tips")
    assert report.disagreed == [tip_id]
    assert db.scalar(conn, "SELECT outcome FROM tips") == "lose"
    assert "different outcome" in report.describe()


def test_season_path_follows_the_football_season_not_the_calendar_year():
    assert csv_grader.season_for("2026-08-15") == "2627"
    assert csv_grader.season_for("2027-05-20") == "2627"
    assert csv_grader.season_for("2026-06-30") == "2526"


# --- the wire ---------------------------------------------------------------
#
# Every test above hands `parse_results` a string built in Python, so none of
# them go through `fetch`. That is how a BOM sat in the feed for two seasons
# making `division` None on every row -- 552 results fetched, 0 graded, exit 0
# -- without a single test going red. These four cover the decode and the two
# ways football-data says "not published yet".


class _Response:
    """The parts of an `HTTPResponse` that `fetch` touches."""

    def __init__(self, body: bytes, url: str):
        self._body, self.url = body, url

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self) -> bytes:
        return self._body


def _serve(monkeypatch, body: bytes, *, landing: str | None = None):
    def fake_urlopen(url, timeout=None):
        return _Response(body, landing or url)

    monkeypatch.setattr(csv_grader.urllib.request, "urlopen", fake_urlopen)


def _refuse(monkeypatch, code: int, reason: str):
    def fake_urlopen(url, timeout=None):
        raise urllib.error.HTTPError(url, code, reason, {}, None)

    monkeypatch.setattr(csv_grader.urllib.request, "urlopen", fake_urlopen)


def test_the_feeds_utf8_bom_does_not_swallow_the_division_column(monkeypatch):
    """Decoded as cp1252 the BOM renames `Div` to `ï»¿Div`, so every row parses
    with `division` None and is dropped by the caller's division filter. The
    grader settles nothing and reports success."""
    _serve(monkeypatch, b"\xef\xbb\xbf" + results(ARSENAL_WIN).encode("cp1252"))

    rows = csv_grader.parse_results(csv_grader.fetch("E0", "2627"))

    assert [r["division"] for r in rows] == ["E0"]


def test_a_season_file_that_is_not_published_yet_is_not_a_crash(monkeypatch):
    """The first weeks of a season: the directory exists, the division's file
    does not, and mod_speling answers 300 rather than 404."""
    _refuse(monkeypatch, 300, "Multiple Choices")

    with pytest.raises(csv_grader.ResultsNotPublished):
        csv_grader.fetch("E1", "2627")


def test_a_redirect_onto_another_division_is_refused(monkeypatch):
    """mod_speling answers a single near-miss with a 301 that urllib follows,
    so asking for the 2026-27 Premier League returns the National League with a
    200. Grading E0's fixtures against EC's results is the failure to avoid."""
    _serve(monkeypatch, results(ARSENAL_WIN).encode("cp1252"),
           landing="https://www.football-data.co.uk/mmz4281/2627/EC.csv")

    with pytest.raises(csv_grader.ResultsNotPublished):
        csv_grader.fetch("E0", "2627")


def test_a_real_http_failure_is_still_a_failure(monkeypatch):
    """`ResultsNotPublished` is one narrow condition. A dead server must not be
    laundered into 'the season has not started'."""
    _refuse(monkeypatch, 500, "Internal Server Error")

    with pytest.raises(urllib.error.HTTPError):
        csv_grader.fetch("E0", "2526")
