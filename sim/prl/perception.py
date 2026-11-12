"""벽돌 자세 측정기 (3단계 · 규칙 기반 기준선용): 카메라 한 대의 원본 색 + 잡음 넣은 깊이 + 보정값 + 도면으로 벽돌 한 장의 자세를 잰다.

wall3/perception.py(수직 top 카메라, 잡음 없는 깊이)의 방식을 임의의 카메라와 잡음 있는 깊이로 옮긴 것. 같은 원리를 쓴다:
벽돌 색 화소 중 윗면 높이에 있는 것을 고르고, 도면의 벽돌 크기(L × W)로 자세를 맞춘다. 달라진 점:
- 비스듬한 카메라는 윗면과 함께 옆면도 본다. 그래서 '윗면에서 아래로 band 만큼의 판'(벽돌의 윗부분)을 모형으로 삼아, 그 판을
  영상에 투영한 볼록 다각형이 [벽돌 색 · 높이가 그 판 범위] 화소와 가장 잘 겹치는 (x, y, yaw)를 찾는다.
- 깊이는 화소를 고르는 데(높이 범위, 가리는 물체)만 쓰고, 위치는 색 영상의 윤곽으로 정한다. 깊이 잡음이 수평 위치에 바로
  들어가지 않게 하기 위함이다. 높이는 윗면 화소 높이의 중앙값으로 잰다.
- 가리는 것(벽돌 윗부분 높이 이상에 있는 벽돌 아닌 것: 팔 · 집게)과 이웃 벽돌 자리는 비교에서 뺀다.
시뮬레이터 참값은 쓰지 않는다. 쓰는 가정: 카메라 보정값, 벽돌 치수, 대상의 대략 위치(공급 칸 · 설계 자리 · 집게 아래)와 윗면 높이.
"""
from __future__ import annotations

import cv2
import numpy as np
from scipy.optimize import minimize

from wall3.config import W, H

RATIO_MIN = 1.25         # R / G: 적벽돌 약 2.2, 공급대(갈색) 약 1.3, 바닥 · 로봇(회색 · 검정) 약 1.0.
                         # 낮게 잡는다: 화소가 벽돌인지는 깊이(화소 중심의 높이)가 정하고, 색은 그 높이에 있는 벽돌 아닌 것(집게 · 팔)만
                         # 걸러 낸다. 1.7로 색이 경계를 정하게 했을 때는 윤곽의 반쯤 덮인 화소(벽돌 + 바닥 섞인 색)가 빠져
                         # 밝은 배경 쪽 모서리가 0.4화소 짧게 잡혔다(비스듬한 카메라 쪽으로 0.7 mm 치우침, 2026-11-12 개발 장면)
R_MIN = 18               # 너무 어두운 화소는 색을 믿지 않는다
BAND_MIN, BAND_MAX = 0.012, 0.025
SS = 4                   # 다각형을 그릴 때의 초표본 배수
MIN_FRAC = 0.30          # 기대 넓이의 이 비율보다 적게 보이면 못 잰 것으로 한다


class Camera:
    """Pinhole from MuJoCo camera data: f in raw pixels, R (columns: x right, y up, z backward), t."""

    def __init__(self, fovy_deg, R, t, w, h, sigma_fn=None):
        self.w, self.h = int(w), int(h)
        self.f = (self.h / 2) / np.tan(np.radians(fovy_deg) / 2)
        self.R, self.t = np.asarray(R, float), np.asarray(t, float)
        self.sigma_fn = sigma_fn

    def project(self, P):
        pc = (np.atleast_2d(P) - self.t) @ self.R
        z = -pc[:, 2]
        return self.f * pc[:, 0] / z + self.w / 2, -self.f * pc[:, 1] / z + self.h / 2, z

    def points(self, depth, x0, y0, x1, y1):
        """World points of the pixel block [y0:y1, x0:x1] from the depth image (nan where invalid)."""
        xs, ys = np.meshgrid(np.arange(x0, x1), np.arange(y0, y1))
        d = depth[y0:y1, x0:x1].astype(np.float64)
        pc = np.stack([(xs + 0.5 - self.w / 2) / self.f * d, -(ys + 0.5 - self.h / 2) / self.f * d, -d], -1)
        return pc @ self.R.T + self.t


def slab_corners(x, y, yaw, L, z_top, band):
    c, s = np.cos(yaw), np.sin(yaw)
    out = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            px = x + c * sx * L / 2 - s * sy * W / 2
            py = y + s * sx * L / 2 + c * sy * W / 2
            out += [[px, py, z_top], [px, py, z_top - band]]
    return np.array(out)


def _hull_px(cam, corners, x0, y0, scale=1):
    u, v, z = cam.project(corners)
    if (z <= 0.02).any():
        return None
    pts = np.stack([(u - x0) * scale - 0.5, (v - y0) * scale - 0.5], 1).astype(np.float32)   # OpenCV: integer = pixel centre
    return cv2.convexHull(pts)


def _coverage(cam, corners, x0, y0, shape, ss=SS):
    """Fractional coverage of the projected slab on the pixel block (supersampled ss times; ss = 1: binary)."""
    hl = _hull_px(cam, corners, x0, y0, ss)
    if hl is None:
        return None
    big = np.zeros((shape[0] * ss, shape[1] * ss), np.uint8)
    cv2.fillConvexPoly(big, np.round(hl * 16).astype(np.int32), 255, lineType=cv2.LINE_8, shift=4)
    if ss == 1:
        return big.astype(np.float32) / 255.0
    return cv2.resize(big, (shape[1], shape[0]), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0


def _coverage_exact(cam, corners, x0, y0, shape, ss=SS):
    """Fractional coverage of the projected slab on the pixel block: ss × ss sample points per pixel tested against the
    polygon's edges. cv2.fillConvexPoly (used for the coarse search only) also fills the border pixels and its filled area
    sits up to half a pixel off (measured on rectangles: +0.5 px at ss = 1, +0.13 px at ss = 4): too much for a 2 mm test."""
    u, v, z = cam.project(corners)
    if (z <= 0.02).any():
        return None
    hl = cv2.convexHull(np.stack([u - x0, v - y0], 1).astype(np.float32)).reshape(-1, 2).astype(np.float64)
    out = np.zeros(shape, np.float32)
    cx0, cx1 = max(int(np.floor(hl[:, 0].min())), 0), min(int(np.ceil(hl[:, 0].max())), shape[1])
    cy0, cy1 = max(int(np.floor(hl[:, 1].min())), 0), min(int(np.ceil(hl[:, 1].max())), shape[0])
    if cx1 <= cx0 or cy1 <= cy0:
        return out
    xs = cx0 + (np.arange((cx1 - cx0) * ss) + 0.5) / ss
    ys = cy0 + (np.arange((cy1 - cy0) * ss) + 0.5) / ss
    X, Y = np.meshgrid(xs, ys)
    area2 = float(np.sum(hl[:, 0] * np.roll(hl[:, 1], -1) - np.roll(hl[:, 0], -1) * hl[:, 1]))
    sgn = 1.0 if area2 >= 0 else -1.0
    inside = np.ones(X.shape, bool)
    for a, b in zip(hl, np.roll(hl, -1, axis=0)):
        inside &= sgn * ((b[0] - a[0]) * (Y - a[1]) - (b[1] - a[1]) * (X - a[0])) >= 0
    out[cy0:cy1, cx0:cx1] = inside.reshape(cy1 - cy0, ss, cx1 - cx0, ss).mean((1, 3))
    return out


class PolyIntegrator:
    """Sum of an image g over a convex polygon, with ss × ss sample points per pixel (the same sampling as _coverage_exact),
    in O(rows): per sample row the polygon is an interval [x_left, x_right) and the row sums come from prefix sums.
    The fit cost Σ w·|M − c(θ)| for a binary mask M is const + Σ c(θ)·g with g = w·(1 − 2M), so one evaluation is one such sum."""

    def __init__(self, g, ss=SS):
        self.ss = ss
        gs = np.repeat(np.repeat(np.asarray(g, np.float64), ss, 0), ss, 1) / (ss * ss)
        self.C = np.concatenate([np.zeros((gs.shape[0], 1)), np.cumsum(gs, 1)], 1)
        self.ys = (np.arange(gs.shape[0]) + 0.5) / ss
        self.nx = gs.shape[1]

    def integral(self, hull):
        hl = np.asarray(hull, np.float64).reshape(-1, 2)
        a, b = hl, np.roll(hl, -1, axis=0)
        r0 = max(int(np.ceil(hl[:, 1].min() * self.ss - 0.5)), 0)
        r1 = min(int(np.ceil(hl[:, 1].max() * self.ss - 0.5)), len(self.ys))
        if r1 <= r0:
            return 0.0
        ys = self.ys[r0:r1]
        dy = b[:, 1] - a[:, 1]
        ok = np.abs(dy) > 1e-12
        a, b, dy = a[ok], b[ok], dy[ok]
        lo, hi = np.minimum(a[:, 1], b[:, 1])[:, None], np.maximum(a[:, 1], b[:, 1])[:, None]
        X = a[:, 0:1] + (ys[None] - a[:, 1:2]) * ((b[:, 0] - a[:, 0]) / dy)[:, None]
        hit = (ys[None] >= lo) & (ys[None] < hi)
        xl = np.where(hit, X, np.inf).min(0)
        xr = np.where(hit, X, -np.inf).max(0)
        good = np.isfinite(xl) & np.isfinite(xr)
        j0 = np.clip(np.ceil(xl[good] * self.ss - 0.5), 0, self.nx).astype(int)
        j1 = np.clip(np.ceil(xr[good] * self.ss - 0.5), 0, self.nx).astype(int)
        rows = np.arange(r0, r1)[good]
        return float((self.C[rows, np.maximum(j1, j0)] - self.C[rows, j0]).sum())


def brick_colour(rgb):
    r, g = rgb[..., 0].astype(np.float32), rgb[..., 1].astype(np.float32)
    return (r >= R_MIN) & (r >= RATIO_MIN * np.maximum(g, 1.0))


def measure(rgb, depth, cam: Camera, prior_xy, prior_yaw, L, z_top, radius=0.03, yaw_range_deg=14.0, others=(), refine_z=True):
    """Pose of one brick. prior_xy / prior_yaw: where the drawing (or the gripper) says it is; z_top: its top height;
    radius: how far the centre may be from the prior; others: [(x, y, yaw, L, z_top)] of neighbouring bricks to leave out.
    Returns dict(pos, yaw, z_top, score, n_px, visible_frac) or None when it cannot be measured."""
    px, py = float(prior_xy[0]), float(prior_xy[1])
    _, _, zc = cam.project(np.array([[px, py, z_top]]))
    if zc[0] <= 0.02:
        return None
    sig = float(cam.sigma_fn(zc[0])) if cam.sigma_fn is not None else 0.0
    band = float(np.clip(3.0 * sig, BAND_MIN, BAND_MAX))
    # pixel block: the prior slab moved by the search radius
    half = float(np.hypot(L / 2, W / 2)) + radius + 0.01
    ext = np.array([[px + sx * half, py + sy * half, zz] for sx in (-1, 1) for sy in (-1, 1) for zz in (z_top, z_top - band)])
    u, v, z = cam.project(ext)
    if (z <= 0.02).any():
        return None
    pad = 6
    x0, x1 = int(np.floor(u.min())) - pad, int(np.ceil(u.max())) + pad
    y0, y1 = int(np.floor(v.min())) - pad, int(np.ceil(v.max())) + pad
    x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, cam.w), min(y1, cam.h)
    if x1 - x0 < 8 or y1 - y0 < 8:
        return None
    shape = (y1 - y0, x1 - x0)
    P = cam.points(depth, x0, y0, x1, y1)
    hgt = P[..., 2]
    valid = np.isfinite(hgt)
    col = brick_colour(rgb[y0:y1, x0:x1])
    in_band = valid & (hgt >= z_top - band) & (hgt <= z_top + band)
    M = (col & in_band).astype(np.float32)
    occl = valid & ~col & (hgt > z_top - band)             # something that is not brick at / above the slab: arm, gripper
    high = valid & (hgt > z_top + band)                     # anything above the slab (a brick of an upper course, the hand)
    use = valid & ~occl & ~high
    known = np.zeros(shape, np.float32)                     # neighbours at the same height: their slabs are part of the model
    for (ox, oy, oyaw, oL, oz) in others:                   # (drawn where the drawing says they are), not left out: a brick in
        if abs(oz - z_top) > band:                          # front of its neighbour covers part of the neighbour's outline
            continue
        c = _coverage_exact(cam, slab_corners(ox, oy, oyaw, oL, oz, band), x0, y0, shape)
        if c is not None:
            known = np.maximum(known, c)
    wgt = use.astype(np.float32)
    n_use = float(wgt.sum())
    if n_use < 50 or float((M * wgt).sum()) < 30:
        return None

    kb = known >= 0.5
    integ = PolyIntegrator(np.where(kb, 0.0, wgt * (1.0 - 2.0 * M)))
    const = float((wgt * M)[~kb].sum() + (wgt * (1.0 - M))[kb].sum())

    lim_xy, lim_yaw = radius + 0.006, np.radians(yaw_range_deg + 3.0)

    def cost(p):
        if np.hypot(p[0] - px, p[1] - py) > lim_xy or abs(p[2] - prior_yaw) > lim_yaw:
            return 1e9                                      # the refinement stays inside the search region
        u, v, z = cam.project(slab_corners(p[0], p[1], p[2], L, z_top, band))
        if (z <= 0.02).any():
            return 1e9
        hl = cv2.convexHull(np.stack([u - x0, v - y0], 1).astype(np.float32))
        return const + integ.integral(hl)

    # coarse search on a grid, then a simplex refinement
    best, bc = None, np.inf
    step = max(0.004, radius / 6)
    offs = np.arange(-radius, radius + 1e-9, step)
    yaws = np.radians(np.arange(-yaw_range_deg, yaw_range_deg + 1e-9, 3.5))
    for dyaw in yaws:
        for dx in offs:
            for dy in offs:
                if dx * dx + dy * dy > (radius + step) ** 2:
                    continue
                p = (px + dx, py + dy, prior_yaw + dyaw)
                c = cost(p)
                if c < bc:
                    best, bc = p, c
    res = minimize(cost, np.array(best), method="Nelder-Mead",
                   options={"initial_simplex": np.array(best) + np.array([[0, 0, 0], [0.002, 0, 0], [0, 0.002, 0], [0, 0, 0.02]]),
                            "xatol": 5e-5, "fatol": 0.05, "maxiter": 200})
    p = res.x
    cov = _coverage_exact(cam, slab_corners(p[0], p[1], p[2], L, z_top, band), x0, y0, shape)
    exp_px = float((cov * wgt).sum())
    seen = float((np.minimum(M, cov) * wgt * (known < 0.5)).sum())
    full_px = float((cov * (known < 0.5)).sum())
    if exp_px < 20 or seen < MIN_FRAC * max(full_px, 1.0):
        return None
    # height: median height of the brick pixels well inside the fitted top face
    top = _coverage_exact(cam, slab_corners(p[0], p[1], p[2], L - 0.02, z_top, 0.0005), x0, y0, shape)
    sel = (top > 0.99) & (M > 0) & use if top is not None else np.zeros(shape, bool)
    z_meas = float(np.median(hgt[sel])) if sel.sum() >= 20 else None
    # the top height from the drawing is replaced only when the measured one differs by more than its own uncertainty
    # (noise is correlated over about corr × corr pixels) and by more than 4 mm
    z_tol = max(0.004, 3.0 * sig / np.sqrt(max(sel.sum() / 49.0, 1.0)))
    if z_meas is not None and abs(z_meas - z_top) <= z_tol:
        z_meas_used = z_top if sig > 0.006 else z_meas          # a noisy sensor adds nothing to a height known from the drawing
    else:
        z_meas_used = z_meas
    if refine_z and z_meas is not None and abs(z_meas - z_top) > z_tol:
        r2 = measure(rgb, depth, cam, (p[0], p[1]), p[2], L, z_meas, radius=0.012, yaw_range_deg=4.0, others=others, refine_z=False)
        if r2 is not None:
            return r2
    zt = z_meas_used if z_meas_used is not None else z_top
    return {"pos": np.array([p[0], p[1], zt - H / 2]), "yaw": float(p[2]), "z_top": zt, "score": float(res.fun) / max(exp_px, 1.0),
            "n_px": int(seen), "visible_frac": seen / max(full_px, 1.0), "band_m": band, "height_measured": z_meas is not None}
