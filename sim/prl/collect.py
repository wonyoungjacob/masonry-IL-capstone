"""건식 환경 시연 수집 (4 · 5단계): 시작값마다 대본으로 벽을 쌓고 매 제어 스텝을 기록, 벽 하나 = 파일 하나.

wall3.collect와 같은 구조. 다른 점: 건식 환경(dry_v1), 카메라는 세팅에 들어가는 것만 한 번에 모두 기록(세팅마다 다시 수집하지 않음),
영상은 원본 1280 × 960을 비율 유지로 줄인 224 × 168(정책 입력 224 × 224의 여백을 뺀 부분)로 저장한다.
영상 배열은 시간 방향 차분(첫 프레임 + 앞 프레임과의 차, uint8 넘침 그대로)으로 압축해 저장한다: load_images로 되돌린다(무손실).
중단된 벽은 저장하지 않는다(임시 파일 → 이름 바꾸기). 같은 출력 폴더가 있으면 멈춘다.

실행: cd sim && MUJOCO_GL=egl PYTHONPATH=. venv/bin/python -m prl.collect --seed0 810000 --n 320 --target-pass 300 \\
        --out outputs/prl/<이름> [--cams G1 H0 ...] [--workers 6]
깨끗한 합격 = 시방 합격(건식) + 완주 + 대본 과부하 해제 0번.
"""
import argparse, json, os, subprocess, time, zipfile
from multiprocessing import Pool
from pathlib import Path

import cv2
import numpy as np

SIM = Path(__file__).resolve().parents[1]
IMG_W, IMG_H = 224, 168


def save_npz(path, arrays, level=1):
    """npz with a chosen deflate level (np.savez_compressed is fixed at 6: several times slower on the image blocks)."""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED, compresslevel=level, allowZip64=True) as zf:
        for k, a in arrays.items():
            with zf.open(k + ".npy", "w", force_zip64=True) as f:
                np.lib.format.write_array(f, np.asanyarray(a), allow_pickle=False)


def delta_encode(a):
    """(T, H, W, 3) uint8 → first frame + differences to the previous frame (uint8 wrap-around), in place. Lossless."""
    for t in range(len(a) - 1, 0, -1):
        np.subtract(a[t], a[t - 1], out=a[t])
    return a


def load_images(z, cam):
    """Frames of one camera from a raw wall file (inverse of delta_encode)."""
    return np.cumsum(z[f"imgd_{cam}"], axis=0, dtype=np.uint8)


class StepLog:
    def __init__(self, env, cams):
        self.env, self.cams = env, list(cams)
        self.rows = {k: [] for k in ("t", "phase", "brick", "state", "action", "closure", "fingers", "ft", "bricks", "tcp", "lock")}
        self.cap = 3200                                     # frames per wall (the script takes about 2,870); grown if needed
        self.n = 0
        self.img = {c: np.empty((self.cap, IMG_H, IMG_W, 3), np.uint8) for c in self.cams}   # preallocated: no per-frame allocation
        self.raw = np.empty((env.model.vis.global_.offheight, env.model.vis.global_.offwidth, 3), np.uint8)

    def __call__(self, env, action, phase, k):
        import mujoco
        from prl.run_script import PHASES
        d = env.data
        self.rows["t"].append(env.t)
        self.rows["phase"].append(PHASES.index(phase))
        self.rows["brick"].append(k)
        q = env.arm_q()
        fl = float(d.joint("g_finger_joint").qpos[0]); fr = float(-d.joint("g_right_outer_knuckle_joint").qpos[0])
        self.rows["state"].append(np.r_[q, fl].astype(np.float32))
        self.rows["action"].append(np.asarray(action, np.float32))
        self.rows["closure"].append(np.float32(0.5 * (fl + fr)))
        self.rows["fingers"].append(np.array([fl, fr], np.float32))
        f, tq = env.wrist_ft()
        self.rows["ft"].append(np.r_[f, tq].astype(np.float32))
        self.rows["bricks"].append(env.brick_poses().astype(np.float32))
        p, R = env.tcp()
        qt = np.zeros(4); mujoco.mju_mat2Quat(qt, R.ravel())
        self.rows["tcp"].append(np.r_[p, qt].astype(np.float32))
        self.rows["lock"].append(env.lock_state())
        if self.n == self.cap:
            self.cap += 800
            self.img = {c: np.concatenate([v, np.empty((800, IMG_H, IMG_W, 3), np.uint8)]) for c, v in self.img.items()}
        for c in self.cams:
            cv2.resize(env.render_raw(c, out=self.raw), (IMG_W, IMG_H), dst=self.img[c][self.n], interpolation=cv2.INTER_AREA)
        self.n += 1

    def arrays(self):
        out = {k: np.asarray(v) for k, v in self.rows.items()}
        for c in self.cams:
            out[f"imgd_{c}"] = delta_encode(self.img[c][:self.n])
        return out


def one_wall(args):
    seed, out_dir, cams = args
    from prl import config as C
    from prl.env import DryEnv
    from prl.expert import DryExpert
    from prl.spec import evaluate_dry, brick_error
    from wall3.collect import sha256
    t0 = time.time()
    env = DryEnv(fixed_cams=C.final_cams(cams))
    ex = DryExpert(env)
    log = StepLog(env, cams)
    r = ex.run(seed, on_step=log)
    t_run = time.time() - t0
    ev = evaluate_dry(env)
    r["eval"] = ev
    r["brick_errors"] = [brick_error(env, i) for i in range(env.n)]
    r["final_brick_poses"] = env.brick_poses().tolist()
    r["design"] = env.design
    r["env_version"] = C.ENV_VERSION
    r["supply_initial"] = [[p.tolist(), float(y)] for p, y in env.supply]
    over = [dict(e, slot=b["slot"]) for b in r["bricks"] for e in b.get("lock_events", []) if e["event"] == "release" and e["reason"] != "open"]
    r["overload_releases"] = len(over)
    r["overload_events"] = over
    r["clean_pass"] = bool(ev["spec_pass"] and not r.get("fail") and not over)
    arr = log.arrays()
    raw = Path(out_dir) / "raw"
    tmp = raw / f".wall_{seed}.tmp.npz"
    save_npz(tmp, arr)
    final = raw / f"wall_{seed}.npz"
    os.replace(tmp, final)
    r["raw_file"] = final.name
    r["raw_sha256"] = sha256(final)
    r["raw_bytes"] = final.stat().st_size
    r["frames"] = int(len(arr["t"]))
    r["cams"] = list(cams)
    r["time_s"] = {"simulate_render": t_run, "total": time.time() - t0}
    (raw / f"wall_{seed}.json").write_text(json.dumps(r, indent=1, default=float, ensure_ascii=False))
    env.close()
    return {"seed": seed, "fail": r.get("fail"), "spec_pass": ev["spec_pass"], "clean_pass": r["clean_pass"],
            "overload_releases": r["overload_releases"], "frames": r["frames"], "raw_bytes": r["raw_bytes"], "time_s": r["time_s"]["total"]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed0", type=int, required=True)
    ap.add_argument("--n", type=int, required=True, help="most seeds to try")
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--target-pass", type=int, default=0, help="stop once this many walls are clean passes (0 = run all --n)")
    ap.add_argument("--cams", nargs="*", default=None, help="cameras to record (default: every camera of the six settings)")
    ap.add_argument("--zone", default="demo")
    ap.add_argument("--min-free-gb", type=float, default=50.0)
    a = ap.parse_args()
    from prl import config as C
    from prl.expert import EXPERT_VERSION
    from prl.run_script import PHASES
    from wall3.expert import expert_config
    seeds = C.check_seeds(a.zone, range(a.seed0, a.seed0 + a.n))
    cams = a.cams or C.load_settings()["cameras_used"]
    out = Path(a.out)
    if out.exists():
        raise SystemExit(f"{out} 이미 있음: 덮어쓰지 않음")
    (out / "raw").mkdir(parents=True)
    env_d = C.env_dict()
    cam_d = {"final_fixed": C.final_cams(cams), "wrist": {c: C.WRIST_CAMS[c] for c in cams if c in C.WRIST_CAMS},
             "raw": [C.RAW_W, C.RAW_H], "stored": [IMG_W, IMG_H], "resize": "cv2.INTER_AREA"}
    meta = {"git_commit": subprocess.check_output(["git", "-C", str(SIM), "rev-parse", "HEAD"], text=True).strip(),
            "git_dirty": bool(subprocess.check_output(["git", "-C", str(SIM), "status", "--porcelain", "--", "prl", "wall3"], text=True).strip()),
            "env": env_d, "env_sha256": C.sha(env_d), "cams": cams, "cam_config": cam_d, "cams_sha256": C.sha(cam_d),
            "expert_version": EXPERT_VERSION, "expert": expert_config(EXPERT_VERSION).to_dict(),
            "seeds": seeds, "phases": PHASES, "args": vars(a), "started": time.strftime("%Y-%m-%d %H:%M:%S")}
    (out / "collect_config.json").write_text(json.dumps(meta, indent=1, default=float, ensure_ascii=False))
    t0 = time.time()
    res, stop = [], None
    with Pool(a.workers, maxtasksperchild=4) as p:
        pending, nxt = [], 0
        while True:
            while nxt < len(seeds) and len(pending) < a.workers and stop is None and (
                    not a.target_pass or sum(r["clean_pass"] for r in res) + len(pending) < a.target_pass):
                pending.append(p.apply_async(one_wall, ((seeds[nxt], str(out), cams),)))
                nxt += 1
            if not pending:
                break
            done = [x for x in pending if x.ready()]
            if not done:
                time.sleep(0.5)
                continue
            for x in done:
                pending.remove(x)
                r = x.get()
                res.append(r)
                print(f"[{len(res):4d}] seed {r['seed']} fail {r['fail']} spec {r['spec_pass']} clean {r['clean_pass']} frames {r['frames']} "
                      f"raw {r['raw_bytes'] / 1e6:.0f} MB {r['time_s']:.0f} s (clean {sum(q['clean_pass'] for q in res)}, "
                      f"elapsed {time.time() - t0:.0f} s)", flush=True)
            free = os.statvfs(out).f_bavail * os.statvfs(out).f_frsize / 1e9
            if stop is None and free < a.min_free_gb:
                stop = f"남은 디스크 {free:.0f} GB < {a.min_free_gb:.0f} GB"
                print(f"STOP: {stop}", flush=True)
    res.sort(key=lambda r: r["seed"])
    summ = {"n": len(res), "n_pass": sum(r["spec_pass"] for r in res), "n_clean_pass": sum(r["clean_pass"] for r in res),
            "n_fail_run": sum(bool(r["fail"]) for r in res), "stopped": stop,
            "seeds_attempted": [res[0]["seed"], res[-1]["seed"]] if res else None, "raw_bytes": int(sum(r["raw_bytes"] for r in res)),
            "frames": int(sum(r["frames"] for r in res)), "elapsed_s": time.time() - t0, "workers": a.workers,
            "target_pass": a.target_pass, "walls": res, "finished": time.strftime("%Y-%m-%d %H:%M:%S")}
    (out / "collect_summary.json").write_text(json.dumps(summ, indent=1, default=float, ensure_ascii=False))
    print(f"done: {summ['n_pass']}/{summ['n']} spec pass, {summ['n_clean_pass']} clean, {summ['n_fail_run']} aborted, "
          f"{summ['raw_bytes'] / 1e9:.1f} GB, {summ['elapsed_s']:.0f} s" + (f", STOPPED: {stop}" if stop else ""))
    if stop:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
