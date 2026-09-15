# Photo Style Match

**把喜欢的色彩，调进自己的照片。每一步，都留在 Lightroom 里。**

简体中文 · [English](README.en.md)

Photo Style Match 是一个在**本机 Lightroom Classic** 中工作的参考图调色 skill。给助手几张参考图和一张目标照片，它会分析影调与色彩共性，通过 Lightroom 原生 SDK 调整虚拟副本，再检查 Lightroom 实际渲染的画面。

**保留原片 · 参数可继续编辑 · Lightroom 原生导出 · 不使用生成式改图**

> 使用 $photo-style-match，前五张是参考，最后一张是目标。请在 Lightroom 中调出相近的色彩和影调，保留原片，导出一份 JPEG。

[快速开始](#快速开始) · [使用示例](#使用示例) · [工作原理](#工作原理) · [兼容性](#兼容性) · [常见问题](#常见问题)

## 你会得到什么

- **适合这张照片的调色方案。** 从参考中提炼反差、亮部过渡、主要色相、饱和度和冷暖关系，结合目标照片的光线与已有处理进行适配。
- **可以继续调整的 Lightroom 版本。** 在明确的虚拟副本上修改曝光、白平衡、HSL 和颜色分级，保留快照，并回读实际参数。
- **经过画面检查的原生成片。** 对照 Lightroom 渲染的前后图，逐轮修正，再导出到新位置。
- **可以追溯的判断和操作。** 用直方图、亮度、Lab 与 HSV 统计辅助观察，保存本地会话记录，方便后续继续修改。

适用于模仿参考风格、重新调整已有调色的 JPEG，以及为系列照片建立一致方向。不同场景仍会分别处理曝光、白平衡，并检查实际画面。

## 快速开始

### 环境要求

- **Windows 与 Lightroom Classic。** 原生工作流程已在 Classic 13.0.2 上验证。
- **能够访问本机的智能体宿主。** 本项目使用 Codex 开发；助手需要读取本地文件并运行 Python 的权限。其他宿主需要单独核验集成。
- **Python 3.11+。** 当前自动化检查使用 Python 3.12。图像分析依赖 Pillow 和 NumPy，桥接客户端只使用标准库。

下载并解压仓库，在仓库根目录打开 PowerShell。

### 1. 准备 Python 环境

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r photo-style-match/scripts/requirements.txt
```

让助手使用这个环境中的 Python 解释器，也可以使用已有的兼容运行时。

### 2. 安装 skill

将完整的 `photo-style-match/` 文件夹放入宿主的技能目录。对于本项目使用的 Codex 配置，可以运行：

```powershell
$skillRoot = if ($env:CODEX_HOME) {
    Join-Path $env:CODEX_HOME 'skills'
} else {
    Join-Path $env:USERPROFILE '.codex\skills'
}
$skillDestination = Join-Path $skillRoot 'photo-style-match'
if (Test-Path -LiteralPath $skillDestination) {
    throw '请先备份已有的 skill 目录，再安装这个版本。'
}
New-Item -ItemType Directory -Path $skillRoot -Force | Out-Null
Copy-Item -LiteralPath './photo-style-match' -Destination $skillDestination -Recurse
```

安装后开始新对话；如果未发现技能，重启宿主后再试。技能执行说明使用英文，助手仍会跟随你的语言交流。

### 3. 加载 Lightroom 插件

首次调色时，agent 会先检查连接；缺少插件文件时自动运行 `setup_lightroom.py`，并在有可用桌面控制工具时完成添加、启用和连接验证。没有桌面控制通道时，仍需你完成下面的管理器操作。已有可用连接会直接复用。详见[首次使用流程](photo-style-match/references/bridge.zh-CN.md#首次使用时自动准备)。

也可手动安装：

1. 将完整的 `photo-style-match/assets/PhotoStyleBridge.lrplugin` 文件夹复制到稳定位置，例如 `%APPDATA%\Adobe\Lightroom\Modules\PhotoStyleBridge.lrplugin`。已有版本请先备份。
2. 在 Lightroom Classic 中打开 **文件 → 增效工具管理器 → 添加**，选择这个文件夹。
3. 点击插件面板里的 **运行只读连接检查**，再点击 **完成** 关闭管理器。当前插件按钮为中文标签。

skill 和 Lightroom 插件需要分别安装：前者指导助手，后者为 Lightroom 提供本地命令通道。

### 4. 检查连接，开始第一张照片

```powershell
.\.venv\Scripts\python.exe photo-style-match/scripts/lightroom_probe.py --timeout 15
```

检查新回执中的 `connected: true`、`command_protocol: 1` 和 `capabilities.catalog.ok: true`，并确认目录路径是你要使用的 Lightroom 目录。这一步验证连接；实际调色成功还需要任务中的参数回读与原生渲染检查。

上传参考和目标，使用页面开头的示例即可。一张参考也能工作，3–8 张相关照片通常能提供更充分的线索。请明确哪张是待调照片。

## 使用示例

### 模仿一组参考

> 使用 $photo-style-match，第 1–5 张是参考，第 6 张是目标。希望接近参考的柔和反差、浅蓝色和自然肤色。请在 Lightroom 中处理并导出新的 JPEG。

### 重新调整已有调色

> 这张 JPEG 已经调过较强的橙青色。请沿用上一组参考，检查直方图和颜色差异，做出适配所需的调整，保留原片和之前的版本。

### 根据反馈继续修改

> 保留目前的感觉，但天空饱和度有些高，肤色也稍微偏冷。请在当前虚拟副本上细调这两处，再检查新的渲染结果。

助手会将直方图作为辅助证据，不强求不同内容的照片具有相同亮度分布，也不会给出虚构的“风格相似度百分比”。

## 工作原理

```text
参考照片 + 目标照片
        ↓
视觉观察 + 只读图像统计
        ↓
针对目标确定影调与色彩调整
        ↓
Lightroom 虚拟副本 → 原生参数修改
        ↓
独立回读 → 原生渲染检查 → 导出
```

智能体负责判断，Python 负责测量和传递命令，Lightroom 插件负责应用设置并渲染结果。照片内容和构图保持不变；流程不使用图像生成、内容替换或外部脚本调色。

每轮集中调整相关参数，默认最多进行三轮画面检查。结果保存在 `PhotoStyle-` 虚拟副本中，并有快照可回退。除非你明确只要软件内编辑，否则可以导出新的高质量 sRGB JPEG 供查看。本地 `session.md` 记录目标、副本、设置、检查结果和输出路径。

## 兼容性

| 项目 | 当前范围 |
| --- | --- |
| 已验证环境 | Windows · Lightroom Classic 13.0.2 · 插件 0.2.2.0 |
| 原生编辑 | 受保护虚拟副本上的影调、参数曲线与综合点曲线、JPEG 白平衡、HSL 和颜色分级 |
| 原生导出 | 质量 0.95 的 JPEG · sRGB · 原始尺寸 · 新输出目录 |
| 图像测量 | 支持已渲染的 8-bit SDR 图片；RAW、MPO/多帧、HDR 和高位深源图需先取得适用的软件渲染预览 |
| 桥接未提供 | 独立 RGB 通道曲线写入、蒙版、裁切、修复、锐化、降噪、配置文件写入、任意预设 |
| 需要单独验证 | RAW 白平衡、其他 Classic 版本、macOS、Lightroom 云版、其他智能体宿主或调色软件 |

已支持参数曲线，以及白色 RGB 综合点曲线：可柔化黑白端点，用中间锚点增强层次。每次调整均回读参数并检查 Lightroom 导出，按照片选择曲线，不套用固定预设。详见 [曲线指南](photo-style-match/references/curves.zh-CN.md)。

桥接尚未提供的控件需要实际可用的桌面控制通道。TIFF/HDR 等输出要求，需要使用软件中适用的导出流程。

**验证情况：** 自动化测试覆盖图像统计、模拟 SDK 和发布打包；原生流程已在上表环境中测试。自动化检查不代表调色审美质量，也不保证其他版本兼容。最新自动化检查见 [GitHub Actions](https://github.com/Wyyyyuu/photo-style-match/actions/workflows/test.yml)。

## 常见问题

**以前调过色的 JPEG，还能继续适配吗？**  
可以。此前调色已经体现在像素里，即使导入 Lightroom 后滑块为零也依然存在。skill 会在副本上从当前外观继续调整；重置滑块无法恢复未经处理的 RAW 原片。

**插件显示已启用，为什么助手仍然连不上？**  
在插件面板运行只读检查，关闭管理器，再获取新的连接回执。核对实际加载路径和协议版本。更新后可用 **重新载入增效工具** 刷新元信息；旧的诊断文件不能证明当前连接。详细步骤见 [桥接指南](photo-style-match/references/bridge.zh-CN.md)。

**命令超时了，要重新执行吗？**  
遇到 `outcome_unknown`，先用 `status --request-id ID` 查询原请求。在核清原请求结果和照片当前状态前，不要再次发送 `copy`、`apply` 或 `export`。

**照片会上传吗？**  
Lightroom 插件本身不联网，图像统计在本地运行。AI 宿主如何处理附件和模型请求由宿主决定；本地操作 Lightroom 不代表模型推理离线。流程不会发布照片，发布包也排除了私人图片、目录数据和回执。

**桥接文件存在哪里？**  
默认目录是 `%APPDATA%\Adobe\Lightroom\PhotoStyleMatchBridge`。受沙箱限制的宿主需要获得这个目录的访问权限；实际安装使用其他位置时，通过 `--state-dir` 指定已核实的目录。

## 参考指南

以下指南均提供独立的中英文版本，可在文档顶部切换。`SKILL.md` 与默认模型指引保持英文；中文指南供阅读和查阅，不要求模型重复加载两种语言。

| 指南 | 简体中文 | English |
| --- | --- | --- |
| 图像测量与风格判断 | [中文](photo-style-match/references/analysis.zh-CN.md) | [English](photo-style-match/references/analysis.md) |
| SDK 桥接与参数操作 | [中文](photo-style-match/references/bridge.zh-CN.md) | [English](photo-style-match/references/bridge.md) |
| 色调曲线 | [中文](photo-style-match/references/curves.zh-CN.md) | [English](photo-style-match/references/curves.md) |
| Lightroom 应用工作流 | [中文](photo-style-match/references/lightroom.zh-CN.md) | [English](photo-style-match/references/lightroom.md) |

## 开发与贡献

```powershell
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
python tools/build_release.py --check
python tools/build_release.py
```

打包工具会创建新的 `dist/release-<timestamp>/`，包含干净仓库目录、仓库 ZIP、独立 skill ZIP 和 SHA-256 清单。它检查明确的文件清单，以及桥接开发源码与 skill 内发布副本的一致性。检查内容后，从干净目录发布。

| 路径 | 用途 |
| --- | --- |
| `photo-style-match/` | 可独立安装的 skill，包含说明、参考文档、客户端、分析脚本、插件和 MIT 许可证 |
| `lightroom-bridge/` | 桥接开发源码及按需运行的实机验收程序 |
| `tests/` | 图像分析与模拟 SDK 测试 |
| `tools/` | 发布检查与打包 |

普通测试不会启动 Lightroom。`lightroom-bridge/validate_native.py` 会实际导入测试图、创建副本、修改参数并导出，仅在明确进行实机验收时运行。详细说明见 [桥接开发说明](lightroom-bridge/CONNECTION.md)。本地制作历史、评估输入和照片会话均排除在 Git 与发布包之外。

提交改进时，请附上环境、复现步骤、预期行为和相关检查结果。报告中移除个人路径、照片与目录数据；文档修改请同步维护中英文 README。

## 致谢与许可证

本技能使用 [Anthropic skill-creator](https://github.com/anthropics/skills/tree/main/skills/skill-creator) 整理和改进；它是制作工具，不是修图运行依赖。README 的组织方式参考了 [Anthropic Skills](https://github.com/anthropics/skills/blob/main/README.md)、[Superpowers](https://github.com/obra/superpowers/blob/main/README.md) 和 [baoyu-skills 的双语文档](https://github.com/JimLiu/baoyu-skills/blob/main/README.zh.md)。

本独立项目采用 [MIT 许可证](LICENSE)。第三方软件与照片仍适用各自的许可和权利。
