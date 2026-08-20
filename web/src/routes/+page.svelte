<script>
  import { onMount } from 'svelte';
  import {
    getTips,
    getTipResults,
    getTipRecord,
    callLabel,
    callCode,
    callMeans,
    DIVISIONS,
    pct
  } from '$lib/api.js';
  import { fixtureBadges } from '$lib/badge.js';
  import { localKickoff, viewerZone } from '$lib/kickoff.js';
  import { nextLikeliest } from '$lib/view.js';
  import { resolveOwner } from '$lib/owner.js';
  import { slide } from 'svelte/transition';

  let tipsDivision = $state('');
  // The settled section filters and sizes itself independently of the tips
  // tabs. 500 is the server's own ceiling (api/main.py, limit le=500) — the
  // API 400s above it, so "all" means "up to the server max".
  let resultsDivision = $state('');
  let showAll = $state(false);
  let resultsLoading = $state(false);
  let resultsError = $state(null);
  const resultsLimit = () => (showAll ? 500 : 12);
  // Scores and claimed probabilities on the settled cards are opt-in: the
  // default card is the graded call and its outcome, nothing else.
  let showDetail = $state(false);
  // The rule's name and parameters are for the owner, not testers
  // (`$lib/owner.js`: `/?owner=1` to show, `/?owner=0` to hide).
  let owner = $state(false);
  // The drawer behind a call (B22): which fixture is open.
  let open = $state(null);
  const toggle = (id) => (open = open === id ? null : id);
  const onRowKey = (event, id) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      toggle(id);
    }
  };
  let tips = $state([]);
  let results = $state([]);
  let record = $state(null);
  let error = $state(null);
  let loading = $state(true);
  let loaded = $state(false);

  async function load() {
    loading = true;
    error = null;
    try {
      [tips, results, record] = await Promise.all([
        getTips(tipsDivision || null),
        getTipResults(resultsDivision || null, resultsLimit()),
        getTipRecord()
      ]);
    } catch (e) {
      error = e.message;
    } finally {
      loading = false;
      loaded = true;
    }
  }

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

  async function loadResults() {
    resultsLoading = true;
    resultsError = null;
    try {
      results = await getTipResults(resultsDivision || null, resultsLimit());
    } catch (e) {
      resultsError = e.message;
    } finally {
      resultsLoading = false;
    }
  }

  onMount(() => {
    owner = resolveOwner(window.location.search, window.localStorage);
    load();
  });
  $effect(() => {
    tipsDivision;
    if (loaded) loadTips();
  });
  $effect(() => {
    resultsDivision;
    showAll;
    if (loaded) loadResults();
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
  // whose local date differs says so with a +1 / −1.
  const zone = viewerZone();
  const kick = (t) => localKickoff(t.match_date, t.kickoff_time, zone);

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

  // --- hero parallax -------------------------------------------------------
  let art, plate, copy;

  function heroMove(event) {
    const box = event.currentTarget.getBoundingClientRect();
    const x = (event.clientX - box.left) / box.width - 0.5;
    const y = (event.clientY - box.top) / box.height - 0.5;
    const shift = (node, mx, my, scale) => {
      if (node)
        node.style.transform =
          `translate3d(${(x * mx).toFixed(2)}px, ${(y * my).toFixed(2)}px, 0)` +
          (scale ? ` scale(${scale})` : '');
    };
    shift(art, -80, -40, 1.05);
    shift(plate, 46, 26);
    shift(copy, 18, 10);
  }

  const heroLeave = () => {
    for (const node of [art, plate, copy])
      if (node) node.style.transform = 'translate3d(0,0,0)';
  };
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<section class="hero" onmousemove={heroMove} onmouseleave={heroLeave}>
  <div class="plate" bind:this={plate}>
    <div class="orb light"></div>
    <div class="orb dark"></div>
  </div>
  <div class="notch"></div>
  <div class="art" bind:this={art}>
    <img src="/player.png" alt="" />
  </div>
  <div class="copy" bind:this={copy}>
    <div class="eyebrow"><span class="dot"></span>Premier League · Championship · League One · League Two</div>
    <h1>We call it before kick-off</h1>
    <p>
      Every fixture in the top four English divisions, called before kick-off and
      graded after. One call per match — and we say plainly when we are hedging.
    </p>
    <div class="actions">
      <a href="#tips" class="solid">See this week's calls</a>
      <a href="#record" class="ghost">Check the record</a>
    </div>
  </div>
</section>

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
        <span class="zone">· kick-offs in your local time ({zone})</span>
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
    </p>
  {/if}
</section>

<section id="results" class="page">
  <div class="head">
    <div>
      <div class="kicker">Settled</div>
      <h2>Last time out</h2>
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

  <div class="tabs">
    {#each DIVISIONS as [code, label]}
      <button class:on={resultsDivision === code} onclick={() => (resultsDivision = code)}>{label}</button>
    {/each}
  </div>

  <!-- `error` is checked as well as emptiness: a failed fetch also leaves the
       list empty, and reporting that as "nothing graded yet" would present an
       outage as a record. `resultsError` is the same rule for this section's
       own refetches (filter and show-all changes). -->
  {#if resultsError || error}
    <p class="state bad">{resultsError || error}</p>
  {:else if resultsLoading}
    <p class="state">Loading…</p>
  {:else if !loading && results.length === 0}
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
          {#if !resultsDivision}
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
</section>

<section id="record" class="page">
  <div class="head">
    <div>
      <div class="kicker">Everything we have published</div>
      <h2>The record</h2>
    </div>
  </div>

  {#if error}
    <p class="state bad">{error}</p>
  {:else if record}
    <!-- Cells are nowrap, so on a narrow viewport the table is wider than the
         screen. It scrolls inside this box; without it the whole page scrolled
         sideways and every section inherited the overflow. -->
    <div class="tablewrap">
      <table class="record">
      <thead>
        <tr>
          <th>Division</th>
          <th class="num">Published</th>
          <th class="num">Graded</th>
          <th class="num">Right</th>
          <th class="num">Strike rate</th>
        </tr>
      </thead>
      <tbody>
        {#each record.by_division as d}
          <tr>
            <td>{divisionName(d.division)}</td>
            <td class="num">{d.published.toLocaleString()}</td>
            <td class="num">{d.graded.toLocaleString()}</td>
            <td class="num">{d.won.toLocaleString()}</td>
            <td class="num strike">{d.strike_rate == null ? '—' : pct(d.strike_rate, 1)}</td>
          </tr>
        {/each}
        <tr class="total">
          <td>All divisions</td>
          <td class="num">{record.published.toLocaleString()}</td>
          <td class="num">{record.graded.toLocaleString()}</td>
          <td class="num">{record.won.toLocaleString()}</td>
          <td class="num strike">{record.strike_rate == null ? '—' : pct(record.strike_rate, 1)}</td>
        </tr>
      </tbody>
      </table>
    </div>

    <div class="honesty">
      <h3>What this number is, and what it is not</h3>
      <p>
        <strong>It is honest about accuracy.</strong> Every call above was written
        to the database before the match was played and settled from the result
        afterwards. Nothing is added later, nothing is removed, and there is one
        call per fixture — the database refuses a second one.
      </p>
      <p>
        <strong>It is not a return.</strong> A high strike rate is mostly a
        property of backing short prices, not of being better than the market.
        Measured over eleven seasons at the prices a customer can actually get,
        this rule does not make money to any degree we can demonstrate. We do not
        publish a profit figure because we cannot support one.
      </p>
      {#if owner && record.rule}
        <p class="mono prov">
          rule {record.rule.rule_version} · floor {record.rule.floor}{record.rule
            .ceiling
            ? ` · ceiling ${record.rule.ceiling}`
            : ''}
        </p>
      {/if}
    </div>

    <!-- The headline above is one rule's record. When the rule has changed, the
         earlier versions are shown here rather than pooled into it or dropped:
         two rules are two products, and averaging them would label a mixed
         number with one rule's name. Hidden while only one version exists, so
         nothing on the page changes until it has to -- and owner-only, like
         the provenance line above. -->
    {#if owner && record.by_rule && record.by_rule.length > 1}
      <div class="tablewrap">
        <table class="record versions">
          <thead>
            <tr>
              <th>Rule version</th>
              <th class="num">Published</th>
              <th class="num">Graded</th>
              <th class="num">Right</th>
              <th class="num">Strike rate</th>
            </tr>
          </thead>
          <tbody>
            {#each record.by_rule as v}
              <tr class:current={v.rule_version === record.rule?.rule_version}>
                <td class="mono">{v.rule_version}</td>
                <td class="num">{v.published.toLocaleString()}</td>
                <td class="num">{v.graded.toLocaleString()}</td>
                <td class="num">{v.won.toLocaleString()}</td>
                <td class="num strike">{v.strike_rate == null ? '—' : pct(v.strike_rate, 1)}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {/if}
  {/if}
</section>

<style>
  .page { max-width: var(--page); margin: 0 auto; padding: 64px 32px 0; }

  /* --- hero --------------------------------------------------------------- */
  .hero {
    position: relative;
    background: var(--accent);
    overflow: hidden;
    min-height: 520px;
    isolation: isolate;
  }
  .plate {
    position: absolute; inset: -6%; z-index: 0;
    transition: transform 340ms cubic-bezier(0.2, 0.7, 0.3, 1);
  }
  .orb { position: absolute; border-radius: 50%; }
  .orb.light { right: -4%; top: -30%; width: 900px; height: 900px; background: rgba(255,255,255,0.07); }
  .orb.dark { left: -8%; bottom: -40%; width: 620px; height: 620px; background: rgba(0,0,0,0.06); }
  .notch {
    position: absolute; inset: 0; z-index: 3; pointer-events: none;
    background: var(--bg);
    clip-path: polygon(100% 34%, 100% 100%, 0 100%, 0 96%);
  }
  .art {
    position: absolute; z-index: 5; right: -2%; bottom: -4%;
    width: min(64%, 1000px); pointer-events: none;
    transition: transform 340ms cubic-bezier(0.2, 0.7, 0.3, 1);
    will-change: transform;
  }
  .art img { width: 100%; display: block; filter: drop-shadow(0 30px 60px rgba(0,0,0,0.28)); }
  .copy {
    position: relative; z-index: 4; max-width: var(--page); margin: 0 auto;
    padding: 96px 32px 120px;
    transition: transform 340ms cubic-bezier(0.2, 0.7, 0.3, 1);
  }
  /* Not flex: as a flex item the division list is one unbreakable box, so on a
     narrow viewport it wrapped as a whole and left the dot alone on its own
     line. Inline flow lets the text wrap around the dot instead. */
  .eyebrow {
    font-family: var(--mono); font-weight: 600; font-size: 12px; line-height: 1.6;
    letter-spacing: 0.22em; text-transform: uppercase; color: rgba(255,255,255,0.85);
  }
  .dot {
    display: inline-block; width: 8px; height: 8px; border-radius: 50%;
    background: var(--bg); margin-right: 10px; vertical-align: middle;
  }
  h1 {
    font-family: var(--display); font-weight: 800;
    font-size: clamp(48px, 7.4vw, 116px); line-height: 0.88; letter-spacing: -0.01em;
    text-transform: uppercase; color: #fff; margin: 22px 0 0; max-width: 12ch;
    text-wrap: balance;
  }
  .copy p {
    font-size: 18px; line-height: 1.55; color: rgba(255,255,255,0.92);
    max-width: 46ch; margin: 22px 0 0; font-weight: 500;
  }
  .actions { display: flex; flex-wrap: wrap; gap: 14px; margin-top: 34px; }
  .actions a {
    font-family: var(--display); font-weight: 700; font-size: 16px;
    letter-spacing: 0.1em; text-transform: uppercase; border-radius: 3px;
  }
  .solid { background: var(--bg); color: #fff; padding: 15px 30px; }
  .ghost { border: 2px solid rgba(255,255,255,0.7); color: #fff; padding: 13px 28px; }
  .actions a:hover { color: #fff; }

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
  .score { font-family: var(--mono); font-weight: 700; color: #fff; padding: 0 1px; }
  .mark { font-family: var(--mono); font-size: 12px; font-weight: 600; color: var(--muted); }
  .card.won .mark { color: var(--good); }
  .card.lost .mark { color: var(--bad); }
  .cardfoot {
    display: flex; justify-content: space-between; gap: 10px; margin-top: 9px;
    font-family: var(--mono); font-size: 11px; color: var(--muted);
  }
  .when { color: #c9c9d2; }

  /* --- record ------------------------------------------------------------- */
  .tablewrap { overflow-x: auto; }
  .record { margin-top: 24px; min-width: 460px; }
  .record .strike { font-weight: 700; color: var(--accent); }
  .record .total td { border-top: 1px solid var(--line); font-weight: 700; color: #fff; }
  .versions .current td { color: #fff; }
  .honesty { margin-top: 34px; max-width: 74ch; }
  .honesty h3 {
    font-family: var(--display); font-weight: 700; font-size: 24px;
    text-transform: uppercase; color: #fff; margin: 0 0 12px;
  }
  .honesty p { font-size: 15px; line-height: 1.7; color: var(--body); margin: 0 0 14px; }
  .honesty strong { color: #fff; }
  .prov { font-size: 11px; color: var(--dim); }

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
    .art { width: 78%; opacity: 0.35; }
    .copy { padding: 64px 18px 90px; }
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
