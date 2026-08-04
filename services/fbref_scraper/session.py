"""The Cloudflare session: a cookie jar plus the exact user agent that earned it.

fbref sits behind a *managed* challenge. Plain requests, curl_cffi alone and
vanilla Playwright all fail it; the one route the probe found that clears it is
patchright driving real Chrome, headed, against a persistent profile. So a
browser is launched rarely, to mint a session, and never during scraping.

The cookie and the user agent are a pair. Presenting the cookie under a
different user agent looks like a stolen cookie, which is exactly what
Cloudflare is there to catch, so both travel together in one file.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

#: Any fbref page will do -- the challenge is per site, not per URL.
WARMUP_URL = "https://fbref.com/en/matches/"


@dataclass(frozen=True)
class Session:
    cookies: dict[str, str]
    user_agent: str


def load(path: Path) -> Session:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return Session(cookies=_fbref_cookies(raw["cookies"]),
                   user_agent=raw["user_agent"])


def _fbref_cookies(cookies: list[dict]) -> dict[str, str]:
    """Name -> value, for fbref only.

    The browser profile also holds cookies for the ad and script domains the
    page pulls in, and one of those is another `__cf_bm`. Flattening the whole
    jar into one dict would let it overwrite fbref's.
    """
    return {c["name"]: c["value"] for c in cookies
            if c["domain"].lstrip(".").endswith("fbref.com")}


def acquire(config) -> Session:
    """Mint a fresh session with a real browser, and save it. Needs a desktop."""
    from patchright.sync_api import sync_playwright

    config.profile_dir.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            user_data_dir=str(config.profile_dir),
            channel="chrome",
            headless=config.headless,
            no_viewport=True,
        )
        try:
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(WARMUP_URL, wait_until="domcontentloaded", timeout=45_000)
            _wait_for_challenge(page)
            page.wait_for_selector("table.stats_table", timeout=20_000)
            cookies, user_agent = context.cookies(), page.evaluate("navigator.userAgent")
        finally:
            context.close()

    config.session_file.parent.mkdir(parents=True, exist_ok=True)
    config.session_file.write_text(
        json.dumps({"cookies": cookies, "user_agent": user_agent}), encoding="utf-8")
    return Session(cookies=_fbref_cookies(cookies), user_agent=user_agent)


def _wait_for_challenge(page, timeout: float = 30.0) -> None:
    """Block until the interstitial goes away. It clears itself in seconds."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if "just a moment" not in page.title().lower():
            return
        time.sleep(1)
    raise RuntimeError("the Cloudflare challenge did not clear within 30s")
