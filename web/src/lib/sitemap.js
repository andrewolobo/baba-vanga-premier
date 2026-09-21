// sitemap.xml from the API's list of match pages (docs/SEO_PLAN.md 2.7).
// Pure, so the node runner can pin it.
//
// This is the "generates from the games that are playing" piece the owner
// asked for: each matchday's calls and each settlement move a match page's
// <lastmod>, which is what tells a crawler to come back to it. <lastmod> is
// only ever a time the page visibly changed (the API's rule, 2.2), so the
// front page and /parlay carry none: their content moves with every call,
// and a date that is not accurate is one Google learns to ignore site-wide.
// No <priority> or <changefreq>; Google reads neither.

import { matchPath } from './match.js';
import { leaguePath } from './leagues.js';
import { teamPath } from './teams.js';

// The pages the store does not generate. /record and /results joined them
// with 2.6. They carry no <lastmod> for the same reason as the front page:
// their content moves with every call, and only match pages have a date the
// API can state accurately. /book and /performance are internal and
// disallowed in robots.txt, so never listed.
export const STATIC_PATHS = ['/', '/parlay', '/record', '/results'];

const escapeXml = (s) =>
  s.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;');

const url = (loc, lastmod) =>
  `<url><loc>${escapeXml(loc)}</loc>${lastmod ? `<lastmod>${escapeXml(lastmod)}</lastmod>` : ''}</url>`;

// `entries` is the API's `/sitemap/entries`: `matches`, `leagues` (2.4) and
// `teams` (2.5). A league or a team is dated by the latest change among its
// own matches, which is the same rule and just as accurate.
export function sitemapXml(entries, origin) {
  const urls = [
    ...STATIC_PATHS.map((path) => url(`${origin}${path}`)),
    ...entries.leagues.map((l) => url(`${origin}${leaguePath(l.division)}`, l.lastmod)),
    ...entries.teams.map((t) => url(`${origin}${teamPath(t.team_id, t.slug)}`, t.lastmod)),
    ...entries.matches.map((e) => url(`${origin}${matchPath(e)}`, e.lastmod))
  ];
  return [
    '<?xml version="1.0" encoding="UTF-8"?>',
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ...urls,
    '</urlset>',
    ''
  ].join('\n');
}
