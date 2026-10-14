# -*- coding: utf-8 -*-
"""UR10e 고정 베이스로 쌓을 수 있는 일자 벽 크기 추정 (실험설계_3층벽체.md 5.1절, 2026-10-14).

방법
1. UR10e 공식 DH로 순기구학을 만들고, 공구 축을 연직 아래로 둔 채 (r, z) 점에 집는 점을 놓을 수 있는지 수치 IK로 검사한다.
   손목 회전(q6)은 자유라 벽돌 방향(yaw)은 도달 여부에 영향이 없고, 베이스 회전 대칭이라 반경 r과 높이 z만 보면 된다.
2. 여유 조건: 팔꿈치가 거의 펴진 자세(|q3| < 15°)와 손목 특이점(|sin q5| < 0.15)은 제외, 모든 관절과 집는 점이 바닥 위.
3. 벽: 벽돌 190×90×57 mm, 줄눈 10 mm, 1단 아래 줄눈 없음. 각 단의 놓는 자세와 그 위 0.10 m 접근 자세가 모두 도달해야 한다.
   벽 중심선과 베이스 중심 거리 yc, 반경 여유 margin을 두고, 모든 단에서 가장 먼 벽돌 중심까지 닿는 최대 장수를 센다.

한계: 받침대·베이스·벽과의 충돌, 집게와 벽돌의 실제 형상, 동역학(가반 하중에 따른 속도 제한)은 보지 않는다.
최종 확정은 MuJoCo 전체 모델(집게·벽돌 충돌 포함)로 도달 지도를 다시 만든다.

사용: python ur10e_reach_estimate.py --base-heights 0 0.3 0.6 --yc 0.5 --margin 0.10
"""
import argparse
import numpy as np
from scipy.optimize import least_squares

D = [0.1807, 0, 0, 0.17415, 0.11985, 0.11655]          # UR10e DH (Universal Robots 공개값)
A = [0, -0.6127, -0.57155, 0, 0, 0]
AL = [np.pi / 2, 0, 0, np.pi / 2, -np.pi / 2, 0]
BRICK_L, JOINT, COURSE = 0.19, 0.010, 0.067


def fk(q, tool):
    T = np.eye(4); pts = [T[:3, 3].copy()]
    for i in range(6):
        ct, st = np.cos(q[i]), np.sin(q[i]); ca, sa = np.cos(AL[i]), np.sin(AL[i])
        T = T @ np.array([[ct, -st * ca, st * sa, A[i] * ct], [st, ct * ca, -ct * sa, A[i] * st], [0, sa, ca, D[i]], [0, 0, 0, 1]])
        pts.append(T[:3, 3].copy())
    return T[:3, 3] + tool * T[:3, 2], T[:3, 2], np.array(pts)


def reachable(r, z, floor, tool, rng, tries=10):
    tgt = np.array([r, 0.0, z]); down = np.array([0, 0, -1.0])
    for _ in range(tries):
        q0 = rng.uniform(-np.pi, np.pi, 6); q0[2] = rng.choice([-1, 1]) * rng.uniform(0.3, 2.8)
        s = least_squares(lambda q: np.r_[fk(q, tool)[0] - tgt, 0.3 * (fk(q, tool)[1] - down)], q0, xtol=1e-10, ftol=1e-10, max_nfev=400)
        tcp, zt, pts = fk(s.x, tool)
        if np.linalg.norm(tcp - tgt) > 1e-4 or np.linalg.norm(zt - down) > 1e-3:
            continue
        q3 = (s.x[2] + np.pi) % (2 * np.pi) - np.pi
        if abs(q3) < np.radians(15) or abs(np.sin(s.x[4])) < 0.15:
            continue
        if np.any(pts[2:, 2] < floor + 0.02) or tcp[2] < floor:
            continue
        return True
    return False


def rmax_table(hb, tool, rng, rs=np.round(np.arange(0.20, 1.42, 0.02), 3), dz=0.05, ztop=1.0):
    zs = np.round(np.arange(-hb, ztop + 1e-9, dz), 3); out = []
    for z in zs:
        rm = 0.0
        for r in rs[::-1]:
            if reachable(r, z, -hb, tool, rng):
                rm = r; break
        out.append(rm)
    return zs, np.array(out)


def wall_capacity(zs, rm, hb, yc, margin, kmax=30):
    def r_at(z):
        if z < zs[0] or z > zs[-1]:
            return 0.0
        i = np.searchsorted(zs, z); j = max(i - 1, 0)
        return min(rm[j], rm[min(i, len(zs) - 1)])            # 두 격자 높이 중 나쁜 쪽
    rows = []
    for K in range(1, kmax + 1):
        need = [0.0285 + COURSE * k - hb for k in range(K)]
        R = min(r_at(z) for z in need + [z + 0.10 for z in need]) - margin
        if R <= yc:
            break
        n = int(np.floor((2 * (np.sqrt(R ** 2 - yc ** 2) + BRICK_L / 2) + JOINT) / (BRICK_L + JOINT)))
        if n < 2:
            break
        rows.append((K, n, K * n, R))
    return rows


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-heights", type=float, nargs="+", default=[0.0, 0.3, 0.6])
    ap.add_argument("--tool", type=float, default=0.20, help="플랜지에서 집는 점까지 (m)")
    ap.add_argument("--yc", type=float, default=0.5, help="벽 중심선과 베이스 중심 거리 (m)")
    ap.add_argument("--margin", type=float, default=0.10, help="반경 여유 (m)")
    a = ap.parse_args()
    rng = np.random.default_rng(0)
    for hb in a.base_heights:
        zs, rm = rmax_table(hb, a.tool, rng)
        rows = wall_capacity(zs, rm, hb, a.yc, a.margin)
        best = max(rows, key=lambda t: (t[2], -t[0]))
        print(f"베이스 높이 {hb:.2f} m: " + " · ".join(f"{k}단x{n}장" for k, n, _, _ in rows if k in (3, 5, 8, 10, 12, 15)))
        print(f"  최대 {best[2]}장(온장 환산) = {best[0]}단 x {best[1]}장, 벽 {best[1] * 0.19 + (best[1] - 1) * 0.01:.2f} m x {best[0] * 0.057 + (best[0] - 1) * 0.01:.2f} m")
