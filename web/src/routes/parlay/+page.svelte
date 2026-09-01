<script>
  // The parlay page (`docs/PARLAY_PLAN.md`, B24): one parlay generated from
  // today's published calls. Three controls -- league, how safe each leg
  // must be, how many legs -- and the page shows the strongest calls that
  // clear the bar with their claimed probabilities multiplied. The selection
  // and the product are the API's (`GET /parlay`, `engine/serve/parlay.py`);
  // this component renders what it is handed and forms no probability.
  import {
    getParlay,
    callLabel,
    callCode,
    callMeans,
    DIVISIONS,
    RISK_PRESETS,
    LEGS,
    pct
  } from '$lib/api.js';
  import { fixtureBadges } from '$lib/badge.js';
  import { localKickoff, viewerZone } from '$lib/kickoff.js';
  import { availability } from '$lib/parlay.js';

  // Defaults are the recommendation (`PARLAY_PLAN.md` §1): every league,
  // the Safer threshold, two legs.
  let division = $state('');
  let risk = $state('safer');
  let legs = $state(LEGS.default);

  let parlay = $state(null);
  let error = $state(null);
  let loading = $state(true);

  const minClaim = () => RISK_PRESETS.find(([key]) => key === risk)[2];

  async function load(div, size, min) {
    loading = true;
    error = null;
    try {
      parlay = await getParlay(div || null, size, min);
    } catch (e) {
      error = e.message;
    } finally {
      loading = false;
    }
  }
  // One fetch on mount and one per control change. The controls are read
  // here, synchronously, which is what makes the effect track them.
  $effect(() => {
    load(division, legs, minClaim());
  });

  const divisionName = (code) => DIVISIONS.find(([c]) => c === code)?.[1] ?? code;
  const legsOffered = Array.from({ length: LEGS.max - LEGS.min + 1 }, (_, i) => LEGS.min + i);

  // Kick-offs arrive as UK wall-clock and are shown in the viewer's zone
  // (`$lib/kickoff.js`), as on the main list.
  const zone = viewerZone();
  const kick = (t) => localKickoff(t.match_date, t.kickoff_time, zone);
  const shortDay = (iso) => {
    const [y, m, d] = iso.split('-').map(Number);
    return new Date(y, m - 1, d).toLocaleDateString('en-GB', {
      weekday: 'short',
      day: 'numeric',
      month: 'short'
    });
  };
</script>

<section class="page">
  <div class="head">
    <div>
      <div class="kicker">Build a parlay</div>
      <h2>Today's calls, combined</h2>
    </div>
    <div class="mono summary">
      {#if parlay}
        {parlay.pool} call{parlay.pool === 1 ? '' : 's'} live
        <span class="zone">· kick-offs in your local time ({zone})</span>
      {/if}
    </div>
  </div>

  <p class="intro">
    Pick a league, how safe each leg must be, and how many legs. The page takes
    the strongest published calls that clear the bar and multiplies their claimed
    probabilities. Every leg is one of today's calls from the main list — nothing
    here is a new call.
  </p>

  <div class="tabs">
    {#each DIVISIONS as [code, label]}
      <button class:on={division === code} onclick={() => (division = code)}>{label}</button>
    {/each}
  </div>

  <div class="controls">
    <div class="control">
      <span class="label">Risk · each leg must claim at least</span>
      <div class="switch" role="group" aria-label="Minimum claim per leg">
        {#each RISK_PRESETS as [key, label, min]}
          <button class:on={risk === key} onclick={() => (risk = key)}>
            {label}{#if min > 0}&nbsp;· {pct(min, 0)}{/if}
          </button>
        {/each}
      </div>
    </div>
    <div class="control">
      <span class="label">Legs</span>
      <div class="switch" role="group" aria-label="Number of legs">
        {#each legsOffered as n}
          <button class:on={legs === n} class:warn={n >= LEGS.warn} onclick={() => (legs = n)}>{n}</button>
        {/each}
      </div>
    </div>
  </div>

  {#if error}
    <p class="state bad">{error}</p>
  {:else if !parlay}
    <p class="state">Loading…</p>
  {:else}
    {@const note = availability(parlay)}

    <!-- Owner decision D3: four legs are offered, labelled. On a typical
         Saturday the best four calls multiply to about 0.49 (PARLAY_PLAN.md
         §1), so the label is a measured statement, not a hedge. -->
    {#if parlay.size_warning}
      <p class="warning">
        A {parlay.requested}-leg parlay is more likely to lose than win. On a
        typical Saturday the best four calls multiply to about 49%.
      </p>
    {/if}

    {#if parlay.legs.length === 0}
      <div class="state box">
        <strong>{note.head}</strong>
        <p>{note.body}</p>
      </div>
    {:else}
      <div class="slip" class:busy={loading}>
        {#each parlay.legs as t (t.tip_id)}
          {@const badge = fixtureBadges(t.home_team, t.away_team)}
          {@const k = kick(t)}
          <div class="leg">
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
                  {#if callCode(t.side) && callMeans(t.side, t.home_team, t.away_team)}
                    <span class="code" title={callMeans(t.side, t.home_team, t.away_team)}
                      >{callCode(t.side)}</span
                    >
                  {/if}
                </div>
                <div class="league">{divisionName(t.division)} · {shortDay(t.match_date)}</div>
              </div>
              <div class="conf">
                <div class="confhead"><span>CLAIMED</span><span class="v">{pct(t.model_prob, 0)}</span></div>
                <div class="track"><div class="fill" style="width:{100 * t.model_prob}%"></div></div>
              </div>
            </div>
          </div>
        {/each}

        <div class="total">
          <div class="figure">
            <span class="label">All {parlay.legs.length} legs · claimed</span>
            <span class="big">{pct(parlay.claimed, 0)}</span>
          </div>
          <p class="fine">
            The legs' claimed probabilities multiplied together, on the assumption
            that the games are independent. Uncalibrated, like every probability
            on this site.
          </p>
        </div>
      </div>

      <!-- Fewer calls cleared the bar than legs asked for (owner decision D5):
           the slip shows what cleared and says so, and never fills a slot
           with a weaker call. -->
      {#if note}
        <p class="short"><strong>{note.head}</strong> {note.body}</p>
      {/if}
    {/if}

    <div class="honesty">
      <h3>What this figure is, and what it is not</h3>
      <p>
        <strong>It is claimed, not measured.</strong> The combined figure is the
        legs' claimed probabilities multiplied together, assuming the games are
        independent. Each leg's claim is the model's own probability as published
        — uncalibrated, and historically it understates its favourites.
      </p>
      <p>
        <strong>Each leg is graded; the parlay is not.</strong> Every leg is one of
        today's published calls and is settled on its own on the record. We keep no
        record of parlays.
      </p>
      <p>
        <strong>It is not a return.</strong> We publish no return for single calls
        because we cannot support one, and a parlay compounds whatever the singles
        return — it would be worse, not better.
      </p>
    </div>
  {/if}
</section>

<style>
  .page { max-width: var(--page); margin: 0 auto; padding: 64px 32px 0; }

  /* --- section heading, as on the main page ------------------------------- */
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
  .intro { margin: 18px 0 0; font-size: 15px; line-height: 1.7; color: var(--body); max-width: 70ch; }

  /* --- controls ----------------------------------------------------------- */
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

  .controls { display: flex; flex-wrap: wrap; gap: 28px; margin-top: 18px; }
  .control { display: flex; flex-direction: column; gap: 8px; }
  .label {
    font-family: var(--mono); font-size: 10px; letter-spacing: 0.2em;
    text-transform: uppercase; color: var(--dim);
  }
  .switch { display: flex; gap: 4px; flex-wrap: wrap; }
  .switch button {
    font-family: var(--mono); font-size: 12px; letter-spacing: 0.06em;
    text-transform: uppercase; padding: 7px 12px; border-radius: 3px;
    border: 1px solid var(--line); background: transparent; color: var(--muted);
    cursor: pointer; min-width: 40px;
  }
  .switch button:hover { border-color: var(--muted); color: var(--body); }
  .switch button.on { background: var(--bg); border-color: var(--accent); color: var(--accent); }
  .switch button.warn.on { border-color: var(--bad); color: var(--bad); }
  .switch button:focus-visible, .tabs button:focus-visible {
    outline: 2px solid var(--accent); outline-offset: 2px;
  }

  .warning {
    margin: 22px 0 0; padding: 12px 16px; font-size: 14px; line-height: 1.6;
    color: var(--body); background: var(--panel); border: 1px solid var(--line);
    border-left: 3px solid var(--bad); border-radius: 5px; max-width: 70ch;
  }

  /* --- the slip ----------------------------------------------------------- */
  .slip {
    margin-top: 26px; border: 1px solid var(--line); border-radius: 6px;
    overflow: hidden; background: var(--panel); transition: opacity 120ms;
  }
  .slip.busy { opacity: 0.6; }
  .leg {
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
  .conf { width: 92px; flex: none; }
  .confhead {
    display: flex; justify-content: space-between; font-family: var(--mono);
    font-size: 11px; color: var(--muted); margin-bottom: 5px;
  }
  .confhead .v { color: #fff; }
  .track { height: 5px; border-radius: 3px; background: #2c2c34; overflow: hidden; }
  .fill { height: 100%; border-radius: 3px; background: var(--accent); }

  .total {
    display: flex; align-items: center; justify-content: space-between; gap: 24px;
    flex-wrap: wrap; padding: 18px 22px; background: var(--panel-2);
  }
  .figure { display: flex; flex-direction: column; gap: 4px; }
  .big { font-family: var(--display); font-weight: 800; font-size: 44px; line-height: 1; color: var(--accent); }
  .fine { margin: 0; font-size: 12.5px; line-height: 1.6; color: var(--muted); max-width: 52ch; }
  .short { margin: 14px 0 0; font-size: 13px; line-height: 1.7; color: var(--muted); max-width: 80ch; }
  .short strong { color: var(--body); }

  /* --- honesty ------------------------------------------------------------ */
  .honesty { margin-top: 34px; max-width: 74ch; }
  .honesty h3 {
    font-family: var(--display); font-weight: 700; font-size: 24px;
    text-transform: uppercase; color: #fff; margin: 0 0 12px;
  }
  .honesty p { font-size: 15px; line-height: 1.7; color: var(--body); margin: 0 0 14px; }
  .honesty strong { color: #fff; }

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
    .leg { grid-template-columns: 1fr; gap: 14px; }
    .verdict { justify-content: space-between; }
    .call { text-align: left; }
  }
  @media (max-width: 820px) {
    .page { padding: 48px 18px 0; }
    .fixture { grid-template-columns: 1fr auto 1fr; gap: 10px; }
    .club { font-size: 14px; }
  }
</style>
