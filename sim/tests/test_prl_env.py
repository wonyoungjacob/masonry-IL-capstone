"""개인 연구 건식 환경(dry_v1) 시험.

실행: cd sim && PYTHONPATH=. MUJOCO_GL=egl venv/bin/python -m unittest discover -s tests -p "test_prl_*.py"
"""
import unittest

import numpy as np

from wall3.config import scene_config, H, JOINT, design_slots
from prl import config as C
from prl.env import DryEnv, letterbox, noisy_depth
from prl.spec import evaluate_dry, brick_error


class TestConfig(unittest.TestCase):
    def test_wall3_untouched(self):
        # the frozen wall3 environments keep their design (mortar joints) and their config dict
        d = design_slots()
        self.assertAlmostEqual(d[5]["z"], H / 2 + H + JOINT)
        self.assertEqual(scene_config("main_v1").env_version, "main_v1")
        self.assertNotIn("bed_rule", scene_config("main_v1").to_dict())

    def test_dry_design(self):
        d = C.dry_design()
        w = design_slots()
        self.assertEqual(len(d), 16)
        for a, b in zip(d, w):
            self.assertEqual((a["x"], a["y"], a["yaw"], a["L"]), (b["x"], b["y"], b["yaw"], b["L"]))
            self.assertAlmostEqual(a["z"], H / 2 + (a["course"] - 1) * H)

    def test_seed_zones(self):
        C.check_seeds("script", range(800100, 800150))
        with self.assertRaises(SystemExit):
            C.check_seeds("script", [700300])
        with self.assertRaises(SystemExit):
            C.check_seeds("select", [840000])
        for lo, hi in C.SEED_ZONES.values():
            self.assertTrue(hi < C.LOCKED[0] and lo > C.FORBIDDEN[1])

    def test_fov_and_noise_formula(self):
        self.assertAlmostEqual(C.FOVY_D435, 70.9, places=1)
        f = C.focal_px(C.FOVY_D435)
        self.assertAlmostEqual(f, 640 / np.tan(np.radians(43.5)), places=3)
        self.assertAlmostEqual(float(C.depth_sigma(1.0, C.FOVY_D435)), 0.08 / (f * 0.05), places=9)


class TestEnv(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.env = DryEnv()

    @classmethod
    def tearDownClass(cls):
        cls.env.close()

    def test_cameras_exist(self):
        m = self.env.model
        for n in list(C.FIXED_CAMS) + ["wrist", "H1", "H2"]:
            self.assertGreaterEqual(m.camera(n).id, 0)
        p, R = (self.env.reset(800200), self.env.cam_pose("SA2"))[1]
        np.testing.assert_allclose(p, C.FIXED_CAMS["SA2"]["pos"], atol=1e-9)
        np.testing.assert_allclose(-R[:, 2], [0, 0, -1], atol=1e-9)           # looks straight down

    def test_no_mortar(self):
        env = self.env
        env.reset_piece(800200, 6)
        q = env.last_action
        for _ in range(60):                                   # 3 s: main_v1 would cure the placed bricks and lay bed 1
            env.step(q[:6], float(q[6]))
        self.assertFalse(env.cured.any())
        self.assertFalse(env.data.eq_active[[env.model.equality(f"cure_{i}").id for i in range(16)]].any())
        for mid in env.bed_mocap.values():
            self.assertAlmostEqual(env.data.mocap_pos[mid][2], -1.0)

    def test_reset_piece(self):
        env = self.env
        env.reset(800201)
        supply = [p.copy() for p, _ in env.supply]
        env.reset_piece(800201, 7)
        for i in range(7):
            e = brick_error(env, i)
            self.assertLess(e["xy_err_mm"], 0.2)
            self.assertLess(abs(e["z_err_mm"]), 0.5)
            self.assertTrue(e["filled"])
        for i in range(7, 16):                                # same scatter as the wall-level reset, still on the table
            np.testing.assert_allclose(env.brick_pose(i)[0][:2], supply[i][:2], atol=5e-4)
            self.assertTrue(env.on_table(i))
        self.assertEqual(env.t, 0)

    def test_spec_dry(self):
        env = self.env
        env.reset_piece(800202, 16)
        r = evaluate_dry(env)
        self.assertTrue(r["exists"])
        self.assertTrue(r["spec_pass"])
        self.assertFalse(r["1_bed_joint"]["evaluated"])
        self.assertFalse(r["1_bed_joint"]["pass"])            # no 10 mm bed joint: ① would fail, and is not counted
        a = env.brick_qadr[12]
        env.data.qpos[a + 1] += 0.010                         # 10 mm out of the wall plane: ② ③ fail
        import mujoco
        mujoco.mj_forward(env.model, env.data)
        self.assertFalse(evaluate_dry(env)["spec_pass"])

    def test_images(self):
        env = self.env
        env.reset(800200)
        raw = env.render_raw("WC1")
        self.assertEqual(raw.shape, (C.RAW_H, C.RAW_W, 3))
        img = env.policy_image("H0")
        self.assertEqual(img.shape, (224, 224, 3))
        self.assertEqual(int(img[:28].max()), 0)
        self.assertEqual(int(img[-28:].max()), 0)
        self.assertGreater(int(img[28:-28].max()), 0)
        self.assertEqual(letterbox(np.full((960, 1280, 3), 200, np.uint8))[28:196].min(), 200)

    def test_depth_noise(self):
        rng = np.random.default_rng(0)
        for z in (0.8, 1.6):
            d = np.full((480, 640), z, np.float32)
            n = noisy_depth(d, C.FOVY_D435, "d435", rng)
            f = C.focal_px(C.FOVY_D435, 480)
            want = z * z * 0.08 / (f * 0.05)
            self.assertAlmostEqual(float(np.nanstd(n[40:-40, 40:-40])) / want, 1.0, delta=0.12)
            self.assertAlmostEqual(float(np.nanmean(n)), z, delta=3 * want / 10)
        d = np.full((480, 640), 0.2, np.float32)
        self.assertTrue(np.isnan(noisy_depth(d, C.FOVY_D435, "d435", rng)).all())      # below the D435 range
        self.assertFalse(np.isnan(noisy_depth(d, C.FOVY_D435, "d405", rng)).any())


if __name__ == "__main__":
    unittest.main()
