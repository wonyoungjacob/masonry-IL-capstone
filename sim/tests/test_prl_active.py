"""능동 카메라(팬 · 틸트 + 시선 규칙) 시험.

실행: cd sim && PYTHONPATH=. MUJOCO_GL=egl venv/bin/python -m unittest discover -s tests -p "test_prl_*.py"
"""
import unittest

import mujoco
import numpy as np

from wall3.config import RETRACT_Q
from prl import config as C
from prl.active_cam import ActiveRig, PanTilt, PanTiltSpec, Gaze, Task, cam_pose, look_angles, rig_specs, FINGER_GRASP
from prl.env import DryEnv

CAMS = {"P1": {"base": [1.5, 0.0, 1.4], "pan0": 180.0, "role": "lead"},
        "P2": {"base": [0.0, 1.6, 1.0], "pan0": -90.0, "role": "slot"},
        "P3": {"base": [1.5, 0.0, 1.4], "pan0": 180.0, "role": "pick"}}


class TestKinematics(unittest.TestCase):
    def test_look_at_puts_target_on_axis(self):
        rng = np.random.default_rng(0)
        for _ in range(500):
            base = rng.uniform(-2, 2, 3)
            tgt = base + rng.uniform(-2, 2, 3)
            if np.linalg.norm(tgt - base) < 0.3:
                continue
            pan, tilt = look_angles(base, tgt, 0.03)
            p, R = cam_pose(base, pan, tilt, 0.03)
            d = (tgt - p) / np.linalg.norm(tgt - p)
            self.assertLess(np.degrees(np.arccos(np.clip(d @ (-R[:, 2]), -1, 1))), 1e-4)
            self.assertAlmostEqual(R[2, 0], 0.0, places=12)          # no roll: the image x axis stays horizontal
            self.assertAlmostEqual(np.linalg.det(R), 1.0, places=9)

    def test_tracker_respects_limits_and_settles(self):
        spec = PanTiltSpec()
        u = PanTilt((0, 0, 1.0), 0.0, spec)
        u.snap((1, 0, 1.0))
        tgt = (np.cos(np.radians(90)), np.sin(np.radians(90)), 0.5)
        prev = u.q.copy()
        for i in range(60):
            u.step(tgt, 0.05)
            self.assertLessEqual(np.degrees(np.abs(u.q - prev).max()), spec.w_max * 0.05 + 1e-6)
            prev = u.q.copy()
        self.assertLess(u.error_deg(), 1e-6)
        self.assertEqual(u.speed_deg(), 0.0)
        self.assertTrue(u.reachable)

    def test_limits(self):
        u = PanTilt((0, 0, 1.0), 0.0)
        _, ok = u.angles_for((0.05, 0.0, 0.0))                       # almost straight down: below the tilt limit
        self.assertFalse(ok)
        _, ok = u.angles_for((-1.0, 0.01, 1.0))                      # behind the reference direction: beyond ± 170°
        self.assertFalse(ok)


class TestGaze(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.env = DryEnv(fixed_cams={}, extra_cams=rig_specs(CAMS))
        cls.env.reset(C.SEED_ZONES["dev"][0], arm_q=np.array(RETRACT_Q))
        cls.rig = ActiveRig(cls.env, CAMS, RETRACT_Q)

    @classmethod
    def tearDownClass(cls):
        cls.env.close()

    def finger(self, v):
        self.env.data.qpos[self.rig.task.finger_adr] = v
        mujoco.mj_kinematics(self.env.model, self.env.data)

    def test_roles_follow_the_task_events(self):
        t = self.rig.task
        g = {n: Gaze(c["role"], t) for n, c in CAMS.items()}
        k = 4
        self.finger(0.0)
        for n in g:
            g[n].reset(k)
        np.testing.assert_allclose(g["P1"].target(k), t.supply[k])   # before the grasp: the brick to pick
        np.testing.assert_allclose(g["P2"].target(k), t.slot[k])     # wall eye: the place slot
        np.testing.assert_allclose(g["P3"].target(k), t.supply[k])
        self.finger(FINGER_GRASP + 0.1)                              # grasped
        np.testing.assert_allclose(g["P1"].target(k), t.slot[k])
        np.testing.assert_allclose(g["P3"].target(k), t.supply[k + 1])
        self.finger(0.0)                                             # released
        np.testing.assert_allclose(g["P1"].target(k), t.supply[k + 1])
        np.testing.assert_allclose(g["P2"].target(k), t.slot[k])
        np.testing.assert_allclose(g["P1"].target(k + 1), t.supply[k + 1])   # next brick: a new cycle
        np.testing.assert_allclose(g["P2"].target(k + 1), t.slot[k + 1])
        last = len(t.slot) - 1
        g["P1"].reset(last); self.finger(FINGER_GRASP + 0.1); g["P1"].target(last); self.finger(0.0)
        np.testing.assert_allclose(g["P1"].target(last), t.slot[last])       # last brick: stays on its slot

    def test_leave_after_retract(self):
        t = self.rig.task
        g = Gaze("lead", t, leave="retract")
        g.reset(2)
        self.finger(FINGER_GRASP + 0.1); g.target(2); self.finger(0.0)
        self.assertTrue(t.retracted())
        np.testing.assert_allclose(g.target(2), t.supply[3])
        a = self.env.arm_qadr
        keep = self.env.data.qpos[a].copy()
        g.reset(2)
        self.finger(FINGER_GRASP + 0.1); g.target(2); self.finger(0.0)
        self.env.data.qpos[a] = keep + 0.3                           # arm away from the retract pose: keep looking at the slot
        mujoco.mj_kinematics(self.env.model, self.env.data)
        np.testing.assert_allclose(g.target(2), t.slot[2])
        self.env.data.qpos[a] = keep
        mujoco.mj_kinematics(self.env.model, self.env.data)

    def test_rig_centres_the_target_and_leaves_the_physics_alone(self):
        env, rig = self.env, self.rig
        self.finger(0.0)
        ref = DryEnv(fixed_cams={})
        self.assertEqual(env.model.nq, ref.model.nq)                 # cameras add no joints
        ref.reset(C.SEED_ZONES["dev"][0], arm_q=np.array(RETRACT_Q))
        env.reset(C.SEED_ZONES["dev"][0], arm_q=np.array(RETRACT_Q))
        rig.reset(3)
        q = env.last_action
        for _ in range(5):
            env.step(q[:6], float(q[6])); rig.update(3)
            ref.step(q[:6], float(q[6]))
        np.testing.assert_array_equal(env.data.qpos, ref.data.qpos)  # moving the cameras does not change the simulation
        ref.close()
        p, R = env.cam_pose("P1")
        d = rig.task.supply[3] - p
        self.assertLess(np.degrees(np.arccos(d @ (-R[:, 2]) / np.linalg.norm(d))), 1e-3)
        img = env.render_raw("P1")
        self.assertEqual(img.shape, (C.RAW_H, C.RAW_W, 3))
        c = img[C.RAW_H // 2 - 4:C.RAW_H // 2 + 4, C.RAW_W // 2 - 4:C.RAW_W // 2 + 4].reshape(-1, 3).mean(0)
        self.assertGreater(c[0] / max(c[1], 1.0), 1.5)               # the centre of the image is on the (red) brick


if __name__ == "__main__":
    unittest.main()
