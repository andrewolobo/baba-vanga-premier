// node --test
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { resolveOwner, KEY } from './owner.js';

const storage = (initial = {}) => {
  const m = new Map(Object.entries(initial));
  return {
    getItem: (k) => (m.has(k) ? m.get(k) : null),
    setItem: (k, v) => m.set(k, String(v)),
    removeItem: (k) => m.delete(k),
    map: m
  };
};

test('a fresh browser with no parameter is the public view', () => {
  assert.equal(resolveOwner('', storage()), false);
  assert.equal(resolveOwner('?division=E0', storage()), false);
});

test('?owner=1 shows and is remembered; a later visit without it stays shown', () => {
  const s = storage();
  assert.equal(resolveOwner('?owner=1', s), true);
  assert.equal(s.getItem(KEY), '1');
  assert.equal(resolveOwner('', s), true);
});

test('?owner=0 hides and forgets', () => {
  const s = storage({ [KEY]: '1' });
  assert.equal(resolveOwner('?owner=0', s), false);
  assert.equal(s.getItem(KEY), null);
  assert.equal(resolveOwner('', s), false);
});

test('any other value neither shows nor changes what is remembered', () => {
  assert.equal(resolveOwner('?owner=yes', storage()), false);
  assert.equal(resolveOwner('?owner=2', storage({ [KEY]: '1' })), true);
});

test('unusable storage falls back to the public view rather than throwing', () => {
  const broken = { getItem() { throw new Error('blocked'); }, setItem() {}, removeItem() {} };
  assert.equal(resolveOwner('?owner=1', broken), false);
});
