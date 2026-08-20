// node --test  (no framework; Node's own runner)
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { outcomes, nextLikeliest } from './view.js';

// Bolton v Preston, as served 2026-08-15, under v3: the underdog +1.5 wins
// the fallback (0.80 against `12` at 0.74).
const handicap = {
  side: 'A+1.5', model_prob: 0.8, home_team: 'Bolton', away_team: 'Preston',
  p_home: 0.42, p_draw: 0.26, p_away: 0.32, p_1x: 0.68, p_x2: 0.58, p_12: 0.74,
  p_h15: 0.86, p_a15: 0.8
};
// The same fixture had v2 called it: a `12`.
const hedge = { ...handicap, side: '12', model_prob: 0.74 };
// Wolves v Blackburn: an outright that cleared the floor, so hedges outrank
// it on probability alone.
const outright = {
  side: 'H', model_prob: 0.59, home_team: 'Wolves', away_team: 'Blackburn',
  p_home: 0.59, p_draw: 0.24, p_away: 0.17, p_1x: 0.83, p_x2: 0.41, p_12: 0.76,
  p_h15: 0.97, p_a15: 0.71
};

test('the outright triple is ranked and says how the call covers each result', () => {
  assert.deepEqual(outcomes(hedge), [
    { side: 'H', label: 'Bolton win', p: 0.42, cover: 'full' },
    { side: 'A', label: 'Preston win', p: 0.32, cover: 'full' },
    { side: 'D', label: 'Draw', p: 0.26, cover: 'none' }
  ]);
  assert.deepEqual(outcomes(outright).map((o) => [o.side, o.cover]),
    [['H', 'full'], ['D', 'none'], ['A', 'none']]);
});

test('a handicap covers its side in full and the other side only by one goal', () => {
  assert.deepEqual(outcomes(handicap).map((o) => [o.side, o.cover]),
    [['H', 'part'], ['A', 'full'], ['D', 'full']]);
});

test('the next-likeliest markets exclude the call and say when they outrank it', () => {
  // Under v3 the underdog's +1.5 is on the menu; the favourite's is not.
  assert.deepEqual(nextLikeliest(hedge), [
    { side: 'A+1.5', label: 'Preston Away +1.5', p: 0.8, above: true },
    { side: '1X', label: 'Bolton or draw', p: 0.68, above: false }
  ]);
  assert.deepEqual(nextLikeliest(handicap), [
    { side: '12', label: 'Either team to win', p: 0.74, above: false },
    { side: '1X', label: 'Bolton or draw', p: 0.68, above: false }
  ]);
  assert.deepEqual(nextLikeliest(outright), [
    { side: '1X', label: 'Wolves or draw', p: 0.83, above: true },
    { side: '12', label: 'Either team to win', p: 0.76, above: true }
  ]);
  assert.equal(nextLikeliest(hedge, 9).length, 6);
  assert.ok(!nextLikeliest(hedge, 9).some((m) => m.side === 'H+1.5'));
});

test('the underdog is read the way the rule reads it: home is favourite on a tie', () => {
  const tie = { ...hedge, p_home: 0.37, p_away: 0.37, p_draw: 0.26 };
  assert.equal(nextLikeliest(tie, 9).find((m) => m.side.endsWith('+1.5')).side, 'A+1.5');
});

test('a tip without its view renders nothing rather than throwing', () => {
  const bare = { side: '12', model_prob: 0.7, home_team: 'A', away_team: 'B' };
  assert.deepEqual(outcomes(bare), []);
  assert.deepEqual(nextLikeliest(bare), []);
});
