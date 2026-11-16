import { cp, copyFile, readFile, rm, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';

const destination = process.argv[2];
if (!destination) throw new Error('Provide the Pages demo directory as the first argument');
const target = resolve(destination);
// This directory contains only Vite output from the playground build.
await rm(`${target}/assets`, { recursive: true, force: true });
await cp(new URL('../dist/static-demo/', import.meta.url), target, { recursive: true });
await copyFile(new URL('../packages/browser/THIRD_PARTY_NOTICES.txt', import.meta.url), `${target}/THIRD_PARTY_NOTICES.txt`);
const theme = "<script>(function(){var k='sdt-theme',t;try{t=localStorage.getItem(k)}catch(e){}t=(t==='light'||t==='dark')?t:(matchMedia('(prefers-color-scheme:light)').matches?'light':'dark');document.documentElement.setAttribute('data-theme',t)})();</script>";
const page = `${target}/index.html`;
let html = await readFile(page, 'utf8');
html = html.replace('<head>', `<head>\n  ${theme}`)
  .replace('</head>', '  <script src="../../../js/analytics.js" defer></script>\n</head>');
await writeFile(page, html);
console.log(`Static playground exported to ${target}`);
