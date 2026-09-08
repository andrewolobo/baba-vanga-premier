# BETPAWA_PLAN — a "bet this on betPawa" button on every call

Written **2026-09-08**, assessment only; nothing here is built. Owner
request: on each fixture's published call, a button that takes the user to
betPawa with that wager selected; the same for a parlay; gated behind
sign-in (a paid feature later) and behind location (the countries betPawa
serves); a betPawa scrape of today's games to drive it. The material the
owner supplied is in `docs/bp/` (two browser-captured curls, a July
protobuf capture, a gtleagues sample). This file records what the
investigation found, what in the repo it collides with, the decisions the
owner has to take, and the build that follows from them.

Reading order for a thread picking this up: `STATE.md` → this file →
`AUTH_PLAN.md` §10 (the gate hook) → `services/bbc_calendar.py` (the
bridge-by-identifier pattern this copies) → `engine/serve/parlay.py` (what
a parlay leg is).

---

## 0. Verdict, in one paragraph

**Feasible, about three days, no measurement.** betPawa's sportsbook API
answers plain JSON when asked for it, one request lists every upcoming
Premier League / Championship / League One / League Two event with the
three markets the rule publishes on (1X2, Double Chance, Asian Handicap),
and a public URL on every betPawa country site pre-fills the betslip from
selection ids — **verified headless today for a single (Swansea +1.5) and
for a three-event slip**. Selection ids are identical across the country
brands, so one scrape serves all of them. Every one of the 92 E0–E3 clubs
appeared in today's pull and 88 bridge to our names automatically. The
two things that cannot be verified from here: whether betPawa answers
from the Azure VM's egress (this probe ran from a Ugandan address), and
whether the owner has a partner/affiliate agreement that dictates the
link format (§3 D10).

## 1. What was found

Everything below was observed live on 2026-09-08 against `www.betpawa.ug`
and `www.betpawa.co.ke`; the raw responses are saved as
`docs/bp/fixtures/betpawa_efl_upcoming_2026-09-08.json` (65 events, three
markets each) and `docs/bp/fixtures/betpawa_event_37536526_2026-09-08.json`
(one event, all 113 market groups), for tests.

### 1.1 The API speaks JSON, and needs one header

The owner's captures ask for `application/x-protobuf` (the July fixtures
are protobuf bytes). The same endpoints answer JSON with
`Accept: application/json`. The minimal request:

```
GET https://www.betpawa.ug/api/sportsbook/v4/events/lists/by-queries?q=<url-encoded JSON>
    X-Pawa-Brand: betpawa-uganda        (required: 400 without it)
    Accept: application/json
```

with `q`:

```json
{"queries":[{"query":{"eventType":"UPCOMING","categories":["2"],
  "zones":{"competitions":["11965","12101","12317","12192"]},"hasOdds":true},
  "view":{"marketTypes":["3743","4693","3774"]},"skip":0,"take":100}]}
```

- `categories: ["2"]` is Football; the four competition ids are, in order,
  **Premier League 11965, Championship 12101, League One 12317, League Two
  12192** (region 288, England) — read back from the response, not assumed.
- `take` is capped at **100** (400 with `serverMessage: "The maximum number
  of events is 100"`); `skip` pages. Today the four leagues had **65**
  upcoming events (6 tonight, 40 on Saturday, the rest to 20 Sep), so one
  page covers a fortnight.
- `view.marketTypes` restricts the markets in the list response to the ones
  named. With the three above, every one of the 65 events came back with
  all three markets. `GET /api/sportsbook/v4/events/{id}` returns the whole
  event (113 market groups, ~440 KB) and is not needed.
- None of the fingerprint, sentry, trace or device headers in the captures
  are needed. No cookie, no login.
- Response shape per event: `id`, `name` ("Southampton FC - Swansea
  City"), `participants[{id, name, position}]`, `startTime` (UTC ISO),
  `competition{id,name}`, `markets[{marketType{id,name}, row[{specifier,
  prices[{id, name, typeId, odds, handicap}]}]}]`. The `prices[].id` is the
  **selection id** the whole feature turns on.

### 1.2 The rule's sides map exactly onto three betPawa markets

| `tips.side` | betPawa market | row | price `name` | settlement |
| --- | --- | --- | --- | --- |
| `H` / `D` / `A` | 3743 "1X2 - FT" | the one row | `1` / `X` / `2` | identical |
| `1X` / `X2` / `12` | 4693 "Double Chance - FT" | the one row | `1X` / `X2` / `12` | identical |
| `H+1.5` | 3774 "Asian Handicap - FT" | `specifier.hcp == "1.5"` | `1` (shown "+1.5") | identical — a half line has no push; wins unless home loses by 2+, which is `callMeans` |
| `A+1.5` | 3774 "Asian Handicap - FT" | `specifier.hcp == "-1.5"` | `2` (shown "+1.5") | identical |

Note the Asian Handicap row's `hcp` is stated from the home side: the away
+1.5 sits on the `-1.5` row. "Handicap 1X2" (4724) is the three-way
European handicap on whole goals and is **not** the same market.

**The +1.5 line is not guaranteed for our side.** The ladder is one-sided:
today 64 of 65 events carried +1.5 for the *market* underdog; Gillingham v
Tranmere (2.61 / 2.61) carried +1.5 on the home side only. The rule's
handicap is the **model** underdog (`engine/serve/tips.py`: model
favourite home ⇒ away gets the start), so where the model and the market
disagree on the favourite the line for our side may be absent. That is a
per-fixture "no wager link" state the build has to represent (§3 D11). It happened on the first live run: the rule called
Wrexham +1.5 against Burnley on 2026-09-08 while the market priced Wrexham
as favourite, so the only +1.5 on the book was Burnley's.

### 1.3 The deep link — verified

The site is a Next.js app; its route table carries **`/external-prefill`**,
a page whose only job is to read `?selectionIds=` (comma-separated
selection ids; ids joined with `_` are a same-event combo), POST them to
`/api/sportsbook/v3/prices/list`, add them to the betslip, redirect to the
home page and open the betslip panel. Verified in headless Chromium today:

```
https://www.betpawa.ug/external-prefill?selectionIds=1539591711
  → betslip: "Southampton FC - Swansea City · 2-Way Handicap | Full Time - 2 (+1.5) · 1.32"
https://www.betpawa.ug/external-prefill?selectionIds=1539591711,1537515571,1537497918
  → three legs (Swansea +1.5, Watford 1X, West Ham X2), Odds 2.05, "LOG IN TO PLACE BET"
```

Behaviour worth knowing: the betslip persists in the browser, and a second
prefill **merges** into it with a filter-conflicts strategy — a selection
on an event already in the slip is dropped, not swapped. Expired
selections are silently omitted (the site's own copy: "these picks are no
longer available"). A user who is not logged in sees the slip and a "log
in to place bet" button, so the link is useful before they have an
account.

Alternatives looked at and not recommended: the event page
(`/event/{id}?filter=all`, the owner's Southampton link) has no
selection-preselect parameter — `query.marketId` only chooses which
market tab is open; the booking-code flow (`POST
/api/sportsbook/v3/booking-number` → code → "Enter booking code") works
but creates state on betPawa's side for every link we mint, and the
prefill URL needs no write, so it was not exercised.

### 1.4 One scrape serves every country

Event ids and **selection ids are identical** on the Uganda and Kenya
brands (14 of 14 compared on Southampton v Swansea); only the odds differ
by a few points (Swansea +1.5: 1.32 UG, 1.37 KE). The country sites, from
betPawa's own bundle (host → locale):

| country | host | | country | host |
| --- | --- | --- | --- | --- |
| Benin | `www.betpawa.bj` | | Malawi | `www.betpawa.mw` |
| Cameroon | `www.betpawa.cm` | | Mali | `ml.betpawa.com` |
| Congo (Brazzaville) | `cg.betpawa.com` | | Mozambique | `www.betpawa.co.mz` |
| DR Congo | `www.betpawa.cd` | | Nigeria | `www.betpawa.ng` |
| Ghana | `www.betpawa.com.gh` | | Rwanda | `www.betpawa.rw` |
| Kenya | `www.betpawa.co.ke` | | Sierra Leone | `sl.betpawa.com` |
| Lesotho | `ls.betpawa.com` | | Tanzania | `www.betpawa.co.tz` |
| Liberia | `lr.betpawa.com` | | Uganda | `www.betpawa.ug` |
| | | | Zambia | `www.betpawa.co.zm` |

That is **17**. The owner's list names 18: **South Sudan has no host in
the bundle** (betpawa.com's landing page is JS-rendered and lists no
countries in its HTML). Treat SS as unverified until the owner confirms a
site exists.

### 1.5 Coverage and the name bridge

- **Tonight: 6 of 6.** Every fixture with a published tip today
  (Southampton–Swansea, Watford–Preston, Blackburn–Sheff Utd,
  Cardiff–Stoke, Wrexham–Burnley, Bolton–West Ham) is in the pull, with
  kick-offs matching (18:45 UTC = 19:45 UK; `startTime` is UTC, our
  `kickoff_time` is UK wall-clock, so the join converts through
  Europe/London like `services/bbc_calendar.py`).
- **All 92 clubs of E0–E3 appeared** in the 65-event pull (20+24+24+24).
  A normaliser in the authoring style of `scripts/build_team_aliases.py`
  bridged **88** of them to `teams.canonical_name`; the four needing a
  hand entry are *Manchester United, Queens Park Rangers, Sheffield
  Wednesday, Wolverhampton Wanderers* (our names: Man United, QPR,
  Sheffield Weds, Wolves). So the bridge table can be complete on day one.
- betPawa `participants[].id` is a stable numeric id (Southampton 655237,
  Swansea 657906), the same on every brand — the bridge should key on it,
  as the BBC bridge keys on the URN and for the same reason
  (`FINDINGS.md`, Telford: display names move, identifiers do not).

### 1.6 Where the probe ran from

`ipinfo.io` reported this machine's egress as **UG**. That the API answered
proves nothing about the Azure VM, whose egress is outside betPawa's
markets. **First step of any build is the §4 curl from the VM.** If it is
blocked, the scrape has to run somewhere with an African egress and push
the rows (the owner's machine already runs cycles by hand), or through a
proxy — a decision for then, not now.

## 2. What exists, and what collides

Verified against the tree at `8d89483` (2026-09-08).

- **Sign-in exists and gates nothing** (`AUTH_PLAN.md` D12). `require_user`
  in `api/main.py` is the hook; `users.phone_country` is the ISO region the
  phone was validated under, stored server-side. `GET /me` does **not**
  return it today (`_user_summary`).
- **Country detection is client-side only** (`$lib/country.js`, D6: time
  zone → locale → GB) and is a *default*, spoofable and never sent to the
  server as a fact. No GeoIP on nginx.
- **`/api/tips` is public and cached offline** by the service worker
  (`OFFLINE_API`), and its body is pinned byte-identical across the
  Postgres move. Putting a per-user link into it would put user-dependent
  content into a cached, public response. **The links need their own
  endpoint.**
- **The API is read-only apart from the three account writes** (pinned by
  `test_the_only_write_routes_are_the_account_ones`). This feature needs
  no new write route — the scrape writes from the cycle, the API reads.
- **The cycle already has an "additive, never fatal" step shape**:
  `step_calendar` is disabled unless `BVP_BBC_CALENDAR` is set, runs under
  `_guard`, and a failure cannot stop `results`/`grade`. A `betpawa` step
  copies that exactly.
- **The bridge convention is a pure lookup, no fuzzy matching at runtime**
  (`engine/ingest/teams.py`); unbridged names are counted and reported.
  A `betpawa` source column in `reference/team_aliases.csv` slots in.
- **The parlay page** already knows every leg's `side` and, for derived
  legs, the market it came from; the three scraped markets cover every leg
  the page can build (`SIDE_GROUPS`: win / dc / ah).
- **Prices on the site.** The tip list shows no odds by design (`STATE.md`:
  "return is not a supportable claim"). betPawa's `odds` arrive with the
  scrape; whether to show them is a product decision (D9), not a data one.
- **`docs/bp/` is untracked.** The July protobuf captures and the
  gtleagues sample are from an earlier GT Leagues line of work
  (`PLAN.md` §5 mentions a `BETPAWA_FEED.md` that does not exist in this
  tree); they are not needed by this feature.

## 3. Decisions for the owner

Each with the recommendation the build in §4 assumes.

| # | decision | recommendation | why |
| --- | --- | --- | --- |
| **D1** | Where and when the scrape runs | A **cycle step `betpawa` after `tips`**, daily 06:00 UTC, gated by `BVP_BETPAWA=1`, never fatal (the `step_calendar` shape); optionally re-run by the two-hourly `bvp-results` timer | One request a day is all the ids need; selection ids are stable, odds are not shown (D9). A failed scrape leaves yesterday's rows and hides nothing else |
| **D2** | Storage | Migration `003_betpawa.sql`: `betpawa_events (fixture_id UNIQUE, event_id, competition_id, start_time, fetched_at)` and `betpawa_selections (fixture_id, side, selection_id, odds, fetched_at, UNIQUE (fixture_id, side))` — one row per fixture per rule side, upserted | Brand-independent ids, so no per-country rows. Keeping every side (not only the published one) is what lets the parlay page link derived legs |
| **D3** | The bridge | `betpawa` source in `team_aliases.csv` keyed on **participant id**; generated once from the saved capture by the authoring script with the four hand entries; unbridged ids reported by the step, never guessed | Stable identifier, complete on day one (§1.5) |
| **D4** | Link form | `https://<host>/external-prefill?selectionIds=<id>` for a call; a comma list for a parlay | Verified (§1.3); needs no betPawa-side write; works logged-out |
| **D5** | Which host | Country → host from the §1.4 table, chosen **server-side** | One place to maintain; the SPA never learns the list |
| **D6** | The country signal for the gate | **`users.phone_country`** (server-side, already stored, validated when the number was captured). Alternatives: the browser time zone (client-only, spoofable), nginx GeoIP (a MaxMind licence and module) | The strongest signal the site already holds, and it is the country the user *told us*. A traveller keeps their home site, which is what betPawa itself would do |
| **D7** | The endpoint | New **`GET /betpawa/links`** behind `require_user`: for the caller's country, `{fixture_id: {host, selection_id, url}}` for every live tip and every scraped side; **`{eligible:false}` with no links when the country is not served**; **never inside `/tips`** (§2) | Keeps `/tips` public, cached and byte-identical; one gate in one place; the parlay page reuses it |
| **D8** | What a signed-out or ineligible visitor sees | Signed-out: the button renders as **"Sign in to bet on betPawa"** and opens Google's button (the paid-feature hook); signed-in but not in a served country: **no button** | The signed-out state is the funnel; the ineligible state has nothing to offer and a disabled button would need copy that explains betPawa's map |
| **D9** | Show betPawa's odds on the button | **No, in v1** | The site publishes no prices by design; a price scraped at 06:00 is stale by kick-off and would be the first number on the page the site cannot stand behind |
| **D10** | Partner / affiliate agreement | **Owner, 2026-09-08: there is none.** D4 stands as written | Unknown from here; betPawa's bundle carries `/external-prefill` and `/external-page`, both built for third parties to link in, so a partner form likely exists |
| **D11** | Fixture with no selection for our side (the +1.5 line absent, §1.2) | Button falls back to **"See on betPawa"** → `/event/{id}` with no selection | Says what is true; a wager button that opens an empty slip would read as a bug |
| **D12** | Terms and change risk | Accept: the endpoint is undocumented and protobuf-first; one GET a day; the parse is pinned by the saved capture so a shape change fails the step loudly and hides the buttons, nothing else | The feature degrades to "no button", never to a wrong wager |

## 4. Build

### Phase 0 — the one check only the VM can do (10 minutes)

On the VM, before anything is written:

```
curl -s -o /dev/null -w "%{http_code}\n" \
  "https://www.betpawa.ug/api/sportsbook/v4/events/37536526" \
  -H "X-Pawa-Brand: betpawa-uganda" -H "Accept: application/json"
```

200 → proceed. Anything else → §1.6, decide where the scrape runs.

**Done 2026-09-08 (owner, on the VM): both answer 200 — the single event
(440,043 B) and the list query (562,796 B, 65 events, tonight's six first).
The VM's egress is served; the scrape runs in the cycle as D1 says.**

### Phase A — scrape, bridge, store, cycle step (~1 day)

**BUILT 2026-09-08**, as written, with three notes. `services/betpawa_feed.py`
(`query` / `fetch` / `parse` / `sync`, `--file` replay, `--dry-run`);
`db/migrations/003_betpawa.sql` (ids as TEXT; selections replaced per fixture
per run; an event id may not sit on two fixtures — the rescheduling case is
handled and tested); `reference/betpawa_teams.csv` **complete for all 92
clubs** from the saved capture via the new `scripts/build_betpawa_teams.py`
(six hand pairs, Leyton Orient London and MK Dons joining the four named in
§1.5), folded into the bridge by `build_team_aliases.py` as source `betpawa`
keyed on participant id; `step_betpawa` after `tips` in the cycle, off unless
`BVP_BETPAWA=1`, off for every test by `conftest.py`. Verified: 21 feed tests
on the five-event capture and 4 cycle tests; **738 pass** (full suite); a live
dry run and then a real run into the development store — **65 events, 55 on
our fixtures, 10 unmatched (the book runs past our feed window), 407
selections, every club bridged** — and a join of tonight's six calls to their
selections: five resolve, **Wrexham +1.5 does not** (the market makes Wrexham
favourite; the line is Burnley's), the D11 case live on day one. The unit
carries `Environment=BVP_BETPAWA=0` until the deploy that ships the buttons.

1. `services/betpawa_feed.py`: `fetch()` (the §1.1 request, paging on
   `skip`), `parse(payload) -> list[Event]` (pure: id, participant ids and
   names, start time, competition, and the selection id + odds for each of
   the eight sides in §1.2, absent when the row is missing), `sync(conn,
   events, bridge)` (join to `fixtures` on bridged team ids + UK date;
   upsert both tables; report unbridged and unmatched).
   → verify: tests on the saved capture — 65 events parsed, the
   Southampton ids pinned (`A+1.5` → 1539591711, `1X` → 1537500845), the
   Gillingham case yields no `A+1.5`, a renamed participant with the same
   id still bridges, an unknown id is reported not guessed.
2. `db/migrations/003_betpawa.sql` (D2); `reference/team_aliases.csv`
   gains the `betpawa` rows; `build_team_aliases.py` learns to emit them
   from the capture with the four manual pairs.
3. `services/run_cycle.py` `step_betpawa` after `step_tips`, `_guard`ed,
   disabled without `BVP_BETPAWA`; `engine/config.py` gains the flag.
   → verify: the cycle test that plants a failing feed and proves `results`
   still runs (the calendar precedent).

### Phase B — the endpoint (~½ day)

**BUILT 2026-09-08**, as written. `api/betpawa.py` (pure: the 17-host table —
South Sudan deliberately absent until a host is confirmed — `host_for`,
`event_url`, `prefill_url`); `GET /betpawa/links` in `api/main.py` behind
`require_user`, country from `users.phone_country`, `links` as a list of
`{fixture_id, event_id, event_url, sides: {side: {selection_id, url}}}` over
the `/tips` predicate joined to the scrape's two tables, `{eligible: false,
links: []}` for an unserved country or an account with no phone yet, no odds
on the wire; `_user_summary` (so `/me` and both write routes) now carries
`phone_country`. Verified: `tests/test_betpawa_api.py` (11 — anonymous 401,
KE host and the verified Swansea link, GB and phoneless not eligible, the
missing-side fixture keeping its event link, past/settled tips and unmatched
fixtures absent, GET only); the auth and API suites unchanged (72 pass with
the new file). The service worker needs nothing: the route is not in its
allow-list and stays network-only.

4. `api/main.py` `GET /betpawa/links` (D7): `require_user`; country from
   `users.phone_country`; host table (D5) as a module constant with the 17
   hosts; body `{eligible, country, links: {fixture_id: {event_id, sides:
   {side: {selection_id, url}}, event_url}}}` for fixtures whose tip is
   live (the `/tips` predicate). `_user_summary` gains `phone_country`.
   → verify: anonymous 401; a KE user gets links with the `.co.ke` host; a
   GB user gets `eligible: false` and no links; a fixture with no `+1.5`
   row has `event_url` and no `A+1.5` side; the body is read-only and the
   write-route pin is unchanged.

### Phase C — the site (~1 day)

**BUILT 2026-09-08**, as written, with two notes. `$lib/betpawa.js` (pure:
`indexLinks`, `wagerLink` — wager / event-page fallback / nothing —
`wagerLabel`, `prefillUrl` mirroring `api/betpawa.py`, `slipLink` — one
accumulator link only when every leg has a line, else the legs that lack
one named; 10 node tests). The layout owns the state: once `me` is known it
fetches `/betpawa/links` and hands the pages a store via `setContext`
(`anonymous` / `ineligible` / `ready` / `unconfigured` / `loading` /
`error`); the signed-out button calls Google One Tap where it can and scrolls
the header's sign-in button into view. Front page: a small outlined button
under each call's league line — "Bet this on betPawa ↗" in the accent, "See
on betPawa ↗" muted for the event-page fallback, a dashed "Sign in to bet on
betPawa" when anonymous, nothing when ineligible — with click and Enter
stopped from reaching the row's drawer toggle; the note gains the "a link,
not a stake" sentence. Parlay page: the same button per leg (a derived leg
links its derived side), and under the total either "Place this slip on
betPawa ↗" as one prefill link or the sentence naming the legs betPawa has
no line for; a fourth honesty paragraph. Note 1: the per-leg button on the
parlay page was not in step 7's wording but is the same button per fixture
the request asked for. Note 2: no odds anywhere (D9). Verified: **49 web
tests** (39 + 10), `npm run build` clean, and a **30-check Playwright
click-through** at 1280 and 390 px on a migrated `bvp_scratch` with three
tips today (Swansea +1.5 with a line, Wrexham +1.5 without, Watford 1X) and
three planted sessions (KE, GB, phoneless): anonymous sees the dashed
sign-in button on every call and under the slip and no links; KE sees two
wager links with the exact prefill URLs and the Wrexham event-page
fallback, new-tab + noopener, click and Enter on the button leave the drawer
shut while the row still opens it, no odds in the list, the note; the
default Safer slip (which includes Wrexham) is refused by name, and with
handicaps off and Any call on the whole slip links as one accumulator; GB is
signed in and sees no button anywhere; at 390 px the three buttons sit
inside the viewport with no horizontal scroll; no page errors beyond
Google's origin check rejecting the dev port. `bvp_scratch` dropped after.

5. `$lib/betpawa.js` (pure, tested): `wagerUrl(host, ids)` and
   `parlayUrl(host, legs)` — string building only, never a probability.
6. `+page.svelte`: a button in each row's verdict block, three states
   (D8, D11); links fetched once after `me` resolves, from the layout so
   `/parlay` gets them too (`AUTH_PLAN.md` §1: the parlay page fetches in a
   mount effect, so the gate must wrap from the layout).
7. `parlay/+page.svelte`: "Place this slip on betPawa" under the total,
   comma-joined selection ids of the shown legs, derived legs included;
   absent when any leg has no selection, with the sentence saying which.
8. Service worker: nothing — `/api/betpawa/links` is not in `OFFLINE_API`
   and must not be.
   → verify: web tests for the two builders; Playwright click-through on a
   scratch `bvp_scratch` with a planted KE session, a planted GB session
   and anonymous, at 1280 and 390 px; the prefill link opened once for
   real.

### Phase D — documents and deploy (~½ day)

**Documents done 2026-09-08**: `PRODUCT.md` §6 (what the button is and is
not), `BACKLOG.md` B26, `STATE.md` (site, API and cycle rows, the open
table), `RUNBOOK.md` §0 + §5.11, `DEPLOY.md` §2.7 row + the §5.3 betPawa
block, `.env.example`, the cycle unit's `BVP_BETPAWA=0` line,
`OUTSTANDING.md`. **The deploy is the owner's**, on the checklist below.

#### The VM, in order — owner's checklist

Between matchdays (or at least not while the 06:00 UTC cycle is running).
Everything is additive: the schema change is two empty tables, the cycle
step is off until its drop-in exists, and the buttons render for nobody
until a signed-in account from a served country loads the page. Rollback is
`git checkout` of the previous commit and `deploy.sh --no-pull`; the two
tables can stay.

1. **Commit and push** from the development machine — every B26 file is
   uncommitted until then (`git status` on the VM must be clean before
   `deploy.sh` will run). Include `docs/bp/fixtures/` or not as you prefer;
   the test fixture the suite needs is `tests/data/betpawa_efl_2026-09-08.json`
   and is in the tree.
2. **The cycle unit's drop-in**, before the deploy so the next cycle picks
   it up: `sudo mkdir -p /etc/systemd/system/bvp-cycle.service.d` and write
   `/etc/systemd/system/bvp-cycle.service.d/betpawa.conf` containing
   `[Service]` and `Environment=BVP_BETPAWA=1`. After the pull in step 3
   copy the tracked unit (`sudo cp deploy/systemd/bvp-cycle.service
   /etc/systemd/system/`), `sudo systemctl daemon-reload`, and
   `systemctl cat bvp-cycle | grep BETPAWA` shows `=0` from the unit and
   `=1` from the drop-in. The drop-in wins.
3. **`scripts/deploy.sh`** as `bvp` from `/srv/bvp`: pull → pip (no new
   pins) → frontend build (the swap is in place since Phase C of the Postgres
   move) → **migrate** (expect `applied: ['003_betpawa']`) → `pytest -q`
   (expect the 11 `test_betpawa_api` and 21 `test_betpawa_feed` tests among
   the green; the suite runs as `bvp`, non-superuser, as on 2026-09-08) →
   restart → `/health`.
4. **The first scrape, by hand**, so the buttons exist today rather than
   after the next 06:00 cycle. From `/srv/bvp` as `bvp`:
   `BVP_DATABASE_URL=postgresql:///bvp .venv/bin/python -m services.betpawa_feed --dry-run`
   — expect a line like `65 event(s); N matched our fixtures … all team
   names bridged` — then the same without `--dry-run`, then
   `psql bvp -c "SELECT COUNT(*) FROM betpawa_events"`.
5. **Verify over HTTPS**: `curl -s -o /dev/null -w "%{http_code}\n"
   https://babavanga.net/api/betpawa/links` answers **401**; then in a
   browser, signed out, a call shows the dashed "Sign in to bet on betPawa"
   button; sign in with an account whose phone is from a served country
   (Kenya, Uganda, Nigeria, …) and the same call shows "Bet this on
   betPawa ↗" (or "See on betPawa ↗" where the book has no line for our
   side); click it — a new tab opens on that country's betPawa site with
   the selection in the betslip. `/parlay` shows the per-leg buttons and
   "Place this slip on betPawa ↗" when every leg has a line. An account
   with a GB number sees no button: correct.
6. **Tomorrow's cycle**: `journalctl -u bvp-cycle.service --since today`
   carries a `[ok] betpawa   N event(s); M matched …` line (`RUNBOOK.md`
   §5.11 for the two ATTENTION states).
7. **Backup** runs unchanged (`pg_dump` of the whole database covers the two
   tables).
8. **Docs**: `STATE.md`'s B26 row to "live", `OUTSTANDING.md` entry.

9. `BACKLOG.md` B26, `PRODUCT.md` (what the button is and is not — a
   link, not a recommendation to stake), `STATE.md` site and API rows,
   `RUNBOOK.md` (the step, its flag, "buttons gone" diagnosis),
   `DEPLOY.md` (`BVP_BETPAWA=1` on the cycle unit), `OUTSTANDING.md`.
   Deploy is the standard sequence between matchdays.

**Effort: ~3 days**, Phase 0 first.

## 5. What this does not change

The rule, the tip list, the record, the parlay selector, the schema of any
existing table, the book (off), and the ledger — **0 configurations, no
probe**: nothing here forms or measures a probability. The honesty copy
gains one line: the button links to a bookmaker; the call's strike rate is
the only thing the site stands behind, and it is not a return.
