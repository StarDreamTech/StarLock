# 决策、现状与待办

## 核查基线

2026-11-16：当前版本 `0.8.0` 提供八种题型、托管 HTML/Vue/React 接入及 Python/Go 业务后端 SDK。最新 SDK 功能 `b5989c5`、文档 `aa18e01` 已推送，Pages `b9c70a5` 已构建并公开 SDK 指南入口。63 项后端、49 项前端、Python SDK 七项、Go 常规竞态测试与真实 API 跨语言闭环通过，Python wheel/源码安装及 Go 远程模块导入复验通过。正式验证 API、npm/PyPI、Go 版本标签、CDN 与生产防护效果仍待发布或验证。

## 已确认决策

- 产品是可嵌入网站的人机验证服务；不与注册、发邮件等接入方业务耦合，也不承诺与 reCAPTCHA/hCaptcha 的协议或安全能力等价。来源：`README.md`。
- 技术选型已采用 FastAPI + Pydantic + Uvicorn、Pillow、Redis；站点持久数据当前是 SQLite，不以旧 StarDream 的 Django/DRF 服务作为运行依赖。来源：`server/` 与 `docs/implementation.md`。
- 托管脚本统一更新题面，Vue/React 包只封装接入与生命周期；无感是后续触发/升级策略，不代表仅凭鼠标轨迹就能识别人类。来源：`README.md`、`docs/integration.md`。
- 三个星梦项目须各有独立 Logo 并用于 README。星锁为紫色星形锁孔；README 图在 `.github/assets/starlock.svg`，应用品牌资源在 `assets/brand/`，应分别核对使用位置。来源：本项目 README、资源文件及本次对话已确认要求。
- 标准 Logo 与官网场景插画分开；插画不能替代项目标识。官网视觉资料见 `docs/brand-assets.md`、`docs/home-design.md`，与 `examples/playground/` 当前源码对照，旧首页设计记录不代表现行实现；当前官网和图集后台均有浏览器运行记录，见 `docs/verification.md`。
- 当前官网为深紫/雾白、无衬线排版，完整紫色玻璃锁体贯穿首屏；标准 Logo 未改。先前的宋体加方形配图及抽象星轨首屏已退出使用。源码为 `examples/playground/src/App.vue`、`home.css`；主视觉原图 `assets/brand/starlock-hero-v2.png`，网页使用约 36 KB 的 WebP 衍生图，提示词与校验见 `docs/home-design.md`。

- 业务后端 SDK 优先提供 Python 与 Go。当前已实现同步 Python 和带 context 的 Go 标准库客户端，验证服务继续沿用 FastAPI。来源 `docs/server-sdks.md`。

## 已核实实现与易错点

- 四段验证 API、站点授权、短期会话、一次性复核与八种题型已有实现，详见 `architecture.md` 和对应源码。
- 独立直线/曲线滑块、速度缓动和旋转不是同一概念；空间曲线不能替代速度曲线，贴合必须同时满足位置与角度。来源：`server/verification/sliders.py`。
- 官网串行处理演示会话和复核，快速切换只显示最后选择，避免旧响应覆盖上下文。查看 `examples/playground/`，不要把官网的演示业务提交行为复制为 SDK 自动提交业务。
- 官网从 `main.ts` 单独加载 `home.css`；普通网页/React 示例仍继承原 `style.css`，SDK 弹窗使用独立 Shadow DOM。改官网视觉不能误把新全局样式传播到接入示例或宿主网站。
- 预设图库由后台管理，共 23 张系统图、5 套系统图集，可自定义上传。默认图库与显式 `image_set_id` 均由后端会话绑定；客户多租户与站点控制台尚未实现。来源：`docs/image-sets.md`、`server/verification/image_sets.py`。
- 原图可能随源码公开；图库数量、随机旋转和局部模糊都不构成抗自动识别效果证明。来源：`docs/image-sets.md`。

- 新增语义图库为十二张 768×768 JPEG，64–133 KB；实际单格 192×192 JPEG，7–12 KB。官网使用 WebP 衍生图，Pages 按单题懒加载。来源 `docs/selection-assets.md`、`examples/static-demo/`。

## 待办与待定

- **待办**：语义标签后台、扩充分类与多轮换图、图形顺序点选、无感与行为评分。来源：`docs/implementation.md` 的下一阶段。
- **待办**：站点控制台、密钥轮换接口、生产数据库部署、TLS/网关、容量与识别效果评估；npm、正式 CDN、公共验证服务尚未发布。来源：`README.md`。
- **待验证**：真实触屏和跨浏览器、Redis Cluster/跨地域一致性与持久故障恢复。来源：`docs/verification.md`、`docs/implementation.md`。
- **待定**：生产持久数据库、正式域名、部署方案及后续风控模型；有新决策或实测后在本节替换，不追加互相矛盾的旧结论。
