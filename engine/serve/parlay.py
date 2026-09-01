"""One parlay from the day's published calls (`docs/PARLAY_PLAN.md`, B24).

**This is a view over calls that already exist, not a rule.** Every leg is a
row the confidence rule published (`engine/serve/tips.py`) and the record
grades on its own; this module only filters those rows by a minimum claimed
probability, ranks what is left, and multiplies the claims of the top few.
It publishes nothing and reads no outcome.

The combined figure is the **product of the legs' claims**, on the
assumption the games are independent -- distinct matches, so the first
approximation, and the one thing the page adds that gate row 110 did not
measure (`PARLAY_PLAN.md` §3 is the probe that will). It is a claim in the
same sense as `tips.model_prob`, and is labelled "claimed" wherever it is
shown.

Owner decisions 2026-09-01 (`PARLAY_PLAN.md` §2): the selection runs here,
server-side, because the site's frontend never computes a probability
(`web/src/lib/api.js`); the risk control is a minimum claim per leg, offered
as three presets; the page offers 2 to 4 legs and warns at 4, where the
Saturday top-4 product sits below a coin flip (0.49); a fixture whose UK
kick-off has passed leaves the pool; fewer qualifying legs than asked for
are returned as they are, **never padded** from below the threshold.

No import from `engine.eval` or `engine.serve.tips`: the API loads this
module and must keep starting without the measurement stack.
"""

from __future__ import annotations

import math
import re
from datetime import datetime
from typing import Any

#: Sizes the page offers. Measured on the dev corpus (`PARLAY_PLAN.md` §1,
#: claims only): the top-k legs of a Saturday multiply to 0.71 / 0.59 / 0.49
#: at k = 2 / 3 / 4. Two is the default because it is the recommendation;
#: four is offered with a warning because it is more likely to lose than win.
DEFAULT_LEGS = 2
MIN_LEGS = 2
MAX_LEGS = 4
WARN_LEGS = 4

#: The risk presets: a minimum claimed probability per leg, in the currency
#: the rule's own floor and ceiling use. `web/src/lib/api.js` mirrors these
#: for the page's controls. "any" is every call the rule published.
PRESETS = {"safer": 0.80, "balanced": 0.70, "any": 0.0}
DEFAULT_MIN_CLAIM = PRESETS["safer"]

_HHMM = re.compile(r"^\d{2}:\d{2}$")


def kicked_off(row: dict[str, Any], now: datetime) -> bool:
    """True when the fixture's kick-off is at or before `now`.

    `match_date` and `kickoff_time` are UK wall-clock on the wire (both feeds
    publish them so; `web/src/lib/kickoff.js` converts for the viewer), so
    `now` must be UK wall-clock too -- the API passes Europe/London. ISO
    strings compare correctly as text, which keeps this free of any parsing.

    A fixture with no usable kick-off time is never treated as kicked off: it
    stays in the pool for the whole of its date rather than being dropped on
    a guess.
    """
    time = row.get("kickoff_time")
    if not time or not _HHMM.match(time):
        return False
    return f"{row['match_date']} {time}" <= now.strftime("%Y-%m-%d %H:%M")


def select_legs(rows: list[dict[str, Any]], *, legs: int = DEFAULT_LEGS,
                min_claim: float = DEFAULT_MIN_CLAIM, now: datetime) -> dict:
    """The top `legs` published calls at or above `min_claim`, and their product.

    `rows` are tip rows as `/tips` serves them (`model_prob`, `fixture_id`,
    `match_date`, `kickoff_time`, ...). Order is claim descending, then
    earlier kick-off, then `fixture_id`, so the same pool always yields the
    same parlay. **One leg per fixture**: if two rule versions both tipped a
    match (`RUNBOOK.md` §0 guards against it) only the higher claim is
    eligible -- two legs on one game are the dependence the whole figure
    assumes away.

    Returns `legs` (the chosen rows, in order), `claimed` (their product, or
    None when there is nothing to multiply -- never 0, which would read as
    "cannot win"), `requested`, `available` (how many distinct fixtures
    cleared the threshold, before the cut to `legs`, so the page can say "2
    of 3 clear this threshold today"), `pool` (distinct fixtures still to
    kick off, before the threshold -- so "no calls live" and "none clears
    this bar" are different sentences), `min_claim` and `size_warning`.
    """
    if not MIN_LEGS <= legs <= MAX_LEGS:
        raise ValueError(f"legs must be {MIN_LEGS}..{MAX_LEGS}, got {legs}")
    if not 0.0 <= min_claim <= 1.0:
        raise ValueError(f"min_claim must be a probability, got {min_claim}")

    live = [r for r in rows if not kicked_off(r, now)]
    pool = [r for r in live if r["model_prob"] >= min_claim]
    pool.sort(key=lambda r: (-r["model_prob"],
                             r.get("kickoff_time") is None,
                             r.get("kickoff_time") or "",
                             r["fixture_id"]))
    distinct, seen = [], set()
    for r in pool:
        if r["fixture_id"] not in seen:
            seen.add(r["fixture_id"])
            distinct.append(r)
    chosen = distinct[:legs]
    return {
        "legs": chosen,
        "claimed": math.prod(r["model_prob"] for r in chosen) if chosen else None,
        "requested": legs,
        "available": len(distinct),
        "pool": len({r["fixture_id"] for r in live}),
        "min_claim": min_claim,
        "size_warning": legs >= WARN_LEGS,
    }
