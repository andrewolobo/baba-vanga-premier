// The "bet this on betPawa" button (docs/BETPAWA_PLAN.md, B26). Display
// only: the API has already chosen the user's betPawa site from the country
// their phone was captured under and built a link per side it holds
// (`GET /betpawa/links`); this module indexes that body, picks the link for a
// call, and joins a slip's selection ids into the one prefill URL the parlay
// page needs. No probability, no price -- the site shows no odds (D9).
import { get, callLabel } from './api.js';
import { ukInstant } from './kickoff.js';

export const getBetpawaLinks = () => get('/betpawa/links');

// The bet a +1.5 call falls back to when betPawa has no line for it: the same
// team's double chance. The ladder is one-sided, so a missing +1.5 is the
// market favourite's, priced too short to list; its double chance is always
// on the book. It wins on a strict subset of what the call wins on -- it loses
// only a one-goal defeat the call survives -- so whenever this bet wins, the
// graded call has won too. Deliberately not the next-likeliest market: that
// is `12` for nearly every handicap call, which loses on the draw the call
// wins on (checked on 2026-09-26's calls, 9 of 9).
const NEAREST = { 'H+1.5': '1X', 'A+1.5': 'X2' };

// The body, keyed by fixture so a row can find its own entry in O(1).
export const indexLinks = (body) => ({
  eligible: body?.eligible === true,
  host: body?.host ?? null,
  byFixture: Object.fromEntries((body?.links ?? []).map((l) => [String(l.fixture_id), l]))
});

// What the button on one call links to: the wager itself when the book
// carried that side at the last scrape; for a +1.5 call it did not carry, the
// same team's double chance (`NEAREST`, with the `side` it loads); otherwise
// the event page (D11); nothing when the scrape never matched the fixture.
export const wagerLink = (byFixture, fixtureId, side) => {
  const link = byFixture?.[String(fixtureId)];
  if (!link) return null;
  const chosen = link.sides?.[side];
  if (chosen?.url) return { kind: 'wager', url: chosen.url };
  const near = link.sides?.[NEAREST[side]];
  if (near?.url) return { kind: 'nearest', side: NEAREST[side], url: near.url };
  return link.event_url ? { kind: 'event', url: link.event_url } : null;
};

// The button's text. A substitute names the bet it actually loads, so it
// cannot be taken for the call.
export const wagerLabel = (bet, home, away) =>
  bet?.kind === 'nearest'
    ? `Closest on betPawa: ${callLabel(bet.side, home, away)}`
    : ({ wager: 'Bet this on betPawa', event: 'See on betPawa' })[bet?.kind] ?? null;

// Beside a substitute: the one result on which it and the +1.5 part ways.
// Says "the +1.5", not "our call": a derived parlay leg is not the call.
export const nearestNote = (side, home, away) => {
  const team = side === 'H+1.5' ? home : away;
  return `No ${team} +1.5 on betPawa. This loses if ${team} lose by one goal; the +1.5 would not.`;
};

// Mirrors `api/betpawa.py` `prefill_url`, verified against the live site on
// 2026-09-08: a comma list across events is an accumulator.
export const prefillUrl = (host, selectionIds) =>
  `https://${host}/external-prefill?selectionIds=${selectionIds.join(',')}`;

// What one call or leg loads into a slip: its own side's selection, or for a
// +1.5 the book has no line for, the same team's double chance (`NEAREST`,
// the per-call rule), with the label the copy names it by; null when neither
// is on the book.
const selectionFor = (byFixture, row) => {
  const sides = byFixture?.[String(row.fixture_id)]?.sides;
  const own = sides?.[row.side]?.selection_id;
  if (own) return { id: own, substitute: null };
  const near = sides?.[NEAREST[row.side]]?.selection_id;
  return near ? { id: near, substitute: callLabel(NEAREST[row.side], row.home_team, row.away_team) } : null;
};

// The parlay slip as one link (BETPAWA_PLAN.md §9). Every leg loads its own
// side -- a derived leg's side is the derived one -- or its substitute, named;
// a leg with neither is left out and named. The page says what that does to
// the claimed figure, which is for exactly the legs it shows. Returns `{ url,
// loaded, substituted: [labels], missing: [names] }`; `url` is null when
// nothing is loadable.
export const slipLink = (host, legs, byFixture) => {
  const ids = [];
  const substituted = [];
  const missing = [];
  for (const leg of legs ?? []) {
    const pick = selectionFor(byFixture, leg);
    if (!pick) missing.push(`${leg.home_team} v ${leg.away_team}`);
    else {
      ids.push(pick.id);
      if (pick.substitute) substituted.push(pick.substitute);
    }
  }
  return { url: host && ids.length ? prefillUrl(host, ids) : null, loaded: ids.length, substituted, missing };
};

// Every call in the list as one betslip (BETPAWA_PLAN.md 6, D13/D14; §8). A
// basket: a +1.5 the book has no line for loads as its substitute and is
// *named*; a call with neither is left out and named; and a call whose UK
// kick-off has passed is left out and counted -- betPawa drops an expired
// selection silently, and the count on the button must be true. Returns
// `{ url, loaded, substituted: [labels], skipped: [names], kickedOff }`;
// `url` is null when nothing is loadable.
export const daySlip = (host, tips, byFixture, now) => {
  const ids = [];
  const substituted = [];
  const skipped = [];
  let kickedOff = 0;
  for (const t of tips ?? []) {
    const instant = ukInstant(t.match_date, t.kickoff_time);
    if (instant && instant <= now) {
      kickedOff += 1;
      continue;
    }
    const pick = selectionFor(byFixture, t);
    if (!pick) skipped.push(`${t.home_team} v ${t.away_team}`);
    else {
      ids.push(pick.id);
      if (pick.substitute) substituted.push(pick.substitute);
    }
  }
  return {
    url: host && ids.length ? prefillUrl(host, ids) : null,
    loaded: ids.length,
    substituted,
    skipped,
    kickedOff
  };
};
