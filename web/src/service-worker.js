// SvelteKit picks this file up automatically and serves it at
// /service-worker.js; `$service-worker` injects the hashed build assets, the
// static files and a per-build version string, so no plugin is involved.
//
// Offline policy: the app shell and static assets are precached; /api/tips and
// /api/fixtures fall back to the last successful response when the network is
// away (the one case a reader benefits from — checking the published calls on
// a poor signal). Every other /api endpoint is left alone: /api/book and
// /api/performance must never show a stale grade as current.
import { build, files, version } from '$service-worker';

const CACHE = `bvp-${version}`;

// '/' is the adapter-static fallback page — the shell every client-side route
// boots from — and is not listed in `build` or `files`.
const PRECACHE = [...build, ...files, '/'];
const PRECACHED = new Set(PRECACHE);

// Cached per full URL, so each division's query string keeps its own entry.
const OFFLINE_API = new Set(['/api/tips', '/api/fixtures']);

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches
      .open(CACHE)
      .then((cache) => cache.addAll(PRECACHE))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

async function fromPrecache(request, pathname) {
  const cache = await caches.open(CACHE);
  return (await cache.match(pathname)) ?? fetch(request);
}

async function networkFirst(request, cacheKey) {
  const cache = await caches.open(CACHE);
  try {
    const response = await fetch(request);
    if (response.ok) cache.put(cacheKey ?? request, response.clone());
    return response;
  } catch (err) {
    const cached = await cache.match(cacheKey ?? request);
    if (cached) return cached;
    throw err;
  }
}

self.addEventListener('fetch', (event) => {
  const { request } = event;
  if (request.method !== 'GET') return;

  const url = new URL(request.url);
  // Cross-origin requests (fonts, gtag) pass through untouched.
  if (url.origin !== self.location.origin) return;

  if (PRECACHED.has(url.pathname)) {
    event.respondWith(fromPrecache(request, url.pathname));
    return;
  }

  // Client-side routes (/book, /performance, /parlay) all resolve to the
  // shell; refresh it when online, serve the precached copy when not.
  if (request.mode === 'navigate') {
    event.respondWith(networkFirst(request, '/'));
    return;
  }

  if (OFFLINE_API.has(url.pathname)) {
    event.respondWith(networkFirst(request));
  }
  // Anything else — the rest of /api — goes straight to the network.
});
