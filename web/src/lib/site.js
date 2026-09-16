// The site's public identity, for the tags that need an absolute URL or must
// say the same thing as `web/src/app.html` (docs/SEO_PLAN.md D3, 1.5, 1.6).
//
// app.html is static HTML and cannot import this, so it carries the same
// origin and homepage title literally -- it has to, because link previewers
// and non-rendering crawlers read that file and nothing else. `site.test.js`
// reads app.html and fails if the two drift.

export const ORIGIN = 'https://babavanga.net';

export const HOME_TITLE = 'Football Predictions & Tips — EPL to League Two | BabaVanga';
