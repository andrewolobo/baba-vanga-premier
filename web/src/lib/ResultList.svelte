<script>
  // Settled calls as a date-grouped row list
  // (`docs/ui/list-items/Predictions List.dc.html`): one row per call, grouped
  // under the day it was played, with colour reserved for the outcome so the
  // scoreline reads first.
  //
  // Two call sites — `/results` in full, and the front page's summary of the
  // last six (docs/SEO_PLAN.md 2.6) — which is why this is a component rather
  // than markup on a page. It renders the list and nothing around it: the
  // heading, the link out, the error and empty states and the fine print
  // differ between the two and stay with the page.
  //
  // The rows are the API's own, unchanged. Nothing here recomputes an
  // outcome, a score or a call.
  import { callLabel } from '$lib/api.js';
  import { fixtureBadges } from '$lib/badge.js';
  import { matchPath, divisionName, shortDay } from '$lib/match.js';
  import Crest from '$lib/Crest.svelte';

  // `summary` is the per-day "2/3 won · 1 void" tally. It is a record claim
  // about that day, so it may only be shown when the list holds the whole
  // day: the front page cuts at six rows, which truncates the last group, and
  // a tally over the rows that survived the cut would misstate the day (a 2/3
  // day shown as "1/2 won"). Only the caller knows whether it truncated, so
  // it decides.
  let { results, summary = true } = $props();

  // The API orders by match date, newest first, so a day's rows are already
  // contiguous and grouping is a fold — no re-sort, and no assumption about
  // dates the list does not contain.
  const groups = $derived.by(() => {
    const out = [];
    for (const r of results) {
      if (out.at(-1)?.date !== r.match_date) out.push({ date: r.match_date, rows: [] });
      out.at(-1).rows.push(r);
    }
    return out;
  });

  // "3/4 won · 1 void". A void is counted apart rather than folded into the
  // denominator: it was not a losing call, and counting it as one would
  // understate the day.
  function summarise(rows) {
    const voids = rows.filter((r) => r.outcome === 'void').length;
    const graded = rows.length - voids;
    const won = rows.filter((r) => r.outcome === 'win').length;
    const parts = [];
    if (graded) parts.push(`${won}/${graded} won`);
    if (voids) parts.push(`${voids} void`);
    return parts.join(' · ');
  }

  // The score the grader settled from. A row graded before it was recorded
  // (migration 006) has none, and shows a dash rather than an invented line.
  const scored = (r) =>
    r.fthg !== null && r.fthg !== undefined && r.ftag !== null && r.ftag !== undefined;

  const outcomeWord = (o) => (o === 'win' ? 'Won' : o === 'lose' ? 'Lost' : 'Void');
</script>

<div class="legend">
  <span><i class="won" aria-hidden="true"></i>Won</span>
  <span><i class="lost" aria-hidden="true"></i>Lost</span>
  <span><i aria-hidden="true"></i>Void</span>
</div>

{#each groups as g (g.date)}
  <section class="group">
    <div class="grouphead">
      <h3 class="groupdate">{shortDay(g.date)}</h3>
      <div class="rule" aria-hidden="true"></div>
      {#if summary}<div class="groupsummary">{summarise(g.rows)}</div>{/if}
    </div>

    <div class="rows">
      {#each g.rows as r (r.tip_id)}
        {@const badge = fixtureBadges(r.home_team, r.away_team)}
        {@const hasScore = scored(r)}
        <a class="row" class:won={r.outcome === 'win'} class:lost={r.outcome === 'lose'}
          href={matchPath(r)}>
          <span class="bar" aria-hidden="true"></span>
          <span class="league">{divisionName(r.division)}</span>

          <span class="side home">
            <span class="club">{r.home_team}</span>
            <Crest name={r.home_team} badge={badge.home} size={22} />
          </span>
          <!-- Emphasis is on the side that won the match, not on our call: a
               team name is not what was published (see each page's note). -->
          <span class="hs" class:top={hasScore && r.fthg >= r.ftag}>{hasScore ? r.fthg : '—'}</span>
          <span class="sep" aria-hidden="true">{hasScore ? '–' : ''}</span>
          <span class="as" class:top={hasScore && r.ftag >= r.fthg}>{hasScore ? r.ftag : '—'}</span>
          <span class="side away">
            <Crest name={r.away_team} badge={badge.away} size={22} />
            <span class="club">{r.away_team}</span>
          </span>

          <span class="pick">
            <span class="picklabel">Pick</span>
            <span class="pickcall">{callLabel(r.side, r.home_team, r.away_team)}</span>
          </span>
          <span class="status">{outcomeWord(r.outcome)}</span>
        </a>
      {/each}
    </div>
  </section>
{/each}

<style>
  /* Written narrow-first: the row is a stacked scoreboard by default and
     becomes the wide single-line grid at 761px. The two share one DOM and
     differ only in `grid-template-areas`, so nothing is rendered twice. */
  .legend {
    display: flex; align-items: center; gap: 18px; flex-wrap: wrap;
    font-family: var(--mono); font-size: 10.5px; letter-spacing: 0.12em;
    text-transform: uppercase; color: var(--muted);
    border-bottom: 1px solid var(--line); padding: 14px 0 15px; margin-top: 22px;
  }
  .legend span { display: inline-flex; align-items: center; gap: 8px; }
  .legend i { width: 3px; height: 12px; display: inline-block; background: var(--muted); }
  .legend i.won { background: var(--good); }
  .legend i.lost { background: var(--bad); }

  .group { margin-top: 28px; }
  .grouphead { display: flex; align-items: baseline; gap: 12px; padding-bottom: 9px; }
  .groupdate {
    font-family: var(--mono); font-weight: 500; font-size: 11.5px; letter-spacing: 0.14em;
    text-transform: uppercase; color: var(--body); white-space: nowrap; margin: 0;
  }
  .rule { flex: 1; height: 1px; background: var(--line-2); }
  .groupsummary {
    font-family: var(--mono); font-size: 10.5px; letter-spacing: 0.1em;
    text-transform: uppercase; color: var(--muted); white-space: nowrap;
  }

  .rows { display: flex; flex-direction: column; gap: 3px; }

  .row {
    display: grid;
    grid-template-columns: 3px minmax(0, 1fr) auto;
    grid-template-areas:
      'bar league status'
      'bar home   hs'
      'bar away   as'
      'bar pick   pick';
    align-items: center;
    row-gap: 2px;
    background: var(--panel);
    color: inherit; text-decoration: none;
    transition: background 0.14s ease;
  }
  .row:hover { background: var(--panel-2); color: inherit; }
  /* Inset, so the ring is not clipped by the 3px gap between rows. */
  .row:focus-visible { outline: 2px solid var(--accent); outline-offset: -2px; }

  .bar { grid-area: bar; align-self: stretch; background: var(--muted); }
  .row.won .bar { background: var(--good); }
  .row.lost .bar { background: var(--bad); }

  .league {
    grid-area: league; padding: 10px 0 2px 12px;
    font-family: var(--mono); font-size: 10px; letter-spacing: 0.13em;
    text-transform: uppercase; color: var(--muted);
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }
  .status {
    grid-area: status; padding: 10px 12px 2px 0; text-align: right; white-space: nowrap;
    font-family: var(--mono); font-size: 10px; letter-spacing: 0.14em;
    text-transform: uppercase; color: var(--muted);
  }
  .row.won .status { color: var(--good); }
  .row.lost .status { color: var(--bad); }

  .side { display: flex; align-items: center; gap: 9px; min-width: 0; padding: 2px 0 2px 12px; }
  /* Narrow: the crest leads on both lines, so the two clubs align. Wide
     (below) the home side runs name-then-crest, hugging the score. */
  .side.home { grid-area: home; flex-direction: row-reverse; justify-content: flex-end; }
  .side.away { grid-area: away; }
  .club {
    min-width: 0; font-size: 14px; color: var(--body);
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }

  .hs { grid-area: hs; }
  .as { grid-area: as; }
  .hs, .as {
    padding-right: 12px; text-align: right;
    font-family: var(--mono); font-variant-numeric: tabular-nums;
    font-size: 16px; font-weight: 600; color: var(--dim);
  }
  .hs.top, .as.top { color: #fff; }
  .sep { display: none; }

  .pick {
    grid-area: pick; display: flex; align-items: baseline; gap: 7px; min-width: 0;
    padding: 3px 12px 10px; font-family: var(--mono); font-size: 11.5px; color: var(--body);
  }
  .picklabel {
    flex: none; font-size: 9.5px; letter-spacing: 0.16em;
    text-transform: uppercase; color: var(--dim);
  }
  .pickcall { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

  @media (max-width: 820px) {
    .groupdate { letter-spacing: 0.1em; }
    .groupsummary { letter-spacing: 0.06em; }
  }

  @media (min-width: 761px) {
    .row {
      /* The pick column holds the longest call the rule publishes
         ("AFC Wimbledon Away +1.5") without ellipsis; the two 1fr team
         columns absorb the difference, and the clubs hug the score. */
      grid-template-columns:
        3px 132px minmax(0, 1fr) 42px 16px 42px minmax(0, 1fr) 244px 72px;
      grid-template-areas: 'bar league home hs sep as away pick status';
      row-gap: 0;
    }
    .league { padding: 0 0 0 16px; }
    .status { padding: 0 16px 0 0; }
    .side { padding: 15px 0; }
    .side.home { flex-direction: row; justify-content: flex-end; }
    .side.home .club { text-align: right; }
    .side.away { padding-left: 0; }
    .hs, .as { font-size: 18px; padding-right: 0; }
    .as { text-align: left; }
    .sep {
      display: block; text-align: center;
      font-family: var(--mono); font-size: 13px; color: var(--dim);
    }
    .pick { padding: 0 10px; }
  }

  @media (prefers-reduced-motion: reduce) {
    .row { transition: none; }
  }
</style>
