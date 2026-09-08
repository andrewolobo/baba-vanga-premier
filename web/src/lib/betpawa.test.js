// node --test
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { indexLinks, wagerLink, wagerLabel, prefillUrl, slipLink } from './betpawa.js';

const KE = 'www.betpawa.co.ke';
const body = {
  eligible: true,
  country: 'KE',
  host: KE,
  links: [
    {
      fixture_id: 212,
      event_id: '37536526',
      event_url: `https://${KE}/event/37536526?filter=all`,
      sides: {
        H: { selection_id: '1537500854', url: `https://${KE}/external-prefill?selectionIds=1537500854` },
        '1X': { selection_id: '1537500845', url: `https://${KE}/external-prefill?selectionIds=1537500845` },
        'A+1.5': { selection_id: '1539591711', url: `https://${KE}/external-prefill?selectionIds=1539591711` }
      }
    },
    {
      // Wrexham v Burnley on the first live run: the published H+1.5 had no line.
      fixture_id: 214,
      event_id: '37558254',
      event_url: `https://${KE}/event/37558254?filter=all`,
      sides: { '1X': { selection_id: '9', url: `https://${KE}/external-prefill?selectionIds=9` } }
    }
  ]
};

test('the body is indexed by fixture id, as a string key', () => {
  const idx = indexLinks(body);
  assert.equal(idx.eligible, true);
  assert.equal(idx.host, KE);
  assert.deepEqual(Object.keys(idx.byFixture), ['212', '214']);
  assert.equal(idx.byFixture['212'].event_id, '37536526');
});

test('an ineligible or empty body indexes to nothing', () => {
  assert.deepEqual(indexLinks({ eligible: false, host: null, links: [] }),
    { eligible: false, host: null, byFixture: {} });
  assert.deepEqual(indexLinks(null), { eligible: false, host: null, byFixture: {} });
});

test('a call with a line links to the wager; number or string fixture id', () => {
  const { byFixture } = indexLinks(body);
  assert.deepEqual(wagerLink(byFixture, 212, 'A+1.5'),
    { kind: 'wager', url: `https://${KE}/external-prefill?selectionIds=1539591711` });
  assert.deepEqual(wagerLink(byFixture, '212', 'H'),
    { kind: 'wager', url: `https://${KE}/external-prefill?selectionIds=1537500854` });
});

test('a call whose side has no line falls back to the event page (D11)', () => {
  const { byFixture } = indexLinks(body);
  assert.deepEqual(wagerLink(byFixture, 214, 'H+1.5'),
    { kind: 'event', url: `https://${KE}/event/37558254?filter=all` });
});

test('a fixture the scrape did not match has no link at all', () => {
  const { byFixture } = indexLinks(body);
  assert.equal(wagerLink(byFixture, 999, 'H'), null);
  assert.equal(wagerLink({}, 212, 'H'), null);
  assert.equal(wagerLink(undefined, 212, 'H'), null);
});

test('the labels say which of the two the button is', () => {
  assert.equal(wagerLabel('wager'), 'Bet this on betPawa');
  assert.equal(wagerLabel('event'), 'See on betPawa');
  assert.equal(wagerLabel('other'), null);
});

test('the prefill URL is the verified form', () => {
  assert.equal(prefillUrl(KE, ['1539591711']),
    'https://www.betpawa.co.ke/external-prefill?selectionIds=1539591711');
  assert.equal(prefillUrl('www.betpawa.ug', ['1', '2', '3']),
    'https://www.betpawa.ug/external-prefill?selectionIds=1,2,3');
});

test('a slip whose every leg has a line becomes one accumulator link', () => {
  const { byFixture } = indexLinks(body);
  const legs = [
    { fixture_id: 212, side: 'A+1.5', home_team: 'Southampton', away_team: 'Swansea' },
    { fixture_id: 214, side: '1X', home_team: 'Wrexham', away_team: 'Burnley' }
  ];
  assert.deepEqual(slipLink(KE, legs, byFixture),
    { url: `https://${KE}/external-prefill?selectionIds=1539591711,9`, missing: [] });
});

test('a slip with a leg the book has no line for is not offered, and names the leg', () => {
  const { byFixture } = indexLinks(body);
  const legs = [
    { fixture_id: 212, side: 'A+1.5', home_team: 'Southampton', away_team: 'Swansea' },
    { fixture_id: 214, side: 'H+1.5', home_team: 'Wrexham', away_team: 'Burnley' },
    { fixture_id: 300, side: 'H', home_team: 'Luton', away_team: 'Barnsley' }
  ];
  assert.deepEqual(slipLink(KE, legs, byFixture),
    { url: null, missing: ['Wrexham v Burnley', 'Luton v Barnsley'] });
});

test('no host, or no legs, is no slip link', () => {
  const { byFixture } = indexLinks(body);
  assert.deepEqual(slipLink(null, [{ fixture_id: 212, side: 'H' }], byFixture), { url: null, missing: [] });
  assert.deepEqual(slipLink(KE, [], byFixture), { url: null, missing: [] });
});
