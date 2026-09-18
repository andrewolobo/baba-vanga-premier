import { error, redirect } from '@sveltejs/kit';
import { ApiError, getFixture } from '$lib/api.js';
import { matchPath, parseMatchParam } from '$lib/match.js';

// One fixture's page (docs/SEO_PLAN.md 2.3). The id at the front of the
// address decides which fixture; the words after it are decoration (D9), so
// any other words -- a typo, a pre-rename slug, none at all -- get a
// permanent redirect to the current address, and a link never breaks.
//
// The API decides which fixtures have a page (D8): 404 there is 404 here.
export async function load({ params, fetch }) {
  const id = parseMatchParam(params.match);
  if (id === null) error(404, 'Not found');
  let fixture;
  try {
    fixture = await getFixture(id, fetch);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) error(404, 'Not found');
    throw e;
  }
  const path = matchPath(fixture);
  if (`/match/${params.match}` !== path) redirect(301, path);
  return { fixture };
}
