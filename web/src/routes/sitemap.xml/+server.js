import { get } from '$lib/api.js';
import { ORIGIN } from '$lib/site.js';
import { sitemapXml } from '$lib/sitemap.js';

// /sitemap.xml (docs/SEO_PLAN.md 2.7), built per request from the API's
// list of match pages. `fetch` is the request's own, so `hooks.server.js`
// sends it straight to uvicorn.
//
// If the API cannot answer, this answers 503 rather than a sitemap with no
// matches in it: a crawler retries a 503 later, whereas an empty list reads
// as every match page having gone.
export async function GET({ fetch }) {
  let entries;
  try {
    entries = await get('/sitemap/entries', {}, fetch);
  } catch {
    return new Response('sitemap temporarily unavailable\n', {
      status: 503,
      headers: { 'content-type': 'text/plain; charset=utf-8', 'retry-after': '600' }
    });
  }
  return new Response(sitemapXml(entries, ORIGIN), {
    headers: {
      'content-type': 'application/xml; charset=utf-8',
      // An hour: calls land at 06:00 and settle through the day, so nothing
      // a crawler acts on moves faster than this.
      'cache-control': 'max-age=3600'
    }
  });
}
