#!/usr/bin/env python3
"""Read rendered SDR photos and report color evidence. Never write image pixels."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
import warnings
from pathlib import Path

import numpy as np
from PIL import Image, ImageCms, ImageOps


PERCENTILES = [1, 5, 25, 50, 75, 95, 99]
ALLOWED = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp", ".bmp"}
WEIGHTS = np.array([0.2126, 0.7152, 0.0722])
warnings.simplefilter("error", Image.DecompressionBombWarning)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def quantiles(values: np.ndarray) -> dict:
    return {f"p{p:02}": float(v) for p, v in zip(PERCENTILES, np.percentile(values, PERCENTILES, method="linear"))}


def histogram(values: np.ndarray, bins: int = 64) -> list:
    counts, _ = np.histogram(values, bins=bins, range=(0, 1))
    return (counts / max(int(counts.sum()), 1)).tolist()


def srgb_to_lab(rgb: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    linear = np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)
    xyz = linear @ np.array([
        [0.4124564, 0.3575761, 0.1804375],
        [0.2126729, 0.7151522, 0.0721750],
        [0.0193339, 0.1191920, 0.9503041],
    ]).T
    relative = xyz / np.array([0.95047, 1.0, 1.08883])
    delta = 6 / 29
    f = np.where(relative > delta**3, np.cbrt(relative), relative / (3 * delta**2) + 4 / 29)
    lab = np.column_stack((116 * f[:, 1] - 16, 500 * (f[:, 0] - f[:, 1]), 200 * (f[:, 1] - f[:, 2])))
    return linear, lab


def load_sdr(path: Path, max_edge: int) -> tuple[np.ndarray, dict]:
    if path.suffix.lower() not in ALLOWED:
        raise ValueError(f"Unsupported input {path.suffix}: export a rendered SDR sRGB JPEG/PNG from the editing app first")
    notes = []
    with Image.open(path) as source:
        if getattr(source, "n_frames", 1) != 1:
            raise ValueError("Multi-frame/animated input: export the intended still frame in the editing app")
        original_mode = source.mode
        if original_mode not in {"RGB", "RGBA", "L", "LA", "P", "CMYK"}:
            raise ValueError(f"Mode {original_mode} is not supported: export an 8-bit SDR sRGB preview in the editing app")
        # Pillow can silently expose 16-bit RGB TIFF/PNG as 8-bit RGB.
        bits = getattr(source, "tag_v2", {}).get(258, (8,))
        bits = (bits,) if isinstance(bits, int) else bits
        if any(b > 8 for b in bits):
            raise ValueError("High-bit-depth TIFF: export an 8-bit SDR sRGB preview for comparable analysis")
        if source.format == "PNG":
            with path.open("rb") as handle:
                header = handle.read(25)
            if len(header) > 24 and header[24] > 8:
                raise ValueError("High-bit-depth PNG: export an 8-bit SDR sRGB preview for comparable analysis")
        metadata_text = str(source.info.get("xmp", "")) + str(source.info.get("XML:com.adobe.xmp", ""))
        if "hdrgm:" in metadata_text or "hdr-gain-map" in metadata_text.lower():
            raise ValueError("HDR gain map detected: export an explicit SDR rendering in the editing app")
        if source.mode == "CMYK" and not source.info.get("icc_profile"):
            raise ValueError("Untagged CMYK has no reliable conversion: export an sRGB preview in the editing app")
        icc = source.info.get("icc_profile")
        if not icc and source.format == "PNG":
            gamma = source.info.get("gamma")
            chromaticity = source.info.get("chromaticity")
            if gamma is not None and abs(float(gamma) - 0.45455) > 0.01:
                raise ValueError("Non-sRGB PNG gamma without ICC: export a tagged sRGB preview in the editing app")
            srgb_chromaticity = (0.3127, 0.3290, 0.64, 0.33, 0.30, 0.60, 0.15, 0.06)
            if chromaticity is not None and not np.allclose(chromaticity, srgb_chromaticity, atol=0.002, rtol=0):
                raise ValueError("Non-sRGB PNG chromaticities without ICC: export a tagged sRGB preview in the editing app")
        img = ImageOps.exif_transpose(source)
        dimensions = list(img.size)
        has_alpha = "A" in img.mode or "transparency" in source.info
        alpha = img.convert("RGBA").getchannel("A") if has_alpha else None
        if icc:
            try:
                profile = ImageCms.ImageCmsProfile(io.BytesIO(icc))
                profile_label = ImageCms.getProfileName(profile).strip()
                color_space = str(profile.profile.xcolor_space).strip()
                if color_space == "CMYK":
                    base = img.convert("CMYK")
                elif color_space == "GRAY":
                    base = img.convert("L")
                else:
                    base = img.convert("RGB")
                img = ImageCms.profileToProfile(base, profile, ImageCms.createProfile("sRGB"), outputMode="RGB", renderingIntent=1)
                profile_status = "embedded ICC converted to sRGB (relative colorimetric)"
            except Exception as error:
                raise ValueError(f"ICC conversion failed; obtain a tagged sRGB export: {error}") from error
        else:
            img = img.convert("RGB")
            profile_label = None
            profile_status = "untagged: sRGB assumed, not verified"
            notes.append("No ICC profile. Gamma/chromaticity tags are not applied; sRGB assumption may bias comparisons.")
        # Deterministic point sampling avoids inventing colors by resampling edges.
        width, height = img.size
        ratio = min(1.0, max_edge / max(width, height))
        sample_size = (max(1, round(width * ratio)), max(1, round(height * ratio)))
        img = img.resize(sample_size, Image.Resampling.NEAREST)
        pixels = np.asarray(img, dtype=np.float64).reshape(-1, 3) / 255.0
        opaque_fraction = 1.0
        if alpha is not None:
            keep = np.asarray(alpha.resize(sample_size, Image.Resampling.NEAREST)).reshape(-1) == 255
            opaque_fraction = float(keep.mean())
            pixels = pixels[keep]
            if not len(pixels):
                raise ValueError("No fully opaque sampled pixels; supply a flattened SDR photo")
            notes.append("All partially/fully transparent sampled pixels excluded; no background was composited.")
        notes.append("Analysis is for the decoded SDR rendering; HDR detection is incomplete. Never infer scene radiance or RAW clipping.")
        return pixels, {
            "oriented_size": dimensions, "source_mode": original_mode,
            "sample_grid_size": list(sample_size), "sample_count": len(pixels),
            "opaque_sample_fraction": opaque_fraction, "embedded_profile_name": profile_label,
            "color_management": profile_status, "warnings": notes,
        }


def analyze(path: Path, max_edge: int = 1400) -> dict:
    digest = sha256(path)
    rgb, info = load_sdr(path, max_edge)
    linear, lab = srgb_to_lab(rgb)
    luma = rgb @ WEIGHTS
    luminance = linear @ WEIGHTS
    maximum, minimum = rgb.max(axis=1), rgb.min(axis=1)
    chroma_rgb = maximum - minimum
    saturation = np.divide(chroma_rgb, maximum, out=np.zeros_like(maximum), where=maximum > 0)
    hue = np.zeros_like(maximum)
    colored = chroma_rgb > 1e-8
    for channel in range(3):
        selected = colored & (np.argmax(rgb, axis=1) == channel)
        first, second = [(1, 2), (2, 0), (0, 1)][channel]
        hue[selected] = ((rgb[selected, first] - rgb[selected, second]) / chroma_rgb[selected] + 2 * channel) * 60
    hue %= 360
    eligible = (saturation >= 0.15) & (maximum >= 0.08) & (maximum <= 0.98)
    hue_counts, _ = np.histogram(hue[eligible], bins=12, range=(0, 360))
    lab_chroma = np.hypot(lab[:, 1], lab[:, 2])
    tonal_zones = {}
    for name, mask in {
        "shadows": luma < 0.25,
        "midtones": (luma >= 0.25) & (luma <= 0.75),
        "highlights": luma > 0.75,
    }.items():
        count = int(mask.sum())
        low_chroma = mask & (lab_chroma <= 12)
        low_count = int(low_chroma.sum())
        tonal_zones[name] = {
            "fraction": float(mask.mean()), "sample_count": count,
            "median_lab": np.median(lab[mask], axis=0).tolist() if count else None,
            "low_chroma_count": low_count,
            "low_chroma_median_ab": np.median(lab[low_chroma, 1:], axis=0).tolist() if low_count >= 32 else None,
        }
    q = quantiles(luma)
    return {
        "path": str(path), "sha256": digest, **info,
        "encoded_luma": {"quantiles": q, "p95_minus_p05": q["p95"] - q["p05"], "histogram_64": histogram(luma)},
        "linear_luminance_quantiles": quantiles(luminance),
        "rgb_histograms_64": {name: histogram(rgb[:, i]) for i, name in enumerate("rgb")},
        "rendered_endpoint_fraction": {
            "all_channels_le_1_of_255": float((maximum <= 1 / 255).mean()),
            "all_channels_ge_254_of_255": float((minimum >= 254 / 255).mean()),
            "any_channel_le_1_of_255": float((minimum <= 1 / 255).mean()),
            "any_channel_ge_254_of_255": float((maximum >= 254 / 255).mean()),
        },
        "hsv_saturation_quantiles": quantiles(saturation),
        "lab_chroma_quantiles": quantiles(lab_chroma),
        "hue": {
            "eligible_fraction": float(eligible.mean()), "eligible_count": int(eligible.sum()),
            "bin_edges_degrees": list(range(0, 361, 30)),
            "fractions": (hue_counts / hue_counts.sum()).tolist() if hue_counts.sum() else None,
        },
        "tonal_zones": tonal_zones,
    }


def summarize(values: list[float]) -> dict:
    array = np.asarray(values, dtype=float)
    median = float(np.median(array))
    return {"n": len(values), "median": median, "mad": float(np.median(np.abs(array - median))), "min": float(array.min()), "max": float(array.max())}


def summarize_references(references: list[dict]) -> dict:
    metrics = {}
    for p in PERCENTILES:
        metrics[f"encoded_luma_p{p:02}"] = summarize([r["encoded_luma"]["quantiles"][f"p{p:02}"] for r in references])
    metrics["encoded_luma_p95_minus_p05"] = summarize([r["encoded_luma"]["p95_minus_p05"] for r in references])
    metrics["hsv_saturation_p50"] = summarize([r["hsv_saturation_quantiles"]["p50"] for r in references])
    metrics["lab_chroma_p50"] = summarize([r["lab_chroma_quantiles"]["p50"] for r in references])
    for zone in ("shadows", "midtones", "highlights"):
        metrics[f"{zone}_fraction"] = summarize([r["tonal_zones"][zone]["fraction"] for r in references])
        ab = [r["tonal_zones"][zone]["low_chroma_median_ab"] for r in references]
        ab = [value for value in ab if value is not None]
        for index, axis in enumerate(("a", "b")):
            metrics[f"{zone}_low_chroma_{axis}"] = summarize([value[index] for value in ab]) if ab else None
    return {
        "unique_reference_count": len(references), "equal_image_weight_metrics": metrics,
        "interpretation": "Descriptive evidence, not a style classifier, target to minimize, confidence probability, or Lightroom settings. Median/MAD summarize equally weighted unique images; visually separate conflicting styles and scene content before deciding common traits.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--references", nargs="+", required=True, type=Path)
    parser.add_argument("--targets", nargs="*", default=[], type=Path)
    parser.add_argument("--output", required=True, type=Path, help="A NEW JSON file; never overwritten")
    parser.add_argument("--max-edge", type=int, default=1400)
    args = parser.parse_args(argv)
    if not 64 <= args.max_edge <= 2400:
        parser.error("--max-edge must be between 64 and 2400")
    output = args.output.expanduser().resolve()
    if output.suffix.lower() != ".json":
        parser.error("--output must end in .json")
    if output.exists():
        parser.error("Output exists; choose a new filename")
    refs = [path.expanduser().resolve(strict=True) for path in args.references]
    targets = [path.expanduser().resolve(strict=True) for path in args.targets]
    if output in refs + targets:
        parser.error("Output must not be an input")
    results, duplicates, seen = [], [], set()
    for path in refs:
        result = analyze(path, args.max_edge)
        if result["sha256"] in seen:
            duplicates.append(str(path))
        else:
            results.append(result)
            seen.add(result["sha256"])
    report = {
        "schema_version": 1,
        "method": {
            "purpose": "Read-only statistical evidence for visually guided editing in a real photo application",
            "input": "8-bit SDR rendered photos; ICC to sRGB where available; EXIF orientation applied",
            "sampling": "Deterministic nearest-neighbor grid with capped long edge; opaque pixels only; NumPy linear-interpolation percentiles",
            "encoded_luma": "0.2126 R' + 0.7152 G' + 0.0722 B' (gamma-encoded sRGB proxy, 0..1, not Lightroom histogram)",
            "linear_luminance": "sRGB inverse transfer followed by Rec.709 luminance weights, 0..1",
            "lab": "CIELAB using sRGB -> XYZ, D65 white; a+ red, b+ yellow; not D50 ICC PCS",
            "zones": "Encoded luma <0.25 shadows, 0.25..0.75 midtones, >0.75 highlights; fixed ranges, not subject masks",
            "low_chroma": "Lab C* <=12 and >=32 pixels; candidate low-chroma pixels, not recognized neutral objects",
            "hue": "HSV 12 circular 30-degree bins, only S>=0.15 and V in [0.08,0.98]; no arithmetic mean hue",
            "endpoint_counts": "Rendered channel endpoints at <=1/255 or >=254/255, not proof of capture clipping",
        },
        "references": results, "duplicate_references_ignored": duplicates,
        "reference_summary": summarize_references(results),
        "targets": [analyze(path, args.max_edge) for path in targets],
    }
    serialized = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as handle:
        handle.write(serialized + "\n")
    print(f"Wrote analysis of {len(results)} unique references and {len(targets)} targets: {output}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning) as error:
        print(f"Analysis failed: {error}", file=sys.stderr)
        raise SystemExit(2)
