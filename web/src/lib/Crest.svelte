<script>
  // A club's crest, with the generated badge behind it.
  //
  // `$lib/badge.js` draws initials on a colour from the canonical name alone,
  // which is all the schema carried before real crests existed. It stays as
  // the fallback for the handful of clubs football-logos.cc publishes no crest
  // for, and for a file that fails to load -- the alternative, an empty gap
  // where a crest should be, reads as a broken page.
  //
  // The club's full name is rendered beside every crest at all three call
  // sites, so the image is decorative and takes an empty alt: announcing
  // "Arsenal" twice is worse for a screen reader than not announcing it.
  import { crestFile } from '$lib/crests.js';

  let { name, badge, size = 34 } = $props();

  const file = $derived(crestFile(name));

  // A crest that 404s (a club promoted since the last fetch run) falls back
  // rather than showing a broken image.
  let broken = $state(false);
</script>

{#if file && !broken}
  <!-- Twice the drawn size or more, for retina: the 64px file up to 32px,
       the 128px one above (the 40px page headings). -->
  <img
    class="crest"
    src="/crests/{size > 32 ? 128 : 64}/{file}.png"
    alt=""
    width={size}
    height={size}
    loading="lazy"
    decoding="async"
    style="--crest-size: {size}px"
    onerror={() => (broken = true)}
  />
{:else}
  <span class="crest fallback" style="--crest-size: {size}px; background: {badge.colour}"
    >{badge.code}</span
  >
{/if}

<style>
  .crest {
    flex: none;
    width: var(--crest-size);
    height: var(--crest-size);
    object-fit: contain;
  }
  .fallback {
    border-radius: 50%;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-family: var(--display);
    font-weight: 800;
    /* 13px at the default 34, and scaled with it so three letters still fit
       the 18px crests in a form guide. */
    font-size: calc(var(--crest-size) * 0.38);
    letter-spacing: 0.03em;
    color: #fff;
  }
</style>
