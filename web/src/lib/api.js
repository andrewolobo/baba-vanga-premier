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
export const getParlay = (division, legs, minClaim) =>
  get('/parlay', { division, legs, min_claim: minClaim });

// The parlay page's controls (`docs/PARLAY_PLAN.md` D2, D3). These mirror
// `engine/serve/parlay.py` -- PRESETS and MIN/MAX/WARN_LEGS -- and
// `tests/test_parlay.py` pins the numbers against it, so a change on one
// side that is not made on the other goes red rather than quietly drifting.
// The API validates every request against its own copy either way.
export const RISK_PRESETS = [
  ['safer', 'Safer', 0.8],
  ['balanced', 'Balanced', 0.7],
  ['any', 'Any call', 0]
];
export const LEGS = { min: 2, max: 4, default: 2, warn: 4 };

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

// The published call, in words. `tips.side` carries a market code and most of
// them are not outrights: under `confidence-v3` (`BACKLOG.md` B21) the modal
// call is the underdog +1.5 handicap (~64% of matches), and the rest are
// unions or outrights.
//
// Rendering only H/A would silently drop most of the product, and rendering
// a code as a plain team name would misstate what was published and graded.
// So every code has a phrase; the handicap names its team, side and line, its
// market and settlement ride in the badge (`callCode`), and the mechanics are
// in `callMeans` (V3_ADOPTION_PLAN.md D3).
export const callLabel = (side, home, away) =>
  ({
    H: `${home} win`,
    A: `${away} win`,
    D: 'Draw',
    '1X': `${home} or draw`,
    X2: `${away} or draw`,
    12: 'Either team to win',
    'H+1.5': `${home} Home +1.5`,
    'A+1.5': `${away} Away +1.5`
  })[side] ?? side;

// The badge beside a hedged call: the union codes `1X`, `X2`, `12` are the
// disclosure that two results are covered; the handicap's names its market
// and settlement, since the phrase carries only team, side and line.
export const callCode = (side) => (side.endsWith('+1.5') ? 'Handicap | Fulltime' : side);

// What the call actually needs to happen, for the codes where the phrase alone
// is not self-explanatory.
export const callMeans = (side, home, away) =>
  ({
    '1X': `${home} must win or draw`,
    X2: `${away} must win or draw`,
    12: `either ${home} or ${away} must win`,
    'H+1.5': `${home} must not lose by 2 or more goals`,
    'A+1.5': `${away} must not lose by 2 or more goals`
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
