"""One-off authoring tool: generate reference/team_aliases.csv.

Run this only when new team names appear in the sources (a promotion from
outside the five divisions, or a rename). The engine NEVER normalises names at
runtime -- it does a pure dict lookup against the generated file, so that an
unrecognised name fails loudly instead of being silently fuzzy-matched into the
wrong club. The normalisation here is authoring convenience, reviewed by a
human once, not a runtime behaviour.

    python scripts/build_team_aliases.py [--check]

--check exits non-zero if the file on disk is stale, for CI.
"""

from __future__ import annotations

import argparse
import csv
import io
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine import config
from engine.seasons import DIVISIONS, SEASONS

FOOTBALL_DATA = "football-data"
FBREF = "fbref"
BBC = "bbc"

#: fbref squad name -> football-data name, for pairs the normaliser cannot
#: reach (football-data drops the suffix: "Birmingham City" -> "Birmingham").
#: Reviewed by hand 2026-07-28 against the season ranges each name appears in.
MANUAL_FBREF_TO_FD = {
    "Aldershot Town": "Aldershot",
    "Birmingham City": "Birmingham",
    "Bradford City": "Bradford",
    "Burton Albion": "Burton",
    "Cardiff City": "Cardiff",
    "Carlisle United": "Carlisle",
    "Charlton Athletic": "Charlton",
    "Coventry City": "Coventry",
    "Crewe Alexandra": "Crewe",
    "Derby County": "Derby",
    "Eastbourne": "Eastbourne Borough",
    "Ebbsfleet United": "Ebbsfleet",
    "Exeter City": "Exeter",
    "FC Halifax Town": "Halifax",
    "Grimsby Town": "Grimsby",
    "Harriers": "Kidderminster",  # Kidderminster Harriers, fbref short form
    "Harrogate Town": "Harrogate",
    "Havant & W'ville": "Havant & Waterlooville",
    "Hereford United": "Hereford",
    "Hull City": "Hull",
    "Hyde": "Hyde United",
    "Ipswich Town": "Ipswich",
    "Leeds United": "Leeds",
    "Leicester City": "Leicester",
    "Lincoln City": "Lincoln",
    "Luton Town": "Luton",
    "MK Dons": "Milton Keynes Dons",
    "Maidstone Utd": "Maidstone",
    "Manchester City": "Man City",
    "Manchester Utd": "Man United",
    "Mansfield Town": "Mansfield",
    "N Ferriby Utd": "North Ferriby",
    "Norwich City": "Norwich",
    "Nottingham": "Nott'm Forest",
    "Oldham Athletic": "Oldham",
    "Oxford United": "Oxford",  # NOT Oxford City -- a different club
    "Peterborough": "Peterboro",
    "Plymouth Argyle": "Plymouth",
    "R&D": "Rushden & D",  # Rushden & Diamonds
    "Salford City FC": "Salford",
    "Salisbury City": "Salisbury",
    "Solihull Moors": "Solihull",
    "Southend United": "Southend",
    "Stoke City": "Stoke",
    "Sutton United": "Sutton",
    "Swansea City": "Swansea",
    "Swindon Town": "Swindon",
    "Telford United": "Telford United",
    "Torquay United": "Torquay",
    "Tranmere Rovers": "Tranmere",
    "Truro City FC": "Truro",
    "Wigan Athletic": "Wigan",
    "Yeovil Town": "Yeovil",
    "York City": "York",
}

#: football-data writes two names for one club. Left side folds into the right.
#: Telford: "AFC Telford United" appears only in 2011-12, "Telford United" in
#: 2012-13 onward. The phoenix club is the only Telford in the pyramid across
#: this corpus, so these are one entity.
FD_SELF_ALIASES = {
    "AFC Telford United": "Telford United",
}

_SUFFIX = re.compile(r"\b(fc|afc)\b")


def _read_bbc_teams(path: Path) -> list[tuple[str, str]]:
    """(canonical_name, bbc_urn) from the hand-reviewed reference file.

    Unlike the other two sources, BBC names are not derivable from anything on
    disk -- they come from a live page -- so the mapping is authored once into
    `reference/bbc_teams.csv` and reviewed there rather than in a dict here.
    The alias stored is the **URN**, not the display name: it is present on
    every English side, it is stable across renames, and it makes the lookup a
    machine key rather than a spelling.
    """
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as fh:
        return [(row["canonical_name"].strip(), row["bbc_urn"].strip())
                for row in csv.DictReader(fh)]


def normalise(name: str) -> str:
    s = name.lower().replace("&", "and").replace("'", "").replace("’", "")
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    s = _SUFFIX.sub(" ", s)
    s = s.replace(" united", " utd").replace(" rovers", " rvs")
    return re.sub(r"\s+", " ", s).strip()


def _read_fbref_squads(path: Path) -> set[str]:
    lines = path.read_bytes().decode("utf-8-sig").splitlines()
    header = next(i for i, ln in enumerate(lines) if ln.startswith("Rk,"))
    rows = csv.DictReader(io.StringIO("\n".join(lines[header:])))
    return {(r.get("Squad") or "").strip() for r in rows if (r.get("Squad") or "").strip()}


def collect_names() -> tuple[set[str], set[str]]:
    """(football-data names, fbref squad names) across the whole corpus."""
    fd: set[str] = set()
    for season in SEASONS:
        for code in DIVISIONS:
            path = config.MATCH_DIR / season / f"{code}.csv"
            if not path.exists():
                continue
            text = path.read_bytes().decode("cp1252")
            for row in csv.DictReader(io.StringIO(text)):
                for key in ("HomeTeam", "AwayTeam"):
                    name = (row.get(key) or "").strip()
                    if name:
                        fd.add(name)

    fb: set[str] = set()
    for season in SEASONS:
        for div in DIVISIONS.values():
            base = config.PLAYER_DIR if div.player_subdir == "." else (
                config.PLAYER_DIR / div.player_subdir
            )
            path = base / f"{season}{div.player_suffix}"
            if path.exists():
                fb |= _read_fbref_squads(path)
    return fd, fb


def bbc_rows(canonicals: set[str]) -> tuple[list[tuple[str, str, str]], list[str]]:
    """(rows, unresolved) for the BBC source.

    The reference file already carries the canonical name, so the only thing to
    check is that it names a club that actually exists. That check is the point:
    a typo would otherwise mint a phantom canonical club that nothing else in
    the corpus refers to, and the bridge would resolve to it happily.
    """
    rows, unresolved = [], []
    for canonical, urn in _read_bbc_teams(config.BBC_TEAMS_CSV):
        if canonical not in canonicals:
            unresolved.append(f"{urn!r} -> {canonical!r} (no such canonical club)")
            continue
        rows.append((canonical, BBC, urn))
    return rows, unresolved


def build_rows() -> list[tuple[str, str, str]]:
    fd_names, fb_names = collect_names()

    canonical_of_fd = {n: FD_SELF_ALIASES.get(n, n) for n in fd_names}
    canonicals = set(canonical_of_fd.values())

    by_norm: dict[str, list[str]] = {}
    for canonical in canonicals:
        by_norm.setdefault(normalise(canonical), []).append(canonical)

    rows: list[tuple[str, str, str]] = []
    for fd_name, canonical in sorted(canonical_of_fd.items()):
        rows.append((canonical, FOOTBALL_DATA, fd_name))

    unresolved = []
    for fb_name in sorted(fb_names):
        if fb_name in MANUAL_FBREF_TO_FD:
            target = MANUAL_FBREF_TO_FD[fb_name]
            canonical = canonical_of_fd.get(target, FD_SELF_ALIASES.get(target, target))
            if target not in canonical_of_fd and target not in canonicals:
                unresolved.append(f"{fb_name!r} -> {target!r} (no such football-data name)")
                continue
        else:
            hits = by_norm.get(normalise(fb_name), [])
            if len(hits) != 1:
                unresolved.append(f"{fb_name!r} (normalised {normalise(fb_name)!r}, hits={hits})")
                continue
            canonical = hits[0]
        rows.append((canonical, FBREF, fb_name))

    bbc, bbc_unresolved = bbc_rows(canonicals)
    rows.extend(bbc)
    unresolved.extend(bbc_unresolved)

    if unresolved:
        raise SystemExit(
            "Cannot bridge these names; fix MANUAL_FBREF_TO_FD or "
            "reference/bbc_teams.csv:\n  " + "\n  ".join(unresolved)
        )
    return sorted(set(rows))


def render(rows) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(["canonical_name", "source", "alias"])
    writer.writerows(rows)
    return buf.getvalue()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail if the file is stale")
    args = parser.parse_args()

    rows = build_rows()
    text = render(rows)
    path = config.TEAM_ALIASES_CSV

    if args.check:
        current = path.read_text(encoding="utf-8") if path.exists() else ""
        if current != text:
            print(f"{path} is stale; re-run scripts/build_team_aliases.py", file=sys.stderr)
            return 1
        print(f"{path} is current ({len(rows)} aliases)")
        return 0

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    clubs = len({r[0] for r in rows})
    counts = {source: sum(1 for r in rows if r[1] == source)
              for source in (FOOTBALL_DATA, FBREF, BBC)}
    print(f"wrote {path}")
    print(f"  {clubs} canonical clubs, "
          + ", ".join(f"{n} {source} aliases" for source, n in counts.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
