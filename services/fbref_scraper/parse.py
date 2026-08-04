"""A saved fbref date page -> fixtures. Pure: no network, no clock, no disk.

The schedule tables are live DOM, not the comment-wrapped tables fbref uses
elsewhere, so an ordinary CSS selector finds them. Every cell carries a
`data-stat` name, which is far more stable than column position: the cup tables
drop the matchweek column entirely, so counting columns would silently shift
every field on those tables by one.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from bs4 import BeautifulSoup

BASE_URL = "https://fbref.com"

#: `sched_2026-2027_34` = season, competition id. Calendar-year competitions
#: write the season as `2026`, so the season part is not always hyphenated.
_TABLE_ID = re.compile(r"^sched_(?P<season>[\d-]+)_(?P<comp_id>\d+)$")

#: "2-1", and "1 (4)-1 (3)" once the shootout parentheses are stripped. fbref
#: writes an en dash; a hyphen is accepted so a saved page edited by hand parses.
_SCORE = re.compile(r"^(?P<home>\d+)\s*[–-]\s*(?P<away>\d+)$")


@dataclass(frozen=True)
class Fixture:
    date: str
    season: str
    comp_id: int
    comp_name: str
    round: str | None
    week: int | None
    kickoff_local: str | None
    home: str
    away: str
    home_goals: int | None
    away_goals: int | None
    venue: str | None
    match_url: str | None


def parse_date_page(html: str, date: str,
                    comps: tuple[int, ...] = ()) -> list[Fixture]:
    """Fixtures for `date`, keeping only `comps` (empty keeps every league)."""
    soup = BeautifulSoup(html, "lxml")
    fixtures = []
    for table in soup.select("table.stats_table"):
        match = _TABLE_ID.match(table.get("id") or "")
        if match is None:
            continue
        comp_id = int(match["comp_id"])
        if comps and comp_id not in comps:
            continue
        comp_name = _text(table.select_one("caption a")) or ""
        for row in table.select("tbody tr"):
            # fbref repeats the header inside long tbodies.
            if "thead" in (row.get("class") or []):
                continue
            fixture = _fixture(row, date, match["season"], comp_id, comp_name)
            if fixture is not None:
                fixtures.append(fixture)
    return fixtures


def _fixture(row, date: str, season: str, comp_id: int,
             comp_name: str) -> Fixture | None:
    cells = {cell.get("data-stat"): cell for cell in row.find_all(["th", "td"])}
    home, away = _text(cells.get("home_team")), _text(cells.get("away_team"))
    if not home or not away:
        return None
    home_goals, away_goals = _score(_text(cells.get("score")))
    return Fixture(
        date=date,
        season=season,
        comp_id=comp_id,
        comp_name=comp_name,
        round=_text(cells.get("round")) or None,
        week=_int(_text(cells.get("gameweek"))),
        kickoff_local=_text(_select(cells.get("start_time"), "span.venuetime")) or None,
        home=home,
        away=away,
        home_goals=home_goals,
        away_goals=away_goals,
        venue=_text(cells.get("venue")) or None,
        match_url=_href(cells.get("match_report")),
    )


def _select(cell, selector):
    return None if cell is None else cell.select_one(selector)


def _text(node) -> str:
    return "" if node is None else node.get_text(" ", strip=True)


def _int(value: str) -> int | None:
    return int(value) if value.isdigit() else None


def _href(cell) -> str | None:
    link = None if cell is None else cell.find("a")
    return None if link is None else BASE_URL + link["href"]


def _score(value: str) -> tuple[int | None, int | None]:
    """Goals, or (None, None) for an unplayed game.

    Penalty shootout scores are written in parentheses after the 90-minute
    goals; the shootout is not a goal, so it is dropped rather than added in.
    """
    match = _SCORE.match(re.sub(r"\([^)]*\)", "", value).strip())
    if match is None:
        return None, None
    return int(match["home"]), int(match["away"])
