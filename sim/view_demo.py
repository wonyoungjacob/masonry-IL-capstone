"""Watch the IK scripted expert -- or a trained LeRobot policy -- build the wall in the interactive MuJoCo viewer.

Usage:  python view_demo.py [--mortar dry|mortarA|mortarB] [--courses 3] [--seed 0] [--speed 1.0] [--loop]
        python view_demo.py --task 2p1 --mortar mortarB --noise 0.003            # DART execution noise, clean labels
        python view_demo.py --task 2p1 --mortar mortarB --ckpt outputs/act_2p1_joint_image_clean/checkpoints/last/pretrained_model
Controls: mouse drag = orbit, scroll = zoom, double-click = select body, Esc = close.
"""
import argparse, json, sys, time
from pathlib import Path

import mujoco
import mujoco.viewer
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from brick_sim.scene import BrickEnv, SceneConfig, WallSpec, blueprint_config
from brick_sim.expert import ScriptedExpert
from brick_sim.metrics import compute_metrics


def run_policy(env, cfg, v, pacer, a):
    """Roll out a trained policy (same loop as eval_policy.py) while the viewer follows."""
    import torch
    from eval_policy import load_policy, camera_sources, build_obs
    rename_map = json.loads(a.rename_map) if a.rename_map else None
    if not hasattr(run_policy, "cache"):
        run_policy.cache = load_policy(a.ckpt, a.device, rename_map)
    policy, pcfg, pre, post = run_policy.cache
    cam_src = camera_sources(pcfg, rename_map)
    policy.reset()
    env.stage_brick(0); staged = 1
    rng = np.random.default_rng(a.seed + 777)
    kick_t = int(rng.integers(40, 400)) if rng.random() < a.disturb else -1
    for t in range(a.max_steps):
        obs = build_obs(env, cam_src, pcfg)
        with torch.inference_mode():
            act = post(policy.select_action(pre(obs)))
        env.step(act.squeeze(0).detach().cpu().numpy())
        if t == kick_t:
            tcp = env.tcp_pose()[0]
            free = [i for i in range(env.n_bricks)
                    if np.linalg.norm(env.brick_pose(i)[0] - tcp) > 0.05 and not env.cured[i]]
            if free:
                print("kick:", env.kick_brick(int(rng.choice(free)), rng, speed=(0.3, 0.5), tip_prob=0.0))
            else:
                kick_t += 20
        if staged < env.n_bricks:
            p, _ = env.brick_pose(staged - 1)
            if env.data.qpos[env.jaw_qidx] > 0.5 and abs(p[1] - cfg.wall.origin_y) < 0.03 and p[0] < 0.0:
                env.stage_brick(staged); staged += 1
        pacer()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mortar", default="dry")
    ap.add_argument("--courses", type=int, default=3)
    ap.add_argument("--per-course", type=int, default=3)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--speed", type=float, default=1.0, help="playback speed multiplier")
    ap.add_argument("--size-rand", type=float, default=0.05)
    ap.add_argument("--pos-rand", type=float, default=0.01)
    ap.add_argument("--yaw-rand", type=float, default=10.0)
    ap.add_argument("--loop", action="store_true")
    ap.add_argument("--clean-single-pass", action="store_true", help="expert: first-attempt grasp, no re-placement")
    ap.add_argument("--valid-supply", action="store_true", help="expert: sample nonoverlapping supply layouts")
    ap.add_argument("--task", default="2p1", help="2p1 (blueprint 4.3, default) | wall")
    ap.add_argument("--noise", type=float, default=0.0, help="expert only: DART execution noise std (m)")
    ap.add_argument("--disturb", type=float, default=0.0, help="policy: P(one kick per episode), as in eval_policy.py; expert: per-opportunity probability")
    ap.add_argument("--ckpt", default="", help="LeRobot checkpoint dir: roll out the trained policy instead of the expert")
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--rename-map", default="", help="JSON {dataset key: policy key} for pretrained VLAs (see eval_policy.py)")
    ap.add_argument("--max-steps", type=int, default=1800)
    ap.add_argument("--spec", default="v2", choices=["v1", "v2"], help="scene spec for the expert (a --ckpt policy "
                    "always gets the spec of the dataset it was trained on)")
    a = ap.parse_args()

    if a.task == "2p1":
        spec = {}
        if a.ckpt:
            from eval_policy import scene_spec_for_ckpt
            spec = scene_spec_for_ckpt(a.ckpt)
            print("scene spec from checkpoint dataset:", spec)
        cfg = blueprint_config(a.mortar, spec=a.spec, size_rand=a.size_rand, pos_rand=a.pos_rand, supply_yaw_deg=a.yaw_rand,
                               valid_supply=a.valid_supply, **spec)
    else:
        bed = 0.002 if a.mortar != "dry" else 0.0
        cfg = SceneConfig(wall=WallSpec(n_courses=a.courses, n_per_course=a.per_course, bed_joint=bed), mortar=a.mortar,
                          size_rand=a.size_rand, pos_rand=a.pos_rand, supply_yaw_deg=5.0)
    env = BrickEnv(cfg)
    seed = a.seed
    who = f"policy {Path(a.ckpt).parts[-4] if a.ckpt else ''}" if a.ckpt else f"expert noise={a.noise} disturb={a.disturb}"
    while True:
        a.seed = seed
        env.reset(seed)
        ex = ScriptedExpert(env, noise_std=a.noise, seed=seed, disturb_prob=a.disturb,
                            max_retries=0 if a.clean_single_pass else 2, clean_single_pass=a.clean_single_pass)
        with mujoco.viewer.launch_passive(env.model, env.data) as v:
            v.cam.lookat[:] = [-0.03, -0.18, 0.05]
            v.cam.distance = 0.75
            v.cam.azimuth = 150
            v.cam.elevation = -25
            last = time.time()

            def rec(obs, act, info):
                nonlocal last
                if not v.is_running():
                    raise KeyboardInterrupt
                v.sync()
                # pace to real time
                dt = env.cfg.ctrl_dt / a.speed
                now = time.time()
                if now - last < dt:
                    time.sleep(dt - (now - last))
                last = time.time()

            try:
                if a.ckpt:
                    run_policy(env, cfg, v, lambda: rec(None, None, None), a)
                else:
                    ex.run_episode(rec)
                before = env.brick_poses().copy()
                env.settle(50)
                v.sync()
                M = compute_metrics(env.brick_poses(), env.design, env.brick, cfg.wall, poses_before_settle=before)
                extra = f" kicks {len(ex.events)} recov {ex.recoveries} unrec {ex.unrecoverable}" if not a.ckpt else ""
                print(f"[{who} | seed {seed} {a.mortar}{extra}] placement success {M['m1_success_rate']:.2f}, xy err {M['m1_exy_mean_mm']:.2f} mm, "
                      f"plumb {M['m3_plumb_mm']:.2f} mm, straightness {M['m4_straightness_max_mm']:.2f} mm, fallen {M['m7_fallen_count']}, IoU {M['m8_voxel_iou']:.2f}")
                # hold the finished wall on screen
                t_end = time.time()
                while v.is_running() and time.time() - t_end < (3.0 if a.loop else 1e9):
                    v.sync(); time.sleep(0.05)
            except KeyboardInterrupt:
                return
        if not a.loop:
            return
        seed += 1


if __name__ == "__main__":
    main()
