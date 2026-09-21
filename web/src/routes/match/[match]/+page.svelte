<script>
  // A match page (docs/SEO_PLAN.md 2.3): one fixture, its call and the facts
  // around it, server-rendered so search engines and link previews see the
  // content. It shows only what the front page's cards show -- the call,
  // what it needs, the claim, the outcome -- plus facts that carry no
  // probability: the venue, recent form with our calls on it, and past
  // meetings (D7). No prices, no return (§6).
  import { onMount, getContext } from 'svelte';
  import { callLabel, callCode, callMeans, pct } from '$lib/api.js';
  import { fixtureBadges } from '$lib/badge.js';
  import { localKickoff, viewerZone } from '$lib/kickoff.js';
  import { wagerLink, wagerLabel } from '$lib/betpawa.js';
  import { ORIGIN } from '$lib/site.js';
  import PageHead from '$lib/PageHead.svelte';
  import { leaguePath } from '$lib/leagues.js';
  import {
    matchPath,
    matchState,
    pageTitle,
    pageDescription,
    longDate,
    shortDay,
    divisionName,
    outcomeWords,
    formGame,
    formTally,
    sportsEventScript
  } from '$lib/match.js';

  let { data } = $props();
  // Derived, not copied: a move from one match page to another reuses this
  // component with new data.
  const fx = $derived(data.fixture);
  const state = $derived(matchState(fx));
  const badge = $derived(fixtureBadges(fx.home_team, fx.away_team));

  // The betPawa button (B26), as on the front page: the layout owns the
  // session and the links.
  const { store: betpawa, promptSignIn } = getContext('betpawa');

  // UK time in the server's HTML, the viewer's own once mounted (2.1).
  let zone = $state(null);
  onMount(() => (zone = viewerZone()));
  const kick = $derived(localKickoff(fx.match_date, fx.kickoff_time, zone ?? 'Europe/London'));

  const sides = $derived([
    { name: fx.home_name, games: fx.form.home },
    { name: fx.away_name, games: fx.form.away }
  ]);
</script>

<PageHead title={pageTitle(fx)} path={matchPath(fx)} description={pageDescription(fx)} />
<svelte:head>
  {@html sportsEventScript(fx, ORIGIN)}
</svelte:head>

<article class="page">
  <div class="kicker">Match prediction · <a href={leaguePath(fx.division)}>{divisionName(fx.division)}</a></div>
  <h1>
    <span class="team"><span class="crest" style="background:{badge.home.colour}">{badge.home.code}</span>{fx.home_name}</span>
    <span class="vs">vs</span>
    <span class="team"><span class="crest" style="background:{badge.away.colour}">{badge.away.code}</span>{fx.away_name}</span>
  </h1>
  <p class="meta">
    {shortDay(fx.match_date)}
    {#if kick}
      · {kick.time}{#if kick.dayShift}<sup>{kick.dayShift > 0 ? '+1' : '−1'}</sup>{/if}
      {zone ? `your time (${zone})` : 'UK time'}
    {/if}
    {#if fx.venue}· {fx.venue}{/if}
  </p>

  <section class="callbox" class:settled={state === 'settled'}>
    <div class="label">Our call</div>
    {#if state === 'upcoming'}
      <p class="pending">
        Published on matchday at 06:00 UTC, before kick-off. Every call is graded
        after the match.
      </p>
    {:else}
      {@const t = fx.tip}
      {@const means = callMeans(t.side, fx.home_name, fx.away_name)}
      <div class="callrow">
        <div>
          <div class="phrase">
            {callLabel(t.side, fx.home_name, fx.away_name)}
            {#if callCode(t.side) && means}<span class="code" title={means}>{callCode(t.side)}</span>{/if}
          </div>
          {#if means}<p class="means">For this to come in, {means}.</p>{/if}
        </div>
        <div class="conf">
          <div class="confhead"><span>CONF</span><span class="v">{pct(t.model_prob, 0)}</span></div>
          <div class="track"><div class="fill" style="width:{100 * t.model_prob}%"></div></div>
        </div>
      </div>
      {#if state === 'settled'}
        <p class="result">
          {#if t.fthg != null}<span class="score">{fx.home_name} {t.fthg}–{t.ftag} {fx.away_name}</span>{/if}
          <span class="outcome {t.outcome}">Our call {outcomeWords(t.outcome)}</span>
        </p>
      {:else if $betpawa.status === 'anonymous'}
        <button type="button" class="bet ghost" onclick={promptSignIn}>Sign in to bet on betPawa</button>
      {:else if $betpawa.status === 'ready'}
        {@const bet = wagerLink($betpawa.byFixture, fx.fixture_id, t.side)}
        {#if bet}
          <a class="bet" class:event={bet.kind === 'event'} href={bet.url} target="_blank"
            rel="noopener noreferrer">{wagerLabel(bet.kind)} ↗</a>
        {/if}
      {/if}
    {/if}
  </section>

  <section class="block">
    <h2>Recent form</h2>
    <p class="sub">League games this season before this one, with our call on each.</p>
    <div class="cols">
      {#each sides as side}
        <div class="col">
          <h3>{side.name}</h3>
          {#if side.games.length === 0}
            <p class="empty">No league games yet this season.</p>
          {:else}
            {@const tally = formTally(side.games)}
            <ol class="games">
              {#each side.games as g (g.fixture_id)}
                {@const view = formGame(g)}
                <li>
                  <span class="res {g.result ?? ''}">{g.result ?? '–'}</span>
                  <span class="score">{view.score}</span>
                  <span class="opp">{view.where} {view.opponent}</span>
                  <span class="ours" class:won={g.outcome === 'win'} class:lost={g.outcome === 'lose'}
                    >{callLabel(g.side, g.home_name, g.away_name)}
                    {g.outcome === 'win' ? '✓' : g.outcome === 'lose' ? '✗' : ''}</span>
                </li>
              {/each}
            </ol>
            <p class="tally">Our calls: {tally.won} of {tally.graded} came in</p>
          {/if}
        </div>
      {/each}
    </div>
  </section>

  <section class="block">
    <h2>Last meetings</h2>
    {#if fx.meetings.length === 0}
      <p class="empty">No earlier meeting in our records.</p>
    {:else}
      <ol class="meetings">
        {#each fx.meetings as m}
          <li>
            <span class="date">{longDate(m.match_date)}</span>
            <span class="line">{m.home_name} <b>{m.fthg}–{m.ftag}</b> {m.away_name}</span>
          </li>
        {/each}
      </ol>
    {/if}
  </section>

  <p class="fine">
    CONF is the probability the model gave the call when it was published. It
    is uncalibrated and it is not a price. Strike rate, the share of graded
    calls that came in, is the whole claim: <a href="/">today's calls and the
    record</a>.
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
    font-family: var(--display); font-weight: 800; font-size: clamp(30px, 5vw, 48px);
    line-height: 1.05; text-transform: uppercase; color: #fff; margin: 12px 0 0;
    display: flex; flex-wrap: wrap; align-items: center; gap: 6px 14px;
  }
  .team { display: inline-flex; align-items: center; gap: 12px; }
  .vs { font-size: 0.55em; color: var(--muted); }
  .crest {
    flex: none; width: 34px; height: 34px; border-radius: 50%;
    display: inline-flex; align-items: center; justify-content: center;
    font-family: var(--display); font-weight: 800; font-size: 13px; color: #fff;
  }
  .meta { margin: 14px 0 0; font-family: var(--mono); font-size: 12px; color: var(--muted); }
  .meta sup { font-size: 10px; margin-left: 2px; }

  .callbox {
    margin-top: 28px; background: var(--panel); border: 1px solid var(--line);
    border-left: 3px solid var(--accent); border-radius: 5px; padding: 20px 22px;
  }
  .label {
    font-family: var(--mono); font-size: 10px; letter-spacing: 0.2em;
    text-transform: uppercase; color: var(--dim);
  }
  .pending { margin: 8px 0 0; font-size: 15px; color: var(--body); line-height: 1.6; }
  .callrow { display: flex; align-items: flex-end; justify-content: space-between; gap: 20px; margin-top: 6px; }
  .phrase {
    font-family: var(--display); font-weight: 800; font-size: 26px;
    text-transform: uppercase; color: var(--accent); line-height: 1.1;
  }
  .code {
    font-family: var(--mono); font-size: 11px; font-weight: 600; color: var(--body);
    background: var(--panel-2); border: 1px solid var(--line);
    border-radius: 3px; padding: 1px 5px; vertical-align: 4px; cursor: help;
  }
  .means { margin: 6px 0 0; font-size: 14px; color: var(--body); }
  .conf { width: 110px; flex: none; }
  .confhead {
    display: flex; justify-content: space-between; font-family: var(--mono);
    font-size: 11px; color: var(--muted); margin-bottom: 5px;
  }
  .confhead .v { color: #fff; }
  .track { height: 5px; border-radius: 3px; background: #2c2c34; overflow: hidden; }
  .fill { height: 100%; border-radius: 3px; background: var(--accent); }
  .result { margin: 14px 0 0; display: flex; flex-wrap: wrap; gap: 8px 16px; align-items: baseline; }
  .result .score { font-family: var(--display); font-weight: 700; font-size: 20px; color: #fff; }
  .outcome { font-family: var(--mono); font-size: 12px; letter-spacing: 0.06em; text-transform: uppercase; }
  .outcome.win { color: var(--good); }
  .outcome.lose { color: var(--bad); }
  .outcome.void { color: var(--muted); }

  .bet {
    display: inline-block; margin-top: 14px; font-family: var(--mono); font-size: 10.5px;
    letter-spacing: 0.08em; text-transform: uppercase; text-decoration: none;
    line-height: 1.2; padding: 6px 12px; border-radius: 3px; white-space: nowrap;
    border: 1px solid var(--accent); color: var(--accent); background: transparent; cursor: pointer;
  }
  .bet:hover { background: var(--accent); color: var(--bg); }
  .bet.event { border-color: var(--line); color: var(--muted); }
  .bet.ghost { border-style: dashed; border-color: var(--line); color: var(--muted); }
  .bet.ghost:hover { background: transparent; border-color: var(--accent); color: var(--accent); }
  .bet:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }

  .block { margin-top: 40px; }
  h2 {
    font-family: var(--display); font-weight: 800; font-size: 26px;
    text-transform: uppercase; color: #fff; margin: 0;
  }
  .sub { margin: 4px 0 0; font-size: 13px; color: var(--muted); }
  .cols { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; margin-top: 16px; }
  h3 {
    font-family: var(--display); font-weight: 700; font-size: 17px; letter-spacing: 0.06em;
    text-transform: uppercase; color: #d6d6de; margin: 0 0 8px;
  }
  .games, .meetings { list-style: none; margin: 0; padding: 0; }
  .games li {
    display: grid; grid-template-columns: 26px 44px minmax(0, 1fr); gap: 2px 10px;
    align-items: baseline; padding: 8px 0; border-bottom: 1px solid var(--line-2); font-size: 14px;
  }
  .res {
    font-family: var(--mono); font-size: 11px; font-weight: 600; text-align: center;
    border-radius: 3px; padding: 2px 0; background: var(--panel-2); color: var(--muted);
  }
  .res.W { background: var(--good); color: #0b0b0e; }
  .res.L { background: var(--bad); color: #fff; }
  .score { font-family: var(--mono); color: #fff; }
  .opp { color: var(--body); min-width: 0; }
  .ours { grid-column: 3; font-family: var(--mono); font-size: 11px; color: var(--muted); }
  .ours.won { color: var(--good); }
  .ours.lost { color: var(--bad); }
  .tally { margin: 10px 0 0; font-family: var(--mono); font-size: 12px; color: var(--body); }
  .meetings li {
    display: flex; gap: 16px; padding: 8px 0; border-bottom: 1px solid var(--line-2); font-size: 14px;
  }
  .meetings .date { font-family: var(--mono); font-size: 12px; color: var(--muted); width: 96px; flex: none; }
  .meetings .line { color: var(--body); }
  .meetings b { color: #fff; font-family: var(--mono); font-weight: 600; margin: 0 4px; }
  .empty { margin: 8px 0 0; font-size: 14px; color: var(--muted); }
  .fine { margin: 40px 0 0; font-size: 12.5px; line-height: 1.6; color: var(--muted); max-width: 72ch; }

  @media (max-width: 820px) {
    .page { padding: 32px 18px 0; }
    .cols { grid-template-columns: 1fr; }
    .callrow { flex-direction: column; align-items: flex-start; }
    .phrase { font-size: 22px; }
  }
</style>
