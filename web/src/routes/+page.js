import { getTips, getTipResults, getTipRecord } from '$lib/api.js';

// What the front page opens on: every league's calls, the last 12 results
// and the record (docs/SEO_PLAN.md 2.1). Runs on the server for the first
// request, so the calls are in the HTML, and in the browser on a move back
// from another page. A failed read renders the page's own error line, as it
// did when this ran on mount, rather than SvelteKit's error page.
export async function load({ fetch }) {
  try {
    const [tips, results, record] = await Promise.all([
      getTips(null, fetch),
      getTipResults(null, 12, fetch),
      getTipRecord(fetch)
    ]);
    return { tips, results, record, error: null };
  } catch (e) {
    return { tips: [], results: [], record: null, error: e.message };
  }
}
