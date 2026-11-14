import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath } from 'node:url'
import { readFileSync } from 'node:fs'

export default defineConfig({
  plugins: [vue()], publicDir: false,
  esbuild: { legalComments: 'inline' },
  resolve: { alias: { '@starlock/core': fileURLToPath(new URL('../core/src/index.ts', import.meta.url)) } },
  define: { 'process.env.NODE_ENV': JSON.stringify('production') },
  build: {
    outDir: fileURLToPath(new URL('../../dist/sdk/v1', import.meta.url)), emptyOutDir: true,
    lib: { entry: fileURLToPath(new URL('./src/index.ts', import.meta.url)), formats: ['iife'], name: 'StarLockBundle', fileName: () => 'api.js' },
    target: 'es2022',
    rollupOptions: { output: { banner: `/*!\n${readFileSync(new URL('./THIRD_PARTY_NOTICES.txt', import.meta.url), 'utf8')}\n*/` } },
  },
})
