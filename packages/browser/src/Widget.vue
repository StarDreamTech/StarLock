<script setup lang="ts">
import { computed, onBeforeUnmount, ref, useId, watch } from 'vue'
import { isSlider, isTextClick, isGrid, StarLockClient } from '@starlock/core'
import type { Point, State, VerificationResult } from '@starlock/core'
import PuzzleSlider from './PuzzleSlider.vue'
import TextClick from './TextClick.vue'
import SemanticGrid from './SemanticGrid.vue'
import logoSvg from '../../../assets/brand/starlock.svg?raw'
const logo = `data:image/svg+xml,${encodeURIComponent(logoSvg)}`

const props = defineProps<{ siteKey: string; sessionTicket: string; apiBase?: string; transport?: typeof fetch }>()
const emit = defineEmits<{ success: [result: VerificationResult]; expire: []; error: [code: string] }>()
const state = ref<State>({ status: 'idle', message: '' })
const answer = ref('')
const clickPoints = ref<Point[]>([])
const selectedTiles = ref<string[]>([])
const input = ref<HTMLInputElement>()
const inputId = useId()
const statusId = useId()
let client: StarLockClient | undefined
let unsubscribe: (() => void) | undefined
const busy = computed(() => ['loading', 'verifying'].includes(state.value.status))
const slider = computed(() => state.value.challenge && isSlider(state.value.challenge) ? state.value.challenge : undefined)
const clickChallenge = computed(() => state.value.challenge && isTextClick(state.value.challenge) ? state.value.challenge : undefined)
const gridChallenge = computed(() => state.value.challenge && isGrid(state.value.challenge) ? state.value.challenge : undefined)
const selection = computed(() => clickChallenge.value || gridChallenge.value)
const textChallenge = computed(() => {
  const challenge = state.value.challenge
  return challenge && !isSlider(challenge) && !isTextClick(challenge) && !isGrid(challenge) ? challenge : undefined
})
const canSubmit = computed(() => state.value.status === 'ready' && (clickChallenge.value
  ? clickPoints.value.length === clickChallenge.value.payload.required_clicks
  : gridChallenge.value ? selectedTiles.value.length > 0 : !!answer.value.trim()))
function submit() {
  void client?.verify(clickChallenge.value ? { points: clickPoints.value }
    : gridChallenge.value ? { tile_ids: selectedTiles.value } : answer.value)
}

watch(() => [props.siteKey, props.sessionTicket, props.apiBase], () => {
  unsubscribe?.()
  client?.destroy()
  answer.value = ''
  client = new StarLockClient({ siteKey: props.siteKey, sessionTicket: props.sessionTicket, apiBase: props.apiBase,
    onSuccess: result => emit('success', result), onExpire: () => emit('expire') }, props.transport)
  unsubscribe = client.subscribe(next => {
    if (next.challenge?.challenge_id !== state.value.challenge?.challenge_id) { clickPoints.value = []; selectedTiles.value = [] }
    state.value = next
    if (next.status === 'error' && next.errorCode) emit('error', next.errorCode)
  })
  void client.initialize()
}, { immediate: true })

async function refresh() { answer.value = ''; await client?.refresh(); input.value?.focus() }
async function reset(ticket?: string) { answer.value = ''; await client?.reset(ticket) }
onBeforeUnmount(() => { unsubscribe?.(); client?.destroy() })
defineExpose({ refresh, reset })
</script>

<template>
  <section class="sl-widget" :class="{ 'sl-rotation-widget': state.challenge?.challenge_type === 'rotate' }" aria-label="星锁人机验证" :aria-busy="busy">
    <div class="sl-heading">
      <img class="sl-logo" :src="logo" width="24" height="24" alt="星锁 Logo" />
      <strong>星锁验证</strong>
    </div>
    <div v-if="state.status === 'success'" class="sl-success" role="status">
      <span class="sl-check" aria-hidden="true">✓</span><strong>验证通过</strong><p>本次验证已完成</p>
    </div>
    <form v-else @submit.prevent="submit">
      <p class="sl-instruction">{{ state.challenge?.payload.instruction || '正在准备验证…' }}</p>
      <TextClick v-if="clickChallenge" :key="clickChallenge.challenge_id" :challenge="clickChallenge" :disabled="state.status !== 'ready'"
        @change="clickPoints = $event" @error="emit('error', $event)" />
      <SemanticGrid v-else-if="gridChallenge" :key="gridChallenge.challenge_id" :challenge="gridChallenge" :disabled="state.status !== 'ready'"
        @change="selectedTiles = $event" @error="emit('error', $event)" />
      <PuzzleSlider v-else-if="slider" :key="slider.challenge_id" :challenge="slider" :disabled="state.status !== 'ready'"
        @verify="client?.verify($event)" @error="emit('error', $event)" />
      <div v-else class="sl-image-frame">
        <img v-if="textChallenge" :src="textChallenge.payload.image" alt="需要识别的验证码图片" width="280" height="88" />
        <span v-else class="sl-loading">{{ state.status === 'error' ? '暂时无法加载题目' : '正在连接验证服务' }}</span>
        <div v-if="state.status === 'loading' && state.challenge" class="sl-overlay">正在换一题…</div>
      </div>
      <label v-if="!slider && !selection" class="sl-label" :for="inputId">验证答案</label>
      <div v-if="!slider && !selection" class="sl-input-row"><input :id="inputId" ref="input" v-model="answer" :inputmode="textChallenge?.payload.input_mode || 'text'"
        maxlength="32" autocomplete="off" autocapitalize="characters" spellcheck="false" placeholder="输入图片答案"
        :disabled="state.status !== 'ready'" :aria-invalid="state.errorCode === 'ANSWER_INVALID'" :aria-describedby="statusId" />
        <button type="button" class="sl-refresh" :disabled="busy" aria-label="换一张验证码" @click="refresh">↻</button></div>
      <div v-if="slider || selection" class="sl-toolbar">
        <button type="button" class="sl-refresh sl-slider-refresh" :disabled="busy" aria-label="换一题" title="换一题" @click="refresh">↻</button>
        <div :id="statusId" class="sl-message" role="status" aria-live="polite">
          {{ busy ? (state.status === 'verifying' ? '正在校验…' : '正在换一题…') : state.message }}
        </div>
        <span class="sl-credits">星梦科技</span>
      </div>
      <div v-else :id="statusId" class="sl-message" role="status" aria-live="polite">{{ state.message }}</div>
      <button v-if="!slider" type="submit" class="sl-submit" :disabled="!canSubmit">{{ state.status === 'verifying' ? '正在验证…' : gridChallenge ? '确认选择' : clickChallenge ? '确认点选' : '确认验证' }}<span aria-hidden="true">↗</span></button>
    </form>
    <p v-if="!slider && !selection" class="sl-footer">星梦科技</p>
  </section>
</template>
