# 决策、现状与待办

## 核查基线

2026-11-16：版本字段仍为 `0.7.0`。静态交互 demo 源码在 `ccff872` 提交并推送，Pages 的 `ece49c9` 已构建，公开链接 `https://stardreamtech.github.io/projects/starlock/demo/` 返回 HTTP 200。六种题型在本地静态浏览器逐个完成，线上完成圆环和数字题，手机入口与弹窗尺寸检查通过。本轮 42 项前端测试和完整构建通过。图集后台和正式验证 API 仍使用现有服务端协议，生产服务部署与防护效果待验证。历史后端 57 项通过，本轮未修改后端服务代码且未重复运行后端测试。

## 已确认决策

- 产品是可嵌入网站的人机验证服务；不与注册、发邮件等接入方业务耦合，也不承诺与 reCAPTCHA/hCaptcha 的协议或安全能力等价。来源：`README.md`。
- 技术选型已采用 FastAPI + Pydantic + Uvicorn、Pillow、Redis；站点持久数据当前是 SQLite，不以旧 StarDream 的 Django/DRF 服务作为运行依赖。来源：`server/` 与 `docs/implementation.md`。
- 托管脚本统一更新题面，Vue/React 包只封装接入与生命周期；无感是后续触发/升级策略，不代表仅凭鼠标轨迹就能识别人类。来源：`README.md`、`docs/integration.md`。
- 三个星梦项目须各有独立 Logo 并用于 README。星锁为紫色星形锁孔；README 图在 `.github/assets/starlock.svg`，应用品牌资源在 `assets/brand/`，应分别核对使用位置。来源：本项目 README、资源文件及本次对话已确认要求。
- 标准 Logo 与官网场景插画分开；插画不能替代项目标识。官网视觉资料见 `docs/brand-assets.md`、`docs/home-design.md`，与 `examples/playground/` 当前源码对照，旧首页设计记录不代表现行实现；当前官网和图集后台均有浏览器运行记录，见 `docs/verification.md`。
- 当前官网为深紫/雾白、无衬线排版，完整紫色玻璃锁体贯穿首屏；标准 Logo 未改。先前的宋体加方形配图及抽象星轨首屏已退出使用。源码为 `examples/playground/src/App.vue`、`home.css`；主视觉 `assets/brand/starlock-hero-v2.png`，提示词与校验见 `docs/home-design.md`。

## 已核实实现与易错点

- 四段验证 API、站点授权、短期会话、一次性复核与六种题型已有实现，详见 `architecture.md` 和对应源码。
- 独立直线/曲线滑块、速度缓动和旋转不是同一概念；空间曲线不能替代速度曲线，贴合必须同时满足位置与角度。来源：`server/verification/sliders.py`。
- 官网串行处理演示会话和复核，快速切换只显示最后选择，避免旧响应覆盖上下文。查看 `examples/playground/`，不要把官网的演示业务提交行为复制为 SDK 自动提交业务。
- 官网从 `main.ts` 单独加载 `home.css`；普通网页/React 示例仍继承原 `style.css`，SDK 弹窗使用独立 Shadow DOM。改官网视觉不能误把新全局样式传播到接入示例或宿主网站。
- 预设图库由后台管理，共 23 张系统图、5 套系统图集，可自定义上传。默认图库与显式 `image_set_id` 均由后端会话绑定；客户多租户与站点控制台尚未实现。来源：`docs/image-sets.md`、`server/verification/image_sets.py`。
- 原图可能随源码公开；图库数量、随机旋转和局部模糊都不构成抗自动识别效果证明。来源：`docs/image-sets.md`。

## 待办与待定

- **待办**：顺序点选、静态九宫格，之后再做无感与行为评分；目前不标成已实现。来源：`docs/implementation.md` 的下一阶段。
- **待办**：站点控制台、密钥轮换接口、生产数据库部署、TLS/网关、容量与识别效果评估；npm、正式 CDN、公共验证服务尚未发布。来源：`README.md`。
- **待验证**：真实触屏和跨浏览器、Redis Cluster/跨地域一致性与持久故障恢复。来源：`docs/verification.md`、`docs/implementation.md`。
- **待定**：生产持久数据库、正式域名、部署方案及后续风控模型；有新决策或实测后在本节替换，不追加互相矛盾的旧结论。
