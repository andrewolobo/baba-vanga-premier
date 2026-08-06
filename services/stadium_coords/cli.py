"""Build `reference/stadiums.csv`.

    python -m services.stadium_coords                 # Wikidata + LocationIQ check
    python -m services.stadium_coords --no-geocode    # Wikidata alone, unchecked
    python -m services.stadium_coords --divisions E0,E1,E2,E3

Exit codes follow `run_cycle.py`, because the distinction has already earned
its keep there: **0** clean, **2** ran but needs a human look (unmatched clubs,
geocode disagreements, name collisions), **1** a step failed outright. An
unresolved club is a `2`, never a dropped row -- a coordinate table that
quietly omits a club produces a travel feature that is silently null for every
match that club played.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from engine import db
from services.stadium_coords import bridge, locationiq, reconcile, wikidata

DATA_DIR = Path("data/stadiums")
OUT = Path("reference/stadiums.csv")


def clubs_and_divisions(conn, divisions: tuple[str, ...]) -> dict[str, str]:
    """canonical_name -> the divisions it has appeared in, comma separated."""
    placeholders = ",".join("?" * len(divisions))
    rows = conn.execute(
        "SELECT t.canonical_name, GROUP_CONCAT(DISTINCT m.division) "
        "FROM teams t JOIN matches m "
        "  ON m.home_team_id = t.team_id OR m.away_team_id = t.team_id "
        f"WHERE m.division IN ({placeholders}) "
        "GROUP BY t.canonical_name ORDER BY t.canonical_name",
        divisions,
    )
    return {name: divs or "" for name, divs in rows}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--divisions", default="E0,E1,E2,E3,EC",
                        help="Comma-separated. EC is in the joint fit, so it is in by default.")
    parser.add_argument("--no-geocode", action="store_true",
                        help="Skip the LocationIQ check. Faster, and unverified.")
    parser.add_argument("--refresh", action="store_true",
                        help="Ignore the cached Wikidata response and re-query.")
    args = parser.parse_args(argv)

    divisions = tuple(d.strip() for d in args.divisions.split(",") if d.strip())
    cache = DATA_DIR / "wikidata_venues.json"
    if args.refresh and cache.exists():
        cache.unlink()

    conn = db.connect()
    club_divisions = clubs_and_divisions(conn, divisions)
    print(f"{len(club_divisions)} clubs in {'+'.join(divisions)}")

    venues, ambiguous = wikidata.venues(wikidata.fetch(cache))
    print(f"{len(venues)} UK clubs from Wikidata with an unambiguous current venue"
          f" ({len(ambiguous)} ambiguous, excluded)")

    overrides = bridge.load_overrides()
    matched, unmatched, collided = bridge.match(club_divisions, venues, overrides.targets)
    print(f"matched {len(matched)}/{len(club_divisions)}"
          f"  ({len(overrides.targets)} via overrides)")

    geocoder = None
    if not args.no_geocode:
        try:
            geocoder = locationiq.Geocoder(locationiq.api_key(), DATA_DIR / "geocode")
        except locationiq.MissingKey as error:
            print(f"\nFAIL  {error}")
            return 1

    rows, unresolved = reconcile.build(
        matched, club_divisions, geocoder, overrides.venues, overrides.reviewed)
    reconcile.write_csv(rows, args.out)
    geocoded = sum(1 for r in rows if r.source == "locationiq")
    verified = sum(1 for r in rows if r.check_status in VERIFIED)
    print(f"wrote {len(rows)}/{len(club_divisions)} rows to {args.out}"
          f"  ({geocoded} geocode-sourced, {verified} verified)")
    if geocoder is not None:
        print(f"{geocoder.requests_made} LocationIQ request(s) made")

    still_missing = sorted(set(unmatched) - set(overrides.venues)) + unresolved
    return _report(rows, still_missing, collided, ambiguous, club_divisions)


#: Check outcomes that mean "a human has to look at this row before the table
#: is used". `unchecked` is deliberately absent -- a geocode-sourced row is
#: expected to be unchecked and is reported by its `source`, not as a defect.
NEEDS_EYES = ("review", "out_of_bounds", "not_a_venue", "no_match")

#: Statuses that count as verified. `agree_reverse` is a real confirmation,
#: not a weaker one: the coordinate was handed back an address in the town the
#: venue belongs to, which is what the table is claiming.
VERIFIED = ("agree", "agree_reverse", "agree_manual")


def _report(rows, unmatched, collided, ambiguous, club_divisions) -> int:
    counts: dict[str, int] = {}
    for row in rows:
        counts[row.check_status] = counts.get(row.check_status, 0) + 1
    print("\ncheck status: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())))

    needs_eyes = [r for r in rows if r.check_status in NEEDS_EYES]
    _print_rows_to_review(needs_eyes)
    _print_block(
        collided, "name collision(s) -- add an override naming the right one",
        lambda club: f"  {club:<22} -> {collided[club]}")
    _print_block(
        unmatched, f"unmatched club(s) -- add to {bridge.OVERRIDES}",
        lambda club: f"  {club}  [{club_divisions.get(club, '')}]")

    wanted = {bridge.normalise(c) for c in club_divisions}
    relevant = {k: v for k, v in ambiguous.items() if bridge.normalise(k) in wanted}
    _print_block(
        relevant, "matched club(s) ambiguous in Wikidata",
        lambda club: f"  {club:<22} -> {sorted(relevant[club])}")

    print("\nStanding caveat -- the table is static, these clubs moved inside the corpus:")
    for club, move, when, km in reconcile.KNOWN_MOVES:
        print(f"  {club:<16} {when:<20} ~{km:>4.1f} km  {move}")
    print("  Only Rotherham changes town. See reconcile.KNOWN_MOVES.")

    return 2 if (needs_eyes or unmatched or collided) else 0


def _print_rows_to_review(rows) -> None:
    if not rows:
        return
    print(f"\n{len(rows)} row(s) to look at:")
    for row in rows:
        delta = f"{row.check_delta_km:.1f} km" if row.check_delta_km else "-"
        print(f"  {row.check_status:<14} {row.canonical_name:<22} {row.venue:<30}"
              f" {delta:>8}  {row.check_display_name[:60]}")


def _print_block(items, heading, line) -> None:
    if not items:
        return
    print(f"\n{len(items)} {heading}:")
    for key in sorted(items):
        print(line(key))


if __name__ == "__main__":
    raise SystemExit(main())
