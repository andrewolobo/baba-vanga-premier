"""Paths and environment configuration.

Everything resolves from the repo root so the package works regardless of the
working directory. Overridable by env var for the eventual VPS move.
"""

from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = Path(os.environ.get("BVP_DATA_DIR", REPO_ROOT / "data"))
MATCH_DIR = DATA_DIR / "play_history"
PLAYER_DIR = DATA_DIR / "player-stats"

REFERENCE_DIR = Path(os.environ.get("BVP_REFERENCE_DIR", REPO_ROOT / "reference"))
TEAM_ALIASES_CSV = REFERENCE_DIR / "team_aliases.csv"

DB_DIR = REPO_ROOT / "db"
MIGRATIONS_DIR = DB_DIR / "migrations"
DB_PATH = Path(os.environ.get("BVP_DB_PATH", DB_DIR / "premier.db"))


def relpath(path: Path) -> str:
    """Provenance string for a source file: repo-relative when it is inside the
    repo, absolute otherwise (test fixtures live in a temp directory)."""
    try:
        return str(Path(path).relative_to(REPO_ROOT))
    except ValueError:
        return str(path)
