"""The validator (`services/analysis/validate.py`): every rule, passing and
failing, and the number extraction's edge cases.

Nothing the LLM writes is served until it passes these checks, so each one
is tested both ways. A check that never fails is as useless as one that
always does.
"""

from __future__ import annotations

from services.analysis.schemas import (
    Call, EvidencePack, Fact, Flag, MatchAnalysis, MenuLine, Pick, TeamSummary,
)
from services.analysis.validate import (
    check_analysis, check_summary, numbers_in, unknown_numbers,
)


def make_pack() -> EvidencePack:
    """A small, hand-checkable pack: Leeds v Hull, the call `12` at 74.2%."""
    facts = [
        Fact(id="HOME_FORM_L5", label="Leeds United results, last 5", value="WWDLW",
             scope="home_team"),
        Fact(id="HOME_WON_L5", label="Leeds United wins, last 5", value=3, unit="games",
             scope="home_team"),
        Fact(id="HOME_PPG_L5", label="Leeds United points per game, last 5", value=2.0,
             unit="pts/game", scope="home_team"),
        Fact(id="HOME_CS_PCT_SEASON", label="Leeds United clean sheets", value=40, unit="%",
             scope="home_team"),
        Fact(id="HOME_GF_PG_SEASON", label="Leeds United goals per game", value=1.75,
             unit="goals/game", scope="home_team"),
        Fact(id="AWAY_PPG_L5", label="Hull City points per game, last 5", value=0.8,
             unit="pts/game", scope="away_team"),
        Fact(id="AWAY_GA_PG_SEASON", label="Hull City conceded per game", value=2.1,
             unit="goals/game", scope="away_team"),
        Fact(id="H2H_MATCH_1", label="Meeting 1", scope="h2h",
             value="2026-01-24, Leeds United 3-1 Hull City, Championship"),
        Fact(id="LEAGUE_GOALS_PG_SEASON", label="Championship goals per game", value=2.83,
             unit="goals/game", scope="league"),
    ]
    menu = [
        MenuLine(id="MENU_H", side="H", label="Leeds United win", p_model=48.9,
                 role="outright", eligible=False, is_call=False),
        MenuLine(id="MENU_12", side="12", label="Either team to win", p_model=74.2,
                 role="fallback", eligible=True, is_call=True),
        MenuLine(id="MENU_A15", side="A+1.5", label="Hull City Away +1.5", p_model=71.4,
                 role="fallback", eligible=True, is_call=False),
    ]
    return EvidencePack(
        fixture_id=1, division="E1", division_name="Championship", match_date="2026-10-03",
        kickoff_time="15:00", home="Leeds United", away="Hull City",
        home_team_id=1, away_team_id=2,
        call=Call(tip_id=1, side="12", label="Either team to win",
                  means="either Leeds United or Hull City must win", model_prob=74.2,
                  floor=55.0, ceiling=85.0, rule_version="confidence-v3"),
        menu=menu, facts=facts, flags=[Flag(code="small_sample", side="away")],
        omitted=[], model_version="m", data_as_of="x")


def home_facts(pack):
    return [f for f in pack.facts if f.scope == "home_team"]


def good_summary(**changes) -> TeamSummary:
    fields = dict(
        narrative=("Leeds United have taken 2.0 points per game across their last five league "
                   "games, winning 3 of them with a form line of WWDLW. They have kept clean "
                   "sheets in 40% of their league games this season and score 1.75 goals per "
                   "game. The record points to a side in good recent form."),
        strengths=["2.0 points per game recently", "Clean sheets in 40% of games"],
        weaknesses=["One defeat in the last 5"],
        trend="improving",
        cited_facts=["HOME_PPG_L5", "HOME_WON_L5", "HOME_FORM_L5", "HOME_CS_PCT_SEASON",
                     "HOME_GF_PG_SEASON"])
    return TeamSummary(**{**fields, **changes})


def good_analysis(**changes) -> MatchAnalysis:
    call = dict(side="12",
                rationale=("No outright cleared the floor: a Leeds United win sits at 48.9%. "
                           "Either team to win is the likeliest eligible market at 74.2%, ahead "
                           "of the Hull City +1.5 at 71.4%."),
                supporting_facts=["MENU_12", "HOME_PPG_L5", "AWAY_GA_PG_SEASON"],
                contradicting_facts=["H2H_MATCH_1"])
    fields = dict(
        preview=("Leeds United arrive with 2.0 points per game from their last 5, while Hull "
                 "City have managed 0.8 and concede 2.1 goals per game. Championship games "
                 "average 2.83 goals, and the last meeting, on 2026-01-24, finished 3-1."),
        call=Pick(**{**call, **changes.pop("call", {})}),
        risk_commentary="Hull City have played few league games this season.")
    return MatchAnalysis(**{**fields, **changes})


# --- number extraction ---------------------------------------------------- #


def test_numbers_are_read_with_their_precision_and_percent_sign():
    found = {n.text: (n.value, n.decimals, n.percent)
             for n in numbers_in("62% vs 0.62, priced 2.10, won 3-1, the +1.5 line")}
    assert found == {"62%": (62.0, 0, True), "0.62": (0.62, 2, False),
                     "2.10": (2.1, 2, False), "3": (3.0, 0, False), "1": (1.0, 0, False),
                     "1.5": (1.5, 1, False)}


def test_codes_and_window_names_are_not_numbers():
    assert numbers_in("the 1X and X2 markets, L5 and L10 windows, O25") == []
    assert [n.value for n in numbers_in("on 2026-01-24.")] == [2026.0, 1.0, 24.0]


def test_rounding_to_the_prose_precision_is_allowed():
    allowed = {76.9, 2.83, 62.0, 2.1, 3.0}
    assert unknown_numbers("77% and 76.9%, 2.8 and 2.83 goals", allowed) == []
    assert unknown_numbers("0.62 is 62%, and 2.10 is 2.1", allowed) == []
    assert unknown_numbers("78% and 2.9", allowed) == ["78%", "2.9"]


def test_a_whole_number_must_be_a_whole_value():
    # 2.83 goals cannot be written "3 goals" -- but a count of 3 can be.
    assert unknown_numbers("3 goals a game", {2.83}) == ["3"]
    assert unknown_numbers("won 3", {3}) == []


# --- the team summary ----------------------------------------------------- #


def test_a_good_summary_passes():
    summary = good_summary()
    words = len(summary.narrative.split())                  # short: a warning only
    assert check_summary(summary, home_facts(make_pack())) == ([], [
        f"narrative: {words} words, outside 80-120"])


def test_summary_citations_must_exist_and_be_this_teams():
    errors, _ = check_summary(good_summary(cited_facts=["HOME_PPG_L5", "AWAY_PPG_L5"]),
                              home_facts(make_pack()))
    assert errors == ["cited_facts: unknown id AWAY_PPG_L5"]
    errors, _ = check_summary(good_summary(cited_facts=[]), home_facts(make_pack()))
    assert errors == ["cited_facts: empty; every statement must cite a fact"]


def test_summary_limits_points_to_three():
    errors, _ = check_summary(good_summary(strengths=["Wins", "Draws", "Goals", "Form"]),
                              home_facts(make_pack()))
    assert errors == ["strengths: 4 items, at most 3"]


def test_summary_numbers_must_be_in_its_own_facts():
    narrative = good_summary().narrative + " They win 64% of home games."
    errors, _ = check_summary(good_summary(narrative=narrative), home_facts(make_pack()))
    assert errors == ["narrative: the number 64% is not in the evidence"]
    # Hull's 0.8 is in the pack but not in Leeds's facts.
    errors, _ = check_summary(good_summary(weaknesses=["Rivals took 0.8 points a game"]),
                              home_facts(make_pack()))
    assert errors == ["weaknesses[0]: the number 0.8 is not in the evidence"]


def test_summary_banned_phrases_any_case_and_apostrophe():
    errors, _ = check_summary(good_summary(strengths=["A BANKER at home",
                                                      "They can’t lose here"]),
                              home_facts(make_pack()))
    assert errors == ["strengths[0]: banned phrase 'banker'",
                      "strengths[1]: banned phrase 'can’t lose'"]
    # A banned word inside another word is not a match.
    assert check_summary(good_summary(weaknesses=["Deadlocked in the last 5"]),
                         home_facts(make_pack()))[0] == []


# --- the match analysis --------------------------------------------------- #


def test_a_good_analysis_passes_with_word_count_warnings_only():
    analysis = good_analysis()
    errors, warnings = check_analysis(analysis, make_pack())
    assert errors == []
    assert warnings == [
        f"preview: {len(analysis.preview.split())} words, outside 120-180",
        f"call.rationale: {len(analysis.call.rationale.split())} words, outside 40-80"]


def test_the_analysis_must_explain_the_published_call():
    errors, _ = check_analysis(good_analysis(call={"side": "A+1.5"}), make_pack())
    assert errors == ["call.side: A+1.5 is not the published call 12"]


def test_analysis_citations_may_be_facts_or_menu_lines_and_must_exist():
    errors, _ = check_analysis(
        good_analysis(call={"supporting_facts": ["MENU_12", "HOME_XG_L5"],
                            "contradicting_facts": ["H2H_MATCH_9"]}), make_pack())
    assert errors == ["call.supporting_facts: unknown id HOME_XG_L5",
                      "call.contradicting_facts: unknown id H2H_MATCH_9"]
    errors, _ = check_analysis(good_analysis(call={"supporting_facts": []}), make_pack())
    assert errors == ["call.supporting_facts: empty; the explanation must cite its evidence"]


def test_analysis_numbers_include_the_call_and_menu_and_nothing_else():
    ok = good_analysis(risk_commentary="The floor is 55% and the ceiling 85%; the 2.5 line "
                                       "and the last 5 are standing terms.")
    assert check_analysis(ok, make_pack())[0] == []
    bad = good_analysis(risk_commentary="Hull win 31% of away games.")
    assert check_analysis(bad, make_pack())[0] == [
        "risk_commentary: the number 31% is not in the evidence"]


def test_analysis_may_not_talk_prices():
    bad = good_analysis(preview=good_analysis().preview + " The odds look generous.")
    assert check_analysis(bad, make_pack())[0] == ["preview: banned phrase 'odds'"]
