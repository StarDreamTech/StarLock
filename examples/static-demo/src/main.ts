import { createRuntime } from '../../../packages/browser/src/runtime'
import type { ChallengeType } from '@starlock/core'
import type { WidgetHandle } from '../../../packages/browser/src/types'
import { createDemoTransport } from './transport'
import type { DemoSample } from './transport'
import './style.css'

const buttons = Array.from(document.querySelectorAll<HTMLButtonElement>('[data-kind]'))
const result = document.querySelector<HTMLElement>('#result')!
const retry = document.querySelector<HTMLButtonElement>('#retry')!
const container = document.querySelector<HTMLElement>('#widget')!
let sampleRequest: Promise<DemoSample[]> | undefined
let handle: WidgetHandle | undefined
let selected: ChallengeType = 'rotate'
let operation = 0
const source = new URL('./demo-api', location.href).href

function loadSamples() {
  sampleRequest ??= fetch(new URL('./challenges.json', location.href)).then(async response => {
    if (!response.ok) throw new Error('演示题暂时没有加载成功，请重试')
    const data = await response.json() as DemoSample[]
    if (!Array.isArray(data) || !data.length) throw new Error('演示题暂时不可用，请重试')
    return data
  }).catch(error => {
    sampleRequest = undefined
    throw error
  })
  return sampleRequest
}

async function start(kind: ChallengeType) {
  const current = ++operation
  selected = kind
  handle?.destroy()
  handle = undefined
  buttons.forEach(button => button.setAttribute('aria-pressed', String(button.dataset.kind === kind)))
  const label = buttons.find(button => button.dataset.kind === kind)!.querySelector('strong')!.textContent
  result.textContent = `正在准备${label}…`
  retry.disabled = true
  try {
    const bank = await loadSamples()
    if (current !== operation) return
    const session = createDemoTransport(kind, bank)
    const runtime = createRuntime(source, '', session.transport)
    handle = runtime.render(container, {
      siteKey: 'site_demo_only', sessionTicket: session.sessionTicket, apiBase: source,
      displayMode: 'popup', autoOpen: true,
      onSuccess() {
        if (current !== operation) return
        result.textContent = `${label}体验完成，换一种方式试试。`
      },
      onExpire() {
        if (current === operation) result.textContent = '演示题已过期，点击再试一次即可继续。'
      },
      onClose() {
        if (current === operation && !handle?.getResponse()) result.textContent = `已收起${label}，点击卡片可继续体验。`
      },
      onError(code) {
        if (current === operation && code === 'IMAGE_ERROR') result.textContent = '图片加载失败，请重新体验。'
      },
    })
    result.textContent = `正在体验${label}`
  } catch (error) {
    if (current === operation) result.textContent = error instanceof Error ? error.message : '加载失败，请重新体验'
  } finally {
    if (current === operation) retry.disabled = false
  }
}
for (const button of buttons) button.addEventListener('click', () => { void start(button.dataset.kind as ChallengeType) })
retry.addEventListener('click', () => { void start(selected) })
window.addEventListener('pagehide', () => { operation++; handle?.destroy() })
void start('rotate')
