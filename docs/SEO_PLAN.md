# SEO_PLAN — getting babavanga.net found

Written **2026-09-16**, for review. This is an assessment, and **nothing in
it is built yet**. The owner asked for a review of the site's SEO, suggestions
for improving it, and an exploration of a "dynamic robots.txt that
generates based on the games that are playing". §2 is what the review found
on the live site, §3 the decisions the owner has to take, §4 and §5 the two
phases of work, §7 how to tell whether it worked.

Reading order for a thread picking this up: `STATE.md` → this file →
`web/src/routes/+layout.js` (why every page is client-rendered today) →
`deploy/nginx/bvp.conf.template` (how pages are served) →
`engine/serve/tips.py` `PUBLISH_WITHIN_DAYS` (when a call exists).

---

## 0. Verdict

**Phase 1 (~1 day, no architecture change)** fixes the problems that are
actively hurting the site today:
- every unknown address answers "200 OK" with the homepage;
- `https://www.babavanga.net` fails with a certificate error;
- shared links have no preview image;
- the page title carries no search terms;
- a 2 MB favicon.

**Phase 2 (~5 days, rough)** is what could actually bring search traffic.
Every fixture, league and team gets a permanent page whose HTML already
contains its content, and the database generates a `sitemap.xml` listing
those pages. Phase 2 hinges on one architectural decision (D1).

**The "dynamic robots.txt" becomes a dynamic `sitemap.xml`** (§1). robots.txt
lists what crawlers must *not* fetch, and Google caches it for up to a day,
so a version that changed with each game would be both the wrong tool and
out of date. A sitemap lists the pages that exist and when each last
changed, and that is the file the database should drive. It has nothing to
list until Phase 2 creates per-match pages.

## 1. SEO basics this plan relies on

A search engine **crawls** a URL (fetches it), **renders** it (runs its
JavaScript, if it bothers), **indexes** what it finds, then **ranks** it
against a query. Each item below changes one of those steps.

| term | what it is | why it matters here |
| --- | --- | --- |
| `robots.txt` | A plain-text file at the site root saying which paths crawlers may not fetch. | It is not a list of content. A disallowed URL can still be indexed if something links to it. Google caches the file for up to 24 h. |
| `sitemap.xml` | A list of the site's URLs, each with a `<lastmod>` date. | It helps crawlers find pages and know when they changed. Google ignores `<priority>` and `<changefreq>` but uses an accurate `<lastmod>`. |
| URL fragment | Everything after `#`. | **Not a separate page** to a search engine: `/#tips`, `/#results` and `/#record` are all just `/`. |
| client-side rendering | The server sends an empty page and JavaScript fills it in. | Google renders JavaScript eventually, Bing less reliably. WhatsApp, Telegram, X and Facebook link previews never do. |
| soft 404 | A missing page answered with status 200 instead of 404. | Google flags these, wastes crawl time on them, and trusts the site less. |
| canonical | `<link rel="canonical">`, "this is the official URL for this content". | It merges duplicates such as `/?owner=1` into `/`. Pointing it at the wrong URL de-indexes the page. |
| `noindex` | A meta tag or `X-Robots-Tag` header saying "do not list this". | The crawler has to be able to fetch the page to see it, so never combine it with a robots.txt block. |
| Open Graph tags | `og:title`, `og:image` and similar in the page head. | They control what a shared link looks like in WhatsApp, Facebook and X. |
| structured data | JSON-LD describing the page ("this is a football match between…"). | It helps Google understand the page. It does not guarantee any special search-result display. |
| Core Web Vitals | Google's speed and stability measures (LCP, INP, CLS). | They are a ranking input, measured with PageSpeed Insights. |

Expect weeks to months, not days. babavanga.net is a new domain with no
links pointing at it, and gambling-adjacent content is held to a higher
trust bar ("Your Money or Your Life" pages). The site's public, graded
record is a genuine trust asset for that bar.

## 2. What was found (live, 2026-09-16)

| # | finding | evidence | effect |
| --- | --- | --- | --- |
| F1 | **Every page's HTML is an empty shell.** | `+layout.js` sets `ssr = false`. `GET /` returns 3,837 B of script tags and no content. | Link previews and non-Google crawlers see no content. Google sees it only after its render queue. |
| F2 | **Soft 404s everywhere.** | `/robots.txt`, `/sitemap.xml` and `/does-not-exist` all return `200 text/html` 3,837 B, the homepage. Cause: `try_files $uri $uri/ /index.html` in `bvp.conf.template`. | Any junk URL is "a page"; `/robots.txt` and `/sitemap.xml` return HTML instead of text and XML. |
| F3 | **`https://www.babavanga.net` fails TLS.** | DNS aliases `www` to the VM. `curl` reports `SEC_E_WRONG_PRINCIPAL`: the certificate covers the apex only. `http://www…` returns 301 to `https://www…`, which then fails. | Anyone typing www gets a security error. Search engines see two hosts. |
| F4 | **No durable URLs for the actual content.** | Calls live under `/#tips`, which is not a page (§1). `PUBLISH_WITHIN_DAYS = 0` with the cycle at 06:00 UTC, so a call exists only from matchday morning. A settled call leaves the list. `/api/tips` was `[]` on the day of this review (a Wednesday). | Nothing answers "Middlesbrough vs Millwall prediction", which is the query people actually type. The record (266 graded, 208 won, 6 matchweeks at the time of writing; re-read `/api/tips/record`, don't quote this) has no page of its own. |
| F5 | **Head tags carry no search terms and no previews.** | The title is "BabaVanga — we call it before kick-off". `/parlay` has no title of its own. No canonical, no Open Graph or Twitter tags, no JSON-LD. The `<h1>` is the brand line. | Weak relevance signals. Shared links show a bare title. |
| F6 | **Page weight.** | `favicon.svg` is **2,043,245 B**, a RealFaviconGenerator SVG wrapping a raster. `bv-logo-update.fw.png` (1,532,058 B) and `bv-icon.fw.png` (175,959 B) are referenced nowhere but ship in `web/static/`. The service worker precaches every static file except the video. | Roughly 3.7 MB downloaded on a first visit for icons and unused sources, which hurts mobile speed scores. |
| F7 | **`/api/docs` is public.** | `200`: FastAPI's Swagger page, listing every route including `/book` and `/performance`. | Not an SEO problem as such, but an indexable HTML page and an unnecessary map of the internals. |
| F8 | **nginx `add_header` inheritance** (existing, noted for §4). | A location with any `add_header` drops the server-level ones. `location /_app/` already loses `X-Content-Type-Options` this way. | Any task below that adds a header inside a location must repeat the server-level headers. |

## 3. Decisions for the owner

| id | question | recommended | the alternative |
| --- | --- | --- | --- |
| **D1** | How Phase 2 pages get their content into the HTML. | **(a) Server-side rendering.** SvelteKit's `adapter-node` runs as one more systemd service; nginx proxies pages to it. It gives real 404s, per-page previews and full content for every crawler. Cost: one Node process on the VM and a second service in `deploy.sh`. The `+layout.js` comment rejects prerendering because it "would bake in whatever was true at build time", but SSR renders fresh on every request, so the objection doesn't apply. | **(b)** Keep client-side rendering and rely on Google running the JavaScript. Cheapest, but indexing is slower and every shared link previews as the homepage. **(c)** Have the cycle write static HTML files from Python. No new process, but it means a second templating system beside Svelte. |
| **D2** | Which host is canonical. | **`babavanga.net`**, with `www` added to the certificate and redirected (301) to the apex. People type www. | Delete the `www` DNS record. |
| **D3** | Where the site's origin (`https://babavanga.net`) lives in the frontend. Canonical, `og:image` and the sitemap need absolute URLs. | **One constant in `web/src/lib/site.js`.** The domain is now the product's identity. The nginx template keeps it as environment, as `DEPLOY.md` §3.6 requires for server config. | A build-time `PUBLIC_SITE_ORIGIN` via `$env/static/public`, which needs an untracked env file on the VM. |
| **D4** | Title and description wording. | Draft in §4 task 1.5. The owner's words decide. Check the Search Console query report (1.0) before finalising, since how the audience searches (e.g. "EPL predictions" vs "Premier League tips") is a measurement, not a guess. | — |
| **D5** | The share image. | Owner supplies a 1200×630 PNG or JPG, kept small (≤ 300 KB is the commonly cited safe size for WhatsApp previews), from the existing design work in `docs/ui/designs/`. | — |
| **D6** | `/api/docs`, `/api/redoc`, `/api/openapi.json` in production. | **404 them in nginx.** They stay available on `uvicorn` locally for development. | Leave them public. |
| **D7** | What a match page says before its call is published. | **The fixture, kick-off and "our call is published on matchday at 06:00 UTC".** `PUBLISH_WITHIN_DAYS` stays 0: publishing earlier changes the information the call is made on, which is a product and measurement change, not an SEO one. | Pages only from matchday. That throws away the days of pre-match searching. |
| **D8** | Which fixtures get a page and a sitemap entry. | **Every fixture that has a published tip** (permanent), **plus upcoming fixtures within 7 days**. **Never** the historical `matches` corpus: those were backtest scores, not published calls, and a page presenting them as calls would break "published before kick-off". | Tipped fixtures only. |
| **D9** | URL shape. | **`/match/{fixture_id}-{home}-vs-{away}`**, `/team/{team_id}-{name}`, `/premier-league`, `/championship`, `/league-one`, `/league-two`. The id is authoritative and the words are decoration: a wrong or renamed slug 301s to the current one, so a team rename never breaks a link. | Words only, e.g. `/match/2026-09-15/middlesbrough-v-millwall`. Prettier, but it breaks on renames and reschedules. |
| **D10** | Split `/results` and `/record` into real pages (the `docs/notes` item "Separate last time out/record, separate pages"). | **Yes for `/record`**, the trust asset. The nav links change from `/#record` to `/record`. | Keep the one-page layout; the record stays unindexable as a page. |
| **D11** | Is Google Search Console already set up for the domain? | If not, it is task 1.0 and comes before everything else. | — |

## 4. Phase 1 — defects and quick wins (~1 day)

No rendering change and no API change. Tasks 1.2–1.4 are nginx and certificate
work that lands on the VM. The rest ships with the next frontend build.

### 1.0 Baseline first (owner, ~30 min)

- **Google Search Console:** add a **Domain property** for `babavanga.net`,
  verified by a DNS TXT record at the registrar. A domain property covers
  apex, www, http and https in one go.
- **Bing Webmaster Tools:** import the site from Search Console.
- **PageSpeed Insights** on `https://babavanga.net/`, mobile. Write the
  score, LCP, INP and CLS into §7.
- Note Search Console's Pages report counts as they stand. Expect little
  data for the first week.

### 1.1 A real `robots.txt`

**Built 2026-09-16, deploy pending.**

New `web/static/robots.txt`:

```
User-agent: *
Disallow: /book
Disallow: /performance
```

- **Do not add `Disallow: /api/`.** The page is client-rendered, so Google's
  renderer has to fetch `/api/tips` to see any calls. Blocking it makes the
  indexed page an empty shell. `/api/` is kept out of the index by a response
  header instead (1.3).
- No `Sitemap:` line until 2.7 creates one. A pointer to a 404 is an error in
  Search Console.
- `/book` and `/performance` are disallowed rather than `noindex`ed: they are
  unlinked, and a blocked page's meta tag is never read anyway.

**Verify:** `curl -i https://babavanga.net/robots.txt` returns `200`,
`Content-Type: text/plain`, and the three lines.

### 1.2 Real 404s — `deploy/nginx/bvp.conf.template`

**Built 2026-09-16, deploy pending.** As built, `error_page` sits inside
`location /` (so a missing `/_app/` asset keeps nginx's plain 404), and the
`index.html` block's header gained `always`: `add_header` skips non-2xx/3xx
responses without it, which left the 404 shell without `no-cache`. The test
is `tests/test_nginx_routes.py`.

Replace the catch-all fallback with a list of the routes that exist:

```nginx
location / {
    try_files $uri $uri/ =404;
    # Unknown paths: status 404, body is the shell, and SvelteKit renders
    # its own not-found page in the browser.
    error_page 404 /index.html;
}
# Client-side routes: the SvelteKit shell. `rewrite … last` re-enters the
# `location = /index.html` block, so its no-cache header still applies
# (a non-final `try_files /index.html` argument would skip it).
location ~ ^/(parlay|book|performance)/?$ {
    rewrite ^ /index.html last;
}
location = /index.html {
    add_header Cache-Control "no-cache" always;   # `always`: the 404 too
}
```

- **This creates a coupling:** a new client route must be added to the regex,
  or it 404s. Pin it with a test that reads the template and checks the regex
  names every `web/src/routes/*/+page.svelte` directory. The coupling goes
  away under D1(a), where SvelteKit decides 404s itself.
- `bvp-http.conf.template` is the superseded no-domain posture. Leave it.

**Verify** (after deploy):
- `/`, `/parlay`, `/book`, `/?owner=1`, `/_app/…` any asset, `/site.webmanifest`
  and `/service-worker.js` all return `200`.
- `/does-not-exist` and `/sitemap.xml` return `404`, and the browser shows
  SvelteKit's not-found page.
- `/parlay` still carries `Cache-Control: no-cache`.
- An installed PWA still opens offline.

### 1.3 Keep `/api/` out of the index; close the API docs (D6)

- In each `/api/…` location of `bvp.conf.template`, add
  `add_header X-Robots-Tag "noindex" always;`. Because of F8, **repeat** the
  server-level `X-Content-Type-Options` and `Referrer-Policy` lines in the
  same location, or they silently disappear from API responses.
- `location ~ ^/api/(docs|redoc|openapi\.json) { return 404; }`. A regex
  location beats the plain `/api/` prefix.

**Verify:**
- `curl -I https://babavanga.net/api/tips` shows `X-Robots-Tag: noindex`,
  `X-Content-Type-Options: nosniff` and the referrer policy.
- `/api/docs` returns `404`.
- The front page still loads its calls.

### 1.4 One host: www → apex (D2)

On the VM:
- Expand the certificate:
  `sudo certbot certonly --webroot -w /var/www/certbot --cert-name babavanga.net -d babavanga.net -d www.babavanga.net`.
  Renewal then covers both names, and the files stay under
  `live/babavanga.net/`.

In the template:
- The port-80 block: `server_name ${BVP_DOMAIN} www.${BVP_DOMAIN};` and
  redirect to `https://${BVP_DOMAIN}$request_uri`, not `$host`, so
  `http://www` reaches the apex in one hop.
- A new 443 server for `www.${BVP_DOMAIN}`, using the same certificate,
  containing only `return 301 https://${BVP_DOMAIN}$request_uri;`.

`DEPLOY.md` step 5b gains the expanded certbot line.

**Verify:** `curl -I` on `https://www.babavanga.net/x` and on
`http://www.babavanga.net/x` each return one `301` to
`https://babavanga.net/x`.

### 1.5 Head tags every crawler and previewer sees — `web/src/app.html`

`app.html` is the only HTML that non-rendering bots receive, so the tags
shared by every page go here. The draft copy below is for D4. It makes no
return claim, in line with `PRODUCT.md`.

- `<title>Football Predictions &amp; Tips — EPL to League Two | BabaVanga</title>`
- `<meta name="description" content="Predictions for every Premier League, Championship, League One and League Two match, published before kick-off and graded after.">`
- **Open Graph:** `og:type` `website`, `og:site_name` `BabaVanga`,
  `og:title`, `og:description`, `og:url` `https://babavanga.net/`,
  `og:image` `https://babavanga.net/og-image.png` (absolute),
  `og:image:width` 1200, `og:image:height` 630, `og:image:alt`.
- **Twitter/X:** `twitter:card` `summary_large_image`.
- **JSON-LD:**
  - `Organization`: `name`, `url`, `logo` = the 512 px manifest icon.
    `sameAs` only if real social profiles exist.
  - `WebSite`: `name`, `url`.
- **Not a canonical.** A canonical in `app.html` would tell Google that
  `/parlay` is a copy of `/` and de-index it. Canonicals are per route (1.6).
- Leave the `<h1>` alone in Phase 1. It is a design element, and keyword
  text beside it is a D4 conversation, not a default.

### 1.6 Per-route head — `<svelte:head>`

- `+page.svelte`: `<link rel="canonical" href="https://babavanga.net/">`,
  from the D3 constant. This also merges `/?owner=1` into `/`.
- `parlay/+page.svelte`: its own title and canonical. Draft title:
  "Accumulator Builder — Combine Today's Calls | BabaVanga". "Accumulator"
  or "multibet" is how UK and African punters say parlay; confirm with the
  Search Console queries.
- Svelte 5 turns `<title>` inside `<svelte:head>` into a `document.title`
  assignment, so there is no duplicate title. Under client-side rendering
  only Google sees these; a shared `/parlay` link still previews with the
  homepage's tags until D1(a).

**Verify** (Playwright click-through, per `web-clickthrough-setup`): on `/`
and `/parlay`, `document.title` is as intended, there is exactly one
`link[rel=canonical]` with the right href, and exactly one meta description.

### 1.7 The share image (D5)

- Owner supplies `web/static/og-image.png`.
- Exclude it from the service worker precache, the same way as
  `header-video.mp4` (`web/src/service-worker.js`): visitors never need it.

**Verify:**
- Paste the URL into Facebook's Sharing Debugger or opengraph.xyz.
- Send the link to yourself on WhatsApp. It should show the image, title and
  description. WhatsApp caches previews per URL, so test with `/?v=1` after
  a change.

### 1.8 Page weight (F6)

- `favicon.svg`: remove its `<link rel="icon" type="image/svg+xml">` line and
  the file. `favicon-96x96.png`, `favicon.ico` and `apple-touch-icon.png`
  already cover every browser. If the owner has a true vector logo, a
  hand-made small SVG can come back later.
- Move `bv-icon.fw.png` and `bv-logo-update.fw.png` to `docs/ui/`, where
  `player.fw.png` already lives. Delete the untracked `web/static/favi-old.rar`.
- The service worker precache shrinks by itself, because it reads `files`.

**Verify:**
- `npm run build` output has no `.fw.png`.
- `cd web && npm test` stays green.
- Re-run PageSpeed Insights and record it in §7.

### 1.9 Docs and deploy

- `DEPLOY.md`: the nginx template changes and the certbot line.
- `STATE.md`: the site row.
- `OUTSTANDING.md`: journal entry.
- A `BACKLOG.md` item (next free id, B27).

VM order:
1. Commit.
2. Expand the certificate (1.4).
3. Render the template and run `nginx -t`.
4. Reload nginx.
5. `deploy.sh` (frontend build).
6. The 1.1–1.4 curls.
7. In Search Console: URL Inspection on `/` and "Request indexing".

## 5. Phase 2 — permanent pages and a generated sitemap (~5 days, rough)

Written for **D1(a)**. Under D1(b):
- skip 2.1;
- the new routes are client-side and go into the 1.2 regex;
- the sitemap (2.7) is built by FastAPI and proxied at `/sitemap.xml`;
- per-page share previews are not possible.

Every new page **shows only what the front page's cards already show** —
the call, what it needs, the confidence bar, the kick-off, and after the
match the score and outcome. No prices, no return, no new probability
(§6).

### 2.1 Server-side rendering (~1½ days)

**Frontend:**
- `@sveltejs/adapter-node` in `svelte.config.js`.
- `+layout.js`: remove `ssr = false`, keep `prerender = false`, and rewrite
  its comment.
- **Server/browser audit:** anything reading `window`, `localStorage` or the
  viewer's zone must run after mount.
  - `+page.svelte` has `const zone = viewerZone()` at the top level. Under
    SSR that is the VM's zone, and kick-off times would flip on hydration.
    Render UK time with a "UK" label on the server, and convert in
    `onMount`.
  - `resolveOwner` already runs in `onMount`, and `HeroVideo` is
    mount-only.
- **API during SSR:** `web/src/hooks.server.js` `handleFetch` rewrites
  `/api/*` to `BVP_API_URL` (default `http://127.0.0.1:8000`), the variable
  `vite.config.js` already reads.
- **Signed-in state stays browser-only** (session, phone gate, betPawa links,
  as now). Server HTML is therefore identical for every visitor: no cookie
  is forwarded, no personal data is rendered server-side, and responses are
  cacheable.
- **Service worker:** the navigation handler caches every route under the
  key `'/'`. With SSR each route is its own document: cache per URL, and fall
  back to the cached `/` offline.

**Server:**
- **systemd:** new `deploy/systemd/bvp-web.service`
  (`node /srv/bvp/web/build`, `HOST=127.0.0.1`, `PORT=3000`,
  `ORIGIN=https://babavanga.net`). Set `ORIGIN` as environment in a drop-in,
  on the `bvp-api` client-id pattern.
- **nginx:** `location /` proxies to `127.0.0.1:3000`.
  - Keep `/_app/immutable/` served from disk with the year-long cache.
  - Remove the 1.2 route regex and `error_page`: SvelteKit returns real 404s.
  - The `/api/` locations are unchanged.
- **`deploy.sh`:** restart `bvp-web` after the build. It currently "needs sudo
  for exactly one thing"; the sudoers line in `DEPLOY.md` gains the second
  restart.
- **VM memory:** one more Node process, roughly 60–100 MB (estimate, measure
  it). The frontend build already needs swap (`STATE.md`, Postgres row).

**Verify:**
- `curl -s https://babavanga.net/ | grep` finds a call's team names in the
  raw HTML on a matchday.
- `curl -I /does-not-exist` returns `404`.
- Web tests green.
- The click-through repeats the B25 and B26 checks: sign-in, phone gate,
  betPawa buttons, 390 px width, PWA offline.

### 2.2 Read-only API additions (~1 day) — `api/main.py`

- **`GET /fixture/{fixture_id}`:**
  - teams, division, date, kick-off, and its tip if any (the `TIP_SELECT`
    shape, settled or not, through `_with_handicap`);
  - **no fixture prices**;
  - `404` if unknown.
- **`GET /teams`:** served-division teams with `team_id`, name and slug.
- **`GET /team/{team_id}/tips`:** published tips involving the team, newest
  first, with a limit.
- **`GET /sitemap/entries`:** per D8, fixture ids, slugs and a `lastmod`
  (the latest of `published_at`, `settled_at` and the fixture's
  `updated_at`, all stored as UTC text).
- **Slugs:** computed, not stored. Lowercase, accents folded, runs of
  non-alphanumerics become `-`. A test pins that served-division slugs are
  unique.
- **The write surface is unchanged.** The existing test pinning the three
  account writes must stay green.
- Tests in `tests/test_api.py` style.

### 2.3 Match pages (~1 day) — `web/src/routes/match/[match]/`

Load via `+page.js` from `/fixture/{id}`. A slug that doesn't match
redirects (301) to the current one.

States:

| state | shows |
| --- | --- |
| upcoming, no call yet | teams, league, kick-off, "our call is published on matchday at 06:00 UTC" (D7) |
| call published | the call phrase, `callMeans`, the confidence bar, kick-off |
| settled | the call, the score it was graded from, won/lost |
| **stale**: date passed, no tip, never settled | **404**, and excluded from the sitemap |

- **Why stale fixtures exist:** the `fixtures` unique key includes
  `match_date`, so a rescheduled match arrives as a *new* row and the old one
  stays behind.
- **Head:**
  - title "{Home} vs {Away} Prediction, {15 Sep 2026} | BabaVanga";
  - a description written per state;
  - canonical;
  - Open Graph with the generic image.
- **JSON-LD `SportsEvent`:** `name`, `startDate` with the Europe/London
  offset, `homeTeam` and `awayTeam` as `SportsTeam`. It helps understanding;
  no rich result is promised. **No `Review` or `AggregateRating` markup for
  the record**: Google's policy excludes self-serving reviews.
- The betPawa button stays client-side, as on the front page.
- **Optional:** earlier *published* calls between the same two teams (the
  `docs/notes` "prediction history" item). This will be empty for most
  fixtures until more seasons have been published.

### 2.4 League pages (~½ day) — `/premier-league`, `/championship`, `/league-one`, `/league-two`

- **Content:**
  - the division's live calls (`/tips?division=`);
  - recent results (`/tips/results?division=`);
  - the division's line from `/tips/record` `by_division`;
  - links to each match page.
- **Title:** "Premier League Predictions Today | BabaVanga", and so on.
- **Each needs a short intro in the owner's words.** Four identical
  templates with no unique text read as thin, duplicate content.

### 2.5 Team pages (~½ day) — `/team/[team]/`

- **Content:**
  - the next fixture, if any;
  - the published calls involving the team, with outcomes;
  - counts, shown as counts ("8 calls, 6 came in"), not as a strike rate that
    implies skill on a handful of games.
- **Title:** "{Team} Predictions & Record | BabaVanga".

### 2.6 `/record` (and `/results`) as pages (D10)

- Move the sections out of `+page.svelte` into their own routes.
- The header and bottom-nav links change from `/#record` to `/record`.
- The front page keeps a short summary that links through.

### 2.7 The dynamic sitemap (~½ day) — `web/src/routes/sitemap.xml/+server.js`

- **Content:** from `/sitemap/entries`, the static pages, the four league
  pages, the team pages and the match pages per D8.
- **Format:** `<loc>` absolute (D3); `<lastmod>` as ISO 8601 UTC; no
  `<priority>` or `<changefreq>`; `Content-Type: application/xml`;
  `Cache-Control: max-age=3600`.
- **Size:** about 2,000 fixtures a season across E0–E3, far under the
  50,000-URL limit for years.
- **robots.txt** gains `Sitemap: https://babavanga.net/sitemap.xml`. Submit it
  in Search Console.

**This is the "generates from the games that are playing" piece.** Each
matchday's calls and each settlement change `<lastmod>`, which is the signal
for Google to recrawl those pages.

### 2.8 Internal links

- The call drawer on the front page links to the match page.
- Settled cards link to their match page.
- The footer links to the four league pages and `/record`.
- Crawlers find pages mainly by following links. The sitemap is a hint, not
  a substitute.

### 2.9 Docs and deploy (~½ day)

- `DEPLOY.md`: `bvp-web` unit, nginx, sudoers.
- `RUNBOOK.md`: the new service.
- `STATE.md`: the site row.
- `PRODUCT.md`: the new public surfaces and what they may show.
- `BACKLOG.md`.
- `OUTSTANDING.md`.
- In Search Console: submit the sitemap; URL-inspect one match page, one
  league page and one team page ("Test live URL", then "View tested page",
  where the rendered HTML should contain the call).

## 6. What this does not change

- **No rule, cycle, measurement or ledger change.** `PUBLISH_WITHIN_DAYS`
  stays 0 (D7), and nothing here touches `engine/`.
- **No odds, return or P&L on any page.** The same honesty line as
  `PRODUCT.md` §6 and `/tips/record`'s `return_supported: false`.
- **No page for any row of the historical `matches` corpus** (D8).
- **The API's write surface is unchanged.** Sign-in and the betPawa links
  stay browser-side and signed-in only.
- **The fence on `/api/book` and `/api/performance` stays as it is.**

## 7. Measuring it

Record numbers here as they are taken; don't restate them in prose elsewhere.

| when | PageSpeed mobile (score / LCP / INP / CLS) | Search Console: indexed pages | Search Console: soft 404s | impressions, last 28 days |
| --- | --- | --- | --- | --- |
| baseline (1.0) | | | | |
| Phase 1 + 4 weeks | | | | |
| Phase 2 + 4 weeks | | | | |
| Phase 2 + 12 weeks | | | | |

**Phase 1 worked if:**
- Search Console's Pages report shows no soft-404 or "duplicate without
  user-selected canonical" entries for our URLs after a recrawl (allow 2–4
  weeks);
- both www forms 301 to the apex in one hop;
- a WhatsApp share shows the image;
- the mobile PageSpeed score has not fallen.

**Phase 2 worked if:**
- raw HTML carries page content;
- the sitemap shows "Success" in Search Console, with discovered URLs ≈
  submitted;
- indexed match pages trend upward;
- the Performance report shows impressions on queries containing "vs" and
  "prediction".

The owner sets numeric targets once four weeks of baseline exist. A target
set before any data is a guess.
