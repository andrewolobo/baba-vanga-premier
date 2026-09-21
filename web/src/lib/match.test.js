// node --test
import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  longDate,
  shortDay,
  matchPath,
  parseIdParam,
  matchState,
  pageTitle,
  pageDescription,
  formGame,
  formTally,
  sportsEventScript
} from './match.js';

const base = {
  fixture_id: 268,
  slug: 'manchester-united-vs-nottingham-forest',
  division: 'E0',
  match_date: '2026-09-20',
  kickoff_time: '15:00',
  home_name: 'Manchester United',
  away_name: 'Nottingham Forest',
  venue: 'Old Trafford',
  tip: null
};
const live = { ...base, tip: { side: 'A+1.5', settled_at: null, outcome: null } };
const settled = {
  ...base,
  tip: { side: 'A+1.5', settled_at: '2026-09-20 19:00:00', outcome: 'win', fthg: 2, ftag: 1 }
};

test('dates are written out, not left to the ICU build', () => {
  assert.equal(longDate('2026-09-20'), '20 Sep 2026');
  assert.equal(shortDay('2026-09-20'), 'Sun 20 Sep');
  assert.equal(shortDay('2026-09-19'), 'Sat 19 Sep');
});

test('the address is id first, words second', () => {
  assert.equal(matchPath(base), '/match/268-manchester-united-vs-nottingham-forest');
  assert.equal(parseIdParam('268-manchester-united-vs-nottingham-forest'), 268);
  assert.equal(parseIdParam('268'), 268);
  assert.equal(parseIdParam('268-anything'), 268);
  for (const bad of ['', 'manchester-united', '12x', '-268']) assert.equal(parseIdParam(bad), null, bad);
});

test('three states, from the call', () => {
  assert.deepEqual([base, live, settled].map(matchState), ['upcoming', 'live', 'settled']);
});

test('title and description name the match and say what the page holds', () => {
  assert.equal(pageTitle(base), 'Manchester United vs Nottingham Forest Prediction, 20 Sep 2026 | BabaVanga');
  assert.match(pageDescription(base), /published on matchday at 06:00 UTC/);
  assert.match(pageDescription(live), /Our call for .*: Nottingham Forest Away \+1\.5\./);
  assert.equal(
    pageDescription(settled),
    'Manchester United 2–1 Nottingham Forest (Premier League, Sun 20 Sep 2026). Our call, Nottingham Forest Away +1.5, came in.'
  );
});

test("a form line is from the side's own point of view", () => {
  const away = { at_home: false, home_name: 'Chelsea', away_name: 'Manchester United', fthg: 0, ftag: 3 };
  assert.deepEqual(formGame(away), { opponent: 'Chelsea', where: 'at', score: '3–0' });
  const home = { at_home: true, home_name: 'Manchester United', away_name: 'Brighton', fthg: 0, ftag: 1 };
  assert.deepEqual(formGame(home), { opponent: 'Brighton', where: 'v', score: '0–1' });
});

test('the tally counts graded calls and leaves voids out', () => {
  const games = ['win', 'lose', 'win', 'void', 'win'].map((outcome) => ({ outcome }));
  assert.deepEqual(formTally(games), { won: 3, graded: 4 });
});

test('the structured data is a SportsEvent that cannot close its script early', () => {
  const html = sportsEventScript({ ...base, home_name: 'A</script><b>' }, 'https://babavanga.net');
  assert.equal(html.match(/<\/script>/g).length, 1);
  const event = JSON.parse(html.replace(/^<script[^>]*>/, '').replace(/<\/script>$/, ''));
  assert.equal(event['@type'], 'SportsEvent');
  assert.equal(event.startDate, '2026-09-20T14:00:00Z'); // 15:00 BST
  assert.equal(event.url, 'https://babavanga.net/match/268-manchester-united-vs-nottingham-forest');
  assert.equal(event.location.name, 'Old Trafford');
  assert.equal(event.homeTeam.name, 'A</script><b>');
  const noVenue = JSON.parse(sportsEventScript({ ...base, venue: null }, 'x').replace(/^<script[^>]*>/, '').replace(/<\/script>$/, ''));
  assert.equal(noVenue.location, undefined);
});
