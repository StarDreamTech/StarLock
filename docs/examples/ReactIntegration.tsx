'use client'

import { StarLock } from '@starlock/react'
import type { VerificationResult } from '@starlock/core'

interface Props {
  siteKey: string
  sessionTicket: string
  onSuccess: (result: VerificationResult) => void
  onExpire?: () => void
  onError?: (code: string) => void
}

// 票据由业务后端创建，成功回调的 token 仍需交给业务后端复核。
export default function ReactIntegration(props: Props) {
  return (
    <StarLock
      {...props}
      sdkUrl="http://127.0.0.1:8018/sdk/v1/api.js"
      displayMode="popup"
    />
  )
}
