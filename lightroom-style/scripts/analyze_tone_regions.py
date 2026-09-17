"""Read-only regional tone evidence; boxes are chosen visually, never auto-segmented."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import numpy as np
from analyze_images import load_sdr, sha256, srgb_to_lab, WEIGHTS


def validate_spec(spec: dict) -> None:
    if not isinstance(spec, dict) or set(spec) != {"regions", "pairs"}:
        raise ValueError("Specification needs regions and pairs")
    regions, pairs = spec["regions"], spec["pairs"]
    if not isinstance(regions, list) or not 1 <= len(regions) <= 16:
        raise ValueError("Supply 1-16 visually selected regions")
    names = set()
    for r in regions:
        if not isinstance(r, dict) or set(r) != {"name", "box"}:
            raise ValueError("Each region needs name and box")
        name, box = r["name"], r["box"]
        if not isinstance(name, str) or not name.strip() or name in names:
            raise ValueError("Region names must be nonempty and unique")
        names.add(name)
        if (not isinstance(box, list) or len(box) != 4
            or any(isinstance(v, bool) or not isinstance(v, (int, float))
                   or not math.isfinite(v) or not 0 <= v <= 1 for v in box)
            or not box[0] < box[2] or not box[1] < box[3]):
            raise ValueError("Box must be normalized left, top, right, bottom")
    if not isinstance(pairs, list) or len(pairs) > 16:
        raise ValueError("Supply at most 16 dark/light pairs")
    pair_names = set()
    for pair in pairs:
        if not isinstance(pair, dict) or set(pair) != {"name", "dark", "light"}:
            raise ValueError("Each pair needs name, dark and light")
        if not isinstance(pair["name"], str) or not pair["name"].strip() or pair["name"] in pair_names:
            raise ValueError("Pair names must be nonempty and unique")
        pair_names.add(pair["name"])
        if (not isinstance(pair["dark"], str) or not isinstance(pair["light"], str)
            or pair["dark"] not in names or pair["light"] not in names or pair["dark"] == pair["light"]):
            raise ValueError("Pair must reference two distinct existing regions")


def analyze_tones(path: Path, spec: dict, max_edge: int = 1400) -> dict:
    validate_spec(spec)
    if isinstance(max_edge, bool) or not isinstance(max_edge, int) or not 64 <= max_edge <= 4096:
        raise ValueError("max_edge must be an integer from 64 to 4096")
    rgb, info = load_sdr(path, max_edge)
    width, height = info["sample_grid_size"]
    if len(rgb) != width * height:
        raise ValueError("Transparent images need a flattened native preview for spatial analysis")
    pixels = rgb.reshape(height, width, 3)
    regions = []
    for r in spec["regions"]:
        left, top, right, bottom = r["box"]
        crop = pixels[math.floor(top*height):math.ceil(bottom*height),
                      math.floor(left*width):math.ceil(right*width)].reshape(-1, 3)
        if len(crop) < 16:
            raise ValueError("Region too small; enlarge box or increase max_edge")
        luma = crop @ WEIGHTS * 255
        q = np.percentile(luma, [5, 25, 50, 75, 95])
        _, lab = srgb_to_lab(crop)
        maximum, minimum = crop.max(axis=1), crop.min(axis=1)
        saturation = np.divide(maximum-minimum, maximum, out=np.zeros_like(maximum), where=maximum>0)
        regions.append({**r, "samples": len(crop),
            "encoded_luma_0_255": dict(zip(["p05", "p25", "p50", "p75", "p95"], map(float, q))),
            "regional_spread_p95_p05": float(q[4]-q[0]),
            "median_lab": np.median(lab, axis=0).tolist(),
            "median_hsv_saturation": float(np.median(saturation))})
    medians = {r["name"]: r["encoded_luma_0_255"]["p50"] for r in regions}
    pairs = [{**p, "light_minus_dark_median": medians[p["light"]]-medians[p["dark"]]} for p in spec["pairs"]]
    return {"path": str(path.resolve()), "sha256": sha256(path), **info, "regions": regions,
        "pairs": pairs, "interpretation": "Encoded sRGB luma evidence in 0..255, not exposure stops, "
        "a style score, microcontrast, or Lightroom slider values. Boxes and semantic roles are manual. "
        "Regional spread ignores spatial arrangement and can include grain, objects and edges. "
        "Compare the same target boxes before/after, and comparable materials in references; inspect images."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--images", nargs="+", type=Path, required=True)
    parser.add_argument("--regions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-edge", type=int, default=1400)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Output exists; choose a new filename")
    spec = json.loads(args.regions.read_text(encoding="utf-8"))
    results = [analyze_tones(p, spec, args.max_edge) for p in args.images]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as f:
        json.dump({"images": results}, f, ensure_ascii=False, indent=2)
    print(json.dumps({"report": str(args.output.resolve()), "images": [
        {"path": r["path"], "regions": [{"name": z["name"], **z["encoded_luma_0_255"]} for z in r["regions"]],
         "pairs": r["pairs"]} for r in results]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
