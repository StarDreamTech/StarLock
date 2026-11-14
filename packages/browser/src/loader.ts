import type { StarLockApi } from './types'
export type { RenderOptions, WidgetHandle, StarLockApi } from './types'

const pending = new Map<string, Promise<StarLockApi>>()
export function loadStarLock(sdkUrl = '/sdk/v1/api.js', nonce?: string): Promise<StarLockApi> {
  if (typeof window === 'undefined') return Promise.reject(new Error('星锁只能在浏览器挂载'))
  let source: URL
  try {
    source = new URL(sdkUrl, document.baseURI)
    if (!['https:', 'http:'].includes(source.protocol) || source.username || source.password || source.hash) {
      throw new Error('无效的星锁 SDK 地址')
    }
  } catch (error) { return Promise.reject(error) }
  const url = source.href
  if (window.StarLock) {
    return window.StarLock.sdkUrl === url ? Promise.resolve(window.StarLock) :
      Promise.reject(new Error('当前页面已加载其他星锁 SDK 地址'))
  }
  const existing = pending.get(url)
  if (existing) return existing
  if (pending.size) return Promise.reject(new Error('当前页面正在加载其他星锁 SDK 地址'))
  const loading = new Promise<StarLockApi>((resolve, reject) => {
    const script = document.createElement('script')
    script.src = url
    script.async = true
    if (nonce) script.nonce = nonce
    function finish(error?: Error) {
      clearTimeout(timeout)
      script.onload = script.onerror = null
      if (error) { script.remove(); reject(error) }
      else resolve(window.StarLock!)
    }
    const timeout = setTimeout(() => finish(new Error('星锁 SDK 加载超时')), 15000)
    script.onload = () => {
      const api = window.StarLock
      if (!api || api.sdkUrl !== url || typeof api.render !== 'function') finish(new Error('星锁 SDK 响应无效'))
      else finish()
    }
    script.onerror = () => finish(new Error('无法加载星锁 SDK，请检查网络或 CSP 配置'))
    document.head.append(script)
  })
  pending.set(url, loading)
  void loading.catch(() => pending.delete(url))
  return loading
}
