<script>
  // A fixture's form and last meetings, in place (B27): the sheet the front
  // page's calls and /parlay's legs open with `$lib/FactsButton.svelte`.
  // The content is the match page's own (`$lib/MatchFacts.svelte`, from
  // `GET /fixture/{id}`), so the two can never tell a reader different things.
  //
  // Open is a history entry, not a flag: the button pushes `facts` onto the
  // page's state and this renders while it is there. Every way of closing --
  // the ×, the dimmed page, Esc, a phone's back button -- is therefore one
  // step back, and the page underneath is never reloaded.
  //
  // Browser-only by construction: `page.state` is empty on the server, so
  // nothing here is in the HTML. The button's link to the match page is.
  //
  // A native <dialog> opened modal: it takes the top layer, so no z-index
  // contest with the sticky header, the bottom bar or the nudge, and it makes
  // the page behind it inert, which is the focus trap.
  import { untrack } from 'svelte';
  import { page } from '$app/stores';
  import { getFixture } from '$lib/api.js';
  import { fixtureBadges } from '$lib/badge.js';
  import Crest from '$lib/Crest.svelte';
  import MatchFacts from '$lib/MatchFacts.svelte';
  import { localKickoff, viewerZone } from '$lib/kickoff.js';
  import { matchPath, shortDay, divisionName } from '$lib/match.js';

  const row = $derived($page.state.facts ?? null);
  const badge = $derived(row && fixtureBadges(row.home_team, row.away_team));
  const kick = $derived(row && localKickoff(row.match_date, row.kickoff_time, viewerZone()));

  // Each fixture is read once while the page is open and kept by id, so a
  // slow answer for one fixture can never land in another's sheet. A failed
  // read is not kept: the next open, or "Try again", reads it afresh.
  let loaded = $state({});
  function read(id) {
    loaded[id] = { pending: true };
    getFixture(id).then(
      (fx) => (loaded[id] = { fx }),
      (e) => (loaded[id] = { error: e.message })
    );
  }
  $effect(() => {
    const id = row?.fixture_id;
    if (id == null) return;
    untrack(() => {
      if (!loaded[id] || loaded[id].error) read(id);
    });
  });
  const entry = $derived(row ? loaded[row.fixture_id] : null);

  let dialog = $state(null);
  $effect(() => {
    if (!dialog) return;
    const opener = document.activeElement;
    dialog.showModal();
    return () => opener?.focus?.();
  });

  const close = () => history.back();
  // Esc closes a modal dialog natively; this puts the history in step. The
  // ×, the backdrop and a back press arrive with the state already gone.
  const closed = () => $page.state.facts && close();
</script>

{#if row}
  <!-- The dialog fills its box with the panel, so a click whose target is
       the dialog itself landed on the dimmed page around it. Esc is the
       keyboard's way out, and the dialog handles it natively. -->
  <!-- svelte-ignore a11y_click_events_have_key_events a11y_no_noninteractive_element_interactions -->
  <dialog
    class="sheet"
    bind:this={dialog}
    aria-labelledby="facts-title"
    onclose={closed}
    onclick={(e) => e.target === dialog && close()}
  >
    <div class="panel">
      <header class="top">
        <div class="kicker">Form &amp; head to head · {divisionName(row.division)}</div>
        <h2 id="facts-title">
          <span class="team"><Crest name={row.home_team} badge={badge.home} size={28} />{row.home_team}</span>
          <span class="vs">vs</span>
          <span class="team"><Crest name={row.away_team} badge={badge.away} size={28} />{row.away_team}</span>
        </h2>
        <p class="meta">
          {shortDay(row.match_date)}
          {#if kick}
            · {kick.time}{#if kick.dayShift}<sup>{kick.dayShift > 0 ? '+1' : '−1'}</sup>{/if} your time
          {/if}
        </p>
        <button type="button" class="x" aria-label="Close" onclick={close}>×</button>
      </header>

      <div class="scroll">
        {#if entry?.fx}
          <MatchFacts fx={entry.fx} />
          <a class="full" href={matchPath(row)}>The full match page — our call, the venue and more →</a>
        {:else if entry?.error}
          <div class="state bad">
            <p>The form and meetings could not be loaded ({entry.error}).</p>
            <button type="button" class="retry" onclick={() => read(row.fixture_id)}>Try again</button>
          </div>
        {:else}
          <p class="state">Loading form and meetings…</p>
        {/if}
      </div>
    </div>
  </dialog>
{/if}

<style>
  /* Scroll stays with the sheet: the page behind it holds still. No
     `scrollbar-gutter` -- a reserved gutter narrows the box the dialog is
     laid out in, and left a strip of page down the sheet's right edge. */
  :global(html:has(dialog.sheet[open])) { overflow: hidden; }

  /* Desktop: a panel down the right-hand edge, wide enough for the two form
     cards side by side, as on the match page. */
  .sheet {
    margin: 0 0 0 auto; padding: 0; border: 0; border-left: 1px solid var(--line);
    width: min(760px, 100%); max-width: 100%; height: 100dvh; max-height: 100dvh;
    background: var(--bg); color: var(--body);
    animation: sheet-in 0.22s ease-out;
  }
  .sheet::backdrop { background: rgba(0, 0, 0, 0.6); animation: sheet-fade 0.2s ease-out; }
  .sheet:focus { outline: none; }
  .panel { height: 100%; display: flex; flex-direction: column; }

  .top {
    flex: none; position: relative; padding: 20px 64px 16px 28px;
    border-bottom: 1px solid var(--line); background: var(--panel);
  }
  .kicker {
    font-family: var(--mono); font-size: 11px; letter-spacing: 0.22em;
    text-transform: uppercase; color: var(--accent);
  }
  h2 {
    font-family: var(--display); font-weight: 800; font-size: 26px; line-height: 1.1;
    text-transform: uppercase; color: #fff; margin: 10px 0 0;
    display: flex; flex-wrap: wrap; align-items: center; gap: 4px 12px;
  }
  .team { display: inline-flex; align-items: center; gap: 10px; }
  .vs { font-size: 0.6em; color: var(--muted); }
  .meta { margin: 8px 0 0; font-family: var(--mono); font-size: 12px; color: var(--muted); }
  .meta sup { font-size: 10px; margin-left: 2px; }
  .x {
    position: absolute; top: 14px; right: 16px; width: 40px; height: 40px;
    display: grid; place-items: center; font-size: 26px; line-height: 1;
    border: 1px solid var(--line); border-radius: 4px; background: transparent;
    color: var(--body); cursor: pointer;
  }
  .x:hover { border-color: var(--accent); color: var(--accent); }
  .x:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }

  .scroll { flex: 1; overflow-y: auto; overscroll-behavior: contain; padding: 0 28px 36px; }
  .full {
    display: inline-block; margin-top: 32px; font-family: var(--mono); font-size: 11px;
    letter-spacing: 0.08em; text-transform: uppercase; color: var(--accent);
  }
  .full:hover { color: var(--accent-soft); }

  .state { margin: 28px 0 0; color: var(--muted); }
  .state p { margin: 0; }
  .state.bad p { color: var(--bad); }
  .retry {
    margin-top: 12px; font-family: var(--mono); font-size: 11px; letter-spacing: 0.08em;
    text-transform: uppercase; padding: 6px 12px; border-radius: 3px; cursor: pointer;
    border: 1px solid var(--line); background: transparent; color: var(--body);
  }
  .retry:hover { border-color: var(--accent); color: var(--accent); }

  @keyframes sheet-in { from { transform: translateX(40px); opacity: 0; } }
  @keyframes sheet-fade { from { opacity: 0; } }
  @keyframes sheet-up { from { transform: translateY(32px); opacity: 0; } }

  /* Phones: the whole screen, over the bottom bar, rising from the foot. */
  @media (max-width: 820px) {
    .sheet { width: 100%; border-left: 0; animation-name: sheet-up; }
    .top { padding: 16px 60px 14px 18px; }
    h2 { font-size: 22px; }
    .scroll { padding: 0 18px 32px; }
  }
  @media (prefers-reduced-motion: reduce) {
    .sheet, .sheet::backdrop { animation: none; }
  }
</style>
