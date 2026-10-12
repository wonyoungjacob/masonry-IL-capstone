"""Camera-only feasibility runs; no privileged brick state in control or scoring.

Run from sim/ with venv/bin/python. Existing source files are not modified.
The existing RGB-D detector, gate gains/tolerances, scene and policies are reused.
Identity is assigned from initial image x order and tracked between camera frames.
Missing required observations STOP a rollout: no truth, cached pose or FK fallback.
The simulator still uses its state for physics and the existing layout sampler.
Absolute pose accuracy cannot be evaluated here: there is no reference measurement.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import contextmanager
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys
import time
from types import SimpleNamespace

SIM = Path.cwd().resolve()
if not (SIM / "brick_sim/scene.py").is_file():
    raise RuntimeError("Run from the repository sim/ directory")
sys.path.insert(0, str(SIM))

import numpy as np
from scipy.optimize import linear_sum_assignment

from brick_sim.scene import BrickEnv, blueprint_config, design_poses, JAW_OPEN, JAW_CLOSED
from brick_sim.perception import BrickPoseEstimator, MATCH_R
from brick_sim.grasp_gate import (
    GraspGate, _fold, _yaw, LOAD_LIFT, LOAD_MIN, LOAD_STEPS, PRESS_MIN,
    LIFT, HOVER, REPLACE_GRASP_TRIES, CHECK_LIFT, FIXED_PAD_X, PLACE_CLEAR,
)


class ObservationUnavailable(RuntimeError):
    pass


class ForbiddenTruthRead(RuntimeError):
    pass


def cfg_paper():
    return blueprint_config("mortarB", size_rand=0, pos_rand=.03,
                            supply_yaw_deg=60, valid_supply=True, feasible_supply=True)


def serial(v):
    if isinstance(v, np.ndarray):
        return v.tolist()
    if isinstance(v, np.generic):
        return v.item()
    raise TypeError(type(v).__name__)


def write_new(path, value):
    with Path(path).open("x", encoding="utf-8") as f:
        json.dump(value, f, indent=2, default=serial, allow_nan=False)


class SensorBackend:
    """Only this layer advances physics and renders raw simulation sensor data."""
    def __init__(self, seed):
        self.raw = BrickEnv(cfg_paper())
        self.raw.reset(seed)
        self.depth = 0
        self.physics_calls = Counter()
        self.forbidden = []
        # step() otherwise constructs and returns an unused privileged observation.
        self.raw.observe = lambda: {"observation.state": self.raw.qpos_arm()}
        for name in ("brick_pose", "brick_poses", "brick_vel", "brick_in_slot", "grasped", "env_state"):
            original = getattr(self.raw, name)
            def guarded(*args, _name=name, _fn=original, **kw):
                if not self.depth:
                    self.forbidden.append(_name)
                    raise ForbiddenTruthRead(_name)
                self.physics_calls[_name] += 1
                return _fn(*args, **kw)
            setattr(self.raw, name, guarded)
        # Renderer input is intentionally confined to the sensor backend. Geometry
        # fitting sees the drawing's dimensions/design, not sampled brick properties.
        self.sensor_view = SimpleNamespace(model=self.raw.model, data=self.raw.data, cfg=self.raw.cfg,
            t=self.raw.t, brick=self.raw.cfg.brick,
            design=design_poses(self.raw.cfg, self.raw.cfg.brick))
        self.estimator = BrickPoseEstimator(self.sensor_view)

    @contextmanager
    def physics(self):
        self.depth += 1
        try:
            yield
        finally:
            self.depth -= 1

    def step(self, action):
        with self.physics():
            self.raw.step(action)
        self.sensor_view.t = self.raw.t

    def close(self):
        self.estimator.close()
        if self.raw.renderer is not None:
            self.raw.renderer.close()
            self.raw.renderer = None


class CameraTracks:
    """Last images supply association priors only, NEVER a missing measurement."""
    def __init__(self, estimator, expected=3):
        self.est = estimator
        self.expected = expected
        self.last = {}
        self.current = {}
        self.key = None
        self.frames = []
        self.reads = []

    def update(self):
        t = int(self.est.env.t)
        if t == self.key:
            return
        ds = self.est.detect()
        self.key = t
        self.current = {}
        if not self.last:
            if len(ds) != self.expected or any(d["ambiguous"] for d in ds):
                raise ObservationUnavailable(f"initial image: expected {self.expected} unambiguous detections, got {len(ds)}")
            self.current = dict(enumerate(sorted(ds, key=lambda d: (d["pos"][0], d["pos"][1]))))
        elif ds:
            ids = sorted(self.last)
            costs = np.array([[np.linalg.norm(self.last[i]["pos"][:2] - d["pos"][:2]) for d in ds] for i in ids])
            # Dummy columns make an unmatched track preferable to a > MATCH_R link.
            padded = np.concatenate([costs, np.full((len(ids), len(ids)), MATCH_R)], axis=1)
            rows, cols = linear_sum_assignment(padded)
            for r, c in zip(rows, cols):
                if c >= len(ds) or costs[r, c] >= MATCH_R:
                    continue
                i, d = ids[r], ds[c]
                if d["ambiguous"]:
                    alt = d.get("alt")
                    if alt is None:
                        continue
                    prior = self.last[i]["yaw"]
                    if abs(_fold(alt["yaw"] - prior)) < abs(_fold(d["yaw"] - prior)):
                        d = {**d, **alt}
                self.current[i] = d
        self.last.update(self.current)
        self.frames.append({"t": t, "detections": len(ds), "tracked": sorted(self.current),
                            "full": sum(bool(d["full"]) for d in ds),
                            "ambiguous": sum(bool(d["ambiguous"]) for d in ds)})

    def pose(self, i):
        self.update()
        if i not in self.current:
            self.reads.append({"t": self.key, "track": i, "source": "missing"})
            raise ObservationUnavailable(f"t={self.key}: camera track {i} not visible/matchable; visible={sorted(self.current)}")
        d = self.current[i]
        self.reads.append({"t": self.key, "track": i, "source": "current_rgbd",
                           "full": bool(d["full"]), "ambiguous": bool(d["ambiguous"])})
        return np.array(d["pos"], copy=True), np.array(d["quat"], copy=True)


class CameraWorld:
    """Robot observations plus camera tracks. No raw brick state is exported."""
    def __init__(self, backend, tracks=None):
        self._backend, self.tracks = backend, tracks
        raw = backend.raw
        self.cfg = raw.cfg
        self.brick = self.cfg.brick
        self.design = design_poses(self.cfg, self.brick)
        self.n_bricks = len(self.design)
        self.model = raw.model              # robot IK geometry, never dynamic brick poses
        for name in ("arm_qidx", "arm_dofidx", "jaw_qidx", "act_ids", "tcp_site"):
            setattr(self, name, getattr(raw, name))

    @property
    def t(self):
        return self._backend.raw.t

    @property
    def data(self):
        raw = self._backend.raw
        q = np.zeros(raw.model.nq)
        # Give IK valid identity free-joint rotations, but ZERO object positions.
        for j in range(raw.model.njnt):
            if int(raw.model.jnt_type[j]) == 0:
                q[int(raw.model.jnt_qposadr[j]) + 3] = 1.0
        q[self.arm_qidx] = raw.data.qpos[self.arm_qidx]
        q[self.jaw_qidx] = raw.data.qpos[self.jaw_qidx]
        return SimpleNamespace(qpos=q, ctrl=raw.data.ctrl.copy())

    def qpos_arm(self):
        return self._backend.raw.qpos_arm()

    def wrist_ft(self):
        return self._backend.raw.wrist_ft()

    def gripper_mass(self):
        return self._backend.raw.gripper_mass()

    def tcp_pose(self):
        return self._backend.raw.tcp_pose()

    def render(self, cam):
        return self._backend.raw.render(cam)

    def step(self, action):
        self._backend.step(action)
        if self.tracks is not None:
            self.tracks.update()

    def brick_pose(self, i):
        if self.tracks is None:
            raise ObservationUnavailable("No tracker")
        return self.tracks.pose(i)

    def brick_in_slot(self, i, slots=None, **kw):
        # Reuse tolerance formula; its only pose input is this camera-only method.
        return BrickEnv.brick_in_slot(self, i, slots, **kw)

    def __getattr__(self, name):
        if name in {"grasped", "brick_poses", "brick_vel", "env_state", "cured", "bed_laid", "bed_mocap", "supply_poses"}:
            self._backend.forbidden.append("world." + name)
            raise ForbiddenTruthRead("world." + name)
        raise AttributeError(name)


def without_audit(value):
    if isinstance(value, dict):
        return {k: without_audit(v) for k, v in value.items() if k != "sim_grasped"}
    if isinstance(value, list):
        return [without_audit(v) for v in value]
    return value


class CameraGate(GraspGate):
    def __init__(self, world, policy, replace):
        super().__init__(world, policy, max_retries=0, recover="reguide", release_gate=True,
                         force=True, replace=replace, nominal_plan=True)
        self.pose_source = "strict_camera_current_rgbd"
        self.cam = world._backend.estimator

    def pose(self, i):
        return self.env.brick_pose(i)

    def _sim_grasped(self):
        return None                      # inherited event placeholder; stripped from output

    def unplaced(self):
        free = [i for i in range(self.env.n_bricks)
                if i not in self._released and self.env.brick_in_slot(i) is None]
        return sorted(free, key=lambda i: self.pose(i)[0][0])

    def _carry_monitor(self, jaw):
        if jaw < self.held_min:
            return "jaw"
        if not self.force or self.env.tcp_pose()[0][2] - self._carry_z < LOAD_LIFT:
            return None
        ld = self.load()
        if ld < -PRESS_MIN:
            if not self._pressing:
                self.events.append({"t": int(self.env.t), "jaw": round(jaw, 3), "held": True,
                    "action": "pressing", "load_N": round(ld, 3), "retry": self.retries})
            self._pressing, self._low_load = True, 0
            return None
        self._pressing = False
        self._low_load = self._low_load + 1 if abs(ld) < LOAD_MIN else 0
        return "load" if self._low_load >= LOAD_STEPS else None

    def _slot_target(self, k, held):
        env, D, B = self.env, *self._plan()
        dx, dy, dz, dyaw = D[k][:4]
        if dz < B.H:
            for kk in range(len(D)):
                if kk == k or D[kk][2] >= B.H:
                    continue
                neighbors = [j for j in range(env.n_bricks)
                             if j != held and env.brick_in_slot(j, [kk]) is not None]
                if neighbors:
                    dx = self.pose(neighbors[0])[0][0] + np.sign(dx - D[kk][0]) * (B.L + env.cfg.wall.head_gap + self.nbr_bias)
        else:
            zs = self.cam.surface_z(dx, dy)
            if zs is None:
                raise ObservationUnavailable(f"t={env.t}: upper-course support surface not visible")
            dz = zs + B.H / 2
        return np.array([dx, dy, dz]), float(dyaw)

    def _replace(self, i, k, act):
        # Same movements/thresholds as GraspGate._replace, without truth audit.
        env = self.env
        act[5] = JAW_OPEN
        self._lift(act, LIFT, 10)
        verdicts = []
        for _ in range(REPLACE_GRASP_TRIES):
            g, yaw_g, dz_grip = self._grasp_target(i)
            self._segments([(g + np.array([0, 0, HOVER]), yaw_g, JAW_OPEN, .8, "lin"),
                (g, yaw_g, JAW_OPEN, .6, "lin"), (g, yaw_g, JAW_CLOSED, .4, "lin")], act)
            jaw1, load = self._weigh(act)
            ok = jaw1 > self.held_min and (load >= LOAD_MIN or not self.force)
            verdicts.append({"jaw": round(jaw1, 3), "load_N": round(load, 3), "ok": bool(ok)})
            if ok:
                break
            act[5] = JAW_OPEN
            self._hold(act, 6)
            self._lift(act, LIFT, 10)
        else:
            return {"result": "grasp_failed", "grasps": verdicts}
        self._lift(act, HOVER - CHECK_LIFT, 10)
        target, dyaw = self._slot_target(k, i)
        yaw_p = yaw_g + _fold(dyaw - _yaw(self.pose(i)[1]))
        d_off = max(0.0, env.brick.W / 2 - FIXED_PAD_X)
        pz = target[2] + dz_grip + PLACE_CLEAR
        hover = np.array([target[0] + d_off * np.cos(yaw_p), target[1] + d_off * np.sin(yaw_p), pz + HOVER])
        self._segments([(hover, yaw_p, JAW_CLOSED, 1.2, "polar")], act)
        self._servo(i, target, dyaw, act, hold_z=True)
        p_b = self.pose(i)[0]
        down = env.tcp_pose()[0] + np.array([0., 0., target[2] + PLACE_CLEAR - p_b[2]])
        _, R = env.tcp_pose()
        self._segments([(down, float(np.arctan2(R[1, 0], R[0, 0])), JAW_CLOSED, .7, "lin")], act)
        ev = self._release(i, k, act)
        return {"result": "ok" if ev["post_release"]["ok"] else "still_bad", "grasps": verdicts, "second_release": ev}

    def summary(self):
        return {"pose_source": self.pose_source, "gate_events": without_audit(self.events),
            "release_events": without_audit(self.release_events), "gate_retries": self.retries,
            "gate_done": self.done, "gate_abort": self.aborted,
            "release_corrected": sum(bool(e.get("corrected")) for e in self.release_events),
            "post_release_replacements": len(self._replaced), "replace_enabled": self.replace,
            "nbr_bias_m": self.nbr_bias}


def camera_assessment(backend):
    """Current visible detections against the drawing; never a true success metric."""
    ds = backend.estimator.detect(force=True)
    D = backend.sensor_view.design
    out = {"source": "current_rgbd_vs_nominal_drawing", "absolute_accuracy_mm": None,
           "true_task_success": None, "visible_detections": len(ds), "slots": []}
    if ds:
        cost = np.array([[np.linalg.norm(d["pos"] - np.array(s[:3])) for d in ds] for s in D])
        rows, cols = linear_sum_assignment(cost)
        for k, j in zip(rows, cols):
            d, s = ds[j], D[k]
            exy = 1000 * float(np.linalg.norm(d["pos"][:2] - np.array(s[:2])))
            ez = 1000 * float(d["pos"][2] - s[2])
            eyaw = float(np.degrees(abs(_fold(d["yaw"] - s[3]))))
            out["slots"].append({"slot": int(k), "camera_exy_mm": exy, "camera_ez_mm": ez,
                "camera_eyaw_deg": eyaw, "full": bool(d["full"]), "ambiguous": bool(d["ambiguous"]),
                "camera_gate_tolerance_pass": bool(exy <= 4.5 and abs(ez) <= 3 and eyaw <= 5 and d["tilt_deg"] <= 5)})
    reliable = len(out["slots"]) == len(D) and all(s["full"] and not s["ambiguous"] for s in out["slots"])
    out["camera_all_slots_pass"] = all(s["camera_gate_tolerance_pass"] for s in out["slots"]) if reliable else None
    return out


def consistency(args):
    rows = []
    for seed in range(args.seed0, args.seed0 + args.episodes):
        b = SensorBackend(seed)
        try:
            for _ in range(5):
                b.step(b.raw.data.ctrl[b.raw.act_ids].copy())
            frames = [b.estimator.detect(force=True) for _ in range(3)]
            base = frames[0]
            drift = []
            count_stable = len(base) == 3 and all(len(ds) == len(base) for ds in frames)
            if count_stable:
                for ds in frames[1:]:
                    cost = np.array([[np.linalg.norm(d["pos"] - q["pos"]) for q in ds] for d in base])
                    ii, jj = linear_sum_assignment(cost)
                    drift.extend((cost[ii, jj] * 1000).tolist())
            rows.append({"seed": seed, "counts": [len(ds) for ds in frames],
                "three_detections_each_frame": count_stable, "full": sum(bool(d["full"]) for d in base),
                "ambiguous": sum(bool(d["ambiguous"]) for d in base), "repeat_displacement_mm": drift,
                "forbidden_truth_reads": b.forbidden,
                "initial_camera_estimates": [{k: d[k] for k in ("pos", "quat", "full", "ambiguous", "n_px")} for d in base]})
            print(f"CONSISTENCY seed={seed} count={[len(ds) for ds in frames]} full={rows[-1]['full']} forbidden={b.forbidden}", flush=True)
        finally:
            b.close()
    disps = [d for row in rows for d in row["repeat_displacement_mm"]]
    return {"status": "completed", "kind": "camera_count_and_frozen_scene_repeatability",
        "absolute_accuracy_mm": None, "precision_or_recall": None,
        "limitations": ["No independent reference, so no absolute accuracy or precision/recall is measured.",
            "Three detections is count consistency, not proof of correct object detection.",
            "Repeated ideal RGB-D renders of a frozen scene do not represent real sensor noise.",
            "No training or camera calibration changes; existing simulated RGB-D detector used."],
        "n_layouts": len(rows), "three_detections_layouts": sum(r["three_detections_each_frame"] for r in rows),
        "n_repeat_matches": len(disps), "repeat_displacement_max_mm": max(disps) if disps else None,
        "repeat_displacement_mean_mm": float(np.mean(disps)) if disps else None, "rows": rows}


def rollout(args):
    import torch
    from eval_policy import load_policy, camera_sources, build_obs
    ckpt = SIM / f"outputs/{args.policy}_v3_2p1_joint_image_clean_seed1000/checkpoints/last/pretrained_model"
    # Verify scene metadata directly; never use the legacy-scene fallback.
    train_cfg = json.loads((ckpt / "train_config.json").read_text())
    data_root = Path(train_cfg["dataset"]["root"])
    if not data_root.is_absolute():
        data_root = SIM / data_root
    recorded = json.loads((data_root / "collect_config.json").read_text())["scene"]
    from brick_sim.scene import SPEC_V2
    assert all(recorded.get(k) == v for k, v in SPEC_V2.items()), recorded
    policy, pcfg, pre, post = load_policy(str(ckpt), "cuda", n_action_steps=10)
    assert "observation.environment_state" not in pcfg.input_features
    cams = camera_sources(pcfg, None)
    rows = []
    for seed in range(args.seed0, args.seed0 + args.episodes):
        inf = 70000 + seed - args.seed0
        torch.manual_seed(inf)
        torch.cuda.manual_seed_all(inf)
        policy.reset()
        b = SensorBackend(seed)
        tracker = CameraTracks(b.estimator) if args.condition != "policy_only" else None
        world = CameraWorld(b, tracker)
        gate = CameraGate(world, policy, replace=args.condition == "prepost") if tracker else None
        start = time.monotonic()
        row = {"seed": seed, "inference_seed": inf, "status": "completed", "true_task_success": None}
        try:
            if tracker:
                tracker.update()
            while world.t < 1800:
                obs = build_obs(world, cams, pcfg)
                with torch.inference_mode():
                    act = post(policy.select_action(pre(obs))).squeeze(0).detach().cpu().numpy()
                if gate:
                    act = gate.before_step(act)
                    if act is None:
                        continue
                world.step(act)
                if gate and gate.after_step(act) in ("abort", "done"):
                    break
                if world.t % 200 == 0:
                    print(f"PROGRESS {args.policy} {args.condition} seed={seed} step={world.t}", flush=True)
            # Match the existing final settling period, using sensor-only backend.
            for _ in range(50):
                b.step(b.raw.data.ctrl[b.raw.act_ids].copy())
        except ObservationUnavailable as e:
            row.update(status="blocked_missing_camera_observation", reason=str(e))
        except ForbiddenTruthRead as e:
            row.update(status="blocked_forbidden_truth_read", reason=str(e))
        finally:
            row.update(steps=world.t, wall_s=time.monotonic() - start,
                       forbidden_truth_reads=b.forbidden, physics_truth_calls=dict(b.physics_calls))
            row["camera_assessment"] = camera_assessment(b)
            if gate:
                row["gate"] = gate.summary()
                row["camera_frames"] = tracker.frames
                row["camera_reads"] = tracker.reads
            # Preserve the actual camera image at completion/blockage for review.
            from PIL import Image
            rgb, _ = b.estimator.render()
            image_path = Path(args.out).with_name(Path(args.out).stem + f"_seed{seed}_top.png")
            with image_path.open("xb") as f:
                Image.fromarray(rgb).save(f, format="PNG")
            row["top_image"] = image_path.name
            b.close()
        rows.append(row)
        print(f"DONE {args.policy} {args.condition} seed={seed} status={row['status']} steps={row['steps']} forbidden={row['forbidden_truth_reads']} reason={row.get('reason', '')}", flush=True)
        if row["status"] != "completed":
            break                        # User: stop on a blocker, no workaround.
    return {"status": rows[-1]["status"], "policy": args.policy, "condition": args.condition,
        "checkpoint": str(ckpt.relative_to(SIM)), "input_features": list(pcfg.input_features),
        "requested_episodes": args.episodes, "completed_episodes": sum(r["status"] == "completed" for r in rows),
        "episodes": rows}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["consistency", "rollout"])
    ap.add_argument("--policy", choices=["act", "diffusion"])
    ap.add_argument("--condition", choices=["policy_only", "pre", "prepost"], default="prepost")
    ap.add_argument("--seed0", type=int, default=50000)
    ap.add_argument("--episodes", type=int, default=1)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    assert args.episodes > 0
    if Path(args.out).exists():
        raise FileExistsError(args.out)
    if args.mode == "rollout" and not args.policy:
        ap.error("--policy is required for rollout")
    res = consistency(args) if args.mode == "consistency" else rollout(args)
    res.update(scene=asdict(cfg_paper()), script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        config=vars(args), scope="No privileged brick state in perception association, control, or scoring. Simulator physics and original feasible-layout sampling retain internal state.")
    write_new(args.out, res)
    print(f"SAVED {args.out}", flush=True)
    if res["status"] != "completed":
        sys.exit(2)


if __name__ == "__main__":
    main()
