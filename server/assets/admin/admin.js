'use strict';
const $ = (id) => document.getElementById(id);
const state = { sets: [], selected: null, detail: null, defaultId: 'system-all', filter: 'all' };
let busy = false, sequence = 0, noticeTimer, editing = false;
function el(tag, className, text) { const node = document.createElement(tag); if (className) node.className = className; if (text !== undefined) node.textContent = text; return node; }
function notice(message, error = false) { clearTimeout(noticeTimer); $('notice').textContent = message; $('notice').className = error ? 'error' : ''; $('notice').hidden = false; noticeTimer = setTimeout(() => { $('notice').hidden = true; }, error ? 10000 : 4500); }
async function api(path, data, extra = {}) {
  const options = data === undefined ? {} : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) };
  const response = await fetch('/admin/api' + path, { credentials: 'same-origin', ...options, ...extra });
  const result = await response.json();
  if (!response.ok) { if (response.status === 401) { $('workspace').hidden = true; $('login').hidden = false; $('logout').hidden = true; } throw new Error(result.message || '请求失败，请重试'); }
  return result;
}
function action(fn) { return async (event) => { if (busy) return; busy = true; document.body.setAttribute('aria-busy', 'true'); try { await fn(event); } catch (error) { notice(error.message, true); } finally { busy = false; document.body.removeAttribute('aria-busy'); } }; }
function renderList() {
  $('set-list').replaceChildren();
  for (const set of state.sets.filter((s) => state.filter === 'all' || s.source === state.filter)) {
    const button = el('button', 'set-row'); button.setAttribute('aria-current', String(set.id === state.selected));
    const icon = el('span', 'set-placeholder', set.source === 'system' ? '✦' : '▧');
    const label = el('span'); label.append(el('strong', '', set.name), el('small', '', `${set.enabled_count} / ${set.image_count} 张 · ${set.active ? '已启用' : '已停用'}${state.defaultId === set.id ? ' · 默认' : ''}`));
    button.append(icon, label); button.addEventListener('click', () => select(set.id).catch((e) => notice(e.message, true))); $('set-list').append(button);
  }
}
function renderDetail() {
  const set = state.detail; if (!set) return;
  $('set-title').textContent = set.name; $('set-source').textContent = set.source === 'system' ? 'SYSTEM COLLECTION' : 'CUSTOM COLLECTION'; $('set-id').textContent = set.id;
  $('set-status').textContent = set.active ? '已启用' : '已停用'; $('set-status').className = 'badge' + (set.active ? ' active' : '');
  $('toggle-set').textContent = set.active ? '停用图集' : '启用图集'; $('set-default').textContent = state.defaultId === set.id ? '当前默认图库 ✓' : '设为默认图库 ↗'; $('set-default').disabled = state.defaultId === set.id || !set.active || !set.images.some((i) => i.active);
  $('upload-box').hidden = set.source !== 'custom'; $('system-note').hidden = set.source !== 'system'; $('empty').hidden = set.images.length > 0;
  $('image-grid').replaceChildren();
  for (const image of set.images) {
    const card = el('figure', 'image-card' + (image.active ? '' : ' off'));
    const img = el('img'); img.src = `/admin/api/images/${encodeURIComponent(image.id)}/preview`; img.alt = image.name; img.loading = 'lazy'; img.width = 256; img.height = 256;
    const caption = el('figcaption'); const button = el('button', 'secondary', image.active ? '停用图片' : '启用图片');
    button.setAttribute('aria-label', `${image.active ? '停用' : '启用'} ${image.name}`);
    button.addEventListener('click', action(async () => { await api('/images/' + image.id, { active: !image.active }); await reload(set.id); }));
    caption.append(el('strong', '', image.name), el('small', '', `${image.width} × ${image.height} · ${image.active ? (set.active ? '参与出题' : '图片已启用') : '暂停出题'}`), button); card.append(img, caption); $('image-grid').append(card);
  }
}
async function select(id) { const serial = ++sequence; state.selected = id; renderList(); const detail = await api('/sets/' + id); if (serial !== sequence) return; state.detail = detail; renderDetail(); }
async function reload(id = state.selected) {
  const result = await api('/sets'); state.sets = result.sets; state.defaultId = result.default_set_id;
  $('total').textContent = state.sets.filter((s) => s.active).reduce((n, s) => n + s.enabled_count, 0);
  $('default-name').textContent = state.defaultId === 'system-all' ? '全部系统随机' : state.sets.find((s) => s.id === state.defaultId)?.name || '—';
  $('all-default').disabled = state.defaultId === 'system-all';
  await select(id && state.sets.some((s) => s.id === id) ? id : state.sets[0].id);
}
async function enter() { await reload(); $('login').hidden = true; $('workspace').hidden = false; $('logout').hidden = false; }
$('login-form').addEventListener('submit', (event) => { event.preventDefault(); action(async () => { const token = $('token').value; $('token').value = ''; await api('/login', { token }); await enter(); })(event); });
$('logout').addEventListener('click', action(async () => { await api('/logout', {}); $('workspace').hidden = true; $('login').hidden = false; $('logout').hidden = true; notice('已退出管理后台'); }));
for (const button of document.querySelectorAll('[data-filter]')) button.addEventListener('click', () => { state.filter = button.dataset.filter; for (const option of document.querySelectorAll('[data-filter]')) option.setAttribute('aria-pressed', String(option === button)); renderList(); });
function openName(edit) { if (busy) return; editing = edit; $('dialog-title').textContent = edit ? '重命名图片集' : '新建图片集'; $('dialog-hint').textContent = edit ? '名称仅用于管理，不会更改图片集标识。' : '新建图集默认停用，上传图片后即可启用。'; $('set-name').value = edit ? state.detail.name : ''; $('name-dialog').showModal(); $('set-name').focus(); }
$('new-set').addEventListener('click', () => openName(false)); $('rename').addEventListener('click', () => openName(true)); $('cancel-name').addEventListener('click', () => $('name-dialog').close());
$('name-form').addEventListener('submit', (event) => { event.preventDefault(); action(async () => { const name = $('set-name').value.trim(); if (!name) throw new Error('请输入图集名称'); const result = editing ? await api('/sets/' + state.detail.id, { name, active: Boolean(state.detail.active) }) : await api('/sets', { name }); $('name-dialog').close(); if (!editing) { state.filter = 'all'; for (const button of document.querySelectorAll('[data-filter]')) button.setAttribute('aria-pressed', String(button.dataset.filter === 'all')); } await reload(result.id); notice(editing ? '图片集名称已更新' : '已创建图片集，请上传图片'); })(event); });
$('toggle-set').addEventListener('click', action(async () => { const set = state.detail; await api('/sets/' + set.id, { name: set.name, active: !set.active }); await reload(set.id); notice(set.active ? '已停用图集' : '已启用图集'); }));
$('set-default').addEventListener('click', action(async () => { await api('/default', { set_id: state.detail.id }); await reload(); notice('默认图库已更新，新会话将使用此图片集'); }));
$('all-default').addEventListener('click', action(async () => { await api('/default', { set_id: 'system-all' }); await reload(); notice('默认图库已设为全部系统随机'); }));
$('upload').addEventListener('change', (event) => { const files = Array.from(event.target.files); event.target.value = ''; action(async () => {
  if (!files.length) return; if (files.length > 200) throw new Error('每次最多选择 200 张图片'); const id = state.detail.id; let saved = 0, duplicate = 0; const errors = [];
  for (const [index, file] of files.entries()) {
    $('upload-progress').textContent = `正在处理 ${index + 1} / ${files.length}：${file.name}`;
    try { if (!['image/png', 'image/jpeg', 'image/webp'].includes(file.type) || file.size > 5 * 1024 * 1024) throw new Error('请使用不超过 5 MB 的 PNG、JPEG 或 WebP'); const result = await api('/sets/' + id + '/images', undefined, { method: 'POST', headers: { 'Content-Type': file.type, 'X-File-Name': encodeURIComponent(file.name) }, body: file }); result.duplicate ? duplicate++ : saved++; }
    catch (error) { errors.push(`${file.name}：${error.message}`); }
  }
  await reload(id); $('upload-progress').textContent = `新增 ${saved} 张，重复 ${duplicate} 张，失败 ${errors.length} 张。` + (errors.length ? '\n' + errors.join('\n') : (state.detail.active ? '\n上传完成，图片已加入出题池。' : '\n上传完成；启用图集后即可参与出题。')); notice(`上传完成：新增 ${saved} 张，重复 ${duplicate} 张，失败 ${errors.length} 张`, errors.length > 0);
})(event); });
(async () => { try { const status = await api('/status'); $('token-label').hidden = status.local_mode; $('login-hint').textContent = status.local_mode ? '本地开发环境，可直接进入。对外部署须配置管理口令。' : status.enabled ? '请输入服务端配置的管理口令。登录状态仅保存在当前浏览器。' : '后台尚未开放。请在服务端配置至少 32 字符的 STARLOCK_ADMIN_TOKEN。'; $('login-button').disabled = !status.enabled; if (status.authenticated) await enter(); } catch (error) { notice(error.message, true); } })();
