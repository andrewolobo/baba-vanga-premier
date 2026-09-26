<script>
  // The facts around a fixture that carry no probability (docs/SEO_PLAN.md
  // D7): each side's recent form with our call on each game, and the last
  // meetings. `fx` is `GET /fixture/{id}` unchanged.
  //
  // Two call sites: the match page, in the server's HTML, and the form &
  // meetings sheet on the front page and /parlay (B27), fetched on a click.
  // Meetings carry no club colours: the schema has none, and $lib/badge.js
  // must not be read as them.
  import { fixtureBadges } from '$lib/badge.js';
  import Crest from '$lib/Crest.svelte';
  import FormCard from '$lib/FormCard.svelte';
  import { longDate, meetingTally } from '$lib/match.js';

  let { fx } = $props();

  const badge = $derived(fixtureBadges(fx.home_team, fx.away_team));
  const sides = $derived([
    { name: fx.home_name, games: fx.form.home },
    { name: fx.away_name, games: fx.form.away }
  ]);
  const h2h = $derived(meetingTally(fx.meetings, fx.home_name));
</script>

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

<style>
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

  @media (max-width: 560px) {
    .meetings li { grid-template-columns: minmax(0, 1fr); }
    .meetings .line { font-size: 14px; }
  }
</style>
