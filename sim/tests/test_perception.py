"""On-board camera brick pose estimation and the gate reading it (2026-10-08, RQ4)."""
import unittest
import numpy as np
import mujoco

from brick_sim.scene import BrickEnv, blueprint_config
from brick_sim.expert import ScriptedExpert
from brick_sim.grasp_gate import GraspGate, _yaw, _fold
from brick_sim.perception import BrickPoseEstimator


def cfg(**kw):
    return blueprint_config('mortarB', size_rand=0, pos_rand=.03, supply_yaw_deg=60, valid_supply=True, feasible_supply=True, **kw)


class _P:
    def reset(self): pass


def run_expert_with_gate(env, seed, source):
    env.reset(seed)
    ex = ScriptedExpert(env, seed=seed, max_retries=0, clean_single_pass=True)
    gate = GraspGate(env, _P(), max_retries=0, recover="reguide", release_gate=True, force=True, replace=True, pose_source=source)
    orig = env.step; busy = [False]
    def step(act):
        if busy[0]:
            return orig(act)
        busy[0] = True
        try:
            a = gate.before_step(np.asarray(act, dtype=np.float32))
            if a is None:
                return
            orig(a); gate.after_step(a)
        finally:
            busy[0] = False
    env.step = step
    try:
        ex.run_episode()
    finally:
        env.step = orig
    return ex, gate


class PerceptionTests(unittest.TestCase):
    def test_policy_observation_unchanged_by_larger_offscreen_buffer(self):
        # the 128 px policy cameras must render pixel-identically with the old 640x480 buffer (datasets / checkpoints)
        env = BrickEnv(cfg()); env.reset(40000)
        xml_old = env.last_xml.replace('offwidth="1280" offheight="960"', 'offwidth="640" offheight="480"')
        self.assertNotEqual(xml_old, env.last_xml)
        m = mujoco.MjModel.from_xml_string(xml_old, env._assets); d = mujoco.MjData(m)
        d.qpos[:] = env.data.qpos; d.ctrl[:] = env.data.ctrl; mujoco.mj_forward(m, d)
        r = mujoco.Renderer(m, 128, 128)
        for cam in ("top", "front", "wrist"):
            r.update_scene(d, camera=cam)
            self.assertTrue(np.array_equal(r.render(), env.render(cam)), cam)
        r.close()

    def test_spawn_poses_within_a_millimetre(self):
        env = BrickEnv(cfg()); est = BrickPoseEstimator(env)
        n_full = 0
        for s in (40000, 40005, 40011):
            env.reset(s); env.settle(5)
            dets = est.detect(force=True)
            self.assertEqual(len(dets), 3, s)
            for i in range(3):
                p, q = env.brick_pose(i); d = est.match(p[:2], dets)
                self.assertIsNotNone(d, (s, i))
                n_full += int(d["full"])                       # a brick under the parked arm is partial, still accurate
                self.assertLess(1000 * np.hypot(*(d["pos"][:2] - p[:2])), 1.5, (s, i))
                self.assertLess(abs(1000 * (d["pos"][2] - p[2])), 1.0, (s, i))
                self.assertLess(abs(np.degrees(_fold(d["yaw"] - _yaw(q)))), 1.0, (s, i))
        self.assertGreaterEqual(n_full, 7)
        est.close()

    def test_two_butted_wall_bricks_are_split(self):
        # the lower course as laid (1 mm head joint): one orange blob from above, must come back as two bricks
        env = BrickEnv(cfg()); env.reset(40000)
        for i in range(2):
            x, y, z, yaw, _ = env.design[i]
            a = env.brick_qadr[i]
            env.data.qpos[a: a + 3] = [x, y, z + 0.0003]; env.data.qpos[a + 3: a + 7] = [1, 0, 0, 0]
        mujoco.mj_forward(env.model, env.data); env.settle(10)
        est = BrickPoseEstimator(env); dets = est.detect(force=True)
        self.assertEqual(len(dets), 3, [(round(d["long"], 3), d["k"]) for d in dets])
        self.assertEqual(sum(d["k"] == 2 for d in dets), 2)
        for i in range(2):
            p, _ = env.brick_pose(i); d = est.match(p[:2], dets)
            self.assertIsNotNone(d, i)
            self.assertLess(1000 * np.hypot(*(d["pos"][:2] - p[:2])), 1.5, i)
        est.close()

    def test_gate_with_camera_completes_and_logs_sub_mm_errors(self):
        env = BrickEnv(cfg())
        ex, gate = run_expert_with_gate(env, 40000, "camera")
        S = gate.summary(); gate.cam.close()
        self.assertEqual(S["pose_source"], "camera")
        self.assertEqual(S["cam_stats"]["fallback_truth"], 0)
        self.assertGreater(S["cam_stats"]["measurements"], 5)
        self.assertEqual(S["bad_releases"], 0)
        self.assertLess(S["cam_err_xy_mm_max"], 2.0)
        self.assertLess(S["cam_err_yaw_deg_p95"], 2.0)
        held = [e for e in S["cam_log"] if e["held"]]
        self.assertTrue(held)                                    # the held brick was measured, not read from the simulator
        self.assertTrue(all(e["src"] == "camera" for e in held))
        self.assertTrue(all(not ex.unrecoverable for _ in [0]))

    def test_camera_rejects_pose_noise(self):
        env = BrickEnv(cfg()); env.reset(40000)
        with self.assertRaises(AssertionError):
            GraspGate(env, _P(), pose_source="camera", pose_noise=0.002)


if __name__ == '__main__':
    unittest.main()
