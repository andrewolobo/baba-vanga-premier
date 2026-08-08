"""The fbref fixture scraper.

Nothing here touches the network. The parser runs against a real fbref date
page saved during the probe (2026-08-08, gzipped because it is a megabyte of
HTML), so the assertions are about what fbref actually publishes rather than
about a mock of it. Everything the live path adds -- Cloudflare, throttling,
the cache -- is deliberately untested here: it is I/O, and the parser is where
the fixtures can go quietly wrong.
"""

from __future__ import annotations

import csv
import gzip
import json
from pathlib import Path

import pytest

# The scraper's dependencies are the `scrape` extra, which a serving install
# deliberately does not have: it pulls patchright, which downloads a full
# Chrome onto the host. The scraper is also SHELVED by owner decision and must
# not be enabled without a recorded one (OUTSTANDING.md 4.1), so a serving VM
# having no bs4 is the correct state rather than a missing step.
#
# Without this the module raises ModuleNotFoundError at import, which pytest
# reports as a COLLECTION error -- the entire suite refuses to run, so the
# deployment's acceptance gate cannot report on the 415 tests that have
# nothing to do with the scraper. Skipping is what makes those still count.
# BOTH names, because the module needs both and they fail at different moments.
# `bs4` missing is an ImportError at collection. `lxml` missing is not: bs4
# imports fine, `BeautifulSoup(html, "lxml")` then raises FeatureNotFound at
# CALL time, so gating on bs4 alone let 13 of these through to fail and error
# on a host that simply did not have the extra. Skipping on one name is a claim
# about imports; the module's real precondition is the `scrape` extra, and that
# is two packages.
_SCRAPE = "fbref scraper tests need the `scrape` extra (pip install -e '.[scrape]')"
pytest.importorskip("bs4", reason=_SCRAPE)
pytest.importorskip("lxml", reason=_SCRAPE)

from services.fbref_scraper import cli, config, parse  # noqa: E402

PAGE = Path(__file__).parent / "data" / "fbref_2026-08-08.html.gz"
DATE = "2026-08-08"

NATIONAL_LEAGUE = 34
EFL_CUP = 690


@pytest.fixture(scope="module")
def fixtures() -> list[parse.Fixture]:
    """Every fixture on the saved page: 51 competitions, worldwide."""
    with gzip.open(PAGE, "rt", encoding="utf-8") as handle:
        return parse.parse_date_page(handle.read(), DATE)


def only(fixtures, comp_id) -> list[parse.Fixture]:
    return [f for f in fixtures if f.comp_id == comp_id]


# --- parsing the real page -------------------------------------------------


def test_a_date_page_carries_every_competition_worldwide(fixtures):
    """The reason one request per date is enough: 51 leagues arrive together."""
    assert len({f.comp_id for f in fixtures}) == 51
    assert len(fixtures) == 407


def test_national_league_fixtures_are_read_off_the_saved_page(fixtures):
    rows = only(fixtures, NATIONAL_LEAGUE)
    assert len(rows) == 12
    first = rows[0]
    assert (first.home, first.away) == ("Boston United", "Aldershot Town")
    assert first.venue == "The Jakemans Stadium"
    assert first.kickoff_local == "15:00"
    assert first.date == DATE
    assert first.season == "2026-2027"
    assert first.comp_name == "National League"
    assert first.week == 1


def test_a_cup_table_has_no_matchweek_column_and_a_named_round(fixtures):
    """Cup tables drop the Wk column entirely, which is why cells are read by
    `data-stat` and not by position: counting columns would shift every field
    after Round by one on these tables."""
    rows = only(fixtures, EFL_CUP)
    assert len(rows) == 28
    first = rows[0]
    assert (first.home, first.away) == ("Cambridge", "Barnet")
    assert first.round == "First round"
    assert first.week is None
    assert first.comp_name == "EFL Cup"


def test_an_unplayed_fixture_has_no_goals(fixtures):
    """Every game on this date is in the future, so a goal count anywhere would
    mean an empty score cell had been read as a 0-0."""
    assert all(f.home_goals is None and f.away_goals is None for f in fixtures)


def test_a_fixture_links_to_its_match_page(fixtures):
    assert only(fixtures, NATIONAL_LEAGUE)[0].match_url.startswith("https://fbref.com/en/")


def test_the_competition_allowlist_keeps_only_those_ids():
    with gzip.open(PAGE, "rt", encoding="utf-8") as handle:
        rows = parse.parse_date_page(handle.read(), DATE, (NATIONAL_LEAGUE, EFL_CUP))
    assert len(rows) == 40
    assert {f.comp_id for f in rows} == {NATIONAL_LEAGUE, EFL_CUP}


# --- score parsing ---------------------------------------------------------
#
# No game on the probe date had been played, so the played-game shapes are
# exercised against a hand-built table carrying the two forms fbref publishes.


def table(score: str) -> str:
    return f"""
    <table class="stats_table" id="sched_2026-2027_34">
      <caption><a href="/en/comps/34/x">National League</a> Table</caption>
      <tbody><tr>
        <th data-stat="round">National League</th>
        <td data-stat="home_team"><a href="/x">Boston United</a></td>
        <td data-stat="score">{score}</td>
        <td data-stat="away_team"><a href="/y">Aldershot Town</a></td>
      </tr></tbody>
    </table>"""


@pytest.mark.parametrize("score, expected", [
    ("2–1", (2, 1)),
    ("0–0", (0, 0)),
    ("", (None, None)),
    # A shootout is not a goal: 1-1 after 90 minutes, won 4-3 on penalties.
    ("1 (4)–1 (3)", (1, 1)),
])
def test_scores_are_read_without_counting_penalty_shootouts(score, expected):
    row = parse.parse_date_page(table(score), DATE)[0]
    assert (row.home_goals, row.away_goals) == expected


def test_a_row_without_clubs_is_skipped():
    """fbref pads some tables with blank rows; a fixture with no teams is not
    a fixture."""
    assert parse.parse_date_page(table("").replace("Boston United", ""), DATE) == []


# --- configuration ---------------------------------------------------------


def test_defaults_apply_when_nothing_is_given():
    settings = config.load()
    assert settings.comps == ()
    assert settings.format == "csv"
    assert settings.min_interval == 6.0


def test_a_toml_file_overrides_the_defaults(tmp_path):
    path = tmp_path / "s.toml"
    path.write_text('comps = [9, 34]\nformat = "jsonl"\nmin_interval = 12.0\n',
                    encoding="utf-8")
    settings = config.load(path)
    assert settings.comps == (9, 34)
    assert settings.format == "jsonl"
    assert isinstance(settings.cache_dir, Path)


def test_a_cli_flag_beats_the_toml_file(tmp_path):
    """The point of the file is a standing default; the point of the flag is
    to depart from it for one run without editing anything."""
    path = tmp_path / "s.toml"
    path.write_text('comps = [9, 34]\nformat = "jsonl"\n', encoding="utf-8")
    settings = cli.settings(["--config", str(path), "--from", DATE,
                             "--comps", "34,690", "--format", "csv",
                             "--out", "x/y.csv"])
    assert settings.comps == (34, 690)
    assert settings.format == "csv"
    assert settings.out == Path("x/y.csv")
    assert settings.date_from == DATE


def test_flags_that_are_not_passed_leave_the_file_alone(tmp_path):
    path = tmp_path / "s.toml"
    path.write_text("min_interval = 12.0\nretries = 3\n", encoding="utf-8")
    settings = cli.settings(["--from", DATE, "--config", str(path)])
    assert (settings.min_interval, settings.retries) == (12.0, 3)
    assert settings.headless is False


def test_an_unknown_setting_is_refused_rather_than_ignored(tmp_path):
    """A typo in the file must not silently mean 'no throttle'."""
    path = tmp_path / "s.toml"
    path.write_text("min_intervals = 0.0\n", encoding="utf-8")
    with pytest.raises(ValueError, match="min_intervals"):
        config.load(path)


def test_an_unsupported_output_format_is_refused():
    with pytest.raises(ValueError, match="csv or jsonl"):
        config.load(format="parquet")


# --- date range and output -------------------------------------------------


def test_a_range_expands_to_every_date_inclusive():
    assert cli.dates(config.load(date_from="2026-08-08", date_to="2026-08-10")) == [
        "2026-08-08", "2026-08-09", "2026-08-10"]


def test_one_date_needs_only_a_start():
    assert cli.dates(config.load(date_from=DATE)) == [DATE]


def test_a_backwards_range_is_refused():
    with pytest.raises(ValueError, match="before"):
        cli.dates(config.load(date_from="2026-08-10", date_to="2026-08-08"))


def test_csv_output_carries_every_fixture_field(fixtures, tmp_path):
    path = tmp_path / "out.csv"
    cli.write(only(fixtures, NATIONAL_LEAGUE), path, "csv")
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    assert len(rows) == 12
    assert list(rows[0]) == list(cli.COLUMNS)
    assert rows[0]["home"] == "Boston United"
    assert rows[0]["home_goals"] == ""


def test_jsonl_output_keeps_nulls_as_nulls(fixtures, tmp_path):
    path = tmp_path / "out.jsonl"
    cli.write(only(fixtures, EFL_CUP), path, "jsonl")
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 28
    assert rows[0]["home_goals"] is None
    assert rows[0]["week"] is None
