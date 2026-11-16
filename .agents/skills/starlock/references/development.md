# 开发与验证

## 环境与入口

环境要求和命令来自根目录 `README.md`、`package.json` 与 Python 锁文件。当前使用 Python 3.12、uv、Node.js 22.12+ 或兼容的新 LTS、npm 与 Redis 7+。Python 运行依赖锁定在 `server/requirements.lock`，测试依赖锁定在 `server/requirements-dev.lock`。

常用启动流程（从仓库根目录；涉及服务启动时仍遵循当前任务授权）：

```bash
uv venv --python 3.12 .venv
uv pip sync --python .venv/bin/python server/requirements.lock
npm ci
docker compose up -d redis
env STARLOCK_DEBUG=1 .venv/bin/python server/cli.py init-db
env STARLOCK_DEBUG=1 STARLOCK_DEMO=1 .venv/bin/uvicorn --app-dir server main:create_app --factory --host 127.0.0.1 --port 8018 --no-proxy-headers
```

另开终端使用 `npm run dev` 启动官网本地版，或 `npm run dev:hosted` 启动独立网页示例。

| 入口 | 默认本地端口 |
| --- | --- |
| 验证 API 与托管脚本 | 8018；脚本路径 `/sdk/v1/api.js` |
| 图片集运营后台 | 8018；路径 `/admin`，本地开发可直接进入 |
| 官网本地版 | 5178 |
| 独立接入示例 | 5179；React 页面为 `/react.html` |
| Redis | 6391，仅本机监听 |

这些地址指服务所在的电脑，不能作为公网服务地址。Redis 本地配置在 `compose.yaml`，由 Docker Compose 自动发现；不自行新建第二套配置。

## SDK 接入约定

- 官网开发代理转发 `/sdk`、`/v1`、`/demo`；独立示例的挑战请求跨源直连验证 API。
- 普通网页使用 `window.StarLock.render`；Vue 3 与 React 18.2+/19 封装加载同一远程 SDK，包目前是私有工作区源码。
- 默认弹窗显示；需要嵌入式界面时用已有 `displayMode: 'inline'`。卸载、换票据时清理旧实例及过期回调。
- 默认 `apiBase` 来自脚本地址；空字符串表示宿主同源接口，脚本与 API 分开部署时显式配置。更多参数查 `docs/integration.md`。
- 修改托管组件后需要重新 `npm run build:sdk` 并刷新宿主页；旧脚本缓存会使界面看起来没有变化。

## 验证入口

```bash
uv pip sync --python .venv/bin/python server/requirements-dev.lock
env PYTHONPATH=server .venv/bin/python -m unittest discover -s server/verification/tests -v
npm test
npm run build
```

按改动选择后端、客户端或构建检查，记录实际运行结果。`npm run build` 包含类型检查、SDK、官网和独立接入示例构建。后端测试使用独立 Redis 命名空间，不清空现有 Redis 数据。

历史结果与局限见 `docs/verification.md`；文档中的通过记录不等于本轮已运行。真实触屏、其他浏览器、生产容量、真人完成率与抗识别能力需要分别验证。

最近官网视觉检查：2026-11-15，39 项前端测试、类型检查和全构建通过；Chromium 1440 × 1000、390 × 844、320 × 740 模拟视口已检查，首屏入口和题型卡可打开实际挑战，Esc 关闭、React/Vue 接入代码切换可用。320 像素下弹窗收缩为 296 × 416，主要布局无横向溢出；不等同于 Safari、Firefox 或真实触屏验证。依据 `docs/verification.md` 的官网整体视觉重构记录。

## 开发与生产边界

`STARLOCK_DEMO=1` 只在显式 DEBUG 下注册演示业务接口；正式接入不用演示后端。非开发模式须提供自己的服务端密钥，交互文档与 OpenAPI 路由关闭。CORS 只开放已授权来源的挑战接口，不携带 cookie；会话创建和凭证复核不开放浏览器跨源调用。生产 HTTPS、代理信任链与网关部署尚需独立处理。

## 图片集验证基线

2026-11-15：57 项后端、39 项前端测试、类型检查及全构建通过。新增图集测试在 `server/verification/tests/test_image_sets.py`，使用临时 SQLite 和隔离 Redis。实际浏览器跑通批量上传、重复去重、图集默认选择，以及自定义图的官网旋转题和后端复核；管理页桌面与 390 px 无横向溢出。保留的本地上传演示图集已停用，默认恢复 23 张系统随机。未发布新的公网后台、未测生产抗识别效果。运维、备份、配额和认证细节见 `docs/image-sets.md`。

## 仓库同步核验

2026-11-16，功能与官网两批提交 `82104df`、`7d39dd7` 已推送 `https://github.com/StarDreamTech/starlock` 的 `main`，远程提交号核对通过；同日重新运行 57 项后端、39 项前端测试与完整构建通过。组织 Pages 远程保持 `e1f470a`。后续状态检查以实时 `git status` 和 `git ls-remote` 为准，不以此前的测试通过或本地提交代替推送成功。

## Pages 试玩构建

`npm run dev:demo` 启动独立的静态体验页，默认端口 5182。`npm run build:demo` 输出 `dist/static-demo/`，完整 `npm run build` 也包含该构建。导出命令为 `node scripts/export-demo.mjs ../StarDreamTech.github.io/projects/starlock/demo`，会替换目标的生成资产目录；详细操作在 `examples/static-demo/README.md`。

2026-11-16 文字点选与语义九宫格轮完成 61 项后端、49 项前端测试、类型检查及完整构建。Vue 官网与 React 手机模拟视口均完成两种新题的实际服务端复核；静态 demo 完成两种新题，九宫格 390×844 视口的弹窗为 340×564，无横向溢出。真实触屏与 Safari/Firefox 尚未检查。单题懒加载及压缩图像尺寸依据 `docs/selection-assets.md`。


## 服务端 SDK 验证

2026-11-16 新增 Python / Go SDK。Python 源码及安装后的 wheel 均通过七项测试；Go 六项常规测试通过竞态检测，`go vet` 通过，另由服务端的隔离 HTTP 测试运行 `TestLiveAPI`。完整服务端六十三项、前端四十九项及全构建通过。

`server/verification/tests/test_server_sdks.py` 使用临时站点数据库、HTTP 端口与隔离 Redis 命名空间，分别由 Python 与 Go 创建八种会话，再完成实际挑战与一次性复核，检查错误上下文和重复消费。没有 Go 环境时，仅跨语言那项跳过，不能据此声称已完成 Go 实测。

Python 独立单元入口为 `PYTHONPATH=sdks/python/src python -m unittest discover -s sdks/python/tests -v`。Go 在 `sdks/go` 内运行 `go test -race -count=1 -timeout=30s ./...` 和 `go vet ./...`。Python 构建采用 `uv build --wheel sdks/python`，构建目录与 egg-info 已在该 SDK 的 `.gitignore` 中排除。最低语法目标 Python 3.10 / Go 1.22，本轮实际执行环境为 Python 3.12.13、Go 1.25.0，其他版本待独立测试。
