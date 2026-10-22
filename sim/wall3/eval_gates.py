"""검측 예비 평가 (2026-10-22, 결과 아님 · 문턱 임시값): 정책 × 조건(검측 없음 / G1·G2·G3 모두) × 100벽.

평가 환경 main_v1_eval(모르타르가 벽 하나 쌓는 동안 굳지 않음), 시작값은 파일럿 블록 미사용 700300 ~ 700399(검증 720000번대 ·
시험 730000번대는 쓰지 않음). 벽마다 rollout.py와 같은 규칙(도면 순서, 철수 또는 정책 시간 17 s, 검측 동작 시간은 제한에 안 넣음).
(정책, 조건)마다 시작값을 묶음으로 나눠 동시에 돌리고, 끝나면 하나로 모아 요약한다.

실행: cd sim && venv/bin/python -m wall3.eval_gates --out outputs/wall3/eval_gates_<날짜> [--parallel 8] [--chunks 4]
"""
import argparse, json, subprocess, sys, time
from pathlib import Path

import numpy as np

SIM = Path(__file__).resolve().parents[1]
CKPT = {"act": "outputs/wall3/main_train_20261019/act_s1000/checkpoints/last/pretrained_model",
        "diffusion": "outputs/wall3/main_train_20261019/diffusion_s1000/checkpoints/last/pretrained_model"}
COND = {"none": [], "all": ["--g1", "--g2", "--g3"]}


def summarize(walls):
    br = [b for w in walls for b in w["bricks"]]
    n = len(walls)
    filled = np.array([w["eval"]["slots_filled"] for w in walls], float)            # (walls, 16)
    lifted = np.array([[b["grasped_lifted"] for b in w["bricks"]] for w in walls], float)
    errs = [b["final_xy_err_mm"] for w in walls for b in w["bricks"] if w["eval"]["slots_filled"][b["slot"]]]
    g = [b.get("gates") for b in br if b.get("gates")]
    out = {"walls": n, "spec_pass": int(sum(w["eval"]["spec_pass"] for w in walls)),
           "slots_filled_mean": float(filled.sum(1).mean()), "iou_mean": float(np.mean([w["eval"]["iou_mean"] for w in walls])),
           "filled_rate_by_slot": filled.mean(0).round(3).tolist(), "lifted_rate_by_slot": lifted.mean(0).round(3).tolist(),
           "filled_err_mm": {"n": len(errs), "median": float(np.median(errs)) if errs else None,
                             "p90": float(np.percentile(errs, 90)) if errs else None},
           "policy_time_s_per_brick": float(np.mean([b.get("policy_time_s", b["duration_s"]) for b in br])),
           "gate_time_s_per_brick": float(np.mean([b.get("gate_time_s", 0.0) for b in br])),
           "wall_clock_s_per_wall": float(np.mean([w["wall_clock_s"] for w in walls]))}
    if g:
        g1 = [e for x in g for e in x["g1"] if "grasped" in e]
        g2 = [e for x in g for e in x["g2"] if not e.get("release_here")]
        g3 = [e for x in g for e in x["g3"]]
        rep = [e["replace"] for e in g3 if isinstance(e.get("replace"), dict)]
        out["gates"] = {
            "g1_checks": len(g1), "g1_grasped": sum(e["grasped"] for e in g1),
            "g1_grasped_but_target_not_lifted": sum(e["grasped"] and (e.get("audit_target_rise_mm") or 0) < 10 for e in g1),
            "g2_releases": len(g2), "g2_in_hand_by_camera": sum(e.get("in_hand_src") == "camera" for e in g2),
            "g2_in_hand_err_mm_median": float(np.median([e["audit_in_hand_err_mm"] for e in g2 if e.get("audit_in_hand_err_mm") is not None]))
            if any(e.get("audit_in_hand_err_mm") is not None for e in g2) else None,
            "g3_inspections": len(g3), "g3_seen": sum(e.get("seen", False) for e in g3), "g3_bad": sum(e.get("bad", False) for e in g3),
            "g3_replaced": len(rep), "g3_meas_err_mm_median": float(np.median([e["audit_meas_err_mm"] for e in g3 if "audit_meas_err_mm" in e]))
            if any("audit_meas_err_mm" in e for e in g3) else None,
            "g3_replace_after_mm_median": float(np.median([r["audit_after_mm"] for r in rep if "audit_after_mm" in r])) if rep else None}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--seed0", type=int, default=700300)
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--policies", nargs="+", default=["act", "diffusion"])
    ap.add_argument("--conditions", nargs="+", default=["none", "all"])
    ap.add_argument("--chunks", type=int, default=4)
    ap.add_argument("--parallel", type=int, default=8)
    ap.add_argument("--env-version", default="main_v1_eval")
    a = ap.parse_args()
    out = Path(a.out)
    if out.exists():
        raise SystemExit(f"{out} 이미 있음")
    out.mkdir(parents=True)
    seeds = list(range(a.seed0, a.seed0 + a.n))
    jobs = []
    for pol in a.policies:
        for cond in a.conditions:
            for ci, part in enumerate(np.array_split(seeds, a.chunks)):
                d = out / f"{pol}_{cond}_part{ci}"
                cmd = [sys.executable, "-m", "wall3.rollout", "--ckpt", CKPT[pol], "--env-version", a.env_version,
                       "--seeds", *map(str, part), "--out", str(d)] + COND[cond] + (["--record-first"] if ci == 0 else [])
                jobs.append((pol, cond, ci, d, cmd))
    (out / "plan.json").write_text(json.dumps({"seeds": [seeds[0], seeds[-1]], "env_version": a.env_version, "ckpt": CKPT,
                                               "conditions": COND, "jobs": [[p, c, i, str(d)] for p, c, i, d, _ in jobs],
                                               "started": time.strftime("%Y-%m-%d %H:%M:%S"),
                                               "git_commit": subprocess.check_output(["git", "-C", str(SIM), "rev-parse", "HEAD"], text=True).strip()},
                                              indent=1))
    running, pending, done = [], list(jobs), []
    t0 = time.time()
    while pending or running:
        while pending and len(running) < a.parallel:
            j = pending.pop(0)
            log = open(f"{j[3]}.log", "w")
            running.append((j, subprocess.Popen(j[4], cwd=SIM, stdout=log, stderr=subprocess.STDOUT), log))
        time.sleep(5)
        for item in list(running):
            j, p, log = item
            if p.poll() is not None:
                running.remove(item); log.close(); done.append((j, p.returncode))
                print(time.strftime("[%H:%M:%S]"), f"{j[0]} {j[1]} part{j[2]} exit {p.returncode} ({len(done)}/{len(jobs)}, {time.time() - t0:.0f} s)", flush=True)
    summ = {}
    for pol in a.policies:
        for cond in a.conditions:
            walls = []
            for d in sorted(out.glob(f"{pol}_{cond}_part*")):
                if d.is_dir() and (d / "rollout.json").exists():
                    walls += json.loads((d / "rollout.json").read_text())["walls"]
            walls.sort(key=lambda w: w["seed"])
            summ[f"{pol}_{cond}"] = summarize(walls) if walls else None
    summ["_meta"] = {"failed_jobs": [[j[0], j[1], j[2], rc] for j, rc in done if rc != 0], "elapsed_s": time.time() - t0,
                     "finished": time.strftime("%Y-%m-%d %H:%M:%S")}
    (out / "summary.json").write_text(json.dumps(summ, indent=1, default=float))
    print(json.dumps({k: ({kk: v[kk] for kk in ("walls", "spec_pass", "slots_filled_mean", "iou_mean")} if isinstance(v, dict) and "walls" in v else v)
                      for k, v in summ.items()}, indent=1, default=float))


if __name__ == "__main__":
    main()
