<script>
  // /record (docs/SEO_PLAN.md 2.6, D10). Moved from the front page's #record
  // section unchanged: the per-division table, the two honesty paragraphs,
  // and -- owner-only, as before -- the rule provenance line and the split by
  // rule version. Nothing new is shown and no number is recomputed here.
  import { onMount } from 'svelte';
  import { DIVISIONS, pct } from '$lib/api.js';
  import { resolveOwner } from '$lib/owner.js';
  import { RECORD_TITLE, recordDescription } from '$lib/site.js';
  import { LEAGUES, leaguePath } from '$lib/leagues.js';
  import PageHead from '$lib/PageHead.svelte';

  let { data } = $props();
  const record = $derived(data.record);

  // The rule's name and parameters are for the owner, not testers
  // (`$lib/owner.js`: `/record?owner=1` to show, `?owner=0` to hide).
  let owner = $state(false);
  onMount(() => (owner = resolveOwner(window.location.search, window.localStorage)));

  const divisionName = (code) => DIVISIONS.find(([c]) => c === code)?.[1] ?? code;
</script>

<PageHead title={RECORD_TITLE} path="/record" description={recordDescription(record)} />

<article class="page">
  <div class="head">
    <div>
      <div class="kicker">Everything we have published</div>
      <h1>The record</h1>
    </div>
  </div>

  {#if data.error}
    <p class="state bad">{data.error}</p>
  {:else if record}
    <!-- Cells are nowrap, so on a narrow viewport the table is wider than the
         screen. It scrolls inside this box; without it the whole page scrolled
         sideways and every section inherited the overflow. -->
    <div class="tablewrap">
      <table class="record">
        <thead>
          <tr>
            <th>Division</th>
            <th class="num">Published</th>
            <th class="num">Graded</th>
            <th class="num">Right</th>
            <th class="num">Strike rate</th>
          </tr>
        </thead>
        <tbody>
          {#each record.by_division as d}
            <tr>
              <td>{divisionName(d.division)}</td>
              <td class="num">{d.published.toLocaleString()}</td>
              <td class="num">{d.graded.toLocaleString()}</td>
              <td class="num">{d.won.toLocaleString()}</td>
              <td class="num strike">{d.strike_rate == null ? '—' : pct(d.strike_rate, 1)}</td>
            </tr>
          {/each}
          <tr class="total">
            <td>All divisions</td>
            <td class="num">{record.published.toLocaleString()}</td>
            <td class="num">{record.graded.toLocaleString()}</td>
            <td class="num">{record.won.toLocaleString()}</td>
            <td class="num strike">{record.strike_rate == null ? '—' : pct(record.strike_rate, 1)}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="honesty">
      <h2>What this number is, and what it is not</h2>
      <p>
        <strong>It is honest about accuracy.</strong> Every call above was written
        to the database before the match was played and settled from the result
        afterwards. Nothing is added later, nothing is removed, and there is one
        call per fixture — the database refuses a second one.
      </p>
      <p>
        <strong>It is not a return.</strong> A high strike rate is mostly a
        property of backing short prices, not of being better than the market.
        Measured over eleven seasons at the prices a customer can actually get,
        this rule does not make money to any degree we can demonstrate. We do not
        publish a profit figure because we cannot support one.
      </p>
      {#if owner && record.rule}
        <p class="mono prov">
          rule {record.rule.rule_version} · floor {record.rule.floor}{record.rule
            .ceiling
            ? ` · ceiling ${record.rule.ceiling}`
            : ''}
        </p>
      {/if}
    </div>

    <!-- The headline above pools every rule version (B16 reversed 2026-08-21).
         This table is the split behind it, so the owner can see what each
         rule contributed to the one public number. Hidden while only one
         version exists, so nothing on the page changes until it has to -- and
         owner-only, like the provenance line above. -->
    {#if owner && record.by_rule && record.by_rule.length > 1}
      <div class="tablewrap">
        <table class="record versions">
          <thead>
            <tr>
              <th>Rule version</th>
              <th class="num">Published</th>
              <th class="num">Graded</th>
              <th class="num">Right</th>
              <th class="num">Strike rate</th>
            </tr>
          </thead>
          <tbody>
            {#each record.by_rule as v}
              <tr class:current={v.rule_version === record.rule?.rule_version}>
                <td class="mono">{v.rule_version}</td>
                <td class="num">{v.published.toLocaleString()}</td>
                <td class="num">{v.graded.toLocaleString()}</td>
                <td class="num">{v.won.toLocaleString()}</td>
                <td class="num strike">{v.strike_rate == null ? '—' : pct(v.strike_rate, 1)}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {/if}

    <p class="fine">
      Call by call: <a href="/results">the latest results</a>. By division:
      {#each LEAGUES as league, i (league.code)}<a href={leaguePath(league.code)}>{league.name}</a
        >{i < LEAGUES.length - 1 ? ', ' : '.'}{/each}
      Today's calls are on <a href="/">the front page</a>.
    </p>
  {/if}
</article>

<style>
  .page { max-width: var(--page); margin: 0 auto; padding: 64px 32px 0; }
  .head {
    display: flex; align-items: flex-end; justify-content: space-between;
    flex-wrap: wrap; gap: 16px;
  }
  .kicker {
    font-family: var(--mono); font-size: 11px; letter-spacing: 0.22em;
    text-transform: uppercase; color: var(--accent);
  }
  h1 {
    font-family: var(--display); font-weight: 800; font-size: clamp(32px, 4vw, 52px);
    line-height: 1; text-transform: uppercase; color: #fff; margin: 10px 0 0;
  }
  .mono { font-family: var(--mono); }

  .tablewrap { overflow-x: auto; }
  .record { margin-top: 24px; min-width: 460px; }
  .record .strike { font-weight: 700; color: var(--accent); }
  .record .total td { border-top: 1px solid var(--line); font-weight: 700; color: #fff; }
  .versions .current td { color: #fff; }
  .honesty { margin-top: 34px; max-width: 74ch; }
  .honesty h2 {
    font-family: var(--display); font-weight: 700; font-size: 24px;
    text-transform: uppercase; color: #fff; margin: 0 0 12px;
  }
  .honesty p { font-size: 15px; line-height: 1.7; color: var(--body); margin: 0 0 14px; }
  .honesty strong { color: #fff; }
  .prov { font-size: 11px; color: var(--dim); }

  .state { margin-top: 26px; color: var(--muted); }
  .state.bad { color: var(--bad); }
  .fine { margin: 34px 0 0; font-size: 12.5px; line-height: 1.6; color: var(--muted); max-width: 72ch; }

  @media (max-width: 820px) {
    .page { padding: 48px 18px 0; }
  }
</style>
