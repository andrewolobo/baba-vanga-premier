<script>
  import { page } from '$app/stores';
  let { children } = $props();

  const tabs = [
    ['/', 'Fixtures'],
    ['/book', 'Paper book'],
    ['/performance', 'Performance']
  ];
</script>

<div class="shell">
  <header>
    <h1>baba<span>.</span>vanga<span>.</span>premier</h1>
    <nav>
      {#each tabs as [href, label]}
        <a {href} class:active={$page.url.pathname === href}>{label}</a>
      {/each}
    </nav>
  </header>

  <p class="banner">
    Probabilities are <strong>uncalibrated</strong> — raw Poisson pmf output from the
    P1 base head. Calibration lands in P3. Paper trading only; no money at stake.
  </p>

  {@render children()}
</div>

<style>
  :global(:root) {
    --bg: #0f1115;
    --panel: #171a21;
    --line: #262b36;
    --text: #e6e9ef;
    --muted: #8b94a7;
    --accent: #4f9cf9;
    --good: #3fbf7f;
    --bad: #e56a6a;
  }
  :global(body) {
    margin: 0;
    background: var(--bg);
    color: var(--text);
    font: 15px/1.5 ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif;
  }
  :global(table) { border-collapse: collapse; width: 100%; }
  :global(th), :global(td) {
    padding: 0.55rem 0.7rem;
    border-bottom: 1px solid var(--line);
    text-align: left;
    white-space: nowrap;
  }
  :global(th) { color: var(--muted); font-weight: 600; font-size: 0.82rem;
                text-transform: uppercase; letter-spacing: 0.04em; }
  :global(td.num), :global(th.num) { text-align: right; font-variant-numeric: tabular-nums; }
  .shell { max-width: 1180px; margin: 0 auto; padding: 1.5rem 1.25rem 4rem; }
  header { display: flex; align-items: baseline; gap: 1.5rem; flex-wrap: wrap; }
  h1 { font-size: 1.15rem; margin: 0; letter-spacing: -0.01em; }
  h1 span { color: var(--accent); }
  nav { display: flex; gap: 1rem; }
  nav a { color: var(--muted); text-decoration: none; padding: 0.2rem 0; font-size: 0.92rem; }
  nav a.active { color: var(--text); border-bottom: 2px solid var(--accent); }
  .banner {
    margin: 1rem 0 1.5rem; padding: 0.6rem 0.8rem; font-size: 0.85rem;
    color: var(--muted); background: var(--panel);
    border: 1px solid var(--line); border-left: 3px solid var(--accent); border-radius: 4px;
  }
</style>
