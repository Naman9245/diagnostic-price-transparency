import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  // A fixed port, so the README's links always work.
  server: { port: 5173, strictPort: true },
})
