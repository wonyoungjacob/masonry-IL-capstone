"""장 단위 시험 (정책 단독): 자리 k보다 앞선 벽돌을 설계 위치에 미리 놓은 장면에서 벽돌 k 한 장만 수행. 16자리 × 장면 수.

정의는 기준_해석_20261112.md 1절. 정책 관측 = 그 세팅의 카메라 영상(원본 1280 × 960을 비율 유지로 줄여 채운 224 × 224) + 관절 6 + 집게
+ 목표 정보 5. 정답 좌표는 채점에만 쓴다. 시행의 끝 = wall3.rollout과 같은 규칙(철수 자세로 돌아와 3스텝 머묾, 또는 17 s) 뒤 2 s 정지.
장당 성공 = 벽돌 k가 자리 k를 채움 + 미리 놓은 벽돌이 모두 제 자리를 채움.

병렬 수(지시 문서 4.2): 먼저 프로세스 1개로 첫 장면을 돌려 RAM · VRAM을 재고
P = min(8, (사용 가능 RAM − 12 GB) ÷ 프로세스당 RAM, (남은 VRAM − 4 GB) ÷ 프로세스당 VRAM). 끝나면 <out>/summary.json.

실행: cd sim && MUJOCO_GL=egl PYTHONPATH=. venv/bin/python -m prl.eval_piece --ckpt <pretrained_model> --zone select --seed0 820000 --n 50 \\
        --out outputs/prl/<이름>
"""
import argparse, json, os, resource, subprocess, sys, time
from pathlib import Path

import numpy as np

SIM = Path(__file__).resolve().parents[1]
LIMIT_S = 17.0


def worker(a):
    import cv2
    cv2.setNumThreads(1)
    import torch
    from eval_policy import load_policy
    from wall3.config import RETRACT_Q
    from wall3.to_lerobot import target_of, TASK
    from prl import config as C
    from prl.env import DryEnv, letterbox
    from prl.spec import piece_record
    policy, pcfg, pre, post = load_policy(a.ckpt, a.device, None, None)
    cams = [k.split(".")[-1] for k in pcfg.input_features if k.startswith("observation.images.")]
    env = DryEnv(fixed_cams=C.final_cams(cams))
    q_ret = np.array(RETRACT_Q)
    dt = env.cfg.ctrl_dt
    n_limit = int(round(LIMIT_S / dt))
    raw = np.empty((C.RAW_H, C.RAW_W, 3), np.uint8)
    out = []
    t_all = time.time()
    for seed in a.seeds:
        for k in range(env.n):
            env.reset_piece(seed, k, arm_q=q_ret)
            start = env.brick_poses()
            policy.reset()
            z0 = env.brick_pose(k)[0][2]
            zmax = z0
            left, still, reason = False, 0, "timeout"
            last = np.r_[q_ret, env.cfg.gripper.open_ctrl]
            t0 = time.time()
            tgt = torch.from_numpy(target_of(env.design[k])).unsqueeze(0)
            while env.t < n_limit:
                obs = {f"observation.images.{c}": torch.from_numpy(letterbox(env.render_raw(c, out=raw))).permute(2, 0, 1).float().div(255.0).unsqueeze(0)
                       for c in cams}
                st = np.r_[env.arm_q(), float(env.data.joint("g_finger_joint").qpos[0])].astype(np.float32)
                obs["observation.state"] = torch.from_numpy(st).unsqueeze(0)
                obs["observation.environment_state"] = tgt
                obs["task"] = [TASK]
                with torch.inference_mode():
                    act = post(policy.select_action(pre(obs))).squeeze(0).detach().cpu().numpy().astype(np.float64)
                env.step(act[:6], float(act[6]))
                last = act
                q = env.arm_q()
                zmax = max(zmax, env.brick_pose(k)[0][2])
                dev = np.abs(q - q_ret).max()
                if dev > 0.3:
                    left = True
                qd = np.abs(env.data.qvel[env.arm_dofadr]).max()
                still = still + 1 if (left and dev < 0.05 and qd < 0.05) else 0
                if still >= 3:
                    reason = "retract"
                    break
            steps = env.t
            for _ in range(int(round(2.0 / dt))):
                env.step(last[:6], float(last[6]))
            rec = piece_record(env, k, start)
            lifted = bool(zmax > z0 + 0.02)
            ok = bool(rec["filled"] and rec["placed_still_filled"])
            kind = None if ok else ("pushed_placed" if rec["filled"] else ("lifted_not_in_slot" if lifted else "not_lifted"))
            out.append({"seed": int(seed), "slot": k, "success": ok, "fail_kind": kind, "end_reason": reason, "lifted": lifted,
                        "max_lift_mm": float((zmax - z0) * 1000), "duration_s": steps * dt, "wall_s": time.time() - t0, **rec})
        print(f"seed {seed}: success {sum(r['success'] for r in out[-16:])}/16 ({time.time() - t_all:.0f} s)", flush=True)
    env.close()
    res = {"trials": out, "cams": cams, "policy_type": pcfg.type, "n_action_steps": pcfg.n_action_steps,
           "rss_peak_gb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1048576,
           "torch_vram_peak_gb": torch.cuda.max_memory_allocated() / 2 ** 30 if a.device == "cuda" else 0.0, "wall_s": time.time() - t_all}
    Path(a.part_out).write_text(json.dumps(res, default=float))


def gpu_used_mib():
    return int(subprocess.check_output(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"], text=True).split()[0])


def gpu_total_mib():
    return int(subprocess.check_output(["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"], text=True).split()[0])


def mem_available_gb():
    for line in open("/proc/meminfo"):
        if line.startswith("MemAvailable"):
            return int(line.split()[1]) / 1048576


def launch(a, seeds, part):
    out = Path(a.out)
    cmd = [sys.executable, "-m", "prl.eval_piece", "--worker", "--ckpt", a.ckpt, "--device", a.device, "--out", a.out,
           "--part-out", str(out / f"part_{part}.json"), "--seeds", *map(str, seeds)]
    f = open(out / f"part_{part}.log", "w")
    return subprocess.Popen(cmd, cwd=SIM, stdout=f, stderr=subprocess.STDOUT, env=dict(os.environ, MUJOCO_GL="egl", PYTHONPATH="."))


def bootstrap_ci(by_scene, n=10000, seed=0):
    """by_scene: (scenes, trials per scene) 0/1. Scene-level bootstrap, percentile 2.5 ~ 97.5 of the success rate."""
    rng = np.random.default_rng(seed)
    m = np.asarray(by_scene, float).mean(1)
    idx = rng.integers(0, len(m), size=(n, len(m)))
    b = m[idx].mean(1)
    return [float(np.percentile(b, 2.5)), float(np.percentile(b, 97.5))]


def summarize(trials, meta):
    seeds = sorted({t["seed"] for t in trials})
    S = np.zeros((len(seeds), 16))
    for t in trials:
        S[seeds.index(t["seed"]), t["slot"]] = t["success"]
    ok = [t for t in trials if t["filled"]]
    xy = np.array([t["xy_err_mm"] for t in ok]) if ok else np.array([np.nan])
    kinds = {}
    for t in trials:
        if not t["success"]:
            kinds[t["fail_kind"]] = kinds.get(t["fail_kind"], 0) + 1
    return {"n_scenes": len(seeds), "trials": len(trials), "success": int(S.sum()), "success_rate": float(S.mean()),
            "success_ci95": bootstrap_ci(S), "success_by_slot": S.mean(0).round(4).tolist(),
            "filled_rate": float(np.mean([t["filled"] for t in trials])), "lifted_rate": float(np.mean([t["lifted"] for t in trials])),
            "timeout_rate": float(np.mean([t["end_reason"] == "timeout" for t in trials])),
            "filled_xy_err_mm": {"n": len(ok), "median": float(np.median(xy)), "p95": float(np.percentile(xy, 95))},
            "filled_within_6mm_rate_of_trials": float(np.sum(xy <= 6.0) / len(trials)) if ok else 0.0,
            "filled_z_err_mm_median": float(np.median([abs(t["z_err_mm"]) for t in ok])) if ok else None,
            "filled_yaw_err_deg_median": float(np.median([abs(t["yaw_err_deg"]) for t in ok])) if ok else None,
            "placed_moved_max_mm_p95": float(np.percentile([t["placed_moved_max_mm"] for t in trials], 95)),
            "fail_kinds": kinds, "duration_s_mean": float(np.mean([t["duration_s"] for t in trials])), "_meta": meta}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--zone", default="select")
    ap.add_argument("--seed0", type=int, default=0)
    ap.add_argument("--n", type=int, default=0)
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--parallel", type=int, default=0, help="0 = from the measured per-process RAM / VRAM")
    ap.add_argument("--worker", action="store_true")
    ap.add_argument("--seeds", type=int, nargs="*", default=None)
    ap.add_argument("--part-out", default=None)
    a = ap.parse_args()
    if a.worker:
        worker(a)
        return
    from prl import config as C
    seeds = C.check_seeds(a.zone, range(a.seed0, a.seed0 + a.n))
    out = Path(a.out)
    if out.exists():
        raise SystemExit(f"{out} 이미 있음: 덮어쓰지 않음")
    out.mkdir(parents=True)
    t0 = time.time()
    # probe: one process, first scene
    vram0 = gpu_used_mib()
    p = launch(a, seeds[:1], "probe")
    vmax = vram0
    while p.poll() is None:
        time.sleep(2)
        vmax = max(vmax, gpu_used_mib())
    if p.returncode != 0:
        raise SystemExit(f"probe failed (rc {p.returncode}), see {out / 'part_probe.log'}")
    probe = json.loads((out / "part_probe.json").read_text())
    rss, vram = probe["rss_peak_gb"], max((vmax - vram0) / 1024, 0.3)
    avail, vfree = mem_available_gb(), (gpu_total_mib() - gpu_used_mib()) / 1024
    P = a.parallel or int(max(1, min(8, (avail - 12.0) // rss, (vfree - 4.0) // vram)))
    rest = seeds[1:]
    P = min(P, len(rest)) if rest else 0
    procs = [launch(a, rest[i::P], i) for i in range(P)]
    vpeak = gpu_used_mib()
    while any(q.poll() is None for q in procs):
        time.sleep(5)
        vpeak = max(vpeak, gpu_used_mib())
    bad = [i for i, q in enumerate(procs) if q.returncode != 0]
    if bad:
        raise SystemExit(f"worker(s) {bad} failed, see {out}/part_*.log (부분 결과는 합치지 않음)")
    trials = list(probe["trials"])
    for i in range(P):
        trials += json.loads((out / f"part_{i}.json").read_text())["trials"]
    trials.sort(key=lambda t: (t["seed"], t["slot"]))
    assert len(trials) == 16 * len(seeds), "missing trials"
    (out / "trials.json").write_text(json.dumps(trials, default=float))
    meta = {"ckpt": a.ckpt, "seeds": [seeds[0], seeds[-1]], "zone": a.zone, "cams": probe["cams"], "policy_type": probe["policy_type"],
            "n_action_steps": probe["n_action_steps"], "limit_s": LIMIT_S, "env_sha256": C.sha(C.env_dict()),
            "git_commit": subprocess.check_output(["git", "-C", str(SIM), "rev-parse", "HEAD"], text=True).strip(),
            "parallel": {"P": P, "rss_per_proc_gb": rss, "vram_per_proc_gb": vram, "ram_available_gb": avail, "vram_free_gb": vfree,
                         "vram_peak_mib": vpeak, "vram_before_mib": vram0},
            "elapsed_s": time.time() - t0, "finished": time.strftime("%F %T")}
    summ = summarize(trials, meta)
    (out / "summary.json").write_text(json.dumps(summ, indent=1, default=float, ensure_ascii=False))
    print(json.dumps({k: v for k, v in summ.items() if k != "_meta"}, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
