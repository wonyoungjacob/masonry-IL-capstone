"""건식 환경의 채점: wall3.spec_metrics(평가지표 md 구현)를 건식 설계 높이로 부르고, ① 가로줄눈을 판정에서 뺀다.

시방 합격(건식) = 16자리 채움 + ② 선 및 면 + ③ 수직도 + ④ 평면상 위치(각 6 mm) + ⑤ 벽 두께. ①은 값만 남기고 평가하지 않는다.
장 단위 기록(piece_record): 채움, 설계 대비 자세 오차, 이미 놓인 벽돌이 밀린 최대 거리.
모든 측정은 시뮬레이터 참값으로 하며 채점에만 쓴다.
"""
import numpy as np

from wall3.config import W, H, WALL_Y
from wall3.poses import yaw_of_quat
from wall3.spec_metrics import evaluate, EXIST_XY, EXIST_Z, EXIST_TILT

ITEMS = ("2_line_plane", "3_plumb", "4_position", "5_thickness")


def evaluate_dry(env):
    lengths = [s["L"] for s in env.design]
    r = evaluate(env.brick_poses(), lengths, env.design, W, H, front_y=WALL_Y + W / 2)
    r["1_bed_joint"]["evaluated"] = False
    r["items_pass_wet"] = r["items_pass"]                 # with ① (not used: there is no mortar)
    r["items_pass"] = bool(all(r[k]["pass"] for k in ITEMS))
    r["spec_pass"] = bool(r["exists"] and r["items_pass"])
    r["spec_items"] = list(ITEMS)
    return r


def _tilt_deg(q):
    w, x, y, z = q
    return float(np.degrees(np.arccos(np.clip(1 - 2 * (x * x + y * y), -1, 1))))


def brick_error(env, i, k=None):
    """Pose error of brick i against design slot k (default i): horizontal mm, height mm, yaw deg (folded to ±90), tilt deg,
    and the loose presence check of spec_metrics (채움)."""
    s = env.design[i if k is None else k]
    p, q = env.brick_pose(i)
    e = (p - [s["x"], s["y"], s["z"]]) * 1000.0
    yaw = np.degrees((yaw_of_quat(q) - s["yaw"] + np.pi / 2) % np.pi - np.pi / 2)
    tilt = _tilt_deg(q)
    filled = bool(np.hypot(e[0], e[1]) <= EXIST_XY * 1000 and abs(e[2]) <= EXIST_Z * 1000 and tilt < EXIST_TILT)
    return {"err_mm": e.round(3).tolist(), "xy_err_mm": float(np.hypot(e[0], e[1])), "z_err_mm": float(e[2]),
            "yaw_err_deg": float(yaw), "tilt_deg": tilt, "filled": filled}


def piece_record(env, k, poses_start):
    """Brick-level outcome of slot k. poses_start: brick poses (16 × 7) when the trial started (after the scene settled)."""
    r = brick_error(env, k)
    now = env.brick_poses()
    moved = [float(np.linalg.norm(now[i, :3] - poses_start[i, :3]) * 1000) for i in range(k)]
    prev_ok = all(brick_error(env, i)["filled"] for i in range(k))
    r["placed_moved_max_mm"] = max(moved) if moved else 0.0
    r["placed_still_filled"] = bool(prev_ok)
    return r
