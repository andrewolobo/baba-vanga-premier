// Where the API is during server rendering (docs/SEO_PLAN.md 2.1). Server
// only: it reads `process.env`, which a browser does not have.
//
// A page's `load` calls `fetch('/api/tips')`, the same origin-relative URL
// the browser uses. In the browser, nginx (production) or Vite's proxy
// (development) sends it to uvicorn with the /api prefix stripped. On the
// server there is neither in the way: SvelteKit would ask this Node process
// for /api/tips, a route it does not have. So `hooks.server.js` hands every
// same-origin /api/ GET to this, which points it at uvicorn directly.
//
// The prefix strip matters as much here as it does in nginx (the trailing
// slash on its proxy_pass): uvicorn answers /tips, and a request for
// /api/tips would 404 into an empty list that reads as "no matches this
// week" rather than as a fault.

// The same default and the same two variables as web/vite.config.js, so
// development and production find the API the same way.
export const API = process.env.BVP_API_URL ?? `http://127.0.0.1:${process.env.BVP_API_PORT ?? 8000}`;

// The request to send instead, or null to leave `request` alone. No cookie
// and no other header of the visitor's is carried: server-rendered HTML
// must be the same for every visitor, so it may only read what anyone could
// (SEO_PLAN.md 2.1, "Signed-in state stays browser-only").
export function apiRequest(request, origin, api = API) {
  const url = new URL(request.url);
  if (url.origin !== origin || !url.pathname.startsWith('/api/') || request.method !== 'GET') {
    return null;
  }
  return new Request(`${api.replace(/\/+$/, '')}${url.pathname.slice('/api'.length)}${url.search}`, {
    headers: { accept: 'application/json' },
    credentials: 'omit'
  });
}
