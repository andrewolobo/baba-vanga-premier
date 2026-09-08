// The video hero's three-tone palette (docs/ui/designs/new-header): every
// frame is downscaled to a coarse grid, then each pixel's luminance is mapped
// onto dark → accent → light, so whatever the clip shows comes out in the
// site's own colours. MID is the house --accent, not the mockup's near-twin.
//
// Pure: a flat RGBA array in, the same array recoloured in place, so the
// mapping is testable without a canvas.
export const DARK = [14, 14, 17]; // --bg
export const MID = [255, 107, 26]; // --accent
export const LIGHT = [255, 226, 200];

// The luminance split between the dark→mid ramp and the mid→light ramp.
const SPLIT = 0.62;

export function applyPalette(d) {
  for (let i = 0; i < d.length; i += 4) {
    let L = (0.299 * d[i] + 0.587 * d[i + 1] + 0.114 * d[i + 2]) / 255;
    // A little contrast before the ramp, so mid-greys spread instead of
    // pooling at the accent.
    L = Math.min(1, Math.max(0, (L - 0.5) * 1.4 + 0.5));
    const lo = L < SPLIT;
    const a = lo ? DARK : MID;
    const b = lo ? MID : LIGHT;
    const t = lo ? L / SPLIT : (L - SPLIT) / (1 - SPLIT);
    d[i] = a[0] + (b[0] - a[0]) * t;
    d[i + 1] = a[1] + (b[1] - a[1]) * t;
    d[i + 2] = a[2] + (b[2] - a[2]) * t;
  }
  return d;
}
