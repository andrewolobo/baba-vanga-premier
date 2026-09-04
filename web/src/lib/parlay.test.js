// node --test  (no framework; Node's own runner)
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { availability, claimLabel } from './parlay.js';

test('a whole parlay needs no note', () => {
  assert.equal(availability({ pool: 31, available: 12, requested: 2 }), null);
  assert.equal(availability({ pool: 3, available: 3, requested: 3 }), null);
});

test('an empty pool is not the same as a threshold nothing clears', () => {
  const none = availability({ pool: 0, available: 0, requested: 2 });
  assert.equal(none.head, 'No games are live right now.');
  assert.match(none.body, /publish on matchday/);

  const bar = availability({ pool: 5, available: 0, requested: 2 });
  assert.equal(bar.head, 'None of the 5 games live clears this threshold.');
  assert.match(bar.body, /Balanced or Any call/);
});

test('a short slip says how many cleared and that nothing was padded', () => {
  const one = availability({ pool: 9, available: 1, requested: 3 });
  assert.equal(one.head, '1 of the 3 legs you asked for.');
  assert.equal(one.body,
    'Only 1 leg clears this threshold today, and we never fill a slot with a weaker leg.');
  const two = availability({ pool: 9, available: 2, requested: 4 });
  assert.equal(two.head, '2 of the 4 legs you asked for.');
  assert.match(two.body, /^Only 2 legs clear this threshold/);
});

test('one live game is singular', () => {
  assert.equal(availability({ pool: 1, available: 0, requested: 2 }).head,
    'None of the 1 game live clears this threshold.');
});

test('the combined claim never reads as zero', () => {
  assert.equal(claimLabel(0.7), '70%');
  assert.equal(claimLabel(0.05), '5%');
  assert.equal(claimLabel(0.049), '4.9%');
  assert.equal(claimLabel(0.015), '1.5%');
  assert.equal(claimLabel(0.005), '0.5%');
  assert.equal(claimLabel(0.004), 'about 1 in 250');
  assert.equal(claimLabel(0.000043), 'about 1 in 23,256');
  assert.equal(claimLabel(null), '—');
});
