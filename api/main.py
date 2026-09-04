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

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from scipy import stats

from engine import db
from engine.seasons import SERVED_DIVISIONS
from engine.serve import parlay as parlay_rule

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


def get_conn() -> db.Connection:
    """One connection per request, autocommit.

    Autocommit because this API only reads: psycopg would otherwise open a
    transaction on the first SELECT and hold it until the connection closed,
    leaving every request *idle in transaction* for its whole life. FastAPI
    runs this dependency's setup, the endpoint and the teardown on whichever
    threadpool workers are free; psycopg connections are not thread-bound, so
    that hand-off needs nothing special here.
    """
    conn = db.connect(autocommit=True)
    try:
        yield conn
    finally:
        conn.close()


def _rows(conn, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(sql, params)]


@app.get("/health")
def health(conn: db.Connection = Depends(get_conn)) -> dict:
    """Liveness plus enough state to tell whether the cycle is actually running."""
    counts = {
        table: db.scalar(conn, f"SELECT COUNT(*) FROM {table}")
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
    conn: db.Connection = Depends(get_conn),
) -> list[dict]:
    if division and division not in SERVED_DIVISIONS:
        raise HTTPException(400, f"unknown division {division!r}")
    clause = " WHERE f.division = %s" if division else ""
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
    conn: db.Connection = Depends(get_conn),
) -> list[dict]:
    """The most recent prediction per fixture, with the price beside it.

    One row per fixture rather than the full history: the history is kept in
    the table and is what makes the record auditable, but a client asking
    "what do we think" wants the current answer.
    """
    clause = " AND f.division = %s" if division else ""
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
#:
#: The `p_*` columns are **the model's view behind the call** (`BACKLOG.md`
#: B22): the three outright probabilities and the three double-chance sums,
#: read from the prediction row the tip was made from -- `t.prediction_id`,
#: **not** the fixture's latest prediction. A tip is never revised, so the
#: numbers shown beside it must be the ones it was published from; joining on
#: the fixture would show a fresher artifact than the call and the two could
#: disagree. The sums are formed here rather than in the browser because the
#: frontend displays stored decisions and never computes a probability
#: (`web/src/lib/api.js`). They are context, not calls: only `side` is graded.
#: `lam_h`/`lam_a` ride along for `_with_handicap`, which adds the two +1.5
#: probabilities the same way.
TIP_SELECT = """
    SELECT t.tip_id, t.published_at, t.side, t.model_prob, t.floor, t.ceiling,
           t.best_price, t.avg_price, t.rule_version,
           t.settled_at, t.outcome, t.fthg, t.ftag,
           f.fixture_id, f.division, f.match_date, f.kickoff_time,
           h.canonical_name AS home_team, a.canonical_name AS away_team,
           p.lam_h, p.lam_a, p.p_home, p.p_draw, p.p_away,
           p.p_home + p.p_draw AS p_1x,
           p.p_away + p.p_draw AS p_x2,
           p.p_home + p.p_away AS p_12
    FROM tips t
    JOIN fixtures f ON f.fixture_id = t.fixture_id
    JOIN teams h ON h.team_id = f.home_team_id
    JOIN teams a ON a.team_id = f.away_team_id
    JOIN predictions p ON p.prediction_id = t.prediction_id
"""

#: Goals per side in the score matrix -- `engine.eval.dispersion.MAX_GOALS`,
#: restated rather than imported so this module keeps reading what the cycle
#: wrote without loading the measurement stack (`engine.eval` pulls in the
#: ledger and store). `tests/test_api.py` pins the two against each other.
MAX_GOALS = 15


def _with_handicap(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Add `p_h15` / `p_a15` -- P(home loses by at most 1) and P(away loses by
    at most 1) -- to each tip, from the stored lambdas.

    `confidence-v3` chooses among `1X`, `X2`, `12` and the underdog +1.5, and
    the handicap probability lives nowhere but in the stored lambdas:
    `predictions` keeps them raw for exactly this reason (migration 002), and
    `engine.serve.tips.select` reads the same marginal off the same pmf --
    independent Poisson on 0..MAX_GOALS, no Dixon-Coles tau -- so the figure
    shown behind a call is the one the rule compared. Not a fit and not a
    price: a marginal of what was served. Both sides are returned and the
    browser picks the underdog's, as the rule does; the favourite's +1.5 is a
    near-certainty that is on no menu (`PRODUCT.md` §3).
    """
    if not rows:
        return rows
    lam_h = np.array([r["lam_h"] for r in rows], dtype=float)
    lam_a = np.array([r["lam_a"] for r in rows], dtype=float)
    k = np.arange(MAX_GOALS + 1)
    joint = (stats.poisson.pmf(k[None, :], lam_h[:, None])[:, :, None]
             * stats.poisson.pmf(k[None, :], lam_a[:, None])[:, None, :])
    margin = k[:, None] - k[None, :]            # home goals minus away goals
    home_by_2 = joint[:, margin >= 2].sum(axis=1)
    away_by_2 = joint[:, margin <= -2].sum(axis=1)
    for row, h, a in zip(rows, 1.0 - away_by_2, 1.0 - home_by_2):
        row["p_h15"], row["p_a15"] = float(h), float(a)
    return rows


def _check_division(division: str | None) -> None:
    if division and division not in SERVED_DIVISIONS:
        raise HTTPException(400, f"unknown division {division!r}")


@app.get("/tips")
def tips(
    division: str | None = Query(None, description="E0 | E1 | E2 | E3"),
    conn: db.Connection = Depends(get_conn),
) -> list[dict]:
    """The published tip list for matches that have not been played.

    One tip per fixture, which the schema enforces rather than this query
    (`UNIQUE (fixture_id, rule_version)`, migration 003): a tipster showing two
    contradictory calls for one match has no defensible strike rate.

    `side` is one of `H`, `A`, `1X`, `X2`, `12`, `H+1.5`, `A+1.5` -- the
    confidence rule steps down to a double chance or the +1.5 handicap when no
    outright clears its floor (`confidence-v3`, `BACKLOG.md` B21), so **most
    calls are unions or handicaps rather than an outright**. A surface that
    renders only `H`/`A` will silently drop the majority of the product.
    `H+1.5` means the home side with a 1.5-goal start (wins unless home loses
    by 2 or more); `A+1.5` the mirror. Handicap tips carry NULL prices -- the
    feed has no +1.5 line and none is derivable from the 1X2 legs.

    `best_price` and `avg_price` are carried for reporting and took no part in
    selection. On a double chance they are *derived* from the 1X2 legs and are
    an **upper bound** on what a customer could get, because real double-chance
    markets carry their own margin.

    `p_home`, `p_draw`, `p_away`, the sums `p_1x`, `p_x2`, `p_12` and the
    handicap marginals `p_h15`, `p_a15` are the probabilities the call was
    chosen from, for display behind it (`BACKLOG.md` B22). They are
    uncalibrated (`/health` says so for the whole surface) and **none of them
    is a second call** -- one tip per fixture is what the record is graded on.
    """
    _check_division(division)
    clause = " WHERE t.settled_at IS NULL AND f.match_date >= %s"
    params: tuple = (db.today(),)
    if division:
        clause += " AND f.division = %s"
        params += (division,)
    return _with_handicap(_rows(
        conn,
        TIP_SELECT + clause
        + " ORDER BY f.match_date, f.kickoff_time, f.fixture_id",
        params,
    ))


@app.get("/tips/results")
def tip_results(
    division: str | None = Query(None),
    limit: int = Query(60, ge=1, le=500),
    conn: db.Connection = Depends(get_conn),
) -> list[dict]:
    """Settled tips, most recently played first.

    Carries the scoreline each tip was settled from (`fthg`/`ftag`, written
    by the grader beside the outcome -- migration 006). A row settled before
    the score was recorded serves NULLs rather than a reconstruction;
    `scripts/backfill_tip_scores.py` fills them from the same pages that
    settled them.
    """
    _check_division(division)
    clause = " WHERE t.settled_at IS NOT NULL"
    params: tuple = ()
    if division:
        clause += " AND f.division = %s"
        params = (division,)
    return _with_handicap(_rows(
        conn,
        TIP_SELECT + clause + " ORDER BY f.match_date DESC, t.tip_id DESC LIMIT %s",
        params + (limit,),
    ))


def _london_now() -> datetime:
    """UK wall-clock now, the zone the fixture feeds publish kick-offs in.
    A function so a test can pin the clock."""
    return datetime.now(ZoneInfo("Europe/London"))


@app.get("/parlay")
def parlay(
    division: str | None = Query(None, description="E0 | E1 | E2 | E3"),
    legs: int = Query(parlay_rule.DEFAULT_LEGS,
                      description=f"{parlay_rule.MIN_LEGS}..{parlay_rule.MAX_LEGS}"),
    min_claim: float = Query(parlay_rule.DEFAULT_MIN_CLAIM,
                             description="minimum claimed probability per leg"),
    conn: db.Connection = Depends(get_conn),
) -> dict:
    """A parlay generated from the published tip list (`PARLAY_PLAN.md`, B24).

    **A view over `/tips`, not a second call.** The legs are rows `/tips`
    would serve -- unplayed, one per fixture -- at or above `min_claim`,
    ranked by claim, cut to `legs`, minus any fixture whose UK kick-off has
    passed. `claimed` is the product of the legs' claims: a claimed figure in
    the same sense as `model_prob`, assuming the games are independent, and
    it is not graded -- each leg is graded on its own on the record. Nothing
    is padded: fewer calls clearing the threshold than `legs` asked for come
    back as they are, with `available` saying how many cleared.

    The selection is `engine.serve.parlay.select_legs`, computed here rather
    than in the browser because the frontend never forms a probability
    (`web/src/lib/api.js`). Sizes and presets live there too; the page
    mirrors them. No price on the parlay and no return: most legs are
    unpriceable handicaps, and a parlay compounds whatever the singles return.
    """
    _check_division(division)
    if not parlay_rule.MIN_LEGS <= legs <= parlay_rule.MAX_LEGS:
        raise HTTPException(
            400, f"legs must be {parlay_rule.MIN_LEGS}..{parlay_rule.MAX_LEGS}")
    if not 0.0 <= min_claim <= 1.0:
        raise HTTPException(400, "min_claim must be between 0 and 1")
    clause = " WHERE t.settled_at IS NULL AND f.match_date >= %s"
    params: tuple = (db.today(),)
    if division:
        clause += " AND f.division = %s"
        params += (division,)
    rows = _with_handicap(_rows(
        conn,
        TIP_SELECT + clause
        + " ORDER BY f.match_date, f.kickoff_time, f.fixture_id",
        params,
    ))
    selected = parlay_rule.select_legs(rows, legs=legs, min_claim=min_claim,
                                       now=_london_now())
    return {**selected, "division": division}


#: Strike rate and volume. **No P&L column appears here by design** -- see the
#: module docstring. `void` is excluded from the denominator rather than counted
#: as a loss, which is why the graded count is not `settled_at IS NOT NULL`.
#:
#: `{where}` is empty for the headline: **it pools every rule version** (owner
#: decision 2026-08-21, reversing `BACKLOG.md` B16 -- a version bump had left
#: the public record empty while the graded history sat behind the owner
#: view). The split by version is `by_rule`, grouped on the same template.
RECORD = """
    SELECT {group}
           COUNT(*) AS published,
           SUM(CASE WHEN t.outcome IN ('win', 'lose') THEN 1 ELSE 0 END) AS graded,
           SUM(CASE WHEN t.outcome = 'win' THEN 1 ELSE 0 END) AS won,
           SUM(CASE WHEN t.outcome = 'win' THEN 1 ELSE 0 END) * 1.0
             / NULLIF(SUM(CASE WHEN t.outcome IN ('win', 'lose')
                               THEN 1 ELSE 0 END), 0) AS strike_rate,
           SUM(CASE WHEN t.settled_at IS NULL AND f.match_date >= %s
                    THEN 1 ELSE 0 END) AS upcoming
    FROM tips t
    JOIN fixtures f ON f.fixture_id = t.fixture_id
    {where}
"""


def _matchweeks(conn, column: str | None) -> dict[Any, int]:
    """Distinct graded matchweeks, per value of `column` (None for one total).

    Counted here rather than in SQL: the record's matchweek is SQLite's
    `strftime('%Y-%W')` -- the Monday-first week number, 00-53 -- and Postgres
    has no format for that definition (`IW` is ISO and differs at the year
    boundary). Python's `strftime('%Y-%W')` is the same definition, so the
    figure is unchanged by the move (docs/POSTGRES_PLAN.md D4).
    """
    select = f"{column}, " if column else ""
    key = column.split(".")[-1] if column else None
    weeks: dict[Any, set[str]] = {}
    for row in conn.execute(
        f"SELECT DISTINCT {select}f.match_date FROM tips t"
        " JOIN fixtures f ON f.fixture_id = t.fixture_id"
        " WHERE t.outcome IN ('win', 'lose')"
    ):
        week = datetime.strptime(row["match_date"], "%Y-%m-%d").strftime("%Y-%W")
        weeks.setdefault(row[key] if key else None, set()).add(week)
    return {k: len(v) for k, v in weeks.items()}


@app.get("/tips/record")
def tip_record(conn: db.Connection = Depends(get_conn)) -> dict:
    """How the published tips have actually done.

    **Strike rate is the whole claim, and this endpoint returns nothing else
    that could be mistaken for one.** No profit, no ROI, no streak: the rule is
    sold on how often it is right, and `engine/eval/tips.py` measured that the
    return at customer prices is negative at every sellable setting with no
    interval excluding zero.

    `strike_rate` is **null**, never zero, until something has been graded. A
    zero would read as "we get everything wrong" rather than "nothing has been
    played yet", and opening weekend is exactly when that gets screenshotted.

    **The headline and `by_division` pool every rule version ever published**
    (owner decision 2026-08-21, reversing `BACKLOG.md` B16: a bump reset the
    public headline to null while the graded history sat in `by_rule`, which
    the site shows only to the owner). `by_rule` still splits the record by
    version, newest first, so the pooled number can always be decomposed.
    `rule` names the version currently publishing -- the rule of the most
    recently published tip -- not the version the headline is for. Derived
    from the table rather than imported from `engine.serve.tips`, so the API
    keeps reading what the cycle wrote and never loads the serving stack.
    """
    today = (db.today(),)
    rule = conn.execute(
        "SELECT rule_version, floor, ceiling FROM tips"
        " ORDER BY tip_id DESC LIMIT 1").fetchone()
    overall = dict(conn.execute(
        RECORD.format(group="", where=""), today).fetchone())
    overall["matchweeks"] = _matchweeks(conn, None).get(None, 0)
    by_division = _rows(
        conn, RECORD.format(group="f.division,", where="")
        + " GROUP BY f.division ORDER BY f.division", today)
    weeks = _matchweeks(conn, "f.division")
    for row in by_division:
        row["matchweeks"] = weeks.get(row["division"], 0)
    by_rule = _rows(
        conn, RECORD.format(group="t.rule_version,", where="")
        + " GROUP BY t.rule_version ORDER BY MAX(t.tip_id) DESC", today)
    weeks = _matchweeks(conn, "t.rule_version")
    for row in by_rule:
        row["matchweeks"] = weeks.get(row["rule_version"], 0)
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
    conn: db.Connection = Depends(get_conn),
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
def performance(conn: db.Connection = Depends(get_conn)) -> list[dict]:
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
