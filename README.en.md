# Lightroom Style

[简体中文](README.md) · English

An AI skill for grading photos in local Lightroom Classic using reference images.

Provide references and a photo to edit. The assistant studies their light, color, and warm/cool relationships, creates a virtual copy in Lightroom, adjusts its settings, and exports the result for review. Your original stays intact, and you can continue editing the result in Lightroom.

> Use $lightroom-style. The first four photos are references; the last is the photo to edit. Match the reference style in Lightroom and export a JPEG.

[Installation](#installation) · [Usage](#usage) · [Features and compatibility](#features-and-compatibility) · [FAQ](#faq) · [Development](#development)

## Installation

Tested with Windows, Lightroom Classic 13.0.2, and Codex. Requires Python 3.11 or later and permission for the assistant to read local files and run Python. Other operating systems, Classic versions, and AI tools need testing.

Download and extract the repository, then open PowerShell in its root directory.

### 1. Install Python dependencies

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r lightroom-style/scripts/requirements.txt
```

Tell the assistant to use this virtual environment's Python. An existing environment with Pillow and NumPy also works.

### 2. Install the skill

Copy the repository's `lightroom-style/` folder into the Codex skills directory:

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

Start a new conversation after installing. If the skill is not recognized, restart Codex.

Earlier versions were named `photo-style-match`. Replace the old folder when upgrading, then invoke `$lightroom-style`. Existing Lightroom photos and virtual copies are unaffected.

### 3. Load the Lightroom plugin

The skill provides instructions; the plugin executes them in Lightroom. Both need to be installed. On first use, the assistant checks the connection and attempts plugin setup. If it cannot control the desktop, load the plugin manually:

1. Copy the entire `lightroom-style/assets/PhotoStyleBridge.lrplugin` folder to a fixed location, such as `%APPDATA%\Adobe\Lightroom\Modules\PhotoStyleBridge.lrplugin`. Back up any existing version first.
2. In Lightroom Classic, open **File → Plug-in Manager → Add** and select that folder.
3. Click **运行只读连接检查** (“Run read-only connection check”) in the plugin panel, then **Done**.

From the repository root, run:

```powershell
.\.venv\Scripts\python.exe lightroom-style/scripts/lightroom_probe.py --timeout 15
```

The response should include `connected: true`, `command_protocol: 1`, and `capabilities.catalog.ok: true`. Check that the path under `catalog` is the Lightroom catalog you intend to use. For connection problems, see the [bridge guide](lightroom-style/references/bridge.md).

## Usage

Attach your references and the photo to edit, and identify which is which. One reference is enough; when using several, choose photos with a similar style.

Describe the parts of the look that matter to you:

> Use $lightroom-style. The first photo is the reference and the second is mine. I like the cool shadows and warm lights, but want to keep natural skin tones. Please edit it in Lightroom.

You can also refine the result:

> The sky is a little too blue and the people are too dark. Adjust the virtual copy from the last round and keep the previous version.

Edits stay in a virtual copy whose name starts with `PhotoStyle-`, with snapshots saved before changes. By default, the workflow exports a new, full-size, high-quality sRGB JPEG to a new directory. If you only want the Lightroom edit, say so.

Previously graded JPEGs can be edited too, but resetting Lightroom sliders cannot remove a grade already baked into the image.

## Features and compatibility

The current plugin version is **0.3.1.0**. Native operation has been tested with **Lightroom Classic 13.0.2 on Windows**.

| Feature | Support |
| --- | --- |
| Basic grading | Exposure, contrast, highlights, shadows, whites, blacks, JPEG white balance, HSL, and color grading |
| Curves | Parametric curves, RGB composite points, and individual red, green, and blue channel curves |
| Calibration | Red, green, and blue primary hue; tested on JPEG virtual copies |
| Grain | Amount, size, and roughness, when requested or supported by the references |
| Local adjustments | Reduced Clarity and Texture through masks; luminance range and background masks tested, subject and sky masks still need native testing |
| Export | JPEG at quality 0.95, sRGB, original dimensions |

Luminance range mask writes are currently limited to Classic 13.0.2. RAW white balance, other Classic versions, macOS, and Lightroom cloud need separate testing.

The bridge does not currently provide cropping, retouching, sharpening, denoising, arbitrary mask drawing, profile writes, or arbitrary preset application. TIFF, HDR, and other export formats also require Lightroom's interface.

## How it works

The assistant studies the images and chooses adjustments, Python scripts carry the commands, and the Lightroom plugin uses the native SDK to edit a virtual copy and render the photo. The workflow preserves image content and composition and does not use generative editing.

After each round, it reads back the settings and inspects Lightroom's export before deciding whether to revise the edit. Image statistics support that judgment; the actual photo determines the result. A `session.md` in the task directory records the photo, copy, adjustments, and output paths so work can continue later.

Detailed guides are available in both languages:

| Guide | English | 简体中文 |
| --- | --- | --- |
| Image analysis and reference matching | [English](lightroom-style/references/analysis.md) | [中文](lightroom-style/references/analysis.zh-CN.md) |
| Shadow, midtone, and highlight color | [English](lightroom-style/references/tonal-color.md) | [中文](lightroom-style/references/tonal-color.zh-CN.md) |
| Connection and parameter commands | [English](lightroom-style/references/bridge.md) | [中文](lightroom-style/references/bridge.zh-CN.md) |
| Adjustment and review rounds | [English](lightroom-style/references/rounds.md) | [中文](lightroom-style/references/rounds.zh-CN.md) |
| Curves | [English](lightroom-style/references/curves.md) | [中文](lightroom-style/references/curves.zh-CN.md) |
| Calibration | [English](lightroom-style/references/calibration.md) | [中文](lightroom-style/references/calibration.zh-CN.md) |
| Masks | [English](lightroom-style/references/masks.md) | [中文](lightroom-style/references/masks.zh-CN.md) |
| Lightroom interface operations | [English](lightroom-style/references/lightroom.md) | [中文](lightroom-style/references/lightroom.zh-CN.md) |
| Tool integration | [English](lightroom-style/references/tools.md) | [中文](lightroom-style/references/tools.zh-CN.md) |

## FAQ

**The plugin is enabled, but the assistant cannot connect.**

Run the connection check in the plugin panel, close the manager, and run the probe script again. After updating, use **Reload Plug-in**. Check that Lightroom loaded the correct plugin folder. See the [bridge guide](lightroom-style/references/bridge.md).

**Can I retry a timed-out command?**

If the response is `outcome_unknown`, query the original request with `status --request-id ID` first. A timeout does not necessarily mean failure; retrying may create duplicate copies or exports.

**Are my photos uploaded?**

The Lightroom plugin does not make network requests, and image analysis scripts run locally. How photos attached to a conversation are processed depends on your AI tool. This skill does not publish photos to GitHub, and release packages do not include personal photos or Lightroom catalog data.

**Which local directories does the assistant need to access?**

Besides the photo and output directories, it needs the bridge state directory, which defaults to `%APPDATA%\Adobe\Lightroom\PhotoStyleMatchBridge`. A sandboxed AI tool may ask for permission. Use `--state-dir` for a different installation location.

## Development

| Path | Contents |
| --- | --- |
| `lightroom-style/` | Installable skill with instructions, guides, scripts, and plugin |
| `lightroom-bridge/` | Bridge development source and native validation scripts |
| `tests/` | Image analysis, simulated SDK, and packaging tests |
| `tools/` | Release validation and packaging |

Tool entry points are listed in [tools.yaml](lightroom-style/tools.yaml). Keep the skill instructions and catalog in sync when changing tools or scripts. Plugin changes also need to be copied to the bundled version in `lightroom-style/assets/`.

```powershell
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
python tools/build_release.py --check
python tools/build_release.py
```

Builds are written to `dist/release-<timestamp>/`, containing the source files listed in `release-manifest.json`, a repository ZIP, a skill ZIP, and SHA-256 checksums. Personal photos, editing sessions, and local development records are outside the release list.

Routine tests do not launch Lightroom. `lightroom-bridge/validate_native.py` performs real imports, creates copies, changes settings, and exports photos; read the [bridge development notes — 中文](lightroom-bridge/CONNECTION.md) before running it. Automated results are on [GitHub Actions](https://github.com/Wyyyyuu/lightroom-style/actions/workflows/test.yml).

Issues and contributions are welcome. Include your environment, reproduction steps, and errors, with personal paths and photo information removed. Keep both README versions in sync when editing documentation.

## Acknowledgments

[Anthropic's skill-creator](https://github.com/anthropics/skills/tree/main/skills/skill-creator) was used to organize and refine the skill instructions.

## License

[MIT](LICENSE)
