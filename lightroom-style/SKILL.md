---
name: lightroom-style
description: Match reference photos' color and tone in local Lightroom Classic. Use for reference-based grading, adapting previously graded photos, or consistent photo series. Preserves originals and uses native edits, never image generation.
license: MIT
allowed-tools: exec_command write_stdin apply_patch view_image
metadata:
  tool-catalog: tools.yaml
---

# Lightroom Style

Analyze references, adapt the look to the target, and verify Lightroom's actual render. Respond in the user's language.

## Environment

Requires Lightroom Classic, Python 3.11+, and local file access. Set up the bundled plugin on first use as below. Tested on Windows with Classic 13.0.2; other environments need verification. Install analysis dependencies from `scripts/requirements.txt` in an existing runtime or virtual environment.

## Tools

Read [tools.yaml](tools.yaml) for host tool names and bundled CLI entry points. Invoke helpers through the host shell with paths resolved from this skill directory. Use [tool integration](references/tools.md) for host adaptation or optional desktop control. The catalog and `allowed-tools` do not register tools or override host permissions.

## Boundaries

- Lightroom renders all edited pixels. No generative editing, replacement content, external scripted grading, or direct catalog database writes.
- Preserve subjects, composition, and original files. Default to color/tone only; other edits must fit the user's requested scope.
- Treat references as read-only. Edit an identified virtual copy or a version with a recorded native rollback point. Current selection alone does not identify the user's target.
- Store personal images, reports, and receipts in a separate task directory, never inside this skill.

## Workflow

### 1. Connect and preserve

Resolve reference/target roles and exact paths; preserve transient attachments and hashes when copying them. Use [rounds.md](references/rounds.md) for connected operation; read [bridge.md](references/bridge.md) for setup, recovery, or detailed low-level controls. Probe first; if disconnected, follow its first-use setup automatically: install missing files, use an available verified UI tool to load/enable the plugin, then probe again. Respect host permissions. A timeout alone does not mean the plugin is absent; never overwrite an existing installation blindly or claim copying files loaded it. Reuse a working connection on later runs.

Verify the fresh diagnostic and catalog. Record target ID, copy identity, baseline settings/profile, rollback point, and a native before preview.

Use [lightroom.md](references/lightroom.md) only for desktop fallback, unsupported controls, batch synchronization, or another explicitly selected application. Distinguish missing desktop control from app permission denial using the bridge guide; request only the unresolved action. Do not treat every startup failure as requiring manual launch.

### 2. Analyze and adapt

View every reference and target. Before choosing sliders, record a short ranked visual brief: (1) where the dark and lit masses are and how strongly they separate, (2) black/white endpoints and contrast within the subject region, (3) selective hue/saturation and warm/cool relationships, (4) texture. Name concrete image evidence and what must survive the edit. Distinguish shared style from scene lighting/composition; do not average conflicting looks or give duplicates extra weight. Read the visual decision section of [analysis.md](references/analysis.md) for a new reference match or a user-reported style mismatch.

For tonal color, use [direct image measurement](references/tonal-color.md) when statistics help: the bundled analyzer reads RGB/brightness histograms and joint tone/hue distributions without desktop interaction. Reuse unchanged reference reports and analyze an existing current Lightroom export for edited results. Record main/secondary hue, low-chroma content, strength and evidence separately for shadows, midtones and highlights; brightness fractions alone are insufficient. Native UI readouts are an optional cross-check or an explicitly requested mode. Keep file statistics, native UI observations and grading inputs distinct.

Muted color, grain and soft highlight transitions do not imply low tonal contrast. Deep shadows can coexist with bright whites and strong subject separation; an already-black foreground frame cannot compensate for a flat central subject. Do not infer a universal matte/teal look from “film.”

Read [analysis.md](references/analysis.md) for optional external measurements or their interpretation; honor a request for native-only analysis. Histograms support visual judgment; they neither determine Lightroom settings nor define a cross-scene similarity score. If external/file measurement is authorized, obtain a native SDR sRGB measurement preview for RAW, HDR, high-bit-depth or multi-frame inputs while retaining the original editing source. Native-only observation uses Lightroom directly and does not require a measurement export.

Previously graded JPEGs have baked-in edits even with zero sliders. Diagnose their current appearance; Reset cannot recover the ungraded source.

### 3. Adjust and inspect

Set the tonal intent before palette/texture: preserve or establish the reference-supported lit/shaded separation, then refine color. Plan a coherent first result across the needed controls. When lowering Highlights, Whites and the curve shoulder together, or raising Shadows/black endpoints, identify the visible problem and the bright/dark anchor being protected; do not stack compression just to make a photograph “soft.” Use scripts/lightroom_round.py to apply related groups sequentially, independently read back, and export once; inspect before deciding another round. Keep an intermediate exposure/WB or texture checkpoint when uncertainty justifies it. Use absolute values with fresh expected old values; respect RAW versus JPEG white-balance units and supported controls.

For broader color relationships, consider [RGB primary hue calibration](references/calibration.md) when justified by the reference. It affects mixed colors and skin as well as the named primary; include it in the first round, then refine selective hues with HSL. Do not add it by default.

For requested or reference-supported grain, use the bridge guide's native grain controls; inspect texture at 100% and delivery size, not histograms alone. Do not add grain by default.

Masks are optional: use them only for a concrete regional change that suitable global controls cannot achieve without harming other areas, or when the user explicitly requests masking. Otherwise skip mask-specific analysis and operations. A soft-looking reference alone does not require a mask. When local softness needs a mask, read [masks.md](references/masks.md); protect important details, choose the appropriate region or feathered luminance range, and reuse its ID for corrections. Decide from the images already available; do not add a global-only trial round just to justify masking. Reduced clarity/texture is not true optical blur.

For S-curves or finer tonal separation, read [curves.md](references/curves.md). The bridge supports parametric, white composite, and individual red/green/blue point curves (command module 0.3.1).

Read back parameters and compare the native original, current result and references at comparable display sizes. Verify the ranked visual brief first: is the subject’s light/shade separation convincing, are intended bright whites still luminous, and are intended deep shadows still deep? Inspect a subject-region crop in addition to the full frame when borders/foreground dominate. Recheck shadow/midtone/highlight color relationships using the same measurement source and region definitions, then check skin, readability, casts, banding and color edges. Correct the highest-impact mismatch instead of repeatedly nudging hue while the tone remains wrong. For batches, establish a representative edit per lighting group, adapt each target, and inspect every result.

For `outcome_unknown`, query the same request ID and reconcile current state using the bridge guide. Never blindly resend `copy`, `apply`, `curve`, `mask-create`, `mask-adjust`, or `export`.

### 4. Verify and deliver

Aim for one complete adjustment/render round, then at most one targeted correction when a visible mismatch remains. Use a third only for a material defect or user-requested refinement; this is a ceiling, not a quota. Stop once the recorded style and quality criteria are met. Preserve the best reversible result if a mismatch remains; continue when the user requests more iteration.

Independently read back final settings and inspect the application-rendered result. A diagnostic, preset, or file's existence is not completion. Keep the editable copy and export to a new location in the requested format; otherwise use a high-quality sRGB JPEG unless the user wants application-only editing. Reopen the export and check appearance, dimensions, and profile. If the accepted round already has an independent final read and a suitable native export, reuse them when settings are unchanged; do not repeat the same export/check merely for a final folder.

Separate technical verification from aesthetic review: successful readback and export do not establish a style match. Record user rejection as superseding prior agent review; do not mark user acceptance without their response. Deliver the preview/file link, copy identity, key changes, and any material limitation. Keep a concise `session.md` in the task directory with input roles, style observations, copy/rollback IDs, receipts, checks, and next step so interrupted work resumes without replaying mutations.

## Keep execution context small

Reuse this task's brief style observations and fresh connection; load detailed guides and numerical reports only when relevant. Keep full receipts on disk, use compact command/round summaries, and inspect raw data on failures or a specific question. Resume from session.md and the referenced latest evidence rather than replaying history. Do not create comparison sites, exhaustive reports, or usage-accounting artifacts unless requested. Never skip visual acceptance to meet a round or token budget.
