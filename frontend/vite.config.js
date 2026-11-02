import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// In dev the API runs on :8000; proxying keeps everything same-origin (no CORS, ws works).
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': { target: 'http://localhost:8000', ws: true, changeOrigin: true },
    },
  },
  build: { chunkSizeWarningLimit: 900 },
})
