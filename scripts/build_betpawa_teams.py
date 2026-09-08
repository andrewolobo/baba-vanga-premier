"""One-off authoring tool: reference/betpawa_teams.csv from a saved capture.

    python scripts/build_betpawa_teams.py docs/bp/fixtures/betpawa_efl_upcoming_2026-09-08.json

Reads every participant in a saved `by-queries` capture (`services.betpawa_feed`),
proposes the canonical club for each by normalised-name match against every
name the bridge already knows (canonical names and the football-data, fbref
and BBC aliases), applies the hand-reviewed exceptions below, and rewrites the
reference file -- keeping every row already in it, since a reviewed row
outranks a fresh guess. It refuses to write while any participant is
unresolved: a club the pyramid has not shown us before is a human decision,
not a fuzzy match (SPEC 0.2). Then re-run scripts/build_team_aliases.py to
fold the file into the bridge, which is what the engine actually reads.

The alias stored is the **participant id**, not the display name: it is the
same on every betPawa country site and survives a rename. The name is kept
beside it so the file can be reviewed by a person.
"""

from __future__ import annotations

import argparse
import csv
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_team_aliases import normalise  # noqa: E402  (a sibling script)

from engine import config  # noqa: E402
from engine.ingest.teams import TeamBridge  # noqa: E402
from services import betpawa_feed  # noqa: E402

#: betPawa display name -> canonical name, for the pairs the normaliser
#: cannot reach. Reviewed by hand 2026-09-08 against the 92 E0-E3 clubs.
MANUAL = {
    "Manchester United": "Man United",
    "Queens Park Rangers": "QPR",
    "Sheffield Wednesday": "Sheffield Weds",
    "Wolverhampton Wanderers": "Wolves",
    "Leyton Orient London": "Leyton Orient",
    "Milton Keynes Dons": "Milton Keynes Dons",
}

COLUMNS = ["betpawa_id", "betpawa_name", "canonical_name"]


def read_existing(path: Path) -> dict[str, tuple[str, str]]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8", newline="") as fh:
        return {row["betpawa_id"].strip(): (row["betpawa_name"].strip(),
                                             row["canonical_name"].strip())
                for row in csv.DictReader(fh)}


def known_names(bridge: TeamBridge) -> dict[str, set[str]]:
    """normalised name -> canonical clubs it could mean, from everything the
    bridge and the BBC reference already carry."""
    by_norm: dict[str, set[str]] = {}
    for canonical in bridge.canonical_names:
        by_norm.setdefault(normalise(canonical), set()).add(canonical)
    for (source, alias), canonical in bridge.canonical_by_alias.items():
        if not alias.startswith("urn:") and not alias.isdigit():
            by_norm.setdefault(normalise(alias), set()).add(canonical)
    if config.BBC_TEAMS_CSV.exists():
        with config.BBC_TEAMS_CSV.open("r", encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                by_norm.setdefault(normalise(row["bbc_name"]), set()).add(
                    row["canonical_name"].strip())
    return by_norm


def propose(participants: dict[str, str], bridge: TeamBridge,
            existing: dict[str, tuple[str, str]]) -> tuple[list[tuple[str, str, str]], list[str]]:
    """(rows, unresolved). `participants` is id -> betPawa name."""
    by_norm = known_names(bridge)
    canonicals = set(bridge.canonical_names)
    rows = {pid: (name, canonical) for pid, (name, canonical) in existing.items()}
    unresolved = []
    for pid, name in sorted(participants.items(), key=lambda kv: kv[1]):
        if pid in rows:
            continue
        if name in MANUAL:
            canonical = MANUAL[name]
            if canonical not in canonicals:
                unresolved.append(f"{name!r} -> {canonical!r} (no such canonical club)")
                continue
        else:
            hits = by_norm.get(normalise(name), set())
            if len(hits) != 1:
                unresolved.append(f"{name!r} (id {pid}, normalised {normalise(name)!r}, hits={sorted(hits)})")
                continue
            canonical = next(iter(hits))
        rows[pid] = (name, canonical)
    return sorted((pid, name, canonical) for pid, (name, canonical) in rows.items()), unresolved


def render(rows) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(COLUMNS)
    writer.writerows(rows)
    return buf.getvalue()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("capture", type=Path, help="a saved by-queries body")
    parser.add_argument("--dry-run", action="store_true", help="print, do not write")
    args = parser.parse_args()

    parsed = betpawa_feed.parse(betpawa_feed.load_capture(args.capture))
    participants: dict[str, str] = {}
    for event in parsed.events:
        participants[event.home_id] = event.home_name
        participants[event.away_id] = event.away_name

    bridge = TeamBridge.load()
    existing = read_existing(config.BETPAWA_TEAMS_CSV)
    rows, unresolved = propose(participants, bridge, existing)
    if unresolved:
        print("Cannot bridge these participants; add them to MANUAL:\n  "
              + "\n  ".join(unresolved), file=sys.stderr)
        return 1

    text = render(rows)
    new = len(rows) - len(existing)
    if args.dry_run:
        print(text, end="")
    else:
        config.BETPAWA_TEAMS_CSV.write_text(text, encoding="utf-8")
        print(f"wrote {config.BETPAWA_TEAMS_CSV}: {len(rows)} clubs ({new} new)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
