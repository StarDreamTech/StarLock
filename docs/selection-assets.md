# 文字点选与语义图片素材

## 语义图库

首版十二张图片由内置 imagegen 生成，经逐张检查，分别标注为四张小汽车、四张船只和四张水果。每图只包含一个主要类别，题目与类别关系定义在 `server/verification/selections.py`，没有使用未经确认的自动标签。

最终素材位于 `server/assets/semantic/`。`manifest.json` 保存场景提示词、共同生成约束、生成输出编号、类别、尺寸、字节数和 SHA-256。每张 `768 × 768` JPEG，质量 82，约 64–133 KB。原始生成 PNG 留在生成输出归档，服务端只读取项目中的压缩图。

生成采用写实照片风格，主体在 100 像素缩略图下可辨认，画面不包含文字、品牌、人物或其他题库类别。车辆包含轿车、两厢车、SUV 与双门车，船只包含帆船、机动艇、皮艇和木划艇，水果包含苹果、香蕉、橙子和葡萄。实际输入场景及共同约束整理在清单中。

运行时裁为 `192 × 192` JPEG，质量 84，当前每张约 7–12 KB，九张图片和题面 JSON 约 117–124 KB。下发图片使用 data URL，格子只有临时随机标识。公开响应不包含清单标签、来源文件名或正确集合。

当前自定义上传后台管理旋转和滑块的通用素材。语义图库使用独立清单，增加类别需要同时补齐图片、审核标签和明确题目；后台标注编辑与自定义语义题库尚待实现。

## 中文字体

文字点选使用 Google Fonts 发布的 Noto Sans SC 可变字体，服务端渲染后返回 PNG，字体文件不进入前端下载。

- 字体路径为 `server/assets/fonts/NotoSansSC.ttf`，使用字重 600。
- 来源为 [Google Fonts Noto Sans SC](https://github.com/google/fonts/tree/main/ofl/notosanssc)。
- 授权为 SIL Open Font License 1.1，完整许可随文件保存为 `server/assets/fonts/OFL.txt`。

文字、位置、颜色和小角度旋转逐题生成。文字点选输出为 `300 × 180` PNG，当前约 12–15 KB。

## 网页图像

`scripts/optimize-web-assets.py` 从现有品牌原图生成网页 WebP，保留原图。官网与 demo 使用约 36 KB 的主图，图库展示使用约 51–77 KB 的品牌图。

```bash
.venv/bin/python scripts/optimize-web-assets.py
```

图片扩容、压缩和随机排布的效果以功能及传输体积为验收内容。对抗识别与真人完成率需要另行评估。
