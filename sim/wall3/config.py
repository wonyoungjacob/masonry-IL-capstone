"""3층 벽체 파일럿 설정 (실험설계 md 10절, 지시서 3절). 모든 값은 실행 결과와 함께 저장한다(to_dict).

좌표: 세계 원점 = 로봇 받침대 아래 바닥 중심. x = 벽 길이 방향, y = 벽면에 수직(+y가 로봇에서 벽 쪽), z = 연직 위.
벽 중심선 y = WALL_Y(0.6 m), 벽 중앙 x = 0. 벽의 '앞면'(평가지표 md의 y_f)은 로봇 반대쪽 면(y = WALL_Y + W/2)이며
앞 카메라가 이쪽에서 벽을 본다. 공급대는 로봇 뒤쪽(y < 0).
"""
from dataclasses import dataclass, field, asdict

import numpy as np

from wall3 import gripper as G

# ---- brick (P2) and wall (평가지표 md 1절) -------------------------------------------------------------------------
L_FULL, L_HALF, W, H = 0.190, 0.090, 0.090, 0.057
RHO = 2000.0                    # kg/m^3 (v8)
MU_BRICK = 0.6                  # brick friction (floor and table use the same value)
JOINT = 0.010                   # bed and head joint (KCS 41 34 02 3.4.2(1))
WALL_Y = 0.60                   # wall centre line, 0.6 m in front of the base (P4)


def design_slots():
    """16 design slots in laying order (P7: course 1 L→R, course 2 L→R with half bricks at the ends, course 3 L→R).
    Each: dict(course, index, x, y, z, yaw, L, half)."""
    out = []
    pitch = L_FULL + JOINT
    xs_full = [(-2 + i) * pitch for i in range(5)]                      # -0.4 .. 0.4
    z = [H / 2, H / 2 + H + JOINT, H / 2 + 2 * (H + JOINT)]
    x_half = 0.5 * (5 * L_FULL + 4 * JOINT) - L_HALF / 2               # 0.45
    xs_c2 = [-x_half] + [(-1.5 + i) * pitch for i in range(4)] + [x_half]
    for k, xs in enumerate([xs_full, xs_c2, xs_full]):
        for i, x in enumerate(xs):
            half = (k == 1 and i in (0, len(xs) - 1))
            out.append(dict(course=k + 1, index=i, x=float(x), y=WALL_Y, z=float(z[k]), yaw=0.0,
                            L=L_HALF if half else L_FULL, half=half))
    return out


# ---- supply table (P5): set from the reach map (단계 2, sim/wall3/reach_map.py) ---------------------------------------
# slot centre (x, y) on the table; slot i holds the brick for design slot i. Brick long axis along x.
# Chosen by reach_map.py (2026-10-15, outputs/wall3/reach_map_try3): 16 of 18 grid candidates (rows y = -0.25 … -0.79,
# columns 0.26 m apart, base distance 0.55 ~ 0.95 m) assigned to the wall slots to minimise the pan travel.
SUPPLY_SLOTS = ((-0.91, -0.25), (-0.65, -0.25), (+0.91, -0.25), (+0.65, -0.25), (+0.65, -0.43), (-0.65, -0.43), (-0.39, -0.43), (-0.39, -0.79), (+0.65, -0.61), (+0.39, -0.43), (+0.39, -0.61), (-0.65, -0.61), (-0.39, -0.61), (+0.39, -0.79), (+0.13, -0.79), (+0.13, -0.61))


# 철수 자세 (reach_map.py): TCP (0, 0.40, 0.75) m, gripper down. Every brick starts and ends here.
RETRACT_TCP = (0.0, 0.40, 0.75)
RETRACT_Q = (-2.020805, -2.131279, 2.263128, -1.702647, -1.570801, -0.450007)


@dataclass
class SceneConfig:
    # robot (P3)
    pedestal_h: float = 0.60
    pedestal_half: float = 0.15                 # square pedestal half-size (m)
    # supply table (P5)
    table_h: float = 0.35                       # table top height (m)
    table_x: tuple = (-1.00, 1.00)
    table_y: tuple = (-1.00, -0.17)
    supply_slots: tuple = SUPPLY_SLOTS          # ((x, y), ...) x16, design-slot order
    scatter_pos: float = 0.010                  # P6: +-10 mm
    scatter_yaw_deg: float = 10.0               # P6: +-10 deg
    # mortar (mortarB as in brick_sim, scaled to a 10 mm joint)
    mortar_sag: float = 0.0005 * 0.010 / 0.004737   # 1.06 mm
    mortar_zeta: float = 1.0
    mortar_friction: float = 0.75
    bed_overhang: float = 0.002
    cure_settle_steps: int = 40                 # 2 s at 20 Hz
    hand_clear: float = 0.05                    # TCP farther than this from the brick centre = hand off the brick
    # bed laying check (brick_sim brick_in_slot tolerances)
    slot_tol_xy: float = 0.008
    slot_tol_z: float = 0.003
    slot_tol_yaw_deg: float = 10.0
    slot_tol_tilt_deg: float = 10.0
    # physics (P8, 10.2) — solver options as brick_sim/scene.py (지난 실험)
    timestep: float = 0.001
    ctrl_dt: float = 0.05                       # 20 Hz
    impratio: float = 10.0
    noslip_iterations: int = 3
    # cameras (P9, 10.3)
    img: int = 128
    hi_w: int = 1280
    hi_h: int = 960
    # gripper (P1, A1+)
    gripper: G.GripperConfig = field(default_factory=lambda: G.a1plus(4.0))
    grasp_clear: float = 0.005                  # ③ deepest finger point above the brick bottom (2 mm let the fingertips touch the table: pads sink ~2 mm into the brick under 50 N and keep descending as they close)

    def to_dict(self):
        d = asdict(self)
        return d


def slot_distance(x, y):
    return float(np.hypot(x, y))
