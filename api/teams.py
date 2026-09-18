"""Team names, slugs and venues for the public pages (docs/SEO_PLAN.md 2.2).

Pure, and read once from `reference/`. `teams.canonical_name` is
football-data's abbreviation ("Man United", "Nott'm Forest"), which nobody
types into a search box, so every page title, heading and URL uses the BBC's
full name instead (D12, owner 2026-09-18). `reference/bbc_teams.csv` already
maps one to the other for the results bridge, keyed on the canonical name.

A slug is computed from the display name, never stored: a rename changes the
slug, and the page's id-first URL (D9) 301s an old slug to the new one, so
no link breaks.

The venue is `reference/venues.csv`, a hand-reviewed list of the served
clubs' grounds (owner decision 2026-09-18), shown only where its `status` is
`ok`; a `check` row is a name not yet confirmed, and prints nothing. It is
**not** `reference/stadiums.csv`: that file was built from Wikidata for the
travel measurement, whose labels are stale for a page (Brentford at Griffin
Park, which it left in 2020; Stoke at the Britannia Stadium) and whose
coordinates are a measured input that must not be rewritten for display.
"""

from __future__ import annotations

import csv
import re
import unicodedata
from functools import cache

from engine import config

VENUES_CSV = config.REFERENCE_DIR / "venues.csv"


@cache
def _names() -> dict[str, str]:
    with open(config.BBC_TEAMS_CSV, encoding="utf-8", newline="") as f:
        return {r["canonical_name"]: r["bbc_name"] for r in csv.DictReader(f)}


@cache
def _venues() -> dict[str, str]:
    with open(VENUES_CSV, encoding="utf-8", newline="") as f:
        return {r["canonical_name"]: r["venue"] for r in csv.DictReader(f)
                if r["status"] == "ok"}


def display_name(canonical: str) -> str:
    """The BBC's name for a club, or the canonical one if it has none."""
    return _names().get(canonical, canonical)


def venue(canonical: str) -> str | None:
    """The club's home ground, or None until its name is confirmed."""
    return _venues().get(canonical)


def slug(text: str) -> str:
    """Lowercase ASCII words joined by `-`: accents folded, anything else a
    separator. "Brighton & Hove Albion" -> "brighton-hove-albion"."""
    folded = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", folded.lower()).strip("-")


def fixture_slug(home: str, away: str) -> str:
    """The words of a match page's URL, from two canonical names."""
    return f"{slug(display_name(home))}-vs-{slug(display_name(away))}"
