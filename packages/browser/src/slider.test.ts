// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'
import { createRuntime } from './runtime'
import type { WidgetHandle } from './types'

const challenge = { decision: 'challenge', challenge_id: 'ch_slider', challenge_type: 'slider', expires_in: 120,
  payload: { instruction: '拖动拼图', image: 'data:image/png;base64,test', image_width: 320, image_height: 180,
    piece_image: 'data:image/png;base64,piece', piece_width: 56, piece_height: 56,
    path: { kind: 'linear', control_points: [{ x: 6, y: 40 }, { x: 258, y: 40 }] } } }
const response = (value: object, status = 200) => new Response(JSON.stringify(value), { status })
const settle = async () => { await new Promise(resolve => setTimeout(resolve, 0)); await nextTick() }
const pointer = (type: string, x: number, id = 1, primary = true) => {
  const event = new MouseEvent(type, { bubbles: true, cancelable: true, clientX: x, button: 0 })
  Object.defineProperties(event, { pointerId: { value: id }, isPrimary: { value: primary }, pointerType: { value: 'touch' } })
  return event
}

describe('hosted puzzle slider', () => {
  const handles: WidgetHandle[] = []
  afterEach(() => { handles.forEach(handle => handle.destroy()); handles.length = 0; document.body.innerHTML = ''; vi.unstubAllGlobals() })
  async function mount(width = 310, value: { payload: { image: string } } = challenge) {
    document.body.innerHTML = '<div id="captcha"></div>'
    const onSuccess = vi.fn(), onError = vi.fn()
    const handle = createRuntime('https://verify.example.com/sdk/v1/api.js').render('#captcha', {
      displayMode: 'inline', siteKey: 'site_slider', sessionTicket: 'ticket.slider', onSuccess, onError,
    })
    handles.push(handle)
    await settle()
    const shadow = document.querySelector('#captcha > div')!.shadowRoot!
    const track = shadow.querySelector('.sl-track')!
    const thumb = shadow.querySelector<HTMLButtonElement>('[role=slider]')!
    vi.spyOn(track, 'getBoundingClientRect').mockReturnValue({ width } as DOMRect)
    vi.spyOn(thumb, 'getBoundingClientRect').mockReturnValue({ width: 44 } as DOMRect)
    thumb.setPointerCapture = vi.fn(); thumb.releasePointerCapture = vi.fn(); thumb.hasPointerCapture = vi.fn(() => true)
    shadow.querySelectorAll('img').forEach(image => image.dispatchEvent(new Event('load')))
    await nextTick()
    expect(shadow.querySelector('input')).toBeNull()
    expect(shadow.querySelector('.sl-scene')?.getAttribute('src')).toBe(value.payload.image)
    return { shadow, thumb, handle, onSuccess, onError }
  }

  it.each([210, 310, 462])('uses normalized progress at track width %i and retries a wrong answer', async width => {
    const fetcher = vi.fn().mockResolvedValueOnce(response(challenge))
      .mockResolvedValueOnce(response({ error_code: 'ANSWER_INVALID', message: '位置不正确', attempts_remaining: 2 }, 400))
      .mockResolvedValueOnce(response({ verification_token: 'token.slider', expires_in: 120 }))
    vi.stubGlobal('fetch', fetcher)
    const { thumb, handle, shadow } = await mount(width)
    const drag = () => {
      thumb.dispatchEvent(pointer('pointerdown', 10))
      thumb.dispatchEvent(pointer('pointermove', 10 + (width - 44) * .62))
      thumb.dispatchEvent(pointer('pointerup', 10 + (width - 44) * .62))
    }
    drag(); await settle()
    expect(JSON.parse(fetcher.mock.calls[1][1].body).answer.progress).toBeCloseTo(.62)
    expect(thumb.getAttribute('aria-valuenow')).toBe('0')
    expect(shadow.textContent).toContain('位置不正确')
    drag(); await settle()
    expect(handle.getResponse()).toBe('token.slider')
  })

  it('supports keyboard positioning on a cubic path and confirms explicitly', async () => {
    const curved = { ...challenge, challenge_type: 'bezier_slider', payload: { ...challenge.payload, path: {
      kind: 'cubic_bezier', control_points: [{ x: 0, y: 0 }, { x: 0, y: 100 }, { x: 100, y: 100 }, { x: 100, y: 0 }],
    } } }
    const fetcher = vi.fn().mockResolvedValueOnce(response(curved))
      .mockResolvedValueOnce(response({ verification_token: 'token.keyboard', expires_in: 120 }))
    vi.stubGlobal('fetch', fetcher)
    const { thumb, shadow, handle } = await mount(310, curved)
    for (let i = 0; i < 10; i++) thumb.dispatchEvent(new KeyboardEvent('keydown', { key: 'PageUp', bubbles: true, cancelable: true }))
    await nextTick()
    const piece = shadow.querySelector<HTMLElement>('.sl-piece')!
    expect(parseFloat(piece.style.left)).toBeCloseTo(50 / 320 * 100)
    expect(parseFloat(piece.style.top)).toBeCloseTo(75 / 180 * 100)
    expect(fetcher).toHaveBeenCalledTimes(1)
    thumb.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true }))
    await settle()
    expect(handle.getResponse()).toBe('token.keyboard')
  })

  it.each([210, 310, 462])('eases and rotates a straight path at width %i without changing submitted handle progress', async width => {
    const timed = { ...challenge, payload: { ...challenge.payload,
      path: { kind: 'linear', control_points: [{ x: 8, y: 50 }, { x: 248, y: 50 }] },
      motion: { easing: { kind: 'cubic_bezier', control_points: [{ x: .25, y: .1 }, { x: .25, y: 1 }] },
        rotation: { start_degrees: -80, end_degrees: 60 } },
    } }
    const fetcher = vi.fn().mockResolvedValueOnce(response(timed))
      .mockResolvedValueOnce(response({ verification_token: 'token.motion', expires_in: 120 }))
    vi.stubGlobal('fetch', fetcher)
    const { thumb, shadow, handle } = await mount(width, timed)
    const x = 10 + (width - 44) * .3125
    thumb.dispatchEvent(pointer('pointerdown', 10))
    thumb.dispatchEvent(pointer('pointermove', x))
    await nextTick()
    const piece = shadow.querySelector<HTMLElement>('.sl-piece')!
    expect(parseFloat(piece.style.left)).toBeCloseTo(137 / 320 * 100)
    expect(parseFloat(piece.style.top)).toBeCloseTo(50 / 180 * 100)
    expect(parseFloat(piece.style.transform.slice(7))).toBeCloseTo(-4.75)
    expect(thumb.getAttribute('aria-valuenow')).toBe('31')
    thumb.dispatchEvent(pointer('pointerup', x))
    await settle()
    expect(JSON.parse(fetcher.mock.calls[1][1].body).answer).toEqual({ progress: .3125 })
    expect(handle.getResponse()).toBe('token.motion')
  })

  it('rotates only the inner disk with eased speed and submits raw handle progress', async () => {
    const ring = { ...challenge, challenge_type: 'rotate', payload: { instruction: '旋转内圈', image: challenge.payload.image,
      piece_image: challenge.payload.piece_image, image_width: 256, image_height: 256, piece_width: 256, piece_height: 256,
      motion: { easing: { kind: 'cubic_bezier', control_points: [{ x: .25, y: .1 }, { x: .25, y: 1 }] },
        rotation: { start_degrees: 0, end_degrees: 360 } },
    } }
    const fetcher = vi.fn().mockResolvedValueOnce(response(ring)).mockResolvedValueOnce(response({ verification_token: 'token.ring', expires_in: 120 }))
    vi.stubGlobal('fetch', fetcher)
    const { thumb, shadow, handle } = await mount(310, ring)
    thumb.dispatchEvent(pointer('pointerdown', 10))
    thumb.dispatchEvent(pointer('pointermove', 10 + 266 * .3125))
    await nextTick()
    const piece = shadow.querySelector<HTMLElement>('.sl-piece')!
    expect(piece.style.left).toBe('0%')
    expect(piece.style.width).toBe('100%')
    expect(parseFloat(piece.style.transform.slice(7))).toBeCloseTo(193.5)
    expect(shadow.querySelector('.sl-scene')?.getAttribute('style')).toBeNull()
    expect(thumb.getAttribute('aria-label')).toBe('旋转进度')
    expect(shadow.querySelector('.sl-ring')).not.toBeNull()
    thumb.dispatchEvent(pointer('pointerup', 10 + 266 * .3125))
    await settle()
    expect(JSON.parse(fetcher.mock.calls[1][1].body).answer).toEqual({ progress: .3125 })
    expect(handle.getResponse()).toBe('token.ring')
  })

  it('cancels touch gestures and resize without submission; failed images disable interaction', async () => {
    let resized: () => void = () => {}
    const disconnect = vi.fn()
    vi.stubGlobal('ResizeObserver', class { constructor(callback: () => void) { resized = callback } observe() {} disconnect = disconnect })
    const fetcher = vi.fn().mockResolvedValueOnce(response(challenge))
    vi.stubGlobal('fetch', fetcher)
    const { thumb, shadow, onError, handle } = await mount()
    thumb.dispatchEvent(pointer('pointerdown', 10))
    thumb.dispatchEvent(pointer('pointermove', 160))
    thumb.dispatchEvent(pointer('pointercancel', 160))
    thumb.dispatchEvent(pointer('pointerup', 160))
    expect(fetcher).toHaveBeenCalledTimes(1)
    thumb.dispatchEvent(pointer('pointerdown', 10, 2, false))
    thumb.dispatchEvent(pointer('pointerup', 160, 2, false))
    expect(fetcher).toHaveBeenCalledTimes(1)
    thumb.dispatchEvent(pointer('pointerdown', 10))
    resized()
    thumb.dispatchEvent(pointer('pointerup', 160))
    await nextTick()
    expect(thumb.getAttribute('aria-valuenow')).toBe('0')
    expect(fetcher).toHaveBeenCalledTimes(1)
    shadow.querySelector('.sl-piece')!.dispatchEvent(new Event('error'))
    await nextTick()
    expect(thumb.disabled).toBe(true)
    expect(onError).toHaveBeenCalledWith('IMAGE_ERROR')
    handle.destroy()
    expect(disconnect).toHaveBeenCalled()
  })
})
