# 架构与验证协议

## 源码入口

| 路径 | 职责 |
| --- | --- |
| `server/main.py`、`server/verification/api.py` | FastAPI 工厂、Pydantic 输入、HTTP 边界与路由 |
| `server/cli.py`、`server/verification/models.py` | 站点初始化、创建和禁用；SQLite 站点数据、密钥派生记录 |
| `server/verification/service.py` | 会话、出题、答案校验、限流及一次性凭证复核 |
| `server/verification/generators.py` | 字符、数字、算术题与题型分派 |
| `server/verification/selections.py` | 文字点选、语义九宫格生成及私有答案校验 |
| `server/verification/sliders.py`、`server/verification/rotations.py` | 直线/曲线拼图、旋转题的生成与几何校验 |
| `server/verification/cors.py` | 按启用站点的精确 Origin 授权浏览器挑战接口 |
| `sdks/python/`、`sdks/go/` | Python 同步 / Go context 服务端客户端，仅封装会话创建与一次性复核 |
| `packages/core/src/` | 无框架依赖的 TypeScript 客户端和生命周期 |
| `packages/browser/src/` | 托管验证 UI、Shadow DOM、弹窗和远程脚本加载 |
| `packages/vue/src/`、`packages/react/src/` | 托管 SDK 的框架生命周期封装 |
| `examples/static-demo/` | Pages 浏览器内试玩，复用 UI 与客户端，公开样题和本地判定 |
| `examples/playground/`、`examples/hosted/` | 官网本地版与独立网页、React 接入示例 |

模块细节以 `docs/implementation.md`、接入细节以 `docs/integration.md` 为准，不在这里复制完整接口类型。

## 信任与生命周期

1. 接入方后端通过 `POST /v1/sessions` 创建会话，绑定站点、允许的 `action`、后端保存的 `context_id`、Origin 和题型。
2. 浏览器用公开的 `site_key` 和短期 `session_ticket` 请求 `POST /v1/challenges`；当前实现返回 `decision: challenge`。
3. 浏览器向 `POST /v1/challenges/{challenge_id}/verify` 提交答案，成功后取得通过凭证。
4. 接入方后端通过 `POST /v1/siteverify` 校验凭证与预期动作、上下文并消费，再幂等处理自己的业务。

`site_secret` 不进入浏览器。会话票据不是通过凭证；前端自行提供的业务上下文不能成为可信依据。

Redis 保存会话及短期挑战状态，`service.py` 使用 WATCH/MULTI/EXEC 原子变更。当前关键状态为 `created`、`active`、`passed`、`consumed`；过期通过时间与 TTL 检查，不能把设计图中的状态都当成已实现的持久字段。失败尝试也提交计数；换题后旧挑战失效；成功后删除题面及答案材料；同一会话只签发一份凭证，复核最多成功一次。Redis 丢失短期状态时需要重新验证。

字符答案采用服务端 HMAC 校验材料；滑块和旋转使用私有几何解。答案、目标位置和密钥不能因调试进入公开响应或常规日志。

## 题型与运动

源码已有 `text`、`digits`、`arithmetic`、`slider`、`bezier_slider`、`rotate`、`text_click`、`semantic_grid`。滑块的空间路径与 CSS 语义的三次贝塞尔速度缓动分别计算，并同步旋转；校验位置和角度，不能仅验证客户端声明“已贴合”。旋转题支持预设素材与程序生成，来源由后端会话约束。系统图库为 23 张、5 套，原有素材在 `assets/rotation/`、新增 20 张在 `server/assets/image-sets/`。图集配置与规范化自定义图片保存在 SQLite；部署须同时保留两处系统素材和数据库。详见 `docs/image-sets.md`。

文字点选使用 300×180 中文图和三个有序点击，归一化坐标按 27 原图像素容差比较。语义九宫格使用三个类别、十二张审核图片，每题九格、二至四个正确项，随机格子标识按集合校验。素材与标签清单在 `server/assets/semantic/manifest.json`，字体及授权在 `server/assets/fonts/`。语义标签后台、多轮换图、无感与行为评分仍属后续范围。

## 图片集管理

`verification/image_sets.py` 负责系统/自定义图集、规范化上传与同集去重、启停及默认池事务保护；`verification/admin.py` 与 `server/assets/admin/` 提供运营后台。生产配置独立 `STARLOCK_ADMIN_TOKEN`，管理会话使用 Redis 与 HttpOnly cookie，写操作检查精确同源；本地免口令进入仅允许 DEBUG + DEMO + 回环连接且未配置口令的组合，仍需登录会话。

`image_set_id` 只能由业务后端在创建会话时指定，或在预设旋转会话创建时绑定后台默认。两种滑块可显式选图集，未指定保留程序背景；随机几何旋转和输入题拒绝图集参数。刷新保持图集并过滤停用图片，已下发题面继续在有效期内校验；不可用时明确报错，不回退其他图库。公开题面不暴露图集、素材编号或正确角度。原始素材不能作为秘密或抗识别效果证明。

## 静态交互演示

Pages demo 位于 `examples/static-demo/`。`scripts/generate-demo-challenges.py` 复用后端生成器导出 32 道公开题与演示解，`transport.ts` 在浏览器内提供出题、换题和判定。按单题 `challenges/<题型>/<0–3>.json` 加载，换题时再获取，页面内缓存；聚合 JSON 保留给旧缓存入口与测试。样题与演示答案公开，凭证带 `demo_only` 前缀。正式接入使用原有服务端信任链。

`StarLockClient` 可选第二构造参数接收请求实现，`createRuntime` 的第三参数将其传入内部 Widget。正式 `api.js` 入口继续使用默认请求。demo 不改变 `StarLock.render`、Vue 或 React 的公开配置。

## 业务后端 SDK

`sdks/python` 提供 `Client.create_session` / `siteverify` 和冻结结果对象，`sdks/go` 提供 `CreateSession` / `SiteVerify`、context 和并发复用。两者只使用标准库，支持八种会话题型、旋转来源与图集参数、网关路径前缀、超时及 API 错误码。成功响应再次核对站点、动作和上下文；禁止 HTTP 重定向，不自动重试，避免一次性消费结果不确定时重复请求。Go 客户端配置格式化隐藏站点密钥，Python Client 默认表示不含字段。

Python 为同步客户端，异步路由中交给线程池。Python wheel 已可构建，PyPI 与 Go 版本标签尚未发布，Go 模块路径为 `github.com/StarDreamTech/starlock/sdks/go`。源码安装及完整示例在 `docs/server-sdks.md`。SDK 服务于接入方业务后端，当前验证服务仍采用 FastAPI。
