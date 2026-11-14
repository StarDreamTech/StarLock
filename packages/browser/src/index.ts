import { createRuntime } from './runtime'

// Capture while this classic script executes; async callbacks have no currentScript.
const script = document.currentScript as HTMLScriptElement | null
const source = script?.src
if (!source) throw new Error('星锁 SDK 必须通过 script src 加载')
if (!window.StarLock) window.StarLock = createRuntime(source, script?.nonce)
else if (window.StarLock.sdkUrl !== source) throw new Error('当前页面已加载其他星锁 SDK 地址')
