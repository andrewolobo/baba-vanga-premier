// node --test
//
// The house faces are served from this site ($lib/fonts, docs/SEO_PLAN.md §7).
// A face whose file is missing or misnamed fails silently -- the browser
// falls back to the system font and nothing reports it -- so these read the
// stylesheet against the folder.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';

const dir = new URL('./fonts/', import.meta.url);
const css = readFileSync(new URL('fonts.css', dir), 'utf8');
const faces = [...css.matchAll(/@font-face \{([^}]*)\}/g)].map(([, body]) => ({
  family: body.match(/font-family: '([^']+)'/)[1],
  weight: body.match(/font-weight: (\d+)/)[1],
  file: body.match(/url\('\.\/([^']+)'\)/)[1]
}));

test('every face names a woff2 file that is there, and every file is used', () => {
  const files = readdirSync(dir).filter((f) => f.endsWith('.woff2'));
  assert.deepEqual(faces.map((f) => f.file).sort(), files.sort());
  for (const { file } of faces) {
    const magic = readFileSync(new URL(file, dir)).subarray(0, 4).toString('latin1');
    assert.equal(magic, 'wOF2', file);
  }
});

test('the faces are the families and weights the design uses', () => {
  const have = faces.map((f) => `${f.family} ${f.weight}`).sort();
  assert.deepEqual(have, [
    'Barlow 400', 'Barlow 500', 'Barlow 600', 'Barlow 700',
    'Barlow Condensed 500', 'Barlow Condensed 600', 'Barlow Condensed 700', 'Barlow Condensed 800',
    'IBM Plex Mono 500', 'IBM Plex Mono 600'
  ]);
});

test('no page asks Google Fonts for anything', () => {
  // The render-blocking cross-origin stylesheet this folder replaced.
  const html = readFileSync(new URL('../app.html', import.meta.url), 'utf8');
  assert.doesNotMatch(html, /fonts\.(googleapis|gstatic)\.com/);
});

test('the preloaded face exists', () => {
  // hooks.server.js preloads by this name; a rename would drop the preload.
  const hooks = readFileSync(new URL('../hooks.server.js', import.meta.url), 'utf8');
  const name = hooks.match(/path\.includes\('([^']+)'\)/)[1];
  assert.ok(faces.some((f) => f.file === `${name}.woff2`), name);
});
