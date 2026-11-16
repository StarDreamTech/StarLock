import { afterEach, describe, expect, it, vi } from 'vitest'
import { readFileSync } from 'node:fs'
import { easedProgress, motionState, StarLockClient } from '@starlock/core'
import type { Answer } from '@starlock/core'
import { createDemoTransport } from './transport'
import type { DemoSample } from './transport'

const samples = JSON.parse(readFileSync(new URL('../public/challenges.json', import.meta.url), 'utf8')) as DemoSample[]
const clients: StarLockClient[] = []
function solve(sample: DemoSample): Answer {
  if (!sample.solution) return sample.answer
  if ('targets' in sample.solution) return { points: sample.solution.targets }
  if ('tile_ids' in sample.solution) return { tile_ids: sample.solution.tile_ids }
  const solution = sample.solution
  let low = 0, high = 1
  for (let index = 0; index < 40; index++) {
    const progress = (low + high) / 2
    const challenge = sample.challenge
    if (challenge.challenge_type === 'rotate') {
      if (easedProgress(challenge.payload.motion.easing, progress) * 360 < solution.target_angle) low = progress
      else high = progress
    } else if ((challenge.challenge_type === 'slider' || challenge.challenge_type === 'bezier_slider') && 'target_x' in solution) {
      if (motionState(challenge.payload, progress).x < solution.target_x) low = progress
      else high = progress
    }
  }
  return { progress: (low + high) / 2 }
}
function create(bank: DemoSample[]) {
  const session = createDemoTransport(bank[0].challenge.challenge_type, bank)
  const client = new StarLockClient({ siteKey: 'site_demo_only', sessionTicket: session.sessionTicket,
    apiBase: 'https://demo.invalid/demo-api' }, session.transport)
  clients.push(client)
  return { client, session }
}
afterEach(() => { clients.forEach(client => client.destroy()); clients.length = 0; vi.unstubAllGlobals(); vi.useRealTimers() })

describe('public static playground', () => {
  it('loads one sample on demand and requests a new one only when refreshing', async () => {
    const bank = samples.filter(sample => sample.challenge.challenge_type === 'text_click')
    const load = vi.fn().mockResolvedValueOnce(bank[0]).mockResolvedValueOnce(bank[1])
    const session = createDemoTransport('text_click', load)
    const client = new StarLockClient({ siteKey: 'site_demo_only', sessionTicket: session.sessionTicket,
      apiBase: 'https://demo.invalid/demo-api' }, session.transport)
    clients.push(client)
    expect(load).not.toHaveBeenCalled()
    await client.initialize()
    expect(load).toHaveBeenCalledTimes(1)
    const first = client.state.challenge
    await client.refresh()
    expect(load).toHaveBeenCalledTimes(2)
    expect(client.state.challenge?.challenge_id).not.toBe(first?.challenge_id)
    await client.verify(solve(bank[1]))
    expect(client.state.status).toBe('success')
  })

  it('completes every exported sample through the shared client without a network request', async () => {
    const network = vi.fn(() => { throw new Error('Unexpected live API request') })
    vi.stubGlobal('fetch', network)
    expect(samples).toHaveLength(32)
    expect(new Set(samples.map(sample => sample.challenge.challenge_type)).size).toBe(8)
    for (const sample of samples) {
      const { client } = create([sample])
      await client.initialize()
      expect(client.state.status).toBe('ready')
      const wrong: Answer = !sample.solution ? 'incorrect' : 'targets' in sample.solution
        ? { points: sample.solution.targets.map(() => ({ x: 0, y: 0 })) } : 'tile_ids' in sample.solution
          ? { tile_ids: sample.challenge.challenge_type === 'semantic_grid' ? sample.challenge.payload.tiles.map(tile => tile.id) : [] } : { progress: 0 }
      await client.verify(wrong)
      expect(client.state.status).toBe('ready')
      expect(client.state.attemptsRemaining).toBe(2)
      await client.verify(solve(sample))
      expect(client.state.status).toBe('success')
    }
    expect(network).not.toHaveBeenCalled()
  })

  it('locks failed answers, refreshes to another sample and rejects the replaced challenge', async () => {
    const bank = samples.filter(sample => sample.challenge.challenge_type === 'digits')
    const { client, session } = create(bank)
    await client.initialize()
    const old = client.state.challenge!
    for (let index = 0; index < 3; index++) await client.verify('incorrect')
    expect(client.state.errorCode).toBe('ATTEMPTS_EXCEEDED')
    await client.refresh()
    expect(client.state.status).toBe('ready')
    expect('image' in client.state.challenge!.payload && client.state.challenge!.payload.image).not.toBe('image' in old.payload && old.payload.image)
    const stale = await session.transport('https://demo.invalid/demo-api/v1/challenges/' + old.challenge_id + '/verify', {
      method: 'POST', body: JSON.stringify({ session_ticket: session.sessionTicket, answer: bank[0].answer }),
    })
    expect(stale.status).toBe(409)
  })

  it('expires a sample and permits a fresh challenge in the same demo session', async () => {
    vi.useFakeTimers()
    const { client } = create(samples.filter(sample => sample.challenge.challenge_type === 'rotate'))
    await client.initialize()
    const old = client.state.challenge!.challenge_id
    vi.advanceTimersByTime(120001)
    expect(client.state.status).toBe('expired')
    await client.refresh()
    expect(client.state.status).toBe('ready')
    expect(client.state.challenge!.challenge_id).not.toBe(old)
  })
})
