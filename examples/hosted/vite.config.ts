import { defineConfig } from 'vite'
import { fileURLToPath } from 'node:url'

export default defineConfig({
  publicDir: fileURLToPath(new URL('../../assets', import.meta.url)),
  root: fileURLToPath(new URL('.', import.meta.url)),
  cacheDir: fileURLToPath(new URL('../../node_modules/.vite-hosted', import.meta.url)),
  resolve: { alias: {
    '@starlock/core': fileURLToPath(new URL('../../packages/core/src/index.ts', import.meta.url)),
    '@starlock/browser': fileURLToPath(new URL('../../packages/browser/src/loader.ts', import.meta.url)),
    '@starlock/react': fileURLToPath(new URL('../../packages/react/src/index.ts', import.meta.url)),
  } },
  esbuild: { jsx: 'automatic' },
  plugins: [{
    name: 'react-client-demo',
    apply: 'build',
    transform(code, id) {
      if (!id.includes('/packages/react/src/')) return
      // This SPA has no server boundary; preserve the directive in the package source.
      return code.replace(/^['"]use client['"]/, '')
    },
  }],
  server: { proxy: { '/demo': 'http://127.0.0.1:8018' } },
  build: {
    outDir: fileURLToPath(new URL('../../dist/hosted-example', import.meta.url)),
    emptyOutDir: true,
    rollupOptions: {
      input: {
        hosted: fileURLToPath(new URL('./index.html', import.meta.url)),
        react: fileURLToPath(new URL('./react.html', import.meta.url)),
      },
    },
  },
})
