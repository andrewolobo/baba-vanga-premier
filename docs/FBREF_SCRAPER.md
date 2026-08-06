# FBref fixture scraper — probe results and implementation plan

Probed **2026-08-03** against `https://fbref.com/en/matches/2026-08-08`.
Relates to Track A fixture sync (`OUTSTANDING.md` §4.1) but is a standalone
evaluation; it does not replace the football-data.org path until decided.

> **SHELVED, AND ITS MAIN USE CASE IS CLOSED — read this before §1.**
>
> The scraper is built, tested and working. **It is not wired into serving and
> must not be enabled without a recorded decision** (`OUTSTANDING.md` §4.1,
> owner decision 2026-08-04). Two reasons beyond the decision itself: it needs a
> *headed* browser on a live desktop to refresh the Cloudflare session, which
> does not compose with an unattended scheduled cycle; and it carries **no
> odds**, so `fixture_sync` is still required for the CLV feed either way.
>
> **The xG route it was expected to open does not exist** (`OUTSTANDING.md`
> §1.8, `CHANNELS.md` §7, verified 2026-08-06). Date pages carry no xG column
> for any of 60 competitions, and neither does the Premier League comp-season
> schedule page for 2022-23 or the current season — zero `xg` data-stats in
> 628 KB, HTML comments included. `P4_CHANNELS_PREGATE.md` §7 predicted xG lived
> on comp-season pages and estimated a 52-request backfill; **that prediction was
> refuted.** The remaining route is per-match report pages: ~26,000 requests
> against a 10 req/min policy, roughly 43 hours of continuous scraping.
>
> **A further operational finding:** the session does not survive two days
> unattended. The one minted 2026-08-04 was refused on first use on 2026-08-06,
> which is a third independent reason it does not fit an unattended cycle.
>
> §1–§6 below are the original probe and are left unedited — the architecture
> and rate-limit findings remain accurate and would be the starting point if
> this is ever revived.

## 1. Probe findings

| route                                        | result                                        |
| -------------------------------------------- | --------------------------------------------- |
| plain `curl` / `requests`                    | **403** — Cloudflare *managed* JS challenge   |
| `curl_cffi` (Chrome TLS impersonation) alone | **403**                                       |
| WebFetch                                     | **403**                                       |
| Playwright, vanilla (headless or headed)     | challenge never clears (CDP detected)         |
| **patchright, headed, persistent profile**   | **PASS** — challenge clears in seconds        |
| `curl_cffi` + captured `cf_clearance` cookie | **200**, full page, on a *different* date URL |

Page structure (from the saved probe page): one page per calendar date carries
**every competition worldwide** — 51 `table.stats_table` elements on 2026-08-08,
each with id `sched_<season>_<comp_id>` (e.g. `sched_2026-2027_34` = National
League, `sched_2026-2027_690` = EFL Cup, calendar-year comps use
`sched_2026_939`). Rows carry round/week, kickoff time (venue-local + viewer),
home, away, score when played, venue, and a match-report/head-to-head link.
Premier League is comp id **9**; it appears on a date page only when fixtures
exist for that date.

**Verdict: feasible.** One request fetches all leagues for a date; a full week
of fixtures costs 7 requests.

## 2. Architecture

Two-tier session model:

1. **Session acquisition (rare):** patchright + real Chrome, *headed*, with a
   persistent profile dir. Loads any fbref URL, waits for the challenge to
   clear, exports cookie jar + exact user agent to a session file.
2. **Scraping (all real work):** `curl_cffi` with `impersonate="chrome"`, the
   saved cookies and the *matching* UA string. On a 403 or challenge-shaped
   response, re-run step 1 once and retry.

Constraints honoured by design:

- **Rate limit:** Sports Reference's bot policy allows roughly 10 req/min and
  blocks violators for ~24 h. Default throttle: ≥6 s between requests plus
  jitter, no concurrency, hard-fail rather than hammer on repeated 403.
- **Cache:** raw HTML saved per date under `data/fbref/raw/`; re-parses never
  re-fetch. A date in the past never changes once all its games are graded.
- **Headed browser dependency:** session refresh needs a desktop session. The
  cookie survives across dates and (observed) at least tens of minutes;
  refreshes are occasional, not per-run.

## 3. Layout

```
services/fbref_scraper/
  __init__.py
  config.py      # ScraperConfig dataclass + TOML loader (see §4)
  session.py     # acquire/load/refresh Cloudflare session
  fetch.py       # throttled curl_cffi GET with cache + 403→refresh→retry
  parse.py       # date page HTML → list[Fixture]; pure, no network
  cli.py         # python -m services.fbref_scraper ...
tests/test_fbref_scraper.py   # parser tests against a saved HTML fixture page
```

`Fixture` fields: `date, season, comp_id, comp_name, round, week, kickoff_local,
home, away, home_goals, away_goals, venue, match_url`. Unplayed games have null
goals.

## 4. Configurability

`ScraperConfig` (TOML file + CLI overrides): date range, competition allowlist
by comp id (empty = all), output path and format (`csv` | `jsonl`), raw-cache
dir, profile dir, session file, min request interval, retry count, headless
attempt toggle. Defaults live in code; a checked-in `fbref_scraper.toml`
example carries the E0–EC + cups ids.

## 5. Out of scope (deliberate)

- No DB writes — output is CSV/JSONL. Wiring into `services/fixture_sync.py`
  is a separate decision once the source is trusted.
- No match-report/stats scraping — schedule tables only.
- No proxy rotation, no challenge "solving" beyond a real browser doing what a
  real browser does, and no attempt to exceed the published rate limit.

## 6. Verification

1. Parser tests pass against the saved probe page (51 tables, known counts for
   National League = 12 rows and EFL Cup = 28 rows on 2026-08-08).
2. Live smoke: one fetch of one date using the cached session, ≤2 requests
   total, producing a CSV with the National League and EFL Cup fixtures.
