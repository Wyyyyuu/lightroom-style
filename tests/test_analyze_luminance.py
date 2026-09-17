import hashlib
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lightroom-style/scripts"))
from analyze_luminance import analyze_regions


class LuminanceAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "zones.png"
        pixels = np.zeros((64, 96, 3), dtype=np.uint8)
        pixels[:, :32] = 51
        pixels[:, 32:64] = 204
        pixels[:, 64:] = 51
        Image.fromarray(pixels).save(self.path)
        self.regions = [
            dict(name="haze", role="soft", box=[0, 0, 1/3, 1]),
            dict(name="bright face", role="protect", box=[1/3, 0, 2/3, 1]),
            dict(name="dark detail", role="protect", box=[2/3, 0, 1, 1]),
        ]

    def test_regions_distinguish_brightness_and_report_protected_overlap(self):
        before = self.path.read_bytes()
        result = analyze_regions(self.path, self.regions)
        self.assertAlmostEqual(result["regions"][0]["encoded_luma_0_100"]["median"], 20)
        self.assertAlmostEqual(result["regions"][1]["encoded_luma_0_100"]["median"], 80)
        self.assertEqual([r["protected_fraction_in_soft_p10_p90"] for r in result["brightness_overlap"]], [0, 1])
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(result["sha256"], hashlib.sha256(before).hexdigest())

    def test_invalid_regions_rejected_before_analysis(self):
        for box in ([0, 0, 2, 1], [1, 0, 0, 1], [0, 0, float("nan"), 1], [False, 0, 1, 1]):
            with self.subTest(box=box), self.assertRaises(ValueError):
                analyze_regions(self.path, [dict(name="x", role="soft", box=box)])
        with self.assertRaises(ValueError):
            analyze_regions(self.path, self.regions[1:])
        with self.assertRaises(ValueError):
            analyze_regions(self.path, [self.regions[0]] * 2)

    def test_tiny_region_and_transparency_rejected(self):
        with self.assertRaisesRegex(ValueError, "too small"):
            analyze_regions(self.path, [dict(name="x", role="soft", box=[0, 0, .001, .001])])
        rgba = np.full((64, 64, 4), 255, dtype=np.uint8)
        rgba[0, 0, 3] = 0
        Image.fromarray(rgba).save(self.path)
        with self.assertRaisesRegex(ValueError, "Transparent"):
            analyze_regions(self.path, [dict(name="x", role="soft", box=[0, 0, 1, 1])])
