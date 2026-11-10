"""추가 제어 K1 · K2 · K6 (2026-11-10, 01_사기설/실험파이프라인_실패원인제거_20261110.md).

K1: G1이 빈손으로 판정하면 집게를 연 뒤 철수 자세로 보내고, 롤아웃이 그것을 정책의 철수로 세지 않게 한 번만 알린다. 이웃 벽돌은 건드리지 않는다.
K2: 정책이 집게를 연 채 공급칸 위로 내려오면 도면 공급칸 중심에서 집고 G1 판정 뒤 운반 중 상태로 돌려준다. 이웃은 그대로.
    집게를 닫는 중 · 올라가는 중 · 너무 높음 · 이미 집은 칸에서는 가로채지 않는다.
K6: G3가 놓인 벽돌을 찾는 반경이 설정값을 따른다. 기본값은 그 전과 같다.
K1 + K2: G0가 빈 공급칸을 집어 G1이 '안 쥠'이면 before() 안에서 철수한다. 롤아웃은 before · after 어느 쪽 뒤에서도 그 철수를 알아듣는다.
실행: cd sim && MUJOCO_GL=egl PYTHONPATH=. venv/bin/python -m unittest discover -s tests -p "test_wall3_gate_fix.py" -v
"""
import unittest

import numpy as np

from wall3.gates import FIXES, GateConfig, WallGates, fix_fields


class FixConfigTest(unittest.TestCase):
    def test_defaults_are_the_old_gates(self):
        c = GateConfig()
        self.assertFalse(c.g1_fail_retract)
        self.assertEqual(c.g3_find_r, 0.04)

    def test_fix_fields(self):
        self.assertEqual(fix_fields([]), {})
        self.assertEqual(fix_fields(["k1", "k6"]), {"g1_fail_retract": True, "g3_find_r": 0.07})
        self.assertEqual(fix_fields(["k2"]), {"g0_align": True})
        self.assertFalse(GateConfig().g0_align)
        for k, v in FIXES.items():
            GateConfig(**v)                                   # every fix is a valid config
        with self.assertRaises(ValueError):
            fix_fields(["k9"])


class K1RetractTest(unittest.TestCase):
    def test_empty_grasp_goes_to_retract(self):
        from wall3 import gripper as G
        from wall3.config import scene_config
        from wall3.expert import WallExpert
        from wall3.g1 import G1Config
        from wall3.ik import down_R
        from wall3.poses import yaw_of_quat
        from wall3.scene import WallEnv
        from wall3.test_g1 import SEED, empty_side
        env = WallEnv(scene_config("main_v1_eval"))
        ex = WallExpert(env)
        env.reset(SEED, arm_q=ex.q_ret)
        ex.on_step, ex.q_cmd, ex.grip_cmd, ex.fail, ex.touch, ex.brick_k = None, ex.q_ret.copy(), 0.0, None, [], 2
        ex.in_hand, ex.max_drift, ex.steps = None, 0.0, 0
        k = 2
        pb, qb = env.brick_pose(k)
        u, _ = empty_side(env, k)                             # beside the brick, clear of it: an empty grasp
        p = pb + u * (env.design[k]["L"] / 2 + 0.063) + [0, 0, ex.dzp]
        R = down_R(yaw_of_quat(qb))
        ex._joint_move(ex._solve(p + [0, 0, ex.cfg.approach], R, ex.q_ret, ex.q_ret[0]), 0.0, None, "to_supply")
        ex._cart_move(p, R, ex.cfg.t_down, 0.0, None, "grasp_descend")
        gc = env.cfg.gripper
        n = int(round(ex.cfg.t_close / ex.dt))
        cg = ex.grip_close_cmd()
        ex._hold(n, [min(cg, G.ramp(gc, True, (i + 1) * ex.dt, gc.open_ctrl)) for i in range(n)], None, "grasp_close")
        ex._cart_move(p + [0, 0, 0.015], R, 0.3, cg, None, "grasp_lift")
        before = env.brick_poses().copy()
        gates = WallGates(env, None, g1=True, g1_cfg=G1Config(thr_load=4.5, thr_angle=0.47), cfg=GateConfig(**fix_fields(["k1"])))
        gates.start_brick(k, env.t + 10_000)
        gates.trig.update = lambda grip, z: True              # the G1 moment (closed and lifted 1.5 cm), forced once
        act = np.asarray(env.last_action, float).copy()
        gates.after(act)
        e = gates.ev["g1"][-1]
        self.assertFalse(e["grasped"])
        self.assertIn("retract", e)
        self.assertLess(np.abs(env.arm_q() - ex.q_ret).max(), 0.02)
        self.assertTrue(gates.pop_gate_retract())
        self.assertFalse(gates.pop_gate_retract())            # once only
        moved = np.linalg.norm(env.brick_poses()[:, :3] - before[:, :3], axis=1).max()
        self.assertLess(moved, 0.002)

    def test_off_by_default(self):
        g = WallGates.__new__(WallGates)
        g._gate_retracted = False
        self.assertFalse(WallGates.pop_gate_retract(g))


class K2AlignTest(unittest.TestCase):
    def setUp(self):
        from wall3.config import scene_config
        from wall3.expert import WallExpert
        from wall3.g1 import G1Config
        from wall3.ik import down_R
        from wall3.scene import WallEnv, _quat_rotmat
        self.R, self.qm = down_R, _quat_rotmat
        self.env = env = WallEnv(scene_config("main_v1_eval"))
        self.ex = ex = WallExpert(env)
        env.reset(700323, arm_q=ex.q_ret)
        ex.on_step, ex.q_cmd, ex.grip_cmd, ex.fail, ex.touch, ex.brick_k = None, ex.q_ret.copy(), 0.0, None, [], 10
        ex.in_hand, ex.max_drift, ex.steps = None, 0.0, 0
        ex._watch = lambda held, phase: None
        self.gates = WallGates(env, None, g1=True, g1_cfg=G1Config(thr_load=4.5, thr_angle=0.47),
                               cfg=GateConfig(target="held_grasp", **fix_fields(["k2"])))
        self.gates.start_brick(0, env.t + 10_000)
        self.gates.k = 6
        pos, self.z_grasp, self.z_app = self.gates._g0_heights(10)
        # where the policy was in 700323: about 30 / 25 mm off the slot centre, a little below the approach height
        self.p = np.r_[pos[:2] + [0.030, 0.025], self.z_app - 0.01]
        q = ex._solve(self.p, down_R(0.0), ex.q_ret, ex.q_ret[0])
        ex._joint_move(q, 0.0, None, "to_test_pose")
        self.q_down = ex._solve(self.p - [0, 0, 0.01], down_R(0.0), env.arm_q(), env.arm_q()[0])

    def test_grasps_at_the_slot_centre(self):
        env, g = self.env, self.gates
        before = env.brick_poses().copy()
        self.assertTrue(g.before(np.r_[self.q_down, 0.0]))
        e = g.ev["g0"][-1]
        self.assertEqual((e["supply_slot"], e["result"], e["g1_grasped"]), (10, "done", True))
        self.assertTrue(g.carrying)
        self.assertEqual(g.tgt, 10)
        self.assertIn(10, g.g0_taken)
        pt, Rt = env.tcp()
        pb, _ = env.brick_pose(10)
        rel = Rt.T @ (pb - pt)
        self.assertLess(abs(rel[0]), 0.015)
        self.assertLess(abs(rel[1]), 0.008)
        self.assertGreater(pb[2] - before[10, 2], 0.005)
        others = [j for j in range(env.n) if j != 10]
        self.assertLess(np.linalg.norm(env.brick_poses()[others, :3] - before[others, :3], axis=1).max(), 0.002)
        self.assertFalse(g.before(np.r_[self.q_down, 0.0]))     # carrying: no second G0

    def test_not_triggered(self):
        g = self.gates
        self.assertIsNone(g._g0_slot(np.r_[self.q_down, 0.3]))        # closing: the policy's own grasp
        self.assertIsNone(g._g0_slot(np.r_[self.env.arm_q(), 0.0]))   # not going down
        g.g0_taken.add(10)
        self.assertIsNone(g._g0_slot(np.r_[self.q_down, 0.0]))        # already grasped from this slot
        g.g0_taken.clear()
        g.g0_tries[10] = g.cfg.g0_max_tries
        self.assertIsNone(g._g0_slot(np.r_[self.q_down, 0.0]))        # tries used up
        g.g0_tries[10] = 0
        self.assertEqual(g._g0_slot(np.r_[self.q_down, 0.0]), 10)

    def test_too_high(self):
        ex, env, g = self.ex, self.env, self.gates
        p = self.p + [0, 0, g.cfg.g0_zone_z + 0.03]
        ex._joint_move(ex._solve(p, self.R(0.0), env.arm_q(), env.arm_q()[0]), 0.0, None, "up")
        q = ex._solve(p - [0, 0, 0.01], self.R(0.0), env.arm_q(), env.arm_q()[0])
        self.assertIsNone(g._g0_slot(np.r_[q, 0.0]))


class K1K2Test(unittest.TestCase):
    """K1 + K2: G0 grasps an empty supply slot, G1 says not grasped, K1 sends the arm to the retract pose inside before().
    The rollout must hear about that retract too (pop once), whichever gate call did it."""

    def setUp(self):
        K2AlignTest.setUp(self)                               # same scene and arm pose as the K2 tests (not their test cases)
        import mujoco
        self.gates.cfg.g1_fail_retract = True
        a = self.env.brick_qadr[10]
        self.env.data.qpos[a:a + 3] = [0.0, -1.3, 0.03]       # brick 10 away from its supply slot: an empty grasp
        self.env.data.qvel[:] = 0
        mujoco.mj_forward(self.env.model, self.env.data)
        self.env.step(self.env.arm_q(), 0.0)

    def test_empty_g0_then_retract(self):
        env, g = self.env, self.gates
        self.assertTrue(g.before(np.r_[self.q_down, 0.0]))
        e = g.ev["g0"][-1]
        self.assertEqual((e["supply_slot"], e["result"], e["g1_grasped"]), (10, "done", False))
        self.assertTrue(g.ev["g1"][-1]["retract"])
        self.assertFalse(g.carrying)
        self.assertLess(np.abs(env.arm_q() - np.asarray(self.ex.q_ret)).max(), 0.02)
        self.assertTrue(g.pop_gate_retract())
        self.assertFalse(g.pop_gate_retract())

    def test_rollout_checks_after_both_gate_calls(self):
        import inspect
        from wall3 import rollout
        src = inspect.getsource(rollout.run_wall)
        i_pop = src.index("gates.pop_gate_retract()")
        self.assertGreater(i_pop, src.index("gates.after(act)"))
        line = [l for l in src.splitlines() if "gates.pop_gate_retract()" in l][0]
        body = [l for l in src.splitlines() if "if gates is not None and gates.before(act)" in l][0]
        self.assertEqual(len(line) - len(line.lstrip()), len(body) - len(body.lstrip()))   # same level as the before/after branch


class K6RadiusTest(unittest.TestCase):
    def test_g3_uses_the_configured_radius(self):
        from wall3.config import scene_config, RETRACT_Q
        from wall3.scene import WallEnv
        env = WallEnv(scene_config("main_v1_eval"))
        env.reset(700300, arm_q=np.array(RETRACT_Q))
        for r_cfg in (0.04, 0.07):
            gates = WallGates(env, None, g3=True, cfg=GateConfig(g3_find_r=r_cfg))
            seen = []

            class FakeCam:
                _key = None

                def find(self, xy, r=0.05, **kw):
                    seen.append(r)
                    return None
            gates.cam = FakeCam()
            gates.k = 5
            gates._view_laid(5)
            self.assertTrue(seen)
            self.assertEqual(set(seen), {r_cfg})


if __name__ == "__main__":
    unittest.main()
