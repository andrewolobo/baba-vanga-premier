import { getTipRecord } from '$lib/api.js';

// The record as its own page (docs/SEO_PLAN.md 2.6, D10): the trust asset,
// so it gets an address that can be linked, shared and indexed rather than
// an anchor inside the front page. Read on the server, so the figures are in
// the HTML.
//
// A failed read renders the page's own error line, as the section did while
// it lived on the front page, rather than SvelteKit's error page: an outage
// must not be presented as an absence of a record.
export async function load({ fetch }) {
  try {
    return { record: await getTipRecord(fetch), error: null };
  } catch (e) {
    return { record: null, error: e.message };
  }
}
