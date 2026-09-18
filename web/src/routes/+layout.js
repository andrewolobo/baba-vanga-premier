// Server-rendered on every request (docs/SEO_PLAN.md 2.1): the HTML carries
// the calls as they stand at that moment, so crawlers and link previewers
// see content without running JavaScript. Never prerendered -- every page
// reads live engine state, and a build-time copy would bake in whatever was
// true when the build ran.
//
// Anything that belongs to the viewer rather than the page -- the session,
// the phone gate, betPawa links, the time zone, `?owner=1` -- stays in the
// browser, after mount. The server's HTML is the same for every visitor.
export const prerender = false;
