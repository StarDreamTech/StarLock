# Pages 交互 demo

访问 https://stardreamtech.github.io/projects/starlock/demo/ 即可试玩八种验证码。默认打开圆环旋转题，点击题型卡直接切换，支持输入、拖动、换题和键盘操作。

页面复用 `packages/browser` 的弹窗、题面和生命周期。`transport.ts` 在本页内判定公开样题，模拟答错、次数耗尽、换题和过期。样题包含公开答案，演示凭证使用 `demo_only` 前缀。业务接入继续使用正式服务端创建会话、验证和一次性凭证复核。

`StarLockClient` 的可选第二个构造参数提供请求实现，`createRuntime` 将该实现传给内部组件。正式脚本入口沿用默认网络请求，demo 的判定代码与公开答案仅由本 demo 入口打包。

## 本地预览

```bash
npm run dev:demo
```

打开 http://127.0.0.1:5182 。此页面运行需要前端静态资源，每次按需获取一份当前题型的样题，换题再加载下一份。当前文字点选样题约 16–20 KB、九宫格样题约 117–124 KB、旋转样题约 299–350 KB（含公开演示解和 base64 图片）；已加载样题在页面内缓存。

## 构建并同步组织 Pages

```bash
npm run build:demo
node scripts/export-demo.mjs ../StarDreamTech.github.io/projects/starlock/demo
```

导出目标应是专用于本 demo 的目录。导出脚本替换其中 Vite 生成的 `assets/`，复制构建文件及第三方许可，并接上组织 Pages 的主题初始化和统计脚本。

然后在组织 Pages 仓库同步和检查元信息。

```bash
node scripts/update-search.mjs
node scripts/check-search.mjs
node scripts/check-analytics.mjs
```

将组织 Pages 仓库提交并推送后等待 GitHub Pages 构建。源项目提供 `transport.test.ts`，检查 32 道样题均通过同一客户端完成、失败次数、换题替换与过期恢复。

## 更新样题

以下命令使用已安装服务端依赖的 Python 环境。生成器复用真实题型生成和几何校验，在导出前校验每道视觉题有可通过的位置。

```bash
.venv/bin/python scripts/generate-demo-challenges.py
npm run build:demo
```

输出包含 `public/challenges/<题型>/<0–3>.json` 单题文件，每种题型四道。聚合文件 `public/challenges.json` 保留给此前缓存的 demo 与测试使用，新入口按单题加载。更新后按上面的导出步骤同步 Pages。
