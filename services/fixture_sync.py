"""Pull upcoming fixtures and their opening prices from football-data.co.uk.

    python -m services.fixture_sync            # fetch and upsert
    python -m services.fixture_sync --dry-run  # show what would change
    python -m services.fixture_sync --file X   # replay a saved snapshot

One file carries all four English divisions with prices attached, and it comes
from the same publisher as the historical corpus, so club naming matches the
bridge by construction rather than by luck.

Two properties of the feed shape the code:

*It is a rolling ~7-day window, not a fixture list.* There is no way to ask it
for the season. Anything needing a full calendar needs another source.

*It republishes the same fixture with updated prices.* So an upsert on
(division, date, home, away) is the normal path. `first_seen_at` is preserved
and `updated_at` moves, because when we first saw a price is the interesting
question for an information-set argument later.

Unbridged club names are excluded by name and counted, never silently dropped
(SPEC §0.2). On this feed that should never fire -- every English club is in the
bridge -- so if it does, a new club has been promoted from outside the corpus
and `scripts/build_team_aliases.py` needs re-running.
"""

from __future__ import annotations

import argparse
import csv
import io
import sqlite3
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from engine import db
from engine.ingest.teams import FOOTBALL_DATA, BridgeReport, TeamBridge
from engine.seasons import SERVED_DIVISIONS

FIXTURES_URL = "https://www.football-data.co.uk/fixtures.csv"

#: Feed column -> our column. The feed publishes the modern market-era schema,
#: which is the same one `matches` stores, so nothing has to be translated.
_ODDS_COLUMNS = {
    "AvgH": "avg_h", "AvgD": "avg_d", "AvgA": "avg_a",
    "MaxH": "max_h", "MaxD": "max_d", "MaxA": "max_a",
    "Avg>2.5": "avg_over25", "Avg<2.5": "avg_under25",
    "AHh": "ah_line", "AvgAHH": "avg_ah_h", "AvgAHA": "avg_ah_a",
}

UPSERT_COLUMNS = ("kickoff_time", *_ODDS_COLUMNS.values())


@dataclass
class SyncReport:
    fetched: int = 0
    english: int = 0
    inserted: int = 0
    updated: int = 0
    report: BridgeReport = None  # type: ignore[assignment]

    def describe(self) -> str:
        lines = [
            f"fetched {self.fetched} rows ({self.english} in E0-E3); "
            f"{self.inserted} new, {self.updated} updated",
        ]
        if self.report is not None:
            lines.append(self.report.describe())
        return "\n".join(lines)


def fetch(url: str = FIXTURES_URL, timeout: int = 30) -> str:
    with urllib.request.urlopen(url, timeout=timeout) as response:  # noqa: S310
        return response.read().decode("utf-8-sig")


def parse(text: str) -> list[dict]:
    """Feed rows for the served divisions, with odds coerced to float."""
    rows = []
    for raw in csv.DictReader(io.StringIO(text)):
        if raw.get("Div") not in SERVED_DIVISIONS:
            continue
        if not raw.get("HomeTeam") or not raw.get("AwayTeam"):
            continue
        row = {
            "division": raw["Div"],
            "match_date": _iso_date(raw["Date"]),
            "kickoff_time": (raw.get("Time") or "").strip() or None,
            "home": raw["HomeTeam"].strip(),
            "away": raw["AwayTeam"].strip(),
        }
        for source, target in _ODDS_COLUMNS.items():
            row[target] = _float(raw.get(source))
        rows.append(row)
    return rows


def _iso_date(value: str) -> str:
    """dd/mm/yyyy or dd/mm/yy -> ISO. The feed has used both forms."""
    day, month, year = value.strip().split("/")
    if len(year) == 2:
        year = f"20{year}"
    return f"{year}-{int(month):02d}-{int(day):02d}"


def _float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _resolve_pair(row, bridge, ids, report) -> tuple[int, int] | None:
    """(home_id, away_id), or None with both failures recorded by name.

    A club can fail two ways, needing different fixes: absent from the alias
    table (re-run `build_team_aliases.py`), or present there but absent from
    `teams`. The second should be impossible, since `teams` is built from the
    bridge -- but an unhandled KeyError would take the sync down on a matchday
    morning, and impossible states arrive unannounced.
    """
    out = []
    for raw in (row["home"], row["away"]):
        canonical = bridge.try_resolve(FOOTBALL_DATA, raw)
        if canonical is None or canonical not in ids:
            report.record(FOOTBALL_DATA, raw)
            out.append(None)
        else:
            out.append(ids[canonical])
    return None if None in out else (out[0], out[1])


def sync(conn: sqlite3.Connection, text: str, source_file: str,
         *, dry_run: bool = False) -> SyncReport:
    bridge = TeamBridge.load()
    ids = {row["canonical_name"]: row["team_id"]
           for row in conn.execute("SELECT team_id, canonical_name FROM teams")}
    rows = parse(text)
    total = sum(1 for _ in csv.DictReader(io.StringIO(text)))
    out = SyncReport(fetched=total, english=len(rows), report=BridgeReport())

    for row in rows:
        resolved = _resolve_pair(row, bridge, ids, out.report)
        if resolved is None:
            continue
        key = (row["division"], row["match_date"], *resolved)
        existing = conn.execute(
            "SELECT fixture_id FROM fixtures WHERE division=? AND match_date=? "
            "AND home_team_id=? AND away_team_id=?", key,
        ).fetchone()

        if existing:
            out.updated += 1
            if not dry_run:
                assignments = ", ".join(f"{c}=?" for c in UPSERT_COLUMNS)
                conn.execute(
                    f"UPDATE fixtures SET {assignments}, updated_at=datetime('now'), "
                    "source_file=? WHERE fixture_id=?",
                    [*(row[c] for c in UPSERT_COLUMNS), source_file, existing["fixture_id"]],
                )
        else:
            out.inserted += 1
            if not dry_run:
                conn.execute(
                    "INSERT INTO fixtures (division, match_date, home_team_id, away_team_id,"
                    f" {', '.join(UPSERT_COLUMNS)}, source_file)"
                    f" VALUES (?, ?, ?, ?, {', '.join('?' * len(UPSERT_COLUMNS))}, ?)",
                    [*key, *(row[c] for c in UPSERT_COLUMNS), source_file],
                )
    if not dry_run:
        conn.commit()
    return out


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, help="replay a saved snapshot instead of fetching")
    parser.add_argument("--url", default=FIXTURES_URL)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--save", type=Path, help="write the fetched feed here")
    args = parser.parse_args(argv)

    if args.file:
        text, source = args.file.read_text(encoding="utf-8-sig"), str(args.file)
    else:
        text, source = fetch(args.url), args.url
        if args.save:
            args.save.write_text(text, encoding="utf-8")

    conn = db.connect()
    db.migrate(conn)
    report = sync(conn, text, source, dry_run=args.dry_run)
    print(report.describe())
    if args.dry_run:
        print("(dry run -- nothing written)")
    if not report.report.clean:
        print("\nUnbridged names mean a club outside the corpus is now playing in "
              "E0-E3. Re-run scripts/build_team_aliases.py before serving.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
