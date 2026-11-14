'use client'

import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from 'react'
import type { CSSProperties } from 'react'
import { loadStarLock } from '@starlock/browser'
import type { RenderOptions, WidgetHandle } from '@starlock/browser'

export interface StarLockProps extends RenderOptions {
  sdkUrl?: string
  nonce?: string
  className?: string
  style?: CSSProperties
}

export type StarLockHandle = Pick<WidgetHandle, 'open' | 'close' | 'refresh'>

export const StarLock = forwardRef<StarLockHandle, StarLockProps>(function StarLock({
  siteKey, sessionTicket, apiBase, sdkUrl, nonce, displayMode, autoOpen,
  onSuccess, onExpire, onError, onClose, className, style,
}, ref) {
  const container = useRef<HTMLDivElement>(null)
  const widget = useRef<WidgetHandle | null>(null)
  const latest = useRef({ onSuccess, onExpire, onError, onClose, autoOpen })
  const [loading, setLoading] = useState(true)
  const [message, setMessage] = useState('')
  const [attempt, setAttempt] = useState(0)

  // Callback changes should not replace an active challenge.
  useEffect(() => {
    latest.current = { onSuccess, onExpire, onError, onClose, autoOpen }
  }, [onSuccess, onExpire, onError, onClose, autoOpen])

  useImperativeHandle(ref, () => ({
    open: () => widget.current?.open(),
    close: () => widget.current?.close(),
    refresh: async () => { await widget.current?.refresh() },
  }), [])

  useEffect(() => {
    let active = true
    let instance: WidgetHandle | undefined
    setLoading(true)
    setMessage('')

    async function mount() {
      try {
        const api = await loadStarLock(sdkUrl ?? `${apiBase || ''}/sdk/v1/api.js`, nonce)
        if (!active || !container.current) return
        instance = api.render(container.current, {
          siteKey, sessionTicket, apiBase, displayMode,
          autoOpen: latest.current.autoOpen,
          onSuccess: result => { if (active) latest.current.onSuccess?.(result) },
          onExpire: () => { if (active) latest.current.onExpire?.() },
          onError: code => { if (active) latest.current.onError?.(code) },
          onClose: () => { if (active) latest.current.onClose?.() },
        })
        widget.current = instance
      } catch (error) {
        if (!active) return
        setMessage(error instanceof Error ? error.message : '无法加载星锁验证组件')
        latest.current.onError?.('SDK_LOAD_FAILED')
      } finally {
        if (active) setLoading(false)
      }
    }

    void mount()
    return () => {
      active = false
      instance?.destroy()
      if (widget.current === instance) widget.current = null
    }
  }, [siteKey, sessionTicket, apiBase, sdkUrl, nonce, displayMode, attempt])

  useEffect(() => {
    if (autoOpen) widget.current?.open()
  }, [autoOpen])

  return (
    <div className={className} style={style}>
      {loading && <p role="status">正在加载星锁验证…</p>}
      {message && <p role="alert">{message}</p>}
      {message && <button type="button" onClick={() => setAttempt(value => value + 1)}>重新加载验证组件</button>}
      <div ref={container} />
    </div>
  )
})
