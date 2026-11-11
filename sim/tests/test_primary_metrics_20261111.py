"""wall3.primary_metrics_20261111 점검: 기존 compare json(compare_ladder.py 결과)과 같은 값을 내는가. 결과 파일만 읽는다."""
import json
import unittest
from pathlib import Path

from wall3 import primary_metrics_20261111 as pm
from wall3.poster_ksarc_20261111d import wall_rects
from wall3.poster_ksarc_20261111e import fmt_ci, fmt_n, slot_columns, verdict
from wall3 import pptx_text_check_20261111 as tc

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


class TestPosterEHelpers(unittest.TestCase):
    """포스터 e판의 표 1 · 그림 5 도우미 (결과 파일 없이 돈다)."""

    def test_fmt(self):
        self.assertEqual(fmt_n(0.2), "0")
        self.assertEqual(fmt_n(-0.4), "0")
        self.assertEqual(fmt_n(7), "+7")
        self.assertEqual(fmt_n(-37), "−37")
        self.assertEqual(fmt_ci((-48, -26)), "−48 ~ −26")
        self.assertEqual(fmt_ci((-7, 7)), "−7 ~ +7")

    def test_verdict(self):
        self.assertEqual(verdict((-48, -26)), "몫 있음")
        self.assertEqual(verdict((-7, 7)), "구별 못 함")
        self.assertEqual(verdict((-19, 4)), "구별 못 함")
        self.assertEqual(verdict((-5, 0)), "구별 못 함")       # 0을 포함하면 구별 못 함
        self.assertEqual(verdict((1, 9)), "Full보다 많음")

    def test_slot_columns(self):
        c = slot_columns()
        self.assertEqual(len(c), 16)
        ws = [w for _, w in c]
        self.assertEqual([k for k, w in enumerate(ws) if w < max(ws)], [5, 10])    # 반장 = 자리 6 · 11 (0부터 세면 5 · 10)
        for (x0, w0), (x1, _) in zip(c, c[1:]):
            self.assertGreater(x1, x0 + w0)                                         # 칸이 겹치지 않는다
        gaps = [round(x1 - (x0 + w0), 6) for (x0, w0), (x1, _) in zip(c, c[1:])]
        self.assertEqual([k + 1 for k, g in enumerate(gaps) if g > min(gaps)], [5, 11])   # 단 사이(5 | 6, 11 | 12)만 넓다


class TestPptxTextCheck(unittest.TestCase):
    """양식만 다듬은 판이 글 · 숫자를 바꾸지 않았는지 보는 도구."""

    def test_diff(self):
        base = [tc.norm("완성 60벽 · 시방 합격 60벽"), tc.norm("차이 –37 [–48, –26]"), "같은문단", "같은문단"]
        self.assertEqual(tc.diff(base, list(reversed(base))), ([], [], {}, {}))                 # 순서는 보지 않는다
        gone, new, ngone, nnew = tc.diff(base, [base[0], tc.norm("차이 –37 [–48, –25]"), "같은문단"])
        self.assertEqual(gone, [base[1], "같은문단"])                                            # 횟수까지 센다
        self.assertEqual(new, ["차이–37[–48,–25]"])
        self.assertEqual((dict(ngone), dict(nnew)), ({"–26": 1}, {"–25": 1}))
        split = [base[0], "차이–37", "[–48,–26]", "같은문단", "같은문단"]                         # 문단을 나눠도 숫자 묶음은 같다
        g, n, ng, nn = tc.diff(base, split)
        self.assertTrue(g and n)
        self.assertEqual((dict(ng), dict(nn)), ({}, {}))

    def test_poster_e_reads(self):
        pptx = pm.SIM.parent / "02_KSARC2026" / "KSARC2026_포스터_초안_20261111e.pptx"
        if not pptx.exists():
            self.skipTest("포스터 e판 없음")
        paras = tc.paragraphs(pptx)
        self.assertEqual(tc.diff(paras, paras), ([], [], {}, {}))
        self.assertIn(tc.norm("3.3  결과"), paras)
        self.assertTrue(any("RS-2024-00457308" in p for p in paras))                            # 감사의 글 (표도 읽는다: 아래)
        self.assertTrue(any(p == tc.norm("참값 (진단)") for p in paras))


if __name__ == "__main__":
    unittest.main()
