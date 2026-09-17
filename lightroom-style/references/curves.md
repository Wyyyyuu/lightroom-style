# Tone curves

English · [简体中文](curves.zh-CN.md)

Read for S-curves, matte endpoints, or finer tonal separation. Compare a curve-only edit on a copy of the current grade before changing other controls.

## Choose from the image

- The white **RGB composite point curve** shapes all channels together. Choose endpoints from the reference: retain deep blacks and luminous whites for a strong light/shade look; lift the toe or lower the shoulder only when visibly supported. Middle anchors set tonal separation. Neither film grain nor muted color implies compressed endpoints.
- Endpoint compression and midtone contrast are separate decisions. A mild S lowers lower midtones and raises upper midtones; keep the subject readable and avoid crushed hair, gray whites, or exaggerated skin contrast. Backlit faces may need a flatter lower section.
- Inspect the existing curve, profile, exposure, and Basic contrast first. Preserve or deliberately replace existing anchors; never stack two S-curves unknowingly. Lowering an endpoint cannot recover detail already clipped in a JPEG.
- Composite RGB curves can also change saturation. Check skin and hue relationships in the native render. Individual R/G/B curves are separate color controls, not interchangeable with the white curve.

## Native point-curve operation

Require command module `0.3.1`, an enabled Tone Curve panel, and SDR PV2012 coordinates. Use `curve`, not numeric `--set`. Coordinates use input/output pairs from 0 to 255: 2–16 pairs, integer values, strictly increasing inputs, nondecreasing outputs, and input endpoints 0 and 255.

```python
from lightroom_client import send_command

identity = dict(catalog=catalog_path, path=target_path, photo_id=copy_id)
receipt = send_command("read", **identity)
assert receipt["ok"] and receipt["command_version"] == "0.3.1"
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

Region-boundary changes and HDR curve writes still need a verified native UI channel.

## Individual red, green, and blue curves

With command module 0.3.1, select `curve_channel="red"`, `"green"`, or `"blue"` in `send_command("curve", ...)`, or CLI `--curve-channel red`. Omission/`composite` retains white-curve behavior. Round plans accept `{"action":"curve","channel":"blue","points":[[0,3],[64,69],[128,128],[192,187],[255,249]]}`; these points illustrate syntax, not a preset. Each step uses a fresh revision; group the needed channel steps before one export.

A channel write changes only `ToneCurvePV2012Red/Green/Blue` and its matching extended representation when present, plus the shared Custom name. It preserves composite and unrequested channel curves, parametric settings, profile and Basic controls. Missing channels and ambiguous extended representations are refused. The client sends a distinct `curve-channel` wire action so older plugins fail rather than edit the composite curve accidentally. Apply the same coordinate, identity, snapshot and readback rules above.

Raise red for more red / lower for cyan; raise green for green / lower for magenta; raise blue for blue / lower for yellow, confined by the curve's input region. Start with restrained offsets and neutral anchors outside the intended region. Curves, white balance and grading interact; avoid stacking a cast or flattening the subject. Inspect actual render and all channel curves. RGB primary hue calibration is a different control. Use only when a channel-specific tonal color change helps the reference match.

## Acceptance

Independently read back points/values and inspect native before/after exports at matching dimensions and color space. Check faces, endpoint detail, casts, saturation, banding, and tonal separation. A successful receipt with an unchanged render is insufficient. Do not infer an exact Lightroom spline or final pixel luminance from anchor coordinates alone. Reconcile failures using the snapshot and request ID; never blindly resend.

Reference: [Adobe Lightroom Classic tone and color controls](https://helpx.adobe.com/lightroom-classic/desktop/process-and-develop-photos/image-tone-color.html).
