# Lightroom Classic native SDK bridge

English · [简体中文](bridge.zh-CN.md)

Use `scripts/lightroom_probe.py` for a fresh connection check and `scripts/lightroom_client.py` for explicit photo commands. Python exchanges requests and receipts; Lightroom performs catalog operations, develop edits, and rendering. Writes are restricted to verified `PhotoStyle-` virtual copies.

Tool names and CLI entry points are maintained in [tools.yaml](../tools.yaml); see [tool integration](tools.md) when adapting the host.

## Install and connect

### Automatic first-use setup

When a grading request requires this bridge, carry out setup within the task and host permissions:

1. Run the probe first. Reuse a working connection; do not reinstall or reload on every task. A timeout does not prove that files are missing. Inspect errors and the actual loaded plugin path when available.
2. If files are missing, run `python scripts/setup_lightroom.py`. This Windows helper uses only the bundled assets, installs into the conventional Modules folder, and returns JSON with the exact path. Use `--plugin-dir ABSOLUTE_PATH` for a verified alternative. It needs no third-party Python packages. Exit 0 means files are installed or identical; exit 2 means an existing installation differs and was preserved; exit 1 indicates an installation error. Resolve a differing installation deliberately with the backup procedure below, not by repeatedly running setup. Failed staging files are retained at the reported `.installing` path for diagnosis.
3. With an available desktop tool and readable UI state, open Lightroom Classic if necessary without terminating a session or upgrading a catalog. In File → Plug-in Manager, add the returned folder only if it is absent, enable it if disabled, or reload only after a deliberate update. Run the read-only connection check and close the manager. Use observed controls, never blind keystrokes or fixed coordinates. Do not modify preferences/catalog databases to force registration.
4. Run the probe again and require the fresh protocol/catalog checks below. If no usable desktop channel exists, explain that specific limitation and ask the user only to complete the remaining manager action, then continue verification. Do not promise unattended loading in that environment.

Installation is not loading, and loading is not a verified connection. The helper never claims either. The plugin's existing `LrInitPlugin` starts its worker when Lightroom loads it; no new startup service or scheduled task is needed. Installing this skill alone does not execute a setup hook: the agent follows this procedure when first using it.

Registration follows [Adobe's Lightroom Classic plugin installation guide](https://blog.developer.adobe.com/en/publish/2022/07/lightroom-classic-plugin-support-for-the-adobe-exchange-for-creative-cloud).

`assets/PhotoStyleBridge.lrplugin` is a complete plugin folder. On Windows the conventional installation location is `%APPDATA%\Adobe\Lightroom\Modules\PhotoStyleBridge.lrplugin`. Back up an existing installation before replacing it, then add/load it in File → Plug-in Manager. The actual loaded path takes priority over this convention. Do not edit catalog databases or application preference files.

After an update, click the read-only connection check button in the manager (current UI label: `运行只读连接检查`) and close it. Version 0.2.0 supports handing over from an older background task. Plugin metadata changes require Reload Plug-in to refresh the panel version. If no desktop channel works, request only this necessary application action, explaining the limitation.

```text
python scripts/lightroom_probe.py --timeout 15
```

Require a fresh receipt with `command_protocol: 1`, `bridge_version: 0.2.0`, and `capabilities.catalog.ok`; record `capabilities.catalog.value.path`. Plugin package version is 0.2.2.0; the bootstrap diagnostic remains 0.2.0. Command receipts report `command_version: 0.2.2`; check this before using curves. The worker loads the command module per poll, so replacing Commands.lua does not require a worker restart; panel metadata updates after Reload Plug-in. `connected: true` establishes the read channel only. Current selection is diagnostic context, not an authorized target. Default state directory: `%APPDATA%\Adobe\Lightroom\PhotoStyleMatchBridge`; use `--state-dir` when the actual location differs.

## Resolve the target and preserve a baseline

Replace placeholders with real absolute paths and receipt IDs, quoted for the active shell. Clients return photo IDs; do not ask users to discover them manually.

```text
python scripts/lightroom_client.py import --catalog "CATALOG.lrcat" --path "TARGET.jpg"
python scripts/lightroom_client.py read --catalog "CATALOG.lrcat" --path "TARGET.jpg" --photo-id MASTER_ID
python scripts/lightroom_client.py copy --catalog "CATALOG.lrcat" --path "TARGET.jpg" --photo-id MASTER_ID
python scripts/lightroom_client.py export --catalog "CATALOG.lrcat" --path "TARGET.jpg" --photo-id COPY_ID --output-dir "NEW_BEFORE_DIRECTORY"
```

`import` returns the existing master for an already cataloged exact path; otherwise it calls `catalog:addPhoto` without moving files or scanning a directory. `copy` activates the exact parent folder, waits for verified single selection, and creates one virtual copy. It changes the current folder/selection. Inspect its receipt on failure instead of duplicating the operation. The copy inherits existing settings; its name is `PhotoStyle-<request-id>`. Record ID, path, name, baseline settings, and exported preview.

## Apply and independently read back

```text
python scripts/lightroom_client.py apply --catalog "CATALOG.lrcat" --path "TARGET.jpg" --photo-id COPY_ID --set Exposure2012=0.65 --expect Exposure2012=0 --set Highlights2012=-28 --expect Highlights2012=0
python scripts/lightroom_client.py read --catalog "CATALOG.lrcat" --path "TARGET.jpg" --photo-id COPY_ID
python scripts/lightroom_client.py export --catalog "CATALOG.lrcat" --path "TARGET.jpg" --photo-id COPY_ID --output-dir "NEW_AFTER_DIRECTORY"
```

These values demonstrate syntax, not a preset. `--set` is an absolute target value; every `--expect` must come from a recent read of the same photo. Clients accept no arbitrary Lua or shell commands. The plugin validates catalog, path, ID, copy identity, allowed parameter, range, deadline, and old value. It rechecks inside the write gate, creates `PhotoStyle-before-<request-id>`, calls native `applyDevelopSettings`, and checks readback. A mismatch is a failure with a retained snapshot. Roll back through the native snapshot or an explicit guarded restoration after reading current values; also check white-balance mode.

| Group | Allowed numeric fields and ranges |
| --- | --- |
| Tone | `Exposure2012` −5…5; `Contrast2012`, `Highlights2012`, `Shadows2012`, `Whites2012`, `Blacks2012` −100…100 |
| Parametric tone curve | `ParametricShadows`, `ParametricDarks`, `ParametricLights`, `ParametricHighlights` -100…100; panel must already be enabled |
| Overall color | `Vibrance`, `Saturation` −100…100 |
| JPEG/RGB white balance | `IncrementalTemperature`, `IncrementalTint` −100…100; despite their names these are absolute slider targets |
| RAW white balance | `Temperature` 2000…50000, `Tint` −150…150; only if actually returned for the photo; not hardware-validated |
| HSL | `HueAdjustment`, `SaturationAdjustment`, `LuminanceAdjustment` plus Red/Orange/Yellow/Green/Aqua/Blue/Purple/Magenta; −100…100 |
| Shadow/highlight grading | `SplitToningShadowHue`, `SplitToningHighlightHue` 0…360; matching `Saturation` 0…100; `SplitToningBalance` −100…100 |
| Midtone/global grading | `ColorGradeMidtoneHue/Sat/Lum`, `ColorGradeGlobalHue/Sat/Lum`; Hue 0…360, Sat 0…100, Lum −100…100 |
| Grading luminance/blending | `ColorGradeShadowLum`, `ColorGradeHighlightLum` −100…100; `ColorGradeBlending` 0…100 |

Only numeric parameters present in current photo settings can be written. White-balance writes also set native `WhiteBalance` to `Custom` and verify it; otherwise Lightroom may ignore JPEG temperature/tint values. Process version is preserved. Zero sliders on an imported JPEG say nothing about grading baked into its pixels.

For curve selection and checks, read [curves.md](curves.md). Photo reads include `curve_state` with the panel switch, region splits, and indexed point-curve coordinates for comparison. Reads also include an opaque `curve_revision` guard. Composite point writes use the separate `curve` action with that fresh revision; all other curve context is preserved and rechecked.

The bridge does not expose individual RGB curve writes, curve region splits, masks, crop, sharpening, denoise, camera profile writes, or arbitrary presets. Use an actually verified UI channel for a needed unsupported control or report the missing capability. Do not claim that a documented UI feature is available through this bridge.

## Native export and acceptance

`LrExportSession` renders high-quality JPEG (quality 0.95), sRGB, original dimensions, no output sharpening/watermark/reimport, copyright-only metadata, and location removal. Output must be an absolute directory that does not exist, preventing overwrite. Requested TIFF, HDR, or specialized formats need supported application export controls; do not substitute this fixed JPEG interface silently.

Reopen and visually inspect native before/after exports. Measure them read-only when helpful. Readback and file existence do not replace image inspection. A calibration chart establishes command/render functionality, not photographic style matching.

## Unknown outcomes and recovery

Each request uses a unique ID. The plugin atomically claims it as `.running` before executing, at most once per ID. It writes `.ready` only after completing the JSON receipt. The client therefore ignores partial or unrelated stale receipts. Default wait is 30 seconds; command `--timeout` supports 1–120 seconds.

For `outcome_unknown`, preserve the ID and query it:

```text
python scripts/lightroom_client.py status --request-id REQUEST_ID --timeout 15
```

**Do not automatically resend copy, apply, or export.** A `.running` marker without a completed result remains uncertain even after a timeout. Unclaimed expired requests are rejected by the plugin. Also inspect `progress` on explicit failures: `created_copy_id` identifies an already-created copy; `parameters_applied` means the write returned; `snapshot_name` identifies rollback. Reconcile with a new `read`, diagnose and repair the cause, then issue a new intentional guarded operation only if still necessary. Retain failed receipts and recovery notes.

The plugin makes no network requests and launches no external programs. Its local file protocol is not an authenticated remote service; do not expose it publicly. This does not imply the AI host processes images offline.

## Compatibility

Tested with Windows, Lightroom Classic 13.0.2, and ProcessVersion 15.4: import, virtual copies, tone/color, parametric and composite point-curve writes, independent readback, and native sRGB JPEG export. RAW white balance and other versions require separate native validation. A successful command does not establish aesthetic quality.

Primary API entry point: [Adobe Lightroom Classic SDK](https://developer.adobe.com/lightroom-classic/). Success claims must come from actual task receipts and Lightroom renders.
