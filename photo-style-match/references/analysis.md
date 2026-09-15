# Measurement and photographic judgment

English · [简体中文](analysis.zh-CN.md)

## Input and output contract

`scripts/analyze_images.py` reads rendered 8-bit SDR JPEG, PNG, TIFF, WebP, and BMP images. It does not decode camera RAW, edit images, or control Lightroom. It writes one new JSON report and refuses to overwrite it. Analyze explicitly supplied files, never scan a personal photo library recursively.

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
| `tonal_zones` | Fractions and median Lab in fixed brightness intervals | Skin/sky segmentation or identification of the light source |
| `low_chroma_median_ab` | Median a*/b* for C* ≤12 with at least 32 samples | A neutral-gray detector or true white balance |
| `reference_summary` | Equal-image medians, MAD, min/max; exact file SHA-256 deduplication | Automatic style consensus, outlier removal, or statistical confidence |

Lab uses sRGB → XYZ and a D65 white point: L* is approximately 0–100, positive a* is red, negative a* green, positive b* yellow, and negative b* blue. Do not mix it directly with D50 ICC PCS values. Tonal zones use encoded brightness <0.25, 0.25–0.75, and >0.75, not per-image quantiles. Sparse zones provide weak evidence.

Read medians alongside MAD, ranges, and individual references. Small samples, unknown color management, differing content/light, and conflicting references weaken conclusions. A mean between two distinct looks may represent neither. Exact hashing cannot recognize recompressed or visually near-duplicate images; identify those visually and reduce their influence.

## Turn observations into a target

Describe only supported characteristics, for example:

| Observed feature | Evidence and consistency | Target-specific adaptation | Candidate controls |
| --- | --- | --- | --- |
| Slightly lifted blacks with detail | Repeated visually across different scenes; histogram supports | Keep dark hair and clothing separated | Black point/curve, shadows, blacks |
| Warm highlights with cooler shadows | Comparable materials and light support it | Protect skin from a global blue cast | Grading and supported non-generative masks |
| Muted yellow-green vegetation | Repeated in references containing plants | Apply only to relevant target colors | HSL/color mixer |

These examples are a reasoning format, not a default film preset. Do not automatically add teal shadows, warm highlights, grain, or a matte curve.

Semantic decisions require viewing images; the analyzer has no segmentation. Compare similar materials under similar lighting. For numerical regional comparisons, use a verified non-generative selection or application-exported region and disclose the selected sample. Do not label a region's statistics as whole-image evidence.

Already graded JPEGs need diagnosis of their current pixels. Zero imported sliders do not mean an ungraded image, and the source cannot be recovered by Reset. Similar brightness distributions can coexist with very different hues. Correct the actual mismatch instead of automatically lowering or raising exposure to chase a reference median.

## Evaluate change

Use the same target, crop, profile, and SDR export conditions before and after. Check readability, natural skin, endpoint detail, and local edges before numerical similarity. Then assess whether the requested transferable characteristics appeared. Encoding may introduce small differences; do not demand identical measurements.

Do not use global histogram distance as the sole optimization objective. A white-background portrait and a dark forest can share a look while having different distributions. Avoid forcing identical exposure, gray point, temperature, or saturation medians across unrelated scenes.

Color management implementation: [Pillow ImageCms documentation](https://pillow.readthedocs.io/en/stable/reference/ImageCms.html). Converted analysis pixels are never written back to the source.
