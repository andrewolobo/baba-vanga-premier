"""Scrape fbref fixtures for a date range.

    python -m services.fbref_scraper --from 2026-08-08 --to 2026-08-08 \
        --comps 34,690 --out data/fbref/smoke.csv

Output is CSV or JSONL, never the database: this source is on trial, and
wiring it into `fixture_sync` is a decision to take once it is trusted
(docs/FBREF_SCRAPER.md §5).
"""

from __future__ import annotations

import argparse
import csv
import dataclasses
import json
from datetime import date, timedelta
from pathlib import Path

from services.fbref_scraper import config as config_module
from services.fbref_scraper import parse
from services.fbref_scraper.fetch import Fetcher

COLUMNS = tuple(f.name for f in dataclasses.fields(parse.Fixture))


def dates(config) -> list[str]:
    """Every ISO date in the configured range, inclusive."""
    if not config.date_from:
        raise ValueError("a start date is required (--from)")
    start = date.fromisoformat(config.date_from)
    end = date.fromisoformat(config.date_to or config.date_from)
    if end < start:
        raise ValueError(f"--to {end} is before --from {start}")
    return [(start + timedelta(days=n)).isoformat()
            for n in range((end - start).days + 1)]


def write(fixtures: list[parse.Fixture], path: Path, fmt: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        if fmt == "jsonl":
            for fixture in fixtures:
                handle.write(json.dumps(dataclasses.asdict(fixture)) + "\n")
        else:
            writer = csv.DictWriter(handle, fieldnames=COLUMNS)
            writer.writeheader()
            writer.writerows(dataclasses.asdict(f) for f in fixtures)


def _comps(value: str) -> tuple[int, ...]:
    return tuple(int(part) for part in value.split(",") if part.strip())


def settings(argv=None) -> config_module.ScraperConfig:
    """Command line over TOML file over defaults."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, help="TOML settings file")
    parser.add_argument("--from", dest="date_from", help="first date, ISO")
    parser.add_argument("--to", dest="date_to", help="last date, ISO (default: --from)")
    parser.add_argument("--comps", type=_comps,
                        help="competition ids to keep, comma separated (default: all)")
    parser.add_argument("--out", help="output file")
    parser.add_argument("--format", choices=["csv", "jsonl"])
    parser.add_argument("--cache-dir", dest="cache_dir", help="raw HTML cache")
    parser.add_argument("--profile-dir", dest="profile_dir", help="Chrome profile")
    parser.add_argument("--session-file", dest="session_file")
    parser.add_argument("--min-interval", dest="min_interval", type=float,
                        help="seconds between live requests")
    parser.add_argument("--retries", type=int,
                        help="session refreshes to attempt on a challenged response")
    parser.add_argument("--headless", action="store_true", default=None,
                        help="acquire the session headless (the probe never cleared)")
    args = vars(parser.parse_args(argv))
    return config_module.load(args.pop("config"), **args)


def main(argv=None) -> int:
    config = settings(argv)
    days = dates(config)

    fetcher = Fetcher(config)
    fixtures = []
    for day in days:
        html = fetcher.date_page(day)
        fixtures.extend(parse.parse_date_page(html, day, config.comps))

    write(fixtures, config.out, config.format)
    print(f"{len(fixtures)} fixtures from {len(days)} date(s), "
          f"{fetcher.requests_made} request(s) -> {config.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
