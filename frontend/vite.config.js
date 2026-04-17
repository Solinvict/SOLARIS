/* SPDX-License-Identifier: MPL-2.0 */

import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const apiTarget = process.env.SOLARIS_API_PROXY || 'http://127.0.0.1:8766'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: apiTarget,
        changeOrigin: true,
      },
      '/ws': {
        target: apiTarget,
        ws: true,
        changeOrigin: true,
      },
    },
  },
  test: {
    environment: 'jsdom',
  },
})
