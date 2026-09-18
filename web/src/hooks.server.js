import { apiRequest } from '$lib/proxy.js';

// SvelteKit preloads scripts and stylesheets by default. Add the one font
// face the first paint needs: Barlow Condensed 800 sets the hero headline
// (the LCP element) and the wordmark, and without a preload the browser
// only asks for it once the stylesheet has been parsed ($lib/fonts/fonts.css).
export async function handle({ event, resolve }) {
  return resolve(event, {
    preload: ({ type, path }) =>
      type === 'js' || type === 'css' || (type === 'font' && path.includes('barlow-condensed-800'))
  });
}

// Server-side `fetch('/api/…')` goes straight to uvicorn ($lib/proxy.js).
export async function handleFetch({ event, request, fetch }) {
  return fetch(apiRequest(request, event.url.origin) ?? request);
}
