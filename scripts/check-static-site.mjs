import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const html = await readFile(new URL('../dist/playground/index.html', import.meta.url), 'utf8');
const head = html.slice(0, html.indexOf('</head>'));
assert.equal((html.match(/<h1\b/g) || []).length, 1);
for (const id of ['hero-title', 'experience', 'architecture', 'integration', 'visuals']) {
  assert.ok(html.includes(`id="${id}"`), `Missing static section ${id}`);
}
assert.ok(html.includes('href="https://github.com/StarDreamTech/starlock/blob/main/docs/examples/ReactIntegration.tsx"'));
assert.equal((head.match(/type="application\/ld\+json"/g) || []).length, 1);
const data = JSON.parse(head.match(/<script type="application\/ld\+json">(.*?)<\/script>/s)[1]);
assert.equal(data['@type'], 'SoftwareSourceCode');
if (process.env.STARLOCK_PUBLIC_URL) {
  const address = new URL(process.env.STARLOCK_PUBLIC_URL).href;
  assert.ok(head.includes(`<link rel="canonical" href="${address}">`));
  assert.doesNotMatch(head, /noindex/);
} else {
  assert.match(head, /name="robots" content="noindex, follow"/);
  assert.doesNotMatch(head, /rel="canonical"/);
}
console.log('PASS: static product content, document links, JSON-LD and indexing configuration.');
