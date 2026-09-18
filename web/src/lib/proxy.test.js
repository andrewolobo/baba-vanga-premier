import { test } from 'node:test';
import assert from 'node:assert/strict';
import { apiRequest } from './proxy.js';

const ORIGIN = 'https://babavanga.net';
const API = 'http://127.0.0.1:8000';
const req = (path, init) => new Request(`${ORIGIN}${path}`, init);

test('an /api/ read goes to uvicorn with the prefix stripped and the query kept', () => {
  const out = apiRequest(req('/api/tips/results?division=E1&limit=12'), ORIGIN, API);
  assert.equal(out.url, 'http://127.0.0.1:8000/tips/results?division=E1&limit=12');
  assert.equal(out.method, 'GET');
});

test('a trailing slash on the API address does not double up', () => {
  assert.equal(apiRequest(req('/api/tips'), ORIGIN, `${API}/`).url, 'http://127.0.0.1:8000/tips');
});

test("the visitor's cookie never reaches the API from the server", () => {
  const out = apiRequest(req('/api/tips', { headers: { cookie: 'bvp_session=secret' } }), ORIGIN, API);
  assert.equal(out.headers.get('cookie'), null);
  assert.equal(out.credentials, 'omit');
});

test('anything else is left alone', () => {
  assert.equal(apiRequest(req('/parlay'), ORIGIN, API), null);
  assert.equal(apiRequest(req('/apiary'), ORIGIN, API), null);
  assert.equal(apiRequest(new Request('https://example.com/api/tips'), ORIGIN, API), null);
  assert.equal(apiRequest(req('/api/me/phone', { method: 'POST', body: '{}' }), ORIGIN, API), null);
});
