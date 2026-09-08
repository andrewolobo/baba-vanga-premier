// node --test
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { applyPalette, DARK, MID, LIGHT } from './pixel.js';

const px = (...rgba) => Uint8ClampedArray.from(rgba);

test('black maps to the dark tone exactly', () => {
  const d = applyPalette(px(0, 0, 0, 255));
  assert.deepEqual([...d], [...DARK, 255]);
});

test('white maps to the light tone exactly', () => {
  const d = applyPalette(px(255, 255, 255, 255));
  assert.deepEqual([...d], [...LIGHT, 255]);
});

test('a mid grey lands between dark and accent, leaning accent', () => {
  const d = applyPalette(px(128, 128, 128, 255));
  for (let c = 0; c < 3; c++) {
    const lo = Math.min(DARK[c], MID[c]);
    const hi = Math.max(DARK[c], MID[c]);
    assert.ok(d[c] >= lo && d[c] <= hi, `channel ${c} inside the dark→accent ramp`);
  }
  // Luminance 0.5 sits past half the ramp, so red is closer to the accent's.
  assert.ok(d[0] > MID[0] / 2);
});

test('every output is one of the two ramps — never the raw input', () => {
  // A saturated green has no place in the palette; it must come out as a
  // blend whose green channel sits inside the ramps' envelope.
  const d = applyPalette(px(0, 255, 0, 255));
  assert.notDeepEqual([...d].slice(0, 3), [0, 255, 0]);
  assert.ok(d[2] <= Math.max(DARK[2], MID[2], LIGHT[2]));
});

test('alpha is untouched and pixels are independent', () => {
  const d = applyPalette(px(0, 0, 0, 40, 255, 255, 255, 200));
  assert.equal(d[3], 40);
  assert.equal(d[7], 200);
  assert.deepEqual([...d].slice(0, 3), [...DARK]);
  assert.deepEqual([...d].slice(4, 7), [...LIGHT]);
});

test('the array is recoloured in place and returned', () => {
  const d = px(10, 10, 10, 255);
  assert.equal(applyPalette(d), d);
});
