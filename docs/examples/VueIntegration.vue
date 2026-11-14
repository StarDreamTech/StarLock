<script setup lang="ts">
import { StarLock } from '@starlock/vue'
import type { VerificationResult } from '@starlock/core'

// 由自己的后端创建会话后传入；不要传站点密钥。
defineProps<{ siteKey: string; sessionTicket: string }>()
const emit = defineEmits<{
  verified: [token: string]
  expired: []
}>()
const sdkUrl = import.meta.env.VITE_STARLOCK_SDK_URL || '/sdk/v1/api.js'
const apiBase = import.meta.env.VITE_STARLOCK_API_BASE || undefined

function onSuccess(result: VerificationResult) {
  // 父页面把 token 随业务请求交给自己的后端复核。
  emit('verified', result.token)
}
</script>

<template>
  <StarLock :site-key="siteKey" :session-ticket="sessionTicket"
    :sdk-url="sdkUrl" :api-base="apiBase" display-mode="popup" @success="onSuccess"
    @expire="emit('expired')" />
</template>
