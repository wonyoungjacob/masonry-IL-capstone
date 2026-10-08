"""On-board brick pose estimation from the fixed top RGB-D camera (2026-10-08, RQ4).

Until now the inspection gate (brick_sim.grasp_gate) read every brick pose it corrected with straight from the
simulator (the 'oracle' condition).  This module replaces that with what a real robot could have: the scene's own
top camera rendered at full resolution as RGB + depth, the camera intrinsics (fovy) and extrinsics (mount pose)
from calibration, and the nominal brick size from the drawing.  The simulator's true poses are used for
nothing but (a) deciding which detection is which brick (an identity label, as a tracker would keep) and
(b) the audit error logged next to every measurement.

Pipeline (BrickPoseEstimator.detect):
  1. render RGB + depth, back-project every pixel to a world point;
  2. brick pixels by colour (the fired-clay orange of the brick geoms); 'occluder' pixels = anything that stands
     higher than a brick top (the arm / gripper) -> used to tell a real brick edge from an occluded one;
  3. connected components; pieces of one brick cut in two by the gripper fingers are merged when they are
     collinear and together no longer than one brick; a blob as long as several butted bricks (the wall course,
     1 mm head joint) is split into that many bricks along its long axis;
  4. each blob: plane fit (tilt), min-area rectangle in the plane (yaw), centre from the edges that are not
     occluded plus the known L x W (an occluded end is reconstructed from the free end), centre height from
     the top face minus H/2; a blob with the proportions of a brick on its side is reported as toppled (90 deg).

Accuracy is measured in tools/perception_accuracy.py and tests/test_perception.py.  Nothing here changes the physics
or the 128 x 128 policy observations (the offscreen buffer was enlarged in scene.build_xml; the 128 px render is
pixel-identical, see the test).
"""
from __future__ import annotations

import numpy as np
import mujoco

try:
    import cv2
except ImportError as e:  # pragma: no cover - opencv-python is in setup_ubuntu.sh
    raise ImportError("brick_sim.perception needs opencv-python (cv2)") from e

# colour segmentation on RGB chroma.  Brick geoms are rgba (0.72,0.33,0.22) / (0.78,0.40,0.28); under the scene lights the
# top face is overexposed to about (255,226,160) and the shaded sides go down to (64,29,20), but R-B stays >= 40 for all
# of them, while the floor checker, the arm (white/black) and the mortar bed (0.55,0.53,0.49 -> R-B = 15) are grey.
CHROMA_MIN = 40         # R - B
MIN_PX = 40
OCCLUDER_DZ = 0.003     # m above the blob's top face: a non-brick pixel this much higher next to the blob is the arm (the jaw
                        # pads stand only a few mm above the top face of the brick they hold)
FLAT_MAX = 0.45         # max |d height / d pixel| (m per px * 1e3 -> mm/px) for a pixel to count as a brick top face: the side
                        # faces of a lifted brick, seen from above, are steep bands and would stretch the footprint
MERGE_L = 0.015         # m: margin on L when testing whether two pieces together still fit one brick footprint
MERGE_W = 0.012         # m: margin on W
EDGE_BAND_PX = 3        # how far outside an edge we look for occluder pixels
EDGE_OCC_FRAC = 0.25    # fraction of edge samples next to an occluder -> that edge is not trusted
PLANE_INLIER = 0.003    # m: second-pass plane fit keeps points this close to the first plane
MATCH_R = 0.030         # m: a detection within this of a brick's bookkeeping position is that brick (the top
                        # brick sits 45 mm from either lower brick, which the laid bed hides: never match those)
SIDE_TOL = 0.006        # m: tolerance when matching a measured extent to L / W / H


def _rect(points2d):
    """cv2.minAreaRect on an (n,2) array -> (centre(2), unit direction of the long side(2), long, short)."""
    (cx, cy), (w, h), ang = cv2.minAreaRect(np.asarray(points2d, dtype=np.float32))
    a = np.deg2rad(ang)
    ex = np.array([np.cos(a), np.sin(a)])
    if h > w:
        w, h = h, w
        ex = np.array([-ex[1], ex[0]])
    return np.array([cx, cy]), ex, float(w), float(h)


def _quat_from_axes(x, z):
    """wxyz quaternion of the rotation whose columns are (x, z cross x, z)."""
    x = np.asarray(x, dtype=np.float64); z = np.asarray(z, dtype=np.float64)
    z = z / np.linalg.norm(z); x = x - (x @ z) * z; x = x / np.linalg.norm(x); y = np.cross(z, x)
    R = np.column_stack([x, y, z])
    t = np.trace(R)
    if t > 0:
        s = np.sqrt(t + 1.0) * 2
        return np.array([0.25 * s, (R[2, 1] - R[1, 2]) / s, (R[0, 2] - R[2, 0]) / s, (R[1, 0] - R[0, 1]) / s])
    i = int(np.argmax(np.diag(R)))
    if i == 0:
        s = np.sqrt(1.0 + R[0, 0] - R[1, 1] - R[2, 2]) * 2
        return np.array([(R[2, 1] - R[1, 2]) / s, 0.25 * s, (R[0, 1] + R[1, 0]) / s, (R[0, 2] + R[2, 0]) / s])
    if i == 1:
        s = np.sqrt(1.0 + R[1, 1] - R[0, 0] - R[2, 2]) * 2
        return np.array([(R[0, 2] - R[2, 0]) / s, (R[0, 1] + R[1, 0]) / s, 0.25 * s, (R[1, 2] + R[2, 1]) / s])
    s = np.sqrt(1.0 + R[2, 2] - R[0, 0] - R[1, 1]) * 2
    return np.array([(R[1, 0] - R[0, 1]) / s, (R[0, 2] + R[2, 0]) / s, (R[1, 2] + R[2, 1]) / s, 0.25 * s])


class BrickPoseEstimator:
    def __init__(self, env, cam: str = "top", height: int = 960, width: int = 1280):
        self.env, self.cam_name, self.h, self.w = env, cam, int(height), int(width)
        self._model = None
        self._key, self._dets = None, None
        self.r_rgb = self.r_dep = None
        self.n_renders = 0

    # ------------------------------------------------------------------ camera
    def _ensure(self):
        """(Re)create the renderers when the env rebuilt its model (every reset).  The old renderers must be closed
        first: a second pair of GL contexts next to a live one renders black frames (seen on Windows GLFW)."""
        m = self.env.model
        if m is self._model:
            return
        self.close()
        self._model = m
        self.cam_id = m.camera(self.cam_name).id
        self.fovy = float(m.cam_fovy[self.cam_id])
        self.f = (self.h / 2) / np.tan(np.deg2rad(self.fovy) / 2)      # focal length, px (square pixels)
        self.r_rgb = mujoco.Renderer(m, self.h, self.w)
        self.r_dep = mujoco.Renderer(m, self.h, self.w)
        self.r_dep.enable_depth_rendering()
        u = (np.arange(self.w) + 0.5 - self.w / 2) / self.f
        v = -(np.arange(self.h) + 0.5 - self.h / 2) / self.f
        self._dirs = np.stack(np.meshgrid(u, v), axis=-1)             # (h, w, 2): x/|z|, y/|z| in the camera frame
        self._key = None

    def close(self):
        for name in ("r_rgb", "r_dep"):
            r = getattr(self, name, None)
            if r is not None:
                r.close()
                setattr(self, name, None)
        self._model = None

    def render(self):
        """RGB (h,w,3) uint8 and the world HEIGHT of every pixel (h,w) m; full xyz for chosen pixels via xyz()."""
        self._ensure()
        d = self.env.data
        self.r_rgb.update_scene(d, camera=self.cam_name); rgb = self.r_rgb.render().copy()
        self.r_dep.update_scene(d, camera=self.cam_name); dep = self.r_dep.render().copy()
        self._R = d.cam_xmat[self.cam_id].reshape(3, 3).copy(); self._t = d.cam_xpos[self.cam_id].copy(); self._dep = dep
        R, t = self._R, self._t
        # p_cam = dep * (dir_x, dir_y, -1); world z = t_z + R[2] . p_cam, done in one channel (1.2 MP: ~5 ms)
        hgt = t[2] + dep * (R[2, 0] * self._dirs[..., 0] + R[2, 1] * self._dirs[..., 1] - R[2, 2])
        self.n_renders += 1
        return rgb, hgt

    def xyz(self, ys, xs):
        """World points of the pixels (ys, xs) of the last render, (n, 3) m."""
        dep = self._dep[ys, xs]
        p = np.stack([self._dirs[ys, xs, 0] * dep, self._dirs[ys, xs, 1] * dep, -dep], axis=-1)
        return p @ self._R.T + self._t

    def project(self, p):
        """Pixel (u, v) of a world point and its depth along the camera axis (last render's camera pose)."""
        pc = self._R.T @ (np.asarray(p, dtype=np.float64) - self._t)
        z = -pc[2]
        return self.f * pc[0] / z + self.w / 2, -self.f * pc[1] / z + self.h / 2, z

    # ------------------------------------------------------------------ detection
    def detect(self, force: bool = False):
        """All bricks visible now: list of dicts (pos, quat, yaw, tilt_deg, long, short, n_px, edges, toppled, k).
        Memoised per control step (env.t) because the gate's servo asks several times per step."""
        key = (self.env.t, self.env.model)
        if not force and self._key == key:
            return self._dets
        rgb, hgt = self.render()
        B = self.env.brick
        r, g, b = rgb[..., 0].astype(np.int16), rgb[..., 1].astype(np.int16), rgb[..., 2].astype(np.int16)
        colour = (r - b >= CHROMA_MIN) & (r >= g) & (g >= b - 10) & (hgt < 0.2)
        gy, gx = np.gradient(hgt * 1000.0)                                 # mm per pixel
        flat = np.hypot(gx, gy) < FLAT_MAX
        self._colour = colour
        brick = colour & flat
        mask = cv2.morphologyEx(brick.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
        n, lab = cv2.connectedComponents(mask, connectivity=8)
        pieces = []
        for k in range(1, n):
            sel = lab == k
            if sel.sum() < MIN_PX:
                continue
            ys, xs = np.nonzero(sel)
            pts = self.xyz(ys, xs)
            c2, ex, lo, sh = _rect(pts[:, :2])
            pieces.append({"ys": ys, "xs": xs, "pts": pts, "c": c2, "ex": ex, "long": lo, "short": sh})
        pieces = self._merge_pieces(pieces, B)
        dets = []
        for pc in pieces:
            dets += self._fit(pc, hgt, B)
        self._key, self._dets = key, dets
        return dets

    def _merge_pieces(self, pieces, B):
        """Pieces of one brick cut apart by the gripper fingers or the arm are merged when their union still fits
        inside one brick footprint (L x W plus a margin).  Two butted wall bricks (181 mm) never pass this test; the
        wall course is handled by the split in _fit instead."""
        changed = True
        while changed and len(pieces) > 1:
            changed = False
            for i in range(len(pieces)):
                for j in range(i + 1, len(pieces)):
                    a, b = pieces[i], pieces[j]
                    if float(np.hypot(*(a["c"] - b["c"]))) > B.L:
                        continue
                    pts = np.concatenate([a["pts"], b["pts"]])
                    c2, ex, lo, sh = _rect(pts[:, :2])
                    if lo <= B.L + MERGE_L and sh <= B.W + MERGE_W:
                        ys = np.concatenate([a["ys"], b["ys"]]); xs = np.concatenate([a["xs"], b["xs"]])
                        pieces[i] = {"ys": ys, "xs": xs, "pts": pts, "c": c2, "ex": ex, "long": lo, "short": sh}
                        del pieces[j]
                        changed = True
                        break
                if changed:
                    break
        return pieces

    @staticmethod
    def _edge_occluded(ys, xs, u, v, u_ext, v_ext, occ_d):
        """For the four extents (u-, u+, v-, v+): is the edge there next to an occluder (the arm hides it)?"""
        out = {}
        for name, coord, ext in (("u-", u, u_ext[0]), ("u+", u, u_ext[1]), ("v-", v, v_ext[0]), ("v+", v, v_ext[1])):
            band = np.abs(coord - ext) < 0.0015                      # the pixels that form that edge
            out[name] = True if band.sum() < 3 else bool(np.mean(occ_d[ys[band], xs[band]]) > EDGE_OCC_FRAC)
        return out

    def _fit(self, pc, hgt, B):
        ys, xs, pts = pc["ys"], pc["xs"], pc["pts"]
        n_px = int(len(ys))
        # plane: PCA, then refit on inliers (keeps the top face, drops the sliver of a side face seen from above)
        cen = pts.mean(0); nrm = np.linalg.svd(pts - cen, full_matrices=False)[2][2]
        if nrm[2] < 0:
            nrm = -nrm
        inl = np.abs((pts - cen) @ nrm) < PLANE_INLIER
        if inl.sum() >= 20:
            cen = pts[inl].mean(0); nrm = np.linalg.svd(pts[inl] - cen, full_matrices=False)[2][2]
            if nrm[2] < 0:
                nrm = -nrm
            inl = np.abs((pts - cen) @ nrm) < PLANE_INLIER
            pts, ys, xs = pts[inl], ys[inl], xs[inl]               # the top face only: a side face seen at a grazing
        tilt = float(np.degrees(np.arccos(np.clip(nrm[2], -1, 1))))  # angle would stretch the extents by a few mm
        z_top = float(np.percentile(pts[:, 2], 90))
        # occluder pixels (the arm) only matter within a band around this blob: crop before dilating
        y0, y1, x0, x1 = max(ys.min() - 8, 0), ys.max() + 9, max(xs.min() - 8, 0), xs.max() + 9
        z_ref = float(np.median(pts[:, 2]))
        own = np.zeros((y1 - y0, x1 - x0), np.uint8); own[ys - y0, xs - x0] = 1   # this blob's own pixels (a brick hanging
        own = cv2.dilate(own, np.ones((5, 5), np.uint8)).astype(bool)             # tilted in the jaw: its high end is not
        occ = ((hgt[y0:y1, x0:x1] > z_ref + OCCLUDER_DZ) & ~own).astype(np.uint8)  # an occluder; anything else above is)
        occ_d = cv2.dilate(occ, np.ones((2 * EDGE_BAND_PX + 1,) * 2, np.uint8)).astype(bool)
        # in-plane frame: ex along the rectangle's long side, ey = nrm x ex
        ex3 = np.array([pc["ex"][0], pc["ex"][1], 0.0]); ex3 -= (ex3 @ nrm) * nrm; ex3 /= np.linalg.norm(ex3)
        ey3 = np.cross(nrm, ex3)
        frame = dict(pts=pts, ys=ys - y0, xs=xs - x0, cen=cen, nrm=nrm, tilt=tilt, z_top=z_top, occ_d=occ_d, n_px=n_px, B=B)
        dets = self._reconstruct(ex3, ey3, **frame)
        d0 = dets[0]
        # A fragment no longer than W in either direction (an end of the brick sticking out beside the gripper) does
        # not tell which way the brick runs: report it as ambiguous, with the alternative (axes swapped) attached.
        # The gate resolves it with a prior the robot legitimately has (the jaw's own yaw for a held brick, the slot
        # for a laid one, else its last unoccluded measurement).
        if d0["k"] == 1 and d0["long"] <= B.W + SIDE_TOL:
            alt = self._reconstruct(ey3, -ex3, **frame)[0]
            d0["ambiguous"], d0["alt"] = True, alt
            alt["ambiguous"], alt["alt"] = True, None
        return dets

    def _reconstruct(self, ex3, ey3, pts, ys, xs, cen, nrm, tilt, z_top, occ_d, n_px, B):
        """Brick centre(s) in the frame (ex3 along the bricks, ey3 across) from the visible top-face points, the
        occluded-edge flags and the known L x W; a run of k butted bricks is split into k."""
        rel = pts - cen
        u, v = rel @ ex3, rel @ ey3
        u_ext, v_ext = (float(u.min()), float(u.max())), (float(v.min()), float(v.max()))
        edges = self._edge_occluded(ys, xs, u, v, u_ext, v_ext, occ_d)
        long_m, short_m = u_ext[1] - u_ext[0], v_ext[1] - v_ext[0]
        toppled = abs(short_m - B.H) < SIDE_TOL and abs(z_top - B.W) < SIDE_TOL and short_m < B.W - SIDE_TOL
        W_use = B.H if toppled else B.W
        gap = self.env.cfg.wall.head_gap
        pitch = B.L + gap
        k = max(1, int(round((long_m + gap) / pitch)))               # butted bricks along the long axis (wall course)
        if abs(long_m - (k * pitch - gap)) > 0.012 and not (edges["u-"] or edges["u+"]):
            k = max(1, int(np.floor((long_m + gap) / pitch)))
        total = k * pitch - gap
        # across: centre from the trusted edge(s) and the known width
        if edges["v-"] and not edges["v+"]:
            vc = v_ext[1] - W_use / 2
        elif edges["v+"] and not edges["v-"]:
            vc = v_ext[0] + W_use / 2
        else:
            vc = (v_ext[0] + v_ext[1]) / 2
        # along: the run of k bricks from the trusted end(s)
        if edges["u-"] and not edges["u+"]:
            u0 = u_ext[1] - total
        elif edges["u+"] and not edges["u-"]:
            u0 = u_ext[0]
        else:
            u0 = (u_ext[0] + u_ext[1]) / 2 - total / 2
        full = k == 1 and abs(long_m - B.L) < SIDE_TOL and abs(short_m - W_use) < SIDE_TOL and not any(edges.values())
        dets = []
        for i in range(k):
            top_c = cen + (u0 + i * pitch + B.L / 2) * ex3 + vc * ey3
            if tilt < 3.0:
                top_c[2] = z_top
            pos = top_c - nrm * ((B.W if toppled else B.H) / 2)
            quat = _quat_from_axes(ex3, ey3) if toppled else _quat_from_axes(ex3, nrm)
            dets.append({"pos": pos, "quat": quat, "yaw": float(np.arctan2(ex3[1], ex3[0])),
                         "tilt_deg": 90.0 if toppled else tilt, "long": float(long_m), "short": float(short_m),
                         "n_px": n_px, "edges": edges, "toppled": bool(toppled), "k": int(k), "full": bool(full),
                         "ambiguous": False, "alt": None})
        return dets

    # ------------------------------------------------------------------ queries the gate uses
    def surface_z(self, x, y, along=(1.0, 0.0), offsets=(-0.06, 0.06), r=0.006):
        """Height of the surface around (x, y) - the laid mortar bed when the top brick is about to be released -
        sampled at two points along the wall axis so the held brick and the gripper above the centre do not hide
        it.  Median world z of the pixels there (below 12 cm, i.e. not the arm); None if nothing is visible."""
        self.detect()
        z_guess = self.env.design[-1][2] - self.env.brick.H / 2          # nominal bed top, only to aim the window
        zs = []
        for o in offsets:
            u, v, z = self.project((x + o * along[0], y + o * along[1], z_guess))
            rp = int(np.ceil(r * self.f / z))
            v0, v1, u0, u1 = int(v) - rp, int(v) + rp + 1, int(u) - rp, int(u) + rp + 1
            if v0 < 0 or u0 < 0 or v1 > self.h or u1 > self.w:
                continue
            ys, xs = np.mgrid[v0:v1, u0:u1]
            p = self.xyz(ys.ravel(), xs.ravel())
            ok = (np.abs(p[:, 0] - (x + o * along[0])) < r) & (np.abs(p[:, 1] - (y + o * along[1])) < r) & (p[:, 2] < 0.12)
            if ok.sum() >= 5:
                zs.append(float(np.median(p[ok, 2])))
        return float(np.mean(zs)) if zs else None

    def match(self, ref_xy, dets=None):
        """The detection nearest to ref_xy (the brick's bookkeeping position) within MATCH_R, else None."""
        dets = self.detect() if dets is None else dets
        best, bd = None, MATCH_R
        for d in dets:
            dd = float(np.hypot(*(d["pos"][:2] - np.asarray(ref_xy)[:2])))
            if dd < bd:
                best, bd = d, dd
        return best
