// Club badges: a three-letter code and a colour, derived from the canonical
// name alone.
//
// **These are not the club's real crest colours and must not be presented as
// them.** Nothing in the schema carries club identity beyond a name, and
// recalling primary colours for 151 clubs down to the National League would be
// inventing data that looks authoritative and would be wrong for some of them.
// The palette below is decorative: its only job is to tell the two sides of a
// fixture apart. If real crest colours are ever acquired they belong in
// `reference/`, keyed by canonical_name, and this file becomes the fallback.
//
// Official three-letter codes are likewise not derivable — MUN, MCI, NFO and
// BHA are conventions, not abbreviations — so these are generated instead. The
// full club name is rendered beside every badge, which is what makes an
// imperfect code cosmetic rather than misleading.

// The design mockup's palette, kept as-is so generated badges sit in the same
// colour world as the rest of the page.
const PALETTE = [
  '#B4122A', '#1B4FA0', '#12233F', '#2E8FD6', '#6C1D45',
  '#1F6B44', '#2A2A30', '#C8791A', '#4A2A7A', '#17706E'
];

// 'AFC Wimbledon' -> Wimbledon; 'Dag and Red' -> Dag Red. Dropping these first
// is what stops every AFC club sharing a code.
const NOISE = new Set(['afc', 'fc', 'and', 'the']);

const words = (name) =>
  (name ?? '')
    .split(/[^A-Za-z]+/)
    .filter(Boolean)
    .filter((w, i, all) => !(NOISE.has(w.toLowerCase()) && all.length > 1));

// Two deterministic forms per club. The primary is used everywhere; the
// alternate exists only to break a tie inside one fixture — Barnet v Barnsley
// is a real League Two match and two identical badges in one row reads as a
// rendering bug.
function forms(name) {
  const w = words(name);
  if (w.length === 0) return ['???', '???'];
  if (w.length === 1) {
    const one = w[0];
    return [one.slice(0, 3), one.slice(0, 2) + one.slice(-1)];
  }
  return [w[0].slice(0, 2) + w[1][0], w[0][0] + w[1].slice(0, 2)];
}

// FNV-1a. Any stable hash would do; what matters is that a club keeps the same
// colour between requests, so the page does not reshuffle on every load.
function hash(name) {
  let h = 0x811c9dc5;
  for (let i = 0; i < name.length; i++) {
    h ^= name.charCodeAt(i);
    h = Math.imul(h, 0x01000193) >>> 0;
  }
  return h;
}

export const abbr = (name) => forms(name)[0].toUpperCase();

export const colour = (name) => PALETTE[hash(name ?? '') % PALETTE.length];

/** Badges for both sides of one fixture, guaranteed to differ from each other. */
export function fixtureBadges(home, away) {
  const [homeCode, homeAlt] = forms(home).map((f) => f.toUpperCase());
  const [awayCode, awayAlt] = forms(away).map((f) => f.toUpperCase());
  const homeColour = colour(home);
  let awayColour = colour(away);
  if (awayColour === homeColour) {
    awayColour = PALETTE[(PALETTE.indexOf(homeColour) + 3) % PALETTE.length];
  }
  return {
    home: { code: homeCode, colour: homeColour },
    away: {
      code: awayCode === homeCode ? awayAlt : awayCode,
      colour: awayColour
    }
  };
}
