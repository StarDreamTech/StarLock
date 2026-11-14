import { defineConfig } from 'vite'
import { fileURLToPath } from 'node:url'

export default defineConfig({
  publicDir: fileURLToPath(new URL('../../assets', import.meta.url)),
  root: fileURLToPath(new URL('.', import.meta.url)),
  cacheDir: fileURLToPath(new URL('../../node_modules/.vite-hosted', import.meta.url)),
  server: { proxy: { '/demo': 'http://127.0.0.1:8018' } },
  build: { outDir: fileURLToPath(new URL('../../dist/hosted-example', import.meta.url)), emptyOutDir: true },
})
