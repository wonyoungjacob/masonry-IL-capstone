"""측정기(prl.perception) 시험: 잡음 없는 깊이로 설계 위치에 놓인 벽돌과 흩어진 공급 벽돌을 0.5 mm 안으로 재는지, 가려지면 못 잰 것으로 내는지.

실행: cd sim && PYTHONPATH=. MUJOCO_GL=egl venv/bin/python -m unittest discover -s tests -p "test_prl_*.py"
"""
import unittest

import numpy as np

from wall3.config import H, RETRACT_Q
from wall3.poses import yaw_of_quat
from prl import config as C
from prl.env import DryEnv, noisy_depth
from prl.perception import Camera, PolyIntegrator, _coverage_exact, measure, slab_corners


class TestPerception(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.env = DryEnv(fixed_cams=C.final_cams())
        cls.q = np.array(RETRACT_Q)

    @classmethod
    def tearDownClass(cls):
        cls.env.close()

    def cam(self, name):
        env = self.env
        p, R = env.cam_pose(name)
        fovy = env.cam_fovy[name]
        return Camera(fovy, R, p, C.RAW_W, C.RAW_H, sigma_fn=lambda z: C.depth_sigma(z, fovy, "d435"))

    def test_integrator_equals_sampled_coverage(self):
        env = self.env
        env.reset_piece(800210, 0, arm_q=self.q)
        cm = self.cam("WC1")
        rng = np.random.default_rng(0)
        g = rng.standard_normal((90, 160))
        cor = slab_corners(0.01, 0.602, 0.03, 0.19, 0.057, 0.013)
        u, v, _ = cm.project(cor)
        x0, y0 = int(u.min()) - 20, int(v.min()) - 20
        import cv2
        hl = cv2.convexHull(np.stack([u - x0, v - y0], 1).astype(np.float32))
        cov = _coverage_exact(cm, cor, x0, y0, g.shape)
        self.assertAlmostEqual(PolyIntegrator(g).integral(hl), float((cov * g).sum()), places=6)

    def test_placed_and_supply(self):
        env = self.env
        env.reset_piece(800211, 8, arm_q=self.q)
        for name, tol in (("WA1", 0.6), ("WC1", 0.9), ("WE1", 1.2)):
            cm = self.cam(name)
            rgb, dep = env.render_raw(name), env.render_raw(name, depth=True)
            k = 7
            s = env.design[k]
            top = lambda o: o["z"] + H / 2 - C.TOP_SINK_M[o["course"]]
            others = [(o["x"], o["y"], o["yaw"], o["L"], top(o)) for j, o in enumerate(env.design) if j < k]
            est = measure(rgb, dep, cm, (s["x"] + 0.004, s["y"] - 0.003), 0.02, s["L"], top(s), radius=0.03, yaw_range_deg=10.5, others=others)
            self.assertIsNotNone(est, name)
            pt, _ = env.brick_pose(k)
            self.assertLess(np.hypot(*(est["pos"][:2] - pt[:2])) * 1000, tol, name)
        cm = self.cam("SB1")
        rgb = env.render_raw("SB1")
        dep = noisy_depth(env.render_raw("SB1", depth=True), env.cam_fovy["SB1"], "d435", np.random.default_rng(1))
        errs = []
        for i in range(8, 16):                                # still on the table, scattered ±10 mm / ±10°
            x, y = env.cfg.supply_slots[i]
            est = measure(rgb, dep, cm, (x, y), 0.0, env.design[i]["L"], env.cfg.table_h + H - C.TOP_SINK_M["supply"], radius=0.025)
            self.assertIsNotNone(est)
            pt, qt = env.brick_pose(i)
            errs.append(np.hypot(*(est["pos"][:2] - pt[:2])) * 1000)
            self.assertLess(abs(np.degrees((est["yaw"] - yaw_of_quat(qt) + np.pi / 4) % (np.pi / 2) - np.pi / 4)), 1.5)
        self.assertLess(max(errs), 2.0)
        self.assertLess(float(np.median(errs)), 0.6)

    def test_nothing_there(self):
        env = self.env
        env.reset_piece(800212, 3, arm_q=self.q)
        cm = self.cam("WA2")
        rgb, dep = env.render_raw("WA2"), env.render_raw("WA2", depth=True)
        s = env.design[4]                                     # slot 4 is still empty
        self.assertIsNone(measure(rgb, dep, cm, (s["x"], s["y"]), 0.0, s["L"], s["z"] + H / 2, radius=0.03))


if __name__ == "__main__":
    unittest.main()
