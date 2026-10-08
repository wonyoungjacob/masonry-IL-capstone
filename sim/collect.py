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
    ap.add_argument("--clean-single-pass", action="store_true", help="first-attempt grasps, no re-placement, all three must succeed")
    ap.add_argument("--valid-supply", action="store_true", help="reject overlapping or out-of-reach initial layouts")
    ap.add_argument("--feasible-supply", action="store_true", help="also reject layouts whose expert grasp self-collides or whose closing jaw hits a neighbour (brick_sim.feasibility)")
    ap.add_argument("--target-kept", type=int, default=0, help="stop once this many accepted episodes have been collected")
    ap.add_argument("--task", default="wall", help="wall | 2p1 (blueprint 4.3: 3 bricks, 90x42.6x27 mm, 20 Hz)")
    ap.add_argument("--obs-set", default="both", choices=["both", "image", "state"],
                    help="image = vision policy dataset (no brick poses); state = coordinate baseline (no cameras); both")
    ap.add_argument("--spec", default="v2", choices=["v1", "v2"], help="scene spec (see brick_sim.scene.SPEC_V1/V2)")
    ap.add_argument("--disturb", type=float, default=0.0, help="P(a brick gets knocked) before each pick and after each release; the expert recovers (re-pick, re-place) and the recovery is recorded")
    ap.add_argument("--retries", type=int, default=2, help="max re-placements per brick after a bad placement")
    ap.add_argument("--max-kicks", type=int, default=2, help="max disturbances per episode (1 with a low --disturb gives a mostly-clean set with some recoveries)")
    ap.add_argument("--kick-hold", type=int, default=0, help="control steps the arm freezes after a kick (0 = keep moving)")
    ap.add_argument("--per-episode-kick", action="store_true", help="--disturb is P(episode has one kick) instead of P(kick) at each of the 2*n_bricks opportunities")
    ap.add_argument("--disturb-from", type=int, default=-1, help="episodes with index >= N always get a kick, earlier ones never do "
                    "(a 'clean + extra recovery episodes' set: the clean part stays identical to the clean dataset, "
                    "recovery is added on top instead of replacing clean demonstrations)")
    a = ap.parse_args()
    if a.clean_single_pass and (a.keep_all or a.noise or a.disturb or a.disturb_from >= 0):
        ap.error("clean-single-pass cannot be combined with keep-all, noise or disturbances")
    if a.clean_single_pass:
        a.retries = 0

    from lerobot.datasets.lerobot_dataset import LeRobotDataset

    cams = a.cams.split(",")
    if a.task == "2p1":
        cfg = blueprint_config(a.mortar, spec=a.spec, size_rand=a.size_rand, pos_rand=a.pos_rand, supply_yaw_deg=a.yaw_rand,
                               img_h=a.img, img_w=a.img, valid_supply=a.valid_supply,
                               feasible_supply=a.feasible_supply)
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
        initial_poses = env.brick_poses().tolist()
        dprob = a.disturb
        per_ep = a.per_episode_kick
        if a.disturb_from >= 0:
            dprob, per_ep = (1.0 if ep >= a.disturb_from else 0.0), True
        ex = ScriptedExpert(env, noise_std=a.noise, seed=seed, disturb_prob=dprob, max_retries=a.retries, max_kicks=a.max_kicks,
                            kick_hold=a.kick_hold, per_episode=per_ep, clean_single_pass=a.clean_single_pass)

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
        M.update({"initial_poses": initial_poses, "expert_log": ex.log,
                  "supply_sample_attempts": env.supply_sample_attempts, "feasibility_rejects": env.feasibility_rejects})
        if cfg.layout == "2p1":
            from brick_sim.metrics import compute_metrics3
            M.update({f"bp_{k}": v for k, v in compute_metrics3(env.brick_poses(), env.design, env.brick, cfg.wall).items() if k != "assignment"})
        keep = a.keep_all or (M["m7_stable"] and M["m1_success_rate"] >= 0.5)
        if a.clean_single_pass:
            keep = bool(M["m1_all_success"] and M["m7_stable"] and not ex.unrecoverable
                        and not ex.recoveries
                        and sum(e.get("stage") == "grasp" and e["ok"] for e in ex.log) == env.n_bricks
                        and sum(e.get("stage") == "release" and e["ok"] for e in ex.log) == env.n_bricks)
        M["kept"] = bool(keep)
        if a.clean_single_pass:
            M["rejection_reasons"] = ([] if keep else
                (["first_grasp_or_carry_or_release_failed"] if ex.unrecoverable else []) +
                (["final_placement_not_all_success"] if not M["m1_all_success"] else []) +
                (["unstable"] if not M["m7_stable"] else []))
        metrics_log.append(M)
        if keep:
            ds.save_episode()
            kept += 1
        else:
            ds.clear_episode_buffer()
        (root / "collection_progress.json").write_text(json.dumps({"attempted": len(metrics_log), "kept": kept,
                                                                  "target": a.target_kept, "last_seed": seed}))
        print(f"ep {ep:3d} seed {seed} steps {env.t} exy {M['m1_exy_mean_mm']:.2f}mm succ {M['m1_success_rate']:.2f} "
              f"stable {M['m7_stable']} kicks {len(ex.events)} recov {ex.recoveries} unrec {ex.unrecoverable} kept {keep}  ({time.time()-t0:.0f}s)")
        if a.target_kept and kept >= a.target_kept:
            break
    (root / "episode_metrics.json").write_text(json.dumps(metrics_log, indent=1, default=float), encoding="utf-8")
    # the scene spec is recorded so that eval_policy.py / view_demo.py rebuild exactly this task for the policy
    (root / "collect_config.json").write_text(json.dumps({**vars(a), "scene": scene_spec(cfg)}, indent=1), encoding="utf-8")
    if kept == 0:
        raise SystemExit("No accepted episodes; rejection audit saved, dataset is not suitable for training")
    ds.finalize()
    print(f"done: kept {kept}/{len(metrics_log)} attempted episodes -> {root}  ({time.time()-t0:.0f}s)")
    if a.target_kept and kept < a.target_kept:
        raise SystemExit(f"Insufficient accepted demonstrations: {kept}/{a.target_kept}; do not start training")


if __name__ == "__main__":
    main()
