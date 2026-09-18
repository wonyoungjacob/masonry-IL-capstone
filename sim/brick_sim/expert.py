"""Scripted pick-and-place expert: Cartesian waypoints -> DLS IK -> joint-position actions.

Primitive sequence per brick (ManiSkill/robosuite-style scripted solver):
  pre-grasp (above) -> descend -> close jaw -> lift -> transport (above target) -> descend -> open -> retreat.
Optional DART-style noise: the *executed* target is perturbed while the *recorded* label stays clean,
so the policy sees recovery data (Laskey et al., 2017).
Optional disturbances (disturb_prob): a brick is shoved before its pick or right after its release and the
expert re-plans from the brick's current pose (pick it up again, place it again) -> recovery demonstrations.
"""
from __future__ import annotations

import numpy as np

from .ik import DLSIK, rot_from_down_yaw
from .scene import BrickEnv, JAW_OPEN, JAW_CLOSED

GRASP_DZ = 0.004        # TCP above brick centre when grasping (16 mm bricks); scaled with H in plan_brick
PLACE_CLEAR = 0.0015    # release height above the design centre (+ grasp offset)
PLACE_CLEAR_BED = 0.004 # same, for the brick released onto the soft mortar bed
HOVER = 0.04            # hover height above pick/place
FIXED_PAD_X = 0.012     # inner face of the fixed-jaw pads from the TCP centre line, +x of the jaw frame (m)


def smoothstep(s):
    s = np.clip(s, 0.0, 1.0)
    return s * s * (3 - 2 * s)


class ScriptedExpert:
    def __init__(self, env: BrickEnv, noise_std: float = 0.0, seed: int = 0, speed: float = 1.0,
                 disturb_prob: float = 0.0, max_retries: int = 2, tip_prob: float = 0.15, max_kicks: int = 2):
        self.env = env
        self.rng = np.random.default_rng(seed)
        self.noise_std = noise_std
        self.disturb_prob = disturb_prob      # P(kick) before each pick and again right after each release
        self.max_retries = max_retries
        self.tip_prob = tip_prob              # P(a kick has a tipping component | kick)
        self.max_kicks = max_kicks            # at most this many kicks per episode
        self.events, self.recoveries, self.unrecoverable = [], 0, []
        self.speed = speed
        self.ik = DLSIK(env.model, env.tcp_site, env.arm_qidx, env.arm_dofidx)
        self.segments = []
        self.log = []

    def D(self, i):
        """Design slot pose assigned to brick i (see self.order / self.slot in run_episode)."""
        return self.env.design[self.slot[i]] if hasattr(self, "slot") else self.env.design[i]

    # ---------------------------------------------------------------- planning
    def plan_brick(self, i: int):
        env = self.env
        env.stage_brick(i)   # no-op with scatter supply
        p0, q0 = env.brick_pose(i)
        yaw_b = 2 * np.arctan2(q0[3], q0[0])
        dz_grip = GRASP_DZ + max(0.0, (env.brick.H - 0.016) / 2)   # keep the pads on the upper half
        gx, gy, gz = p0[0], p0[1], p0[2] + dz_grip
        dx, dy, dz, dyaw = self.D(i)[:4]
        if getattr(env, "bed_laid", False) and dz > env.brick.H:
            dz = self.top_target_z()      # rest the top brick on the bed as laid, not on the nominal height
        # A mason butts a brick against its neighbour; our ~2-3 mm placement error would land it on the
        # neighbour's end (1 mm head joint), so aim slightly away from an already placed neighbour, plus any
        # correction learnt from a failed attempt on this brick (self.place_bias).
        bias = np.array(self.place_bias.get(i, (0.0, 0.0)))
        if dz < env.brick.H:
            for j in range(env.n_bricks):
                if j != i and self.D(j)[2] < env.brick.H and env.brick_in_slot(j, [self.slot[j]]) is not None:
                    bias[0] += 0.0015 * np.sign(dx - self.D(j)[0])
        dx, dy = dx + bias[0], dy + bias[1]
        self._brick_target = np.array([dx, dy, dz])   # where the brick itself should end up (servo target)
        self._brick_yaw_target = dyaw
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
        clear = PLACE_CLEAR
        if getattr(env, 'bed_laid', False) and self.D(i)[2] > env.brick.H:
            # the brick hangs ~10 deg in the jaw; on the soft mortar bed its low corner must not touch before
            # release or the servo pushes it in and rolls the brick over in the hand -> release from higher up
            clear = PLACE_CLEAR_BED
        pz = dz + dz_grip + clear
        S = self.speed
        segs = [
            # (target xyz, yaw, jaw, duration s, interpolation)
            ((gx, gy, gz + HOVER), yaw_grasp, JAW_OPEN, 1.0 / S, "polar"),
            ((gx, gy, gz), yaw_grasp, JAW_OPEN, 0.6 / S, "lin"),
            ((gx, gy, gz), yaw_grasp, JAW_CLOSED, 0.4 / S, "lin"),
            ((gx, gy, gz + HOVER), yaw_grasp, JAW_CLOSED, 0.5 / S, "lin"),
            ((dx, dy, pz + HOVER), yaw_place, JAW_CLOSED, 1.2 / S, "polar"),
            ((dx, dy, pz + HOVER), yaw_place, JAW_CLOSED, 0.4 / S, "servo"),   # align the *brick* xy/yaw in the air first:
            ((dx, dy, pz), yaw_place, JAW_CLOSED, 0.7 / S, "lin"),             # descending with the in-hand offset would
                                                                               # land a brick end on the neighbour's top
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

    # ---------------------------------------------------------------- disturbances / checks
    def kick_brick(self, i, record_fn=None, hold_steps=12, speed=(0.3, 0.6)):
        """Simulate the arm (or anything else) knocking brick i: a planar shove, sometimes with a tipping component.

        The arm holds still while physics runs, and those frames are recorded with the clean 'hold' action so the
        policy sees the brick move.  Returns the kick description for the episode log.
        """
        env = self.env
        rng = self.rng
        dof = env.brick_dofadr[i]
        ang = rng.uniform(-np.pi, np.pi)
        v = rng.uniform(*speed)                        # 0.3-0.6 m/s -> slides ~0.6-2.5 cm (mu=0.75); stays reachable
        wz = rng.uniform(-4.0, 4.0)
        tip = rng.random() < self.tip_prob             # occasionally a real knock-over (unrecoverable for a 5-DoF arm)
        env.data.qvel[dof: dof + 3] = [v * np.cos(ang), v * np.sin(ang), 0.0]
        env.data.qvel[dof + 3: dof + 6] = [rng.uniform(-7, 7) if tip else 0.0, rng.uniform(-7, 7) if tip else 0.0, wz]
        self._hold(hold_steps, record_fn)
        return {"brick": int(i), "t": int(env.t), "speed": float(v), "tip": bool(tip)}

    def _hold(self, n_steps, record_fn=None):
        """Keep the arm at its current joint targets for n control steps (recorded as clean hold actions)."""
        env = self.env
        act = np.asarray(env.data.ctrl[env.act_ids], dtype=np.float32).copy()
        for _ in range(n_steps):
            if record_fn is not None:
                record_fn(env.observe(), act, {"brick": -1, "ik_pos_err": 0.0, "ik_rot_err": 0.0, "hold": True})
            env.step(act)

    def placement_ok(self, i, tol_xy=0.008, tol_z=0.003, tol_yaw_deg=10.0, tol_tilt_deg=10.0):
        """Is brick i within tolerance of its design slot?  Returns (ok, reason); details in self.last_err."""
        env = self.env
        p, q = env.brick_pose(i)
        dx, dy, dz, dyaw = self.D(i)[:4]
        if env.bed_laid and dz > env.brick.H:
            dz = self.top_target_z()
        w, x, y, z = q
        yaw = np.arctan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z))
        up = np.array([2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)])   # body z axis in world
        tilt = np.degrees(np.arccos(np.clip(up[2], -1, 1)))
        dyaw_err = np.degrees(abs((yaw - dyaw + np.pi / 2) % np.pi - np.pi / 2))   # brick is 180-deg symmetric
        self._pre_kick_dxy = np.array([dx - p[0], dy - p[1]])
        self.last_err = {"exy_mm": round(1000 * float(np.hypot(p[0] - dx, p[1] - dy)), 2), "ez_mm": round(1000 * float(p[2] - dz), 2),
                         "eyaw_deg": round(float(dyaw_err), 1), "tilt_deg": round(float(tilt), 1)}
        if tilt > 45:
            return False, "toppled"
        if np.hypot(p[0] - dx, p[1] - dy) > tol_xy:
            return False, "xy"
        if abs(p[2] - dz) > tol_z:
            return False, "z"
        if dyaw_err > tol_yaw_deg:
            return False, "yaw"
        if tilt > tol_tilt_deg:
            return False, "tilt"
        return True, "ok"

    def top_target_z(self):
        """Centre height for the top brick once the bed is laid: on the real bed surface (privileged, like a mason's eye)."""
        env = self.env
        if not getattr(env, "bed_laid", False):
            return env.design[-1][2]
        tops = [env.data.mocap_pos[env.bed_mocap[kk]][2] + env.cfg.wall.bed_joint / 2 for kk in range(2)]
        return float(np.mean(tops)) + env.brick.H / 2

    # ---------------------------------------------------------------- execution
    def run_episode(self, record_fn=None, max_ik_err=0.004):
        """Execute all bricks with recovery. record_fn(obs, action_clean, info) is called every control step.

        Per brick: (optional disturbance before the pick) -> pick & place -> (optional disturbance right after
        release) -> check the placement; if it is off, re-plan from the brick's *current* pose and do it again
        (up to max_retries).  A toppled brick cannot be righted by this gripper and is logged as unrecoverable.
        Returns the number of IK-error steps; details in self.events / self.recoveries / self.unrecoverable.
        """
        env = self.env
        self.dt = env.cfg.ctrl_dt
        self.q_prev = env.data.qpos[env.arm_qidx].copy()
        p_prev, R_prev = env.tcp_pose()
        self.p_prev = p_prev
        self.yaw_prev = float(np.arctan2(R_prev[1, 0], R_prev[0, 0]))
        self.jaw_prev = JAW_OPEN
        self.n_fail = 0
        self.events, self.recoveries, self.unrecoverable = [], 0, []
        self.place_bias = {}
        # Canonical, observable laying order: bricks are identical, so the policy can only imitate a rule it can
        # see.  Nearest to the wall (smallest x) first; the k-th picked brick goes to design slot k.  (Picking by
        # brick id made the same scene demonstrate three different first picks -> multimodal, unlearnable.)
        self.order = sorted(range(env.n_bricks), key=lambda b: env.brick_pose(b)[0][0])
        self.slot = {b: k for k, b in enumerate(self.order)}

        def may_kick():   # disturbances only on first attempts and at most max_kicks per episode (no cascades)
            return (self.disturb_prob > 0 and len(self.events) < self.max_kicks
                    and self.rng.random() < self.disturb_prob)

        for i in self.order:
            for attempt in range(1 + self.max_retries):
                if attempt == 0 and may_kick():
                    self.events.append({"when": "before_pick", **self.kick_brick(i, record_fn, speed=(0.3, 0.45))})
                    ok, why = self.placement_ok(i)
                    if why == "toppled":
                        self.unrecoverable.append(i)
                        break
                segs = self.plan_brick(i)
                self._run_segments(segs[:4], i, record_fn, max_ik_err)          # pre-grasp .. lift
                p_b, _ = env.brick_pose(i)
                if p_b[2] < env.brick.H * 0.9 + (self.top_target_z() - env.brick.H / 2 if self.slot[i] == env.n_bricks - 1 and env.bed_laid else 0.0) * 0:
                    # the brick did not come up with the hand (missed / knocked grasp): open, back off, try again
                    self._run_segments([(segs[3][0], segs[3][1], JAW_OPEN, 0.3 / self.speed, "lin")], i, record_fn, max_ik_err)
                    self.log.append({"brick": int(i), "attempt": attempt, "ok": False, "why": "grasp", "t": int(env.t)})
                    if attempt == self.max_retries:
                        self.unrecoverable.append(i)
                        break
                    self.recoveries += 1
                    continue
                self._run_segments(segs[4:], i, record_fn, max_ik_err)          # transport .. retreat
                ok0, why0 = self.placement_ok(i)                                # the placement itself
                err0 = dict(self.last_err)
                kicked = False
                if attempt == 0 and may_kick():
                    self.events.append({"when": "after_place", **self.kick_brick(i, record_fn)})
                    kicked = True
                ok, why = self.placement_ok(i)
                self.log.append({"brick": int(i), "attempt": attempt, "ok": bool(ok), "why": why, "t": int(env.t),
                                 "placed_ok": bool(ok0), "placed_why": why0, "kicked": kicked, **err0})
                if ok:
                    break
                if why == "toppled" or attempt == self.max_retries:
                    self.unrecoverable.append(i)
                    break
                self.recoveries += 1
                if not ok0:
                    # learn from the failed placement (pre-kick pose): cancel the xy error (capped); if the brick
                    # rode up on a neighbour ('z' / 'tilt') aim a further 2 mm away from that neighbour
                    b = np.array(self.place_bias.get(i, (0.0, 0.0)))
                    if why0 in ("z", "tilt") and self.D(i)[2] < env.brick.H:
                        others = [self.D(j)[0] for j in range(env.n_bricks) if j != i and self.D(j)[2] < env.brick.H]
                        if others:
                            b[0] += 0.002 * np.sign(self.D(i)[0] - min(others, key=lambda x: abs(x - self.D(i)[0])))
                    elif why0 == "xy":
                        b += np.clip(self._pre_kick_dxy, -0.004, 0.004)
                    self.place_bias[i] = tuple(b)
        return self.n_fail

    def _run_segments(self, segs, i, record_fn, max_ik_err):
        env = self.env
        dt = self.dt
        q_prev, p_prev, yaw_prev, jaw_prev = self.q_prev, self.p_prev, self.yaw_prev, self.jaw_prev
        for (tp, tyaw, tjaw, dur, mode) in segs:
            n_steps = max(1, int(round(dur / dt)))
            tp = np.asarray(tp, dtype=np.float64)
            # unwrap yaw to be near previous
            tyaw = yaw_prev + (tyaw - yaw_prev + np.pi) % (2 * np.pi) - np.pi
            p_cmd = tp.copy()
            yaw_cmd = tyaw
            for s in range(1, n_steps + 1):
                a = smoothstep(s / n_steps)
                if mode == "servo":
                    # integrate the measured error into the commanded target (gain 0.6/step): the carried brick's
                    # xy error to its target (the in-hand offset is the dominant error) and the TCP's z error
                    p_meas, _ = env.tcp_pose()
                    p_b, _ = env.brick_pose(i)
                    err = np.r_[self._brick_target[:2] - p_b[:2], tp[2] - p_meas[2]]
                    p_cmd = p_cmd + 0.6 * err
                    p_t = p_cmd.copy()
                    # and the brick's yaw (180-deg symmetric): a 3 deg yaw error swings a brick end by 2.7 mm
                    _, q_b = env.brick_pose(i)
                    yaw_b = np.arctan2(2 * (q_b[0] * q_b[3] + q_b[1] * q_b[2]), 1 - 2 * (q_b[2] ** 2 + q_b[3] ** 2))
                    e_yaw = (self._brick_yaw_target - yaw_b + np.pi / 2) % np.pi - np.pi / 2
                    yaw_cmd = yaw_cmd + 0.6 * e_yaw
                else:
                    p_t = self._interp(p_prev, tp, a, mode)
                yaw_t = yaw_cmd if mode == "servo" else yaw_prev + a * (tyaw - yaw_prev)
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
                    self.n_fail += 1
                act_clean = np.r_[q_clean, jaw_t].astype(np.float32)
                act_exec = np.r_[q_exec, jaw_t]
                obs = env.observe()
                if record_fn is not None:
                    record_fn(obs, act_clean, {"brick": i, "ik_pos_err": ep, "ik_rot_err": er})
                env.step(act_exec)
                q_prev = q_clean
            p_prev, yaw_prev, jaw_prev = tp, (yaw_cmd if mode == "servo" else tyaw), tjaw
        self.q_prev, self.p_prev, self.yaw_prev, self.jaw_prev = q_prev, p_prev, yaw_prev, jaw_prev
