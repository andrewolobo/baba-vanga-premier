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

export const DIVISIONS = [
  ['', 'All'],
  ['E0', 'Premier League'],
  ['E1', 'Championship'],
  ['E2', 'League One'],
  ['E3', 'League Two']
];

// Break-even is raw 1/odds, vig-inclusive. This is the only arithmetic the
// frontend does, and it is display-only: the engine has already applied the
// same rule when deciding what to bet. It is NOT the de-vigged market
// probability, which would understate the bar by the bookmaker's margin.
export const breakEven = (price) => (price > 1 ? 1 / price : null);

export const pct = (x, digits = 1) =>
  x === null || x === undefined ? '—' : `${(100 * x).toFixed(digits)}%`;

export const signed = (x, digits = 3) =>
  x === null || x === undefined ? '—' : `${x >= 0 ? '+' : ''}${x.toFixed(digits)}`;
