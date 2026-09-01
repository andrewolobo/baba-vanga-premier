// The parlay page's words for the states `GET /parlay` reports by number
// (`docs/PARLAY_PLAN.md`, B24). Display only: the API has already chosen the
// legs and multiplied their claims, and this module forms no probability.
//
//   pool       published calls still to kick off, before the threshold
//   available  of those, how many clear the minimum claim
//   requested  how many legs were asked for
//
// Returns `{ head, body }` for the reader, or null when the parlay is whole.
// Owner decision D5: fewer calls clearing the bar than legs asked for is shown
// as it is and said plainly -- a slot is never filled with a weaker call.
const calls = (n) => `${n} call${n === 1 ? '' : 's'}`;

export const availability = ({ pool, available, requested }) => {
  if (pool === 0) {
    return {
      head: 'No calls are live right now.',
      body: 'Calls publish on matchday, and a game leaves the pool once it kicks off. Check the main list for when the next calls are due.'
    };
  }
  if (available === 0) {
    return {
      head: `None of the ${calls(pool)} live clears this threshold.`,
      body: 'Try Balanced or Any call to let weaker calls in — the combined figure will be lower, and it will say so.'
    };
  }
  if (available < requested) {
    return {
      head: `${available} of the ${requested} legs you asked for.`,
      body: `Only ${calls(available)} clear${available === 1 ? 's' : ''} this threshold today, and we never fill a slot with a weaker call.`
    };
  }
  return null;
};
