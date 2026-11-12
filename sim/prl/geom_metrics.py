"""2단계 기하 선별 (학습 없음): 대본 궤적을 재생하면서 카메라 후보마다 가림 · 포함 · 화소 크기 · 입사각 · 깊이 잡음을 잰다.

정의는 04_개인연구/근거_카메라선정_20261112/기준_해석_20261112.md 3절. 궤적은 prl.run_script --save-traj가 남긴 qpos를 그대로 재생한다
(시뮬레이션을 다시 돌리지 않음). 분할 · 깊이 영상은 640 × 480.

실행: cd sim && MUJOCO_GL=egl PYTHONPATH=. venv/bin/python -m prl.geom_metrics --traj outputs/prl/s2_traj_20261112 \\
        --out outputs/prl/<이름> [--cams-json <고정 카메라 정의>] [--seeds 800000 ...] [--clearance-only]
"""
import argparse, json, time
from multiprocessing import Pool
from pathlib import Path

import cv2
import mujoco
import numpy as np

from wall3.config import H, W, RETRACT_Q
from wall3.spec_metrics import EXIST_XY, EXIST_Z
from prl import config as C
from prl.env import DryEnv, cam_model_name, make_renderer
from prl.run_script import PHASES

RW, RH = 640, 480
EVERY = 5
TARGETS = ("pick", "slot", "held", "tip")
SEGMENTS = {"집기 접근": ("to_supply", "grasp_descend"), "집기": ("grasp_close", "grasp_lift"), "운반": ("to_wall",),
            "놓기 접근": ("place_align", "place_descend", "place_servo", "place_lower"),
            "놓기": ("place_unload", "place_open", "retreat")}
PICK_PH = {"to_supply", "grasp_descend", "grasp_close"}
HELD_PH = {"grasp_lift", "to_wall", "place_align", "place_descend", "place_servo", "place_lower", "place_unload"}
DEPTH_EPS = 0.002


def box_corners(p, R, half):
    s = np.array([[x, y, z] for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)], float) * half
    return p + s @ R.T


class CamView:
    """Pinhole of one model camera at the current data (640 × 480)."""

    def __init__(self, env, name):
        self.env, self.name = env, name
        self.cid = env.model.camera(cam_model_name(name)).id
        self.f = (RH / 2) / np.tan(np.radians(float(env.model.cam_fovy[self.cid])) / 2)

    def update(self):
        d = self.env.data
        self.p = d.cam_xpos[self.cid].copy()
        self.R = d.cam_xmat[self.cid].reshape(3, 3).copy()

    def project(self, P):
        pc = (np.atleast_2d(P) - self.p) @ self.R
        z = -pc[:, 2]
        with np.errstate(divide="ignore", invalid="ignore"):
            u = self.f * pc[:, 0] / z + RW / 2
            v = -self.f * pc[:, 1] / z + RH / 2
        return u, v, z

    def hull(self, corners):
        """(area in px², mask of in-image pixels) of the convex hull of the projected corners; (0, None) if behind the camera."""
        u, v, z = self.project(corners)
        if (z <= 0.02).any():
            return 0.0, None
        pts = np.clip(np.stack([u, v], 1), -2e4, 2e4).astype(np.float32)
        hl = cv2.convexHull(pts)
        area = float(cv2.contourArea(hl))
        mask = np.zeros((RH, RW), np.uint8)
        cv2.fillConvexPoly(mask, np.round(hl * 16).astype(np.int32), 1, lineType=cv2.LINE_8, shift=4)
        return area, mask.astype(bool)

    def box_entry_depth(self, lo, hi, ys, xs):
        """Optical-axis depth at which the pixel rays enter the world-aligned box [lo, hi] (nan where they miss)."""
        dc = np.stack([(xs + 0.5 - RW / 2) / self.f, -(ys + 0.5 - RH / 2) / self.f, -np.ones(len(xs))], 1)
        dw = dc @ self.R.T
        with np.errstate(divide="ignore", invalid="ignore"):
            t1 = (lo - self.p) / dw
            t2 = (hi - self.p) / dw
        tn, tf = np.nanmax(np.minimum(t1, t2), 1), np.nanmin(np.maximum(t1, t2), 1)
        return np.where((tn <= tf) & (tf > 0), np.maximum(tn, 0), np.nan)


class Replay:
    def __init__(self, cams, extra=None, markers=False):
        fixed = {n: C.FIXED_CAMS[n] for n in cams if n in C.FIXED_CAMS}
        self.env = DryEnv(fixed_cams=fixed, extra_cams=extra, cam_markers=markers)
        env = self.env
        m = env.model
        self.cams = [n for n in cams if n in C.FIXED_CAMS or n in C.WRIST_CAMS] + list(extra or {})
        self.views = {n: CamView(env, n) for n in self.cams}
        self.r_seg = make_renderer(m, RH, RW, "seg")           # sampled at the pixel centres (no multisampling)
        self.r_dep = make_renderer(m, RH, RW, "depth")
        self.tip_col = [m.geom("g_left_fingertip_collision").id, m.geom("g_right_fingertip_collision").id]
        self.tip_ids = np.array([m.geom(f"g_{s}_{n}").id for s in ("left", "right")
                                 for n in ("fingertip_collision", "fingertip_visual", "fingerpad_collision")])
        self.q_ret = np.array(RETRACT_Q)

    def close(self):
        self.r_seg.close(); self.r_dep.close(); self.env.close()

    def set_qpos(self, qpos):
        self.env.data.qpos[:] = qpos
        mujoco.mj_forward(self.env.model, self.env.data)
        for v in self.views.values():
            v.update()

    def render(self, cam):
        d = self.env.data
        self.r_seg.update_scene(d, camera=cam_model_name(cam), scene_option=self.env.vopt)
        seg = self.r_seg.render()
        gid = np.where(seg[..., 1] == int(mujoco.mjtObj.mjOBJ_GEOM), seg[..., 0], -1)
        self.r_dep.update_scene(d, camera=cam_model_name(cam), scene_option=self.env.vopt)
        return gid, self.r_dep.render()

    # ---- visible ratios of the four targets at the current state, for one camera
    def brick_ratio(self, view, gid, i):
        env = self.env
        d = env.data
        b = env.brick_bid[i]
        area, mask = view.hull(box_corners(d.xpos[b], d.xmat[b].reshape(3, 3), np.array([env.design[i]["L"], W, H]) / 2))
        if area < 1.0:
            return 0.0
        return float(min(1.0, np.count_nonzero(gid == env.brick_gid[i]) / area))

    def slot_ratio(self, view, dep, k, bottom_only=False, gid=None):
        """Visible ratio of the design slot box k: pixels of its projection with nothing in front of the box.
        gid given (segmentation image): brick k itself counts as visible once it is in the slot (기준_해석 3절: 벽돌이 자리에
        들어가 있으면 보이는 것으로 센다). 'In the slot' = the presence check of spec_metrics (채움: 수평 45 mm, 높이 28.5 mm)."""
        s = self.env.design[k]
        half = np.array([s["L"], W, H]) / 2
        c = np.array([s["x"], s["y"], s["z"]])
        if bottom_only:                                   # the support face of the slot (static inclusion)
            c = c - [0, 0, H / 2 - 0.0005]; half = half * [1, 1, 0] + [0, 0, 0.0005]
        area, mask = view.hull(box_corners(c, np.eye(3), half))
        if area < 1.0 or mask is None or not mask.any():
            return 0.0
        ys, xs = np.nonzero(mask)
        te = view.box_entry_depth(c - half, c + half, ys, xs)
        vis = np.isfinite(te) & (dep[ys, xs] >= te - DEPTH_EPS)
        if gid is not None and self.in_slot(k):
            vis |= np.isfinite(te) & (gid[ys, xs] == self.env.brick_gid[k])
        return float(min(1.0, np.count_nonzero(vis) / area))

    def in_slot(self, k):
        s = self.env.design[k]
        p = self.env.data.xpos[self.env.brick_bid[k]]
        return bool(np.hypot(p[0] - s["x"], p[1] - s["y"]) <= EXIST_XY and abs(p[2] - s["z"]) <= EXIST_Z)

    def tip_ratio(self, view, gid):
        m, d = self.env.model, self.env.data
        tot = 0.0
        for g in self.tip_col:
            a, _ = view.hull(box_corners(d.geom_xpos[g], d.geom_xmat[g].reshape(3, 3), m.geom_size[g]))
            tot += a
        if tot < 1.0:
            return 0.0
        return float(min(1.0, np.count_nonzero(np.isin(gid, self.tip_ids)) / tot))

    def frame(self, k, phase):
        """(n_cams, 4) visible ratios [pick, slot, held, tip] (nan where the target does not apply)."""
        out = np.full((len(self.cams), 4), np.nan)
        for ci, n in enumerate(self.cams):
            v = self.views[n]
            gid, dep = self.render(n)
            if phase in PICK_PH:
                out[ci, 0] = self.brick_ratio(v, gid, k)
            out[ci, 1] = self.slot_ratio(v, dep, k, gid=gid)
            if phase in HELD_PH:
                out[ci, 2] = self.brick_ratio(v, gid, k)
            out[ci, 3] = self.tip_ratio(v, gid)
        return out

    # ---- static quantities
    def static(self):
        """Per camera: inclusion of the 16 supply bricks' top faces and the 16 place slots' support faces with the arm
        retracted (corners inside the central 90 %; and visible ratio ≥ 0.5), pixel size, incidence angle, depth noise."""
        env = self.env
        m, d = env.model, env.data
        env.reset(C.SEED_ZONES["geom"][0], arm_q=self.q_ret)
        nominal = []
        for i in range(env.n):                                   # nominal supply poses (no scatter)
            p, yaw = env.supply_pose(i, None)
            a = env.brick_qadr[i]
            d.qpos[a:a + 3] = p; d.qpos[a + 3:a + 7] = [1, 0, 0, 0]
            nominal.append(p.copy())
        base = d.qpos.copy()
        out = {n: {"supply_in": [], "supply_in_vis": [], "wall_in": [], "wall_in_vis": [], "supply_z": [], "wall_z": [],
                   "supply_inc": [], "wall_inc": []} for n in self.cams}

        def inside(view, rect):
            u, v, z = view.project(rect)
            return bool((z > 0.02).all() and (np.abs(u - RW / 2) <= 0.45 * RW).all() and (np.abs(v - RH / 2) <= 0.45 * RH).all())

        def axis_dist_inc(view, pt):
            _, _, z = view.project(pt)
            ray = pt - view.p
            return float(z[0]), float(np.degrees(np.arccos(abs(ray[2]) / np.linalg.norm(ray))))

        self.set_qpos(base)
        for n in self.cams:                                      # supply
            v = self.views[n]
            gid, dep = self.render(n)
            for i in range(env.n):
                s = env.design[i]
                top = nominal[i] + [0, 0, H / 2]
                rect = top + np.array([[sx * s["L"] / 2, sy * W / 2, 0] for sx in (-1, 1) for sy in (-1, 1)])
                inn = inside(v, rect)
                out[n]["supply_in"].append(inn)
                out[n]["supply_in_vis"].append(bool(inn and self.brick_ratio(v, gid, i) >= 0.5))
                z, inc = axis_dist_inc(v, top)
                out[n]["supply_z"].append(z); out[n]["supply_inc"].append(inc)
        for k in range(env.n):                                   # place slot k with bricks 0 .. k−1 at design
            q = base.copy()
            for i in range(k):
                s = env.design[i]
                a = env.brick_qadr[i]
                q[a:a + 3] = [s["x"], s["y"], s["z"]]
            self.set_qpos(q)
            s = env.design[k]
            bot = np.array([s["x"], s["y"], s["z"] - H / 2])
            rect = bot + np.array([[sx * s["L"] / 2, sy * W / 2, 0] for sx in (-1, 1) for sy in (-1, 1)])
            for n in self.cams:
                v = self.views[n]
                gid, dep = self.render(n)
                inn = inside(v, rect)
                out[n]["wall_in"].append(inn)
                out[n]["wall_in_vis"].append(bool(inn and self.slot_ratio(v, dep, k, bottom_only=True) >= 0.5))
                z, inc = axis_dist_inc(v, bot + [0, 0, H])
                out[n]["wall_z"].append(z); out[n]["wall_inc"].append(inc)
        return out


def clearance(env, qpos_frames, held_frames, names):
    """Min distance (m) over the frames from each camera marker to (a) the arm + gripper + held brick, (b) for wrist cameras
    also the scene (table, floor, pedestal, other bricks). Negative = overlapping."""
    m, d = env.model, env.data
    robot = [g for g in range(m.ngeom) if m.geom_bodyid[g] in env.robot_bodies and (m.geom_contype[g] or m.geom_conaffinity[g])]
    grip = [g for g in robot if m.geom_bodyid[g] in env.gripper_bodies]
    scene = [m.geom(n).id for n in ("floor", "table", "pedestal")]
    out = {n: {"robot": np.inf, "gripper": np.inf, "scene": np.inf} for n in names}
    ft = np.zeros(6)
    for q, held in zip(qpos_frames, held_frames):
        d.qpos[:] = q
        mujoco.mj_forward(m, d)
        for n in names:
            mk = m.geom(f"cam_{n}").id
            if n in C.WRIST_CAMS:
                g_list = grip + ([env.brick_gid[held]] if held >= 0 else [])
                dist = min(mujoco.mj_geomDistance(m, d, mk, g, 0.5, ft) for g in g_list)
                out[n]["gripper"] = min(out[n]["gripper"], dist)
                others = scene + [env.brick_gid[i] for i in range(env.n) if i != held]
                out[n]["scene"] = min(out[n]["scene"], min(mujoco.mj_geomDistance(m, d, mk, g, 0.5, ft) for g in others))
            else:
                g_list = robot + ([env.brick_gid[held]] if held >= 0 else [])
                out[n]["robot"] = min(out[n]["robot"], min(mujoco.mj_geomDistance(m, d, mk, g, 0.5, ft) for g in g_list))
    return {n: {k: (None if not np.isfinite(v) else float(v)) for k, v in o.items()} for n, o in out.items()}


def load_traj(traj_dir, seed):
    z = np.load(Path(traj_dir) / "raw" / f"traj_{seed}.npz")
    return {k: z[k] for k in z.files}


def one_wall(args):
    traj_dir, seed, cams, extra, do_clear = args
    z = load_traj(traj_dir, seed)
    idx = np.arange(0, len(z["t"]), EVERY)
    phase = [PHASES[p] for p in z["phase"][idx]]
    brick = z["brick"][idx]
    res = {"seed": seed, "t": z["t"][idx], "phase": z["phase"][idx], "brick": brick}
    if do_clear:
        env = DryEnv(fixed_cams={n: C.FIXED_CAMS[n] for n in cams if n in C.FIXED_CAMS}, extra_cams=extra, cam_markers=True)
        held = [int(b) if (p in HELD_PH and b >= 0) else -1 for p, b in zip(phase, brick)]
        names = [n for n in cams if n in C.FIXED_CAMS or n in C.WRIST_CAMS] + list(extra or {})
        res["clearance"] = clearance(env, z["qpos"][idx], held, names)
        env.close()
        return res
    rp = Replay(cams, extra)
    vis = np.full((len(idx), len(rp.cams), 4), np.nan, np.float32)
    for j, i in enumerate(idx):
        if brick[j] < 0:
            continue
        rp.set_qpos(z["qpos"][i])
        vis[j] = rp.frame(int(brick[j]), phase[j])
    res["vis"] = vis
    res["cams"] = rp.cams
    rp.close()
    return res


def seg_of_phase():
    out = np.full(len(PHASES), -1)
    for si, (name, phs) in enumerate(SEGMENTS.items()):
        for p in phs:
            out[PHASES.index(p)] = si
    return out


def summarize(vis, phase, cams):
    """Per camera: {segment: {target: {median, frac_lt50, n}}}."""
    seg = seg_of_phase()[phase]
    out = {}
    for ci, n in enumerate(cams):
        o = {}
        for si, sname in enumerate(SEGMENTS):
            o[sname] = {}
            for ti, tname in enumerate(TARGETS):
                v = vis[seg == si, ci, ti]
                v = v[np.isfinite(v)]
                o[sname][tname] = ({"median": float(np.median(v)), "frac_lt50": float(np.mean(v < 0.5)), "n": int(len(v))}
                                   if len(v) else None)
        out[n] = o
    return out


def static_summary(st, env_fovy):
    out = {}
    for n, o in st.items():
        f_raw = C.focal_px(env_fovy[n])
        kind = "d405" if n in C.WRIST_CAMS else "d435"
        r = {"supply_in": int(sum(o["supply_in"])), "supply_in_vis": int(sum(o["supply_in_vis"])),
             "wall_in": int(sum(o["wall_in"])), "wall_in_vis": int(sum(o["wall_in_vis"])), "fovy_deg": env_fovy[n], "focal_raw_px": f_raw}
        for side in ("supply", "wall"):
            zs = np.array(o[f"{side}_z"])
            ok = zs > 0.02
            if not ok.any():
                continue
            zf = float(zs[ok].max())
            mmpx = zf / f_raw * 1000
            r[side] = {"z_far_m": zf, "raw_mm_per_px": mmpx, "px224_per_90mm": 90.0 / (mmpx * C.RAW_W / C.POLICY_IMG),
                       "incidence_max_deg": float(np.max(np.array(o[f"{side}_inc"])[ok])),
                       "depth_sigma_mm": float(C.depth_sigma(zf, env_fovy[n], kind) * 1000)}
        out[n] = r
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--traj", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--seeds", type=int, nargs="*", default=None)
    ap.add_argument("--cams", nargs="*", default=None, help="candidate names (default: all fixed + wrist)")
    ap.add_argument("--extra-json", default=None, help="json {name: {pos, target, up, fovy}} of more fixed cameras (G1 grid, moved cameras)")
    ap.add_argument("--clearance-only", action="store_true")
    ap.add_argument("--static-only", action="store_true", help="only the static block (inclusion flags per slot, pixel size, angles)")
    ap.add_argument("--workers", type=int, default=10)
    a = ap.parse_args()
    out = Path(a.out)
    if out.exists():
        raise SystemExit(f"{out} 이미 있음: 덮어쓰지 않음")
    summ = json.loads((Path(a.traj) / "summary.json").read_text())
    seeds = a.seeds or [w["seed"] for w in summ["walls"]]
    C.check_seeds("geom", seeds)
    cams = a.cams if a.cams is not None else list(C.FIXED_CAMS) + list(C.WRIST_CAMS)
    extra = json.loads(Path(a.extra_json).read_text()) if a.extra_json else None
    out.mkdir(parents=True)
    t0 = time.time()
    if a.static_only:
        rp = Replay(cams, extra)
        raw = rp.static()
        st = static_summary(raw, rp.env.cam_fovy | {n: float(c["fovy"]) for n, c in (extra or {}).items()})
        rp.close()
        flags = {n: {k: [bool(x) for x in o[k]] for k in ("supply_in", "supply_in_vis", "wall_in", "wall_in_vis")} for n, o in raw.items()}
        (out / "static.json").write_text(json.dumps({"cams": cams, "extra": extra, "static": st, "static_flags": flags}, indent=1))
        print(f"static: {len(st)} cameras, {time.time() - t0:.0f} s")
        return
    with Pool(min(a.workers, len(seeds))) as p:
        res = p.map(one_wall, [(a.traj, s, cams, extra, a.clearance_only) for s in seeds])
    meta = {"traj": a.traj, "seeds": seeds, "cams": cams, "extra": extra, "every": EVERY, "render": [RW, RH],
            "traj_env_sha256": summ.get("env_sha256"), "elapsed_s": None}
    if a.clearance_only:
        names = list(res[0]["clearance"])
        cl = {n: {k: (min(r["clearance"][n][k] for r in res) if res[0]["clearance"][n][k] is not None else None)
                  for k in ("robot", "gripper", "scene")} for n in names}
        meta["elapsed_s"] = time.time() - t0
        (out / "clearance.json").write_text(json.dumps({"meta": meta, "clearance_m": cl}, indent=1))
        print(json.dumps(cl, indent=1))
        return
    names = res[0]["cams"]
    vis = np.concatenate([r["vis"] for r in res])
    phase = np.concatenate([r["phase"] for r in res])
    np.savez_compressed(out / "frames.npz", vis=vis, phase=phase, brick=np.concatenate([r["brick"] for r in res]),
                        t=np.concatenate([r["t"] for r in res]), wall=np.concatenate([np.full(len(r["t"]), r["seed"]) for r in res]),
                        cams=np.array(names))
    rp = Replay(cams, extra)
    raw = rp.static()
    st = static_summary(raw, rp.env.cam_fovy | {n: float(c["fovy"]) for n, c in (extra or {}).items()})
    rp.close()
    flags = {n: {k: [bool(x) for x in o[k]] for k in ("supply_in", "supply_in_vis", "wall_in", "wall_in_vis")} for n, o in raw.items()}
    meta["elapsed_s"] = time.time() - t0
    (out / "metrics.json").write_text(json.dumps({"meta": meta, "occlusion": summarize(vis, phase, names), "static": st,
                                                  "static_flags": flags}, indent=1))
    print(f"done: {len(names)} cameras, {len(vis)} frames, {meta['elapsed_s']:.0f} s")


if __name__ == "__main__":
    main()
