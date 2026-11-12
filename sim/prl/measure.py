"""3단계 측정 오차: 세팅마다 그 세팅의 카메라로 벽돌 자세를 재고(정답 좌표 없이, 깊이 잡음 넣고) 참값과 비교한다.

절차는 기준_해석_20261112.md 6절. 장면마다:
  공급대의 벽돌: 초기화 뒤 팔이 철수 자세일 때 16장. 공급 쪽 고정 카메라(SA1 · SB1 · G1), R0는 손목 H0를 그 칸 위 접근 자세에 두고.
  놓인 벽돌: 대본으로 벽을 쌓으면서 벽돌 k를 놓고 철수 자세로 돌아온 때. 벽 쪽 고정 카메라(WA1 · WA2 · WC1 · WE1 · G1).
  손에 든 벽돌: 운반이 끝난 때(자리 위 0.10 m). 벽 쪽 고정 카메라와 손목 H0.
카메라별로 한 번씩 재고, 세팅별 표는 그 세팅이 쓰는 카메라의 값을 가져온다(같은 카메라는 같은 측정).

실행: cd sim && MUJOCO_GL=egl PYTHONPATH=. venv/bin/python -m prl.measure --zone select --seed0 820000 --n 100 --out outputs/prl/<이름>
"""
import argparse, json, subprocess, time
from multiprocessing import Pool
from pathlib import Path

import mujoco
import numpy as np

SIM = Path(__file__).resolve().parents[1]
SUPPLY_CAMS = ("SA1", "SB1", "G1")
WALL_CAMS = ("WA1", "WA2", "WC1", "WE1", "G1")
SETTING_CAMS = {"R0": ("H0", "WA1"), "RA": ("SA1", "WA2"), "RB": ("SB1", "WC1"), "RC": ("SA1", "WC1"), "RD": ("SB1", "WE1"), "RE": ("G1", "G1")}


def fold(a, period):
    return (a + period / 2) % period - period / 2


def one_scene(args):
    seed, = args
    import cv2
    cv2.setNumThreads(1)
    from wall3.config import H
    from wall3.ik import down_R
    from wall3.poses import yaw_of_quat
    from prl import config as C
    from prl.env import DryEnv, noisy_depth
    from prl.expert import DryExpert
    from prl.perception import Camera, measure
    t0 = time.time()
    env = DryEnv(fixed_cams=C.final_cams())
    ex = DryExpert(env)
    m, d = env.model, env.data
    cam_idx = {n: i for i, n in enumerate(list(C.final_cams()) + ["H0"])}
    recs = []

    def grab(name, tag, k):
        kind = "d405" if name in C.WRIST_CAMS else "d435"
        fovy = env.cam_fovy[name]
        rng = np.random.default_rng([seed, cam_idx[name], tag, k + 1])
        rgb = env.render_raw(name)
        dep = noisy_depth(env.render_raw(name, depth=True), fovy, kind, rng)
        p, R = env.cam_pose(name)
        return rgb, dep, Camera(fovy, R, p, C.RAW_W, C.RAW_H, sigma_fn=lambda z: C.depth_sigma(z, fovy, kind))

    def record(target, cam, k, est, L):
        pt, qt = env.brick_pose(k)
        r = {"seed": seed, "target": target, "cam": cam, "slot": k, "ok": est is not None}
        if est is not None:
            period = np.pi / 2 if abs(L - 0.090) < 1e-6 else np.pi
            r.update(xy_mm=float(np.hypot(*(est["pos"][:2] - pt[:2])) * 1000), z_mm=float((est["pos"][2] - pt[2]) * 1000),
                     yaw_deg=float(np.degrees(fold(est["yaw"] - yaw_of_quat(qt), period))), visible_frac=est["visible_frac"],
                     height_measured=est["height_measured"])
        recs.append(r)

    # ---- supply bricks, arm retracted
    env.reset_piece(seed, 0, arm_q=ex.q_ret)                 # nothing placed; 0.5 s for the supply bricks to settle
    z_top = env.cfg.table_h + H - C.TOP_SINK_M["supply"]
    for cam in SUPPLY_CAMS:
        rgb, dep, cm = grab(cam, 0, -1)
        for i in range(env.n):
            x, y = env.cfg.supply_slots[i]
            record("supply", cam, i, measure(rgb, dep, cm, (x, y), 0.0, env.design[i]["L"], z_top, radius=0.025, yaw_range_deg=14.0), env.design[i]["L"])
    q_keep = d.qpos.copy()
    for i in range(env.n):                                   # R0: wrist camera above the nominal slot (0.10 m above the grasp)
        x, y = env.cfg.supply_slots[i]
        q = ex._solve(np.array([x, y, z_top - H / 2 + ex.dzp + ex.cfg.approach]), down_R(0.0), ex.q_ret, ex.q_ret[0])
        if q is None:
            recs.append({"seed": seed, "target": "supply", "cam": "H0", "slot": i, "ok": False, "why": "ik"})
            continue
        d.qpos[env.arm_qadr] = q
        mujoco.mj_forward(m, d)
        rgb, dep, cm = grab("H0", 1, i)
        record("supply", "H0", i, measure(rgb, dep, cm, (x, y), 0.0, env.design[i]["L"], z_top, radius=0.025, yaw_range_deg=14.0), env.design[i]["L"])
    d.qpos[:] = q_keep
    mujoco.mj_forward(m, d)

    # ---- placed and held bricks during a scripted wall
    prev = {"phase": None, "k": -1}

    def on_step(env_, action, phase, k):
        pp, pk = prev["phase"], prev["k"]
        if pp == "to_wall" and phase != "to_wall":           # hovering 0.10 m above the slot
            s = env.design[pk]
            pt, Rt = env.tcp()
            pb = pt + Rt @ np.array([0.0, 0.0, ex.dzp - C.HELD_DZ_M])
            yaw = float(np.arctan2(Rt[1, 0], Rt[0, 0]))
            for cam in WALL_CAMS + ("H0",):
                rgb, dep, cm = grab(cam, 2, pk)
                record("held", cam, pk, measure(rgb, dep, cm, pb[:2], yaw, s["L"], pb[2] + H / 2, radius=0.03, yaw_range_deg=10.5), s["L"])
        if pp == "to_retract" and phase != "to_retract":     # brick pk placed, arm back at the retract pose
            s = env.design[pk]
            top = lambda o: o["z"] + H / 2 - C.TOP_SINK_M[o["course"]]
            others = [(o["x"], o["y"], o["yaw"], o["L"], top(o)) for j, o in enumerate(env.design) if j < pk]
            for cam in WALL_CAMS:
                rgb, dep, cm = grab(cam, 3, pk)
                record("placed", cam, pk, measure(rgb, dep, cm, (s["x"], s["y"]), s["yaw"], s["L"], top(s), radius=0.03,
                                                  yaw_range_deg=10.5, others=others), s["L"])
        prev["phase"], prev["k"] = phase, k

    r = ex.run(seed, on_step=on_step)
    env.close()
    return {"seed": seed, "fail": r.get("fail"), "records": recs, "time_s": time.time() - t0}


def stats(rows):
    n = len(rows)
    ok = [r for r in rows if r["ok"]]
    out = {"n": n, "miss_rate": (1 - len(ok) / n) if n else None}
    for key in ("xy_mm", "yaw_deg", "z_mm"):
        v = np.abs([r[key] for r in ok]) if ok else np.array([])
        out[key] = {"median": float(np.median(v)), "p95": float(np.percentile(v, 95)), "max": float(v.max())} if len(v) else None
    return out


def summarize(recs):
    by = {}
    for r in recs:
        by.setdefault((r["target"], r["cam"]), []).append(r)
    cams = {f"{t}/{c}": stats(v) for (t, c), v in sorted(by.items())}
    settings = {}
    for name, (sc, wc) in SETTING_CAMS.items():
        sup, pla = cams.get(f"supply/{sc}"), cams.get(f"placed/{wc}")
        ok = bool(sup and pla and sup["xy_mm"] and pla["xy_mm"] and sup["xy_mm"]["p95"] <= 2.0 and pla["xy_mm"]["p95"] <= 2.0
                  and sup["miss_rate"] <= 0.02 and pla["miss_rate"] <= 0.02)
        settings[name] = {"supply_cam": sc, "wall_cam": wc, "supply": sup, "placed": pla, "held_fixed": cams.get(f"held/{wc}"),
                          "held_wrist": cams.get("held/H0"), "measure_ok": ok}
    return {"by_target_cam": cams, "settings": settings}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--zone", required=True)
    ap.add_argument("--seed0", type=int, required=True)
    ap.add_argument("--n", type=int, required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()
    from prl import config as C
    seeds = C.check_seeds(a.zone, range(a.seed0, a.seed0 + a.n))
    out = Path(a.out)
    if out.exists():
        raise SystemExit(f"{out} 이미 있음: 덮어쓰지 않음")
    out.mkdir(parents=True)
    t0 = time.time()
    res = []
    with Pool(min(a.workers, len(seeds))) as p:
        for r in p.imap_unordered(one_scene, [(s,) for s in seeds]):
            res.append(r)
            print(f"[{len(res):3d}] seed {r['seed']} fail {r['fail']} records {len(r['records'])} {r['time_s']:.0f} s", flush=True)
    res.sort(key=lambda r: r["seed"])
    recs = [x for r in res for x in r["records"]]
    (out / "records.json").write_text(json.dumps(recs, default=float))
    summ = summarize(recs)
    summ["_meta"] = {"seeds": seeds, "zone": a.zone, "script_fails": [r["seed"] for r in res if r["fail"]], "elapsed_s": time.time() - t0,
                     "git_commit": subprocess.check_output(["git", "-C", str(SIM), "rev-parse", "HEAD"], text=True).strip(),
                     "git_dirty": bool(subprocess.check_output(["git", "-C", str(SIM), "status", "--porcelain", "--", "prl", "wall3"], text=True).strip()),
                     "depth_noise": C.DEPTH_NOISE, "env_sha256": C.sha(C.env_dict())}
    (out / "summary.json").write_text(json.dumps(summ, indent=1, default=float, ensure_ascii=False))
    for k, v in summ["by_target_cam"].items():
        xy, yw, zz = v["xy_mm"], v["yaw_deg"], v["z_mm"]
        print(f"{k:14s} n {v['n']:5d} miss {v['miss_rate'] * 100:5.1f} %  xy med {xy['median']:.2f} p95 {xy['p95']:.2f} max {xy['max']:.1f} mm | "
              f"yaw med {yw['median']:.2f} p95 {yw['p95']:.2f} | z med {zz['median']:.2f} p95 {zz['p95']:.2f}" if xy else f"{k:14s} n {v['n']} miss 100 %")


if __name__ == "__main__":
    main()
