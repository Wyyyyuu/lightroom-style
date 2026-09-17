"""Numerical and file-safety checks; fixtures are synthetic, not user photo edits."""
import importlib.util
import json
import struct
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image, ImageCms, PngImagePlugin


SCRIPT = Path(__file__).resolve().parents[1] / "lightroom-style" / "scripts" / "analyze_images.py"
SPEC = importlib.util.spec_from_file_location("analysis", SCRIPT)
analysis = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(analysis)


class AnalysisTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name).resolve()

    def tearDown(self):
        self.directory.cleanup()

    def save(self, name, array, **kwargs):
        path = self.root / name
        Image.fromarray(np.asarray(array, dtype=np.uint8)).save(path, **kwargs)
        return path

    def test_black_white_gray_and_finite_histograms(self):
        for level, expected in [(0, 0.0), (128, 128 / 255), (255, 1.0)]:
            path = self.save(f"gray-{level}.png", np.full((12, 12, 3), level))
            result = analysis.analyze(path)
            self.assertAlmostEqual(result["encoded_luma"]["quantiles"]["p50"], expected)
            self.assertEqual(result["hsv_saturation_quantiles"]["p50"], 0)
            self.assertIsNone(result["hue"]["fractions"])
            for hist in [result["encoded_luma"]["histogram_64"], *result["rgb_histograms_64"].values()]:
                self.assertAlmostEqual(sum(hist), 1)
            json.dumps(result, allow_nan=False)

    def test_known_linear_luminance_and_lab(self):
        rgb = np.array([[0, 0, 0], [1, 1, 1], [128 / 255] * 3, [1, 0, 0]])
        linear, lab = analysis.srgb_to_lab(rgb)
        np.testing.assert_allclose(linear[2], 0.2158605001, atol=1e-9)
        np.testing.assert_allclose(lab[0], [0, 0, 0], atol=1e-5)
        np.testing.assert_allclose(lab[1], [100, 0, 0], atol=3e-5)
        np.testing.assert_allclose(lab[3], [53.2408, 80.0925, 67.2032], atol=0.0001)

    def test_hue_wrap_and_primary_bins(self):
        pixels = np.array([[[255, 0, 1], [255, 1, 0], [0, 200, 0], [0, 0, 200]]])
        # Hue excludes V > .98; bring red below that threshold.
        pixels[0, :2, 0] = 200
        result = analysis.analyze(self.save("colors.png", pixels))
        distribution = result["hue"]["fractions"]
        self.assertEqual(result["hue"]["eligible_count"], 4)
        self.assertEqual([distribution[i] for i in (0, 4, 8, 11)], [0.25] * 4)
        self.assertAlmostEqual(sum(distribution), 1)

    def test_alpha_exclusion_and_empty_rejection(self):
        rgba = np.array([[[70, 110, 150, 255], [255, 0, 0, 0], [0, 255, 0, 127]]])
        target = analysis.analyze(self.save("alpha.png", rgba))
        baseline = analysis.analyze(self.save("opaque.png", rgba[:, :1, :3]))
        self.assertEqual(target["encoded_luma"], baseline["encoded_luma"])
        self.assertEqual(target["rgb_histograms_64"], baseline["rgb_histograms_64"])
        rgba[:, :, 3] = 0
        with self.assertRaisesRegex(ValueError, "No fully opaque"):
            analysis.analyze(self.save("empty.png", rgba))

    def test_tone_conditioned_hues_include_bright_colors(self):
        pixels = np.array([[[0, 0, 100], [0, 150, 0], [255, 240, 160]]])
        result = analysis.analyze(self.save("tone-colors.png", pixels))
        for zone, hue in [("shadows", "blue"), ("midtones", "green"), ("highlights", "yellow")]:
            measured = result["tonal_zones"][zone]
            self.assertEqual(measured["sample_count"], 1)
            self.assertEqual(measured["hue_fractions_of_zone"][hue], 1)
            self.assertEqual(measured["largest_chromatic_bins"][0]["hue"], hue)

    def test_neutral_base_keeps_small_color_accent_small(self):
        pixels = np.array([[[128, 128, 128]] * 9 + [[0, 128, 255]]])
        measured = analysis.analyze(self.save("neutral-base.png", pixels))["tonal_zones"]["midtones"]
        self.assertAlmostEqual(measured["low_chroma_fraction_of_zone"], 0.9)
        self.assertEqual(measured["chromatic_sample_count"], 1)
        self.assertAlmostEqual(measured["largest_chromatic_bins"][0]["fraction_of_zone"], 0.1)
        self.assertAlmostEqual(sum(measured["hue_fractions_of_zone"].values()) + measured["low_chroma_fraction_of_zone"], 1)

    def test_tonal_red_wrap_and_empty_zone_are_unambiguous(self):
        pixels = np.array([[[200, 0, 1], [200, 1, 0]]])
        zones = analysis.analyze(self.save("red-wrap.png", pixels))["tonal_zones"]
        self.assertEqual(zones["shadows"]["hue_fractions_of_zone"]["red"], 1)
        self.assertIsNone(zones["highlights"]["hue_fractions_of_zone"])
        self.assertIsNone(zones["highlights"]["low_chroma_fraction_of_zone"])
        self.assertEqual(zones["highlights"]["largest_chromatic_bins"], [])

    def test_opposing_hues_stay_separate_in_same_tone_zone(self):
        pixels = np.array([[[150, 30, 30], [0, 70, 70]]])
        measured = analysis.analyze(self.save("mixed-shadow.png", pixels))["tonal_zones"]["shadows"]
        self.assertEqual(measured["sample_count"], 2)
        self.assertEqual(measured["hue_fractions_of_zone"]["red"], 0.5)
        self.assertEqual(measured["hue_fractions_of_zone"]["cyan"], 0.5)

    def test_icc_conversion_and_invalid_profile(self):
        rgb = np.array([[[64, 128, 192], [90, 50, 170]]])
        profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
        tagged = analysis.analyze(self.save("tagged.png", rgb, icc_profile=profile))
        untagged = analysis.analyze(self.save("untagged.png", rgb))
        self.assertEqual(tagged["encoded_luma"], untagged["encoded_luma"])
        self.assertIn("embedded ICC converted", tagged["color_management"])
        with self.assertRaisesRegex(ValueError, "ICC conversion failed"):
            analysis.analyze(self.save("broken.png", rgb, icc_profile=b"not-an-icc"))

    def test_rotation_equal_image_weight_and_deduplication(self):
        pattern = np.arange(12 * 16 * 3, dtype=np.uint8).reshape(12, 16, 3)
        first = analysis.analyze(self.save("pattern.png", pattern))
        rotated = analysis.analyze(self.save("rotated.png", np.rot90(pattern)))
        self.assertEqual(first["encoded_luma"], rotated["encoded_luma"])
        black = self.save("small.png", np.zeros((4, 4, 3)))
        white = self.save("large.png", np.full((200, 200, 3), 255))
        output = self.root / "report.json"
        analysis.main(["--references", str(black), str(white), str(black), "--output", str(output)])
        report = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(len(report["references"]), 2)
        self.assertEqual(report["reference_summary"]["equal_image_weight_metrics"]["encoded_luma_p50"]["median"], 0.5)
        self.assertEqual(report["duplicate_references_ignored"], [str(black)])

    def test_repeatability_readonly_and_output_protection(self):
        path = self.save("源图.png", np.full((16, 16, 3), [64, 128, 192]))
        before = (path.read_bytes(), path.stat().st_mtime_ns)
        first, second = self.root / "first.json", self.root / "second.json"
        for output in [first, second]:
            analysis.main(["--references", str(path), "--targets", str(path), "--output", str(output)])
        self.assertEqual(first.read_bytes(), second.read_bytes())
        self.assertEqual((path.read_bytes(), path.stat().st_mtime_ns), before)
        old_output = first.read_bytes()
        with self.assertRaises(SystemExit):
            analysis.main(["--references", str(path), "--output", str(first)])
        self.assertEqual(first.read_bytes(), old_output)

    def test_unsupported_inputs_do_not_produce_reports(self):
        raw = self.root / "camera.cr3"
        raw.write_bytes(b"not-a-supported-render")
        with self.assertRaisesRegex(ValueError, "Unsupported input"):
            analysis.analyze(raw)
        high = self.root / "high.png"
        Image.fromarray(np.array([[0, 65535]], dtype=np.uint16)).save(high)
        with self.assertRaises(ValueError):
            analysis.analyze(high)
        hdr = PngImagePlugin.PngInfo()
        hdr.add_text("XML:com.adobe.xmp", "hdrgm:Version")
        with self.assertRaisesRegex(ValueError, "HDR gain map"):
            analysis.analyze(self.save("hdr.png", np.ones((8, 8, 3)), pnginfo=hdr))

    def test_explicit_non_srgb_gamma_requires_managed_export(self):
        metadata = PngImagePlugin.PngInfo()
        metadata.add(b"gAMA", struct.pack(">I", 100000))
        path = self.save("linear-gamma.png", np.full((8, 8, 3), 128), pnginfo=metadata)
        with self.assertRaisesRegex(ValueError, "Non-sRGB PNG gamma"):
            analysis.analyze(path)


if __name__ == "__main__":
    unittest.main()
