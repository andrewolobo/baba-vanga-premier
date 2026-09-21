// node --test
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { sitemapXml, STATIC_PATHS } from './sitemap.js';
import { ORIGIN } from './site.js';

const matches = [
  { fixture_id: 268, slug: 'manchester-united-vs-nottingham-forest', lastmod: '2026-09-20T19:00:00Z' },
  { fixture_id: 7, slug: 'brighton-hove-albion-vs-chelsea', lastmod: '2026-09-18T06:05:00Z' }
];
const leagues = [
  { division: 'E0', lastmod: '2026-09-20T19:00:00Z' },
  { division: 'E3', lastmod: '2026-09-18T06:05:00Z' }
];
const teams = [
  { team_id: 14, slug: 'manchester-united', lastmod: '2026-09-20T19:00:00Z' },
  { team_id: 3, slug: 'chelsea', lastmod: '2026-09-18T06:05:00Z' }
];
const xml = sitemapXml({ matches, leagues, teams }, ORIGIN);
const urls = [...xml.matchAll(/<url><loc>([^<]*)<\/loc>(?:<lastmod>([^<]*)<\/lastmod>)?<\/url>/g)]
  .map(([, loc, lastmod]) => ({ loc, lastmod }));
const BEFORE_TEAMS = STATIC_PATHS.length + leagues.length;
const BEFORE_MATCHES = BEFORE_TEAMS + teams.length;
const PAGES = BEFORE_MATCHES + matches.length;

test('a sitemaps.org urlset, one <url> per page', () => {
  assert.match(xml, /^<\?xml version="1.0" encoding="UTF-8"\?>\n<urlset xmlns="http:\/\/www\.sitemaps\.org\/schemas\/sitemap\/0\.9">/);
  assert.match(xml, /<\/urlset>\n$/);
  assert.equal(xml.match(/<url>/g).length, PAGES);
  assert.equal(urls.length, PAGES);
});

test('league pages at their address with their lastmod', () => {
  assert.deepEqual(urls.slice(STATIC_PATHS.length, BEFORE_TEAMS), [
    { loc: `${ORIGIN}/premier-league`, lastmod: '2026-09-20T19:00:00Z' },
    { loc: `${ORIGIN}/league-two`, lastmod: '2026-09-18T06:05:00Z' }
  ]);
});

test('team pages at their id-first address with their lastmod', () => {
  assert.deepEqual(urls.slice(BEFORE_TEAMS, BEFORE_MATCHES), [
    { loc: `${ORIGIN}/team/14-manchester-united`, lastmod: '2026-09-20T19:00:00Z' },
    { loc: `${ORIGIN}/team/3-chelsea`, lastmod: '2026-09-18T06:05:00Z' }
  ]);
});

test('match pages at their canonical address with the API lastmod', () => {
  assert.deepEqual(urls.slice(BEFORE_MATCHES), [
    { loc: `${ORIGIN}/match/268-manchester-united-vs-nottingham-forest`, lastmod: '2026-09-20T19:00:00Z' },
    { loc: `${ORIGIN}/match/7-brighton-hove-albion-vs-chelsea`, lastmod: '2026-09-18T06:05:00Z' }
  ]);
});

test('the pages the store does not generate are listed with no lastmod, and nothing internal is', () => {
  // A lastmod none of them has an accurate one for is a date Google learns to
  // ignore for the whole site (2.7).
  assert.deepEqual(urls.slice(0, STATIC_PATHS.length), [
    { loc: `${ORIGIN}/`, lastmod: undefined },
    { loc: `${ORIGIN}/parlay`, lastmod: undefined },
    { loc: `${ORIGIN}/record`, lastmod: undefined },
    { loc: `${ORIGIN}/results`, lastmod: undefined }
  ]);
  assert.doesNotMatch(xml, /\/book|\/performance|priority|changefreq/);
});

test('text is escaped', () => {
  const odd = sitemapXml(
    { matches: [{ fixture_id: 1, slug: 'a&b<c', lastmod: 'x' }], leagues: [], teams: [] },
    ORIGIN
  );
  assert.match(odd, /\/match\/1-a&amp;b&lt;c</);
});

test('robots.txt names the sitemap at the canonical origin, once', () => {
  const robots = readFileSync(new URL('../../static/robots.txt', import.meta.url), 'utf8');
  assert.deepEqual(robots.match(/^Sitemap: .*$/gm), [`Sitemap: ${ORIGIN}/sitemap.xml`]);
});
