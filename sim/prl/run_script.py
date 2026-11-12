"""대본(정답 좌표)으로 건식 벽 쌓기: 통과 확인(1단계), 기하 선별용 궤적(2단계). 영상은 그리지 않는다(GPU를 쓰지 않음).

벽 단위(기본) 또는 장 단위(--piece: 16자리 × 장면). 벽마다 json 하나, --save-traj면 매 제어 스텝의 qpos를 npz로 남긴다
(카메라 후보를 나중에 재생하면서 그리기 위함). 같은 출력 폴더가 있으면 멈춘다. 부분 결과는 요약하지 않는다.

실행: cd sim && PYTHONPATH=. venv/bin/python -m prl.run_script --zone script --seed0 800100 --n 50 --out outputs/prl/<이름>
"""
import argparse, json, os, subprocess, time
from multiprocessing import Pool
from pathlib import Path

import numpy as np

SIM = Path(__file__).resolve().parents[1]
PHASES = ["to_supply", "grasp_descend", "grasp_close", "grasp_lift", "to_wall", "wait_bed", "place_align", "place_descend",
          "place_servo", "place_lower", "place_unload", "place_open", "retreat", "to_retract", "settle"]


class TrajLog:
    def __init__(self):
        self.rows = {k: [] for k in ("t", "phase", "brick", "qpos", "action")}

    def __call__(self, env, action, phase, k):
        self.rows["t"].append(env.t)
        self.rows["phase"].append(PHASES.index(phase))
        self.rows["brick"].append(k)
        self.rows["qpos"].append(env.data.qpos.astype(np.float64).copy())
        self.rows["action"].append(np.asarray(action, np.float32))

    def arrays(self):
        return {k: np.asarray(v) for k, v in self.rows.items()}


def one(args):
    seed, out_dir, save_traj, piece = args
    from prl.env import DryEnv
    from prl.expert import DryExpert
    from prl.spec import evaluate_dry, brick_error, piece_record
    t0 = time.time()
    env = DryEnv(fixed_cams={})
    ex = DryExpert(env)
    out = Path(out_dir)
    if piece:
        trials = []
        for k in range(env.n):
            env.reset_piece(seed, k, arm_q=ex.q_ret)          # run_piece resets again: this is only to read the start poses
            start = env.brick_poses()
            r = ex.run_piece(seed, k)
            rec = piece_record(env, k, start)
            b = r["bricks"][0]
            trials.append({"slot": k, "fail": r.get("fail"), "duration_s": b.get("duration_s"), **rec})
        res = {"seed": seed, "trials": trials, "time_s": time.time() - t0}
        (out / "raw" / f"piece_{seed}.json").write_text(json.dumps(res, indent=1, default=float))
        env.close()
        return {"seed": seed, "filled": [t["filled"] for t in trials], "fails": [t["fail"]["reason"] if t["fail"] else None for t in trials],
                "xy_err_mm": [t["xy_err_mm"] for t in trials], "time_s": res["time_s"]}
    log = TrajLog() if save_traj else None
    r = ex.run(seed, on_step=log)
    ev = evaluate_dry(env)
    r["eval"] = ev
    r["brick_errors"] = [brick_error(env, i) for i in range(env.n)]
    r["final_brick_poses"] = env.brick_poses().tolist()
    r["supply_initial"] = [[p.tolist(), float(y)] for p, y in env.supply]
    over = [dict(e, slot=b["slot"]) for b in r["bricks"] for e in b.get("lock_events", []) if e["event"] == "release" and e["reason"] != "open"]
    r["overload_releases"] = len(over)
    r["clean_pass"] = bool(ev["spec_pass"] and not r.get("fail") and not over)
    r["time_s"] = time.time() - t0
    if log is not None:
        tmp = out / "raw" / f".traj_{seed}.tmp.npz"
        np.savez_compressed(tmp, **log.arrays())
        os.replace(tmp, out / "raw" / f"traj_{seed}.npz")
    (out / "raw" / f"wall_{seed}.json").write_text(json.dumps(r, indent=1, default=float, ensure_ascii=False))
    env.close()
    items = {k: ev[k]["pass"] for k in ("2_line_plane", "3_plumb", "4_position", "5_thickness")}
    return {"seed": seed, "fail": r.get("fail"), "spec_pass": ev["spec_pass"], "exists": ev["exists"], "items": items,
            "values_mm": {"2": ev["2_line_plane"]["value_mm"], "3": ev["3_plumb"]["value_mm"], "4": ev["4_position"]["value_mm"]},
            "clean_pass": r["clean_pass"], "overload_releases": len(over), "steps": r["steps"], "time_s": r["time_s"]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--zone", required=True, help="prl.config.SEED_ZONES key")
    ap.add_argument("--seed0", type=int, required=True)
    ap.add_argument("--n", type=int, required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--save-traj", action="store_true")
    ap.add_argument("--piece", action="store_true", help="brick-level trials (16 slots per seed)")
    a = ap.parse_args()
    from prl import config as C
    from wall3.expert import expert_config
    from prl.expert import EXPERT_VERSION
    seeds = C.check_seeds(a.zone, range(a.seed0, a.seed0 + a.n))
    out = Path(a.out)
    if out.exists():
        raise SystemExit(f"{out} 이미 있음: 덮어쓰지 않음")
    (out / "raw").mkdir(parents=True)
    env_d = C.env_dict()
    meta = {"git_commit": subprocess.check_output(["git", "-C", str(SIM), "rev-parse", "HEAD"], text=True).strip(),
            "git_dirty_prl": bool(subprocess.check_output(["git", "-C", str(SIM), "status", "--porcelain", "--", "prl", "wall3"], text=True).strip()),
            "env": env_d, "env_sha256": C.sha(env_d), "expert_version": EXPERT_VERSION,
            "expert": expert_config(EXPERT_VERSION).to_dict(), "seeds": seeds, "phases": PHASES, "args": vars(a),
            "started": time.strftime("%Y-%m-%d %H:%M:%S")}
    (out / "config.json").write_text(json.dumps(meta, indent=1, default=float, ensure_ascii=False))
    t0 = time.time()
    res = []
    with Pool(a.workers) as p:
        for r in p.imap_unordered(one, [(s, str(out), a.save_traj, a.piece) for s in seeds]):
            res.append(r)
            if a.piece:
                print(f"[{len(res):3d}] seed {r['seed']} filled {sum(r['filled'])}/16 fails {[f for f in r['fails'] if f]} {r['time_s']:.0f} s", flush=True)
            else:
                print(f"[{len(res):3d}] seed {r['seed']} fail {r['fail']} spec {r['spec_pass']} items {r['items']} "
                      f"values {{{', '.join(f'{k}: {v:.2f}' for k, v in r['values_mm'].items())}}} {r['time_s']:.0f} s", flush=True)
    res.sort(key=lambda r: r["seed"])
    if a.piece:
        filled = np.array([r["filled"] for r in res], float)
        summ = {"n_scenes": len(res), "trials": int(filled.size), "filled": int(filled.sum()), "filled_rate": float(filled.mean()),
                "filled_rate_by_slot": filled.mean(0).round(4).tolist(),
                "xy_err_mm_median": float(np.median([e for r in res for e, f in zip(r["xy_err_mm"], r["filled"]) if f] or [np.nan])),
                "fails": sorted({f for r in res for f in r["fails"] if f})}
    else:
        summ = {"n": len(res), "n_pass": sum(r["spec_pass"] for r in res), "n_clean_pass": sum(r["clean_pass"] for r in res),
                "n_fail_run": sum(bool(r["fail"]) for r in res), "n_exists": sum(r["exists"] for r in res),
                "item_fail": {k: sum(not r["items"][k] for r in res) for k in ("2_line_plane", "3_plumb", "4_position", "5_thickness")},
                "fail_reasons": sorted({r["fail"]["reason"] for r in res if r["fail"]})}
    summ.update(elapsed_s=time.time() - t0, workers=a.workers, walls=res, finished=time.strftime("%Y-%m-%d %H:%M:%S"),
                env_sha256=meta["env_sha256"])
    (out / "summary.json").write_text(json.dumps(summ, indent=1, default=float, ensure_ascii=False))
    print(json.dumps({k: v for k, v in summ.items() if k != "walls"}, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
