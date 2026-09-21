// The site's public identity, for the tags that need an absolute URL or must
// say the same thing on every page (docs/SEO_PLAN.md D3, 1.5, 2.1).
//
// app.html is static HTML and cannot import this, so the origin in its share
// image and structured data is written out literally; `site.test.js` reads
// app.html and fails if the two drift. The tags that name a page are
// rendered from here by `PageHead.svelte`.

import { pct } from './api.js';

export const ORIGIN = 'https://babavanga.net';

export const HOME_TITLE = 'Football Predictions & Tips — EPL to League Two | BabaVanga';

// The owner's words (SEO_PLAN.md D4). Pages without a description of their
// own use this one, as every page did while it lived in app.html.
export const DESCRIPTION =
  'Predictions for every Premier League, Championship, League One and League Two match, published before kick-off and graded after.';

// The site's own two other pages (docs/SEO_PLAN.md 2.6, D10). Drafts: the
// owner's words decide (D4). `/record` is the trust asset, so its description
// carries the live figure rather than a claim about it; both are kept inside
// the ~155 characters a search result shows before it truncates.
export const RECORD_TITLE = 'Our Prediction Record — Every Call, Graded | BabaVanga';

export function recordDescription(record) {
  if (!record?.graded) {
    return 'Every call we publish is written down before kick-off and graded from the result. Nothing is added later and nothing is removed.';
  }
  return (
    `${record.won} of ${record.graded} graded calls came in, ${pct(record.strike_rate, 1)}, ` +
    `over ${record.matchweeks} matchweeks. Every one was published before kick-off. ` +
    'A strike rate, not a return.'
  );
}

export const RESULTS_TITLE = 'Latest Results — How Our Calls Went | BabaVanga';

export const RESULTS_DESCRIPTION =
  'How our most recent calls went: the score each was graded from, whether it came in, and the same for every division from the Premier League to League Two.';
