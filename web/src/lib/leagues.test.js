// node --test
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readdirSync } from 'node:fs';
import { LEAGUES, leagueBySlug, leagueByCode, leaguePath, leagueTitle, leagueDescription } from './leagues.js';

test('the four served divisions, each with a name, a slug and its own intro', () => {
  assert.deepEqual(LEAGUES.map((l) => l.code), ['E0', 'E1', 'E2', 'E3']);
  assert.deepEqual(LEAGUES.map((l) => l.name), ['Premier League', 'Championship', 'League One', 'League Two']);
  assert.deepEqual(LEAGUES.map((l) => l.slug), ['premier-league', 'championship', 'league-one', 'league-two']);
  const intros = LEAGUES.map((l) => l.intro);
  assert.equal(new Set(intros).size, 4, 'four identical intros read as duplicate content');
  for (const intro of intros) assert.ok(intro.length > 80);
});

test('lookups both ways, and nothing else is a league', () => {
  assert.equal(leagueBySlug('league-one').code, 'E2');
  assert.equal(leagueByCode('E3').slug, 'league-two');
  assert.equal(leaguePath('E0'), '/premier-league');
  for (const other of ['parlay', 'match', 'book', 'Premier-League', '']) assert.equal(leagueBySlug(other), null, other);
});

test('no league slug collides with a route of its own', () => {
  // `/[league=league]` sits beside the real top-level routes; a league slug
  // that matched one would shadow it or be shadowed.
  const routes = readdirSync(new URL('../routes/', import.meta.url), { withFileTypes: true })
    .filter((d) => d.isDirectory() && !d.name.startsWith('['))
    .map((d) => d.name);
  for (const l of LEAGUES) assert.ok(!routes.includes(l.slug), l.slug);
});

test('title and description', () => {
  const pl = leagueByCode('E0');
  assert.equal(leagueTitle(pl), 'Premier League Predictions & Tips | BabaVanga');
  assert.equal(
    leagueDescription(pl, { graded: 40 }),
    'Premier League predictions: one call for every match, published on matchday before kick-off and graded after. 40 calls graded so far.'
  );
  assert.doesNotMatch(leagueDescription(pl, { graded: 0 }), /graded so far/);
});
