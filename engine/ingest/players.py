"""Load the FBref per-season player tables for all five divisions.

OPEN-1 resolved to case (c): these are per-player, per-club, per-season
aggregates of *completed* seasons. There are no per-match rows, so within-season
as-of correctness is unachievable and the player layer must refresh only at
season boundaries -- see `engine.asof.PLAYER_SEASON_RULE`.

Source quirks, all confirmed by audit:

* **The header is not on a fixed line.** Most files carry a two-line preamble
  (FBref group band, then the real header); `efl-league-one/201112.txt` and
  `efl-league-two/201314.csv` carry three. The header row is found by scanning
  for the line starting `Rk,`.
* **League One files are `.txt`.** A `*.csv` glob silently drops the whole E2
  tier, which is why the extension lives in the division registry.
* **The last column is the FBref player ID** under a mangled `-9999` header.
  It must be read as text: the Championship carries leading-zero ids in 14 of
  16 files, and numeric coercion silently forks a player into two entities.
* **National League ids before 2018-19 are name slugs**, not FBref ids. They
  collide on common names and are not stable, so they are marked and must never
  be joined across seasons or divisions.
* **Mid-season transfers produce two rows** sharing one id. Never group by name;
  five namesake pairs exist in the Championship alone.
"""

from __future__ import annotations

import io
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from engine import config
from engine.ingest.holdout import Corpus, Purpose, resolve_seasons
from engine.ingest.teams import FBREF, BridgeReport, TeamBridge
from engine.seasons import ALL_DIVISIONS, DIVISIONS

ID_HEADER = "-9999"
HEX_ID = re.compile(r"^[0-9a-f]{8}$")

KIND_HEX = "hex"
KIND_SLUG = "slug"
KIND_CORRUPT = "corrupt"

_FIELDS = {
    "player_name": "Player",
    "nation": "Nation",
    "position": "Pos",
    "squad_raw": "Squad",
    "age": "Age",
    "born": "Born",
    "mp": "MP",
    "starts": "Starts",
    "minutes": "Min",
    "nineties": "90s",
    "goals": "Gls",
    "assists": "Ast",
    "goals_non_pk": "G-PK",
    "pk": "PK",
    "pk_att": "PKatt",
    "cards_y": "CrdY",
    "cards_r": "CrdR",
}

INT_FIELDS = ("age", "born", "mp", "starts", "minutes", "goals", "assists",
              "goals_non_pk", "pk", "pk_att", "cards_y", "cards_r")


@dataclass
class PlayerLoadReport:
    files: int = 0
    rows_read: int = 0
    rows_loaded: int = 0
    slug_ids: int = 0
    corrupt_ids: int = 0
    dropped_unbridged: int = 0
    bridge: BridgeReport = field(default_factory=BridgeReport)

    def describe(self) -> str:
        return (
            f"{self.rows_loaded} player-seasons from {self.files} files "
            f"(read {self.rows_read}; {self.slug_ids} slug ids, "
            f"{self.corrupt_ids} corrupt ids, "
            f"{self.dropped_unbridged} unbridged)\n" + self.bridge.describe()
        )


def player_file(season: str, division: str, root: Path | None = None) -> Path:
    div = DIVISIONS[division]
    base = Path(root or config.PLAYER_DIR)
    if div.player_subdir != ".":
        base = base / div.player_subdir
    return base / f"{season}{div.player_suffix}"


def read_table(path: Path) -> pd.DataFrame:
    """Read one FBref export, locating the header rather than assuming its line."""
    text = path.read_bytes().decode("utf-8-sig")
    lines = text.splitlines()
    try:
        start = next(i for i, line in enumerate(lines) if line.startswith("Rk,"))
    except StopIteration:
        raise ValueError(f"{path}: no header row starting 'Rk,'") from None
    body = "\n".join(lines[start:])
    return pd.read_csv(io.StringIO(body), dtype=str, keep_default_na=False, na_values=[""])


def classify_id(raw: str) -> tuple[str, str]:
    """(id, kind). Zero-pads short all-digit ids; flags slugs and corruption."""
    value = (raw or "").strip()
    if not value:
        return "", KIND_CORRUPT
    if "E+" in value.upper() or "." in value:
        # Excel rendered the id in scientific notation; the digits are gone.
        return value, KIND_CORRUPT
    if value.isdigit():
        value = value.zfill(8)
    lowered = value.lower()
    if HEX_ID.match(lowered):
        return lowered, KIND_HEX
    return value, KIND_SLUG


def _clean_int(series: pd.Series) -> pd.Series:
    """FBref writes thousands separators in Min and years-days in Age."""
    text = series.astype("string").str.replace(",", "", regex=False)
    text = text.str.split("-").str[0]
    return pd.to_numeric(text, errors="coerce").astype("Int64")


def load_file(path: Path, season: str, division: str, bridge: TeamBridge,
              report: PlayerLoadReport) -> pd.DataFrame:
    raw = read_table(path)
    report.files += 1
    report.rows_read += len(raw)

    id_col = ID_HEADER if ID_HEADER in raw.columns else raw.columns[-1]
    out = pd.DataFrame(index=raw.index)
    out["season"] = season
    out["division"] = division
    out["source_file"] = config.relpath(path)

    for field_name, source_col in _FIELDS.items():
        out[field_name] = raw[source_col] if source_col in raw.columns else pd.NA

    classified = raw[id_col].map(classify_id)
    out["player_id"] = [c[0] for c in classified]
    out["player_id_kind"] = [c[1] for c in classified]

    out = out[out["player_name"].notna() & out["squad_raw"].notna()].copy()

    for field_name in INT_FIELDS:
        out[field_name] = _clean_int(out[field_name])
    out["nineties"] = pd.to_numeric(
        out["nineties"].astype("string").str.replace(",", "", regex=False), errors="coerce"
    )

    team = out["squad_raw"].map(lambda n: bridge.try_resolve(FBREF, n))
    unbridged = team.isna()
    if unbridged.any():
        for name in out.loc[unbridged, "squad_raw"]:
            report.bridge.record(FBREF, name)
        report.dropped_unbridged += int(unbridged.sum())
        out = out[~unbridged].copy()
        team = team[~unbridged]
    out["team"] = team

    report.slug_ids += int((out["player_id_kind"] == KIND_SLUG).sum())
    report.corrupt_ids += int((out["player_id_kind"] == KIND_CORRUPT).sum())
    report.rows_loaded += len(out)
    return out


def load(
    *,
    purpose: Purpose = Purpose.DEV,
    seasons: tuple[str, ...] | None = None,
    divisions: tuple[str, ...] = ALL_DIVISIONS,
    bridge: TeamBridge | None = None,
    conn: sqlite3.Connection | None = None,
    unseal_reason: str | None = None,
    player_dir: Path | None = None,
) -> tuple[Corpus, PlayerLoadReport]:
    """Load player-seasons, honouring the holdout seal.

    The same seal applies as for matches: a Purpose.DEV load stops at 2022-23.
    The 2025-26 file is both sealed and the N-1 prior for live 2026-27, which is
    exactly the case Purpose.LIVE exists for.
    """
    resolved = resolve_seasons(
        purpose, seasons, conn=conn, unseal_reason=unseal_reason, name="players.load"
    )
    bridge = bridge or TeamBridge.load()
    report = PlayerLoadReport()

    frames = []
    for season in resolved:
        for division in divisions:
            if division not in DIVISIONS:
                raise ValueError(f"unknown division {division!r}")
            path = player_file(season, division, player_dir)
            if path.exists():
                frames.append(load_file(path, season, division, bridge, report))

    frame = (
        pd.concat(frames, ignore_index=True)
        if frames
        else pd.DataFrame(columns=["season", "division", "player_id"])
    )
    return Corpus(frame, purpose, tuple(resolved), tuple(divisions)), report
