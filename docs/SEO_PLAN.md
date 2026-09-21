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

**Phase 2 (~6 days, rough; ~5 before the 2026-09-18 review in §5)** is what
could actually bring search traffic.
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
| F8 | **nginx `add_header` inheritance** (existing, noted for §4). | A location with any `add_header` drops the server-level ones. **Measured 2026-09-16** under Ubuntu's nginx 1.24: `/`, `/parlay`, the 404 shell (all via `location = /index.html`), `/service-worker.js` and `/_app/` go out **without** `X-Content-Type-Options` and `Referrer-Policy`; only files served by `location /` (e.g. `/robots.txt`) and `/api/` carry them. | Any task below that adds a header inside a location must repeat the server-level headers. The pages missing both headers is a separate security-header issue, not SEO; open with the owner. |

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
| **D12** | Which team names Phase 2 pages show (added 2026-09-18). `teams.canonical_name` is football-data's abbreviation: "Man United", "Nott'm Forest", "Sheffield Weds", "Peterboro", "Bristol Rvs", "Wolves". | **The BBC's full name** from `reference/bbc_teams.csv` (`bbc_name`, keyed on `canonical_name`; covers all 92 served clubs, checked 2026-09-18) in titles, headings, JSON-LD and slugs. "Man United vs Nott'm Forest Prediction" is not what anyone types. The front page's cards are a separate question. | Keep the canonical names: no new mapping, weaker titles and slugs such as `nott-m-forest`. |

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

**Built 2026-09-16, deploy pending.** As built, not as first written below:
one `map $uri $bvp_robots_tag` (`~^/api/` → `noindex`, else empty, which
sends no header) at the top of the template, and one server-level
`add_header X-Robots-Tag $bvp_robots_tag always;`. No `/api/` location
declares a header, so all of them — and any added later — keep nosniff and
the referrer policy without repeating anything;
`tests/test_nginx_routes.py` pins that no `/api/` location sets its own
headers. The docs regex is anchored `(/|$)`, which also closes
`/api/docs/oauth2-redirect`. D6 taken as recommended.

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

**Template built 2026-09-16, uncommitted; VM steps pending** (`DEPLOY.md`
§5.3 "www" block carries the order). As written below, plus: the www server
sits last so the site stays the default server for 443, and the certbot
command gains `--deploy-hook "systemctl reload nginx"` — nothing reloaded
nginx after a renewal before this. Order on the VM: render the template,
dry-run the expansion, expand, reload, verify, `certbot renew --dry-run`.

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

**Built 2026-09-16, uncommitted.** Owner took D3 (the constant, in
`web/src/lib/site.js`: `ORIGIN`, `HOME_TITLE`), D4 (the draft copy below,
verbatim) and, for D5 until 1.7 exists, **the square 512 px app icon as
`og:image` with `twitter:card` `summary`** — 1.7 switches both to the
1200×630 image and `summary_large_image`. `og:title` repeats the page
title. `web/src/lib/site.test.js` (4 tests) pins app.html's title,
`og:title` and every site URL to `site.js`, that app.html has no canonical,
and that the JSON-LD parses.

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

**Built 2026-09-16, uncommitted.** Owner took "Accumulator Builder". As built,
the front page sets its **title as well as** its canonical: without it a
client-side move from `/parlay` back to `/` kept the parlay title, since the
front page would never set one. `/book` and `/performance` set nothing (they
are disallowed and unlinked), so a move to them keeps the previous title.

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

**Built 2026-09-17, uncommitted.** Owner supplied `web/static/og-image.jpg`
(JPEG, not PNG): 1200×630, 183,928 B. `og:image` points at it with width,
height and alt text, `twitter:card` is `summary_large_image`, the JSON-LD
logo stays the square icon. The service worker's precache now skips a set
(`/header-video.mp4`, `/og-image.jpg`); a Playwright check of the built site
confirmed neither is cached. `site.test.js` gained a test that every site
file `app.html` names exists in `web/static`.

- Owner supplies `web/static/og-image.png`.
- Exclude it from the service worker precache, the same way as
  `header-video.mp4` (`web/src/service-worker.js`): visitors never need it.

**Verify:**
- Paste the URL into Facebook's Sharing Debugger or opengraph.xyz.
- Send the link to yourself on WhatsApp. It should show the image, title and
  description. WhatsApp caches previews per URL, so test with `/?v=1` after
  a change.

### 1.8 Page weight (F6)

**Built 2026-09-17, uncommitted.** `favicon.svg` link and file removed; the
two `.fw.png` files moved to `docs/ui/`; `favi-old.rar` left alone — it is
git-ignored, so the VM never has it. Static files precached in production
~4.18 MB → ~0.43 MB (the build's own `/_app` assets unchanged). **Expect
little change to the PageSpeed score from this**: the icons were never on
the render path. The score is driven by 1.10.

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

### 1.10 Layout shift from the header's sign-in slot (found 2026-09-17)

**Built 2026-09-18, uncommitted.** The owner chose to keep the two-row phone
header, laid out from first paint. `+layout.svelte` only, CSS only:
- at ≤ 820 px the actions take their own row from the start (`flex-basis:
  100%`), at least 40 px tall, and never wrap;
- a long signed-in first name is ellipsised rather than wrapping the row,
  which it did as the font swapped in (0.42 of the 0.65 signed-in CLS at
  360 px);
- `.gsi` has a fixed 40 px height where it had a minimum, so Google's
  container growing to 64 px no longer moves the page.

Measured on a production build under `vite preview`, 4× CPU, against a
scratch database (the real sign-in button renders on `localhost:5173`):

| | 360 px | 390 px |
| --- | --- | --- |
| signed out, before → after | 0.283 → **0.003** | 0.308 → **0.002** |
| signed in, long name, before → after | 0.647 → **0.001** | 0.259 → **0.001** |
| signed in, short name, after | **0.000** | **0.000** |

The phone header is 123 px throughout. At 1280 px the header's geometry is
identical to the live site's. 58 web tests pass. **Still to do:** re-run
PageSpeed after deploy and record it in §7.

The baseline's **CLS 0.337** was reproduced on the live site (0.339, Moto G4
emulation, 4× CPU, throttled network) and traced by `layout-shift` source:

| when | shift | what moved |
| --- | --- | --- |
| ~3.1 s | **0.267** | at phone width the header's actions wrap to a second row when the Google sign-in button mounts (`authReady`), so the header grows 56 px and pushes the hero, stats and everything below |
| ~3.6 s | 0.033 + 0.039 | Google's sign-in iframe resizes (host 40 → 64 → 40 px), moving the header's actions and the page under them again |

CLS is 25% of the Lighthouse performance score and 0.337 is in the "poor"
band (> 0.25). **Fix:** reserve the sign-in slot's final size from first
paint — the `.gsi` host (and the signed-in `.who` state) at a fixed box, so
the header's height at ≤ 820 px is the same before and after sign-in state
resolves. A header design change, so the owner sees it first. **Verify:**
the same layout-shift trace reads < 0.1 on the built site, at 360 and 390 px,
signed out and signed in; PageSpeed mobile re-run.

**LCP 5.7 s** is the hero `<h1>` (2.5 s in the throttled trace above;
PageSpeed's simulation is slower), which exists only after the JavaScript
bundle has loaded and run — client-side rendering (F1). Phase 1 cannot move
it much; D1(a) or prerendering the static hero shell can, and belongs to
Phase 2.

### 1.11 Self-hosted fonts (found and built 2026-09-18, uncommitted)

After 2.1, PageSpeed read 69 with LCP 5.2 s. The hero `<h1>` was in the
HTML by then, and two-thirds of the LCP was render delay behind **the Google
Fonts stylesheet**, the page's one render-blocking resource (§7).

Owner chose to fix it before Phase 2. The build:
- `web/src/lib/fonts/` holds the ten latin woff2 files Google served that
  day for the weights `app.html` asked for (209 KB), with their OFL
  licences.
- `fonts.css` is imported by the layout, so Vite bundles it into the
  layout's stylesheet and emits the fonts as hashed files under
  `/_app/immutable/`, cached for a year by the existing nginx rule.
- `hooks.server.js` adds a preload for Barlow Condensed 800, the hero's and
  the wordmark's face, alongside SvelteKit's default JS and CSS preloads. It
  is sent as a `Link` header.
- `app.html` loses the stylesheet link and both preconnects.
- The service worker now precaches the fonts (they are in `build`), so the
  installed app keeps its type offline; before, it fell back to system
  fonts.
- Characters outside latin (latin-ext, e.g. "Ł") use the system fallback.
- `fonts.test.js` (4): each face's file exists and is woff2, no file is
  orphaned, the families and weights, no Google Fonts reference, and the
  preloaded name exists.

**Measured A/B, same machine, same conditions** (Lighthouse 12 mobile, the
`a711f6b` build against this one, both served by `node build` with no API,
two runs each):

| | score | FCP | LCP | Speed Index | render-blocking |
| --- | --- | --- | --- | --- | --- |
| live code, Google Fonts | 70, 68 | 3.9, 4.0 s | 4.0, 4.3 s | 4.8, 4.8 s | fonts.googleapis.com |
| self-hosted | 76, 82 | 2.5, 2.5 s | 3.0, 3.0 s | 2.8, 2.7 s | none |

Rendering is unchanged:
- the same seven faces load, now all from our own origin;
- a 390 px screenshot of each build, with the animated canvas hidden,
  differs in **0 pixels**.

68 web tests pass.

**Deploy:** the normal `deploy.sh`; no nginx or unit change. **Verify:**
- `curl -sI https://babavanga.net/ | grep -o 'barlow-condensed-800[^;]*'`
  finds the preload;
- `curl -s https://babavanga.net/ | grep -c fonts.googleapis` prints 0;
- then re-run PageSpeed mobile into §7.

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

## 5. Phase 2 — permanent pages and a generated sitemap (~6 days, rough)

**Reviewed against the code 2026-09-18**, before any of it was built. Six
gaps were found and folded into the tasks below, each marked *(review)*:

| # | gap | folded into |
| --- | --- | --- |
| R1 | SSR alone puts no calls in the HTML: the front page fetches in `onMount`, the parlay page in an `$effect`, and neither runs on the server. `$lib/api.js` calls the global `fetch('/api/…')`, which has no base URL in Node and bypasses `handleFetch`. 2.1's own verify step would fail. | 2.1 |
| R2 | `app.html`'s title, description, `og:title` and `og:url` (`/`) sit before `%sveltekit.head%`. Under SSR a match page would ship two `<title>`s (the homepage's first) and an `og:url` naming `/`, so shares collapse onto the homepage — the per-page previews that justify D1(a). | 2.1 |
| R3 | Team names are football-data abbreviations. | D12, 2.2, 2.3 |
| R4 | `fixtures.updated_at` moves on every price refresh (`services/fixture_sync.py`), and no page shows a price, so a `lastmod` built on it changes daily with nothing visible changing. | 2.2, 2.7 |
| R5 | `tips` is `UNIQUE (fixture_id, rule_version)`: a fixture re-tipped across versions has two tips. | 2.2 |
| R6 | 1.10 (CLS) is not fixed by SSR: sign-in state still resolves in the browser, so the header still wraps after first paint. | 2.1 |

Smaller points, also folded in: `adapter-node`'s static files live in
`build/client/` (2.1); the service worker's per-URL cache is unbounded (2.1);
measure VM memory before 2.1; a rescheduled fixture can 301 rather than 404
(2.3). Together they add about a day, mostly R1 and R2.

**Owner decisions, 2026-09-18:** **D1(a), server-side rendering**, taken as
recommended. **1.10 lands first**, before 2.1. **Kick-off times:** the
server's HTML shows UK time labelled "UK", and the browser switches it to
the viewer's zone after load (2.1's server/browser audit, as written).

**Owner decisions for 2.2, 2.3 and 2.7, 2026-09-18**, all as recommended:
- **D7, content:** the call plus facts. A match page also carries the
  venue, each side's last five results this season with our call on each
  and whether it came in, and the last meetings between the two. It shows
  no probability or price beyond what the front page already shows.
- **D8, which fixtures:** every fixture with a published call, plus upcoming
  fixtures in the feed before their call lands. A fixture whose date passed
  with no call returns 404.
- **D9 + D12, URLs and names:** `/match/{id}-{home}-vs-{away}` with BBC full
  names in the slug, the title and the headings.
- **Scope:** `GET /teams` and `GET /team/{id}/tips` move to 2.5. The minimal
  internal links (2.8) were **not** taken into this batch, so match pages
  are reachable through the sitemap only until 2.8.

**Measured before deciding, on the live API:**
- The fixtures feed runs **1–3 days ahead**, not the 7 the plan assumed: 45
  upcoming fixtures across 18–20 Sep. A pre-call page therefore exists for
  at most about three days.
- **Every past fixture has a call**, 267 of 267, so no page 404s as stale
  today, and the sitemap starts at about 312 URLs.
- This season's scores exist for every played fixture, because every
  fixture was called and graded with its score. `matches` holds the
  2010-11 to 2025-26 seasons for head-to-heads.
- Every served club has a venue in `reference/stadiums.csv`. Its `town`
  field is an administrative district ("City Ground, Rushcliffe"), so the
  page shows the venue name only.
- Expect a new domain's match pages to be indexed after their games more
  often than before them. The value builds with the number of pages over a
  season.

**Order:** 2.1 ships alone, with no new page, and the B25/B26/PWA
click-through repeats before anything is built on it — it is the one risky
infrastructure change and the easiest to roll back on its own. Then 2.2,
2.3 and 2.7 (match pages and the sitemap are the search value), then 2.4–2.6
and 2.8.

Written for **D1(a)**. Under D1(b):
- skip 2.1;
- the new routes are client-side and go into the 1.2 regex;
- the sitemap (2.7) is built by FastAPI and proxied at `/sitemap.xml`;
- per-page share previews are not possible.

Every new page **shows only what the front page's cards already show** —
the call, what it needs, the confidence bar, the kick-off, and after the
match the score and outcome. No prices, no return, no new probability
(§6).

### 2.1 Server-side rendering (~2½ days)

**Live 2026-09-18** (`a711f6b`, cut over 07:53–08:01 UTC; ~8 min of 403 on `/` from the step-5 fault noted below). As written
here, with these specifics:
- `adapter-node` replaces `adapter-static`.
- `+page.js` loads for `/` and `/parlay`; `/parlay`'s opening control
  positions come from its load, so the server's slip and the controls
  cannot disagree.
- The in-page effects skip their hydration run, so a first visit makes no
  browser read of tips, results, record or parlay. The old front page read
  tips and results twice on every load.
- `$lib/proxy.js` holds the `handleFetch` rewrite (4 node tests: the prefix
  strip, a trailing slash, no cookie, and non-API or non-GET requests left
  alone).
- `$lib/PageHead.svelte` renders title, description, canonical, `og:title`,
  `og:description` and `og:url`, once per public page.
- The service worker answers navigations network-first, keeping `/` and
  `/parlay` for offline.
- `bvp-web.service` reads the origin from nginx's headers
  (`PROTOCOL_HEADER=x-forwarded-proto`) — **owner decision, in place of the
  `ORIGIN` drop-in below**.
- nginx: `root …/build/client`, `try_files $uri @web`, the 1.2 regex and
  `index.html` blocks gone, and the year-long cache narrowed to
  `/_app/immutable/`, so `version.json` stays fresh.

**Found while building:** `app.html`'s new comment named SvelteKit's head
placeholder, and SvelteKit fills the *first* occurrence. The page's tags
landed inside the comment, the hydration marker closed it early, and the
browser rendered every tag twice. It was caught by the click-through; a
`site.test.js` test now pins each placeholder to one occurrence.

**Side effect:** pages proxied through `@web` carry nosniff and the referrer
policy, so **F8 is fixed for pages**. `/_app/immutable/` and
`/service-worker.js` still lack both, because their locations set their own
headers.

**Verified:**
- **64 web tests** pass (58 before, plus 4 proxy and 2 head-tag tests).
  `tests/test_nginx_routes.py` was rewritten: 2 tests, each failing on the
  old template, and the header test fails on a planted `add_header` in
  `@web`. The full Python suite: **751 pass**.
- **Under Ubuntu 24.04's nginx 1.24**, extracted in WSL, in front of the
  real build on Node 24 and a stub API replaying the scratch database:
  - `nginx -t` clean; pages 200, unknown paths 404 from the page server;
  - static files from disk, the hashed assets with the year-long cache;
  - `/api` still `noindex`, `/api/docs` 404;
  - both www redirects unchanged; the stub saw only prefix-stripped reads.
- **Playwright click-through, 39 checks**, on `vite preview` of the build
  against `bvp_scratch`:
  - the calls and "UK time" in the server's HTML; no browser re-read on
    load; the zone switching to Nairobi with 20:00 UK shown as 22:00;
  - one of each head tag on `/`, `/?owner=1` and `/parlay`, before and
    after client-side moves and browser back;
  - a tab, toggle or risk change reads exactly once;
  - owner view; 404 inside the layout;
  - signed in: name, betPawa links fetched, no personal data in the
    server's HTML; the phone gate for a phoneless account;
  - 390 px bottom nav, no horizontal scroll; offline `/` and `/parlay`,
    and an uncached page falls back to `/`.
- CLS on the SSR build: 0.001–0.003 at 360 and 390 px, signed in and out.

**VM cutover (one-time, between matchdays).** The first build replaces the
files the old site is served from, so the order matters. The site is down
from the end of step 4 until step 5 finishes, a few seconds if they are run
back to back.
1. Commit and push. On the VM: `free -m`, and write it down.
2. `sudo -u bvp git -C /srv/bvp pull --ff-only`.
3. Add the two `bvp-web` lines to `/etc/sudoers.d/bvp` (`DEPLOY.md` §5.2),
   then `sudo visudo -c`. Then
   `sudo cp /srv/bvp/deploy/systemd/bvp-web.service /etc/systemd/system/`,
   `sudo systemctl daemon-reload` and `sudo systemctl enable bvp-web`.
   Enable only, **not `--now`**: there is no server build to run yet.
4. Build: `sudo -u bvp -H bash -c 'cd /srv/bvp/web && npm ci --silent && npm run build'`.
5. At once: `sudo systemctl start bvp-web`, then **wait for it**
   (`until curl -fsS -o /dev/null http://127.0.0.1:3000/; do sleep 1; done`).
   Then re-render the template (`DEPLOY.md` §5.3), `sudo nginx -t` and
   `sudo systemctl reload nginx`. As first run on 2026-09-18, a single
   `curl … && render …` chain failed: Node takes a second or two to bind,
   the chain stopped before nginx, and the old config served 403 on `/`
   (no `index.html` left in `web/build`) until the render was run by hand.
6. `sudo -u bvp /srv/bvp/scripts/deploy.sh --no-pull`: the normal path from
   now on. Expect "page server answering", then the suite and the API
   restart.
7. The `DEPLOY.md` §5.3 curls, including the new `og:url` count. Record
   `free -m` and `systemctl show -p MemoryCurrent bvp-web` against step 1.
8. On a phone: `/` shows today's calls, sign-in works, the betPawa button,
   `/parlay`, and the installed app still opens offline.
9. PageSpeed mobile into §7 (1.10 and 2.1 together). In Search Console,
   URL-inspect `/`: the tested page's HTML should contain the calls.

**Rollback:**
- `git revert` the commit and push.
- On the VM: pull, then `cd web && npm ci && npm run build` (the static
  build again).
- Re-render the old template and reload nginx.
- `sudo systemctl disable --now bvp-web`.

**Before starting:** `free -m` on the VM, to size the Node process against
what Postgres, uvicorn and the build already use (843 MB RAM + 2 GB swap).
**1.10 lands before or with this task** *(review R6)*: the header's sign-in
slot still resolves in the browser under SSR, and a PageSpeed reading taken
after 2.1 would otherwise mix the two changes.

**Frontend:**
- `@sveltejs/adapter-node` in `svelte.config.js`.
- `+layout.js`: remove `ssr = false`, keep `prerender = false`, and rewrite
  its comment.
- **Data loading moves into `load` functions** *(review R1)*. `/` gets a
  `+page.js` that loads tips, results and the record; `/parlay` one that
  loads the launch slip. `$lib/api.js`'s `get()` takes the load's `fetch`
  as an optional argument (the browser's global stays the default), because
  the global `fetch` has no base URL on the server and never passes through
  `handleFetch`. The in-page reloads on a tab, filter or slider change stay
  client-side, as now.
- **Per-page head tags move out of `app.html`** *(review R2)*. Title,
  description, `og:title`, `og:description` and `og:url` go into
  `<svelte:head>`: a default in `+layout.svelte`, overridden per page.
  `app.html` keeps only what is identical on every page — `og:type`,
  `og:site_name`, the share image and its size and alt, `twitter:card`,
  and the Organization/WebSite JSON-LD. `site.test.js` changes with it: it
  pins that app.html carries none of the moved tags, and that the rendered
  front page carries exactly one of each.
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
  back to the cached `/` offline. **Bound it** *(review)*: once match pages
  exist, one entry per page visited grows without limit, so cache only the
  top-level routes (`/`, `/parlay`, later the league pages and `/record`) and
  let the rest fall back to `/`.

**Server:**
- **systemd:** new `deploy/systemd/bvp-web.service`
  (`node /srv/bvp/web/build`, `HOST=127.0.0.1`, `PORT=3000`,
  `ORIGIN=https://babavanga.net`). Set `ORIGIN` as environment in a drop-in,
  on the `bvp-api` client-id pattern.
- **nginx:** `location /` proxies to `127.0.0.1:3000`.
  - Keep `/_app/immutable/` served from disk with the year-long cache.
  - **`root` moves to `/srv/bvp/web/build/client`** *(review)*: that is
    where `adapter-node` writes the static files, and `build/` itself now
    holds the server bundle, which must never be served as files.
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
- The raw HTML of `/` and of `/parlay` each carries exactly one `<title>`,
  one meta description, one `og:title` and one `og:url`, naming that page
  *(review R2)*.
- `curl -I /does-not-exist` returns `404`.
- Web tests green.
- The click-through repeats the B25 and B26 checks: sign-in, phone gate,
  betPawa buttons, 390 px width, PWA offline.

### 2.2 Read-only API additions (~1½ days) — `api/main.py`

**Built 2026-09-18, uncommitted.** As specified below, plus the following.

**What was built:**
- `api/teams.py` (pure): `display_name`, `slug`, `fixture_slug` and
  `venue`.
- `GET /fixture/{id}`: the page's data, with `form` and `meetings`.
- `GET /sitemap/entries`: `[{fixture_id, slug, lastmod}]`, newest first.
- The API's write surface is unchanged.

**Venues (owner decision, same day):** `reference/stadiums.csv` turned out
unfit to print. Its Wikidata labels are stale even as Wikidata's "current"
ground: Brentford at Griffin Park, which it left in 2020; Stoke at the
Britannia Stadium, renamed in 2016. The labels also mix sponsor and
generic names, and Wigan's is a bare item id. The owner chose a reviewed
list:
- `reference/venues.csv` has one row per served club (92): venue, `status`
  and a note. The draft is **69 `ok`, 23 `check`**, the `check` rows being
  mostly sponsor names that change.
- **A `check` row prints no venue** until the owner confirms it by editing
  the file (`status` → `ok`). Nothing else changes.
- `stadiums.csv` is untouched, because its coordinates feed the travel
  measurement.
- fbref was tried as a source of current names and answered 403 with a
  Cloudflare challenge. It was not pursued.

**Tests:** `tests/test_match_api.py`, 24 tests. They use fixed dates for
the season-boundary cases and dates relative to today for the
upcoming/live/stale split. They cover:
- names, slug, venue and call on a settled page;
- no fixture prices;
- form as this season's newest five before the match, W/D/L from the
  side's own view, the later of two calls, last season excluded;
- meetings as scores only, newest first, with a `matches` row that repeats
  a called fixture listed once and a scoreless row left out;
- 404 for a stale fixture, a National League fixture and an unknown id;
- **the sitemap listing exactly the fixtures `/fixture` answers 200 for**;
- `lastmod` for settled, live and upcoming fixtures;
- every served club having a BBC name and one venue row;
- unique slugs, the slug rules and the season start.

Four planted bugs were each caught by the intended test: the sitemap
listing stale fixtures; form using the earliest call; form ignoring the
season; the page ignoring the stale rule.

**Full suite 775 pass.** Read-only smoke test on the development store:
119 sitemap entries in 68 ms; 40 `/fixture` calls, all 200, median 65 ms.

- **`GET /fixture/{fixture_id}`:**
  - teams, division, date, kick-off, and its tip if any (the `TIP_SELECT`
    shape, settled or not, through `_with_handicap`). **"Its tip" is the
    latest `tip_id`** *(review R5)*: `tips` is unique per
    `(fixture_id, rule_version)`, so a fixture re-tipped across versions has
    two, and the page shows one call;
  - **no fixture prices**;
  - `404` if unknown, outside the served divisions, or **stale** (date
    passed, no tip; D8). The rule lives here, once, so the page and the
    sitemap cannot disagree about which fixtures exist.
  - **The D7 facts:**
    - `venue`: `reference/stadiums.csv` `venue` for the home side;
    - `form.home` and `form.away`: each side's last five settled fixtures
      this season, before this one. Each gives the date, the opponent's
      display name, home or away, the score, W/D/L from the side's own
      view, our call's phrase and its outcome. They come from `tips` joined
      to `fixtures`, which carry every played fixture's score since
      2026-08-14;
    - `meetings`: the last five meetings between the two sides, from
      `matches` plus this season's settled fixtures, with date, season,
      home side and score. Scores only, never a call: `matches` rows were
      backtests and must not read as published calls (D8, §6).
- **`GET /teams` and `GET /team/{team_id}/tips`** moved to 2.5 (owner,
  2026-09-18): only the team pages use them.
- **`GET /sitemap/entries`:** per D8, fixture ids, slugs and a `lastmod`:
  the latest of the tip's `published_at` and `settled_at`, or the fixture's
  `first_seen_at` before a tip exists, all stored as UTC text. **Not
  `fixtures.updated_at`** *(review R4)*: `fixture_sync` moves it on every
  price refresh and no page shows a price, so it would change daily with
  nothing visible changing, and Google stops trusting a site's `lastmod`
  when it does.
- **Display names** *(review R3, D12)*: every endpoint above also returns
  each team's display name, read from `reference/bbc_teams.csv` (a test pins
  that every served club has one).
- **Slugs:** computed, not stored, **from the display name**. Lowercase,
  accents folded, runs of non-alphanumerics become `-`. A test pins that
  served-division slugs are unique.
- **The write surface is unchanged.** The existing test pinning the three
  account writes must stay green.
- Tests in `tests/test_api.py` style.

### 2.3 Match pages (~1 day) — `web/src/routes/match/[match]/`

**Built 2026-09-18, uncommitted.** **Ship it with 2.7:** until the sitemap
exists no crawler can find a match page, because nothing links to one yet
(2.8 not taken).

**What was built:**
- `+page.js` loads `/fixture/{id}` through the load's `fetch`. A missing or
  wrong slug 301s to `matchPath`, and an API 404 is a page 404.
- `+page.svelte` has:
  - the kicker and an `<h1>` "{Home} vs {Away}" with the badge crests;
  - a meta line: day, kick-off (UK time in the server's HTML, the viewer's
    after mount) and venue when confirmed;
  - the call box: the matchday line before the call; the phrase, hedge
    badge, "for this to come in…" and CONF bar with the call; the score and
    "our call came in / did not" once settled;
  - the betPawa button on a live call only;
  - recent form, two columns (one below 820 px): W/D/L, the score from the
    side's own view, "v/at" the opponent, and our call with ✓/✗, then
    "Our calls: N of M came in";
  - last meetings, scores only;
  - a closing note that CONF is uncalibrated and not a price, linking to `/`.
- `$lib/match.js` (pure, 7 node tests):
  - dates written out rather than through `Intl`, so the server's and the
    browser's text cannot differ;
  - the path, the id parse and the state;
  - the title and a description per state (below);
  - the form line and the tally;
  - the SportsEvent script, with `<` escaped and a UTC `startDate`;
  - a venue only when confirmed.
- `$lib/api.js` gains `getFixture`.
- The page renders `PageHead` once plus its SportsEvent script, which Svelte
  removes on a move away.

**Descriptions (drafts; the owner's words decide, as D4):**
- before the call: "{game}, {league}, {day date}. Our call is published on
  matchday at 06:00 UTC, before kick-off. Recent form and past meetings are
  here now."
- with the call: "Our call for {game} ({league}, {date}): {call}. Published
  before kick-off and graded after the match."
- settled: "{Home} {h}–{a} {Away} ({league}, {date}). Our call, {call},
  came in / did not come in."

**Verified:**
- 75 web tests; build clean, with no warning from the new files.
- curl on `vite preview` of the build against `bvp_scratch`, seeded from
  `tests/test_match_api.py`: id-only and wrong-word addresses 301 to the
  canonical one; stale, unserved, unknown and non-numeric ids 404; the
  server's HTML carries one of each head tag and one SportsEvent.
- A **25-check Playwright click-through**:
  - the call, score and form in the server's HTML;
  - one of each head tag after hydration, and still after a client-side
    move to `/` and back, with the SportsEvent gone on `/`;
  - title, venue and UTC start in the structured data;
  - form W/D/L and scores from the side's view; the empty-form line;
    meetings newest first;
  - the zone switch (15:00 UK → 17:00 Nairobi);
  - no betPawa button on a settled call, the sign-in-to-bet button on a
    live one; the pre-call state with no CONF bar;
  - a stale fixture 404s inside the layout;
  - 390 px with no horizontal scroll and the columns stacked;
  - no page errors.
- Scratch database dropped.

Load via `+page.js` from `/fixture/{id}`. A slug that doesn't match
redirects (301) to the current one.

States:

| state | shows |
| --- | --- |
| upcoming, no call yet | teams, league, kick-off, "our call is published on matchday at 06:00 UTC" (D7) |
| call published | the call phrase, `callMeans`, the confidence bar, kick-off, the betPawa button |
| settled | the call, the score it was graded from, won/lost |
| **stale**: date passed, no tip, never settled | **404**, and excluded from the sitemap |

In every state below the call (D7, owner 2026-09-18):
- **the venue**;
- **recent form**: each side's last five this season as W/D/L with scores,
  and our calls on those games as a count ("our calls: 4 of 5 came in") —
  a count, not a rate, as in 2.5;
- **last meetings**: scores only.

When a list is short or empty it says so plainly ("first meeting in our
records"). The confidence bar is the one on the front page's cards; there
is no other probability.

- **Why stale fixtures exist:** the `fixtures` unique key includes
  `match_date`, so a rescheduled match arrives as a *new* row and the old one
  stays behind.
- **Optional** *(review)*: a stale fixture whose division, home and away
  match a later fixture 301s to it instead of 404ing, so a shared or indexed
  link survives a reschedule.
- **Head:**
  - title "{Home} vs {Away} Prediction, {15 Sep 2026} | BabaVanga", with the
    D12 display names;
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

**Owner decisions for 2.4 and 2.5, 2026-09-18**, all as recommended:
- **League intros:** drafted here, owner edits (below).
- **League page content:** live calls, plus upcoming fixtures still waiting
  for their call, plus recent results with our calls, plus the record line.
- **Team pages:** build now, for all 92 clubs.
- **Links:** cross-link the new pages and put the four leagues in the site
  footer (part of 2.8). The front page's cards are unchanged, and the 2.8
  call-drawer links remain not taken.

**Measured on the live API that day:**
- 40–83 graded calls per league over 5–6 matchweeks, at 70% (E0), 85.5%
  (E1), 72% (E2) and 81% (E3). The front page already shows these.
- 10–12 upcoming fixtures per league in the feed, but only 2 live calls on
  a Friday.
- All 92 clubs have calls, **4–8 each** (median 6).

### 2.4 League pages (~1 day) — `/premier-league`, `/championship`, `/league-one`, `/league-two`

**Built 2026-09-18, uncommitted**, as specified below, with the owner's
intros verbatim.

**API:**
- `GET /league/{division}`. `record` comes from the same `RECORD` query as
  `/tips/record` `by_division`, and a test pins that they are equal.
  `upcoming` lists unsettled fixtures from today on, called or not.
  `results` lists the last 12 settled. Each fixture gets the latest call by
  a lateral join, and the list shape is shared by `LISTED` and `_listed`,
  which 2.5 reuses.
- **`/sitemap/entries` is now `{matches, leagues}`**. A league's `lastmod`
  is the latest of its matches'.
- `tests/test_match_api.py` +8, **32 in all**.

**Web:**
- `$lib/leagues.js`: slugs, intros, names from `DIVISIONS`, title and
  description.
- The param matcher `src/params/league.js`.
- `routes/[league=league]/`: intro, record line ("60.0% of graded Premier
  League calls came in: 6 of 10, over N matchweeks. Strike rate, not a
  return."), calls and upcoming fixtures by day, recent results. Every row
  links to its match page, and each section has an empty-state line.
- `sitemap.js` lists the league pages.
- The footer lists the four leagues, using the layout's previously unused
  `.links` rule (so that build warning is gone). The match page's league
  name links to its league page.
- The service worker keeps the four league pages for offline, as 2.1
  planned.
- `leagues.test.js` (4) pins the four codes, names and slugs; distinct
  intros; that no other path is a league; that no slug shadows a real
  route; and the title and description. `sitemap.test.js` covers leagues.
  85 web tests.

**Verified** on `vite preview` of the build, against a scratch API seeded
from `tests/test_match_api.py`:
- **curl:** all four leagues 200; a trailing slash 308; `/Premier-League`,
  `/national-league` and `/foo` 404; one of each head tag; all 11 match
  pages linked; the sitemap lists the league with its `lastmod`; the empty
  leagues show their empty-state lines.
- **A 12-check Playwright click-through:**
  - the intro, record and lists in the server's HTML;
  - the head tags;
  - the record line matching the API;
  - the upcoming order, and "call on matchday" for an uncalled fixture;
  - the zone switch;
  - results newest first, marked;
  - league → match → league by client-side links, with head tags
    following;
  - the footer's four links, footer → League Two with its empty states;
  - no page errors; no horizontal scroll at 390 px.
- The **2.3 click-through re-ran, 25/25**.
- Full Python suite **783 pass**. Scratch database dropped.

**Found while testing:** a Vite **dev** server on `[::1]:5173` and a uvicorn
on `:8000`, both started at 12:17 and not by this session, serve the
working tree. `localhost` resolves to the dev server first, so the checks
moved to `127.0.0.1`. **That uvicorn predates `/league` and `/fixture`**:
league and match pages return 500 in that dev stack until it is restarted.

- **Route:** one `routes/[league=league]/` with a param matcher
  (`src/params/league.js`) that accepts the four slugs only, so every other
  top-level path still 404s. The slugs, names and intros live in
  `$lib/leagues.js`.
- **API: `GET /league/{division}`**, one read per page:
  - `record`: the division's row from `/tips/record` `by_division`;
  - `upcoming`: fixtures dated today or later, each with its call if
    published;
  - `results`: the last 12 settled, with score, call and outcome.
  Every fixture carries `fixture_id`, `slug`, the display names and the
  date. No prices. 404 for a division that is not served.
- **Content:** intro, record line, then "Calls and upcoming fixtures"
  (called fixtures show the call; the rest show "call on matchday"), then
  "Recent results". Every fixture links to its match page.
- **Title:** "{League} Predictions & Tips | BabaVanga" (the plan's
  "…Predictions Today" is untrue on days with no calls).
- **Description:** "{League} predictions: one call for every match,
  published on matchday before kick-off and graded after. {graded} calls
  graded so far."
- **Intros (drafts, owner to edit).** They carry no figure that goes stale;
  the live counts are in the record line.
  - **Premier League:** "Our call for every Premier League match, published
    on matchday morning before kick-off and graded once the final whistle
    goes. Twenty clubs, 380 matches a season: each gets a single call, and
    every one counts toward the record below."
  - **Championship:** "The busiest division we cover: 24 clubs and 552
    league matches, midweek rounds included. Every fixture gets one call on
    matchday, published before kick-off, graded after, and never revised."
  - **League One:** "Every League One fixture, one call each: published on
    matchday before kick-off, graded once the result is in. Calls here, as
    everywhere on the site, are judged on how often they come in, not on
    any return."
  - **League Two:** "League Two's 24 clubs and 552 matches, each with a
    single call published before kick-off. Graded calls feed the record
    below, and each fixture's page carries recent form and past meetings."

### 2.5 Team pages (~1 day) — `/team/[team]/`

**Built 2026-09-21, uncommitted**, as specified below.

**API:**
- `GET /team/{team_id}`: display name, slug, `division` (from the club's
  latest served fixture, so a promoted or relegated side is filed under the
  league it plays in now), venue, `upcoming` in the league page's shape
  (`LISTED`/`_listed`, shared with 2.4), `calls` and `tally`. 404 for a club
  with no fixture in a served division.
- `_form` (2.3) and the team page's `calls` are now one query,
  **`_team_calls`**: the same row from the club's own side, the form being
  its last five before the match it sits on. The team page passes no upper
  bound (`NO_BOUND`), so a fixture played and graded earlier today is still
  listed; only the match page has a game it must stop short of. Form rows
  gained `division` and `slug` as a result — additive, and nothing reads
  them yet.
- `/fixture/{id}` gained `home_team_id`, `away_team_id`, `home_slug`,
  `away_slug`, so the match page's names can link (2.8).
- **`/sitemap/entries` is now `{matches, leagues, teams}`.** A team's
  `lastmod` is the latest of its own matches'. It lists a club that appears
  in a listed match, which is a subset of the clubs that have a page, so no
  listed URL 404s — pinned by a test that fetches every one.
- `api/teams.py` gained `team_slug`; `fixture_slug` is now two of them.
- `tests/test_match_api.py` +11, **43 in all**.

**Web:**
- `$lib/teams.js`: `teamPath`, title, description and `tallySentence` —
  counts, never a rate. `parseMatchParam` was renamed **`parseIdParam`**
  (`$lib/match.js`), because the team address parses by the same id-first
  rule (D9).
- `routes/team/[team]/`: `+page.js` id-first with a 301 to the canonical
  slug and the API's 404 as the page's; `+page.svelte` with the league
  kicker, venue, the tally line, next fixtures with their call or "call on
  matchday", and every settled call this season with its W/D/L, score and
  outcome. Every fixture links to its match page.
- The match page's two team names are now links to their team pages.
- `sitemap.js` lists the team pages. `teams.test.js` (3) and the sitemap
  tests cover it.
- **Team pages are not kept for offline**: 92 of them is past what the
  service worker's bounded list is for.

**Content decision:** the page shows the tally as counts and links to
`/record` for the rate, so no page carries a strike rate over a handful of
games.

- **Route:** `/team/{team_id}-{slug}` (D9). The id decides; other words
  301 to the current slug, as on match pages.
- **API: `GET /team/{team_id}`** replaces the plan's `/teams` and
  `/team/{id}/tips`, one read per page. It returns:
  - the display name, slug and current division (from its latest fixture);
  - the venue, when confirmed;
  - `upcoming`, in the league page's shape;
  - `calls`: every fixture involving the team this season with a settled
    call, newest first, with score, W/D/L from the team's side, our call
    and outcome;
  - `tally`: graded and won.
  404 for a team with no fixture in a served division.
- **Content:** next fixtures with their calls or "call on matchday"; "Our
  calls on {Team} this season: N graded, M came in", **as counts, never a
  rate** on so few; then each call with score and outcome. Every fixture
  links to its match page.
- **Title:** "{Team} Predictions & Record | BabaVanga". **Description:**
  "Our calls on {Team} this season: {graded} graded, {won} came in.
  Next: {Home} vs {Away}, {date}."
- Expect thin pages early in the season (4–8 calls today). They fill
  themselves every matchweek.

**Sitemap (extends 2.7):** `/sitemap/entries` becomes `{matches, leagues,
teams}`. The `lastmod` of a league or team page is the latest visible
change among its own fixtures, which is accurate by the same rule as the
match pages.

**Links (the part of 2.8 taken):**
- match pages link each team name to its team page and the league to its
  league page (so `/fixture` gains each team's id and slug);
- league and team pages link every fixture to its match page;
- the site footer lists the four leagues.

### 2.6 `/record` (and `/results`) as pages (D10)

**Built 2026-09-21, uncommitted.**

**Owner decisions, 2026-09-21:** **both** `/record` and `/results` become
pages, not `/record` alone — the settled list is its own search target, and
moving its controls off the front page takes their JavaScript with them. The
front page **keeps a short summary of each that links through**, rather than
a bare link card or a duplicate of the page.

- `routes/record/` and `routes/results/`, each reading on the server so its
  figures are in the HTML, each with its own error line rather than
  SvelteKit's error page: an outage must never render as "nothing graded
  yet".
- `/record` is the front page's `#record` section moved unchanged — the
  per-division table, the two honesty paragraphs, and, owner-only, the rule
  line and the split by version. Its `<h2>` became the page's `<h1>`.
- `/results` is the `#results` section moved unchanged: the cards, the
  division filter, the size switch, and "Scores & claims" off by default.
  **Its default is 60, not the front page's 12** (owner, 2026-09-21): a page
  of its own is somewhere to read the record call by call, and twelve is a
  summary's worth. 60 is also the API's own default for `/tips/results`.
  `routes/results/limit.js` holds the two numbers, because the loader and the
  toggle must ask for the same one or hydration refetches for nothing.
- **The front page keeps** the last six settled calls (no filter, no
  toggles) and a one-sentence record summary, each linking through. The
  `#results` and `#record` ids stay, so an old `/#record` link still lands
  on the summary that replaced the section.
- Nav: `sections` in `+layout.svelte` is now `[href, label, icon]`, Tips
  still `/#tips`, Results and Record their routes; `activeSection` marks an
  anchor current only on its own page. The hero's "Check the record" button
  points at `/record`.
- `STATIC_PATHS` in the sitemap gains both, with **no `lastmod`** for the
  same reason as `/` and `/parlay`. The service worker keeps both offline.
- **`?owner=1` moved with the detail it reveals**: `/record?owner=1`, not
  `/?owner=1`. A browser already set stays set (localStorage).

**Titles and descriptions (drafts, owner to edit — D4):**
- `/record`: "Our Prediction Record — Every Call, Graded | BabaVanga";
  description built from the live figure ("{won} of {graded} graded calls
  came in, {rate}, over {n} matchweeks. Every one was published before
  kick-off. A strike rate, not a return.").
- `/results`: "Latest Results — How Our Calls Went | BabaVanga"; "How our
  most recent calls went: the score each was graded from, whether it came
  in, and the same for every division from the Premier League to League
  Two."

**Verified (2.5 and 2.6 together)**, on `node build` behind an nginx
stand-in, against a scratch API seeded from `tests/test_match_api.py`:
- **curl:** the new pages 200; `/team/1` and `/team/1-wrong-words` 301 to
  the canonical slug; a club outside the served divisions, an unknown id and
  a non-numeric id 404; head tags, `<h1>` and the lists in the server's HTML;
  the sitemap is 22 URLs (4 static + 1 league + 6 teams + 11 matches) and
  **every one answers 200 with no redirect**.
- **A 39-check Playwright click-through:** the team page's tally, venue,
  "call on matchday", the season's calls newest first with result, score and
  outcome, the zone switch, team → match → team by client-side links with
  the head following; `/record`'s table, totals and honesty prose, and the
  owner flag on and off; `/results`' toggles and a division with nothing
  graded; the front page's six-card summary, its record line, no controls
  left on it, and both links through; the nav's routes and `aria-current`;
  no horizontal scroll at 390 px. The only console errors are Google
  sign-in refusing `127.0.0.1` as an origin.
- **An 18-check regression pass** over what 2.5/2.6 touched but did not set
  out to change: the front page's calls, drawer and tabs, the three old
  anchors, the league page and its links, the match page's form, meetings
  and structured data, `/parlay`, the footer.
- Tests: API 43, web 89, full Python suite **794 pass**; build clean, no
  warnings. Scratch database dropped.

**Deploy:** commit, then the normal `deploy.sh`. It restarts the API for
`/team/{id}`, rebuilds and restarts `bvp-web`. No nginx, unit or schema
change. Then: `curl -sI https://babavanga.net/record` and `/results` for
200; `curl -s https://babavanga.net/sitemap.xml | grep -c '<url>'` should
rise by the number of clubs plus 2; `curl -sI` one `/team/{id}` for a 301
to its slug; **re-submit nothing** — the sitemap address is unchanged, but
URL-inspect one team page and `/record` in Search Console.

### 2.7 The dynamic sitemap (~½ day) — `web/src/routes/sitemap.xml/+server.js`

**Built 2026-09-18, uncommitted.**
- `$lib/sitemap.js` (pure, 5 node tests) builds the urlset:
  - `/` and `/parlay` with **no `lastmod`**. Their content moves with every
    call, and the API only knows match pages' visible changes. An
    inaccurate date teaches Google to ignore the site's `lastmod`.
  - then each match page at `matchPath` with the API's `lastmod`;
  - XML-escaped; nothing internal; no `priority` or `changefreq`.
- `+server.js` reads `/sitemap/entries` through the request's `fetch`
  (`handleFetch` → uvicorn). It answers `application/xml`, cached for an
  hour. **If the API fails it answers 503 with `Retry-After: 600`**, never
  an empty list, which would read as every match page having gone.
- `robots.txt` gains `Sitemap: https://babavanga.net/sitemap.xml`; a test
  pins it to `ORIGIN`. Its `/api/` comment, stale since 2.1, is corrected.
- nginx is unchanged: there is no `sitemap.xml` file in `build/client`, so
  `try_files` hands the request to `@web`.

**Verified:**
- 80 web tests; build clean.
- `node build` against a scratch API seeded from `tests/test_match_api.py`:
  - 200, `application/xml; charset=utf-8`, `max-age=3600`;
  - parses as XML: 13 URLs, `/`, `/parlay` and exactly the API's 11 match
    pages, newest first, stale and unserved fixtures absent;
  - **every listed URL answers 200 with no redirect**;
  - with the API stopped, 503 with `Retry-After`.
- Scratch database dropped.

**Deploy (2.2 + 2.3 + 2.7 together):**
1. Commit, then the normal `deploy.sh`. It restarts the API for the new
   endpoints, rebuilds, and restarts `bvp-web`. No nginx, unit or schema
   change.
2. Verify:
   - `curl -s https://babavanga.net/sitemap.xml | head -5` shows the
     urlset;
   - `curl -s https://babavanga.net/sitemap.xml | grep -c '<url>'` is the
     number of match pages plus 2;
   - `curl -sI https://babavanga.net/robots.txt` then
     `curl -s https://babavanga.net/robots.txt | tail -1` shows the
     `Sitemap:` line;
   - take one `<loc>` from the sitemap, `curl -sI` it for 200, and open it
     in a browser;
   - `curl -sI https://babavanga.net/match/<id>` gives 301 to the full
     address.
3. Search Console:
   - Sitemaps → add `https://babavanga.net/sitemap.xml`; expect "Success"
     and discovered ≈ submitted within days.
   - URL-inspect one match page: "Test live URL" then "View tested page";
     the HTML should hold the call and the form.

- **Content:** from `/sitemap/entries`, the static pages, the four league
  pages, the team pages and the match pages per D8. It lists only pages that
  exist when it ships: in the 2.2/2.3/2.7 batch that is `/`, `/parlay` and
  the match pages. League and team pages join it with 2.4 and 2.5.
- **Format:** `<loc>` absolute (D3); `<lastmod>` as ISO 8601 UTC, defined
  in 2.2 (never the fixture's price-driven `updated_at`); no
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

**Built 2026-09-21, uncommitted** — the two links that were still not taken,
plus `/record` in the footer.

- **API:** `/tips` and `/tips/results` rows gained `slug` (`_with_page`), so
  the front page's links are the canonical address rather than a bare id
  that every crawl would follow through a 301. A test pins each row's slug
  against `/fixture`'s for the same id.
- **The call drawer** carries "Form, venue & past meetings →". It sits in
  the drawer head, not on the row, because the row is already the control
  that opens the drawer.
- **Every settled card is now a link** to its match page — the front page's
  six-card summary and `/results` alike. The card is the `<a>`, so the whole
  tile is the target.
- **The footer** lists the four leagues and now `/record`, so both are one
  link from any page on the site.

**Worth knowing, and not fixed here:**
- **The drawer link is not in the server's HTML.** The drawer renders only
  when it is open, so a crawler never sees that link and it is worth nothing
  for indexing — it is a reader's convenience. Upcoming fixtures' match
  pages are reached by a crawler through the league and team pages, which do
  carry them in their HTML, and through the sitemap. If the front page
  should feed them too, the link has to sit on the row itself; that is a
  layout decision for the owner, not a bug.
- **`/tips/results` is one row per tip, not per fixture.** A fixture called
  under two rule versions has two settled cards, and they now both link to
  the one match page. Harmless for search — but the list can show two
  contradictory graded calls for one match, where the match and league pages
  take the latest (review R5). Pre-existing; raised, not changed.

**Verified:** a **22-check Playwright click-through** (the drawer link
appears only with the drawer, is canonical, opens the match page without a
redirect, and the row still toggles; every settled card on both pages is a
link to a canonical address; the toggles still work now the card is an
anchor; the footer's `/record` from five different pages; no horizontal
scroll at 390 px), plus the 2.5/2.6 click-through re-run 39/39 and the
18-check regression pass. API 44, web 89, full suite **795 pass**.

Originally, and now built:
- The call drawer on the front page links to the match page.
- Settled cards link to their match page.
- The footer links to the four league pages and `/record`.
- Crawlers find pages mainly by following links. The sitemap is a hint, not
  a substitute.
- **Not in the 2.2/2.3/2.7 batch** (owner, 2026-09-18). Until this lands,
  the sitemap is the only way to reach a match page.
- **Partly taken with 2.4/2.5** (owner, 2026-09-18): the footer's league
  links, and links between match, league and team pages. The front page's
  call-drawer and settled-card links are still not taken.
- **Built with 2.5** (2026-09-21): the match page's two team names link to
  their team pages, and team pages link every fixture to its match page and
  the club's league to its league page. The settled cards stayed unlinked,
  on `/results` as on the front page, because that is the part of this task
  the owner has not taken — so the only route into a match page from the
  settled list is still the sitemap or a league page.

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
| baseline (1.0), 2026-09-17, after 1.1–1.6 were live | **48** / LCP **5.7 s** / TBT 130 ms (lab, in place of INP) / CLS **0.337** | not yet reported | not yet reported | not yet reported |
| after 1.10 + 2.1, 2026-09-18 | **69** / LCP **5.2 s** / TBT 140 ms / CLS **0.002** (FCP 3.8 s, Speed Index 4.4 s) | — | — | — |
| Phase 1 + 4 weeks | | | | |
| Phase 2 + 4 weeks | | | | |
| Phase 2 + 12 weeks | | | | |

**What holds LCP up now (2026-09-18, a local Lighthouse run on the live
site; its absolute numbers are this machine's, not PageSpeed's):**
- **The LCP element is still the hero `<h1>`**, but it is now in the
  server's HTML: load delay and load time are 0.
- LCP is **TTFB (36%) plus render delay (64%)**.
- The render delay is the **Google Fonts stylesheet**, the one
  render-blocking resource (~1.3 s estimated). It is a cross-origin CSS
  request that must finish before anything paints; the font files
  themselves use `display=swap` and do not block.
- The document took 710 ms from here, network included. How much of that
  is rendering on the VM is not yet measured.
- Also: 148 KiB of unused JavaScript, mostly Google Tag Manager (196 KB)
  and Google sign-in (159 KB); only Tag Manager blocks the main thread
  (84 ms).

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
