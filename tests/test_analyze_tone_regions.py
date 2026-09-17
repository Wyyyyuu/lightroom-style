import sys
import tempfile
import unittest
from pathlib import Path
import numpy as np
from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"lightroom-style/scripts"))
from analyze_tone_regions import analyze_tones


class ToneRegionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.spec = {"regions": [{"name":"dark", "box":[.25,0,.5,1]},
                                 {"name":"light", "box":[.5,0,.75,1]}],
                     "pairs":[{"name":"subject separation", "dark":"dark", "light":"light"}]}

    def picture(self, name, values):
        p = self.root/name
        pixels = np.zeros((64,128,3), dtype=np.uint8)
        for i,v in enumerate(values): pixels[:,i*32:(i+1)*32]=v
        Image.fromarray(pixels).save(p)
        return p

    def test_black_and_white_edges_cannot_hide_flattened_subject(self):
        original = self.picture("before.png", [0,45,215,255])
        flattened = self.picture("after.png", [0,105,155,255])
        data = original.read_bytes()
        before = analyze_tones(original,self.spec)
        after = analyze_tones(flattened,self.spec)
        self.assertAlmostEqual(before["pairs"][0]["light_minus_dark_median"],170)
        self.assertAlmostEqual(after["pairs"][0]["light_minus_dark_median"],50)
        self.assertEqual(original.read_bytes(),data)

    def test_reversed_visual_roles_report_negative_gap(self):
        p = self.picture("reverse.png",[0,200,50,255])
        r = analyze_tones(p,self.spec)
        self.assertAlmostEqual(r["pairs"][0]["light_minus_dark_median"],-150)

    def test_invalid_boxes_names_and_pairs_fail(self):
        p = self.picture("valid.png",[0,45,215,255])
        import copy
        cases=[]
        for box in ([0,0,2,1],[.5,0,.4,1],[False,0,1,1],[0,0,float("nan"),1]):
            s=copy.deepcopy(self.spec);s["regions"][0]["box"]=box;cases.append(s)
        s=copy.deepcopy(self.spec);s["pairs"][0]["dark"]="missing";cases.append(s)
        s=copy.deepcopy(self.spec);s["regions"][1]["name"]="dark";cases.append(s)
        for s in cases:
            with self.assertRaises(ValueError):analyze_tones(p,s)

    def test_transparency_and_tiny_boxes_rejected(self):
        p=self.root/"alpha.png";pixels=np.full((64,64,4),255,dtype=np.uint8);pixels[0,0,3]=0
        Image.fromarray(pixels).save(p)
        with self.assertRaisesRegex(ValueError,"Transparent"):analyze_tones(p,self.spec)
        p=self.picture("opaque.png",[0,45,215,255])
        spec={"regions":[{"name":"tiny","box":[0,0,.001,.001]}],"pairs":[]}
        with self.assertRaisesRegex(ValueError,"too small"):analyze_tones(p,spec)
