"""Watch the IK scripted expert build the wall in the interactive MuJoCo viewer (real time).

Usage:  python view_demo.py [--mortar dry|mortarA|mortarB] [--courses 3] [--seed 0] [--speed 1.0] [--loop]
Controls: mouse drag = orbit, scroll = zoom, double-click = select body, Esc = close.
"""
import argparse, sys, time
from pathlib import Path

import mujoco
import mujoco.viewer
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from brick_sim.scene import BrickEnv, SceneConfig, WallSpec, blueprint_config
from brick_sim.expert import ScriptedExpert
from brick_sim.metrics import compute_metrics


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mortar", default="dry")
    ap.add_argument("--courses", type=int, default=3)
    ap.add_argument("--per-course", type=int, default=3)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--speed", type=float, default=1.0, help="playback speed multiplier")
    ap.add_argument("--size-rand", type=float, default=0.05)
    ap.add_argument("--pos-rand", type=float, default=0.01)
    ap.add_argument("--loop", action="store_true")
    ap.add_argument("--task", default="2p1", help="2p1 (blueprint 4.3, default) | wall")
    a = ap.parse_args()

    if a.task == "2p1":
        cfg = blueprint_config(a.mortar, size_rand=a.size_rand, pos_rand=a.pos_rand, supply_yaw_deg=10.0)
    else:
        bed = 0.002 if a.mortar != "dry" else 0.0
        cfg = SceneConfig(wall=WallSpec(n_courses=a.courses, n_per_course=a.per_course, bed_joint=bed), mortar=a.mortar,
                          size_rand=a.size_rand, pos_rand=a.pos_rand, supply_yaw_deg=5.0)
    env = BrickEnv(cfg)
    seed = a.seed
    while True:
        env.reset(seed)
        ex = ScriptedExpert(env, seed=seed)
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
                ex.run_episode(rec)
                before = env.brick_poses().copy()
                env.settle(50)
                v.sync()
                M = compute_metrics(env.brick_poses(), env.design, env.brick, cfg.wall, poses_before_settle=before)
                print(f"[seed {seed} {a.mortar}] placement success {M['m1_success_rate']:.2f}, xy err {M['m1_exy_mean_mm']:.2f} mm, "
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
