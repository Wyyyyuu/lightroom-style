# Lightroom Style

**Bring a reference look into Lightroom. Keep the edit in your hands.**

[简体中文](README.md) · English

Lightroom Style is an agent skill for reference-based photo grading in **local Lightroom Classic**. Give your assistant a few reference photos and a target: it studies their shared tone and color, adjusts a virtual copy through Lightroom's native SDK, and checks the image Lightroom actually renders.

**Originals preserved · Editable Lightroom parameters · Native JPEG output · No generative editing**

> Use $lightroom-style. The first five photos are references; the last is my target. Match their color and tone in Lightroom, keep the original, and export a JPEG.

[Quick start](#quick-start) · [Examples](#examples) · [How it works](#how-it-works) · [Compatibility](#compatibility) · [FAQ](#faq)

## What you get

- **A look adapted to your photo.** Compare references for contrast, highlight transitions, key hues, saturation, and warm/cool relationships. Account for your target's lighting and existing edits.
- **An editable result.** Apply exposure, white balance, HSL, and color grading to an identified virtual copy, with snapshots and parameter readback.
- **A checked native render.** Review Lightroom's before/after output, refine the settings, and export to a new location.
- **Evidence you can inspect.** Use histogram, brightness, Lab, and HSV measurements alongside visual judgment, with a local session record for continuing later.

The workflow suits reference matching, reworking a previously graded JPEG, and establishing a consistent direction across a photo series. Each scene still needs its own exposure, white balance, and visual check.

## Quick start

### Requirements

- **Windows and Lightroom Classic.** The native workflow has been tested with Classic 13.0.2.
- **A local agent host.** Developed with Codex; the assistant needs local file access and permission to run Python. Other hosts require their own integration checks.
- **Python 3.11+.** Current automated validation uses Python 3.12. Image analysis needs Pillow and NumPy; the bridge clients use the standard library.

Download and extract the repository, then open PowerShell in its root directory.

### 1. Prepare the Python environment

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r lightroom-style/scripts/requirements.txt
```

Tell your assistant to use this environment's Python interpreter, or use an existing compatible runtime.

### 2. Install the skill

Copy the entire `lightroom-style/` folder into your host's skills directory. For the Codex setup used by this project:

```powershell
$skillRoot = if ($env:CODEX_HOME) {
    Join-Path $env:CODEX_HOME 'skills'
} else {
    Join-Path $env:USERPROFILE '.codex\skills'
}
$skillDestination = Join-Path $skillRoot 'lightroom-style'
if (Test-Path -LiteralPath $skillDestination) {
    throw 'Back up the existing skill folder before installing this version.'
}
New-Item -ItemType Directory -Path $skillRoot -Force | Out-Null
Copy-Item -LiteralPath './lightroom-style' -Destination $skillDestination -Recurse
```

Start a new conversation. If the skill is not discovered, restart the host. Skill instructions are in English; the assistant responds in your language.

When upgrading from `photo-style-match`, rename the installed skill folder to `lightroom-style` and update its contents, avoiding duplicate discovery; invoke `$lightroom-style` afterward. The internal Lightroom bridge identifier, `PhotoStyleBridge.lrplugin`, state directory, and `PhotoStyle-` copy prefix remain compatible. Renaming does not require reimporting photos.

### 3. Load the Lightroom plugin

On first use, the agent checks the connection, runs `setup_lightroom.py` if plugin files are missing, and uses an available desktop tool to add/enable the plugin and verify the connection. Without desktop control, you still need to complete the manager steps below. Working connections are reused. See [first-use setup](lightroom-style/references/bridge.md#automatic-first-use-setup).

For manual installation:

1. Copy the complete `lightroom-style/assets/PhotoStyleBridge.lrplugin` folder to a stable location, such as `%APPDATA%\Adobe\Lightroom\Modules\PhotoStyleBridge.lrplugin`. Back up any existing version first.
2. In Lightroom Classic, open **File → Plug-in Manager → Add**, and select that folder.
3. Click **运行只读连接检查** in the plugin panel, then **Done** to close the manager. The button means “Run read-only connection check”; its label is currently Chinese.

The skill and the Lightroom plugin are two separate installations: the skill guides the assistant, and the plugin gives Lightroom a local command channel.

### 4. Check the connection and try a photo

```powershell
.\.venv\Scripts\python.exe lightroom-style/scripts/lightroom_probe.py --timeout 15
```

Look for a fresh receipt with `connected: true`, `command_protocol: 1`, and `capabilities.catalog.ok: true`. Confirm the catalog path is the one you intend to use. This checks the connection; successful editing is established by parameter readback and native render inspection during the task.

Attach your references and target, then use the example prompt above. One reference works; 3–8 related images usually provide more useful context. Clearly identify which photo should be edited.

## Examples

### Match a reference set

> Use $lightroom-style. Photos 1–5 are references and photo 6 is the target. Aim for their soft contrast, pale blues, and natural skin tones. Edit in Lightroom and export a new JPEG.

### Rework an existing grade

> This JPEG already has a strong orange-and-cyan grade. Use the previous references, inspect its histogram and colors, and make the changes needed to fit. Keep the original and the earlier version.

### Continue from feedback

> Keep the current look, but the sky is too saturated and the skin is slightly cool. Refine those areas in the existing virtual copy, then check the new render.

The assistant treats a histogram as supporting evidence. It does not force unrelated images to share a brightness distribution or claim a numerical “style similarity” score.

## How it works

```text
Reference photos + target
          ↓
Visual observations + read-only image measurements
          ↓
Target-specific tone and color decisions
          ↓
Lightroom virtual copy → native parameter edits
          ↓
Independent readback → native render review → export
```

The agent chooses adjustments; Python measures images and carries commands; the Lightroom plugin applies settings and renders the result. Photo content and composition are preserved. Image generation, content replacement, and external scripted grading are outside this workflow.

Edits proceed in related parameter groups, with up to three review rounds by default. The result stays in a `PhotoStyle-` virtual copy with rollback snapshots. Unless you request application-only editing, a new high-quality sRGB JPEG can be exported for review. A local `session.md` records the target, copy, settings, checks, and output paths.

## Compatibility

| Component | Current scope |
| --- | --- |
| Verified environment | Windows · Lightroom Classic 13.0.2 · plugin 0.2.2.0 |
| Native editing | Tone, parametric/composite point curves, JPEG white balance, HSL, and color grading on protected virtual copies |
| Native export | Quality 0.95 JPEG · sRGB · original dimensions · new output directory |
| Image measurements | Supported rendered 8-bit SDR images; RAW, MPO/multi-frame, HDR, and high-bit-depth sources need a suitable application-rendered preview |
| Outside the bridge | Individual RGB curve writes, masks, cropping, retouching, sharpening, denoising, profile writes, and arbitrary presets |
| Needs separate validation | RAW white balance, other Classic versions, macOS, Lightroom cloud, and other agent hosts/applications |

Native curves support regional S-curves and white RGB composite points for softer endpoints with midtone contrast. Each edit is read back and checked in Lightroom exports; curve shape follows the image, not a fixed preset. See the [curve guide](lightroom-style/references/curves.md).

Unsupported bridge controls require an actually available desktop control channel. TIFF/HDR and other requested export formats require an appropriate application export workflow.

**Validation:** Automated tests cover image statistics, a simulated SDK, and release packaging. The native workflow has been tested on the environment listed above. Automated checks do not establish photographic style quality or compatibility with other versions. See [GitHub Actions](https://github.com/Wyyyyuu/lightroom-style/actions/workflows/test.yml) for the latest automated checks.

## FAQ

**Can it edit a JPEG that has already been graded?**  
Yes. Existing grading is baked into the pixels even when Lightroom's imported sliders read zero. The skill works from the current appearance on a copy; it cannot recover an ungraded RAW source by resetting sliders.

**The plugin is enabled, but the assistant cannot connect.**  
Run the plugin panel's read-only check, close the manager, and obtain a new probe receipt. Check the loaded plugin path and protocol. After updating, use **Reload Plug-in** to refresh its metadata. An old diagnostic file is not a live connection. See the [bridge guide](lightroom-style/references/bridge.md).

**A command timed out. Should I retry?**  
For `outcome_unknown`, query the original request ID with `status --request-id ID`. Do not resend `copy`, `apply`, or `export` until the original outcome and current photo state have been reconciled.

**Are my photos uploaded?**  
The Lightroom plugin does not make network requests, and measurements run locally. Your AI host determines how attachments and model requests are processed; local Lightroom execution does not imply offline AI inference. The workflow does not publish photos. Personal images, catalog data, and private receipts are excluded from release packages.

**Where does the bridge store its files?**  
By default, `%APPDATA%\Adobe\Lightroom\PhotoStyleMatchBridge`. A sandboxed host needs access to this directory. Use `--state-dir` when your verified installation uses another location.

## Tool architecture

The YAML frontmatter of `SKILL.md` declares top-level `allowed-tools`, while `metadata.tool-catalog` points to [tools.yaml](lightroom-style/tools.yaml). The catalog centralizes host tool names, script entry points, purpose, and optional desktop capability; the skill body retains the grading workflow. Release checks verify that frontmatter stays in sync and every helper and guide is packaged.

Execution path: **agent → host tool → Python client → Lightroom plugin → native settings and render**. The catalog does not register an MCP service or grant permissions. First-use installation/loading still follows the bridge guide. See [tool integration](lightroom-style/references/tools.md) for host differences and maintenance.

## Reference guides

Each guide has separate English and Simplified Chinese editions with a language switch at the top. `SKILL.md` and the default model instructions remain in English; the Chinese guides are reading alternatives, not additional required model context.

| Guide | English | 简体中文 |
| --- | --- | --- |
| Measurement and photographic judgment | [English](lightroom-style/references/analysis.md) | [中文](lightroom-style/references/analysis.zh-CN.md) |
| SDK bridge and parameter operations | [English](lightroom-style/references/bridge.md) | [中文](lightroom-style/references/bridge.zh-CN.md) |
| Tone curves | [English](lightroom-style/references/curves.md) | [中文](lightroom-style/references/curves.zh-CN.md) |
| Lightroom application workflow | [English](lightroom-style/references/lightroom.md) | [中文](lightroom-style/references/lightroom.zh-CN.md) |
| Tool catalog and host integration | [English](lightroom-style/references/tools.md) | [中文](lightroom-style/references/tools.zh-CN.md) |

## Development

```powershell
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
python tools/build_release.py --check
python tools/build_release.py
```

The builder creates a fresh `dist/release-<timestamp>/` containing a clean repository directory, repository ZIP, standalone skill ZIP, and SHA-256 manifest. It checks an explicit file allowlist and consistency between bridge source and bundled copies. Publish from the clean directory after reviewing its contents.

| Path | Purpose |
| --- | --- |
| `lightroom-style/` | Self-contained installable skill: instructions, references, clients, analyzer, plugin, and MIT license |
| `lightroom-style/tools.yaml` | Tool catalog validated against the frontmatter tool declaration |
| `lightroom-bridge/` | Bridge development source and the opt-in native acceptance driver |
| `tests/` | Image analysis and simulated SDK tests |
| `tools/` | Release validation and packaging |

Routine tests do not launch Lightroom. `lightroom-bridge/validate_native.py` does perform real imports, copies, edits, and exports; use it only for intentional native acceptance. See the [bridge development notes — 中文](lightroom-bridge/CONNECTION.md). Local authoring history, evaluation inputs, and photo sessions are excluded from Git and release archives.

When contributing, include the environment, reproduction steps, expected behavior, and relevant checks. Remove personal paths and photo/catalog data from reports. Keep the two README versions consistent.

## Acknowledgments and license

The skill was refined using [Anthropic's skill-creator](https://github.com/anthropics/skills/tree/main/skills/skill-creator); it is a development tool, not a runtime dependency.

This independent project is licensed under the [MIT License](LICENSE). Third-party software and photographs retain their respective licenses and rights.
