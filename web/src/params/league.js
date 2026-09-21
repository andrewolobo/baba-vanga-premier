import { leagueBySlug } from '$lib/leagues.js';

// `/[league=league]` answers only for the four league slugs
// (docs/SEO_PLAN.md 2.4), so every other top-level path still 404s rather
// than being taken for a league.
export function match(param) {
  return leagueBySlug(param) !== null;
}
