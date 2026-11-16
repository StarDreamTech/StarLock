# 模块与接入（0.8.0）

三种基础输入题、直线/曲线滑块、圆环旋转、文字点选与语义九宫格共用前后端协议。公开接口和演示业务后端分开，滑块复用会话、挑战、凭证生命周期。

## 模块边界

| 模块 | 已实现职责 | 扩展方式 |
| --- | --- | --- |
| `server/verification/generators.py` | 字符、纯数字、算术题的图片、题面及内部答案 | 新题型在生成器与校验器分别实现；公开参数与答案分开 |
| `server/verification/sliders.py` | 四种图形、多缺口、路径/缓动/旋转、原图位置与角度校验 | 目标与容差只存在服务端，不能使用客户端判定 |
| `server/verification/selections.py` | 文字点选图、顺序坐标校验、语义九宫格与正确集合校验 | 新素材需审核标签；原图与私有解分离 |
| `server/verification/rotations.py` | 品牌预设/随机几何双来源、整图随机方向、双层圆环、局部模糊/羽化、服务端角度判定 | 来源在业务会话绑定；目标只存在服务端，界面仅提交手柄进度 |
| `server/verification/image_sets.py` | 系统/自定义图片集、规范化上传、并发去重、启停与默认池保护 | 与站点共用 SQLite，后端会话绑定图库 |
| `server/verification/admin.py`、`server/assets/admin/` | 图集管理界面、独立管理认证、同源检查与私有预览 | 不复用站点密钥，不开放管理跨域 |
| `server/verification/service.py` | 会话、HMAC 答案、刷新、失败次数、凭证、限流 | 保持业务绑定和原子状态变更，题型不能绕开生命周期 |
| `server/verification/models.py` | 独立 Site 数据类与 sqlite3 存储；保留旧表与 PBKDF2 凭证 | 后续按部署需要引入数据库适配，不依赖 Web 框架 |
| `server/verification/api.py` | FastAPI 路由、Pydantic 请求校验、后端认证、请求大小检查、固定 SDK 文件分发 | API 不缓存；SDK 使用五分钟公共缓存 |
| `server/verification/cors.py` | 仅挑战路由按启用站点 Origin 授权预检及跨源响应 | 数据库检查在线程池执行，实际请求仍核对票据来源 |
| `server/main.py`、`server/config/settings.py` | 应用工厂与显式配置注入 | 通过环境配置启动，每个测试注入独立配置 |
| `server/cli.py` | 站点表初始化、创建、禁用与显式题型授权 | 图片集已有独立后台；站点管理界面待实现 |
| `server/verification/demo.py` | 仅供本地使用的接入方示例，保存业务上下文并消费凭证 | 正式业务在自己的后端实现相同步骤 |
| `packages/core` | 无框架依赖的请求、状态订阅、过期与请求竞争处理 | 供不同 UI 封装复用 |
| `packages/browser` | 托管挑战界面、顶层弹窗/Shadow DOM、验证卡挂载与共享加载器 | 新交互在托管组件中扩展 |
| `packages/vue` | 加载托管脚本、挂载、销毁、转发结果与错误 | 不打包挑战界面 |
| `examples/playground` | 实际联调、品牌展示、同源开发代理 | 不把演示 `/demo/*` 当作正式接入接口 |

Redis 存储一个会话的全部短期状态，凭证包含随机会话标识与 256 位随机部分，服务端只保存摘要。使用 Redis WATCH/MULTI/EXEC 进行冲突检测和原子更新；失败尝试也提交更新，再返回错误。挑战通过后删除题面与答案材料。同一会话只签发一个凭证，复核最多成功一次。Redis 数据丢失时要求重新验证。

该实现面向单节点 Redis。Redis Cluster、跨地域一致性及持久故障恢复尚未测试。本地站点数据继续使用 SQLite，不随框架迁移切换数据库。

路由使用普通 `def`，由 FastAPI 在线程池执行同步 Redis、SQLite 和 Pillow 操作，避免在事件循环里直接运行阻塞操作。更重的图像算法与模型计算，后续按测量结果决定是否引入进程任务模块。

## 接入顺序

官网、SDK 分发、API 地址与 Vue 组件示例见 [项目网站与接入指南](integration.md)。当前已提供托管脚本、Vue 加载封装和跨源挑战接口；npm 包和正式 CDN 尚未发布。

1. 在后端注册站点，指定精确 origin（包含协议与非默认端口）及允许的 action。
2. 接入方后端通过 `Authorization: Bearer <site_secret>` 请求 `/v1/sessions`，同时传入后端生成并保存的 `context_id`。本次业务内容应与该上下文绑定。
3. 只把 `site_key` 与 `session_ticket` 返回浏览器，交给 Vue 组件。
4. 浏览器取得 token 后，将它随业务请求交给接入方后端。
5. 接入方后端向 `/v1/siteverify` 提交 token、预期 action 与从自身会话读取的 context_id，认证通过且返回 success 后，幂等执行业务。

站点创建命令（本地示例）：

```bash
env STARLOCK_DEBUG=1 .venv/bin/python server/cli.py create-site --name "Local app" --origin http://127.0.0.1:5178 --action register
```

命令只打印公开站点标识和凭证文件路径，站点密钥保存在用户目录 `~/.local/share/starlock/credentials/` 下，文件权限为 `0600`，不写进前端或项目源码。正式接入方后端从私有配置读取，不要把密钥提交到仓库。非开发模式创建站点要求 HTTPS 来源。最小版本暂不提供控制台、密钥轮换或多租户权限。

禁用站点（将示例标识换成自己的公开站点标识）：

```bash
env STARLOCK_DEBUG=1 .venv/bin/python server/cli.py disable-site site_example
```

禁用后现有会话和公开复核请求都会被拒绝。`init-db` 及应用启动只创建缺失的表，不删除站点；本地旧表可直接复用，旧 PBKDF2 密钥记录无需重发。

会话创建的 JSON 示例（仅示例数据）：

```json
{
  "site_key": "site_example",
  "action": "register",
  "context_id": "server-generated-random-context",
  "origin": "http://127.0.0.1:5178",
  "challenge_type": "digits"
}
```

浏览器组件示例（包尚未发布，通过本仓库工作区引用）：

```vue
<script setup lang="ts">
import { StarLock } from '@starlock/vue'
defineProps<{ siteKey: string; sessionTicket: string }>()
const emit = defineEmits<{ verified: [token: string] }>()
</script>

<template>
  <StarLock :site-key="siteKey" :session-ticket="sessionTicket"
    @success="result => emit('verified', result.token)" />
</template>
```

复核请求 JSON 示例（携带站点密钥，接入方后端调用）：

```json
{
  "site_key": "site_example",
  "token": "token-returned-by-widget",
  "action": "register",
  "context_id": "server-generated-random-context"
}
```

复核在消费前检查站点、摘要、动作、上下文与有效期。上下文不匹配不会消耗合法凭证。网络响应丢失且接入方没有保存复核结果时，需要重新验证；当前不提供复核幂等查询接口。

## 运行配置

| 变量 | 用途 | 本地默认值 |
| --- | --- | --- |
| `STARLOCK_DEBUG` | 只有 `1` 启用开发模式 | 关闭 |
| `STARLOCK_DEMO` | 与 DEBUG 同时开启才挂载演示业务接口 | 关闭 |
| `STARLOCK_SECRET_KEY` | HMAC 答案密钥 | 仅 DEBUG 可使用公开的本地开发值 |
| `STARLOCK_REDIS_URL` | Redis 连接 | `redis://127.0.0.1:6391/0` |
| `STARLOCK_REDIS_PREFIX` | 本部署的短期状态命名空间 | `starlock:dev:` |
| `STARLOCK_ALLOWED_HOSTS` | Host 白名单，逗号分隔 | 本机与测试主机 |
| `STARLOCK_DATABASE_PATH` | 本地站点数据库路径 | `server/db.sqlite3` 的绝对路径 |
| `STARLOCK_SDK_DIRECTORY` | 只分发其 `v1/api.js` 构建文件 | 项目 `dist/sdk` 的绝对路径 |

挑战接口通过 CORS 允许已登记的启用站点 Origin，授权精确包含协议、域名及非默认端口；禁止 Authorization 预检头和 cookie 凭据。站点白名单检查不会替代后端认证。`/v1/sessions` 与 `/v1/siteverify` 不开放 CORS。使用同源代理时须保留浏览器 Origin；Vite 已配置开发代理。启动命令使用 `--no-proxy-headers`，当前限流不信任 `X-Forwarded-For`；代理后的 IP 限额可能由多个用户共享，生产网关信任链需部署时另行配置。

`/sdk/v1/api.js` 固定分发构建产物，缺失时返回 503 与 `SDK_NOT_BUILT`，不会暴露源码目录或数据库。短期挑战与凭证响应继续使用 `no-store`。CORS 来源当前每次查询站点表，规模扩大后按测量结果增加可失效的缓存。

演示业务用 HttpOnly、SameSite=Strict 的随机 cookie 引用 Redis 中的上下文，cookie 不包含业务上下文内容，引用随会话到期删除。同一主机的多个演示标签（包括不同端口）会共享该 cookie，重开会话会覆盖它；正式业务应按业务请求分别保存上下文。迁移前的演示 cookie 不再使用，需要重新开始验证。

`STARLOCK_DEBUG=1` 时开放 `/docs` 与 `/openapi.json`，其余模式关闭。请求校验错误继续返回 400 与统一 `error_code/message/request_id`，不会回显 Pydantic 错误中的原始票据或 token；超过 32 KiB 的 JSON 请求（包括分块传输）返回 413。

## 下一阶段

直线和贝塞尔滑块已实现，协议、坐标和旧站点开启命令见 [README 第 7 节](../README.md#7-直线与贝塞尔滑块已实现)。文字顺序点选和静态语义九宫格已经接入相同生命周期，详见 [README 第 8 节](../README.md#8-文字点选与语义九宫格已实现)。下一步扩展语义题库管理、多轮换图、无感策略与行为评分。当前滑块验证位置与角度，不声称能够通过轨迹判断用户身份。

实现参考：[FastAPI 并发与线程池](https://fastapi.tiangolo.com/async/)、[FastAPI 测试](https://fastapi.tiangolo.com/tutorial/testing/)、[Redis 原子脚本与事务语义](https://redis.io/docs/latest/develop/programmability/)、[Vue TypeScript 支持](https://vuejs.org/guide/typescript/overview)。

## React 组件

`packages/react` 通过现有加载器复用托管 SDK，支持 React 18.2+ 与 React 19。组件在 Effect 中挂载，清理时销毁实例并屏蔽旧会话回调；StrictMode、加载重试、回调更新和服务端渲染有独立回归检查。可运行示例为 `examples/hosted/react.html`，详细使用方法见 [React 接入](integration.md#react-接入)。
