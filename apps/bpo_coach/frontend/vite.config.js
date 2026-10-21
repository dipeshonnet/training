import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath } from 'node:url'
export default defineConfig({
  plugins: [vue()],
  base: '/assets/bpo_coach/coach/',
  build: {
    outDir: '../bpo_coach/public/coach', emptyOutDir: true,
    rollupOptions: {
      input: fileURLToPath(new URL('./src/main.js', import.meta.url)),
      output: {entryFileNames: 'main.js', assetFileNames: '[name][extname]', chunkFileNames: '[name]-[hash].js'},
    },
  },
  test: {environment: 'jsdom', include: ['src/**/*.test.js']},
})
