<script>
  import { onMount } from 'svelte';
  import { getBook, pct, signed } from '$lib/api.js';

  let rows = $state([]);
  let error = $state(null);
  let loading = $state(true);

  onMount(async () => {
    try {
      rows = await getBook(null);
    } catch (e) {
      error = e.message;
    } finally {
      loading = false;
    }
  });
</script>

{#if loading}
  <p class="muted">Loading…</p>
{:else if error}
  <p class="error">{error}</p>
{:else if rows.length === 0}
  <p class="muted">No bets placed. Run <code>python -m engine.serve.book</code>.</p>
{:else}
  <table>
    <thead>
      <tr>
        <th>Date</th><th>Div</th><th>Fixture</th><th>Bet</th>
        <th class="num">Price</th>
        <th class="num">Model</th>
        <th class="num">Break-even</th>
        <th class="num">Edge</th>
        <th class="num">Close</th>
        <th class="num">CLV</th>
        <th>Result</th>
        <th class="num">P&amp;L</th>
      </tr>
    </thead>
    <tbody>
      {#each rows as b}
        <tr>
          <td class="muted">{b.match_date}</td>
          <td class="muted">{b.division}</td>
          <td>{b.home_team} <span class="muted">v</span> {b.away_team}</td>
          <td>{b.market === 'ou25' ? 'O/U 2.5' : '1X2'} <strong>{b.side}</strong></td>
          <td class="num">{b.price.toFixed(2)}</td>
          <td class="num">{pct(b.model_prob)}</td>
          <!-- raw 1/odds, vig-inclusive: the bar the model actually had to clear -->
          <td class="num muted">{pct(b.breakeven_prob)}</td>
          <td class="num pos">{signed(b.edge)}</td>
          <td class="num">{b.close_price ? b.close_price.toFixed(2) : '—'}</td>
          <td class="num" class:pos={b.clv > 0} class:neg={b.clv < 0}>
            {b.clv === null || b.clv === undefined ? '—' : signed(b.clv)}
          </td>
          <td>
            {#if b.outcome}
              <span class:pos={b.outcome === 'win'} class:neg={b.outcome === 'lose'}>
                {b.outcome}
              </span>
            {:else}<span class="muted">open</span>{/if}
          </td>
          <td class="num" class:pos={b.pnl > 0} class:neg={b.pnl < 0}>
            {b.pnl === null || b.pnl === undefined ? '—' : signed(b.pnl, 2)}
          </td>
        </tr>
      {/each}
    </tbody>
  </table>
{/if}

<style>
  .muted { color: var(--muted); }
  .error { color: var(--bad); }
  .pos { color: var(--good); }
  .neg { color: var(--bad); }
  code { background: var(--panel); padding: 0.1rem 0.35rem; border-radius: 3px; }
</style>
