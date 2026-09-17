# Lightroom Style

简体中文 · [English](README.en.md)

让 AI 参照你喜欢的照片，在本机 Lightroom Classic 中调色。

提供参考图和一张待调照片，助手会分析明暗、色彩和冷暖关系，在 Lightroom 中创建虚拟副本，调整参数，再导出照片检查效果。原片保留，调色结果可以在 Lightroom 里继续修改。

> 使用 $lightroom-style，前四张是参考，最后一张是待调照片。请参考前四张的风格，在 Lightroom 中调色并导出 JPEG。

[安装](#安装) · [使用](#使用) · [功能与兼容性](#功能与兼容性) · [常见问题](#常见问题) · [开发](#开发)

## 安装

目前在 Windows、Lightroom Classic 13.0.2 和 Codex 中验证过。需要 Python 3.11 或更高版本，以及助手读取本地文件、运行 Python 的权限。其他系统、Classic 版本和 AI 工具尚需测试。

下载并解压仓库，在仓库根目录打开 PowerShell。

### 1. 安装 Python 依赖

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r lightroom-style/scripts/requirements.txt
```

告诉助手使用这个虚拟环境中的 Python。如果已有安装了 Pillow 和 NumPy 的环境，也可以直接使用。

### 2. 安装 skill

将仓库中的 `lightroom-style/` 文件夹复制到 Codex 的技能目录：

```powershell
$skillRoot = if ($env:CODEX_HOME) {
    Join-Path $env:CODEX_HOME 'skills'
} else {
    Join-Path $env:USERPROFILE '.codex\skills'
}
$skillDestination = Join-Path $skillRoot 'lightroom-style'
if (Test-Path -LiteralPath $skillDestination) {
    throw '请先备份已有的 skill 目录，再安装这个版本。'
}
New-Item -ItemType Directory -Path $skillRoot -Force | Out-Null
Copy-Item -LiteralPath './lightroom-style' -Destination $skillDestination -Recurse
```

安装后新建对话。如果没有识别到技能，重启 Codex 再试。

旧版名称是 `photo-style-match`。升级时用新文件夹替换旧版，之后使用 `$lightroom-style` 调用；Lightroom 中已有的照片和虚拟副本不受影响。

### 3. 加载 Lightroom 插件

skill 提供操作说明，插件负责在 Lightroom 中执行，两者都需要安装。首次使用时，助手会检查连接并尝试完成插件安装；如果无法操作桌面，需要手动加载：

1. 将 `lightroom-style/assets/PhotoStyleBridge.lrplugin` 整个文件夹复制到固定位置，例如 `%APPDATA%\Adobe\Lightroom\Modules\PhotoStyleBridge.lrplugin`。已有版本请先备份。
2. 打开 Lightroom Classic，进入 **文件 → 增效工具管理器 → 添加**，选择该文件夹。
3. 点击插件面板中的 **运行只读连接检查**，再点击 **完成**。

然后在仓库根目录运行：

```powershell
.\.venv\Scripts\python.exe lightroom-style/scripts/lightroom_probe.py --timeout 15
```

返回结果应包含 `connected: true`、`command_protocol: 1` 和 `capabilities.catalog.ok: true`。同时确认 `catalog` 中的路径是你正在使用的 Lightroom 目录。连接失败时，见[桥接指南](lightroom-style/references/bridge.zh-CN.md)。

## 使用

在对话里附上参考图和待调照片，说明各自的角色即可。一张参考也能使用；多张参考最好有接近的风格。

可以描述你在意的部分：

> 使用 $lightroom-style，第一张是参考，第二张是待调照片。我喜欢参考图的冷色暗部和暖色灯光，但希望保留人物肤色。请在 Lightroom 中调整。

也可以在结果上继续修改：

> 天空有点太蓝了，人物也偏暗。请在刚才的虚拟副本上调整，保留之前的版本。

结果保存在以 `PhotoStyle-` 开头的虚拟副本中，调整前会保留快照。默认导出一份原尺寸、高质量的 sRGB JPEG 到新目录；如果只想保留 Lightroom 中的编辑，直接说明即可。

已经调过色的 JPEG 也能继续调整，但重置 Lightroom 滑块无法去掉已经写进照片里的旧调色。

## 功能与兼容性

当前插件版本为 **0.3.1.0**，已验证的 Lightroom 版本为 **Classic 13.0.2（Windows）**。

| 功能 | 支持情况 |
| --- | --- |
| 基础调色 | 曝光、反差、高光、阴影、白色、黑色、JPEG 白平衡、HSL、颜色分级 |
| 曲线 | 参数曲线、RGB 综合点曲线、独立红／绿／蓝通道曲线 |
| 原色校准 | 红、绿、蓝原色色相；已在 JPEG 虚拟副本上验证 |
| 颗粒 | 数量、大小、粗糙度，按参考图或用户要求添加 |
| 局部调整 | 通过蒙版降低清晰度、纹理；明亮度范围和背景蒙版已验证，主体／天空蒙版仍需实测 |
| 导出 | JPEG，质量 0.95，sRGB，原始尺寸 |

明亮度范围蒙版的写入目前限定 Classic 13.0.2。RAW 白平衡、其他 Classic 版本、macOS 和 Lightroom 云版尚需单独验证。

桥接暂不提供裁切、修复、锐化、降噪、任意蒙版形状绘制、配置文件写入或任意预设应用。TIFF、HDR 等导出格式也需要通过 Lightroom 界面处理。

## 工作原理

助手负责观察照片和选择参数，Python 脚本负责传递命令，Lightroom 插件通过原生 SDK 修改虚拟副本并渲染照片。调色过程中保留画面内容与构图，不使用生成式改图。

每轮修改后会读回参数并查看 Lightroom 导出图，再决定是否需要修正。图像统计用于辅助判断；调色效果仍要看实际照片。任务目录中的 `session.md` 会记录照片、副本、调整和导出位置，方便之后继续。

需要了解具体操作时，可以查看这些指南：

| 指南 | 简体中文 | English |
| --- | --- | --- |
| 图像分析与风格判断 | [中文](lightroom-style/references/analysis.zh-CN.md) | [English](lightroom-style/references/analysis.md) |
| 阴影、中间调与高光色彩 | [中文](lightroom-style/references/tonal-color.zh-CN.md) | [English](lightroom-style/references/tonal-color.md) |
| 连接与参数操作 | [中文](lightroom-style/references/bridge.zh-CN.md) | [English](lightroom-style/references/bridge.md) |
| 调整与检查流程 | [中文](lightroom-style/references/rounds.zh-CN.md) | [English](lightroom-style/references/rounds.md) |
| 曲线 | [中文](lightroom-style/references/curves.zh-CN.md) | [English](lightroom-style/references/curves.md) |
| 原色校准 | [中文](lightroom-style/references/calibration.zh-CN.md) | [English](lightroom-style/references/calibration.md) |
| 蒙版 | [中文](lightroom-style/references/masks.zh-CN.md) | [English](lightroom-style/references/masks.md) |
| Lightroom 界面操作 | [中文](lightroom-style/references/lightroom.zh-CN.md) | [English](lightroom-style/references/lightroom.md) |
| 工具集成 | [中文](lightroom-style/references/tools.zh-CN.md) | [English](lightroom-style/references/tools.md) |

## 常见问题

**插件已启用，为什么还是连不上？**

先在插件面板运行连接检查，关闭管理器，再运行探测脚本。更新插件后，可以点击 **重新载入增效工具**。还应确认加载的是正确的插件文件夹，详见[桥接指南](lightroom-style/references/bridge.zh-CN.md)。

**命令超时后能重试吗？**

如果返回 `outcome_unknown`，先用 `status --request-id ID` 查询原请求。超时不一定代表操作失败，直接重试可能重复创建副本或导出照片。

**照片会上传吗？**

Lightroom 插件不联网，图像分析脚本也在本地运行。你在对话中提供的照片如何被处理，取决于所用的 AI 工具。这个技能不会将照片发布到 GitHub，发布包也不包含个人照片或 Lightroom 目录数据。

**助手需要访问哪些本地目录？**

除了照片和输出目录，还需要访问桥接的状态目录，默认是 `%APPDATA%\Adobe\Lightroom\PhotoStyleMatchBridge`。受沙箱限制时，可能需要在 AI 工具中授权。其他安装位置可通过 `--state-dir` 指定。

## 开发

| 路径 | 内容 |
| --- | --- |
| `lightroom-style/` | 可独立安装的 skill，包括提示词、指南、脚本和插件 |
| `lightroom-bridge/` | 桥接开发源码和实机验证程序 |
| `tests/` | 图像分析、模拟 SDK 和打包测试 |
| `tools/` | 发布检查与打包工具 |

工具入口列在 [tools.yaml](lightroom-style/tools.yaml) 中。修改工具或脚本时，需要同步维护技能说明和清单；修改插件时，也要同步 `lightroom-style/assets/` 中的发布副本。

```powershell
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
python tools/build_release.py --check
python tools/build_release.py
```

打包结果位于 `dist/release-<timestamp>/`，包含按 `release-manifest.json` 收集的源码、仓库 ZIP、skill ZIP 和 SHA-256 清单。个人照片、调色会话和本地开发记录不在发布清单中。

普通测试不会启动 Lightroom；`lightroom-bridge/validate_native.py` 会实际导入测试图、创建副本、修改参数并导出，使用前请阅读[桥接开发说明](lightroom-bridge/CONNECTION.md)。自动测试结果见 [GitHub Actions](https://github.com/Wyyyyuu/lightroom-style/actions/workflows/test.yml)。

欢迎提交问题或改进。报告问题时请附上环境、复现步骤和报错，去掉个人路径和照片信息。修改文档时请同步中英文版本。

## 致谢

使用 [Anthropic skill-creator](https://github.com/anthropics/skills/tree/main/skills/skill-creator) 整理和改进技能说明。

## 许可证

[MIT](LICENSE)
