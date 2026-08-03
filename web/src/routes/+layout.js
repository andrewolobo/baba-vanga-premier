// Client-rendered: every page reads live engine state, so prerendering would
// bake in whatever was true at build time.
export const ssr = false;
export const prerender = false;
