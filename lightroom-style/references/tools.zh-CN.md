# 工具集成

[English](tools.md) · 简体中文

## 文件分工

- [tools.yaml](../tools.yaml) 是本项目的工具清单：集中记录 Codex 宿主工具名、本地 CLI 入口、用途、对应指南和可选桌面能力。其结构是本项目自定义的。
- [SKILL.md](../SKILL.md) 在 YAML frontmatter 顶层声明 `allowed-tools`，值为空格分隔的工具名。`metadata.tool-catalog` 是指向清单的项目自定义字符串，不是宿主认识的自动加载钩子；正文会明确要求 agent 读取它。
- [agents/openai.yaml](../agents/openai.yaml) 保存 Codex 的界面元数据。此桥接使用本地 Python/Lua，不是 MCP 服务，因此没有虚构 MCP 依赖。

[Agent Skills 规范](https://agentskills.io/specification#allowed-tools-field)将 `allowed-tools` 标为实验性字段，其支持取决于宿主。声明不代表宿主已提供或强制执行这些工具名，也不声称 Codex 会据此授予权限。实际可调用工具、沙箱和审批仍由宿主控制。宿主元数据与依赖配置见 [OpenAI skill 文档](https://developers.openai.com/codex/skills)。

## 执行方式

agent 读取清单，通过宿主 shell 调用 Python 脚本，再用图片查看工具检查结果。Python 客户端与已加载的 Lightroom 插件交换本地请求，由 Lightroom 修改参数并渲染。`tools.yaml` 本身不执行代码，`lightroom` 等脚本 ID 也不是可直接调用的宿主工具名。参数格式查各脚本的 `--help`；身份校验、状态与恢复规则查清单中链接的指南。

在 skill 目录中执行的示例：

```text
python scripts/lightroom_probe.py --timeout 15
```

首次安装与界面加载仍遵循[桥接流程](bridge.zh-CN.md#首次使用时自动准备)。桌面工具必须能读取 Lightroom 原生界面，仅支持浏览器的工具不够。先发现宿主实际提供的工具；如果部署严格执行允许列表，维护者需要在部署权限范围内，将准确工具名同时加入 `host_tools` 与 `allowed-tools`，之后才能使用。区分工具不可用与应用访问被拒绝；按桥接指南恢复授权，再判断是否需要手动操作。不要虚构桌面工具名，也不要通过 shell 自动化绕过允许列表。

## 如何维护

先修改 `tools.yaml`。宿主工具名变更时，同步修改 `allowed-tools` 字符串，保持顺序一致。本地脚本放在 `cli_helpers` 中，不放进 `allowed-tools`。其他宿主需要经过验证的工具名映射，不能直接复制 Codex 名称后就声称兼容。同步维护英文指南。

在仓库根目录执行 `python tools/build_release.py --check`。它会检查清单结构、frontmatter 一致性、工具/脚本 ID 唯一性，以及脚本与指南是否包含在发布包中。这些检查验证的是声明和打包，不代表运行时工具可用、能够控制界面或已完成 Lightroom 编辑；仍需遵守宿主权限并核验新的原生回执。

已连接环境的调色优先使用[精简轮次](rounds.zh-CN.md)与 scripts/lightroom_round.py，顺序执行有校验的分组调整，统一导出一次。
