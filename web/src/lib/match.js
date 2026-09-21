// The match page's words, address and structured data (docs/SEO_PLAN.md 2.3).
// Pure, so the node runner can pin them.
//
// Dates are written out by hand rather than through `Intl`: the page is
// rendered by Node on the server and hydrated by the visitor's browser, and
// two ICU builds can disagree ("Sep" or "Sept"). A text mismatch is not
// repaired on hydration, so the server's version would simply stay.

import { callLabel, DIVISIONS } from './api.js';
import { ukInstant } from './kickoff.js';

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const DAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

const parts = (iso) => iso.split('-').map(Number);

// "20 Sep 2026"
export function longDate(iso) {
  const [y, m, d] = parts(iso);
  return `${d} ${MONTHS[m - 1]} ${y}`;
}

// "Sat 20 Sep"
export function shortDay(iso) {
  const [y, m, d] = parts(iso);
  return `${DAYS[new Date(Date.UTC(y, m - 1, d)).getUTCDay()]} ${d} ${MONTHS[m - 1]}`;
}

export const divisionName = (code) => DIVISIONS.find(([c]) => c === code)?.[1] ?? code;

// `/match/268-manchester-united-vs-nottingham-forest`. The id decides which
// fixture; the words are the API's `slug` (D9), and any other words redirect.
export const matchPath = (fx) => `/match/${fx.fixture_id}-${fx.slug}`;

// The id at the front of the route parameter, or null when there is none.
// Both the match and the team address are id-first (D9), so both parse here.
export function parseIdParam(param) {
  const m = /^(\d+)(?:-|$)/.exec(param ?? '');
  return m ? Number(m[1]) : null;
}

// 'upcoming' (no call yet), 'live' (called, not settled) or 'settled'.
export function matchState(fx) {
  if (!fx.tip) return 'upcoming';
  return fx.tip.settled_at ? 'settled' : 'live';
}

export const outcomeWords = (outcome) =>
  ({ win: 'came in', lose: 'did not come in', void: 'was void' })[outcome] ?? 'is not graded yet';

export const callPhrase = (fx) => callLabel(fx.tip.side, fx.home_name, fx.away_name);

export const pageTitle = (fx) =>
  `${fx.home_name} vs ${fx.away_name} Prediction, ${longDate(fx.match_date)} | BabaVanga`;

// One sentence or two, per state, for the meta description and link previews.
export function pageDescription(fx) {
  const game = `${fx.home_name} vs ${fx.away_name}`;
  const when = `${divisionName(fx.division)}, ${shortDay(fx.match_date)} ${parts(fx.match_date)[0]}`;
  const state = matchState(fx);
  if (state === 'upcoming') {
    return `${game}, ${when}. Our call is published on matchday at 06:00 UTC, before kick-off. Recent form and past meetings are here now.`;
  }
  if (state === 'live') {
    return `Our call for ${game} (${when}): ${callPhrase(fx)}. Published before kick-off and graded after the match.`;
  }
  const t = fx.tip;
  const score = t.fthg == null ? game : `${fx.home_name} ${t.fthg}–${t.ftag} ${fx.away_name}`;
  return `${score} (${when}). Our call, ${callPhrase(fx)}, ${outcomeWords(t.outcome)}.`;
}

// A side's recent game from its own point of view.
export function formGame(g) {
  const scored = g.at_home ? g.fthg : g.ftag;
  const conceded = g.at_home ? g.ftag : g.fthg;
  return {
    opponent: g.at_home ? g.away_name : g.home_name,
    where: g.at_home ? 'v' : 'at',
    score: scored == null ? '–' : `${scored}–${conceded}`
  };
}

// Our calls on those games, as counts (2.5: a rate on five games would imply
// a skill the sample cannot show). Voids are neither.
export function formTally(games) {
  const graded = games.filter((g) => g.outcome === 'win' || g.outcome === 'lose');
  return { won: graded.filter((g) => g.outcome === 'win').length, graded: graded.length };
}

// schema.org SportsEvent, as a <script> for the head. `<` is escaped so no
// name can close the element early.
export function sportsEventScript(fx, origin) {
  const start = ukInstant(fx.match_date, fx.kickoff_time);
  const event = {
    '@context': 'https://schema.org',
    '@type': 'SportsEvent',
    name: `${fx.home_name} vs ${fx.away_name}`,
    sport: 'Football',
    url: `${origin}${matchPath(fx)}`,
    startDate: start ? start.toISOString().replace('.000Z', 'Z') : fx.match_date,
    homeTeam: { '@type': 'SportsTeam', name: fx.home_name },
    awayTeam: { '@type': 'SportsTeam', name: fx.away_name },
    ...(fx.venue ? { location: { '@type': 'Place', name: fx.venue } } : {})
  };
  const json = JSON.stringify(event).replaceAll('<', '\\u003c');
  return `<script type="application/ld+json">${json}</script>`;
}
