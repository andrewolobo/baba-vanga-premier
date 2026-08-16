<script>
  import { page } from '$app/stores';
  let { children } = $props();

  // The public site is one page with three sections; /book and /performance are
  // the internal views that existed before it and are reached from the footer.
  const sections = [
    ['tips', 'Tips'],
    ['results', 'Results'],
    ['record', 'Record']
  ];

  const internal = $derived($page.url.pathname !== '/');
</script>

<header>
  <div class="bar">
    <a href="/" class="wordmark"><span>Baba</span><span class="accent">Vanga</span></a>

    <nav>
      {#each sections as [id, label]}
        <a href="/#{id}">{label}</a>
      {/each}
    </nav>

    <a href="/#tips" class="cta">This week's calls</a>
  </div>
</header>

{#if internal}
  <div class="shell">
    <p class="banner">
      Internal view. Probabilities are <strong>uncalibrated</strong> — raw Poisson pmf
      output from the P1 base head. The paper book is switched off
      (<code>CALIBRATION.md</code> §5); nothing here stakes money.
    </p>
    {@render children()}
  </div>
{:else}
  {@render children()}
{/if}

<footer>
  <div class="bar">
    <div>
      <div class="wordmark"><span>Baba</span><span class="accent">Vanga</span></div>
      <p class="claim">
        Every call is published before kick-off and graded afterwards. <strong>Strike
        rate is how often the call is right — it is not a return, and we do not
        publish one.</strong>
      </p>
    </div>
    <div class="small">
      <p>18+. Predictions are opinion, not certainty. Please gamble responsibly —
        <a href="https://www.begambleaware.org" rel="noreferrer noopener" target="_blank"
          >begambleaware.org</a
        ></p>
      <!-- /book and /performance are internal views: uncalibrated pmf output
           and a paper book that is switched off. They stay routable for the
           operator but are not linked from the public page. -->
    </div>
  </div>
</footer>

<style>
  /* The design's tokens. The four names the internal pages already use --
     panel, line, text, muted, accent, good, bad -- are kept and remapped rather
     than renamed, so /book and /performance restyle themselves for free. */
  :global(:root) {
    --bg: #0e0e11;
    --panel: #151519;
    --panel-2: #1d1d23;
    --line: #26262c;
    --line-2: #212127;
    --text: #efefef;
    --body: #c4c4cd;
    --muted: #8a8a94;
    --dim: #75757f;
    --accent: #ff6b1a;
    --accent-soft: #ff8c4d;
    --cta: #e4384f;
    --good: #2fb56b;
    --bad: #e4384f;
    --display: 'Barlow Condensed', 'Arial Narrow', system-ui, sans-serif;
    --sans: 'Barlow', system-ui, -apple-system, 'Segoe UI', sans-serif;
    --mono: 'IBM Plex Mono', ui-monospace, 'Cascadia Mono', monospace;
    --page: 1240px;
  }
  :global(*) { box-sizing: border-box; }
  :global(body) {
    margin: 0;
    background: var(--bg);
    color: var(--text);
    font: 15px/1.5 var(--sans);
    -webkit-font-smoothing: antialiased;
    overflow-x: hidden;
  }
  :global(a) { color: var(--accent); text-decoration: none; }
  :global(a:hover) { color: var(--accent-soft); }
  :global(::selection) { background: var(--accent); color: #fff; }

  :global(table) { border-collapse: collapse; width: 100%; }
  :global(th), :global(td) {
    padding: 0.55rem 0.7rem;
    border-bottom: 1px solid var(--line);
    text-align: left;
    white-space: nowrap;
  }
  :global(th) {
    color: var(--muted); font-weight: 600; font-size: 0.82rem;
    text-transform: uppercase; letter-spacing: 0.04em; font-family: var(--mono);
  }
  :global(td.num), :global(th.num) { text-align: right; font-variant-numeric: tabular-nums; }

  .bar {
    max-width: var(--page);
    margin: 0 auto;
    padding: 0 32px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 32px;
  }

  header {
    position: sticky; top: 0; z-index: 40;
    background: rgba(14, 14, 17, 0.92);
    backdrop-filter: blur(10px);
    border-bottom: 1px solid var(--line);
  }
  header .bar { height: 72px; }

  .wordmark {
    display: flex; align-items: baseline; gap: 10px;
    font-family: var(--display); font-weight: 800; font-size: 28px;
    letter-spacing: 0.04em; text-transform: uppercase; color: var(--text);
  }
  .wordmark .accent { color: var(--accent); }

  nav { display: flex; align-items: center; gap: 30px; }
  nav a {
    font-family: var(--display); font-weight: 600; font-size: 17px;
    letter-spacing: 0.08em; text-transform: uppercase; color: var(--muted);
  }
  nav a:hover { color: var(--text); }

  .cta {
    background: var(--cta); color: #fff; font-family: var(--display);
    font-weight: 700; font-size: 15px; letter-spacing: 0.1em;
    text-transform: uppercase; padding: 11px 22px; border-radius: 3px;
    white-space: nowrap;
  }
  .cta:hover { color: #fff; filter: brightness(1.1); }

  footer { border-top: 1px solid var(--line); background: #0b0b0e; margin-top: 90px; }
  footer .bar { padding: 40px 32px; align-items: flex-start; flex-wrap: wrap; }
  footer .wordmark { font-size: 22px; }
  .claim { max-width: 52ch; font-size: 14px; color: var(--muted); margin: 14px 0 0; }
  .claim strong { color: var(--body); font-weight: 600; }
  .small { font-family: var(--mono); font-size: 11px; color: #6c6c76; max-width: 44ch; }
  .small p { margin: 0 0 10px; }
  .links a { color: var(--muted); }

  /* Internal views keep the narrower measure they were designed for. */
  .shell { max-width: 1180px; margin: 0 auto; padding: 1.5rem 1.25rem 2rem; }
  .banner {
    margin: 1rem 0 1.5rem; padding: 0.6rem 0.8rem; font-size: 0.85rem;
    color: var(--muted); background: var(--panel);
    border: 1px solid var(--line); border-left: 3px solid var(--accent);
    border-radius: 4px;
  }
  .banner code { background: var(--panel-2); padding: 0.1rem 0.35rem; border-radius: 3px; }

  @media (max-width: 820px) {
    .bar { padding: 0 18px; gap: 16px; }
    header .bar { height: auto; padding-top: 12px; padding-bottom: 12px; flex-wrap: wrap; }
    nav { gap: 18px; order: 3; width: 100%; }
    .cta { padding: 9px 16px; font-size: 13px; }
  }
</style>
