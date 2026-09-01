"""The parlay selector: a ranking over published calls, nothing more.

Planted rows only. Nothing here reads a database or an outcome -- the
selector multiplies claims it is handed, and these tests pin that it picks
the right rows, in a fixed order, and never invents a leg.
"""

from __future__ import annotations

import math
import random
from datetime import datetime

import pytest

from engine.serve import parlay

NOW = datetime(2026, 9, 5, 12, 0)   # Saturday noon, UK wall-clock


def row(fixture_id, prob, kickoff="15:00", date="2026-09-05", **extra):
    return {"fixture_id": fixture_id, "tip_id": fixture_id, "model_prob": prob,
            "match_date": date, "kickoff_time": kickoff, "side": "A+1.5",
            **extra}


POOL = [
    row(1, 0.83),
    row(2, 0.79, kickoff="17:30"),
    row(3, 0.83, kickoff="12:30"),
    row(4, 0.71),
    row(5, 0.58),
    row(6, 0.83, kickoff=None),
]


def test_the_threshold_is_applied_and_nothing_is_padded_from_below_it():
    out = parlay.select_legs(POOL, legs=4, min_claim=0.80, now=NOW)
    assert [r["fixture_id"] for r in out["legs"]] == [3, 1, 6]
    assert out["available"] == 3 and out["requested"] == 4
    # Three legs cleared 0.80; the fourth slot is left empty rather than
    # filled with the 0.79 -- a "Safer" parlay must not carry a weaker leg.
    assert all(r["model_prob"] >= 0.80 for r in out["legs"])


def test_order_is_claim_then_earlier_kickoff_then_fixture_id_with_no_time_last():
    tied = [row(30, 0.80, kickoff="15:00"), row(10, 0.80, kickoff="15:00"),
            row(20, 0.80, kickoff="12:30"), row(40, 0.80, kickoff=None)]
    out = parlay.select_legs(tied, legs=4, min_claim=0.0, now=NOW)
    assert [r["fixture_id"] for r in out["legs"]] == [20, 10, 30, 40]


def test_the_combined_claim_is_the_product_of_the_legs():
    out = parlay.select_legs(POOL, legs=3, min_claim=0.70, now=NOW)
    assert out["claimed"] == pytest.approx(0.83 * 0.83 * 0.83)
    out = parlay.select_legs(POOL, legs=4, min_claim=0.70, now=NOW)
    assert out["claimed"] == pytest.approx(0.83 ** 3 * 0.79)
    assert out["available"] == 5      # every fixture at or above 0.70, uncapped
    assert out["pool"] == 6           # every fixture still to kick off


def test_an_empty_pool_claims_none_not_zero():
    out = parlay.select_legs(POOL, legs=2, min_claim=0.95, now=NOW)
    assert out["legs"] == [] and out["claimed"] is None and out["available"] == 0
    assert out["pool"] == 6           # the calls exist; the bar is what empties it


def test_a_fixture_that_has_kicked_off_leaves_the_pool():
    later = datetime(2026, 9, 5, 15, 0)   # exactly 15:00: the 15:00 games are off
    out = parlay.select_legs(POOL, legs=4, min_claim=0.0, now=later)
    # 12:30 and every 15:00 game have started; the 17:30 is still to come and
    # the fixture with no kick-off time is never treated as started.
    assert [r["fixture_id"] for r in out["legs"]] == [6, 2]
    assert out["available"] == 2 and out["pool"] == 2
    # Yesterday's fixture is gone whatever its time; tomorrow's stays.
    days = [row(7, 0.9, date="2026-09-04", kickoff="20:00"),
            row(8, 0.9, date="2026-09-06", kickoff="09:00")]
    out = parlay.select_legs(days, legs=2, min_claim=0.0, now=NOW)
    assert [r["fixture_id"] for r in out["legs"]] == [8]


def test_a_malformed_kickoff_time_is_treated_as_missing():
    assert parlay.kicked_off(row(1, 0.8, kickoff="TBC"), NOW) is False
    assert parlay.kicked_off(row(1, 0.8, kickoff=""), NOW) is False
    assert parlay.kicked_off(row(1, 0.8, kickoff="11:59"), NOW) is True
    assert parlay.kicked_off(row(1, 0.8, kickoff="12:01"), NOW) is False


def test_one_leg_per_fixture_keeps_the_higher_claim():
    """Two rule versions on one match must not become two legs: a parlay on
    the same game twice is exactly the dependence the product assumes away."""
    twice = [row(1, 0.74, tip_id=11, rule_version="confidence-v2"),
             row(1, 0.80, tip_id=12, rule_version="confidence-v3"),
             row(2, 0.77)]
    out = parlay.select_legs(twice, legs=3, min_claim=0.0, now=NOW)
    assert [(r["fixture_id"], r["tip_id"]) for r in out["legs"]] == [(1, 12), (2, 2)]
    assert out["available"] == 2


def test_the_same_pool_always_gives_the_same_parlay():
    shuffled = list(POOL)
    random.Random(7).shuffle(shuffled)
    a = parlay.select_legs(POOL, legs=3, min_claim=0.0, now=NOW)
    b = parlay.select_legs(shuffled, legs=3, min_claim=0.0, now=NOW)
    assert [r["fixture_id"] for r in a["legs"]] == [r["fixture_id"] for r in b["legs"]]


def test_size_bounds_and_the_warning_at_four():
    assert parlay.select_legs(POOL, legs=3, now=NOW)["size_warning"] is False
    assert parlay.select_legs(POOL, legs=4, now=NOW)["size_warning"] is True
    for bad in (1, 5):
        with pytest.raises(ValueError):
            parlay.select_legs(POOL, legs=bad, now=NOW)
    with pytest.raises(ValueError):
        parlay.select_legs(POOL, legs=2, min_claim=1.5, now=NOW)


def test_the_defaults_are_the_recommendation():
    assert parlay.DEFAULT_LEGS == 2
    assert parlay.DEFAULT_MIN_CLAIM == parlay.PRESETS["safer"] == 0.80
    assert (parlay.MIN_LEGS, parlay.MAX_LEGS, parlay.WARN_LEGS) == (2, 4, 4)
    out = parlay.select_legs(POOL, now=NOW)
    assert len(out["legs"]) == 2 and out["min_claim"] == 0.80
    assert math.isclose(out["claimed"], 0.83 * 0.83)


def test_the_pages_controls_mirror_the_selectors_constants():
    """`web/src/lib/api.js` restates PRESETS and the leg bounds for the page's
    buttons. Pinned here so the two cannot drift: the API validates against
    its own copy, so a mismatch would show as a button that always 400s."""
    from pathlib import Path
    js = Path("web/src/lib/api.js").read_text(encoding="utf-8")
    for key, label in (("safer", "Safer"), ("balanced", "Balanced"), ("any", "Any call")):
        assert f"['{key}', '{label}', {parlay.PRESETS[key]:g}]" in js, key
    assert (f"LEGS = {{ min: {parlay.MIN_LEGS}, max: {parlay.MAX_LEGS},"
            f" default: {parlay.DEFAULT_LEGS}, warn: {parlay.WARN_LEGS} }}") in js
