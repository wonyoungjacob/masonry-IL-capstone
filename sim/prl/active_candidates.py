"""능동 카메라 받침 후보 (기준_해석_능동카메라_20261113.md 5절): 격자 196곳 + 1차 후보 위치 9곳, 모두 '선행' 역할로 계산한다.

실행: cd sim && PYTHONPATH=. venv/bin/python -m prl.active_candidates --out prl/active_mounts_20261113.json
"""
import argparse, json
from pathlib import Path

import numpy as np

from prl import config as C
from prl.active_cam import PanTiltSpec

GRID = dict(x=(-1.6, -1.2, -0.8, 0.0, 0.8, 1.2, 1.6), y=(-1.4, -0.9, -0.4, 0.1, 0.6, 1.1, 1.6), z=(0.6, 1.0, 1.4, 1.8))
NAMED = {"SA1": (0.0, -0.52, 1.45), "SB1": (0.0, -1.25, 1.50), "SC1": (1.50, -0.52, 1.50), "WA2": (0.0, 0.65, 1.30),
         "WB1": (0.0, 1.75, 0.75), "WC1": (0.0, 1.45, 1.10), "WD1": (1.35, 0.60, 0.95), "WE1": (0.90, 1.40, 1.20),
         "G1": (2.20, -0.50, 1.20)}                      # 1차 후보의 위치(받침점으로 씀)
CELL_C = C.G1_TARGET[:2]                               # 두 영역 중심의 가운데 (0, 0.04): 팬 범위의 가운데가 이쪽을 본다


def pan0_of(base):
    d = np.array(CELL_C) - np.array(base[:2])
    return float(np.degrees(np.arctan2(d[1], d[0]))) if np.hypot(*d) > 1e-6 else 90.0


def mounts():
    out = {}
    i = 0
    for x in GRID["x"]:
        for y in GRID["y"]:
            for z in GRID["z"]:
                out[f"M{i:03d}"] = (x, y, z)
                i += 1
    for n, p in NAMED.items():
        out[f"N{n}"] = p
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--role", default="lead")
    a = ap.parse_args()
    out = Path(a.out)
    if out.exists():
        raise SystemExit(f"{out} 이미 있음: 덮어쓰지 않음")
    cams = {n: {"base": [float(v) for v in p], "pan0": pan0_of(p), "role": a.role, "leave": "release"} for n, p in mounts().items()}
    out.write_text(json.dumps({"spec": PanTiltSpec().to_dict(), "grid": GRID, "named": NAMED, "cams": cams}, indent=1, ensure_ascii=False))
    print(len(cams), "mounts ->", out)


if __name__ == "__main__":
    main()
