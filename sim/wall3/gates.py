"""정책 밖 검측 G1 · G2 · G3 (3단 벽, 2026-10-20; 실험설계 md 1 · 3절, 소형 실험 brick_sim/grasp_gate.py를 옮김).

정책을 밖에서 지켜보다가 세 순간에만 개입한다. 판단에는 로봇이 실제로 가진 정보만 쓴다:
관절값(순기구학), 손목 힘 센서, 집게 각도, 작업대 위 카메라(top 고해상도 RGB-D, wall3/perception.py), 도면(설계 자리 · 벽돌 크기 ·
작업 순서). **시뮬레이터 참값은 판단에 쓰지 않고**, 기록(측정 오차 · 모르타르 경화 여부)에만 쓴다.

G1 들기 확인 (wall3/g1.py): 집게를 닫고 1.5 cm 들면 멈춰 손목 하중 · 집게 각도로 쥠 판정. 못 쥐었으면 열고 정책을 reset해 다시 집게 함.
G2 놓기 전 보정: '쥐고 있음' 상태에서 정책이 집게를 풀기 시작하면(명령이 쥠 명령보다 내려감) 가로챈다. 자리 위 10 cm로 올려
   쥔 벽돌을 카메라로 잰 뒤(이웃 벽돌과 높이로 구분), 벽돌이 설계 자리 · 방향에 오도록 손을 옮기고, 받침 위 0.5 mm까지 내려 놓는다.
G3 놓은 뒤 재검사: 놓은 직후 팔을 벽 위에서 비켜(로봇 쪽으로) 놓인 벽돌을 잰다. 허용치를 넘으면 모르타르가 굳기 전에(손이 5 cm 밖에서
   2 s 정지하면 굳음) 한 번 다시 집어 G2 방식으로 다시 놓는다(벽돌당 1회).
G2를 끄고 G3만 켜면 놓는 순간 가로채 그 자리에서 그대로 놓은 뒤(보정 없음) G3를 한다.

동작은 대본(wall3/expert.py)의 이동 함수(역동역학 피드포워드 포함)를 그대로 쓴다. 검측 동작 시간도 벽돌당 시간 제한(17 s)에 들어간다.
문턱 · 허용치는 임시값(검증 배치로 정해 동결 전). 결과는 '정책 + 검측'으로 따로 보고한다.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict

import numpy as np

from wall3 import gripper as G
from wall3.config import H, W, JOINT
from wall3.expert import WallExpert
from wall3.g1 import G1, G1Config, G1Trigger
from wall3.ik import down_R, wrap
from wall3.poses import yaw_of_quat
from wall3.perception import BrickPoseEstimator, _fold


@dataclass
class GateConfig:
    near_slot: float = 0.15          # m: TCP within this (xy) of the brick's design slot = a release meant for that slot
    release_drop: float = 0.02       # rad: grip command this far below the holding command = the policy starts to release
    view_up: float = 0.25            # m: G2 measures the held brick this high above its place height (clear of neighbours;
                                     #    2026-10-20: at 0.10 the elbow hid 3 / 16 slots, at 0.25 all 16 were seen, <= 1.9 mm)
    view_shift: float = 0.035        # m: second / third G2 view shifted along the jaw axis when no brick end was visible
    place_gap: float = 0.0005        # m: brick bottom above its support when released (expert)
    g2_tol_xy: float = 0.0015        # m: after moving, re-measure; correct again above this (once)
    g3_view_back: float = 0.38       # m: G3 views the laid brick with the TCP this far toward the robot (arm off the wall strip)
    g3_view_up: float = 0.25         # m: ... and this high above the brick top (2026-10-20: 0.22 / 0.12 left 2.5 mm errors)
    g3_tol_xy: float = 0.003         # m: re-place above this (임시; 시방 ④ 등에서 벽돌 단위 기준을 유도해 검증 배치로 동결 예정)
    g3_tol_yaw_deg: float = 1.5
    g3_tol_z: float = 0.002          # m: brick centre above its place height by more than this (perched)
    g3_tol_tilt_deg: float = 2.0
    g3_partial_margin: float = 0.003  # m: a partial view (up to ~2.5 mm error) decides 'bad' only beyond tol + this
    min_time_left_s: float = 0.0     # G3 re-placement only if this much of the brick time limit is left (0 = always; 예비 확인 2026-10-20)

    def to_dict(self):
        return asdict(self)


class WallGates:
    def __init__(self, env, policy=None, g1: bool = False, g2: bool = False, g3: bool = False,
                 g1_cfg: G1Config | None = None, cfg: GateConfig | None = None, on_frame=None):
        self.env, self.policy = env, policy
        self.on_g1, self.on_g2, self.on_g3 = bool(g1), bool(g2), bool(g3)
        self.cfg = cfg or GateConfig()
        self.g1cfg = g1_cfg or G1Config(thr_load=4.5, thr_angle=0.47)   # 임시 문턱 (나4 분포의 가운데)
        self.g1 = G1(env, self.g1cfg) if g1 else None
        self.cam = BrickPoseEstimator(env) if (g2 or g3) else None
        self.ex = WallExpert(env)                       # motion primitives only (IK + feed-forward), never its plan
        self.ex._watch = lambda held, phase: None        # gate motions are not aborted on contact
        self.dt = env.cfg.ctrl_dt
        self.on_frame = on_frame
        self.ex.on_step = (lambda e, a, ph, k: on_frame(ph, k)) if on_frame else None
        self.trig = G1Trigger(self.g1cfg, self.dt)
        self.replaced = set()
        self._t_release = None
        self.debug_dir = None

    # ------------------------------------------------------------------ per brick
    def start_brick(self, k, deadline_t):
        self.k, self.deadline = k, deadline_t
        self.carrying, self.hold_cmd = False, None
        self.trig.reset()
        self.ev = {"g1": [], "g2": [], "g3": []}
        self.z_start = [self.env.brick_pose(j)[0][2] for j in range(self.env.n)]      # audit only

    def end_brick(self):
        return self.ev

    def _time_left(self):
        return (self.deadline - self.env.t) * self.dt

    def _audit(self, k):
        """Ground truth for the log only."""
        p, q = self.env.brick_pose(k)
        return p, yaw_of_quat(q)

    def _design(self, k):
        s = self.env.design[k]
        return np.array([s["x"], s["y"]]), float(s["yaw"]), s["L"], s

    # ------------------------------------------------------------------ hooks around the policy's step
    def before(self, act):
        """Called with the policy's action before it is executed. True = the gate handled the step(s) itself."""
        if not self.carrying or self.hold_cmd is None:
            return False
        if float(act[6]) >= self.hold_cmd - self.cfg.release_drop:
            return False
        p, _ = self.env.tcp()
        xy, _, _, _ = self._design(self.k)
        if float(np.hypot(*(p[:2] - xy))) > self.cfg.near_slot or not (self.on_g2 or self.on_g3):
            self.carrying = False                         # a release elsewhere (or no G2/G3): the policy does it
            return False
        self.carrying = False
        if self.on_g2:
            self._g2_place(self.k, self.hold_cmd, measure=True)
        else:
            self._release_here(self.k, self.hold_cmd)      # G3 only: release where the policy is, no correction
        if self.on_g3:
            self._g3(self.k)
        self._handback()
        return True

    def after(self, act):
        """Called after the policy's action was executed (G1 trigger: closed and lifted 1.5 cm)."""
        if self.carrying:
            return
        p, _ = self.env.tcp()
        if not self.trig.update(float(act[6]), p[2]):
            return
        if self.g1 is None:                                 # no check: treat as carrying
            self.carrying, self.hold_cmd = True, float(act[6])
            return
        if (self.deadline - self.env.t) < sum(max(1, int(round(t / self.dt))) for t in
                                              (self.g1cfg.t_settle, self.g1cfg.t_load, self.g1cfg.t_squeeze, self.g1cfg.t_restore, self.g1cfg.t_open)):
            self.ev["g1"].append({"t": int(self.env.t), "skipped": "time_limit"})
            return
        m = self.g1.measure(act[:6], float(act[6]), (lambda lb: self.on_frame(lb, self.k)) if self.on_frame else None)
        ok = self.g1.decide(m)
        rise = [self.env.brick_pose(j)[0][2] - self.z_start[j] for j in range(self.env.n)]     # audit only
        self.ev["g1"].append({"t": int(self.env.t), "load_N": m["load_N"], "angle_rad": m["angle_rad"], "grasped": ok,
                              "audit_target_rise_mm": round(rise[self.k] * 1000, 1), "audit_max_rise_brick": int(np.argmax(rise)),
                              "audit_max_rise_mm": round(max(rise) * 1000, 1)})
        if ok:
            self.carrying, self.hold_cmd = True, float(act[6])
        else:
            for _ in range(max(1, int(round(self.g1cfg.t_open / self.dt)))):
                self.env.step(act[:6], self.env.cfg.gripper.open_ctrl)
                if self.on_frame:
                    self.on_frame("G1 open", self.k)
            self.trig.reset()
        if self.policy is not None:
            self.policy.reset()

    def _handback(self):
        self.trig.reset()
        if self.policy is not None:
            self.policy.reset()

    # ------------------------------------------------------------------ helpers
    def _sync_expert(self, grip):
        ex = self.ex
        ex.q_cmd = self.env.arm_q().copy()
        ex.grip_cmd, ex.fail, ex.brick_k, ex.in_hand = grip, None, self.k, None
        ex.steps, ex.touch, ex.max_drift, ex.drift_before_place = getattr(ex, "steps", 0), [], 0.0, 0.0

    def _support_top(self, k):
        """Top of what slot k rests on: the floor for course 1, else the laid mortar bed measured by the camera next to
        the slot (head-joint gaps / bed edge), falling back to the drawing."""
        xy, yaw, L, s = self._design(k)
        if s["course"] == 1:
            return 0.0, "floor"
        if self.cam is not None:
            z = self.cam.surface_z(xy[0], xy[1], yaw, offsets=(-(L / 2 + 0.005), L / 2 + 0.005), across=(0.0,),
                                   z_lo=s["z"] - H / 2 - 0.01, z_hi=s["z"] - H / 2 + 0.01)
            if z is not None:
                return z, "camera"
        return s["z"] - H / 2, "drawing"

    def _move_tcp(self, p, yaw, grip, held, phase, T=0.6, exact_yaw=False):
        """Joint-space move to a TCP pose (gripper down, x axis = yaw); unless exact_yaw, the yaw is chosen modulo pi
        closest to the wrist (an empty jaw or a 180-degree symmetric brick)."""
        ex, env = self.ex, self.env
        _, R0 = env.tcp()
        cur = float(np.arctan2(R0[1, 0], R0[0, 0]))
        if not exact_yaw:
            yaw = yaw if abs(wrap(yaw - cur)) <= abs(wrap(yaw + np.pi - cur)) else yaw + np.pi
        q = ex._solve(np.asarray(p, float), down_R(yaw), env.arm_q(), env.arm_q()[0])
        if q is None:
            return False
        ex._joint_move(q, grip, held, phase, t_min=T, lag=0.0)
        return True

    def _measure_held(self, k):
        """In-hand brick from the camera at the current pose; up to two extra views shifted along the jaw axis."""
        env, ex = self.env, self.ex
        _, _, L, _ = self._design(k)
        tries = []
        p_home, R_home = env.tcp()
        yaw_home = float(np.arctan2(R_home[1, 0], R_home[0, 0]))
        out = np.r_[self._design(k)[0] / np.linalg.norm(self._design(k)[0]), 0.0]          # away from the robot
        views = [(0.0, 0.0, 0.0), (0.0, 0.0, 0.08), (self.cfg.view_shift, 0.0, 0.0), (-self.cfg.view_shift, 0.0, 0.0),
                 (0.0, np.deg2rad(35), 0.0), (0.0, -np.deg2rad(35), 0.0)]
        got = []                                                   # (hb, p, R) of the views that saw a brick end
        for shift, turn, o in views:
            if len(got) >= 3:
                break
            if shift or turn or o:
                tgt = p_home + shift * R_home[:, 0] + o * out
                if turn:
                    self._move_tcp(tgt, yaw_home + turn, ex.grip_cmd, k, "g2_view_turn", T=0.4, exact_yaw=True)
                else:
                    self._move_tcp(tgt, yaw_home, ex.grip_cmd, k, "g2_view_shift", T=0.3, exact_yaw=True)
            p, R = env.tcp()
            hb = self.cam.held_brick(p, R, L, ex.dzp)
            tries.append(hb is not None)
            if hb is None and self.debug_dir is not None:          # what the camera saw when no brick end was visible
                from PIL import Image
                self.debug_dir.mkdir(parents=True, exist_ok=True)
                Image.fromarray(self.cam.last_rgb).save(self.debug_dir / f"g2_t{env.t}_k{k}_shift{shift:+.3f}_turn{np.degrees(turn):+.0f}_out{o:.2f}.png")
            if hb is not None:
                got.append((hb, p, R))
        if (p - p_home).any():
            self._move_tcp(p_home, yaw_home, ex.grip_cmd, k, "g2_view_home", T=0.3, exact_yaw=True)
        p, R = env.tcp()
        if not got:
            return None, p, R, tries
        # the grasp position along the brick is a property of the grasp: the median over the views that saw it
        hb = dict(got[0][0])
        hb["along_m"] = float(np.median([h["along_m"] for h, _, _ in got]))
        hb["across_m"] = 0.0
        hb["n_views"] = len(got)
        return hb, p, R, tries

    # ------------------------------------------------------------------ G2
    def _g2_place(self, k, grip, measure=True):
        env, ex, c = self.env, self.ex, self.cfg
        self._sync_expert(grip)
        xy, yaw_d, L, s = self._design(k)
        sup, sup_src = self._support_top(k)
        tcp_place_z = sup + c.place_gap + H / 2 + ex.dzp       # brick hangs dzp below the TCP
        ev = {"t": int(env.t), "slot": int(k), "support_src": sup_src}
        # 1) up to the view height above where the hand is, measure the brick in the hand
        p, R = env.tcp()
        ex._cart_move(np.r_[p[:2], max(p[2], tcp_place_z + c.view_up)], R, 0.4, grip, k, "g2_up")
        hb, p, R, tries = self._measure_held(k) if measure else (None, *env.tcp(), [])
        ev["views"] = tries
        tcp_yaw = float(np.arctan2(R[1, 0], R[0, 0]))
        if hb is None:
            u0, c0, dpsi, src = 0.0, 0.0, 0.0, "nominal"         # grasp position unknown: assume a centred, aligned grasp
        else:
            u0, c0, dpsi, src = hb["along_m"], hb["across_m"], np.deg2rad(hb["yaw_in_hand_deg"]), "camera"
        ev.update(in_hand_along_mm=round(u0 * 1000, 2), in_hand_across_mm=round(c0 * 1000, 2),
                  in_hand_yaw_deg=round(float(np.degrees(dpsi)), 2), in_hand_src=src)
        bp, byaw = self._audit(k)                                # log only: true in-hand offset
        ax = R[:2, 0] / np.linalg.norm(R[:2, 0])
        ay = np.array([-ax[1], ax[0]])
        ev["audit_in_hand_err_mm"] = round(float(np.hypot(*((p[:2] + u0 * ax + c0 * ay) - bp[:2]))) * 1000, 2) if hb is not None else None
        ev["audit_in_hand_yaw_err_deg"] = round(float(np.degrees(_fold(tcp_yaw + dpsi - byaw))), 2) if hb is not None else None
        if self.debug_dir is not None and hb is not None and ev["audit_in_hand_err_mm"] > 3:
            from PIL import Image
            self.debug_dir.mkdir(parents=True, exist_ok=True)
            self.cam._key = None; self.cam.detect()
            Image.fromarray(self.cam.last_rgb).save(self.debug_dir / f"g2bad_t{env.t}_k{k}_err{ev['audit_in_hand_err_mm']:.1f}.png")
            (self.debug_dir / f"g2bad_t{env.t}_k{k}.json").write_text(__import__("json").dumps(
                {k2: (v.tolist() if hasattr(v, "tolist") else v) for k2, v in hb.items()}, default=float))
        # 2) over the slot: TCP so the brick (offset u0 along / c0 across the jaw, turned dpsi in the hand) lands on the
        # design x, y, yaw. Brick yaw = TCP yaw + dpsi -> TCP yaw = design yaw - dpsi (modulo pi, closest to the wrist)
        yaw_t = yaw_d - dpsi
        yaw_t = yaw_t if abs(wrap(yaw_t - tcp_yaw)) <= abs(wrap(yaw_t + np.pi - tcp_yaw)) else yaw_t + np.pi
        ax_t = np.array([np.cos(yaw_t), np.sin(yaw_t)]); ay_t = np.array([-ax_t[1], ax_t[0]])
        tgt = np.r_[xy - u0 * ax_t - c0 * ay_t, tcp_place_z + c.view_up]
        ok = self._move_tcp(tgt, yaw_t, grip, k, "g2_align", T=0.8, exact_yaw=True)
        ev["moved_mm"] = round(float(np.hypot(*(tgt[:2] - p[:2]))) * 1000, 1)
        # 3) re-measure once at the target and correct the residual
        if ok and measure:
            p2, R2 = env.tcp()
            hb2 = self.cam.held_brick(p2, R2, L, ex.dzp)
            if hb2 is not None:
                err = xy - hb2["pos"][:2]
                ev["residual_mm"] = round(float(np.hypot(*err)) * 1000, 2)      # logged only
        # 4) straight down to the place height and release
        p, R = env.tcp()
        ex._cart_move(np.r_[p[:2], tcp_place_z], R, 0.6, grip, k, "g2_descend")
        self._open_and_lift(k, grip)
        bp, byaw = self._audit(k)
        ev["audit_after_mm"] = round(float(np.hypot(*(bp[:2] - xy))) * 1000, 2)
        ev["audit_after_yaw_deg"] = round(float(np.degrees(_fold(byaw - yaw_d))), 2)
        self.ev["g2"].append(ev)

    def _release_here(self, k, grip):
        """G3 without G2: the policy's release, done where the hand is (no measurement, no correction)."""
        self._sync_expert(grip)
        self._open_and_lift(k, grip)
        self.ev["g2"].append({"t": int(self.env.t), "slot": int(k), "release_here": True})

    def _open_and_lift(self, k, grip):
        env, ex = self.env, self.ex
        gc = env.cfg.gripper
        cl = env.closure()
        nu = max(1, int(round(ex.cfg.t_unload / self.dt)))
        ex._hold(nu, list(np.linspace(grip, cl, nu + 1)[1:]), k, "release_unload")
        n = int(round(ex.cfg.t_open / self.dt))
        ex._hold(n, [G.ramp(gc, False, (i + 1) * self.dt, cl) for i in range(n)], None, "release_open")
        self._t_release = int(env.t)
        p, R = env.tcp()
        ex._cart_move(p + [0, 0, 0.05], R, 0.25, 0.0, None, "release_up")

    # ------------------------------------------------------------------ G3
    def _view_laid(self, k, fast=True):
        """Move the hand off the wall strip toward the robot and up, checking the camera at every step: decide as soon as
        the laid brick is fully visible (the mortar sets 2 s after the hand leaves a still brick, so G3 has to be quick).
        If it never shows in full, look once more from the retract pose (too late for a re-placement, logged)."""
        env, ex, c = self.env, self.ex, self.cfg
        self._sync_expert(0.0)
        xy, yaw_d, L, s = self._design(k)
        zr = (s["z"] + H / 2 - 0.02, s["z"] + H / 2 + H + 0.01)       # also a brick perched on a neighbour
        p0, R = env.tcp()
        yaw0 = float(np.arctan2(R[1, 0], R[0, 0]))
        toward_robot = -xy / np.linalg.norm(xy)
        view = np.r_[xy + c.g3_view_back * toward_robot, s["z"] + H / 2 + ex.dzp + c.g3_view_up]
        q_v = ex._solve(view, down_R(yaw0), env.arm_q(), env.arm_q()[0])
        d = None
        self.view_steps = 0
        if q_v is not None:
            q0 = env.arm_q().copy()
            n = max(2, int(round(0.7 / self.dt)))
            from wall3.expert import smooth_trap
            prof = smooth_trap(np.linspace(0, 1, n + 1)[1:])
            path = q0[None] + prof[:, None] * (q_v - q0)[None]
            for i in range(n):
                ex._play(path[i:i + 1], 0.0, None, "g3_view")
                self.view_steps += 1
                if i >= 3:
                    dd = self.cam.find(xy, r=0.04, z_range=zr, L=L, yaw_prior=yaw_d)
                    if dd is not None and dd["full"]:
                        return dd
                    if dd is not None and float(np.hypot(*(dd["pos"][:2] - xy))) > c.g3_tol_xy + c.g3_partial_margin:
                        dd["decided_on_partial"] = True                  # clearly off even with a partial view: no time to lose
                        return dd
                    d = dd if dd is not None else d
        ex._joint_move(np.array(ex.q_ret), 0.0, None, "g3_view_retract", lag=0.0)
        self.cam._key = None
        d2 = self.cam.find(xy, r=0.04, z_range=zr, L=L, yaw_prior=yaw_d)
        return d2 if d2 is not None else d

    def _g3(self, k):
        env, c = self.env, self.cfg
        self._sync_expert(0.0)
        xy, yaw_d, L, s = self._design(k)
        d = self._view_laid(k)
        ev = {"t": int(env.t), "slot": int(k), "seen": d is not None, "t_release_done": self._t_release}
        if d is not None:
            sup, _ = self._support_top(k)
            exy = float(np.hypot(*(d["pos"][:2] - xy)))
            eyaw = float(np.degrees(_fold(d["yaw"] - yaw_d)))
            ez = float(d["pos"][2] - (sup + H / 2))
            bp, byaw = self._audit(k)
            ev.update(exy_mm=round(exy * 1000, 2), eyaw_deg=round(eyaw, 2), ez_mm=round(ez * 1000, 2), tilt_deg=round(d["tilt_deg"], 2),
                      audit_meas_err_mm=round(float(np.hypot(*(d["pos"][:2] - bp[:2]))) * 1000, 2))
            bad = exy > c.g3_tol_xy or abs(eyaw) > c.g3_tol_yaw_deg or ez > c.g3_tol_z or d["tilt_deg"] > c.g3_tol_tilt_deg
            ev["bad"] = bool(bad)
            if bad and k not in self.replaced and d["tilt_deg"] < 45:
                if c.min_time_left_s > 0 and self._time_left() < c.min_time_left_s:
                    ev["replace"] = "skipped_time"
                else:
                    self.replaced.add(k)
                    ev["replace"] = self._replace(k, d)
        self.ev["g3"].append(ev)

    def _replace(self, k, d):
        """Re-grasp the laid brick at its measured pose and place it again with G2 (once)."""
        env, ex = self.env, self.ex
        xy, yaw_d, L, s = self._design(k)
        gc = env.cfg.gripper
        pos, yaw_b = d["pos"], d["yaw"]
        above = np.r_[pos[:2], pos[2] + ex.dzp + 0.045]
        out = {"audit_cured_before": bool(env.cured[k])}
        if not self._move_tcp(above, yaw_b, 0.0, None, "g3_to_brick", T=0.4):
            out["result"] = "ik_failed"
            return out
        p, R = env.tcp()
        ex._cart_move(np.r_[pos[:2], pos[2] + ex.dzp], R, 0.35, 0.0, None, "g3_descend")
        n = int(round(ex.cfg.t_close / self.dt))
        cg = ex.grip_close_cmd()
        ex._hold(n, [min(cg, G.ramp(gc, True, (i + 1) * self.dt, gc.open_ctrl)) for i in range(n)], None, "g3_close")
        closure = env.closure()
        out["audit_cured_at_close"] = bool(env.cured[k])                 # log only: mortar set before the gate got there?
        out["audit_cure_t"] = int(env.cure_t[k]); out["t_close"] = int(env.t)
        if closure > ex.cfg.grip_empty:
            out["result"] = "grasp_empty"
            self._open_and_lift(k, cg)
            return out
        self.k = k
        self._g2_place(k, cg, measure=True)
        d2 = self._view_laid(k)
        if d2 is not None:
            out["after_exy_mm"] = round(float(np.hypot(*(d2["pos"][:2] - xy))) * 1000, 2)
            out["after_eyaw_deg"] = round(float(np.degrees(_fold(d2["yaw"] - yaw_d))), 2)
        bp, byaw = self._audit(k)
        out["audit_after_mm"] = round(float(np.hypot(*(bp[:2] - xy))) * 1000, 2)
        out["result"] = "replaced"
        return out

    def summary_config(self):
        return {"g1": self.on_g1, "g2": self.on_g2, "g3": self.on_g3, "gate_cfg": self.cfg.to_dict(),
                "g1_cfg": {**self.g1cfg.to_dict(), "tare_N": self.g1.f0 if self.g1 else None}}
