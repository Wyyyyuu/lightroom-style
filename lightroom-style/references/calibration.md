# Calibration: RGB primary hue

English · [简体中文](calibration.zh-CN.md)

Use when the reference calls for a broader change in color relationships that white balance and selective HSL alone do not explain. Calibration changes the red/green/blue primaries; it is not the HSL red/green/blue color bucket. Mixed colors and skin can move together. Inspect the native result rather than treating a primary as a selection mask.

Choose exposure/white balance and retain the existing profile/process first. If calibration is justified, make a modest, coherent primary-hue change in the first round, then use HSL for remaining selective differences. There is no fixed recipe, mandatory blue-primary shift, or extra calibration round. If only one object's color is wrong, prefer HSL or a local mask. Do not add calibration by default.

## Supported fields

| Calibration control | Native field | Absolute slider range |
| --- | --- | --- |
| Red Primary Hue | `RedHue` | -100 to 100 |
| Green Primary Hue | `GreenHue` | -100 to 100 |
| Blue Primary Hue | `BlueHue` | -100 to 100 |

These are slider units, not hue degrees. `HueAdjustmentRed/Green/Blue` remain separate HSL parameters. Primary saturation and shadow tint are read-only context for this feature; preserve them, the profile and process version. A disabled Calibration panel stops the write, rather than silently enabling inherited edits.

Example step for the [round runner](rounds.md), demonstrating syntax rather than a preset:

```json
{"action":"apply","settings":{"RedHue":12,"GreenHue":-8,"BlueHue":-15}}
```

Choose only needed fields. The existing apply path checks exact copy identity, fresh expected values, ranges, panel/profile/process context, snapshot and native readback. A final independent read checks requested hues and calibration context before one shared export. Reuse accepted output; no duplicate analysis or render.

Inspect skin, sky, foliage, saturated colors and neutral surfaces. A pleasing sky with damaged skin is not a successful match. Correction can reduce or restore the original primary values on the same copy. Do not change camera defaults, presets, or profiles as part of a per-photo calibration edit.

Windows / Classic 13.0.2: all three hue fields were written together on an isolated JPEG virtual copy, independently read back, exported and inspected at full-frame and 100% skin detail. Source hashes and master settings were unchanged; HSL, primary saturation, shadow tint, profile and process were retained. This verifies control behavior, not a universal look. RAW and other versions need separate acceptance; zero sliders on an already graded JPEG do not undo its baked-in look.

Sources: [Adobe calibration guide](https://helpx.adobe.com/lightroom-classic/desktop/process-and-develop-photos/image-tone-color.html#adjust_the_color_calibration_for_your_camera), [Adobe-authored Develop API reference, mirrored](https://lrc.mcor.dev/modules/LrDevelopController.html).
