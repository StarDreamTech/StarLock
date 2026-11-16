# 星梦旋转验证码预设素材

生成日期：2026-11-15。使用内置 `image_gen.imagegen`，每张单独生成，以现有 [星锁项目 PNG](../assets/brand/starlock.png) 为品牌参考。标准 Logo 保持原样；本组插画延展紫色锁体、四角星锁孔、星轨与暖纸色的视觉语言，没有另造角色设定。

| 名称 | 原图 | 尺寸 | 视觉内容 |
| --- | --- | --- | --- |
| 兰庭微光 | [starlock-garden.png](../assets/rotation/starlock-garden.png) | 1254 × 1254 | 陶瓷紫锁、兰花、桃色丝带与珍珠 |
| 星轨工坊 | [starlock-workshop.png](../assets/rotation/starlock-workshop.png) | 1254 × 1254 | 纸艺紫锁、玻璃星轨、月牙与阶梯 |
| 极光之钥 | [starlock-aurora.png](../assets/rotation/starlock-aurora.png) | 1254 × 1254 | 透光紫锁、四角星、极光与折纸地貌 |

[manifest.json](../assets/rotation/manifest.json) 保存原图尺寸、字节数与 SHA-256。生成原件原样复制，没有用插画替换项目 Logo。官网品牌区可预览和下载。

## 出题方式

`rotation_source: "preset"` 默认随机取一张插画，后端缩放为 256 × 256，随机改变整幅图方向，再独立生成 75°–285° 的内圈校正角度。界面只旋转内圈；正确结果是画面连续，不保证锁体正立。模糊交界、边缘羽化、贝塞尔旋转速度和 5° 校验容差沿用现有规则。

`rotation_source: "procedural"` 保留每题绘制的几何图案。两种来源由业务后端创建会话时选择，刷新保持来源，前端 SDK 不增加属性。挑战响应不包含完整原始素材、文件名或目标角度；官网品牌区和项目源码仍公开这些素材，因此预设图库不能视为秘密。

以下三个文件是首批品牌素材；当前已扩为 23 张、5 套系统图集，并提供自定义上传与后台管理，详见 [图片集指南](image-sets.md)。素材用于品牌体验；随机旋转不代表抗自动识别能力已获验证。生产防护效果和真人完成率仍需独立评估。部署后端时应保留仓库根目录下的 `assets/rotation/`。

## 完整生成提示词

以下三次均使用 `referenced_image_paths` 指向项目 `assets/brand/starlock.png`，`transparent_background: false`。

### 兰庭微光

```text
Use case: stylized-concept. Asset type: square full-bleed illustration used as the source image for StarLock 星锁 rotating-disc verification. Image 1 is the EXISTING project brand reference, NOT an edit target: its dark rounded lock, lilac pink shackle/body, and distinctive four-point-star keyhole are the identity to echo. Create one exquisite tactile 3D miniature sculpture scene, a purple glass-and-ceramic lock inspired by that exact reference, lying diagonally in a surreal orchid studio garden. An asymmetric thin peach ribbon travels across the lock and the image; sculptural lilac leaves, one small champagne pearl and a pale mauve arch continue across foreground and background. Warm ivory / dusty orchid / deep ink purple palette, premium art direction, editorial still life, soft museum lighting, subtle fine grain. Square 1024x1024 composition. The lock occupies roughly 65% of the frame and is offset slightly from center. IMPORTANT intended circular crop: keep the core subject inside the central 85% diameter, distribute distinct asymmetric colored edges and recognizable details throughout the central 40%-75% diameter band, so inner disk and outer ring can be visually aligned. This is a single continuous unbroken scene; do NOT draw circles, rings, seams, puzzle pieces, captcha controls, inset panels, UI or border. No text, no letters, no watermark, no five-point stars, no generic cybersecurity shields, no new mascot or new logo design. Avoid rotational symmetry and featureless background.
```

### 星轨工坊

```text
Use case: stylized-concept. Asset type: one square full-bleed source illustration for a StarLock rotating inner-disc verification challenge. Image 1 is identity reference only: echo the existing purple rounded lock with lilac shackle and FOUR-point-star keyhole, do not invent a new mascot/logo. Create an art-directed paper-and-frosted-glass celestial workshop: a little sculptural lavender lock sits tilted diagonally on a terraced warm-ivory platform, a large asymmetrical sweeping silver-lilac orbital ribbon passes BEHIND and in front of it, a peach glass moon shard at upper left, one blue pearl below right, scattered tiny luminous four-point glints. Physical layered papercraft and translucent resin, quiet cinematic blue-hour lighting, ink-purple shadows, iris purple and lavender with restrained ice blue and warm peach. Square, no white margins. Camera close enough that several colored ribbons, platform edges and the lock silhouette cross the middle 40%-75% diameter band; the core subject is inside the central circular 85% crop. Rich distinctive non-repeating asymmetric visual landmarks throughout. Elegant modern collectible designer object scene, coherent physical depth, sharp crafted edges, subtle textures. NO actual circles/disc masks/seams/UI/controls/arrows/letters/words/numbers/watermarks/border. Avoid radial symmetry, concentric orbit patterns, five-point stars, generic security shields. One continuous illustration, not a contact sheet.
```

### 极光之钥

```text
Use case: stylized-concept. Asset type: square illustration, one preset source image for StarLock 星锁 circular rotation challenge. Reference image 1 is the established brand identity: purple rounded padlock body, lavender-pink shackle and dark four-point-star-shaped keyhole. Render a dreamy gallery still-life of that lock as polished translucent lilac glass, diagonally reclining above a deep plum folded-paper landscape, an asymmetric peach silk ribbon sweeps from lower left past the middle to upper right, a small milky four-point-star sculpture and one frosted blue pearl sit off-axis. Luxurious optical caustics, restrained champagne reflections, rich ink-purple background with soft aurora glow, beautiful material contrast, contemporary collectible art. The lock is a recognizable 3D interpretation of the reference, not a replacement logo, not a new mascot. Square full bleed, single continuous scene without panels. Frame the lock inside central 85% diameter and ensure the irregular silk ribbon, glass lock and contrasting foreground edges cross the central 40%-75% diameter region in multiple places, clearly readable when the picture is displayed as a 256-pixel circle split into an inner disk and an outer ring. Off-center asymmetry, NOT rotationally symmetric. Do not draw any actual circular framing, circle seams, control elements, UI, puzzle holes, text, letters, numbers, watermarks, five-point stars, badges or shields.
```
