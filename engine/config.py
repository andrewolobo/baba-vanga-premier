"""Paths and environment configuration.

Everything resolves from the repo root so the package works regardless of the
working directory. Overridable by env var for the eventual VPS move.

Settings resolve in one order, and it matters: **real environment variable, then
`.env`, then the default.** The environment winning is what keeps the server
honest -- a systemd `Environment=` line must not be silently overridden by a
`.env` someone left in the checkout months ago. `.env` is gitignored, so it is a
developer convenience for this machine and never a deployment mechanism;
`.env.example` is the tracked list of what it may contain.
"""

from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

#: Parsed by hand rather than adding python-dotenv, matching the one that was
#: already here for LOCATIONIQ_API_KEY (`services/stadium_coords/locationiq.py`).
#: `KEY=value`, `#` comments and blank lines; quotes stripped; nothing else.
def _dotenv(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name, sep, value = line.partition("=")
        if sep:
            values[name.strip()] = value.strip().strip("'\"")
    return values


_FILE = _dotenv(REPO_ROOT / ".env")


def setting(name: str, default: str = "") -> str:
    """One setting, environment first. See the module docstring for the order."""
    return os.environ.get(name) or _FILE.get(name, default)


DATA_DIR = Path(setting("BVP_DATA_DIR") or REPO_ROOT / "data")
MATCH_DIR = DATA_DIR / "play_history"
PLAYER_DIR = DATA_DIR / "player-stats"

REFERENCE_DIR = Path(setting("BVP_REFERENCE_DIR") or REPO_ROOT / "reference")
TEAM_ALIASES_CSV = REFERENCE_DIR / "team_aliases.csv"
BBC_TEAMS_CSV = REFERENCE_DIR / "bbc_teams.csv"

#: Opt-in for the second fixture calendar (`services.bbc_calendar`). Off unless
#: set, because running it is a recorded decision with an exit condition rather
#: than a default -- `OUTSTANDING.md` §4.5.
BBC_CALENDAR_ENABLED = setting("BVP_BBC_CALENDAR") == "1"
#: Opt-in for full-time results from the same pages (`services.bbc_results`),
#: which settle tips before football-data publishes the season's file. Same
#: decision, same exit condition; a separate switch so either can run alone.
BBC_RESULTS_ENABLED = setting("BVP_BBC_RESULTS") == "1"

DB_DIR = REPO_ROOT / "db"
MIGRATIONS_DIR = DB_DIR / "migrations"
#: A libpq connection URL. The default is libpq's own: database `bvp` over the
#: local socket as the OS user on Linux (peer auth on the server), localhost
#: 5432 on Windows. Development machines set it in `.env`; the server sets it
#: in the systemd units. docs/POSTGRES_PLAN.md.
DATABASE_URL = setting("BVP_DATABASE_URL", "postgresql:///bvp")


def relpath(path: Path) -> str:
    """Provenance string for a source file: repo-relative when it is inside the
    repo, absolute otherwise (test fixtures live in a temp directory)."""
    try:
        return str(Path(path).relative_to(REPO_ROOT))
    except ValueError:
        return str(path)
