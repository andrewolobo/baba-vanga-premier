"""Silent failure modes of the nginx site (docs/SEO_PLAN.md 1.3, 2.1).

None of these shows up anywhere but production: nginx is not part of
development, and each mistake leaves the site working for a person clicking
around it.

Pages (2.1): every path that is not a static file goes to the SvelteKit page
server, which decides 404s itself. That replaced 1.2's list of client routes,
whose test lived here: a route added without a matching regex entry 404'd on
a refresh and for every crawler. The page server's port is written in two
files, and a mismatch is a 502 on every page.

Headers (1.3): nosniff, the referrer policy and X-Robots-Tag are set once, at
server level. nginx drops every inherited add_header in a location that
declares one of its own, so an add_header in a proxied location strips all
three from everything behind it, without an error.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TEMPLATE = REPO / "deploy" / "nginx" / "bvp.conf.template"
WEB_UNIT = REPO / "deploy" / "systemd" / "bvp-web.service"


def _locations(text: str) -> list[tuple[str, str]]:
    return re.findall(r"location\s+(?:[=~]\s*)?(\S+)\s*\{([^}]*)\}", text)


def test_every_path_that_is_not_a_file_goes_to_the_page_server():
    text = TEMPLATE.read_text(encoding="utf-8")
    locations = dict(_locations(text))

    assert locations["/"].split() == ["try_files", "$uri", "@web;"]
    assert re.search(r"root /srv/bvp/web/build/client;", text), \
        "static files must come from build/client -- build/ holds the server's code"
    assert not re.search(r"index\.html", text), "a leftover of the client-rendered shell"

    port = re.search(r"^Environment=PORT=(\d+)$", WEB_UNIT.read_text(encoding="utf-8"), re.M)
    assert re.search(rf"proxy_pass http://127\.0\.0\.1:{port[1]};", locations["@web"])


def test_no_proxied_location_sets_headers_of_its_own():
    text = TEMPLATE.read_text(encoding="utf-8")
    proxied = [(path, body) for path, body in _locations(text) if "proxy_pass" in body]

    assert len(proxied) >= 6, "the proxied locations were not found; has the template's shape changed?"
    assert any(path == "@web" for path, _ in proxied)
    assert [path for path, body in proxied if "add_header" in body] == []
    assert re.search(r"^\s+add_header X-Robots-Tag \$bvp_robots_tag always;", text, re.M)
