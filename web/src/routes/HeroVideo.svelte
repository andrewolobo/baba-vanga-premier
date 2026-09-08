<script>
  // The pixel-video hero (owner design, docs/ui/designs/new-header,
  // 2026-09-08). The clip never shows raw: every frame is drawn onto a
  // coarse canvas grid and recoloured through the site's three tones
  // ($lib/pixel.js), so the band reads as graphics, not footage. Until the
  // video has a frame — or when it never will (offline, autoplay refused) —
  // an animated noise field stands in, so nothing here can look broken.
  // Revert to the parallax hero: $lib/hero.js.
  import { onMount } from 'svelte';
  import { applyPalette } from '$lib/pixel.js';

  let canvas;
  let video;

  // One palette block's edge in CSS pixels — the mockup's chosen coarseness.
  const PX = 12;

  onMount(() => {
    const ctx = canvas.getContext('2d', { willReadFrequently: true });
    let raf;
    let grid = null; // the noise field, rebuilt whenever the grid resizes

    const noise = (w, h) => {
      if (!grid) {
        grid = new Float32Array(w * h);
        for (let i = 0; i < grid.length; i++) grid[i] = Math.random() * 0.5;
      }
      const t = performance.now() / 1000;
      for (let k = 0; k < w * h * 0.04; k++)
        grid[(Math.random() * grid.length) | 0] =
          Math.random() < 0.85 ? Math.random() * 0.45 : 0.6 + Math.random() * 0.4;
      const sweep = ((t * 0.35) % 1.4) * w - w * 0.2;
      for (let y = 0; y < h; y++)
        for (let x = 0; x < w; x++) {
          let L = grid[y * w + x];
          const dx = Math.abs(x - sweep - y * 0.35);
          if (dx < 3) L = Math.min(1, L + (3 - dx) * 0.25);
          const v = (L * 255) | 0;
          ctx.fillStyle = `rgb(${v},${v},${v})`;
          ctx.fillRect(x, y, 1, 1);
        }
    };

    const frame = () => {
      // Sized from the container every frame, so a resize just lands on the
      // next tick; the canvas stays coarse and CSS stretches it back up.
      const W = canvas.parentElement.clientWidth || 1200;
      const H = canvas.parentElement.clientHeight || 300;
      const w = Math.max(8, Math.round(W / PX));
      const h = Math.max(4, Math.round(H / PX));
      if (canvas.width !== w || canvas.height !== h) {
        canvas.width = w;
        canvas.height = h;
        grid = null;
      }
      if (video && video.readyState >= 2) ctx.drawImage(video, 0, 0, w, h);
      else noise(w, h);
      const img = ctx.getImageData(0, 0, w, h);
      applyPalette(img.data);
      ctx.putImageData(img, 0, 0);
    };

    // Reduced motion means no clip and no animation loop: one recoloured
    // noise frame stands as a static backdrop (the CSS below stills the
    // blink and glitch to match).
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      frame();
      return;
    }

    video.play().catch(() => {}); // refused autoplay: the noise field stays

    const loop = () => {
      raf = requestAnimationFrame(loop);
      frame();
    };
    loop();
    return () => cancelAnimationFrame(raf);
  });
</script>

<section class="hero">
  <canvas bind:this={canvas}></canvas>
  <video bind:this={video} src="/header-video.mp4" muted loop playsinline preload="auto" aria-hidden="true"></video>
  <div class="shade"></div>
  <div class="scan"></div>
  <div class="topline"></div>
  <div class="inner">
    <!-- Two halves: one line on desktop, two snug chips stacked on a
         phone (the mid separator goes; each chip keeps its own background,
         so no full-width block with a ragged second line). -->
    <div class="eyebrow">
      <span class="grp">
        <span class="blink"></span>
        <span>Premier League</span><span class="sep">/</span>
        <span>Championship</span>
      </span>
      <span class="sep mid">/</span>
      <span class="grp">
        <span>League One</span><span class="sep">/</span>
        <span>League Two</span>
      </span>
    </div>
    <h1>We call<br />it before<br />kick-off</h1>
  </div>
</section>

<style>
  .hero {
    position: relative;
    height: 300px;
    overflow: hidden;
    background: var(--bg);
  }
  canvas {
    position: absolute; inset: 0;
    width: 100%; height: 100%; display: block;
    image-rendering: pixelated;
  }
  video { display: none; }
  .shade {
    position: absolute; inset: 0; pointer-events: none;
    background: linear-gradient(90deg,
      rgba(14, 14, 17, 0.9) 0%, rgba(14, 14, 17, 0.82) 55%,
      rgba(14, 14, 17, 0.35) 78%, rgba(14, 14, 17, 0) 92%);
  }
  .scan {
    position: absolute; inset: 0; pointer-events: none;
    background: repeating-linear-gradient(0deg, rgba(0, 0, 0, 0.28) 0 2px, transparent 2px 4px);
    mix-blend-mode: multiply;
  }
  .topline { position: absolute; top: 0; left: 0; right: 0; height: 4px; background: var(--accent); }
  /* The text column is the page's own: same max-width and side padding as
     the header's .bar, so the strip and headline start exactly under the
     wordmark rather than at the viewport edge (owner correction
     2026-09-08 — left-justified, in line with the rest of the page). */
  .inner {
    position: relative; height: 100%;
    max-width: var(--page); margin: 0 auto;
    display: flex; flex-direction: column; align-items: flex-start;
    justify-content: center; gap: 14px;
    padding: 0 32px;
    pointer-events: none;
  }
  /* Below the nav breakpoint the strip shrinks and splits into two snug
     chips — at full size it swallowed a third of the band on a phone. */
  .eyebrow {
    display: flex; align-items: center;
    gap: 14px; flex-wrap: wrap;
    align-self: flex-start;
    font-family: var(--mono); font-weight: 600; font-size: 12px;
    letter-spacing: 0.32em; text-transform: uppercase; color: var(--accent);
    background: var(--bg); padding: 8px 14px 8px 12px;
  }
  .grp { display: inline-flex; align-items: center; gap: 14px; white-space: nowrap; }
  .blink {
    width: 9px; height: 9px; background: var(--accent);
    box-shadow: 0 0 12px var(--accent);
    animation: bvblink 1.4s steps(2) infinite;
  }
  .sep { opacity: 0.5; }
  h1 {
    margin: 0;
    font-family: var(--display); font-weight: 800;
    font-size: clamp(36px, 4.2vw, 64px); line-height: 0.9; letter-spacing: -0.01em;
    text-transform: uppercase; color: #fff;
    text-shadow: 0 0 24px rgba(14, 14, 17, 0.9);
    animation: bvglitch 6s infinite;
  }
  @keyframes bvblink {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.25; }
  }
  @keyframes bvglitch {
    0%, 92%, 100% { transform: translate(0, 0); }
    94% { transform: translate(-4px, 2px); }
    96% { transform: translate(4px, -2px); }
    98% { transform: translate(-2px, 0); }
  }
  @media (max-width: 820px) {
    .inner { padding: 0 18px; } /* the .bar's own narrow padding */
    .eyebrow {
      flex-direction: column; align-items: flex-start; gap: 5px;
      align-self: flex-start;
      font-size: 9px; letter-spacing: 0.18em; line-height: 1.2;
      background: none; padding: 0;
    }
    .eyebrow .mid { display: none; }
    .grp { gap: 8px; background: var(--bg); padding: 5px 9px 5px 8px; }
    .blink { width: 7px; height: 7px; }
    /* The desktop clamp floors at 36px, which reads small on a phone; the
       headline is the band's one job there, so it scales with the viewport
       instead (~49px at 390px, still three lines inside the 300px band). */
    h1 { font-size: clamp(42px, 12.5vw, 56px); }
  }
  @media (prefers-reduced-motion: reduce) {
    .blink, h1 { animation: none; }
  }
</style>
