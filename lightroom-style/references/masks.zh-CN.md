# 按明亮度范围局部柔化

[English](masks.md) · 简体中文

蒙版仅在必要时使用：存在明确的局部调整需求，合适的全局调整无法实现而不影响其他区域，或用户明确要求使用蒙版。仅仅要求朦胧效果、或参考图看起来柔和，并不足以决定添加蒙版。全局调整能够达到目标时，跳过本流程，包括局部测量、创建和修改蒙版。根据已有图像判断必要性，不为证明需要蒙版额外增加试调和导出。先看参考／原图中哪些地方显得模糊，再判断目标图对应区域的明暗度和位置，在这些区域降低局部清晰度、纹理。负清晰度降低局部反差，负纹理减弱细节；不等同于镜头失焦，也不生成雾气。

## 一次分析，确定选区

区分亮部泛光、柔和暗部、浅景深和运动模糊，不默认把所有亮部调软。检查相似亮度的眼睛、肤色、衣服及重要边缘：明亮度蒙版也会选中它们。重叠明显时，通过可验证界面做空间交集／减去，或减弱柔化；不能把明确的局部要求改成全局调整。

明暗范围不确定时，对已目视选出的少量区域测量一次。使用原生 SDR sRGB 预览，不直接分析未解码的 RAW／MPO。区域文件示例：

```json
[
  {"name":"haze","role":"soft","box":[0.05,0.1,0.3,0.5]},
  {"name":"face","role":"protect","box":[0.45,0.2,0.6,0.45]}
]
```

box 是摆正方向后图像的左、上、右、下比例坐标；示例不是固定人物位置。

```text
python scripts/analyze_luminance.py PREVIEW.jpg --regions regions.json --output luminance.json
```

脚本只读像素，输出区域亮度 p10／中位数／p90，以及与保护区域的明暗重叠。它不自动识别模糊、不生成蒙版，也不把 SDR 亮度直接当作 Lightroom 滑块刻度。参考与目标分别观察，迁移视觉意图，不跨场景照抄范围。保留简短结论及报告路径，图像和区域未变时不重复分析。

## 一轮调整，统一原生导出

命令模块 0.3.0 在 Classic 13.0.2 支持自动创建明亮度范围蒙版及修改范围。四个递增控制点均为 0..100，依次代表：下端无效果、下端全效果、上端全效果、上端无效果。两侧区间形成渐变过渡；这不是对单个“平滑度”数值的猜测换算。

在[轮次计划](rounds.zh-CN.md)中加入亮部柔化，例如：

```json
{"action":"mask-create","mask_type":"luminance","luminance_range":[40,60,100,100],"clarity":-25,"texture":-20}
```

数值仅演示语法，不是固定预设。清晰度／纹理使用界面绝对值 -100..0，依据照片选择范围与强度。创建明亮度蒙版必须明确指定范围，柔化参数可以提供一个或两个。需要修正时复用同一 ID：

```json
{"action":"mask-adjust","mask_id":"EXACT_RETURNED_ID","luminance_range":[50,65,100,100],"clarity":-15}
```

允许只改范围；保留同一蒙版和其他局部参数。轮次执行器自动获取新鲜校验值、记录快照和 ID、独立读回最终请求值，再与全局调整统一导出。通常一次目视修正即可。

仍支持原生 AI 主体／天空／背景选区创建，不生成替换画面；已有蒙版可按精确 ID 修改清晰度／纹理。范围修改仅适用于启用、未反转、只有一个明亮度工具的简单蒙版。复合／相交蒙版的范围需可验证界面操作，但可以按 ID 调整局部柔化。

## 原生实现与验证

AI 选区使用 LrDevelopController。明亮度创建使用从 Lightroom 13.0.2 捕获的中性 schema-3 结构，每次生成全新 ID，通过 photo:applyDevelopSettings 写入四个范围控制点；保留并核验已有修正条目。这一嵌套结构来自实机观察，不是稳定的公开滑块 API，因此写入限定 13.0.2，其他版本需单独验收或可验证界面，不虚构不透明蒙版数据。

背景创建、明亮度创建与修正均已在 Windows / Classic 13.0.2 完成原生回读和导出。五个明暗纹理带的测试确认：亮部范围主要作用在亮带，暗部范围主要作用在暗带；真实照片的范围修改也已成功渲染。原文件哈希与操作前后的母片设置未变。主体／天空目前只有模拟覆盖。这些证据验证控制行为，不保证新照片的选区或审美效果。

命令单独选择精确 PhotoStyle- 虚拟副本，进入修改照片／蒙版，保存快照；状态过期、选择变化即停止。新蒙版清除支持的数值局部残留，保留中性线性局部曲线；遇到不能安全处理的非中性结构会停止。执行时不要同时操作相同控件。

## 回读与恢复

```text
python scripts/lightroom_client.py mask-read --catalog "CATALOG.lrcat" --path "TARGET.jpg" --photo-id COPY_ID --mask-id MASK_ID
```

返回精简 ID、局部参数、校验值和可识别的原生范围。底层创建支持 `--mask-type luminance --luminance-range 40,60,100,100 --clarity -25`，写操作还需精确身份及新鲜 `--expected-mask-revision-file`。优先使用轮次执行器。

部分失败时，用 status 查询同一请求 ID，再用 mask-read 核对现状。进度包括 snapshot_name、planned_mask_id、created_mask_id、luminance_range_requested、mask_creation_requested、parameters_applied。不能因为超时重新创建；失败不等于自动回滚。

检查交付尺寸和 100% 局部，尤其是相似亮度的保护细节；范围不确定时查看原生叠加层。验收一次最终导出，通过且参数未变时直接复用；回执成功不等于视觉达标。

依据：[Adobe 蒙版指南](https://helpx.adobe.com/lightroom-classic/desktop/process-and-develop-photos/masking.html)、[Adobe SDK 入口](https://developer.adobe.com/lightroom-classic/)、[Adobe Develop API 参考镜像](https://lrc.mcor.dev/modules/LrDevelopController.html)、[Photo API 参考镜像](https://lrc.mcor.dev/modules/LrPhoto.html)。
