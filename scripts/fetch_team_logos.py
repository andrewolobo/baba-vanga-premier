"""One-off authoring tool: club crests into web/static/crests/.

    python scripts/fetch_team_logos.py [--only "Man United,Arsenal"] [--force]

Reads the reviewed mapping in reference/team_logos.csv, downloads each club's
crest from football-logos.cc, and writes the sizes the pages actually use,
downscaled locally with Lanczos. Run it after a promotion changes the served
clubs, or when the site redraws a crest.

The slug half of a logo URL is stable and lives in reference/; the hash half
changes whenever the site redraws a crest, so it is read at run time -- from
the image sitemap, which carries all 361 in one request.

**Why 700px and not the 3000px the site also offers.** The 3000px file lives
on a second host that must be asked for each club's page first, to learn that
size's hash (each size has its own, so a size cannot be reached by editing
another size's URL). That is two requests per club, and it earns a 429 after
about thirty of them, with the penalty outlasting a 240s backoff. The 700px
file needs no page read, comes from the host the sitemap points at, and is
still 5.5x the largest size written here. Measured rather than assumed: at
256px -- larger than anything shipped -- the two sources differ by a mean of
0.5/255 per channel, which is nothing. The smaller source is simply the right
one for the job, politeness aside.

Masters land in data/crests/ (gitignored) and are reused on a re-run, so
changing SIZES costs no downloads. Only the downscaled files are served.

Files are keyed by the same slug the team pages use (api.teams.team_slug), so a
page can reference /crests/64/<slug>.png with no second lookup. A club renamed
by the BBC changes that slug, so re-run this after such a rename.
"""

from __future__ import annotations

import argparse
import csv
import io
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import requests  # noqa: E402
from PIL import Image  # noqa: E402

from build_team_logos import USER_AGENT, fetch_logos  # noqa: E402  (a sibling script)

from api.teams import team_slug  # noqa: E402
from engine import config  # noqa: E402

#: The sizes the pages use, and only those. A crest is drawn at 34px, so 64 is
#: its file on a 2x screen and 128 on a 3x phone. A 256px tier was dropped
#: before it shipped: nothing renders a crest that large, and it cost 8MB of
#: committed assets for it.
SIZES = (128, 64)

SOURCE_PX = 700
IMAGE_URL = ("https://assets.football-logos.cc/logos/england/"
             f"{SOURCE_PX}x{SOURCE_PX}/{{slug}}.{{hash}}.png")

#: Cloudflare serves a 403 to the default urllib/requests agent.
HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9",
}

MASTER_DIR = config.REPO_ROOT / "data" / "crests"
STATIC_DIR = config.REPO_ROOT / "web" / "static" / "crests"

#: The site is a free service; a crawl of 146 clubs should not look like an
#: attack. One request per club at this spacing stays well under the rate the
#: image host refused.
DELAY_SECONDS = 1.5

#: A 429 is the site asking us to slow down, so wait and retry rather than
#: dropping the club: a partial crest set is worse than a slow one.
MAX_ATTEMPTS = 5
BACKOFF_SECONDS = 30.0

#: One pooled session, which is not a micro-optimisation: the host advertises
#: IPv6, and a fresh connection stalls ~43s on it before falling back to IPv4
#: (curl hides this with Happy Eyeballs; Python does not). Keep-alive pays that
#: once instead of once per club.
SESSION = requests.Session()
SESSION.headers.update(HEADERS)


def get(url: str) -> bytes:
    for attempt in range(MAX_ATTEMPTS):
        response = SESSION.get(url, timeout=60)
        if response.status_code != 429:
            response.raise_for_status()
            return response.content
        if attempt == MAX_ATTEMPTS - 1:
            break
        # The site's own figure if it gives one, otherwise back off doubling.
        pause = float(response.headers.get("Retry-After")
                      or BACKOFF_SECONDS * 2 ** attempt)
        print(f"    429 -- waiting {pause:.0f}s", file=sys.stderr)
        time.sleep(pause)
    response.raise_for_status()
    return response.content


def master_for(slug: str, digest: str, force: bool) -> bytes:
    """The crest at its source size, from the local cache unless it is missing."""
    cached = MASTER_DIR / f"{slug}.png"
    if cached.exists() and not force:
        return cached.read_bytes()
    data = get(IMAGE_URL.format(slug=slug, hash=digest))
    MASTER_DIR.mkdir(parents=True, exist_ok=True)
    cached.write_bytes(data)
    return data


def downscale(data: bytes, name: str) -> None:
    """Write one PNG per size, square and transparent, from the master."""
    with Image.open(io.BytesIO(data)) as image:
        source = image.convert("RGBA")
        for size in SIZES:
            target = STATIC_DIR / str(size)
            target.mkdir(parents=True, exist_ok=True)
            source.resize((size, size), Image.LANCZOS).save(
                target / f"{name}.png", "PNG", optimize=True)


def served_clubs(only: set[str] | None) -> list[tuple[str, str]]:
    """(canonical name, logo slug) for every club with a crest to fetch."""
    path = config.REFERENCE_DIR / "team_logos.csv"
    if not path.exists():
        raise SystemExit(f"{path} is missing; run scripts/build_team_logos.py first")
    with path.open("r", encoding="utf-8", newline="") as fh:
        rows = [(row["canonical_name"].strip(), row["logo_slug"].strip())
                for row in csv.DictReader(fh) if row["status"].strip() == "ok"]
    if only is None:
        return rows
    unknown = only - {canonical for canonical, _ in rows}
    if unknown:
        raise SystemExit(f"not mapped in {path}: {', '.join(sorted(unknown))}")
    return [row for row in rows if row[0] in only]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", help="comma-separated canonical names")
    parser.add_argument("--force", action="store_true",
                        help="re-download masters instead of reusing the cache")
    args = parser.parse_args()

    only = {name.strip() for name in args.only.split(",")} if args.only else None
    clubs = served_clubs(only)
    hashes = fetch_logos()

    failed: list[tuple[str, str]] = []
    for index, (canonical, slug) in enumerate(clubs, start=1):
        name = team_slug(canonical)
        digest = hashes.get(slug)
        if digest is None:
            failed.append((canonical, f"{slug!r} is no longer in the sitemap"))
            print(f"[{index}/{len(clubs)}] {canonical}: FAILED -- {slug!r} is "
                  "no longer in the sitemap; re-run scripts/build_team_logos.py",
                  file=sys.stderr)
            continue
        try:
            cached = (MASTER_DIR / f"{slug}.png").exists() and not args.force
            downscale(master_for(slug, digest, args.force), name)
        except (LookupError, OSError) as error:  # RequestException is an OSError
            failed.append((canonical, str(error)))
            print(f"[{index}/{len(clubs)}] {canonical}: FAILED -- {error}", file=sys.stderr)
            continue
        print(f"[{index}/{len(clubs)}] {canonical} -> {name}.png"
              f"{' (cached)' if cached else ''}")
        if not cached:
            time.sleep(DELAY_SECONDS)

    sizes = ", ".join(f"{size}px" for size in SIZES)
    print(f"\n{len(clubs) - len(failed)}/{len(clubs)} clubs written to "
          f"{config.relpath(STATIC_DIR)} at {sizes}")
    if failed:
        print(f"{len(failed)} failed:", file=sys.stderr)
        for canonical, error in failed:
            print(f"  {canonical}: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
