# Lightroom Classic 原生 SDK 桥接

[English](bridge.md) · 简体中文

使用 `scripts/lightroom_probe.py` 获取新的连接检查结果，用 `scripts/lightroom_client.py` 对明确的照片执行命令。Python 负责交换请求与回执；Lightroom 负责目录操作、修改照片与渲染。写入仅限经过核验的 `PhotoStyle-` 虚拟副本。

## 安装与连接

### 首次使用时自动准备

调色任务需要桥接时，在任务授权与宿主权限范围内完成以下步骤：

1. 先运行连接检查。已有可用连接就直接复用，不要每次重装或重新载入。超时不代表插件文件缺失；先检查错误，条件允许时核对实际加载路径。
2. 缺少文件时运行 `python scripts/setup_lightroom.py`。此 Windows 脚本仅使用随 skill 附带的资源，安装到默认 Modules 文件夹，返回包含准确路径的 JSON。已核实的其他位置可用 `--plugin-dir ABSOLUTE_PATH` 指定。脚本不依赖第三方 Python 包。退出码 0 表示文件安装完成或已有相同版本；2 表示已有版本不同且已保留；1 表示安装错误。不同版本按下文备份流程有意更新，不要反复运行安装脚本。安装失败时暂存文件保留在报告的 `.installing` 路径，供诊断使用。
3. 有桌面工具且能读取界面时，必要时打开 Lightroom Classic，不终止现有会话、不升级目录。在“文件 → 增效工具管理器”中，仅在插件不存在时添加返回的文件夹，禁用时启用，有意更新后才重新载入。运行只读连接检查并关闭管理器。操作必须依据实际可见控件，不使用盲目按键或固定坐标，不修改偏好设置或目录数据库强制注册。
4. 再运行连接检查，要求通过下文的新回执、协议与目录验证。没有可用桌面通道时，说明这一具体限制，只请用户完成剩余的管理器操作，然后继续验证；此环境下不能承诺无人值守加载。

文件安装、软件加载和连接验证是三个不同状态，脚本不会将它们混淆。现有 `LrInitPlugin` 会在 Lightroom 加载插件时启动后台任务，无需新增开机服务或定时任务。仅安装 skill 不会自动执行安装钩子；agent 在首次使用时遵循此流程。

注册步骤参考 [Adobe Lightroom Classic 插件安装指南](https://blog.developer.adobe.com/en/publish/2022/07/lightroom-classic-plugin-support-for-the-adobe-exchange-for-creative-cloud)。

`assets/PhotoStyleBridge.lrplugin` 是完整的插件文件夹。Windows 上通常安装在 `%APPDATA%\Adobe\Lightroom\Modules\PhotoStyleBridge.lrplugin`。替换已有安装前先备份，然后在“文件 → 增效工具管理器”中添加/加载。以实际加载路径为准，不要仅凭惯例推断。不要编辑目录数据库或应用偏好设置文件。

更新后，在管理器中点击只读连接检查按钮（当前标签为 `运行只读连接检查`），然后关闭管理器。0.2.0 支持从旧后台任务接管。插件元信息变更需要点击“重新载入增效工具”，才能刷新面板版本。如果桌面控制通道不可用，只请求用户执行这一步必要操作，并解释限制。

```text
python scripts/lightroom_probe.py --timeout 15
```

必须取得新回执，包含 `command_protocol: 1`、`bridge_version: 0.2.0` 和成功的 `capabilities.catalog.ok`；记录 `capabilities.catalog.value.path`。插件包版本为 0.2.2.0，启动诊断版本仍为 0.2.0。命令回执报告 `command_version: 0.2.2`，使用曲线前需核对。后台任务每次轮询都会加载命令模块，因此替换 Commands.lua 无需重启后台任务；面板元信息在重新载入后更新。`connected: true` 仅证明读取通道已连接。当前选中照片只是诊断上下文，不代表获准编辑的目标。默认状态目录为 `%APPDATA%\Adobe\Lightroom\PhotoStyleMatchBridge`；实际位置不同时使用 `--state-dir`。

## 确定目标并保留基线

将占位符替换为真实绝对路径和回执中的 ID，并按当前 shell 的规则引用。客户端会返回照片 ID，不要要求用户手动查找。

```text
python scripts/lightroom_client.py import --catalog "CATALOG.lrcat" --path "TARGET.jpg"
python scripts/lightroom_client.py read --catalog "CATALOG.lrcat" --path "TARGET.jpg" --photo-id MASTER_ID
python scripts/lightroom_client.py copy --catalog "CATALOG.lrcat" --path "TARGET.jpg" --photo-id MASTER_ID
python scripts/lightroom_client.py export --catalog "CATALOG.lrcat" --path "TARGET.jpg" --photo-id COPY_ID --output-dir "NEW_BEFORE_DIRECTORY"
```

对于已入库的精确路径，`import` 返回已有主照片；否则调用 `catalog:addPhoto`，不会移动文件或扫描目录。`copy` 激活准确的父文件夹，等待并核验单选状态，然后创建一个虚拟副本，因此会改变当前文件夹/选择。失败时先检查回执，不要重复执行。副本继承现有设置，名称为 `PhotoStyle-<request-id>`。记录 ID、路径、名称、基线设置和导出预览。

## 应用参数并独立回读

```text
python scripts/lightroom_client.py apply --catalog "CATALOG.lrcat" --path "TARGET.jpg" --photo-id COPY_ID --set Exposure2012=0.65 --expect Exposure2012=0 --set Highlights2012=-28 --expect Highlights2012=0
python scripts/lightroom_client.py read --catalog "CATALOG.lrcat" --path "TARGET.jpg" --photo-id COPY_ID
python scripts/lightroom_client.py export --catalog "CATALOG.lrcat" --path "TARGET.jpg" --photo-id COPY_ID --output-dir "NEW_AFTER_DIRECTORY"
```

以上数值仅演示语法，不是预设。`--set` 是绝对目标值；每个 `--expect` 必须来自同一照片的最近一次读取。客户端不接受任意 Lua 或 shell 命令。插件验证目录、路径、ID、副本身份、参数白名单、范围、截止时间和旧值，并在写入锁内再次检查，创建 `PhotoStyle-before-<request-id>` 快照，调用原生 `applyDevelopSettings` 后回读核验。不匹配即判为失败，并保留快照。通过原生快照回滚，或重新读取当前值后执行明确、带旧值校验的恢复；同时核对白平衡模式。

| 分组 | 允许的数值字段与范围 |
| --- | --- |
| 影调 | `Exposure2012` −5…5；`Contrast2012`、`Highlights2012`、`Shadows2012`、`Whites2012`、`Blacks2012` −100…100 |
| 参数色调曲线 | `ParametricShadows`、`ParametricDarks`、`ParametricLights`、`ParametricHighlights` -100…100；面板必须已启用 |
| 整体颜色 | `Vibrance`、`Saturation` −100…100 |
| JPEG/RGB 白平衡 | `IncrementalTemperature`、`IncrementalTint` −100…100；名称虽带 Incremental，实际仍为滑块绝对目标值 |
| RAW 白平衡 | `Temperature` 2000…50000、`Tint` −150…150；仅限该照片实际返回这些字段时；尚未经实机验证 |
| HSL | `HueAdjustment`、`SaturationAdjustment`、`LuminanceAdjustment` 加 Red/Orange/Yellow/Green/Aqua/Blue/Purple/Magenta 后缀；−100…100 |
| 阴影/高光颜色分级 | `SplitToningShadowHue`、`SplitToningHighlightHue` 0…360；对应的 `Saturation` 0…100；`SplitToningBalance` −100…100 |
| 中间调/全局颜色分级 | `ColorGradeMidtoneHue/Sat/Lum`、`ColorGradeGlobalHue/Sat/Lum`；Hue 0…360、Sat 0…100、Lum −100…100 |
| 分级亮度/混合 | `ColorGradeShadowLum`、`ColorGradeHighlightLum` −100…100；`ColorGradeBlending` 0…100 |

只允许写入当前照片设置中已存在的数值参数。写入白平衡时，还会将原生 `WhiteBalance` 设为 `Custom` 并验证，否则 Lightroom 可能忽略 JPEG 的色温/色调值。保留处理版本。导入 JPEG 后滑块为零，并不说明像素中没有已有调色。

曲线选择与检查见[曲线指南](curves.zh-CN.md)。照片读取结果包含 `curve_state`，其中提供面板开关、区域分界和带索引的点曲线坐标，供比较使用；同时返回不透明的 `curve_revision` 状态校验值。综合点曲线使用独立的 `curve` 操作，传入新读取的校验值；其他曲线上下文均保留并再次核验。

桥接不提供独立 RGB 曲线写入、曲线区域分界、蒙版、裁切、锐化、降噪、相机配置文件写入或任意预设。需要不支持的控件时，使用实际验证过的 UI 通道，或说明缺少的能力。不能因为软件文档描述了某项功能，就声称桥接支持它。

## 原生导出与验收

`LrExportSession` 渲染高质量 JPEG（质量 0.95）、sRGB、原始尺寸，不进行输出锐化、不加水印、不重新导入，仅保留版权元数据并移除位置。输出必须是尚不存在的绝对目录，以防覆盖。TIFF、HDR 或其他特殊格式需要适用的软件导出控件，不能默默改用这个固定的 JPEG 接口。

重新打开并目视检查原生导出的前后图；有帮助时进行只读测量。回读成功和文件存在不能代替画面检查。校准图只能验证命令与渲染功能，不能证明照片风格匹配。

## 未知结果与恢复

每个请求使用唯一 ID。插件执行前通过原子操作将其标记为 `.running`，每个 ID 最多执行一次。JSON 回执完整写入后才创建 `.ready`，因此客户端会忽略不完整或无关的旧回执。默认等待 30 秒；命令的 `--timeout` 支持 1–120 秒。

出现 `outcome_unknown` 时，保留 ID 并查询：

```text
python scripts/lightroom_client.py status --request-id REQUEST_ID --timeout 15
```

**不要自动重发 copy、apply 或 export。** `.running` 存在但没有完整结果时，即使超时仍不能确定结果。尚未被领取且已过期的请求会被插件拒绝。明确失败时也要检查 `progress`：`created_copy_id` 指向已创建的副本；`parameters_applied` 表示写入调用已返回；`snapshot_name` 提供回滚快照。通过新的 `read` 核清状态，诊断并修复原因，仅在仍有必要时有意发起新的、带状态校验的操作。保留失败回执和恢复记录。

插件不发起网络请求，也不启动外部程序。其本地文件协议不是经过身份验证的远程服务，不要公开暴露。这并不意味着 AI 宿主会离线处理图像。

## 兼容性

已在 Windows、Lightroom Classic 13.0.2、ProcessVersion 15.4 上测试：导入、虚拟副本、影调/颜色、参数曲线与综合点曲线写入、独立回读，以及原生 sRGB JPEG 导出。RAW 白平衡和其他版本需单独进行原生验证。命令成功不代表审美质量合格。

主要 API 入口：[Adobe Lightroom Classic SDK](https://developer.adobe.com/lightroom-classic/)。成功声明必须以当前任务的真实回执和 Lightroom 渲染结果为依据。
