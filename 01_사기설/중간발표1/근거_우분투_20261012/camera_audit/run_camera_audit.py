"""Frozen vision/controller; write predictions first, references only for offline scoring.
Run from sim/. No training, no changes to the previous tracker or gate settings.
"""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path('outputs/midterm1_fix/camera_audit')
LEGACY = Path('outputs/midterm1_fix/camera_only')
sys.path.insert(0, str(LEGACY.resolve()))
from strict_camera_only import (SensorBackend, CameraWorld, CameraTracks, CameraGate,
    ObservationUnavailable, ForbiddenTruthRead, serial, cfg_paper, write_new)
import numpy as np


class OfflineRecorder:
    """Write-only sink. Returns no labels/errors/assignments to the running system."""
    def __init__(self, backend, prefix, seed):
        self.backend, self.seed = backend, seed
        self.seen = set()
        self.files = {k: Path(str(prefix) + '_' + k + '.jsonl').open('x')
                      for k in ('predictions', 'references', 'queries')}

    def append(self, name, row):
        self.files[name].write(json.dumps(row, default=serial, allow_nan=False) + '\n')

    def record(self, tracks, query=None, missing=False):
        b = self.backend
        key = f'{self.seed}:{b.raw.t}'
        if query is not None:
            self.append('queries', dict(key=key, track=int(query), missing=bool(missing)))
        if key in self.seen:
            return None
        ds = b.estimator.detect()
        fields = ('pos', 'quat', 'yaw', 'tilt_deg', 'full', 'ambiguous')
        pred = dict(key=key, seed=self.seed, step=int(b.raw.t),
                    detections=[{k:d[k] for k in fields} for d in ds],
                    tracks={str(i):{k:d[k] for k in fields} for i,d in tracks.current.items()})
        # Serialization completes BEFORE the reference state is read.
        self.append('predictions', pred)
        self.files['predictions'].flush()
        self._write_reference(key)
        self.seen.add(key)
        return None

    def _write_reference(self, key):
        # Privileged data is confined to this write-only auditing sink. It is never
        # returned to camera association, policy, gate, or episode stopping logic.
        raw = self.backend.raw
        poses = [raw.data.qpos[a:a+7].copy() for a in raw.brick_qadr]
        self.append('references', dict(key=key, poses=poses))

    def close(self):
        for f in self.files.values():
            f.close()


class AuditedTracks(CameraTracks):
    recorder = None

    def pose(self, i):
        try:
            value = super().pose(i)
        except ObservationUnavailable:
            if self.recorder:
                self.recorder.record(self, query=i, missing=True)
            raise
        if self.recorder:
            self.recorder.record(self, query=i)
        return value


class RecordedWorld(CameraWorld):
    recorder = None

    def step(self, action):
        super().step(action)
        if self.recorder and self.t % 5 == 0:
            self.recorder.record(self.tracks)


def run(args):
    policy = None
    if args.mode == 'rollout':
        import torch
        from eval_policy import load_policy, camera_sources, build_obs
        from brick_sim.scene import SPEC_V2
        ckpt = Path(f'outputs/{args.policy}_v3_2p1_joint_image_clean_seed1000/checkpoints/last/pretrained_model')
        tc = json.loads((ckpt/'train_config.json').read_text())
        scene = json.loads((Path(tc['dataset']['root'])/'collect_config.json').read_text())['scene']
        assert all(scene.get(k) == v for k,v in SPEC_V2.items()), scene
        policy, pcfg, pre, post = load_policy(str(ckpt), 'cuda', n_action_steps=10)
        assert 'observation.environment_state' not in pcfg.input_features
        cams = camera_sources(pcfg, None)
    rows = []
    for seed in range(args.seed0, args.seed0 + args.episodes):
        if policy:
            torch.manual_seed(70000 + seed - args.seed0)
            torch.cuda.manual_seed_all(70000 + seed - args.seed0)
            policy.reset()
        b = SensorBackend(seed)
        tracks = AuditedTracks(b.estimator)
        world = RecordedWorld(b, tracks)
        recorder = OfflineRecorder(b, ROOT/f'{args.name}_s{seed}', seed)
        tracks.recorder = world.recorder = recorder
        gate = CameraGate(world, policy, args.condition == 'prepost') if policy and args.condition != 'policy_only' else None
        row = dict(seed=seed, inference_seed=70000 + seed - args.seed0, status='completed')
        start = time.monotonic()
        try:
            if args.mode == 'spawn':
                for _ in range(5):
                    b.step(b.raw.data.ctrl[b.raw.act_ids].copy())
                tracks.update()
                recorder.record(tracks)
            else:
                tracks.update()
                recorder.record(tracks)
                while world.t < 1800:
                    obs = build_obs(world, cams, pcfg)
                    with torch.inference_mode():
                        action = post(policy.select_action(pre(obs))).squeeze(0).detach().cpu().numpy()
                    if gate:
                        action = gate.before_step(action)
                        if action is None:
                            continue
                    world.step(action)
                    if gate and gate.after_step(action) in ('abort', 'done'):
                        break
                    if world.t % 300 == 0:
                        print('PROGRESS',args.name,seed,world.t,flush=True)
                for _ in range(50):
                    world.step(world.data.ctrl[world.act_ids])
                recorder.record(tracks)
        except ObservationUnavailable as e:
            row.update(status='blocked_camera_tracking', reason=str(e))
            recorder.record(tracks)
        except ForbiddenTruthRead as e:
            row.update(status='blocked_forbidden_truth', reason=str(e))
        finally:
            row.update(steps=world.t, wall_s=time.monotonic()-start,
                controller_forbidden_truth_reads=b.forbidden,
                audit_reference_frames=len(recorder.seen),
                physical_world_truth_calls=dict(b.physics_calls))
            if gate:
                row['gate'] = gate.summary()
                row['camera_reads'] = tracks.reads
            recorder.close()
            b.close()
        rows.append(row)
        write_new(ROOT/f'{args.name}_s{seed}_episode.json',row)
        print('DONE',args.name,seed,row['status'],'steps',row['steps'],'audit_frames',row['audit_reference_frames'],flush=True)
        if row['status'] != 'completed':
            break
    paths = [Path(__file__), LEGACY/'strict_camera_only.py', Path('brick_sim/perception.py'),Path('brick_sim/grasp_gate.py')]
    write_new(ROOT/f'{args.name}_run.json',dict(config=vars(args),scene=asdict(cfg_paper()),episodes=rows,
        source_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
        reference_scope='Write-only recording AFTER prediction serialization; offline scoring in a separate process.'))


if __name__ == '__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('mode',choices=['spawn','rollout'])
    ap.add_argument('--name',required=True)
    ap.add_argument('--policy',choices=['act','diffusion'])
    ap.add_argument('--condition',choices=['policy_only','pre','prepost'],default='policy_only')
    ap.add_argument('--seed0',type=int,default=50000)
    ap.add_argument('--episodes',type=int,default=1)
    args=ap.parse_args()
    run(args)
