<script>
  // A crest with its side's form trend pinned to the corner
  // (docs/ANALYSIS_PLAN.md section 8). Signed-in readers only: `entry` is
  // null until the page has fetched `/trends`, and for a side with too few
  // games, and then this is the crest alone. The mark sits over the crest's
  // corner rather than beside it, so its arrival moves nothing on the row.
  //
  // Hover (where there is hover) or tap opens a note with the figures and
  // the analysis's own word. The note is `position: fixed`, placed from the
  // mark, because the lists clip their rows (`overflow: hidden`). A click
  // here must not reach the row, which opens the call's drawer.
  import { trendText } from '$lib/analysis.js';
  import { trendLines } from '$lib/trend.js';

  let { entry, team, side, children } = $props();

  let mark = $state();
  let note = $state();
  let pinned = $state(false);
  let hovered = $state(false);
  let at = $state(null);
  const open = $derived(entry && (pinned || hovered) && at);

  const WIDTH = 236;
  function place() {
    const r = mark.getBoundingClientRect();
    const left = Math.min(Math.max(8, r.left + r.width / 2 - WIDTH / 2), window.innerWidth - WIDTH - 8);
    at = { top: r.bottom + 8, left };
  }
  function toggle(event) {
    event.stopPropagation();
    pinned = !pinned;
    if (pinned) place();
  }
  function enter() {
    if (!window.matchMedia('(hover: hover)').matches) return;
    place();
    hovered = true;
  }
  function onKey(event) {
    event.stopPropagation();
    if (event.key === 'Escape') pinned = false;
  }

  // A pinned note closes on a press elsewhere, and on scroll or resize,
  // which would leave a fixed note behind its mark.
  $effect(() => {
    if (!pinned) return;
    const away = (event) => {
      if (!mark.contains(event.target) && !note?.contains(event.target)) pinned = false;
    };
    const close = () => (pinned = false);
    window.addEventListener('pointerdown', away);
    window.addEventListener('scroll', close, { passive: true });
    window.addEventListener('resize', close);
    return () => {
      window.removeEventListener('pointerdown', away);
      window.removeEventListener('scroll', close);
      window.removeEventListener('resize', close);
    };
  });
</script>

<span class="wrap">
  {@render children()}
  {#if entry}
    <button
      type="button"
      class="mark {entry.trend} {side}"
      bind:this={mark}
      aria-label="{team} form: {trendText(entry.trend)}. Details"
      aria-expanded={!!open}
      onclick={toggle}
      onkeydown={onKey}
      onmouseenter={enter}
      onmouseleave={() => (hovered = false)}
    >
      <svg viewBox="0 0 12 12" aria-hidden="true"><path d="M2 6h7.5M6.5 3l3 3-3 3" /></svg>
    </button>
    {#if open}
      <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
      <!-- svelte-ignore a11y_click_events_have_key_events -->
      <span class="formnote" role="tooltip" bind:this={note} onclick={(e) => e.stopPropagation()} style="top: {at.top}px; left: {at.left}px; width: {WIDTH}px">
        {#each trendLines(entry) as line, i}
          <span class="line" class:head={i === 0}>{line}</span>
        {/each}
      </span>
    {/if}
  {/if}
</span>

<style>
  .wrap { position: relative; display: inline-flex; flex: none; }
  .mark {
    position: absolute; bottom: -5px; width: 18px; height: 18px; padding: 0;
    display: inline-flex; align-items: center; justify-content: center;
    border-radius: 50%; border: 2px solid var(--panel); background: #3a3a44;
    color: #fff; cursor: pointer;
  }
  /* Toward the club's name: the home crest sits right of it, the away left. */
  .mark.home { left: -6px; }
  .mark.away { right: -6px; }
  /* A finger-sized target around an 18px mark. */
  .mark::before { content: ''; position: absolute; inset: -8px; }
  .mark.improving { background: var(--good); }
  .mark.declining { background: var(--bad); }
  .mark svg { width: 10px; height: 10px; fill: none; stroke: currentColor; stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round; }
  .mark.improving svg { transform: rotate(-45deg); }
  .mark.declining svg { transform: rotate(45deg); }
  .mark:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
  .formnote {
    position: fixed; z-index: 40; display: flex; flex-direction: column; gap: 3px;
    padding: 10px 12px; border-radius: 4px; background: var(--panel-2);
    border: 1px solid var(--line); box-shadow: 0 6px 20px rgba(0, 0, 0, 0.45);
    font-size: 12.5px; line-height: 1.4; color: var(--body); text-align: left;
    white-space: normal; cursor: default;
  }
  .line.head {
    font-family: var(--mono); font-size: 10.5px; letter-spacing: 0.08em;
    text-transform: uppercase; color: var(--text);
  }
</style>
