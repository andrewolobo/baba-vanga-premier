<script>
  // The way into a fixture's form and last meetings from a list (B27): on the
  // front page's calls and on each /parlay leg.
  //
  // A link to the match page, so it is in the server's HTML (a crawl path to
  // every live fixture's page, which the drawer's link is not -- SEO_PLAN.md
  // 2.8) and a modified click opens the page in a new tab as any link does.
  // A plain click opens `$lib/FixtureSheet.svelte` in place instead, as a
  // history entry (`pushState`), so a phone's back button closes the sheet
  // rather than leaving the page -- and /parlay keeps the slip it was on.
  import { pushState } from '$app/navigation';
  import { matchPath, plainClick, factsState } from '$lib/match.js';

  let { row } = $props();

  // The front page's row is itself the control for its drawer: neither a
  // click here nor Enter on this link may reach it.
  const keep = (event) => event.stopPropagation();

  function open(event) {
    keep(event);
    if (!plainClick(event)) return;
    event.preventDefault();
    pushState('', { facts: factsState(row) });
  }
</script>

<a class="facts" href={matchPath(row)} aria-haspopup="dialog" onclick={open} onkeydown={keep}>Form &amp; H2H</a>

<style>
  .facts {
    display: inline-block; margin-top: 8px; font-family: var(--mono); font-size: 10.5px;
    letter-spacing: 0.08em; text-transform: uppercase; text-decoration: none;
    line-height: 1.2; padding: 5px 10px; border-radius: 3px; white-space: nowrap;
    border: 1px solid var(--line); color: var(--body); background: transparent;
  }
  .facts:hover { border-color: var(--accent); color: var(--accent); }
  .facts:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
</style>
