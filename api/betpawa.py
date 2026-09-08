"""betPawa's country sites and the links into them (docs/BETPAWA_PLAN.md).

Pure: a host per served country and two URL builders. The ids come from the
cycle's scrape (`services/betpawa_feed.py`, migration 003) and are the same on
every betPawa site, so the only per-user fact is which site -- chosen from
the country the account's phone number was validated under (D6), server-side,
so the browser never learns the list (D5).

The prefill route is betPawa's own: `/external-prefill?selectionIds=<id>[,<id>]`
reads the ids, posts them to its prices endpoint, drops them into the betslip
and lands on the home page with the slip open -- verified in a headless browser
on 2026-09-08 for one selection and for three across three events (1.3 of the
plan). A parlay is the comma list; ids joined with `_` would be a same-event
combo, which nothing here builds.
"""

from __future__ import annotations

#: ISO 3166-1 alpha-2 -> host, read from betPawa's own web bundle on
#: 2026-09-08 (plan 1.4). Seventeen of the eighteen countries betpawa.com
#: names: **South Sudan has no host in the bundle** and is left out until one
#: is confirmed -- an unserved country gets no button, never a wrong site.
HOSTS = {
    "BJ": "www.betpawa.bj",
    "CD": "www.betpawa.cd",
    "CG": "cg.betpawa.com",
    "CM": "www.betpawa.cm",
    "GH": "www.betpawa.com.gh",
    "KE": "www.betpawa.co.ke",
    "LR": "lr.betpawa.com",
    "LS": "ls.betpawa.com",
    "ML": "ml.betpawa.com",
    "MW": "www.betpawa.mw",
    "MZ": "www.betpawa.co.mz",
    "NG": "www.betpawa.ng",
    "RW": "www.betpawa.rw",
    "SL": "sl.betpawa.com",
    "TZ": "www.betpawa.co.tz",
    "UG": "www.betpawa.ug",
    "ZM": "www.betpawa.co.zm",
}


def host_for(country: str | None) -> str | None:
    """The country's betPawa host, or None when betPawa does not serve it
    (or the account has no country yet)."""
    return HOSTS.get(country or "")


def event_url(host: str, event_id: str) -> str:
    """The event page, every market, nothing selected -- the fallback when
    the book carries no line for the published side (D11)."""
    return f"https://{host}/event/{event_id}?filter=all"


def prefill_url(host: str, selection_ids: list[str]) -> str:
    """The betslip pre-filled with these selections; one id is a single, a
    list across events is an accumulator."""
    if not selection_ids:
        raise ValueError("a prefill link needs at least one selection")
    return f"https://{host}/external-prefill?selectionIds={','.join(selection_ids)}"
