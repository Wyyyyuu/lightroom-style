# 色调曲线

[English](curves.md) · 简体中文

需要 S 型曲线、柔化黑白端点或更细致的影调分离时阅读本指南。先在当前调色版本的副本上只改曲线并对比，再调整其他控件。

## 根据照片选择曲线

- 白色 **RGB 综合点曲线** 同时调整所有通道。抬高黑色端点可柔化黑位，压低白色端点可收敛亮部，中间锚点用于调整层次。这可能适合柔和的日系观感，但不是默认预设，也不能代替参考图分析。
- 端点压缩与中间调反差是两个独立决定。轻微 S 型会压低较暗的中间调、抬高较亮的中间调；应保持主体清晰，避免头发死黑、白色发灰或肤色反差过强。逆光面部可能需要更平缓的曲线下段。
- 先检查已有曲线、配置文件、曝光和基本面板中的对比度。有意识地保留或替换现有锚点，不要无意中叠加两条 S 型曲线。压低端点无法恢复 JPEG 中已丢失的高光细节。
- RGB 综合曲线也可能改变饱和度。需要检查原生渲染中的肤色与色相关系。独立 R/G/B 通道曲线属于不同的颜色控件，不能与白色综合曲线混为一谈。

## 原生点曲线操作

要求命令模块版本为 `0.2.2`、色调曲线面板已启用，且使用 SDR PV2012 坐标。使用 `curve`，而不是数值参数 `--set`。坐标为 0–255 的输入/输出整数对：共 2–16 对，输入严格递增，输出不递减，首尾输入分别为 0 和 255。

```python
from lightroom_client import send_command

identity = dict(catalog=catalog_path, path=target_path, photo_id=copy_id)
receipt = send_command("read", **identity)
assert receipt["ok"] and receipt["command_version"] == "0.2.2"
photo = receipt["result"]["photo"]
# Illustration only: softer endpoints with a mild middle S; adapt to the image.
points = [[0, 12], [32, 30], [64, 57], [128, 129],
          [192, 204], [224, 232], [255, 246]]
result = send_command("curve", **identity, curve_points=points,
                      expected_revision=photo["curve_revision"])
assert result["ok"] and result["result"]["readback_verified"]
```

从本 skill 的 `scripts` 目录导入客户端。示例仅演示柔化端点与轻微中段 S 型，实际坐标需根据照片调整。`curve_revision` 是新一次读取返回的不透明状态校验值，用于拒绝过期状态；必须原样传入。对应 CLI 接受 `--curve-points "0,12;32,30;64,57;128,129;192,204;224,232;255,246"` 和 `--expected-revision-file FILE`（文件包含原样的 UTF-8 校验值，不添加换行）。

桥接会为副本创建快照，写入 `ToneCurvePV2012` 及其存在时对应的扩展表示，将综合曲线名称设为 Custom，并验证结果。原有独立 RGB 曲线、参数曲线值、区域边界、配置文件与基本设置必须保持不变。面板禁用、HDR、过期状态及含义不明确的扩展曲线会被拒绝。返回坐标为带索引的对象；比较时按键的数值顺序解码。

## 参数曲线方案

`ParametricShadows`、`ParametricDarks`、`ParametricLights` 和 `ParametricHighlights` 均接受 -100…100，通过 `apply` 与最新的 `--expect` 值写入；详见[桥接指南](bridge.zh-CN.md)。它们调整影调区域而非明确端点，也不同于基本面板的阴影/高光。区域调整足够时可以使用。Darks -10 / Lights +10 只是示例，并非通用 S 型曲线。桥接要求面板已启用，并保留点曲线和区域边界。

独立 RGB 点曲线、区域边界修改以及 HDR 曲线写入需要经过验证的原生 UI 通道；不要声称桥接已支持这些操作。

## 验收

独立回读控制点/参数值，并在相同尺寸与色彩空间下检查原生导出的前后图。关注面部、黑白端点细节、偏色、饱和度、色带和影调分离。只有成功回执、渲染却没有变化，不足以通过验收。不能仅凭锚点坐标推断 Lightroom 的精确样条曲线或最终像素亮度。失败后结合快照与请求 ID 核清状态，禁止盲目重发。

参考：[Adobe Lightroom Classic 影调与颜色控件](https://helpx.adobe.com/lightroom-classic/desktop/process-and-develop-photos/image-tone-color.html)。
