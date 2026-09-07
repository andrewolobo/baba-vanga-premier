<script>
  import { page } from '$app/stores';
  import { onMount } from 'svelte';
  import {
    getAuthConfig,
    getMe,
    signInWithGoogle,
    savePhone,
    signOut,
    phoneRequired,
    firstName,
    plausiblePhone
  } from '$lib/session.js';
  import { detectCountry } from '$lib/country.js';
  let { children } = $props();

  // Sign-in (docs/AUTH_PLAN.md, B25). The layout owns the session state
  // because the control lives in the header and the phone gate covers every
  // route; nothing below it needs `me` yet (AUTH_PLAN.md §10 says when it
  // moves to a shared module). The server is the only authority: `getMe`
  // asks it on every load and the cookie is HttpOnly, so nothing here can
  // decide anyone is signed in.
  let me = $state(null);
  let authReady = $state(false);
  let cfg = $state(null);
  let authError = $state(null);
  let buttonHost = $state(null);

  // The one-time phone step (D5, D6).
  let phone = $state('');
  let country = $state('GB');
  let phoneError = $state(null);
  let saving = $state(false);

  const regionName = (() => {
    try {
      const names = new Intl.DisplayNames(['en'], { type: 'region' });
      return (code) => names.of(code) ?? code;
    } catch {
      return (code) => code;
    }
  })();
  const regionOptions = $derived(
    (cfg?.regions ?? [])
      .map((r) => ({ ...r, name: regionName(r.code) }))
      .sort((a, b) => a.name.localeCompare(b.name))
  );

  onMount(async () => {
    try {
      cfg = await getAuthConfig();
      me = await getMe();
      country = detectCountry(
        Intl.DateTimeFormat().resolvedOptions().timeZone,
        navigator.language,
        new Set(cfg.regions.map((r) => r.code))
      );
    } catch (e) {
      authError = e.message;
    }
    authReady = true;
  });

  // Google's script loads async and its button is an iframe it draws into a
  // host element, so render once both exist; the host is conditional on
  // being signed out, so a sign-out re-mounts it and this runs again.
  $effect(() => {
    const host = buttonHost;
    const clientId = cfg?.google_client_id;
    if (!host || !clientId || me) return;
    let tries = 0;
    let cancelled = false;
    const tick = () => {
      if (cancelled) return;
      const gsi = window.google?.accounts?.id;
      if (gsi) {
        gsi.initialize({
          client_id: clientId,
          callback: ({ credential }) => onCredential(credential),
          ux_mode: 'popup'
        });
        gsi.renderButton(host, { theme: 'filled_black', size: 'medium', shape: 'pill', text: 'signin_with' });
      } else if (tries++ < 50) {
        setTimeout(tick, 100);
      }
    };
    tick();
    return () => {
      cancelled = true;
    };
  });

  async function onCredential(credential) {
    authError = null;
    try {
      me = await signInWithGoogle(credential);
    } catch {
      authError = 'Sign-in did not go through. Try again.';
    }
  }

  async function doSignOut() {
    try {
      await signOut();
    } catch {
      // The cookie is cleared server-side on success; on failure the next
      // load asks /me again, which is the truth either way.
    }
    me = null;
    phone = '';
    phoneError = null;
  }

  async function savePhoneNow(event) {
    event.preventDefault();
    saving = true;
    phoneError = null;
    try {
      me = await savePhone(phone, country);
    } catch (e) {
      if (e.status === 409 && !/another account/.test(e.detail ?? '')) {
        me = await getMe(); // already captured elsewhere: the gate closes itself
      } else {
        phoneError = e.detail ?? 'That number could not be saved. Try again.';
      }
    } finally {
      saving = false;
    }
  }

  // The public site is one page with three sections, plus /parlay (B24). /book
  // and /performance are the internal views that existed before it and are
  // reached from the footer; they are named here rather than inferred from
  // "not the front page", so a new public route does not inherit the
  // uncalibrated-pmf banner and the narrow shell by default.
  const sections = [
    ['tips', 'Tips'],
    ['results', 'Results'],
    ['record', 'Record']
  ];

  // Bottom-bar icons (owner request 2026-09-07): stroke paths on a 24px
  // grid, drawn inline so there is no icon dependency and `currentColor`
  // lets the active state colour icon and label together. Compound paths
  // (several M commands in one `d`) keep each icon a single element.
  const icons = {
    tips: 'M11 5 6 9H3v6h3l5 4V5z M15.5 8.5a5 5 0 0 1 0 7', // a call, spoken
    results: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z m-3.8 9.2 2.6 2.6 5-5.6', // graded
    record: 'M5 20v-4 M12 20v-9 M19 20V6', // the strike-rate chart
    parlay: 'M12 3 3 7.5l9 4.5 9-4.5z m-9 9 9 4.5 9-4.5 M3 16.5 12 21l9-4.5' // stacked legs
  };

  const internal = $derived(['/book', '/performance'].includes($page.url.pathname));
</script>

<header>
  <div class="bar">
    <a href="/" class="wordmark"><span>Baba</span><span class="accent">Vanga</span></a>

    <nav>
      {#each sections as [id, label]}
        <a href="/#{id}">{label}</a>
      {/each}
    </nav>

    <!-- Two actions, side by side: the parlay page (solid accent orange so it
         stands out in its own right -- owner decision 2026-09-01, ahead of
         the B24 probe, PARLAY_PLAN.md D7) and sign-in. The "This week's
         calls" CTA that used to sit between them was removed at the owner's
         request on 2026-09-07: the calls are the front page, which the
         wordmark and the Tips link already reach. -->
    <div class="actions">
      <a href="/parlay" class="cta parlay" aria-current={$page.url.pathname === '/parlay' ? 'page' : undefined}>Build a parlay</a>
      <!-- Sign-in (AUTH_PLAN.md). Nothing renders until the server has said
           who this is and whether sign-in is configured at all: an empty
           client id means the site behaves exactly as it did before B25. -->
      {#if authReady && cfg?.google_client_id}
        {#if me}
          <div class="who">
            {#if me.picture_url}
              <img class="avatar" src={me.picture_url} alt="" referrerpolicy="no-referrer" />
            {/if}
            <span class="name">{firstName(me)}</span>
            <button type="button" class="link" onclick={doSignOut}>Sign out</button>
          </div>
        {:else}
          <div class="gsi" bind:this={buttonHost}></div>
        {/if}
      {/if}
    </div>
  </div>
  {#if authError}
    <p class="auth-error">{authError}</p>
  {/if}
</header>

<!-- The one-time phone step (AUTH_PLAN.md D5): a signed-in account without a
     number sees this over every route until it saves one. The server writes
     it once and refuses a second; this form only asks. -->
{#if phoneRequired(me) && cfg}
  <div class="veil" role="dialog" aria-modal="true" aria-labelledby="phone-title">
    <form class="phone" onsubmit={savePhoneNow}>
      <p class="eyebrow">One more thing</p>
      <h2 id="phone-title">Your mobile number</h2>
      <p class="copy">
        We ask once. It is kept with your account, shown nowhere on the site, and
        is the number we would reach you on.
      </p>
      <label>
        <span>Country</span>
        <select bind:value={country}>
          {#each regionOptions as r (r.code)}
            <option value={r.code}>{r.name} (+{r.dial})</option>
          {/each}
        </select>
      </label>
      <label>
        <span>Mobile number</span>
        <input type="tel" inputmode="tel" autocomplete="tel" bind:value={phone} />
      </label>
      {#if phoneError}
        <p class="bad">{phoneError}</p>
      {/if}
      <div class="row">
        <button type="submit" class="cta" disabled={!plausiblePhone(phone) || saving}>
          {saving ? 'Saving…' : 'Save number'}
        </button>
        <button type="button" class="link" onclick={doSignOut}>Sign out instead</button>
      </div>
    </form>
  </div>
{/if}

{#if internal}
  <div class="shell">
    <p class="banner">
      Internal view. Probabilities are <strong>uncalibrated</strong> — raw Poisson pmf
      output from the P1 base head. The paper book is switched off
      (<code>CALIBRATION.md</code> §5); nothing here stakes money.
    </p>
    {@render children()}
  </div>
{:else}
  {@render children()}
{/if}

<!-- On phones the header's links live down here instead (owner request,
     2026-09-07): a fixed bottom bar, the pattern the PWA install implies.
     The CTAs and sign-in stay in the header. CSS swaps the two navs at the
     existing 820px breakpoint; the section links highlight on tap (hash),
     the parlay link by route, same as the header CTA. -->
<nav class="bottom-nav" aria-label="Sections">
  {#each sections as [id, label]}
    <a
      href="/#{id}"
      aria-current={$page.url.pathname === '/' && $page.url.hash === `#${id}` ? 'page' : undefined}
    >
      <svg viewBox="0 0 24 24" aria-hidden="true"><path d={icons[id]} /></svg>
      <span>{label}</span>
    </a>
  {/each}
  <a href="/parlay" aria-current={$page.url.pathname === '/parlay' ? 'page' : undefined}>
    <svg viewBox="0 0 24 24" aria-hidden="true"><path d={icons.parlay} /></svg>
    <span>Parlay</span>
  </a>
</nav>

<footer>
  <div class="bar">
    <div>
      <div class="wordmark"><span>Baba</span><span class="accent">Vanga</span></div>
      <p class="claim">
        Every call is published before kick-off and graded afterwards. <strong>Strike
        rate is how often the call is right — it is not a return, and we do not
        publish one.</strong>
      </p>
    </div>
    <div class="small">
      <p>18+. Predictions are opinion, not certainty. Please gamble responsibly —
        <a href="https://www.begambleaware.org" rel="noreferrer noopener" target="_blank"
          >begambleaware.org</a
        ></p>
      <!-- /book and /performance are internal views: uncalibrated pmf output
           and a paper book that is switched off. They stay routable for the
           operator but are not linked from the public page. -->
    </div>
  </div>
</footer>

<style>
  /* The design's tokens. The four names the internal pages already use --
     panel, line, text, muted, accent, good, bad -- are kept and remapped rather
     than renamed, so /book and /performance restyle themselves for free. */
  :global(:root) {
    --bg: #0e0e11;
    --panel: #151519;
    --panel-2: #1d1d23;
    --line: #26262c;
    --line-2: #212127;
    --text: #efefef;
    --body: #c4c4cd;
    --muted: #8a8a94;
    --dim: #75757f;
    --accent: #ff6b1a;
    --accent-soft: #ff8c4d;
    --cta: #e4384f;
    --good: #2fb56b;
    --bad: #e4384f;
    --display: 'Barlow Condensed', 'Arial Narrow', system-ui, sans-serif;
    --sans: 'Barlow', system-ui, -apple-system, 'Segoe UI', sans-serif;
    --mono: 'IBM Plex Mono', ui-monospace, 'Cascadia Mono', monospace;
    --page: 1240px;
  }
  :global(*) { box-sizing: border-box; }
  :global(body) {
    margin: 0;
    background: var(--bg);
    color: var(--text);
    font: 15px/1.5 var(--sans);
    -webkit-font-smoothing: antialiased;
    overflow-x: hidden;
  }
  :global(a) { color: var(--accent); text-decoration: none; }
  :global(a:hover) { color: var(--accent-soft); }
  :global(::selection) { background: var(--accent); color: #fff; }

  :global(table) { border-collapse: collapse; width: 100%; }
  :global(th), :global(td) {
    padding: 0.55rem 0.7rem;
    border-bottom: 1px solid var(--line);
    text-align: left;
    white-space: nowrap;
  }
  :global(th) {
    color: var(--muted); font-weight: 600; font-size: 0.82rem;
    text-transform: uppercase; letter-spacing: 0.04em; font-family: var(--mono);
  }
  :global(td.num), :global(th.num) { text-align: right; font-variant-numeric: tabular-nums; }

  .bar {
    max-width: var(--page);
    margin: 0 auto;
    padding: 0 32px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 32px;
  }

  header {
    position: sticky; top: 0; z-index: 40;
    background: rgba(14, 14, 17, 0.92);
    backdrop-filter: blur(10px);
    border-bottom: 1px solid var(--line);
  }
  header .bar { height: 72px; }

  .wordmark {
    display: flex; align-items: baseline; gap: 10px;
    font-family: var(--display); font-weight: 800; font-size: 28px;
    letter-spacing: 0.04em; text-transform: uppercase; color: var(--text);
  }
  .wordmark .accent { color: var(--accent); }

  nav { display: flex; align-items: center; gap: 30px; }
  nav a {
    font-family: var(--display); font-weight: 600; font-size: 17px;
    letter-spacing: 0.08em; text-transform: uppercase; color: var(--muted);
  }
  nav a:hover { color: var(--text); }

  .cta {
    background: var(--cta); color: #fff; font-family: var(--display);
    font-weight: 700; font-size: 15px; letter-spacing: 0.1em;
    text-transform: uppercase; padding: 11px 22px; border-radius: 3px;
    white-space: nowrap;
  }
  .cta:hover { color: #fff; filter: brightness(1.1); }
  .actions { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; justify-content: flex-end; }
  .cta.parlay { background: var(--accent); color: var(--bg); }
  .cta.parlay:hover { color: var(--bg); }
  /* On its own page the button is the one place the accent reads as "you
     are here" rather than "go here", so it settles to the softer shade. */
  .cta.parlay[aria-current="page"] { background: var(--accent-soft); }
  .cta:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
  .cta:disabled { opacity: 0.45; cursor: not-allowed; filter: none; }

  /* --- sign-in (AUTH_PLAN.md) --------------------------------------------- */
  /* Google draws its own button into .gsi; the height keeps the header from
     jumping while the script loads. */
  .gsi { min-height: 40px; display: flex; align-items: center; }
  .who { display: flex; align-items: center; gap: 10px; }
  .avatar { width: 30px; height: 30px; border-radius: 50%; border: 1px solid var(--line); }
  .name {
    font-family: var(--display); font-weight: 600; font-size: 17px;
    letter-spacing: 0.06em; text-transform: uppercase; color: var(--text);
  }
  .link {
    background: none; border: 0; padding: 0; cursor: pointer;
    font-family: var(--mono); font-size: 12px; letter-spacing: 0.06em;
    text-transform: uppercase; color: var(--muted);
  }
  .link:hover { color: var(--accent-soft); }
  .link:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
  .auth-error {
    max-width: var(--page); margin: 0 auto; padding: 0 32px 10px;
    font-family: var(--mono); font-size: 12px; color: var(--bad);
  }

  .veil {
    position: fixed; inset: 0; z-index: 50;
    background: rgba(14, 14, 17, 0.85);
    display: flex; align-items: center; justify-content: center; padding: 18px;
  }
  .phone {
    width: min(460px, 100%);
    background: var(--panel); border: 1px solid var(--line);
    border-left: 3px solid var(--accent); border-radius: 5px; padding: 26px 28px;
  }
  .eyebrow {
    font-family: var(--mono); font-size: 10px; letter-spacing: 0.2em;
    text-transform: uppercase; color: var(--dim); margin: 0 0 6px;
  }
  .phone h2 {
    font-family: var(--display); font-weight: 700; font-size: 28px;
    text-transform: uppercase; color: #fff; margin: 0 0 10px;
  }
  .copy { font-size: 14px; line-height: 1.6; color: var(--body); margin: 0 0 18px; }
  .phone label { display: block; margin-bottom: 14px; }
  .phone label span {
    display: block; font-family: var(--mono); font-size: 10px; letter-spacing: 0.2em;
    text-transform: uppercase; color: var(--dim); margin-bottom: 6px;
  }
  .phone select, .phone input {
    width: 100%; padding: 10px 12px; border-radius: 3px;
    background: var(--panel-2); border: 1px solid var(--line); color: var(--text);
    font: 15px/1.4 var(--sans);
  }
  .phone input { font-family: var(--mono); letter-spacing: 0.04em; }
  .phone select:focus-visible, .phone input:focus-visible {
    outline: 2px solid var(--accent); outline-offset: 1px;
  }
  .bad { color: var(--bad); font-size: 14px; margin: -4px 0 12px; }
  .row { display: flex; align-items: center; gap: 18px; flex-wrap: wrap; margin-top: 6px; }
  .phone .cta { border: 0; cursor: pointer; }

  footer { border-top: 1px solid var(--line); background: #0b0b0e; margin-top: 90px; }
  footer .bar { padding: 40px 32px; align-items: flex-start; flex-wrap: wrap; }
  footer .wordmark { font-size: 22px; }
  .claim { max-width: 52ch; font-size: 14px; color: var(--muted); margin: 14px 0 0; }
  .claim strong { color: var(--body); font-weight: 600; }
  .small { font-family: var(--mono); font-size: 11px; color: #6c6c76; max-width: 44ch; }
  .small p { margin: 0 0 10px; }
  .links a { color: var(--muted); }

  /* Internal views keep the narrower measure they were designed for. */
  .shell { max-width: 1180px; margin: 0 auto; padding: 1.5rem 1.25rem 2rem; }
  .banner {
    margin: 1rem 0 1.5rem; padding: 0.6rem 0.8rem; font-size: 0.85rem;
    color: var(--muted); background: var(--panel);
    border: 1px solid var(--line); border-left: 3px solid var(--accent);
    border-radius: 4px;
  }
  .banner code { background: var(--panel-2); padding: 0.1rem 0.35rem; border-radius: 3px; }

  /* Mobile bottom navigation. Nothing on desktop; below 820px it replaces
     the header nav's old third row. Fixed over the page, so the body gains
     matching bottom padding at the same breakpoint or the footer would end
     behind it. The phone-gate veil (z 50) still covers it. */
  .bottom-nav { display: none; }

  @media (max-width: 820px) {
    .bar { padding: 0 18px; gap: 16px; }
    header .bar { height: auto; padding-top: 12px; padding-bottom: 12px; flex-wrap: wrap; }
    header nav { display: none; } /* moved to .bottom-nav */
    .cta { padding: 9px 16px; font-size: 13px; }

    .bottom-nav {
      display: flex; gap: 0;
      position: fixed; left: 0; right: 0; bottom: 0; z-index: 40;
      background: rgba(14, 14, 17, 0.92);
      backdrop-filter: blur(10px);
      border-top: 1px solid var(--line);
      /* iOS home indicator; 0 wherever there is no inset. */
      padding-bottom: env(safe-area-inset-bottom);
    }
    .bottom-nav a {
      flex: 1;
      display: flex; flex-direction: column; align-items: center; gap: 5px;
      padding: 13px 0;
      /* The label under the icon takes the house small-label style
         (.link/.eyebrow), not the header nav's display face. */
      font-family: var(--mono); font-size: 10px; line-height: 1;
      letter-spacing: 0.14em;
    }
    .bottom-nav svg {
      width: 24px; height: 24px;
      fill: none; stroke: currentColor; stroke-width: 1.8;
      stroke-linecap: round; stroke-linejoin: round;
    }
    .bottom-nav a[aria-current='page'] { color: var(--accent); }

    /* Bar = 13px x2 padding + 24px icon + 5px gap + 10px label + 1px border
       = 66px; a little slack so rounding never puts the footer's last line
       under the bar. */
    :global(body) { padding-bottom: calc(70px + env(safe-area-inset-bottom)); }
  }
</style>
