// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { StarLockApi } from './types'

const url = 'https://verify.example.com/sdk/v1/api.js'
describe('hosted script loader', () => {
  beforeEach(() => { vi.useFakeTimers(); vi.resetModules(); delete window.StarLock; document.head.innerHTML = '' })
  afterEach(() => { vi.useRealTimers(); delete window.StarLock })
  it('deduplicates loading and resolves the actual hosted runtime', async () => {
    const { loadStarLock } = await import('./loader')
    const one = loadStarLock(url, 'test-csp-nonce'), two = loadStarLock(url)
    expect(one).toBe(two)
    expect(document.querySelectorAll('script')).toHaveLength(1)
    expect(document.querySelector('script')!.nonce).toBe('test-csp-nonce')
    await expect(loadStarLock('https://other.example/sdk/v1/api.js')).rejects.toThrow('正在加载')
    const api = { sdkUrl: url, version: '0.3.0', render: vi.fn() } satisfies StarLockApi
    window.StarLock = api
    document.querySelector('script')!.dispatchEvent(new Event('load'))
    expect(await one).toBe(api)
    expect(await loadStarLock(url)).toBe(api)
    await expect(loadStarLock('https://other.example/sdk/v1/api.js')).rejects.toThrow('其他')
  })
  it('cleans up a failed request and allows retry', async () => {
    const { loadStarLock } = await import('./loader')
    const first = loadStarLock(url)
    const rejected = expect(first).rejects.toThrow('无法加载')
    document.querySelector('script')!.dispatchEvent(new Event('error'))
    await rejected
    expect(document.querySelector('script')).toBeNull()
    const retry = loadStarLock(url)
    const timeout = expect(retry).rejects.toThrow('超时')
    await vi.advanceTimersByTimeAsync(15000)
    await timeout
    expect(document.querySelector('script')).toBeNull()
  })
  it('rejects unexpected script output and non-http URLs', async () => {
    const { loadStarLock } = await import('./loader')
    await expect(loadStarLock('javascript:alert(1)')).rejects.toThrow('无效')
    const request = loadStarLock(url)
    const rejected = expect(request).rejects.toThrow('响应无效')
    document.querySelector('script')!.dispatchEvent(new Event('load'))
    await rejected
  })
})
