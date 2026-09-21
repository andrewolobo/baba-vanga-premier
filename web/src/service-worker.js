// SvelteKit picks this file up automatically and serves it at
// /service-worker.js; `$service-worker` injects the hashed build assets, the
// static files and a per-build version string, so no plugin is involved.
//
// Offline policy: the build's assets and static files are precached; pages
// are network-first, the front page and /parlay kept for offline; /api/tips and
// /api/fixtures fall back to the last successful response when the network is
// away (the one case a reader benefits from — checking the published calls on
// a poor signal). Every other /api endpoint is left alone: /api/book and
// /api/performance must never show a stale grade as current, and the account
// calls (/api/me, /api/auth/*) must never be answered from a cache -- they
// are not in the set below, and POSTs never reach the worker at all.
import { build, files, version } from '$service-worker';
import { LEAGUES, leaguePath } from '$lib/leagues.js';

const CACHE = `bvp-${version}`;

// '/' is not listed in `build` or `files`: it is a server-rendered page
// (docs/SEO_PLAN.md 2.1), precached so an offline first open still has
// something to show. It is never served cache-first -- see `page` below.
// The hero clip (~2.3MB) is left out: precaching would pull it into every
// new version's cache on activate, and offline the video hero already
// falls back to its animated noise, so nothing is lost without it. The share
// image (docs/SEO_PLAN.md 1.7) is for link previewers, never for a visitor.
const NOT_PRECACHED = new Set(['/header-video.mp4', '/og-image.jpg']);
const PRECACHE = [...build, ...files.filter((f) => !NOT_PRECACHED.has(f)), '/'];
const PRECACHED = new Set(PRECACHE);

// Cached per full URL, so each division's query string keeps its own entry.
const OFFLINE_API = new Set(['/api/tips', '/api/fixtures']);

// The pages kept for offline, each under its own path. A bounded list rather
// than every page visited: per-match pages will number in the thousands
// (SEO_PLAN.md 2.3) and team pages in the dozens (2.5), so neither is kept.
// Any other page, offline, gets the cached front page.
const OFFLINE_PAGES = new Set([
  '/',
  '/parlay',
  '/record',
  '/results',
  ...LEAGUES.map((l) => leaguePath(l.code))
]);

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

async function networkFirst(request) {
  const cache = await caches.open(CACHE);
  try {
    const response = await fetch(request);
    if (response.ok) cache.put(request, response.clone());
    return response;
  } catch (err) {
    const cached = await cache.match(request);
    if (cached) return cached;
    throw err;
  }
}

// A page is the day's calls rendered into HTML, so it always comes from the
// network when there is one: served cache-first, `/` would show the calls as
// they stood when the worker installed, until the next deploy.
async function page(request, pathname) {
  const cache = await caches.open(CACHE);
  const key = OFFLINE_PAGES.has(pathname) ? pathname : null;
  try {
    const response = await fetch(request);
    if (key && response.ok) cache.put(key, response.clone());
    return response;
  } catch (err) {
    const cached = (key && (await cache.match(key))) ?? (await cache.match('/'));
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

  // Before the precache check: '/' is in the precache, and must not be
  // answered from it while the network is up.
  if (request.mode === 'navigate') {
    event.respondWith(page(request, url.pathname));
    return;
  }

  if (PRECACHED.has(url.pathname)) {
    event.respondWith(fromPrecache(request, url.pathname));
    return;
  }

  if (OFFLINE_API.has(url.pathname)) {
    event.respondWith(networkFirst(request));
  }
  // Anything else — the rest of /api — goes straight to the network.
});
