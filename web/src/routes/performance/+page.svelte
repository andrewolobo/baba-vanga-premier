<script>
  import { onMount } from 'svelte';
  import { getPerformance, getHealth, pct, signed } from '$lib/api.js';

  let rows = $state([]);
  let health = $state(null);
  let error = $state(null);
  let loading = $state(true);

  onMount(async () => {
    try {
      [rows, health] = await Promise.all([getPerformance(), getHealth()]);
    } catch (e) {
      error = e.message;
    } finally {
      loading = false;
    }
  });
</script>

<p class="note">
  <strong>CLV is the primary metric.</strong> ROI is confirmatory and hit rate is a
  diagnostic only — on a few hundred bets ROI is mostly noise, and hit rate says
  almost nothing about whether the prices taken were good.
</p>

{#if loading}
  <p class="muted">Loading…</p>
{:else if error}
  <p class="error">{error}</p>
{:else}
  {#if health?.model}
    <p class="muted small">
      Serving <code>{health.model.model_version}</code>
      ({health.model.config_label}, fitted {health.model.fitted_at.slice(0, 10)},
      n_train {health.model.n_train.toLocaleString()})
    </p>
  {/if}

  {#if rows.length === 0}
    <p class="muted">Nothing graded yet.</p>
  {:else}
    <table>
      <thead>
        <tr>
          <th>Div</th><th>Market</th>
          <th class="num">Bets</th>
          <th class="num">Mean CLV</th>
          <th class="num">Beat close</th>
          <th class="num">P&amp;L</th>
          <th class="num">ROI</th>
          <th class="num">Hit rate</th>
        </tr>
      </thead>
      <tbody>
        {#each rows as r}
          <tr>
            <td>{r.division}</td>
            <td>{r.market === 'ou25' ? 'O/U 2.5' : '1X2'}</td>
            <td class="num">{r.bets}</td>
            <td class="num strong" class:pos={r.mean_clv > 0} class:neg={r.mean_clv < 0}>
              {signed(r.mean_clv, 4)}
            </td>
            <td class="num">{pct(r.beat_close_rate)}</td>
            <td class="num" class:pos={r.pnl > 0} class:neg={r.pnl < 0}>
              {r.pnl === null ? '—' : signed(r.pnl, 2)}
            </td>
            <td class="num muted">{pct(r.roi)}</td>
            <td class="num muted">{pct(r.hit_rate)}</td>
          </tr>
        {/each}
      </tbody>
    </table>
  {/if}
{/if}

<style>
  .note {
    font-size: 0.85rem; color: var(--muted); background: var(--panel);
    border: 1px solid var(--line); border-radius: 4px; padding: 0.6rem 0.8rem;
    margin-bottom: 1.25rem;
  }
  .small { font-size: 0.82rem; }
  .muted { color: var(--muted); }
  .error { color: var(--bad); }
  .pos { color: var(--good); }
  .neg { color: var(--bad); }
  .strong { font-weight: 600; }
  code { background: var(--panel); padding: 0.1rem 0.35rem; border-radius: 3px; }
</style>
