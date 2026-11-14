import { createApp } from 'vue'
import Widget from './Widget.vue'
import styles from './widget.css?inline'
import logoSvg from '../../../assets/brand/starlock.svg?raw'
import type { RenderOptions, StarLockApi, WidgetHandle } from './types'
import type { VerificationResult } from '@starlock/core'

const logo = `data:image/svg+xml,${encodeURIComponent(logoSvg)}`
function activeElement(): HTMLElement | null {
  let element = document.activeElement
  while (element?.shadowRoot?.activeElement) element = element.shadowRoot.activeElement
  return element instanceof HTMLElement ? element : null
}

export function createRuntime(sdkUrl: string, nonce = ''): StarLockApi {
  const source = new URL(sdkUrl)
  const defaultBase = source.origin + source.pathname.replace(/\/sdk\/v1\/api\.js$/, '').replace(/\/$/, '')
  const widgets = new WeakMap<HTMLElement, WidgetHandle>()
  return {
    version: '0.7.0', sdkUrl: source.href,
    render(target, options) {
      const container = typeof target === 'string' ? document.querySelector(target) : target
      if (!(container instanceof HTMLElement)) throw new Error('找不到星锁挂载容器')
      if (widgets.has(container)) throw new Error('该容器已挂载星锁，请先销毁原组件')
      if (!options.siteKey || !options.sessionTicket) throw new Error('需要站点标识与会话票据')
      const popup = options.displayMode !== 'inline'
      const host = document.createElement('div')
      const shadow = host.attachShadow({ mode: 'open' })
      const sheet = () => { const style = document.createElement('style'); if (nonce) style.nonce = nonce; style.textContent = styles; return style }
      shadow.append(sheet())
      const response = document.createElement('input')
      response.type = 'hidden'; response.name = 'starlock-response'
      container.append(host, response)
      const mount = document.createElement('div')
      let portal: HTMLDivElement | undefined, dialog: HTMLDialogElement | undefined, trigger: HTMLButtonElement | undefined
      let returnFocus: HTMLElement | null = null, destroyed = false
      let label: HTMLElement | undefined
      function status(text: string, passed = false) {
        if (label) label.textContent = text
        if (trigger) trigger.dataset.passed = String(passed)
      }
      function close(notify = false) {
        if (!dialog?.open) return
        dialog.close()
        trigger?.setAttribute('aria-expanded', 'false')
        if (returnFocus?.isConnected) returnFocus.focus({ preventScroll: true })
        else trigger?.focus({ preventScroll: true })
        if (notify) options.onClose?.()
      }
      if (popup) {
        trigger = document.createElement('button'); trigger.type = 'button'; trigger.className = 'sl-trigger'
        trigger.setAttribute('aria-haspopup', 'dialog'); trigger.setAttribute('aria-expanded', 'false')
        const mark = document.createElement('img'); mark.src = logo; mark.alt = ''; mark.width = mark.height = 34
        const copy = document.createElement('span'); copy.className = 'sl-trigger-copy'
        label = document.createElement('strong'); label.textContent = '点击完成验证'
        const sub = document.createElement('small'); sub.textContent = 'STARLOCK / HUMAN VERIFICATION'
        const arrow = document.createElement('span'); arrow.className = 'sl-trigger-arrow'; arrow.textContent = '↗'; arrow.setAttribute('aria-hidden', 'true')
        copy.append(label, sub); trigger.append(mark, copy, arrow); shadow.append(trigger)
        portal = document.createElement('div'); portal.dataset.starlockPortal = ''
        const root = portal.attachShadow({ mode: 'open' }); root.append(sheet())
        dialog = document.createElement('dialog'); dialog.className = 'sl-dialog'; dialog.setAttribute('aria-label', '星锁人机验证'); dialog.tabIndex = -1
        const dismiss = document.createElement('button'); dismiss.type = 'button'; dismiss.className = 'sl-dismiss'
        dismiss.textContent = '×'; dismiss.setAttribute('aria-label', '关闭验证'); dismiss.addEventListener('click', () => close(true))
        dialog.append(dismiss, mount); root.append(dialog); document.body.append(portal)
        dialog.addEventListener('cancel', event => { event.preventDefault(); close(true) })
        const inside = (x: number, y: number) => { const b = dialog!.getBoundingClientRect(); return x >= b.left && x <= b.right && y >= b.top && y <= b.bottom }
        dialog.addEventListener('click', event => { if (event.target === dialog && !inside(event.clientX, event.clientY)) close(true) })
        dialog.addEventListener('wheel', event => {
          if (event.ctrlKey) return
          const d = dialog!
          if (!inside(event.clientX, event.clientY) || d.scrollHeight <= d.clientHeight ||
              (event.deltaY < 0 && d.scrollTop <= 0) || (event.deltaY > 0 && d.scrollTop + d.clientHeight >= d.scrollHeight)) event.preventDefault()
        }, { passive: false })
        dialog.addEventListener('touchmove', event => { if (event.target === dialog) event.preventDefault() }, { passive: false })
      } else shadow.append(mount)
      const app = createApp(Widget, {
        siteKey: options.siteKey, sessionTicket: options.sessionTicket, apiBase: options.apiBase ?? defaultBase,
        onSuccess: (result: VerificationResult) => { response.value = result.token; status('验证通过', true); close(); options.onSuccess?.(result) },
        onExpire: () => { response.value = ''; status('验证已过期'); close(); options.onExpire?.() },
        onError: (code: string) => { response.value = ''; options.onError?.(code) },
      })
      let instance: { refresh(): Promise<void>; reset(ticket?: string): Promise<void> }
      try { instance = app.mount(mount) as unknown as typeof instance }
      catch (error) { portal?.remove(); host.remove(); response.remove(); throw error }
      const handle: WidgetHandle = {
        getResponse() { return response.value },
        open() {
          if (destroyed) throw new Error('组件已销毁')
          if (!dialog || dialog.open) return
          if (typeof dialog.showModal !== 'function') throw new Error('当前浏览器不支持验证弹窗')
          returnFocus = activeElement()
          dialog.showModal(); trigger?.setAttribute('aria-expanded', 'true')
        },
        close() { close(true) },
        async refresh() {
          if (destroyed) throw new Error('组件已销毁')
          response.value = ''; status('点击完成验证')
          await instance.refresh()
        },
        async reset(ticket) {
          if (destroyed) throw new Error('组件已销毁')
          response.value = ''; status('点击完成验证')
          await instance.reset(ticket)
        },
        destroy() {
          if (destroyed) return
          destroyed = true; close(); response.value = ''
          app.unmount(); portal?.remove(); host.remove(); response.remove(); widgets.delete(container)
        },
      }
      trigger?.addEventListener('click', () => handle.open())
      widgets.set(container, handle)
      try { if (popup && options.autoOpen) handle.open() }
      catch (error) { handle.destroy(); throw error }
      return handle
    },
  }
}
