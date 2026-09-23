<script>
  // A match page (docs/SEO_PLAN.md 2.3): one fixture, its call and the facts
  // around it, server-rendered so search engines and link previews see the
  // content. It shows only what the front page's cards show -- the call,
  // what it needs, the claim, the outcome -- plus facts that carry no
  // probability: the venue, recent form with our calls on it, and past
  // meetings (D7). No prices, no return (§6).
  //
  // Laid out from `docs/ui/team-page/Match Prediction.dc.html`, with two
  // departures: the meetings carry no club colours (the schema has none, and
  // $lib/badge.js must not be read as them), and the confidence bar has no
  // 50% mark (the number is uncalibrated, so a coin-flip line misleads).
  import { onMount, getContext } from 'svelte';
  import { callLabel, callCode, callMeans } from '$lib/api.js';
  import { fixtureBadges } from '$lib/badge.js';
  import Crest from '$lib/Crest.svelte';
  import FormCard from '$lib/FormCard.svelte';
  import { localKickoff, viewerZone } from '$lib/kickoff.js';
  import { wagerLink, wagerLabel } from '$lib/betpawa.js';
  import { ORIGIN } from '$lib/site.js';
  import PageHead from '$lib/PageHead.svelte';
  import { leaguePath } from '$lib/leagues.js';
  import { teamPath } from '$lib/teams.js';
  import {
    matchPath,
    matchState,
    pageTitle,
    pageDescription,
    longDate,
    shortDay,
    divisionName,
    outcomeWords,
    marginScale,
    meetingTally,
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
  const h2h = $derived(meetingTally(fx.meetings, fx.home_name));

  const mark = (outcome) => (outcome === 'win' ? '✓' : outcome === 'lose' ? '✕' : '–');
</script>

<PageHead title={pageTitle(fx)} path={matchPath(fx)} description={pageDescription(fx)} />
<svelte:head>
  {@html sportsEventScript(fx, ORIGIN)}
</svelte:head>

<article class="page">
  <div class="kicker">Match prediction · <a href={leaguePath(fx.division)}>{divisionName(fx.division)}</a></div>
  <h1>
    <a class="team" href={teamPath(fx.home_team_id, fx.home_slug)}><Crest name={fx.home_team} badge={badge.home} size={40} />{fx.home_name}</a>
    <span class="vs">vs</span>
    <a class="team" href={teamPath(fx.away_team_id, fx.away_slug)}><Crest name={fx.away_team} badge={badge.away} size={40} />{fx.away_name}</a>
  </h1>
  <p class="meta">
    {shortDay(fx.match_date)}
    {#if kick}
      · {kick.time}{#if kick.dayShift}<sup>{kick.dayShift > 0 ? '+1' : '−1'}</sup>{/if}
      {zone ? `your time (${zone})` : 'UK time'}
    {/if}
    {#if fx.venue}· {fx.venue}{/if}
  </p>

  <section class="callbox">
    {#if state === 'upcoming'}
      <div class="body">
        <div class="label">Our call</div>
        <p class="pending">
          Published on matchday at 06:00 UTC, before kick-off. Every call is graded
          after the match.
        </p>
      </div>
    {:else}
      {@const t = fx.tip}
      {@const means = callMeans(t.side, fx.home_name, fx.away_name)}
      {@const scale = marginScale(t.side, t.fthg, t.ftag)}
      {#if state === 'settled'}
        <div class="banner {t.outcome ?? ''}">
          <span class="verdict"><span class="tick" aria-hidden="true">{mark(t.outcome)}</span>Our call {outcomeWords(t.outcome)}</span>
          {#if t.fthg != null}
            <span class="ft"><span class="ftlabel">FT</span>{fx.home_name} <b>{t.fthg}–{t.ftag}</b> {fx.away_name}</span>
          {/if}
        </div>
      {/if}
      <div class="body">
        <div class="callgrid">
          <div class="call">
            <div class="labelrow">
              <span class="label">Our call</span>
              {#if callCode(t.side) && means}<span class="code" title={means}>{callCode(t.side)}</span>{/if}
            </div>
            <div class="phrase">{callLabel(t.side, fx.home_name, fx.away_name)}</div>
            {#if means}<p class="means">For this to come in, {means}.</p>{/if}
          </div>
          <div class="conf">
            <div class="confhead">
              <span class="label">Model confidence</span>
              <span class="v">{(100 * t.model_prob).toFixed(0)}<small>%</small></span>
            </div>
            <div class="track"><div class="fill" style="width:{100 * t.model_prob}%"></div></div>
          </div>
        </div>

        <!-- The scale restates the call in goals; the words above and the
             banner's score already say all of it, so it is hidden from
             screen readers rather than read out twice. -->
        {#if scale}
          <div class="scale" aria-hidden="true">
            <div class="scalehead">
              <span>{scale.team === 'home' ? fx.home_name : fx.away_name} goal margin</span>
              <span class="key"><i class="in"></i>Call comes in <i class="out"></i>Does not</span>
            </div>
            <div class="cells">
              {#each scale.cells as c (c.label)}
                <div class="cellcol">
                  <div class="zone {c.comesIn ? 'in' : 'out'} {c.ended ? `ended ${t.outcome ?? ''}` : ''}">
                    {c.ended ? 'FT' : ''}
                  </div>
                  <span class="mlabel">{c.label}</span>
                </div>
              {/each}
            </div>
          </div>
        {/if}

        {#if state === 'live'}
          {#if $betpawa.status === 'anonymous'}
            <button type="button" class="bet ghost" onclick={promptSignIn}>Sign in to bet on betPawa</button>
          {:else if $betpawa.status === 'ready'}
            {@const bet = wagerLink($betpawa.byFixture, fx.fixture_id, t.side)}
            {#if bet}
              <a class="bet" class:event={bet.kind === 'event'} href={bet.url} target="_blank"
                rel="noopener noreferrer">{wagerLabel(bet.kind)} ↗</a>
            {/if}
          {/if}
        {/if}
      </div>
    {/if}
  </section>

  <section class="block">
    <h2>Recent form</h2>
    <p class="sub">Each side's last five league games this season, oldest to latest, with our call on each.</p>
    <div class="cols">
      {#each sides as side}
        <FormCard title={side.name} games={side.games} />
      {/each}
    </div>
  </section>

  <section class="block">
    <h2>Last meetings</h2>
    {#if fx.meetings.length === 0}
      <p class="empty">No earlier meeting in our records.</p>
    {:else}
      <div class="h2h">
        <div class="bar" aria-hidden="true">
          {#if h2h.home}<span class="home" style="flex:{h2h.home}">{h2h.home}</span>{/if}
          {#if h2h.draw}<span class="draw" style="flex:{h2h.draw}">{h2h.draw}</span>{/if}
          {#if h2h.away}<span class="away" style="flex:{h2h.away}">{h2h.away}</span>{/if}
        </div>
        <div class="barkey">
          <span><Crest name={fx.home_team} badge={badge.home} size={18} />{fx.home_name} wins {h2h.home}</span>
          <span>Draws {h2h.draw}</span>
          <span>{fx.away_name} wins {h2h.away}<Crest name={fx.away_team} badge={badge.away} size={18} /></span>
        </div>
      </div>
      <ol class="meetings">
        {#each fx.meetings as m}
          <li>
            <span class="date">{longDate(m.match_date)}</span>
            <span class="line">
              <span class="mh" class:won={m.fthg > m.ftag} class:beaten={m.fthg < m.ftag}>{m.home_name}</span>
              <b>{m.fthg}–{m.ftag}</b>
              <span class="ma" class:won={m.ftag > m.fthg} class:beaten={m.ftag < m.fthg}>{m.away_name}</span>
            </span>
          </li>
        {/each}
      </ol>
    {/if}
  </section>

  <p class="fine">
    Confidence is the probability the model gave the call when it was
    published. It is uncalibrated and it is not a price. Strike rate, the
    share of graded calls that came in, is the whole claim: <a href="/">today's
    calls and the record</a>.
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
  /* Each name is the link to that club's page (2.5, 2.8); it carries the
     heading's own colour, and says so on hover rather than by default. */
  .team { display: inline-flex; align-items: center; gap: 12px; color: inherit; text-decoration: none; }
  .team:hover { color: var(--accent); }
  .team:focus-visible { outline: 2px solid var(--accent); outline-offset: 3px; }
  .vs { font-size: 0.55em; color: var(--muted); }
  .meta { margin: 14px 0 0; font-family: var(--mono); font-size: 12px; color: var(--muted); }
  .meta sup { font-size: 10px; margin-left: 2px; }

  .callbox {
    margin-top: 32px; background: var(--panel); border: 1px solid var(--line);
    border-radius: 8px; overflow: hidden;
  }
  .body { padding: 22px; }
  .label {
    font-family: var(--mono); font-size: 10.5px; letter-spacing: 0.16em;
    text-transform: uppercase; color: var(--muted);
  }
  .pending { margin: 8px 0 0; font-size: 15px; color: var(--body); line-height: 1.6; }

  /* The verdict, above everything once the match is graded. Colour follows
     the outcome and nothing else; the words and the mark say it too. */
  .banner {
    display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap;
    gap: 8px 16px; padding: 13px 22px; border-bottom: 1px solid var(--line);
    background: var(--panel-2); color: var(--muted);
  }
  .banner.win {
    color: var(--good); background: color-mix(in srgb, var(--good) 10%, transparent);
    border-bottom-color: color-mix(in srgb, var(--good) 25%, transparent);
  }
  .banner.lose {
    color: var(--bad); background: color-mix(in srgb, var(--bad) 10%, transparent);
    border-bottom-color: color-mix(in srgb, var(--bad) 25%, transparent);
  }
  .verdict {
    display: inline-flex; align-items: center; gap: 10px;
    font-family: var(--mono); font-size: 12.5px; font-weight: 600;
    letter-spacing: 0.12em; text-transform: uppercase;
  }
  .tick {
    width: 22px; height: 22px; border-radius: 50%; display: grid; place-items: center;
    background: var(--muted); color: var(--bg); font-size: 13px; font-weight: 700; letter-spacing: 0;
  }
  .banner.win .tick { background: var(--good); }
  .banner.lose .tick { background: var(--bad); }
  .ft {
    display: inline-flex; align-items: baseline; gap: 8px;
    font-family: var(--display); font-weight: 700; font-size: 20px; color: #fff;
  }
  .ft b { font-size: 26px; }
  .ftlabel {
    font-family: var(--mono); font-weight: 400; font-size: 11px;
    letter-spacing: 0.12em; color: var(--muted);
  }

  .callgrid { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 24px 28px; }
  .call { display: flex; flex-direction: column; gap: 10px; min-width: 0; }
  .labelrow { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
  .phrase {
    font-family: var(--display); font-weight: 800; font-size: 34px;
    text-transform: uppercase; color: var(--accent); line-height: 1;
  }
  .code {
    font-family: var(--mono); font-size: 10px; font-weight: 600; letter-spacing: 0.06em;
    text-transform: uppercase; color: var(--body); background: var(--panel-2);
    border: 1px solid var(--line); border-radius: 3px; padding: 2px 6px; cursor: help;
  }
  .means { margin: 0; font-size: 15px; color: var(--body); }
  .conf { display: flex; flex-direction: column; justify-content: flex-end; gap: 10px; }
  .confhead { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; }
  .confhead .v {
    font-family: var(--display); font-weight: 800; font-size: 40px; line-height: 1; color: #fff;
  }
  .confhead small { font-size: 22px; color: var(--muted); }
  .track { height: 10px; border-radius: 5px; background: var(--line); overflow: hidden; }
  .fill { height: 100%; border-radius: 5px; background: var(--accent); }

  .scale { margin-top: 24px; display: flex; flex-direction: column; gap: 10px; }
  .scalehead {
    display: flex; justify-content: space-between; gap: 6px 12px; flex-wrap: wrap;
    font-family: var(--mono); font-size: 10.5px; letter-spacing: 0.1em;
    text-transform: uppercase; color: var(--muted);
  }
  .key { display: inline-flex; align-items: center; gap: 6px; }
  .key i { display: inline-block; width: 9px; height: 9px; border-radius: 2px; }
  .key i.out { margin-left: 8px; }
  .key i.in, .zone.in { background: color-mix(in srgb, var(--good) 16%, transparent); border: 1px solid color-mix(in srgb, var(--good) 40%, transparent); }
  .key i.out, .zone.out { background: color-mix(in srgb, var(--bad) 14%, transparent); border: 1px solid color-mix(in srgb, var(--bad) 32%, transparent); }
  .cells { display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); gap: 4px; }
  .cellcol { display: flex; flex-direction: column; align-items: center; gap: 6px; min-width: 0; }
  .zone {
    width: 100%; height: 34px; box-sizing: border-box; border-radius: 4px;
    display: grid; place-items: center;
    font-family: var(--mono); font-size: 11px; font-weight: 600; color: var(--bg);
  }
  /* The full-time mark takes the graded outcome's colour, not the zone's. */
  .zone.ended { border-color: transparent; background: var(--muted); }
  .zone.ended.win { background: var(--good); }
  .zone.ended.lose { background: var(--bad); color: #fff; }
  .mlabel { font-family: var(--mono); font-size: 12px; color: var(--body); white-space: nowrap; }

  .bet {
    display: inline-block; margin-top: 20px; font-family: var(--mono); font-size: 10.5px;
    letter-spacing: 0.08em; text-transform: uppercase; text-decoration: none;
    line-height: 1.2; padding: 6px 12px; border-radius: 3px; white-space: nowrap;
    border: 1px solid var(--accent); color: var(--accent); background: transparent; cursor: pointer;
  }
  .bet:hover { background: var(--accent); color: var(--bg); }
  .bet.event { border-color: var(--line); color: var(--muted); }
  .bet.ghost { border-style: dashed; border-color: var(--line); color: var(--muted); }
  .bet.ghost:hover { background: transparent; border-color: var(--accent); color: var(--accent); }
  .bet:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }

  .block { margin-top: 44px; }
  h2 {
    font-family: var(--display); font-weight: 800; font-size: 28px;
    text-transform: uppercase; color: #fff; margin: 0;
  }
  .sub { margin: 4px 0 0; font-size: 14px; color: var(--muted); }
  .cols { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 16px; margin-top: 18px; }

  /* Head to head: two neutral tones and a darker one for draws. Club colours
     would need data the schema does not have. */
  .h2h { margin-top: 18px; display: flex; flex-direction: column; gap: 8px; }
  .bar {
    display: flex; height: 28px; gap: 3px; border-radius: 4px; overflow: hidden;
    font-family: var(--mono); font-size: 12px; font-weight: 600;
  }
  .bar span { display: grid; place-items: center; min-width: 22px; }
  .bar .home { background: var(--body); color: var(--bg); }
  .bar .draw { background: var(--panel-2); color: var(--muted); }
  .bar .away { background: #4a4a54; color: #fff; }
  /* Three columns, so on a phone each label wraps under its own end of the
     bar instead of the last one dropping to a line of its own. */
  .barkey {
    display: grid; grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr); gap: 14px;
    font-family: var(--mono); font-size: 11px; letter-spacing: 0.06em;
    text-transform: uppercase; color: var(--muted);
  }
  .barkey span { display: inline-flex; align-items: center; gap: 7px; }
  .barkey span:last-child { justify-content: flex-end; text-align: right; }
  .meetings { list-style: none; margin: 10px 0 0; padding: 0; }
  .meetings li {
    display: grid; grid-template-columns: 104px minmax(0, 1fr); gap: 4px 12px; align-items: center;
    padding: 11px 0; border-bottom: 1px solid var(--line-2);
  }
  .meetings .date { font-family: var(--mono); font-size: 12px; color: var(--muted); }
  .meetings .line {
    display: grid; grid-template-columns: minmax(0, 1fr) 52px minmax(0, 1fr); gap: 10px;
    align-items: center; font-size: 15px; color: var(--body);
  }
  .meetings .mh { text-align: right; }
  .meetings .won { color: #fff; font-weight: 600; }
  .meetings .beaten { color: var(--muted); }
  .meetings b {
    font-family: var(--mono); font-weight: 600; color: #fff; text-align: center;
    background: var(--panel-2); border-radius: 3px; padding: 2px 0;
  }
  .empty { margin: 8px 0 0; font-size: 14px; color: var(--muted); }
  .fine { margin: 44px 0 0; font-size: 12.5px; line-height: 1.6; color: var(--muted); max-width: 72ch; }

  @media (max-width: 820px) {
    .page { padding: 32px 18px 0; }
    .body { padding: 18px; }
    .banner { padding: 12px 18px; }
    .phrase { font-size: 28px; }
  }
  @media (max-width: 560px) {
    .meetings li { grid-template-columns: minmax(0, 1fr); }
    .meetings .line { font-size: 14px; }
  }
</style>
