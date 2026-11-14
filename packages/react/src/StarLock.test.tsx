// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, createRef, StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import type { Root } from 'react-dom/client'
import { renderToString } from 'react-dom/server'
import { loadStarLock } from '@starlock/browser'
import type { RenderOptions, StarLockApi } from '@starlock/browser'
import { StarLock } from './StarLock'
import type { StarLockHandle } from './StarLock'

vi.mock('@starlock/browser', () => ({ loadStarLock: vi.fn() }))

let root: Root
const handle = () => ({
  open: vi.fn(), close: vi.fn(), refresh: vi.fn().mockResolvedValue(undefined),
  reset: vi.fn().mockResolvedValue(undefined), getResponse: vi.fn(() => ''), destroy: vi.fn(),
})
const sdk = (render: StarLockApi['render']): StarLockApi => ({
  version: '0.7.0', sdkUrl: 'https://verify.example/sdk/v1/api.js', render,
})

beforeEach(() => {
  vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true)
  root = createRoot(document.body.appendChild(document.createElement('div')))
})
afterEach(async () => {
  await act(async () => root.unmount())
  document.body.innerHTML = ''
  vi.resetAllMocks()
  vi.unstubAllGlobals()
})

describe('React hosted SDK adapter', () => {
  it('ignores the stale StrictMode setup and destroys the mounted widget', async () => {
    let resolve!: (api: StarLockApi) => void
    vi.mocked(loadStarLock).mockReturnValue(new Promise(done => { resolve = done }))
    const instance = handle()
    const render = vi.fn().mockReturnValue(instance)
    await act(async () => {
      root.render(<StrictMode><StarLock siteKey="site_test" sessionTicket="ticket.test" /></StrictMode>)
    })
    expect(loadStarLock).toHaveBeenCalledTimes(2)
    await act(async () => resolve(sdk(render)))
    expect(render).toHaveBeenCalledTimes(1)
    await act(async () => root.unmount())
    expect(instance.destroy).toHaveBeenCalledTimes(1)
    root = createRoot(document.createElement('div'))
  })

  it('ignores a script response after unmounting', async () => {
    let resolve!: (api: StarLockApi) => void
    vi.mocked(loadStarLock).mockReturnValue(new Promise(done => { resolve = done }))
    const render = vi.fn()
    await act(async () => root.render(<StarLock siteKey="site_test" sessionTicket="ticket.test" />))
    await act(async () => root.unmount())
    await act(async () => resolve(sdk(render)))
    expect(render).not.toHaveBeenCalled()
    root = createRoot(document.createElement('div'))
  })

  it('keeps callback updates in place and rejects old-session callbacks', async () => {
    const first = handle(), second = handle()
    const render = vi.fn().mockReturnValueOnce(first).mockReturnValueOnce(second)
    vi.mocked(loadStarLock).mockResolvedValue(sdk(render))
    const ref = createRef<StarLockHandle>()
    const oldSuccess = vi.fn(), success = vi.fn(), close = vi.fn()
    await act(async () => root.render(<StarLock ref={ref} siteKey="site_test" sessionTicket="ticket.old" onSuccess={oldSuccess} />))
    await act(async () => root.render(<StarLock ref={ref} siteKey="site_test" sessionTicket="ticket.old" onSuccess={success} onClose={close} />))
    expect(render).toHaveBeenCalledTimes(1)
    const oldOptions = render.mock.calls[0][1] as RenderOptions
    oldOptions.onSuccess?.({ token: 'token.old', expiresIn: 120 })
    oldOptions.onClose?.()
    expect(oldSuccess).not.toHaveBeenCalled()
    expect(success).toHaveBeenCalledExactlyOnceWith({ token: 'token.old', expiresIn: 120 })
    expect(close).toHaveBeenCalledTimes(1)
    await act(async () => root.render(<StarLock ref={ref} siteKey="site_test" sessionTicket="ticket.new" onSuccess={success} />))
    expect(first.destroy).toHaveBeenCalledTimes(1)
    oldOptions.onSuccess?.({ token: 'token.stale', expiresIn: 120 })
    expect(success).toHaveBeenCalledTimes(1)
    expect(render.mock.calls[1][1].sessionTicket).toBe('ticket.new')
    ref.current?.open()
    ref.current?.close()
    await ref.current?.refresh()
    expect(second.open).toHaveBeenCalledTimes(1)
    expect(second.close).toHaveBeenCalledTimes(1)
    expect(second.refresh).toHaveBeenCalledTimes(1)
  })

  it('retries load errors and honors autoOpen changes while the script is pending', async () => {
    let resolve!: (api: StarLockApi) => void
    vi.mocked(loadStarLock).mockRejectedValueOnce(new Error('脚本连接失败'))
      .mockReturnValueOnce(new Promise(done => { resolve = done }))
    const onError = vi.fn(), instance = handle()
    const render = vi.fn().mockReturnValue(instance)
    const props = { siteKey: 'site_test', sessionTicket: 'ticket.test', sdkUrl: 'https://verify.example/sdk/v1/api.js', nonce: 'test-nonce', onError }
    await act(async () => root.render(<StarLock {...props} autoOpen={false} />))
    expect(document.querySelector('[role=alert]')?.textContent).toBe('脚本连接失败')
    expect(onError).toHaveBeenCalledExactlyOnceWith('SDK_LOAD_FAILED')
    await act(async () => document.querySelector<HTMLButtonElement>('button')!.click())
    await act(async () => root.render(<StarLock {...props} autoOpen />))
    await act(async () => resolve(sdk(render)))
    expect(render.mock.calls[0][1].autoOpen).toBe(true)
    expect(loadStarLock).toHaveBeenLastCalledWith(props.sdkUrl, 'test-nonce')
    expect(document.querySelector('[role=alert]')).toBeNull()
    await act(async () => root.render(<StarLock {...props} autoOpen={false} />))
    await act(async () => root.render(<StarLock {...props} autoOpen />))
    expect(instance.open).toHaveBeenCalledTimes(1)
  })

  it('renders server markup without loading a browser script', () => {
    const html = renderToString(<StarLock siteKey="site_test" sessionTicket="ticket.server" />)
    expect(html).toContain('正在加载星锁验证')
    expect(loadStarLock).not.toHaveBeenCalled()
  })
})
