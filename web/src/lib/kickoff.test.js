// node --test  (no framework; Node's own runner)
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { ukInstant, localKickoff } from './kickoff.js';

test('a summer kick-off is BST: 15:00 UK is 14:00 UTC', () => {
  assert.equal(ukInstant('2026-08-15', '15:00').toISOString(), '2026-08-15T14:00:00.000Z');
});

test('a winter kick-off is GMT: 15:00 UK is 15:00 UTC', () => {
  assert.equal(ukInstant('2026-12-26', '15:00').toISOString(), '2026-12-26T15:00:00.000Z');
});

test('the switch weekend is read from the calendar, not assumed', () => {
  // BST ends 2026-10-25 at 02:00 BST. A Saturday 15:00 before it is BST; the
  // Sunday 14:00 after it is GMT.
  assert.equal(ukInstant('2026-10-24', '15:00').toISOString(), '2026-10-24T14:00:00.000Z');
  assert.equal(ukInstant('2026-10-25', '14:00').toISOString(), '2026-10-25T14:00:00.000Z');
});

test('shown in the viewer zone, 24h, with the day shift when the date moves', () => {
  assert.deepEqual(localKickoff('2026-08-15', '15:00', 'Africa/Nairobi'),
    { time: '17:00', dayShift: 0, zone: 'Africa/Nairobi' });
  assert.deepEqual(localKickoff('2026-08-15', '15:00', 'Europe/London'),
    { time: '15:00', dayShift: 0, zone: 'Europe/London' });
  assert.deepEqual(localKickoff('2026-08-14', '20:00', 'Australia/Sydney'),
    { time: '05:00', dayShift: 1, zone: 'Australia/Sydney' });
  assert.deepEqual(localKickoff('2026-08-15', '12:30', 'America/Los_Angeles'),
    { time: '04:30', dayShift: 0, zone: 'America/Los_Angeles' });
  assert.deepEqual(localKickoff('2026-08-15', '00:30', 'America/Los_Angeles'),
    { time: '16:30', dayShift: -1, zone: 'America/Los_Angeles' });
});

test('a fixture without a time prints nothing rather than a wrong time', () => {
  assert.equal(localKickoff('2026-08-15', null, 'Europe/London'), null);
  assert.equal(localKickoff('2026-08-15', '', 'Europe/London'), null);
  assert.equal(localKickoff('2026-08-15', 'TBC', 'Europe/London'), null);
});
