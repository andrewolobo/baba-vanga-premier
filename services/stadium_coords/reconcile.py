"""Turn matched venues into the coordinate table, and check them.

The checks are cheap and they are not decoration. A coordinate that is a degree
out, sign-flipped, or transposed reads as a perfectly ordinary number in a CSV,
and 151 populated rows prove only that 151 rows were populated -- the exact
failure shape behind both data defects this project has already found. So every
row is checked three ways: against a bounding box, against an independent
geocode, and (in the tests) against distances that are known without reference
to this table at all.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from math import asin, cos, radians, sin, sqrt
from pathlib import Path

#: England and Wales with a margin. Northernmost league grounds sit near 55.0
#: (Carlisle, Newcastle); the westernmost are Welsh, the southernmost Cornish
#: and Channel-coast. Any transposed `Point(lon lat)` lands outside on both
#: axes, which is the point of checking rather than trusting the parser.
BOUNDS = (49.9, 55.9, -6.5, 1.9)   # lat_min, lat_max, lon_min, lon_max

#: Kilometres between the two sources above which a row is not accepted
#: silently. Below it, the pair are the same site read from different corners;
#: above it, something resolved the wrong feature.
DISAGREEMENT_KM = 1.0

#: Outcomes a `reviewed` note is allowed to clear. Deliberately not `agree` --
#: a note cannot make a passing row fail, and cannot silently restate one.
NEEDS_REVIEW = ("review", "no_match", "out_of_bounds")

#: Clubs that changed ground inside the corpus window (2010-11 -> 2025-26),
#: with the approximate distance moved. **This list is a stated assumption, not
#: a verified one, and nothing in this module can check it** -- a stale tenancy
#: gives a venue whose name and coordinates agree with each other perfectly.
#:
#: It is recorded because a static table silently applies today's ground to
#: 2010, and convention 9 says the thing held fixed gets written down before it
#: is relied on. For travel *distance* the error is small: almost every move is
#: intra-city. Rotherham is the exception that is not -- Don Valley is in
#: Sheffield -- and Tottenham's Wembley seasons are the other.
KNOWN_MOVES = (
    ("Rotherham", "Don Valley (Sheffield) -> New York Stadium", "2012-13", 9.0),
    ("Tottenham", "White Hart Lane -> Wembley -> new stadium", "2017-18..2018-19", 11.0),
    ("West Ham", "Boleyn Ground -> London Stadium", "2016-17", 5.0),
    ("Brighton", "Withdean -> Amex", "2011-12", 4.0),
    ("AFC Wimbledon", "Kingsmeadow -> Plough Lane", "2020-21", 4.0),
    ("Everton", "Goodison Park -> Hill Dickinson", "2025-26 (holdout)", 3.0),
    ("Brentford", "Griffin Park -> Gtech Community", "2020-21", 1.4),
    ("Morecambe", "Christie Park -> Globe Arena", "2010-11", 1.0),
)

FIELDS = (
    "canonical_name", "divisions", "venue", "lat", "lon", "town", "source",
    "wikidata_qid", "wikidata_club", "check_status", "check_delta_km",
    "check_display_name",
)


@dataclass(frozen=True)
class Row:
    canonical_name: str
    divisions: str
    venue: str
    lat: float
    lon: float
    town: str | None
    #: `wikidata` when Wikidata supplied the coordinate and LocationIQ only
    #: checked it, `locationiq` when Wikidata had no `P115` and the geocoder
    #: became the source. The distinction is the difference between a checked
    #: number and an unchecked one, so it is stored, not inferred.
    source: str
    wikidata_qid: str
    wikidata_club: str
    check_status: str
    check_delta_km: float | None
    check_display_name: str


def haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Great-circle distance in km between two (lat, lon) pairs."""
    lat1, lon1 = radians(a[0]), radians(a[1])
    lat2, lon2 = radians(b[0]), radians(b[1])
    h = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2
    return 2 * 6371.0088 * asin(sqrt(h))


def in_bounds(lat: float, lon: float) -> bool:
    lat_min, lat_max, lon_min, lon_max = BOUNDS
    return lat_min <= lat <= lat_max and lon_min <= lon <= lon_max


def check(venue, geocoder) -> tuple[str, float | None, str]:
    """Second opinion on one venue: `(status, delta_km, display_name)`.

    Status is `skipped` (no geocoder), `no_match`, `agree`, or `review`.

    **The distance is the check; the feature type is not.** An earlier version
    rejected any result whose OSM `class`/`type` was not venue-like, and it
    threw away 40 of 144 perfectly good checks -- LocationIQ leaves those
    fields empty on a large share of results, and where it does populate them
    the answer is often a feature that sits *at* the ground rather than being
    it. The top hit for Selhurst Park is a bus stop called "Selhurst Park
    Stadium", 100 m from the centre circle, which is an excellent confirmation
    and a terrible `type`.

    What the type filter was meant to catch -- the silent centroid fallback --
    the distance catches anyway, because a town centroid is kilometres from the
    ground. It also catches what the type filter could not: asked for Everton's
    "Hill Dickinson Stadium", LocationIQ returns *Hillsborough Stadium* in
    Sheffield, a different club's ground 100 km away. Only a distance
    comparison sees that.

    So the type is recorded for information and the kilometres decide. The
    strict filter stays where it is still load-bearing: `_from_geocode`, where
    there is no Wikidata coordinate to compare against.
    """
    if geocoder is None:
        return "skipped", None, ""

    query = ", ".join(part for part in (venue.venue, venue.town, "United Kingdom") if part)
    result = geocoder.search(query)
    if result is not None:
        delta = haversine_km((venue.lat, venue.lon), (result.lat, result.lon))
        if delta <= DISAGREEMENT_KM:
            kind = f"{result.osm_class}/{result.osm_type}".strip("/") or "untyped"
            return "agree", delta, f"[{kind}] {result.display_name}"

    # The forward lookup either found nothing or found somewhere else. Ask the
    # other question instead -- what is at Wikidata's coordinate -- and accept
    # the point if the answer is in the town the venue is supposed to be in.
    address = geocoder.reverse(venue.lat, venue.lon)
    if _confirms(address, venue.town, venue.venue):
        return "agree_reverse", None, address
    return "review", (delta if result is not None else None), address or "no reverse match"


def _confirms(address: str, town: str | None, venue_name: str) -> bool:
    """Whether a reverse-geocoded address confirms the venue's location.

    Two ways it can, because neither alone is enough on this data:

    *The address names the venue.* Boston's `P131` is absent entirely, but the
    reverse lookup returns "York Street Stadium, York Street, ... Boston", and
    Burton's returns "Pirelli Stadium" while its town label says `Burton upon
    Trent` against an address in `Stretton, East Staffordshire`.

    *The address is in the town.* Matched on the leading token as well as the
    whole label, because Wikidata's `P131` is an administrative unit and the
    address is a postal one -- `Eastleigh Town` against `Eastleigh, Hampshire`.
    The token needs five characters, so `Ten Acres` cannot confirm itself on
    `ten` and no venue confirms on `park` or `road`.
    """
    text = address.lower()
    if not text:
        return False
    if _head(venue_name) in text:
        return True
    if town is None:
        return False
    head = _head(town)
    if head and head in text:
        return True
    token = head.split(" ")[0] if head else ""
    return len(token) >= 5 and token in text


def _head(label: str) -> str:
    head = label.split(",")[0].strip().lower()
    for prefix in ("city of ", "royal borough of ", "london borough of ", "borough of "):
        head = head.removeprefix(prefix)
    return head


def build(matched: dict, divisions: dict[str, str], geocoder=None,
          fallbacks: dict[str, str] | None = None,
          reviewed: dict[str, str] | None = None) -> tuple[list[Row], list[str]]:
    """One row per resolved club, plus the fallback clubs that stayed unresolved.

    A `venue_name` override **wins over a Wikidata match**, because it is used
    for two different jobs: filling a club Wikidata has no venue for, and
    replacing a coordinate Wikidata has wrong. Darlington is the second case --
    its `P625` points at Heritage Park in Bishop Auckland, 16.5 km from the
    ground it has played on since 2016, and reverse geocoding is what caught it.

    Wikidata-sourced clubs come first in the code path but the output is sorted
    on canonical name, so the two sources interleave and nobody can read the
    file order as a quality ranking.
    """
    fallbacks = fallbacks or {}
    reviewed = reviewed or {}
    rows = [
        _from_wikidata(club, matched[club], divisions.get(club, ""), geocoder, reviewed)
        for club in sorted(matched) if club not in fallbacks
    ]

    unresolved = []
    for club, venue_name in sorted(fallbacks.items()):
        # Not `club in matched`: a fallback deliberately *replaces* a match
        # when Wikidata's coordinate is wrong, and the Wikidata loop above has
        # already stood aside for it. Skipping here as well dropped Darlington
        # from the table entirely, reported by neither path.
        if club not in divisions:
            continue
        row = _from_geocode(club, venue_name, divisions.get(club, ""), geocoder)
        if row is None:
            unresolved.append(club)
        else:
            rows.append(row)

    rows.sort(key=lambda r: r.canonical_name)
    return rows, unresolved


def _from_wikidata(club: str, venue, divisions: str, geocoder, reviewed: dict) -> Row:
    status, delta, display = check(venue, geocoder)
    if not in_bounds(venue.lat, venue.lon):
        status = "out_of_bounds"
    if status in NEEDS_REVIEW and club in reviewed:
        status, display = "agree_manual", reviewed[club]
    return Row(
        canonical_name=club, divisions=divisions, venue=venue.venue,
        lat=venue.lat, lon=venue.lon, town=venue.town, source="wikidata",
        wikidata_qid=venue.club_qid.rsplit("/", 1)[-1], wikidata_club=venue.club,
        check_status=status, check_delta_km=delta, check_display_name=display,
    )


def _from_geocode(club: str, venue_name: str, divisions: str, geocoder) -> Row | None:
    """A row sourced from the geocoder, for clubs Wikidata has no venue for.

    Returns None when there is no geocoder or it cannot resolve a venue-like
    feature -- an unresolvable club is reported, never written with a guess.
    """
    if geocoder is None:
        return None
    result = geocoder.search(f"{venue_name}, United Kingdom")
    if result is None or not result.is_venue or not in_bounds(result.lat, result.lon):
        return None

    # The forward result is the only source here, so confirm it points back at
    # itself. Without this the row would be the one thing the table otherwise
    # has none of: a coordinate nothing ever checked. The override string
    # carries its own town after the last comma -- "Westleigh Park, Havant".
    venue_part, _, town_part = venue_name.rpartition(",")
    address = geocoder.reverse(result.lat, result.lon)
    confirmed = _confirms(address, town_part.strip() or None, venue_part.strip() or venue_name)
    return Row(
        canonical_name=club, divisions=divisions, venue=venue_name,
        lat=result.lat, lon=result.lon, town=town_part.strip() or None,
        source="locationiq", wikidata_qid="", wikidata_club="",
        check_status="agree_reverse" if confirmed else "unchecked",
        check_delta_km=None, check_display_name=address or result.display_name,
    )


def write_csv(rows: list[Row], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        for row in rows:
            record = row.__dict__.copy()
            if record["check_delta_km"] is not None:
                record["check_delta_km"] = f"{record['check_delta_km']:.3f}"
            writer.writerow(record)
