"""2차 측정 (기준_해석_능동카메라_20261113.md 6절). 측정기(prl.perception)는 1차에서 고정한 그대로 쓴다.

장면마다 대본으로 벽을 쌓으면서:
  놓인 벽돌 / 손목 H0     벽돌 k를 놓고 후퇴(retreat)가 끝난 때(놓은 자리 위 0.10 m, 집게 열림)에 벽돌 k를 잰다. → 필수 조건 5
  공급대 벽돌 / 능동 카메라  초기화 뒤 팔이 철수 자세일 때, 카메라가 벽돌마다 겨냥하고 멈춘 뒤 잰다. → 참고
  놓인 벽돌 / 능동 카메라   팔이 철수 자세로 돌아온 때, 카메라가 자리 k를 겨냥하고 멈춘 뒤 잰다. → 참고
능동 카메라의 자세는 인코더 값으로 계산해 측정기에 준다: none(실제 각), precise(분해능 0.013°로 반올림), servo(0.088°로 반올림 + 축마다 ± 0.125° 균등).
공급대 벽돌 / 손목 H0(필수 조건 4)는 1차의 값을 그대로 쓰므로 여기서 다시 재지 않는다.

실행: cd sim && MUJOCO_GL=egl PYTHONPATH=. venv/bin/python -m prl.measure_active --settings prl/active_settings_20261113.json \\
        --zone select --seed0 820000 --n 100 --out outputs/prl/<이름> [--workers 16]
"""
import argparse, json, subprocess, time
from multiprocessing import Pool
from pathlib import Path

import numpy as np

from prl.measure import fold, stats

SIM = Path(__file__).resolve().parents[1]
CLASSES = {"none": dict(res_deg=0.0, backlash_deg=0.0), "precise": dict(res_deg=0.013, backlash_deg=0.0),
           "servo": dict(res_deg=0.088, backlash_deg=0.25)}


def angle_error(q, klass, rng):
    """Error (rad) of the angles a user of the encoders would read: quantised to the resolution, plus a uniform backlash term."""
    c = CLASSES[klass]
    dq = np.zeros(2)
    if c["res_deg"] > 0:
        r = np.radians(c["res_deg"])
        dq = np.round(q / r) * r - q
    if c["backlash_deg"] > 0:
        dq = dq + rng.uniform(-0.5, 0.5, 2) * np.radians(c["backlash_deg"])
    return dq


def one_scene(args):
    seed, cams, spec_d = args
    import cv2
    cv2.setNumThreads(1)
    from wall3.config import H
    from wall3.poses import yaw_of_quat
    from prl import config as C
    from prl.active_cam import ActiveRig, PanTiltSpec, rig_specs
    from prl.env import DryEnv, noisy_depth
    from prl.expert import DryExpert
    from prl.perception import Camera, measure
    t0 = time.time()
    spec = PanTiltSpec(**spec_d) if spec_d else PanTiltSpec()
    env = DryEnv(fixed_cams={}, extra_cams=rig_specs(cams, spec))
    ex = DryExpert(env)
    rig = ActiveRig(env, cams, ex.q_ret, spec)
    names = list(cams)
    cam_idx = {n: i for i, n in enumerate(names + ["H0"])}
    sup_cams = [n for n in names if cams[n]["role"] in ("lead", "pick")]
    wall_cams = [n for n in names if cams[n]["role"] in ("lead", "slot")]
    recs = []

    def images(name, tag, k):
        kind = "d405" if name == "H0" else spec.kind
        fovy = env.cam_fovy["H0"] if name == "H0" else spec.fovy
        rng = np.random.default_rng([seed, cam_idx[name], tag, k + 1])
        rgb = env.render_raw(name)
        dep = noisy_depth(env.render_raw(name, depth=True), fovy, kind, rng)
        return rgb, dep, fovy, kind, rng

    def record(target, cam, klass, k, est, L, extra=None):
        pt, qt = env.brick_pose(k)                                   # 참값 (진단): 오차 계산에만 쓴다
        r = {"seed": seed, "target": target, "cam": cam, "klass": klass, "slot": k, "ok": est is not None}
        if est is not None:
            period = np.pi / 2 if abs(L - 0.090) < 1e-6 else np.pi
            r.update(xy_mm=float(np.hypot(*(est["pos"][:2] - pt[:2])) * 1000), z_mm=float((est["pos"][2] - pt[2]) * 1000),
                     yaw_deg=float(np.degrees(fold(est["yaw"] - yaw_of_quat(qt), period))), visible_frac=est["visible_frac"])
        r.update(extra or {})
        recs.append(r)

    def active(target, cam, tag, k, point, prior_xy, prior_yaw, L, z_top, radius, yaw_range, others=()):
        """Aim, dwell, take one image pair, and run the estimator once per pose-knowledge class."""
        reach = rig.aim(cam, point)
        rgb, dep, fovy, kind, rng = images(cam, tag, k)
        u = rig.unit[cam]
        for klass in CLASSES:
            p, R = u.pose(dq=angle_error(u.q, klass, rng))
            cm = Camera(fovy, R, p, C.RAW_W, C.RAW_H, sigma_fn=lambda z: C.depth_sigma(z, fovy, kind))
            est = measure(rgb, dep, cm, prior_xy, prior_yaw, L, z_top, radius=radius, yaw_range_deg=yaw_range, others=others)
            record(target, cam, klass, k, est, L, {"in_limits": bool(reach)})

    top = lambda o: o["z"] + H / 2 - C.TOP_SINK_M[o["course"]]

    # ---- supply bricks from the active cameras, arm retracted
    env.reset_piece(seed, 0, arm_q=ex.q_ret)
    z_top = env.cfg.table_h + H - C.TOP_SINK_M["supply"]
    for cam in sup_cams:
        for i in range(env.n):
            x, y = env.cfg.supply_slots[i]
            active("supply", cam, 0, i, rig.task.supply[i], (x, y), 0.0, env.design[i]["L"], z_top, 0.025, 14.0)

    # ---- placed bricks during a scripted wall
    prev = {"phase": None, "k": -1}

    def on_step(env_, action, phase, k):
        pp, pk = prev["phase"], prev["k"]
        if pp in ("retreat", "to_retract") and phase != pp:
            s = env.design[pk]
            others = [(o["x"], o["y"], o["yaw"], o["L"], top(o)) for j, o in enumerate(env.design) if j < pk]
            if pp == "retreat":                                   # wrist camera 0.10 m above the brick just released
                rgb, dep, fovy, kind, _ = images("H0", 4, pk)
                p, R = env.cam_pose("H0")
                cm = Camera(fovy, R, p, C.RAW_W, C.RAW_H, sigma_fn=lambda z: C.depth_sigma(z, fovy, kind))
                record("placed", "H0", "arm", pk, measure(rgb, dep, cm, (s["x"], s["y"]), s["yaw"], s["L"], top(s), radius=0.03,
                                                          yaw_range_deg=10.5, others=others), s["L"])
            else:                                                 # arm back at the retract pose: the active cameras look at slot pk
                for cam in wall_cams:
                    active("placed", cam, 3, pk, rig.task.slot[pk], (s["x"], s["y"]), s["yaw"], s["L"], top(s), 0.03, 10.5, others)
        prev["phase"], prev["k"] = phase, k

    r = ex.run(seed, on_step=on_step)
    env.close()
    return {"seed": seed, "fail": r.get("fail"), "records": recs, "time_s": time.time() - t0}


def summarize(recs):
    by = {}
    for r in recs:
        by.setdefault((r["target"], r["cam"], r["klass"]), []).append(r)
    out = {}
    for (t, c, k), v in sorted(by.items()):
        s = stats(v)
        miss = sorted({r["slot"] for r in v if not r["ok"]})
        s["miss_slots"] = {str(i): sum(1 for r in v if not r["ok"] and r["slot"] == i) for i in miss}
        s["ok_2mm_2pct"] = bool(s["xy_mm"] and s["xy_mm"]["p95"] <= 2.0 and s["miss_rate"] <= 0.02)
        out[f"{t}/{c}/{k}"] = s
    return out


def main():
    from prl import config as C
    ap = argparse.ArgumentParser()
    ap.add_argument("--settings", required=True, help="active settings json (prl.select_active pick)")
    ap.add_argument("--zone", required=True)
    ap.add_argument("--seed0", type=int, required=True)
    ap.add_argument("--n", type=int, required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=16)
    a = ap.parse_args()
    out = Path(a.out)
    if out.exists():
        raise SystemExit(f"{out} 이미 있음: 덮어쓰지 않음")
    S = json.loads(Path(a.settings).read_text())
    cams, role_of = {}, {}
    for s, cs in S["settings"].items():                           # one camera per (mount, measuring duty)
        for cn, c in cs.items():
            name = c["mount"]
            duty = {"lead": {"supply", "wall"}, "pick": {"supply"}, "slot": {"wall"}}[c["role"]]
            role_of.setdefault(name, set()).update(duty)
            cams[name] = {"base": c["base"], "pan0": c["pan0"]}
    for n, d in role_of.items():
        cams[n]["role"] = "lead" if d == {"supply", "wall"} else ("pick" if d == {"supply"} else "slot")
    seeds = C.check_seeds(a.zone, range(a.seed0, a.seed0 + a.n))
    out.mkdir(parents=True)
    git = subprocess.run(["git", "rev-parse", "HEAD"], cwd=SIM, capture_output=True, text=True).stdout.strip()
    dirty = bool(subprocess.run(["git", "status", "--porcelain", "--", "prl", "wall3"], cwd=SIM, capture_output=True, text=True).stdout.strip())
    t0 = time.time()
    with Pool(min(a.workers, len(seeds))) as p:
        res = p.map(one_scene, [(s, cams, S.get("spec")) for s in seeds], chunksize=1)
    recs = [r for x in res for r in x["records"]]
    meta = {"seeds": [seeds[0], seeds[-1]], "zone": a.zone, "cams": cams, "classes": CLASSES, "spec": S.get("spec"),
            "script_fails": [x["seed"] for x in res if x["fail"]], "elapsed_s": time.time() - t0, "git_commit": git, "git_dirty": dirty,
            "env_sha256": C.sha(C.env_dict()), "depth_noise": C.DEPTH_NOISE, "finished": time.strftime("%F %T")}
    (out / "records.json").write_text(json.dumps(recs))
    (out / "summary.json").write_text(json.dumps({"by_target_cam_class": summarize(recs), "_meta": meta}, indent=1, ensure_ascii=False))
    print(json.dumps({k: {"n": v["n"], "miss": v["miss_rate"], "xy_p95": v["xy_mm"]["p95"] if v["xy_mm"] else None}
                      for k, v in summarize(recs).items()}, indent=1))


if __name__ == "__main__":
    main()
