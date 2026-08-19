// node --test  (no framework; Node's own runner)
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { callLabel, callMeans } from './api.js';

test('every publishable side has a phrase, none falls through to its raw code', () => {
  const sides = ['H', 'A', 'D', '1X', 'X2', '12', 'H+1.5', 'A+1.5'];
  for (const side of sides) {
    assert.notEqual(callLabel(side, 'Brentford', 'Arsenal'), side);
  }
});

test('the handicap names the handicapped team with its start', () => {
  assert.equal(callLabel('H+1.5', 'Brentford', 'Arsenal'), 'Brentford +1.5');
  assert.equal(callLabel('A+1.5', 'Brentford', 'Arsenal'), 'Arsenal +1.5');
});

test('the handicap mechanics say what must not happen', () => {
  assert.equal(callMeans('H+1.5', 'Brentford', 'Arsenal'),
    'Brentford must not lose by 2 or more goals');
  assert.equal(callMeans('A+1.5', 'Brentford', 'Arsenal'),
    'Arsenal must not lose by 2 or more goals');
});

test('an unknown code still renders rather than crashing the page', () => {
  assert.equal(callLabel('X9', 'A', 'B'), 'X9');
  assert.equal(callMeans('X9', 'A', 'B'), null);
});
