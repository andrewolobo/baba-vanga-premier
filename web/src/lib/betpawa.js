// The "bet this on betPawa" button (docs/BETPAWA_PLAN.md, B26). Display
// only: the API has already chosen the user's betPawa site from the country
// their phone was captured under and built a link per side it holds
// (`GET /betpawa/links`); this module indexes that body, picks the link for a
// call, and joins a slip's selection ids into the one prefill URL the parlay
// page needs. No probability, no price -- the site shows no odds (D9).
import { get } from './api.js';

export const getBetpawaLinks = () => get('/betpawa/links');

// The body, keyed by fixture so a row can find its own entry in O(1).
export const indexLinks = (body) => ({
  eligible: body?.eligible === true,
  host: body?.host ?? null,
  byFixture: Object.fromEntries((body?.links ?? []).map((l) => [String(l.fixture_id), l]))
});

// What the button on one call links to: the wager itself when the book
// carried that side at the last scrape, the event page when it did not
// (D11: the +1.5 ladder is one-sided, so the model's underdog can lack a
// line), nothing when the scrape never matched the fixture.
export const wagerLink = (byFixture, fixtureId, side) => {
  const link = byFixture?.[String(fixtureId)];
  if (!link) return null;
  const chosen = link.sides?.[side];
  if (chosen?.url) return { kind: 'wager', url: chosen.url };
  return link.event_url ? { kind: 'event', url: link.event_url } : null;
};

export const wagerLabel = (kind) =>
  ({ wager: 'Bet this on betPawa', event: 'See on betPawa' })[kind] ?? null;

// Mirrors `api/betpawa.py` `prefill_url`, verified against the live site on
// 2026-09-08: a comma list across events is an accumulator.
export const prefillUrl = (host, selectionIds) =>
  `https://${host}/external-prefill?selectionIds=${selectionIds.join(',')}`;

// The parlay slip as one link. Every leg needs a selection for *its* side --
// a derived leg's side is the derived one -- and a slip with a gap is not
// offered at all, with the legs that lack a line named, rather than a
// shorter slip nobody asked for.
export const slipLink = (host, legs, byFixture) => {
  const missing = [];
  const ids = [];
  for (const leg of legs) {
    const id = byFixture?.[String(leg.fixture_id)]?.sides?.[leg.side]?.selection_id;
    if (id) ids.push(id);
    else missing.push(`${leg.home_team} v ${leg.away_team}`);
  }
  if (!host || legs.length === 0 || missing.length) return { url: null, missing };
  return { url: prefillUrl(host, ids), missing };
};
