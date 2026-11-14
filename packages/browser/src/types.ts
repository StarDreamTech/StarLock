import type { ClientOptions } from '@starlock/core'

export interface RenderOptions extends ClientOptions {
  displayMode?: 'popup' | 'inline'
  autoOpen?: boolean
  onClose?: () => void
  onError?: (code: string) => void
}
export interface WidgetHandle {
  open(): void
  close(): void
  getResponse(): string
  refresh(): Promise<void>
  reset(sessionTicket?: string): Promise<void>
  destroy(): void
}
export interface StarLockApi {
  readonly version: string
  readonly sdkUrl: string
  render(target: string | HTMLElement, options: RenderOptions): WidgetHandle
}
declare global {
  interface Window { StarLock?: StarLockApi }
}
