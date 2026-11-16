import { StrictMode, useRef, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { StarLock } from '@starlock/react'
import type { ChallengeType, VerificationResult } from '@starlock/core'

interface Session { site_key: string; session_ticket: string }

function Demo() {
  const [session, setSession] = useState<Session>()
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('选择题型，在弹窗中体验 React 组件。')
  const current = useRef(0)

  async function post(path: string, body: object) {
    const response = await fetch(path, {
      method: 'POST', credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
    })
    const data = await response.json()
    if (!response.ok) throw new Error(data.message || '请求失败')
    return data
  }

  async function prepare(kind: ChallengeType, source: 'preset' | 'procedural' = 'preset') {
    if (busy) return
    const request = ++current.current
    setBusy(true)
    setSession(undefined)
    setMessage('正在创建会话…')
    try {
      const result = await post('/demo/session', { challenge_type: kind,
        ...(kind === 'rotate' ? { rotation_source: source } : {}) })
      if (request === current.current) {
        setSession(result)
        setMessage('请完成弹窗中的验证。')
      }
    } catch (error) {
      setMessage(error instanceof Error ? error.message : '请求失败')
    } finally {
      setBusy(false)
    }
  }

  async function consume(result: VerificationResult, request: number) {
    if (request !== current.current) return
    setBusy(true)
    setMessage('正在进行服务端复核…')
    try {
      const response = await post('/demo/submit', { token: result.token })
      if (response.success !== true) throw new Error('验证结果不完整')
      setMessage('React 验证与服务端复核均已完成。')
    } catch (error) {
      setMessage(error instanceof Error ? error.message : '复核失败')
    } finally {
      setSession(undefined)
      setBusy(false)
    }
  }

  const request = current.current
  return (
    <div className="site-shell integration-page">
      <header className="site-header">
        <a className="brand" href="/"><img src="/brand/starlock.svg" alt="星锁 Logo" width="38" height="38" /><strong>StarLock<span>React 接入示例</span></strong></a>
        <a className="back-link" href="/">普通网页示例 ↗</a>
      </header>
      <main className="section-wrap react-demo">
        <h1>React 验证接入</h1>
        <p>同一份托管 SDK，支持弹窗、刷新与服务端复核。</p>
        <div className="react-demo-actions">
          <button className="primary-link" disabled={busy} onClick={() => void prepare('rotate')}>星梦预设 · 圆环旋转</button>
          <button className="primary-link" disabled={busy} onClick={() => void prepare('rotate', 'procedural')}>随机几何 · 圆环旋转</button>
          <button className="primary-link" disabled={busy} onClick={() => void prepare('text_click')}>文字顺序点选</button>
          <button className="primary-link" disabled={busy} onClick={() => void prepare('semantic_grid')}>语义九宫格</button>
          <button className="primary-link" disabled={busy} onClick={() => void prepare('digits')}>数字验证</button>
        </div>
        {session && <StarLock
          siteKey={session.site_key} sessionTicket={session.session_ticket}
          sdkUrl="http://127.0.0.1:8018/sdk/v1/api.js" autoOpen
          onSuccess={result => { void consume(result, request) }}
          onExpire={() => { setSession(undefined); setMessage('验证已过期，请选择题型重新开始。') }}
          onClose={() => setMessage('弹窗已收起，点击验证卡可继续。')}
          onError={code => setMessage(`验证提示：${code}`)}
        />}
        <p role="status" aria-live="polite">{message}</p>
      </main>
    </div>
  )
}

createRoot(document.querySelector('#root')!).render(<StrictMode><Demo /></StrictMode>)
