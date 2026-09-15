---
name: photo-style-match
description: Match reference photos' color and tone in local Lightroom Classic. Use for reference-based grading, adapting previously graded photos, or consistent photo series. Preserves originals and uses native edits, never image generation.
license: MIT
allowed-tools: exec_command write_stdin apply_patch view_image
metadata:
  tool-catalog: tools.yaml
---

# Photo Style Match

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

Resolve reference/target roles and exact paths; preserve transient attachments and hashes when copying them. Read [bridge.md](references/bridge.md) before SDK commands. Probe first; if disconnected, follow its first-use setup automatically: install missing files, use an available verified UI tool to load/enable the plugin, then probe again. Respect host permissions. A timeout alone does not mean the plugin is absent; never overwrite an existing installation blindly or claim copying files loaded it. Reuse a working connection on later runs.

Verify the fresh diagnostic and catalog. Record target ID, copy identity, baseline settings/profile, rollback point, and a native before preview.

Use [lightroom.md](references/lightroom.md) only for desktop fallback, unsupported controls, batch synchronization, or another explicitly selected application. If a necessary UI action cannot be automated, explain the failed capability and request that specific action.

### 2. Analyze and adapt

View every reference and target. Identify recurring tone, key hues, warm/cool relationships, skin, and texture; distinguish shared style from scene lighting and composition. Record a few transferable characteristics and the target's actual mismatches. Do not average conflicting looks or give duplicates extra weight.

Read [analysis.md](references/analysis.md) when measuring images or interpreting reports. Histograms support visual judgment; they neither determine Lightroom settings nor define a cross-scene similarity score. For RAW, HDR, high-bit-depth, or multi-frame inputs, obtain a native SDR sRGB measurement preview while retaining the original editing source.

Previously graded JPEGs have baked-in edits even with zero sliders. Diagnose their current appearance; Reset cannot recover the ungraded source.

### 3. Adjust and inspect

Correct target-specific exposure/white balance when needed, then refine tone, HSL, and grading. Change one related group at a time. Use absolute values with fresh expected old values; respect RAW versus JPEG white-balance units and supported controls.

For S-curves or finer tonal separation, read [curves.md](references/curves.md). The bridge supports parametric and white RGB composite point curves; individual RGB curves require verified UI controls.

Read back parameters and inspect each native render against the references. Check skin, subject readability, highlights, shadow detail, casts, banding, and color edges. For batches, establish a representative edit per lighting group, adapt each target, and inspect every result.

For `outcome_unknown`, query the same request ID and reconcile current state using the bridge guide. Never blindly resend `copy`, `apply`, `curve`, or `export`.

### 4. Verify and deliver

Use up to three adjustment/render rounds by default. If a mismatch remains, preserve the best reversible result and explain it; continue when the user requests more iteration.

Independently read back final settings and inspect the application-rendered result. A diagnostic, preset, or file's existence is not completion. Keep the editable copy and export to a new location in the requested format; otherwise use a high-quality sRGB JPEG unless the user wants application-only editing. Reopen the export and check appearance, dimensions, and profile.

Deliver the preview/file link, copy identity, key changes, and any material limitation. Keep a concise `session.md` in the task directory with input roles, style observations, copy/rollback IDs, receipts, checks, and next step so interrupted work resumes without replaying mutations.
