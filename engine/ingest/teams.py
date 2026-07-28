"""The team-name bridge.

Pure lookup. No fuzzy matching, no normalisation, no runtime guessing: a name
either appears in reference/team_aliases.csv or it fails. Regenerate that file
with scripts/build_team_aliases.py when new names appear.

SPEC §0.2 is explicit that unbridged teams must be excluded *by name* and
counted, never silently dropped -- a silent drop is invisible sample loss, and
gtleague reached only 79 of 106 clubs before anyone noticed. Hence
`UnbridgedTeam` carries the offending name and `BridgeReport` counts them.
"""

from __future__ import annotations

import csv
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from engine import config

FOOTBALL_DATA = "football-data"
FBREF = "fbref"


class UnbridgedTeam(KeyError):
    """A source name with no entry in the bridge table."""

    def __init__(self, source: str, alias: str):
        self.source = source
        self.alias = alias
        super().__init__(f"no bridge entry for {source} name {alias!r}")


@dataclass
class BridgeReport:
    """Counts of names that failed to bridge, by source and name."""

    misses: Counter = field(default_factory=Counter)

    def record(self, source: str, alias: str) -> None:
        self.misses[(source, alias)] += 1

    @property
    def clean(self) -> bool:
        return not self.misses

    def describe(self) -> str:
        if self.clean:
            return "all team names bridged"
        lines = [f"{len(self.misses)} unbridged name(s):"]
        for (source, alias), n in self.misses.most_common():
            lines.append(f"  {source}: {alias!r} ({n} rows excluded)")
        return "\n".join(lines)


@dataclass(frozen=True)
class TeamBridge:
    canonical_by_alias: dict[tuple[str, str], str]
    canonical_names: tuple[str, ...]

    @classmethod
    def load(cls, path: Path | None = None) -> "TeamBridge":
        target = Path(path or config.TEAM_ALIASES_CSV)
        if not target.exists():
            raise FileNotFoundError(
                f"{target} missing; run scripts/build_team_aliases.py"
            )
        mapping: dict[tuple[str, str], str] = {}
        with target.open("r", encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                key = (row["source"], row["alias"])
                if key in mapping and mapping[key] != row["canonical_name"]:
                    raise ValueError(f"conflicting bridge entries for {key}")
                mapping[key] = row["canonical_name"]
        return cls(mapping, tuple(sorted(set(mapping.values()))))

    def resolve(self, source: str, alias: str) -> str:
        try:
            return self.canonical_by_alias[(source, alias.strip())]
        except KeyError:
            raise UnbridgedTeam(source, alias) from None

    def try_resolve(self, source: str, alias: str) -> str | None:
        return self.canonical_by_alias.get((source, alias.strip()))

    def team_ids(self) -> dict[str, int]:
        """Canonical name -> stable integer id (1-based, alphabetical)."""
        return {name: i for i, name in enumerate(self.canonical_names, start=1)}
