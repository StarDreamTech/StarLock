# 网站与 AI 搜索发现

## 已发布的项目入口

公开项目页为 `https://stardreamtech.github.io/projects/starlock/`，组织首页为 `https://stardreamtech.github.io/`，源码位于组织 Pages 仓库 相邻的 `../StarDreamTech.github.io`。

2026-11-15，Pages 提交 `e1f470a` 已推送并构建成功。首页和五个项目页提供独立标题、摘要、canonical、分享信息，以及 Organization、WebSite、WebPage、SoftwareSourceCode 和面包屑 JSON-LD。星锁页补充可见 FAQ、中英文简介和源码文档链接。页面正文默认可见，渐入效果由 JS 就绪后启用。

根路径的 `robots.txt` 允许公开抓取，`sitemap.xml` 包含六个规范页面，`llms.txt` 提供项目与资料链接索引。页脚可访问该索引。元信息与站点地图由 `scripts/update-search.mjs` 同步，用 `scripts/check-search.mjs` 和既有 `check-analytics.mjs` 检查。结构化资料与可见正文保持一致，开发计划和发布状态分别描述。

线上六页及上述资源、分享图片 HTTP 检查通过。使用 OAI-SearchBot、Googlebot 和 bingbot User-Agent 的普通公开请求通过，尚未取得实际机器人抓取日志或搜索平台收录报告。`scripts/submit-indexnow.mjs` 已通知六个 URL，返回 HTTP 202，表示收到通知且所有权验证待处理。`indexnow.txt` 按协议公开托管验证内容。

## Pages 交互试玩

新增 `https://stardreamtech.github.io/projects/starlock/demo/`，页面复用验证码界面，公开样题在浏览器内判定。组织首页、星锁介绍页提供试玩入口，站点地图与资料索引包含演示页，元信息和统计检查共覆盖七个页面。静态 demo 从星锁仓库构建并导出到 Pages 仓库，构建步骤见 `examples/static-demo/README.md`。2026-11-16，Pages 提交 `ece49c9` 构建完成，公开链接返回 HTTP 200。实际线上浏览器完成圆环旋转和数字题，手机视口从项目介绍的试玩入口进入正常，弹窗 340 × 416，无横向溢出。

## 星锁独立官网构建

`npm run build` 通过 `build:site` 调用 `scripts/prerender-home.mjs`，利用 Vue 服务端渲染输出完整初始 HTML。客户端继续按现有入口挂载并加载挑战。静态 HTML 提供产品正文、接入步骤和源码示例链接，避免索引完全依赖 JavaScript 执行。

正式域名确定后，构建时设置 `STARLOCK_PUBLIC_URL` 为 HTTPS 根地址，生成自身 canonical、OG 地址、robots.txt、sitemap.xml。未指定时保留本地预览的 `noindex, follow`。独立域名与公网验证服务尚未确定或部署，当前公开搜索入口仍是组织 Pages。

已检查正式地址配置、静态正文、JSON-LD、重复预渲染、恢复本地配置和清理旧站点地图。39 项前端测试与全构建通过，未重复后端测试。公开域名下示例入口指向 GitHub 文档，本地浏览器继续链接 5179 示例。

## 观察与后续核验

Google Search Console 与 Bing Webmaster Tools 的账户验证和真实收录报告尚未核验。实际排名、AI 引用与推荐效果需发布后观察，HTTP 可访问和 IndexNow 接收分别记录。

实施依据为 Google 的 AI 搜索网站指南、OpenAI 的 OAI-SearchBot 说明和 IndexNow 协议，链接记录在组织 Pages README。`llms.txt` 作为便于读取的资料入口，官方搜索支持和实际访问情况仍以各平台行为为准。
