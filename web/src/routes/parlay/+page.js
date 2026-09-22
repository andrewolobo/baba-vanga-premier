import { getParlay, LEGS, RISK_PRESETS } from '$lib/api.js';

// The slip the page opens on is the recommendation (`PARLAY_PLAN.md` §1):
// every league, the Safer threshold, two legs, every call type. Read here so
// the server renders it into the HTML (docs/SEO_PLAN.md 2.1); the page takes
// its opening control positions from `launch`, so the two cannot disagree.
// `divisions: []` is every league -- the picker turns all four chips on and
// sends no league param, which is the same request (D15).
const LAUNCH = { divisions: [], risk: 'safer', legs: LEGS.default };

export async function load({ fetch }) {
  const minClaim = RISK_PRESETS.find(([key]) => key === LAUNCH.risk)[2];
  try {
    const parlay = await getParlay(LAUNCH.divisions, LAUNCH.legs, minClaim, 'any', fetch);
    return { launch: LAUNCH, parlay, error: null };
  } catch (e) {
    return { launch: LAUNCH, parlay: null, error: e.message };
  }
}
