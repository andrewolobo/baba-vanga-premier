import { error, redirect } from '@sveltejs/kit';
import { ApiError, getTeam } from '$lib/api.js';
import { parseIdParam } from '$lib/match.js';
import { teamPath } from '$lib/teams.js';

// One club's page (docs/SEO_PLAN.md 2.5), on the same rule as a match page
// (2.3): the id at the front of the address decides which club, the words
// after it are decoration (D9), and any other words get a permanent redirect
// to the current address. A club that is renamed keeps its links.
//
// The API decides which clubs have a page -- a fixture in a served division
// -- so 404 there is 404 here.
export async function load({ params, fetch }) {
  const id = parseIdParam(params.team);
  if (id === null) error(404, 'Not found');
  let team;
  try {
    team = await getTeam(id, fetch);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) error(404, 'Not found');
    throw e;
  }
  const path = teamPath(team.team_id, team.slug);
  if (`/team/${params.team}` !== path) redirect(301, path);
  return { team };
}
