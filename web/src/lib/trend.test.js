// node --test
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { indexTrends, trendOf, trendLines } from './trend.js';

const side = (over) => ({ trend: 'improving', window: 'SEASON', last5: 2.6, versus: 1.88, ai: 'stable', ...over });
const body = {
  trends: [
    { fixture_id: 10, home: side({}), away: side({ trend: null, window: null, last5: null, versus: null, ai: null }) }
  ]
};

test('a side marks only when it has a trend', () => {
  const byFixture = indexTrends(body);
  assert.equal(trendOf(byFixture, 10, 'home').trend, 'improving');
  assert.equal(trendOf(byFixture, '10', 'home').trend, 'improving');
  assert.equal(trendOf(byFixture, 10, 'away'), null);          // too few games
  assert.equal(trendOf(byFixture, 11, 'home'), null);          // not listed
  assert.equal(trendOf({}, 10, 'home'), null);                 // signed out: nothing fetched
  assert.deepEqual(indexTrends(null), {});
});

test('the lines name the window and add the analysis word only when there is one', () => {
  assert.deepEqual(trendLines(side({})), [
    'Form: Improving',
    'Points per game, last 5: 2.60 · season: 1.88',
    'AI analysis: Stable'
  ]);
  assert.deepEqual(trendLines(side({ trend: 'declining', window: 'L10', last5: 1, versus: 1.5, ai: null })), [
    'Form: Declining',
    'Points per game, last 5: 1.00 · last 10: 1.50'
  ]);
});
