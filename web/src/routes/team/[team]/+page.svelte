<script>
  // A team page (docs/SEO_PLAN.md 2.5): the club's next fixtures with their
  // calls, how many of our calls on it have come in, and every settled call
  // this season from the club's own side. Every fixture links to its match
  // page, and the league to its league page (2.8).
  //
  // The tally is counts, never a rate ($lib/teams.js). Shows only what the
  // front page already shows -- no prices, no return, no new probability
  // (§6).
  import { onMount } from 'svelte';
  import { callLabel, pct } from '$lib/api.js';
  import { localKickoff, viewerZone } from '$lib/kickoff.js';
  import { leaguePath } from '$lib/leagues.js';
  import { matchPath, shortDay, divisionName, outcomeWords } from '$lib/match.js';
  import { teamPath, teamTitle, teamDescription, tallySentence } from '$lib/teams.js';
  import PageHead from '$lib/PageHead.svelte';

  let { data } = $props();
  const team = $derived(data.team);

  // UK time in the server's HTML, the viewer's own once mounted (2.1).
  let zone = $state(null);
  onMount(() => (zone = viewerZone()));
  const kick = (f) => localKickoff(f.match_date, f.kickoff_time, zone ?? 'Europe/London');

  // A settled call from this club's side: who it played, where, and the score
  // the grader settled from, read the club's way round.
  const seen = (c) => ({
    opponent: c.at_home ? c.away_name : c.home_name,
    where: c.at_home ? 'v' : 'at',
    score: c.fthg == null ? '–' : c.at_home ? `${c.fthg}–${c.ftag}` : `${c.ftag}–${c.fthg}`
  });
</script>

<PageHead
  title={teamTitle(team)}
  path={teamPath(team.team_id, team.slug)}
  description={teamDescription(team)}
/>

<article class="page">
  <div class="kicker">
    Team predictions · <a href={leaguePath(team.division)}>{divisionName(team.division)}</a>
  </div>
  <h1>{team.name} predictions</h1>
  {#if team.venue}
    <p class="meta">{team.venue}</p>
  {/if}

  <p class="record">
    <strong>{tallySentence(team)}</strong>
    <span class="note">Counts, not a strike rate — too few games for one. Strike rate, not a
      return: <a href="/record">the record</a>.</span>
  </p>

  <section class="block">
    <h2>Next fixtures</h2>
    {#if team.upcoming.length === 0}
      <p class="empty">
        No {team.name} fixture in the feed yet. The next round appears a few days before it is
        played.
      </p>
    {:else}
      <p class="sub">
        Calls are published on matchday at 06:00 UTC ·
        {zone ? `kick-offs in your local time (${zone})` : 'kick-offs in UK time'}
      </p>
      <ul class="list">
        {#each team.upcoming as f (f.fixture_id)}
          {@const k = kick(f)}
          <li>
            <a href={matchPath(f)}>
              <span class="time">{shortDay(f.match_date)}
                {#if k}· {k.time}{#if k.dayShift}<sup>{k.dayShift > 0 ? '+1' : '−1'}</sup>{/if}{/if}</span>
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
    {/if}
  </section>

  <section class="block">
    <h2>Our calls this season</h2>
    {#if team.calls.length === 0}
      <p class="empty">Nothing graded yet. Every call is listed here once its match is settled.</p>
    {:else}
      <ul class="list calls">
        {#each team.calls as c (c.fixture_id)}
          {@const view = seen(c)}
          <li>
            <a href={matchPath(c)}>
              <span class="time date">{shortDay(c.match_date)}</span>
              <span class="game">
                <span class="res {c.result ?? ''}">{c.result ?? '–'}</span>
                <b>{view.score}</b>
                <span class="opp">{view.where} {view.opponent}</span>
              </span>
              <span class="call" class:won={c.outcome === 'win'} class:lost={c.outcome === 'lose'}
                title="Our call {outcomeWords(c.outcome)}"
                >{callLabel(c.side, c.home_name, c.away_name)}
                {c.outcome === 'win' ? '✓' : c.outcome === 'lose' ? '✗' : ''}</span>
            </a>
          </li>
        {/each}
      </ul>
    {/if}
  </section>

  <p class="fine">
    The percentage beside a call is the probability the model gave it when it was published:
    uncalibrated, and not a price. Every {divisionName(team.division)} call is on
    <a href={leaguePath(team.division)}>the {divisionName(team.division)} page</a>, and today's
    across all four leagues are on <a href="/">the front page</a>.
  </p>
</article>

<style>
  .page { max-width: 880px; margin: 0 auto; padding: 56px 32px 0; }
  .kicker {
    font-family: var(--mono); font-size: 11px; letter-spacing: 0.22em;
    text-transform: uppercase; color: var(--accent);
  }
  .kicker a { color: inherit; text-decoration: underline; text-underline-offset: 3px; }
  .kicker a:hover { color: var(--accent-soft); }
  h1 {
    font-family: var(--display); font-weight: 800; font-size: clamp(34px, 5vw, 52px);
    line-height: 1; text-transform: uppercase; color: #fff; margin: 10px 0 0;
  }
  .meta { margin: 14px 0 0; font-family: var(--mono); font-size: 12px; color: var(--muted); }
  .record {
    margin: 22px 0 0; padding: 14px 18px; background: var(--panel); border: 1px solid var(--line);
    border-left: 3px solid var(--accent); border-radius: 5px; font-size: 15px; color: var(--body);
  }
  .record strong { font-weight: 600; color: var(--text); }
  .record .note { display: block; margin-top: 4px; font-family: var(--mono); font-size: 11px; color: var(--dim); }
  .record .note a { color: var(--muted); }

  .block { margin-top: 40px; }
  h2 {
    font-family: var(--display); font-weight: 800; font-size: 26px;
    text-transform: uppercase; color: #fff; margin: 0;
  }
  .sub { margin: 4px 0 0; font-family: var(--mono); font-size: 11px; color: var(--muted); }
  .list { list-style: none; margin: 14px 0 0; padding: 0; }
  .list li { border-bottom: 1px solid var(--line-2); }
  .list a {
    display: grid; grid-template-columns: 132px minmax(0, 1fr) auto; gap: 4px 14px;
    align-items: baseline; padding: 11px 16px; color: var(--body); text-decoration: none;
  }
  .list a:hover { background: var(--panel); color: var(--text); }
  .list a:focus-visible { outline: 2px solid var(--accent); outline-offset: -2px; }
  .time { font-family: var(--mono); font-size: 12px; color: #fff; }
  .time.date { color: var(--muted); }
  .time sup { font-size: 10px; color: var(--muted); }
  .game { font-size: 15px; min-width: 0; }
  .game b { font-family: var(--mono); color: #fff; }
  .opp { color: var(--muted); }
  .vs { color: var(--muted); font-size: 13px; }
  .res {
    display: inline-block; width: 18px; text-align: center; margin-right: 6px;
    font-family: var(--display); font-weight: 800; font-size: 12px; color: var(--muted);
  }
  .res.W { color: var(--good); }
  .res.L { color: var(--bad); }
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
    .list a { grid-template-columns: 104px minmax(0, 1fr); padding: 11px 10px; }
    .call { grid-column: 2; text-align: left; }
  }
</style>
