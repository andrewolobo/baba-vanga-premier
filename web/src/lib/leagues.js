// The four league pages (docs/SEO_PLAN.md 2.4): address, name and intro.
// Pure, so the node runner can pin them.
//
// The intros are the owner's (approved 2026-09-18). Each page needs text of
// its own: four identical templates read as thin, duplicate content. They
// carry no figure that goes stale; the live counts are in the record line.

import { DIVISIONS } from './api.js';

const PAGES = [
  {
    code: 'E0',
    slug: 'premier-league',
    intro:
      'Our call for every Premier League match, published on matchday morning before kick-off and graded once the final whistle goes. Twenty clubs, 380 matches a season: each gets a single call, and every one counts toward the record below.'
  },
  {
    code: 'E1',
    slug: 'championship',
    intro:
      'The busiest division we cover: 24 clubs and 552 league matches, midweek rounds included. Every fixture gets one call on matchday, published before kick-off, graded after, and never revised.'
  },
  {
    code: 'E2',
    slug: 'league-one',
    intro:
      'Every League One fixture, one call each: published on matchday before kick-off, graded once the result is in. Calls here, as everywhere on the site, are judged on how often they come in, not on any return.'
  },
  {
    code: 'E3',
    slug: 'league-two',
    intro:
      "League Two's 24 clubs and 552 matches, each with a single call published before kick-off. Graded calls feed the record below, and each fixture's page carries recent form and past meetings."
  }
];

// Names from the same table the front page's tabs use, so the two agree.
export const LEAGUES = PAGES.map((p) => ({ ...p, name: DIVISIONS.find(([c]) => c === p.code)[1] }));

export const leagueBySlug = (slug) => LEAGUES.find((l) => l.slug === slug) ?? null;
export const leagueByCode = (code) => LEAGUES.find((l) => l.code === code) ?? null;
export const leaguePath = (code) => `/${leagueByCode(code).slug}`;

export const leagueTitle = (league) => `${league.name} Predictions & Tips | BabaVanga`;

export function leagueDescription(league, record) {
  const graded = record?.graded ? ` ${record.graded} calls graded so far.` : '';
  return `${league.name} predictions: one call for every match, published on matchday before kick-off and graded after.${graded}`;
}
