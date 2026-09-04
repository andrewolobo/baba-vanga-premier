// The parlay page's words for the states `GET /parlay` reports by number
// (`docs/PARLAY_PLAN.md`, B24). Display only: the API has already chosen the
// legs and multiplied their claims, and this module forms no probability.
//
//   pool       live games still to kick off (each grows one leg -- D12)
//   available  of those, how many legs clear the minimum claim
//   requested  how many legs were asked for
//
// Returns `{ head, body }` for the reader, or null when the parlay is whole.
// Owner decision D5: fewer legs clearing the bar than asked for is shown as
// it is and said plainly -- a slot is never filled with a weaker leg.
const games = (n) => `${n} game${n === 1 ? '' : 's'}`;

export const availability = ({ pool, available, requested }) => {
  if (pool === 0) {
    return {
      head: 'No games are live right now.',
      body: 'Calls publish on matchday, and a game leaves the pool once it kicks off. Check the main list for when the next calls are due.'
    };
  }
  if (available === 0) {
    return {
      head: `None of the ${games(pool)} live clears this threshold.`,
      body: 'Try Balanced or Any call to let weaker legs in — the combined figure will be lower, and it will say so.'
    };
  }
  if (available < requested) {
    return {
      head: `${available} of the ${requested} legs you asked for.`,
      body: `Only ${available} leg${available === 1 ? '' : 's'} clear${available === 1 ? 's' : ''} this threshold today, and we never fill a slot with a weaker leg.`
    };
  }
  return null;
};

// The combined claim, worded so it can never read as zero. Whole percents
// down to 5%, one decimal to 0.5%, and odds below that -- a 39-leg Saturday
// multiplies to ~0.004%, which `pct(x, 0)` would print as "0%" and this page
// must never show (D9). Formatting only: the number itself is the API's.
export const claimLabel = (x) => {
  if (x == null) return '—';
  if (x >= 0.05) return `${(100 * x).toFixed(0)}%`;
  if (x >= 0.005) return `${(100 * x).toFixed(1)}%`;
  return `about 1 in ${Math.round(1 / x).toLocaleString('en-GB')}`;
};
