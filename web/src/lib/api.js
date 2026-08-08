// Thin wrapper over the read-only API. Kept deliberately dumb: the frontend
// displays what the engine already decided and never recomputes a probability
// or an edge, so that what a user sees is provably what was stored.

const BASE = '/api';

async function get(path, params = {}) {
  const query = new URLSearchParams(
    Object.entries(params).filter(([, v]) => v !== null && v !== undefined && v !== '')
  );
  const url = `${BASE}${path}${query.toString() ? `?${query}` : ''}`;
  const response = await fetch(url);
  if (!response.ok) throw new Error(`${response.status} ${response.statusText} for ${url}`);
  return response.json();
}

export const getHealth = () => get('/health');
export const getFixtures = (division) => get('/fixtures', { division });
export const getPredictions = (division) => get('/predictions', { division });
export const getBook = (settled) => get('/book', { settled });
export const getPerformance = () => get('/performance');
export const getTips = (division) => get('/tips', { division });
export const getTipResults = (division, limit) => get('/tips/results', { division, limit });
export const getTipRecord = () => get('/tips/record');

export const DIVISIONS = [
  ['', 'All'],
  ['E0', 'Premier League'],
  ['E1', 'Championship'],
  ['E2', 'League One'],
  ['E3', 'League Two']
];

// The engine serves E0-E3 only. EC (National League) is loaded and may enter
// the joint strength fit, but no market is served for it, so it must not appear
// as a filter here — an empty tab reads as "no matches this week" rather than
// as "we do not cover this league".

// The published call, in words. `tips.side` carries a market code and 85.6% of
// them are unions rather than a named team (`BACKLOG.md` B3): at the shipped
// floor the rule says `12` in 65% of matches and names a team in 14.3%.
//
// Rendering only H/A would silently drop most of the product, and rendering
// `12` as a team name would misstate what was published and graded. So every
// code has a phrase, and "Not a draw" is shown as exactly that.
export const callLabel = (side, home, away) =>
  ({
    H: `${home} win`,
    A: `${away} win`,
    D: 'Draw',
    '1X': `${home} or draw`,
    X2: `${away} or draw`,
    12: 'Not a draw'
  })[side] ?? side;

// What the call actually needs to happen, for the codes where the phrase alone
// is not self-explanatory.
export const callMeans = (side, home, away) =>
  ({
    '1X': `${home} must win or draw`,
    X2: `${away} must win or draw`,
    12: `either ${home} or ${away} must win`
  })[side] ?? null;

// Break-even is raw 1/odds, vig-inclusive. This is the only arithmetic the
// frontend does, and it is display-only: the engine has already applied the
// same rule when deciding what to bet. It is NOT the de-vigged market
// probability, which would understate the bar by the bookmaker's margin.
export const breakEven = (price) => (price > 1 ? 1 / price : null);

export const pct = (x, digits = 1) =>
  x === null || x === undefined ? '—' : `${(100 * x).toFixed(digits)}%`;

export const signed = (x, digits = 3) =>
  x === null || x === undefined ? '—' : `${x >= 0 ? '+' : ''}${x.toFixed(digits)}`;
