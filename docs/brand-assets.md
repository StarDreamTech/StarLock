# 星锁品牌与视觉资产

## 当前标准 Logo

当前项目标识是紫粉色锁体与四角星形锁孔，不是星梦通用的蓝色代码五星。用户提供的 `StarDreamTech-project-logos.zip` 内含 `starlock.svg` 与 `starlock.png`，已逐字节复制到 `assets/brand/`，未重新生成或改动标识图形。

- [项目 SVG](../assets/brand/starlock.svg)：页头、favicon、页脚、品牌区；托管 SDK 内嵌同一文件的 data URL，独立接入无需额外下载 Logo。
- [项目 PNG](../assets/brand/starlock.png)：保留用于其他展示与导出。
- [素材清单](../assets/brand/manifest.json)：记录原件尺寸、字节数与 SHA-256。

## 0.7.0 官网视觉

采用暖纸色 `#f4f0e9`、墨紫 `#2c2433`、兰紫 `#a16fb4`，以中文衬线字、星形负空间、细线星轨与低强度纸面肌理构成视觉。首页光学星轨是可编辑的原生 SVG/Vue 组件 [BrandOrbit.vue](../examples/playground/src/BrandOrbit.vue)，不是通用五星图片或一张界面截图。

官网与独立接入示例共用样式语言；验证码本身是带独立 Logo 的悬浮弹窗。正文和操作说明使用更深的紫灰色保证可读性，细小浅色标记仅作装饰。所有装饰动画遵循减少动态效果偏好。

原蓝色五星 `stardream-logo.svg` 和下面的早期生成插画保留作历史素材，当前页面不再把它们当作星锁项目 Logo。

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
