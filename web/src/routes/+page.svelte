<script>
  import { onMount, getContext } from 'svelte';
  import {
    getTips,
    callLabel,
    callCode,
    callMeans,
    DIVISIONS,
    pct
  } from '$lib/api.js';
  import { fixtureBadges } from '$lib/badge.js';
  import { localKickoff, viewerZone } from '$lib/kickoff.js';
  import { nextLikeliest } from '$lib/view.js';
  import { slide } from 'svelte/transition';
  import HeroClassic from './HeroClassic.svelte';
  import HeroVideo from './HeroVideo.svelte';
  import { VIDEO_HERO } from '$lib/hero.js';
  import { wagerLink, wagerLabel, daySlip } from '$lib/betpawa.js';
  import { HOME_TITLE } from '$lib/site.js';
  import { matchPath } from '$lib/match.js';
  import PageHead from '$lib/PageHead.svelte';

  // The opening lists and record, read by `+page.js` -- on the server for a
  // first visit, so they are in the HTML.
  let { data } = $props();

  // The betPawa button (B26): state and links come from the layout, which
  // owns the session. A click on the button must not toggle the row's
  // drawer, and Enter on it must not be swallowed by the row's key handler.
  const { store: betpawa, promptSignIn } = getContext('betpawa');
  const keep = (event) => event.stopPropagation();

  let tipsDivision = $state('');
  // The drawer behind a call (B22): which fixture is open.
  let open = $state(null);
  const toggle = (id) => (open = open === id ? null : id);
  const onRowKey = (event, id) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      toggle(id);
    }
  };
  let tips = $state(data.tips);
  // The settled list and the record are summaries here, linking through to
  // /results and /record (docs/SEO_PLAN.md 2.6): neither refetches, so both
  // are plain values rather than state.
  const recent = $derived(data.results.slice(0, 6));
  const record = data.record;
  let error = $state(data.error);
  let loading = $state(false);

  async function loadTips() {
    loading = true;
    error = null;
    try {
      tips = await getTips(tipsDivision || null);
    } catch (e) {
      error = e.message;
    } finally {
      loading = false;
    }
  }

  onMount(() => (zone = viewerZone()));
  // The opening lists came with the page; only a change of tab or toggle
  // reads again. Each effect's first run is hydration, and is skipped by
  // comparing with what is already shown.
  let shownTips = tipsDivision;
  $effect(() => {
    if (tipsDivision === shownTips) return;
    shownTips = tipsDivision;
    loadTips();
  });

  const byDay = $derived(
    Object.entries(
      tips.reduce((acc, t) => ((acc[t.match_date] ??= []).push(t), acc), {})
    ).sort(([a], [b]) => a.localeCompare(b))
  );

  const divisionName = (code) =>
    DIVISIONS.find(([c]) => c === code)?.[1] ?? code;

  // Kick-offs arrive as UK wall-clock and are shown in the viewer's zone
  // (`$lib/kickoff.js`). The list stays grouped by the UK match date, so a row
  // whose local date differs says so with a +1 / −1. The server cannot know
  // the viewer's zone, so its HTML says UK time and the browser switches to
  // local on mount (owner decision 2026-09-18, docs/SEO_PLAN.md 2.1).
  let zone = $state(null);
  const kick = (t) => localKickoff(t.match_date, t.kickoff_time, zone ?? 'Europe/London');

  // Built from the parts rather than parsed, so a date never shifts a day
  // across a timezone boundary — `new Date('2026-08-15')` is UTC midnight.
  const day = (iso) => {
    const [y, m, d] = iso.split('-').map(Number);
    return new Date(y, m - 1, d).toLocaleDateString('en-GB', {
      weekday: 'long',
      day: 'numeric',
      month: 'long'
    });
  };
  const shortDay = (iso) => {
    const [y, m, d] = iso.split('-').map(Number);
    return new Date(y, m - 1, d).toLocaleDateString('en-GB', {
      day: 'numeric',
      month: 'short'
    });
  };
</script>

<!-- docs/SEO_PLAN.md 1.6, 2.1. The canonical ignores the query string, so
     /?owner=1 is /. -->
<PageHead title={HOME_TITLE} path="/" />

<!-- The hero: the pixel-video band, or the parallax art it replaced:
     one flag in $lib/hero.js decides, and flipping it back is the whole
     revert. Both components live beside this file. -->
{#if VIDEO_HERO}
  <HeroVideo />
{:else}
  <HeroClassic />
{/if}

<!-- Every tile falls back to an em dash rather than to zero. A failed fetch or
     an unrun cycle would otherwise render "0 calls graded" beside a blank
     strike rate, which reads as a record rather than as an absence of one. -->
<div class="stats">
  <div class="inner">
    <div class="tile">
      <span class="figure accent"
        >{record?.strike_rate == null ? '—' : pct(record.strike_rate, 1)}</span
      >
      <span class="caption">Strike rate, graded calls</span>
    </div>
    <div class="tile">
      <span class="figure">{record ? record.graded.toLocaleString() : '—'}</span>
      <span class="caption">Calls graded</span>
    </div>
    <div class="tile">
      <span class="figure">{record ? record.upcoming.toLocaleString() : '—'}</span>
      <span class="caption">Calls live now</span>
    </div>
    <div class="tile">
      <span class="figure">{record ? record.matchweeks.toLocaleString() : '—'}</span>
      <span class="caption">Matchweeks graded</span>
    </div>
  </div>
  <p class="disclaimer">
    Strike rate is the share of graded calls that came in. It is not a profit
    figure and it does not imply one.
  </p>
</div>

<section id="tips" class="page">
  <div class="head">
    <div>
      <div class="kicker">The published list</div>
      <h2>Fixtures &amp; calls</h2>
    </div>
    <div class="mono summary">
      {#if tips.length}
        {tips.length} call{tips.length === 1 ? '' : 's'} · {byDay.length} day{byDay.length === 1 ? '' : 's'}
        <span class="zone"
          >· {zone ? `kick-offs in your local time (${zone})` : 'kick-offs in UK time'}</span
        >
      {/if}
    </div>
  </div>

  <div class="tabs">
    {#each DIVISIONS as [code, label]}
      <button class:on={tipsDivision === code} onclick={() => (tipsDivision = code)}>{label}</button>
    {/each}
  </div>

  {#if loading}
    <p class="state">Loading…</p>
  {:else if error}
    <p class="state bad">{error}</p>
  {:else if tips.length === 0}
    <div class="state box">
      <strong>No calls published for these fixtures yet.</strong>
      <p>
        The list is rebuilt by the weekly serving cycle. Out of season, or before
        the fixtures feed carries the coming week, this is the correct and
        expected state — it is not an error.
      </p>
    </div>
  {:else}
    <div class="list">
      {#each byDay as [date, matches]}
        <div class="daylabel">{day(date)}</div>
        {#each matches as t}
          {@const badge = fixtureBadges(t.home_team, t.away_team)}
          {@const k = kick(t)}
          <!-- The row is the control for the drawer beneath it (B22): a
               button role rather than a <button>, because the grid layout
               inside does not survive button's default styling, and the
               keyboard handler restores what the role promises. -->
          <div
            class="row"
            class:open={open === t.tip_id}
            role="button"
            tabindex="0"
            aria-expanded={open === t.tip_id}
            aria-controls="view-{t.tip_id}"
            onclick={() => toggle(t.tip_id)}
            onkeydown={(e) => onRowKey(e, t.tip_id)}
          >
            <div class="fixture">
              <div class="side home">
                <span class="club">{t.home_team}</span>
                <span class="crest" style="background:{badge.home.colour}">{badge.home.code}</span>
              </div>
              <div class="kick" title={k ? `${t.kickoff_time} UK time` : undefined}>
                {#if k}
                  {k.time}{#if k.dayShift}<sup class="shift">{k.dayShift > 0 ? '+1' : '−1'}</sup>{/if}
                {:else}—{/if}
              </div>
              <div class="side away">
                <span class="crest" style="background:{badge.away.colour}">{badge.away.code}</span>
                <span class="club">{t.away_team}</span>
              </div>
            </div>

            <div class="verdict">
              <div class="call">
                <div class="label">Our call</div>
                <div class="phrase">
                  {callLabel(t.side, t.home_team, t.away_team)}
                  <!-- Only on a hedge. On an outright the phrase already names
                       the team, so the code is noise; on `12`/`1X`/`X2` it is
                       the disclosure that two results are covered. -->
                  {#if callCode(t.side) && callMeans(t.side, t.home_team, t.away_team)}
                    <span class="code" title={callMeans(t.side, t.home_team, t.away_team)}
                      >{callCode(t.side)}</span
                    >
                  {/if}
                </div>
                <div class="league">{divisionName(t.division)}</div>
                <!-- The wager button (BETPAWA_PLAN.md D8, D11): sign-in when
                     anonymous; the wager when the book carries this side; the
                     event page when it does not; nothing when the account's
                     country is not served or the scrape never saw the game. -->
                {#if $betpawa.status === 'anonymous'}
                  <button type="button" class="bet ghost" onclick={(e) => { keep(e); promptSignIn(); }} onkeydown={keep}
                    >Sign in to bet on betPawa</button>
                {:else if $betpawa.status === 'ready'}
                  {@const bet = wagerLink($betpawa.byFixture, t.fixture_id, t.side)}
                  {#if bet}
                    <a class="bet" class:event={bet.kind === 'event'} href={bet.url} target="_blank"
                      rel="noopener noreferrer" onclick={keep} onkeydown={keep}>{wagerLabel(bet.kind)} ↗</a>
                  {/if}
                {/if}
              </div>
              <div class="conf">
                <div class="confhead"><span>CONF</span><span class="v">{pct(t.model_prob, 0)}</span></div>
                <div class="track"><div class="fill" style="width:{100 * t.model_prob}%"></div></div>
              </div>
              <span class="caret" aria-hidden="true"></span>
            </div>
          </div>

          <!-- What the model thought when the call was published, from the
               prediction row the call was made from: the next-likeliest
               markets on the rule's own menu (`$lib/view.js`). Not a second
               call, and the copy says so because the strike rate has exactly
               one denominator. -->
          {#if open === t.tip_id}
            <div class="drawer" id="view-{t.tip_id}" transition:slide={{ duration: 180 }}>
              <div class="drawerhead">
                <span class="label">Next-likeliest markets</span>
                <!-- The way into this fixture's page (docs/SEO_PLAN.md 2.8).
                     It sits here rather than on the row, which is already the
                     control that opens this drawer. -->
                <a class="more" href={matchPath(t)}>Form, venue &amp; past meetings →</a>
              </div>

                <ol class="bars">
                  {#each nextLikeliest(t) as m}
                    <li>
                      <span class="name">
                        {m.label}
                        {#if callCode(m.side) && callMeans(m.side, t.home_team, t.away_team)}
                          <span class="code" title={callMeans(m.side, t.home_team, t.away_team)}>{callCode(m.side)}</span>
                        {/if}
                        {#if m.above}<span class="tag">likelier than our call</span>{/if}
                      </span>
                      <span class="track"><span class="fill" style="width:{100 * m.p}%"></span></span>
                      <span class="v">{pct(m.p, 0)}</span>
                    </li>
                  {/each}
                </ol>
                <p class="fine">
                  The two likeliest markets after our call, on probability
                  alone. A hedge is almost always likelier than a named team,
                  which is why the rule does not pick this way: it names a team
                  whenever one clears its floor.
                </p>

              <p class="fine dim">
                Probabilities as stored when the call was published — uncalibrated,
                and the model historically understates its favourites. Only the
                call above is graded.
              </p>
            </div>
          {/if}
        {/each}
      {/each}

      <!-- Every call in the list as one betslip (BETPAWA_PLAN.md 6). A basket,
           not a parlay: lineless calls are left out and named (D13), kicked-off
           calls left out and counted, and the copy says what a single multibet
           of this size is (D14). The count on the button is what loads. -->
      {#if $betpawa.status === 'anonymous'}
        <div class="place">
          <button type="button" class="bet ghost" onclick={promptSignIn}>Sign in to place these on betPawa</button>
        </div>
      {:else if $betpawa.status === 'ready'}
        {@const slip = daySlip($betpawa.host, tips, $betpawa.byFixture, new Date())}
        {#if slip.url}
          <div class="place">
            <a class="bet big" href={slip.url} target="_blank" rel="noopener noreferrer"
              >{slip.loaded === 1 ? 'Place this call' : `Place all ${slip.loaded} calls`} on betPawa ↗</a>
            <p class="fine">
              Loads {slip.loaded} selection{slip.loaded === 1 ? '' : 's'} into one betPawa betslip.
              {#if slip.loaded > 1}As a single multibet it will almost never win — remove legs
              there, or see what a slip claims on the <a href="/parlay">parlay page</a>.{/if}
              {#if slip.skipped.length}No line on betPawa for {slip.skipped.join(', ')}.{/if}
              {#if slip.kickedOff}{slip.kickedOff} already kicked off and left out.{/if}
            </p>
          </div>
        {/if}
      {/if}
    </div>

    <p class="note">
      A call of <span class="code">+1.5</span> backs that team with a
      1.5-goal start: it wins unless they lose by two or more. A call of
      <span class="code">12</span>, <span class="code">1X</span> or
      <span class="code">X2</span> is a hedge covering two of the three
      results. The rule steps down to one of these whenever no single result
      clears its confidence floor, which is most weeks and most matches.
      Confidence is the model's own probability for the call as published — it
      is uncalibrated and historically understates itself. Click a fixture to
      see what the model thought of each result; only the call is graded.
      Signed in from a country betPawa serves, a call also carries a
      <span class="code">Bet this on betPawa</span> button: it opens that
      wager in a betslip on betPawa's site for your country. It is a link,
      not a stake, and the odds there are the bookmaker's — this site shows
      none.
    </p>
  {/if}
</section>

<!-- The settled list and the record are pages of their own (docs/SEO_PLAN.md
     2.6, D10). What stays here is a summary that links through: enough for a
     first-time reader to see that calls are graded, little enough that the
     pages it links to are not competing with a copy of themselves. The ids
     are kept so an old /#results or /#record link still lands on the summary
     that replaced the section. -->
<section id="results" class="page">
  <div class="head">
    <div>
      <div class="kicker">Settled</div>
      <h2>Last time out</h2>
    </div>
    <a class="more" href="/results">All results →</a>
  </div>

  <!-- `error` is checked as well as emptiness: a failed read also leaves the
       list empty, and reporting that as "nothing graded yet" would present an
       outage as a record. -->
  {#if error}
    <p class="state bad">{error}</p>
  {:else if recent.length === 0}
    <p class="state">Nothing graded yet.</p>
  {:else}
    <div class="cards">
      {#each recent as r}
        <a class="card" class:won={r.outcome === 'win'} class:lost={r.outcome === 'lose'}
          href={matchPath(r)}>
          <div class="cardtop">
            <span class="cardfix">{r.home_team} v {r.away_team}</span>
            <span class="mark">{r.outcome === 'win' ? 'WON' : r.outcome === 'lose' ? 'LOST' : 'VOID'}</span>
          </div>
          <div class="league">{divisionName(r.division)}</div>
          <div class="cardfoot">
            <span>{callLabel(r.side, r.home_team, r.away_team)}</span>
            <span class="when">{shortDay(r.match_date)}</span>
          </div>
        </a>
      {/each}
    </div>
    <p class="fine">
      The last six. <a href="/results">Every settled call</a> — by division, with the score each
      was graded from.
    </p>
  {/if}
</section>

<section id="record" class="page">
  <div class="head">
    <div>
      <div class="kicker">Everything we have published</div>
      <h2>The record</h2>
    </div>
    <a class="more" href="/record">The full record →</a>
  </div>

  {#if error}
    <p class="state bad">{error}</p>
  {:else if record}
    <p class="lede">
      {#if record.graded}
        <strong>{pct(record.strike_rate, 1)}</strong> of our graded calls came in —
        {record.won.toLocaleString()} of {record.graded.toLocaleString()}, over
        {record.matchweeks} matchweek{record.matchweeks === 1 ? '' : 's'}. Every one was written to
        the database before its match was played and settled from the result afterwards.
      {:else}
        Nothing has been graded yet. Every call is written to the database before its match is
        played and settled from the result afterwards.
      {/if}
    </p>
    <p class="fine">
      <a href="/record">The record, division by division</a> — with what the number is, and what it
      is not.
    </p>
  {/if}
</section>

<style>
  .page { max-width: var(--page); margin: 0 auto; padding: 64px 32px 0; }

  /* --- stats strip -------------------------------------------------------- */
  .stats { border-bottom: 1px solid var(--line); }
  .stats .inner {
    max-width: var(--page); margin: 0 auto; padding: 26px 32px 0;
    display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 8px;
  }
  .tile { display: flex; flex-direction: column; gap: 2px; }
  .figure { font-family: var(--display); font-weight: 800; font-size: 40px; line-height: 1; }
  .figure.accent { color: var(--accent); }
  .caption {
    font-family: var(--mono); font-size: 11px; letter-spacing: 0.18em;
    text-transform: uppercase; color: var(--muted);
  }
  .disclaimer {
    max-width: var(--page); margin: 0 auto; padding: 16px 32px 26px;
    font-size: 13px; color: var(--dim);
  }

  /* --- section headings --------------------------------------------------- */
  .head {
    display: flex; align-items: flex-end; justify-content: space-between;
    flex-wrap: wrap; gap: 16px;
  }
  .kicker {
    font-family: var(--mono); font-size: 11px; letter-spacing: 0.22em;
    text-transform: uppercase; color: var(--accent);
  }
  h2 {
    font-family: var(--display); font-weight: 800; font-size: clamp(32px, 4vw, 52px);
    line-height: 1; text-transform: uppercase; color: #fff; margin: 10px 0 0;
  }
  .mono { font-family: var(--mono); }
  .summary { font-size: 12px; color: var(--muted); }
  .zone { display: block; }

  /* --- division tabs ------------------------------------------------------ */
  .tabs { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 30px; }
  .tabs button {
    font-family: var(--display); font-weight: 700; font-size: 16px;
    letter-spacing: 0.09em; text-transform: uppercase; white-space: nowrap;
    line-height: 1.2; padding: 12px 22px; border-radius: 3px;
    border: 1px solid #33333c; background: transparent; color: var(--body);
    cursor: pointer;
  }
  .tabs button:hover { border-color: var(--muted); }
  .tabs button.on { background: var(--accent); border-color: var(--accent); color: var(--bg); }

  /* --- the list ----------------------------------------------------------- */
  .list {
    margin-top: 26px; border: 1px solid var(--line); border-radius: 6px;
    overflow: hidden; background: var(--panel);
  }
  .daylabel {
    background: var(--panel-2); padding: 13px 22px; font-family: var(--display);
    font-weight: 700; font-size: 17px; letter-spacing: 0.09em; text-transform: uppercase;
    color: #d6d6de; border-bottom: 1px solid var(--line);
  }
  .row {
    display: grid; grid-template-columns: minmax(0, 1fr) 320px; gap: 24px;
    align-items: center; padding: 18px 22px; border-bottom: 1px solid var(--line-2);
  }
  .fixture { display: grid; grid-template-columns: 1fr auto 1fr; align-items: center; gap: 16px; }
  .side { display: flex; align-items: center; gap: 12px; min-width: 0; }
  .side.home { justify-content: flex-end; }
  .side.home .club { text-align: right; }
  .club { font-size: 16px; font-weight: 600; color: #f2f2f5; }
  .crest {
    flex: none; width: 34px; height: 34px; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-family: var(--display); font-weight: 800; font-size: 13px;
    letter-spacing: 0.03em; color: #fff;
  }
  .kick {
    font-family: var(--display); font-weight: 700; font-size: 20px; color: #fff;
    background: var(--bg); border: 1px solid #2c2c34; border-radius: 3px; padding: 5px 12px;
  }
  .kick .shift { font-size: 11px; margin-left: 3px; color: var(--muted); }
  .verdict { display: flex; align-items: center; gap: 16px; justify-content: flex-end; }
  .call { text-align: right; min-width: 0; }
  .label {
    font-family: var(--mono); font-size: 10px; letter-spacing: 0.2em;
    text-transform: uppercase; color: var(--dim);
  }
  .phrase {
    font-family: var(--display); font-weight: 800; font-size: 19px;
    text-transform: uppercase; color: var(--accent); line-height: 1.15;
  }
  .league { font-family: var(--mono); font-size: 11px; color: var(--muted); margin-top: 2px; }
  .code {
    font-family: var(--mono); font-size: 11px; font-weight: 600; color: var(--body);
    background: var(--panel-2); border: 1px solid var(--line);
    border-radius: 3px; padding: 1px 5px; vertical-align: 2px; cursor: help;
  }
  /* --- the betPawa button (B26) ------------------------------------------ */
  .bet {
    display: inline-block; margin-top: 8px; font-family: var(--mono); font-size: 10.5px;
    letter-spacing: 0.08em; text-transform: uppercase; text-decoration: none;
    line-height: 1.2; padding: 5px 10px; border-radius: 3px; white-space: nowrap;
    border: 1px solid var(--accent); color: var(--accent); background: transparent;
    cursor: pointer;
  }
  .bet:hover { background: var(--accent); color: var(--bg); }
  .bet.event { border-color: var(--line); color: var(--muted); }
  .bet.event:hover { background: transparent; border-color: var(--muted); color: var(--body); }
  .bet.ghost { border-style: dashed; border-color: var(--line); color: var(--muted); }
  .bet.ghost:hover { background: transparent; border-color: var(--accent); color: var(--accent); }
  .bet:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
  .bet.big { font-size: 12px; padding: 10px 18px; margin-top: 0; background: var(--accent); color: var(--bg); }
  .bet.big:hover { background: var(--accent-soft); }
  .place {
    display: flex; align-items: center; gap: 18px; flex-wrap: wrap;
    padding: 16px 22px; background: var(--panel-2); border-top: 1px solid var(--line-2);
  }
  .place .fine { margin: 0; max-width: 60ch; }
  .place .fine a { color: var(--accent); }
  .conf { width: 92px; flex: none; }
  .confhead {
    display: flex; justify-content: space-between; font-family: var(--mono);
    font-size: 11px; color: var(--muted); margin-bottom: 5px;
  }
  .confhead .v { color: #fff; }
  .track { height: 5px; border-radius: 3px; background: #2c2c34; overflow: hidden; }
  .fill { height: 100%; border-radius: 3px; background: var(--accent); }

  /* --- the drawer behind a call (B22) ------------------------------------- */
  .row { cursor: pointer; transition: background 120ms; }
  .row:hover, .row.open { background: var(--panel-2); }
  .row:focus-visible { outline: 2px solid var(--accent); outline-offset: -2px; }
  .caret {
    flex: none; width: 8px; height: 8px; margin-left: 2px;
    border-right: 2px solid var(--dim); border-bottom: 2px solid var(--dim);
    transform: rotate(45deg); transition: transform 160ms;
  }
  .row.open .caret { transform: rotate(-135deg); border-color: var(--accent); }
  .drawer {
    padding: 14px 22px 18px; background: var(--panel-2);
    border-bottom: 1px solid var(--line-2); border-top: 1px dashed var(--line);
  }
  .drawerhead {
    display: flex; justify-content: space-between; align-items: center;
    gap: 12px; flex-wrap: wrap; margin-bottom: 10px;
  }
  .bars { list-style: none; margin: 0; padding: 0; max-width: 640px; }
  .bars li {
    display: grid; grid-template-columns: minmax(0, 1fr) 160px 44px;
    align-items: center; gap: 14px; padding: 5px 0;
  }
  .bars .name { font-size: 14px; font-weight: 600; color: var(--body); min-width: 0; }
  .bars .track, .bars .fill { display: block; }
  .bars .fill { background: var(--accent); }
  .bars .v { font-family: var(--mono); font-size: 12px; color: #fff; text-align: right; }
  .tag {
    display: inline-block; margin-left: 8px; font-family: var(--mono); font-size: 10px;
    letter-spacing: 0.08em; text-transform: uppercase; color: var(--accent);
    white-space: nowrap;
  }
  .fine { margin: 10px 0 0; font-size: 12.5px; line-height: 1.6; color: var(--muted); max-width: 72ch; }
  .fine.dim { color: var(--dim); }

  .note {
    margin-top: 18px; font-size: 13px; line-height: 1.7; color: var(--muted);
    max-width: 90ch;
  }

  /* --- results cards ------------------------------------------------------ */
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
  .mark { font-family: var(--mono); font-size: 12px; font-weight: 600; color: var(--muted); }
  .card.won .mark { color: var(--good); }
  .card.lost .mark { color: var(--bad); }
  .cardfoot {
    display: flex; justify-content: space-between; gap: 10px; margin-top: 9px;
    font-family: var(--mono); font-size: 11px; color: var(--muted);
  }
  .when { color: #c9c9d2; }

  /* --- record summary ----------------------------------------------------- */
  .lede { margin: 22px 0 0; font-size: 16px; line-height: 1.7; color: var(--body); max-width: 78ch; }
  .lede strong {
    font-family: var(--display); font-weight: 800; font-size: 26px; color: var(--accent);
  }

  /* The link out of a summary to the page it summarises (2.6), and out of a
     call's drawer to its match page (2.8). */
  .more {
    font-family: var(--mono); font-size: 11px; letter-spacing: 0.08em;
    text-transform: uppercase; color: var(--muted); white-space: nowrap;
  }
  .more:hover { color: var(--accent); }

  /* A settled card is a link to its match page (2.8). */
  .card { display: block; color: inherit; text-decoration: none; }
  .card:hover { background: var(--panel-2); color: inherit; }
  .card:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }

  /* --- states ------------------------------------------------------------- */
  .state { margin-top: 26px; color: var(--muted); }
  .state.bad { color: var(--bad); }
  .state.box {
    background: var(--panel); border: 1px solid var(--line);
    border-left: 3px solid var(--accent); border-radius: 5px; padding: 18px 20px;
  }
  .state.box strong { color: var(--text); display: block; margin-bottom: 8px; }
  .state.box p { margin: 0; max-width: 70ch; line-height: 1.6; }

  @media (max-width: 940px) {
    .row { grid-template-columns: 1fr; gap: 14px; }
    /* Stacked, the call is no longer the right-hand column, so right-aligned
       text leaves the short label ragged over the long one. */
    .verdict { justify-content: space-between; }
    .call { text-align: left; }
  }
  @media (max-width: 820px) {
    .page { padding: 48px 18px 0; }
    .drawer { padding-left: 18px; padding-right: 18px; }
    .bars li { grid-template-columns: minmax(0, 1fr) 90px 40px; gap: 10px; }
    .stats .inner, .disclaimer { padding-left: 18px; padding-right: 18px; }
    .fixture { grid-template-columns: 1fr auto 1fr; gap: 10px; }
    .club { font-size: 14px; }
  }
</style>
