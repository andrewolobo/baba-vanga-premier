// node --test
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { indexLinks, wagerLink, wagerLabel, prefillUrl, slipLink, daySlip } from './betpawa.js';

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

// --- every call in the list as one slip (D13, D14) ---------------------------

const NOW = new Date('2026-09-08T12:00:00Z'); // 13:00 in London, BST
const tips = [
  { fixture_id: 212, side: 'A+1.5', home_team: 'Southampton', away_team: 'Swansea', match_date: '2026-09-08', kickoff_time: '19:45' },
  { fixture_id: 214, side: 'H+1.5', home_team: 'Wrexham', away_team: 'Burnley', match_date: '2026-09-08', kickoff_time: '19:45' },
  { fixture_id: 212, side: 'H', home_team: 'Southampton', away_team: 'Swansea', match_date: '2026-09-08', kickoff_time: '20:00' }
];

test('a lineless call is left out and named, and the rest load (D13)', () => {
  const { byFixture } = indexLinks(body);
  const slip = daySlip(KE, tips, byFixture, NOW);
  assert.equal(slip.url, `https://${KE}/external-prefill?selectionIds=1539591711,1537500854`);
  assert.equal(slip.loaded, 2);
  assert.deepEqual(slip.skipped, ['Wrexham v Burnley']);
  assert.equal(slip.kickedOff, 0);
});

test('a call whose UK kick-off has passed is left out and counted', () => {
  const { byFixture } = indexLinks(body);
  const later = new Date('2026-09-08T18:50:00Z'); // 19:50 London: the 19:45 games are on
  const slip = daySlip(KE, tips, byFixture, later);
  assert.equal(slip.url, `https://${KE}/external-prefill?selectionIds=1537500854`);
  assert.equal(slip.loaded, 1);
  assert.equal(slip.kickedOff, 2);
  assert.deepEqual(slip.skipped, [], 'a kicked-off lineless call is counted once, as kicked off');
});

test('a call with no kick-off time is kept, as the server keeps it', () => {
  const { byFixture } = indexLinks(body);
  const slip = daySlip(KE, [{ ...tips[0], kickoff_time: null }], byFixture, NOW);
  assert.equal(slip.loaded, 1);
});

test('nothing loadable is no link, not an empty one', () => {
  const { byFixture } = indexLinks(body);
  assert.equal(daySlip(KE, [tips[1]], byFixture, NOW).url, null);
  assert.equal(daySlip(KE, [], byFixture, NOW).url, null);
  assert.equal(daySlip(null, tips, byFixture, NOW).url, null);
  assert.equal(daySlip(KE, tips, {}, NOW).url, null);
});
