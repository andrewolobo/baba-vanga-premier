<script>
  // The match analysis (docs/ANALYSIS_PLAN.md, Phase 4): the written preview
  // of the published call, for signed-in readers (D10).
  //
  // The server renders only a fixed-size card, and only when an analysis
  // exists (`fx.has_analysis`). The text is fetched in the browser when a
  // signed-in reader opens it. That keeps it out of the page's HTML, so no
  // crawler or shared cache sees it, and keeps the page's layout still: a
  // panel that grew on its own after load would shift everything below it,
  // and the match page's CLS is ~0.003 (SEO_PLAN.md 1.10). Growth that
  // follows a click does not count.
  //
  // Every number shown comes from the evidence pack, never from the prose.
  // The prose is the model's and passed the validator. There are no prices
  // here (D1).
  import { getContext } from 'svelte';
  import { callLabel } from '$lib/api.js';
  import {
    getFixtureAnalysis,
    factText,
    menuNote,
    flagText,
    trendText,
    paragraphs,
    fallbackFacts
  } from '$lib/analysis.js';

  let { fx } = $props();
  const { store: account, promptSignIn } = getContext('account');

  let view = $state('closed'); // closed | loading | open | error
  let body = $state(null);
  let why = $state(false);

  // Another match page reuses this component: start closed, fetch afresh.
  $effect(() => {
    fx.fixture_id;
    view = 'closed';
    body = null;
    why = false;
  });

  const pack = $derived(body?.evidence_pack);
  const label = (side) => callLabel(side, fx.home_name, fx.away_name);
  const panelId = $derived(`analysis-${fx.fixture_id}`);

  async function toggle() {
    if ($account === 'anonymous') return promptSignIn();
    if (body) {
      view = view === 'open' ? 'closed' : 'open';
      return;
    }
    view = 'loading';
    try {
      body = await getFixtureAnalysis(fx.fixture_id);
      view = 'open';
    } catch (e) {
      view = e?.status === 401 ? 'closed' : 'error';
      if (e?.status === 401) promptSignIn();
    }
  }
</script>

{#if fx.has_analysis && $account !== 'unconfigured'}
  <section class="analysis" aria-labelledby="{panelId}-title">
    <div class="head">
      <div>
        <h2 id="{panelId}-title">Match analysis</h2>
        <p class="sub">
          Written when the call was published: the evidence for it, the evidence against it,
          and what could undo it.
        </p>
      </div>
      <button type="button" class="open" class:ghost={$account === 'anonymous'}
        aria-expanded={view === 'open'} aria-controls={panelId} onclick={toggle}
        disabled={view === 'loading'}>
        {#if $account === 'anonymous'}Sign in to read the analysis
        {:else if view === 'loading'}Loading…
        {:else if view === 'open'}Hide the analysis
        {:else}Read the analysis{/if}
      </button>
    </div>

    {#if view === 'error'}
      <p class="note">The analysis could not be loaded. Try again in a moment.</p>
    {/if}

    {#if view === 'open' && body}
      <div class="panel" id={panelId}>
        {#if body.status === 'ok'}
          <div class="prose">
            {#each paragraphs(body.analysis.preview) as p}<p>{p}</p>{/each}
          </div>

          <div class="card">
            <div class="label">Why this call</div>
            <p class="call">{label(pack.call.side)} <span class="claim">{pack.call.model_prob}%</span></p>
            {#if pack.call.means}<p class="means">For this to come in, {pack.call.means}.</p>{/if}
            <p class="rationale">{body.analysis.call.rationale}</p>
            <button type="button" class="why" aria-expanded={why} aria-controls="{panelId}-why"
              onclick={() => (why = !why)}>{why ? 'Hide the evidence' : 'Why? Show the evidence'}</button>
            {#if why}
              <div class="evidence" id="{panelId}-why">
                <div>
                  <h3>For the call</h3>
                  <ul>
                    {#each body.analysis.call.supporting as f (f.id)}
                      <li><span>{f.label}</span><b>{factText(f)}</b></li>
                    {/each}
                  </ul>
                </div>
                <div>
                  <h3>Against the call</h3>
                  {#if body.analysis.call.contradicting.length}
                    <ul>
                      {#each body.analysis.call.contradicting as f (f.id)}
                        <li><span>{f.label}</span><b>{factText(f)}</b></li>
                      {/each}
                    </ul>
                  {:else}
                    <p class="note">None was cited.</p>
                  {/if}
                </div>
              </div>
            {/if}
          </div>
        {:else}
          <p class="note">
            The written analysis for this match did not pass our checks, so only the figures it
            would have been written from are shown.
          </p>
          <div class="card">
            <div class="label">The call</div>
            <p class="call">{label(pack.call.side)} <span class="claim">{pack.call.model_prob}%</span></p>
            {#if pack.call.means}<p class="means">For this to come in, {pack.call.means}.</p>{/if}
          </div>
          {@const card = fallbackFacts(pack)}
          <div class="cols">
            {#each [[pack.home, card.home], [pack.away, card.away], ['Last meetings', card.h2h]] as [title, facts]}
              {#if facts.length}
                <div class="facts">
                  <h3>{title}</h3>
                  <ul>
                    {#each facts as f (f.id)}<li><span>{f.label}</span><b>{factText(f)}</b></li>{/each}
                  </ul>
                </div>
              {/if}
            {/each}
          </div>
        {/if}

        <div class="menu">
          <h3>How the rule chose</h3>
          <p class="note">
            The model's probability for each market. The rule takes the favourite's win at
            {pack.call.floor}% or more; otherwise the likeliest market at {pack.call.ceiling}% or less.
          </p>
          <table>
            <tbody>
              {#each pack.menu as m (m.id)}
                <tr class:called={m.is_call}>
                  <th scope="row">{label(m.side)}</th>
                  <td class="p">{m.p_model}%</td>
                  <td class="n">{menuNote(m, pack.call.floor, pack.call.ceiling)}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>

        {#if pack.flags.length || body.status === 'ok'}
          <div class="risks">
            <h3>What could undo it</h3>
            {#if pack.flags.length}
              <ul class="flags">
                {#each pack.flags as f (f.code + f.side)}<li>{flagText(f, pack.home, pack.away)}</li>{/each}
              </ul>
            {/if}
            {#if body.status === 'ok'}<p>{body.analysis.risk_commentary}</p>{/if}
          </div>
        {/if}

        {#if body.summaries}
          <div class="cols">
            {#each [['home', pack.home], ['away', pack.away]] as [side, name]}
              {@const s = body.summaries[side]}
              <div class="profile">
                <div class="profilehead"><h3>{name}</h3><span class="trend {s.trend}">{trendText(s.trend)}</span></div>
                <p>{s.narrative}</p>
                {#if s.strengths.length}
                  <ul class="points plus">{#each s.strengths as x}<li>{x}</li>{/each}</ul>
                {/if}
                {#if s.weaknesses.length}
                  <ul class="points minus">{#each s.weaknesses as x}<li>{x}</li>{/each}</ul>
                {/if}
              </div>
            {/each}
          </div>
        {/if}

        <!-- Fixed, never generated (D9). -->
        <p class="ai">
          {#if body.status === 'ok'}Written by an AI from the figures on this page.{/if}
          Analysis, not a guarantee.
        </p>
      </div>
    {/if}
  </section>
{/if}

<style>
  .analysis {
    margin-top: 32px; background: var(--panel); border: 1px solid var(--line);
    border-radius: 8px; padding: 22px;
  }
  .head { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 14px 24px; }
  h2 {
    font-family: var(--display); font-weight: 800; font-size: 28px;
    text-transform: uppercase; color: #fff; margin: 0;
  }
  .sub { margin: 4px 0 0; font-size: 14px; color: var(--muted); max-width: 52ch; }
  .open, .why {
    font-family: var(--mono); font-size: 10.5px; letter-spacing: 0.08em; text-transform: uppercase;
    line-height: 1.2; padding: 8px 14px; border-radius: 3px; cursor: pointer;
    border: 1px solid var(--accent); color: var(--accent); background: transparent;
  }
  .open:hover:not(:disabled), .why:hover { background: var(--accent); color: var(--bg); }
  .open.ghost { border-style: dashed; border-color: var(--line); color: var(--muted); }
  .open.ghost:hover { background: transparent; border-color: var(--accent); color: var(--accent); }
  .open:disabled { cursor: progress; opacity: 0.7; }
  .open:focus-visible, .why:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }

  .panel { margin-top: 22px; border-top: 1px solid var(--line); padding-top: 20px; }
  .prose p, .rationale, .risks p, .profile p { font-size: 15px; line-height: 1.65; color: var(--body); margin: 0 0 12px; }
  .note { margin: 8px 0 0; font-size: 13px; line-height: 1.55; color: var(--muted); }
  h3 {
    font-family: var(--mono); font-size: 10.5px; font-weight: 600; letter-spacing: 0.16em;
    text-transform: uppercase; color: var(--muted); margin: 0 0 8px;
  }
  .label {
    font-family: var(--mono); font-size: 10.5px; letter-spacing: 0.16em;
    text-transform: uppercase; color: var(--muted);
  }

  .card { margin-top: 18px; background: var(--panel-2); border: 1px solid var(--line); border-radius: 6px; padding: 18px; }
  .call {
    margin: 6px 0 4px; font-family: var(--display); font-weight: 800; font-size: 24px;
    text-transform: uppercase; color: #fff;
  }
  .claim { color: var(--accent); margin-left: 6px; }
  .means { margin: 0 0 10px; font-size: 14px; color: var(--body); }
  .why { margin-top: 4px; }
  .evidence { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 16px; margin-top: 16px; }

  ul { list-style: none; margin: 0; padding: 0; }
  .evidence li, .facts li {
    display: flex; justify-content: space-between; gap: 12px; padding: 7px 0;
    border-bottom: 1px solid var(--line-2); font-size: 13.5px; color: var(--body);
  }
  .evidence b, .facts b { font-family: var(--mono); font-weight: 600; color: #fff; white-space: nowrap; }

  .cols { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 16px; margin-top: 18px; }

  .menu { margin-top: 22px; }
  table { width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 14px; }
  tr { border-bottom: 1px solid var(--line-2); }
  th, td {
    padding: 8px 6px; text-align: left; font-weight: 400; color: var(--body);
    font-family: inherit; text-transform: none; letter-spacing: normal;
  }
  td.p { font-family: var(--mono); color: #fff; text-align: right; white-space: nowrap; }
  td.n { font-family: var(--mono); font-size: 11px; color: var(--muted); text-align: right; }
  tr.called th, tr.called td { color: var(--accent); font-weight: 600; }

  .risks { margin-top: 22px; }
  .flags { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; }
  .flags li {
    font-family: var(--mono); font-size: 11px; color: var(--body); background: var(--panel-2);
    border: 1px solid var(--line); border-radius: 3px; padding: 4px 8px;
  }

  .profile { background: var(--panel-2); border: 1px solid var(--line); border-radius: 6px; padding: 16px; }
  .profilehead { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; margin-bottom: 8px; }
  .profilehead h3 { margin: 0; color: #fff; font-size: 12px; }
  .trend { font-family: var(--mono); font-size: 10.5px; text-transform: uppercase; letter-spacing: 0.08em; color: var(--muted); }
  .trend.improving { color: var(--good); }
  .trend.declining { color: var(--bad); }
  .points li { font-size: 13.5px; color: var(--body); padding: 3px 0 3px 18px; position: relative; }
  .points li::before { position: absolute; left: 0; font-family: var(--mono); }
  .plus li::before { content: '+'; color: var(--good); }
  .minus li::before { content: '−'; color: var(--bad); }

  .ai { margin: 22px 0 0; font-size: 12.5px; color: var(--muted); }

  @media (max-width: 560px) {
    .analysis { padding: 18px; }
    .open { width: 100%; }
    /* The market and its probability on one line, the rule's note under them:
       three columns do not fit a phone without cutting the note off. */
    tr { display: grid; grid-template-columns: minmax(0, 1fr) auto; }
    td.n { grid-column: 1 / -1; text-align: left; padding-top: 0; }
  }
</style>
