// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'
import { createRuntime } from './runtime'
import type { WidgetHandle } from './types'

const challenge = { decision: 'challenge', challenge_id: 'ch_remote', challenge_type: 'digits', expires_in: 120,
  payload: { instruction: '输入数字', image: 'data:image/png;base64,test', image_width: 280, image_height: 88, input_mode: 'numeric' } }
const response = (value: object) => new Response(JSON.stringify(value), { status: 200, headers: { 'Content-Type': 'application/json' } })
const settle = async () => { await new Promise(resolve => setTimeout(resolve, 0)); await nextTick() }
describe('hosted widget runtime', () => {
  const handles: WidgetHandle[] = []
  afterEach(() => { handles.forEach(handle => handle.destroy()); handles.length = 0; document.body.innerHTML = ''; vi.unstubAllGlobals() })
  it('isolates UI, uses the script service origin, returns token and clears it on reset', async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(response(challenge))
      .mockResolvedValueOnce(response({ verification_token: 'token.remote', expires_in: 120 }))
      .mockResolvedValueOnce(response({ ...challenge, challenge_id: 'ch_new' }))
    vi.stubGlobal('fetch', fetcher)
    document.body.innerHTML = '<form><div id="captcha"></div></form>'
    const api = createRuntime('https://verify.example.com/starlock/sdk/v1/api.js', 'test-csp-nonce')
    const onSuccess = vi.fn()
    const handle = api.render('#captcha', { displayMode: 'inline', siteKey: 'site_test', sessionTicket: 'ticket.remote', onSuccess })
    handles.push(handle)
    await settle()
    expect(fetcher.mock.calls[0][0]).toBe('https://verify.example.com/starlock/v1/challenges')
    expect(fetcher.mock.calls[0][1].credentials).toBe('omit')
    const host = document.querySelector('#captcha > div')!
    const shadow = host.shadowRoot!
    expect(document.querySelector('input:not([type=hidden])')).toBeNull()
    expect(shadow.querySelector('style')?.textContent).toContain('.sl-widget')
    expect(shadow.querySelector('style')?.nonce).toBe('test-csp-nonce')
    const answer = shadow.querySelector('input')!
    answer.value = '23456'; answer.dispatchEvent(new Event('input', { bubbles: true }))
    await nextTick()
    shadow.querySelector('form')!.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }))
    await settle()
    expect(onSuccess).toHaveBeenCalledExactlyOnceWith({ token: 'token.remote', expiresIn: 120 })
    expect(handle.getResponse()).toBe('token.remote')
    expect(new FormData(document.querySelector('form')!).get('starlock-response')).toBe('token.remote')
    await handle.reset('ticket.new')
    expect(handle.getResponse()).toBe('')
    expect(JSON.parse(fetcher.mock.calls[2][1].body).session_ticket).toBe('ticket.new')
    handle.destroy(); handle.destroy()
    expect(document.querySelector('#captcha')!.children).toHaveLength(0)
    await expect(handle.refresh()).rejects.toThrow('已销毁')
  })
  it('keeps instances independent and cancels late responses after removal', async () => {
    let resolve: (value: Response) => void = () => {}
    vi.stubGlobal('fetch', vi.fn().mockImplementationOnce(() => new Promise<Response>(done => { resolve = done }))
      .mockResolvedValueOnce(response(challenge)))
    document.body.innerHTML = '<div id="one"></div><div id="two"></div>'
    const api = createRuntime('https://verify.example.com/sdk/v1/api.js')
    const one = api.render('#one', { displayMode: 'inline', siteKey: 'site_one', sessionTicket: 'ticket.one' })
    const two = api.render('#two', { displayMode: 'inline', siteKey: 'site_two', sessionTicket: 'ticket.two' })
    handles.push(one, two)
    expect(() => api.render('#two', { siteKey: 'x', sessionTicket: 'y' })).toThrow('已挂载')
    one.destroy(); resolve(response(challenge)); await settle()
    expect(document.querySelector('#one')!.children).toHaveLength(0)
    expect(document.querySelector('#two > div')!.shadowRoot?.querySelector('input')?.disabled).toBe(false)
  })
})
