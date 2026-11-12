"""개인 연구 설정: 건식 환경 dry_v1, 시작값 구역, 카메라 위치 후보, 깊이 잡음, 자원 한도.

좌표는 wall3와 같다(세계 원점 = 로봇 받침대 아래 바닥 중심, 벽 중심선 y = +0.60, 공급대 y = −1.00 ~ −0.17, 윗면 0.35 m).
모든 값은 결과와 함께 저장한다(to_dict, sha).
"""
import hashlib
import json
from dataclasses import dataclass, field

import numpy as np

from wall3.config import SceneConfig, design_slots, H, W, L_FULL, WALL_Y

ENV_VERSION = "dry_v1"

# ---- 시작값 구역 (지시 문서 2절). 사기설용 700000 ~ 739999는 쓰지 않는다 -------------------------------------------------
SEED_ZONES = {
    "geom": (800000, 800019),        # 기하 선별용 대본 궤적 (2단계)
    "dev": (800200, 800299),         # 측정기 · 코드 개발용 (스스로 정함: 800000 구역 안의 쓰지 않는 값, 보고 수치에 안 씀)
    "script": (800100, 800149),      # 대본 통과 확인 (1단계)
    "demo": (810000, 819999),        # 시연 수집
    "select": (820000, 820099),      # 카메라 선정용 시험 배치 (3 · 4단계). 그 뒤 어떤 보고 수치에도 다시 쓰지 않는다
    "nominal": (830000, 830099),     # 명목 조건 확인 (5단계, 개발 배치)
}
LOCKED = (840000, 10**9)             # 본 실험 시험 배치: 사용자가 허락하기 전에는 쓰지 않는다
FORBIDDEN = (700000, 739999)         # 사기설용


def check_seeds(zone, seeds):
    lo, hi = SEED_ZONES[zone]
    bad = [int(s) for s in seeds if not lo <= int(s) <= hi]
    if bad:
        raise SystemExit(f"시작값 {bad[:5]} 은 구역 {zone!r} ({lo} ~ {hi}) 밖")
    return [int(s) for s in seeds]


# ---- 건식 벽 -----------------------------------------------------------------------------------------------------------
COURSE_H = H                         # 단 높이 = 벽돌 두께 57 mm (모르타르 없음)


def dry_design():
    """16 design slots, dry stacking: same x / y / yaw as wall3 (10 mm head gap left empty), z = H/2 + (course − 1)·H."""
    out = design_slots()
    for s in out:
        s["z"] = float(H / 2 + (s["course"] - 1) * COURSE_H)
    return out


def dry_scene(**kw) -> SceneConfig:
    """main_v1 scene values (robot, gripper, supply table, scatter, control rate), env_version dry_v1.
    The mortar fields stay in the dict but are never used: prl.env.DryEnv never lays a bed and never cures a brick."""
    return SceneConfig(env_version=ENV_VERSION, **kw)


DRY_RULES = {
    "mortar": "none (no bed slabs, no cure weld, no joint model)",
    "course_height_m": COURSE_H,
    "head_gap_m": 0.010,
    "placed_bricks": "held by friction only",
    "spec_items": ["2_line_plane", "3_plumb", "4_position", "5_thickness"],
    "spec_not_evaluated": ["1_bed_joint"],
    "brick_time_limit_s": 17.0,
}

# ---- 카메라 ------------------------------------------------------------------------------------------------------------
RAW_W, RAW_H = 1280, 960             # 원본 영상 (색 + 깊이)
POLICY_IMG = 224                     # 정책 입력: 원본을 비율 유지로 줄이고(224 × 168) 위아래 여백을 채움


def fovy_from_hfov(hfov_deg, w=RAW_W, h=RAW_H):
    return float(np.degrees(2 * np.arctan(np.tan(np.radians(hfov_deg) / 2) * h / w)))


FOVY_D435 = fovy_from_hfov(87.0)     # 가로 87° (D435급) → 세로 70.9° (4:3)
SUPPLY_C = (0.0, -0.52, 0.38)        # 공급 영역 중심 (SB의 보는 점 높이 0.38과 같게)
WALL_C = (0.0, 0.60, 0.09)

# 고정 카메라 후보 (지시 문서 6.2). up: 수직 아래를 보는 카메라는 영상 위쪽 = 세계 +y
FIXED_CAMS = {
    "SA1": dict(pos=(0.0, -0.52, 1.45), target=(0.0, -0.52, 0.0), up=(0, 1, 0), fovy=FOVY_D435, side="supply"),
    "SA2": dict(pos=(0.0, -0.52, 1.75), target=(0.0, -0.52, 0.0), up=(0, 1, 0), fovy=FOVY_D435, side="supply"),
    "SB1": dict(pos=(0.0, -1.25, 1.50), target=(0.0, -0.50, 0.38), up=(0, 0, 1), fovy=FOVY_D435, side="supply"),
    "SB2": dict(pos=(0.0, -1.45, 1.35), target=(0.0, -0.50, 0.38), up=(0, 0, 1), fovy=FOVY_D435, side="supply"),
    "SC1": dict(pos=(1.50, -0.52, 1.50), target=SUPPLY_C, up=(0, 0, 1), fovy=FOVY_D435, side="supply"),
    "SD1": dict(pos=(0.0, 0.20, 1.90), target=SUPPLY_C, up=(0, 0, 1), fovy=FOVY_D435, side="supply"),
    "WA1": dict(pos=(0.0, 0.60, 1.85), target=(0.0, 0.60, 0.0), up=(0, 1, 0), fovy=45.0, side="wall"),
    "WA2": dict(pos=(0.0, 0.60, 1.30), target=(0.0, 0.60, 0.0), up=(0, 1, 0), fovy=FOVY_D435, side="wall"),
    "WB1": dict(pos=(0.0, 1.75, 0.75), target=(0.0, 0.55, 0.10), up=(0, 0, 1), fovy=50.0, side="wall"),
    "WC1": dict(pos=(0.0, 1.45, 1.10), target=WALL_C, up=(0, 0, 1), fovy=FOVY_D435, side="wall"),
    "WC2": dict(pos=(0.0, 1.20, 1.30), target=WALL_C, up=(0, 0, 1), fovy=FOVY_D435, side="wall"),
    "WD1": dict(pos=(1.35, 0.60, 0.95), target=WALL_C, up=(0, 0, 1), fovy=FOVY_D435, side="wall"),
    "WE1": dict(pos=(0.90, 1.40, 1.20), target=WALL_C, up=(0, 0, 1), fovy=FOVY_D435, side="wall"),
}
FAMILIES = {"SA": ("SA1", "SA2"), "SB": ("SB1", "SB2"), "WA": ("WA1", "WA2"), "WC": ("WC1", "WC2"), "WDE": ("WD1", "WE1")}

# G1 (외부 1대): 작은 격자에서 찾는다 (prl.geom_metrics). 보는 점 = 두 영역 중심의 가운데
G1_TARGET = tuple(float(v) for v in (np.array(SUPPLY_C) + np.array(WALL_C)) / 2)
G1_GRID = dict(x=(1.4, 1.8, 2.2), y=(-0.5, 0.0, 0.5), z=(1.2, 1.7, 2.2))

# 손목 카메라 후보. 집게 부착 좌표(z = 접근축 = 손끝 방향, y = 닫힘축, x = 든 벽돌의 길이 방향), 원점 = 플랜지 부착점.
# H0 = wall3의 손목 카메라 그대로(모델에 이미 있음, 이름 "wrist").
# H1: 집게 몸통 위쪽 뒤(플랜지 높이, 길이 방향으로 0.10 m)에서 손끝을 봄. H2: 집게 옆면(닫힘축 쪽 0.11 m, 길이 방향 0.06 m)에서
# 든 벽돌 옆 아래(손끝에서 접근축으로 0.12 m 더 간 자리, 닫힘축 쪽 0.03 m)를 비스듬히 봄. 정확한 값은 스스로 정한 것(보고서에 기록).
WRIST_CAMS = {
    "H0": dict(model_name="wrist", fovy=80.0),
    "H1": dict(pos=(0.100, 0.0, 0.000), target_tcp_offset=(0.0, 0.0, 0.0), fovy=FOVY_D435),
    "H2": dict(pos=(0.060, -0.110, 0.050), target_tcp_offset=(0.0, -0.030, 0.120), fovy=FOVY_D435),
}
CAM_BODY_R = 0.05                    # m, 카메라 몸체로 본 구의 반지름 (D435 90 × 25 × 25 mm, D405 42 × 42 × 23 mm 를 덮는 값)
CAM_CLEAR = 0.05                     # m, 팔이 지나는 부피와 카메라 몸체 사이에 둘 최소 여유

# ---- 깊이 잡음 (지시 문서 6.1) ---------------------------------------------------------------------------------------------
# σ_z = z² × 시차 잡음 ÷ (초점거리 × 기선). 초점거리는 원본 영상(1280 화소 폭)의 화소 단위.
# 값의 출처: Intel RealSense D400 계열 자료(시차 잡음 RMS 약 0.08 화소; D435 기선 50 mm, 범위 0.3 ~ 3 m;
# D405 기선 18 mm, 범위 7 ~ 50 cm). 인용 전에 원문 확인 필요(아이디어 md 7.4와 같은 조건).
DEPTH_NOISE = {
    "d435": dict(baseline_m=0.050, subpixel_px=0.08, range_m=(0.3, 3.0)),
    "d405": dict(baseline_m=0.018, subpixel_px=0.08, range_m=(0.07, 0.5)),
    # 시차 잡음을 화소마다 독립으로 두면 평균으로 거의 사라져 잡음 없는 깊이와 같아진다. 스테레오 정합 창 크기만큼
    # 이웃 화소끼리 상관되게 한다(스스로 정함): 흰 잡음을 corr_px 화소 상자 평균으로 고르고 표준편차를 다시 맞춤.
    "corr_px": 7,
}


def focal_px(fovy_deg, h=RAW_H):
    return float((h / 2) / np.tan(np.radians(fovy_deg) / 2))


def depth_sigma(z, fovy_deg, kind="d435"):
    p = DEPTH_NOISE[kind]
    return np.asarray(z, float) ** 2 * p["subpixel_px"] / (focal_px(fovy_deg) * p["baseline_m"])


# ---- 윗면 높이 보정값 (측정기 · 규칙 기반이 쓰는 환경 보정값) ---------------------------------------------------------------
# 도면 높이(단 × 57 mm, 공급대 0.35 + 0.057 m)와 실제 윗면 높이의 차. 시뮬레이터의 접촉이 조금 가라앉기 때문이다.
# 비스듬한 카메라는 윗면 높이가 0.5 mm 틀리면 수평 위치가 0.5 ~ 0.8 mm 틀린다(개발 장면에서 확인) → 카메라 보정값처럼 한 번 재서 쓴다.
# 잰 곳: 공급대 = 개발 장면 800200 ~ 800202(0.5 s 가라앉힌 뒤), 단 1 ~ 3 = 궤적 800000 ~ 800009에서 벽돌을 놓고 철수한 시점
# (평균 0.108 · 0.295 · 0.567 mm, 표준편차 0.000 · 0.032 · 0.057 mm). 선정 · 명목 배치의 참값은 쓰지 않았다.
TOP_SINK_M = {"supply": 0.000106, 1: 0.000108, 2: 0.000295, 3: 0.000567}
# 손에 든 벽돌: 집게 형상으로 계산한 높이(패드 중심에서 dz_pad 아래)보다 실제 벽돌 중심이 이만큼 높다
# (개발 장면 800200 ~ 800203의 64장: 평균 1.582 mm, 표준편차 0.083 mm). 집게 보정값으로 쓴다.
HELD_DZ_M = 0.00158

# ---- 자원 한도 (지시 문서 4.2). 0단계에서 잰 값으로 계산해 진행상황.md에 기록 ------------------------------------------------
@dataclass
class Limits:
    ram_total_gb: float = 60.4
    train_mem_max_gb: int = 36          # min(전체 × 0.6, 전체 − 12)
    train_swap_max_gb: int = 2
    eval_mem_max_gb: int = 30           # 전체 × 0.5
    workers: int = 4                    # 데이터 로딩 작업자 (최대 6)
    ckpt_every: int = 20000             # 스텝마다 저장하고 프로세스를 끝낸 뒤 이어 함
    vram_limit_gb: float = 26.0         # 넘으면 배치를 반으로
    vram_reserve_gb: float = 4.0
    disk_stop_gb: float = 50.0
    disk_use_frac: float = 0.5
    ram_reserve_gb: float = 12.0
    low_ram_gb: float = 6.0
    max_eval_procs: int = 8


def sha(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=float).encode()).hexdigest()


def env_dict(scene: SceneConfig | None = None):
    """Everything that defines the dry_v1 physics and task (cameras are separate: they do not change the physics)."""
    scene = scene or dry_scene()
    return {"env_version": ENV_VERSION, "scene": scene.to_dict(), "dry": DRY_RULES, "design": dry_design()}


def cams_dict():
    return {"raw": [RAW_W, RAW_H], "policy_img": POLICY_IMG, "fixed": FIXED_CAMS, "wrist": WRIST_CAMS,
            "g1_target": G1_TARGET, "g1_grid": G1_GRID, "depth_noise": DEPTH_NOISE}


# ---- 2단계에서 확정한 카메라와 세팅 (prl/settings_20261112.json, prl.select_settings가 만든 것) ---------------------------------
SETTINGS_JSON = "settings_20261112.json"


def load_settings():
    from pathlib import Path
    return json.loads((Path(__file__).resolve().parent / SETTINGS_JSON).read_text())


def final_cams(names=None):
    """Fixed cameras of the six settings with their final poses (WA2 moved, G1 from the grid): {name: spec} for DryEnv."""
    S = load_settings()
    use = [n for n in (names or S["cameras_used"]) if n not in WRIST_CAMS]
    return {n: S["camera_poses"][n] for n in use}


def setting_cams(name):
    return list(load_settings()["settings"][name]["cams"])
