"""Roll out a trained LeRobot policy (ACT / Diffusion / ...) in the brick environment and score it
with the 8-metric masonry scorecard.  Works for image-based and state-based (environment_state) policies.

Usage:
  python eval_policy.py --ckpt outputs/act_dry_v0/checkpoints/last/pretrained_model --episodes 5 --mortar dry
"""
import argparse, json, sys, time
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from brick_sim.scene import BrickEnv, SceneConfig, WallSpec, blueprint_config
from brick_sim.metrics import compute_metrics, compute_metrics3
from run_expert_eval import KEYS


def load_policy(ckpt: str):
    from lerobot.policies.factory import get_policy_class
    from lerobot.configs.policies import PreTrainedConfig
    cfg = PreTrainedConfig.from_pretrained(ckpt)
    cfg.device = "cpu"
    cls = get_policy_class(cfg.type)
    policy = cls.from_pretrained(ckpt, config=cfg)
    policy.eval()
    return policy, cfg


def build_obs(env, cams, cfg):
    obs = {}
    for k in cfg.input_features:
        if k.startswith("observation.images."):
            cam = k.split(".")[-1]
            img = env.render(cam)  # HWC uint8
            obs[k] = torch.from_numpy(img).permute(2, 0, 1).float().div(255.0).unsqueeze(0)
        elif k == "observation.state":
            obs[k] = torch.from_numpy(env.qpos_arm()).unsqueeze(0)
        elif k == "observation.environment_state":
            obs[k] = torch.from_numpy(env.env_state()).unsqueeze(0)
    obs["task"] = ["Stack the bricks into a running-bond wall on the marked line."]
    return obs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", required=True)
    ap.add_argument("--episodes", type=int, default=5)
    ap.add_argument("--mortar", default="dry")
    ap.add_argument("--courses", type=int, default=3)
    ap.add_argument("--per-course", type=int, default=3)
    ap.add_argument("--size-rand", type=float, default=0.05)
    ap.add_argument("--pos-rand", type=float, default=0.01)
    ap.add_argument("--yaw-rand", type=float, default=5.0)
    ap.add_argument("--seed0", type=int, default=1000, help="use seeds disjoint from training")
    ap.add_argument("--max-steps", type=int, default=1800)
    ap.add_argument("--fps", type=int, default=25)
    ap.add_argument("--out", default="")
    ap.add_argument("--task", default="wall", help="wall | 2p1 (blueprint 4.3)")
    a = ap.parse_args()

    policy, pcfg = load_policy(a.ckpt)
    print("policy", pcfg.type, "inputs", list(pcfg.input_features.keys()))
    if a.task == "2p1":
        cfg = blueprint_config(a.mortar, size_rand=a.size_rand, pos_rand=a.pos_rand, supply_yaw_deg=a.yaw_rand)
    else:
        bed = 0.002 if a.mortar != "dry" else 0.0
        cfg = SceneConfig(wall=WallSpec(n_courses=a.courses, n_per_course=a.per_course, bed_joint=bed), mortar=a.mortar,
                          size_rand=a.size_rand, pos_rand=a.pos_rand, supply_yaw_deg=a.yaw_rand, ctrl_dt=1.0 / a.fps)
    env = BrickEnv(cfg)
    cams = [k.split(".")[-1] for k in pcfg.input_features if k.startswith("observation.images.")]
    results = []
    for ep in range(a.episodes):
        seed = a.seed0 + ep
        env.reset(seed)
        policy.reset()
        # the feeder stages bricks in order; the policy must trigger nothing -> we stage brick i when brick i-1 is on the wall
        staged = 0
        env.stage_brick(0); staged = 1
        t0 = time.time()
        for t in range(a.max_steps):
            obs = build_obs(env, cams, pcfg)
            with torch.inference_mode():
                act = policy.select_action(obs)
            env.step(act.squeeze(0).numpy())
            # stage the next brick once the current one has been released on the wall line
            if staged < env.n_bricks:
                p, _ = env.brick_pose(staged - 1)
                jaw_open = env.data.qpos[env.jaw_qidx] > 0.5
                if jaw_open and abs(p[1] - cfg.wall.origin_y) < 0.03 and p[0] < 0.0:
                    env.stage_brick(staged); staged += 1
        before = env.brick_poses().copy(); env.settle(50)
        M = compute_metrics(env.brick_poses(), env.design, env.brick, cfg.wall, poses_before_settle=before)
        if cfg.layout == "2p1":
            M.update({f"bp_{k}": v for k, v in compute_metrics3(env.brick_poses(), env.design, env.brick, cfg.wall).items() if k != "assignment"})
        M["seed"] = seed; M["staged"] = staged; M["wall_s"] = time.time() - t0
        results.append(M)
        print(f"ep {ep} seed {seed} staged {staged}/{env.n_bricks} succ {M['m1_success_rate']:.2f} exy {M['m1_exy_mean_mm']:.1f}mm "
              f"fallen {M['m7_fallen_count']} iou {M['m8_voxel_iou']:.2f}  ({M['wall_s']:.0f}s)")
    agg = {k: float(np.mean([r[k] for r in results])) for k in ["m1_success_rate", "m1_exy_mean_mm", "m2_level_range_max_mm",
                                                              "m3_plumb_mm", "m4_straightness_max_mm", "m6_through_joints",
                                                              "m7_fallen_count", "m8_voxel_iou"]}
    print("MEAN:", json.dumps(agg, indent=1))
    if a.out:
        Path(a.out).write_text(json.dumps({"episodes": results, "mean": agg}, indent=1, default=float), encoding="utf-8")


if __name__ == "__main__":
    main()
