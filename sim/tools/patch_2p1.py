# -*- coding: utf-8 -*-
"""Add the team blueprint's 2+1 task (4.3/4.4) and its 3 metrics (4.9) to brick_sim."""
import io
from pathlib import Path

SIM = Path(__file__).resolve().parents[1]

# ---------------- scene.py ----------------
p = SIM / "brick_sim" / "scene.py"
s = io.open(p, encoding="utf-8").read()

def rep(old, new):
    global s
    assert old in s, old[:60]
    s = s.replace(old, new, 1)

rep('''    ctrl_dt: float = 0.04                   # 25 Hz control
    seed: int = 0
''', '''    ctrl_dt: float = 0.04                   # 25 Hz control
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
''')

rep('''def design_poses(cfg: SceneConfig, brick: BrickSpec):
    """Design centres in laying order: list of (x, y, z, yaw, length)."""
    w = cfg.wall
    L, g = brick.L, w.head_gap
    pitch = L + g
    poses = []
''', '''def design_poses(cfg: SceneConfig, brick: BrickSpec):
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
''')

rep('''def n_bricks_for(wall: WallSpec) -> int:
    return sum((wall.n_per_course + 1) if k % 2 else wall.n_per_course for k in range(wall.n_courses))''',
'''def n_bricks_for(wall: WallSpec, layout: str = "wall") -> int:
    if layout == "2p1":
        return 3
    return sum((wall.n_per_course + 1) if k % 2 else wall.n_per_course for k in range(wall.n_courses))''')
rep('        n = n_bricks_for(cfg.wall)\n        poses = []', '        n = n_bricks_for(cfg.wall, cfg.layout)\n        poses = []')
rep('<option timestep="0.002" cone="elliptic" impratio="10" noslip_iterations="3"/>',
    '<option timestep="{cfg.timestep}" cone="elliptic" impratio="10" noslip_iterations="3"/>')
# cure: on-wall test for 2p1 uses the same x-range logic; widen with layout
rep('''        x_lo = w.origin_x - self.brick.L
        x_hi = w.origin_x + (w.n_per_course - 1) * (self.brick.L + w.head_gap) + self.brick.L''',
'''        x_lo = w.origin_x - self.brick.L * 1.5
        x_hi = w.origin_x + (w.n_per_course - 1) * (self.brick.L + w.head_gap) + self.brick.L * 1.5''')
io.open(p, "w", encoding="utf-8").write(s)

# ---------------- metrics.py: the blueprint's 3 metrics ----------------
p = SIM / "brick_sim" / "metrics.py"
s = io.open(p, encoding="utf-8").read()
s += '''

# ---------------------------------------------------------------------------
# Blueprint 4.9: three metrics (3D IoU, mean height error E_h, wall-face max deviation E_f)
# ---------------------------------------------------------------------------
import itertools


def _assign(P, D):
    """One-to-one brick->slot assignment minimising the sum of centre distances (blueprint 4.9.1)."""
    n = len(D)
    best, best_perm = None, None
    for perm in itertools.permutations(range(n)):
        c = sum(np.linalg.norm(P[perm[i], :3] - D[i, :3]) for i in range(n))
        if best is None or c < best - 1e-12:
            best, best_perm = c, perm
    return list(best_perm)


def brick_corners(center, q, L, W, H):
    _, _, R = quat_to_yaw_tilt(q)
    c = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            for sz in (-1, 1):
                c.append(center + R @ np.array([sx * L / 2, sy * W / 2, sz * H / 2]))
    return np.array(c)


def compute_metrics3(poses, design, brick, wall, res=0.0005):
    """Return dict(iou, E_h_mm, E_f_mm, assignment) per blueprint 4.9.

    - IoU: union of the 3 real boxes vs union of the 3 target boxes (voxel grid, default 0.5 mm)
    - E_h: mean |z_i - z_i*| over the 3 assigned bricks, mm
    - E_f: max over the 12 front-face corners of |y_corner - y*| where y* = origin_y - W/2 (fixed design face), mm
    """
    N = len(design)
    L, W, H = brick.L, brick.W, brick.H
    P = np.asarray(poses)[:N]
    D = np.asarray(design)[:N]
    perm = _assign(P, D)
    Pa = P[perm]
    E_h = float(np.mean(np.abs(Pa[:, 2] - D[:, 2])) * 1000)
    y_star = wall.origin_y - W / 2
    front = []
    for i in range(N):
        cs = brick_corners(Pa[i, :3], Pa[i, 3:7], D[i, 4] if D.shape[1] > 4 else L, W, H)
        # the 4 corners with the smallest y are the (design) front face; take those
        front.append(cs[np.argsort(cs[:, 1])[:4]])
    front = np.vstack(front)
    E_f = float(np.max(np.abs(front[:, 1] - y_star)) * 1000)
    Lvec = D[:, 4] if D.shape[1] > 4 else np.full(N, L)
    iou = float(_voxel_iou(Pa, D[:, :4], Lvec, W, H, res=res))
    return {"iou": iou, "E_h_mm": E_h, "E_f_mm": E_f, "assignment": perm}
'''
io.open(p, "w", encoding="utf-8").write(s)

# ---------------- expert.py: grasp height for the taller brick ----------------
p = SIM / "brick_sim" / "expert.py"
s = io.open(p, encoding="utf-8").read()
# GRASP_DZ was tuned for 16 mm bricks; for 27 mm bricks grip the upper part too: scale with H
s = s.replace("GRASP_DZ = 0.004        # TCP above brick centre when grasping (grip the upper part of the brick)",
              "GRASP_DZ = 0.004        # TCP above brick centre when grasping (16 mm bricks); scaled with H in plan_brick")
s = s.replace("        gx, gy, gz = p0[0], p0[1], p0[2] + GRASP_DZ",
              "        dz_grip = GRASP_DZ + max(0.0, (env.brick.H - 0.016) / 2)   # keep the pads on the upper half\n        gx, gy, gz = p0[0], p0[1], p0[2] + dz_grip")
s = s.replace("        pz = dz + GRASP_DZ + PLACE_CLEAR", "        pz = dz + dz_grip + PLACE_CLEAR")
io.open(p, "w", encoding="utf-8").write(s)
print("patched scene/metrics/expert for 2+1")
