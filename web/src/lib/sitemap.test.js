// node --test
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { sitemapXml, STATIC_PATHS } from './sitemap.js';
import { ORIGIN } from './site.js';

const entries = [
  { fixture_id: 268, slug: 'manchester-united-vs-nottingham-forest', lastmod: '2026-09-20T19:00:00Z' },
  { fixture_id: 7, slug: 'brighton-hove-albion-vs-chelsea', lastmod: '2026-09-18T06:05:00Z' }
];
const xml = sitemapXml(entries, ORIGIN);
const urls = [...xml.matchAll(/<url><loc>([^<]*)<\/loc>(?:<lastmod>([^<]*)<\/lastmod>)?<\/url>/g)]
  .map(([, loc, lastmod]) => ({ loc, lastmod }));

test('a sitemaps.org urlset, one <url> per page', () => {
  assert.match(xml, /^<\?xml version="1.0" encoding="UTF-8"\?>\n<urlset xmlns="http:\/\/www\.sitemaps\.org\/schemas\/sitemap\/0\.9">/);
  assert.match(xml, /<\/urlset>\n$/);
  assert.equal(xml.match(/<url>/g).length, STATIC_PATHS.length + entries.length);
  assert.equal(urls.length, STATIC_PATHS.length + entries.length);
});

test('match pages at their canonical address with the API lastmod', () => {
  assert.deepEqual(urls.slice(STATIC_PATHS.length), [
    { loc: `${ORIGIN}/match/268-manchester-united-vs-nottingham-forest`, lastmod: '2026-09-20T19:00:00Z' },
    { loc: `${ORIGIN}/match/7-brighton-hove-albion-vs-chelsea`, lastmod: '2026-09-18T06:05:00Z' }
  ]);
});

test('the front page and /parlay are listed with no lastmod, and nothing internal is', () => {
  assert.deepEqual(urls.slice(0, STATIC_PATHS.length), [
    { loc: `${ORIGIN}/`, lastmod: undefined },
    { loc: `${ORIGIN}/parlay`, lastmod: undefined }
  ]);
  assert.doesNotMatch(xml, /\/book|\/performance|priority|changefreq/);
});

test('text is escaped', () => {
  const odd = sitemapXml([{ fixture_id: 1, slug: 'a&b<c', lastmod: 'x' }], ORIGIN);
  assert.match(odd, /\/match\/1-a&amp;b&lt;c</);
});

test('robots.txt names the sitemap at the canonical origin, once', () => {
  const robots = readFileSync(new URL('../../static/robots.txt', import.meta.url), 'utf8');
  assert.deepEqual(robots.match(/^Sitemap: .*$/gm), [`Sitemap: ${ORIGIN}/sitemap.xml`]);
});
