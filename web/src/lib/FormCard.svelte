<script>
  // One side's last five league games as a form guide
  // (`docs/ui/team-page/Match Prediction.dc.html`): W/D/L as a wave, oldest
  // to latest, our call on each beneath it, and how many came in -- a count,
  // never a rate (docs/SEO_PLAN.md 2.5).
  //
  // Two call sites -- the match page, once per side, and the team page --
  // which is why this is a component. `games` is the API's list, newest
  // first, unchanged: nothing here recomputes a result or an outcome.
  //
  // The wave is colour and position only, so each column carries its words
  // for a screen reader and links to that match's page. `list` adds the same
  // games as text rows behind a <details>, which keeps them in the server's
  // HTML: a crawler reads the opponents and calls whether or not it is opened.
  // The team page lists the whole season below, so it passes `list={false}`.
  import { callLabel } from '$lib/api.js';
  import { clubBadge } from '$lib/badge.js';
  import Crest from '$lib/Crest.svelte';
  import { matchPath, formGame, formTally, formRecord, outcomeWords } from '$lib/match.js';

  let { title, games, list = true } = $props();

  const SLOTS = 5;
  // The latest game sits on the right edge whatever the count, so a side two
  // games into its season has three empty slots on the left and the two
  // cards on a match page line up game for game.
  const oldestFirst = $derived([...games].reverse());
  const empty = $derived(Math.max(0, SLOTS - games.length));
  const tally = $derived(formTally(games));

  const mark = (outcome) => (outcome === 'win' ? '✓' : outcome === 'lose' ? '✕' : '–');
  const RESULT = { W: 'Won', D: 'Drew', L: 'Lost' };
  const said = (g, view) =>
    `${RESULT[g.result] ?? 'No score'} ${view.score} ${view.where} ${view.opponent}. ` +
    `Our call, ${callLabel(g.side, g.home_name, g.away_name)}, ${outcomeWords(g.outcome)}.`;
</script>

<div class="card">
  <div class="head">
    <h3>{title}</h3>
    {#if games.length}<span class="record">{formRecord(games)}</span>{/if}
  </div>

  {#if games.length === 0}
    <p class="empty">No league games yet this season.</p>
  {:else}
    <div class="wave">
      <div class="axis" aria-hidden="true">
        <span>W</span><span>D</span><span>L</span><span class="callrow">Call</span>
      </div>
      <ol class="games">
        {#each { length: empty }, i (i)}
          <li class="slot" aria-hidden="true"></li>
        {/each}
        {#each oldestFirst as g (g.fixture_id)}
          {@const view = formGame(g)}
          {@const words = said(g, view)}
          <li>
            <a href={matchPath(g)} aria-label={words} title={words}>
              <span class="cell">{#if g.result === 'W'}<i class="w"></i>{/if}</span>
              <span class="cell">{#if g.result === 'D'}<i class="d"></i>{/if}</span>
              <span class="cell">{#if g.result === 'L'}<i class="l"></i>{/if}</span>
              <span class="call {g.outcome ?? ''}">{mark(g.outcome)}</span>
              <span class="score">{view.score}</span>
              <Crest name={view.opponentTeam} badge={clubBadge(view.opponentTeam)} size={18} />
            </a>
          </li>
        {/each}
      </ol>
    </div>

    <div class="foot">
      <p class="tally">Our calls: <b>{tally.won} of {tally.graded}</b> came in</p>
      <div class="strip" aria-hidden="true">
        {#each oldestFirst as g (g.fixture_id)}<span class={g.outcome ?? ''}></span>{/each}
      </div>
    </div>

    {#if list}
      <details>
        <summary><span class="show">Show matches</span><span class="hide">Hide matches</span></summary>
        <ol class="rows">
          {#each games as g (g.fixture_id)}
            {@const view = formGame(g)}
            <li>
              <a href={matchPath(g)}>
                <span class="res {g.result ?? ''}">{g.result ?? '–'}</span>
                <span class="rscore">{view.score}</span>
                <span class="opp">{view.where} {view.opponent}</span>
                <span class="ours" class:won={g.outcome === 'win'} class:lost={g.outcome === 'lose'}
                  >{callLabel(g.side, g.home_name, g.away_name)} {mark(g.outcome)}</span>
              </a>
            </li>
          {/each}
        </ol>
      </details>
    {/if}
  {/if}
</div>

<style>
  .card {
    background: var(--panel); border: 1px solid var(--line); border-radius: 8px;
    padding: 18px; display: flex; flex-direction: column; gap: 16px; min-width: 0;
  }
  .head { display: flex; justify-content: space-between; align-items: baseline; gap: 8px; }
  h3 {
    font-family: var(--display); font-weight: 700; font-size: 19px; letter-spacing: 0.02em;
    text-transform: uppercase; color: #fff; margin: 0; min-width: 0;
  }
  .record { font-family: var(--mono); font-size: 12px; color: var(--muted); white-space: nowrap; }
  .empty { margin: 0; font-size: 14px; color: var(--muted); }

  /* The axis and every column share one vertical rhythm: three 16px result
     rows, then the call row, so W/D/L line up across the card. */
  .wave { display: grid; grid-template-columns: 36px minmax(0, 1fr); gap: 0 8px; }
  .axis {
    display: flex; flex-direction: column; gap: 4px;
    font-family: var(--mono); font-size: 10px; color: var(--dim);
  }
  .axis span { height: 16px; line-height: 16px; }
  .axis .callrow { height: 18px; line-height: 18px; margin-top: 8px; text-transform: uppercase; }

  .games { list-style: none; margin: 0; padding: 0; display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 6px; }
  .games a {
    display: flex; flex-direction: column; align-items: center; gap: 4px;
    padding: 0 0 4px; border-radius: 4px; color: inherit; text-decoration: none;
  }
  .games a:hover { background: var(--panel-2); color: inherit; }
  .games a:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
  .slot::before {
    content: ''; display: block; height: 56px; margin: 0 auto; width: 18px;
    border: 1px dashed var(--line); border-radius: 3px;
  }
  .cell { height: 16px; display: grid; place-items: center; }
  .cell i { display: block; width: 16px; height: 16px; border-radius: 3px; }
  .cell i.w { background: var(--good); }
  .cell i.d { height: 7px; border-radius: 2px; background: var(--dim); }
  .cell i.l { background: var(--bad); }
  .call {
    margin-top: 8px; width: 18px; height: 18px; box-sizing: border-box; border-radius: 50%;
    border: 1.5px solid var(--dim); color: var(--dim);
    display: grid; place-items: center; font-size: 10px; font-weight: 700; line-height: 1;
  }
  .call.win { border-color: var(--good); color: var(--good); }
  .call.lose { border-color: var(--bad); color: var(--bad); }
  .score { margin-top: 2px; font-family: var(--mono); font-size: 11px; color: var(--text); white-space: nowrap; }

  .foot { display: flex; flex-direction: column; gap: 6px; border-top: 1px solid var(--line); padding-top: 12px; }
  .tally { margin: 0; font-family: var(--mono); font-size: 12px; color: var(--body); }
  .tally b { color: var(--text); font-weight: 600; }
  .strip { display: flex; gap: 3px; height: 4px; }
  .strip span { flex: 1; border-radius: 2px; background: var(--line); }
  .strip .win { background: var(--good); }
  .strip .lose { background: color-mix(in srgb, var(--bad) 35%, var(--panel)); }

  summary {
    display: inline-block; list-style: none; cursor: pointer;
    font-family: var(--mono); font-size: 11px; color: var(--body);
    border: 1px solid var(--line); border-radius: 4px; padding: 4px 9px;
  }
  summary::-webkit-details-marker { display: none; }
  summary:hover { border-color: var(--accent); color: var(--accent); }
  summary:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
  details[open] .show, details:not([open]) .hide { display: none; }

  .rows { list-style: none; margin: 8px 0 0; padding: 0; }
  .rows li { border-bottom: 1px solid var(--line-2); }
  .rows li:last-child { border-bottom: 0; }
  .rows a {
    display: grid; grid-template-columns: 22px 38px minmax(0, 1fr); gap: 2px 10px;
    align-items: baseline; padding: 8px 4px; font-size: 14px; color: var(--body); text-decoration: none;
  }
  .rows a:hover { background: var(--panel-2); color: var(--text); }
  .rows a:focus-visible { outline: 2px solid var(--accent); outline-offset: -2px; }
  .res {
    font-family: var(--mono); font-size: 11px; font-weight: 600; text-align: center;
    border-radius: 3px; padding: 2px 0; background: var(--panel-2); color: var(--muted);
  }
  .res.W { background: var(--good); color: var(--bg); }
  .res.D { background: var(--dim); color: var(--bg); }
  .res.L { background: var(--bad); color: #fff; }
  .rscore { font-family: var(--mono); color: #fff; }
  .opp { min-width: 0; }
  .ours { grid-column: 3; font-family: var(--mono); font-size: 11px; color: var(--muted); }
  .ours.won { color: var(--good); }
  .ours.lost { color: var(--bad); }
</style>
