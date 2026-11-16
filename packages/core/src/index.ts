export type TextChallengeType = 'text' | 'digits' | 'arithmetic'
export type SliderChallengeType = 'slider' | 'bezier_slider'
export type ChallengeType = TextChallengeType | SliderChallengeType | 'rotate' | 'text_click' | 'semantic_grid'
export interface Point { x: number; y: number }
export interface MotionPath { kind: 'linear' | 'cubic_bezier'; control_points: Point[] }
export type Easing = { kind: 'linear' } | { kind: 'cubic_bezier'; control_points: [Point, Point] }
export interface SliderMotion { easing: Easing; rotation: { start_degrees: number; end_degrees: number } }
export interface SliderAnswer { progress: number }
export interface ClickAnswer { points: Point[] }
export interface GridAnswer { tile_ids: string[] }
export type Answer = string | SliderAnswer | ClickAnswer | GridAnswer
export type Status = 'idle' | 'loading' | 'ready' | 'verifying' | 'success' | 'expired' | 'error' | 'destroyed'
interface ChallengeBase {
  decision: 'challenge'
  challenge_id: string
  expires_in: number
}
export interface TextChallenge extends ChallengeBase {
  challenge_type: TextChallengeType
  payload: { instruction: string; image: string; image_width: number; image_height: number; input_mode: 'text' | 'numeric' }
}
export interface SliderChallenge extends ChallengeBase {
  challenge_type: SliderChallengeType
  payload: { instruction: string; image: string; image_width: number; image_height: number;
    piece_image: string; piece_width: number; piece_height: number; path: MotionPath; motion?: SliderMotion }
}
export interface RotationChallenge extends ChallengeBase {
  challenge_type: 'rotate'
  payload: { instruction: string; image: string; image_width: number; image_height: number;
    piece_image: string; piece_width: number; piece_height: number; motion: SliderMotion }
}
export interface TextClickChallenge extends ChallengeBase {
  challenge_type: 'text_click'
  payload: { instruction: string; image: string; image_width: number; image_height: number; required_clicks: number }
}
export interface GridChallenge extends ChallengeBase {
  challenge_type: 'semantic_grid'
  payload: { instruction: string; columns: 3; tiles: { id: string; image: string }[] }
}
export type Challenge = TextChallenge | SliderChallenge | RotationChallenge | TextClickChallenge | GridChallenge

export function isTextClick(challenge: Challenge): challenge is TextClickChallenge {
  return challenge.challenge_type === 'text_click'
}
export function isGrid(challenge: Challenge): challenge is GridChallenge {
  return challenge.challenge_type === 'semantic_grid'
}

export function isSlider(challenge: Challenge): challenge is SliderChallenge | RotationChallenge {
  return challenge.challenge_type === 'slider' || challenge.challenge_type === 'bezier_slider' || challenge.challenge_type === 'rotate'
}
export function pathPoint(path: MotionPath, progress: number): Point {
  const u = Math.max(0, Math.min(1, progress))
  const weights = path.kind === 'linear' ? [1 - u, u] : [(1 - u) ** 3, 3 * (1 - u) ** 2 * u, 3 * (1 - u) * u ** 2, u ** 3]
  return path.control_points.reduce((point, value, index) => ({
    x: point.x + weights[index] * value.x, y: point.y + weights[index] * value.y,
  }), { x: 0, y: 0 })
}

export function easedProgress(easing: Easing | undefined, progress: number): number {
  const u = Math.max(0, Math.min(1, progress))
  if (!easing || easing.kind === 'linear' || u === 0 || u === 1) return u
  const [a, b] = easing.control_points
  let low = 0, high = 1
  for (let i = 0; i < 30; i++) {
    const t = (low + high) / 2
    const x = 3 * (1 - t) ** 2 * t * a.x + 3 * (1 - t) * t ** 2 * b.x + t ** 3
    if (x < u) low = t
    else high = t
  }
  const t = (low + high) / 2
  return 3 * (1 - t) ** 2 * t * a.y + 3 * (1 - t) * t ** 2 * b.y + t ** 3
}

export function motionState(payload: Pick<SliderChallenge['payload'], 'path' | 'motion'>, progress: number): Point & { angle: number } {
  const t = easedProgress(payload.motion?.easing, progress)
  const rotation = payload.motion?.rotation ?? { start_degrees: 0, end_degrees: 0 }
  return { ...pathPoint(payload.path, t), angle: rotation.start_degrees + t * (rotation.end_degrees - rotation.start_degrees) }
}

function validMotion(motion: SliderMotion | undefined): boolean {
  if (motion === undefined) return true // Existing 0.4 challenges keep linear timing and no rotation.
  const easing = motion?.easing, rotation = motion?.rotation
  if (!easing || !rotation || ![rotation.start_degrees, rotation.end_degrees].every(v => Number.isFinite(v) && Math.abs(v) <= 360) ||
      Math.abs(rotation.end_degrees - rotation.start_degrees) > 360) return false
  if (easing.kind === 'linear') return true
  return easing.kind === 'cubic_bezier' && Array.isArray(easing.control_points) && easing.control_points.length === 2 &&
    easing.control_points.every(p => p && [p.x, p.y].every(v => Number.isFinite(v) && v >= 0 && v <= 1)) &&
    easing.control_points[0].x <= easing.control_points[1].x && easing.control_points[0].y <= easing.control_points[1].y
}

function validChallenge(data: Challenge): boolean {
  const png = (value: unknown) => typeof value === 'string' && value.startsWith('data:image/png;base64,')
  const dimension = (value: number) => Number.isInteger(value) && value > 0 && value <= 2048
  if (data?.decision !== 'challenge' || typeof data.challenge_id !== 'string' || !data.challenge_id || !data.payload ||
      typeof data.payload.instruction !== 'string' ||
      !Number.isFinite(data.expires_in) || data.expires_in <= 0 || data.expires_in > 300) return false
  if (isGrid(data)) {
    const tiles = data.payload.tiles
    return data.payload.columns === 3 && Array.isArray(tiles) && tiles.length === 9 &&
      tiles.every(tile => tile && typeof tile.id === 'string' && tile.id.length > 0 && tile.id.length <= 80 &&
        (png(tile.image) || (typeof tile.image === 'string' && tile.image.startsWith('data:image/jpeg;base64,')))) &&
      new Set(tiles.map(tile => tile.id)).size === 9
  }
  const payload = data.payload
  if (!png(payload.image) || !dimension(payload.image_width) || !dimension(payload.image_height)) return false
  if (isTextClick(data)) return Number.isInteger(data.payload.required_clicks) && data.payload.required_clicks >= 1 && data.payload.required_clicks <= 6
  if (data.challenge_type === 'rotate') return png(data.payload.piece_image) && !!data.payload.motion && validMotion(data.payload.motion) &&
    payload.image_width === payload.image_height && data.payload.piece_width === payload.image_width && data.payload.piece_height === payload.image_height &&
    data.payload.motion.rotation.start_degrees === 0 && data.payload.motion.rotation.end_degrees === 360
  if (!isSlider(data)) return ['text', 'digits', 'arithmetic'].includes(data.challenge_type) && ['text', 'numeric'].includes(data.payload.input_mode)
  const slider = data.payload
  const path = slider.path
  return validMotion(slider.motion) && png(slider.piece_image) && dimension(slider.piece_width) && dimension(slider.piece_height) &&
    slider.piece_width < payload.image_width && slider.piece_height < payload.image_height &&
    path?.kind === (data.challenge_type === 'slider' ? 'linear' : 'cubic_bezier') &&
    Array.isArray(path.control_points) && path.control_points.length === (path.kind === 'linear' ? 2 : 4) &&
    path.control_points.every(point => point && Number.isFinite(point.x) && Number.isFinite(point.y) &&
      point.x >= 0 && point.x <= payload.image_width - slider.piece_width &&
      point.y >= 0 && point.y <= payload.image_height - slider.piece_height)
}
export interface State {
  status: Status
  challenge?: Challenge
  message: string
  errorCode?: string
  attemptsRemaining?: number
}
export interface VerificationResult { token: string; expiresIn: number }
export interface ClientOptions {
  siteKey: string
  sessionTicket: string
  apiBase?: string
  onSuccess?: (result: VerificationResult) => void
  onExpire?: () => void
}
export class StarLockError extends Error {
  constructor(public code: string, message: string, public attemptsRemaining?: number) { super(message) }
}

export class StarLockClient {
  state: State = { status: 'idle', message: '' }
  private listeners = new Set<(state: State) => void>()
  private controller?: AbortController
  private timer?: ReturnType<typeof setTimeout>
  private generation = 0
  private expiresAt = 0
  constructor(private options: ClientOptions, private transport?: typeof fetch) {}

  subscribe(listener: (state: State) => void) {
    this.listeners.add(listener)
    listener(this.state)
    return () => { this.listeners.delete(listener) }
  }
  private publish(next: State) {
    if (this.state.status === 'destroyed') return
    this.state = next
    this.listeners.forEach(listener => listener(next))
  }
  private armExpiry(seconds: number) {
    clearTimeout(this.timer)
    this.expiresAt = Date.now() + seconds * 1000
    this.timer = setTimeout(() => {
      this.generation++
      this.controller?.abort()
      this.publish({ ...this.state, status: 'expired', message: '验证已过期，请重新开始', errorCode: 'EXPIRED' })
      this.options.onExpire?.()
    }, seconds * 1000)
  }
  private async request(path: string, body: object, signal: AbortSignal) {
    let response: Response
    try {
      response = await (this.transport ?? fetch)((this.options.apiBase || '') + path, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, signal,
        credentials: 'omit', body: JSON.stringify({
          site_key: this.options.siteKey, session_ticket: this.options.sessionTicket, ...body,
        }),
      })
    } catch (error) {
      if (signal.aborted) throw error
      throw new StarLockError('NETWORK_ERROR', '网络连接失败，请稍后重试')
    }
    const data = await response.json().catch(() => null)
    if (!response.ok) {
      throw new StarLockError(data?.error_code || 'SERVICE_ERROR', data?.message || '验证服务暂时不可用', data?.attempts_remaining)
    }
    if (!data || typeof data !== 'object') throw new StarLockError('PROTOCOL_ERROR', '验证服务响应异常')
    return data
  }
  private begin(status: 'loading' | 'verifying') {
    if (this.state.status === 'destroyed') throw new StarLockError('DESTROYED', '组件已销毁')
    this.controller?.abort()
    this.controller = new AbortController()
    this.publish({ ...this.state, status, message: '' })
    return { generation: ++this.generation, signal: this.controller.signal }
  }
  private current(generation: number) { return generation === this.generation && this.state.status !== 'destroyed' }
  private fail(error: unknown) {
    const failure = error instanceof StarLockError ? error : new StarLockError('SERVICE_ERROR', '验证服务暂时不可用')
    const canRetryAnswer = failure.code === 'ANSWER_INVALID' && Date.now() < this.expiresAt
    this.publish({ ...this.state, status: canRetryAnswer ? 'ready' : 'error', message: failure.message,
      errorCode: failure.code, attemptsRemaining: failure.attemptsRemaining })
  }
  async initialize() {
    const operation = this.begin('loading')
    clearTimeout(this.timer)
    try {
      const data = await this.request('/v1/challenges', {}, operation.signal)
      if (!this.current(operation.generation)) return
      this.acceptChallenge(data)
    } catch (error) { if (this.current(operation.generation)) this.fail(error) }
  }
  private acceptChallenge(data: Challenge) {
    if (!validChallenge(data)) {
      throw new StarLockError('PROTOCOL_ERROR', '验证题目响应异常，请重试')
    }
    this.publish({ status: 'ready', challenge: data, message: '' })
    this.armExpiry(data.expires_in)
  }
  async refresh() {
    if (this.state.status === 'success') throw new StarLockError('NEW_SESSION_REQUIRED', '请创建新的验证会话')
    const previous = this.state.challenge?.challenge_id
    const operation = this.begin('loading')
    clearTimeout(this.timer)
    try {
      const data = await this.request('/v1/challenges', previous ? { replace_challenge_id: previous } : {}, operation.signal)
      if (!this.current(operation.generation)) return
      this.acceptChallenge(data)
    } catch (error) { if (this.current(operation.generation)) this.fail(error) }
  }
  async verify(answer: Answer) {
    if (this.state.status !== 'ready' || !this.state.challenge) return
    const challenge = this.state.challenge
    let valid: boolean
    if (isTextClick(challenge)) {
      valid = typeof answer === 'object' && answer !== null && 'points' in answer && Array.isArray(answer.points) &&
        answer.points.length === challenge.payload.required_clicks && answer.points.every(point => point &&
          [point.x, point.y].every(value => Number.isFinite(value) && value >= 0 && value <= 1))
    } else if (isGrid(challenge)) {
      const ids = new Set(challenge.payload.tiles.map(tile => tile.id))
      valid = typeof answer === 'object' && answer !== null && 'tile_ids' in answer && Array.isArray(answer.tile_ids) &&
        answer.tile_ids.length > 0 && answer.tile_ids.length <= 9 && new Set(answer.tile_ids).size === answer.tile_ids.length &&
        answer.tile_ids.every(id => ids.has(id))
    } else if (isSlider(challenge)) {
      valid = typeof answer === 'object' && answer !== null && 'progress' in answer &&
        Number.isFinite(answer.progress) && answer.progress >= 0 && answer.progress <= 1
    } else valid = typeof answer === 'string' && !!answer.trim()
    if (!valid) {
      const message = isTextClick(challenge) || isGrid(challenge) ? '请按提示完成选择' : isSlider(challenge) ? '请先调整拼图位置' : '请先输入答案'
      this.publish({ ...this.state, message })
      return
    }
    const challengeId = this.state.challenge.challenge_id
    const operation = this.begin('verifying')
    try {
      const data = await this.request(`/v1/challenges/${encodeURIComponent(challengeId)}/verify`, { answer }, operation.signal)
      if (!this.current(operation.generation)) return
      if (typeof data.verification_token !== 'string' || !data.verification_token || !Number.isFinite(data.expires_in) ||
          data.expires_in <= 0 || data.expires_in > 300) throw new StarLockError('PROTOCOL_ERROR', '验证结果响应异常')
      this.publish({ status: 'success', message: '验证通过' })
      this.armExpiry(data.expires_in)
      this.options.onSuccess?.({ token: data.verification_token, expiresIn: data.expires_in })
    } catch (error) { if (this.current(operation.generation)) this.fail(error) }
  }
  async reset(sessionTicket?: string) {
    if (sessionTicket) {
      this.options = { ...this.options, sessionTicket }
      this.publish({ status: 'idle', message: '' })
      return this.initialize()
    }
    return this.refresh()
  }
  destroy() {
    if (this.state.status === 'destroyed') return
    this.generation++
    this.controller?.abort()
    clearTimeout(this.timer)
    this.publish({ status: 'destroyed', message: '' })
    this.listeners.clear()
  }
}
