"""wall3.primary_metrics_20261111 점검: 기존 compare json(compare_ladder.py 결과)과 같은 값을 내는가. 결과 파일만 읽는다."""
import json
import unittest
from pathlib import Path

from wall3 import primary_metrics_20261111 as pm
from wall3.poster_ksarc_20261111d import wall_rects

W = pm.W


class TestPrimaryMetrics(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (W / "eval_lf_20261110_compare.json").exists():
            raise unittest.SkipTest("결과 파일 없음")
        cls.res = pm.compute()
        cls.rows = {r["key"]: r for r in cls.res["rows"]}

    def test_matches_compare_json(self):
        for f in ("eval_lf_20261110_compare.json", "eval_lf_g1fix_20261111_compare.json"):
            c = json.loads((W / f).read_bytes())
            for k, v in c["conditions"].items():
                if k not in self.rows:
                    continue
                r = self.rows[k]
                self.assertAlmostEqual(r["filled_mean"], v["filled_mean"], places=2, msg=k)
                self.assertEqual(r["complete"], v["complete"], k)
                self.assertEqual(r["spec_pass"], v["spec_pass"], k)
                if "vs_base" in v and "vs_full" in r:
                    self.assertAlmostEqual(round(r["vs_full"]["filled"], 2), v["vs_base"]["diff_mean"], places=2, msg=k)
                    self.assertEqual([round(x, 2) for x in r["vs_full"]["filled_ci"]], v["vs_base"]["ci95"], k)

    def test_full_complete_walls_pass(self):
        full = self.rows["eval_lf_full_20261110/act_all_held+k2+k7"]
        self.assertEqual(full["complete"], 60)
        for k in ("2", "3", "4"):
            self.assertEqual(full["items"][k]["over_limit"], 0)

    def test_wall_rects(self):
        r = wall_rects()
        self.assertEqual(len(r), 16)
        self.assertEqual(sum(1 for x in r if x[2] == 90.0), 2)
        self.assertAlmostEqual(min(x[0] for x in r), -495.0)
        self.assertAlmostEqual(max(x[0] + x[2] for x in r), 495.0)


if __name__ == "__main__":
    unittest.main()
