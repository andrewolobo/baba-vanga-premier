<script>
  // The tags that name one page (docs/SEO_PLAN.md 2.1, review R2): every
  // public page renders this exactly once, and nothing else sets them --
  // app.html carries only what is identical on every page. Server-rendered,
  // so link previewers see each page's own title and URL; on a client-side
  // move Svelte swaps them with the page, so there is never a second set.
  //
  // `path` is the page's canonical path, not the address it was reached by:
  // /?owner=1 is /.
  import { ORIGIN, DESCRIPTION } from '$lib/site.js';

  let { title, path, description = DESCRIPTION } = $props();
</script>

<svelte:head>
  <title>{title}</title>
  <meta name="description" content={description} />
  <link rel="canonical" href="{ORIGIN}{path}" />
  <meta property="og:title" content={title} />
  <meta property="og:description" content={description} />
  <meta property="og:url" content="{ORIGIN}{path}" />
</svelte:head>
