// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'
import { createRuntime } from './runtime'
import type { WidgetHandle } from './types'

const challenge = { decision: 'challenge', challenge_id: 'ch_popup', challenge_type: 'digits', expires_in: 120,
  payload: { instruction: '输入数字', image: 'data:image/png;base64,test', image_width: 280, image_height: 88, input_mode: 'numeric' } }
const response = (value: object) => new Response(JSON.stringify(value), { status: 200 })
const settle = async () => { await new Promise(resolve => setTimeout(resolve, 0)); await nextTick() }
const roots = () => [...document.querySelectorAll<HTMLElement>('[data-starlock-portal]')].map(host => host.shadowRoot!)
const handles: WidgetHandle[] = []
beforeEach(() => {
  // jsdom has no top layer. Browser QA verifies native focus containment and inert background.
  HTMLDialogElement.prototype.showModal = function() { this.open = true; this.querySelector<HTMLButtonElement>('button')?.focus() }
  HTMLDialogElement.prototype.close = function() { this.open = false; this.dispatchEvent(new Event('close')) }
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response(challenge)))
  document.body.innerHTML = '<button id="before">原页面操作</button><form><div id="captcha"></div></form>'
})
afterEach(() => { handles.forEach(h => h.destroy()); handles.length = 0; document.body.innerHTML = ''; document.body.removeAttribute('style'); vi.unstubAllGlobals() })

describe('popup verification', () => {
  it('keeps the challenge in a body portal and restores focus without changing host page styles', async () => {
    const onClose = vi.fn()
    document.body.style.overflow = 'scroll'; document.body.style.paddingRight = '7px'
    const style = document.body.getAttribute('style')
    const handle = createRuntime('https://verify.example/sdk/v1/api.js', 'nonce-test').render('#captcha', {
      siteKey: 'site_test', sessionTicket: 'ticket.popup', onClose,
    }); handles.push(handle)
    await settle()
    const host = document.querySelector('#captcha > div')!.shadowRoot!
    expect(host.querySelector('.sl-widget')).toBeNull()
    expect(host.querySelector('.sl-trigger img')?.getAttribute('src')).toContain('data:image/svg+xml,')
    const root = roots()[0], dialog = root.querySelector('dialog')!
    expect(root.querySelector('.sl-widget')).not.toBeNull()
    expect(dialog.open).toBe(false)
    expect(root.querySelector('style')!.nonce).toBe('nonce-test')
    const before = document.querySelector<HTMLButtonElement>('#before')!; before.focus()
    handle.open()
    expect(dialog.open).toBe(true)
    expect(host.querySelector('.sl-trigger')?.getAttribute('aria-expanded')).toBe('true')
    const cancel = new Event('cancel', { cancelable: true }); dialog.dispatchEvent(cancel)
    expect(cancel.defaultPrevented).toBe(true)
    expect(dialog.open).toBe(false)
    expect(document.activeElement).toBe(before)
    expect(document.body.getAttribute('style')).toBe(style)
    expect(onClose).toHaveBeenCalledTimes(1)
    handle.open(); root.querySelector<HTMLButtonElement>('.sl-dismiss')!.click()
    expect(onClose).toHaveBeenCalledTimes(2)
    handle.destroy(); expect(roots()).toHaveLength(0)
  })

  it('auto-opens on request, retains the form token, closes on success and cleans up after destruction', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(response(challenge)).mockResolvedValueOnce(response({ verification_token: 'token.popup', expires_in: 120 })))
    const success = vi.fn(), closed = vi.fn()
    const handle = createRuntime('https://verify.example/sdk/v1/api.js').render('#captcha', {
      siteKey: 'site_test', sessionTicket: 'ticket.popup', autoOpen: true, onSuccess: success, onClose: closed,
    }); handles.push(handle)
    await settle()
    const root = roots()[0], dialog = root.querySelector('dialog')!
    expect(dialog.open).toBe(true)
    const input = root.querySelector('input')!; input.value = '23456'; input.dispatchEvent(new Event('input', { bubbles: true }))
    await nextTick(); root.querySelector('form')!.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })); await settle()
    expect(dialog.open).toBe(false)
    expect(success).toHaveBeenCalledExactlyOnceWith({ token: 'token.popup', expiresIn: 120 })
    expect(closed).not.toHaveBeenCalled()
    expect(new FormData(document.querySelector('form')!).get('starlock-response')).toBe('token.popup')
    expect(handle.getResponse()).toBe('token.popup')
    handle.destroy(); handle.destroy()
    expect(document.querySelector('#captcha')!.children).toHaveLength(0)
    expect(roots()).toHaveLength(0)
    expect(() => handle.open()).toThrow('已销毁')
  })

  it('dismisses backdrop clicks but keeps clicks inside the dialog and blocks background wheel scrolling', async () => {
    const handle = createRuntime('https://verify.example/sdk/v1/api.js').render('#captcha', { siteKey: 'site_test', sessionTicket: 'ticket.popup', autoOpen: true })
    handles.push(handle); await settle()
    const dialog = roots()[0].querySelector('dialog')!
    vi.spyOn(dialog, 'getBoundingClientRect').mockReturnValue({ left: 100, right: 400, top: 100, bottom: 600 } as DOMRect)
    dialog.dispatchEvent(new MouseEvent('click', { clientX: 200, clientY: 200, bubbles: true }))
    expect(dialog.open).toBe(true)
    const wheel = new WheelEvent('wheel', { clientX: 20, clientY: 20, deltaY: 300, cancelable: true })
    dialog.dispatchEvent(wheel); expect(wheel.defaultPrevented).toBe(true)
    dialog.dispatchEvent(new MouseEvent('click', { clientX: 20, clientY: 20, bubbles: true }))
    expect(dialog.open).toBe(false)
  })
})
