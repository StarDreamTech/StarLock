import { readFile, writeFile, rm } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { createServer } from 'vite';
import { createSSRApp } from 'vue';
import { renderToString } from 'vue/server-renderer';

const root = fileURLToPath(new URL('../', import.meta.url));
const directory = `${root}dist/playground/`;
const publicAddress = process.env.STARLOCK_PUBLIC_URL;
let publicUrl;
if (publicAddress) {
  publicUrl = new URL(publicAddress);
  if (publicUrl.protocol !== 'https:' || publicUrl.pathname !== '/' || publicUrl.search || publicUrl.hash || publicUrl.username || publicUrl.password) {
    throw new Error('STARLOCK_PUBLIC_URL must be an HTTPS site root without credentials, query or fragment');
  }
}
const server = await createServer({
  configFile: `${root}examples/playground/vite.config.ts`,
  server: { middlewareMode: true }, appType: 'custom',
});
let body;
try {
  const { default: App } = await server.ssrLoadModule('/src/App.vue');
  body = await renderToString(createSSRApp(App));
} finally {
  await server.close();
}
let html = await readFile(`${directory}index.html`, 'utf8');
html = html.replace(/<!-- prerender:start -->[\s\S]*?<!-- prerender:end -->/g, '')
  .replace(/<!-- search:start -->[\s\S]*?<!-- search:end -->\n?/g, '')
  .replace(/<meta name="robots" content="[^"]+"\s*\/?>/, '<meta name="robots" content="noindex, follow" />');
if (!html.includes('<div id="app"></div>')) throw new Error('Homepage mount element changed');
html = html.replace('<div id="app"></div>', () => `<div id="app"><!-- prerender:start -->${body}<!-- prerender:end --></div>`);
const description = html.match(/<meta name="description" content="([^"]+)"/)[1];
const projectUrl = 'https://stardreamtech.github.io/projects/starlock/';
const data = {
  '@context': 'https://schema.org', '@type': 'SoftwareSourceCode',
  '@id': `${projectUrl}#software`, name: '星锁 StarLock', description,
  url: projectUrl, codeRepository: 'https://github.com/StarDreamTech/starlock',
  license: 'https://github.com/StarDreamTech/starlock/blob/main/LICENSE',
  programmingLanguage: ['TypeScript', 'Python'],
  author: { '@type': 'Organization', name: '星梦科技 StarDreamTech', url: 'https://stardreamtech.github.io/' },
};
const tags = [
  '<meta property="og:type" content="website">',
  '<meta property="og:locale" content="zh_CN">',
  '<meta property="og:site_name" content="星锁 StarLock">',
  '<meta property="og:title" content="星锁 StarLock · 开源验证码 SDK 与人机验证服务">',
  `<meta property="og:description" content="${description}">`,
  '<meta name="twitter:card" content="summary_large_image">',
  `<script type="application/ld+json">${JSON.stringify(data).replaceAll('<', '\\u003c')}</script>`,
];
if (publicUrl) {
  const url = publicUrl.href;
  html = html.replace('content="noindex, follow"', 'content="index, follow, max-image-preview:large"');
  tags.push(`<link rel="canonical" href="${url}">`, `<meta property="og:url" content="${url}">`,
    `<meta property="og:image" content="${url}brand/starlock-hero-v2.webp">`,
    '<meta property="og:image:alt" content="星锁紫色玻璃锁体与四角星锁孔">');
  await writeFile(`${directory}robots.txt`, `User-agent: *\nAllow: /\n\nSitemap: ${url}sitemap.xml\n`);
  await writeFile(`${directory}sitemap.xml`, `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>${url}</loc></url></urlset>\n`);
} else {
  await writeFile(`${directory}robots.txt`, 'User-agent: *\nAllow: /\n');
  await rm(`${directory}sitemap.xml`, { force: true });
}
html = html.replace('</head>', `<!-- search:start -->${tags.join('\n')}\n<!-- search:end -->\n</head>`);
await writeFile(`${directory}index.html`, html);
console.log(`Homepage prerendered with visible content. ${publicUrl ? `Canonical ${publicUrl.href}` : 'Local preview uses noindex; set STARLOCK_PUBLIC_URL for a public build.'}`);
