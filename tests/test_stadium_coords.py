"""Tests for the stadium coordinate table.

The validation ones matter more than the plumbing ones. A coordinate table is
the shape of data this project has twice been burned by -- fully populated,
correctly typed, quietly wrong -- so each guard gets a *planted* defect that it
has to catch, on the same principle as `test_calibration.py`'s poison test and
P2's oracle arm. A check that has never rejected anything is not known to work.

The known-distance cases are the independent quantity `OUTSTANDING.md` §7.6
asks for: the derby distances are stated from outside this table, so they fail
if the table, the WKT parser, or the haversine is wrong, and they do not depend
on any of the three being right to be believable.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from services.stadium_coords import bridge, locationiq, reconcile, wikidata

TABLE = Path("reference/stadiums.csv")


# --- the WKT trap ----------------------------------------------------------

def test_parse_point_returns_lat_lon_not_lon_lat():
    """Wikidata emits `Point(lon lat)`. Old Trafford is at 53.46N, 2.29W."""
    lat, lon = wikidata.parse_point("Point(-2.291388888 53.463055555)")
    assert lat == pytest.approx(53.463, abs=1e-3)
    assert lon == pytest.approx(-2.291, abs=1e-3)


def test_transposed_coordinates_are_rejected_by_the_bounds():
    """The planted defect: read the same point as (lon, lat) instead."""
    assert reconcile.in_bounds(53.463, -2.291)
    assert not reconcile.in_bounds(-2.291, 53.463)


def test_sign_flipped_longitude_is_rejected():
    """Dropping the minus on a western longitude lands in the North Sea."""
    assert reconcile.in_bounds(53.463, -2.291)
    assert not reconcile.in_bounds(53.463, 2.291 + 3.0)


# --- distances known without reference to this table -----------------------

ANFIELD = (53.4308, -2.9608)
GOODISON = (53.4388, -2.9663)
OLD_TRAFFORD = (53.4631, -2.2914)
ETIHAD = (53.4831, -2.2004)
ST_JAMES = (54.9756, -1.6217)
HOME_PARK = (50.3881, -4.1508)


@pytest.mark.parametrize("a, b, low, high", [
    (ANFIELD, GOODISON, 0.5, 1.5),          # across Stanley Park
    (OLD_TRAFFORD, ETIHAD, 4.0, 8.0),       # the Manchester derby
    (ST_JAMES, HOME_PARK, 500.0, 575.0),    # the longest trip in the corpus
])
def test_haversine_reproduces_known_distances(a, b, low, high):
    """Bounds are **great-circle**, which is not what a team actually travels.

    Newcastle to Plymouth is ~538 km straight line against roughly 660 km by
    road, and the gap is not a constant multiple -- it is widest exactly where
    the road network is worst, which in this corpus means Norwich, Plymouth and
    Carlisle rather than the M6 clubs. That is a caveat the travel feature
    inherits, and the first version of this test failed because the road figure
    was asserted against the straight-line code.
    """
    assert low < reconcile.haversine_km(a, b) < high


def test_haversine_is_symmetric_and_zero_on_itself():
    assert reconcile.haversine_km(ANFIELD, ANFIELD) == pytest.approx(0.0)
    assert reconcile.haversine_km(ANFIELD, HOME_PARK) == pytest.approx(
        reconcile.haversine_km(HOME_PARK, ANFIELD))


# --- the geocoder's silent failure -----------------------------------------

def _geocoded(osm_class, osm_type):
    return locationiq.Geocoded(53.4, -2.2, "somewhere", osm_class, osm_type)


def test_a_stadium_result_is_accepted():
    assert _geocoded("leisure", "stadium").is_venue


class _FakeHTTP(locationiq.Geocoder):
    """A Geocoder whose only live behaviour -- the HTTP call -- is replaced."""

    def __init__(self, payload):
        super().__init__("key", Path("unused"))
        self.payload = payload

    def _raw(self, query):
        return self.payload


def test_search_skips_the_street_and_returns_the_stadium():
    """The defect this caught: Portman Road is a road, and it outranks the ground.

    43 of 144 clubs were rejected because the geocoder's top hit was the street
    the stadium is named after. Taking the first *venue-like* result rather
    than the first result is the fix, and this pins it.
    """
    result = _FakeHTTP([
        {"lat": "52.05", "lon": "1.14", "display_name": "Portman Road, Ipswich",
         "class": "highway", "type": "tertiary"},
        {"lat": "52.0550", "lon": "1.1450", "display_name": "Portman Road stadium",
         "class": "leisure", "type": "stadium"},
    ]).search("Portman Road, Ipswich")
    assert result.is_venue
    assert result.lat == pytest.approx(52.0550)


def test_search_returns_the_top_result_when_nothing_is_venue_like():
    """Rejection must be visible to the caller, not expressed as None."""
    result = _FakeHTTP([
        {"lat": "52.05", "lon": "1.14", "display_name": "Portman Road",
         "class": "highway", "type": "tertiary"},
    ]).search("Portman Road")
    assert result is not None
    assert not result.is_venue


@pytest.mark.parametrize("osm_class, osm_type", [
    ("place", "town"),                  # the centroid fallback
    ("place", "city"),
    ("boundary", "administrative"),
    ("highway", "residential"),
])
def test_centroid_fallbacks_are_rejected(osm_class, osm_type):
    """The planted defect: a 200 response carrying the wrong kind of feature."""
    assert not _geocoded(osm_class, osm_type).is_venue


# --- the bridge must not collapse distinct clubs ---------------------------

def test_normalise_strips_club_furniture_but_not_identity():
    assert bridge.normalise("Nottingham Forest F.C.") == "nottingham forest"
    assert bridge.normalise("AFC Bournemouth") == "bournemouth"
    assert bridge.normalise("King’s Lynn") == bridge.normalise("King's Lynn")


def test_normalise_keeps_oxford_and_oxford_city_apart():
    """The planted defect a fuzzy matcher would fail: two real, distinct clubs."""
    assert bridge.normalise("Oxford") != bridge.normalise("Oxford City")
    assert bridge.normalise("Bradford") != bridge.normalise("Bradford Park Avenue")


def test_match_reports_collisions_instead_of_picking_one():
    venues = [
        wikidata.Venue("Chester F.C.", "http://x/Q1", frozenset(), "Deva", 53.1, -2.9, None),
        wikidata.Venue("Chester City F.C.", "http://x/Q2", frozenset({"Chester"}),
                       "Deva", 53.1, -2.9, None),
    ]
    matched, unmatched, collided = bridge.match(["Chester"], venues, {})
    assert not matched and not unmatched
    assert collided["Chester"] == ["Chester F.C.", "Chester City F.C."]


def test_a_qid_override_breaks_a_collision_a_label_cannot():
    """Two Wikidata items share the label `Crystal Palace F.C.`."""
    venues = [
        wikidata.Venue("Crystal Palace F.C.", "http://x/Q2494372", frozenset(),
                       "Crystal Palace Park", 51.4203, -0.0705, None),
        wikidata.Venue("Crystal Palace F.C.", "http://x/Q19467", frozenset(),
                       "Selhurst Park", 51.3983, -0.0856, None),
    ]
    matched, _, _ = bridge.match(["Crystal Palace"], venues, {"Crystal Palace": "Q19467"})
    assert matched["Crystal Palace"].venue == "Selhurst Park"


def test_unmatched_clubs_are_reported_never_dropped():
    matched, unmatched, _ = bridge.match(["Nowhere Town"], [], {})
    assert not matched
    assert unmatched == ["Nowhere Town"]


# --- the geocode fallback, for clubs Wikidata has no venue for -------------

class _StubGeocoder:
    """Returns whatever it is handed, so the fallback path is testable offline."""

    def __init__(self, result, address=""):
        self.result = result
        self.address = address
        self.queried: list[str] = []

    def search(self, query):
        self.queried.append(query)
        return self.result

    def reverse(self, lat, lon):
        return self.address


def test_a_fallback_club_is_sourced_from_the_geocoder():
    stub = _StubGeocoder(locationiq.Geocoded(52.7539, -0.4014, "The Walks", "leisure", "stadium"))
    rows, unresolved = reconcile.build(
        {}, {"King's Lynn": "EC"}, stub, {"King's Lynn": "The Walks, King's Lynn"})
    assert not unresolved
    assert rows[0].source == "locationiq"
    assert rows[0].check_status == "unchecked"
    assert "The Walks" in stub.queried[0]


@pytest.mark.parametrize("result", [
    None,                                                             # no match
    locationiq.Geocoded(52.75, -0.40, "King's Lynn", "place", "town"),  # centroid
    locationiq.Geocoded(1.29, 103.85, "Singapore", "leisure", "stadium"),  # out of bounds
])
def test_an_unresolvable_fallback_is_reported_not_guessed(result):
    """The planted defect: three ways the geocoder can fail to answer usefully."""
    rows, unresolved = reconcile.build(
        {}, {"King's Lynn": "EC"}, _StubGeocoder(result), {"King's Lynn": "The Walks"})
    assert not rows
    assert unresolved == ["King's Lynn"]


def test_a_fallback_replaces_a_wrong_wikidata_coordinate():
    """Darlington: Wikidata's P625 points 16.5 km away at Heritage Park.

    The fallback has to win over the match, not merely fill a gap. The first
    version skipped the club in both loops and dropped it from the table with
    no report at all -- a coordinate table that silently omits a club yields a
    travel feature that is null for every match that club played.
    """
    wrong = wikidata.Venue("Darlington F.C.", "http://x/Q1", frozenset(),
                           "Blackwell Meadows", 54.638, -1.69271, "Darlington")
    stub = _StubGeocoder(
        locationiq.Geocoded(54.5093, -1.5647, "Blackwell Meadows, Darlington",
                            "landuse", "recreation_ground"))
    rows, unresolved = reconcile.build(
        {"Darlington": wrong}, {"Darlington": "E3"}, stub,
        {"Darlington": "Blackwell Meadows, Darlington"})
    assert not unresolved
    assert len(rows) == 1
    assert rows[0].source == "locationiq"
    assert rows[0].lat == pytest.approx(54.5093)


def test_no_club_is_ever_dropped_without_being_reported():
    """The completeness invariant: every club lands in rows or in unresolved."""
    clubs = {"Matched": "E0", "Fallback": "E1", "Hopeless": "E2"}
    matched = {"Matched": wikidata.Venue("A F.C.", "http://x/Q1", frozenset(),
                                         "Ground", 53.0, -2.0, "Town")}
    rows, unresolved = reconcile.build(
        matched, clubs, _StubGeocoder(None),
        {"Fallback": "Somewhere", "Hopeless": "Nowhere"})
    assert set(clubs) == {r.canonical_name for r in rows} | set(unresolved)


def test_fallbacks_are_skipped_without_a_geocoder():
    rows, unresolved = reconcile.build({}, {"King's Lynn": "EC"}, None, {"King's Lynn": "The Walks"})
    assert not rows
    assert unresolved == ["King's Lynn"]


# --- Wikidata folding ------------------------------------------------------

def _binding(qid, club, venue, point, alias=None):
    row = {
        "club": {"value": f"http://www.wikidata.org/entity/{qid}"},
        "clubLabel": {"value": club},
        "venueLabel": {"value": venue},
        "coord": {"value": point},
    }
    if alias:
        row["alias"] = {"value": alias}
    return row


def test_venues_folds_alias_rows_into_one_club():
    bindings = [
        _binding("Q1", "Queens Park Rangers F.C.", "Loftus Road", "Point(-0.2322 51.5092)", "QPR"),
        _binding("Q1", "Queens Park Rangers F.C.", "Loftus Road", "Point(-0.2322 51.5092)", "Rangers"),
    ]
    venues, ambiguous = wikidata.venues(bindings)
    assert not ambiguous
    assert len(venues) == 1
    assert venues[0].aliases == frozenset({"QPR", "Rangers"})


def test_a_club_with_two_venues_is_reported_not_guessed():
    bindings = [
        _binding("Q1", "Rochdale A.F.C.", "Spotland Stadium", "Point(-2.18 53.6208)"),
        _binding("Q1", "Rochdale A.F.C.", "Athletic Grounds", "Point(-2.1355 53.6122)"),
    ]
    venues, ambiguous = wikidata.venues(bindings)
    assert not venues
    assert ambiguous["Rochdale A.F.C."] == {"Spotland Stadium", "Athletic Grounds"}


# --- the committed table ---------------------------------------------------

@pytest.mark.skipif(not TABLE.exists(), reason="table not built yet")
class TestCommittedTable:
    @staticmethod
    def rows():
        with TABLE.open(encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))

    def test_every_row_is_inside_the_bounding_box(self):
        outside = [r["canonical_name"] for r in self.rows()
                   if not reconcile.in_bounds(float(r["lat"]), float(r["lon"]))]
        assert not outside

    def test_no_two_clubs_share_a_coordinate_unless_they_share_a_ground(self):
        """Groundshares are real (Wimbledon/MK Dons era, Coventry, Chester).

        The check is that an exact duplicate coordinate always comes with an
        equal venue name -- otherwise it is two clubs pointed at one town by a
        bad match, which is the failure the collision guard exists to stop.
        """
        seen: dict[tuple[str, str], str] = {}
        for row in self.rows():
            key = (row["lat"], row["lon"])
            if key in seen:
                assert seen[key] == row["venue"], (
                    f"{row['canonical_name']} shares a coordinate with a "
                    f"different venue name ({seen[key]!r} vs {row['venue']!r})")
            seen[key] = row["venue"]

    def test_the_committed_table_was_actually_checked(self):
        """Without this, the agreement test below passes on an unchecked table.

        `--no-geocode` writes every row with `check_status = skipped`, and a
        table of skipped rows contains no disagreements -- so the check would
        report green precisely when nothing had been checked. That is the
        vacuous-pass shape, and it is worth a test of its own rather than a
        comment, because the failure is invisible in the output it produces.
        """
        skipped = [r["canonical_name"] for r in self.rows()
                   if r["check_status"] == "skipped"]
        assert not skipped, (
            f"{len(skipped)} row(s) were never checked against LocationIQ. "
            "Rebuild without --no-geocode before committing the table.")

    def test_checked_rows_agree_with_the_independent_geocode(self):
        disagreeing = [r["canonical_name"] for r in self.rows()
                       if r["check_status"] == "review"]
        assert not disagreeing

    def test_the_longest_and_shortest_trips_are_plausible(self):
        points = {r["canonical_name"]: (float(r["lat"]), float(r["lon"]))
                  for r in self.rows()}
        distances = [
            reconcile.haversine_km(a, b)
            for i, a in enumerate(points.values())
            for b in list(points.values())[i + 1:]
        ]
        assert max(distances) < 900.0     # no English trip is longer
        assert min(distances) >= 0.0
