"""One-off authoring tool: reference/team_logos.csv from football-logos.cc.

    python scripts/build_team_logos.py [--sitemap PATH] [--check]

Proposes the football-logos.cc slug for every canonical club by normalised-name
match against every name the bridge already knows (canonical names and the
football-data, fbref and BBC aliases), applies the hand-reviewed exceptions
below, and rewrites the reference file. It refuses to write while any club is
unresolved: a club the site spells in a way the normaliser cannot reach is a
human decision, not a fuzzy match (SPEC 0.2, as in build_betpawa_teams.py).

The stored slug is only the *name* half of a logo URL. The other half is a
content hash that changes whenever the site redraws a crest, so it is read at
download time by scripts/fetch_team_logos.py rather than pinned here -- a
reviewed mapping belongs in reference/, a volatile hash does not.

Slugs come from the site's own image sitemap, which lists every logo it
publishes; --sitemap reads a saved copy instead of fetching.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests  # noqa: E402

from api.teams import team_slug  # noqa: E402
from engine import config  # noqa: E402
from engine.ingest.teams import TeamBridge  # noqa: E402

SITEMAP_URL = "https://football-logos.cc/image-sitemap.xml.gz"

#: Cloudflare serves a 403 to the default urllib/curl agent.
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36")

#: A logo URL looks like
#: .../logos/england/700x700/<slug>.<hash>.png. A slug carrying `--` is a
#: historical crest ("arsenal--1904-1922") or a restyle
#: ("arsenal--black-monochrome"), never the club's current one.
SLUG_RE = re.compile(r"logos/england/700x700/([a-z0-9-]+)\.([0-9a-f]+)\.png")

#: canonical name -> slug, for the pairs the normaliser cannot reach.
#: Reviewed by hand 2026-09-21 against the 361 England slugs the site lists.
MANUAL = {
    "Dag and Red": "dagenham-and-redbridge",
    "Fylde": "afc-fylde",
    "Newport County": "newport",
}

#: Clubs the site publishes no crest for, checked by hand 2026-09-21 by
#: substring search over every England slug. All are long defunct or fell out
#: of the covered pyramid; they appear in old results only. A row is still
#: written for each, so that `absent` means "asked and answered" rather than
#: "forgotten", and a future run does not re-open the question.
ABSENT = {
    "Histon",
    "North Ferriby",
    "Nuneaton Town",
    "Rushden & D",
    "Weymouth",
}

COLUMNS = ["canonical_name", "logo_slug", "status"]


def normalise(name: str) -> str:
    """A club name as the site would slug it: accents folded, `&` spelled out
    (the site writes "dagenham-and-redbridge"), anything else a separator."""
    folded = unicodedata.normalize("NFKD", name.replace("&", " and "))
    folded = folded.encode("ascii", "ignore").decode().lower()
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", folded)).strip("-")


def fetch_logos(sitemap: Path | None = None) -> dict[str, str]:
    """Every current England crest: slug -> the hash in its 700px URL.

    scripts/fetch_team_logos.py downloads by these, which is why the hash is
    returned rather than discarded: it is the volatile half of a logo URL, and
    reading it here costs one request for all 361 crests.
    """
    if sitemap:
        raw = sitemap.read_bytes()
    else:
        response = requests.get(SITEMAP_URL, headers={"User-Agent": USER_AGENT},
                                timeout=60)
        response.raise_for_status()
        raw = response.content
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    xml = raw.decode("utf-8", errors="replace")
    return {slug: digest for slug, digest in SLUG_RE.findall(xml)
            if "--" not in slug}


def candidate_names(bridge: TeamBridge) -> dict[str, set[str]]:
    """canonical name -> every name we know it by, any of which the site may
    have used. football-data abbreviates ("Man United"), the BBC does not
    ("Manchester United"), and the site does both ("manchester-united", but
    "wolves" and "tottenham"), so no single source spells them all."""
    names = {canonical: {canonical} for canonical in bridge.canonical_names}
    for (_, alias), canonical in bridge.canonical_by_alias.items():
        if canonical in names and not alias.startswith("urn:") and not alias.isdigit():
            names[canonical].add(alias)
    if config.BBC_TEAMS_CSV.exists():
        with config.BBC_TEAMS_CSV.open("r", encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                canonical = row["canonical_name"].strip()
                if canonical in names:
                    names[canonical].add(row["bbc_name"].strip())
    return names


def propose(bridge: TeamBridge, slugs: set[str]) -> tuple[list[tuple[str, str, str]], list[str]]:
    """(rows, unresolved). A club matches on any of its known names, exactly
    first; a name the site suffixes ("Hull" -> "hull-city") is accepted only
    when exactly one slug extends it, so that "Oxford" never silently becomes
    Oxford City and "Plymouth" never becomes Plymouth Parkway."""
    rows: list[tuple[str, str, str]] = []
    unresolved: list[str] = []
    for canonical, names in sorted(candidate_names(bridge).items()):
        if canonical in ABSENT:
            rows.append((canonical, "", "absent"))
            continue
        if canonical in MANUAL:
            rows.append((canonical, MANUAL[canonical], "ok"))
            continue
        exact = {normalise(name) for name in names} & slugs
        if len(exact) == 1:
            rows.append((canonical, exact.pop(), "ok"))
            continue
        extended = {slug for name in names for slug in slugs
                    if slug.startswith(normalise(name) + "-")}
        if len(extended) == 1:
            rows.append((canonical, extended.pop(), "ok"))
        else:
            unresolved.append(canonical)
    return rows, unresolved


def render(rows: list[tuple[str, str, str]]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(COLUMNS)
    writer.writerows(rows)
    return buf.getvalue()


def render_module(rows: list[tuple[str, str, str]]) -> str:
    """The same mapping as a module the pages can import.

    The pages hold canonical names and nothing else -- a fixture row carries
    `home_team`, not a slug -- while a crest file is named for the club's
    display name ("Man United" -> manchester-united.png), which comes from
    `reference/bbc_teams.csv`. Rather than teach the browser that file, or add
    two fields to every row of every endpoint, the pairing is generated here
    as a lookup, in the same spirit as the rest of `reference/`: a reviewed
    table, not a rule applied at runtime.

    A club with no crest is simply absent, and `$lib/Crest.svelte` falls back
    to the generated badge for it.
    """
    entries = "".join(
        f"  {json.dumps(name)}: {json.dumps(team_slug(name))},\n"
        for name, _, status in rows if status == "ok")
    return (
        "// Generated by scripts/build_team_logos.py -- do not edit by hand.\n"
        "//\n"
        "// Canonical club name -> the basename of its crest under\n"
        "// web/static/crests/<size>/. A club absent here has no crest\n"
        "// published upstream; Crest.svelte draws its badge instead.\n"
        "const CRESTS = {\n"
        f"{entries}"
        "};\n"
        "\n"
        "export const crestFile = (name) => CRESTS[name] ?? null;\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sitemap", type=Path, help="a saved image-sitemap.xml[.gz]")
    parser.add_argument("--check", action="store_true", help="fail if the file is stale")
    args = parser.parse_args()

    bridge = TeamBridge.load()
    slugs = set(fetch_logos(args.sitemap))
    rows, unresolved = propose(bridge, slugs)

    if unresolved:
        print(f"{len(unresolved)} club(s) unresolved against {len(slugs)} slugs; "
              "add each to MANUAL or ABSENT in scripts/build_team_logos.py:",
              file=sys.stderr)
        for canonical in unresolved:
            print(f"  {canonical}", file=sys.stderr)
        return 1

    outputs = {
        config.REFERENCE_DIR / "team_logos.csv": render(rows),
        config.REPO_ROOT / "web" / "src" / "lib" / "crests.js": render_module(rows),
    }

    if args.check:
        stale = [path for path, text in outputs.items()
                 if (path.read_text(encoding="utf-8") if path.exists() else "") != text]
        if stale:
            for path in stale:
                print(f"{path} is stale; re-run scripts/build_team_logos.py", file=sys.stderr)
            return 1
        print(f"{len(outputs)} generated files are current ({len(rows)} clubs)")
        return 0

    for path, text in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    ok = sum(1 for row in rows if row[2] == "ok")
    for path in outputs:
        print(f"wrote {config.relpath(path)}")
    print(f"  {ok} clubs mapped, {len(rows) - ok} with no crest published, "
          f"from {len(slugs)} England slugs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
