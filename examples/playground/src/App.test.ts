// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest'
import { createApp, nextTick } from 'vue'
import App from './App.vue'

const widgets = vi.hoisted(() => [] as { success(): void; expire(): void }[])
vi.mock('@starlock/vue', async () => {
  const { defineComponent, h } = await import('vue')
  return { StarLock: defineComponent({ props: ['siteKey', 'sessionTicket'], emits: ['success', 'expire'],
    setup(props, { emit }) {
      widgets.push({ success: () => emit('success', { token: 'test.token', expiresIn: 120 }), expire: () => emit('expire') })
      return () => h('div', { 'data-widget': props.sessionTicket }, '已显示验证题目')
    } }) }
})
const response = (value: object) => new Response(JSON.stringify(value), { status: 200 })
const session = (ticket: string) => response({ site_key: 'site_test', session_ticket: ticket })
const settle = async () => { await new Promise(resolve => setTimeout(resolve, 0)); await nextTick() }
const button = (name: string) => [...document.querySelectorAll<HTMLButtonElement>('button')].find(b => b.getAttribute('aria-label') === name || b.textContent!.trim().startsWith(name))!
let app: ReturnType<typeof createApp>
function mount() { app = createApp(App); app.mount(document.body.appendChild(document.createElement('div'))) }
afterEach(() => { app?.unmount(); widgets.length = 0; document.body.innerHTML = ''; vi.unstubAllGlobals() })

describe('instant playground experience', () => {
  it('shows the advanced default immediately and completes backend verification automatically', async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(session('ticket.ring')).mockResolvedValueOnce(response({ success: true }))
    vi.stubGlobal('fetch', fetcher)
    mount(); await settle()
    expect(JSON.parse(fetcher.mock.calls[0][1].body).challenge_type).toBe('rotate')
    expect(document.querySelector('[data-widget]')).not.toBeNull()
    expect(document.body.textContent).not.toContain('开始验证')
    widgets[0].success(); await settle()
    expect(fetcher.mock.calls[1][0]).toBe('/demo/submit')
    expect(document.body.textContent).toContain('刚刚好，是你。')
    expect(document.querySelector('[data-widget]')).toBeNull()
  })

  it('coalesces quick selections and keeps demo cookie requests in order', async () => {
    let finish: (value: Response) => void = () => {}
    const fetcher = vi.fn().mockImplementationOnce(() => new Promise<Response>(resolve => { finish = resolve }))
      .mockResolvedValueOnce(session('ticket.digits'))
    vi.stubGlobal('fetch', fetcher)
    mount()
    button('旋转滑块').click(); button('数字验证').click()
    await nextTick()
    expect(fetcher).toHaveBeenCalledTimes(1)
    expect(button('数字验证').getAttribute('aria-pressed')).toBe('true')
    finish(session('ticket.old')); await settle()
    expect(fetcher).toHaveBeenCalledTimes(2)
    expect(JSON.parse(fetcher.mock.calls[1][1].body).challenge_type).toBe('digits')
    expect(document.querySelector('[data-widget]')?.getAttribute('data-widget')).toBe('ticket.digits')
  })

  it('finishes an in-flight consume before creating a new context and discards stale callbacks', async () => {
    let finish: (value: Response) => void = () => {}
    const fetcher = vi.fn().mockResolvedValueOnce(session('ticket.first'))
      .mockImplementationOnce(() => new Promise<Response>(resolve => { finish = resolve }))
      .mockResolvedValueOnce(session('ticket.next'))
    vi.stubGlobal('fetch', fetcher)
    mount(); await settle()
    const old = widgets[0]
    old.success(); button('字符验证').click(); await settle()
    expect(fetcher).toHaveBeenCalledTimes(2)
    finish(response({ success: true })); await settle()
    expect(fetcher).toHaveBeenCalledTimes(3)
    expect(JSON.parse(fetcher.mock.calls[2][1].body).challenge_type).toBe('text')
    old.success(); old.expire(); await settle()
    expect(fetcher).toHaveBeenCalledTimes(3)
    expect(document.querySelector('[data-widget]')?.getAttribute('data-widget')).toBe('ticket.next')
    expect(document.body.textContent).not.toContain('刚刚好，是你。')
  })

  it('recovers from initial connection failure and expired challenges', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValueOnce(new Error('连接失败')).mockResolvedValueOnce(session('ticket.retry'))
      .mockResolvedValueOnce(session('ticket.fresh')))
    mount(); await settle()
    expect(document.body.textContent).toContain('连接失败')
    button('重新加载').click(); await settle()
    widgets[0].expire(); await settle()
    expect(document.body.textContent).toContain('这份挑战已过期')
    button('重新加载').click(); await settle()
    expect(document.querySelector('[data-widget]')?.getAttribute('data-widget')).toBe('ticket.fresh')
  })

  it('requires an explicit successful backend verdict before displaying completion', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(session('ticket.invalid-result')).mockResolvedValueOnce(response({ success: false })))
    mount(); await settle()
    widgets[0].success(); await settle()
    expect(document.body.textContent).toContain('验证结果不完整')
    expect(document.body.textContent).not.toContain('刚刚好，是你。')
  })
})
