// node --test
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { recordView, markShown, VIEWS_KEY, SHOWN_KEY } from './nudge.js';

const storage = (initial = {}) => {
  const m = new Map(Object.entries(initial));
  return {
    getItem: (k) => (m.has(k) ? m.get(k) : null),
    setItem: (k, v) => m.set(k, String(v)),
    map: m
  };
};

test('the page a visitor lands on is never the one', () => {
  const s = storage();
  assert.equal(recordView(() => s), false);
  assert.equal(s.getItem(VIEWS_KEY), '1');
});

test('the second page view makes it due, and it stays due until shown', () => {
  const s = storage();
  recordView(() => s);
  assert.equal(recordView(() => s), true);
  assert.equal(recordView(() => s), true);
});

test('once shown, never again in the session', () => {
  const s = storage();
  recordView(() => s);
  recordView(() => s);
  markShown(() => s);
  assert.equal(s.getItem(SHOWN_KEY), '1');
  assert.equal(recordView(() => s), false);
});

test('a corrupt count starts again rather than throwing', () => {
  const s = storage({ [VIEWS_KEY]: 'x' });
  assert.equal(recordView(() => s), false);
  assert.equal(recordView(() => s), true);
});

test('blocked storage never shows the card', () => {
  const blocked = () => {
    throw new Error('SecurityError');
  };
  assert.equal(recordView(blocked), false);
  assert.equal(recordView(blocked), false);
  assert.doesNotThrow(() => markShown(blocked));
});
