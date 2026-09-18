"""Scripted pick-and-place expert: Cartesian waypoints -> DLS IK -> joint-position actions.

Primitive sequence per brick (ManiSkill/robosuite-style scripted solver):
  pre-grasp (above) -> descend -> close jaw -> lift -> transport (above target) -> descend -> open -> retreat.
Optional DART-style noise: the *executed* target is perturbed while the *recorded* label stays clean,
so the policy sees recovery data (Laskey et al., 2017).
"""
from __future__ import annotations

import numpy as np

from .ik import DLSIK, rot_from_down_yaw
from .scene import BrickEnv, JAW_OPEN, JAW_CLOSED

GRASP_DZ = 0.004        # TCP above brick centre when grasping (16 mm bricks); scaled with H in plan_brick
PLACE_CLEAR = 0.0015    # release height above the design centre (+ grasp offset)
HOVER = 0.04            # hover height above pick/place
FIXED_PAD_X = 0.012     # inner face of the fixed-jaw pads from the TCP centre line, +x of the jaw frame (m)


def smoothstep(s):
    s = np.clip(s, 0.0, 1.0)
    return s * s * (3 - 2 * s)


class ScriptedExpert:
    def __init__(self, env: BrickEnv, noise_std: float = 0.0, seed: int = 0, speed: float = 1.0):
        self.env = env
        self.rng = np.random.default_rng(seed)
        self.noise_std = noise_std
        self.speed = speed
        self.ik = DLSIK(env.model, env.tcp_site, env.arm_qidx, env.arm_dofidx)
        self.segments = []
        self.log = []

    # ---------------------------------------------------------------- planning
    def plan_brick(self, i: int):
        env = self.env
        env.stage_brick(i)
        p0, q0 = env.brick_pose(i)
        yaw_b = 2 * np.arctan2(q0[3], q0[0])
        dz_grip = GRASP_DZ + max(0.0, (env.brick.H - 0.016) / 2)   # keep the pads on the upper half
        gx, gy, gz = p0[0], p0[1], p0[2] + dz_grip
        dx, dy, dz, dyaw = env.design[i][:4]
        # jaw closes across the brick width -> jaw axis (site x) perpendicular to the brick long axis
        yaw_grasp = yaw_b + np.pi / 2
        yaw_place = dyaw + np.pi / 2
        # The SO-ARM100 fixed jaw does not move: its pads sit ~12 mm from the TCP centre line on the +x side of
        # the jaw frame while the moving jaw swings out to -70 mm.  For a brick wider than 24 mm the TCP must be
        # offset toward the fixed jaw (+x) by (W/2 - 12 mm) so the fixed pad meets the brick face.  The same
        # offset is applied at place because the brick stays offset in the hand.
        d_off = max(0.0, env.brick.W / 2 - FIXED_PAD_X)
        xg = np.array([np.cos(yaw_grasp), np.sin(yaw_grasp), 0.0])
        xp = np.array([np.cos(yaw_place), np.sin(yaw_place), 0.0])
        gx, gy = gx + d_off * xg[0], gy + d_off * xg[1]   # toward the fixed jaw (+x of the jaw frame)
        dx, dy = dx + d_off * xp[0], dy + d_off * xp[1]
        pz = dz + dz_grip + PLACE_CLEAR
        S = self.speed
        segs = [
            # (target xyz, yaw, jaw, duration s, interpolation)
            ((gx, gy, gz + HOVER), yaw_grasp, JAW_OPEN, 1.0 / S, "polar"),
            ((gx, gy, gz), yaw_grasp, JAW_OPEN, 0.6 / S, "lin"),
            ((gx, gy, gz), yaw_grasp, JAW_CLOSED, 0.4 / S, "lin"),
            ((gx, gy, gz + HOVER), yaw_grasp, JAW_CLOSED, 0.5 / S, "lin"),
            ((dx, dy, pz + HOVER), yaw_place, JAW_CLOSED, 1.2 / S, "polar"),
            ((dx, dy, pz), yaw_place, JAW_CLOSED, 0.7 / S, "lin"),
            ((dx, dy, pz), yaw_place, JAW_CLOSED, 0.4 / S, "servo"),   # closed-loop correction of steady-state error
            ((dx, dy, pz), yaw_place, JAW_OPEN, 0.4 / S, "lin"),
            ((dx, dy, pz + HOVER), yaw_place, JAW_OPEN, 0.5 / S, "lin"),
        ]
        return segs

    @staticmethod
    def _interp(p0, p1, a, mode):
        """Linear, or polar about the robot base (keeps the arc outside the unreachable inner zone)."""
        if mode == "lin":
            return p0 + a * (p1 - p0)
        r0, r1 = np.hypot(p0[0], p0[1]), np.hypot(p1[0], p1[1])
        t0, t1 = np.arctan2(p0[1], p0[0]), np.arctan2(p1[1], p1[0])
        dt = (t1 - t0 + np.pi) % (2 * np.pi) - np.pi
        r = r0 + a * (r1 - r0)
        th = t0 + a * dt
        z = p0[2] + a * (p1[2] - p0[2])
        return np.array([r * np.cos(th), r * np.sin(th), z])

    # ---------------------------------------------------------------- execution
    def run_episode(self, record_fn=None, max_ik_err=0.004):
        """Execute all bricks. record_fn(obs, action_clean, info) is called every control step."""
        env = self.env
        dt = env.cfg.ctrl_dt
        q_prev = env.data.qpos[env.arm_qidx].copy()
        p_prev, R_prev = env.tcp_pose()
        yaw_prev = float(np.arctan2(R_prev[1, 0], R_prev[0, 0]))
        jaw_prev = JAW_OPEN
        n_fail = 0
        for i in range(env.n_bricks):
            for (tp, tyaw, tjaw, dur, mode) in self.plan_brick(i):
                n_steps = max(1, int(round(dur / dt)))
                tp = np.asarray(tp, dtype=np.float64)
                # unwrap yaw to be near previous
                tyaw = yaw_prev + (tyaw - yaw_prev + np.pi) % (2 * np.pi) - np.pi
                p_cmd = tp.copy()
                for s in range(1, n_steps + 1):
                    a = smoothstep(s / n_steps)
                    if mode == "servo":
                        # integrate the measured TCP error into the commanded target (gain 0.6/step)
                        p_meas, _ = env.tcp_pose()
                        p_cmd = p_cmd + 0.6 * (tp - p_meas)
                        p_t = p_cmd.copy()
                    else:
                        p_t = self._interp(p_prev, tp, a, mode)
                    yaw_t = yaw_prev + a * (tyaw - yaw_prev)
                    jaw_t = jaw_prev + a * (tjaw - jaw_prev)
                    p_exec = p_t.copy()
                    if self.noise_std > 0:
                        p_exec += self.rng.normal(0, self.noise_std, 3)
                    q_clean, ep, er = self.ik.solve(q_prev, p_t, rot_from_down_yaw(yaw_t), env.data.qpos.copy())
                    if self.noise_std > 0:
                        q_exec, _, _ = self.ik.solve(q_prev, p_exec, rot_from_down_yaw(yaw_t), env.data.qpos.copy())
                    else:
                        q_exec = q_clean
                    if ep > max_ik_err:
                        n_fail += 1
                    act_clean = np.r_[q_clean, jaw_t].astype(np.float32)
                    act_exec = np.r_[q_exec, jaw_t]
                    obs = env.observe()
                    if record_fn is not None:
                        record_fn(obs, act_clean, {"brick": i, "ik_pos_err": ep, "ik_rot_err": er})
                    env.step(act_exec)
                    q_prev = q_clean
                p_prev, yaw_prev, jaw_prev = tp, tyaw, tjaw
        return n_fail
