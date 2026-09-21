// A team page's address and words (docs/SEO_PLAN.md 2.5). Pure, so the node
// runner can pin them.
//
// The address is id-first, like a match page's (D9): the id decides which
// club, the words after it are decoration, and a club that is renamed 301s
// to its new spelling instead of losing the link. `parseIdParam`
// ($lib/match.js) reads both.

import { longDate } from './match.js';

// `/team/14-manchester-united`
export const teamPath = (id, slug) => `/team/${id}-${slug}`;

export const teamTitle = (team) => `${team.name} Predictions & Record | BabaVanga`;

// Counts, never a rate (2.5). Four or five graded calls is what a club has
// early in a season, and a percentage on that many would claim a precision
// the sample cannot carry. The pooled rate is on /record, where the whole
// published history stands behind it.
export function tallySentence(team) {
  const { graded, won } = team.tally;
  return graded
    ? `Our calls on ${team.name} this season: ${graded} graded, ${won} came in.`
    : `No call on ${team.name} has been graded yet this season.`;
}

export function teamDescription(team) {
  const next = team.upcoming[0];
  const when = next
    ? ` Next: ${next.home_name} vs ${next.away_name}, ${longDate(next.match_date)}.`
    : '';
  return `${tallySentence(team)}${when}`;
}
