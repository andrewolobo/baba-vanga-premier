import { sveltekit } from '@sveltejs/kit/vite';

// scripts/dev.ps1 takes -ApiPort and passes it to uvicorn. This has to follow
// it: with the target hardcoded, running the API anywhere but 8000 left the
// frontend proxying to a dead port and every page reading as an empty week
// rather than as a misconfiguration.
const API = process.env.BVP_API_URL ?? `http://127.0.0.1:${process.env.BVP_API_PORT ?? 8000}`;

export default {
  plugins: [sveltekit()],
  server: {
    port: 5173,
    // The API runs separately in development; proxying keeps the frontend
    // origin-relative so no base URL has to be configured per environment.
    proxy: {
      '/api': {
        target: API,
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/api/, '')
      }
    }
  }
};
