const form = document.querySelector('#business-form')
const submit = document.querySelector('#submit')
const status = document.querySelector('#status')
const retry = document.querySelector('#retry')
const choices = [...document.querySelectorAll('[data-kind]')]
const script = document.querySelector('#starlock-sdk')
const sourceChoices = [...document.querySelectorAll('[data-rotation-source]')]
let rotationSource = 'preset'
let widget, selected = 'rotate', revision = 0, busy = false, pending = false, autoOpen = false, disposed = false
const controller = new AbortController()
const ready = window.StarLock ? Promise.resolve() : new Promise((resolve, reject) => {
  const timeout = setTimeout(() => reject(new Error('托管脚本加载超时')), 15000)
  script.addEventListener('load', () => { clearTimeout(timeout); resolve() }, { once: true })
  script.addEventListener('error', () => { clearTimeout(timeout); reject(new Error('托管脚本加载失败')) }, { once: true })
})
void ready.catch(error => { status.textContent = error.message })
async function post(path, body) {
  const response = await fetch(path, { method: 'POST', credentials: 'same-origin', signal: controller.signal,
    headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
  const result = await response.json()
  if (!response.ok) throw new Error(result.message || '请求失败')
  return result
}
function choose(kind, open = true, source = rotationSource) {
  const same = kind === selected && source === rotationSource
  if (same && widget && !busy) { widget.open(); return }
  if (same && busy) { autoOpen = open; return }
  rotationSource = source
  selected = kind; autoOpen = open; revision++; pending = true
  submit.disabled = true; retry.hidden = true; widget?.destroy(); widget = undefined
  for (const choice of choices) choice.setAttribute('aria-pressed', String(choice.dataset.kind === kind))
  for (const choice of sourceChoices) choice.setAttribute('aria-pressed', String(choice.dataset.rotationSource === source))
  document.querySelector('#rotation-sources').hidden = kind !== 'rotate'
  document.querySelector('#current-kind').textContent = choices.find(choice => choice.dataset.kind === kind).querySelector('strong').textContent
  status.textContent = '正在准备新的验证…'
  void prepare()
}
async function prepare() {
  if (busy || disposed) return
  busy = true
  try {
    while (pending && !disposed) {
      pending = false
      const current = revision
      try {
        await ready
        const session = await post('/demo/session', { challenge_type: selected,
          ...(selected === 'rotate' ? { rotation_source: rotationSource } : {}) })
        if (current !== revision || disposed) continue
        widget = window.StarLock.render('#captcha', {
          siteKey: session.site_key, sessionTicket: session.session_ticket, autoOpen,
          onSuccess: () => { if (current === revision) { submit.disabled = false; status.textContent = '验证已通过，可以提交本次演示。' } },
          onExpire: () => { if (current === revision) { submit.disabled = true; retry.hidden = false; status.textContent = '验证已过期，请准备新会话。' } },
          onClose: () => { if (current === revision && !widget?.getResponse()) status.textContent = '弹窗已收起，点击验证卡可继续。' },
          onError: code => { if (current === revision) { submit.disabled = true; status.textContent = `验证暂不可用：${code}` } },
        })
        status.textContent = '点击题型或验证卡，在弹窗中完成挑战。'
      } catch (error) { if (current === revision && !disposed) { status.textContent = error.message; retry.hidden = false } }
    }
  } finally { busy = false }
}
for (const choice of choices) choice.addEventListener('click', () => choose(choice.dataset.kind))
for (const choice of sourceChoices) choice.addEventListener('click', () => choose('rotate', true, choice.dataset.rotationSource))
retry.addEventListener('click', () => { widget?.destroy(); widget = undefined; choose(selected) })
form.addEventListener('submit', async event => {
  event.preventDefault()
  if (busy || !widget?.getResponse()) return
  const current = revision
  busy = true; submit.disabled = true
  try {
    const token = new FormData(form).get('starlock-response')
    const result = await post('/demo/submit', { token })
    if (current !== revision || disposed) return
    if (result.success !== true) throw new Error('验证结果不完整')
    status.textContent = '服务端复核成功，本次演示已完成。'
  } catch (error) { if (current === revision && !disposed) { status.textContent = `${error.message}，请重新验证。`; retry.hidden = false } }
  finally { if (current === revision) { widget?.destroy(); widget = undefined; retry.hidden = false }; busy = false; if (pending && !disposed) void prepare() }
})
window.addEventListener('pagehide', () => { disposed = true; revision++; controller.abort(); widget?.destroy() })
choose('rotate', false)
