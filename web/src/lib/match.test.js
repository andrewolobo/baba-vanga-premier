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
  formRecord,
  marginScale,
  meetingTally,
  sportsEventScript,
  plainClick,
  factsState
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
  const away = {
    at_home: false, home_name: 'Chelsea', away_name: 'Manchester United',
    home_team: 'Chelsea', away_team: 'Man United', fthg: 0, ftag: 3
  };
  assert.deepEqual(formGame(away), { opponent: 'Chelsea', opponentTeam: 'Chelsea', where: 'at', score: '3–0' });
  const home = {
    at_home: true, home_name: 'Manchester United', away_name: 'Brighton & Hove Albion',
    home_team: 'Man United', away_team: 'Brighton', fthg: 0, ftag: 1
  };
  assert.deepEqual(formGame(home), {
    opponent: 'Brighton & Hove Albion', opponentTeam: 'Brighton', where: 'v', score: '0–1'
  });
});

test('the form record counts W/D/L and skips a game with no score', () => {
  const games = ['W', 'D', 'L', 'W', null].map((result) => ({ result }));
  assert.equal(formRecord(games), 'W2 D1 L1');
  assert.equal(formRecord([]), 'W0 D0 L0');
});

// Cells as a string, −3 to +3: 'y' comes in, 'n' does not, upper case where it ended.
const cells = (scale) =>
  scale.cells.map((c) => (c.comesIn ? 'y' : 'n')[c.ended ? 'toUpperCase' : 'toString']()).join('');
const endedAt = (scale) => scale.cells.findIndex((c) => c.ended) - 3;

test('the margin scale reads each call from the side it names', () => {
  const table = {
    H: ['home', 'nnnnyyy'],
    A: ['away', 'nnnnyyy'],
    D: ['home', 'nnnynnn'],
    '1X': ['home', 'nnnyyyy'],
    X2: ['away', 'nnnyyyy'],
    12: ['home', 'yyynyyy'],
    'H+1.5': ['home', 'nnyyyyy'],
    'A+1.5': ['away', 'nnyyyyy']
  };
  for (const [side, [team, zones]] of Object.entries(table)) {
    const scale = marginScale(side, null, null);
    assert.equal(scale.team, team, side);
    assert.equal(cells(scale), zones, side);
    assert.equal(endedAt(scale), -4, `${side}: no score, no full-time mark`);
  }
  assert.deepEqual(
    marginScale('H', null, null).cells.map((c) => c.label),
    ['≤−3', '−2', '−1', '0', '+1', '+2', '≥+3']
  );
  assert.equal(marginScale('O2.5', 1, 2), null);
});

test('the full-time mark is the margin from the named side, folded at the ends', () => {
  // Bristol City 1–0 Watford, Watford +1.5: Watford lost by one, and it came in.
  assert.equal(endedAt(marginScale('A+1.5', 1, 0)), -1);
  assert.equal(marginScale('A+1.5', 1, 0).cells[2].comesIn, true);
  assert.equal(endedAt(marginScale('H', 1, 0)), 1);
  assert.equal(endedAt(marginScale('X2', 0, 0)), 0);
  assert.equal(endedAt(marginScale('H', 5, 0)), 3);
  assert.equal(endedAt(marginScale('A+1.5', 6, 1)), -3);
  assert.equal(cells(marginScale('12', 0, 4)), 'Yyynyyy');
});

test('meetings are tallied by club, whichever way round they were played', () => {
  const m = (home_name, fthg, ftag) => ({ home_name, fthg, ftag });
  const meetings = [
    m('Bristol City', 1, 2), // Watford
    m('Watford', 1, 1), // draw
    m('Bristol City', 2, 1), // Bristol City
    m('Watford', 1, 0), // Watford
    m('Watford', 0, 3) // Bristol City, away
  ];
  assert.deepEqual(meetingTally(meetings, 'Bristol City'), { home: 2, draw: 1, away: 2 });
  assert.deepEqual(meetingTally(meetings, 'Watford'), { home: 2, draw: 1, away: 2 });
  assert.deepEqual(meetingTally([], 'Watford'), { home: 0, draw: 0, away: 0 });
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

test('only a plain main-button click opens the sheet; anything else is the link', () => {
  const click = (extra = {}) => ({ button: 0, metaKey: false, ctrlKey: false, shiftKey: false, altKey: false, ...extra });
  assert.equal(plainClick(click()), true);
  for (const extra of [{ ctrlKey: true }, { metaKey: true }, { shiftKey: true }, { altKey: true }, { button: 1 }]) {
    assert.equal(plainClick(click(extra)), false, JSON.stringify(extra));
  }
});

test('the sheet state is the heading fields alone, and survives a structured clone', () => {
  const row = { ...base, tip_id: 9, side: 'H', model_prob: 0.8, home_team: 'Man United', away_team: "Nott'm Forest", extra: () => 1 };
  const state = factsState(row);
  assert.deepEqual(Object.keys(state).sort(), ['away_team', 'division', 'fixture_id', 'home_team', 'kickoff_time', 'match_date', 'slug']);
  assert.deepEqual(structuredClone(state), state);
  assert.equal(matchPath(state), '/match/268-manchester-united-vs-nottingham-forest');
});
