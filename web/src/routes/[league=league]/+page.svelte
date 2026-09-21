<script>
  // A league page (docs/SEO_PLAN.md 2.4): the owner's intro, the division's
  // record line, its fixtures with their calls or "call on matchday", and
  // its recent results. Every fixture links to its match page. Shows only
  // what the front page already shows for the division -- no prices, no
  // return, no new probability (§6).
  import { onMount } from 'svelte';
  import { callLabel, pct } from '$lib/api.js';
  import { localKickoff, viewerZone } from '$lib/kickoff.js';
  import { leaguePath, leagueTitle, leagueDescription } from '$lib/leagues.js';
  import { matchPath, shortDay, outcomeWords } from '$lib/match.js';
  import PageHead from '$lib/PageHead.svelte';

  let { data } = $props();
  const league = $derived(data.league);
  const body = $derived(data.body);
  const record = $derived(body.record);

  // UK time in the server's HTML, the viewer's own once mounted (2.1).
  let zone = $state(null);
  onMount(() => (zone = viewerZone()));
  const kick = (f) => localKickoff(f.match_date, f.kickoff_time, zone ?? 'Europe/London');

  // The upcoming list by UK match date, soonest first (the API's order).
  const days = $derived(
    body.upcoming.reduce((acc, f) => {
      const last = acc.at(-1);
      if (last && last.date === f.match_date) last.fixtures.push(f);
      else acc.push({ date: f.match_date, fixtures: [f] });
      return acc;
    }, [])
  );
</script>

<PageHead title={leagueTitle(league)} path={leaguePath(league.code)} description={leagueDescription(league, record)} />

<article class="page">
  <div class="kicker">League predictions</div>
  <h1>{league.name} predictions</h1>
  <p class="intro">{league.intro}</p>

  <p class="record">
    {#if record.graded}
      <strong>{pct(record.strike_rate, 1)}</strong> of graded {league.name} calls came in:
      {record.won} of {record.graded}, over {record.matchweeks}
      matchweek{record.matchweeks === 1 ? '' : 's'}.
    {:else}
      No {league.name} calls graded yet.
    {/if}
    <span class="note">Strike rate, not a return.</span>
  </p>

  <section class="block">
    <h2>Calls and upcoming fixtures</h2>
    {#if days.length === 0}
      <p class="empty">
        No fixtures in the feed yet. The next round appears a few days before it is played.
      </p>
    {:else}
      <p class="sub">
        Calls are published on matchday at 06:00 UTC ·
        {zone ? `kick-offs in your local time (${zone})` : 'kick-offs in UK time'}
      </p>
      {#each days as day (day.date)}
        <div class="day">{shortDay(day.date)}</div>
        <ul class="list">
          {#each day.fixtures as f (f.fixture_id)}
            {@const k = kick(f)}
            <li>
              <a href={matchPath(f)}>
                <span class="time">{k ? k.time : '—'}{#if k?.dayShift}<sup>{k.dayShift > 0 ? '+1' : '−1'}</sup>{/if}</span>
                <span class="game">{f.home_name} <span class="vs">vs</span> {f.away_name}</span>
                {#if f.tip}
                  <span class="call">{callLabel(f.tip.side, f.home_name, f.away_name)}
                    <span class="conf">{pct(f.tip.model_prob, 0)}</span></span>
                {:else}
                  <span class="call pending">Call on matchday</span>
                {/if}
              </a>
            </li>
          {/each}
        </ul>
      {/each}
    {/if}
  </section>

  <section class="block">
    <h2>Recent results</h2>
    {#if body.results.length === 0}
      <p class="empty">No {league.name} results graded yet.</p>
    {:else}
      <ul class="list">
        {#each body.results as f (f.fixture_id)}
          <li>
            <a href={matchPath(f)}>
              <span class="time date">{shortDay(f.match_date)}</span>
              <span class="game">{f.home_name}
                <b>{f.tip.fthg ?? '–'}–{f.tip.ftag ?? '–'}</b>
                {f.away_name}</span>
              <span class="call" class:won={f.tip.outcome === 'win'} class:lost={f.tip.outcome === 'lose'}
                title="Our call {outcomeWords(f.tip.outcome)}"
                >{callLabel(f.tip.side, f.home_name, f.away_name)}
                {f.tip.outcome === 'win' ? '✓' : f.tip.outcome === 'lose' ? '✗' : ''}</span>
            </a>
          </li>
        {/each}
      </ul>
    {/if}
  </section>

  <p class="fine">
    The percentage beside a call is the probability the model gave it when it
    was published: uncalibrated, and not a price. <a href="/">Today's calls
    across all four leagues</a>.
  </p>
</article>

<style>
  .page { max-width: 880px; margin: 0 auto; padding: 56px 32px 0; }
  .kicker {
    font-family: var(--mono); font-size: 11px; letter-spacing: 0.22em;
    text-transform: uppercase; color: var(--accent);
  }
  h1 {
    font-family: var(--display); font-weight: 800; font-size: clamp(34px, 5vw, 52px);
    line-height: 1; text-transform: uppercase; color: #fff; margin: 10px 0 0;
  }
  .intro { margin: 16px 0 0; font-size: 16px; line-height: 1.65; color: var(--body); max-width: 68ch; }
  .record {
    margin: 22px 0 0; padding: 14px 18px; background: var(--panel); border: 1px solid var(--line);
    border-left: 3px solid var(--accent); border-radius: 5px; font-size: 15px; color: var(--body);
  }
  .record strong { font-family: var(--display); font-weight: 800; font-size: 22px; color: var(--accent); }
  .record .note { display: block; margin-top: 4px; font-family: var(--mono); font-size: 11px; color: var(--dim); }

  .block { margin-top: 40px; }
  h2 {
    font-family: var(--display); font-weight: 800; font-size: 26px;
    text-transform: uppercase; color: #fff; margin: 0;
  }
  .sub { margin: 4px 0 0; font-family: var(--mono); font-size: 11px; color: var(--muted); }
  .day {
    margin-top: 18px; padding: 10px 16px; background: var(--panel-2); font-family: var(--display);
    font-weight: 700; font-size: 16px; letter-spacing: 0.09em; text-transform: uppercase; color: #d6d6de;
  }
  .list { list-style: none; margin: 0; padding: 0; }
  .list li { border-bottom: 1px solid var(--line-2); }
  .list a {
    display: grid; grid-template-columns: 88px minmax(0, 1fr) auto; gap: 4px 14px;
    align-items: baseline; padding: 11px 16px; color: var(--body); text-decoration: none;
  }
  .list a:hover { background: var(--panel); color: var(--text); }
  .list a:focus-visible { outline: 2px solid var(--accent); outline-offset: -2px; }
  .time { font-family: var(--display); font-weight: 700; font-size: 17px; color: #fff; }
  .time.date { font-family: var(--mono); font-weight: 500; font-size: 11px; color: var(--muted); }
  .time sup { font-size: 10px; color: var(--muted); }
  .game { font-size: 15px; min-width: 0; }
  .game b { font-family: var(--mono); color: #fff; margin: 0 4px; }
  .vs { color: var(--muted); font-size: 13px; }
  .call {
    font-family: var(--display); font-weight: 700; font-size: 14px; text-transform: uppercase;
    color: var(--accent); text-align: right;
  }
  .call .conf { font-family: var(--mono); font-size: 11px; color: var(--muted); margin-left: 6px; }
  .call.pending { font-family: var(--mono); font-weight: 500; font-size: 11px; color: var(--dim); }
  .call.won { color: var(--good); }
  .call.lost { color: var(--bad); }
  .empty { margin: 10px 0 0; font-size: 14px; color: var(--muted); }
  .fine { margin: 40px 0 0; font-size: 12.5px; line-height: 1.6; color: var(--muted); max-width: 72ch; }

  @media (max-width: 820px) {
    .page { padding: 32px 18px 0; }
    .list a { grid-template-columns: 52px minmax(0, 1fr); padding: 11px 10px; }
    .call { grid-column: 2; text-align: left; }
  }
</style>
