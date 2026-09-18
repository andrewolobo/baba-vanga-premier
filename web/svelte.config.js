import adapter from '@sveltejs/adapter-node';

// Server-side rendered by a Node process behind nginx (docs/SEO_PLAN.md 2.1,
// D1(a)): pages arrive with their content in the HTML, for crawlers and link
// previewers that never run JavaScript. `npm run build` writes the server to
// build/ and its static files to build/client/, which nginx serves directly.
export default {
  kit: {
    adapter: adapter()
  }
};
