# Tonal color: direct measurement and optional native observation

English · [简体中文](tonal-color.zh-CN.md)

Use this for reference-based tone/color analysis. Keep brightness structure and tonal color together: a shadow can be deep neutral, blue, cyan-green or warm brown; a highlight can be bright neutral, cream, gold or pink. Record the reference's actual relationship, not a default cool-shadow/warm-highlight recipe.

## What to record

Before choosing parameters, keep one compact row for **shadows, midtones and highlights** for reference and target:

| Tone zone | Light/dark role | Main hue/cold-warm tendency | Secondary hue / neutral content | Strength and extent | Evidence |
| --- | --- | --- | --- | --- | --- |
| Each of the three zones | Depth/brightness and protected detail | Specific hue, or neutral/mixed/unknown | A second material or color if significant | Saturated vs subtle; broad area vs small accent | Lightroom readout/screenshot, object/sample location and current version |

Separate “which hue occupies more area” from “which is most saturated” and “which has the strongest RGB channel.” Include low-chroma areas so a few colorful pixels do not get called the entire shadow/highlight base. Do not invent exact area percentages from sparse samples. Green and magenta cannot always be reduced to a universal warm/cool label; describe their hue and their relationship to adjacent colors. Treat very dark, clipped, near-neutral or mixed samples as uncertain.

## Direct file measurement: usual path

Use the bundled `scripts/analyze_images.py` (Pillow/NumPy); no additional plugin or desktop interaction is required for supported rendered files. It returns RGB/brightness histograms plus shadow/midtone/highlight Lab and hue-family distributions. See [analysis.md](analysis.md) for the CLI and color-management contract. These are file measurements, not Lightroom's internal histogram.

Reuse unchanged reference reports. For an edited target, analyze its existing current Lightroom export; the original file does not include catalog edits. For RAW, HDR, high-bit-depth or multi-frame sources, obtain a supported SDR preview through Lightroom first. Numerical reports stay on disk; read a compact summary rather than dumping histograms into context. Do not add export/analysis rounds if the current report already answers the question.

Read `hue_fractions_of_zone` together with `low_chroma_fraction_of_zone`. Their denominator is all sampled pixels in that brightness zone, so a small colored accent remains small even when it is the largest chromatic bin. The two `largest_chromatic_bins` are sampled color families, not necessarily the dominant overall base or recognized materials. Inspect mixed hues, sparse zones, and possible neutral casts; do not reduce green/magenta to an automatic warm/cool label.

Use the native workflow below only for an explicit native-only request, a specific rendering/color-management question, or a useful UI cross-check. A desktop-control failure does not block ordinary file analysis.

## Optional native observation workflow

1. Verify exact photo/catalog identity and current edit before selecting it. Use the Develop module with a verified readable desktop tool, after the native rendering settles. Do not interfere with another active editor. Keep the original/reference unmodified; use Reference View for comparison when available.
2. Inspect the **native RGB histogram** for channel distributions, overlap and clipping across its tonal span. Note relevant SDR/HDR/soft-proof state and Lightroom version. This is evidence of the native display, not a reconstruction from a screenshot of the photograph or an exported JPEG.
3. Hover over representative dark, middle and bright image areas to read **Lightroom's RGB percentages or Lab values under the histogram**. In Reference View the app can show reference/active readings; when dimensions differ, only the image being hovered may have values. Compare related materials/light roles, not arbitrary identical coordinates in unrelated scenes. Use a few well-chosen samples, including a neutral candidate and any competing color; one pixel is not a zone average. Record the sample's image/position/material, unit/readout mode and observed values, with a small UI evidence capture when useful. Hovering for a readout is not clicking the white-balance eyedropper.
4. Describe each zone's supported dominant and secondary tendency, then its relation to other zones. Compare references and target in the same native readout mode/display state. Use small positive/negative channel differences as measured evidence, not as direct Kelvin/tint or color-grading slider targets. Lightroom RGB readouts are not assumed to be exported 8-bit sRGB; do not mix their numbers with the external analyzer's D65 Lab or normalized sRGB statistics.
5. Choose controls for the **observed difference**. Color Grading, channel curves, white balance and HSL have different scopes and interact with luminance. After editing, revisit the same native samples and histogram, and verify the protected light/dark anchors as well as hue relationships. An unchanged brightness histogram does not establish an unchanged palette, and a good palette does not establish sufficient contrast.

## Verified Windows UI route

On Classic 13.0.2, native histogram screenshots and changing RGB percentage readouts have been verified through desktop control. This verifies visual histogram inspection and individual point readings, not a numeric histogram-bin API; Lab mode still needs its own live verification.

- Check that the screenshot actually depicts the selected Lightroom window and photo. Activation and a fresh capture may be necessary; a correct accessibility tree does not prove that the accompanying screenshot shows the same app.
- The accessibility tree can expose the histogram panel without its painted RGB numbers. Read those numbers from the native UI capture, retain units, and report only legible precision. Filter tree output to the relevant panel instead of printing the entire application tree.
- Prefer a supported hover operation and verify that the displayed values refresh. A zero-distance scroll moved the displayed pointer in testing but left stale RGB values; do not use it as verified hover. If hover is unavailable, a confirmed Hand/Zoom-tool click can refresh a readout by changing the view only. Inspect the resulting region and readout, record the zoom/final sample location, and restore the original view. Zoom may reposition the pointer, so the initial click coordinate is not proof of the final sampled pixel. Never use this fallback with a white-balance, mask, retouch, or adjustment tool active.
- If user input or another foreground window interrupts sampling, discard stale coordinates and reobserve. Keep the number of samples proportional to the actual color question.

## What the histogram cannot establish alone

RGB channel histograms are separate channel distributions. A blue lobe on the left is a distribution of low blue-channel values; it is not a count of blue-colored shadow pixels. Overlap colors describe channel-histogram overlap, not a joint pixel-hue chart. Channel peaks alone cannot give a hue-area percentage conditioned on perceptual brightness. Use image-location readouts to support tonal-color claims; use native displayed area statistics only if the actual tool exposes and defines them.

RGB percentages beneath the histogram are pixel channel values, not percentages of the photo covered by those colors. Lab a/b helps distinguish color axes, but a median/neutral average can conceal opposing colors. Preserve mixed/uncertain findings instead of forcing a single label.

## Availability and provenance

The current bundled bridge `read` returns develop settings and context. It has **no implemented read command for the native histogram bins or cursor RGB/Lab values**. This is a statement about this bridge, not proof that every Adobe SDK version lacks such an API. Color Grading hue/saturation settings and tone-curve control points are editing inputs, not measurements of the rendered photo; a zero slider can still accompany a baked-in color cast.

For native observation, use a verified native UI channel or an independently verified native API if supplied by the host. A fresh bridge connection or a native export does not prove histogram/readout access. After bounded UI recovery fails, mark native tonal-color observation unavailable and report that specific missing capability. Direct file measurement remains available unless the user requires native-only evidence. Do not silently claim that locally computed image statistics came from Lightroom.

Evidence labels:

- **Lightroom-native observation:** actual histogram/readout captured from the identified current photo. Point samples support that location; area dominance remains qualitative unless a native measurement supplies it.
- **Lightroom-rendered SDR proxy, externally measured:** script statistics on a native export, useful as an optional supplementary/fallback check when consistent with the user's request. They are not the native histogram or native Lab readouts.
- **File-based proxy:** external statistics on a standalone reference image, with the same limitations and stated profile assumptions.
- **Unavailable:** native values not obtained; do not populate invented values or substitute develop settings.

When the user requests native-only analysis, keep external measurement off unless they authorize a fallback. A preference for native analysis should make it the first path; explain any fallback explicitly. This does not remove the need to judge reference intent, relevant materials, framing and the final appearance.

Official sources: [Adobe tone, histogram and RGB/Lab readouts](https://helpx.adobe.com/lightroom-classic/desktop/process-and-develop-photos/image-tone-color.html), [Develop and Reference View](https://helpx.adobe.com/lightroom-classic/desktop/process-and-develop-photos/develop-module-tools.html).
