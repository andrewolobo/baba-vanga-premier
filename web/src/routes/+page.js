import { getTips, getTipResults, getTipRecord, getNextFixtures } from '$lib/api.js';

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
    // Only when there is nothing to list: the empty state names the next
    // fixture date, and that date lives in the fixture feed rather than in
    // the tip list, which is empty by construction here. Asked for after the
    // fact rather than alongside, so the usual case -- calls published --
    // pays nothing for a line it will not render. Its own failure is not the
    // page's: the empty state reads correctly without a date.
    const next = tips.length === 0 ? await getNextFixtures(null, fetch).catch(() => null) : null;
    return { tips, results, record, next, error: null };
  } catch (e) {
    return { tips: [], results: [], record: null, next: null, error: e.message };
  }
}
