// Whether the front page's empty state bounces a football (owner request
// 2026-09-21). The animation, the art and the markup all stay in the tree, so
// turning it off is this one line: set BALL_BOUNCE to false, rebuild, deploy —
// nothing else changes.
//
// Off, the box keeps its message and its next-fixture date and goes back to
// the size the text alone needs; the room reserved for the ball to rest in
// goes with it.
//
// This is a decision about the site, not about the reader: a visitor who has
// asked their system for less motion already gets the ball at rest rather
// than in flight, which `+page.svelte` handles under `prefers-reduced-motion`
// and which this flag has no part in.
export const BALL_BOUNCE = false;
