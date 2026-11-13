"""능동 카메라의 기하 선별 (학습 없음): 대본 궤적을 재생하면서, 시선 규칙에 따라 도는 팬 · 틸트 카메라 후보마다
가림 · 시선 도달 · 추종 · 화소 크기 · 입사각 · 깊이 잡음을 잰다.

정의는 04_개인연구/근거_능동카메라_20261113/기준_해석_능동카메라_20261113.md. 보이는 비율의 계산은 prl.geom_metrics 그대로다
(같은 Replay.frame). 달라진 점: 카메라가 프레임마다(20 Hz) 시선 규칙의 목표를 각속도 · 각가속도 한도 안에서 따라간다.
궤적의 모든 프레임에서 장치를 움직이고, 영상은 5스텝마다 그린다. 대본의 단계 이름은 시선 규칙에 쓰지 않는다
(벽돌 번호 k와 로봇 자기 상태만 쓴다). 참값은 지표 계산에만 쓴다: 참값 (진단).

실행: cd sim && MUJOCO_GL=egl PYTHONPATH=. venv/bin/python -m prl.geom_active --traj outputs/prl/s2_traj_20261112 \\
        --cams-json <후보 정의> --out outputs/prl/<이름> [--seeds ...] [--clearance] [--workers 20] [--chunk 12]
"""
import argparse, json, time
from multiprocessing import Pool
from pathlib import Path

import mujoco
import numpy as np

from wall3.config import H, W, RETRACT_Q
from prl import config as C
from prl.active_cam import ActiveRig, PanTiltSpec, rig_specs
from prl.geom_metrics import Replay, EVERY, HELD_PH, RW, RH, SEGMENTS, TARGETS, clearance, load_traj, seg_of_phase
from prl.run_script import PHASES

CENTER = 0.25            # 영상 가운데 50 % = 중심에서 가로 · 세로 각각 ± 25 %


def spec_from(d):
    return PanTiltSpec(**d) if d else PanTiltSpec()


def centred(view, pt):
    u, v, z = view.project(pt)
    return bool(z[0] > 0.02 and abs(u[0] - RW / 2) <= CENTER * RW and abs(v[0] - RH / 2) <= CENTER * RH)


def one_task(args):
    """One wall × one chunk of cameras: (frames, cams, 4) visible ratios, (frames, cams, 2) 'target in the central 50 %'
    for [brick to pick, place slot], (frames, cams) gaze error and unit speed (deg, deg/s)."""
    traj_dir, seed, cams, spec_d = args
    spec = spec_from(spec_d)
    z = load_traj(traj_dir, seed)
    n = len(z["t"])
    rp = Replay([], rig_specs(cams, spec))
    env = rp.env
    rig = ActiveRig(env, cams, RETRACT_Q, spec)
    names = rp.cams
    assert names == list(cams)
    idx = np.arange(0, n, EVERY)
    vis = np.full((len(idx), len(names), 4), np.nan, np.float32)
    cen = np.zeros((len(idx), len(names), 2), bool)
    gerr = np.zeros((len(idx), len(names)), np.float32)
    spd = np.zeros((len(idx), len(names)), np.float32)
    m, d = env.model, env.data
    j = 0
    for i in range(n):
        k = int(z["brick"][i])
        d.qpos[:] = z["qpos"][i]
        mujoco.mj_kinematics(m, d)
        if i == 0:
            rig.reset(max(k, 0))
        else:
            rig.update(k)
        if i % EVERY:
            continue
        if k >= 0:
            mujoco.mj_forward(m, d)
            for v in rp.views.values():
                v.update()
            vis[j] = rp.frame(k, PHASES[int(z["phase"][i])])
            pick = d.xpos[env.brick_bid[k]]
            slot = rig.task.slot[k]
            for ci, nme in enumerate(names):
                v = rp.views[nme]
                cen[j, ci] = [centred(v, pick), centred(v, slot)]
                gerr[j, ci] = rig.unit[nme].error_deg()
                spd[j, ci] = rig.unit[nme].speed_deg()
        j += 1
    rp.close()
    return {"seed": seed, "cams": names, "vis": vis, "cen": cen, "gerr": gerr, "spd": spd,
            "t": z["t"][idx], "phase": z["phase"][idx], "brick": z["brick"][idx]}


def static_task(args):
    """Gaze reach of every camera to the 16 supply bricks (nominal, arm retracted) and the 16 place slots (bricks 0 .. k−1 at
    their design poses): inside the joint limits, inside the depth range, visible ratio with the target on the optical axis;
    distance along the axis, incidence angle."""
    cams, spec_d = args
    spec = spec_from(spec_d)
    rp = Replay([], rig_specs(cams, spec))
    env = rp.env
    rig = ActiveRig(env, cams, RETRACT_Q, spec)
    m, d = env.model, env.data
    env.reset(C.SEED_ZONES["geom"][0], arm_q=np.array(RETRACT_Q))
    nominal = []
    for i in range(env.n):
        p, _ = env.supply_pose(i, None)
        a = env.brick_qadr[i]
        d.qpos[a:a + 3] = p; d.qpos[a + 3:a + 7] = [1, 0, 0, 0]
        nominal.append(p.copy())
    base = d.qpos.copy()
    lo, hi = C.DEPTH_NOISE[spec.kind]["range_m"]
    out = {nme: {"supply": [], "wall": []} for nme in cams}

    def look(nme, side, point, ratio_fn):
        ok = rig.aim(nme, point)
        v = rp.views[nme]
        v.update()
        _, _, zz = v.project(point)
        ray = point - v.p
        gid, dep = rp.render(nme)
        out[nme][side].append({"in_limits": bool(ok), "z_m": float(zz[0]), "in_range": bool(lo <= zz[0] <= hi),
                               "incidence_deg": float(np.degrees(np.arccos(abs(ray[2]) / np.linalg.norm(ray)))),
                               "visible": float(ratio_fn(v, gid, dep))})

    d.qpos[:] = base
    mujoco.mj_forward(m, d)
    for i in range(env.n):
        top = nominal[i] + [0, 0, H / 2]
        for nme in cams:
            look(nme, "supply", top, lambda v, gid, dep, i=i: rp.brick_ratio(v, gid, i))
    for k in range(env.n):
        q = base.copy()
        for i in range(k):
            s = env.design[i]
            a = env.brick_qadr[i]
            q[a:a + 3] = [s["x"], s["y"], s["z"]]
        d.qpos[:] = q
        mujoco.mj_forward(m, d)
        s = env.design[k]
        bot = np.array([s["x"], s["y"], s["z"] - H / 2])
        for nme in cams:
            look(nme, "wall", bot, lambda v, gid, dep, k=k: rp.slot_ratio(v, dep, k, bottom_only=True))
    rp.close()
    return out


def clear_task(args):
    """Min distance over the frames from each camera body (sphere, radius CAM_BODY_R) to (a) the arm + gripper + held brick,
    (b) the scene: floor, table, pedestal and every brick that is not held. Negative = overlapping."""
    traj_dir, seed, cams, spec_d = args
    from prl.env import DryEnv
    z = load_traj(traj_dir, seed)
    idx = np.arange(0, len(z["t"]), EVERY)
    phase = [PHASES[p] for p in z["phase"][idx]]
    held = [int(b) if (p in HELD_PH and b >= 0) else -1 for p, b in zip(phase, z["brick"][idx])]
    env = DryEnv(fixed_cams={}, extra_cams=rig_specs(cams, spec_from(spec_d)), cam_markers=True)
    cl = clearance(env, z["qpos"][idx], held, list(cams))
    m, d = env.model, env.data
    scene = [m.geom(n).id for n in ("floor", "table", "pedestal")]
    ft = np.zeros(6)
    sc = {n: np.inf for n in cams}
    for q, h in list(zip(z["qpos"][idx], held))[::20]:          # the scene changes slowly: every 100th step
        d.qpos[:] = q
        mujoco.mj_forward(m, d)
        others = scene + [env.brick_gid[i] for i in range(env.n) if i != h]
        for n in cams:
            mk = m.geom(f"cam_{n}").id
            sc[n] = min(sc[n], min(mujoco.mj_geomDistance(m, d, mk, g, 0.5, ft) for g in others))
    env.close()
    return {n: {"robot": cl[n]["robot"], "scene": float(sc[n])} for n in cams}


def reach_summary(st, spec):
    """Per camera: number of the 16 + 16 targets that the gaze reaches (limits, depth range, visible ≥ 0.5 when centred), and the
    pixel size / incidence / depth noise at the farthest reached target of each side."""
    f_raw = C.focal_px(spec.fovy)
    out = {}
    for nme, o in st.items():
        r = {}
        for side in ("supply", "wall"):
            rows = o[side]
            ok = [x["in_limits"] and x["in_range"] and x["visible"] >= 0.5 for x in rows]
            geo = [x["in_limits"] and x["in_range"] for x in rows]
            zs = np.array([x["z_m"] for x in rows])
            r[side] = {"reach": int(sum(ok)), "reach_geom": int(sum(geo)), "flags": [bool(x) for x in ok],
                       "z_m": [float(x) for x in zs], "raw_mm_per_px": [float(x / f_raw * 1000) for x in zs],
                       "incidence_deg": [x["incidence_deg"] for x in rows],
                       "z_far_m": float(zs.max()), "raw_mm_per_px_far": float(zs.max() / f_raw * 1000),
                       "incidence_max_deg": float(max(x["incidence_deg"] for x in rows)),
                       "depth_sigma_mm_far": float(C.depth_sigma(zs.max(), spec.fovy, spec.kind) * 1000)}
        out[nme] = r
    return out


def summarize(vis, cen, phase, cams):
    """Per camera: {segment: {target: {median, frac_lt50, n}}} as prl.geom_metrics.summarize, plus the share of the approach
    frames with the target in the central 50 % of the image (pick approach: brick to pick, place approach: place slot)."""
    seg = seg_of_phase()[phase]
    segs = list(SEGMENTS)
    out = {}
    for ci, nme in enumerate(cams):
        o = {}
        for si, sname in enumerate(segs):
            o[sname] = {}
            for ti, tname in enumerate(TARGETS):
                v = vis[seg == si, ci, ti]
                v = v[np.isfinite(v)]
                o[sname][tname] = ({"median": float(np.median(v)), "frac_lt50": float(np.mean(v < 0.5)), "n": int(len(v))}
                                   if len(v) else None)
        ok = np.isfinite(vis[:, ci, 1])
        o["centred"] = {"pick_approach": float(cen[(seg == segs.index("집기 접근")) & ok, ci, 0].mean()),
                        "place_approach": float(cen[(seg == segs.index("놓기 접근")) & ok, ci, 1].mean())}
        out[nme] = o
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--traj", required=True)
    ap.add_argument("--cams-json", required=True, help='{"spec": {...PanTiltSpec...}, "cams": {name: {base, pan0, role, leave, point}}}')
    ap.add_argument("--out", required=True)
    ap.add_argument("--seeds", type=int, nargs="*", default=None)
    ap.add_argument("--clearance", action="store_true", help="also the clearance between the camera bodies and the robot")
    ap.add_argument("--workers", type=int, default=20)
    ap.add_argument("--chunk", type=int, default=12, help="cameras per process")
    a = ap.parse_args()
    out = Path(a.out)
    if out.exists():
        raise SystemExit(f"{out} 이미 있음: 덮어쓰지 않음")
    cfg = json.loads(Path(a.cams_json).read_text())
    cams, spec_d = cfg["cams"], cfg.get("spec") or {}
    spec = spec_from(spec_d)
    summ = json.loads((Path(a.traj) / "summary.json").read_text())
    seeds = a.seeds or [w["seed"] for w in summ["walls"]]
    C.check_seeds("geom", seeds)
    out.mkdir(parents=True)
    t0 = time.time()
    names = list(cams)
    chunks = [{n: cams[n] for n in names[i:i + a.chunk]} for i in range(0, len(names), a.chunk)]
    with Pool(a.workers) as p:
        st_parts = p.map(static_task, [(c, spec_d) for c in chunks])
        res = p.map(one_task, [(a.traj, s, c, spec_d) for s in seeds for c in chunks])
        cl = None
        if a.clearance:
            parts = p.map(clear_task, [(a.traj, s, c, spec_d) for s in seeds for c in chunks])
            cl = {}
            for part in parts:
                for nme, o in part.items():
                    c0 = cl.setdefault(nme, {"robot": np.inf, "scene": np.inf})
                    c0["robot"] = min(c0["robot"], o["robot"]); c0["scene"] = min(c0["scene"], o["scene"])
    st = {}
    for part in st_parts:
        st.update(part)
    by_seed = {}
    for r in res:
        by_seed.setdefault(r["seed"], []).append(r)
    vis, cen, gerr, spd, phase, brick, tt, wall = [], [], [], [], [], [], [], []
    for s in seeds:
        parts = by_seed[s]
        assert [n for r in parts for n in r["cams"]] == names
        vis.append(np.concatenate([r["vis"] for r in parts], axis=1))
        cen.append(np.concatenate([r["cen"] for r in parts], axis=1))
        gerr.append(np.concatenate([r["gerr"] for r in parts], axis=1))
        spd.append(np.concatenate([r["spd"] for r in parts], axis=1))
        phase.append(parts[0]["phase"]); brick.append(parts[0]["brick"]); tt.append(parts[0]["t"])
        wall.append(np.full(len(parts[0]["t"]), s))
    vis, cen, gerr, spd = (np.concatenate(x) for x in (vis, cen, gerr, spd))
    phase, brick, tt, wall = (np.concatenate(x) for x in (phase, brick, tt, wall))
    np.savez_compressed(out / "frames.npz", vis=vis, cen=cen, gerr=gerr, spd=spd, phase=phase, brick=brick, t=tt, wall=wall,
                        cams=np.array(names))
    meta = {"traj": a.traj, "seeds": seeds, "every": EVERY, "render": [RW, RH], "spec": spec.to_dict(), "cams": cams,
            "traj_env_sha256": summ.get("env_sha256"), "elapsed_s": time.time() - t0}
    (out / "metrics.json").write_text(json.dumps({"meta": meta, "occlusion": summarize(vis, cen, phase, names),
                                                  "reach": reach_summary(st, spec), "reach_raw": st,
                                                  "clearance_m": cl}, indent=1, ensure_ascii=False))
    print(f"done: {len(names)} cameras, {len(vis)} frames, {meta['elapsed_s']:.0f} s")


if __name__ == "__main__":
    main()
