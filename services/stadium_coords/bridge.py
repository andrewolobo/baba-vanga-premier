"""Corpus club name -> Wikidata club, by exact match on a normalised form.

**There is deliberately no fuzzy matching here**, and the recon that preceded
this module is the reason. The corpus contains `Oxford` (Oxford United, E2/E3)
and `Oxford City` (National League) as separate clubs, and Wikidata contains
`Bradford City` alongside `Bradford (Park Avenue)`. Every edit-distance or
prefix rule that resolves the football-data abbreviations also collapses those
pairs, and it does so silently -- the output is a fully populated table with
two clubs pointing at one town. `team_aliases.csv` solved the same problem for
the odds feeds the same way, by hand and once.

So: normalise, match exactly, and hand anything left over to
`reference/stadium_name_overrides.csv`. An unmatched club is an error the
caller must see, never a dropped row.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path

OVERRIDES = Path("reference/stadium_name_overrides.csv")

#: Club-name furniture that carries no identity. Applied after punctuation is
#: stripped, so `F.C.` has already become `f c`.
_SUFFIX = re.compile(r"\b(a\s*f\s*c|f\s*c|football club|association football club)\b")

#: U+2019 in `King's Lynn` is genuine UTF-8 in the corpus, not a mojibake --
#: checked against the raw bytes. It still has to fold onto the ASCII form
#: Wikidata uses.
_APOSTROPHES = str.maketrans({"’": "'", "‘": "'", "´": "'"})


def normalise(name: str) -> str:
    """Lowercase, de-punctuate, drop club-name furniture, collapse whitespace."""
    text = name.translate(_APOSTROPHES).lower().replace("&", " and ")
    text = re.sub(r"[^a-z0-9 ]", " ", text)
    text = _SUFFIX.sub(" ", text)
    return " ".join(text.split())


@dataclass(frozen=True)
class Overrides:
    """The three things a hand-reviewed row can say."""

    #: canonical_name -> Wikidata label or QID, when the normaliser cannot reach it.
    targets: dict[str, str]
    #: canonical_name -> ground name to geocode. Used when Wikidata has no
    #: `P115` **and** when its coordinate is wrong, which is why it takes
    #: precedence over a match rather than only filling a gap.
    venues: dict[str, str]
    #: canonical_name -> why a flagged row was accepted anyway. The reason is
    #: mandatory: a whitelist without one is just a disabled check.
    reviewed: dict[str, str]


def load_overrides(path: Path = OVERRIDES) -> Overrides:
    """`canonical_name` -> the Wikidata label *or* QID to match it to.

    A QID is needed because labels are not unique: Wikidata carries two
    distinct items both labelled `Crystal Palace F.C.` (Selhurst Park and
    Crystal Palace Park, 2.5 km apart) and two labelled `Rochdale A.F.C.`
    Naming a label cannot separate those, so `Q19467` is accepted too.

    Absent file is not an error: a first run has nothing to override yet, and
    the CLI reports what would need to go in.

    Returns `(targets, venue_fallbacks)`. A row supplies one or the other:
    a Wikidata label/QID when the club is in Wikidata under a name the
    normaliser cannot reach, or a `venue_name` when Wikidata has no `P115`
    statement for it at all. Seven National League clubs are in the second
    case -- measured, not assumed -- and for those LocationIQ becomes the
    source rather than the check, which the `source` column records.
    """
    if not path.exists():
        return Overrides({}, {}, {})
    targets, venues, reviewed = {}, {}, {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            club = row["canonical_name"]
            if row.get("wikidata_label", "").strip():
                targets[club] = row["wikidata_label"].strip()
            if row.get("venue_name", "").strip():
                venues[club] = row["venue_name"].strip()
            if row.get("reviewed", "").strip():
                reviewed[club] = row["reviewed"].strip()
    return Overrides(targets, venues, reviewed)


def index(venues) -> dict[str, list]:
    """Normalised label or alias -> the venues offering it.

    A list, not a single venue: two Wikidata clubs can share a normalised
    alias, and a collision has to be visible to `match` rather than resolved by
    whichever happened to be indexed last.
    """
    table: dict[str, list] = {}
    for venue in venues:
        for name in {venue.club, *venue.aliases}:
            key = normalise(name)
            if key and venue not in table.setdefault(key, []):
                table[key].append(venue)
    return table


def match(clubs, venues, overrides: dict[str, str]):
    """Resolve each corpus club to one venue.

    Returns `(matched, unmatched, collided)`. An override names a Wikidata
    label directly and is matched on that, so it can also break a collision.
    """
    table = index(venues)
    by_label = {normalise(v.club): v for v in venues}
    by_qid = {v.club_qid.rsplit("/", 1)[-1]: v for v in venues}

    matched, unmatched, collided = {}, [], {}
    for club in clubs:
        if club in overrides:
            wanted = overrides[club].strip()
            target = (by_qid.get(wanted) if _is_qid(wanted)
                      else by_label.get(normalise(wanted)))
            if target is None:
                unmatched.append(club)
            else:
                matched[club] = target
            continue

        candidates = table.get(normalise(club), [])
        if not candidates:
            unmatched.append(club)
        elif len(candidates) > 1:
            collided[club] = [v.club for v in candidates]
        else:
            matched[club] = candidates[0]
    return matched, unmatched, collided


def _is_qid(value: str) -> bool:
    return value.startswith("Q") and value[1:].isdigit()
