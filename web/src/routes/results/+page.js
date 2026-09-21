import { getTipResults } from '$lib/api.js';
import { DEFAULT_LIMIT } from './limit.js';

// The settled list as its own page (docs/SEO_PLAN.md 2.6). The first sixty
// are read on the server so they are in the HTML; the division filter and
// the show-all toggle read again in the browser, as they did on the front
// page.
//
// A failed read renders the page's own error line rather than SvelteKit's
// error page: an empty list from an outage must not read as "nothing graded
// yet".
export async function load({ fetch }) {
  try {
    return { results: await getTipResults(null, DEFAULT_LIMIT, fetch), error: null };
  } catch (e) {
    return { results: [], error: e.message };
  }
}
