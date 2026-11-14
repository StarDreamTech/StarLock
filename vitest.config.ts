import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath } from 'node:url'

export default defineConfig({
  publicDir: fileURLToPath(new URL('./assets', import.meta.url)),
  plugins: [vue()],
  test: { css: true },
  resolve: { alias: {
    '@starlock/core': fileURLToPath(new URL('./packages/core/src/index.ts', import.meta.url)),
    '@starlock/browser': fileURLToPath(new URL('./packages/browser/src/loader.ts', import.meta.url)),
  } },
})
