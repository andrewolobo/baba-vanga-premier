"""The serving API.

    uvicorn api.main:app --reload

Every endpoint reads what the cycle already wrote. Nothing here fits a model,
prices a fixture, or places a bet: predictions are produced by
`engine.serve.cycle` on a weekly schedule and stored, so a request can never
change what was served. That is what makes a stored prediction auditable --
"what did we say, when, from which artifact" has one answer, not one per
request.

Since `002_users.sql` (docs/AUTH_PLAN.md, B25) the API also **writes** -- only
to `users` and `user_sessions`, and only from `POST /auth/google`,
`POST /auth/logout` and `POST /me/phone`. Nothing a request can do changes
what was served; `tests/test_api.py` pins the write routes to that list.

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
import psycopg
from fastapi import Body, Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from scipy import stats

from api import auth, betpawa, teams
from engine import config, db
from engine.seasons import SERVED_DIVISIONS
from engine.serve import parlay as parlay_rule

app = FastAPI(
    title="baba.vanga.premier",
    description="Match prediction engine for the English professional divisions.",
    version="0.1.0",
)

# The frontend is served separately in development. GET only and no
# credentials, deliberately: the SPA reaches this API same-origin through the
# Vite proxy and through nginx, and a credential-less CORS policy is part of
# the write endpoints' CSRF posture (docs/AUTH_PLAN.md D9).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


def get_conn() -> db.Connection:
    """One connection per request, autocommit.

    Autocommit because this API mostly reads: psycopg would otherwise open a
    transaction on the first SELECT and hold it until the connection closed,
    leaving every request *idle in transaction* for its whole life. FastAPI
    runs this dependency's setup, the endpoint and the teardown on whichever
    threadpool workers are free; psycopg connections are not thread-bound, so
    that hand-off needs nothing special here. The account endpoints
    (docs/AUTH_PLAN.md) write on the same connection; the one
    multi-statement write, sign-in, wraps its pair in `conn.transaction()`,
    which on an autocommit connection is an explicit BEGIN/COMMIT.
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
    sides: str = Query(parlay_rule.DEFAULT_SIDES,
                       description="'any', or a comma-separated mix of"
                                   " win,dc,ah -- call-type filter"),
    conn: db.Connection = Depends(get_conn),
) -> dict:
    """A parlay generated from the published tip list (`PARLAY_PLAN.md`, B24).

    **A view over `/tips`, not a second call.** The legs are rows `/tips`
    would serve -- unplayed, one per fixture -- of the chosen call type
    (`sides`: the three groups the rule publishes, D8; over/under is not a
    published market -- B4), at or above `min_claim`, ranked by claim, cut
    to `legs` (the slider runs to the day's `pool` under the hard cap), minus any fixture whose UK kick-off has
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
    try:
        parlay_rule.parse_sides(sides)
    except ValueError as error:
        raise HTTPException(400, str(error)) from error
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
                                       sides=sides, now=_london_now())
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


# --- match pages (docs/SEO_PLAN.md 2.2, 2.3, 2.7) -------------------------- #
#
# A page per fixture, for search. It shows what the front page's cards show --
# the call, what it needs, the claim, the outcome -- plus facts that carry no
# probability: the venue, each side's recent results with our call on each,
# and the last meetings (D7). No prices, no return (§6).
#
# Which fixtures have a page (D8): every fixture with a published call, and
# upcoming ones before their call lands. A fixture whose date passed with no
# call -- a reschedule arrives as a new row and leaves the old one behind --
# has none. `/fixture` and `/sitemap/entries` state that rule separately, in
# Python and in SQL; `tests/test_match_api.py` pins that they agree.


def _season_start(match_date: str) -> str:
    """1 July of the season `match_date` falls in: the English season runs
    August to May, and July is the gap between two."""
    year, month = int(match_date[:4]), int(match_date[5:7])
    return f"{year if month >= 7 else year - 1}-07-01"


#: One settled call per fixture, the latest (as for the page's own call,
#: review R5), with the score it was graded from. Every played fixture since
#: the product launched was called, so this is also the season's results.
SETTLED_PER_FIXTURE = """
    SELECT DISTINCT ON (f.fixture_id)
           f.fixture_id, f.match_date, f.division, f.home_team_id,
           h.canonical_name AS home_team, a.canonical_name AS away_team,
           t.side, t.outcome, t.fthg, t.ftag
    FROM tips t
    JOIN fixtures f ON f.fixture_id = t.fixture_id
    JOIN teams h ON h.team_id = f.home_team_id
    JOIN teams a ON a.team_id = f.away_team_id
    WHERE t.settled_at IS NOT NULL AND f.match_date < %s AND {where}
    ORDER BY f.fixture_id, t.tip_id DESC
"""


#: An open upper bound for `SETTLED_PER_FIXTURE`, whose `before` is exclusive.
#: The team page lists every settled call, one graded earlier today included;
#: only the match page's form has a game it must stop short of.
NO_BOUND = "9999-12-31"


def _team_calls(conn, team_id: int, since: str, before: str = NO_BOUND,
                limit: int | None = None) -> list[dict[str, Any]]:
    """The team's settled fixtures from `since` up to `before` (exclusive),
    newest first, each seen from its own side: the score, W/D/L, and our call
    with how it went.

    The match page's form is the last five of these (docs/SEO_PLAN.md 2.3);
    the team page's list is the whole season's (2.5).
    """
    sql = ("SELECT * FROM (" + SETTLED_PER_FIXTURE.format(
        where="f.match_date >= %s AND %s IN (f.home_team_id, f.away_team_id)")
        + ") s ORDER BY match_date DESC, fixture_id DESC")
    params: tuple = (before, since, team_id)
    if limit is not None:
        sql, params = sql + " LIMIT %s", params + (limit,)
    calls = []
    for r in _rows(conn, sql, params):
        at_home = r["home_team_id"] == team_id
        scored, conceded = (r["fthg"], r["ftag"]) if at_home else (r["ftag"], r["fthg"])
        calls.append({
            "fixture_id": r["fixture_id"],
            "division": r["division"],
            "match_date": r["match_date"],
            "home_name": teams.display_name(r["home_team"]),
            "away_name": teams.display_name(r["away_team"]),
            "slug": teams.fixture_slug(r["home_team"], r["away_team"]),
            "at_home": at_home,
            "fthg": r["fthg"],
            "ftag": r["ftag"],
            "result": (None if scored is None or conceded is None
                       else "W" if scored > conceded else "D" if scored == conceded else "L"),
            "side": r["side"],
            "outcome": r["outcome"],
        })
    return calls


def _form(conn, team_id: int, before: str) -> list[dict[str, Any]]:
    """The side's last five settled fixtures this season before `before`,
    newest first, with our call on each. W/D/L is from the side's own view."""
    return _team_calls(conn, team_id, _season_start(before), before, limit=5)


def _meetings(conn, home_id: int, away_id: int, before: str) -> list[dict[str, Any]]:
    """The last five meetings before `before`, either way round, newest
    first: scores only. The historical rows come from `matches`, which were
    backtest inputs and never published calls, so no call rides with them
    (D8, §6); the fixtures this product called carry their graded score."""
    lo, hi = sorted((home_id, away_id))
    pair = ("LEAST({t}.home_team_id, {t}.away_team_id) = %s"
            " AND GREATEST({t}.home_team_id, {t}.away_team_id) = %s")
    history = _rows(
        conn,
        "SELECT m.match_date, m.division, h.canonical_name AS home_team,"
        " a.canonical_name AS away_team, m.fthg, m.ftag"
        " FROM matches m"
        " JOIN teams h ON h.team_id = m.home_team_id"
        " JOIN teams a ON a.team_id = m.away_team_id"
        f" WHERE {pair.format(t='m')} AND m.match_date < %s"
        " AND m.fthg IS NOT NULL AND m.ftag IS NOT NULL"
        " ORDER BY m.match_date DESC LIMIT 5",
        (lo, hi, before),
    )
    called = _rows(
        conn,
        SETTLED_PER_FIXTURE.format(where=pair.format(t="f") + " AND t.fthg IS NOT NULL"),
        (before, lo, hi),
    )
    # A match in both (were `matches` ever to take in a season this product
    # called) is listed once.
    unique = {}
    for r in called + history:
        unique.setdefault((r["match_date"], r["home_team"], r["away_team"]), r)
    newest = sorted(unique.values(), key=lambda r: r["match_date"], reverse=True)[:5]
    return [{
        "match_date": r["match_date"],
        "division": r["division"],
        "home_name": teams.display_name(r["home_team"]),
        "away_name": teams.display_name(r["away_team"]),
        "fthg": int(r["fthg"]),
        "ftag": int(r["ftag"]),
    } for r in newest]


@app.get("/fixture/{fixture_id}")
def fixture(fixture_id: int, conn: db.Connection = Depends(get_conn)) -> dict:
    """One fixture, for its match page.

    `tip` is the fixture's call in the `/tips` shape, settled or not, or
    null before it is published -- the latest `tip_id` where a fixture was
    called under more than one rule version (review R5). `home_team` and
    `away_team` are the canonical names every other endpoint uses;
    `home_name` and `away_name` are the display names (D12) the page prints,
    and `slug` is built from them. No fixture prices (§6).

    404 for an unknown id, a division that is not served, and a fixture
    whose date has passed with no call (D8).
    """
    row = conn.execute(
        "SELECT f.fixture_id, f.division, f.match_date, f.kickoff_time,"
        " f.home_team_id, f.away_team_id,"
        " h.canonical_name AS home_team, a.canonical_name AS away_team"
        " FROM fixtures f"
        " JOIN teams h ON h.team_id = f.home_team_id"
        " JOIN teams a ON a.team_id = f.away_team_id"
        " WHERE f.fixture_id = %s",
        (fixture_id,),
    ).fetchone()
    if row is None or row["division"] not in SERVED_DIVISIONS:
        raise HTTPException(404, "unknown fixture")
    tip = _with_handicap(_rows(
        conn, TIP_SELECT + " WHERE t.fixture_id = %s ORDER BY t.tip_id DESC LIMIT 1",
        (fixture_id,)))
    if not tip and row["match_date"] < db.today():
        raise HTTPException(404, "no call was published for this fixture")
    home, away, played = row["home_team"], row["away_team"], row["match_date"]
    return {
        "fixture_id": row["fixture_id"],
        "division": row["division"],
        "match_date": played,
        "kickoff_time": row["kickoff_time"],
        "home_team": home,
        "away_team": away,
        "home_team_id": row["home_team_id"],
        "away_team_id": row["away_team_id"],
        "home_name": teams.display_name(home),
        "away_name": teams.display_name(away),
        # Each side's own page address (2.5, 2.8), so the names can link.
        "home_slug": teams.team_slug(home),
        "away_slug": teams.team_slug(away),
        "slug": teams.fixture_slug(home, away),
        "venue": teams.venue(home),
        "tip": tip[0] if tip else None,
        "form": {
            "home": _form(conn, row["home_team_id"], played),
            "away": _form(conn, row["away_team_id"], played),
        },
        "meetings": _meetings(conn, row["home_team_id"], row["away_team_id"], played),
    }


def _iso_utc(text: str) -> str:
    """`YYYY-MM-DD HH:MM:SS` (stored UTC) as ISO 8601 with its zone."""
    return text.replace(" ", "T") + "Z"


@app.get("/sitemap/entries")
def sitemap_entries(conn: db.Connection = Depends(get_conn)) -> dict:
    """Every page generated from the store, for `sitemap.xml`
    (docs/SEO_PLAN.md 2.7): `matches`, every fixture that has a match page
    (D8), newest first; `leagues`, the served divisions that have one; and
    `teams`, every club in one of those matches, by id.

    `lastmod` is when the page last changed in a way a reader could see. For
    a match: the latest of its calls' `published_at` and `settled_at`, or
    `first_seen_at` before any call. **Not `fixtures.updated_at`**, which
    `fixture_sync` moves on every price refresh although no page shows a
    price (review R4). For a league or a team: the latest of its own
    matches', because those pages are those fixtures, their calls and their
    results.

    Every team listed here has a page, because it has a served fixture; the
    reverse does not hold -- a club whose only fixture is stale and uncalled
    has a page and no entry -- so no URL here 404s.
    """
    rows = _rows(
        conn,
        "SELECT f.fixture_id, f.division, f.first_seen_at,"
        " f.home_team_id, f.away_team_id,"
        " h.canonical_name AS home_team, a.canonical_name AS away_team,"
        " MAX(t.published_at) AS published_at, MAX(t.settled_at) AS settled_at"
        " FROM fixtures f"
        " JOIN teams h ON h.team_id = f.home_team_id"
        " JOIN teams a ON a.team_id = f.away_team_id"
        " LEFT JOIN tips t ON t.fixture_id = f.fixture_id"
        " WHERE f.division = ANY(%s)"
        " GROUP BY f.fixture_id, h.canonical_name, a.canonical_name"
        " HAVING COUNT(t.tip_id) > 0 OR f.match_date >= %s"
        " ORDER BY f.match_date DESC, f.fixture_id DESC",
        (list(SERVED_DIVISIONS), db.today()),
    )
    matches = [{
        "fixture_id": r["fixture_id"],
        "division": r["division"],
        "slug": teams.fixture_slug(r["home_team"], r["away_team"]),
        "lastmod": _iso_utc(max(filter(None, (r["published_at"], r["settled_at"])),
                                default=r["first_seen_at"])),
    } for r in rows]
    latest: dict[str, str] = {}
    by_team: dict[int, tuple[str, str]] = {}
    for row, m in zip(rows, matches):          # ISO UTC text sorts as time
        latest[m["division"]] = max(latest.get(m["division"], ""), m["lastmod"])
        for team_id, canonical in ((row["home_team_id"], row["home_team"]),
                                   (row["away_team_id"], row["away_team"])):
            _, when = by_team.get(team_id, (canonical, ""))
            by_team[team_id] = (canonical, max(when, m["lastmod"]))
    leagues = [{"division": d, "lastmod": latest[d]} for d in SERVED_DIVISIONS if d in latest]
    team_pages = [{"team_id": t, "slug": teams.team_slug(canonical), "lastmod": when}
                  for t, (canonical, when) in sorted(by_team.items())]
    return {"matches": matches, "leagues": leagues, "teams": team_pages}


#: The latest call per fixture, as a lateral join: what the league and team
#: pages list beside each fixture (review R5, as on the match page).
LATEST_CALL = """
    LEFT JOIN LATERAL (
        SELECT t.side, t.model_prob, t.outcome, t.settled_at, t.fthg, t.ftag
        FROM tips t WHERE t.fixture_id = f.fixture_id
        ORDER BY t.tip_id DESC LIMIT 1
    ) c ON TRUE
"""

LISTED = """
    SELECT f.fixture_id, f.division, f.match_date, f.kickoff_time,
           f.home_team_id, f.away_team_id,
           h.canonical_name AS home_team, a.canonical_name AS away_team,
           c.side, c.model_prob, c.outcome, c.settled_at, c.fthg, c.ftag
    FROM fixtures f
    JOIN teams h ON h.team_id = f.home_team_id
    JOIN teams a ON a.team_id = f.away_team_id
""" + LATEST_CALL


def _listed(row) -> dict[str, Any]:
    """A fixture as the league and team pages list it: who and when, the
    names and slug for its link, and its call if published. No prices."""
    call = None if row["side"] is None else {
        "side": row["side"],
        "model_prob": row["model_prob"],
        "outcome": row["outcome"],
        "settled_at": row["settled_at"],
        "fthg": row["fthg"],
        "ftag": row["ftag"],
    }
    return {
        "fixture_id": row["fixture_id"],
        "division": row["division"],
        "match_date": row["match_date"],
        "kickoff_time": row["kickoff_time"],
        "home_team": row["home_team"],
        "away_team": row["away_team"],
        "home_name": teams.display_name(row["home_team"]),
        "away_name": teams.display_name(row["away_team"]),
        "slug": teams.fixture_slug(row["home_team"], row["away_team"]),
        "tip": call,
    }


@app.get("/league/{division}")
def league(division: str, conn: db.Connection = Depends(get_conn)) -> dict:
    """One division, for its league page (docs/SEO_PLAN.md 2.4).

    `record` is the division's row of `/tips/record` `by_division`, from the
    same query, so the two cannot disagree. `upcoming` is every unsettled
    fixture dated today or later, called or not, soonest first -- a page on
    a quiet Friday still lists the weekend. `results` is the last twelve
    settled, newest first. 404 for a division that is not served.
    """
    if division not in SERVED_DIVISIONS:
        raise HTTPException(404, "unknown league")
    today = db.today()
    record = dict(conn.execute(
        RECORD.format(group="", where="WHERE f.division = %s"), (today, division)).fetchone())
    record["matchweeks"] = _matchweeks(conn, "f.division").get(division, 0)
    upcoming = _rows(
        conn,
        LISTED + " WHERE f.division = %s AND f.match_date >= %s AND c.settled_at IS NULL"
        " ORDER BY f.match_date, f.kickoff_time, f.fixture_id",
        (division, today),
    )
    results = _rows(
        conn,
        LISTED + " WHERE f.division = %s AND c.settled_at IS NOT NULL"
        " ORDER BY f.match_date DESC, f.fixture_id DESC LIMIT 12",
        (division,),
    )
    return {
        "division": division,
        "record": record,
        "upcoming": [_listed(r) for r in upcoming],
        "results": [_listed(r) for r in results],
    }


@app.get("/team/{team_id}")
def team(team_id: int, conn: db.Connection = Depends(get_conn)) -> dict:
    """One club, for its team page (docs/SEO_PLAN.md 2.5).

    `division` is where the club is playing now -- its latest served fixture
    -- so a promoted or relegated side is filed under this season's league.
    `upcoming` is in the league page's shape; `calls` is every fixture this
    season whose call has settled, newest first, from the club's own side.

    `tally` is counts, never a rate: a handful of calls cannot carry a strike
    rate, and one printed on four games would claim a precision the sample
    does not have. 404 for a club with no fixture in a served division.
    """
    served = list(SERVED_DIVISIONS)
    row = conn.execute(
        "SELECT t.canonical_name, f.division"
        " FROM teams t"
        " JOIN fixtures f ON %s IN (f.home_team_id, f.away_team_id)"
        " WHERE t.team_id = %s AND f.division = ANY(%s)"
        " ORDER BY f.match_date DESC, f.fixture_id DESC LIMIT 1",
        (team_id, team_id, served),
    ).fetchone()
    if row is None:
        raise HTTPException(404, "unknown team")
    canonical = row["canonical_name"]
    today = db.today()
    upcoming = _rows(
        conn,
        LISTED + " WHERE %s IN (f.home_team_id, f.away_team_id)"
        " AND f.division = ANY(%s) AND f.match_date >= %s AND c.settled_at IS NULL"
        " ORDER BY f.match_date, f.kickoff_time, f.fixture_id",
        (team_id, served, today),
    )
    calls = _team_calls(conn, team_id, _season_start(today))
    return {
        "team_id": team_id,
        "name": teams.display_name(canonical),
        "slug": teams.team_slug(canonical),
        "division": row["division"],
        "venue": teams.venue(canonical),
        "upcoming": [_listed(r) for r in upcoming],
        "calls": calls,
        "tally": {
            "graded": sum(1 for c in calls if c["outcome"] in ("win", "lose")),
            "won": sum(1 for c in calls if c["outcome"] == "win"),
        },
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


# --- accounts (docs/AUTH_PLAN.md, B25) ------------------------------------ #
# The only routes that write. `users` and `user_sessions` are the only tables
# they touch, and `tests/test_api.py` pins the write routes to exactly these.


def _same_site_json(request: Request) -> None:
    """The write endpoints take JSON from this site only (AUTH_PLAN.md D9).

    SameSite=Lax keeps the cookie off cross-site POSTs; requiring
    application/json keeps a cross-site form or no-cors fetch from reaching
    the handler at all (a JSON body forces a CORS preflight, which the
    middleware above never grants credentials for); Sec-Fetch-Site is the
    browser saying which it was. No CSRF token: nothing here is a form.
    """
    if not request.headers.get("content-type", "").startswith("application/json"):
        raise HTTPException(415, "send application/json")
    if request.headers.get("sec-fetch-site") == "cross-site":
        raise HTTPException(403, "cross-site request refused")


def current_user(request: Request, conn: db.Connection = Depends(get_conn)) -> dict | None:
    """The signed-in user behind the request's cookie, or None.

    One SELECT per request. The sliding expiry (D8) is written at most once a
    day per session, so a page that polls `/me` does not turn every read into
    a write.
    """
    token = request.cookies.get(auth.COOKIE)
    if not token:
        return None
    row = conn.execute(
        "SELECT u.user_id, u.email, u.name, u.picture_url, u.phone_e164,"
        "       u.phone_country, s.session_id"
        " FROM user_sessions s JOIN users u ON u.user_id = s.user_id"
        " WHERE s.token_hash = %s AND s.revoked_at IS NULL AND s.expires_at > now()",
        (auth.hash_token(token),),
    ).fetchone()
    if row is None:
        return None
    conn.execute(
        "UPDATE user_sessions SET last_seen_at = now(),"
        " expires_at = now() + %s * interval '1 day'"
        " WHERE session_id = %s AND last_seen_at < now() - interval '1 day'",
        (config.SESSION_DAYS, row["session_id"]),
    )
    return dict(row)


def require_user(user: dict | None = Depends(current_user)) -> dict:
    if user is None:
        raise HTTPException(401, "sign in required")
    return user


def _user_summary(row) -> dict:
    return {
        "user_id": row["user_id"],
        "name": row["name"],
        "email": row["email"],
        "picture_url": row["picture_url"],
        "phone_e164": row["phone_e164"],
        "phone_country": row["phone_country"],
        "phone_required": row["phone_e164"] is None,
    }


@app.get("/auth/config")
def auth_config() -> dict:
    """What the browser needs before it can sign anyone in: the Google client
    id (public -- it is the `aud` of every ID token; D7 serves it at runtime
    so one build is the same on every machine) and the country list for the
    phone step."""
    return {"google_client_id": config.GOOGLE_CLIENT_ID, "regions": auth.regions()}


@app.post("/auth/google", dependencies=[Depends(_same_site_json)])
def auth_google(
    request: Request,
    response: Response,
    payload: dict = Body(...),
    conn: db.Connection = Depends(get_conn),
) -> dict:
    """Sign in with a Google ID token: verify it, upsert the user on
    `google_sub`, open a session, set the cookie (D1, D2, D15)."""
    credential = payload.get("credential")
    if not isinstance(credential, str) or not credential:
        raise HTTPException(400, "credential required")
    try:
        claims = auth.verify_google_token(credential)
    except ValueError as error:
        raise HTTPException(401, "invalid google credential") from error
    if not claims.get("email"):
        raise HTTPException(401, "google returned no email")
    token = auth.new_token()
    # The one multi-statement write: on an autocommit connection this is an
    # explicit BEGIN/COMMIT, so a failed session insert leaves no user row.
    with conn.transaction():
        row = conn.execute(
            "INSERT INTO users (google_sub, email, email_verified, name, picture_url)"
            " VALUES (%s, %s, %s, %s, %s)"
            " ON CONFLICT (google_sub) DO UPDATE SET email = EXCLUDED.email,"
            "   email_verified = EXCLUDED.email_verified, name = EXCLUDED.name,"
            "   picture_url = EXCLUDED.picture_url, last_login_at = now()"
            " RETURNING user_id, email, name, picture_url, phone_e164, phone_country",
            (claims["sub"], claims["email"].lower(), bool(claims.get("email_verified")),
             claims.get("name"), claims.get("picture")),
        ).fetchone()
        conn.execute(
            "INSERT INTO user_sessions (user_id, token_hash, expires_at, user_agent)"
            " VALUES (%s, %s, now() + %s * interval '1 day', %s)",
            (row["user_id"], auth.hash_token(token), config.SESSION_DAYS,
             (request.headers.get("user-agent") or "")[:200]),
        )
    response.set_cookie(
        auth.COOKIE, token, max_age=config.SESSION_DAYS * 86400, path="/",
        httponly=True, secure=config.COOKIE_SECURE, samesite="lax",
    )
    return {"user": _user_summary(row)}


@app.get("/me")
def me(user: dict | None = Depends(current_user)) -> dict:
    """200 with `user: null` when anonymous, not 401: the layout asks this on
    every load, and a 401 is an error in every browser console."""
    return {"user": _user_summary(user) if user else None}


@app.post("/me/phone", dependencies=[Depends(_same_site_json)])
def set_phone(
    payload: dict = Body(...),
    user: dict = Depends(require_user),
    conn: db.Connection = Depends(get_conn),
) -> dict:
    """The one-time phone capture (D5). The WHERE clause is the guard: a
    second call updates zero rows and is refused, whatever the client believed."""
    try:
        e164, region = auth.normalise_phone(
            str(payload.get("phone", "")), str(payload.get("country", "")).upper())
    except ValueError as error:
        raise HTTPException(400, str(error)) from error
    try:
        cur = conn.execute(
            "UPDATE users SET phone_e164 = %s, phone_country = %s,"
            " phone_captured_at = now() WHERE user_id = %s AND phone_e164 IS NULL",
            (e164, region, user["user_id"]),
        )
    except psycopg.errors.UniqueViolation as error:
        raise HTTPException(409, "that phone number is already on another account") from error
    if cur.rowcount == 0:
        raise HTTPException(409, "phone number already captured")
    return {"user": _user_summary({**user, "phone_e164": e164, "phone_country": region})}


# --- betPawa links (docs/BETPAWA_PLAN.md, B26) ----------------------------- #


BETPAWA_SELECT = """
    SELECT f.fixture_id, e.event_id, s.side, s.selection_id
    FROM tips t
    JOIN fixtures f ON f.fixture_id = t.fixture_id
    JOIN betpawa_events e ON e.fixture_id = f.fixture_id
    LEFT JOIN betpawa_selections s ON s.fixture_id = f.fixture_id
    WHERE t.settled_at IS NULL AND f.match_date >= %s
    ORDER BY f.fixture_id, s.side
"""


@app.get("/betpawa/links")
def betpawa_links(
    user: dict = Depends(require_user),
    conn: db.Connection = Depends(get_conn),
) -> dict:
    """Where each live call can be placed on betPawa, for the signed-in user.

    **Its own route, on purpose.** `/tips` is public, cached offline by the
    service worker and pinned byte-identical; a per-user link inside it would
    put account-dependent content into a shared cache. This is signed-in only
    (401 otherwise), never cached, and carries no probability -- ids and URLs.

    The user's country is the one their phone number was validated under
    (`users.phone_country`, D6). When betPawa serves it, `host` is that
    country's site and `links` has one entry per fixture with a live tip that
    the scrape matched: the event page (`event_url`, the D11 fallback) and,
    for every side the book carried at the last scrape, the prefill URL that
    opens that wager (`sides`). The published side can be absent from
    `sides` -- the +1.5 ladder is one-sided -- and a fixture the scrape did
    not match is absent altogether; the page renders no wager button for
    either. When betPawa does not serve the country, `eligible` is false and
    `links` is empty: the site shows nothing, rather than a wrong country.

    No odds on the wire (D9): the site publishes no prices, and a morning's
    odds are stale by kick-off.
    """
    country = user.get("phone_country")
    host = betpawa.host_for(country)
    if host is None:
        return {"eligible": False, "country": country, "host": None, "links": []}
    links: dict[int, dict] = {}
    for row in _rows(conn, BETPAWA_SELECT, (db.today(),)):
        entry = links.setdefault(row["fixture_id"], {
            "fixture_id": row["fixture_id"],
            "event_id": row["event_id"],
            "event_url": betpawa.event_url(host, row["event_id"]),
            "sides": {},
        })
        if row["side"] is not None:
            entry["sides"][row["side"]] = {
                "selection_id": row["selection_id"],
                "url": betpawa.prefill_url(host, [row["selection_id"]]),
            }
    return {"eligible": True, "country": country, "host": host,
            "links": list(links.values())}


@app.post("/auth/logout", dependencies=[Depends(_same_site_json)])
def logout(
    user: dict | None = Depends(current_user),
    conn: db.Connection = Depends(get_conn),
) -> Response:
    """Revoke the session behind the cookie and clear it. Without a live
    session there is nothing to revoke, and clearing the cookie is still right."""
    if user:
        conn.execute("UPDATE user_sessions SET revoked_at = now() WHERE session_id = %s",
                     (user["session_id"],))
    response = Response(status_code=204)
    response.delete_cookie(auth.COOKIE, path="/")
    return response
