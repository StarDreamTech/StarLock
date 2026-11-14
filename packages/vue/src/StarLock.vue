<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { loadStarLock } from '@starlock/browser'
import type { WidgetHandle } from '@starlock/browser'
import type { VerificationResult } from '@starlock/core'

const props = defineProps<{ siteKey: string; sessionTicket: string; apiBase?: string; sdkUrl?: string; nonce?: string; displayMode?: 'popup' | 'inline'; autoOpen?: boolean }>()
const emit = defineEmits<{ success: [result: VerificationResult]; expire: []; error: [code: string]; close: [] }>()
const container = ref<HTMLDivElement>()
const loading = ref(true)
const message = ref('')
let widget: WidgetHandle | undefined
let generation = 0

async function mount() {
  if (!container.value) return
  const current = ++generation
  widget?.destroy()
  widget = undefined
  loading.value = true
  message.value = ''
  try {
    const api = await loadStarLock(props.sdkUrl ?? `${props.apiBase || ''}/sdk/v1/api.js`, props.nonce)
    if (current !== generation || !container.value) return
    widget = api.render(container.value, {
      siteKey: props.siteKey, sessionTicket: props.sessionTicket, apiBase: props.apiBase,
      displayMode: props.displayMode, autoOpen: props.autoOpen, onClose: () => emit('close'),
      onSuccess: result => emit('success', result), onExpire: () => emit('expire'),
      onError: code => emit('error', code),
    })
  } catch (error) {
    if (current !== generation) return
    message.value = error instanceof Error ? error.message : '无法加载星锁验证组件'
    emit('error', 'SDK_LOAD_FAILED')
  } finally { if (current === generation) loading.value = false }
}
async function refresh() { await widget?.refresh() }
onMounted(mount)
watch(() => [props.siteKey, props.sessionTicket, props.apiBase, props.sdkUrl, props.nonce, props.displayMode], mount, { flush: 'post' })
watch(() => props.autoOpen, open => { if (open) widget?.open() })
onBeforeUnmount(() => { generation++; widget?.destroy() })
defineExpose({ refresh, open: () => widget?.open(), close: () => widget?.close() })
</script>

<template>
  <div>
    <p v-if="loading" role="status">正在加载星锁验证…</p>
    <p v-if="message" role="alert">{{ message }}</p>
    <button v-if="message" type="button" @click="mount">重新加载验证组件</button>
    <div ref="container"></div>
  </div>
</template>
