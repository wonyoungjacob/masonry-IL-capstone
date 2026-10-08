"""Snapshots of one test episode for the capstone progress report: policy alone vs policy + gates (G1-G3).

Re-runs a single layout seed exactly as eval_policy.py does (same inference seed, same gate options) and keeps a
free-camera frame every few control steps, so the gate events can be shown as pictures.  Writes nothing to the result
folders; frames and an events JSON go to outputs/capstone/.
"""
import os
os.environ.setdefault("MUJOCO_GL", "egl")
os.environ.setdefault("HF_HUB_OFFLINE", "1")
import argparse, json, sys
from pathlib import Path

import mujoco
import numpy as np
import torch
from PIL import Image

SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SIM))
from eval_policy import load_policy, camera_sources, build_obs, scene_spec_for_ckpt
from brick_sim.scene import BrickEnv, blueprint_config
from brick_sim.metrics import compute_metrics
from brick_sim.grasp_gate import GraspGate

OUT = SIM / "outputs" / "capstone"


def free_cam(az, el, dist, lookat):
    c = mujoco.MjvCamera()
    c.type = mujoco.mjtCamera.mjCAMERA_FREE
    c.azimuth, c.elevation, c.distance, c.lookat[:] = az, el, dist, lookat
    return c


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--policy", default="act")
    ap.add_argument("--train-seed", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=50018)
    ap.add_argument("--seed0", type=int, default=50000)
    ap.add_argument("--gates", action="store_true")
    ap.add_argument("--every", type=int, default=4)
    a = ap.parse_args()

    ckpt = str(SIM / f"outputs/{a.policy}_v3_2p1_joint_image_clean_seed{a.train_seed}/checkpoints/last/pretrained_model")
    policy, pcfg, pre, post = load_policy(ckpt, "cuda", None, 10)
    cam_src = camera_sources(pcfg, None)
    spec = scene_spec_for_ckpt(ckpt)
    cfg = blueprint_config("mortarB", size_rand=0.0, pos_rand=0.03, supply_yaw_deg=60.0, valid_supply=True,
                           **{**spec, "feasible_supply": True})
    env = BrickEnv(cfg)
    env.model.vis.global_.offwidth, env.model.vis.global_.offheight = 1600, 1200
    big = mujoco.Renderer(env.model, 720, 960)
    cam = free_cam(145, -32, 0.62, [-0.02, -0.08, 0.04])
    wall_cam = free_cam(90, -14, 0.36, [-0.10, -0.17, 0.035])   # wall face seen from outside: shows heights and gaps

    tag = f"{a.policy}_s{a.train_seed}_{a.seed}_{'gates' if a.gates else 'policy'}"
    fdir = OUT / tag
    fdir.mkdir(parents=True, exist_ok=True)
    step0 = env.step

    def step(action):
        step0(action)
        if env.t % a.every == 0:
            big.update_scene(env.data, camera=cam)
            Image.fromarray(big.render()).save(fdir / f"t{env.t:05d}.jpg", quality=88)
            big.update_scene(env.data, camera=wall_cam)
            Image.fromarray(big.render()).save(fdir / f"w{env.t:05d}.jpg", quality=88)
    env.step = step

    off = a.seed - a.seed0
    torch.manual_seed(70000 + off); torch.cuda.manual_seed_all(70000 + off)
    env.reset(a.seed); policy.reset()
    env.stage_brick(0); staged = 1
    gate = GraspGate(env, policy, max_retries=0, recover="reguide", release_gate=True, force=True, replace=True,
                     pose_noise=0.0, seed=a.seed) if a.gates else None
    for _ in range(1800):
        if env.t >= 1800:
            break
        with torch.inference_mode():
            act = post(policy.select_action(pre(build_obs(env, cam_src, pcfg))))
        act_np = act.squeeze(0).cpu().numpy()
        if gate is not None:
            act_np = gate.before_step(act_np)
            if act_np is None:
                continue
        env.step(act_np)
        if gate is not None and gate.after_step(act_np) in ("abort", "done"):
            break
        if staged < env.n_bricks:
            p, _ = env.brick_pose(staged - 1)
            if env.data.qpos[env.jaw_qidx] > 0.5 and abs(p[1] - cfg.wall.origin_y) < 0.03 and p[0] < 0.0:
                env.stage_brick(staged); staged += 1
    env.settle(50)
    big.update_scene(env.data, camera=cam)
    Image.fromarray(big.render()).save(fdir / "final.jpg", quality=92)
    big.update_scene(env.data, camera=wall_cam)
    Image.fromarray(big.render()).save(fdir / "wfinal.jpg", quality=92)
    M = compute_metrics(env.brick_poses(), env.design, env.brick, cfg.wall)
    rec = {"success": M["m1_success_rate"], "all": bool(M["m1_all_success"]), "steps": int(env.t)}
    if gate is not None:
        s = gate.summary()
        rec.update(gate_events=s["gate_events"], release_events=s["release_events"])
    (fdir / "events.json").write_text(json.dumps(rec, indent=1, default=float), encoding="utf-8")
    print(tag, rec["success"], rec["all"], rec["steps"])


if __name__ == "__main__":
    main()
