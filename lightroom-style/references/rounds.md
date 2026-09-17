# Connected grading and compact rounds

English · [简体中文](rounds.zh-CN.md)

Use this path when the bridge is already connected. Read [bridge.md](bridge.md) only for setup/recovery, detailed parameter ranges, or low-level commands; [curves.md](curves.md) for curve decisions. Helpers exchange requests with Lightroom; only Lightroom edits and renders pixels.

## Prepare once

Run `python scripts/lightroom_probe.py --timeout 15`. Require a fresh protocol-1 response and successful catalog capability; record its exact catalog path. If disconnected, use bridge.md. For curves/grain, confirm command_version 0.2.3 or compatible in a command receipt.

Resolve exact reference and target paths. Import/read the target through lightroom_client.py, create one PhotoStyle- virtual copy, and export its native before image. Record IDs, baseline and receipts. Current selection is not target identity.

```text
python scripts/lightroom_client.py import --catalog "CATALOG.lrcat" --path "TARGET.jpg"
python scripts/lightroom_client.py read --catalog "CATALOG.lrcat" --path "TARGET.jpg" --photo-id MASTER_ID
python scripts/lightroom_client.py copy --catalog "CATALOG.lrcat" --path "TARGET.jpg" --photo-id MASTER_ID
python scripts/lightroom_client.py export --catalog "CATALOG.lrcat" --path "TARGET.jpg" --photo-id COPY_ID --output-dir "NEW_BEFORE_DIRECTORY"
```

Replace placeholders with absolute paths and returned IDs. The client prints compact receipts by default; read/import/copy retain settings needed for decisions. Full SDK receipts remain at receipt_path; `--full` prints them. An unknown outcome may not yet have a receipt file. Python send_command callers still receive full responses.

View each reference and the target once at a useful inspection size. Record 3–5 transferable traits, target mismatches and acceptance criteria. Reuse these notes during this task. Numerical analysis is optional when it answers an actual question. Do not re-read unchanged references, raw JSON or historical troubleshooting on every round.

## Execute one planned round

Put a JSON plan in the task directory. The values below illustrate syntax, not a preset:

```json
{
  "catalog": "C:/Photos/Catalog.lrcat",
  "path": "C:/Photos/target.jpg",
  "photo_id": "RETURNED_COPY_ID",
  "steps": [
    {"action": "apply", "settings": {"Exposure2012": 0.3, "Highlights2012": -15}},
    {"action": "apply", "settings": {"SaturationAdjustmentBlue": -10}}
  ]
}
```

Each step is one related group. A composite curve step uses `{"action":"curve","points":[[0,4],[128,128],[255,250]]}`. Use only controls actually supported for that photo. RAW Temperature/Tint and JPEG IncrementalTemperature/IncrementalTint have different units; both specify absolute slider targets. Grain is only for requested/reference-supported texture.

```text
python scripts/lightroom_round.py --plan "ABSOLUTE_PLAN.json" --round-dir "NEW_ABSOLUTE_ROUND_DIRECTORY"
```

The runner reads fresh guards before each group, applies groups sequentially with the existing native snapshots and checks, independently reads final settings, and exports once. It returns changes, snapshot IDs, output paths and receipt directory. `ok: true` means execution succeeded; `needs_visual_review` explicitly leaves visual acceptance to the agent. Full plans, pre-dispatch request IDs and receipts stay on disk. Existing round directories are rejected.

For a predictable target, make the first round a coherent look across needed controls. Inspect before another round. Use a separate early exposure/WB or texture checkpoint only when uncertainty justifies it. A second round corrects an identified visible issue; use a third only for a remaining material defect or a user-requested refinement. Stop when the observed acceptance criteria are met. Do not spend rounds on speculative polishing or try to equalize unrelated scene histograms.

The helper is synchronous; its timeout is per command. If the host yields a running shell session, poll that session, never start the round again. Follow the host's progress-update requirements.

## Inspect, recover, deliver

Inspect the Lightroom export against the recorded traits and references as needed. Check skin, readability, highlights, shadows and casts. Inspect texture/edges at 100% where relevant. Each export is currently full-size sRGB JPEG at quality 0.95; the helper does not implement reduced native previews. Read-only resized inspection copies are allowed, with native full-size crops for texture checks.

On a failed/unknown command, the runner stops before subsequent steps. Query the SAME request ID using `lightroom_client.py status --request-id ID`, read current state and inspect saved progress/snapshot data as described in bridge.md. Do not rerun a plan under a new directory to bypass uncertainty. An interruption can leave only a request intent; reconcile that ID first. Completed earlier steps remain applied; recovery never implies an automatic rollback or replay.

After visual acceptance, the existing native round export may be the deliverable if it already meets the requested format/location and settings have not changed. Its independent final read can serve as the final settings check. Reopen the chosen file, verify dimensions/profile and appearance; do not export identical pixels again merely to name a folder final. If settings change, repeat the relevant verification. Retain the editable copy, original baseline and rollback evidence.

Keep session.md concise: input roles, traits, exact catalog/copy IDs, baseline/rollback references, chosen round, acceptance, unresolved issues and next step. Detailed receipts belong in files. Case-study HTML, exhaustive analyses and cost-accounting reports are additional outputs only when requested.

For local softness, use [native masks](masks.md): command module 0.3.0, luminance ranges with explicit feather handles (Classic 13.0.2), subject/sky/background creation, and adjustment of an exact existing mask ID. Inspect each native render.

Individual channel steps add `"channel":"red"`, `"green"`, or `"blue"` to a curve step; see [curves.md](curves.md). Requires command module 0.3.1; omitted channel means composite.

Before accepting a round, compare original/reference/result for the ranked tonal anchors and subject-region separation, not just hue and texture. A black frame does not prove the lit scene is contrasty. Use the optional regional tool in [analysis.md](analysis.md) when this is unclear; successful readback is technical verification only. User rejection supersedes prior agent-only review.

Tonal-color acceptance compares shadows, midtones and highlights separately: dominant/secondary hue, low-chroma content and strength alongside brightness. Use [direct file measurement or requested native observations](tonal-color.md) with consistent provenance; bridge parameter receipts and external SDR statistics cannot be labeled native histogram analysis.
