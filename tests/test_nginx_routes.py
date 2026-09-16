"""Silent failure modes of the nginx site (docs/SEO_PLAN.md 1.2, 1.3).

Neither of these shows up anywhere but production: nginx is not part of
development, and both mistakes leave the site working for a person clicking
around it.

Client routes (1.2):

`deploy/nginx/bvp.conf.template` answers 404 for any path that is neither a
file nor a route it lists. A SvelteKit page added without a matching entry
works when reached by a click from the front page -- the router never asks
the server -- and 404s on a refresh, a pasted link and for every crawler, so
nothing short of production would show it. This reads both sides instead.

A nested or parameterised route (`match/[match]`) cannot be expressed in the
regex's alternation and fails here too: by then the site needs a different
answer (SEO_PLAN.md D1), not a longer regex.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TEMPLATE = REPO / "deploy" / "nginx" / "bvp.conf.template"
ROUTES = REPO / "web" / "src" / "routes"


def test_every_client_route_is_named_in_the_nginx_site():
    pages = {p.parent.relative_to(ROUTES).as_posix()
             for p in ROUTES.rglob("+page.svelte")} - {"."}
    listed = re.findall(r"location ~ \^/\(([^)]+)\)/\?\$",
                        TEMPLATE.read_text(encoding="utf-8"))

    assert len(listed) == 1, "expected exactly one client-route location in the template"
    assert set(listed[0].split("|")) == pages


def test_no_api_location_sets_headers_of_its_own():
    """X-Robots-Tag (1.3), nosniff and the referrer policy are set once, at
    server level. nginx drops every inherited add_header in a location that
    declares one of its own, so an add_header in an /api/ location would put
    the API back in the index and strip the other two, without an error.
    """
    text = TEMPLATE.read_text(encoding="utf-8")
    api = re.findall(r"location\s+[=~]?\s*\^?(/api/\S*)\s*\{([^}]*)\}", text)

    assert len(api) >= 5, "the /api/ locations were not found; has the template's shape changed?"
    assert [path for path, body in api if "add_header" in body] == []
    assert re.search(r"^\s+add_header X-Robots-Tag \$bvp_robots_tag always;", text, re.M)
