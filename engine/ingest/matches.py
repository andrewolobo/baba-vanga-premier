"""Load the football-data.co.uk match corpus into one normalised frame.

Source quirks this handles, all confirmed by audit rather than assumed:

* **cp1252, not UTF-8.** `King's Lynn` carries a 0x92 curly apostrophe that
  raises under UTF-8. Every file decodes as cp1252.
* **Columns are selected by name, never position.** Header width grows from 62
  to 133 columns over the corpus as bookmakers come and go, and 2025-26 E3
  carries a phantom trailing empty column.
* **Two date formats**, dd/mm/yy in the early files and dd/mm/yyyy later.
* **`Time` exists only from 2019-20**; before that kickoff is unknown, which is
  what limits the kickoff-slot feature to seven seasons.
* **Stat columns are absent for EC from 2016-17** and land as NULL rather than
  causing the division to be skipped.
* **Two odds eras** (Betbrain aggregates to 2018-19, market Avg/Max after),
  unified by `engine.odds`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from engine import config, db, odds as odds_mod
from engine.ingest.holdout import Corpus, Purpose, resolve_seasons
from engine.ingest.teams import FOOTBALL_DATA, BridgeReport, TeamBridge
from engine.seasons import ALL_DIVISIONS, DIVISIONS

ENCODING = "cp1252"

_CORE = {
    "match_date": "Date",
    "kickoff_time": "Time",
    "home_raw": "HomeTeam",
    "away_raw": "AwayTeam",
    "fthg": "FTHG",
    "ftag": "FTAG",
    "ftr": "FTR",
    "hthg": "HTHG",
    "htag": "HTAG",
    "htr": "HTR",
    "referee": "Referee",
}

_STATS = {
    "home_shots": "HS",
    "away_shots": "AS",
    "home_sot": "HST",
    "away_sot": "AST",
    "home_corners": "HC",
    "away_corners": "AC",
    "home_fouls": "HF",
    "away_fouls": "AF",
    "home_yellow": "HY",
    "away_yellow": "AY",
    "home_red": "HR",
    "away_red": "AR",
}

INT_FIELDS = ("fthg", "ftag", "hthg", "htag", *_STATS)


@dataclass
class LoadReport:
    files: int = 0
    rows_read: int = 0
    rows_loaded: int = 0
    dropped_blank: int = 0
    dropped_no_result: int = 0
    dropped_unbridged: int = 0
    bridge: BridgeReport = field(default_factory=BridgeReport)

    def describe(self) -> str:
        return (
            f"{self.rows_loaded} matches from {self.files} files "
            f"(read {self.rows_read}; dropped {self.dropped_blank} blank, "
            f"{self.dropped_no_result} without a result, "
            f"{self.dropped_unbridged} unbridged)\n" + self.bridge.describe()
        )


def _parse_dates(raw: pd.Series) -> pd.Series:
    """dd/mm/yyyy with a dd/mm/yy fallback. Never guesses month-first."""
    parsed = pd.to_datetime(raw, format="%d/%m/%Y", errors="coerce")
    missing = parsed.isna() & raw.notna()
    if missing.any():
        parsed = parsed.fillna(
            pd.to_datetime(raw.where(missing), format="%d/%m/%y", errors="coerce")
        )
    return parsed


def _normalise_time(raw: pd.Series) -> pd.Series:
    """'19:45' -> '19:45'. Absent before 2019-20, so may be entirely NA."""
    text = raw.astype("string").str.strip()
    return text.where(text.str.match(r"^\d{1,2}:\d{2}$", na=False))


def load_file(path: Path, season: str, division: str, bridge: TeamBridge,
              report: LoadReport) -> pd.DataFrame:
    raw = pd.read_csv(path, encoding=ENCODING, low_memory=False)
    report.files += 1
    report.rows_read += len(raw)

    era = odds_mod.detect_era(raw.columns)
    out = pd.DataFrame(index=raw.index)
    out["season"] = season
    out["division"] = division
    out["odds_era"] = era
    out["source_file"] = config.relpath(path)

    for field_name, source_col in _CORE.items():
        out[field_name] = raw[source_col] if source_col in raw.columns else pd.NA
    for field_name, source_col in _STATS.items():
        out[field_name] = raw[source_col] if source_col in raw.columns else pd.NA
    for field_name, source_col in odds_mod.column_map(era).items():
        out[field_name] = (
            pd.to_numeric(raw[source_col], errors="coerce")
            if source_col in raw.columns
            else pd.NA
        )

    blank = out["match_date"].isna() | out["home_raw"].isna() | out["away_raw"].isna()
    report.dropped_blank += int(blank.sum())
    out = out[~blank].copy()

    out["match_date"] = _parse_dates(out["match_date"])
    out["kickoff_time"] = _normalise_time(out["kickoff_time"])
    for field_name in INT_FIELDS:
        out[field_name] = pd.to_numeric(out[field_name], errors="coerce").astype("Int64")

    no_result = out["ftr"].isna() | out["match_date"].isna()
    report.dropped_no_result += int(no_result.sum())
    out = out[~no_result].copy()

    # Bridge both sides. An unbridged name is excluded BY NAME and counted --
    # never dropped silently (SPEC §0.2).
    home = out["home_raw"].map(lambda n: bridge.try_resolve(FOOTBALL_DATA, n))
    away = out["away_raw"].map(lambda n: bridge.try_resolve(FOOTBALL_DATA, n))
    unbridged = home.isna() | away.isna()
    if unbridged.any():
        for name in out.loc[home.isna(), "home_raw"]:
            report.bridge.record(FOOTBALL_DATA, name)
        for name in out.loc[away.isna(), "away_raw"]:
            report.bridge.record(FOOTBALL_DATA, name)
        report.dropped_unbridged += int(unbridged.sum())
        out = out[~unbridged].copy()
        home, away = home[~unbridged], away[~unbridged]

    out["home_team"] = home
    out["away_team"] = away
    out["match_id"] = (
        season + ":" + division + ":"
        + out["match_date"].dt.strftime("%Y-%m-%d") + ":"
        + out["home_team"] + ":" + out["away_team"]
    )
    report.rows_loaded += len(out)
    return out.drop(columns=["home_raw", "away_raw"])


def load(
    *,
    purpose: Purpose = Purpose.DEV,
    seasons: tuple[str, ...] | None = None,
    divisions: tuple[str, ...] = ALL_DIVISIONS,
    bridge: TeamBridge | None = None,
    conn: db.Connection | None = None,
    unseal_reason: str | None = None,
    match_dir: Path | None = None,
) -> tuple[Corpus, LoadReport]:
    """Load matches, honouring the holdout seal.

    Defaults to Purpose.DEV, i.e. 2010-11..2022-23 only. See
    `engine.ingest.holdout` for why fitting and measuring differ here.
    """
    resolved = resolve_seasons(
        purpose, seasons, conn=conn, unseal_reason=unseal_reason, name="matches.load"
    )
    bridge = bridge or TeamBridge.load()
    root = Path(match_dir or config.MATCH_DIR)
    report = LoadReport()

    frames = []
    for season in resolved:
        for division in divisions:
            if division not in DIVISIONS:
                raise ValueError(f"unknown division {division!r}")
            path = root / season / f"{division}.csv"
            if path.exists():
                frames.append(load_file(path, season, division, bridge, report))

    frame = (
        pd.concat(frames, ignore_index=True)
        if frames
        else pd.DataFrame(columns=["match_id", "season", "division"])
    )
    if len(frame):
        frame = frame.sort_values(["match_date", "division", "match_id"]).reset_index(drop=True)
    return Corpus(frame, purpose, tuple(resolved), tuple(divisions)), report
