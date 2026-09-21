// node --test
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { teamPath, teamTitle, teamDescription, tallySentence } from './teams.js';
import { parseIdParam } from './match.js';

const TEAM = {
  team_id: 14,
  name: 'Manchester United',
  slug: 'manchester-united',
  tally: { graded: 5, won: 4 },
  upcoming: [{ home_name: 'Manchester United', away_name: 'Chelsea', match_date: '2026-09-27' }]
};

test('the address is id-first, and the id survives the words changing', () => {
  assert.equal(teamPath(14, 'manchester-united'), '/team/14-manchester-united');
  for (const words of ['14-manchester-united', '14', '14-man-utd']) {
    assert.equal(parseIdParam(words), 14, words);
  }
  for (const bad of ['', 'manchester-united', '-14']) assert.equal(parseIdParam(bad), null, bad);
});

test('the tally is counts, never a rate', () => {
  assert.equal(tallySentence(TEAM), 'Our calls on Manchester United this season: 5 graded, 4 came in.');
  assert.doesNotMatch(tallySentence(TEAM), /%/);
  assert.equal(
    tallySentence({ ...TEAM, tally: { graded: 0, won: 0 } }),
    'No call on Manchester United has been graded yet this season.'
  );
});

test('title and description', () => {
  assert.equal(teamTitle(TEAM), 'Manchester United Predictions & Record | BabaVanga');
  assert.equal(
    teamDescription(TEAM),
    'Our calls on Manchester United this season: 5 graded, 4 came in.' +
      ' Next: Manchester United vs Chelsea, 27 Sep 2026.'
  );
  // Out of season, or between rounds, there is no next fixture to name.
  assert.doesNotMatch(teamDescription({ ...TEAM, upcoming: [] }), /Next:/);
});
