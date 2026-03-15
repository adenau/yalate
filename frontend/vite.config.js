import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const frontendPort = Number(process.env.FRONTEND_PORT || 5173)
const backendHost = process.env.BACKEND_HOST || '127.0.0.1'
const backendPort = Number(process.env.BACKEND_PORT || process.env.PORT || 5001)

export default defineConfig({
  plugins: [react()],
  server: {
    port: frontendPort,
    proxy: {
      '/api': {
        target: `http://${backendHost}:${backendPort}`,
        changeOrigin: true
      }
    }
  }
})
