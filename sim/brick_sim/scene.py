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
    valid_supply: bool = False             # reject overlapping/out-of-reach random supply layouts
    feasible_supply: bool = False          # also reject layouts whose expert grasp self-collides or whose jaw sweep hits a
                                            # neighbour (brick_sim.feasibility; 2026-09-23 first-grasp diagnosis)
    img_h: int = 128
    img_w: int = 128
    ctrl_dt: float = 0.04                   # 25 Hz control
    timestep: float = 0.002                 # physics step
    layout: str = "wall"                    # "wall" (running bond, n_courses x n_per_course) | "2p1" (blueprint 4.3)
    first_course_only: bool = False         # 2p1: only the two lower-course bricks exist (KICEM 2026 size study)
    seed: int = 0
    # --- scene spec (v2, 2026-09-18; see SPEC_V1 / SPEC_V2 and blueprint_config) ---
    mortar_impl: str = "bed"                # "bed": one continuous mortar bed (3 mocap slabs) is laid on top of the lower
                                            #        course once both bricks have settled there, following their real
                                            #        poses; the top brick rests on it through a soft contact pair
                                            #        (blueprint 4.8.2 "접촉용 얇은 형상").  Nothing is laid after that.
                                            # "margin": legacy invisible <pair margin> between whole bricks
    mortar_visual: bool = True              # draw the bed (overhang, random drips down the faces, surface bumps)
    bed_overhang: float = 0.002             # m: how far the wet bed spreads past the brick edges
    target_marks: bool = True               # floor outlines of the course-0 targets + chalk line (먹선) on the wall face
    supply: str = "scatter"                 # "scatter": bricks lie near the workspace from the start (random slot/jitter/yaw)
                                            # "feeder": legacy - parked far away, teleported one at a time to feeder_pos
    supply_slots: tuple = ((0.065, -0.145), (0.17, -0.145), (0.09, -0.225))  # scatter slot centres (m), permuted per episode
                                            # constraints (validated 2026-09-18, 0/40 failures with and without kicks):
                                            # radii 0.16-0.24 m from the base (r=0.25 made the descending jaw knock the brick
                                            # over); >= 2 cm clear of the wall's right end (x=-0.0095) so a brick placed there
                                            # never lands on a waiting brick; neighbours >= 10 cm apart along x or >= 8 cm
                                            # along y, because the open moving jaw swings out ~7 cm and hits a closer brick


# Scene specs.  v1 = what the 2026-09-18 datasets (data/2p1_*) were generated with; v2 = current default.
SPEC_V1 = dict(head_gap=0.004737, mortar_impl="margin", mortar_visual=False, target_marks=False, supply="feeder",
               cure_settle_steps=25)
SPEC_V2 = dict(head_gap=0.001, mortar_impl="bed", mortar_visual=True, target_marks=True, supply="scatter",
               cure_settle_steps=40)   # 2 s settle before cure / bed laying (blueprint 4.8.2 first comparison value)
SPEC_KEYS = tuple(SPEC_V2)


def scene_spec(cfg: SceneConfig) -> dict:
    """The spec fields that change the task geometry / physics / observations (recorded with every dataset)."""
    return dict(head_gap=cfg.wall.head_gap, mortar_impl=cfg.mortar_impl, mortar_visual=cfg.mortar_visual,
                target_marks=cfg.target_marks, supply=cfg.supply, cure_settle_steps=cfg.cure_settle_steps,
                feasible_supply=cfg.feasible_supply)


def blueprint_config(mortar: str = "dry", spec: str = "v2", **kw) -> "SceneConfig":
    """SceneConfig matching 설계수행계획서_14조_통합최종본 4.3/4.4: 3 bricks 2+1, 90x42.632x27 mm, 1800 kg/m3,
    bed joint 4.737 mm (equivalent contact layer), 20 Hz control, 1 ms physics.

    spec="v2" (default): 1 mm head joint, continuous mortar bed laid on the settled lower course, floor target outlines + chalk line,
                         bricks scattered near the workspace from the start.
    spec="v1": the 2026-09-18 datasets: 4.737 mm head joint, invisible margin mortar, feeder supply.
    Individual spec fields (SPEC_KEYS) may be overridden through kw, e.g. **collect_config["scene"].
    """
    s = dict(SPEC_V2 if spec == "v2" else SPEC_V1)
    s.update({k: kw.pop(k) for k in list(kw) if k in SPEC_KEYS})
    head_gap = s.pop("head_gap")
    bed = 0.004737 if mortar != "dry" else 0.0
    cfg = SceneConfig(brick=BrickSpec(L=0.09, W=0.042632, H=0.027, density=1800.0),
                      wall=WallSpec(n_courses=2, n_per_course=2, origin_x=-0.10, origin_y=-0.17,
                                    head_gap=head_gap, bed_joint=bed),
                      mortar=mortar, layout="2p1", ctrl_dt=0.05, timestep=0.001, feeder_pos=(0.10, -0.17), **s, **kw)
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
        out = [(w.origin_x - half, w.origin_y, z0, 0.0, L),
               (w.origin_x + half, w.origin_y, z0, 0.0, L),
               (w.origin_x, w.origin_y, z1, 0.0, L)]
        return out[:2] if cfg.first_course_only else out
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


def build_xml(cfg: SceneConfig, brick: BrickSpec, supply_poses, mortar_margin: float, lengths, design=None) -> str:
    n = len(supply_poses)
    hy, hz = brick.W / 2, brick.H / 2
    mass = brick.mass
    # MuJoCo direct-form solref is mass-normalised: stiffness in 1/s^2, damping in 1/s.
    # A brick sags g/k under its own weight, so k = g / sag ; b = 2*zeta*sqrt(k).
    k = 9.81 / cfg.mortar_sag
    b = 2.0 * cfg.mortar_zeta * np.sqrt(k)
    mortar_on = cfg.mortar in ("mortarA", "mortarB")
    bed_impl = mortar_on and cfg.mortar_impl == "bed" and cfg.layout == "2p1"
    tb = cfg.wall.bed_joint            # mortar bed thickness
    fr = f'friction="{cfg.mortar_friction} 0.005 0.0001"'
    visual = 'contype="0" conaffinity="0" mass="0" material="mortar"'

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
            f'rgba="{rgba}" {fr} condim="3" priority="1"/>'
            f'</body>'
        )
    beds, pairs = [], []
    if bed_impl:
        # The bed is laid at run time (BrickEnv._update_bed) on the real poses of the two settled lower bricks:
        # slab bed_0 / bed_1 over each brick top (mocap bodies, parked under the floor until then) and bed_j
        # bridging the head joint, so the three form one continuous layer.  contype/conaffinity 0: they touch
        # nothing except through the explicit soft <pair>s with the bricks (never the floor, the arm, each other).
        ov = cfg.bed_overhang
        hxb, hyb = brick.L / 2 + ov, hy + ov
        for kk in range(2):
            lips = ''
            if cfg.mortar_visual:
                for side, tag in ((-1, "f"), (1, "b")):
                    for s in range(5):   # drips down the front/back faces; length/bulge randomised per episode
                        lips += (f'<geom name="lip_{kk}_{tag}{s}" type="box" '
                                 f'pos="{(-0.8 + 0.4 * s) * hxb * 0.92:.5f} {side * (hyb - 0.0008):.5f} {-tb / 2:.5f}" '
                                 f'size="{hxb * 0.18:.5f} 0.0008 0.001" {visual}/>')
                for s in range(3):       # small bumps on the surface (visual only)
                    lips += (f'<geom name="bump_{kk}_{s}" type="box" pos="0 0 {tb / 2:.5f}" '
                             f'size="0.008 0.005 0.0003" {visual}/>')
            beds.append(f'<body name="bed_{kk}" mocap="true" pos="0 0 -1">'
                        f'<geom name="bed_{kk}" type="box" size="{_fmt([hxb, hyb, tb / 2])}" '
                        f'contype="0" conaffinity="0" mass="0" material="mortar" {fr} condim="3"/>{lips}</body>')
        beds.append(f'<body name="bed_j" mocap="true" pos="0 0 -1">'
                    f'<geom name="bed_j" type="box" size="{_fmt([0.004, hyb, tb / 2])}" '
                    f'contype="0" conaffinity="0" mass="0" material="mortar" {fr} condim="3"/></body>')
        for gname in ("bed_0", "bed_1", "bed_j"):
            for j in range(n):
                pairs.append(
                    f'<pair geom1="{gname}" geom2="brick_{j}" condim="4" '
                    f'friction="{cfg.mortar_friction} {cfg.mortar_friction} 0.005 0.0001 0.0001" '
                    f'solref="{-k:.4f} {-b:.4f}" solimp="0.95 0.99 0.001 0.5 2"/>'
                )
    elif mortar_on:
        for i in range(n):
            for j in range(i + 1, n):
                pairs.append(
                    f'<pair geom1="brick_{i}" geom2="brick_{j}" condim="4" '
                    f'friction="{cfg.mortar_friction} {cfg.mortar_friction} 0.005 0.0001 0.0001" '
                    f'margin="{mortar_margin:.5f}" solref="{-k:.4f} {-b:.4f}" '
                    f'solimp="0.95 0.99 0.001 0.5 2"/>'
                )
    marks = []
    if cfg.target_marks and design is not None:
        z = 0.0002
        bw, bh = 0.00075, 0.00015           # outline bar half-width / half-height
        outline = 'contype="0" conaffinity="0" mass="0" rgba="0.10 0.25 0.75 1"'
        chalk = 'contype="0" conaffinity="0" mass="0" rgba="0.06 0.06 0.08 1"'
        for (x, y, zc, yaw, Li) in design:
            if zc > brick.H:                # only the course on the floor has a footprint to mark
                continue
            hxd, hyd = Li / 2, brick.W / 2
            marks += [f'<geom type="box" pos="{_fmt([x, y - hyd, z])}" size="{_fmt([hxd, bw, bh])}" {outline}/>',
                      f'<geom type="box" pos="{_fmt([x, y + hyd, z])}" size="{_fmt([hxd, bw, bh])}" {outline}/>',
                      f'<geom type="box" pos="{_fmt([x - hxd, y, z])}" size="{_fmt([bw, hyd, bh])}" {outline}/>',
                      f'<geom type="box" pos="{_fmt([x + hxd, y, z])}" size="{_fmt([bw, hyd, bh])}" {outline}/>']
        # chalk line (먹선) snapped along the design wall face, running past both ends of the wall
        xs = [d[0] - d[4] / 2 for d in design] + [d[0] + d[4] / 2 for d in design]
        x0, x1 = min(xs) - 0.06, max(xs) + 0.06
        y_face = cfg.wall.origin_y - brick.W / 2
        marks.append(f'<geom type="box" pos="{_fmt([(x0 + x1) / 2, y_face, z])}" '
                     f'size="{_fmt([(x1 - x0) / 2, 0.0004, bh])}" {chalk}/>')
        for xe in (min(xs), max(xs)):       # short cross ticks at the wall ends
            marks.append(f'<geom type="box" pos="{_fmt([xe, y_face - 0.012, z])}" size="{_fmt([0.0004, 0.012, bh])}" {chalk}/>')
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
    <texture type="2d" name="mortar" builtin="checker" mark="random" random="0.45" rgb1="0.55 0.53 0.49"
      rgb2="0.52 0.50 0.46" markrgb="0.40 0.38 0.35" width="256" height="256"/>
    <material name="mortar" texture="mortar" texuniform="true" texrepeat="40 40" reflectance="0.0" shininess="0.05"
      specular="0.1"/>
  </asset>
  <worldbody>
    <light pos="0.3 -0.6 1.2" dir="-0.2 0.4 -1" directional="true" castshadow="true"/>
    <light pos="-0.5 -0.2 1.0" dir="0.4 0.1 -1" directional="true" castshadow="false"/>
    <geom name="floor" size="0 0 0.05" type="plane" material="ground" friction="0.9 0.005 0.0001"/>
    <site name="wall_origin" pos="{_fmt([cfg.wall.origin_x, cfg.wall.origin_y, 0])}" size="0.003" rgba="0 1 0 0.4"/>
    <camera name="front" pos="0.02 -0.64 0.36" xyaxes="1 0 0 0 0.62 0.78"/>
    <camera name="top" pos="-0.02 -0.18 0.70" xyaxes="1 0 0 0 1 0"/>
    {''.join(marks)}
    {''.join(bricks)}
    {''.join(beds)}
  </worldbody>
  <contact>
    {''.join(pairs)}
  </contact>
  <equality>
    {''.join(welds)}
  </equality>
</mujoco>
"""


def _augmented_arm_xml(src: Path) -> str:
    """so_arm100.xml plus a TCP site, a wrist camera and a wrist force/torque sensor on Fixed_Jaw.

    The 'ft' site sits at the Fixed_Jaw body origin (the wrist-roll axis); MuJoCo's force/torque sensors there report the
    interaction force/torque transmitted from Wrist_Pitch_Roll to the gripper (gripper + anything it holds), in the site
    frame (2026-09-23; used by brick_sim.grasp_gate for the weight check, simulation only).  Adding a site and sensors
    does not change the dynamics, so earlier datasets and evaluations stay valid.
    """
    txt = src.read_text(encoding="utf-8")
    marker = '<geom class="finger_collision" name="fixed_jaw_pad_1"'
    inject = (
        '<site name="tcp" pos="-0.004 -0.097 0" quat="0.7071068 0.7071068 0 0" size="0.003" rgba="0 0 1 0.5"/>'
        '<camera name="wrist" pos="0.0 -0.02 0.045" xyaxes="1 0 0 0 0 -1" fovy="75"/>'
        '<site name="ft" pos="0 0 0" size="0.002" rgba="1 0 0 0.3"/>'
    )
    assert marker in txt, "unexpected so_arm100.xml layout"
    txt = txt.replace(marker, inject + "\n                " + marker, 1)
    sensors = '  <sensor>\n    <force name="wrist_force" site="ft"/>\n    <torque name="wrist_torque" site="ft"/>\n  </sensor>\n</mujoco>'
    assert txt.rstrip().endswith("</mujoco>")
    txt = txt.rstrip()[: -len("</mujoco>")] + sensors + "\n"
    return txt


def _augment_arm_xml(src: Path, dst: Path):
    """Write the augmented arm model next to the original (regenerated whenever the augmentation changes)."""
    txt = _augmented_arm_xml(src)
    if not dst.exists() or dst.read_text(encoding="utf-8") != txt:
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
        for attempt in range(5000):
            brick, poses = self._sample_episode_once()
            if not self.cfg.valid_supply or self._valid_supply_layout(brick, poses):
                self.supply_sample_attempts = attempt + 1
                return brick, poses
        raise ValueError("Cannot sample a valid supply layout; check position/yaw ranges")

    def _valid_supply_layout(self, brick, poses):
        if self.cfg.supply != "scatter":
            raise ValueError("valid_supply requires scatter supply")
        boxes = []
        for x, y, _, yaw in poses:
            if not 0.13 <= np.hypot(x, y) <= 0.26:
                return False
            axes = np.array([[np.cos(yaw), np.sin(yaw)], [-np.sin(yaw), np.cos(yaw)]])
            corners = np.array([np.array([x, y]) + sx * brick.L / 2 * axes[0] + sy * brick.W / 2 * axes[1]
                                for sx in (-1, 1) for sy in (-1, 1)])
            wall_right = self.cfg.wall.origin_x + (brick.L + self.cfg.wall.head_gap) / 2 + brick.L / 2
            if corners[:, 0].min() < wall_right + 0.015:
                return False
            boxes.append((corners, axes))
        for i, (a, aa) in enumerate(boxes):
            for b, ba in boxes[i + 1:]:
                # Separating-axis test with a 10 mm gap; no intersecting initial bricks.
                if not any((a @ axis).max() + 0.01 < (b @ axis).min() or
                           (b @ axis).max() + 0.01 < (a @ axis).min() for axis in np.vstack([aa, ba])):
                    return False
        return True

    def _sample_episode_once(self):
        cfg = self.cfg
        b = cfg.brick
        s = cfg.size_rand
        L = b.L * (1 + self.rng.uniform(-s, s))
        W = b.W * (1 + self.rng.uniform(-s, s))
        H = b.H * (1 + self.rng.uniform(-s, s))
        brick = BrickSpec(L=L, W=W, H=H, density=b.density)
        n = 2 if cfg.first_course_only else n_bricks_for(cfg.wall, cfg.layout)
        poses = []
        self.feeder_targets = []
        scatter = cfg.supply == "scatter" and n <= len(cfg.supply_slots)
        slots = list(cfg.supply_slots)
        if scatter:
            self.rng.shuffle(slots)   # which brick lies where changes every episode
        for i in range(n):
            if scatter:
                # all bricks lie in the workspace from the start: random slot, +-pos_rand jitter, +-yaw
                sx, sy = slots[i]
                fx = sx + self.rng.uniform(-cfg.pos_rand, cfg.pos_rand)
                fy = sy + self.rng.uniform(-cfg.pos_rand, cfg.pos_rand)
                fyaw = np.deg2rad(self.rng.uniform(-cfg.supply_yaw_deg, cfg.supply_yaw_deg))
                poses.append((fx, fy, H / 2 + 0.0005, fyaw))
            else:
                # parked in a row far from the workspace; staged to the feeder slot when it is that brick's turn
                poses.append((cfg.park_pos[0] + 0.07 * (i % 5), cfg.park_pos[1] + 0.06 * (i // 5), H / 2 + 0.0005, 0.0))
                fx = cfg.feeder_pos[0] + self.rng.uniform(-cfg.pos_rand, cfg.pos_rand)
                fy = cfg.feeder_pos[1] + self.rng.uniform(-cfg.pos_rand, cfg.pos_rand)
                fyaw = np.deg2rad(self.rng.uniform(-cfg.supply_yaw_deg, cfg.supply_yaw_deg))
            self.feeder_targets.append((fx, fy, fyaw))
        self._scatter = scatter
        return brick, poses

    def reset(self, seed: int | None = None):
        if seed is not None:
            self.rng = np.random.default_rng(seed)
        self.feasibility_rejects = 0
        for _ in range(500):
            self._build_episode()
            if not self.cfg.feasible_supply:
                break
            from .feasibility import layout_feasibility   # lazy: feasibility imports expert imports scene
            self.supply_feasibility = layout_feasibility(self)
            if all(f["ok"] for f in self.supply_feasibility):
                break
            self.feasibility_rejects += 1
        else:
            raise ValueError("Cannot sample a feasible supply layout; check position/yaw ranges")
        return self._finish_reset()

    def _build_episode(self):
        self.brick, self.supply_poses = self._sample_episode()
        self.design = design_poses(self.cfg, self.brick)
        self.brick_L = np.array([d[4] for d in self.design])
        margin = self.cfg.wall.bed_joint if self.cfg.mortar != "dry" else 0.0
        xml = build_xml(self.cfg, self.brick, self.supply_poses, margin, list(self.brick_L), self.design)
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
        d.qpos[self.arm_qidx] = HOME_QPOS[:5]
        d.qpos[self.jaw_qidx] = JAW_OPEN
        mujoco.mj_forward(m, d)

    def _finish_reset(self):
        m, d = self.model, self.data
        self.cured = np.zeros(self.n_bricks, dtype=bool)
        self.settle_count = np.zeros(self.n_bricks, dtype=int)
        # mortar bed (spec v2): laid once the lower course has settled
        self.bed_impl = self.cfg.mortar in ("mortarA", "mortarB") and self.cfg.mortar_impl == "bed" and self.cfg.layout == "2p1"
        self.bed_laid = False
        self.bed_count = np.zeros(self.n_bricks, dtype=int)
        self.bed_bricks = []
        if self.bed_impl:
            self.bed_mocap = [m.body_mocapid[m.body(f"bed_{kk}").id] for kk in ("0", "1", "j")]
            self.bed_geom_j = m.geom("bed_j").id
            tb = self.cfg.wall.bed_joint
            if self.cfg.mortar_visual:
                # randomise the wet look per episode: drip length / bulge and bump placement
                hxb = self.brick.L / 2 + self.cfg.bed_overhang
                for kk in range(2):
                    for tag in ("f", "b"):
                        for s in range(5):
                            gid = m.geom(f"lip_{kk}_{tag}{s}").id
                            drop = self.rng.uniform(0.0004, 0.0028)
                            m.geom_size[gid, 0] = hxb * self.rng.uniform(0.10, 0.19)
                            m.geom_size[gid, 2] = drop
                            m.geom_pos[gid, 2] = -tb / 2 - drop + 0.0006
                            m.geom_pos[gid, 1] += np.sign(m.geom_pos[gid, 1]) * self.rng.uniform(0.0, 0.0006)
                    for s in range(3):
                        gid = m.geom(f"bump_{kk}_{s}").id
                        m.geom_pos[gid, 0] = self.rng.uniform(-0.7, 0.7) * hxb
                        m.geom_pos[gid, 1] = self.rng.uniform(-0.5, 0.5) * self.brick.W / 2
                        m.geom_size[gid, 0] = self.rng.uniform(0.005, 0.012)
                        m.geom_size[gid, 1] = self.rng.uniform(0.003, 0.008)
                        m.geom_size[gid, 2] = self.rng.uniform(0.0002, 0.0005)
            else:
                for gname in ("bed_0", "bed_1", "bed_j"):
                    m.geom_rgba[m.geom(gname).id, 3] = 0.0
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
        """Teleport brick i from the park row to the feeder slot (simulates an automatic brick feeder).

        No-op with supply="scatter": every brick already lies at its (random) place in the workspace.
        """
        if getattr(self, "_scatter", False):
            return
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

    def grasped(self, i):
        """Privileged simulation check: brick contacts both jaws and stays near the TCP."""
        bid = self.brick_bids[i]
        jaws = {self.model.body(name).id for name in ("Fixed_Jaw", "Moving_Jaw")}
        touched = set()
        for contact in self.data.contact:
            if contact.dist > 0.0005:
                continue
            b1, b2 = self.model.geom_bodyid[contact.geom1], self.model.geom_bodyid[contact.geom2]
            if b1 == bid and b2 in jaws:
                touched.add(b2)
            if b2 == bid and b1 in jaws:
                touched.add(b1)
        return touched == jaws and np.linalg.norm(self.brick_pose(i)[0] - self.tcp_pose()[0]) < 0.05

    def qpos_arm(self):
        return np.r_[self.data.qpos[self.arm_qidx], self.data.qpos[self.jaw_qidx]].astype(np.float32)

    def env_state(self):
        return np.r_[self.brick_poses().ravel(), self.brick_L, self.brick.W, self.brick.H].astype(np.float32)

    def wrist_ft(self):
        """Wrist force/torque sensor (site 'ft' on Fixed_Jaw), rotated into the world frame: (F[3] N, T[3] Nm).

        Simulation-only signal: what the wrist transmits to the gripper, i.e. gripper weight + held load + inertial forces.
        """
        m, d = self.model, self.data
        f = d.sensordata[m.sensor("wrist_force").adr[0]: m.sensor("wrist_force").adr[0] + 3]
        t = d.sensordata[m.sensor("wrist_torque").adr[0]: m.sensor("wrist_torque").adr[0] + 3]
        R = d.site_xmat[m.site("ft").id].reshape(3, 3)
        return R @ f, R @ t

    def gripper_mass(self):
        """Mass hanging below the wrist-roll axis (Fixed_Jaw subtree: both jaws), kg."""
        return float(self.model.body_subtreemass[self.model.body("Fixed_Jaw").id])

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
        if self.bed_impl and not self.bed_laid:
            self._update_bed()
        return self.observe()

    def brick_in_slot(self, i, slots=None, tol_xy=0.008, tol_yaw_deg=10.0, tol_tilt_deg=10.0):
        """Index of the design slot brick i correctly occupies (position/yaw/tilt within tolerance), else None."""
        p, q = self.brick_pose(i)
        w, x, y, z = q
        yaw = np.arctan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z))
        tilt = np.degrees(np.arccos(np.clip(1 - 2 * (x * x + y * y), -1, 1)))
        if tilt > tol_tilt_deg:
            return None
        for k in (slots if slots is not None else range(len(self.design))):
            dx, dy, dz, dyaw = self.design[k][:4]
            if np.hypot(p[0] - dx, p[1] - dy) > tol_xy or abs(p[2] - dz) > 0.003:
                continue
            if np.degrees(abs((yaw - dyaw + np.pi / 2) % np.pi - np.pi / 2)) > tol_yaw_deg:
                continue
            return k
        return None

    def _hand_clear(self, p, dist=0.05):
        """True when the TCP is at least `dist` away from point p (the mason's hand is not on the brick)."""
        return np.linalg.norm(self.tcp_pose()[0] - p) > dist

    def _lower_course_settled(self):
        """Indices of bricks correctly placed in a lower-course slot, released, hand clear and static long enough."""
        lower = [k for k, dd in enumerate(self.design) if dd[2] < self.brick.H]
        out = []
        for i in range(self.n_bricks):
            p, _ = self.brick_pose(i)
            v = self.brick_vel(i)
            placed = self.brick_in_slot(i, lower) is not None
            static = np.linalg.norm(v[:3]) < 0.01 and np.linalg.norm(v[3:]) < 0.2
            ok = placed and static and self._hand_clear(p)
            self.bed_count[i] = self.bed_count[i] + 1 if ok else 0
            if self.bed_count[i] >= self.cfg.cure_settle_steps:
                out.append(i)
        return out

    def _update_bed(self):
        """Lay one continuous mortar bed on the real top faces of the two settled lower bricks (spec v2).

        Real practice: the bed is spread on the finished course, not carried on the brick.  It is laid only once
        both lower bricks are *correctly* in their slots (so a shoved brick is never pinned under the bed and can
        still be re-placed); nothing is laid after the top brick.
        """
        idx = self._lower_course_settled()
        if len(idx) < 2:
            return
        m, d = self.model, self.data
        tb = self.cfg.wall.bed_joint
        L, H = self.brick.L, self.brick.H
        idx = sorted(idx[:2], key=lambda i: self.brick_pose(i)[0][0])   # left, right
        tops = []
        for kk, i in enumerate(idx):
            p, q = self.brick_pose(i)
            R = _quat_rotmat(q)
            c = p + R @ np.array([0.0, 0.0, H / 2 + tb / 2])
            d.mocap_pos[self.bed_mocap[kk]] = c
            d.mocap_quat[self.bed_mocap[kk]] = q
            tops.append((p, c))
        (pl, cl), (pr, cr) = tops
        gap = max((pr[0] - L / 2) - (pl[0] + L / 2), 0.0)
        m.geom_size[self.bed_geom_j, 0] = gap / 2 + self.cfg.bed_overhang + 0.002
        d.mocap_pos[self.bed_mocap[2]] = [(pl[0] + pr[0]) / 2, (cl[1] + cr[1]) / 2, (cl[2] + cr[2]) / 2]
        d.mocap_quat[self.bed_mocap[2]] = [1, 0, 0, 0]
        mujoco.mj_forward(m, d)
        self.bed_laid = True
        self.bed_bricks = list(idx)
        self.bed_t = self.t

    def _update_cure(self):
        """Cure a brick once it is on the wall line, nearly static and released (mortarB).

        MuJoCo weld eq_data[3:10] = relpose = pose of body2 (world) relative to body1, i.e. the inverse
        of the brick's world pose (verified empirically: 0.07 mm drift after activation).
        """
        m, d = self.model, self.data
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
            # the hand must be off the brick: a brick about to be re-grasped (recovery) must not cure under the jaw
            self.settle_count[i] = self.settle_count[i] + 1 if (on_wall and static and self._hand_clear(p)) else 0
            if self.settle_count[i] >= self.cfg.cure_settle_steps:
                eq = m.equality(f"cure_{i}").id
                qi = np.r_[q[0], -q[1:]]
                m.eq_data[eq, 0:3] = 0.0
                m.eq_data[eq, 3:6] = _quat_rotmat(qi) @ (-p)
                m.eq_data[eq, 6:10] = qi
                m.eq_data[eq, 10] = 1.0
                d.eq_active[eq] = 1
                self.cured[i] = True

    def kick_brick(self, i, rng, speed=(0.3, 0.6), tip_prob=0.15):
        """Knock brick i: planar shove (0.3-0.6 m/s -> slides ~0.6-2.5 cm at mu=0.75) with an optional tipping
        component.  Physics only; the caller decides what the arm does meanwhile.  Returns a log dict."""
        dof = self.brick_dofadr[i]
        ang = rng.uniform(-np.pi, np.pi)
        v = rng.uniform(*speed)
        wz = rng.uniform(-4.0, 4.0)
        tip = rng.random() < tip_prob
        self.data.qvel[dof: dof + 3] = [v * np.cos(ang), v * np.sin(ang), 0.0]
        self.data.qvel[dof + 3: dof + 6] = [rng.uniform(-7, 7) if tip else 0.0, rng.uniform(-7, 7) if tip else 0.0, wz]
        return {"brick": int(i), "t": int(self.t), "speed": float(v), "tip": bool(tip)}

    def settle(self, n_ctrl_steps=25):
        """Let physics run with the arm held still (used before metrics)."""
        for _ in range(n_ctrl_steps):
            self.step(self.data.ctrl[self.act_ids].copy())

    def close(self):
        pass
