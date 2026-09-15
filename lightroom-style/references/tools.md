# Tool integration

English · [简体中文](tools.zh-CN.md)

## Files and responsibilities

- [tools.yaml](../tools.yaml) is the project's tool catalog: Codex host tool names, local CLI entry points, purpose, supporting guides, and optional desktop capability. Its schema is specific to this project.
- [SKILL.md](../SKILL.md) declares `allowed-tools` at the top level of YAML frontmatter as a space-separated string. `metadata.tool-catalog` is a project-specific string pointing to the catalog, not a host-recognized auto-loader. The skill body explicitly tells the agent to read it.
- [agents/openai.yaml](../agents/openai.yaml) holds Codex UI metadata. No MCP dependency is declared because this bridge is a local Python/Lua integration, not an MCP server.

The [Agent Skills specification](https://agentskills.io/specification#allowed-tools-field) marks `allowed-tools` experimental and host-dependent. It is a declaration, not evidence that a host exposes or enforces those names. We do not claim Codex grants permissions from it. The host's actual callable tools, sandbox, and approvals remain authoritative. See [OpenAI skill documentation](https://developers.openai.com/codex/skills) for host metadata and dependency configuration.

## Execution

The agent reads the catalog, invokes a Python helper with the host shell, and uses the image viewer to inspect output. The Python client exchanges local requests with the loaded Lightroom plugin; Lightroom edits and renders. `tools.yaml` itself executes nothing, and helper IDs such as `lightroom` are not callable host tool names. Use each helper's `--help` for its arguments; use its linked guide for identity, state, and recovery rules.

Example from the skill directory:

```text
python scripts/lightroom_probe.py --timeout 15
```

First-use installation and UI loading remain governed by [the bridge workflow](bridge.md#automatic-first-use-setup). A desktop tool must expose readable native Lightroom state; a browser-only tool is insufficient. Discover the tool actually supplied by the host. If the deployment enforces a strict allowlist, its maintainer must add that exact binding to `host_tools` and `allowed-tools` under the deployment's permissions before use. Without an available and permitted binding, request only the needed manual UI action. Do not invent a desktop tool name or bypass an allowlist through shell automation.

## Maintaining the catalog

Edit `tools.yaml` first. When host tool names change, update the `allowed-tools` string to match, preserving order. Local scripts belong in `cli_helpers`, not `allowed-tools`. A different host needs verified tool-name mappings; do not copy Codex names and claim compatibility. Keep the Chinese guide aligned.

Run `python tools/build_release.py --check` from the repository root. It verifies the catalog schema, frontmatter consistency, unique tool/helper IDs, and that helper scripts and guides are packaged. These checks verify declarations and distribution, not runtime availability, UI control, or Lightroom edits. Existing host permissions and fresh native receipts remain necessary.
