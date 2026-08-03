"""Read-only serving API.

    uvicorn api.main:app --reload

Every endpoint reads what the cycle already wrote. Nothing here fits a model,
prices a fixture, or places a bet: predictions are produced by
`engine.serve.cycle` on a weekly schedule and stored, so a request can never
change what was served. That is what makes a stored prediction auditable --
"what did we say, when, from which artifact" has one answer, not one per
request.

Probabilities are served as-is and flagged `calibrated: false` until P3 exists.
Marking that on the wire rather than in a document is deliberate: a consumer
that treats raw pmf output as calibrated will be wrong in level, and the
response should say so.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from engine import db
from engine.seasons import SERVED_DIVISIONS

app = FastAPI(
    title="baba.vanga.premier",
    description="Match prediction engine for the English professional divisions.",
    version="0.1.0",
)

# The frontend is served separately in development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


def get_conn() -> sqlite3.Connection:
    conn = db.connect()
    try:
        yield conn
    finally:
        conn.close()


def _rows(conn, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(sql, params)]


@app.get("/health")
def health(conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    """Liveness plus enough state to tell whether the cycle is actually running."""
    counts = {
        table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in ("fixtures", "predictions", "paper_bets", "clv_grades")
    }
    latest = conn.execute(
        "SELECT model_version, fitted_at, config_label FROM model_runs"
        " ORDER BY created_at DESC LIMIT 1"
    ).fetchone()
    return {
        "status": "ok",
        "counts": counts,
        "model": dict(latest) if latest else None,
        "calibrated": False,
    }


@app.get("/fixtures")
def fixtures(
    division: str | None = Query(None, description="E0 | E1 | E2 | E3"),
    conn: sqlite3.Connection = Depends(get_conn),
) -> list[dict]:
    if division and division not in SERVED_DIVISIONS:
        raise HTTPException(400, f"unknown division {division!r}")
    clause = " WHERE f.division = ?" if division else ""
    return _rows(
        conn,
        "SELECT f.fixture_id, f.division, f.match_date, f.kickoff_time,"
        " h.canonical_name AS home_team, a.canonical_name AS away_team,"
        " f.avg_h, f.avg_d, f.avg_a, f.avg_over25, f.avg_under25"
        " FROM fixtures f"
        " JOIN teams h ON h.team_id = f.home_team_id"
        " JOIN teams a ON a.team_id = f.away_team_id"
        f"{clause} ORDER BY f.match_date, f.kickoff_time, f.fixture_id",
        (division,) if division else (),
    )


@app.get("/predictions")
def predictions(
    division: str | None = Query(None),
    conn: sqlite3.Connection = Depends(get_conn),
) -> list[dict]:
    """The most recent prediction per fixture, with the price beside it.

    One row per fixture rather than the full history: the history is kept in
    the table and is what makes the record auditable, but a client asking
    "what do we think" wants the current answer.
    """
    clause = " AND f.division = ?" if division else ""
    return _rows(
        conn,
        "SELECT p.prediction_id, p.fixture_id, p.served_at, p.model_version,"
        " p.information_set, p.lam_h, p.lam_a, p.p_home, p.p_draw, p.p_away,"
        " p.p_over25, p.p_under25, p.calibrated,"
        " f.division, f.match_date, f.kickoff_time,"
        " f.avg_h, f.avg_d, f.avg_a, f.avg_over25, f.avg_under25,"
        " h.canonical_name AS home_team, a.canonical_name AS away_team"
        " FROM predictions p"
        " JOIN fixtures f ON f.fixture_id = p.fixture_id"
        " JOIN teams h ON h.team_id = f.home_team_id"
        " JOIN teams a ON a.team_id = f.away_team_id"
        " WHERE p.prediction_id = ("
        "   SELECT prediction_id FROM predictions q WHERE q.fixture_id = p.fixture_id"
        "   ORDER BY q.served_at DESC, q.prediction_id DESC LIMIT 1)"
        f"{clause} ORDER BY f.match_date, f.kickoff_time, f.fixture_id",
        (division,) if division else (),
    )


@app.get("/book")
def book(
    settled: bool | None = Query(None, description="filter by settlement state"),
    conn: sqlite3.Connection = Depends(get_conn),
) -> list[dict]:
    """The paper book, with CLV attached where it has been graded."""
    clause = ""
    if settled is True:
        clause = " WHERE b.settled_at IS NOT NULL"
    elif settled is False:
        clause = " WHERE b.settled_at IS NULL"
    return _rows(
        conn,
        "SELECT b.*, f.division, f.match_date,"
        " h.canonical_name AS home_team, a.canonical_name AS away_team,"
        " g.clv, g.clv_pct, g.close_price, g.close_source"
        " FROM paper_bets b"
        " JOIN fixtures f ON f.fixture_id = b.fixture_id"
        " JOIN teams h ON h.team_id = f.home_team_id"
        " JOIN teams a ON a.team_id = f.away_team_id"
        " LEFT JOIN clv_grades g ON g.bet_id = b.bet_id"
        f"{clause} ORDER BY f.match_date DESC, b.bet_id DESC",
    )


@app.get("/performance")
def performance(conn: sqlite3.Connection = Depends(get_conn)) -> list[dict]:
    """Per-population running totals.

    **CLV is the headline, ROI is confirmatory, hit rate is a diagnostic only**
    (SPEC §5.1). They are returned in that order and the frontend shows them in
    that order, because on a few hundred bets ROI is mostly noise and hit rate
    says almost nothing about whether the prices were good.
    """
    return _rows(
        conn,
        "SELECT f.division, b.market,"
        " COUNT(*) AS bets,"
        " AVG(g.clv) AS mean_clv,"
        " SUM(CASE WHEN g.clv > 0 THEN 1 ELSE 0 END) * 1.0 / NULLIF(COUNT(g.clv), 0)"
        "   AS beat_close_rate,"
        " SUM(b.pnl) AS pnl,"
        " SUM(b.pnl) / NULLIF(SUM(CASE WHEN b.settled_at IS NOT NULL"
        "   THEN b.stake ELSE 0 END), 0) AS roi,"
        " SUM(CASE WHEN b.outcome = 'win' THEN 1 ELSE 0 END) * 1.0"
        "   / NULLIF(SUM(CASE WHEN b.settled_at IS NOT NULL THEN 1 ELSE 0 END), 0)"
        "   AS hit_rate"
        " FROM paper_bets b"
        " JOIN fixtures f ON f.fixture_id = b.fixture_id"
        " LEFT JOIN clv_grades g ON g.bet_id = b.bet_id"
        " GROUP BY f.division, b.market ORDER BY f.division, b.market",
    )
