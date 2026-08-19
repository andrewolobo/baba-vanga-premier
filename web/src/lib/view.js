// The drawer behind a call (`BACKLOG.md` B22): what the model thought about
// the match when the call was published. Two readings of the numbers the API
// serves beside every tip. Neither is a second call -- the record grades
// `tip.side` and nothing else -- and neither computes a probability: every
// figure here is one the API stored, summed or derived from the stored
// lambdas, and this module only orders and labels them.
import { callLabel } from './api.js';

// Which outright results each published code wins on, in full. Mirrors
// `engine/serve/tips.py` COMPONENTS for the unions; the +1.5 handicap wins
// outright on a win or a draw for its side and *partly* on a defeat (by one
// goal only), which `PARTLY` names so the triple can say so.
export const COVERS = {
  H: ['H'],
  D: ['D'],
  A: ['A'],
  '1X': ['H', 'D'],
  X2: ['A', 'D'],
  12: ['H', 'A'],
  'H+1.5': ['H', 'D'],
  'A+1.5': ['A', 'D']
};
const PARTLY = { 'H+1.5': 'A', 'A+1.5': 'H' };

const byProbDesc = (x, y) => y.p - x.p;

// Reading (b), the default: the three results ranked by the model's
// probability, each marked with how the call covers it -- 'full', 'part' (a
// handicap's one-goal defeat) or 'none'. This is the honest answer to "who do
// you think wins?" and it cannot compete with the call, because the call is
// drawn from these same three numbers.
export const outcomes = (tip) => {
  if (tip.p_home == null) return [];
  const full = COVERS[tip.side] ?? [];
  const part = PARTLY[tip.side];
  return [
    { side: 'H', label: callLabel('H', tip.home_team, tip.away_team), p: tip.p_home },
    { side: 'D', label: callLabel('D', tip.home_team, tip.away_team), p: tip.p_draw },
    { side: 'A', label: callLabel('A', tip.home_team, tip.away_team), p: tip.p_away }
  ]
    .sort(byProbDesc)
    .map((o) => ({
      ...o,
      cover: full.includes(o.side) ? 'full' : o.side === part ? 'part' : 'none'
    }));
};

// Reading (a), behind a toggle: the `n` likeliest markets on the rule's own
// menu *other than the call*, ranked by probability alone. The menu is the
// three results, the three double chances and the underdog's +1.5 -- the
// candidates `confidence-v3` chooses among, plus the draw. The underdog is
// the side the model makes less likely, read the way the rule reads it
// (`engine/eval/b21.dog15_probs`: home is favourite when p_home >= p_away);
// the favourite's +1.5 is a near-certainty on no menu and is not listed.
//
// Shown as what it is -- a ranking, not the rule. A hedge usually outranks a
// named team here (1X averages 0.69 against a home win's 0.43), which is
// exactly why the rule does not pick this way (`PRODUCT.md` §3) and why an
// entry can sit *above* the call: `above` says so, rather than leaving the
// reader to infer a mistake.
export const nextLikeliest = (tip, n = 2) => {
  if (tip.p_home == null) return [];
  const dog = tip.p_home >= tip.p_away ? ['A+1.5', 'p_a15'] : ['H+1.5', 'p_h15'];
  const menu = [
    ['H', 'p_home'],
    ['D', 'p_draw'],
    ['A', 'p_away'],
    ['1X', 'p_1x'],
    ['X2', 'p_x2'],
    ['12', 'p_12'],
    dog
  ];
  return menu
    .filter(([side, key]) => side !== tip.side && tip[key] != null)
    .map(([side, key]) => ({
      side,
      label: callLabel(side, tip.home_team, tip.away_team),
      p: tip[key],
      above: tip[key] > tip.model_prob
    }))
    .sort(byProbDesc)
    .slice(0, n);
};
