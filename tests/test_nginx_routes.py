"""The nginx site names every client-side route (docs/SEO_PLAN.md 1.2).

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
