import { easedProgress, motionState } from '@starlock/core'
import type { Answer, Challenge, ChallengeType, Point } from '@starlock/core'

interface RotationSolution {
  target_angle: number
  angle_tolerance: number
  rotation_period: number
}
interface SliderSolution extends RotationSolution {
  target_x: number
  target_y: number
  tolerance: number
}
interface ClickSolution { targets: Point[]; radius: number }
interface GridSolution { tile_ids: string[] }
export interface DemoSample {
  challenge: Challenge
  answer: string
  solution: RotationSolution | SliderSolution | ClickSolution | GridSolution | null
}

function matches(sample: DemoSample, answer: Answer): boolean {
  const { challenge, solution } = sample
  if (!solution) return typeof answer === 'string' && answer.trim().toUpperCase() === sample.answer
  if (!answer || typeof answer !== 'object') return false
  if (challenge.challenge_type === 'text_click' && 'targets' in solution && 'points' in answer) {
    return Array.isArray(answer.points) && answer.points.length === solution.targets.length && answer.points.every((point, index) => {
      const target = solution.targets[index]
      return Number.isFinite(point.x) && Number.isFinite(point.y) &&
        Math.hypot((point.x - target.x) * challenge.payload.image_width, (point.y - target.y) * challenge.payload.image_height) <= solution.radius
    })
  }
  if (challenge.challenge_type === 'semantic_grid' && 'tile_ids' in solution && 'tile_ids' in answer) {
    return Array.isArray(answer.tile_ids) && answer.tile_ids.length === solution.tile_ids.length &&
      new Set(answer.tile_ids).size === answer.tile_ids.length && answer.tile_ids.every(id => solution.tile_ids.includes(id))
  }
  if (!('progress' in answer) || !('target_angle' in solution) || !Number.isFinite(answer.progress) || answer.progress < 0 || answer.progress > 1) return false
  let angle: number
  if (challenge.challenge_type === 'rotate') {
    angle = easedProgress(challenge.payload.motion.easing, answer.progress) * 360
  } else if ((challenge.challenge_type === 'slider' || challenge.challenge_type === 'bezier_slider') && 'target_x' in solution) {
    const position = motionState(challenge.payload, answer.progress)
    if (Math.hypot(position.x - solution.target_x, position.y - solution.target_y) > solution.tolerance) return false
    angle = position.angle
  } else return false
  const period = solution.rotation_period
  const distance = Math.abs(((angle - solution.target_angle) % period + period * 1.5) % period - period / 2)
  return distance <= solution.angle_tolerance
}

export function createDemoTransport(kind: ChallengeType, samples: DemoSample[] | (() => Promise<DemoSample>)) {
  const choices = Array.isArray(samples) ? samples.filter(sample => sample.challenge.challenge_type === kind) : []
  if (Array.isArray(samples) && !choices.length) throw new Error('此题型暂时没有演示题，请重新加载')
  const sessionTicket = 'demo_only.' + crypto.randomUUID()
  let active: { sample: DemoSample; id: string; expiresAt: number; attempts: number } | undefined
  let previousIndex = -1
  let passed = false
  const reply = (data: object, status = 200) => new Response(JSON.stringify(data), {
    status, headers: { 'Content-Type': 'application/json' },
  })
  const failure = (code: string, message: string, status: number, details = {}) => reply({ error_code: code, message, ...details }, status)
  const publicChallenge = () => ({ ...active!.sample.challenge, challenge_id: active!.id,
    expires_in: Math.max(1, Math.floor((active!.expiresAt - Date.now()) / 1000)) })

  // This transport is bundled only by the public playground. Sample answers are intentionally public.
  const transport: typeof fetch = async (input, init) => {
    const request = new Request(input, init)
    const body = await request.json()
    if (request.signal.aborted) throw new DOMException('Aborted', 'AbortError')
    if (request.method !== 'POST' || body.session_ticket !== sessionTicket) return failure('SESSION_INVALID', '请重新选择一种验证方式', 403)
    if (passed) return failure('SESSION_CLOSED', '本次体验已完成，请再试一次', 409)
    const path = new URL(request.url).pathname
    if (path.endsWith('/v1/challenges')) {
      if (active && body.replace_challenge_id === undefined && active.expiresAt > Date.now() && active.attempts < 3) return reply(publicChallenge())
      if (active && body.replace_challenge_id !== active.id) return failure('CHALLENGE_REPLACED', '请刷新当前题目', 409)
      let sample: DemoSample
      if (typeof samples === 'function') sample = await samples()
      else {
        let index = Math.floor(Math.random() * choices.length)
        if (choices.length > 1 && index === previousIndex) index = (index + 1) % choices.length
        previousIndex = index
        sample = choices[index]
      }
      if (request.signal.aborted) throw new DOMException('Aborted', 'AbortError')
      if (sample.challenge.challenge_type !== kind) throw new Error('演示题型不匹配，请重新加载')
      active = { sample, id: 'demo_' + crypto.randomUUID(), expiresAt: Date.now() + 120000, attempts: 0 }
      return reply(publicChallenge())
    }
    const verification = path.match(/\/v1\/challenges\/([^/]+)\/verify$/)
    if (!verification || !active || verification[1] !== active.id) return failure('CHALLENGE_REPLACED', '题目已更新，请使用新题', 409)
    if (active.expiresAt <= Date.now()) return failure('CHALLENGE_EXPIRED', '题目已过期，请刷新', 410)
    if (active.attempts >= 3) return failure('ATTEMPTS_EXCEEDED', '请换一题继续体验', 429)
    if (!matches(active.sample, body.answer)) {
      active.attempts++
      const remaining = 3 - active.attempts
      return failure(remaining ? 'ANSWER_INVALID' : 'ATTEMPTS_EXCEEDED', remaining ? '还差一点，请再试一次' : '请换一题继续体验', remaining ? 400 : 429, { attempts_remaining: remaining })
    }
    passed = true
    return reply({ verification_token: 'demo_only.' + crypto.randomUUID(), expires_in: 120 })
  }
  return { sessionTicket, transport }
}
