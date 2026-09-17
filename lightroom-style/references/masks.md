# Softness by luminance range

English · [简体中文](masks.zh-CN.md)

Use masks only when necessary: a specific regional change cannot be achieved with suitable global controls without harming other areas, or the user explicitly requests masking. A haze/softness request or soft-looking reference alone is not sufficient. If global adjustments meet the goal, skip this workflow, including region measurement and mask creation/adjustment. Decide from existing images; no extra trial export is required to establish necessity. First identify the soft-looking regions visually in the reference/original, then locate the corresponding brightness and spatial regions in the target. Lower local Clarity/Texture there. Negative Clarity reduces local contrast; negative Texture reduces fine detail. Neither recreates optical defocus or generates fog.

## Analyze once, then choose a region

Distinguish bright haze, soft shadows, shallow depth of field, and motion blur. Do not assume all bright pixels should be soft. Check eyes, skin, clothing and edges at similar brightness; a luminance mask selects them too. If these overlap, use a spatial intersection/subtraction through verified UI or soften less. Do not silently replace a required local mask with a global adjustment.

When brightness is uncertain, measure a few visually selected regions once, using a native SDR sRGB preview (not an undecoded RAW/MPO). Example region file:

```json
[
  {"name":"haze","role":"soft","box":[0.05,0.1,0.3,0.5]},
  {"name":"face","role":"protect","box":[0.45,0.2,0.6,0.45]}
]
```

Boxes are left/top/right/bottom fractions of the oriented image. These coordinates illustrate syntax, not fixed subject locations.

```text
python scripts/analyze_luminance.py PREVIEW.jpg --regions regions.json --output luminance.json
```

The helper reads pixels only, reports regional p10/median/p90 and brightness overlap with protected regions. It does not detect blur, generate masks, or infer Lightroom's exact slider settings from SDR luma. View reference and target separately; transfer the visual intention, not numerical thresholds between different scenes. Keep the compact observation and report path; no repeated analysis unless the image or region changes.

## One round, one native export

Command module 0.3.0 supports native luminance creation and range adjustment on Classic 13.0.2. Four ordered handles in 0..100 specify lower-none, lower-full, upper-full, upper-none. The outer intervals feather into/out of the fully affected range. This expresses transition explicitly; it is not a guessed conversion from a single Smoothness slider.

Example bright-softness step in a [round plan](rounds.md):

```json
{"action":"mask-create","mask_type":"luminance","luminance_range":[40,60,100,100],"clarity":-25,"texture":-20}
```

Values are examples, not a preset. Clarity/Texture are absolute UI values -100..0. Choose range/strength from the actual photo. Creation requires an explicit range; either or both softness controls may be supplied. For correction, reuse the returned ID:

```json
{"action":"mask-adjust","mask_id":"EXACT_RETURNED_ID","luminance_range":[50,65,100,100],"clarity":-15}
```

Range-only adjustment is allowed. It preserves the same mask and all its other local controls. The runner acquires fresh guards, records snapshots and IDs, independently checks all requested final values, then exports once with the global adjustments. Normally one visible correction is enough.

Automatic subject/sky/background creation is also available through native AI selection (no generated replacement). Existing masks can receive Clarity/Texture by exact ID. Range changes require a simple, active, non-inverted, single-tool luminance mask. Composite/intersected masks need verified UI for range geometry; they can still receive local softness by ID.

## Native implementation and verification

AI masks use LrDevelopController. Luminance creation uses a neutral native schema-3 seed captured from Lightroom 13.0.2, with new IDs per mask. The four range handles are applied through photo:applyDevelopSettings; existing correction entries are preserved and checked. The adapter is version-gated to 13.0.2 because this nested schema is observed application data, not a stable documented slider API. Other versions need separate acceptance or verified UI; never invent an opaque mask payload.

Background creation and luminance creation/adjustment have Windows / Classic 13.0.2 native readback/export acceptance. A textured five-band input confirmed that the highlight range affects the bright bands and the shadow range affects the dark bands. A real-photo range edit also rendered successfully. Source hashes and pre-mask master settings were unchanged. Subject/sky have mock coverage only. These checks prove control behavior, not that any mask is aesthetically right for a new photo.

Commands select only the exact PhotoStyle- virtual copy, switch to Develop/Masking, preserve a snapshot, and stop on stale state or selection drift. New masks neutralize supported numeric inherited controls and preserve linear local curves; unsupported non-neutral structures stop the operation. Do not operate the same controls concurrently.

## Readback and recovery

```text
python scripts/lightroom_client.py mask-read --catalog "CATALOG.lrcat" --path "TARGET.jpg" --photo-id COPY_ID --mask-id MASK_ID
```

This returns compact IDs, local values, revision, and native range when supported. Low-level creation accepts `--mask-type luminance --luminance-range 40,60,100,100 --clarity -25`; writes also need the exact identity and a fresh `--expected-mask-revision-file`. Prefer the round runner.

On partial failure query status with the same request ID, then reconcile mask-read. Progress records include snapshot_name, planned_mask_id, created_mask_id, luminance_range_requested, mask_creation_requested and parameters_applied. Never create again just because a response timed out. Failure does not imply rollback.

Inspect the native export at delivery size and 100%, especially protected details at similar brightness. Use native overlay when coverage is uncertain. Check one final export; reuse it when accepted and unchanged. A successful receipt alone is not visual acceptance.

Sources: [Adobe masking guide](https://helpx.adobe.com/lightroom-classic/desktop/process-and-develop-photos/masking.html), [Adobe SDK entry](https://developer.adobe.com/lightroom-classic/), [Adobe-authored Develop API reference, mirrored](https://lrc.mcor.dev/modules/LrDevelopController.html), [Photo API reference, mirrored](https://lrc.mcor.dev/modules/LrPhoto.html).
