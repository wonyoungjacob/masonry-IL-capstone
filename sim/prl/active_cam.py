"""능동 카메라: 고정 받침 위에서 팬 · 틸트 두 축으로 도는 깊이 카메라와, 작업의 의미 있는 곳을 따라가는 시선 규칙.

정의와 값의 근거는 04_개인연구/근거_능동카메라_20261113/기준_해석_능동카메라_20261113.md (결과를 보기 전에 고정).

- 카메라는 물리에 영향이 없다. 모델에는 세계 좌표계의 카메라로 넣고(DryEnv extra_cams), 제어 스텝마다 model.cam_pos / cam_quat만 바꾼다.
  qpos 크기와 환경 해시가 그대로라서 저장된 대본 궤적을 그대로 재생할 수 있다.
- 팬 · 틸트 장치: 팬축 = 세계 z(수직 기둥 위), 틸트축 = 받침점에서 팬축과 만나는 수평축, 광학 중심은 틸트축에서 lever만큼 위(카메라의 +y 쪽).
  영상의 위쪽은 항상 세계 +z 쪽이다(구르기 없음). 각속도 · 각가속도 한도 안에서 목표 각을 따라간다.
- 시선 규칙은 정답 좌표를 쓰지 않는다. 도면(공급 칸의 명목 위치, 설계 자리)과 로봇 자기 상태(집게 관절, 팔 관절, 순기구학)만 쓴다.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict

import mujoco
import numpy as np

from wall3.config import H
from wall3.scene import _quat_from_R
from prl import config as C

FINGER_GRASP = 0.12          # rad, 집게 관절이 이보다 닫히면 '쥠'(열림 0, 벽돌을 쥐면 약 0.244). 로봇 자기 상태만으로 정한다
RETRACT_TOL = 0.05           # rad, 팔 관절이 철수 자세에서 이 안이면 '철수함'


@dataclass(frozen=True)
class PanTiltSpec:
    """One pan-tilt unit with a D435-class depth camera. Angles in degrees, rates in degrees per second."""
    lever_m: float = 0.03            # 틸트축 → 광학 중심
    pan_lim: tuple = (-170.0, 170.0)     # 받침의 기준 방향(pan0)에서 잰 팬 각의 범위
    tilt_lim: tuple = (-80.0, 30.0)      # 고도각(0 = 수평, 음수 = 아래)
    w_max: float = 100.0             # 최대 각속도
    a_max: float = 400.0             # 최대 각가속도
    fovy: float = C.FOVY_D435
    kind: str = "d435"

    def to_dict(self):
        return asdict(self)


# ---------------------------------------------------------------------------------------------------------------- kinematics
def axes(pan, tilt):
    """Camera axes in the world for pan (heading of the optical axis in the xy plane) and tilt (elevation), radians:
    forward f, right x, up y. MuJoCo camera frame = columns [x, y, −f]."""
    cp, sp, ct, st = np.cos(pan), np.sin(pan), np.cos(tilt), np.sin(tilt)
    f = np.array([ct * cp, ct * sp, st])
    x = np.array([sp, -cp, 0.0])
    y = np.array([-st * cp, -st * sp, ct])
    return f, x, y


def cam_pose(base, pan, tilt, lever):
    """(optical centre, R) of the camera; R columns = [right, up, backward] (the MuJoCo camera frame)."""
    f, x, y = axes(pan, tilt)
    return np.asarray(base, float) + lever * y, np.stack([x, y, -f], axis=1)


def look_angles(base, target, lever):
    """(pan, tilt) in radians that put `target` on the optical axis. With the lever the optical centre moves in the vertical
    plane of the heading: r·sin t − h·cos t = −lever, so t = atan2(h, r) − asin(lever / D)."""
    d = np.asarray(target, float) - np.asarray(base, float)
    r, h = float(np.hypot(d[0], d[1])), float(d[2])
    dist = float(np.hypot(r, h))
    pan = float(np.arctan2(d[1], d[0]))
    tilt = float(np.arctan2(h, r) - np.arcsin(np.clip(lever / max(dist, 1e-9), -1.0, 1.0)))
    return pan, tilt


def wrap(a):
    return (a + np.pi) % (2 * np.pi) - np.pi


class PanTilt:
    """State of one unit: angles follow a commanded gaze point within the rate and acceleration limits."""

    def __init__(self, base, pan0_deg=0.0, spec: PanTiltSpec | None = None):
        self.base = np.asarray(base, float)
        self.spec = spec or PanTiltSpec()
        self.pan0 = np.radians(pan0_deg)                  # 받침의 기준 방향 (팬 범위의 가운데)
        self.q = np.zeros(2)                              # [pan − pan0, tilt] (rad)
        self.v = np.zeros(2)
        self.cmd = np.zeros(2)
        self.reachable = True

    # ---- commands
    def angles_for(self, target):
        """Joint angles [pan − pan0, tilt] that look at `target`, clipped to the limits; second value: inside the limits."""
        pan, tilt = look_angles(self.base, target, self.spec.lever_m)
        q = np.array([wrap(pan - self.pan0), tilt])
        lo = np.radians([self.spec.pan_lim[0], self.spec.tilt_lim[0]])
        hi = np.radians([self.spec.pan_lim[1], self.spec.tilt_lim[1]])
        qc = np.clip(q, lo, hi)
        return qc, bool(np.all(np.abs(qc - q) < 1e-9))

    def snap(self, target):
        """Jump to the target (start of an episode: the camera is already there and at rest)."""
        self.q, self.reachable = self.angles_for(target)
        self.cmd = self.q.copy()
        self.v[:] = 0.0

    def step(self, target, dt, sub=10):
        """One control step toward `target`: speed limited to w_max, changed by at most a_max per second, braking in time
        (v ≤ sqrt(2·a_max·|error|)). Integrated in `sub` sub-steps so that the unit settles on the command (a 20 Hz step
        alone would leave a_max·dt² = 1° of chatter)."""
        self.cmd, self.reachable = self.angles_for(target)
        w, a = np.radians(self.spec.w_max), np.radians(self.spec.a_max)
        h = dt / sub
        for _ in range(sub):
            err = self.cmd - self.q
            v_des = np.sign(err) * np.minimum(w, np.sqrt(2 * a * np.abs(err)))
            self.v = self.v + np.clip(v_des - self.v, -a * h, a * h)
            stepq = self.v * h
            arrive = (np.abs(err) <= np.abs(stepq) + 1e-12) & (np.abs(self.v) <= 2 * a * h + 1e-12)
            self.q = np.where(arrive, self.cmd, self.q + stepq)
            self.v = np.where(arrive, 0.0, self.v)
        return self.q

    # ---- pose
    def pose(self, dq=(0.0, 0.0), dbase=(0.0, 0.0, 0.0)):
        """True pose (dq = 0), or the pose a user of the encoders would compute with angle error dq (rad) and a base
        position error dbase (m)."""
        return cam_pose(self.base + np.asarray(dbase, float), self.pan0 + self.q[0] + dq[0], self.q[1] + dq[1], self.spec.lever_m)

    def speed_deg(self):
        return float(np.degrees(np.abs(self.v).max()))

    def error_deg(self):
        return float(np.degrees(np.abs(self.cmd - self.q).max()))


# ---------------------------------------------------------------------------------------------------------------- gaze rule
class Task:
    """What the gaze rules may use: the drawing (supply slot layout, design slots) and the robot's own state."""

    def __init__(self, env, q_retract):
        self.env = env
        self.q_ret = np.asarray(q_retract, float)[:6]
        c = env.cfg
        self.supply = [np.array([x, y, c.table_h + H]) for x, y in c.supply_slots]        # 명목 칸의 벽돌 윗면 중심
        self.slot = [np.array([s["x"], s["y"], s["z"]]) for s in env.design]               # 설계 자리의 중심
        self.finger_adr = int(env.model.joint("g_finger_joint").qposadr[0])

    def grasped(self):
        return bool(self.env.data.qpos[self.finger_adr] > FINGER_GRASP)

    def retracted(self):
        return bool(np.abs(self.env.arm_q() - self.q_ret).max() < RETRACT_TOL)

    def tcp(self):
        return self.env.tcp()[0]


class Gaze:
    """Where one camera looks. Roles:
      lead   집을 벽돌 k → (쥠) → 놓을 자리 k → (놓음) → 다음 벽돌 k+1 [leave = 'release'] 또는 (놓고 팔이 철수함) → k+1 [leave = 'retract']
      pick   집을 벽돌 k → (쥠) → 다음에 집을 벽돌 k+1 (공급대만 본다)
      slot   놓을 자리 k만 본다 (벽돌 k의 차례가 시작될 때 옮겨 간다)
      hand   집게 끝(순기구학)을 따라간다
      fixed  한 점만 본다
    The brick index k comes from the task (drawing order); the transitions use only the finger joint and the arm joints."""

    def __init__(self, role, task: Task, leave="release", point=None):
        assert role in ("lead", "pick", "slot", "hand", "fixed") and leave in ("release", "retract")
        self.role, self.task, self.leave, self.point = role, task, leave, (None if point is None else np.asarray(point, float))
        self.reset(0)

    def reset(self, k):
        self.k = int(k)
        self.state = "pick"                   # pick → place → done (brick k)
        self.left = False                     # done: already moved on to the next brick

    def target(self, k):
        """Gaze point for the current robot state; k = the brick the task is working on (−1: none, keep the last one)."""
        t = self.task
        if k >= 0 and k != self.k:
            self.reset(k)
        if self.role == "fixed":
            return self.point
        if self.role == "hand":
            return t.tcp()
        if self.role == "slot":
            return t.slot[self.k]
        g = t.grasped()
        if self.state == "pick" and g:
            self.state = "place"
        elif self.state == "place" and not g:
            self.state = "done"
        if self.state == "pick":
            return t.supply[self.k]
        if self.role == "pick":               # 공급대만 보는 눈: 쥔 뒤에는 다음에 집을 벽돌로 먼저 간다
            return t.supply[min(self.k + 1, len(t.supply) - 1)]
        if self.state == "place":
            return t.slot[self.k]
        if self.k + 1 >= len(t.slot):         # last brick: stay on its slot
            return t.slot[self.k]
        if self.leave == "release" or t.retracted():
            self.left = True
        return t.supply[self.k + 1] if self.left else t.slot[self.k]


# ---------------------------------------------------------------------------------------------------------------- rig
class ActiveRig:
    """Pan-tilt cameras of one environment. cams: {name: {"base": (x, y, z), "pan0": deg, "role": ..., "leave": ..., "point": ...}}.
    Use: env = DryEnv(extra_cams=rig_specs(cams)); rig = ActiveRig(env, cams, q_retract); rig.reset(k); then rig.update(k)
    after every env.step (or after setting qpos in a replay)."""

    def __init__(self, env, cams, q_retract, spec: PanTiltSpec | None = None):
        self.env, self.spec = env, spec or PanTiltSpec()
        self.task = Task(env, q_retract)
        self.names = list(cams)
        self.unit = {n: PanTilt(c["base"], c.get("pan0", 0.0), self.spec) for n, c in cams.items()}
        self.gaze = {n: Gaze(c.get("role", "lead"), self.task, c.get("leave", "release"), c.get("point")) for n, c in cams.items()}
        self.cid = {n: env.model.camera(n).id for n in cams}
        self.dt = float(env.cfg.ctrl_dt)

    def _write(self):
        m = self.env.model
        for n, u in self.unit.items():
            p, R = u.pose()
            m.cam_pos[self.cid[n]] = p
            m.cam_quat[self.cid[n]] = _quat_from_R(R)
        mujoco.mj_camlight(m, self.env.data)

    def reset(self, k):
        """Start of an episode (brick k): every camera already looks at its first target, at rest."""
        for n in self.names:
            self.gaze[n].reset(k)
            self.unit[n].snap(self.gaze[n].target(k))
        self._write()

    def update(self, k):
        """One control step: new gaze targets from the task and the robot state, units move within their limits."""
        for n in self.names:
            self.unit[n].step(self.gaze[n].target(k), self.dt)
        self._write()

    def aim(self, name, point):
        """Point one camera at a point and stop there (static measurements: the camera dwells before the image is taken)."""
        self.unit[name].snap(point)
        self._write()
        return self.unit[name].reachable


def rig_specs(cams, spec: PanTiltSpec | None = None):
    """extra_cams for DryEnv: the cameras start level, looking along their pan0."""
    spec = spec or PanTiltSpec()
    out = {}
    for n, c in cams.items():
        p0 = np.radians(c.get("pan0", 0.0))
        base = np.asarray(c["base"], float)
        pos, _ = cam_pose(base, p0, 0.0, spec.lever_m)
        out[n] = dict(pos=[float(v) for v in pos], target=[float(v) for v in pos + [np.cos(p0), np.sin(p0), 0.0]], up=(0, 0, 1), fovy=float(spec.fovy))
    return out
