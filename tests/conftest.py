"""Offline fixtures reproducing the source quirks found by the data audits.

Nothing here reads the real corpus: the suite must pass on a clean checkout
with no data present. Each builder deliberately embeds the defects the loaders
claim to handle, so that a regression in the handling shows up as a test
failure rather than as a quiet change in the numbers.
"""

from __future__ import annotations

import pytest

from engine import db
from engine.ingest.teams import FBREF, FOOTBALL_DATA, TeamBridge

# Header of the Betbrain era (2010-11..2018-19): no Time, no market Avg/Max.
BETBRAIN_HEADER = (
    "Div,Date,HomeTeam,AwayTeam,FTHG,FTAG,FTR,HTHG,HTAG,HTR,Referee,"
    "HS,AS,HST,AST,HF,AF,HC,AC,HY,AY,HR,AR,"
    "B365H,B365D,B365A,PSH,PSD,PSA,"
    "BbMxH,BbAvH,BbMxD,BbAvD,BbMxA,BbAvA,"
    "BbMx>2.5,BbAv>2.5,BbMx<2.5,BbAv<2.5,BbAHh,BbAvAHH,BbAvAHA,PSCH,PSCD,PSCA"
)

# Market era (2019-20..): Time present, closing prices for everything.
MARKET_HEADER = (
    "Div,Date,Time,HomeTeam,AwayTeam,FTHG,FTAG,FTR,HTHG,HTAG,HTR,Referee,"
    "HS,AS,HST,AST,HF,AF,HC,AC,HY,AY,HR,AR,"
    "B365H,B365D,B365A,PSH,PSD,PSA,MaxH,MaxD,MaxA,AvgH,AvgD,AvgA,"
    "Max>2.5,Max<2.5,Avg>2.5,Avg<2.5,AHh,AvgAHH,AvgAHA,"
    "PSCH,PSCD,PSCA,B365CH,B365CD,B365CA,MaxCH,MaxCD,MaxCA,AvgCH,AvgCD,AvgCA,"
    "AvgC>2.5,AvgC<2.5,AHCh,AvgCAHH,AvgCAHA"
)


@pytest.fixture
def bridge(tmp_path):
    """A small bridge carrying the real traps: a two-alias club and a near-miss pair."""
    path = tmp_path / "team_aliases.csv"
    rows = [
        ("canonical_name", "source", "alias"),
        # football-data writes two names for one club (the Telford case).
        ("Telford United", FOOTBALL_DATA, "Telford United"),
        ("Telford United", FOOTBALL_DATA, "AFC Telford United"),
        ("Telford United", FBREF, "Telford United"),
        # fbref writes two names for one club (the Torquay case).
        ("Torquay", FOOTBALL_DATA, "Torquay"),
        ("Torquay", FBREF, "Torquay"),
        ("Torquay", FBREF, "Torquay United"),
        # Two clubs that must never be merged.
        ("Oxford", FOOTBALL_DATA, "Oxford"),
        ("Oxford", FBREF, "Oxford United"),
        ("Oxford City", FOOTBALL_DATA, "Oxford City"),
        ("Oxford City", FBREF, "Oxford City FC"),
        # Ordinary clubs used by the loader fixtures.
        ("Man United", FOOTBALL_DATA, "Man United"),
        ("Man United", FBREF, "Manchester Utd"),
        ("Arsenal", FOOTBALL_DATA, "Arsenal"),
        ("Arsenal", FBREF, "Arsenal"),
        ("King's Lynn", FOOTBALL_DATA, "King’s Lynn"),
    ]
    path.write_text(
        "\n".join(",".join(f'"{c}"' for c in row) for row in rows) + "\n",
        encoding="utf-8",
    )
    return TeamBridge.load(path)


@pytest.fixture
def match_dir(tmp_path):
    """A two-season, one-division match tree carrying the source defects."""
    root = tmp_path / "play_history"

    # 2010-11: Betbrain era, dd/mm/yy dates, no Time column, a cp1252 curly
    # apostrophe, and a trailing blank line.
    old = root / "201011"
    old.mkdir(parents=True)
    rows = [
        BETBRAIN_HEADER,
        "E0,14/08/10,Man United,Arsenal,2,1,H,1,0,H,M Dean,"
        "14,9,6,3,11,12,7,4,2,1,0,0,"
        "1.80,3.50,4.50,1.83,3.60,4.60,"
        "1.85,1.79,3.60,3.45,4.70,4.40,"
        "2.00,1.95,1.90,1.85,-0.75,1.95,1.92,1.85,3.55,4.75",
        "E0,21/08/10,Arsenal,King’s Lynn,0,0,D,0,0,D,H Webb,"
        "10,8,4,2,9,10,5,6,1,2,0,0,"
        "2.10,3.30,3.60,2.15,3.35,3.70,"
        "2.20,2.12,3.40,3.28,3.75,3.62,"
        "1.95,1.90,1.95,1.90,-0.25,1.90,1.98,2.12,3.32,3.68",
        # A comma-only row: pandas reads this as a row of empty fields, so the
        # loader has to drop it itself. 24 of these exist in the real corpus.
        "," * (len(BETBRAIN_HEADER.split(",")) - 1),
        "",  # a truly empty trailing line, which pandas skips before we see it
    ]
    (old / "E0.csv").write_bytes("\n".join(rows).encode("cp1252"))

    # 2019-20: market era, dd/mm/yyyy dates, Time present, and a phantom
    # trailing column exactly as in the real 2025-26 E3 file.
    new = root / "201920"
    new.mkdir(parents=True)
    rows = [
        MARKET_HEADER + ",",
        "E0,09/08/2019,20:00,Man United,Arsenal,4,0,H,1,0,H,A Taylor,"
        "18,6,9,2,10,13,8,3,1,3,0,0,"
        "1.55,4.20,6.00,1.58,4.30,6.20,1.60,4.35,6.40,1.56,4.22,6.10,"
        "1.90,2.00,1.85,1.95,-1.25,1.92,1.94,"
        "1.50,4.50,6.50,1.52,4.40,6.30,1.55,4.60,6.80,1.51,4.45,6.40,"
        "1.88,1.98,-1.25,1.90,1.96,",
        "E0,17/08/2019,15:00,Arsenal,Man United,1,1,D,0,1,A,M Oliver,"
        "12,11,5,5,12,11,6,5,2,2,0,1,"
        "2.40,3.40,3.00,2.45,3.45,3.05,2.50,3.50,3.10,2.42,3.42,3.02,"
        "1.85,1.95,1.80,1.90,0.00,1.95,1.90,"
        "2.35,3.50,3.05,2.38,3.48,3.02,2.45,3.55,3.15,2.36,3.46,3.06,"
        "1.83,1.93,0.00,1.93,1.92,",
    ]
    (new / "E0.csv").write_bytes("\n".join(rows).encode("cp1252"))
    return root


@pytest.fixture
def player_dir(tmp_path):
    """A player tree with a three-line preamble, a .txt division, and bad ids."""
    root = tmp_path / "player-stats"
    root.mkdir()

    header = (
        "Rk,Player,Nation,Pos,Squad,Age,Born,MP,Starts,Min,90s,"
        "Gls,Ast,G+A,G-PK,PK,PKatt,CrdY,CrdR,Gls,Ast,G+A,G-PK,G+A-PK,Matches,-9999"
    )
    band = ",,,,,,,Playing Time,,,,Performance,,,,,,,,Per 90 Minutes,,,,,,"

    # E0 lives at the root. Note the thousands separator in Min, a leading-zero
    # id, a scientific-notation id, and one player at two clubs.
    rows = [
        band,
        header,
        '1,Alpha Player,eng ENG,MF,Arsenal,24,2001,38,38,"3,420",38.0,'
        "5,4,9,5,0,0,3,0,0.13,0.11,0.24,0.13,0.24,Matches,aaaaaaaa",
        "2,Beta Player,eng ENG,DF,Manchester Utd,29,1996,20,18,1620,18.0,"
        "1,1,2,1,0,0,5,1,0.06,0.06,0.11,0.06,0.11,Matches,1226327",
        "3,Gamma Player,fr FRA,FW,Arsenal,31,1994,10,5,540,6.0,"
        "3,0,3,2,1,1,1,0,0.50,0.00,0.50,0.33,0.50,Matches,5.26E+05",
        # Same player, two clubs: one mid-season transfer, one shared id.
        "4,Delta Player,eng ENG,FW,Arsenal,26,1999,15,12,1080,12.0,"
        "6,2,8,6,0,0,2,0,0.50,0.17,0.67,0.50,0.67,Matches,dddddddd",
        "5,Delta Player,eng ENG,FW,Manchester Utd,26,1999,18,16,1440,16.0,"
        "7,1,8,7,0,0,1,0,0.44,0.06,0.50,0.44,0.50,Matches,dddddddd",
    ]
    (root / "201011.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")

    # E2 is a .txt file AND carries the three-line preamble (a single space on
    # the first line) seen in efl-league-one/201112.txt.
    league_one = root / "efl-league-one"
    league_one.mkdir()
    rows = [
        " ",
        band,
        header,
        "1,Slug Player,,,Torquay United,,,30,28,2520,28.0,"
        "4,3,7,4,0,0,6,0,0.14,0.11,0.25,0.14,0.25,Matches,Slug-Player",
        "2,Hex Player,eng ENG,MF,Torquay United,22,2003,25,20,1800,20.0,"
        "2,5,7,2,0,0,4,0,0.10,0.25,0.35,0.10,0.35,Matches,bbbbbbbb",
    ]
    (league_one / "201011.txt").write_text("\n".join(rows) + "\n", encoding="utf-8")
    return root


@pytest.fixture
def conn(tmp_path):
    """A migrated, empty database."""
    connection = db.connect(tmp_path / "test.db")
    db.migrate(connection)
    yield connection
    connection.close()
