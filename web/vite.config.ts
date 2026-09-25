import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// The dashboard talks to the backend on port 8000. In dev we proxy, so the
// browser only ever sees one origin and there is no CORS to think about.
export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/api': { target: process.env.VITE_API_BASE ?? 'http://localhost:8000', changeOrigin: true },
      '/track': { target: process.env.VITE_API_BASE ?? 'http://localhost:8000', changeOrigin: true },
      '/ws': { target: process.env.VITE_API_BASE ?? 'http://localhost:8000', ws: true },
    },
  },
})
