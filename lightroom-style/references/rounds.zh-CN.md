# 已连接环境下的调色与精简轮次

[English](rounds.md) · 简体中文

桥接已连接时使用本流程。安装、恢复、详细参数范围和底层操作按需阅读 [bridge.md](bridge.md)；曲线决策阅读 [curves.md](curves.md)。脚本交换请求，Lightroom 负责所有调色与渲染。

## 一次准备

运行 `python scripts/lightroom_probe.py --timeout 15`，核对新鲜的协议 1 回执和成功的目录能力，记录精确目录路径。未连接时按桥接指南恢复。曲线、颗粒需从命令回执确认支持的版本（0.2.3 或兼容版本）。

确认参考与目标精确路径，使用客户端导入／读取目标、创建一个 PhotoStyle- 虚拟副本并导出原生 before。记录母片、副本 ID、基线和回执；当前选择不能代替目标身份。

```text
python scripts/lightroom_client.py import --catalog "CATALOG.lrcat" --path "TARGET.jpg"
python scripts/lightroom_client.py read --catalog "CATALOG.lrcat" --path "TARGET.jpg" --photo-id MASTER_ID
python scripts/lightroom_client.py copy --catalog "CATALOG.lrcat" --path "TARGET.jpg" --photo-id MASTER_ID
python scripts/lightroom_client.py export --catalog "CATALOG.lrcat" --path "TARGET.jpg" --photo-id COPY_ID --output-dir "NEW_BEFORE_DIRECTORY"
```

占位符需替换为绝对路径和实际返回的 ID。客户端默认输出摘要；read/import/copy 保留判断所需设置。完整回执保存在 receipt_path，`--full` 可输出全文；结果未知时文件可能尚未生成。Python send_command 接口仍返回完整回执。

逐张查看参考和目标，记录 3–5 个可迁移特征、目标差异及验收标准，在本次任务内复用。数值分析只在能回答具体疑问时使用；无需每轮重读未变化的参考、完整 JSON 或历史排障过程。

## 执行一轮

在任务目录写 JSON 计划，以下数值仅演示语法：

```json
{
  "catalog": "C:/Photos/Catalog.lrcat",
  "path": "C:/Photos/target.jpg",
  "photo_id": "RETURNED_COPY_ID",
  "steps": [
    {"action": "apply", "settings": {"Exposure2012": 0.3, "Highlights2012": -15}},
    {"action": "apply", "settings": {"SaturationAdjustmentBlue": -10}}
  ]
}
```

每步为一组相关参数。综合曲线步骤为 `{"action":"curve","points":[[0,4],[128,128],[255,250]]}`。只使用当前照片支持的控件。RAW 的 Temperature/Tint 与 JPEG 的 IncrementalTemperature/IncrementalTint 单位不同，均为绝对滑块目标值。颗粒仅按用户要求或参考纹理添加。

```text
python scripts/lightroom_round.py --plan "ABSOLUTE_PLAN.json" --round-dir "NEW_ABSOLUTE_ROUND_DIRECTORY"
```

脚本在每组前新鲜读回，沿用原生快照和校验顺序应用，结束后独立读回，统一导出一次。返回变化、快照 ID、图片路径及回执目录。`ok: true` 仅表示执行成功；`needs_visual_review` 表示仍需看图。完整计划、发送前请求 ID 和回执留在磁盘；已有轮次目录拒绝重跑。

目标可预测时，首轮形成完整风格；查看之后再决定下一轮。曝光、白平衡或纹理存在实质不确定时可保留中途检查。第二轮只修明确可见的问题；第三轮仅用于仍存的明显缺陷或用户要求的精修。达到验收标准即停，不为“可能更好”继续磨，也不追求不同场景直方图一致。

超时按每条命令计算。宿主返回运行中的 shell 会话时轮询同一会话，不要再次启动脚本。遵守宿主进度沟通要求。

## 检查、恢复与交付

对照已记录特征并按需复看参考，检查肤色、主体可读性、亮暗部和色偏，必要时以 100% 检查纹理和边缘。当前仍导出原尺寸、质量 0.95 的 sRGB JPEG，未实现原生小预览。可只读缩放供看图，纹理判断仍使用原尺寸局部。

命令失败或结果未知就停止后续步骤。使用 `lightroom_client.py status --request-id ID` 查询同一 ID，依桥接指南读回现状、检查快照和进度。不应换新目录重跑整份计划以绕过未知状态；中断后可能只留下请求记录，先核对此 ID。已成功步骤保留，不自动回滚或重放。

视觉验收后，若该轮导出已满足格式／位置要求且参数未变，可直接作为交付文件，轮末独立读回可作为最终设置检查。重新打开选定文件核对外观、尺寸和配置文件；不必为了 final 文件夹再导出一份相同像素。参数变化后重新验证相应项目。保留可编辑副本、母片基线和回滚证据。

session.md 只保留输入角色、特征、精确目录／副本 ID、基线／回滚索引、选定轮次、验收结果、问题与下一步。完整回执放文件。案例 HTML、全套分析和费用统计仅在用户要求时另行制作。

局部柔化参见[原生蒙版](masks.zh-CN.md)：命令模块 0.3.0，支持明亮度范围与过渡控制（Classic 13.0.2）、主体／天空／背景选区创建，或按精确已有蒙版 ID 调整；每张图仍须目视验收。

独立通道曲线步骤可添加 `"channel":"red"`、`"green"` 或 `"blue"`；详见 [curves.zh-CN.md](curves.zh-CN.md)。要求命令模块 0.3.1；省略通道表示总曲线。

轮次验收先比较原图／参考／成片的明暗锚点及主体区域分离，再检查颜色和质感。黑色框景不能证明中央场景有反差；不确定时使用[分析指南](analysis.zh-CN.md)中的可选分区工具。回读成功只是技术验证；用户否定覆盖代理之前的自行验收。

分区色彩验收分别比较暗部、中间调、高光的主色／次色、低彩度内容与强度，同时核验亮度；使用[直接文件测量或按需原生观察](tonal-color.zh-CN.md)，保持来源一致，不能把桥接参数回执或外部SDR统计标记为原生直方图分析。
