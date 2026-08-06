"""Independent coordinates for a named venue, from LocationIQ forward geocoding.

This is the **check**, never the source. Nothing here ever overwrites a
Wikidata coordinate; it produces a second opinion and `reconcile` reports where
the two disagree. A checker that is allowed to become the source quietly stops
being a check.

Two things about that check are worth stating plainly.

*It is only partly independent.* LocationIQ serves OpenStreetMap data, and OSM
objects routinely carry `wikidata` tags, so a venue's OSM node and its Wikidata
item are not guaranteed to be separate observations. Agreement is therefore
weaker evidence than a fully independent basemap would give. It still catches
the failure this table is actually exposed to -- resolving the wrong "Victoria
Park" -- which is most of the value.

*A geocoder's worst failure is a confident one.* Asked for a ground it cannot
find, Nominatim-family services return the enclosing town or postcode centroid
with a 200 and a plausible-looking lat/lon. That is the "row count perfect,
content wrong" shape this project has already been bitten by twice, so the
result `class`/`type` is checked and anything that is not a venue-like feature
is rejected rather than recorded.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

SEARCH_URL = "https://us1.locationiq.com/v1/search"
REVERSE_URL = "https://us1.locationiq.com/v1/reverse"

#: Free tier allows 2 requests/second. One is inside it with room to spare, and
#: the whole corpus is ~150 lookups -- under three minutes, once, ever.
MIN_INTERVAL = 1.0

#: Results to ask for. **Not 1**, and the reason is specific to English
#: football: most grounds are named after the street they stand on -- Portman
#: Road, Elland Road, Vicarage Road, Kenilworth Road, Sincil Bank, Plough Lane
#: -- and the geocoder ranks the road above the stadium. Asking for one result
#: and filtering it rejected 43 of 144 clubs whose stadium was sitting in the
#: result set two rows down. Ask for several, take the first venue-like one.
RESULT_LIMIT = 10

#: OSM feature classes/types that denote an actual venue. Anything outside this
#: set -- `place/town`, `boundary/administrative` -- is the centroid fallback
#: described above, and is rejected.
VENUE_CLASSES = frozenset({"leisure", "building", "amenity", "tourism", "landuse", "club"})
VENUE_TYPES = frozenset({
    "stadium", "sports_centre", "pitch", "arena", "sports_hall",
    "recreation_ground", "grandstand",
    # OSM tags Turf Moor and several other grounds `club=sport` rather than
    # `leisure=stadium`. Both describe the ground itself.
    "sport",
})


class MissingKey(RuntimeError):
    """No LOCATIONIQ_API_KEY in the environment or .env."""


@dataclass(frozen=True)
class Geocoded:
    lat: float
    lon: float
    display_name: str
    osm_class: str
    osm_type: str

    @property
    def is_venue(self) -> bool:
        return self.osm_class in VENUE_CLASSES and self.osm_type in VENUE_TYPES


def api_key(env_file: Path = Path(".env")) -> str:
    """The key from the environment, falling back to a `KEY=value` line in .env.

    Parsed by hand rather than adding python-dotenv for one variable.
    """
    key = os.environ.get("LOCATIONIQ_API_KEY", "").strip()
    if key:
        return key
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            name, _, value = line.partition("=")
            if name.strip() == "LOCATIONIQ_API_KEY":
                key = value.strip().strip("'\"")
                if key:
                    return key
    raise MissingKey(
        "LOCATIONIQ_API_KEY is not set and .env does not define it. "
        "Add it to .env (already gitignored) or export it, then re-run. "
        "Use --no-geocode to build the table from Wikidata alone, unchecked."
    )


class Geocoder:
    """Throttled, disk-cached forward geocoding.

    Cached on the query string, so re-running after a change to the matching or
    reporting logic costs zero requests -- the same rule `fbref_scraper.fetch`
    follows, for the same reason.
    """

    def __init__(self, key: str, cache_dir: Path):
        self.key = key
        self.cache_dir = cache_dir
        self.requests_made = 0
        self._last_request: float | None = None

    def search(self, query: str) -> Geocoded | None:
        """First venue-like result for `query`, or None if there is not one.

        Returning the highest-ranked *venue* rather than the highest-ranked
        result is the whole point -- see `RESULT_LIMIT`. If nothing in the set
        is venue-like the top result comes back anyway, so the caller can see
        what was found and reject it by `is_venue` rather than by silence.
        """
        results = [
            Geocoded(
                lat=float(item["lat"]), lon=float(item["lon"]),
                display_name=item.get("display_name", ""),
                osm_class=item.get("class", ""), osm_type=item.get("type", ""),
            )
            for item in self._raw(query)
        ]
        if not results:
            return None
        return next((r for r in results if r.is_venue), results[0])

    def reverse(self, lat: float, lon: float) -> str:
        """What LocationIQ believes is at a coordinate. Empty when it has no idea.

        This is the check that actually suits the job. Forward geocoding asks
        "where is the ground called X", which fails whenever the name is
        ambiguous or absent -- and English grounds are named after streets,
        share names across towns, and get renamed by sponsors. Reverse asks
        "what is at this point", which is the question the table's correctness
        actually turns on and which has exactly one answer.
        """
        cached = self.cache_dir / f"rev_{lat:.5f}_{lon:.5f}.json"
        if cached.exists():
            payload = json.loads(cached.read_text(encoding="utf-8"))
        else:
            params = urllib.parse.urlencode({
                "key": self.key, "lat": lat, "lon": lon, "format": "json",
            })
            self._throttle()
            self.requests_made += 1
            try:
                with urllib.request.urlopen(
                        f"{REVERSE_URL}?{params}", timeout=30) as response:
                    payload = json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as error:
                if error.code != 404:
                    raise
                payload = {}
            cached.parent.mkdir(parents=True, exist_ok=True)
            cached.write_text(json.dumps(payload), encoding="utf-8")
        return payload.get("display_name", "")

    def _raw(self, query: str) -> list[dict]:
        # The limit is part of the cache key: it changes the response, and a
        # key that ignores it serves a stale one-result payload forever.
        cached = self.cache_dir / f"{_slug(query)}.n{RESULT_LIMIT}.json"
        if cached.exists():
            return json.loads(cached.read_text(encoding="utf-8"))

        params = urllib.parse.urlencode({
            "key": self.key, "q": query, "format": "json",
            "limit": RESULT_LIMIT, "countrycodes": "gb",
        })
        self._throttle()
        self.requests_made += 1
        try:
            with urllib.request.urlopen(f"{SEARCH_URL}?{params}", timeout=30) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            if error.code == 404:      # LocationIQ's "no match", not a failure
                payload = []
            elif error.code == 401:
                raise MissingKey("LocationIQ rejected the key (401).") from error
            else:
                raise

        cached.parent.mkdir(parents=True, exist_ok=True)
        cached.write_text(json.dumps(payload), encoding="utf-8")
        return payload

    def _throttle(self) -> None:
        if self._last_request is not None:
            wait = MIN_INTERVAL - (time.monotonic() - self._last_request)
            if wait > 0:
                time.sleep(wait)
        self._last_request = time.monotonic()


def _slug(query: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in query.lower())[:120]
