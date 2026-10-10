// node --test
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { factText, menuNote, flagText, trendText, paragraphs, fallbackFacts } from './analysis.js';

test('a fact prints with its unit', () => {
  assert.equal(factText({ value: 40, unit: '%' }), '40%');
  assert.equal(factText({ value: 2.0, unit: 'pts/game' }), '2');
  assert.equal(factText({ value: 1.75, unit: 'goals/game' }), '1.75');
  assert.equal(factText({ value: 3, unit: 'games' }), '3');
  assert.equal(factText({ value: 'WWDLW', unit: null }), 'WWDLW');
  assert.equal(factText({ value: 'National League' }), 'National League');
});

test('each market says where it sat in the rule', () => {
  const line = (over) => ({ is_call: false, role: 'fallback', eligible: true, ...over });
  assert.equal(menuNote(line({ is_call: true }), 55, 85), 'The call');
  assert.equal(menuNote(line({ role: 'off_menu', eligible: false }), 55, 85), 'Not on the menu');
  assert.equal(menuNote(line({}), 55, 85), 'Eligible, less likely');
  assert.equal(menuNote(line({ role: 'outright', eligible: false }), 55, 85), 'Below the 55% floor');
  assert.equal(menuNote(line({ eligible: false }), 55, 85), 'Above the 85% ceiling');
});

test('flags name their team', () => {
  assert.equal(flagText({ code: 'small_sample', side: 'away' }, 'Leeds United', 'Hull City'),
    'Hull City: few league games this season');
  assert.equal(flagText({ code: 'new_to_division', side: 'home' }, 'Leeds United', 'Hull City'),
    'Leeds United: new to the division');
  assert.equal(flagText({ code: 'results_gap', side: 'home' }, 'Leeds United', 'Hull City'),
    'Leeds United: a result is missing from the record');
  assert.equal(trendText('declining'), 'Declining');
});

test('prose splits on blank lines only', () => {
  assert.deepEqual(paragraphs('One.\n\nTwo,\nstill two.\n \nThree.'), ['One.', 'Two,\nstill two.', 'Three.']);
  assert.deepEqual(paragraphs(''), []);
  assert.deepEqual(paragraphs(null), []);
});

test('the fallback card takes the shortest complete window per side', () => {
  const fact = (id, value) => ({ id, value, label: id });
  const pack = {
    facts: [
      fact('HOME_FORM_L5', 'WWDLW'), fact('HOME_PPG_L5', 2.0), fact('HOME_GF_PG_L5', 1.8),
      fact('HOME_GA_PG_L5', 1.0), fact('HOME_FORM_SEASON', 'WWWDLW'),
      // Away has no L5 yet: the season stands in.
      fact('AWAY_FORM_SEASON', 'DL'), fact('AWAY_PPG_SEASON', 0.5),
      fact('H2H_GAMES_L5', 3), fact('H2H_HOME_WINS_L5', 1), fact('H2H_DRAWS_L5', 1),
      fact('H2H_AWAY_WINS_L5', 1)
    ]
  };
  const card = fallbackFacts(pack);
  assert.deepEqual(card.home.map((f) => f.id), ['HOME_FORM_L5', 'HOME_PPG_L5', 'HOME_GF_PG_L5', 'HOME_GA_PG_L5']);
  assert.deepEqual(card.away.map((f) => f.id), ['AWAY_FORM_SEASON', 'AWAY_PPG_SEASON']);
  assert.equal(card.h2h.length, 4);
  assert.deepEqual(fallbackFacts({ facts: [] }), { home: [], away: [], h2h: [] });
});
