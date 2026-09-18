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

// The pages that are not matches. /book and /performance are internal and
// disallowed in robots.txt, so never listed.
export const STATIC_PATHS = ['/', '/parlay'];

const escapeXml = (s) =>
  s.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;');

const url = (loc, lastmod) =>
  `<url><loc>${escapeXml(loc)}</loc>${lastmod ? `<lastmod>${escapeXml(lastmod)}</lastmod>` : ''}</url>`;

export function sitemapXml(entries, origin) {
  const urls = [
    ...STATIC_PATHS.map((path) => url(`${origin}${path}`)),
    ...entries.map((e) => url(`${origin}${matchPath(e)}`, e.lastmod))
  ];
  return [
    '<?xml version="1.0" encoding="UTF-8"?>',
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ...urls,
    '</urlset>',
    ''
  ].join('\n');
}
