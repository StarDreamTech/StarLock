// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'
import { createRuntime } from './runtime'
import type { WidgetHandle } from './types'

const image = 'data:image/png;base64,test'
const base = { decision: 'challenge', challenge_id: 'ch_choice', expires_in: 120 }
const clickChallenge = { ...base, challenge_type: 'text_click', payload: {
  instruction: '请依次点击 星 → 月 → 山', image, image_width: 300, image_height: 180, required_clicks: 3,
} }
const gridChallenge = { ...base, challenge_type: 'semantic_grid', payload: {
  instruction: '请选择所有能在水上航行的交通工具', columns: 3,
  tiles: Array.from({ length: 9 }, (_, index) => ({ id: `tile_${index}`, image })),
} }
const response = (data: object, status = 200) => new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } })
const settle = async () => { await new Promise(resolve => setTimeout(resolve, 0)); await nextTick() }
const handles: WidgetHandle[] = []
afterEach(() => { handles.forEach(handle => handle.destroy()); handles.length = 0; document.body.innerHTML = ''; vi.unstubAllGlobals() })

async function mount(challenge: object) {
  const fetcher = vi.fn().mockResolvedValueOnce(response(challenge))
    .mockResolvedValueOnce(response({ error_code: 'ANSWER_INVALID', message: '请再试一次', attempts_remaining: 2 }, 400))
    .mockResolvedValueOnce(response({ verification_token: 'token.choice', expires_in: 120 }))
  vi.stubGlobal('fetch', fetcher)
  document.body.innerHTML = '<div id="captcha"></div>'
  const handle = createRuntime('https://verify.example/sdk/v1/api.js').render('#captcha', {
    displayMode: 'inline', siteKey: 'site_test', sessionTicket: 'ticket.test',
  })
  handles.push(handle)
  await settle()
  const shadow = document.querySelector('#captcha > div')!.shadowRoot!
  shadow.querySelectorAll('img').forEach(element => element.dispatchEvent(new Event('load')))
  await nextTick()
  return { fetcher, shadow, handle }
}

describe('choice challenge interactions', () => {
  it.each([200, 300])('normalizes ordered clicks at width %i, supports undo and preserves choices for retry', async width => {
    const { shadow, fetcher, handle } = await mount(clickChallenge)
    const board = shadow.querySelector<HTMLElement>('.sl-click-board')!
    const scene = board.querySelector('img')!
    vi.spyOn(scene, 'getBoundingClientRect').mockReturnValue({ left: 20, top: 40, width, height: width * .6 } as DOMRect)
    const select = (x: number, y: number) => board.dispatchEvent(new MouseEvent('click', {
      clientX: 20 + x * width, clientY: 40 + y * width * .6, bubbles: true,
    }))
    select(.1, .2); select(.4, .5); await nextTick()
    shadow.querySelector<HTMLButtonElement>('[aria-label="移除第 1 次点击"]')!.click()
    await nextTick()
    expect(shadow.querySelectorAll('.sl-click-marker')).toHaveLength(1)
    expect(shadow.querySelector('.sl-click-marker')!.textContent).toBe('1')
    select(.7, .8); select(.2, .3); select(.9, .9); await nextTick()
    expect(shadow.querySelectorAll('.sl-click-marker')).toHaveLength(3)
    shadow.querySelector('form')!.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }))
    await settle()
    const submitted = JSON.parse(fetcher.mock.calls[1][1].body).answer.points
    expect(submitted).toHaveLength(3)
    expect(submitted[0].x).toBeCloseTo(.4)
    expect(submitted[0].y).toBeCloseTo(.5)
    expect(submitted[1].x).toBeCloseTo(.7)
    expect(submitted[2].x).toBeCloseTo(.2)
    expect(shadow.querySelectorAll('.sl-click-marker')).toHaveLength(3)
    shadow.querySelector('form')!.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }))
    await settle()
    expect(handle.getResponse()).toBe('token.choice')
  })

  it('supports keyboard clicks, clears them on refresh and blocks failed image selection', async () => {
    const { shadow, fetcher } = await mount(clickChallenge)
    const board = shadow.querySelector<HTMLElement>('.sl-click-board')!
    for (const key of ['ArrowLeft', 'Enter', 'ArrowRight', 'Enter', 'Backspace']) {
      board.dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true, cancelable: true }))
    }
    await nextTick()
    expect(shadow.querySelectorAll('.sl-click-marker')).toHaveLength(1)
    fetcher.mockReset().mockResolvedValue(response({ ...clickChallenge, challenge_id: 'ch_new' }))
    shadow.querySelector<HTMLButtonElement>('[aria-label="换一题"]')!.click()
    await settle()
    expect(shadow.querySelectorAll('.sl-click-marker')).toHaveLength(0)
    const next = shadow.querySelector<HTMLElement>('.sl-click-board')!
    next.querySelector('img')!.dispatchEvent(new Event('error'))
    next.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true }))
    await nextTick()
    expect(shadow.querySelectorAll('.sl-click-marker')).toHaveLength(0)
    expect(shadow.querySelector<HTMLButtonElement>('[type=submit]')!.disabled).toBe(true)
  })

  it('toggles semantic tiles, clears selections and submits opaque ids through retry', async () => {
    const { shadow, fetcher, handle } = await mount(gridChallenge)
    const tile = (index: number) => shadow.querySelector<HTMLButtonElement>(`[aria-label="第 ${index} 张图片"]`)!
    tile(1).click(); tile(3).click(); await nextTick()
    expect(tile(1).getAttribute('aria-pressed')).toBe('true')
    tile(1).click(); await nextTick()
    expect(tile(1).getAttribute('aria-pressed')).toBe('false')
    tile(2).click(); await nextTick()
    shadow.querySelector('form')!.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }))
    await settle()
    expect(JSON.parse(fetcher.mock.calls[1][1].body).answer).toEqual({ tile_ids: ['tile_2', 'tile_1'] })
    expect(tile(3).getAttribute('aria-pressed')).toBe('true')
    Array.from(shadow.querySelectorAll('button')).find(button => button.textContent === '清空选择')!.click()
    await nextTick()
    expect(shadow.querySelector<HTMLButtonElement>('[type=submit]')!.disabled).toBe(true)
    tile(9).click(); await nextTick()
    shadow.querySelector('form')!.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }))
    await settle()
    expect(handle.getResponse()).toBe('token.choice')
  })
})
