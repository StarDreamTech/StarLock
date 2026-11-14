<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { StarLock } from '@starlock/vue'
import BrandOrbit from './BrandOrbit.vue'
import type { ChallengeType, VerificationResult } from '@starlock/core'
import integrationExample from '../../../docs/examples/VueIntegration.vue?raw'
import hostedExample from '../../../docs/examples/HostedIntegration.html?raw'
const integrationMode = ref<'html' | 'vue'>('html')

const kinds: { type: ChallengeType; name: string; description: string; hint: string; icon: string }[] = [
  { type: 'rotate', name: '圆环旋转', description: '旋转内圈，找回画面原本的模样。', hint: '拖动旋转内圈，留意模糊交界两侧的图案。', icon: 'M20 12a8 8 0 1 1-3-6m3-3v5h-5M8 12a4 4 0 1 0 4-4' },
  { type: 'bezier_slider', name: '曲线拼图', description: '沿着曲线，找到位置与角度的交点。', hint: '拖动图形，让位置和角度同时贴合。', icon: 'M4 17C7 3 17 3 20 17M4 17l-1-5m1 5 5-1M17 7l3 2-1-4' },
  { type: 'slider', name: '旋转滑块', description: '直线、变速，还有一点旋转的乐趣。', hint: '留意旋转，只有一个缺口能够贴合。', icon: 'M4 12h16m-4-4 4 4-4 4M8 5l3 2-3 2M8 19l-3-2 3-2' },
  { type: 'digits', name: '数字验证', description: '熟悉的数字，也是一种轻巧的选择。', hint: '输入图片中的数字，确认即可完成。', icon: '' },
  { type: 'text', name: '字符验证', description: '从字符里，找回清晰的答案。', hint: '输入图片中的字符，字母不区分大小写。', icon: '' },
  { type: 'arithmetic', name: '算术验证', description: '用一道小算式，开启一次交互。', hint: '算出图片中的结果，输入后确认。', icon: '' },
]
const selected = ref<ChallengeType>('rotate')
const selectedKind = computed(() => kinds.find(item => item.type === selected.value)!)
const phase = ref<'loading' | 'challenge' | 'checking' | 'success' | 'expired' | 'error'>('loading')
const session = ref<{ site_key: string; session_ticket: string;
  onSuccess: (result: VerificationResult) => void; onExpire: () => void }>()
const message = ref('')
const showPopup = ref(false)
const widget = ref<InstanceType<typeof StarLock>>()
const controller = new AbortController()
let operation = 0
let activeRequest = false, pendingStart = false, disposed = false
async function post(path: string, data: object) {
  const response = await fetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json' },
    credentials: 'same-origin', signal: controller.signal, body: JSON.stringify(data) })
  const result = await response.json()
  if (!response.ok) throw new Error(result.message || '验证服务暂时不可用')
  return result
}
function start(open = true) {
  showPopup.value = open
  operation++
  pendingStart = true
  session.value = undefined
  phase.value = 'loading'
  message.value = ''
  void prepare()
}
function choose(kind: ChallengeType) {
  if (selected.value === kind && (phase.value === 'loading' || phase.value === 'challenge')) {
    showPopup.value = true
    widget.value?.open()
    return
  }
  selected.value = kind
  start()
}
async function prepare() {
  if (activeRequest || disposed) return
  activeRequest = true
  try {
    // Demo requests share a context cookie: serialize them and keep only the latest selection.
    while (pendingStart && !disposed) {
      pendingStart = false
      const current = operation
      try {
        const result = await post('/demo/session', { challenge_type: selected.value })
        if (current !== operation || disposed) continue
        session.value = { ...result, onSuccess: value => { void submit(value, current) },
          onExpire: () => {
            if (current !== operation || disposed || phase.value !== 'challenge') return
            session.value = undefined
            phase.value = 'expired'
          } }
        phase.value = 'challenge'
      } catch (error) {
        if (current !== operation || disposed) continue
        phase.value = 'error'
        message.value = error instanceof Error ? error.message : '暂时无法加载验证'
      }
    }
  } finally { activeRequest = false }
}
async function submit(result: VerificationResult, current: number) {
  if (disposed || current !== operation || phase.value !== 'challenge') return
  phase.value = 'checking'
  activeRequest = true
  try {
    const verification = await post('/demo/submit', { token: result.token })
    if (verification.success !== true) throw new Error('验证结果不完整，请重新体验')
    if (current !== operation || disposed) return
    session.value = undefined
    phase.value = 'success'
  } catch (error) {
    if (current !== operation || disposed) return
    session.value = undefined
    phase.value = 'error'
    message.value = error instanceof Error ? error.message : '确认失败，请重新体验'
  } finally {
    activeRequest = false
    if (pendingStart && !disposed) void prepare()
  }
}
onMounted(() => start(location.hash === '#experience'))
onBeforeUnmount(() => { disposed = true; operation++; controller.abort() })
</script>

<template>
  <div class="site-shell">
    <header class="site-header">
      <a class="brand" href="#"><img src="/brand/starlock.svg" alt="星锁项目 Logo" width="38" height="38" /><strong>StarLock<span>星锁 · 星梦科技</span></strong></a>
      <nav aria-label="主导航"><a href="#experience">交互体验</a><a href="#integration">开发接入</a><a href="#architecture">产品架构</a><a href="#visuals">品牌素材</a></nav>
      <a class="header-cta" href="#experience" @click.prevent="choose('rotate')">体验验证 <span>↗</span></a>
    </header>

    <main>
      <section class="hero">
        <div class="hero-copy"><p class="eyebrow"><span class="status-dot"></span> STARLOCK / THE HUMAN SIGNAL</p>
          <h1>为真实，<br /><em>留一束光。</em></h1>
          <p class="hero-description">在复杂的数字世界，辨认真正的交互。<br />让验证有边界，也让体验有余地。</p>
          <div class="hero-actions"><a class="primary-link" href="#experience" @click.prevent="choose('rotate')">唤醒一次验证 <span>↗</span></a><a class="secondary-link" href="#integration">从这里接入 <span>→</span></a></div>
          <div class="hero-meta"><span>独立验证服务</span><span class="meta-line"></span><span>六种交互，随手一试</span></div>
        </div>
        <figure class="hero-visual"><BrandOrbit /><figcaption><span>INTUITION MEETS VERIFICATION.</span><span>一道星形，留给真实。</span></figcaption></figure>
        <span class="hero-index" aria-hidden="true">HUMAN<br />BY NATURE.</span>
      </section>

      <section id="experience" class="experience section-wrap">
        <div class="section-kicker"><span>01 / THE PLAYGROUND</span><span>保持直觉。保持好奇。</span></div>
        <div class="experience-layout">
          <div class="experience-copy"><p class="eyebrow">可信，也可以很有趣。</p><h2>动手，<br /><em>唤醒真实。</em></h2>
            <p>选一种交互，挑战即刻在弹窗中展开。<br />让图形归位，不挤占你的页面。</p>
            <div class="type-options" aria-label="验证方式">
              <button v-for="item in kinds.slice(0, 3)" :key="item.type" :class="{ active: selected === item.type }" :aria-label="item.name" :aria-pressed="selected === item.type" @click="choose(item.type)">
                <span class="type-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path :d="item.icon" /></svg></span>
                <span class="type-copy"><strong>{{ item.name }}<small v-if="item.type === 'rotate'" class="recommended">推荐体验</small></strong><span>{{ item.description }}</span></span><span class="type-arrow" aria-hidden="true">↗</span>
              </button>
            </div>
            <div class="basic-options"><span>也可以简单一点</span><div aria-label="基础验证方式"><button v-for="item in kinds.slice(3)" :key="item.type" :aria-pressed="selected === item.type" @click="choose(item.type)">{{ item.name }}<span aria-hidden="true">↗</span></button></div></div>
          </div>
          <div class="experience-stage">
            <div class="stage-label"><div><span class="live-label"><i></i> A MOMENT OF TRUST</span><h3>{{ selectedKind.name }}</h3></div><button type="button" :disabled="phase === 'loading'" aria-label="重新体验当前题型" @click="start()"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><path d="M20 7v5h-5M4 17v-5h5M5.5 7a7 7 0 0 1 11.7-1L20 9M4 15l2.8 3A7 7 0 0 0 18.5 17" /></svg>换一组</button></div>
            <div class="stage-art" aria-hidden="true"><div class="stage-orbit"></div><svg viewBox="0 0 120 120"><path d="M60 12C67 43 77 53 108 60C77 67 67 77 60 108C53 77 43 67 12 60C43 53 53 43 60 12Z"/></svg><span>THE HUMAN SIGNAL</span></div>
            <div class="widget-space" :aria-busy="phase === 'loading' || phase === 'checking'">
              <StarLock v-if="session" ref="widget" :key="session.session_ticket" :site-key="session.site_key" :session-ticket="session.session_ticket" sdk-url="/sdk/v1/api.js?v=0.7.0-compact.1" :auto-open="showPopup" @success="session.onSuccess" @expire="session.onExpire" />
              <div v-else-if="phase === 'loading'" class="preview-skeleton" role="status" aria-label="正在准备验证"><div class="skeleton-heading"><span></span><i></i></div><div class="skeleton-scene"><span>正在准备一份新挑战</span></div><div class="skeleton-track"></div><p>马上就好…</p></div>
              <div v-else-if="phase === 'success'" class="passed-card" role="status"><span class="success-badge">✓ 验证完成</span><h3>刚刚好，是你。</h3><p>这次交互已通过完整验证。</p><button type="button" @click="start()">再试一次 <span>↗</span></button></div>
              <div v-else class="preview-error" role="alert"><h3>{{ phase === 'expired' ? '这份挑战已过期' : '暂时没能加载' }}</h3><p>{{ phase === 'expired' ? '换一份新挑战，继续体验。' : message }}</p><button type="button" @click="start()">重新加载 <span>↗</span></button></div>
            </div>
            <div class="stage-bottom" role="status" aria-live="polite"><span class="stage-indicator" :class="{ complete: phase === 'success' }"></span><span>{{ phase === 'checking' ? '正在确认验证结果…' : phase === 'success' ? '验证与服务端复核均已完成' : phase === 'loading' ? '每次加载，都是全新的挑战' : selectedKind.hint }}</span></div>
          </div>
        </div>
      </section>

      <section id="architecture" class="architecture section-wrap"><div class="section-kicker"><span>02 — BUILT IN LAYERS</span><span>清晰的模块，渐进的能力。</span></div>
        <div class="architecture-heading"><h2>每一层，各司其职。</h2><p>沿同一套协议，逐步延伸验证的边界。</p></div>
        <div class="module-grid">
          <article><span class="module-number">01 / INTERFACE</span><h3>托管组件</h3><p>远程脚本提供验证界面，Vue 封装复用同一份 SDK。</p><span class="module-status available">脚本与 Vue 接入已实现</span></article>
          <article><span class="module-number">02 / VERIFICATION</span><h3>验证服务</h3><p>服务端保管答案，绑定业务上下文，原子消费一次性凭证。</p><span class="module-status available">第一阶段已实现</span></article>
          <article><span class="module-number">03 / ADAPTIVE</span><h3>按风险升级</h3><p>从滑块、点选到九宫格，逐步构建低打扰的验证策略。</p><span class="module-status">后续阶段规划</span></article>
        </div>
      </section>

      <section id="integration" class="integration section-wrap" aria-labelledby="integration-title">
        <div class="section-kicker"><span>03 — MADE TO CONNECT</span><span class="tiny-pill">Hosted SDK · Vue 3</span></div>
        <div class="integration-heading"><h2 id="integration-title">把星锁，接进你的产品。</h2><p>引入托管脚本，连接验证服务。Vue 项目也复用同一份组件。</p></div>
        <ol class="integration-steps">
          <li><span>01</span><h3>后端创建会话</h3><p>用站点密钥绑定本次业务，向浏览器返回短期票据。</p></li>
          <li><span>02</span><h3>前端挂载组件</h3><p>传入站点标识、票据和 API 地址，展示并完成验证。</p></li>
          <li><span>03</span><h3>后端复核凭证</h3><p>将 token 随业务请求提交，后端复核通过后执行业务。</p></li>
        </ol>
        <div class="integration-layout">
          <div class="integration-code"><div class="code-heading"><div class="code-switch" role="group" aria-label="选择接入方式"><button :aria-pressed="integrationMode === 'html'" @click="integrationMode = 'html'">普通网页</button><button :aria-pressed="integrationMode === 'vue'" @click="integrationMode = 'vue'">Vue 3</button></div><span>本地接入示例</span></div><pre tabindex="0" :aria-label="integrationMode === 'html' ? '托管脚本接入代码' : 'Vue 3 接入代码'"><code>{{ integrationMode === 'html' ? hostedExample : integrationExample }}</code></pre></div>
          <aside class="integration-notes" aria-label="接入配置说明">
            <h3>一个地址，连接验证服务。</h3>
            <dl><dt>托管脚本 · 当前可用</dt><dd><code>/sdk/v1/api.js</code><p>默认调用脚本所在服务的验证 API，普通网页无需安装框架。</p></dd>
              <dt>Vue 封装</dt><dd><code>sdk-url="…/sdk/v1/api.js"</code><p>自动加载并复用脚本，处理组件挂载、销毁和回调。</p></dd>
              <dt>跨源 API · 已实现</dt><dd><p>登记接入网站来源后，挑战接口支持跨源请求。站点密钥继续保存在后端。</p></dd></dl>
            <a class="hosted-demo-link" href="http://127.0.0.1:5179/">打开独立网站接入示例 ↗</a>
            <p class="integration-status">示例中的 /demo 接口仅用于本地联调。npm 包、正式域名、CDN 部署与站点控制台尚未发布。</p>
            <p class="integration-secret">站点密钥只放在你的后端；前端成功回调返回待复核凭证。</p>
          </aside>
        </div>
      </section>

      <section id="visuals" class="visuals section-wrap"><div class="section-kicker"><span>04 / THE STARLOCK SIGNATURE</span><span>紫色锁体 · 星形锁孔</span></div>
        <div class="visual-header"><h2>一眼星锁。<em>始终如一。</em></h2><p>以星形为孔，以信任为钥。这是属于 StarLock 的品牌签名。</p></div>
        <div class="art-grid"><figure class="lockup-art"><div class="logo-composition"><img src="/brand/starlock.svg" alt="星锁专用紫色锁形 Logo" width="104" height="104" /><span>StarLock<small>星锁 · HUMAN VERIFICATION</small></span></div><figcaption><span>01 / THE ORIGINAL MARK</span><a href="/brand/starlock.svg" download>获取项目 Logo ↗</a></figcaption></figure>
          <figure class="signature-art"><div class="signature-symbol" aria-hidden="true"><svg viewBox="0 0 120 120"><path d="M60 12C67 43 77 53 108 60C77 67 67 77 60 108C53 77 43 67 12 60C43 53 53 43 60 12Z"/></svg></div><figcaption><span>02 / A SPACE FOR TRUST</span><span>为真实，留一束光。</span></figcaption></figure></div>
      </section>
    </main>
    <footer class="site-footer"><span><img src="/brand/starlock.svg" alt="" width="26" height="26" /> StarLock · 星锁</span><p>星梦科技 / STARDREAMTECH</p><span class="footer-meta">MADE FOR HUMAN MOMENTS.</span></footer>
  </div>
</template>
