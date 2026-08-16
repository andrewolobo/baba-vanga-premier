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

**The `/tips` endpoints are the customer-facing product** (`BACKLOG.md` B6) and
are held to a stricter rule than the rest of this module: `/tips/record` returns
strike rate and **no profit or loss at all**, even though the `tips` table
carries `pnl_best` and `pnl_avg`. `engine/eval/tips.py` measured the two claims
coming apart -- the strike rate is honest, the return at prices a customer
actually gets is not distinguishable from zero and is negative at every sellable
setting. Leaving P&L off the wire means the surface cannot advertise a return by
accident, which is the failure B7 exists to prevent. The columns stay in the
database, where the record is kept; they are simply not what this API publishes.
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
    """One connection per request.

    `check_same_thread=False` because FastAPI may open this dependency on a
    different threadpool worker from the one that runs the endpoint -- see
    `engine.db.connect`. Without it, any page fetching two endpoints at once
    fails intermittently with `SQLite objects created in a thread can only be
    used in that same thread`.
    """
    conn = db.connect(check_same_thread=False)
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


#: Every tip endpoint reads the same joined shape. Kept as one string so the
#: upcoming list, the settled list and the record cannot drift apart in which
#: fixture a tip is attached to.
TIP_SELECT = """
    SELECT t.tip_id, t.published_at, t.side, t.model_prob, t.floor, t.ceiling,
           t.best_price, t.avg_price, t.rule_version,
           t.settled_at, t.outcome,
           f.fixture_id, f.division, f.match_date, f.kickoff_time,
           h.canonical_name AS home_team, a.canonical_name AS away_team
    FROM tips t
    JOIN fixtures f ON f.fixture_id = t.fixture_id
    JOIN teams h ON h.team_id = f.home_team_id
    JOIN teams a ON a.team_id = f.away_team_id
"""


def _check_division(division: str | None) -> None:
    if division and division not in SERVED_DIVISIONS:
        raise HTTPException(400, f"unknown division {division!r}")


@app.get("/tips")
def tips(
    division: str | None = Query(None, description="E0 | E1 | E2 | E3"),
    conn: sqlite3.Connection = Depends(get_conn),
) -> list[dict]:
    """The published tip list for matches that have not been played.

    One tip per fixture, which the schema enforces rather than this query
    (`UNIQUE (fixture_id, rule_version)`, migration 003): a tipster showing two
    contradictory calls for one match has no defensible strike rate.

    `side` is one of `H`, `A`, `1X`, `X2`, `12` -- the confidence rule steps
    down to a double chance when no outright clears its floor, so **most calls
    are unions rather than a named team**. A surface that renders only `H`/`A`
    will silently drop the majority of the product.

    `best_price` and `avg_price` are carried for reporting and took no part in
    selection. On a double chance they are *derived* from the 1X2 legs and are
    an **upper bound** on what a customer could get, because real double-chance
    markets carry their own margin.
    """
    _check_division(division)
    clause = " WHERE t.settled_at IS NULL AND f.match_date >= date('now')"
    if division:
        clause += " AND f.division = ?"
    return _rows(
        conn,
        TIP_SELECT + clause
        + " ORDER BY f.match_date, f.kickoff_time, f.fixture_id",
        (division,) if division else (),
    )


@app.get("/tips/results")
def tip_results(
    division: str | None = Query(None),
    limit: int = Query(60, ge=1, le=500),
    conn: sqlite3.Connection = Depends(get_conn),
) -> list[dict]:
    """Settled tips, most recently played first.

    Outcome only. The scoreline is not here because it is not stored: the
    grader settles a tip from the result it reads and does not keep the goals,
    so an endpoint claiming to return one would be inventing it.
    """
    _check_division(division)
    clause = " WHERE t.settled_at IS NOT NULL"
    params: tuple = ()
    if division:
        clause += " AND f.division = ?"
        params = (division,)
    return _rows(
        conn,
        TIP_SELECT + clause + " ORDER BY f.match_date DESC, t.tip_id DESC LIMIT ?",
        params + (limit,),
    )


#: Strike rate and volume. **No P&L column appears here by design** -- see the
#: module docstring. `void` is excluded from the denominator rather than counted
#: as a loss, which is why the graded count is not `settled_at IS NOT NULL`.
#:
#: `{where}` is the rule-version predicate. **The headline is one rule's record,
#: never a pool across versions** (`BACKLOG.md` B16): `services/run_cycle.py`
#: promises that changing the floor means bumping `tips.RULE_VERSION` so two
#: products are never averaged into one strike rate, and this is where that
#: promise is kept. Older versions are still reported, grouped, in `by_rule`.
RECORD = """
    SELECT {group}
           COUNT(*) AS published,
           SUM(CASE WHEN t.outcome IN ('win', 'lose') THEN 1 ELSE 0 END) AS graded,
           SUM(CASE WHEN t.outcome = 'win' THEN 1 ELSE 0 END) AS won,
           SUM(CASE WHEN t.outcome = 'win' THEN 1 ELSE 0 END) * 1.0
             / NULLIF(SUM(CASE WHEN t.outcome IN ('win', 'lose')
                               THEN 1 ELSE 0 END), 0) AS strike_rate,
           SUM(CASE WHEN t.settled_at IS NULL AND f.match_date >= date('now')
                    THEN 1 ELSE 0 END) AS upcoming,
           COUNT(DISTINCT CASE WHEN t.outcome IN ('win', 'lose')
                          THEN strftime('%Y-%W', f.match_date) END) AS matchweeks
    FROM tips t
    JOIN fixtures f ON f.fixture_id = t.fixture_id
    {where}
"""


@app.get("/tips/record")
def tip_record(conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    """How the published tips have actually done.

    **Strike rate is the whole claim, and this endpoint returns nothing else
    that could be mistaken for one.** No profit, no ROI, no streak: the rule is
    sold on how often it is right, and `engine/eval/tips.py` measured that the
    return at customer prices is negative at every sellable setting with no
    interval excluding zero.

    `strike_rate` is **null**, never zero, until something has been graded. A
    zero would read as "we get everything wrong" rather than "nothing has been
    played yet", and opening weekend is exactly when that gets screenshotted.

    **The headline and `by_division` are the current rule's record only** --
    the rule of the most recently published tip, which is what `rule` names.
    Derived from the table rather than imported from `engine.serve.tips`, so
    the API keeps reading what the cycle wrote and never loads the serving
    stack; the two agree because the cycle writes `RULE_VERSION` on every tip.
    On the day a rule is bumped the headline resets to null and rebuilds as
    the new rule's tips grade. **`by_rule` carries every version ever
    published**, so the earlier record is reported beside the current one
    rather than pooled into it or dropped (owner decision, `BACKLOG.md` B16).
    """
    rule = conn.execute(
        "SELECT rule_version, floor, ceiling FROM tips"
        " ORDER BY tip_id DESC LIMIT 1").fetchone()
    current = rule["rule_version"] if rule else None
    scoped = "WHERE t.rule_version = ?"
    overall = dict(conn.execute(
        RECORD.format(group="", where=scoped), (current,)).fetchone())
    by_division = _rows(
        conn, RECORD.format(group="f.division,", where=scoped)
        + " GROUP BY f.division ORDER BY f.division",
        (current,))
    by_rule = _rows(
        conn, RECORD.format(group="t.rule_version,", where="")
        + " GROUP BY t.rule_version ORDER BY MAX(t.tip_id) DESC")
    return {
        **overall,
        "by_division": by_division,
        "by_rule": by_rule,
        "rule": dict(rule) if rule else None,
        # Stated on the wire so a surface cannot present the strike rate as a
        # return without ignoring a field it was handed.
        "return_supported": False,
    }


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
