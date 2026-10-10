// The match analysis panel's data (docs/ANALYSIS_PLAN.md, Phase 4).
//
// `GET /fixture/{id}/analysis` is signed-in only (D10) and is fetched in the
// browser when a reader opens the panel, never during server rendering, so
// no analysis text is ever in a page's HTML. Everything here is display:
// the numbers were computed by the engine, the prose was written by the
// model and passed the validator, and the API already resolved every cited
// id to its label and value. Nothing here computes a probability.
import { get } from './api.js';

export const getFixtureAnalysis = (id) => get(`/fixture/${id}/analysis`);

// A fact's value as it sits beside its label. Only a percentage carries its
// unit: every per-game label already says "per game", and a count is a count.
export const factText = ({ value, unit }) => (unit === '%' ? `${value}%` : String(value));

// Where each market sat in the rule (D2): the call itself, one the rule
// could have taken but rated lower, one it could not take, or one that is
// never on the menu. Floor and ceiling are percentages, as the pack stores
// them.
export const menuNote = (line, floor, ceiling) =>
  line.is_call ? 'The call'
    : line.role === 'off_menu' ? 'Not on the menu'
    : line.eligible ? 'Eligible, less likely'
    : line.role === 'outright' ? `Below the ${floor}% floor`
    : `Above the ${ceiling}% ceiling`;

// The data caveats the engine raised (D4), in words, naming the team.
export const flagText = ({ code, side }, home, away) => {
  const team = side === 'home' ? home : away;
  return {
    small_sample: `${team}: few league games this season`,
    new_to_division: `${team}: new to the division`,
    results_gap: `${team}: a result is missing from the record`
  }[code] ?? `${team}: ${code}`;
};

export const trendText = (trend) =>
  ({ improving: 'Improving', stable: 'Stable', declining: 'Declining' })[trend] ?? trend;

// The prose in paragraphs: the model separates them with a blank line.
export const paragraphs = (text) =>
  String(text ?? '')
    .split(/\n\s*\n/)
    .map((p) => p.trim())
    .filter(Boolean);

// The numbers-only card for a fallback (D5): no prose, a few facts per side
// from the shortest complete window (L5, else the season), and the meetings'
// tally. Picked by id, so a missing window simply shows less.
const CARD_METRICS = ['FORM', 'PPG', 'GF_PG', 'GA_PG'];
const H2H_METRICS = ['GAMES', 'HOME_WINS', 'DRAWS', 'AWAY_WINS'];

export const fallbackFacts = (pack) => {
  const byId = new Map(pack.facts.map((f) => [f.id, f]));
  const side = (prefix) => {
    const window = ['L5', 'SEASON'].find((w) => byId.has(`${prefix}_FORM_${w}`));
    return window ? CARD_METRICS.map((m) => byId.get(`${prefix}_${m}_${window}`)).filter(Boolean) : [];
  };
  return {
    home: side('HOME'),
    away: side('AWAY'),
    h2h: H2H_METRICS.map((m) => byId.get(`H2H_${m}_L5`)).filter(Boolean)
  };
};
