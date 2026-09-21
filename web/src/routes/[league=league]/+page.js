import { getLeague } from '$lib/api.js';
import { leagueBySlug } from '$lib/leagues.js';

// A league page (docs/SEO_PLAN.md 2.4). The param matcher has already
// refused anything that is not one of the four leagues.
export async function load({ params, fetch }) {
  const league = leagueBySlug(params.league);
  return { league, body: await getLeague(league.code, fetch) };
}
