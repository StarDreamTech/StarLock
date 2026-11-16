<script setup lang="ts">
import { ref } from 'vue'
import type { GridChallenge } from '@starlock/core'

const props = defineProps<{ challenge: GridChallenge; disabled: boolean }>()
const emit = defineEmits<{ change: [ids: string[]]; error: [code: string] }>()
const selected = ref<string[]>([])
const loaded = ref<string[]>([])
const failed = ref(false)
function toggle(id: string) {
  if (props.disabled || failed.value || loaded.value.length !== 9) return
  selected.value = selected.value.includes(id) ? selected.value.filter(value => value !== id) : [...selected.value, id]
  emit('change', selected.value)
}
function imageError() { failed.value = true; emit('error', 'IMAGE_ERROR') }
function clear() { selected.value = []; emit('change', []) }
</script>

<template>
  <div class="sl-semantic-selection">
    <div class="sl-semantic-grid" role="group" aria-label="九宫格图片选择">
      <button v-for="(tile, index) in challenge.payload.tiles" :key="tile.id" type="button"
        :aria-label="`第 ${index + 1} 张图片`" :aria-pressed="selected.includes(tile.id)"
        :disabled="disabled || failed || loaded.length !== 9" @click="toggle(tile.id)">
        <img :src="tile.image" :alt="`候选图片 ${index + 1}`" width="192" height="192" draggable="false"
          @load="loaded.includes(tile.id) || loaded.push(tile.id)" @error="imageError" />
        <span v-if="selected.includes(tile.id)" class="sl-grid-check" aria-hidden="true">✓</span>
      </button>
    </div>
    <div class="sl-selection-controls"><span role="status">已选择 {{ selected.length }} 张</span>
      <button type="button" :disabled="disabled || !selected.length" @click="clear">清空选择</button></div>
    <p class="sl-selection-help">{{ failed ? '图片加载失败，请换一题。' : '选择所有符合题目含义的图片，再确认。' }}</p>
  </div>
</template>
