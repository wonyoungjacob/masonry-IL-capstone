"""Collect IK-scripted brick-laying demonstrations into a LeRobotDataset (v3 format, lerobot 0.6).

Each episode: randomised bricks/supply -> scripted expert (DLS IK) -> frames recorded at 25 Hz with
front + wrist (+ optional top) cameras, joint state, exact brick poses (privileged env state) and the
clean 6-D joint-position action.  Episodes are filtered on the 8-metric scorecard (stable wall) and the
per-episode metrics are written next to the dataset.

Usage:
  python collect.py --episodes 20 --mortar dry --root data/bricks_dry_v0 --repo-id local/bricks_dry_v0
"""
import argparse, json, sys, time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from brick_sim.scene import BrickEnv, SceneConfig, WallSpec, n_bricks_for, blueprint_config, scene_spec
from brick_sim.expert import ScriptedExpert
from brick_sim.metrics import compute_metrics

TASK = "Stack the three bricks: two side by side, one on top bridging the joint."


def make_features(env: BrickEnv, cams, obs_set="both"):
    """obs_set: both | image (cameras + joints, for the vision policy) | state (brick poses + joints, privileged baseline)."""
    h, w = env.cfg.img_h, env.cfg.img_w
    f = {}
    if obs_set in ("both", "image"):
        for c in cams:
            f[f"observation.images.{c}"] = {"dtype": "video", "shape": (h, w, 3), "names": ["height", "width", "channels"]}
    f["observation.state"] = {"dtype": "float32", "shape": (6,), "names": ["Rotation", "Pitch", "Elbow", "Wrist_Pitch", "Wrist_Roll", "Jaw"]}
    if obs_set in ("both", "state"):
        n_env = env.env_state().shape[0]
        f["observation.environment_state"] = {"dtype": "float32", "shape": (n_env,), "names": [f"e{i}" for i in range(n_env)]}
    f["action"] = {"dtype": "float32", "shape": (6,), "names": ["Rotation", "Pitch", "Elbow", "Wrist_Pitch", "Wrist_Roll", "Jaw"]}
    return f


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--episodes", type=int, default=10)
    ap.add_argument("--mortar", default="dry")
    ap.add_argument("--courses", type=int, default=3)
    ap.add_argument("--per-course", type=int, default=3)
    ap.add_argument("--size-rand", type=float, default=0.0)
    ap.add_argument("--pos-rand", type=float, default=0.0)
    ap.add_argument("--yaw-rand", type=float, default=0.0)
    ap.add_argument("--noise", type=float, default=0.0, help="DART-style execution noise std (m)")
    ap.add_argument("--cams", default="front,wrist")
    ap.add_argument("--img", type=int, default=128)
    ap.add_argument("--fps", type=int, default=25)
    ap.add_argument("--root", required=True)
    ap.add_argument("--repo-id", default="local/bricks")
    ap.add_argument("--seed0", type=int, default=0)
    ap.add_argument("--keep-all", action="store_true", help="keep episodes even if the wall is not stable")
    ap.add_argument("--task", default="wall", help="wall | 2p1 (blueprint 4.3: 3 bricks, 90x42.6x27 mm, 20 Hz)")
    ap.add_argument("--obs-set", default="both", choices=["both", "image", "state"],
                    help="image = vision policy dataset (no brick poses); state = coordinate baseline (no cameras); both")
    ap.add_argument("--spec", default="v2", choices=["v1", "v2"], help="scene spec (see brick_sim.scene.SPEC_V1/V2)")
    ap.add_argument("--disturb", type=float, default=0.0, help="P(a brick gets knocked) before each pick and after each release; the expert recovers (re-pick, re-place) and the recovery is recorded")
    ap.add_argument("--retries", type=int, default=2, help="max re-placements per brick after a bad placement")
    a = ap.parse_args()

    from lerobot.datasets.lerobot_dataset import LeRobotDataset

    cams = a.cams.split(",")
    if a.task == "2p1":
        cfg = blueprint_config(a.mortar, spec=a.spec, size_rand=a.size_rand, pos_rand=a.pos_rand, supply_yaw_deg=a.yaw_rand,
                               img_h=a.img, img_w=a.img)
        a.fps = int(round(1.0 / cfg.ctrl_dt))   # 20 Hz per blueprint 4.4
    else:
        bed = 0.002 if a.mortar != "dry" else 0.0
        cfg = SceneConfig(wall=WallSpec(n_courses=a.courses, n_per_course=a.per_course, bed_joint=bed), mortar=a.mortar,
                          size_rand=a.size_rand, pos_rand=a.pos_rand, supply_yaw_deg=a.yaw_rand, img_h=a.img, img_w=a.img,
                          ctrl_dt=1.0 / a.fps)
    env = BrickEnv(cfg)
    root = Path(a.root)
    if root.exists():
        raise SystemExit(f"{root} exists; choose a new --root")
    if a.obs_set == "state":
        cams = []
    ds = LeRobotDataset.create(a.repo_id, fps=a.fps, features=make_features(env, cams, a.obs_set), root=str(root),
                               robot_type="so100", use_videos=True)
    metrics_log = []
    kept = 0
    t0 = time.time()
    for ep in range(a.episodes):
        seed = a.seed0 + ep
        env.reset(seed)
        ex = ScriptedExpert(env, noise_std=a.noise, seed=seed, disturb_prob=a.disturb, max_retries=a.retries)

        def rec(obs, act, info):
            frame = {"task": TASK, "observation.state": obs["observation.state"], "action": act}
            if a.obs_set in ("both", "state"):
                frame["observation.environment_state"] = obs["observation.environment_state"]
            for c in cams:
                frame[f"observation.images.{c}"] = env.render(c)
            ds.add_frame(frame)

        nfail = ex.run_episode(rec)
        before = env.brick_poses().copy()
        env.settle(50)
        M = compute_metrics(env.brick_poses(), env.design, env.brick, cfg.wall, poses_before_settle=before)
        M.update({"episode_seed": seed, "steps": env.t, "ik_fail_steps": nfail, "n_bricks": env.n_bricks,
                  "brick_LWH": [env.brick.L, env.brick.W, env.brick.H], "cured": env.cured.tolist(),
                  "disturbances": ex.events, "recoveries": ex.recoveries, "unrecoverable": ex.unrecoverable,
                  "bed_laid": bool(getattr(env, "bed_laid", False))})
        if cfg.layout == "2p1":
            from brick_sim.metrics import compute_metrics3
            M.update({f"bp_{k}": v for k, v in compute_metrics3(env.brick_poses(), env.design, env.brick, cfg.wall).items() if k != "assignment"})
        keep = a.keep_all or (M["m7_stable"] and M["m1_success_rate"] >= 0.5)
        M["kept"] = bool(keep)
        metrics_log.append(M)
        if keep:
            ds.save_episode()
            kept += 1
        else:
            ds.clear_episode_buffer()
        print(f"ep {ep:3d} seed {seed} steps {env.t} exy {M['m1_exy_mean_mm']:.2f}mm succ {M['m1_success_rate']:.2f} "
              f"stable {M['m7_stable']} kicks {len(ex.events)} recov {ex.recoveries} unrec {ex.unrecoverable} kept {keep}  ({time.time()-t0:.0f}s)")
    ds.finalize()
    (root / "episode_metrics.json").write_text(json.dumps(metrics_log, indent=1, default=float), encoding="utf-8")
    # the scene spec is recorded so that eval_policy.py / view_demo.py rebuild exactly this task for the policy
    (root / "collect_config.json").write_text(json.dumps({**vars(a), "scene": scene_spec(cfg)}, indent=1), encoding="utf-8")
    print(f"done: kept {kept}/{a.episodes} episodes -> {root}  ({time.time()-t0:.0f}s)")


if __name__ == "__main__":
    main()
