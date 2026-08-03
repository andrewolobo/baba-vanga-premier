<script>
  import { onMount } from 'svelte';
  import { getPredictions, DIVISIONS, breakEven, pct } from '$lib/api.js';

  let division = $state('');
  let rows = $state([]);
  let error = $state(null);
  let loading = $state(true);

  async function load() {
    loading = true;
    error = null;
    try {
      rows = await getPredictions(division || null);
    } catch (e) {
      error = e.message;
    } finally {
      loading = false;
    }
  }

  onMount(load);
  $effect(() => { division; load(); });

  // Display-only. The engine already applied this same rule when deciding what
  // to bet; recomputing it here would let the screen and the book disagree.
  const edge = (probability, price) => {
    const bar = breakEven(price);
    return bar === null ? null : probability - bar;
  };

  const byDay = $derived(
    Object.entries(
      rows.reduce((acc, r) => ((acc[r.match_date] ??= []).push(r), acc), {})
    ).sort(([a], [b]) => a.localeCompare(b))
  );
</script>

<div class="controls">
  {#each DIVISIONS as [code, label]}
    <button class:on={division === code} onclick={() => (division = code)}>{label}</button>
  {/each}
</div>

{#if loading}
  <p class="muted">Loading…</p>
{:else if error}
  <p class="error">{error}</p>
{:else if rows.length === 0}
  <p class="muted">
    No predictions yet. Run <code>python -m services.fixture_sync</code> then
    <code>python -m engine.serve.cycle</code>.
  </p>
{:else}
  {#each byDay as [day, fixtures]}
    <h2>{day}</h2>
    <table>
      <thead>
        <tr>
          <th>Div</th><th>Fixture</th>
          <th class="num">Home</th><th class="num">Draw</th><th class="num">Away</th>
          <th class="num">Over 2.5</th>
          <th class="num">Best edge</th>
          <th class="num">λ</th>
        </tr>
      </thead>
      <tbody>
        {#each fixtures as f}
          {@const edges = [
            ['H', edge(f.p_home, f.avg_h)],
            ['D', edge(f.p_draw, f.avg_d)],
            ['A', edge(f.p_away, f.avg_a)],
            ['O', edge(f.p_over25, f.avg_over25)]
          ].filter(([, v]) => v !== null)}
          {@const best = edges.length
            ? edges.reduce((a, b) => (b[1] > a[1] ? b : a))
            : null}
          <tr>
            <td class="div">{f.division}</td>
            <td>{f.home_team} <span class="muted">v</span> {f.away_team}</td>
            <td class="num">{pct(f.p_home)}</td>
            <td class="num">{pct(f.p_draw)}</td>
            <td class="num">{pct(f.p_away)}</td>
            <td class="num">{pct(f.p_over25)}</td>
            <td class="num">
              {#if best}
                <span class:pos={best[1] > 0.02} class:neg={best[1] <= 0}>
                  {best[0]} {best[1] >= 0 ? '+' : ''}{(100 * best[1]).toFixed(1)}pt
                </span>
              {:else}—{/if}
            </td>
            <td class="num muted">{f.lam_h.toFixed(2)}–{f.lam_a.toFixed(2)}</td>
          </tr>
        {/each}
      </tbody>
    </table>
  {/each}
{/if}

<style>
  .controls { display: flex; gap: 0.4rem; margin-bottom: 1.25rem; flex-wrap: wrap; }
  button {
    background: var(--panel); color: var(--muted); border: 1px solid var(--line);
    padding: 0.35rem 0.75rem; border-radius: 999px; cursor: pointer; font-size: 0.85rem;
  }
  button.on { color: var(--text); border-color: var(--accent); }
  h2 { font-size: 0.9rem; color: var(--muted); margin: 1.75rem 0 0.4rem; font-weight: 600; }
  .div { color: var(--muted); font-size: 0.8rem; }
  .muted { color: var(--muted); }
  .error { color: var(--bad); }
  .pos { color: var(--good); }
  .neg { color: var(--muted); }
  code { background: var(--panel); padding: 0.1rem 0.35rem; border-radius: 3px; }
</style>
