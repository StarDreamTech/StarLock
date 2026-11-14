import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath } from 'node:url'

const root = fileURLToPath(new URL('.', import.meta.url))
export default defineConfig({
  root, plugins: [vue()],
  cacheDir: fileURLToPath(new URL('../../node_modules/.vite-playground', import.meta.url)),
  resolve: { alias: {
    '@starlock/core': fileURLToPath(new URL('../../packages/core/src/index.ts', import.meta.url)),
    '@starlock/vue': fileURLToPath(new URL('../../packages/vue/src/index.ts', import.meta.url)),
    '@starlock/browser': fileURLToPath(new URL('../../packages/browser/src/loader.ts', import.meta.url)),
  } },
  publicDir: fileURLToPath(new URL('../../assets', import.meta.url)),
  server: { proxy: { '/sdk': 'http://127.0.0.1:8018', '/v1': 'http://127.0.0.1:8018', '/demo': 'http://127.0.0.1:8018', '/healthz': 'http://127.0.0.1:8018' } },
  build: { outDir: fileURLToPath(new URL('../../dist/playground', import.meta.url)), emptyOutDir: true },
})
