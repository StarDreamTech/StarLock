<script setup lang="ts">
import { ref } from 'vue'
import type { Point, TextClickChallenge } from '@starlock/core'

const props = defineProps<{ challenge: TextClickChallenge; disabled: boolean }>()
const emit = defineEmits<{ change: [points: Point[]]; error: [code: string] }>()
const image = ref<HTMLImageElement>()
const points = ref<Point[]>([])
const loaded = ref(false)
const failed = ref(false)
const cursor = ref<Point>({ x: .5, y: .5 })
const showCursor = ref(false)
function update(next: Point[]) { points.value = next; emit('change', next) }
function add(point: Point) {
  if (props.disabled || !loaded.value || failed.value || points.value.length >= props.challenge.payload.required_clicks) return
  cursor.value = point
  update([...points.value, point])
}
function click(event: MouseEvent) {
  const bounds = image.value?.getBoundingClientRect()
  if (!bounds || !bounds.width || !bounds.height) return
  const point = { x: (event.clientX - bounds.left) / bounds.width, y: (event.clientY - bounds.top) / bounds.height }
  if (point.x >= 0 && point.x <= 1 && point.y >= 0 && point.y <= 1) add(point)
}
function remove(index: number) { if (!props.disabled) update(points.value.filter((_, value) => value !== index)) }
function key(event: KeyboardEvent) {
  if (props.disabled) return
  const step = event.shiftKey ? .005 : .02
  const deltas: Record<string, Point> = { ArrowLeft: { x: -step, y: 0 }, ArrowRight: { x: step, y: 0 },
    ArrowUp: { x: 0, y: -step }, ArrowDown: { x: 0, y: step } }
  if (event.key in deltas) {
    showCursor.value = true
    const delta = deltas[event.key]
    cursor.value = { x: Math.max(0, Math.min(1, cursor.value.x + delta.x)), y: Math.max(0, Math.min(1, cursor.value.y + delta.y)) }
  } else if (event.key === 'Enter' || event.key === ' ') add({ ...cursor.value })
  else if (event.key === 'Backspace' || event.key === 'Delete') remove(points.value.length - 1)
  else return
  event.preventDefault()
  event.stopPropagation()
}
function imageError() { failed.value = true; emit('error', 'IMAGE_ERROR') }
</script>

<template>
  <div class="sl-text-click">
    <div class="sl-click-board" tabindex="0" role="group" aria-label="文字点选区域，方向键移动光标，回车添加标记"
      :aria-disabled="disabled || !loaded || failed" @click="click" @keydown="key">
      <img ref="image" :src="challenge.payload.image" :width="challenge.payload.image_width" :height="challenge.payload.image_height"
        alt="包含目标文字和干扰文字的图片" draggable="false" @load="loaded = true" @error="imageError" />
      <span v-if="showCursor" class="sl-click-cursor" :style="{ left: `${cursor.x * 100}%`, top: `${cursor.y * 100}%` }" aria-hidden="true"></span>
      <button v-for="(point, index) in points" :key="index" type="button" class="sl-click-marker" :disabled="disabled"
        :style="{ left: `${point.x * 100}%`, top: `${point.y * 100}%` }" :aria-label="`移除第 ${index + 1} 次点击`"
        @click.stop="remove(index)" @keydown.stop>{{ index + 1 }}</button>
    </div>
    <div class="sl-selection-controls"><span role="status">已点选 {{ points.length }} / {{ challenge.payload.required_clicks }}</span>
      <button type="button" :disabled="disabled || !points.length" @click="remove(points.length - 1)">撤销</button>
      <button type="button" :disabled="disabled || !points.length" @click="update([])">清空</button></div>
    <p class="sl-selection-help">按提示顺序点击文字，也可用方向键和回车添加标记。</p>
  </div>
</template>
