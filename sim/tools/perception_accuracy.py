"""RQ4 (2026-10-08): how accurate is the on-board camera brick pose estimate, and do the inspection gates still work
when they read it instead of the simulator's true pose?  Runs on CPU, no policy needed.

  python tools/perception_accuracy.py --spawn 40000:40 --episodes 40000:40 50000:50 --out outputs/rq4/perception_accuracy.json

(a) spawn accuracy: every brick at its initial pose (free, hand at home), estimate vs truth;
(b) expert + G1~G3 episodes on the same layouts as the paper's expert baseline (gate_val40_v2/expert_gate_baseline.py:
    clean single pass expert, reguide / release gate / force / replace), once with the gate reading the simulator pose
    ("sim", the oracle) and once reading the camera ("camera"); completion and the per-measurement audit errors.
The policy runs (ACT / Diffusion + gates, camera) need the checkpoints: tools/rq4_jobs.py prints their commands.
"""
import argparse, json, sys, time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from brick_sim.scene import BrickEnv, blueprint_config
from brick_sim.expert import ScriptedExpert
from brick_sim.grasp_gate import GraspGate, _yaw, _fold, _tilt_deg
from brick_sim.metrics import compute_metrics
from brick_sim.perception import BrickPoseEstimator


def cfg_paper():
    return blueprint_config('mortarB', size_rand=0, pos_rand=.03, supply_yaw_deg=60, valid_supply=True, feasible_supply=True)


def parse_ranges(items):
    out = []
    for it in items:
        a, n = it.split(":")
        out += list(range(int(a), int(a) + int(n)))
    return out


def spawn_accuracy(env, est, seeds):
    rows = []
    for s in seeds:
        env.reset(s); env.settle(5)
        dets = est.detect(force=True)
        for i in range(env.n_bricks):
            p, q = env.brick_pose(i)
            d = est.match(p[:2], dets)
            if d is None:
                rows.append({"seed": s, "brick": i, "matched": False}); continue
            rows.append({"seed": s, "brick": i, "matched": True, "n_dets": len(dets), "full": d["full"],
                         "err_xy_mm": 1000 * float(np.hypot(*(d["pos"][:2] - p[:2]))), "err_z_mm": 1000 * float(d["pos"][2] - p[2]),
                         "err_yaw_deg": float(np.degrees(_fold(d["yaw"] - _yaw(q)))), "err_tilt_deg": d["tilt_deg"] - _tilt_deg(q)})
    return rows


class _P:
    def reset(self):
        pass


def episode(env, seed, source):
    env.reset(seed)
    ex = ScriptedExpert(env, seed=seed, max_retries=0, clean_single_pass=True)
    gate = GraspGate(env, _P(), max_retries=0, recover="reguide", release_gate=True, force=True, replace=True, pose_source=source)
    orig = env.step; busy = [False]

    def step(act):
        if busy[0]:
            return orig(act)
        busy[0] = True
        try:
            a = gate.before_step(np.asarray(act, dtype=np.float32))
            if a is None:
                return
            orig(a); gate.after_step(a)
        finally:
            busy[0] = False
    env.step = step
    t0 = time.time()
    try:
        ex.run_episode()
    finally:
        env.step = orig
    before = env.brick_poses().copy(); env.settle(50)
    M = compute_metrics(env.brick_poses(), env.design, env.brick, env.cfg.wall, poses_before_settle=before)
    S = gate.summary()
    if gate.cam is not None:
        gate.cam.close()
    row = {"seed": seed, "source": source, "full": bool(M["m1_all_success"]), "succ": float(M["m1_success_rate"]),
           "iou": float(M["m8_voxel_iou"]), "exy_mm": float(M["m1_exy_mean_mm"]), "steps": int(env.t), "wall_s": time.time() - t0,
           "corrected": S["release_corrected"], "releases": len(S["release_events"]), "bad": S["bad_releases"],
           "replaced": S["replaced"], "replaced_ok": S["replaced_ok"], "retries": S["gate_retries"],
           "log": [(e["stage"], e.get("why", "")) for e in ex.log if not e["ok"]]}
    if source == "camera":
        row.update({k: v for k, v in S.items() if k.startswith("cam_") and k != "cam_log"})
        row["cam_log"] = S["cam_log"]
    return row


def summarize(rows, key="err_xy_mm"):
    a = np.array([r[key] for r in rows if r.get("matched", True) and key in r], dtype=float)
    a = np.abs(a)
    return {"n": int(len(a)), "mean": float(a.mean()) if len(a) else None, "p95": float(np.percentile(a, 95)) if len(a) else None,
            "max": float(a.max()) if len(a) else None}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spawn", nargs="*", default=["40000:40"], help="seed ranges start:count for the spawn accuracy")
    ap.add_argument("--episodes", nargs="*", default=["40000:40"], help="seed ranges for expert + gate episodes")
    ap.add_argument("--sources", nargs="*", default=["sim", "camera"])
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    env = BrickEnv(cfg_paper())
    res = {"config": vars(a)}
    if a.spawn:
        est = BrickPoseEstimator(env)
        rows = spawn_accuracy(env, est, parse_ranges(a.spawn)); est.close()
        res["spawn"] = {"rows": rows, "matched": sum(r["matched"] for r in rows), "n": len(rows),
                        "xy": summarize(rows), "z": summarize(rows, "err_z_mm"), "yaw": summarize(rows, "err_yaw_deg"),
                        "tilt": summarize(rows, "err_tilt_deg")}
        print(f"spawn: matched {res['spawn']['matched']}/{res['spawn']['n']}  xy mm {res['spawn']['xy']}  z mm {res['spawn']['z']}  "
              f"yaw deg {res['spawn']['yaw']}  tilt deg {res['spawn']['tilt']}", flush=True)
    eps = []
    for s in parse_ranges(a.episodes):
        for src in a.sources:
            r = episode(env, s, src); eps.append(r)
            extra = (f" cam xy p95 {r['cam_err_xy_mm_p95']:.2f} max {r['cam_err_xy_mm_max']:.2f} held p95 {r['cam_err_xy_mm_held_p95']}"
                     f" stats {r['cam_stats']}" if src == "camera" else "")
            print(f"seed {s} {src:6s} full {r['full']} succ {r['succ']:.2f} corrected {r['corrected']}/{r['releases']} bad {r['bad']} "
                  f"replaced {r['replaced_ok']}/{r['replaced']} retries {r['retries']} ({r['wall_s']:.0f}s){extra}", flush=True)
            if a.out:
                Path(a.out).parent.mkdir(parents=True, exist_ok=True)
                Path(a.out + ".partial").write_text(json.dumps({**res, "episodes": eps}, default=float), encoding="utf-8")
    res["episodes"] = eps
    table = {}
    for src in a.sources:
        rs = [r for r in eps if r["source"] == src]
        if not rs:
            continue
        table[src] = {"n": len(rs), "full": sum(r["full"] for r in rs), "bricks_per_ep": 3 * float(np.mean([r["succ"] for r in rs])),
                      "corrected": sum(r["corrected"] for r in rs), "releases": sum(r["releases"] for r in rs),
                      "bad": sum(r["bad"] for r in rs), "replaced_ok": sum(r["replaced_ok"] for r in rs), "replaced": sum(r["replaced"] for r in rs)}
        if src == "camera":
            logs = [e for r in rs for e in r["cam_log"]]
            table[src]["cam"] = {"measurements": len(logs), "xy": summarize(logs), "z": summarize(logs, "err_z_mm"), "yaw": summarize(logs, "err_yaw_deg"),
                                 "held_xy": summarize([e for e in logs if e["held"]]),
                                 "src_counts": {k: sum(e["src"] == k for e in logs) for k in ("camera", "cached_full", "cached", "truth")}}
    res["table"] = table
    print("TABLE:", json.dumps(table, indent=1, default=float))
    if a.out:
        Path(a.out).write_text(json.dumps(res, indent=1, default=float), encoding="utf-8")
        Path(a.out + ".partial").unlink(missing_ok=True)


if __name__ == "__main__":
    main()
