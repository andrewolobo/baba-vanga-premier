<script>
  // The parallax hero the video band replaced (2026-09-08). Kept whole for
  // the one-line revert in $lib/hero.js; markup, motion and styles are
  // verbatim from +page.svelte, nothing here changed in the move.

  // --- hero parallax -------------------------------------------------------
  let art, plate, copy;

  function heroMove(event) {
    const box = event.currentTarget.getBoundingClientRect();
    const x = (event.clientX - box.left) / box.width - 0.5;
    const y = (event.clientY - box.top) / box.height - 0.5;
    const shift = (node, mx, my, scale) => {
      if (node)
        node.style.transform =
          `translate3d(${(x * mx).toFixed(2)}px, ${(y * my).toFixed(2)}px, 0)` +
          (scale ? ` scale(${scale})` : '');
    };
    shift(art, -80, -40, 1.05);
    shift(plate, 46, 26);
    shift(copy, 18, 10);
  }

  const heroLeave = () => {
    for (const node of [art, plate, copy])
      if (node) node.style.transform = 'translate3d(0,0,0)';
  };
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<section class="hero" onmousemove={heroMove} onmouseleave={heroLeave}>
  <div class="plate" bind:this={plate}>
    <div class="orb light"></div>
    <div class="orb dark"></div>
  </div>
  <div class="notch"></div>
  <div class="art" bind:this={art}>
    <img src="/player.png" alt="" />
  </div>
  <div class="copy" bind:this={copy}>
    <div class="eyebrow"><span class="dot"></span>Premier League · Championship · League One · League Two</div>
    <h1>We call it before kick-off</h1>
    <p>
      Every fixture in the top four English divisions, called before kick-off and
      graded after. One call per match — and we say plainly when we are hedging.
    </p>
    <div class="actions">
      <a href="#tips" class="solid">See this week's calls</a>
      <a href="#record" class="ghost">Check the record</a>
    </div>
  </div>
</section>

<style>
  .hero {
    position: relative;
    background: var(--accent);
    overflow: hidden;
    min-height: 520px;
    isolation: isolate;
  }
  .plate {
    position: absolute; inset: -6%; z-index: 0;
    transition: transform 340ms cubic-bezier(0.2, 0.7, 0.3, 1);
  }
  .orb { position: absolute; border-radius: 50%; }
  .orb.light { right: -4%; top: -30%; width: 900px; height: 900px; background: rgba(255,255,255,0.07); }
  .orb.dark { left: -8%; bottom: -40%; width: 620px; height: 620px; background: rgba(0,0,0,0.06); }
  .notch {
    position: absolute; inset: 0; z-index: 3; pointer-events: none;
    background: var(--bg);
    clip-path: polygon(100% 34%, 100% 100%, 0 100%, 0 96%);
  }
  .art {
    position: absolute; z-index: 5; right: -2%; bottom: -4%;
    width: min(64%, 1000px); pointer-events: none;
    transition: transform 340ms cubic-bezier(0.2, 0.7, 0.3, 1);
    will-change: transform;
  }
  .art img { width: 100%; display: block; filter: drop-shadow(0 30px 60px rgba(0,0,0,0.28)); }
  .copy {
    position: relative; z-index: 4; max-width: var(--page); margin: 0 auto;
    padding: 96px 32px 120px;
    transition: transform 340ms cubic-bezier(0.2, 0.7, 0.3, 1);
  }
  /* Not flex: as a flex item the division list is one unbreakable box, so on a
     narrow viewport it wrapped as a whole and left the dot alone on its own
     line. Inline flow lets the text wrap around the dot instead. */
  .eyebrow {
    font-family: var(--mono); font-weight: 600; font-size: 12px; line-height: 1.6;
    letter-spacing: 0.22em; text-transform: uppercase; color: rgba(255,255,255,0.85);
  }
  .dot {
    display: inline-block; width: 8px; height: 8px; border-radius: 50%;
    background: var(--bg); margin-right: 10px; vertical-align: middle;
  }
  h1 {
    font-family: var(--display); font-weight: 800;
    font-size: clamp(48px, 7.4vw, 116px); line-height: 0.88; letter-spacing: -0.01em;
    text-transform: uppercase; color: #fff; margin: 22px 0 0; max-width: 12ch;
    text-wrap: balance;
  }
  .copy p {
    font-size: 18px; line-height: 1.55; color: rgba(255,255,255,0.92);
    max-width: 46ch; margin: 22px 0 0; font-weight: 500;
  }
  .actions { display: flex; flex-wrap: wrap; gap: 14px; margin-top: 34px; }
  .actions a {
    font-family: var(--display); font-weight: 700; font-size: 16px;
    letter-spacing: 0.1em; text-transform: uppercase; border-radius: 3px;
  }
  .solid { background: var(--bg); color: #fff; padding: 15px 30px; }
  .ghost { border: 2px solid rgba(255,255,255,0.7); color: #fff; padding: 13px 28px; }
  .actions a:hover { color: #fff; }

  @media (max-width: 940px) {
    .art { width: 78%; opacity: 0.35; }
    .copy { padding: 64px 18px 90px; }
  }
</style>
