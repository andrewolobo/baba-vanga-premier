import { sveltekit } from '@sveltejs/kit/vite';

export default {
  plugins: [sveltekit()],
  server: {
    port: 5173,
    // The API runs separately in development; proxying keeps the frontend
    // origin-relative so no base URL has to be configured per environment.
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/api/, '')
      }
    }
  }
};
