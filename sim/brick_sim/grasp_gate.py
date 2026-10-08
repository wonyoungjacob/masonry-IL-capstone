"""Grasp / release gate for policy rollouts (2026-09-23, revised 2026-09-28).

The learned policies never see an empty hand in the demonstrations (first-grasp-success-only data), so they carry
on with the transport whether or not the brick is in the jaw, and they release wherever the hand happens to be.
This gate watches the rollout from *outside* the policy and takes over at three moments:

1. Pick check (every time the policy closes the jaw).
   * angle only (force=False): a 42.6 mm brick stops the jaw at ~0.31 rad, an empty jaw closes to -0.12;
     HELD_MIN = 0.2 separates them.
   * angle AND load (force=True, user decision 2026-09-28): the gate lifts the hand CHECK_LIFT straight up,
     holds it still for CHECK_HOLD steps and reads the simulated wrist force sensor.  The grasp counts only if
     the jaw is still above HELD_MIN *and* the mean load beyond the gripper's own weight is >= LOAD_MIN.
     The brick's weight only shows once it is off the floor, so reading the load at the moment of closing
     is meaningless (val40: every wrong angle decision read ~0 N there).
   Held -> the policy carries on (its queue is cleared because the gate moved the arm).  Not held -> open, lift
   4 cm, optionally move above the next unplaced brick ('reguide'), clear the queue and let the policy try
   again.  max_retries <= 0 means no limit: the policy keeps trying until the episode time runs out.

2. Carry monitoring: the jaw closing further (< HELD_MIN) or, with force=True and the hand lifted, the load
   dropping to ~0 for LOAD_STEPS steps = the brick slipped out.  A strongly negative load is the arm pressing the
   held brick onto something ('pressing', logged, not a loss).

3. Release gate (release_gate=True): the policy's 'open' command while carrying is intercepted.  The held brick's
   error to its slot is measured (simulator brick pose) and servo-corrected if above REL_TOL_*, then the gate opens
   the jaw itself.  With replace=True (user decision 2026-09-28, replaces the earlier 'never touch a released
   brick' rule) the released brick is scored right away against the final acceptance tolerances; if it fails,
   the gate re-grasps it (same angle AND load check) and places it again - at most once per brick.  A toppled
   brick (tilt > 45 deg) cannot be righted by this gripper and is only recorded.  The policy itself is never
   allowed to grasp a released brick: such a close is opened again and counted as 'blocked'.

The simulator's privileged env.grasped() is logged next to every decision for auditing only; it never drives it.
Results obtained with the gate are "policy + gate", not "policy": report them separately.
"""
from __future__ import annotations

import numpy as np

from .ik import DLSIK, rot_from_down_yaw
from .scene import JAW_OPEN, JAW_CLOSED, design_poses
from .expert import grasp_pose, smoothstep, HOVER, GRASP_DZ, PLACE_CLEAR, FIXED_PAD_X, GRASP_PAD_CLEAR

CLOSE_THR = 0.5      # jaw below this = the policy is closing / has closed it
HELD_MIN = 0.2       # jaw angle (rad) above this after closing = something brick-sized is in the jaw
SETTLE_STEPS = 4     # consecutive steps with |d jaw| < SETTLE_DQ before deciding
SETTLE_DQ = 0.01
MAX_CLOSE_STEPS = 20 # decide anyway after 1 s of closing
LIFT = 0.04          # m: recovery lift (= expert HOVER)

# --- load check with the simulated wrist force/torque sensor (force=True) ---
G = 9.81
LOAD_MIN = 0.9       # N: load beyond the gripper's own weight that counts as 'a brick hangs in the jaw' (brick 1.83 N)
CHECK_LIFT = 0.015   # m: the gate lifts this much before weighing (= the expert's 15 mm lift check)
CHECK_LIFT_STEPS = 6 # 0.3 s lift
CHECK_HOLD = 5       # 0.25 s still; the load is averaged over these steps
LOAD_LIFT = 0.015    # m: carry monitoring starts once the hand is this far above the grasp height
LOAD_STEPS = 6       # consecutive steps with |load| < LOAD_MIN while carrying -> the brick slipped out
PRESS_MIN = 3.0      # N: load below -PRESS_MIN = the arm presses the held brick onto something ('pressing', not lost)

# --- release gate: verify the held brick's pose BEFORE the jaw opens ---
REL_TOL_XY = 0.0025  # m: correct before releasing above this (final tolerance 4.5 mm; ~2 mm margin for the release,
                     # at 4.5 mm five Diffusion placements drifted from 3-3.9 mm in the hand to 4.3-4.6 mm on release)
REL_TOL_YAW = 3.0    # deg (final tolerance 5 deg)
REL_TOL_Z = 0.003    # m: brick centre above its target height by more than this -> lower it first
REL_NBR_BIAS = 0.0015  # m: aim this far away from an already placed neighbour (expert.plan_brick)
REL_SERVO_S = 1.0    # s: max closed-loop correction (gain 0.6/step), stops early inside half the tolerance
REL_Z_CLEAR = 0.0015 # m: brick centre height aimed for while correcting (= expert PLACE_CLEAR)
REL_GAIN = 0.6

# --- post-release score (replace=True): the final acceptance tolerances of metrics.compute_metrics ---
POST_TOL_XY = 0.0045   # m
POST_TOL_Z = 0.003     # m: perched on a neighbour's end (final tolerance 4.5 mm; 3 mm catches it before it settles)
POST_TOL_YAW = 5.0     # deg
POST_TOL_TILT = 5.0    # deg (final tolerance 10 deg)
TOPPLED_DEG = 45.0     # beyond this the brick lies on another face: this gripper cannot right it
REPLACE_GRASP_TRIES = 3  # gate re-grasp attempts during one re-placement
BLOCK_DIST = 0.03      # m: a policy close this near a released brick is a re-grasp of it (blocked)


RECOVER_MODES = ("lift", "reguide", "expert")
# lift    : open, lift 4 cm where the hand is, hand back to the policy (it re-approaches on its own)
# reguide : open, lift, then move the hand to the expert's pre-grasp hover pose above the next unplaced brick
#           (simulator brick coordinates) and hand back: the policy still does the descend / close / lift
# expert  : the scripted expert performs the whole pick and hands back -> that pick is no longer the policy's


def _yaw(q):
    w, x, y, z = q
    return float(np.arctan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z)))


def _tilt_deg(q):
    w, x, y, z = q
    return float(np.degrees(np.arccos(np.clip(1 - 2 * (x * x + y * y), -1, 1))))


def _fold(a):
    """Angle error for a 180-deg symmetric brick, in (-pi/2, pi/2]."""
    return (a + np.pi / 2) % np.pi - np.pi / 2


def _wrap(a):
    return (a + np.pi) % (2 * np.pi) - np.pi


def _closer(yaw, ref):
    """yaw or yaw + pi, whichever needs the smaller wrist turn from ref (the brick is 180-deg symmetric)."""
    return yaw if abs(_wrap(yaw - ref)) <= abs(_wrap(yaw + np.pi - ref)) else yaw + np.pi


class GraspGate:
    def __init__(self, env, policy=None, max_retries: int = 3, held_min: float = HELD_MIN, recover: str = "lift",
                 release_gate: bool = False, force: bool = False, replace: bool = False, pose_noise: float = 0.0,
                 seed: int = 0, inspect_slots=None, nominal_plan: bool = False):
        assert recover in RECOVER_MODES, recover
        assert not replace or release_gate, "replace needs the release gate"
        self.env, self.policy, self.held_min, self.recover = env, policy, held_min, recover
        self.max_retries = max_retries if max_retries > 0 else 10 ** 9
        self.release_gate, self.force, self.replace = release_gate, force, replace
        # measurement noise on every brick pose the gate uses for correction (sensitivity to the oracle pose):
        # N(0, pose_noise) per axis on the centre, N(0, pose_noise / (L/2)) rad on yaw (same end displacement).
        # Bookkeeping (which slot is filled, which brick is nearest) stays on the true pose at its 8 mm resolution.
        self.pose_noise = float(pose_noise)
        # nominal_plan: the gate measures brick poses but computes where to put a brick from the drawing, i.e. the
        # nominal brick size and the nominal design (KICEM 2026 size-tolerance study).  Grasp geometry stays measured.
        self.nominal_plan = bool(nominal_plan)
        self._rng = np.random.default_rng(seed)
        self._g_weight = env.gripper_mass() * G
        self._carry_z, self._low_load, self._pressing = None, 0, False
        self.ik = DLSIK(env.model, env.tcp_site, env.arm_qidx, env.arm_dofidx)
        self.events, self.retries, self.aborted, self.done = [], 0, False, False
        self.release_events = []
        self._closing, self._settled, self._prev_jaw, self._carrying = 0, 0, None, False
        self._held_brick = None
        self._released, self._replaced = set(), set()
        # design slots the release gate inspects (G2 correction, G3 score/re-place); None = every slot.  A brick bound
        # for another slot is released by the policy itself, unmeasured, and still may not be re-grasped afterwards.
        self.inspect_slots = None if inspect_slots is None else {int(k) for k in inspect_slots}

    # ------------------------------------------------------------------ sensing helpers
    def load(self):
        """Vertical load hanging below the wrist beyond the gripper's own weight (N, world z; simulated sensor)."""
        F, _ = self.env.wrist_ft()
        return float(F[2] - self._g_weight)

    def pose(self, i):
        """Brick i's pose as the gate measures it (true pose + optional noise): (xyz, quat wxyz)."""
        p, q = self.env.brick_pose(i)
        if self.pose_noise <= 0:
            return p, q
        p = p + self._rng.normal(0.0, self.pose_noise, 3)
        dyaw = self._rng.normal(0.0, self.pose_noise / (self.env.brick.L / 2))
        dq = np.array([np.cos(dyaw / 2), 0.0, 0.0, np.sin(dyaw / 2)])
        w1, x1, y1, z1 = dq; w2, x2, y2, z2 = q
        q = np.array([w1*w2 - x1*x2 - y1*y2 - z1*z2, w1*x2 + x1*w2 + y1*z2 - z1*y2,
                      w1*y2 - x1*z2 + y1*w2 + z1*x2, w1*z2 + x1*y2 - y1*x2 + z1*w2])
        return p, q

    def jaw(self):
        return float(self.env.data.qpos[self.env.jaw_qidx])

    def _nearest_brick(self):
        tcp = self.env.tcp_pose()[0]
        d = [np.linalg.norm(self.env.brick_pose(i)[0] - tcp) for i in range(self.env.n_bricks)]
        return int(np.argmin(d)), float(min(d))

    def _sim_grasped(self):
        return bool(any(self.env.grasped(i) for i in range(self.env.n_bricks)))

    def unplaced(self):
        """Bricks the policy may still pick: not cured, not in a slot, never released on the wall (expert order)."""
        env = self.env
        free = [i for i in range(env.n_bricks)
                if not env.cured[i] and env.brick_in_slot(i) is None and i not in self._released]
        return sorted(free, key=lambda b: env.brick_pose(b)[0][0])

    # ------------------------------------------------------------------ motion helpers
    def _act(self, like=None, jaw=None):
        env = self.env
        act = np.asarray(like if like is not None else env.data.ctrl[env.act_ids], dtype=np.float32).copy()
        act[:5] = env.data.qpos[env.arm_qidx]
        if jaw is not None:
            act[5] = jaw
        return act

    def _lift(self, act, dz, n_steps):
        """Move the TCP straight up by dz over n_steps with the current yaw (jaw command unchanged)."""
        env = self.env
        q = np.asarray(env.data.qpos[env.arm_qidx], dtype=np.float64).copy()
        p, R = env.tcp_pose(); Rt = rot_from_down_yaw(float(np.arctan2(R[1, 0], R[0, 0])))
        for s in range(1, n_steps + 1):
            q, _, _ = self.ik.solve(q, p + np.array([0.0, 0.0, dz * smoothstep(s / n_steps)]), Rt, env.data.qpos.copy())
            act[:5] = q
            env.step(act)

    def _hold(self, act, n):
        for _ in range(n):
            self.env.step(act)

    def _segments(self, segs, act):
        """Expert-style Cartesian segments (target, yaw, jaw, duration, mode) -> IK -> env.step."""
        env = self.env
        q = np.asarray(env.data.qpos[env.arm_qidx], dtype=np.float64).copy()
        p_prev, R = env.tcp_pose(); yaw_prev = float(np.arctan2(R[1, 0], R[0, 0])); jaw_prev = float(act[5])
        for tp, tyaw, tjaw, dur, mode in segs:
            n = max(1, int(round(dur / env.cfg.ctrl_dt))); tp = np.asarray(tp, dtype=np.float64)
            tyaw = yaw_prev + (tyaw - yaw_prev + np.pi) % (2 * np.pi) - np.pi
            for s in range(1, n + 1):
                a = smoothstep(s / n)
                if mode == "polar":
                    r0, r1 = np.hypot(*p_prev[:2]), np.hypot(*tp[:2]); t0, t1 = np.arctan2(p_prev[1], p_prev[0]), np.arctan2(tp[1], tp[0])
                    dt = (t1 - t0 + np.pi) % (2 * np.pi) - np.pi; r, th = r0 + a * (r1 - r0), t0 + a * dt
                    p_t = np.array([r * np.cos(th), r * np.sin(th), p_prev[2] + a * (tp[2] - p_prev[2])])
                else:
                    p_t = p_prev + a * (tp - p_prev)
                yaw_t = yaw_prev + a * (tyaw - yaw_prev)
                q, _, _ = self.ik.solve(q, p_t, rot_from_down_yaw(yaw_t), env.data.qpos.copy())
                act[:5] = q; act[5] = jaw_prev + a * (tjaw - jaw_prev)
                env.step(act)
            p_prev, yaw_prev, jaw_prev = tp, tyaw, tjaw

    # ------------------------------------------------------------------ pick check
    def _weigh(self, act):
        """Lift CHECK_LIFT with the jaw kept closed, hold still, return (jaw angle, mean load)."""
        act[5] = JAW_CLOSED
        self._lift(act, CHECK_LIFT, CHECK_LIFT_STEPS)
        loads = []
        for _ in range(CHECK_HOLD):
            self.env.step(act)
            loads.append(self.load())
        return self.jaw(), float(np.mean(loads))

    def _check_pick(self, act):
        """Pick verdict for the jaw closed where the hand is: (held, info).  force=False: angle only."""
        jaw0 = self.jaw()
        if not self.force:
            return jaw0 > self.held_min, {"jaw": round(jaw0, 3), "load_N": round(self.load(), 3)}
        jaw1, load = self._weigh(act)
        jaw_ok, load_ok = jaw1 > self.held_min, load >= LOAD_MIN
        return jaw_ok and load_ok, {"jaw": round(jaw1, 3), "jaw_at_close": round(jaw0, 3), "load_N": round(load, 3),
                                    "jaw_ok": bool(jaw_ok), "load_ok": bool(load_ok)}

    def _recover(self, last_action):
        """Open the jaw where it is, lift LIFT straight up, optionally move above the next brick; clear the queue."""
        act = self._act(last_action, JAW_OPEN)
        self._hold(act, 6)                   # 0.3 s: open in place
        self._lift(act, LIFT, 10)            # 0.5 s: lift
        self._hold(act, 4)                   # 0.2 s: still, so the re-observation is still
        if self.recover in ("reguide", "expert"):
            self._reguide(act, full=self.recover == "expert")
        self._prev_jaw, self._closing, self._settled = None, 0, 0
        if self.policy is not None:
            self.policy.reset()

    def _reguide(self, act, full=False):
        """Move to the expert pre-grasp pose above the next unplaced brick; with full=True also pick it up."""
        free = self.unplaced()
        if not free:
            return
        i = free[0]
        g, yaw, _ = self._grasp_target(i)
        gx, gy, gz = g
        segs = [((gx, gy, gz + HOVER), yaw, JAW_OPEN, 1.0, "polar")]
        if full:
            segs += [((gx, gy, gz), yaw, JAW_OPEN, 0.6, "lin"), ((gx, gy, gz), yaw, JAW_CLOSED, 0.4, "lin"),
                     ((gx, gy, gz + HOVER), yaw, JAW_CLOSED, 0.5, "lin")]
        self._segments(segs, act)
        self.events[-1]["reguide_brick"] = int(i)

    # ------------------------------------------------------------------ main hook after every policy step
    def after_step(self, last_action) -> str:
        """Call after every env.step(action) of the policy.  Returns 'pass' | 'held' | 'retry' | 'abort' | 'done'."""
        env = self.env
        jaw = self.jaw()
        settled = self._prev_jaw is not None and abs(jaw - self._prev_jaw) < SETTLE_DQ
        self._prev_jaw = jaw
        if jaw > CLOSE_THR:                  # jaw open: re-arm (also after a release)
            self._closing, self._settled, self._carrying = 0, 0, False
            return "pass"
        if self._carrying:
            lost_why = self._carry_monitor(jaw)
            if lost_why is None:
                return "pass"
            self._carrying, self._low_load = False, 0
            self.events.append({"t": int(env.t), "jaw": round(jaw, 3), "held": False, "action": "lost", "why": lost_why,
                                "load_N": round(self.load(), 3), "sim_grasped": self._sim_grasped(), "retry": self.retries})
            self._closing = MAX_CLOSE_STEPS   # decide on this step
        self._closing += 1
        self._settled = self._settled + 1 if settled else 0
        if self._settled < SETTLE_STEPS and self._closing < MAX_CLOSE_STEPS:
            return "pass"
        self._closing, self._settled = 0, 0
        b, dist = self._nearest_brick()
        ev = {"t": int(env.t), "nearest_brick": b, "dist_m": round(dist, 4), "retry": self.retries}
        if b in self._released and dist < BLOCK_DIST:
            # the policy closed on a brick already laid on the wall: not its to re-grasp (only the gate re-places)
            ev.update(jaw=round(jaw, 3), held=False, sim_grasped=self._sim_grasped(), action="blocked")
            self.events.append(ev)
            self._recover(last_action)
            return "retry"
        if jaw <= self.held_min and not self.unplaced():   # closed on nothing and nothing left to pick: done
            ev.update(jaw=round(jaw, 3), held=False, sim_grasped=self._sim_grasped(), action="done")
            self.events.append(ev); self.done = True
            return "done"
        act = self._act(last_action)
        held, info = self._check_pick(act)
        ev.update(info, held=bool(held), sim_grasped=self._sim_grasped())
        if held:
            self._carrying, self._held_brick = True, b
            self._carry_z, self._low_load, self._pressing = float(env.tcp_pose()[0][2]) - (CHECK_LIFT if self.force else 0.0), 0, False
            ev["action"] = "carry"; self.events.append(ev)
            if self.force and self.policy is not None:
                self.policy.reset()          # the gate moved the arm: queued actions would push it back down
            self._prev_jaw = None
            return "held"
        if not self.unplaced():
            ev["action"] = "done"; self.events.append(ev); self.done = True
            return "done"
        if self.retries >= self.max_retries:
            ev["action"] = "abort"; self.events.append(ev); self.aborted = True
            return "abort"
        ev["action"] = "recover:" + self.recover; self.events.append(ev)
        self.retries += 1
        self._recover(last_action)
        return "retry"

    def _carry_monitor(self, jaw):
        """None while the carried brick is still in the jaw, else the reason it is considered lost."""
        env = self.env
        if jaw < self.held_min:              # the jaw closed further: the brick slipped out
            return "jaw"
        if not self.force or env.tcp_pose()[0][2] - self._carry_z < LOAD_LIFT:
            return None
        ld = self.load()
        if ld < -PRESS_MIN:                  # pushing the held brick onto something: contact, not an empty jaw
            if not self._pressing:
                self.events.append({"t": int(env.t), "jaw": round(jaw, 3), "held": True, "action": "pressing",
                                    "load_N": round(ld, 3), "sim_grasped": bool(env.grasped(self._held_brick)),
                                    "retry": self.retries})
            self._pressing, self._low_load = True, 0
            return None
        self._pressing = False
        self._low_load = self._low_load + 1 if abs(ld) < LOAD_MIN else 0
        return "load" if self._low_load >= LOAD_STEPS else None

    # ------------------------------------------------------------------ release gate
    def _next_slot(self, held):
        """The design slot the held brick should go to: lowest unfilled slot in the expert's order (0, 1, then top)."""
        env = self.env
        filled = {env.brick_in_slot(j) for j in range(env.n_bricks) if j != held}
        for k in range(len(env.design)):
            if k not in filled:
                return k
        return None

    def _plan(self):
        """(design, brick) the gate plans with: the true ones, or the drawing's nominal ones (nominal_plan)."""
        env = self.env
        if not self.nominal_plan:
            return env.design, env.brick
        return design_poses(env.cfg, env.cfg.brick), env.cfg.brick

    def _slot_target(self, k, held):
        """Where brick `held` should end up in slot k: lower course butted against the neighbour as it actually lies
        (plus REL_NBR_BIAS), top brick on the laid bed.  Returns (xyz, yaw)."""
        env = self.env
        D, B = self._plan()
        dx, dy, dz, dyaw = D[k][:4]
        if dz < B.H:
            for kk in range(len(D)):
                if kk == k or D[kk][2] >= B.H:
                    continue
                nb = [j for j in range(env.n_bricks) if j != held and env.brick_in_slot(j, [kk]) is not None]
                if nb:
                    sgn = np.sign(dx - D[kk][0])
                    dx = self.pose(nb[0])[0][0] + sgn * (B.L + env.cfg.wall.head_gap + REL_NBR_BIAS)
        if getattr(env, "bed_laid", False) and dz > B.H:
            tops = [env.data.mocap_pos[env.bed_mocap[kk]][2] + env.cfg.wall.bed_joint / 2 for kk in range(2)]
            dz = float(np.mean(tops)) + B.H / 2
        return np.array([dx, dy, dz]), float(dyaw)

    def _brick_err(self, i, target, dyaw):
        p, q = self.pose(i)
        return target[:2] - p[:2], float(_fold(dyaw - _yaw(q))), float(p[2] - target[2])

    def _score(self, i, k):
        """Released brick i against the nominal design slot k (what the final metric scores)."""
        env = self.env
        p, q = self.pose(i)
        dx, dy, dz, dyaw = self._plan()[0][k][:4]
        s = {"exy_mm": round(1000 * float(np.hypot(p[0] - dx, p[1] - dy)), 2), "ez_mm": round(1000 * float(p[2] - dz), 2),
             "eyaw_deg": round(float(np.degrees(_fold(_yaw(q) - dyaw))), 2), "tilt_deg": round(_tilt_deg(q), 2),
             "in_slot": env.brick_in_slot(i) is not None}
        s["ok"] = bool(s["exy_mm"] <= 1000 * POST_TOL_XY and abs(s["ez_mm"]) <= 1000 * POST_TOL_Z
                       and abs(s["eyaw_deg"]) <= POST_TOL_YAW and s["tilt_deg"] <= POST_TOL_TILT)
        return s

    def before_step(self, action):
        """Call before env.step(action).  Intercepts the policy's release while carrying (release gate); returns the
        action to execute, or None when the gate executed this step itself."""
        if not self.release_gate or not self._carrying or self._held_brick is None:
            return action
        if float(action[5]) < CLOSE_THR:
            return action
        i = self._held_brick
        k = self._next_slot(i)
        if k is None:
            return action
        if self.inspect_slots is not None and k not in self.inspect_slots:
            self.release_events.append({"t": int(self.env.t), "brick": int(i), "slot": int(k), "inspected": False})
            self._released.add(i)
            return action                    # the policy opens the jaw; after_step re-arms on the open jaw
        act = self._act(action, JAW_CLOSED)
        ev = self._release(i, k, act)
        if self.replace and not ev["post_release"]["ok"] and i not in self._replaced:
            if ev["post_release"]["tilt_deg"] > TOPPLED_DEG:
                ev["replace"] = "toppled"
            else:
                self._replaced.add(i)
                ev["replace"] = self._replace(i, k, act)
        self.release_events.append(ev)
        self._lift(act, LIFT, 10)
        self._released.add(i)
        self._carrying, self._held_brick, self._prev_jaw, self._closing, self._settled = False, None, None, 0, 0
        if self.policy is not None:
            self.policy.reset()
        return None

    def _release(self, i, k, act):
        """Servo-correct the held brick if needed, open the jaw, score the released brick."""
        env = self.env
        target, dyaw = self._slot_target(k, i)
        exy, eyaw, ez = self._brick_err(i, target, dyaw)
        ev = {"t": int(env.t), "brick": int(i), "slot": int(k), "exy_mm": round(1000 * float(np.hypot(*exy)), 2),
              "eyaw_deg": round(float(np.degrees(eyaw)), 2), "ez_mm": round(1000 * ez, 2), "load_N": round(self.load(), 3)}
        corrected = np.hypot(*exy) > REL_TOL_XY or abs(np.degrees(eyaw)) > REL_TOL_YAW or ez > REL_TOL_Z
        if corrected:
            self._servo(i, target, dyaw, act)
            exy2, eyaw2, ez2 = self._brick_err(i, target, dyaw)
            ev.update(exy_after_mm=round(1000 * float(np.hypot(*exy2)), 2), eyaw_after_deg=round(float(np.degrees(eyaw2)), 2),
                      ez_after_mm=round(1000 * ez2, 2))
        ev["corrected"] = bool(corrected)
        q = np.asarray(env.data.qpos[env.arm_qidx], dtype=np.float64).copy()
        for s in range(1, 9):                # open in place
            act[:5] = q; act[5] = JAW_CLOSED + smoothstep(s / 8) * (JAW_OPEN - JAW_CLOSED)
            env.step(act)
        self._hold(act, 6)                   # 0.3 s: let it settle before scoring (cure needs 2 s with the hand away)
        ev["post_release"] = self._score(i, k)
        ev["bad_release"] = not ev["post_release"]["ok"]
        return ev

    def _servo(self, i, target, dyaw, act, hold_z=False):
        """Expert 'servo': integrate the brick's xy / yaw error into the TCP command.  hold_z keeps the TCP height;
        otherwise the brick is only lowered toward REL_Z_CLEAR above its target (never pushed into the bed)."""
        env = self.env
        n = max(1, int(round(REL_SERVO_S / env.cfg.ctrl_dt)))
        p_cmd, R = env.tcp_pose(); p_cmd = p_cmd.copy(); yaw_cmd = float(np.arctan2(R[1, 0], R[0, 0])); z0 = p_cmd[2]
        q = np.asarray(env.data.qpos[env.arm_qidx], dtype=np.float64).copy()
        for _ in range(n):
            exy, eyaw, ez = self._brick_err(i, target, dyaw)
            if np.hypot(*exy) < REL_TOL_XY / 2 and abs(np.degrees(eyaw)) < REL_TOL_YAW / 2 and (hold_z or ez < REL_TOL_Z):
                break
            if hold_z:
                p_meas, _ = env.tcp_pose()
                dz = z0 - p_meas[2]
            else:
                dz = min(0.0, REL_Z_CLEAR - ez)
            p_cmd = p_cmd + REL_GAIN * np.r_[exy, dz]
            yaw_cmd = yaw_cmd + REL_GAIN * eyaw
            q, _, _ = self.ik.solve(q, p_cmd, rot_from_down_yaw(yaw_cmd), env.data.qpos.copy())
            act[:5] = q; act[5] = JAW_CLOSED
            env.step(act)

    # ------------------------------------------------------------------ one re-placement of a badly released brick
    def _grasp_target(self, i):
        """Expert grasp pose for brick i as it lies now (full-quaternion yaw, so a perched / tilted brick works too)."""
        env = self.env
        p, q = self.pose(i)
        _, R = env.tcp_pose()
        yaw_g = _closer(_yaw(q) + np.pi / 2, float(np.arctan2(R[1, 0], R[0, 0])))
        dz_grip = GRASP_DZ + max(0.0, (env.brick.H - 0.016) / 2)
        d_off = max(0.0, env.brick.W / 2 - FIXED_PAD_X) + GRASP_PAD_CLEAR
        return np.array([p[0] + d_off * np.cos(yaw_g), p[1] + d_off * np.sin(yaw_g), p[2] + dz_grip]), yaw_g, dz_grip

    def _replace(self, i, k, act):
        """Re-grasp brick i (angle AND load check, up to REPLACE_GRASP_TRIES) and place it in slot k again."""
        env = self.env
        act[5] = JAW_OPEN
        self._lift(act, LIFT, 10)
        verdicts = []
        for _ in range(REPLACE_GRASP_TRIES):
            g, yaw_g, dz_grip = self._grasp_target(i)
            self._segments([(g + np.array([0, 0, HOVER]), yaw_g, JAW_OPEN, 0.8, "lin"),
                            (g, yaw_g, JAW_OPEN, 0.6, "lin"), (g, yaw_g, JAW_CLOSED, 0.4, "lin")], act)
            jaw1, load = self._weigh(act)
            ok = jaw1 > self.held_min and (load >= LOAD_MIN or not self.force)
            verdicts.append({"jaw": round(jaw1, 3), "load_N": round(load, 3), "ok": bool(ok), "sim_grasped": bool(env.grasped(i))})
            if ok:
                break
            act[5] = JAW_OPEN
            self._hold(act, 6)
            self._lift(act, LIFT, 10)
        else:
            return {"result": "grasp_failed", "grasps": verdicts}
        # carry: up to hover, over the slot with the expert's in-hand offset, align in the air, descend, release
        self._lift(act, HOVER - CHECK_LIFT, 10)
        target, dyaw = self._slot_target(k, i)
        _, R = env.tcp_pose()
        # the brick hangs on the fixed-jaw side: keep the jaw side the brick was grasped with, i.e. the placing yaw is
        # the grasp yaw turned by the brick's required rotation (not freely flipped by 180 deg)
        yaw_p = yaw_g + _fold(dyaw - _yaw(self.pose(i)[1]))
        d_off = max(0.0, env.brick.W / 2 - FIXED_PAD_X)
        pz = target[2] + dz_grip + PLACE_CLEAR
        hover = np.array([target[0] + d_off * np.cos(yaw_p), target[1] + d_off * np.sin(yaw_p), pz + HOVER])
        self._segments([(hover, yaw_p, JAW_CLOSED, 1.2, "polar")], act)
        self._servo(i, target, dyaw, act, hold_z=True)
        p_b = self.pose(i)[0]; tcp = env.tcp_pose()[0]
        down = tcp + np.array([0.0, 0.0, (target[2] + PLACE_CLEAR) - p_b[2]])
        _, R = env.tcp_pose()
        self._segments([(down, float(np.arctan2(R[1, 0], R[0, 0])), JAW_CLOSED, 0.7, "lin")], act)
        ev2 = self._release(i, k, act)
        return {"result": "ok" if ev2["post_release"]["ok"] else "still_bad", "grasps": verdicts, "second_release": ev2}

    # ------------------------------------------------------------------ report
    def summary(self):
        ev, rel = self.events, self.release_events
        return {"gate_events": ev, "gate_retries": self.retries, "gate_abort": self.aborted, "gate_done": self.done,
                "release_gate": self.release_gate, "force_gate": self.force, "replace_gate": self.replace,
                "pose_noise_m": self.pose_noise,
                "release_events": rel, "gate_recover_mode": self.recover,
                "gate_lost": sum(e["action"] == "lost" for e in ev),
                "gate_lost_by_load": sum(e.get("why") == "load" for e in ev),
                "gate_pressing": sum(e["action"] == "pressing" for e in ev),
                "gate_blocked": sum(e["action"] == "blocked" for e in ev),
                "gate_verified_grasps": sum(e["action"] == "carry" for e in ev),
                "gate_rejected_by_load": sum(1 for e in ev if e.get("jaw_ok") and not e.get("load_ok", True)),
                "gate_rejected_by_angle": sum(1 for e in ev if e.get("load_ok") and not e.get("jaw_ok", True)),
                "gate_decisions_vs_sim": sum(e["held"] != e["sim_grasped"] for e in ev if "held" in e),
                "release_corrected": sum(e.get("corrected", False) for e in rel),
                "bad_releases": sum(e.get("bad_release", False) for e in rel),
                "release_uninspected": sum(e.get("inspected") is False for e in rel),
                "replaced": sum(1 for e in rel if isinstance(e.get("replace"), dict)),
                "replaced_ok": sum(1 for e in rel if isinstance(e.get("replace"), dict) and e["replace"]["result"] == "ok"),
                "replace_toppled": sum(1 for e in rel if e.get("replace") == "toppled")}
