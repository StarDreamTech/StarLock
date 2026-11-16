# Python 与 Go 服务端 SDK

业务后端通过 SDK 调用星锁的会话和复核接口。前端继续使用托管脚本、Vue 或 React 组件，完成挑战后把 token 交给业务后端。

| 接入端 | 路径 | 当前能力 |
| --- | --- | --- |
| 普通网页 / Vue / React | `packages/browser`、`packages/vue`、`packages/react` | 挂载题面、交互、取回 token |
| Python 3.10+ | `sdks/python`，包名 `starlock-sdk` | 同步创建会话、复核、类型化结果与异常 |
| Go 1.22+ | `sdks/go` | 带 context 的会话/复核、并发复用、类型化结果与错误 |
| 其他后端语言 | HTTP/JSON API | 按同一协议调用，专用 SDK 待后续扩展 |

Python 与 Go SDK 使用各自标准库。当前验证服务使用 FastAPI、Redis 与 SQLite，接入方的业务后端可以独立选择语言和框架。

## 安装与示例

Python 在仓库根目录安装。

```bash
pip install ./sdks/python
```

也可直接从 GitHub 安装。

```bash
pip install 'git+https://github.com/StarDreamTech/starlock.git@main#subdirectory=sdks/python'
```

Go 从源码分支获取。

```bash
go get github.com/StarDreamTech/starlock/sdks/go@main
```

Python wheel 已提供构建配置，PyPI 和 Go 版本标签尚未发布。生产部署可以固定验证过的源码提交。[Python 用法与示例](../sdks/python/README.md) · [Go 用法与示例](../sdks/go/README.md)

## 配置与业务流程

SDK 构造函数接收验证服务的 API 地址、公开站点标识和后端站点密钥。示例使用以下环境变量，值由部署方的私有配置提供。

| 示例环境变量 | 用途 |
| --- | --- |
| `STARLOCK_API_BASE` | 验证 API 地址，可包含网关路径前缀 |
| `STARLOCK_SITE_KEY` | 站点公开标识 |
| `STARLOCK_SITE_SECRET` | 仅保存在业务后端的站点密钥 |
| `STARLOCK_APP_ORIGIN` | 已登记的应用来源，包含协议与必要端口 |

1. 业务后端生成本次业务的 `context_id` 并保存在其会话或数据库中。
2. Python 调用 `create_session`，Go 调用 `CreateSession`，传入业务动作、上下文、已登记来源与题型。
3. 将结果中的 `site_key` 和 `session_ticket` 交给前端组件。
4. 前端完成挑战，向自己的业务后端提交 token。
5. 业务后端读取自己保存的动作和上下文，调用 `siteverify` / `SiteVerify`。成功后幂等执行业务。

`context_id` 至少十二个字符，应与本次业务绑定。验证服务继续核对站点授权、动作和来源，SDK 也检查成功响应与预期的站点、动作、上下文一致。SDK 发往这两个接口的认证使用 `Authorization: Bearer <site_secret>`。

### 题型与图片参数

| Python 字符串 | Go 常量 | 交互 |
| --- | --- | --- |
| `text` | `starlock.Text` | 字母数字输入，省略题型时的默认值 |
| `digits` | `starlock.Digits` | 数字输入 |
| `arithmetic` | `starlock.Arithmetic` | 算术输入 |
| `slider` | `starlock.Slider` | 直线变速旋转滑块 |
| `bezier_slider` | `starlock.BezierSlider` | 曲线变速旋转滑块 |
| `rotate` | `starlock.Rotate` | 圆环旋转 |
| `text_click` | `starlock.TextClick` | 文字顺序点选 |
| `semantic_grid` | `starlock.SemanticGrid` | 语义九宫格 |

会话可指定 `rotation_source` / `RotationSource` 和 `image_set_id` / `ImageSetID`。来源仅用于旋转题，图片集适用于预设旋转与滑块。使用规则见 [图片集指南](image-sets.md)。已有站点授权保持原范围，需要通过 CLI 显式开启新增题型。

## 错误、超时与复用

SDK 把 API 的错误码、提示、HTTP 状态、请求编号和限流等待秒数作为类型化字段提供。Python 抛出 `StarLockError`，Go 返回可由 `errors.As` 提取的 `*starlock.Error`。响应格式或业务绑定异常使用 `PROTOCOL_ERROR`。

默认网络超时十秒。Go 请求接受调用方 context，并保留取消/截止时间原因供 `errors.Is` 判断；客户端可并发复用。Python SDK 提供同步调用，FastAPI 普通 `def` 路由可直接使用，在异步路由中应交给线程池。

请求只发送一次。网络失败时服务端可能已经创建会话或消费凭证，业务方须按保存的业务状态处理，必要时重新验证。HTTP 重定向会返回 `REDIRECT_DENIED`，站点凭据限定在配置的请求地址。HTTPS 使用系统证书校验，Python 可配置私有 CA，Go 可配置自己的 HTTP transport。[Python urllib.request](https://docs.python.org/3/library/urllib.request.html) · [Go net/http](https://pkg.go.dev/net/http#Client)

## 验证入口

SDK 单元检查可独立运行。

```bash
PYTHONPATH=sdks/python/src python -m unittest discover -s sdks/python/tests -v
```

```bash
cd sdks/go
go test -race -count=1 -timeout=30s ./...
go vet ./...
```

仓库后端测试会启动临时 HTTP 服务、站点数据库和独立 Redis 命名空间，分别用两个 SDK 创建八种题型会话，再完成实际挑战、错误上下文拒绝、正确复核及重复消费拒绝。运行 Go 跨语言测试需要本机装有 Go。

```bash
PYTHONPATH=server python -m unittest discover -s server/verification/tests -p test_server_sdks.py -v
```
