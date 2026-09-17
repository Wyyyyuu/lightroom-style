"""Read-only luminance evidence for visually chosen soft/protected regions."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
from analyze_images import load_sdr, sha256, WEIGHTS


def analyze_regions(path: Path, regions: list[dict], max_edge: int = 1200) -> dict:
    if not isinstance(max_edge, int) or isinstance(max_edge, bool) or not 64 <= max_edge <= 4096:
        raise ValueError("max_edge must be an integer from 64 to 4096")
    if not isinstance(regions, list) or not 1 <= len(regions) <= 16:
        raise ValueError("Supply 1-16 visually selected regions")
    names = set()
    for region in regions:
        if not isinstance(region, dict) or set(region) != {"name", "role", "box"}:
            raise ValueError("Each region needs name, role, and box")
        name, box = region["name"], region["box"]
        if not isinstance(name, str) or not name.strip() or name in names:
            raise ValueError("Region names must be nonempty and unique")
        names.add(name)
        if region["role"] not in {"soft", "protect"}:
            raise ValueError("Region role must be soft or protect")
        if (not isinstance(box, list) or len(box) != 4
            or any(isinstance(v, bool) or not isinstance(v, (int, float))
                   or not math.isfinite(v) or not 0 <= v <= 1 for v in box)
            or not box[0] < box[2] or not box[1] < box[3]):
            raise ValueError("Box must be normalized left, top, right, bottom")
    if not any(r["role"] == "soft" for r in regions):
        raise ValueError("At least one visually selected soft region is required")
    rgb, info = load_sdr(path, max_edge)
    width, height = info["sample_grid_size"]
    if len(rgb) != width * height:
        raise ValueError("Transparent regions cannot be located reliably; supply a flattened native preview")
    luma = (rgb @ WEIGHTS * 100).reshape(height, width)
    reports = []
    for region in regions:
        left, top, right, bottom = region["box"]
        crop = luma[math.floor(top * height):math.ceil(bottom * height),
                    math.floor(left * width):math.ceil(right * width)]
        if crop.size < 16:
            raise ValueError("Region too small to measure; enlarge it or increase max_edge")
        p10, median, p90 = np.percentile(crop, [10, 50, 90])
        reports.append({**region, "samples": int(crop.size),
                        "encoded_luma_0_100": dict(p10=round(float(p10), 2),
                                                   median=round(float(median), 2),
                                                   p90=round(float(p90), 2))})
    overlaps = []
    for soft in reports:
        if soft["role"] != "soft":
            continue
        bounds = soft["encoded_luma_0_100"]
        for protected in regions:
            if protected["role"] != "protect":
                continue
            l, t, r, b = protected["box"]
            values = luma[math.floor(t * height):math.ceil(b * height),
                          math.floor(l * width):math.ceil(r * width)]
            overlaps.append({"soft": soft["name"], "protect": protected["name"],
                             "protected_fraction_in_soft_p10_p90": round(float(
                                 ((values >= bounds["p10"]) & (values <= bounds["p90"])).mean()), 3)})
    return {"path": str(path.resolve()), "sha256": sha256(path), "regions": reports,
            "brightness_overlap": overlaps, "color_management": info["color_management"],
            "interpretation": "Encoded SDR luma is a sampling aid, not Lightroom range-slider units. "
            "This does not detect blur or generate a mask. Sample and verify native range/feather; "
            "overlapping protected detail may need spatial intersection or subtraction."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("--regions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-edge", type=int, default=1200)
    args = parser.parse_args()
    result = analyze_regions(args.image, json.loads(args.regions.read_text(encoding="utf-8")), args.max_edge)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(args.output.resolve()), "regions": result["regions"],
                      "brightness_overlap": result["brightness_overlap"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
