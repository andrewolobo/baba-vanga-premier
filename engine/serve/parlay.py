"""One parlay from the day's games (`docs/PARLAY_PLAN.md`, B24).

**A view over stored numbers, never a new model.** Each live game
contributes one leg. Where the game's **published call** (the confidence
rule, `engine/serve/tips.py`) is of a chosen type, the leg *is* that call
-- the graded one. Where it is not, the leg is **derived** (D12,
2026-09-04): the likeliest option of the chosen types, read from the same
stored prediction the call was made from -- the favourite for straight
wins, the best double-chance union, the underdog +1.5. A derived leg is
not a published call and is not graded, and the page says so on the leg
(D14); with every type selected the published call always wins this rule,
so the default view is exactly the published tip list.

The combined figure is the **product of the legs' claims**, measured
honest twice: probe row 113 (`b24_parlay_independence`) for the published
calls -- realised tracks the product within +/-2 pts at every size with
data, dependent-pair control fired at +14.3 -- and probe row 114
(`b24_market_legs`) for the derived legs: every type's claimed-versus-
delivered is unresolved within +/-1 pt pooled (win +0.61, dc -0.23, ah
-0.09; derived-only subsets likewise), slip products show no resolved
negative, and the planted +5-pt over-claim control fired on all three
types. The weakest region -- derived +1.5 legs claiming under 0.70 --
over-claims by 2-4 pts in the point estimate, unresolved; recorded in
`PARLAY_PLAN.md` §9. Beyond ~10 legs the product is unverifiable in
sample and ships as labelled theory.

Owner decisions (`PARLAY_PLAN.md` §2, §8, §9): selection runs here,
server-side, because the site's frontend never computes a probability;
risk is a minimum claim per leg, three presets; the type chips are
multi-select toggles, never none (D8 as amended); **D13** no veto -- every
live game appears whatever its leg claims; legs run to the day's pool
under a hard cap of 46; the warning is `below_even`, the product under a
coin flip. A fixture whose UK kick-off has passed leaves the pool; fewer
qualifying legs than asked for are returned as they are, **never padded**.
Goal lines are absent deliberately: the rule publishes no over/under call
(B4 closed by measurement) and the owner left them out.

No import from `engine.eval` or `engine.serve.tips`: the API loads this
module and must keep starting without the measurement stack.
"""

from __future__ import annotations

import math
import re
from datetime import datetime
from typing import Any

#: Sizes. The slider's real ceiling is the day's pool (on the wire); 46 is
#: the largest matchday in the dev corpus and the hard cap behind it.
DEFAULT_LEGS = 2
MIN_LEGS = 2
MAX_LEGS = 46

#: The risk presets: a minimum claimed probability per leg, in the currency
#: the rule's own floor and ceiling use. `web/src/lib/api.js` mirrors these
#: for the page's controls. "any" is every call the rule published.
PRESETS = {"safer": 0.80, "balanced": 0.70, "any": 0.0}
DEFAULT_MIN_CLAIM = PRESETS["safer"]

#: The three market groups the rule publishes, and (D12) the columns a leg
#: of each type is derived from when the game's call is of another type.
#: `web/src/lib/api.js` mirrors the keys and labels as toggle chips.
SIDE_GROUPS = {
    "win": frozenset({"H", "A"}),
    "dc": frozenset({"1X", "X2", "12"}),
    "ah": frozenset({"H+1.5", "A+1.5"}),
}
CANDIDATES = {
    "win": (("H", "p_home"), ("A", "p_away")),
    "dc": (("1X", "p_1x"), ("X2", "p_x2"), ("12", "p_12")),
}
DEFAULT_SIDES = "any"

_HHMM = re.compile(r"^\d{2}:\d{2}$")


def parse_sides(sides: str) -> tuple[str, tuple[str, ...]]:
    """Normalise a `sides` value to (canonical string, chosen group keys).

    Accepts "any" or a comma-separated subset of `SIDE_GROUPS` in any order
    ("dc,win" and "win,dc" are the same selection); a subset naming every
    group normalises back to "any". Raises on an empty or unknown selection
    -- a parlay drawn from no call types is a request error, not an empty
    page.
    """
    chosen = list(SIDE_GROUPS) if sides == "any" else [k for k in sides.split(",") if k]
    if not chosen or any(k not in SIDE_GROUPS for k in chosen):
        raise ValueError("sides must be 'any' or a comma-separated subset of "
                         f"{sorted(SIDE_GROUPS)}, got {sides!r}")
    keys = tuple(k for k in SIDE_GROUPS if k in chosen)
    name = "any" if len(keys) == len(SIDE_GROUPS) else ",".join(keys)
    return name, keys


def derive_leg(row: dict[str, Any], keys: tuple[str, ...]) -> dict[str, Any] | None:
    """The game's one leg for the chosen types -- the D12 rule.

    The published call when its group is chosen (it is the graded one, so it
    outranks even a likelier option of another chosen type); otherwise the
    likeliest option across the chosen types, read from the model view the
    row already carries (B22): outrights from `p_home`/`p_away`, unions from
    the sums, the +1.5 always the underdog's -- the favourite's is a
    near-certainty on no menu. D13: no veto, whatever the option claims.

    A derived leg keeps the published call beside it (`published_side`,
    `published_prob`) so the page can name it (D14). Returns None when the
    row lacks the fields a derivation needs -- a leg is never invented from
    missing numbers, and the game then appears only for its published type.
    """
    group = next((k for k, codes in SIDE_GROUPS.items()
                  if row.get("side") in codes), None)
    if group in keys:
        return {**row, "derived": False}
    best = None
    for key in keys:
        if key == "ah":
            if row.get("p_home") is None or row.get("p_away") is None:
                continue
            candidates = [("A+1.5", row.get("p_a15"))
                          if row["p_home"] >= row["p_away"]
                          else ("H+1.5", row.get("p_h15"))]
        else:
            candidates = [(side, row.get(column))
                          for side, column in CANDIDATES[key]]
        for side, prob in candidates:
            if prob is not None and (best is None or prob > best[1]):
                best = (side, prob)
    if best is None:
        return None
    return {**row, "side": best[0], "model_prob": float(best[1]),
            "derived": True, "published_side": row["side"],
            "published_prob": row["model_prob"]}


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
                min_claim: float = DEFAULT_MIN_CLAIM,
                sides: str = DEFAULT_SIDES, now: datetime) -> dict:
    """The top `legs` of the day in the chosen markets, at or above `min_claim`.

    `rows` are tip rows as `/tips` serves them, model view included. Each
    live game becomes one leg via `derive_leg`; order is claim descending,
    then earlier kick-off, then `fixture_id`, so the same pool always yields
    the same parlay. **One leg per fixture**: if two rule versions both
    tipped a match (`RUNBOOK.md` §0 guards against it) only the higher claim
    is eligible -- two legs on one game are the dependence the whole figure
    assumes away, measured at +14.3 pts by row 113's control.

    Returns `legs` (the chosen rows, in order; a derived one carries
    `derived: true` and its `published_side`), `claimed` (their product, or
    None when there is nothing to multiply -- never 0, which would read as
    "cannot win"), `requested`, `available` (distinct fixtures whose leg
    clears the threshold, before the cut), `pool` (distinct live fixtures
    with a leg -- the slider's ceiling), `min_claim`, `sides` echoed in its
    canonical form, and `below_even` (the product sits under a coin flip).
    """
    if not MIN_LEGS <= legs <= MAX_LEGS:
        raise ValueError(f"legs must be {MIN_LEGS}..{MAX_LEGS}, got {legs}")
    if not 0.0 <= min_claim <= 1.0:
        raise ValueError(f"min_claim must be a probability, got {min_claim}")
    sides, keys = parse_sides(sides)

    live = [leg for leg in (derive_leg(r, keys) for r in rows
                            if not kicked_off(r, now))
            if leg is not None]
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
    claimed = math.prod(r["model_prob"] for r in chosen) if chosen else None
    return {
        "legs": chosen,
        "claimed": claimed,
        "requested": legs,
        "available": len(distinct),
        "pool": len({r["fixture_id"] for r in live}),
        "min_claim": min_claim,
        "sides": sides,
        "below_even": bool(chosen) and claimed < 0.5,
    }
