import { apiRequest } from '$lib/proxy.js';

// Server-side `fetch('/api/…')` goes straight to uvicorn ($lib/proxy.js).
export async function handleFetch({ event, request, fetch }) {
  return fetch(apiRequest(request, event.url.origin) ?? request);
}
