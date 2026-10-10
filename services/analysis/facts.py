"""The Fact Builder: what is true about each side and the fixture, as values.

Deterministic, and it reads only the store. Every fact has:

- a stable id, `{SCOPE}_{METRIC}_{WINDOW}` (`HOME_PPG_L5`,
  `AWAY_CS_PCT_SEASON`, `H2H_MATCH_1`);
- a label a reader can follow;
- a value, never an interpretation.

The LLM writes from these and nothing else (docs/ANALYSIS_PLAN.md).

**This season's results come from `tips`.** `matches` stops at the last
complete season. This season's scores exist only as `tips.fthg/ftag`, the
score each call was settled from (ANALYSIS_PLAN.md §3). Production has a
call on every played fixture, so those scores are the season's results.

- **A call settled without a score is a hole.** A window that would span it
  is left out rather than computed short, and the side is flagged
  `results_gap`.
- **A fixture with no call at all is ignored**, not counted as a hole. A
  postponement leaves its old row behind with no call (`api/main.py`, D8).
  Counting that as missing would blank a club's season for a match that was
  never played. It is named in `omitted` instead.

**Windows are season-bounded**, like the match page's form card, so the
text never contradicts the card beside it. L5 and L10 are left out until
the side has that many games; SEASON and VENUE need one.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Literal

from engine import db
from engine.seasons import DIVISIONS, season_code
from services.analysis.schemas import Fact, Flag

Side = Literal["home", "away"]

#: The short windows, in games. Fixed so every club is described on the
#: same footing.
WINDOWS = (5, 10)
#: Fewer league games than this this season raises `small_sample`.
SMALL_SAMPLE_GAMES = 5
#: Meetings shown on the match page; the analysis cites the same ones.
H2H_MEETINGS = 5
#: The listings' form trend (`form_trend`, owner decision 2026-10-10): no
#: trend before this many games, and a change in points per game of at
#: least this much either way is one.
TREND_MIN_GAMES = 6
TREND_MARGIN = Fraction(1, 2)


@dataclass(frozen=True)
class Game:
    """One league game this season, seen from the side's own end."""

    match_date: str
    at_home: bool
    #: None for a game that was played and called but settled without a score.
    scored: int | None
    conceded: int | None
    #: The side's own and its opponent's average 1X2 price, the last snapshot
    #: before kick-off. Used only to say who the market favoured.
    price: float | None = None
    opponent_price: float | None = None

    @property
    def known(self) -> bool:
        return self.scored is not None and self.conceded is not None

    @property
    def result(self) -> str:
        return "W" if self.scored > self.conceded else "D" if self.scored == self.conceded else "L"


def division_name(code: str) -> str:
    return DIVISIONS[code].name if code in DIVISIONS else code


def season_start(match_date: str) -> str:
    """1 July of the season `match_date` falls in. The same rule as the match
    page's form (`api.main._season_start`); a test pins the two together."""
    year, month = int(match_date[:4]), int(match_date[5:7])
    return f"{year if month >= 7 else year - 1}-07-01"


def _pct(k: int, n: int) -> int:
    return round(100 * k / n)


# --- reads ------------------------------------------------------------------ #


#: One row per called fixture of the side's this season, before the fixture
#: being described. A fixture called under two rule versions has two tips;
#: any one carrying a score settles what happened, so a scored tip is
#: preferred over the latest.
TEAM_GAMES = """
    SELECT DISTINCT ON (f.fixture_id)
           f.fixture_id, f.match_date, f.home_team_id, f.avg_h, f.avg_a,
           t.outcome, t.fthg, t.ftag
    FROM fixtures f
    JOIN tips t ON t.fixture_id = f.fixture_id
    WHERE %s IN (f.home_team_id, f.away_team_id)
      AND f.match_date >= %s AND f.match_date < %s
    ORDER BY f.fixture_id, (t.fthg IS NULL), t.tip_id DESC
"""


def team_games(conn: db.Connection, team_id: int, before: str) -> tuple[list[Game], int]:
    """(games oldest first, count of earlier fixtures this season with no call).

    A void tip with no score is a match that did not happen and is dropped.
    """
    since = season_start(before)
    games = []
    rows = conn.execute(TEAM_GAMES, (team_id, since, before)).fetchall()
    for r in sorted(rows, key=lambda r: (r["match_date"], r["fixture_id"])):
        scored = r["fthg"] is not None and r["ftag"] is not None
        if r["outcome"] == "void" and not scored:
            continue
        at_home = r["home_team_id"] == team_id
        own, other = (r["avg_h"], r["avg_a"]) if at_home else (r["avg_a"], r["avg_h"])
        games.append(Game(
            match_date=r["match_date"], at_home=at_home,
            scored=(r["fthg"] if at_home else r["ftag"]) if scored else None,
            conceded=(r["ftag"] if at_home else r["fthg"]) if scored else None,
            price=own, opponent_price=other))
    uncalled = db.scalar(
        conn,
        "SELECT COUNT(*) FROM fixtures f WHERE %s IN (f.home_team_id, f.away_team_id)"
        " AND f.match_date >= %s AND f.match_date < %s"
        " AND NOT EXISTS (SELECT 1 FROM tips t WHERE t.fixture_id = f.fixture_id)",
        (team_id, since, before))
    return games, int(uncalled)


def previous_division(conn: db.Connection, team_id: int, before: str) -> str | None:
    """The division the side played most of last season in, or None.

    `matches` carries every complete season loaded. A season that never
    went into it (any season after 2025-26, until it is ingested) is read
    from this product's own called fixtures instead, so the answer does not
    silently turn into "new to the division" for every club next August.
    """
    this_start = season_start(before)
    last_start = f"{int(this_start[:4]) - 1}-07-01"
    for sql, params in (
        ("SELECT division FROM matches WHERE season = %s"
         " AND %s IN (home_team_id, away_team_id)",
         (season_code(int(last_start[:4])), team_id)),
        ("SELECT f.division FROM fixtures f WHERE %s IN (f.home_team_id, f.away_team_id)"
         " AND f.match_date >= %s AND f.match_date < %s"
         " AND EXISTS (SELECT 1 FROM tips t WHERE t.fixture_id = f.fixture_id)",
         (team_id, last_start, this_start)),
    ):
        row = conn.execute(
            f"SELECT division FROM ({sql}) d GROUP BY division"
            " ORDER BY COUNT(*) DESC, division LIMIT 1", params).fetchone()
        if row is not None:
            return row["division"]
    return None


_PAIR = ("LEAST({t}.home_team_id, {t}.away_team_id) = %s"
         " AND GREATEST({t}.home_team_id, {t}.away_team_id) = %s")


def meetings(conn: db.Connection, home_id: int, away_id: int, before: str) -> list[dict]:
    """The last `H2H_MEETINGS` meetings before `before`, either way round,
    newest first: the corpus's results plus the scores of called fixtures,
    as on the match page (`api.main._meetings`)."""
    lo, hi = sorted((home_id, away_id))
    history = conn.execute(
        "SELECT m.match_date, m.division, m.home_team_id, m.fthg, m.ftag FROM matches m"
        f" WHERE {_PAIR.format(t='m')} AND m.match_date < %s"
        " AND m.fthg IS NOT NULL AND m.ftag IS NOT NULL"
        " ORDER BY m.match_date DESC LIMIT %s",
        (lo, hi, before, H2H_MEETINGS)).fetchall()
    called = conn.execute(
        "SELECT DISTINCT ON (f.fixture_id) f.match_date, f.division, f.home_team_id,"
        " t.fthg, t.ftag FROM fixtures f JOIN tips t ON t.fixture_id = f.fixture_id"
        f" WHERE {_PAIR.format(t='f')} AND f.match_date < %s AND t.fthg IS NOT NULL"
        " ORDER BY f.fixture_id, t.tip_id DESC",
        (lo, hi, before)).fetchall()
    unique = {}
    for r in called + history:
        unique.setdefault((r["match_date"], r["home_team_id"]), r)
    return sorted(unique.values(), key=lambda r: r["match_date"], reverse=True)[:H2H_MEETINGS]


def league_scores(conn: db.Connection, division: str, before: str) -> list[tuple[int, int]]:
    """(home goals, away goals) for every scored fixture in the division
    this season before `before`."""
    return [(r["fthg"], r["ftag"]) for r in conn.execute(
        "SELECT DISTINCT ON (f.fixture_id) t.fthg, t.ftag FROM fixtures f"
        " JOIN tips t ON t.fixture_id = f.fixture_id"
        " WHERE f.division = %s AND f.match_date >= %s AND f.match_date < %s"
        " AND t.fthg IS NOT NULL AND t.ftag IS NOT NULL"
        " ORDER BY f.fixture_id, t.tip_id DESC",
        (division, season_start(before), before))]


# --- facts, from values already read (pure) --------------------------------- #


def _summary(prefix: str, scope: str, name: str, window: str, words: str,
             games: list[Game]) -> list[Fact]:
    n = len(games)
    results = "".join(g.result for g in games)
    gf = sum(g.scored for g in games)
    ga = sum(g.conceded for g in games)
    # The counts restate FORM so that "won 4 of the last 5" is a quotable fact
    # the number check can verify, rather than a sum the LLM worked out.
    rows = [
        ("GAMES", f"{name} league games, {words}", n, "games"),
        ("FORM", f"{name} results, {words}, oldest to latest", results, None),
        ("WON", f"{name} wins, {words}", results.count("W"), "games"),
        ("DRAWN", f"{name} draws, {words}", results.count("D"), "games"),
        ("LOST", f"{name} defeats, {words}", results.count("L"), "games"),
        ("PPG", f"{name} points per game, {words}",
         round((3 * results.count("W") + results.count("D")) / n, 2), "pts/game"),
        ("GF_PG", f"{name} goals scored per game, {words}", round(gf / n, 2), "goals/game"),
        ("GA_PG", f"{name} goals conceded per game, {words}", round(ga / n, 2), "goals/game"),
        ("CS_PCT", f"{name} clean sheets, {words}",
         _pct(sum(g.conceded == 0 for g in games), n), "%"),
        ("BTTS_PCT", f"{name} games in which both sides scored, {words}",
         _pct(sum(g.scored > 0 and g.conceded > 0 for g in games), n), "%"),
        ("O25_PCT", f"{name} games with three or more goals, {words}",
         _pct(sum(g.scored + g.conceded >= 3 for g in games), n), "%"),
    ]
    return [Fact(id=f"{prefix}_{metric}_{window}", label=label, value=value, unit=unit,
                 scope=scope) for metric, label, value, unit in rows]


def _market_record(prefix: str, scope: str, name: str, games: list[Game]) -> list[Fact]:
    """Wins, draws and losses as the market's favourite and as its underdog.

    A record, never a price (D1): who was shorter on the average 1X2 price.
    Games without both prices, or priced level, take no part.
    """
    priced = [g for g in games if g.price and g.opponent_price and g.price != g.opponent_price]
    facts = []
    for role, words, subset in (
        ("FAV", "as the market favourite", [g for g in priced if g.price < g.opponent_price]),
        ("DOG", "as the market underdog", [g for g in priced if g.price > g.opponent_price]),
    ):
        if not subset:
            continue
        results = [g.result for g in subset]
        for metric, label, value in (
            ("GAMES", f"{name} league games this season {words}", len(subset)),
            ("WON", f"{name} wins this season {words}", results.count("W")),
            ("DRAWN", f"{name} draws this season {words}", results.count("D")),
            ("LOST", f"{name} defeats this season {words}", results.count("L")),
        ):
            facts.append(Fact(id=f"{prefix}_{role}_{metric}_SEASON", label=label,
                              value=value, unit="games", scope=scope))
    return facts


def team_facts(side: Side, name: str, games: list[Game], *, division: str,
               last_division: str | None,
               uncalled: int = 0) -> tuple[list[Fact], list[Flag], list[str]]:
    """(facts, flags, omitted) for one side.

    `games` is the side's league games this season, oldest first. VENUE is
    this fixture's venue: home games for the home side, away for the away.
    """
    prefix, scope = side.upper(), f"{side}_team"
    facts: list[Fact] = []
    flags: list[Flag] = []
    omitted: list[str] = []

    windows = []
    for k in WINDOWS:
        if len(games) >= k:
            windows.append((f"L{k}", f"last {k} league games this season", games[-k:]))
        else:
            omitted.append(f"{prefix} L{k}: {len(games)} league game(s) this season")
    if games:
        windows.append(("SEASON", "league games this season", games))
        at_venue = [g for g in games if g.at_home == (side == "home")]
        if at_venue:
            words = f"{'home' if side == 'home' else 'away'} league games this season"
            windows.append(("VENUE", words, at_venue))
    else:
        omitted.append(f"{prefix} SEASON: no league games this season yet")

    for window, words, subset in windows:
        if all(g.known for g in subset):
            facts += _summary(prefix, scope, name, window, words, subset)
        else:
            omitted.append(f"{prefix} {window}: spans a called game with no recorded score")

    if games and all(g.known for g in games):
        facts += _market_record(prefix, scope, name, games)

    if last_division is not None:
        facts.append(Fact(id=f"{prefix}_DIVISION_LAST_SEASON",
                          label=f"{name} division last season",
                          value=division_name(last_division), scope=scope))
    else:
        omitted.append(f"{prefix} DIVISION_LAST_SEASON: no league games last season on record")

    if not all(g.known for g in games):
        flags.append(Flag(code="results_gap", side=side))
    if len(games) < SMALL_SAMPLE_GAMES:
        flags.append(Flag(code="small_sample", side=side))
    if last_division != division:
        flags.append(Flag(code="new_to_division", side=side))
    if uncalled:
        omitted.append(f"{prefix}: {uncalled} earlier fixture(s) this season have no call"
                       " (postponed or missed) and are not counted")
    return facts, flags, omitted


def h2h_facts(rows: list[dict], home_id: int, names: dict[int, str]) -> list[Fact]:
    """The meetings, newest first, and their tally from this fixture's home
    side, whichever ground each was played at."""
    if not rows:
        return []
    home = names[home_id]
    away = next(name for team_id, name in names.items() if team_id != home_id)
    facts = []
    tally = {"W": 0, "D": 0, "L": 0}
    goals = 0
    for i, r in enumerate(rows, start=1):
        host = names[r["home_team_id"]]
        guest = away if host == home else home
        facts.append(Fact(
            id=f"H2H_MATCH_{i}",
            label=f"Meeting {i} of the last {len(rows)}, most recent first",
            value=f"{r['match_date']}, {host} {r['fthg']}-{r['ftag']} {guest}, "
                  f"{division_name(r['division'])}",
            scope="h2h"))
        mine, theirs = ((r["fthg"], r["ftag"]) if r["home_team_id"] == home_id
                        else (r["ftag"], r["fthg"]))
        tally["W" if mine > theirs else "D" if mine == theirs else "L"] += 1
        goals += r["fthg"] + r["ftag"]
    n = len(rows)
    for metric, label, value, unit in (
        ("GAMES", f"Meetings counted (the last {H2H_MEETINGS} at most)", n, "games"),
        ("HOME_WINS", f"{home} wins in the last {n} meetings", tally["W"], "games"),
        ("DRAWS", f"Draws in the last {n} meetings", tally["D"], "games"),
        ("AWAY_WINS", f"{away} wins in the last {n} meetings", tally["L"], "games"),
        ("GOALS_PG", f"Goals per game in the last {n} meetings", round(goals / n, 2),
         "goals/game"),
    ):
        facts.append(Fact(id=f"H2H_{metric}_L{H2H_MEETINGS}", label=label, value=value,
                          unit=unit, scope="h2h"))
    return facts


def league_facts(scores: list[tuple[int, int]], division: str) -> list[Fact]:
    if not scores:
        return []
    name, n = division_name(division), len(scores)
    return [
        Fact(id="LEAGUE_GAMES_SEASON", label=f"{name} games played this season",
             value=n, unit="games", scope="league"),
        Fact(id="LEAGUE_GOALS_PG_SEASON", label=f"{name} goals per game this season",
             value=round(sum(h + a for h, a in scores) / n, 2), unit="goals/game",
             scope="league"),
        Fact(id="LEAGUE_HOME_WIN_PCT_SEASON", label=f"{name} home wins this season",
             value=_pct(sum(h > a for h, a in scores), n), unit="%", scope="league"),
    ]


def build_facts(conn: db.Connection, fixture: dict) -> tuple[list[Fact], list[Flag], list[str]]:
    """Every fact about one fixture, as of the day it is played.

    `fixture` needs `fixture_id`, `division`, `match_date`, `home_team_id`,
    `away_team_id`, `home` and `away` (display names). Only games before the
    fixture's date are read, so a pack built after the match describes what
    was known before it.
    """
    before, division = fixture["match_date"], fixture["division"]
    names = {fixture["home_team_id"]: fixture["home"], fixture["away_team_id"]: fixture["away"]}
    facts: list[Fact] = []
    flags: list[Flag] = []
    omitted: list[str] = []
    for side in ("home", "away"):
        team_id = fixture[f"{side}_team_id"]
        games, uncalled = team_games(conn, team_id, before)
        f, fl, om = team_facts(side, fixture[side], games, division=division,
                               last_division=previous_division(conn, team_id, before),
                               uncalled=uncalled)
        facts, flags, omitted = facts + f, flags + fl, omitted + om

    h2h = h2h_facts(meetings(conn, fixture["home_team_id"], fixture["away_team_id"], before),
                    fixture["home_team_id"], names)
    if not h2h:
        omitted.append("H2H: no meetings on record")
    league = league_facts(league_scores(conn, division, before), division)
    if not league:
        omitted.append("LEAGUE: no scored games in the division this season yet")
    omitted.append("STANDINGS: the store has no league table")
    return facts + h2h + league, flags, omitted


# --- the listings' form trend (pure) ----------------------------------------- #


def _points(games: list[Game]) -> int:
    return sum(3 if g.result == "W" else g.result == "D" for g in games)


def form_trend(games: list[Game]) -> dict | None:
    """Improving, stable or declining, from the side's games oldest first; None
    when there is nothing honest to say.

    Points per game over the last 5 against the last 10, or the season while
    the side has fewer than 10 -- the same windows, and so the same figures,
    as the pack's `PPG_L5` and `PPG_L10`/`PPG_SEASON`. `TREND_MARGIN` or more
    either way is a trend. Below `TREND_MIN_GAMES` the two windows are nearly
    the same games, and a window spanning a game with no score would be
    computed short, so both are None rather than "stable".

    The tip and parlay listings show it to signed-in readers beside the
    analysis's own `trend` word, which the LLM chose and nothing checks
    against this: the two can differ, and the page shows both (ANALYSIS_PLAN.md
    section 8).
    """
    if len(games) < TREND_MIN_GAMES:
        return None
    longer = games[-10:]
    if not all(g.known for g in longer):
        return None
    last5, versus = Fraction(_points(longer[-5:]), 5), Fraction(_points(longer), len(longer))
    change = last5 - versus
    return {
        "trend": ("improving" if change >= TREND_MARGIN
                  else "declining" if change <= -TREND_MARGIN else "stable"),
        "window": "L10" if len(longer) == 10 else "SEASON",
        "last5": round(float(last5), 2),
        "versus": round(float(versus), 2),
    }
