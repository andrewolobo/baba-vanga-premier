// node --test
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { phoneRequired, firstName, plausiblePhone } from './session.js';

test('the phone gate opens only for a signed-in user without a number', () => {
  assert.equal(phoneRequired(null), false);
  assert.equal(phoneRequired(undefined), false);
  assert.equal(phoneRequired({ phone_required: true }), true);
  assert.equal(phoneRequired({ phone_required: false }), false);
  assert.equal(phoneRequired({}), false);
});

test('the header uses the first name, then the email handle', () => {
  assert.equal(firstName({ name: 'Alice Anderson', email: 'alice@example.com' }), 'Alice');
  assert.equal(firstName({ name: null, email: 'bob.k@example.com' }), 'bob.k');
  assert.equal(firstName({ name: '', email: 'c@example.com' }), 'c');
  assert.equal(firstName(null), '');
});

test('the client check accepts what a phone number looks like and no more', () => {
  for (const ok of ['07400 123456', '+254 712 345 678', '(020) 7946-0958', '0712345678']) {
    assert.equal(plausiblePhone(ok), true, ok);
  }
  for (const bad of ['', '   ', 'abc', '12', '+44', '0740 0', 'call me 07400123456 now', null]) {
    assert.equal(plausiblePhone(bad), false, String(bad));
  }
});
