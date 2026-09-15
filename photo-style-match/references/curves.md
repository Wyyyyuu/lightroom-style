# Tone curves

English · [简体中文](curves.zh-CN.md)

Read for S-curves, matte endpoints, or finer tonal separation. Compare a curve-only edit on a copy of the current grade before changing other controls.

## Choose from the image

- The white **RGB composite point curve** shapes all channels together. Lift the black endpoint for softer blacks, lower the white endpoint for restrained whites, and use middle anchors for tonal separation. This can suit a soft Japanese look; it is not a default preset or a substitute for matching the references.
- Endpoint compression and midtone contrast are separate decisions. A mild S lowers lower midtones and raises upper midtones; keep the subject readable and avoid crushed hair, gray whites, or exaggerated skin contrast. Backlit faces may need a flatter lower section.
- Inspect the existing curve, profile, exposure, and Basic contrast first. Preserve or deliberately replace existing anchors; never stack two S-curves unknowingly. Lowering an endpoint cannot recover detail already clipped in a JPEG.
- Composite RGB curves can also change saturation. Check skin and hue relationships in the native render. Individual R/G/B curves are separate color controls, not interchangeable with the white curve.

## Native point-curve operation

Require command module `0.2.2`, an enabled Tone Curve panel, and SDR PV2012 coordinates. Use `curve`, not numeric `--set`. Coordinates use input/output pairs from 0 to 255: 2–16 pairs, integer values, strictly increasing inputs, nondecreasing outputs, and input endpoints 0 and 255.

```python
from lightroom_client import send_command

identity = dict(catalog=catalog_path, path=target_path, photo_id=copy_id)
receipt = send_command("read", **identity)
assert receipt["ok"] and receipt["command_version"] == "0.2.2"
photo = receipt["result"]["photo"]
# Illustration only: softer endpoints with a mild middle S; adapt to the image.
points = [[0, 12], [32, 30], [64, 57], [128, 129],
          [192, 204], [224, 232], [255, 246]]
result = send_command("curve", **identity, curve_points=points,
                      expected_revision=photo["curve_revision"])
assert result["ok"] and result["result"]["readback_verified"]
```

Import the client from this skill's `scripts` directory. `curve_revision` is an opaque stale-state guard from a fresh read; pass it unchanged. The CLI equivalent accepts `--curve-points "0,12;32,30;64,57;128,129;192,204;224,232;255,246"` and `--expected-revision-file FILE` (exact UTF-8 revision, no added newline).

The bridge snapshots the copy, writes `ToneCurvePV2012` and its matching extended representation when present, sets the composite name to Custom, and verifies them. Existing RGB curves, parametric values, boundaries, profile, and Basic settings must remain unchanged. Disabled panels, HDR, stale state, and ambiguous extended curves are refused. Returned coordinates are indexed objects; decode keys in numeric order for comparison.

## Parametric alternative

`ParametricShadows`, `ParametricDarks`, `ParametricLights`, and `ParametricHighlights` each accept -100…100 through `apply` with fresh `--expect` values; see [bridge.md](bridge.md). They adjust tonal regions rather than explicit endpoints and differ from Basic Shadows/Highlights. Use when regional shaping suffices. An illustrative Darks -10 / Lights +10 is not a universal S-curve. The bridge requires an enabled panel and preserves point curves and region boundaries.

Individual RGB point curves, region-boundary changes, and HDR curve writes need a verified native UI channel; do not claim bridge support.

## Acceptance

Independently read back points/values and inspect native before/after exports at matching dimensions and color space. Check faces, endpoint detail, casts, saturation, banding, and tonal separation. A successful receipt with an unchanged render is insufficient. Do not infer an exact Lightroom spline or final pixel luminance from anchor coordinates alone. Reconcile failures using the snapshot and request ID; never blindly resend.

Reference: [Adobe Lightroom Classic tone and color controls](https://helpx.adobe.com/lightroom-classic/desktop/process-and-develop-photos/image-tone-color.html).
