<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, useId, watch } from 'vue'
import { easedProgress, motionState } from '@starlock/core'
import type { RotationChallenge, SliderAnswer, SliderChallenge } from '@starlock/core'

const props = defineProps<{ challenge: SliderChallenge | RotationChallenge; disabled: boolean }>()
const emit = defineEmits<{ verify: [answer: SliderAnswer]; error: [code: string] }>()
const progress = ref(0)
const dragging = ref(false)
const track = ref<HTMLDivElement>()
const thumb = ref<HTMLButtonElement>()
const backgroundLoaded = ref(false), pieceLoaded = ref(false), imageFailed = ref(false)
const helpId = useId()
const unavailable = computed(() => props.disabled || !backgroundLoaded.value || !pieceLoaded.value || imageFailed.value)
const ring = computed(() => props.challenge.challenge_type === 'rotate')
const position = computed(() => props.challenge.challenge_type === 'rotate'
  ? { x: 0, y: 0, angle: easedProgress(props.challenge.payload.motion.easing, progress.value) * 360 }
  : motionState(props.challenge.payload, progress.value))
const pieceStyle = computed(() => {
  const payload = props.challenge.payload
  return { width: `${payload.piece_width / payload.image_width * 100}%`, height: `${payload.piece_height / payload.image_height * 100}%`,
    left: `${position.value.x / payload.image_width * 100}%`, top: `${position.value.y / payload.image_height * 100}%`,
    transform: `rotate(${position.value.angle}deg)` }
})
let pointer: { id: number; x: number; start: number; travel: number } | undefined
let observer: ResizeObserver | undefined

function cancel() {
  if (pointer && thumb.value?.hasPointerCapture?.(pointer.id)) thumb.value.releasePointerCapture(pointer.id)
  pointer = undefined
  dragging.value = false
}
function down(event: PointerEvent) {
  if (unavailable.value || pointer || !event.isPrimary || event.button !== 0) return
  const travel = (track.value?.getBoundingClientRect().width || 0) - (thumb.value?.getBoundingClientRect().width || 0)
  if (travel <= 0) return
  event.preventDefault()
  thumb.value?.focus()
  thumb.value?.setPointerCapture(event.pointerId)
  pointer = { id: event.pointerId, x: event.clientX, start: progress.value, travel }
  dragging.value = true
}
function move(event: PointerEvent) {
  if (!pointer || pointer.id !== event.pointerId || unavailable.value) return
  progress.value = Math.max(0, Math.min(1, pointer.start + (event.clientX - pointer.x) / pointer.travel))
}
function up(event: PointerEvent) {
  if (!pointer || pointer.id !== event.pointerId) return
  move(event)
  const moved = Math.abs(event.clientX - pointer.x) > 1
  cancel()
  if (!unavailable.value && moved) submit()
}
function submit() { if (!unavailable.value) emit('verify', { progress: progress.value }) }
function key(event: KeyboardEvent) {
  if (unavailable.value) return
  const steps: Record<string, number> = { ArrowRight: .005, ArrowUp: .005, ArrowLeft: -.005, ArrowDown: -.005, PageUp: .05, PageDown: -.05 }
  if (event.key in steps) progress.value = Math.max(0, Math.min(1, progress.value + steps[event.key]))
  else if (event.key === 'Home') progress.value = 0
  else if (event.key === 'End') progress.value = 1
  else if (event.key === 'Enter' || event.key === ' ') submit()
  else return
  event.preventDefault()
}
function failed() { imageFailed.value = true; cancel(); emit('error', 'IMAGE_ERROR') }
watch(() => props.disabled, disabled => { cancel(); if (!disabled) progress.value = 0 })
onMounted(() => {
  if (typeof ResizeObserver !== 'undefined' && track.value) {
    observer = new ResizeObserver(() => { if (pointer) { cancel(); progress.value = 0 } })
    observer.observe(track.value)
  }
})
onBeforeUnmount(() => { cancel(); observer?.disconnect() })
</script>

<template>
  <div class="sl-slider">
    <div class="sl-puzzle" :class="{ 'sl-ring': ring }" :style="{ aspectRatio: `${challenge.payload.image_width}/${challenge.payload.image_height}` }">
      <img class="sl-scene" :src="challenge.payload.image" :width="challenge.payload.image_width" :height="challenge.payload.image_height"
        :alt="ring ? '固定外圈与旋转内圈，拖动使交界图案对齐' : '带多个图形缺口的星空题面，只有一个缺口的位置与角度能同时贴合'" draggable="false" @load="backgroundLoaded = true" @error="failed" />
      <img class="sl-piece" :src="challenge.payload.piece_image" :style="pieceStyle" alt="" draggable="false" @load="pieceLoaded = true" @error="failed" />
    </div>
    <div ref="track" class="sl-track" :class="{ 'sl-dragging': dragging, 'sl-track-disabled': unavailable }">
      <span class="sl-track-label" aria-hidden="true">{{ ring ? (dragging ? '对齐图案后松开' : '拖动滑块，旋转内圈') : (dragging ? '对准缺口后松开' : '按住滑块，拖动拼图') }}</span>
      <button ref="thumb" type="button" role="slider" class="sl-thumb" :disabled="unavailable"
        :style="{ left: `calc(${progress * 100}% - ${progress * 44}px)` }"
        :aria-label="ring ? '旋转进度' : '拼图位置'" aria-valuemin="0" aria-valuemax="100" :aria-valuenow="Math.round(progress * 100)"
        :aria-valuetext="ring ? `旋转 ${Math.round(position.angle)} 度，手柄进度 ${Math.round(progress * 100)}%` : `路径进度 ${Math.round(progress * 100)}%`" :aria-describedby="helpId" aria-orientation="horizontal"
        @pointerdown="down" @pointermove="move" @pointerup="up" @pointercancel="cancel" @lostpointercapture="cancel" @keydown="key">⇥</button>
    </div>
    <p :id="helpId" class="sl-slider-help">{{ imageFailed ? '题目图片加载失败，请换题。' : '松开验证 · 方向键微调，回车确认' }}</p>
  </div>
</template>
