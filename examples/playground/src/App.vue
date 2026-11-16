<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { StarLock } from '@starlock/vue'
import type { ChallengeType, VerificationResult } from '@starlock/core'
import integrationExample from '../../../docs/examples/VueIntegration.vue?raw'
import hostedExample from '../../../docs/examples/HostedIntegration.html?raw'
import reactExample from '../../../docs/examples/ReactIntegration.tsx?raw'
const integrationMode = ref<'html' | 'vue' | 'react'>('html')
const integrations = {
  html: { label: '普通网页', code: hostedExample },
  vue: { label: 'Vue 3', code: integrationExample },
  react: { label: 'React', code: reactExample },
}
const localDemo = typeof location !== 'undefined' && ['localhost', '127.0.0.1'].includes(location.hostname)
const demoUrls = localDemo
  ? { html: 'http://127.0.0.1:5179/', react: 'http://127.0.0.1:5179/react.html' }
  : { html: 'https://github.com/StarDreamTech/starlock/blob/main/docs/examples/HostedIntegration.html',
      react: 'https://github.com/StarDreamTech/starlock/blob/main/docs/examples/ReactIntegration.tsx' }

const kinds: { type: ChallengeType; name: string; description: string; hint: string; icon: string }[] = [
  { type: 'rotate', name: '圆环旋转', description: '旋转内圈，找回画面原本的模样。', hint: '拖动旋转内圈，留意模糊交界两侧的图案。', icon: 'M20 12a8 8 0 1 1-3-6m3-3v5h-5M8 12a4 4 0 1 0 4-4' },
  { type: 'bezier_slider', name: '曲线拼图', description: '沿着曲线，找到位置与角度的交点。', hint: '拖动图形，让位置和角度同时贴合。', icon: 'M4 17C7 3 17 3 20 17M4 17l-1-5m1 5 5-1M17 7l3 2-1-4' },
  { type: 'slider', name: '旋转滑块', description: '直线、变速，还有一点旋转的乐趣。', hint: '留意旋转，只有一个缺口能够贴合。', icon: 'M4 12h16m-4-4 4 4-4 4M8 5l3 2-3 2M8 19l-3-2 3-2' },
  { type: 'text_click', name: '文字点选', description: '按题目顺序，在画面中找出指定文字。', hint: '按顺序点选，可撤销和清空标记。', icon: 'M5 4h14M12 4v13M8 17h8M17 14l3 3-3 3' },
  { type: 'semantic_grid', name: '语义九宫格', description: '读懂问题，选出所有符合含义的图片。', hint: '选择所有符合题意的图片，确认后由服务端校验。', icon: 'M3 3h18v18H3zM3 9h18M3 15h18M9 3v18M15 3v18' },
  { type: 'digits', name: '数字验证', description: '熟悉的数字，也是一种轻巧的选择。', hint: '输入图片中的数字，确认即可完成。', icon: '' },
  { type: 'text', name: '字符验证', description: '从字符里，找回清晰的答案。', hint: '输入图片中的字符，字母不区分大小写。', icon: '' },
  { type: 'arithmetic', name: '算术验证', description: '用一道小算式，开启一次交互。', hint: '算出图片中的结果，输入后确认。', icon: '' },
]
const selected = ref<ChallengeType>('rotate')
const rotationSource = ref<'preset' | 'procedural'>('preset')
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
function chooseRotation(source: 'preset' | 'procedural') {
  if (source === rotationSource.value) { choose('rotate'); return }
  rotationSource.value = source
  selected.value = 'rotate'
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
        const result = await post('/demo/session', { challenge_type: selected.value,
          ...(selected.value === 'rotate' ? { rotation_source: rotationSource.value } : {}) })
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
  <div class="site-shell home-page">
    <header class="site-header">
      <a class="brand" href="#"><img src="/brand/starlock.svg" alt="星锁项目 Logo" width="38" height="38" /><strong>StarLock<span>星锁 · 星梦科技</span></strong></a>
      <nav aria-label="主导航"><a href="#experience">交互体验</a><a href="#integration">开发接入</a><a href="#architecture">产品架构</a><a href="#visuals">品牌素材</a></nav>
      <a class="header-cta" href="#experience" @click.prevent="choose('rotate')">体验星锁 <span>↗</span></a>
    </header>

    <main>
      <section class="hero" aria-labelledby="hero-title">
        <img class="hero-artwork" src="/brand/starlock-hero-v2.webp" alt="星锁品牌场景：紫色玻璃锁体、四角星锁孔与流动光轨" width="1600" height="800" fetchpriority="high" decoding="async" />
        <div class="hero-shade" aria-hidden="true"></div>
        <div class="hero-copy"><p class="eyebrow"><span class="status-dot"></span> THE HUMAN SIDE OF THE INTERNET</p>
          <h1 id="hero-title">让信任，<br /><em>自然发生。</em></h1>
          <p class="hero-description">辨认真正的交互，留住流畅的体验。<br />星锁，让每一次验证都有温度。</p>
          <div class="hero-actions"><a class="primary-link" href="#experience" @click.prevent="choose('rotate')">即刻体验 <span>↗</span></a><a class="secondary-link" href="#integration">开发者接入 <span>→</span></a></div>
          <div class="hero-meta"><span>八种验证交互</span><span class="meta-line"></span><span>一个托管 SDK</span></div>
        </div>
        <div class="hero-bottom"><a href="#experience" class="scroll-link">探索真实的交互 <span>↓</span></a><span class="hero-signature">TRUST, IN MOTION.</span><button class="hero-preview" type="button" @click="choose('rotate')"><img src="/rotation/starlock-aurora.webp" width="48" height="48" alt="" /><span><small>TAKE A MOMENT / 01</small><strong>转动之间，找回完整。</strong></span><i aria-hidden="true">↗</i></button></div>
      </section>

      <div class="capability-strip" aria-label="星锁接入方式"><span>为真实而设计<span class="strip-dot">✦</span></span><span>Hosted SDK</span><span>Vue 3</span><span>React</span><span>FastAPI</span><span class="strip-note">前端轻接入 · 后端独立复核</span></div>

      <section id="experience" class="experience section-wrap">
        <div class="section-kicker"><span><i>01</i> THE PLAYGROUND</span><span>亲手试一次，就懂了。</span></div>
        <div class="experience-layout">
          <div class="experience-copy"><p class="eyebrow">一点直觉，一点乐趣。</p><h2>验证，<em>也可以有趣。</em></h2>
            <p>转动、滑动，或解一道小题。<br />选一种方式，在独立弹窗里开始。</p>
            <div class="type-options" aria-label="验证方式">
              <button v-for="item in kinds.filter(item => item.icon)" :key="item.type" :class="{ active: selected === item.type }" :aria-label="item.name" :aria-pressed="selected === item.type" @click="choose(item.type)">
                <span class="type-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path :d="item.icon" /></svg></span>
                <span class="type-copy"><strong>{{ item.name }}<small v-if="item.type === 'rotate'" class="recommended">推荐体验</small></strong><span>{{ item.description }}</span></span><span class="type-arrow" aria-hidden="true">↗</span>
              </button>
            </div>
            <div v-if="selected === 'rotate'" class="rotation-sources" role="group" aria-label="旋转图片来源">
              <span>让画面，也属于星梦</span>
              <div><button :aria-pressed="rotationSource === 'preset'" @click="chooseRotation('preset')">图片集预设 <small>系统与自定义图库</small></button><button :aria-pressed="rotationSource === 'procedural'" @click="chooseRotation('procedural')">随机几何 <small>每题生成图案</small></button></div>
              <a v-if="localDemo" href="http://127.0.0.1:8018/admin" target="_blank" rel="noopener">管理图片集 ↗</a>
            </div>
            <div class="basic-options"><span>也可以简单一点</span><div aria-label="基础验证方式"><button v-for="item in kinds.filter(item => !item.icon)" :key="item.type" :aria-pressed="selected === item.type" @click="choose(item.type)">{{ item.name }}<span aria-hidden="true">↗</span></button></div></div>
          </div>
          <div class="experience-stage">
            <div class="stage-label"><div><span class="live-label"><i></i> A MOMENT OF TRUST</span><h3>{{ selectedKind.name }}</h3></div><button type="button" :disabled="phase === 'loading'" aria-label="重新体验当前题型" @click="start()"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><path d="M20 7v5h-5M4 17v-5h5M5.5 7a7 7 0 0 1 11.7-1L20 9M4 15l2.8 3A7 7 0 0 0 18.5 17" /></svg>换一组</button></div>
            <div class="stage-art" aria-hidden="true"><div class="stage-orbit"></div><img src="/brand/starlock.svg" width="112" height="112" alt="" /><span>HUMAN, BY NATURE.</span></div>
            <div class="widget-space" :aria-busy="phase === 'loading' || phase === 'checking'">
              <StarLock v-if="session" ref="widget" :key="session.session_ticket" :site-key="session.site_key" :session-ticket="session.session_ticket" sdk-url="/sdk/v1/api.js?v=0.8.0-selections.1" :auto-open="showPopup" @success="session.onSuccess" @expire="session.onExpire" />
              <div v-else-if="phase === 'loading'" class="preview-skeleton" role="status" aria-label="正在准备验证"><div class="skeleton-heading"><span></span><i></i></div><div class="skeleton-scene"><span>正在准备一份新挑战</span></div><div class="skeleton-track"></div><p>马上就好…</p></div>
              <div v-else-if="phase === 'success'" class="passed-card" role="status"><span class="success-badge">✓ 验证完成</span><h3>刚刚好，是你。</h3><p>这次交互已通过完整验证。</p><button type="button" @click="start()">再试一次 <span>↗</span></button></div>
              <div v-else class="preview-error" role="alert"><h3>{{ phase === 'expired' ? '这份挑战已过期' : '暂时没能加载' }}</h3><p>{{ phase === 'expired' ? '换一份新挑战，继续体验。' : message }}</p><button type="button" @click="start()">重新加载 <span>↗</span></button></div>
            </div>
            <div class="stage-bottom" role="status" aria-live="polite"><span class="stage-indicator" :class="{ complete: phase === 'success' }"></span><span>{{ phase === 'checking' ? '正在确认验证结果…' : phase === 'success' ? '验证与服务端复核均已完成' : phase === 'loading' ? '每次加载，都是全新的挑战' : selectedKind.hint }}</span></div>
          </div>
        </div>
      </section>

      <section id="architecture" class="architecture section-wrap"><div class="section-kicker"><span><i>02</i> BUILT WITH INTENTION</span><span>体验之外，秩序之内。</span></div>
        <div class="architecture-heading"><h2>轻盈的表面。<br /><em>清晰的内核。</em></h2><p>从界面到复核，每一层各司其职。<br />让产品专注于自己的业务。</p></div>
        <div class="module-grid">
          <article><span class="module-number">01 / INTERFACE</span><h3>托管组件</h3><p>远程脚本提供验证界面，Vue / React 封装复用同一份 SDK。</p><span class="module-status available">脚本、Vue 与 React 接入已实现</span></article>
          <article><span class="module-number">02 / VERIFICATION</span><h3>验证服务</h3><p>服务端保管答案，绑定业务上下文，原子消费一次性凭证。</p><span class="module-status available">第一阶段已实现</span></article>
          <article><span class="module-number">03 / ADAPTIVE</span><h3>按风险升级</h3><p>从滑块、点选到九宫格，逐步构建低打扰的验证策略。</p><span class="module-status">后续阶段规划</span></article>
        </div>
      </section>

      <section id="integration" class="integration section-wrap" aria-labelledby="integration-title">
        <div class="section-kicker"><span><i>03</i> MADE TO CONNECT</span><span class="tiny-pill">Hosted SDK · Vue 3 · React</span></div>
        <div class="integration-heading"><h2 id="integration-title">把星锁，接进你的产品。</h2><p>普通网页、Vue 和 React 项目共用托管 SDK，连接同一套验证服务。</p></div>
        <ol class="integration-steps">
          <li><span>01</span><h3>后端创建会话</h3><p>用站点密钥绑定本次业务，向浏览器返回短期票据。</p></li>
          <li><span>02</span><h3>前端挂载组件</h3><p>传入站点标识、票据和 API 地址，展示并完成验证。</p></li>
          <li><span>03</span><h3>后端复核凭证</h3><p>将 token 随业务请求提交，后端复核通过后执行业务。</p></li>
        </ol>
        <div class="integration-layout">
          <div class="integration-code">
            <div class="code-heading">
              <div class="code-switch" role="group" aria-label="选择接入方式">
                <button v-for="(item, key) in integrations" :key="key" :aria-pressed="integrationMode === key" @click="integrationMode = key">{{ item.label }}</button>
              </div>
              <span>本地接入示例</span>
            </div>
            <pre tabindex="0" :aria-label="integrations[integrationMode].label + ' 接入代码'"><code>{{ integrations[integrationMode].code }}</code></pre>
          </div>
          <aside class="integration-notes" aria-label="接入配置说明">
            <h3>一个地址，连接验证服务。</h3>
            <dl><dt>托管脚本 · 当前可用</dt><dd><code>/sdk/v1/api.js</code><p>默认调用脚本所在服务的验证 API，普通网页无需安装框架。</p></dd>
              <dt>Vue / React 封装</dt><dd><code>sdkUrl / sdk-url</code><p>自动加载并复用脚本，处理组件挂载、销毁和回调。</p></dd>
              <dt>跨源 API · 已实现</dt><dd><p>登记接入网站来源后，挑战接口支持跨源请求。站点密钥继续保存在后端。</p></dd></dl>
            <a class="hosted-demo-link" :href="demoUrls.html">普通网页接入示例 ↗</a>
            <a class="hosted-demo-link" :href="demoUrls.react">React 接入示例 ↗</a>
            <p class="integration-status">示例中的 /demo 接口仅用于本地联调。npm 包、正式域名、CDN 部署与站点控制台尚未发布。</p>
            <p class="integration-secret">站点密钥只放在你的后端；前端成功回调返回待复核凭证。</p>
          </aside>
        </div>
      </section>

      <section id="visuals" class="visuals section-wrap"><div class="section-kicker"><span><i>04</i> THE STARLOCK SIGNATURE</span><span>紫色锁体 · 星形锁孔</span></div>
        <div class="visual-header"><h2>一眼星锁。<em>始终如一。</em></h2><p>以星形为孔，以信任为钥。这是属于 StarLock 的品牌签名。</p></div>
        <div class="art-grid"><figure class="lockup-art"><div class="logo-composition"><img src="/brand/starlock.svg" alt="星锁专用紫色锁形 Logo" width="104" height="104" /><span>StarLock<small>星锁 · HUMAN VERIFICATION</small></span></div><figcaption><span>01 / THE ORIGINAL MARK</span><a href="/brand/starlock.svg" download>获取项目 Logo ↗</a></figcaption></figure>
          <figure class="signature-art"><div class="signature-symbol" aria-hidden="true"><svg viewBox="0 0 120 120"><path d="M60 12C67 43 77 53 108 60C77 67 67 77 60 108C53 77 43 67 12 60C43 53 53 43 60 12Z"/></svg></div><figcaption><span>02 / A SPACE FOR TRUST</span><span>为真实，留一束光。</span></figcaption></figure></div>
        <div class="rotation-gallery" aria-label="星梦旋转验证码预设插画">
          <figure v-for="art in [{ id: 'garden', name: '兰庭微光' }, { id: 'workshop', name: '星轨工坊' }, { id: 'aurora', name: '极光之钥' }]" :key="art.id"><img :src="`/rotation/starlock-${art.id}.webp`" :alt="art.name + '：以星锁紫色锁体和四角星为主题的插画'" loading="lazy" width="768" height="768" /><figcaption><span>{{ art.name }}</span><a :href="`/rotation/starlock-${art.id}.webp`" download>下载图片 ↗</a></figcaption></figure>
        </div>
      </section>
    </main>
    <footer class="site-footer"><div class="footer-invitation"><p>下一次交互，<br /><em>从信任开始。</em></p><a class="primary-link" href="#experience" @click.prevent="choose('rotate')">体验星锁 <span>↗</span></a></div><div class="footer-wordmark" aria-hidden="true">StarLock<span>✦</span></div><div class="footer-bottom"><span><img src="/brand/starlock.svg" alt="" width="26" height="26" /> 星锁 · 星梦科技</span><p>本地开发预览 · 公网服务尚未发布</p><span class="footer-meta">DESIGNED FOR HUMANS.</span></div></footer>
  </div>
</template>
