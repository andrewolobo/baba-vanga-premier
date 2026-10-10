// The form trend beside each crest on the tip and parlay listings
// (docs/ANALYSIS_PLAN.md section 8). Signed-in only, like the analysis:
// `GET /trends` is fetched in the browser once the reader is known, never
// during server rendering. Display only -- the API worked out the trend from
// the same games the analysis quotes, and `ai` is the analysis's own word,
// which can differ from it; the mark shows both.
import { get } from './api.js';
import { trendText } from './analysis.js';

export const getTrends = () => get('/trends');

// The body, keyed by fixture, as the betPawa links are.
export const indexTrends = (body) =>
  Object.fromEntries((body?.trends ?? []).map((t) => [String(t.fixture_id), t]));

// One side's entry, or null when there is no trend to mark: no entry, or too
// few games (the API's nulls).
export const trendOf = (byFixture, fixtureId, side) => {
  const entry = byFixture?.[String(fixtureId)]?.[side];
  return entry?.trend ? entry : null;
};

// The lines under the mark: the trend, the two figures it came from (to the
// same two places, so 2 beside 2.12 does not read as a different kind of
// number), and the analysis's word when there is one.
export const trendLines = ({ trend, window, last5, versus, ai }) => [
  `Form: ${trendText(trend)}`,
  `Points per game, last 5: ${last5.toFixed(2)} · ${window === 'L10' ? 'last 10' : 'season'}: ${versus.toFixed(2)}`,
  ...(ai ? [`AI analysis: ${trendText(ai)}`] : [])
];
