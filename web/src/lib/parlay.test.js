// node --test  (no framework; Node's own runner)
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { availability } from './parlay.js';

test('a whole parlay needs no note', () => {
  assert.equal(availability({ pool: 31, available: 12, requested: 2 }), null);
  assert.equal(availability({ pool: 3, available: 3, requested: 3 }), null);
});

test('an empty pool is not the same as a threshold nothing clears', () => {
  const none = availability({ pool: 0, available: 0, requested: 2 });
  assert.equal(none.head, 'No calls are live right now.');
  assert.match(none.body, /publish on matchday/);

  const bar = availability({ pool: 5, available: 0, requested: 2 });
  assert.equal(bar.head, 'None of the 5 calls live clears this threshold.');
  assert.match(bar.body, /Balanced or Any call/);
});

test('a short slip says how many cleared and that nothing was padded', () => {
  const one = availability({ pool: 9, available: 1, requested: 3 });
  assert.equal(one.head, '1 of the 3 legs you asked for.');
  assert.equal(one.body,
    'Only 1 call clears this threshold today, and we never fill a slot with a weaker call.');
  const two = availability({ pool: 9, available: 2, requested: 4 });
  assert.equal(two.head, '2 of the 4 legs you asked for.');
  assert.match(two.body, /^Only 2 calls clear this threshold/);
});

test('one live call is singular', () => {
  assert.equal(availability({ pool: 1, available: 0, requested: 2 }).head,
    'None of the 1 call live clears this threshold.');
});
