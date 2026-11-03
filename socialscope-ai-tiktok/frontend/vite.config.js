import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// In development, /api requests are proxied to the Flask backend, so no CORS setup is needed.
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: { '/api': 'http://127.0.0.1:5000' } },
  preview: { port: 4173, proxy: { '/api': 'http://127.0.0.1:5000' } },
  build: { chunkSizeWarningLimit: 800 }, // Recharts is the bulk of the bundle
});
