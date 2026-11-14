// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest'
import { createApp, h, nextTick, reactive } from 'vue'
import StarLock from './StarLock.vue'
import { loadStarLock } from '@starlock/browser'
import type { StarLockApi } from '@starlock/browser'

vi.mock('@starlock/browser', () => ({ loadStarLock: vi.fn() }))
const settle = async () => { await new Promise(resolve => setTimeout(resolve, 0)); await nextTick() }
describe('Vue hosted SDK adapter', () => {
  const apps: ReturnType<typeof createApp>[] = []
  afterEach(() => { apps.forEach(app => app.unmount()); apps.length = 0; document.body.innerHTML = ''; vi.resetAllMocks() })
  it('ignores a finished script load after the component unmounts', async () => {
    let resolve: (api: StarLockApi) => void = () => {}
    vi.mocked(loadStarLock).mockReturnValue(new Promise(done => { resolve = done }))
    const app = createApp(StarLock, { siteKey: 'site_test', sessionTicket: 'ticket.test', sdkUrl: 'https://verify.example/sdk/v1/api.js' })
    app.mount(document.body.appendChild(document.createElement('div')))
    app.unmount()
    const render = vi.fn()
    resolve({ version: '0.3.0', sdkUrl: 'https://verify.example/sdk/v1/api.js', render })
    await settle()
    expect(render).not.toHaveBeenCalled()
  })
  it('destroys the old instance on a new session and forwards callbacks', async () => {
    const handle = { getResponse: vi.fn(), refresh: vi.fn(), reset: vi.fn(), destroy: vi.fn() }
    const render = vi.fn().mockReturnValue(handle)
    vi.mocked(loadStarLock).mockResolvedValue({ version: '0.3.0', sdkUrl: 'https://verify.example/sdk/v1/api.js', render })
    const onSuccess = vi.fn()
    const props = reactive({ siteKey: 'site_test', sessionTicket: 'ticket.old', onSuccess })
    const app = createApp({ render: () => h(StarLock, props) })
    apps.push(app); app.mount(document.body.appendChild(document.createElement('div')))
    await settle()
    render.mock.calls[0][1].onSuccess({ token: 'passed.token', expiresIn: 120 })
    expect(onSuccess).toHaveBeenCalledExactlyOnceWith({ token: 'passed.token', expiresIn: 120 })
    props.sessionTicket = 'ticket.new'
    await settle()
    expect(handle.destroy).toHaveBeenCalledTimes(1)
    expect(render.mock.calls[1][1].sessionTicket).toBe('ticket.new')
  })
})
