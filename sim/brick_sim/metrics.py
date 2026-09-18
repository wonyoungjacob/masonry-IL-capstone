"""Masonry inspection metrics computed from exact brick poses (the "검측 성적표", 2.6절 of the blueprint).

All 8 metric families are always computed and reported together:
 1 per-brick placement error & success   (Transporter / FurnitureBench style thresholds, scaled)
 2 course level (bed-joint level)        (TMS 602 3.3F, LABC)
 3 plumb / lean                          (EN 1996-2 Table 3.1, TMS 602)
 4 straightness / bow (string line)      (EN 1996-2, "10 mm in 2 m")
 5 joint consistency (head & bed)        (TMS 602 bed +-3.2 mm, EN 1996-1-1 8.1.5)
 6 bond / stagger (overlap, 통줄눈)        (EN 1996-1-1 8.1.4, KCS 41 34 02)
 7 stability (settle test, fallen bricks)
 8 shape fidelity (voxel IoU vs design envelope)
Tolerances are expressed relative to brick size so they scale with the 1/4-scale bricks.
Design entries are (x, y, z, yaw, length); half-brick closers have length L/2.
"""
from __future__ import annotations

import numpy as np


def quat_to_yaw_tilt(q):
    w, x, y, z = q
    R = np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
    ])
    yaw = np.arctan2(R[1, 0], R[0, 0])
    tilt = np.degrees(np.arccos(np.clip(R[2, 2], -1, 1)))
    return yaw, tilt, R


def compute_metrics(poses, design, brick, wall, tol_frac=0.05, tol_yaw_deg=5.0, poses_before_settle=None):
    """poses: (N,7) [x,y,z,qw,qx,qy,qz]; design: list of (x,y,z,yaw,len); brick: BrickSpec; wall: WallSpec."""
    N = len(design)
    L, W, H = brick.L, brick.W, brick.H
    P = np.asarray(poses)[:N]
    Dfull = np.asarray(design)[:N]
    D = Dfull[:, :4]
    Li = Dfull[:, 4] if Dfull.shape[1] > 4 else np.full(N, L)
    # bricks are identical: pair real bricks and design slots by the minimum-distance assignment (blueprint 4.9.1),
    # never by brick id (the laying order is a function of the scene, see ScriptedExpert.order)
    perm = _assign(P, D)
    P = P[perm]
    if poses_before_settle is not None:
        poses_before_settle = np.asarray(poses_before_settle)[:N][perm]
    out = {}

    # ---------- 1. per-brick placement error
    exy = np.hypot(P[:, 0] - D[:, 0], P[:, 1] - D[:, 1])
    ez = P[:, 2] - D[:, 2]
    yt = [quat_to_yaw_tilt(q)[:2] for q in P[:, 3:7]]
    yaws = np.array([a for a, _ in yt]); tilts = np.array([b for _, b in yt])
    eyaw = np.degrees((yaws - D[:, 3] + np.pi) % (2 * np.pi) - np.pi)
    tol_pos = tol_frac * L
    ok = (exy < tol_pos) & (np.abs(ez) < tol_pos) & (np.abs(eyaw) < tol_yaw_deg) & (tilts < 10)
    out["m1_success_rate"] = float(ok.mean())
    out["m1_all_success"] = bool(ok.all())
    out["m1_exy_mean_mm"] = float(exy.mean() * 1000)
    out["m1_exy_max_mm"] = float(exy.max() * 1000)
    out["m1_ez_mean_mm"] = float(np.abs(ez).mean() * 1000)
    out["m1_eyaw_mean_deg"] = float(np.abs(eyaw).mean())
    out["m1_exy_norm_mean"] = float((exy / L).mean())
    courses = np.round((D[:, 2] - H / 2) / (H + wall.bed_joint)).astype(int)
    nc = int(courses.max()) + 1
    out["m1_exy_by_course_mm"] = [float(exy[courses == k].mean() * 1000) for k in range(nc)]

    # ---------- 2. course level
    top_z = P[:, 2] + H / 2
    lvl = []
    for k in range(nc):
        idx = courses == k
        zs = top_z[idx]; xs = P[idx, 0]
        rng = float((zs.max() - zs.min()) * 1000) if idx.sum() > 1 else 0.0
        slope = float(np.polyfit(xs, zs, 1)[0] * 1000) if idx.sum() > 1 else 0.0
        lvl.append({"course": k, "range_mm": rng, "slope_mm_per_m": slope})
    out["m2_course_level"] = lvl
    out["m2_level_range_max_mm"] = float(max(c["range_mm"] for c in lvl))

    # ---------- 3. plumb
    front_y = P[:, 1] - W / 2
    y0 = front_y[courses == 0].mean()
    ytop = front_y[courses == nc - 1].mean()
    height = nc * (H + wall.bed_joint)
    plumb_mm = float(abs(ytop - y0) * 1000)
    out["m3_plumb_mm"] = plumb_mm
    out["m3_plumb_mm_per_m"] = float(plumb_mm / height) if height > 0 else 0.0
    out["m3_max_tilt_deg"] = float(tilts.max())

    # ---------- 4. straightness (string line per course) and bow
    straight = []
    for k in range(nc):
        idx = np.where(courses == k)[0]
        if len(idx) < 3:
            straight.append(0.0); continue
        xs, ys = P[idx, 0], front_y[idx]
        o = np.argsort(xs); xs, ys = xs[o], ys[o]
        line = ys[0] + (ys[-1] - ys[0]) * (xs - xs[0]) / max(xs[-1] - xs[0], 1e-9)
        straight.append(float(np.abs(ys - line).max() * 1000))
    out["m4_straightness_max_mm"] = float(max(straight))
    cy = np.array([front_y[courses == k].mean() for k in range(nc)])
    if nc >= 3:
        line = cy[0] + (cy[-1] - cy[0]) * np.arange(nc) / (nc - 1)
        out["m4_bow_mm"] = float(np.abs(cy - line).max() * 1000)
    else:
        out["m4_bow_mm"] = 0.0

    # ---------- 5. joint consistency (edges from per-brick lengths)
    def edges(k):
        idx = np.where(courses == k)[0]
        o = idx[np.argsort(P[idx, 0])]
        return P[o, 0] - Li[o] / 2, P[o, 0] + Li[o] / 2
    head = []
    for k in range(nc):
        left, right = edges(k)
        head += list(left[1:] - right[:-1])
    bed = []
    for k in range(1, nc):
        bed.append(P[courses == k, 2].mean() - P[courses == k - 1, 2].mean() - H)
    head = np.array(head) if head else np.zeros(1)
    bed = np.array(bed) if bed else np.zeros(1)
    out["m5_head_gap_mean_mm"] = float(head.mean() * 1000)
    out["m5_head_gap_std_mm"] = float(head.std() * 1000)
    out["m5_head_gap_dev_from_nominal_mm"] = float(np.abs(head - wall.head_gap).max() * 1000)
    out["m5_bed_gap_mean_mm"] = float(bed.mean() * 1000)
    out["m5_bed_gap_dev_from_nominal_mm"] = float(np.abs(bed - wall.bed_joint).max() * 1000)

    # ---------- 6. bond
    def head_joint_x(k):
        left, right = edges(k)
        return (right[:-1] + left[1:]) / 2 if len(left) > 1 else np.array([])
    overlaps, through = [], 0
    for k in range(1, nc):
        jk, jb = head_joint_x(k), head_joint_x(k - 1)
        for j in jk:
            if len(jb):
                dmin = np.abs(jb - j).min()
                overlaps.append(dmin)
                if dmin < 0.1 * L:
                    through += 1
    req = max(0.4 * H, 0.25 * L)
    overlaps = np.array(overlaps) if overlaps else np.array([np.nan])
    out["m6_min_overlap_mm"] = float(np.nanmin(overlaps) * 1000)
    out["m6_overlap_ok_frac"] = float(np.nanmean(overlaps >= req)) if not np.all(np.isnan(overlaps)) else 1.0
    out["m6_through_joints"] = int(through)

    # ---------- 7. stability
    fallen = (tilts > 15) | (P[:, 2] < D[:, 2] - 0.5 * H)
    out["m7_fallen_count"] = int(fallen.sum())
    if poses_before_settle is not None:
        B = np.asarray(poses_before_settle)[:N]
        drift = np.linalg.norm(P[:, :3] - B[:, :3], axis=1)
        out["m7_settle_drift_mean_mm"] = float(drift.mean() * 1000)
        out["m7_settle_drift_max_mm"] = float(drift.max() * 1000)
    out["m7_stable"] = bool(fallen.sum() == 0)

    # ---------- 8. shape fidelity
    out["m8_voxel_iou"] = float(_voxel_iou(P, D, Li, W, H))

    out["m_pass"] = {
        "placement": out["m1_all_success"],
        "level": out["m2_level_range_max_mm"] <= 0.03 * L * 1000,
        "plumb": out["m3_plumb_mm"] <= 0.05 * L * 1000,
        "straight": out["m4_straightness_max_mm"] <= 0.05 * L * 1000,
        "joints": out["m5_head_gap_dev_from_nominal_mm"] <= 0.05 * L * 1000,
        "bond": out["m6_through_joints"] == 0 and out["m6_overlap_ok_frac"] == 1.0,
        "stable": out["m7_stable"],
    }
    return out


def _voxel_iou(P, D, Lvec, W, H, res=0.002):
    """IoU between the union of the real boxes P and the union of the target boxes D on a voxel grid.

    Real bricks far from the design region (e.g. still parked in the feeder row ~0.5 m away when the policy
    did not finish) cannot intersect the targets, so they are not rasterised: their volume is added to the
    union analytically.  Otherwise the grid would span the whole table (hundreds of millions of cells at
    0.5 mm) and one evaluation episode takes minutes.
    """
    Lvec = np.asarray(Lvec, float)
    L = float(np.max(Lvec))
    dmin, dmax = D[:, :3].min(axis=0), D[:, :3].max(axis=0)
    far = np.array([bool(np.any(c < dmin - 2 * L) or np.any(c > dmax + 2 * L)) for c in P[:, :3]])
    far_vol = float(sum(li * W * H for li, f in zip(Lvec, far) if f))
    Pn, Ln = P[~far], Lvec[~far]
    allc = np.vstack([Pn[:, :3], D[:, :3]])
    xmin, xmax = allc[:, 0].min() - L, allc[:, 0].max() + L
    ymin, ymax = allc[:, 1].min() - W * 2, allc[:, 1].max() + W * 2
    zmin, zmax = 0.0, allc[:, 2].max() + H
    gx = np.arange(xmin, xmax, res); gy = np.arange(ymin, ymax, res); gz = np.arange(zmin, zmax, res)
    X, Y, Z = np.meshgrid(gx, gy, gz, indexing="ij")

    def occ(centers, yaws, lengths):
        grid = np.zeros(X.shape, bool)
        for c, yw, li in zip(centers, yaws, lengths):
            dx, dy, dz = X - c[0], Y - c[1], Z - c[2]
            u = np.cos(yw) * dx + np.sin(yw) * dy
            v = -np.sin(yw) * dx + np.cos(yw) * dy
            grid |= (np.abs(u) <= li / 2) & (np.abs(v) <= W / 2) & (np.abs(dz) <= H / 2)
        return grid
    yaws_a = np.array([quat_to_yaw_tilt(q)[0] for q in Pn[:, 3:7]]) if len(Pn) else np.zeros(0)
    A = occ(Pn[:, :3], yaws_a, Ln)
    B = occ(D[:, :3], D[:, 3], Lvec)
    cell = res ** 3
    inter = np.logical_and(A, B).sum() * cell
    union = np.logical_or(A, B).sum() * cell + far_vol
    return inter / union if union else 0.0


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
