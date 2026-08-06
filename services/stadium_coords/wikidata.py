"""Club -> home venue -> coordinates, from the Wikidata query service.

Wikidata rather than a scraped Wikipedia list, for three reasons that were
measured rather than assumed: the coordinates are structured (`P625`) so there
is no name-resolution step to get wrong, `skos:altLabel` supplies the aliases
the name bridge needs, and one query covers the National League as well as the
Football League.

**`P115` records historical tenancies too.** Without the end-time filter below,
24 of 633 clubs return more than one venue -- Darlington comes back as both
Blackwell Meadows and the Darlington Arena, which are 11 km apart. Filtering
statements that carry a `P582` end time cuts that to 6. Any club still
ambiguous after the filter is reported, never silently resolved.

**The filter fixes stale, it does not fix wrong.** Brentford still returns
Griffin Park, which they left in 2020 -- the statement simply has no end time.
The venue name and its coordinates agree with each other, so no cross-check can
catch it; only a tenancy source can. `KNOWN_MOVES` in `reconcile.py` carries
the ones that matter and explains why they mostly do not.
"""

from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

SPARQL_URL = "https://query.wikidata.org/sparql"

#: Wikidata asks for a descriptive agent with a contact route, and throttles
#: anonymous traffic that does not supply one.
USER_AGENT = "baba-vanga-premier/0.1 (stadium coordinates; oloborama@gmail.com)"

#: `wdt:P31/wdt:P279*` walks the subclass tree, so reserve/academy/women's
#: sides come back too. They are filtered by the name bridge, not here -- a
#: narrower query risks dropping a senior club with an unusual class.
QUERY = """
SELECT DISTINCT ?club ?clubLabel ?alias ?venue ?venueLabel ?coord ?townLabel WHERE {
  ?club wdt:P31/wdt:P279* wd:Q476028 .
  ?club wdt:P17 wd:Q145 .
  ?club p:P115 ?statement .
  ?statement ps:P115 ?venue .
  FILTER NOT EXISTS { ?statement pq:P582 ?ended }
  FILTER NOT EXISTS { ?statement wikibase:rank wikibase:DeprecatedRank }
  ?venue wdt:P625 ?coord .
  OPTIONAL { ?venue wdt:P131 ?town }
  OPTIONAL { ?club skos:altLabel ?alias FILTER(lang(?alias) = "en") }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}
"""

#: Well-known text as Wikidata emits it: longitude first. Reading it as
#: (lat, lon) puts every English ground in the Channel or the North Sea, which
#: is why `reconcile.in_bounds` exists and why a test plants the transposition.
_POINT = re.compile(r"Point\(\s*(-?[\d.]+)\s+(-?[\d.]+)\s*\)")


@dataclass(frozen=True)
class Venue:
    club: str           # Wikidata label, e.g. "Reading F.C."
    club_qid: str
    aliases: frozenset[str]
    venue: str
    lat: float
    lon: float
    town: str | None


def _label_or_none(value: str | None) -> str | None:
    """Drop a label that is really a QID.

    Wikidata's label service returns the item id when an item has no English
    label, so `townLabel` comes back as `Q22905` for a handful of places. That
    id then ends up inside a geocoder query -- `Valley Parade, Q22905, United
    Kingdom` -- where it can only hurt. Bradford is findable without it.
    """
    if value is None or (value.startswith("Q") and value[1:].isdigit()):
        return None
    return value


def parse_point(wkt: str) -> tuple[float, float]:
    """`Point(lon lat)` -> `(lat, lon)`. Named to make the swap explicit."""
    match = _POINT.fullmatch(wkt.strip())
    if match is None:
        raise ValueError(f"not a WKT point: {wkt!r}")
    lon, lat = float(match.group(1)), float(match.group(2))
    return lat, lon


def fetch(cache: Path | None = None, *, timeout: int = 120) -> list[dict]:
    """Raw SPARQL bindings, read from `cache` if it is already there.

    Cached because the query is stable and the reconciliation on top of it is
    not -- iterating on the matching logic should cost nothing upstream.
    """
    if cache is not None and cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))["results"]["bindings"]

    url = f"{SPARQL_URL}?format=json&query={urllib.parse.quote(QUERY)}"
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))

    if cache is not None:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(payload), encoding="utf-8")
    return payload["results"]["bindings"]


def venues(bindings: list[dict]) -> tuple[list[Venue], dict[str, set[str]]]:
    """Collapse bindings to one `Venue` per club, plus the ambiguous ones.

    A club appears once per (alias x town) combination, so the rows are folded
    on the club QID. The second return value maps club label -> venue names for
    every club that still offers more than one after the end-time filter; the
    caller decides what to do about them rather than inheriting a silent pick.
    """
    folded: dict[str, dict] = {}
    for binding in bindings:
        qid = binding["club"]["value"]
        entry = folded.setdefault(qid, {
            "club": binding["clubLabel"]["value"],
            "aliases": set(),
            "venues": {},
        })
        if "alias" in binding:
            entry["aliases"].add(binding["alias"]["value"])
        lat, lon = parse_point(binding["coord"]["value"])
        entry["venues"][binding["venueLabel"]["value"]] = (
            lat, lon, _label_or_none(binding.get("townLabel", {}).get("value")),
        )

    resolved, ambiguous = [], {}
    for qid, entry in folded.items():
        if len(entry["venues"]) > 1:
            ambiguous[entry["club"]] = set(entry["venues"])
            continue
        name, (lat, lon, town) = next(iter(entry["venues"].items()))
        resolved.append(Venue(
            club=entry["club"], club_qid=qid, aliases=frozenset(entry["aliases"]),
            venue=name, lat=lat, lon=lon, town=town,
        ))
    return resolved, ambiguous
