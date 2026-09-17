# Measurement and photographic judgment

English · [简体中文](analysis.zh-CN.md)

For tonal-color judgments, normally use the direct file measurements below and the [tone/color interpretation guide](tonal-color.md). They need no extra plugin or UI interaction and are **rendered-image measurements**, not native Lightroom histograms. Brightness-zone fractions must be paired with color distributions per zone; an overall palette or a single Lab median can conceal mixed hues. Honor explicit native-only requests; native UI observation remains an optional cross-check.

## Input and output contract

`scripts/analyze_images.py` reads rendered 8-bit SDR JPEG, PNG, TIFF, WebP, and BMP images. It does not decode camera RAW, edit images, or control Lightroom. It writes one new JSON report and refuses to overwrite it. Analyze explicitly supplied files, never scan a personal photo library recursively.

```text
python scripts/analyze_images.py --references REF1.png REF2.png --targets CURRENT_EXPORT.jpg --output NEW_REPORT.json
```

Reuse unchanged reference reports and current exports; inspect a compact summary while leaving full histogram arrays on disk.

Embedded ICC profiles are converted in memory to sRGB through Pillow LittleCMS. Conversion errors are failures, not permission to discard a profile. Untagged images are marked as assumed sRGB; untagged PNGs with explicit non-sRGB gamma/chromaticity are rejected. Unknown or wide-gamut workflows may need a native standardized preview first. EXIF orientation is applied in memory; transparent and partially transparent samples are excluded without adding a background.

Conversion to 8-bit sRGB may clip out-of-gamut colors; the script does not separately quantify this. Rendered endpoints therefore do not prove clipping in the original or in Lightroom's internal pipeline.

Known high-bit-depth images, unsupported modes, multi-frame/MPO files, and some HDR gain maps are rejected. HDR detection is incomplete: successful decoding does not prove an input is SDR. Native SDR previews are measurement proxies, never replacements for the editing source or a requested high-quality output format.

The deterministic nearest-neighbor sampling grid has a maximum long edge of 1400 pixels and does not enlarge small images. This avoids interpolating colors but may miss small highlights and texture. Inspect grain, sharpening, banding, and edges visually at 100%. Fractions are sample estimates, not full-resolution exact counts.

## Reading the report

| Field | Meaning | Invalid inference |
| --- | --- | --- |
| `encoded_luma` | Gamma-encoded sRGB brightness proxy, 0–1, quantiles and 64-bin histogram | Lightroom's internal histogram or physical scene brightness |
| `linear_luminance_quantiles` | Relative luminance after the sRGB inverse transfer function | RAW exposure or sensor dynamic range |
| `rendered_endpoint_fraction` | Rendered near-black/white and channel endpoint fractions | Irrecoverable capture clipping; a red object can naturally reach a channel endpoint |
| `hsv_saturation_quantiles`, `lab_chroma_quantiles` | Two measures of color strength | Lightroom slider values or a cross-scene style score |
| `hue` | Twelve circular hue bins excluding dark, near-neutral, and very bright samples; null without eligible pixels | Semantic objects or evidence that green content means a green cast |
| `tonal_zones` | Fractions, median Lab, low-chroma content and joint tone/hue distribution in fixed brightness intervals | Skin/sky segmentation or identification of the light source |
| `hue_fractions_of_zone`, `largest_chromatic_bins` | C* >12 hue-family area estimates within a brightness zone; 30° bins centered on red at 0°; denominator includes low-chroma samples | The largest colorful bin necessarily dominates a mostly neutral zone; exact full-resolution areas |
| `low_chroma_fraction_of_zone` | C* ≤12 fraction of the zone; sums with its hue fractions to 1; null for an empty zone | Proof of neutral material or absence of a subtle color cast |
| `low_chroma_median_ab` | Median a*/b* for C* ≤12 with at least 32 samples | A neutral-gray detector or true white balance |
| `reference_summary` | Equal-image medians, MAD, min/max; exact file SHA-256 deduplication | Automatic style consensus, outlier removal, or statistical confidence |

Lab uses sRGB → XYZ and a D65 white point: L* is approximately 0–100, positive a* is red, negative a* green, positive b* yellow, and negative b* blue. Do not mix it directly with D50 ICC PCS values. Tonal zones use encoded brightness <0.25, 0.25–0.75, and >0.75, not per-image quantiles. Sparse zones provide weak evidence.

Read medians alongside MAD, ranges, and individual references. Small samples, unknown color management, differing content/light, and conflicting references weaken conclusions. A mean between two distinct looks may represent neither. Exact hashing cannot recognize recompressed or visually near-duplicate images; identify those visually and reduce their influence.

## Visual decisions before sliders

Use a short evidence → adaptation → acceptance brief, ranked by perceptual importance. Avoid a palette-only list such as “teal, warm whites, grain.”

1. **Light structure:** identify the lit subject, shaded masses, brightest meaningful surfaces and transitions. Is the reference strongly separated, diffuse/high-key, or flat? Which comes from lighting/composition and which can transfer? Choose a reference for each relevant material; a warm stone wall does not require warming every sky.
2. **Tone independently of color:** distinguish deep versus lifted blacks, luminous versus subdued diffuse whites, specular peaks, subject-region tonal spread, and edge/detail contrast. Low saturation is not low contrast; a soft edge is not a flattened tonal range. Near-black borders can coexist with muddy midtones inside them. Low global median brightness can describe a mostly dark composition without saying how the illuminated subject should look.
3. **Color by material and tonal role:** state what is colored, how strongly, and which neutrals stay neutral. Preserve selective color differences. “Muted” may apply to sky but not water or an ochre chair. Do not globally desaturate merely because one large region is muted.
4. **Texture last in priority:** grain, haze and optical blur are separate from light/shade separation. They cannot rescue incorrect tone. Use masks only for a justified regional change, not as a style default.

For high-contrast references, choose a concrete bright anchor and dark anchor within/near the subject. Keep deep framing shadows when intentional, but check separation inside the scene too. For genuinely low-contrast references, preserve their narrower range instead; this is not a new always-increase-contrast rule.

Before writing, state the target's largest mismatch and intended direction in one sentence. Check the combined effect of exposure, Basic controls, composite and channel curves, and grading luminance. Multiple highlight reductions plus a lowered white endpoint can make luminous white gray; shadow recovery plus a raised toe can erase the intended dark anchor. Preserve existing source separation unless changing it is supported by the references. Do not copy parameter values between different sources.

### Optional regional evidence

When the full histogram is dominated by dark framing, mixed illumination, or the user reports flatness, use `scripts/analyze_tone_regions.py`. Draw a few normalized rectangles from viewed images: one subject region and relevant bright/dark surfaces. Use the same boxes on native target before/after exports; choose separate boxes on references for comparable materials. Regions may mix objects, so inspect their content rather than treating labels as segmentation.

```json
{"regions":[{"name":"shade","box":[0.1,0.2,0.3,0.4]},
            {"name":"lit","box":[0.5,0.2,0.7,0.4]}],
 "pairs":[{"name":"subject light/shade","dark":"shade","light":"lit"}]}
```

```text
python scripts/analyze_tone_regions.py --images BEFORE.jpg AFTER.jpg --regions REGIONS.json --output NEW_REPORT.json
```

The helper reports regional brightness quantiles/spread, median Lab/saturation and signed light-minus-dark median gaps. These are encoded-sRGB evidence, not exposure stops, microcontrast, automatic regions, Lightroom settings or style scores. Grain and object boundaries also affect regional spread. A strong global histogram span does not pass a weak subject-region contrast check. Do not force different scenes to equal numeric gaps, and do not use a universal pass threshold. Prefer one targeted report when it resolves uncertainty; skip exhaustive regional measurement otherwise.

## Turn observations into a target

Describe only supported characteristics, for example:

| Observed feature | Evidence and consistency | Target-specific adaptation | Candidate controls |
| --- | --- | --- | --- |
| Deep shade against luminous lit surfaces | Visible bright/dark anchors, also within the subject region | Preserve strong separation without losing important detail | Exposure, white/black points and midtone curve |
| Lifted blacks / compressed range, when actually present | Repeated visible endpoints; not inferred from grain | Adapt a flatter range only where supported | Curve toe/shoulder and Basic tone controls |
| Warm highlights with cooler shadows | Comparable materials and light support it | Protect skin from a global blue cast | Grading and supported non-generative masks |
| Muted yellow-green vegetation | Repeated in references containing plants | Apply only to relevant target colors | HSL/color mixer |

These examples are a reasoning format, not a default film preset. Do not automatically add teal shadows, warm highlights, grain, or a matte curve.

Semantic decisions require viewing images; the analyzer has no segmentation. Compare similar materials under similar lighting. For numerical regional comparisons, use a verified non-generative selection or application-exported region and disclose the selected sample. Do not label a region's statistics as whole-image evidence.

Already graded JPEGs need diagnosis of their current pixels. Zero imported sliders do not mean an ungraded image, and the source cannot be recovered by Reset. Similar brightness distributions can coexist with very different hues. Correct the actual mismatch instead of automatically lowering or raising exposure to chase a reference median.

## Evaluate change

Use the same target, crop, profile, and SDR export conditions before and after. Compare full frame and the chosen subject region against the ranked brief, with original/reference/current visible at matched display sizes. If the center loses separation while a dark border stays black, record that as a tonal regression instead of declaring the contrast preserved. Check readability, natural skin, endpoint detail, and local edges before numerical similarity. Then assess whether the requested transferable characteristics appeared. A negative user assessment overrides earlier agent-only acceptance; record the remaining mismatch separately from successful technical checks. Encoding may introduce small differences; do not demand identical measurements.

Do not use global histogram distance as the sole optimization objective. A white-background portrait and a dark forest can share a look while having different distributions. Avoid forcing identical exposure, gray point, temperature, or saturation medians across unrelated scenes.

Color management implementation: [Pillow ImageCms documentation](https://pillow.readthedocs.io/en/stable/reference/ImageCms.html). Converted analysis pixels are never written back to the source.
