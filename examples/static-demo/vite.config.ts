import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath } from 'node:url'

export default defineConfig({
  root: fileURLToPath(new URL('.', import.meta.url)),
  base: './',
  plugins: [vue()],
  esbuild: { legalComments: 'inline' },
  resolve: { alias: { '@starlock/core': fileURLToPath(new URL('../../packages/core/src/index.ts', import.meta.url)) } },
  build: { outDir: fileURLToPath(new URL('../../dist/static-demo', import.meta.url)), emptyOutDir: true },
})
