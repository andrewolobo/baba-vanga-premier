// node --test
//
// app.html cannot import site.js, so the two carry the same origin by hand
// (docs/SEO_PLAN.md 1.5). A drift is silent in the browser and shows only to
// link previewers and crawlers. Since pages are server-rendered (2.1), the
// tags that name a page come from PageHead.svelte and must not also be in
// app.html, which would put the homepage's first in every page's HTML.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync, readdirSync } from 'node:fs';
import { ORIGIN } from './site.js';

const html = readFileSync(new URL('../app.html', import.meta.url), 'utf8');

// The tags that name a page, each of which a page must carry exactly once.
const PAGE_TAGS = [
  /<title>/g,
  /name="description"/g,
  /rel="canonical"/g,
  /property="og:title"/g,
  /property="og:description"/g,
  /property="og:url"/g
];

test('app.html carries none of the tags that name a page', () => {
  // One here would apply to every route: /parlay would ship the homepage's
  // title first, and a canonical would tell Google it is a copy of /.
  for (const tag of PAGE_TAGS) assert.doesNotMatch(html, tag);
});

test("each of SvelteKit's placeholders appears in app.html exactly once", () => {
  // SvelteKit fills the FIRST occurrence. Written once inside a comment, the
  // page's head tags landed in that comment, the hydration marker closed it
  // early, and the browser rendered every tag a second time.
  for (const placeholder of ['%sveltekit.head%', '%sveltekit.body%']) {
    assert.equal(html.split(placeholder).length - 1, 1, placeholder);
  }
});

test('PageHead renders each of those tags once', () => {
  const head = readFileSync(new URL('./PageHead.svelte', import.meta.url), 'utf8');
  for (const tag of PAGE_TAGS) assert.equal(head.match(tag)?.length, 1, String(tag));
});

test('every public page renders PageHead once and sets none of its tags itself', () => {
  // /book and /performance are internal, disallowed in robots.txt and unlinked.
  const routes = new URL('../routes/', import.meta.url);
  const pages = readdirSync(routes, { recursive: true })
    .map((f) => f.replaceAll('\\', '/'))
    .filter((f) => f.endsWith('+page.svelte') && !/^(book|performance)\//.test(f));
  assert.ok(pages.includes('+page.svelte') && pages.includes('parlay/+page.svelte'));
  for (const page of pages) {
    const src = readFileSync(new URL(page, routes), 'utf8');
    assert.equal(src.match(/<PageHead\b/g)?.length, 1, page);
    for (const tag of PAGE_TAGS) assert.doesNotMatch(src, tag, `${page} ${tag}`);
  }
});

test('every absolute link to the site in app.html uses the canonical origin', () => {
  const urls = html.match(/https?:\/\/(?:www\.)?babavanga\.net[^"\s]*/g);
  assert.ok(urls.length >= 5);
  for (const url of urls) assert.ok(url.startsWith(`${ORIGIN}/`), url);
});

test('every site file app.html names exists in web/static', () => {
  // A typo in og:image breaks every link preview and nothing on the page shows it.
  const files = html.match(/https:\/\/babavanga\.net\/[^"#\s]+\.\w+(?=")/g);
  assert.ok(files.includes(`${ORIGIN}/og-image.jpg`));
  for (const url of files) {
    const path = new URL(`../../static${url.slice(ORIGIN.length)}`, import.meta.url);
    assert.ok(existsSync(path), url);
  }
});

test("app.html's structured data is valid JSON", () => {
  const ld = html.match(/<script type="application\/ld\+json">([\s\S]*?)<\/script>/)[1];
  const types = JSON.parse(ld)['@graph'].map((node) => node['@type']);
  assert.deepEqual(types, ['Organization', 'WebSite']);
});
