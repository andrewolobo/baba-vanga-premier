"""Throttled fetching of fbref date pages, cached as raw HTML on disk.

Two rules shape this module.

*Never fetch twice for the same date.* A date page is written once and reread
forever, so re-parsing, a changed output format or a debugging loop all cost
zero requests. Sports Reference blocks for about 24 hours above roughly 10
requests a minute, and a block costs a day.

*Never hammer a refusal.* A challenged response buys one session refresh and
one retry, then the run stops. Retrying a Cloudflare block is how a slow
scraper becomes a banned one.
"""

from __future__ import annotations

import time

from curl_cffi import requests

from services.fbref_scraper import session as session_module

DATE_URL = "https://fbref.com/en/matches/{date}"


class Blocked(RuntimeError):
    """Cloudflare served a challenge instead of the page."""


class Fetcher:
    def __init__(self, config):
        self.config = config
        self.session = None
        self.requests_made = 0
        self._last_request = None

    def date_page(self, date: str) -> str:
        """The saved HTML for `date`, fetching it only if it is not cached."""
        cached = self.config.cache_dir / f"{date}.html"
        if cached.exists():
            return cached.read_text(encoding="utf-8")
        html = self._get(DATE_URL.format(date=date))
        cached.parent.mkdir(parents=True, exist_ok=True)
        cached.write_text(html, encoding="utf-8")
        return html

    def _get(self, url: str) -> str:
        for attempt in range(self.config.retries + 1):
            if self.session is None:
                # No session file at all means a first run on this machine, so
                # there is nothing to expire and nothing to try before minting.
                self.session = (
                    session_module.load(self.config.session_file)
                    if self.config.session_file.exists()
                    else session_module.acquire(self.config)
                )
            self._throttle()
            self.requests_made += 1
            response = requests.get(
                url,
                impersonate="chrome",
                headers={"User-Agent": self.session.user_agent},
                cookies=self.session.cookies,
                timeout=30,
            )
            if not _is_challenge(response):
                return response.text
            if attempt < self.config.retries:
                self.session = session_module.acquire(self.config)
        raise Blocked(
            f"{url} returned a Cloudflare challenge after "
            f"{self.config.retries} session refresh(es). Mint a new session on a "
            "desktop, or wait -- repeated attempts risk a 24h block."
        )

    def _throttle(self) -> None:
        if self._last_request is not None:
            wait = self.config.min_interval - (time.monotonic() - self._last_request)
            if wait > 0:
                time.sleep(wait)
        self._last_request = time.monotonic()


def _is_challenge(response) -> bool:
    """403, or a 200 whose body is the interstitial rather than the page."""
    if response.status_code == 403:
        return True
    return "just a moment" in response.text[:2000].lower()
