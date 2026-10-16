// node --test  (no framework; Node's own runner)
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { availability, claimLabel, ticketLegs } from './parlay.js';

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

test('each ticket is its legs in slip order, with the figures the API sent', () => {
  const legs = [1, 2, 3, 4].map((tip_id) => ({ tip_id, home_team: `H${tip_id}` }));
  const parlay = {
    legs,
    tickets: [
      { tip_ids: [4, 1], claimed: 0.52, below_even: false },
      { tip_ids: [2, 3], claimed: 0.49, below_even: true }
    ]
  };
  const [first, second] = ticketLegs(parlay);
  // The slip's order, not the order the ids came in.
  assert.deepEqual(first.legs, [legs[0], legs[3]]);
  assert.deepEqual(second.legs, [legs[1], legs[2]]);
  // Carried as sent: the products are the API's, never formed here.
  assert.equal(first.claimed, 0.52);
  assert.equal(first.below_even, false);
  assert.equal(second.claimed, 0.49);
  assert.equal(second.below_even, true);
});

test('no slip, or a response without tickets, has no tickets', () => {
  assert.deepEqual(ticketLegs(null), []);
  assert.deepEqual(ticketLegs({ legs: [], tickets: [] }), []);
  assert.deepEqual(ticketLegs({ legs: [{ tip_id: 1 }] }), []);
});
