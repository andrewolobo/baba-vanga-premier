"""Scraper settings: defaults in code, overridden by a TOML file, then by CLI flags.

Everything that a run might reasonably need to move -- where the cache lives,
how hard to throttle, which competitions to keep -- is here rather than spread
through the modules, because the rate limit and the session paths are the two
things a caller has to get right and the two things worth reading in one place.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, fields
from pathlib import Path

DATA_DIR = Path("data/fbref")

#: Settings whose TOML value is a string but whose in-code type is a Path.
_PATH_FIELDS = frozenset({"out", "cache_dir", "profile_dir", "session_file"})


@dataclass(frozen=True)
class ScraperConfig:
    date_from: str = ""
    date_to: str = ""
    #: Competition ids to keep. Empty means every competition on the page.
    comps: tuple[int, ...] = ()
    out: Path = DATA_DIR / "fixtures.csv"
    format: str = "csv"
    cache_dir: Path = DATA_DIR / "raw"
    profile_dir: Path = DATA_DIR / "chrome_profile"
    session_file: Path = DATA_DIR / "cf_session.json"
    #: Seconds between live requests. Sports Reference blocks for ~24h above
    #: roughly 10/min, so the default sits well under it.
    min_interval: float = 6.0
    #: Session refreshes to attempt when a fetch comes back challenged.
    retries: int = 1
    #: The probe never cleared the challenge headless; the toggle exists so a
    #: future run can retry it without an edit.
    headless: bool = False


def load(path: Path | None = None, **overrides) -> ScraperConfig:
    """Defaults, then the TOML file if given, then any non-None override."""
    values: dict = {}
    if path is not None:
        values.update(tomllib.loads(Path(path).read_text(encoding="utf-8")))
    values.update({k: v for k, v in overrides.items() if v is not None})

    unknown = set(values) - {f.name for f in fields(ScraperConfig)}
    if unknown:
        raise ValueError(f"unknown setting(s): {', '.join(sorted(unknown))}")

    if "comps" in values:
        values["comps"] = tuple(int(c) for c in values["comps"])
    for name in _PATH_FIELDS & set(values):
        values[name] = Path(values[name])
    if values.get("format", "csv") not in ("csv", "jsonl"):
        raise ValueError(f"format must be csv or jsonl, not {values['format']!r}")
    return ScraperConfig(**values)
