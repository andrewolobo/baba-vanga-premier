// The site's public identity, for the tags that need an absolute URL or must
// say the same thing on every page (docs/SEO_PLAN.md D3, 1.5, 2.1).
//
// app.html is static HTML and cannot import this, so the origin in its share
// image and structured data is written out literally; `site.test.js` reads
// app.html and fails if the two drift. The tags that name a page are
// rendered from here by `PageHead.svelte`.

export const ORIGIN = 'https://babavanga.net';

export const HOME_TITLE = 'Football Predictions & Tips — EPL to League Two | BabaVanga';

// The owner's words (SEO_PLAN.md D4). Pages without a description of their
// own use this one, as every page did while it lived in app.html.
export const DESCRIPTION =
  'Predictions for every Premier League, Championship, League One and League Two match, published before kick-off and graded after.';
