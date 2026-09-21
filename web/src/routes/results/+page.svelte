<script>
  // /results (docs/SEO_PLAN.md 2.6). Moved from the front page's #results
  // section unchanged: the settled cards, the division filter, the last-12 /
  // show-all switch, and the "Scores & claims" toggle that is off by default.
  //
  // The cards do not link to their match pages: that link is the part of 2.8
  // the owner has not taken (SEO_PLAN.md 2.8), so it stays off here as it is
  // on the front page.
  import { getTipResults, callLabel, DIVISIONS, pct } from '$lib/api.js';
  import { RESULTS_TITLE, RESULTS_DESCRIPTION } from '$lib/site.js';
  import PageHead from '$lib/PageHead.svelte';

  let { data } = $props();
  let results = $state(data.results);
  let error = $state(data.error);

  // 500 is the server's own ceiling (api/main.py, limit le=500) — the API
  // 400s above it, so "all" means "up to the server max".
  let division = $state('');
  let showAll = $state(false);
  let loading = $state(false);
  const limit = () => (showAll ? 500 : 12);

  // Scores and claimed probabilities are opt-in: the default card is the
  // graded call and its outcome, nothing else.
  let showDetail = $state(false);

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

  const divisionName = (code) => DIVISIONS.find(([c]) => c === code)?.[1] ?? code;

  // Built from the parts rather than parsed, so a date never shifts a day
  // across a timezone boundary — `new Date('2026-08-15')` is UTC midnight.
  const shortDay = (iso) => {
    const [y, m, d] = iso.split('-').map(Number);
    return new Date(y, m - 1, d).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' });
  };
</script>

<PageHead title={RESULTS_TITLE} path="/results" description={RESULTS_DESCRIPTION} />

<article class="page">
  <div class="head">
    <div>
      <div class="kicker">Settled</div>
      <h1>Last time out</h1>
    </div>
    <div class="controls">
      <div class="switch" role="group" aria-label="How many settled calls">
        <button class:on={!showAll} onclick={() => (showAll = false)}>Last 12</button>
        <button class:on={showAll} onclick={() => (showAll = true)}>Show all</button>
      </div>
      <div class="switch">
        <button class:on={showDetail} aria-pressed={showDetail}
          onclick={() => (showDetail = !showDetail)}>Scores &amp; claims</button>
      </div>
    </div>
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
    <div class="cards">
      {#each results as r}
        <div class="card" class:won={r.outcome === 'win'} class:lost={r.outcome === 'lose'}>
          <div class="cardtop">
            <!-- The score is the one the grader settled from; a row graded
                 before it was recorded (migration 006) falls back to "v"
                 rather than showing an invented line. -->
            <span class="cardfix">
              {#if showDetail && r.fthg !== null && r.fthg !== undefined}
                {r.home_team} <span class="score">{r.fthg}&ndash;{r.ftag}</span> {r.away_team}
              {:else}
                {r.home_team} v {r.away_team}
              {/if}
            </span>
            <span class="mark">{r.outcome === 'win' ? 'WON' : r.outcome === 'lose' ? 'LOST' : 'VOID'}</span>
          </div>
          {#if !division}
            <div class="league">{divisionName(r.division)}</div>
          {/if}
          <div class="cardfoot">
            <span>{callLabel(r.side, r.home_team, r.away_team)}{#if showDetail}
                &middot; claimed {pct(r.model_prob, 0)}{/if}</span>
            <span class="when">{shortDay(r.match_date)}</span>
          </div>
        </div>
      {/each}
    </div>
  {/if}

  <p class="fine">
    The card names the call as it was published. A team name on it is not a claim that the team
    won: most calls are double chance or a +1.5 handicap, and each one is listed with what it
    needed on its league page. <a href="/">Today's calls</a>.
  </p>
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
  .intro { margin: 16px 0 0; font-size: 15px; line-height: 1.65; color: var(--body); max-width: 70ch; }
  .controls { display: flex; gap: 12px; flex-wrap: wrap; }
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

  .cards {
    display: grid; grid-template-columns: repeat(auto-fill, minmax(230px, 1fr));
    gap: 12px; margin-top: 24px;
  }
  .card {
    background: var(--panel); border: 1px solid var(--line);
    border-left: 4px solid var(--muted); border-radius: 5px; padding: 14px 16px;
  }
  .card.won { border-left-color: var(--good); }
  .card.lost { border-left-color: var(--bad); }
  .cardtop { display: flex; justify-content: space-between; align-items: center; gap: 10px; }
  .cardfix { font-size: 14px; font-weight: 600; color: #e6e6ec; }
  .score { font-family: var(--mono); font-weight: 700; color: #fff; padding: 0 1px; }
  .mark { font-family: var(--mono); font-size: 12px; font-weight: 600; color: var(--muted); }
  .card.won .mark { color: var(--good); }
  .card.lost .mark { color: var(--bad); }
  .league { font-family: var(--mono); font-size: 11px; color: var(--muted); margin-top: 2px; }
  .cardfoot {
    display: flex; justify-content: space-between; gap: 10px; margin-top: 9px;
    font-family: var(--mono); font-size: 11px; color: var(--muted);
  }
  .when { color: #c9c9d2; }

  .state { margin-top: 26px; color: var(--muted); }
  .state.bad { color: var(--bad); }
  .fine { margin: 34px 0 0; font-size: 12.5px; line-height: 1.6; color: var(--muted); max-width: 72ch; }

  @media (max-width: 820px) {
    .page { padding: 48px 18px 0; }
  }
</style>
