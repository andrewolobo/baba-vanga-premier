"""Loaders, against fixtures carrying every defect the audits found in the real
files. Each test names the defect it pins down.
"""

from __future__ import annotations

import pandas as pd
import pytest

from engine.ingest import matches as matches_mod, players as players_mod
from engine.ingest.holdout import Purpose
from engine.ingest.players import KIND_CORRUPT, KIND_HEX, KIND_SLUG, classify_id


# --- matches --------------------------------------------------------------


@pytest.fixture
def loaded(match_dir, bridge):
    corpus, report = matches_mod.load(
        purpose=Purpose.DEV,
        seasons=("201011", "201920"),
        divisions=("E0",),
        bridge=bridge,
        match_dir=match_dir,
    )
    return corpus.frame, report


def test_cp1252_encoding(loaded):
    """The files are cp1252, not UTF-8: King's Lynn carries a 0x92 curly
    apostrophe that raises under UTF-8."""
    frame, _ = loaded
    assert len(frame) == 4
    assert "King's Lynn" in set(frame["away_team"])


def test_comma_only_rows_are_dropped(loaded):
    """A row of empty fields reads as a row, not as whitespace; the real corpus
    holds 24 of them and they would otherwise become matches with no teams."""
    frame, report = loaded
    assert report.dropped_blank == 1
    assert frame["home_team"].notna().all()
    assert frame["match_date"].notna().all()


def test_both_date_formats_parse_day_first(loaded):
    """dd/mm/yy early, dd/mm/yyyy later, and never month-first: 14/08/10 is
    14 August, not a parse error or 8 October."""
    frame, _ = loaded
    dates = sorted(frame["match_date"])
    assert dates[0] == pd.Timestamp("2010-08-14")
    assert dates[-1] == pd.Timestamp("2019-08-17")


def test_kickoff_time_absent_before_2019_20(loaded):
    frame, _ = loaded
    old = frame[frame["season"] == "201011"]
    new = frame[frame["season"] == "201920"]
    assert old["kickoff_time"].isna().all()
    assert set(new["kickoff_time"]) == {"20:00", "15:00"}


def test_odds_eras_land_in_the_same_fields(loaded):
    """A Betbrain row and a market row both populate avg_h, so downstream code
    never branches on era."""
    frame, _ = loaded
    old = frame[frame["season"] == "201011"].iloc[0]
    new = frame[frame["season"] == "201920"].iloc[0]
    assert old["odds_era"] == "betbrain" and new["odds_era"] == "market"
    assert old["avg_h"] == pytest.approx(1.79)
    assert new["avg_h"] == pytest.approx(1.56)


def test_phantom_trailing_column_is_ignored(loaded):
    """2025-26 E3 has one more header field than columns; selecting by name
    rather than position makes it a non-event."""
    frame, _ = loaded
    new = frame[frame["season"] == "201920"]
    assert new["close_avg_ah_a"].notna().all()


def test_closing_odds_only_where_the_source_has_them(loaded):
    frame, _ = loaded
    old = frame[frame["season"] == "201011"].iloc[0]
    new = frame[frame["season"] == "201920"].iloc[0]
    assert pd.notna(old["close_ps_h"])       # Pinnacle closing reaches back to 2012-13
    assert pd.isna(old["close_avg_h"])       # market closing starts 2019-20
    assert pd.notna(new["close_avg_h"])


def test_match_ids_are_deterministic(loaded):
    frame, _ = loaded
    assert frame["match_id"].is_unique
    assert "201011:E0:2010-08-14:Man United:Arsenal" in set(frame["match_id"])


def test_unbridged_teams_are_excluded_by_name_and_counted(match_dir, bridge, tmp_path):
    """SPEC §0.2: never a silent drop."""
    rogue = match_dir / "201011" / "E0.csv"
    text = rogue.read_bytes().decode("cp1252")
    text += text.splitlines()[1].replace("Man United", "Nowhere Town") + "\n"
    rogue.write_bytes(text.encode("cp1252"))

    _, report = matches_mod.load(
        purpose=Purpose.DEV, seasons=("201011",), divisions=("E0",),
        bridge=bridge, match_dir=match_dir,
    )
    assert report.dropped_unbridged == 1
    assert not report.bridge.clean
    assert "Nowhere Town" in report.bridge.describe()


def test_loader_honours_the_seal(match_dir, bridge):
    from engine.ingest.holdout import HoldoutViolation

    with pytest.raises(HoldoutViolation):
        matches_mod.load(
            purpose=Purpose.DEV, seasons=("202526",), bridge=bridge, match_dir=match_dir
        )


# --- player ids -----------------------------------------------------------


def test_leading_zero_ids_are_recovered():
    """The Championship carries leading-zero ids in 14 of 16 files. Numeric
    coercion drops the zero and forks one player into two entities."""
    assert classify_id("1226327") == ("01226327", KIND_HEX)
    assert classify_id("44781702") == ("44781702", KIND_HEX)


def test_scientific_notation_ids_are_flagged_not_guessed():
    """Excel rendered one id as 5.26E+05; the digits are gone and cannot be
    reconstructed, so it is marked rather than silently repaired."""
    assert classify_id("5.26E+05")[1] == KIND_CORRUPT


def test_name_slugs_are_flagged():
    """National League ids before 2018-19 are name slugs. They collide on common
    names and are not stable identities."""
    assert classify_id("Aaron-Farrell") == ("Aaron-Farrell", KIND_SLUG)


# --- players --------------------------------------------------------------


@pytest.fixture
def players(player_dir, bridge):
    corpus, report = players_mod.load(
        purpose=Purpose.DEV, seasons=("201011",), divisions=("E0", "E2"),
        bridge=bridge, player_dir=player_dir,
    )
    return corpus.frame, report


def test_txt_extension_and_three_line_preamble(players):
    """League One files are .txt -- a *.csv glob drops the whole tier -- and two
    files carry an extra preamble line, so the header is found by scanning."""
    frame, report = players
    assert report.files == 2
    assert set(frame["division"]) == {"E0", "E2"}
    assert len(frame[frame["division"] == "E2"]) == 2


def test_thousands_separator_in_minutes(players):
    """FBref writes Min as "3,420"."""
    frame, _ = players
    alpha = frame[frame["player_name"] == "Alpha Player"].iloc[0]
    assert alpha["minutes"] == 3420
    assert alpha["nineties"] == pytest.approx(38.0)


def test_transfer_split_rows_share_one_id(players):
    """A mid-season transfer is two rows, one id. Grouping by name would merge
    genuine namesakes; grouping by id is the only safe aggregation."""
    frame, _ = players
    delta = frame[frame["player_name"] == "Delta Player"]
    assert len(delta) == 2
    assert delta["player_id"].nunique() == 1
    assert set(delta["team"]) == {"Arsenal", "Man United"}
    assert delta["minutes"].sum() == 2520


def test_id_kinds_are_recorded(players):
    frame, report = players
    kinds = dict(frame["player_id_kind"].value_counts())
    assert kinds[KIND_HEX] == 5
    assert kinds[KIND_SLUG] == 1
    assert kinds[KIND_CORRUPT] == 1
    assert report.slug_ids == 1 and report.corrupt_ids == 1


def test_squads_bridge_to_canonical_clubs(players):
    frame, report = players
    assert report.bridge.clean
    assert set(frame["team"]) == {"Arsenal", "Man United", "Torquay"}
