<script>
  // /results (docs/SEO_PLAN.md 2.6). The list itself is `$lib/ResultList.svelte`
  // — a date-grouped row list, shared with the front page's summary of the
  // last six. What stays here is the page around it: the division filter, the
  // last-60 / show-all switch, and this page's own error and empty states.
  //
  // The score is always shown. It used to sit behind a "Scores & claims"
  // toggle that was off by default, which defeats a layout built around the
  // scoreline; the claimed probability that shared that toggle now lives on
  // the match page alone.
  import { getTipResults, DIVISIONS } from '$lib/api.js';
  import { RESULTS_TITLE, RESULTS_DESCRIPTION } from '$lib/site.js';
  import { DEFAULT_LIMIT, MAX_LIMIT } from './limit.js';
  import ResultList from '$lib/ResultList.svelte';
  import PageHead from '$lib/PageHead.svelte';

  let { data } = $props();
  let results = $state(data.results);
  let error = $state(data.error);

  // 500 is the server's own ceiling (api/main.py, limit le=500) — the API
  // 400s above it, so "all" means "up to the server max".
  let division = $state('');
  let showAll = $state(false);
  let loading = $state(false);
  const limit = () => (showAll ? MAX_LIMIT : DEFAULT_LIMIT);

  async function load() {
    loading = true;
    error = null;
    try {
      results = await getTipResults(division || null, limit());
    } catch (e) {
      error = e.message;
    } finally {
      loading = false;
    }
  }

  // The opening list came with the page; only a change of filter or toggle
  // reads again. The first run is hydration, and is skipped by comparing with
  // what is already shown.
  let shown = `${division}|${showAll}`;
  $effect(() => {
    const key = `${division}|${showAll}`;
    if (key === shown) return;
    shown = key;
    load();
  });
</script>

<PageHead title={RESULTS_TITLE} path="/results" description={RESULTS_DESCRIPTION} />

<article class="page">
  <div class="head">
    <div class="headtop">
      <div class="kicker"><span class="dot" aria-hidden="true"></span>Settled</div>
      <div class="switch" role="group" aria-label="How many settled calls">
        <button class:on={!showAll} onclick={() => (showAll = false)}>Last {DEFAULT_LIMIT}</button>
        <button class:on={showAll} onclick={() => (showAll = true)}>Show all</button>
      </div>
    </div>
    <h1>Last time out</h1>
  </div>

  <p class="intro">
    Every call here was published before its kick-off and settled from the final score. A call is
    never revised and never removed, whichever way it went. The pooled figure they add up to is on
    <a href="/record">the record</a>.
  </p>

  <div class="tabs">
    {#each DIVISIONS as [code, label]}
      <button class:on={division === code} onclick={() => (division = code)}>{label}</button>
    {/each}
  </div>

  <!-- `error` is checked as well as emptiness: a failed fetch also leaves the
       list empty, and reporting that as "nothing graded yet" would present an
       outage as a record. -->
  {#if error}
    <p class="state bad">{error}</p>
  {:else if loading}
    <p class="state">Loading…</p>
  {:else if results.length === 0}
    <p class="state">Nothing graded yet.</p>
  {:else}
    <ResultList {results} />
  {/if}

  <footer class="fine">
    <p>
      Each row names the call as it was published. A team name in it is not a claim that the team
      won: most calls are double chance or a +1.5 handicap, and each row's match page says exactly
      what its call needed. <a href="/">Today's calls</a>.
    </p>
  </footer>
</article>

<style>
  .page { max-width: var(--page); margin: 0 auto; padding: 64px 32px 0; }
  .head { border-bottom: 1px solid var(--line); padding-bottom: 18px; }
  .headtop {
    display: flex; align-items: center; justify-content: space-between;
    flex-wrap: wrap; gap: 12px;
  }
  .kicker {
    display: inline-flex; align-items: center; gap: 7px;
    font-family: var(--mono); font-size: 11px; font-weight: 600; letter-spacing: 0.22em;
    text-transform: uppercase; color: var(--accent);
    background: rgba(255, 107, 26, 0.08); border: 1px solid rgba(255, 107, 26, 0.3);
    border-radius: 999px; padding: 4px 12px 4px 10px;
  }
  .dot {
    width: 6px; height: 6px; border-radius: 50%; background: var(--accent);
    animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
  }
  @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.35; } }
  h1 {
    font-family: var(--display); font-weight: 800; font-size: clamp(32px, 4vw, 52px);
    line-height: 1; text-transform: uppercase; color: #fff; margin: 14px 0 0;
  }
  .intro { margin: 16px 0 0; font-size: 15px; line-height: 1.65; color: var(--body); max-width: 70ch; }
  .switch { display: flex; gap: 4px; }
  .switch button {
    font-family: var(--mono); font-size: 11px; letter-spacing: 0.06em;
    text-transform: uppercase; padding: 5px 10px; border-radius: 3px;
    border: 1px solid var(--line); background: transparent; color: var(--muted);
    cursor: pointer;
  }
  .switch button:hover { border-color: var(--muted); color: var(--body); }
  .switch button.on { background: var(--bg); border-color: var(--accent); color: var(--accent); }

  .tabs { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 26px; }
  .tabs button {
    font-family: var(--display); font-weight: 700; font-size: 16px;
    letter-spacing: 0.09em; text-transform: uppercase; white-space: nowrap;
    line-height: 1.2; padding: 12px 22px; border-radius: 3px;
    border: 1px solid #33333c; background: transparent; color: var(--body);
    cursor: pointer;
  }
  .tabs button:hover { border-color: var(--muted); }
  .tabs button.on { background: var(--accent); border-color: var(--accent); color: var(--bg); }

  .state { margin-top: 26px; color: var(--muted); }
  .state.bad { color: var(--bad); }
  .fine { margin-top: 34px; padding-top: 18px; border-top: 1px solid var(--line); }
  .fine p {
    margin: 0; font-size: 12.5px; line-height: 1.6; color: var(--muted); max-width: 72ch;
  }

  @media (max-width: 820px) {
    .page { padding: 48px 18px 0; }
  }

  @media (prefers-reduced-motion: reduce) {
    .dot { animation: none; }
  }
</style>
