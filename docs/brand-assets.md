# 星锁品牌与视觉资产

## 当前标准 Logo

当前项目标识是紫粉色锁体与四角星形锁孔，不是星梦通用的蓝色代码五星。用户提供的 `StarDreamTech-project-logos.zip` 内含 `starlock.svg` 与 `starlock.png`，已逐字节复制到 `assets/brand/`，未重新生成或改动标识图形。

- [项目 SVG](../assets/brand/starlock.svg)：页头、favicon、页脚、品牌区；托管 SDK 内嵌同一文件的 data URL，独立接入无需额外下载 Logo。
- [项目 PNG](../assets/brand/starlock.png)：保留用于其他展示与导出。
- [素材清单](../assets/brand/manifest.json)：记录原件尺寸、字节数与 SHA-256。

## 当前官网视觉

2026-11-15 重做官网视觉，以深紫 `#110e1b`、雾白 `#faf9fc` 和浅兰紫 `#dcc4f2` 建立明暗节奏。首屏使用专用的 [宽幅玻璃锁体场景](../assets/brand/starlock-hero-v2.png)，配合无衬线大标题，图片贯穿首屏背景；完整锁体和四角星锁孔始终是主体。页头和页脚的标准 Logo 保持原件。

官网的 `home.css` 统一导航、体验卡片、架构、接入代码和品牌区的字号、间距与状态。普通网页/React 接入示例继续使用原样式文件，托管验证码弹窗独立隔离。交互逻辑没有随官网重做；所有过渡遵循减少动态效果偏好。

之前的抽象星轨组件 `BrandOrbit.vue` 与「星轨工坊」左右分栏首屏均已退出首页；「星轨工坊」仍保留作旋转预设和品牌素材。[设计说明、生成提示词及原图校验](home-design.md)。

原蓝色五星 `stardream-logo.svg` 和下面的早期生成插画保留作历史素材，当前页面不再把它们当作星锁项目 Logo。

## 验证码图片集

新增 20 张内置 imagegen 生成的星锁品牌场景，按星际、材质、自然、空间分成四套图集；加原有 3 张，共 23 张、5 套系统图集。新增原图保存在 `server/assets/image-sets/`，提示词规格在该目录 `prompts.json`，SHA-256 在 `generated.json`。由后台管理系统与自定义图库，预设旋转及指定图库的滑块都可使用；标准 Logo 不变。详见 [图片集与后台](image-sets.md)。

## 首批旋转验证品牌预设

新增三张以当前紫色锁体、四角星锁孔和星轨为视觉线索的插画：兰庭微光、星轨工坊、极光之钥。它们用于圆环旋转题的预设图片来源，原有随机几何来源继续保留。标准 Logo 文件没有更改；插画是品牌场景延展，不代替标准标识。

原图位于 `assets/rotation/`，由内置 `image_gen.imagegen` 分别生成。官网品牌区可以预览和下载；完整提示词、尺寸、文件校验清单和出题说明见 [旋转素材说明](rotation-assets.md)。

---

# 历史插画与生成提示词

本组图用于首页、产品介绍和验证成功状态。参考星梦已有的蓝色圆角五角星和组织官网的深空色系，新增玻璃星体、珍珠光点和轨道曲线；原标识保持独立，不以生成插画替换标准 logo。

| 文件 | 用途 | 原图尺寸 | 历史用途 |
| --- | --- | --- | --- |
| `assets/brand/starlock-hero.png` | 深色首页主视觉，左侧留文字空间 | 1672 × 941 | 首页 hero |
| `assets/brand/starlock-orbit.png` | 光轨背景、产品介绍或后续素材探索 | 1672 × 941 | 品牌素材区 |
| `assets/brand/starlock-success.png` | 成功状态与浅色插画 | 1254 × 1254 | 后端复核成功状态、品牌素材区 |
| `assets/brand/stardream-logo.svg` | 既有星梦标识，直接复制保留 | 矢量 | 旧版页头与 favicon，现已替换 |

生成方式：内置 `image_gen.imagegen`，每个素材单独生成；未使用外部收费 API、未向前端嵌入密钥。PNG 原图已经复制到项目，生成原件保持不变。页面中的中文与按钮由 HTML/CSS 绘制，图片本身没有文字。

建议色彩：深空 `#05060f`、星梦蓝 `#3f7ef7`、浅紫 `#b9a6ff`、冰蓝 `#7fd8ff`、少量香槟金 `#f3d38c`。避免把光轨图片当作带正确答案的题面使用；正式滑块、点选和九宫格必须经过独立出题、素材授权及答案质量流程。

参考文件：本地 `stardream-logos/logo.svg`、`stardream-logos/logo.png` 与 `StarDreamTech.github.io/css/style.css`。插画是这次生成的新视觉提案，标准 logo 的形状与白色代码符号保留在原 SVG 中。

## 完整生成提示词

### 1. 首页主视觉

```text
Use case: stylized-concept. Asset type: wide website hero artwork for 星锁 StarLock, the human verification product in the 星梦 StarDreamTech brand family. Create an exquisitely art-directed premium technology sculpture: one rounded five-point cobalt blue star like the brand reference, transformed into a luminous optical-glass and satin-blue metallic object, subtly protecting a tiny warm pearl at its center; one graceful silver-cyan orbital curve passes around it suggesting a Bezier motion path and quiet trust. Floating above an infinite near-black ink-blue studio background (#05060f), restrained lavender and ice-cyan rim lighting, tiny champagne highlights, meticulous material realism, soft shadow, contemporary museum object photography crossed with generative sculpture, calm rather than aggressive cybersecurity. Wide landscape composition, sculpture on the right half, left 45 percent almost empty deep midnight gradient for real HTML headline, sophisticated asymmetry, beautiful generous negative space. Color reference cobalt #3f7ef7, lavender #b9a6ff, cyan #7fd8ff, small warm gold #f3d38c. No text, no typography, no letters, no code symbols, no watermark, no badges, no user interface, no collage, no padlock icon, no circuit-board cliches. This is one finished full-bleed illustration, not a mockup or contact sheet.
```

### 2. 流动光轨

```text
Use case: stylized-concept. Asset type: wide abstract brand background for a human verification developer portal and future slider challenge image art, 星锁 StarLock by 星梦 StarDreamTech. Primary request: an elegant fine-art digital landscape of fluid satin-glass ribbons describing one sweeping cubic Bezier arc above a quiet midnight surface; the arc rises from bottom left into a delicate five-point-star-shaped glint in the upper right, suggestions of celestial orbits, absolutely restrained and spacious. Photographic 3D material study, optical glass, thin brushed cobalt metal, soft volumetric ice-blue and lavender reflections, an understated warm pearl light. Landscape wide format, no hard central subject, flowing asymmetry, large clean areas suitable for interface overlay, moody midnight ink #05060f, cobalt #3f7ef7, lavender #b9a6ff and cyan #7fd8ff. Feel like a contemporary design museum identity, highly polished and artistic, beautiful organic light rather than gaming. No text, no numbers, no watermark, no interface, no actual captcha puzzle cutouts or answer markers, no locks, no shields, no stock circuit board motifs. Full bleed finished artwork.
```

### 3. 成功状态

```text
Use case: stylized-concept. Asset type: square verification success illustration for 星锁 StarLock, part of 星梦 StarDreamTech. A single beautiful rounded five-point cobalt-blue star sculpted from optical frosted glass and satin ceramic, floating gently in a calm almost-white pearl studio with an extremely subtle cool lavender gradient. Inside the star a small warm luminous pearl surrounded by one thin silver orbital ring conveys quiet trust and completed verification. Star clearly five-point, soft rounded silhouette, modest and sophisticated, luxury contemporary product photography, delicate cyan caustics, soft contact shadow, tactile crafted object, generous clean margin on all sides, centered composition suitable as a success-state spot illustration. Restrained brand colors #3f7ef7 cobalt, #b9a6ff lavender, #7fd8ff ice cyan and tiny #f3d38c champagne highlights. Artwork only, no words, no letters, no code glyphs, no numbers, no checkmark, no watermark, no UI, no mockup, no shield, no padlock. One finished square image, luminous but not flashy.
```
