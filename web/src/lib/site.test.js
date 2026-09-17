// node --test
//
// app.html cannot import site.js, so the two carry the same strings by hand
// (docs/SEO_PLAN.md 1.5). A drift is silent in the browser -- the page's own
// <svelte:head> overwrites the title once it renders -- and shows only to
// link previewers and crawlers that never run the page. These read both.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { ORIGIN, HOME_TITLE } from './site.js';

const html = readFileSync(new URL('../app.html', import.meta.url), 'utf8');
const decode = (s) => s.replaceAll('&amp;', '&');
const meta = (property) =>
  decode(html.match(new RegExp(`property="${property}" content="([^"]*)"`))?.[1] ?? '');

test("app.html's title and og:title are the homepage title in site.js", () => {
  assert.equal(decode(html.match(/<title>([^<]*)<\/title>/)[1]), HOME_TITLE);
  assert.equal(meta('og:title'), HOME_TITLE);
});

test('every absolute link to the site in app.html uses the canonical origin', () => {
  const urls = html.match(/https?:\/\/(?:www\.)?babavanga\.net[^"\s]*/g);
  assert.ok(urls.length >= 5);
  for (const url of urls) assert.ok(url.startsWith(`${ORIGIN}/`), url);
  assert.equal(meta('og:url'), `${ORIGIN}/`);
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

test('app.html carries no canonical: each route sets its own', () => {
  // One here would apply to every route and tell Google /parlay is a copy of /.
  assert.doesNotMatch(html, /rel="canonical"/);
});

test("app.html's structured data is valid JSON", () => {
  const ld = html.match(/<script type="application\/ld\+json">([\s\S]*?)<\/script>/)[1];
  const types = JSON.parse(ld)['@graph'].map((node) => node['@type']);
  assert.deepEqual(types, ['Organization', 'WebSite']);
});
