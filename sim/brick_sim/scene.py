"""Brick-stacking scene on the SO-ARM100 (MuJoCo Menagerie model).

Design choices (see 설계수행계획서_통합정리 v5):
- Bricks are 1/4-scale UK standard bricks (215 x 102.5 x 65 mm -> 54 x 26 x 16 mm) by default.
- Wall: running (stretcher) bond along +x with half-brick closers at both ends of odd courses,
  so every brick is fully supported (EN 1996-1-1 8.1.4 overlap; KCS 41 34 02 통줄눈 금지).
- Mortar modes:
    "dry"     : rigid contacts, no joint.
    "mortarA" : compliant contact layer of nominal thickness (MuJoCo <pair> margin + direct-form solref).
    "mortarB" : mortarA + cure: a brick is welded to the world once it has settled (equality weld, eq_active).
- Cameras: "front" (fixed), "top" (fixed), "wrist" (on Fixed_Jaw).
- TCP site "tcp" sits between the jaw pads; its z-axis is the approach axis, x-axis the jaw-opening axis.
- The model is loaded from an XML string with in-memory assets because MuJoCo's file loader cannot
  open non-ASCII (Korean) Windows paths.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import mujoco
import numpy as np

HERE = Path(__file__).resolve().parent
MENAGERIE_DIR = HERE.parent / "menagerie" / "trs_so_arm100"

ARM_JOINTS = ["Rotation", "Pitch", "Elbow", "Wrist_Pitch", "Wrist_Roll"]
JAW_JOINT = "Jaw"
HOME_QPOS = np.array([0.0, -1.57, 1.57, 1.57, -1.57, 0.0])
JAW_OPEN = 0.9
JAW_CLOSED = -0.12


@dataclass
class BrickSpec:
    L: float = 0.054   # along wall (x)
    W: float = 0.026   # through-wall thickness (y)  -> grasped across this
    H: float = 0.016   # course height (z)
    density: float = 1900.0

    @property
    def mass(self):
        return self.L * self.W * self.H * self.density


@dataclass
class WallSpec:
    n_courses: int = 2
    n_per_course: int = 3       # full bricks in even courses
    origin_x: float = -0.16     # centre of first brick of course 0
    origin_y: float = -0.17
    head_gap: float = 0.002     # nominal head-joint gap (m)
    bed_joint: float = 0.0      # nominal bed-joint thickness (m); >0 only in mortar modes


@dataclass
class SceneConfig:
    brick: BrickSpec = field(default_factory=BrickSpec)
    wall: WallSpec = field(default_factory=WallSpec)
    mortar: str = "dry"                     # dry | mortarA | mortarB
    mortar_sag: float = 0.0005              # m: settlement of a brick into the green mortar bed under its own weight
    mortar_zeta: float = 1.0                # damping ratio of the bed spring (1 = critical)
    mortar_friction: float = 0.75           # tan(phi) standard masonry interface value (Lourenço 1996)
    cure_settle_steps: int = 25             # control steps of low velocity before cure (mortarB)
    feeder_pos: tuple = (0.10, -0.18)       # brick feeder slot (like Hadrian X / SAM feeders): one brick at a time
    park_pos: tuple = (0.55, 0.45)          # where unstaged bricks wait, out of camera view
    supply_yaw_deg: float = 0.0             # +/- random yaw of supply bricks
    size_rand: float = 0.0                  # +/- fractional randomisation of brick dims
    pos_rand: float = 0.0                   # +/- metres added to supply positions
    img_h: int = 128
    img_w: int = 128
    ctrl_dt: float = 0.04                   # 25 Hz control
    timestep: float = 0.002                 # physics step
    layout: str = "wall"                    # "wall" (running bond, n_courses x n_per_course) | "2p1" (blueprint 4.3)
    seed: int = 0


def blueprint_config(mortar: str = "dry", **kw) -> "SceneConfig":
    """SceneConfig matching 설계수행계획서_14조_통합최종본 4.3/4.4: 3 bricks 2+1, 90x42.632x27 mm, 1800 kg/m3,
    lower-course gap 4.737 mm, joint 4.737 mm (equivalent contact layer), 20 Hz control, 1 ms physics."""
    bed = 0.004737 if mortar != "dry" else 0.0
    cfg = SceneConfig(brick=BrickSpec(L=0.09, W=0.042632, H=0.027, density=1800.0),
                      wall=WallSpec(n_courses=2, n_per_course=2, origin_x=-0.10, origin_y=-0.17,
                                    head_gap=0.004737, bed_joint=bed),
                      mortar=mortar, layout="2p1", ctrl_dt=0.05, timestep=0.001, feeder_pos=(0.10, -0.17), **kw)
    return cfg


def _fmt(v):
    return " ".join(f"{x:.6g}" for x in np.atleast_1d(v))


def design_poses(cfg: SceneConfig, brick: BrickSpec):
    """Design centres in laying order: list of (x, y, z, yaw, length)."""
    w = cfg.wall
    L, g = brick.L, w.head_gap
    pitch = L + g
    poses = []
    if cfg.layout == "2p1":
        # blueprint 4.4.2: lower centres at x = +-(L+g)/2, z = H/2; top at x = 0, z = 3H/2 (+ joint)
        half = pitch / 2
        z0 = brick.H / 2
        z1 = brick.H * 1.5 + w.bed_joint
        return [(w.origin_x - half, w.origin_y, z0, 0.0, L),
                (w.origin_x + half, w.origin_y, z0, 0.0, L),
                (w.origin_x, w.origin_y, z1, 0.0, L)]
    for k in range(w.n_courses):
        z = brick.H / 2 + k * (brick.H + w.bed_joint)
        if k % 2 == 0:
            for i in range(w.n_per_course):
                poses.append((w.origin_x + i * pitch, w.origin_y, z, 0.0, L))
        else:
            x_end = w.origin_x + (w.n_per_course - 1) * pitch
            poses.append((w.origin_x - L / 4 - g / 2, w.origin_y, z, 0.0, L / 2))
            for i in range(w.n_per_course - 1):
                poses.append((w.origin_x + pitch / 2 + i * pitch, w.origin_y, z, 0.0, L))
            poses.append((x_end + L / 4 + g / 2, w.origin_y, z, 0.0, L / 2))
    return poses


def n_bricks_for(wall: WallSpec, layout: str = "wall") -> int:
    if layout == "2p1":
        return 3
    return sum((wall.n_per_course + 1) if k % 2 else wall.n_per_course for k in range(wall.n_courses))


def build_xml(cfg: SceneConfig, brick: BrickSpec, supply_poses, mortar_margin: float, lengths) -> str:
    n = len(supply_poses)
    hy, hz = brick.W / 2, brick.H / 2
    mass = brick.mass
    # MuJoCo direct-form solref is mass-normalised: stiffness in 1/s^2, damping in 1/s.
    # A brick sags g/k under its own weight, so k = g / sag ; b = 2*zeta*sqrt(k).
    k = 9.81 / cfg.mortar_sag
    b = 2.0 * cfg.mortar_zeta * np.sqrt(k)

    bricks = []
    for i, (x, y, z, yaw) in enumerate(supply_poses):
        q = np.array([np.cos(yaw / 2), 0, 0, np.sin(yaw / 2)])
        rgba = "0.72 0.33 0.22 1" if i % 2 == 0 else "0.78 0.40 0.28 1"
        hx = lengths[i] / 2
        m_i = mass * lengths[i] / brick.L
        bricks.append(
            f'<body name="brick_{i}" pos="{_fmt([x, y, z])}" quat="{_fmt(q)}">'
            f'<freejoint name="brick_{i}_free"/>'
            f'<geom name="brick_{i}" type="box" size="{_fmt([hx, hy, hz])}" mass="{m_i:.5f}" '
            f'rgba="{rgba}" friction="{cfg.mortar_friction} 0.005 0.0001" condim="3" priority="1"/>'
            f'</body>'
        )
    pairs = []
    if cfg.mortar in ("mortarA", "mortarB"):
        for i in range(n):
            for j in range(i + 1, n):
                pairs.append(
                    f'<pair geom1="brick_{i}" geom2="brick_{j}" condim="4" '
                    f'friction="{cfg.mortar_friction} {cfg.mortar_friction} 0.005 0.0001 0.0001" '
                    f'margin="{mortar_margin:.5f}" solref="{-k:.4f} {-b:.4f}" '
                    f'solimp="0.95 0.99 0.001 0.5 2"/>'
                )
    welds = []
    if cfg.mortar == "mortarB":
        for i in range(n):
            welds.append(f'<weld name="cure_{i}" body1="brick_{i}" active="false" solref="0.004 1"/>')

    return f"""
<mujoco model="so_arm100_bricks">
  <include file="ARM_XML"/>
  <option timestep="{cfg.timestep}" cone="elliptic" impratio="10" noslip_iterations="3"/>
  <visual>
    <headlight diffuse="0.7 0.7 0.7" ambient="0.35 0.35 0.35" specular="0.1 0.1 0.1"/>
    <global offwidth="640" offheight="480"/>
    <quality shadowsize="2048"/>
  </visual>
  <asset>
    <texture type="2d" name="ground" builtin="checker" mark="edge" rgb1="0.82 0.82 0.80" rgb2="0.70 0.70 0.68"
      markrgb="0.6 0.6 0.6" width="300" height="300"/>
    <material name="ground" texture="ground" texuniform="true" texrepeat="8 8" reflectance="0.05"/>
  </asset>
  <worldbody>
    <light pos="0.3 -0.6 1.2" dir="-0.2 0.4 -1" directional="true" castshadow="true"/>
    <light pos="-0.5 -0.2 1.0" dir="0.4 0.1 -1" directional="true" castshadow="false"/>
    <geom name="floor" size="0 0 0.05" type="plane" material="ground" friction="0.9 0.005 0.0001"/>
    <site name="wall_origin" pos="{_fmt([cfg.wall.origin_x, cfg.wall.origin_y, 0])}" size="0.003" rgba="0 1 0 0.4"/>
    <camera name="front" pos="0.02 -0.64 0.36" xyaxes="1 0 0 0 0.62 0.78"/>
    <camera name="top" pos="-0.02 -0.18 0.70" xyaxes="1 0 0 0 1 0"/>
    {''.join(bricks)}
  </worldbody>
  <contact>
    {''.join(pairs)}
  </contact>
  <equality>
    {''.join(welds)}
  </equality>
</mujoco>
"""


def _augment_arm_xml(src: Path, dst: Path):
    """Write a copy of so_arm100.xml with a TCP site and a wrist camera on Fixed_Jaw."""
    txt = src.read_text(encoding="utf-8")
    marker = '<geom class="finger_collision" name="fixed_jaw_pad_1"'
    inject = (
        '<site name="tcp" pos="-0.004 -0.097 0" quat="0.7071068 0.7071068 0 0" size="0.003" rgba="0 0 1 0.5"/>'
        '<camera name="wrist" pos="0.0 -0.02 0.045" xyaxes="1 0 0 0 0 -1" fovy="75"/>'
    )
    assert marker in txt, "unexpected so_arm100.xml layout"
    txt = txt.replace(marker, inject + "\n                " + marker, 1)
    dst.write_text(txt, encoding="utf-8")


def _quat_rotmat(q):
    w, x, y, z = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


class BrickEnv:
    def __init__(self, cfg: SceneConfig | None = None):
        self.cfg = cfg or SceneConfig()
        self.rng = np.random.default_rng(self.cfg.seed)
        self.arm_xml = MENAGERIE_DIR / "so_arm100_tcp.xml"
        if not self.arm_xml.exists():
            _augment_arm_xml(MENAGERIE_DIR / "so_arm100.xml", self.arm_xml)
        assets = {self.arm_xml.name: self.arm_xml.read_bytes()}
        for stl in (MENAGERIE_DIR / "assets").glob("*.stl"):
            assets[stl.name] = stl.read_bytes()  # MuJoCo keys assets by basename
        self._assets = assets
        self.model = None
        self.data = None
        self.renderer = None
        self.reset()

    # ------------------------------------------------------------------ setup
    def _sample_episode(self):
        cfg = self.cfg
        b = cfg.brick
        s = cfg.size_rand
        L = b.L * (1 + self.rng.uniform(-s, s))
        W = b.W * (1 + self.rng.uniform(-s, s))
        H = b.H * (1 + self.rng.uniform(-s, s))
        brick = BrickSpec(L=L, W=W, H=H, density=b.density)
        n = n_bricks_for(cfg.wall, cfg.layout)
        poses = []
        self.feeder_targets = []
        for i in range(n):
            # parked in a row far from the workspace; staged to the feeder slot when it is that brick's turn
            poses.append((cfg.park_pos[0] + 0.07 * (i % 5), cfg.park_pos[1] + 0.06 * (i // 5), H / 2 + 0.0005, 0.0))
            fx = cfg.feeder_pos[0] + self.rng.uniform(-cfg.pos_rand, cfg.pos_rand)
            fy = cfg.feeder_pos[1] + self.rng.uniform(-cfg.pos_rand, cfg.pos_rand)
            fyaw = np.deg2rad(self.rng.uniform(-cfg.supply_yaw_deg, cfg.supply_yaw_deg))
            self.feeder_targets.append((fx, fy, fyaw))
        return brick, poses

    def reset(self, seed: int | None = None):
        if seed is not None:
            self.rng = np.random.default_rng(seed)
        self.brick, self.supply_poses = self._sample_episode()
        self.design = design_poses(self.cfg, self.brick)
        self.brick_L = np.array([d[4] for d in self.design])
        margin = self.cfg.wall.bed_joint if self.cfg.mortar != "dry" else 0.0
        xml = build_xml(self.cfg, self.brick, self.supply_poses, margin, list(self.brick_L))
        xml = xml.replace("ARM_XML", self.arm_xml.name)
        self.last_xml = xml
        self.model = mujoco.MjModel.from_xml_string(xml, self._assets)
        self.data = mujoco.MjData(self.model)
        m, d = self.model, self.data
        self.n_bricks = len(self.supply_poses)
        self.arm_qidx = [m.joint(j).qposadr[0] for j in ARM_JOINTS]
        self.arm_dofidx = [m.joint(j).dofadr[0] for j in ARM_JOINTS]
        self.jaw_qidx = m.joint(JAW_JOINT).qposadr[0]
        self.act_ids = [m.actuator(j).id for j in ARM_JOINTS + [JAW_JOINT]]
        self.tcp_site = m.site("tcp").id
        self.brick_bids = [m.body(f"brick_{i}").id for i in range(self.n_bricks)]
        self.brick_qadr = [m.joint(f"brick_{i}_free").qposadr[0] for i in range(self.n_bricks)]
        self.brick_dofadr = [m.joint(f"brick_{i}_free").dofadr[0] for i in range(self.n_bricks)]
        self.cured = np.zeros(self.n_bricks, dtype=bool)
        self.settle_count = np.zeros(self.n_bricks, dtype=int)
        self.n_sub = int(round(self.cfg.ctrl_dt / m.opt.timestep))
        d.qpos[self.arm_qidx] = HOME_QPOS[:5]
        d.qpos[self.jaw_qidx] = JAW_OPEN
        d.ctrl[self.act_ids] = np.r_[HOME_QPOS[:5], JAW_OPEN]
        mujoco.mj_forward(m, d)
        self.renderer = None
        self.t = 0
        return self.observe()

    # ------------------------------------------------------------------ feeder
    def stage_brick(self, i):
        """Teleport brick i from the park row to the feeder slot (simulates an automatic brick feeder)."""
        fx, fy, fyaw = self.feeder_targets[i]
        a = self.brick_qadr[i]
        self.data.qpos[a: a + 3] = [fx, fy, self.brick.H / 2 + 0.0005]
        self.data.qpos[a + 3: a + 7] = [np.cos(fyaw / 2), 0, 0, np.sin(fyaw / 2)]
        self.data.qvel[self.brick_dofadr[i]: self.brick_dofadr[i] + 6] = 0
        mujoco.mj_forward(self.model, self.data)

    # ------------------------------------------------------------------ helpers
    def brick_pose(self, i):
        q = self.data.qpos[self.brick_qadr[i]: self.brick_qadr[i] + 7]
        return q[:3].copy(), q[3:7].copy()

    def brick_poses(self):
        return np.array([self.data.qpos[a: a + 7].copy() for a in self.brick_qadr])

    def brick_vel(self, i):
        dof = self.brick_dofadr[i]
        return self.data.qvel[dof: dof + 6].copy()

    def qpos_arm(self):
        return np.r_[self.data.qpos[self.arm_qidx], self.data.qpos[self.jaw_qidx]].astype(np.float32)

    def env_state(self):
        return np.r_[self.brick_poses().ravel(), self.brick_L, self.brick.W, self.brick.H].astype(np.float32)

    def tcp_pose(self):
        p = self.data.site_xpos[self.tcp_site].copy()
        R = self.data.site_xmat[self.tcp_site].reshape(3, 3).copy()
        return p, R

    def render(self, cam: str):
        if self.renderer is None:
            self.renderer = mujoco.Renderer(self.model, self.cfg.img_h, self.cfg.img_w)
        self.renderer.update_scene(self.data, camera=cam)
        return self.renderer.render().copy()

    def observe(self):
        return {
            "observation.state": self.qpos_arm(),
            "observation.environment_state": self.env_state(),
        }

    # ------------------------------------------------------------------ dynamics
    def step(self, action):
        """action: 6 joint position targets (5 arm + jaw), executed for one control period."""
        self.data.ctrl[self.act_ids] = np.asarray(action, dtype=np.float64)
        for _ in range(self.n_sub):
            mujoco.mj_step(self.model, self.data)
        self.t += 1
        if self.cfg.mortar == "mortarB":
            self._update_cure()
        return self.observe()

    def _update_cure(self):
        """Cure a brick once it is on the wall line, nearly static and released (mortarB).

        MuJoCo weld eq_data[3:10] = relpose = pose of body2 (world) relative to body1, i.e. the inverse
        of the brick's world pose (verified empirically: 0.07 mm drift after activation).
        """
        m, d = self.model, self.data
        jaw_open = d.qpos[self.jaw_qidx] > 0.3
        w = self.cfg.wall
        # only bricks inside the designed wall footprint may cure (never at the feeder or in the park row)
        xs = [dd[0] for dd in self.design]
        x_lo, x_hi = min(xs) - 0.6 * self.brick.L, max(xs) + 0.6 * self.brick.L
        for i in range(self.n_bricks):
            if self.cured[i]:
                continue
            p, q = self.brick_pose(i)
            v = self.brick_vel(i)
            on_wall = abs(p[1] - w.origin_y) < 0.02 and x_lo < p[0] < x_hi and p[2] > 0.3 * self.brick.H
            static = np.linalg.norm(v[:3]) < 0.01 and np.linalg.norm(v[3:]) < 0.2
            self.settle_count[i] = self.settle_count[i] + 1 if (on_wall and static and jaw_open) else 0
            if self.settle_count[i] >= self.cfg.cure_settle_steps:
                eq = m.equality(f"cure_{i}").id
                qi = np.r_[q[0], -q[1:]]
                m.eq_data[eq, 0:3] = 0.0
                m.eq_data[eq, 3:6] = _quat_rotmat(qi) @ (-p)
                m.eq_data[eq, 6:10] = qi
                m.eq_data[eq, 10] = 1.0
                d.eq_active[eq] = 1
                self.cured[i] = True

    def settle(self, n_ctrl_steps=25):
        """Let physics run with the arm held still (used before metrics)."""
        for _ in range(n_ctrl_steps):
            self.step(self.data.ctrl[self.act_ids].copy())

    def close(self):
        pass
