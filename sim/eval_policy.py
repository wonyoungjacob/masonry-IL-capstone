"""Roll out a trained LeRobot policy (ACT / Diffusion / ...) in the brick environment and score it
with the 8-metric masonry scorecard.  Works for image-based and state-based (environment_state) policies.

Usage:
  python eval_policy.py --ckpt outputs/act_dry_v0/checkpoints/last/pretrained_model --episodes 5 --mortar dry
"""
import argparse, functools, json, os, sys, time
from pathlib import Path

import numpy as np
import torch

# The rollout is one MuJoCo thread + tiny CPU tensors; torch's default 32 intra-op threads just spin and,
# with a training job on the same box, slow each step ~8x.  Log lines are flushed so progress is visible.
torch.set_num_threads(int(os.environ.get("EVAL_THREADS", "1")))
print = functools.partial(print, flush=True)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from brick_sim.scene import BrickEnv, SceneConfig, WallSpec, blueprint_config
from brick_sim.metrics import compute_metrics, compute_metrics3
from run_expert_eval import KEYS
from brick_sim.grasp_gate import GraspGate
from collect import TASK  # the language instruction must match the one recorded in the datasets (VLA policies)


def load_policy(ckpt: str, device: str, rename_map: dict | None = None, n_action_steps: int | None = None):
    """Load a LeRobot (>=0.6) checkpoint together with its pre/post-processor pipelines.

    In lerobot 0.6 observation normalisation and action un-normalisation live in the saved
    `policy_preprocessor` / `policy_postprocessor` pipelines, not inside the policy, so calling
    `policy.select_action` on raw observations silently produces garbage actions.
    """
    from lerobot.policies.factory import get_policy_class, make_pre_post_processors
    from lerobot.configs.policies import PreTrainedConfig
    cfg = PreTrainedConfig.from_pretrained(ckpt)
    cfg.device = device
    if n_action_steps:
        # how long the policy runs open loop before it looks again: ACT 100 steps (5 s), SmolVLA 50 (2.5 s),
        # Diffusion 32 (1.6 s).  Lowering it at inference time costs nothing but compute.
        cfg.n_action_steps = n_action_steps
    cls = get_policy_class(cfg.type)
    policy = cls.from_pretrained(ckpt, config=cfg)
    policy.eval()
    overrides = {"device_processor": {"device": device}}
    if rename_map:
        overrides["rename_observations_processor"] = {"rename_map": rename_map}
    pre, post = make_pre_post_processors(policy_cfg=cfg, pretrained_path=ckpt, preprocessor_overrides=overrides)
    return policy, cfg, pre, post


def scene_spec_for_ckpt(ckpt: str) -> dict:
    """Scene spec (head joint, mortar impl, marks, supply) recorded with the dataset this checkpoint was trained on.

    A policy must be evaluated in the task it was trained for; datasets from before the spec was recorded
    (2026-09-18 data/2p1_*) are the legacy v1 scene.
    """
    from brick_sim.scene import SPEC_V1
    try:
        tc = json.loads((Path(ckpt) / "train_config.json").read_text(encoding="utf-8"))
        root = Path(tc["dataset"]["root"])
        if not root.is_absolute():
            root = Path(__file__).resolve().parent / root
        cc = json.loads((root / "collect_config.json").read_text(encoding="utf-8"))
        spec = cc.get("scene")
        if spec is None:
            print(f"scene spec: {root.name} predates the spec record -> legacy v1")
            return dict(SPEC_V1)
        return dict(spec)
    except Exception as e:  # noqa: BLE001 - fall back loudly, never silently evaluate in the wrong scene
        print(f"scene spec: cannot read the dataset's collect_config.json ({e}) -> legacy v1")
        return dict(SPEC_V1)


def camera_sources(cfg, rename_map: dict | None, available=("front", "wrist", "top")):
    """Map each image feature the policy expects -> the simulator camera that feeds it.

    Pretrained VLAs (SmolVLA: camera1..3, pi0: base_0_rgb/left_wrist_0_rgb/...) keep their own feature
    names; `rename_map` {dataset key -> policy key} is the same map used with `lerobot-train --rename_map`.
    Policy image keys with no source (e.g. a third camera we do not have) are left out and handled by the
    policy's `empty_cameras` padding.
    """
    inv = {v: k for k, v in (rename_map or {}).items()}
    out = {}
    for k in cfg.input_features:
        if not k.startswith("observation.images."):
            continue
        src = inv.get(k, k).split(".")[-1]
        if src in available:
            out[inv.get(k, k)] = src
    return out


def build_obs(env, cam_src, cfg):
    """Raw (un-normalised) observation with the *dataset* key names; the preprocessor renames/normalises."""
    obs = {}
    for key, cam in cam_src.items():
        img = env.render(cam)  # HWC uint8
        obs[key] = torch.from_numpy(img).permute(2, 0, 1).float().div(255.0).unsqueeze(0)
    for k in cfg.input_features:
        if k == "observation.state":
            obs[k] = torch.from_numpy(env.qpos_arm()).unsqueeze(0)
        elif k == "observation.environment_state":
            obs[k] = torch.from_numpy(env.env_state()).unsqueeze(0)
    obs["task"] = [TASK]
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
    ap.add_argument("--valid-supply", action="store_true")
    ap.add_argument("--inference-seed", type=int, default=70000)
    ap.add_argument("--seed0", type=int, default=1000, help="use seeds disjoint from training")
    ap.add_argument("--seed-list", default="", help="comma-separated layout seeds to run instead of seed0..seed0+episodes-1 "
                    "(inference seed = --inference-seed + seed - seed0, same as in a contiguous run)")
    ap.add_argument("--max-steps", type=int, default=1800)
    ap.add_argument("--fps", type=int, default=25)
    ap.add_argument("--out", default="")
    ap.add_argument("--task", default="wall", help="wall | 2p1 (blueprint 4.3)")
    ap.add_argument("--first-course-only", action="store_true", help="2p1: spawn and score only the two lower-course bricks")
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    ap.add_argument("--n-action-steps", type=int, default=0, help="override how many steps of each predicted chunk are "
                    "executed before re-observing (0 = the checkpoint's own value)")
    ap.add_argument("--disturb", type=float, default=0.0, help="P(one brick gets knocked during the episode): tests recovery. "
                    "The kick happens at a random step in [40, 400] on a random brick that is not in the hand (planar, no tipping)")
    ap.add_argument("--grasp-gate", action="store_true", help="policy + gate: no transport without a verified grasp (jaw angle); "
                    "an empty close is opened, lifted 4 cm and the policy re-observes (brick_sim.grasp_gate)")
    ap.add_argument("--gate-retries", type=int, default=3, help="empty grasps allowed before the episode is aborted "
                    "(0 = no limit: the policy keeps trying until --max-steps)")
    ap.add_argument("--release-gate", action="store_true", help="with --grasp-gate: intercept the policy's release, measure the held "
                    "brick's xy/yaw error to its slot (sim brick pose), servo-correct if > 2.5 mm / 3 deg, then release")
    ap.add_argument("--gate-replace", action="store_true", help="with --release-gate: score the released brick right away against the "
                    "final tolerances (4.5 mm, 3 mm height, 5 deg yaw, 5 deg tilt) and, if it fails, re-grasp and place it again "
                    "(once per brick).  The policy itself is never allowed to re-grasp a released brick")
    ap.add_argument("--gate-force", action="store_true", help="with --grasp-gate: after each close the gate lifts 1.5 cm, holds still "
                    "and requires jaw angle > 0.2 rad AND wrist load > 0.9 N (simulated force sensor) before the policy may carry")
    ap.add_argument("--gate-inspect", default="", help="with --release-gate: design slots the release gate inspects, "
                    "e.g. '0,1' (lower course) or '2' (top); 'none' = no slot; empty = all.  Other bricks are released by the "
                    "policy unmeasured (KICEM 2026 inspection-scope experiment)")
    ap.add_argument("--gate-nominal-plan", action="store_true", help="the gate plans placements from the nominal brick size "
                    "and design (the drawing) instead of the true sampled size (KICEM 2026 size-tolerance study)")
    ap.add_argument("--gate-pose-noise", type=float, default=0.0, help="std (m) of Gaussian noise on every brick pose the gate "
                    "measures for its corrections (reguide, pre-release servo, post-release score, re-placement)")
    ap.add_argument("--gate-recover", default="lift", choices=["lift", "reguide", "expert"],
                    help="what the gate does after an empty grasp: lift = open+lift where the hand is; reguide = also move to the "
                         "expert pre-grasp pose above the next unplaced brick (sim brick coordinates); expert = the expert does the pick")
    ap.add_argument("--feasible-supply", action="store_true", help="test on layouts that pass the static grasp-feasibility check "
                    "(changes the test distribution: not comparable with earlier results)")
    ap.add_argument("--rename-map", default="", help='JSON {dataset key: policy key}, same as lerobot-train --rename_map, '
                    'e.g. \'{"observation.images.front":"observation.images.camera1"}\'')
    a = ap.parse_args()

    rename_map = json.loads(a.rename_map) if a.rename_map else None
    policy, pcfg, pre, post = load_policy(a.ckpt, a.device, rename_map, a.n_action_steps or None)
    cam_src = camera_sources(pcfg, rename_map)
    print("policy", pcfg.type, "device", a.device, "n_action_steps", pcfg.n_action_steps, "inputs", list(pcfg.input_features.keys()), "cameras", cam_src)
    if a.task == "2p1":
        spec = scene_spec_for_ckpt(a.ckpt)
        print("scene spec", spec)
        cfg = blueprint_config(a.mortar, size_rand=a.size_rand, pos_rand=a.pos_rand, supply_yaw_deg=a.yaw_rand,
                               valid_supply=a.valid_supply, first_course_only=a.first_course_only, **{**spec, 'feasible_supply': spec.get('feasible_supply', False) or a.feasible_supply})
    else:
        bed = 0.002 if a.mortar != "dry" else 0.0
        cfg = SceneConfig(wall=WallSpec(n_courses=a.courses, n_per_course=a.per_course, bed_joint=bed), mortar=a.mortar,
                          size_rand=a.size_rand, pos_rand=a.pos_rand, supply_yaw_deg=a.yaw_rand, ctrl_dt=1.0 / a.fps)
    env = BrickEnv(cfg)
    results = []
    seeds = [int(x) for x in a.seed_list.split(",")] if a.seed_list else [a.seed0 + k for k in range(a.episodes)]
    for ep, seed in enumerate(seeds):
        off = seed - a.seed0   # inference seed follows the layout seed, so a seed list reproduces the contiguous run
        torch.manual_seed(a.inference_seed + off)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(a.inference_seed + off)
        env.reset(seed)
        policy.reset()
        # the feeder stages bricks in order; the policy must trigger nothing -> we stage brick i when brick i-1 is on the wall
        staged = 0
        env.stage_brick(0); staged = 1
        t0 = time.time()
        rng = np.random.default_rng(seed + 777)
        kick_t = int(rng.integers(40, 400)) if rng.random() < a.disturb else -1
        kicks = []
        held_once, released, regrasped = set(), set(), set()
        gate = GraspGate(env, policy, max_retries=a.gate_retries, recover=a.gate_recover, release_gate=a.release_gate, force=a.gate_force,
                          replace=a.gate_replace, pose_noise=a.gate_pose_noise, seed=seed, nominal_plan=a.gate_nominal_plan,
                          inspect_slots=None if not a.gate_inspect else ([] if a.gate_inspect == "none" else
                                                                         [int(x) for x in a.gate_inspect.split(",")])) if a.grasp_gate else None
        for t in range(a.max_steps):
            if env.t >= a.max_steps:   # gate recoveries also consume simulated time
                break
            obs = build_obs(env, cam_src, pcfg)
            with torch.inference_mode():
                act = post(policy.select_action(pre(obs)))
            act_np = act.squeeze(0).detach().cpu().numpy()
            if gate is not None:
                act_np = gate.before_step(act_np)   # None: the release gate executed this step itself
                if act_np is None:
                    continue
            env.step(act_np)
            if gate is not None and gate.after_step(act_np) in ("abort", "done"):
                break
            for i in range(env.n_bricks):
                if env.grasped(i):
                    if i in released:
                        regrasped.add(i)
                    held_once.add(i)
                elif i in held_once and env.data.qpos[env.jaw_qidx] > 0.5:
                    released.add(i)
            if t == kick_t:
                tcp = env.tcp_pose()[0]
                free = [i for i in range(env.n_bricks) if np.linalg.norm(env.brick_pose(i)[0] - tcp) > 0.05
                        and not env.cured[i]]
                if free:
                    kicks.append(env.kick_brick(int(rng.choice(free)), rng, speed=(0.3, 0.5), tip_prob=0.0))
                else:
                    kick_t += 20   # try again a second later
            # stage the next brick once the current one has been released on the wall line
            if staged < env.n_bricks:
                p, _ = env.brick_pose(staged - 1)
                jaw_open = env.data.qpos[env.jaw_qidx] > 0.5
                if jaw_open and abs(p[1] - cfg.wall.origin_y) < 0.03 and p[0] < 0.0:
                    env.stage_brick(staged); staged += 1
        before = env.brick_poses().copy(); env.settle(50)
        M = compute_metrics(env.brick_poses(), env.design, env.brick, cfg.wall, poses_before_settle=before)
        if cfg.layout == "2p1" and not cfg.first_course_only:
            M.update({f"bp_{k}": v for k, v in compute_metrics3(env.brick_poses(), env.design, env.brick, cfg.wall).items() if k != "assignment"})
        M["seed"] = seed; M["staged"] = staged; M["wall_s"] = time.time() - t0; M["kicks"] = kicks
        M.update(inference_seed=a.inference_seed + off, regrasped_after_release=sorted(regrasped),
                 final_poses=env.brick_poses().tolist(), metric_version="oriented_polyhedron_v1",
                 feasibility_rejects=getattr(env, "feasibility_rejects", 0), steps=int(env.t))
        if gate is not None:
            M.update(gate.summary())
        results.append(M)
        if a.out:   # partial results after every episode, so a stopped run keeps its finished episodes
            Path(a.out + ".partial").write_text(json.dumps({"episodes": results, "config": vars(a)}, default=float), encoding="utf-8")
        gtxt = (f" gate verified {M['gate_verified_grasps']} lost {M['gate_lost']} retries {M['gate_retries']} abort {M['gate_abort']} done {M['gate_done']}"
                f" release-corrected {M['release_corrected']}/{len(M['release_events'])} bad-release {M['bad_releases']}"
                f" replaced {M['replaced_ok']}/{M['replaced']} blocked {M['gate_blocked']}"
                if gate is not None else "")
        print(f"ep {ep} seed {seed} kicks {len(kicks)} succ {M['m1_success_rate']:.2f} exy {M['m1_exy_mean_mm']:.1f}mm "
              f"fallen {M['m7_fallen_count']} iou {M['m8_voxel_iou']:.2f}{gtxt}  ({M['wall_s']:.0f}s)")
    agg = {k: float(np.mean([r[k] for r in results])) for k in ["m1_success_rate", "m1_exy_mean_mm", "m2_level_range_max_mm",
                                                              "m3_plumb_mm", "m4_straightness_max_mm", "m6_through_joints",
                                                              "m7_fallen_count", "m8_voxel_iou"]}
    print("MEAN:", json.dumps(agg, indent=1))
    if a.out:
        Path(a.out).write_text(json.dumps({"episodes": results, "mean": agg, "config": vars(a),
                                         "metric_version": "oriented_polyhedron_v1",
                                         "condition": (f"policy+gate({a.gate_recover}" + (",release" if a.release_gate else "") + (",force" if a.gate_force else "") + (",replace" if a.gate_replace else "") + (f",noise{a.gate_pose_noise*1000:g}mm" if a.gate_pose_noise else "") + (f",inspect={a.gate_inspect}" if a.gate_inspect else "") + (",nominal-plan" if a.gate_nominal_plan else "") + ")") if a.grasp_gate else "policy"}, indent=1, default=float), encoding="utf-8")


if __name__ == "__main__":
    main()
