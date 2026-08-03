"""Weekly grading: pull results, settle the book, compute CLV.

    python -m services.csv_grader                    # fetch this season's CSVs
    python -m services.csv_grader --dry-run
    python -m services.csv_grader --file E0.csv --division E0

Runs after a matchday. football-data.co.uk republishes each division's
season-to-date file with results *and closing prices* attached, so one pull
settles bets and grades CLV together.

**CLV is the primary metric (SPEC §5.1)**, and it is measured against the
DE-VIGGED close, not the raw closing price. The question CLV answers is whether
we were ahead of the market's final opinion; a raw closing price is that opinion
plus the bookmaker's margin, so comparing against it would credit us with the
margin on every bet. This is the mirror image of the rule in `engine.serve.book`
-- bet decisions use raw `1/odds`, CLV uses de-vigged probabilities -- and the
two must never be swapped.

The closing source is recorded per grade and never silently mixed: Pinnacle
(`PSC*`) where available, market average (`AvgC*`) otherwise. Those are
different books with different margins, and averaging across them would make a
CLV series that drifts with coverage rather than with skill.
"""

from __future__ import annotations

import argparse
import csv
import io
import sqlite3
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from engine import db
from engine.ingest.teams import FOOTBALL_DATA, TeamBridge
from engine.odds import devig_probs
from engine.seasons import SERVED_DIVISIONS, season_code

RESULTS_URL = "https://www.football-data.co.uk/mmz4281/{season}/{division}.csv"

#: Closing 1X2 columns in preference order. Pinnacle first: sharpest book, and
#: the one SPEC §5.1 names as primary. Never blended -- the chosen source is
#: stored on every grade.
CLOSING_SOURCES = (
    ("PSC", ("PSCH", "PSCD", "PSCA")),
    ("AvgC", ("AvgCH", "AvgCD", "AvgCA")),
)
CLOSING_OU = (
    ("AvgC", ("AvgC>2.5", "AvgC<2.5")),
    ("Avg", ("Avg>2.5", "Avg<2.5")),
)


@dataclass
class GradeReport:
    results_seen: int = 0
    settled: int = 0
    graded: int = 0
    unmatched: list = field(default_factory=list)

    def describe(self) -> str:
        lines = [f"{self.results_seen} result(s) seen; "
                 f"{self.settled} bet(s) settled, {self.graded} CLV grade(s) written"]
        if self.unmatched:
            lines.append(f"  {len(self.unmatched)} fixture(s) had bets but no result yet")
        return "\n".join(lines)


def season_for(date: str) -> str:
    """ISO date -> football-data season path, e.g. '2026-08-15' -> '2627'.

    Our own season codes are six characters ('202627'); the football-data URL
    path wants four ('2627'), which is the last two digits of each year.
    """
    year, month = int(date[:4]), int(date[5:7])
    start = year if month >= 7 else year - 1
    code = season_code(start)          # '202627'
    return code[2:4] + code[4:6]       # '26' + '27'


def fetch(division: str, season: str, timeout: int = 30) -> str:
    url = RESULTS_URL.format(season=season, division=division)
    with urllib.request.urlopen(url, timeout=timeout) as response:  # noqa: S310
        return response.read().decode("cp1252")


def _float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_results(text: str) -> list[dict]:
    rows = []
    for raw in csv.DictReader(io.StringIO(text)):
        if not raw.get("HomeTeam") or not raw.get("FTR"):
            continue
        day, month, year = raw["Date"].strip().split("/")
        if len(year) == 2:
            year = f"20{year}"
        rows.append({
            "division": raw.get("Div"),
            "match_date": f"{year}-{int(month):02d}-{int(day):02d}",
            "home": raw["HomeTeam"].strip(),
            "away": raw["AwayTeam"].strip(),
            "fthg": int(raw["FTHG"]), "ftag": int(raw["FTAG"]),
            "ftr": raw["FTR"].strip(),
            "raw": raw,
        })
    return rows


def closing_probs(raw: dict) -> tuple[str | None, tuple, str | None, tuple]:
    """De-vigged closing probabilities for 1X2 and O/U, with their sources."""
    x2_source, x2 = None, ()
    for name, columns in CLOSING_SOURCES:
        values = [_float(raw.get(c)) for c in columns]
        if all(v and v > 1.0 for v in values):
            x2_source, x2 = name, devig_probs(*[np.array([v]) for v in values])
            x2 = tuple(float(p[0]) for p in x2)
            break
    ou_source, ou = None, ()
    for name, columns in CLOSING_OU:
        values = [_float(raw.get(c)) for c in columns]
        if all(v and v > 1.0 for v in values):
            ou_source, ou = name, devig_probs(*[np.array([v]) for v in values])
            ou = tuple(float(p[0]) for p in ou)
            break
    return x2_source, x2, ou_source, ou


def _won(market: str, side: str, result: dict) -> bool:
    if market == "1x2":
        return result["ftr"] == side
    total = result["fthg"] + result["ftag"]
    return (total > 2.5) if side == "over" else (total < 2.5)


def _devigged_at_bet(market: str, side: str, odds) -> float | None:
    """The market's opinion at bet time, de-vigged.

    CLV must compare like with like: two market opinions, both with margin
    removed. Using the raw `1/price` here instead -- which is what the bet
    decision correctly uses -- would build the bookmaker's margin into every
    CLV figure and make a flat book look like a winning one.
    """
    if odds is None:
        return None
    if market == "1x2":
        values = [odds["avg_h"], odds["avg_d"], odds["avg_a"]]
        index = {"H": 0, "D": 1, "A": 2}[side]
    else:
        values = [odds["avg_over25"], odds["avg_under25"]]
        index = 0 if side == "over" else 1
    if any(v is None or v <= 1.0 for v in values):
        return None
    probs = devig_probs(*[np.array([float(v)]) for v in values])
    return float(probs[index][0])


def _closing_price_for(market: str, side: str, raw: dict) -> tuple[float | None, str | None,
                                                                  float | None]:
    """(raw closing price, source, de-vigged closing probability) for one leg."""
    x2_source, x2, ou_source, ou = closing_probs(raw)
    if market == "1x2":
        if not x2:
            return None, None, None
        index = {"H": 0, "D": 1, "A": 2}[side]
        columns = dict(CLOSING_SOURCES)[x2_source]
        return _float(raw.get(columns[index])), x2_source, x2[index]
    if not ou:
        return None, None, None
    index = 0 if side == "over" else 1
    columns = dict(CLOSING_OU)[ou_source]
    return _float(raw.get(columns[index])), ou_source, ou[index]


def grade(conn: sqlite3.Connection, results: list[dict], *,
          dry_run: bool = False) -> GradeReport:
    bridge = TeamBridge.load()
    ids = {row["canonical_name"]: row["team_id"]
           for row in conn.execute("SELECT team_id, canonical_name FROM teams")}
    out = GradeReport(results_seen=len(results))

    for result in results:
        home = bridge.try_resolve(FOOTBALL_DATA, result["home"])
        away = bridge.try_resolve(FOOTBALL_DATA, result["away"])
        if home not in ids or away not in ids:
            continue
        fixture = conn.execute(
            "SELECT fixture_id FROM fixtures WHERE division=? AND match_date=?"
            " AND home_team_id=? AND away_team_id=?",
            (result["division"], result["match_date"], ids[home], ids[away]),
        ).fetchone()
        if fixture is None:
            continue

        odds_at_bet = conn.execute(
            "SELECT avg_h, avg_d, avg_a, avg_over25, avg_under25 FROM fixtures"
            " WHERE fixture_id=?", (fixture["fixture_id"],),
        ).fetchone()
        bets = conn.execute(
            "SELECT * FROM paper_bets WHERE fixture_id=? AND settled_at IS NULL",
            (fixture["fixture_id"],),
        ).fetchall()
        for bet in bets:
            won = _won(bet["market"], bet["side"], result)
            pnl = bet["stake"] * (bet["price"] - 1.0) if won else -bet["stake"]
            out.settled += 1
            if not dry_run:
                conn.execute(
                    "UPDATE paper_bets SET settled_at=datetime('now'), outcome=?, pnl=?"
                    " WHERE bet_id=?",
                    ("win" if won else "lose", pnl, bet["bet_id"]),
                )

            close_price, source, close_prob = _closing_price_for(
                bet["market"], bet["side"], result["raw"])
            bet_prob = _devigged_at_bet(bet["market"], bet["side"], odds_at_bet)
            if close_price is None or bet_prob is None:
                continue
            out.graded += 1
            if not dry_run:
                conn.execute(
                    "INSERT OR IGNORE INTO clv_grades (bet_id, bet_price, close_price,"
                    " close_source, bet_prob, close_prob, clv, clv_pct)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (bet["bet_id"], bet["price"], close_price, source,
                     bet_prob, close_prob, close_prob - bet_prob,
                     bet["price"] / close_price - 1.0),
                )
    if not dry_run:
        conn.commit()
    return out


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, help="grade a local CSV instead of fetching")
    parser.add_argument("--division", help="division code for --file")
    parser.add_argument("--season", help="football-data season path, e.g. 2627")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    conn = db.connect()
    db.migrate(conn)

    if args.file:
        texts = [(args.division, args.file.read_text(encoding="cp1252"))]
    else:
        pending = conn.execute(
            "SELECT DISTINCT f.division, f.match_date FROM paper_bets b"
            " JOIN fixtures f ON f.fixture_id = b.fixture_id"
            " WHERE b.settled_at IS NULL"
        ).fetchall()
        if not pending:
            print("no unsettled bets")
            return 0
        seasons = {(r["division"], args.season or season_for(r["match_date"]))
                   for r in pending}
        texts = [(division, fetch(division, season)) for division, season in sorted(seasons)]

    total = GradeReport()
    for division, text in texts:
        rows = [r for r in parse_results(text)
                if r["division"] in SERVED_DIVISIONS or r["division"] == division]
        report = grade(conn, rows, dry_run=args.dry_run)
        total.results_seen += report.results_seen
        total.settled += report.settled
        total.graded += report.graded

    print(total.describe())
    if args.dry_run:
        print("(dry run -- nothing written)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
