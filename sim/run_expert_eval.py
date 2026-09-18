"""Run the scripted IK expert for N seeds in a given mortar mode and print/save the 8-metric scorecard.

Usage: python run_expert_eval.py --mortar dry --courses 3 --per-course 3 --seeds 3 [--noise 0.0]
"""
import argparse, json, sys, time
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from brick_sim.scene import BrickEnv, SceneConfig, WallSpec, blueprint_config
from brick_sim.expert import ScriptedExpert
from brick_sim.metrics import compute_metrics, compute_metrics3

KEYS = ["m1_success_rate", "m1_exy_mean_mm", "m1_exy_max_mm", "m1_ez_mean_mm", "m1_eyaw_mean_deg", "m1_exy_by_course_mm",
        "m2_level_range_max_mm", "m3_plumb_mm", "m3_max_tilt_deg", "m4_straightness_max_mm", "m4_bow_mm",
        "m5_head_gap_mean_mm", "m5_head_gap_dev_from_nominal_mm", "m5_bed_gap_mean_mm", "m6_min_overlap_mm",
        "m6_through_joints", "m7_fallen_count", "m7_settle_drift_max_mm", "m8_voxel_iou", "m_pass"]


def run(cfg, seed, noise=0.0, verbose=True):
    env = BrickEnv(cfg); env.reset(seed)
    ex = ScriptedExpert(env, noise_std=noise, seed=seed)
    errs = []
    nfail = ex.run_episode(lambda o, a, i: errs.append(i["ik_pos_err"]))
    before = env.brick_poses().copy(); env.settle(50)
    M = compute_metrics(env.brick_poses(), env.design, env.brick, cfg.wall, poses_before_settle=before)
    M["ik_fail_steps"] = nfail; M["ik_err_mean_mm"] = float(np.mean(errs) * 1000); M["ik_err_max_mm"] = float(np.max(errs) * 1000)
    M["steps"] = env.t; M["n_bricks"] = env.n_bricks; M["cured"] = env.cured.tolist()
    if cfg.layout == "2p1":
        M3 = compute_metrics3(env.brick_poses(), env.design, env.brick, cfg.wall)
        M.update({"bp_iou": M3["iou"], "bp_E_h_mm": M3["E_h_mm"], "bp_E_f_mm": M3["E_f_mm"]})
    if verbose:
        print(f"[{cfg.mortar:8s} seed={seed}] n={env.n_bricks} steps={env.t} ikfail={nfail} ik_mean={M['ik_err_mean_mm']:.2f}mm ik_max={M['ik_err_max_mm']:.1f}mm")
        for k in KEYS:
            v = M[k]
            if isinstance(v, float): v = round(v, 2)
            if isinstance(v, list): v = [round(x, 2) for x in v]
            print(f"   {k:34s} {v}")
        if cfg.mortar == "mortarB": print("   cured:", env.cured.tolist())
        if cfg.layout == "2p1": print(f"   [blueprint 4.9] IoU={M['bp_iou']:.3f}  E_h={M['bp_E_h_mm']:.2f} mm  E_f={M['bp_E_f_mm']:.2f} mm")
    return M


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--mortar", default="dry"); ap.add_argument("--courses", type=int, default=3)
    ap.add_argument("--per-course", type=int, default=3); ap.add_argument("--seeds", type=int, default=1)
    ap.add_argument("--noise", type=float, default=0.0); ap.add_argument("--size-rand", type=float, default=0.0)
    ap.add_argument("--pos-rand", type=float, default=0.0); ap.add_argument("--out", default="")
    ap.add_argument("--task", default="wall", help="wall | 2p1 (blueprint 4.3)")
    a = ap.parse_args()
    if a.task == "2p1":
        cfg = blueprint_config(a.mortar, size_rand=a.size_rand, pos_rand=a.pos_rand)
    else:
        bed = 0.002 if a.mortar != "dry" else 0.0
        cfg = SceneConfig(wall=WallSpec(n_courses=a.courses, n_per_course=a.per_course, bed_joint=bed), mortar=a.mortar,
                          size_rand=a.size_rand, pos_rand=a.pos_rand)
    t = time.time(); res = []
    for s in range(a.seeds):
        res.append(run(cfg, s, a.noise))
    print(f"total {time.time()-t:.1f}s")
    if a.out:
        Path(a.out).write_text(json.dumps(res, indent=1, default=float), encoding="utf-8")
