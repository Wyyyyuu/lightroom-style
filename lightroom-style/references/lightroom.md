# Lightroom application workflow

English · [简体中文](lightroom.zh-CN.md)

Prefer the verified Classic integration described in [bridge.md](bridge.md). This document covers a desktop fallback and controls outside the bridge. Read the current desktop tool instructions before acting; do not use fixed-coordinate macros.

## Classic desktop fallback

1. Discover the actual application, window, catalog, and Develop module. A process or window title alone does not establish control: obtain readable current UI state. Handle real login/permission/catalog dialogs under the task's authorization; do not upgrade a catalog merely to test this skill.
2. Locate the exact requested target. Reuse the catalog object where possible; if needed, import only the specified file, usually using Add for an existing local file. Do not move originals, scan/synchronize whole folders, or change cloud synchronization. References can remain in an external viewer; importing them does not authorize edits.
3. Verify single selection and Auto Sync. Create and identify a named virtual copy, inheriting existing edits. If unavailable, use a documented snapshot/version rollback mechanism. Never Reset by default or overwrite a same-named version.
4. Record copy/source identity, profile, process version, existing masks, and baseline values relevant to the changed groups. Obtain a baseline render under consistent conditions.
5. Use Reference View, before/after, or an observable side-by-side comparison. Distinguish Reference from Active: edits go to Active. View all references even if the interface offers one reference slot.
6. Adjust one related group, preferably by editable numeric values. For sliders, make bounded changes and read the result. Observe → target → act once → refresh/verify, subject to the current tool's interaction rules.
7. Preserve the checked copy/snapshot and export within scope. A virtual copy is a catalog edit relationship, not a separately exported image.

## Controls and pitfalls

| Goal | Candidate control | Check |
| --- | --- | --- |
| Overall or subject brightness | Exposure, whites/blacks, supported local masks | Target lighting, not a copied reference exposure |
| Black level, contrast, highlight shoulder | Tone curve, contrast, highlights/shadows | Detail, current curve mode, channel, and actual point-entry support |
| Light-source color | Temperature/tint | RAW Kelvin versus RGB/JPEG units; never assume the same scale |
| Specific hue strength or brightness | HSL/color mixer | Actual channel, direction, and collateral effects |
| Tonal warm/cool relationships | Grading shadows/midtones/highlights, blending/balance | Correct wheel versus luminance slider; hue needs saturation to affect color |
| Separate skin or sky treatment | Native non-generative masks | Selection boundaries and spill; no generative content replacement |

Preserve the profile by default because it changes the entire color response. If changing it is needed within the task, test on the copy and record why. Add grain or film simulation only with reference evidence and a relevant user goal.

For batches, finish representative images per scene/light first. A reusable preset can transfer verified color/tone settings, but exposure, white balance, and local masks generally need individual adaptation. Check every image and restore a clear rollback point if synchronization affects unintended settings.

Deliver XMP presets only when reuse is requested or needed. Prefer Lightroom's native Create Preset/Export for verified settings. Writing an XMP file is not proof of import or application. Never confuse a preset with a RAW sidecar, overwrite a source sidecar, or read metadata from disk over existing catalog edits without explicit intent.

Export to a new task directory/name. Local review commonly uses SDR sRGB high-quality JPEG, while requested TIFF, bit depth, dimensions, or other formats must be honored through supported controls. Keep source RAWs. Reopen the export and check image, dimensions, profile, and intended look. Resolve overwrite dialogs by choosing a new name.

## Lightroom cloud desktop and other applications

Use this branch only when the user selects that product. Do not assume Classic menus, virtual copies, or SDK interfaces apply. Inspect the actual version and Local/Cloud workspace. Cloud import can upload originals; a local grading request does not itself authorize that upload or changes to synchronization/privacy settings.

Use native Versions or another verified rollback mechanism. The observation/edit/render loop still applies. If local controls or required features are absent, identify the limitation; do not invent a remote API or silently substitute software.

The Classic SDK is an optional plugin integration, not a preinstalled MCP service. Confirm a loaded authorized bridge and its current capabilities before use. Do not invent HTTP endpoints, CLI develop flags, or support for the cloud product.

If UI reading fails, follow the tool's bounded recovery procedure. On repeated failure stop input, preserve analysis, and report application work as incomplete. A discoverable process is not evidence that blind keyboard automation is safe or functional.

## Validation boundary

The plugin manager's **运行只读连接检查** (Run read-only connection check) produces diagnostics only. Accept a fresh request-matched receipt and inspect each capability. Enabled status, an old JSON file, or SDK method existence does not prove that an edit succeeded.

Classic 13.0.2 has historical native JPEG import/copy/apply/readback/export verification. Each real task still needs its own parameter receipts and rendered inspection. RAW Kelvin white balance, other versions, the cloud product, and bridge-unsupported controls require separate acceptance.

Official reference: [Adobe Lightroom Classic SDK](https://developer.adobe.com/lightroom-classic/). Installed controls and current tool results determine what can actually be executed.
