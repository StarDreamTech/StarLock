import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { easedProgress, motionState, pathPoint, StarLockClient } from './index'
import type { SliderChallenge } from './index'
import sharedMotion from '../../../fixtures/slider-motion.json?raw'

const challenge = { decision: 'challenge', challenge_id: 'ch_123', challenge_type: 'digits', expires_in: 120,
  payload: { instruction: '输入数字', image: 'data:image/png;base64,test', image_width: 280, image_height: 88, input_mode: 'numeric' } }
const response = (data: object, status = 200) => new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } })
const options = { siteKey: 'site_test', sessionTicket: 'ticket.test' }
describe('StarLockClient lifecycle', () => {
  const clients: StarLockClient[] = []
  const create = (extra = {}) => { const client = new StarLockClient({ ...options, ...extra }); clients.push(client); return client }
  beforeEach(() => { vi.useFakeTimers() })
  afterEach(() => { clients.forEach(client => client.destroy()); clients.length = 0; vi.unstubAllGlobals(); vi.useRealTimers() })

  it('initializes, refreshes the exact challenge, verifies once and expires', async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(response(challenge))
      .mockResolvedValueOnce(response({ ...challenge, challenge_id: 'ch_new' }))
      .mockResolvedValueOnce(response({ verification_token: 'token.secret', expires_in: 10 }))
    vi.stubGlobal('fetch', fetcher)
    const onSuccess = vi.fn(), onExpire = vi.fn()
    const client = create({ onSuccess, onExpire })
    await client.initialize()
    expect(client.state.status).toBe('ready')
    await client.refresh()
    expect(JSON.parse(fetcher.mock.calls[1][1].body).replace_challenge_id).toBe('ch_123')
    await client.verify('23456')
    expect(client.state.status).toBe('success')
    expect(onSuccess).toHaveBeenCalledExactlyOnceWith({ token: 'token.secret', expiresIn: 10 })
    await client.verify('23456')
    expect(fetcher).toHaveBeenCalledTimes(3)
    vi.advanceTimersByTime(10000)
    expect(client.state.status).toBe('expired')
    expect(onExpire).toHaveBeenCalledTimes(1)
  })

  it('keeps an incorrect answer retryable, then locks after attempts are exhausted', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(response(challenge))
      .mockResolvedValueOnce(response({ error_code: 'ANSWER_INVALID', message: '答案错误', attempts_remaining: 2 }, 400))
      .mockResolvedValueOnce(response({ error_code: 'ATTEMPTS_EXCEEDED', message: '请刷新' }, 429)))
    const client = create()
    await client.initialize()
    await client.verify('wrong')
    expect(client.state.status).toBe('ready')
    expect(client.state.attemptsRemaining).toBe(2)
    await client.verify('wrong')
    expect(client.state.status).toBe('error')
  })

  it('discards a late response after destroy', async () => {
    let resolve: (value: Response) => void = () => {}
    vi.stubGlobal('fetch', vi.fn(() => new Promise<Response>(done => { resolve = done })))
    const onSuccess = vi.fn()
    const client = create({ onSuccess })
    const pending = client.initialize()
    client.destroy()
    resolve(response(challenge))
    await pending
    expect(client.state.status).toBe('destroyed')
    expect(onSuccess).not.toHaveBeenCalled()
    expect(vi.getTimerCount()).toBe(0)
  })

  it('ignores stale responses when reset starts a newer request', async () => {
    let resolve: (value: Response) => void = () => {}
    const fetcher = vi.fn().mockImplementationOnce(() => new Promise<Response>(done => { resolve = done }))
      .mockResolvedValueOnce(response({ ...challenge, challenge_id: 'ch_latest' }))
    vi.stubGlobal('fetch', fetcher)
    const client = create()
    const old = client.initialize()
    await client.reset('new.ticket')
    resolve(response(challenge))
    await old
    expect(client.state.challenge?.challenge_id).toBe('ch_latest')
    expect(JSON.parse(fetcher.mock.calls[1][1].body).session_ticket).toBe('new.ticket')
  })

  it('handles network failures and invalid payloads explicitly', async () => {
    const fetcher = vi.fn().mockRejectedValueOnce(new TypeError('offline'))
      .mockResolvedValueOnce(response({ decision: 'pass' }))
    vi.stubGlobal('fetch', fetcher)
    const client = create()
    await client.initialize()
    expect(client.state.errorCode).toBe('NETWORK_ERROR')
    await client.initialize()
    expect(client.state.errorCode).toBe('PROTOCOL_ERROR')
  })

  it('validates motion paths and submits only normalized progress for a slider', async () => {
    const slider = { ...challenge, challenge_type: 'bezier_slider', payload: {
      instruction: '拖动', image: challenge.payload.image, image_width: 320, image_height: 180,
      piece_image: challenge.payload.image, piece_width: 56, piece_height: 56,
      path: { kind: 'cubic_bezier' as const, control_points: [{ x: 0, y: 0 }, { x: 0, y: 100 }, { x: 100, y: 100 }, { x: 100, y: 0 }] },
    } }
    expect(pathPoint(slider.payload.path, .5)).toEqual({ x: 50, y: 75 })
    const fetcher = vi.fn().mockResolvedValueOnce(response(slider))
      .mockResolvedValueOnce(response({ verification_token: 'token.slider', expires_in: 120 }))
      .mockResolvedValueOnce(response({ ...slider, payload: { ...slider.payload, path: { ...slider.payload.path,
        control_points: [{ x: 99999, y: 0 }, ...slider.payload.path.control_points.slice(1)] } } }))
    vi.stubGlobal('fetch', fetcher)
    const client = create()
    await client.initialize()
    expect(client.state.status).toBe('ready')
    await client.verify('0.5')
    await client.verify({ progress: NaN })
    expect(fetcher).toHaveBeenCalledTimes(1)
    await client.verify({ progress: .5 })
    expect(JSON.parse(fetcher.mock.calls[1][1].body).answer).toEqual({ progress: .5 })
    expect(client.state.status).toBe('success')
    await client.reset('ticket.other')
    expect(client.state.errorCode).toBe('PROTOCOL_ERROR')
  })

  it('matches shared CSS easing vectors instead of treating input as the curve parameter', () => {
    const fixtures = JSON.parse(sharedMotion) as { name: string; progress: number;
      payload: Pick<SliderChallenge['payload'], 'path' | 'motion'>; expected: { x: number; y: number; angle: number } }[]
    for (const fixture of fixtures) {
      const actual = motionState(fixture.payload, fixture.progress)
      for (const key of ['x', 'y', 'angle'] as const) expect(actual[key], fixture.name).toBeCloseTo(fixture.expected[key], 5)
    }
    const easing = fixtures[1].payload.motion!.easing
    expect(easedProgress(easing, -1)).toBe(0)
    expect(easedProgress(easing, 2)).toBe(1)
    expect(easedProgress(easing, .3125)).toBeCloseTo(.5375)
  })

  it('rejects unsafe easing and rotation payloads before rendering', async () => {
    const valid = { ...challenge, challenge_type: 'slider', payload: {
      instruction: '拖动', image: challenge.payload.image, image_width: 320, image_height: 180,
      piece_image: challenge.payload.image, piece_width: 64, piece_height: 64,
      path: { kind: 'linear', control_points: [{ x: 8, y: 50 }, { x: 248, y: 50 }] },
    } }
    const rotation = { start_degrees: -80, end_degrees: 60 }
    for (const motion of [null, {}, { easing: { kind: 'unknown' }, rotation },
      { easing: { kind: 'linear' }, rotation: { start_degrees: -360, end_degrees: 360 } },
      { easing: { kind: 'cubic_bezier', control_points: [{ x: .25, y: -.1 }, { x: .5, y: 1 }] }, rotation },
      { easing: { kind: 'cubic_bezier', control_points: [{ x: .8, y: 0 }, { x: .2, y: 1 }] }, rotation },
      { easing: { kind: 'cubic_bezier', control_points: [] }, rotation }]) {
      vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response({ ...valid, payload: { ...valid.payload, motion } })))
      const client = create()
      await client.initialize()
      expect(client.state.errorCode).toBe('PROTOCOL_ERROR')
    }
  })

  it('rejects a malformed ring before it can render an inconsistent rotation', async () => {
    const ring = { ...challenge, challenge_type: 'rotate', payload: { instruction: '旋转', image: challenge.payload.image,
      piece_image: challenge.payload.image, image_width: 256, image_height: 256, piece_width: 256, piece_height: 256,
      motion: { easing: { kind: 'linear' }, rotation: { start_degrees: 0, end_degrees: 360 } },
    } }
    for (const payload of [{ ...ring.payload, motion: undefined }, { ...ring.payload, image_height: 180 },
      { ...ring.payload, piece_width: 64 }, { ...ring.payload, motion: { ...ring.payload.motion, rotation: { start_degrees: 0, end_degrees: 720 } } }]) {
      vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response({ ...ring, payload })))
      const client = create()
      await client.initialize()
      expect(client.state.errorCode).toBe('PROTOCOL_ERROR')
    }
  })
  it('validates ordered click coordinates and submits the exact sequence', async () => {
    const value = { ...challenge, challenge_type: 'text_click', payload: { ...challenge.payload, required_clicks: 3 } }
    const fetcher = vi.fn().mockResolvedValueOnce(response(value))
      .mockResolvedValueOnce(response({ verification_token: 'token.click', expires_in: 120 }))
    vi.stubGlobal('fetch', fetcher)
    const client = create()
    await client.initialize()
    await client.verify({ points: [{ x: .2, y: .3 }] })
    await client.verify({ points: [{ x: NaN, y: .2 }, { x: .5, y: .5 }, { x: 1, y: 0 }] })
    expect(fetcher).toHaveBeenCalledTimes(1)
    const points = [{ x: .2, y: .3 }, { x: .5, y: .8 }, { x: .7, y: .5 }]
    await client.verify({ points })
    expect(JSON.parse(fetcher.mock.calls[1][1].body).answer).toEqual({ points })
    expect(client.state.status).toBe('success')
  })

  it('rejects duplicate grid ids, unknown selections and malformed tile images', async () => {
    const tiles = Array.from({ length: 9 }, (_, i) => ({ id: `tile_${i}`, image: challenge.payload.image }))
    const value = { ...challenge, challenge_type: 'semantic_grid', payload: { instruction: '选择图片', columns: 3, tiles } }
    const fetcher = vi.fn().mockResolvedValueOnce(response(value))
      .mockResolvedValueOnce(response({ verification_token: 'token.grid', expires_in: 120 }))
      .mockResolvedValueOnce(response({ ...value, payload: { ...value.payload, tiles: tiles.map(() => tiles[0]) } }))
      .mockResolvedValueOnce(response({ ...value, payload: { ...value.payload, tiles: tiles.map(t => ({ ...t, image: 'https://unexpected.example/image' })) } }))
    vi.stubGlobal('fetch', fetcher)
    const client = create()
    await client.initialize()
    for (const tile_ids of [[], ['unknown'], ['tile_1', 'tile_1']]) await client.verify({ tile_ids })
    expect(fetcher).toHaveBeenCalledTimes(1)
    await client.verify({ tile_ids: ['tile_3', 'tile_1'] })
    expect(JSON.parse(fetcher.mock.calls[1][1].body).answer).toEqual({ tile_ids: ['tile_3', 'tile_1'] })
    await client.reset('ticket.new')
    expect(client.state.errorCode).toBe('PROTOCOL_ERROR')
    await client.reset('ticket.other')
    expect(client.state.errorCode).toBe('PROTOCOL_ERROR')
  })

})
