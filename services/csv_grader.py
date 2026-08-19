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
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from engine import db
from engine.eval import selection
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
    tips_settled: int = 0
    unmatched: list = field(default_factory=list)
    disagreed: list = field(default_factory=list)   # tip ids settled elsewhere that this feed contradicts

    def describe(self) -> str:
        lines = [f"{self.results_seen} result(s) seen; "
                 f"{self.settled} bet(s) settled, {self.graded} CLV grade(s) written, "
                 f"{self.tips_settled} tip(s) settled"]
        if self.unmatched:
            lines.append(f"  {len(self.unmatched)} fixture(s) had bets but no result yet")
        if self.disagreed:
            lines.append(f"  {len(self.disagreed)} tip(s) already settled with a different "
                         f"outcome: {self.disagreed}")
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


#: football-data added a UTF-8 BOM to these files between 2023-24 and 2024-25.
#: Decoded as cp1252 those three bytes become `ï»¿` and rename the first column
#: to `ï»¿Div`, so `raw.get("Div")` is None on every row and every result is
#: then dropped by the caller's division filter -- a grader that fetches
#: hundreds of results, settles nothing and reports success. Stripped as bytes
#: rather than switching to `utf-8-sig` so the decode stays cp1252 and a legacy
#: file carrying high bytes still reads exactly as it did before.
_BOM = b"\xef\xbb\xbf"

#: What "no such file" looks like here. The server does not answer with a plain
#: 404: Apache's mod_speling hunts for near-miss names and returns 300 with the
#: candidates listed. See `ResultsNotPublished`.
_NO_SUCH_FILE = frozenset({300, 404})


class ResultsNotPublished(Exception):
    """This division has no season-to-date file on the server yet.

    Expected for a week or so each August, and it is not an error in this code.
    football-data creates the season directory when its earliest league kicks
    off and adds each division's file once that division has played -- so a
    fixture can be tipped, played and pending settlement while `E1.csv` does
    not exist. Raised rather than swallowed because the tips do stay unsettled,
    which is worth an ATTENTION even though it is nobody's bug.

    **The missing file does not 404, and one of its shapes returns 200.** With
    several near-miss names mod_speling answers 300 Multiple Choices; with a
    single candidate it answers **301 onto another division's file**, which
    urllib follows silently. Asking for the 2026-27 Premier League returns the
    National League this way. That redirect is the same condition -- the file
    we asked for is not there -- so it raises this too, rather than handing
    back one division's results against another's fixtures.
    """


def fetch(division: str, season: str, timeout: int = 30) -> str:
    """The division's season-to-date results CSV.

    Raises `ResultsNotPublished` if the file is not on the server yet; any
    other HTTP failure is a real one and propagates.
    """
    url = RESULTS_URL.format(season=season, division=division)
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:  # noqa: S310
            landed, data = response.url, response.read()
    except urllib.error.HTTPError as exc:
        if exc.code in _NO_SUCH_FILE:
            raise ResultsNotPublished(
                f"{division} {season}: no results file yet (HTTP {exc.code})") from exc
        raise
    if not landed.endswith(f"/{division}.csv"):
        raise ResultsNotPublished(
            f"{division} {season}: no results file yet (redirected to {landed})")
    return data.removeprefix(_BOM).decode("cp1252")


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


def settle_tips(conn: sqlite3.Connection, fixture_id: int, result: dict, *,
                dry_run: bool = False) -> int:
    """Settle every unsettled tip on this fixture, at BOTH price levels.

    Two P&L columns rather than one, because the tip product is sold on strike
    rate and `engine/eval/tips.py` measured the two claims coming apart: the
    strike rate is honest and the return at prices a customer without a dozen
    accounts gets is not distinguishable from zero. Recording only the best
    price would reproduce that gap live, in the flattering direction.

    A tip with no stored price still settles -- outcome is the product's
    headline number and must never depend on the feed having carried odds --
    and leaves its P&L NULL rather than guessing one.
    """
    tips = conn.execute(
        "SELECT tip_id, side, best_price, avg_price FROM tips"
        " WHERE fixture_id=? AND settled_at IS NULL", (fixture_id,),
    ).fetchall()
    for tip in tips:
        # Not `_won("1x2", ...)`: a tip may be a union of outright legs or a
        # handicap, and that function only knows single outcomes.
        # `selection.won_from_score` wraps the same `selection._won` the gates
        # measured the strike rate with and adds the margin-aware v3 sides, so
        # the published number and the settled number cannot drift apart.
        won = bool(selection.won_from_score(np.array([tip["side"]]),
                                            np.array([result["fthg"]]),
                                            np.array([result["ftag"]]))[0])
        pnl = {name: (None if tip[name] is None
                      else (tip[name] - 1.0 if won else -1.0))
               for name in ("best_price", "avg_price")}
        if not dry_run:
            conn.execute(
                "UPDATE tips SET settled_at=datetime('now'), outcome=?,"
                " pnl_best=?, pnl_avg=? WHERE tip_id=?",
                ("win" if won else "lose", pnl["best_price"], pnl["avg_price"],
                 tip["tip_id"]),
            )
    return len(tips)


def reconcile_tips(conn: sqlite3.Connection, fixture_id: int, result: dict) -> list[int]:
    """Tip ids on this fixture already settled with an outcome this result contradicts.

    A second results source (`services/bbc_results.py`) may settle a tip days
    before football-data publishes the file. This is football-data's chance to
    disagree: the tip is *not* re-settled -- the site has already shown the
    call -- but a disagreement is surfaced as ATTENTION by the cycle, because a
    wrong score in the timely source is exactly the failure that would
    otherwise be invisible.
    """
    rows = conn.execute(
        "SELECT tip_id, side, outcome FROM tips WHERE fixture_id=?"
        " AND outcome IN ('win', 'lose')", (fixture_id,),
    ).fetchall()
    out = []
    for tip in rows:
        # Margin-aware, like `settle_tips`: a handicap outcome can flip on a
        # one-goal score correction that leaves the 1X2 result intact
        # (2-0 vs 2-1 flips `A+1.5`), which makes this reconciliation *more*
        # load-bearing under v3 than it was for unions.
        won = bool(selection.won_from_score(np.array([tip["side"]]),
                                            np.array([result["fthg"]]),
                                            np.array([result["ftag"]]))[0])
        if ("win" if won else "lose") != tip["outcome"]:
            out.append(tip["tip_id"])
    return out


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

        out.disagreed += reconcile_tips(conn, fixture["fixture_id"], result)
        out.tips_settled += settle_tips(conn, fixture["fixture_id"], result,
                                        dry_run=dry_run)

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
        # Bytes, not `read_text`: a snapshot saved from the feed carries the
        # same BOM the feed does, and it costs the `Div` column the same way.
        texts = [(args.division, args.file.read_bytes().removeprefix(_BOM).decode("cp1252"))]
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
        texts = []
        for division, season in sorted(seasons):
            try:
                texts.append((division, fetch(division, season)))
            except ResultsNotPublished as exc:
                print(f"skipped -- {exc}")

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
