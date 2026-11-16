# 星锁官网视觉重构

日期：2026-11-15。

## 构图与层级

- 首屏改为完整的深紫品牌场景，紫色玻璃锁体位于右侧，左侧保留标题与操作的阅读空间。场景延续标准 Logo 的完整锁体和四角星锁孔，不重新设计 Logo。
- 标题改为无衬线字体，「让信任，自然发生」分两行，导航、正文、辅助文字和按钮按职责建立字号层级。取消之前的暖纸宋体配方和独立方形图片框。
- 主按钮打开真实验证码弹窗；右下角体验卡也可打开圆环验证。框架能力条说明已有接入方式，不展示虚构客户、通过率或性能指标。
- 体验区使用清晰的选中卡片与品牌标识；架构区区分已实现能力和规划；接入代码保留普通网页、Vue、React 切换；页脚提供体验入口。
- 手机采用独立纵向构图：文字和操作在上方，完整锁体在下方，品牌场景按右侧主体裁切，不把桌面双栏等比缩小。

## 文件边界

官网单独使用 `examples/playground/src/home.css`。普通网页与 React 示例继续从原 `style.css` 继承样式，验证码 SDK 的 Shadow DOM 弹窗也不受官网样式影响。会话、刷新、题型选择、一次性凭证与服务端复核逻辑保持原有实现。

## 新主视觉

生成方式：内置 `image_gen.imagegen`，参考项目 `assets/brand/starlock.png`，`transparent_background: false`。

原图：[starlock-hero-v2.png](../assets/brand/starlock-hero-v2.png)，1774 × 887。原始输出直接复制进仓库，未改动早期主视觉或标准 Logo。文件 SHA-256 见 [hero-v2-manifest.json](../assets/brand/hero-v2-manifest.json)。

完整提示词：

```text
Use case: stylized-concept. Asset type: ultra-wide cinematic full-bleed website hero background, ideally aspect 2:1 landscape, for premium human-verification infrastructure brand StarLock. Reference image 1 is the fixed existing logo identity: a rounded purple padlock with a lilac shackle and distinctive FOUR-point-star negative-space keyhole. Translate that recognizable complete lock silhouette into one exquisitely crafted floating lilac optical-glass and satin-metal sculpture, three-quarter view, dominating the RIGHT 48 percent of a wide composition, slightly tilted clockwise, keyhole clearly visible. A single flowing thin iridescent ribbon sweeps from low center behind and in front of the lock toward top right; small lavender light beads, beautiful soft caustics, precise premium industrial details, translucent edges. Environment: seamless deep dark aubergine / near-black purple #110e1b studio, grounded violet light haze on the lower right, restrained soft lavender bloom around the lock. The left 48 percent is very quiet almost-black plum negative space reserved for real HTML headline, with only a subtle organic glow near the bottom; DO NOT put props or the subject there. Art direction: high-end contemporary tech brand meets sculptural fine art and museum object photography. Elegant, restrained, confident, not cute, not toy-like, not gaming, not kitsch. Lock fills roughly 80 percent of image height on the right but stays fully visible within the frame with some breathing room. Wide edge-to-edge continuous image with no frame or panels. No text, typography, UI, buttons, digits, watermark, generic shield, five-point stars, paper landscape, flowers, mountains or architectural sets. It must obviously depict the supplied purple lock brand, not an abstract circular disc. One finished production-quality illustration.
```
