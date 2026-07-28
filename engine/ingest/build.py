"""Build the normalised store from the raw CSVs.

    python -m engine.ingest.build [--db PATH]

Loads with Purpose.LIVE deliberately: the store holds the whole corpus so that
a serving artifact can be fitted on current data. Reads are guarded instead --
see `engine.store`. Building is not measuring, so no ledger entry is made.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from engine import config, db, odds as odds_mod
from engine.ingest import matches as matches_mod, players as players_mod
from engine.ingest.holdout import Purpose
from engine.ingest.teams import FBREF, FOOTBALL_DATA, TeamBridge

MATCH_COLUMNS = (
    "match_id", "season", "division", "match_date", "kickoff_time",
    "home_team_id", "away_team_id",
    "fthg", "ftag", "ftr", "hthg", "htag", "htr", "referee",
    "home_shots", "away_shots", "home_sot", "away_sot",
    "home_corners", "away_corners", "home_fouls", "away_fouls",
    "home_yellow", "away_yellow", "home_red", "away_red",
    *odds_mod.ODDS_FIELDS,
    "odds_era", "source_file",
)

PLAYER_COLUMNS = (
    "season", "division", "player_id", "player_id_kind", "player_name",
    "nation", "position", "age", "born", "team_id", "squad_raw",
    "mp", "starts", "minutes", "nineties",
    "goals", "assists", "goals_non_pk", "pk", "pk_att", "cards_y", "cards_r",
    "source_file",
)


def _rows(frame: pd.DataFrame, columns) -> list[tuple]:
    ordered = frame.reindex(columns=list(columns))
    return [
        tuple(None if pd.isna(v) else v for v in record)
        for record in ordered.itertuples(index=False, name=None)
    ]


def write_teams(conn, bridge: TeamBridge) -> dict[str, int]:
    team_ids = bridge.team_ids()
    conn.executemany(
        "INSERT OR REPLACE INTO teams (team_id, canonical_name) VALUES (?, ?)",
        [(i, name) for name, i in team_ids.items()],
    )
    conn.executemany(
        "INSERT OR REPLACE INTO team_aliases (source, alias, team_id) VALUES (?, ?, ?)",
        [
            (source, alias, team_ids[canonical])
            for (source, alias), canonical in bridge.canonical_by_alias.items()
        ],
    )
    conn.commit()
    return team_ids


#: Columns whose stored SQLite type must stay numeric. A BLOB here means numpy
#: scalars reached the driver unadapted; the rows still count correctly and only
#: aggregates go wrong, so it has to be asserted rather than eyeballed.
NUMERIC_CHECKS = {
    "matches": ("fthg", "ftag", "hthg", "htag", "home_shots", "away_shots",
                "avg_h", "close_ps_h"),
    "player_seasons": ("mp", "starts", "minutes", "nineties", "goals", "assists"),
}


def validate(conn) -> list[str]:
    """Value-level integrity checks. Returns a list of failures (empty is good)."""
    failures = []

    for table, columns in NUMERIC_CHECKS.items():
        for column in columns:
            bad = conn.execute(
                f"SELECT COUNT(*) FROM {table} "
                f"WHERE typeof({column}) NOT IN ('integer','real','null')"
            ).fetchone()[0]
            if bad:
                failures.append(f"{table}.{column}: {bad} rows stored as a non-numeric type")

    # A completed E0 season is 20 clubs x 38 matches x 11 players x 90 minutes.
    # Anything far from 418 team-90s means minutes were mangled on the way in.
    for season, team_90s in conn.execute(
        "SELECT season, SUM(minutes)/90.0/20 FROM player_seasons "
        "WHERE division='E0' GROUP BY season"
    ):
        if team_90s is None or not (410 <= team_90s <= 425):
            failures.append(f"player_seasons E0 {season}: {team_90s} team-90s, expected ~418")

    # Goals in the match corpus must agree with a plain sanity band; English
    # scoring sits near 2.6 goals/match across all four divisions.
    rate = conn.execute("SELECT AVG(fthg + ftag) FROM matches").fetchone()[0]
    if rate is None or not (2.2 <= rate <= 3.0):
        failures.append(f"matches: {rate} goals/match, expected ~2.6")

    expected = {"E0": 6080, "E1": 8832, "E2": 8680, "E3": 8720, "EC": 8610}
    for division, want in expected.items():
        got = conn.execute(
            "SELECT COUNT(*) FROM matches WHERE division=?", (division,)
        ).fetchone()[0]
        if got != want:
            failures.append(f"matches {division}: {got} rows, expected {want}")

    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=None)
    args = parser.parse_args()

    conn = db.connect(args.db)
    applied = db.migrate(conn)
    print(f"migrations applied: {applied or 'none (already current)'}")

    bridge = TeamBridge.load()
    team_ids = write_teams(conn, bridge)
    print(f"teams: {len(team_ids)} canonical, "
          f"{sum(1 for s, _ in bridge.canonical_by_alias if s == FOOTBALL_DATA)} "
          f"football-data aliases, "
          f"{sum(1 for s, _ in bridge.canonical_by_alias if s == FBREF)} fbref aliases")

    match_corpus, match_report = matches_mod.load(purpose=Purpose.LIVE, bridge=bridge)
    frame = match_corpus.frame.copy()
    frame["home_team_id"] = frame["home_team"].map(team_ids)
    frame["away_team_id"] = frame["away_team"].map(team_ids)
    frame["match_date"] = frame["match_date"].dt.strftime("%Y-%m-%d")
    conn.execute("DELETE FROM matches")
    conn.executemany(
        f"INSERT INTO matches ({','.join(MATCH_COLUMNS)}) "
        f"VALUES ({','.join('?' * len(MATCH_COLUMNS))})",
        _rows(frame, MATCH_COLUMNS),
    )
    conn.commit()
    print("\nmatches:", match_report.describe())

    player_corpus, player_report = players_mod.load(purpose=Purpose.LIVE, bridge=bridge)
    pframe = player_corpus.frame.copy()
    pframe["team_id"] = pframe["team"].map(team_ids)
    conn.execute("DELETE FROM player_seasons")
    conn.executemany(
        f"INSERT INTO player_seasons ({','.join(PLAYER_COLUMNS)}) "
        f"VALUES ({','.join('?' * len(PLAYER_COLUMNS))})",
        _rows(pframe, PLAYER_COLUMNS),
    )
    conn.commit()
    print("\nplayer-seasons:", player_report.describe())

    failures = validate(conn)
    print("\nintegrity checks:", "all passed" if not failures else "FAILED")
    for line in failures:
        print(f"  ! {line}")

    print(f"\nstore written to {args.db or config.DB_PATH}")
    conn.close()
    clean = match_report.bridge.clean and player_report.bridge.clean and not failures
    return 0 if clean else 1


if __name__ == "__main__":
    raise SystemExit(main())
