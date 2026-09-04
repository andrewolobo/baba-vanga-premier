"""The parlay selector: a ranking over stored numbers, nothing more.

Planted rows only. Nothing here reads a database or an outcome -- the
selector derives and multiplies claims it is handed, and these tests pin
that it picks the right rows, in a fixed order, never invents a leg from
missing numbers, and never pads a slot.
"""

from __future__ import annotations

import math
import random
from datetime import datetime

import pytest

from engine.serve import parlay

NOW = datetime(2026, 9, 5, 12, 0)   # Saturday noon, UK wall-clock


def row(fixture_id, prob, kickoff="15:00", date="2026-09-05", side="A+1.5", **extra):
    return {"fixture_id": fixture_id, "tip_id": fixture_id, "model_prob": prob,
            "match_date": date, "kickoff_time": kickoff, "side": side,
            **extra}


def viewed(fixture_id, prob, side, ph, pdr, pa, h15, a15, **extra):
    """A row carrying the model view the API serves beside every tip (B22)."""
    return row(fixture_id, prob, side=side, p_home=ph, p_draw=pdr, p_away=pa,
               p_1x=round(ph + pdr, 2), p_x2=round(pdr + pa, 2),
               p_12=round(ph + pa, 2), p_h15=h15, p_a15=a15, **extra)


#: Published calls only -- every test on POOL uses the default "any", where
#: the published call always wins the leg rule and no view field is needed.
POOL = [
    row(1, 0.83),
    row(2, 0.79, kickoff="17:30", side="12"),
    row(3, 0.83, kickoff="12:30", side="H+1.5"),
    row(4, 0.71, side="1X"),
    row(5, 0.58, side="H"),
    row(6, 0.83, kickoff=None),
]

#: The same shape with full views, for the market-selector rule (D12).
VIEWED = [
    viewed(1, 0.83, "A+1.5", 0.44, 0.28, 0.28, 0.92, 0.83),
    viewed(2, 0.79, "12", 0.40, 0.21, 0.39, 0.85, 0.81, kickoff="17:30"),
    viewed(3, 0.83, "H+1.5", 0.30, 0.28, 0.42, 0.83, 0.95, kickoff="12:30"),
    viewed(4, 0.71, "1X", 0.43, 0.28, 0.29, 0.90, 0.84),
    viewed(5, 0.58, "H", 0.58, 0.24, 0.18, 0.95, 0.70),
    viewed(6, 0.83, "A+1.5", 0.45, 0.27, 0.28, 0.91, 0.83, kickoff=None),
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
    assert out["pool"] == 6           # the games exist; the bar is what empties it
    assert out["below_even"] is False  # no slip, no warning


def test_with_every_type_on_the_leg_is_always_the_published_call():
    """D12's anchor property: the default view is the published tip list --
    the market selector changes nothing until a selection is narrowed."""
    out = parlay.select_legs(VIEWED, legs=6, min_claim=0.0, now=NOW)
    assert all(r["derived"] is False for r in out["legs"])
    assert sorted(r["model_prob"] for r in out["legs"]) == sorted(
        r["model_prob"] for r in VIEWED)


def test_a_narrowed_type_derives_the_games_leg_instead_of_dropping_the_game():
    """D12/D13: straight wins on a hedged game shows that game's favourite,
    marked as derived with the published call kept beside it."""
    out = parlay.select_legs(VIEWED, legs=2, min_claim=0.0, sides="win", now=NOW)
    assert out["pool"] == 6                       # every game has a win leg
    assert [r["fixture_id"] for r in out["legs"]] == [5, 6]
    ours, derived = out["legs"]
    assert ours["derived"] is False and ours["side"] == "H"
    assert derived["derived"] is True and derived["side"] == "H"
    assert derived["model_prob"] == pytest.approx(0.45)
    assert derived["published_side"] == "A+1.5"
    assert derived["published_prob"] == pytest.approx(0.83)
    safer = parlay.select_legs(VIEWED, legs=2, min_claim=0.5, sides="win", now=NOW)
    assert (safer["available"], safer["pool"]) == (1, 6)


def test_the_published_call_outranks_a_likelier_option_of_the_same_type():
    """Fixture 4's published 1X (0.71) stays even though its 12 sums to 0.72
    -- the graded call wins the leg rule whenever its type is chosen."""
    out = parlay.select_legs(VIEWED, legs=6, min_claim=0.0, sides="dc", now=NOW)
    assert [r["fixture_id"] for r in out["legs"]] == [5, 2, 6, 3, 1, 4]
    by_id = {r["fixture_id"]: r for r in out["legs"]}
    assert by_id[4]["side"] == "1X" and by_id[4]["derived"] is False
    assert by_id[4]["model_prob"] == pytest.approx(0.71)
    assert by_id[5]["side"] == "1X" and by_id[5]["derived"] is True
    assert by_id[5]["model_prob"] == pytest.approx(0.82)
    assert by_id[6]["side"] == "12"               # argmax, ties to the earlier


def test_the_handicap_leg_is_always_the_underdogs():
    out = parlay.select_legs(VIEWED, legs=2, min_claim=0.0, sides="ah", now=NOW)
    assert [r["fixture_id"] for r in out["legs"]] == [4, 3]
    derived, ours = out["legs"]
    assert derived["derived"] is True and derived["side"] == "A+1.5"
    assert derived["model_prob"] == pytest.approx(0.84)   # home is the favourite
    assert ours["derived"] is False and ours["side"] == "H+1.5"


def test_a_mixed_selection_prefers_the_published_call_across_types():
    """With win+dc on, fixture 5 keeps its published H at 0.58 even though
    its 1X sums to 0.82: the graded call wins whenever its type is chosen."""
    out = parlay.select_legs(VIEWED, legs=6, min_claim=0.0, sides="dc,win", now=NOW)
    by_id = {r["fixture_id"]: r for r in out["legs"]}
    assert by_id[5]["side"] == "H" and by_id[5]["derived"] is False
    assert by_id[5]["model_prob"] == pytest.approx(0.58)
    assert by_id[1]["side"] == "1X" and by_id[1]["derived"] is True
    assert [r["fixture_id"] for r in out["legs"]][:3] == [2, 6, 3]
    assert out["sides"] == "win,dc"


def test_a_row_without_its_view_cannot_grow_a_derived_leg():
    """POOL rows carry no model view, so narrowing to double chance leaves
    only the games whose published call already is one -- a leg is never
    invented from missing numbers."""
    out = parlay.select_legs(POOL, legs=6, min_claim=0.0, sides="dc", now=NOW)
    assert [r["fixture_id"] for r in out["legs"]] == [2, 4]
    assert out["pool"] == 2


def test_sides_parse_normalises_and_never_selects_nothing():
    assert parlay.parse_sides("any") == ("any", ("win", "dc", "ah"))
    assert parlay.parse_sides("ah,dc,win") == ("any", ("win", "dc", "ah"))
    assert parlay.parse_sides("dc,win") == ("win,dc", ("win", "dc"))
    assert parlay.parse_sides("win,win") == ("win", ("win",))
    for bad in ("", "ou25", "win,ou25"):
        with pytest.raises(ValueError):
            parlay.parse_sides(bad)


def test_below_even_keys_on_the_product_not_the_leg_count():
    """D11: a straight-wins double can be below even while a five-leg
    handicap slip is not the moment its product clears 0.5."""
    strong = [row(i, 0.90) for i in range(1, 6)]
    five = parlay.select_legs(strong, legs=5, min_claim=0.0, now=NOW)
    assert five["claimed"] == pytest.approx(0.9 ** 5) and five["below_even"] is False
    weak = [row(1, 0.60, side="H"), row(2, 0.60, side="A")]
    double = parlay.select_legs(weak, legs=2, min_claim=0.0, sides="win", now=NOW)
    assert double["claimed"] == pytest.approx(0.36) and double["below_even"] is True


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
    the same game twice is exactly the dependence the whole figure assumes
    away -- and the B24 control measured what it would cost (+14.3 pts)."""
    twice = [row(1, 0.74, tip_id=11, rule_version="confidence-v2"),
             row(1, 0.80, tip_id=12, rule_version="confidence-v3"),
             row(2, 0.77)]
    out = parlay.select_legs(twice, legs=3, min_claim=0.0, now=NOW)
    assert [(r["fixture_id"], r["tip_id"]) for r in out["legs"]] == [(1, 12), (2, 2)]
    assert out["available"] == 2


def test_the_same_pool_always_gives_the_same_parlay():
    shuffled = list(VIEWED)
    random.Random(7).shuffle(shuffled)
    a = parlay.select_legs(VIEWED, legs=3, min_claim=0.0, sides="dc", now=NOW)
    b = parlay.select_legs(shuffled, legs=3, min_claim=0.0, sides="dc", now=NOW)
    assert [r["fixture_id"] for r in a["legs"]] == [r["fixture_id"] for r in b["legs"]]


def test_size_bounds_hold_at_the_hard_cap():
    """D9: the slider's real ceiling is the day's pool; 46 -- the largest
    matchday in the corpus -- is the hard cap behind it."""
    big = [row(i, 0.80) for i in range(1, 47)]
    out = parlay.select_legs(big, legs=46, min_claim=0.0, now=NOW)
    assert len(out["legs"]) == 46
    assert out["claimed"] == pytest.approx(0.80 ** 46)
    assert out["below_even"] is True
    for bad in (1, 47):
        with pytest.raises(ValueError):
            parlay.select_legs(POOL, legs=bad, now=NOW)
    with pytest.raises(ValueError):
        parlay.select_legs(POOL, legs=2, min_claim=1.5, now=NOW)


def test_the_defaults_are_the_recommendation():
    assert parlay.DEFAULT_LEGS == 2
    assert parlay.DEFAULT_MIN_CLAIM == parlay.PRESETS["safer"] == 0.80
    assert (parlay.MIN_LEGS, parlay.MAX_LEGS) == (2, 46)
    assert parlay.DEFAULT_SIDES == "any"
    assert set(parlay.SIDE_GROUPS) == {"win", "dc", "ah"}
    out = parlay.select_legs(POOL, now=NOW)
    assert len(out["legs"]) == 2 and out["min_claim"] == 0.80
    assert math.isclose(out["claimed"], 0.83 * 0.83)


def test_the_pages_controls_mirror_the_selectors_constants():
    """`web/src/lib/api.js` restates the presets, the side groups and the leg
    bounds for the page's controls. Pinned here so the two cannot drift: the
    API validates against its own copy, so a mismatch would show as a control
    that always 400s."""
    from pathlib import Path
    js = Path("web/src/lib/api.js").read_text(encoding="utf-8")
    for key, label in (("safer", "Safer"), ("balanced", "Balanced"), ("any", "Any call")):
        assert f"['{key}', '{label}', {parlay.PRESETS[key]:g}]" in js, key
    for key, label in (("win", "Straight wins"),
                       ("dc", "Double chance"), ("ah", "Handicap +1.5")):
        assert f"['{key}', '{label}']" in js, key
        assert key in parlay.SIDE_GROUPS
    assert (f"LEGS = {{ min: {parlay.MIN_LEGS}, max: {parlay.MAX_LEGS},"
            f" default: {parlay.DEFAULT_LEGS} }}") in js
