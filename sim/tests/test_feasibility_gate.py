"""Spawn feasibility filter and grasp gate (2026-09-23)."""
import unittest
import numpy as np

from brick_sim.scene import BrickEnv, blueprint_config, JAW_OPEN, JAW_CLOSED
from brick_sim.expert import ScriptedExpert
from brick_sim.feasibility import grasp_feasibility
from brick_sim.grasp_gate import GraspGate


def cfg(**kw):
    return blueprint_config('mortarB', size_rand=0, pos_rand=.03, supply_yaw_deg=60, valid_supply=True, **kw)


class FeasibilityTests(unittest.TestCase):
    def test_seed_1001_first_brick_self_collides(self):
        env = BrickEnv(cfg()); env.reset(1001)
        i = int(np.argmin([env.brick_pose(b)[0][0] for b in range(3)]))
        f = grasp_feasibility(env, i)
        self.assertFalse(f['ok'])
        self.assertGreater(f['self_pen_m'], 0.005)
        self.assertTrue(f['worst'].startswith('self:'))

    def test_seed_1044_neighbour_in_jaw_sweep(self):
        env = BrickEnv(cfg()); env.reset(1044)
        i = int(np.argmin([env.brick_pose(b)[0][0] for b in range(3)]))
        f = grasp_feasibility(env, i)
        self.assertFalse(f['ok'])
        self.assertTrue(f['worst'].startswith('nbr:'))

    def test_check_restores_state_and_passes_success_seed(self):
        env = BrickEnv(cfg()); env.reset(1002)
        before = env.data.qpos.copy()
        f = grasp_feasibility(env, int(np.argmin([env.brick_pose(b)[0][0] for b in range(3)])))
        self.assertTrue(f['ok'])
        np.testing.assert_allclose(env.data.qpos, before)

    def test_feasible_supply_resamples_and_keeps_old_sampler(self):
        env = BrickEnv(cfg()); env.reset(1001); old = env.brick_poses().copy()
        env2 = BrickEnv(cfg(feasible_supply=True)); env2.reset(1001)
        self.assertGreaterEqual(env2.feasibility_rejects, 1)
        self.assertTrue(all(f['ok'] for f in env2.supply_feasibility))
        self.assertFalse(np.allclose(env2.brick_poses(), old))
        env.reset(1001); np.testing.assert_allclose(env.brick_poses(), old)   # default path unchanged


class _Stop(Exception):
    pass


class _FakePolicy:
    def __init__(self): self.resets = 0
    def reset(self): self.resets += 1


class GraspGateTests(unittest.TestCase):
    def _run_first_pick(self, seed, release_gate=False, perturb=None, force=False, replace=False, stop_after_release=False,
                        gate_hook=None):
        env = BrickEnv(cfg()); env.reset(seed)
        ex = ScriptedExpert(env, seed=seed, max_retries=0, clean_single_pass=True)
        pol = _FakePolicy()
        gate = GraspGate(env, pol, max_retries=1, release_gate=release_gate, force=force, replace=replace)
        if gate_hook is not None:
            gate_hook(gate)
        outcomes = []
        orig = env.step
        def step(act):
            if getattr(gate, '_in_recovery', False):
                return orig(act)
            gate._in_recovery = True
            try:
                if perturb is not None:
                    act = perturb(env, act)
                act = gate.before_step(act)
                if act is None:
                    if stop_after_release:
                        raise _Stop
                    return
                orig(act)
                outcomes.append(gate.after_step(act))
            finally:
                gate._in_recovery = False
        env.step = step
        try:
            ex.run_episode()
        except _Stop:
            pass
        env.step = orig
        return env, gate, pol, outcomes

    def test_force_check_needs_angle_and_load(self):
        env, gate, pol, out = self._run_first_pick(1002, force=True)
        ev = gate.events[0]
        self.assertEqual(ev['action'], 'carry')
        self.assertTrue(ev['jaw_ok'] and ev['load_ok'])
        self.assertGreater(ev['load_N'], 1.2)            # brick 1.83 N, measured after the 1.5 cm lift
        self.assertTrue(ev['sim_grasped'])
        carries = sum(e['action'] == 'carry' for e in gate.events)
        self.assertEqual(carries, 3)                     # the expert picks all three bricks
        self.assertEqual(pol.resets, carries)            # the gate moved the arm -> the policy queue is cleared each time

    def test_force_check_rejects_empty_close(self):
        env, gate, pol, out = self._run_first_pick(1001, force=True)
        ev = gate.events[0]
        self.assertTrue(ev['action'].startswith('recover'))
        self.assertFalse(ev['load_ok'])
        self.assertFalse(ev['sim_grasped'])

    def test_force_check_rejects_brick_angle_without_load(self):
        # jaw stopped at a brick-like angle but nothing hangs in it (e.g. jammed on an edge): angle alone would pass
        env, gate, pol, out = self._run_first_pick(1002, force=True, gate_hook=lambda g: setattr(g, 'load', lambda: 0.0))
        ev = gate.events[0]
        self.assertTrue(ev['jaw_ok'])
        self.assertFalse(ev['load_ok'])
        self.assertTrue(ev['action'].startswith('recover'))

    def test_bad_release_is_replaced_once(self):
        # make the first release aim 8 mm off the slot: the post-release score fails and the gate places it again
        def hook(g):
            true_target, calls = g._slot_target, [0]
            def offset_target(k, held):
                calls[0] += 1
                xyz, yaw = true_target(k, held)
                return (xyz + np.array([0.008, 0.0, 0.0]) if calls[0] == 1 else xyz), yaw
            g._slot_target = offset_target
        env, gate, pol, out = self._run_first_pick(1002, release_gate=True, force=True, replace=True,
                                                   stop_after_release=True, gate_hook=hook)
        ev = gate.release_events[0]
        self.assertTrue(ev['bad_release'])
        self.assertGreater(ev['post_release']['exy_mm'], 4.5)
        self.assertIsInstance(ev['replace'], dict)
        self.assertEqual(ev['replace']['result'], 'ok', ev['replace'])
        self.assertLessEqual(ev['replace']['second_release']['post_release']['exy_mm'], 4.5)
        self.assertIn(ev['brick'], gate._replaced)

    def test_policy_cannot_regrasp_a_released_brick(self):
        env, gate, pol, out = self._run_first_pick(1002, release_gate=True, force=True, stop_after_release=True)
        i = gate.release_events[0]['brick']
        act = gate._act(jaw=JAW_OPEN)
        g, yaw_g, _ = gate._grasp_target(i)
        gate._segments([(g + np.array([0, 0, 0.04]), yaw_g, JAW_OPEN, 0.8, 'lin'), (g, yaw_g, JAW_OPEN, 0.6, 'lin'),
                        (g, yaw_g, JAW_CLOSED, 0.4, 'lin')], act)
        verdict = 'pass'
        for _ in range(25):
            env.step(act)
            verdict = gate.after_step(act)
            if verdict != 'pass':
                break
        self.assertEqual(verdict, 'retry')
        self.assertEqual(gate.events[-1]['action'], 'blocked')
        self.assertGreater(env.data.qpos[env.jaw_qidx], 0.5)   # reopened, the brick stays where it was laid

    def test_release_gate_intercepts_the_release_and_records_the_pose(self):
        env, gate, pol, out = self._run_first_pick(1002, release_gate=True)
        self.assertGreaterEqual(len(gate.release_events), 1)
        first = gate.release_events[0]
        self.assertEqual(first['slot'], 0)
        self.assertTrue(first['post_release']['in_slot'])
        self.assertLessEqual(first['exy_mm'], 4.5)   # the expert's own servo lands inside the final tolerance ...
        if first['corrected']:                        # ... but the gate corrects anything beyond 2.5 mm
            self.assertLess(first['exy_after_mm'], first['exy_mm'])
        self.assertLessEqual(first['post_release']['exy_mm'], 4.5)
        self.assertFalse(first['bad_release'])

    def test_empty_close_triggers_recovery(self):
        env, gate, pol, out = self._run_first_pick(1001)
        self.assertIn('retry', out)
        self.assertEqual(gate.events[0]['action'], 'recover:lift')
        self.assertFalse(gate.events[0]['sim_grasped'])
        self.assertEqual(pol.resets, 1)
        self.assertGreater(env.data.qpos[env.jaw_qidx], 0.5)   # jaw reopened by the recovery

    def test_wrist_sensor_reads_gripper_weight_and_brick_load(self):
        env = BrickEnv(cfg()); env.reset(1002)
        for _ in range(20):
            env.step(env.data.ctrl[env.act_ids].copy())
        F, _ = env.wrist_ft()
        self.assertAlmostEqual(float(F[2]), env.gripper_mass() * 9.81, places=2)
        # expert pick + lift only (the first four segments), then hold still and read the load
        ex = ScriptedExpert(env, seed=1002, max_retries=0, clean_single_pass=True)
        ex.dt = env.cfg.ctrl_dt; ex.q_prev = env.data.qpos[env.arm_qidx].copy()
        p, R = env.tcp_pose(); ex.p_prev = p; ex.yaw_prev = float(np.arctan2(R[1, 0], R[0, 0])); ex.jaw_prev = JAW_OPEN
        ex.n_fail = 0; ex.place_bias = {}; ex.log = []
        ex.order = sorted(range(3), key=lambda b: env.brick_pose(b)[0][0]); ex.slot = {b: k for k, b in enumerate(ex.order)}
        i = ex.order[0]
        ex._run_segments(ex.plan_brick(i)[:4], i, None, 0.004)
        for _ in range(10):
            env.step(env.data.ctrl[env.act_ids].copy())
        gate = GraspGate(env, None, force=True)
        self.assertTrue(env.grasped(i))
        self.assertGreater(gate.load(), 1.2)   # brick = 1.83 N hanging in the jaw after the lift

    def test_held_brick_passes(self):
        env, gate, pol, out = self._run_first_pick(1023)
        self.assertEqual(gate.events[0]['action'], 'carry')
        self.assertTrue(gate.events[0]['sim_grasped'])
        self.assertGreater(gate.events[0]['jaw'], 0.25)
        self.assertEqual(pol.resets, 0)
        self.assertEqual(gate.retries, 0)


if __name__ == '__main__':
    unittest.main()
