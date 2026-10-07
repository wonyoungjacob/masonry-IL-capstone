"""One dataset, three policies, three independent training seeds. No parameter sweep."""
import argparse
import csv
import fcntl
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
DATASET = 'v3_2p1_joint_image_clean'
CAMERA_MAP = {'observation.images.front': 'observation.images.camera1',
              'observation.images.wrist': 'observation.images.camera2',
              'observation.images.top': 'observation.images.camera3'}
POLICIES = {'act': 40000, 'diffusion': 60000, 'smolvla': 20000}
STATUS = ROOT / 'outputs/clean_experiment_status.json'


def status(phase, **details):
    record = dict(time=datetime.now(timezone.utc).isoformat(), pid=os.getpid(), phase=phase, **details)
    tmp = STATUS.with_suffix('.tmp')
    tmp.write_text(json.dumps(record, indent=2))
    tmp.replace(STATUS)
    print(json.dumps(record), flush=True)


def run(cmd, log, timeout=1800):
    print('RUN', ' '.join(map(str, cmd)), 'LOG', log, flush=True)
    with log.open('a') as handle:
        proc = subprocess.Popen(cmd, cwd=ROOT, stdout=handle, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            while proc.poll() is None:
                time.sleep(5)
                if time.time() - log.stat().st_mtime > timeout:
                    os.killpg(proc.pid, signal.SIGTERM)
                    try:
                        proc.wait(timeout=30)
                    except subprocess.TimeoutExpired:
                        os.killpg(proc.pid, signal.SIGKILL)
                        proc.wait()
                    raise RuntimeError(f'No log progress for {timeout}s: {log}')
        except BaseException:
            if proc.poll() is None:
                os.killpg(proc.pid, signal.SIGTERM)
                proc.wait()
            raise
        if proc.returncode:
            raise RuntimeError(f'Command exited {proc.returncode}; see {log}')


def training_args(policy, seed, dataset=DATASET, smoke=False):
    steps = 2 if smoke else POLICIES[policy]
    tag = f'{policy}_{dataset}_seed{seed}' + ('_smoke' if smoke else '')
    cmd = [str(Path(sys.executable).with_name('lerobot-train')),
           f'--dataset.repo_id=local/{dataset}', f'--dataset.root=data/{dataset}',
           '--dataset.video_backend=pyav', f'--dataset.eval_split={0 if smoke else 1/6}',
           '--policy.device=cuda', '--policy.push_to_hub=false', '--policy.n_action_steps=10',
           f'--seed={seed}', f'--steps={steps}', f'--batch_size={16 if policy == "smolvla" else 32}',
           f'--num_workers={0 if smoke else 4}', '--wandb.enable=false', '--env_eval_freq=0',
           f'--eval_steps={0 if smoke else 5000}', '--max_eval_samples=2048',
           f'--log_freq={1 if smoke else 200}', f'--save_freq={steps if smoke else 10000}',
           f'--output_dir=outputs/{tag}', f'--job_name={tag}']
    if policy == 'smolvla':
        cmd += ['--policy.path=lerobot/smolvla_base', '--policy.empty_cameras=0',
                '--policy.train_expert_only=true', '--rename_map=' + json.dumps(CAMERA_MAP)]
    else:
        cmd += [f'--policy.type={policy}']
    return tag, cmd


def finalize_split():
    import numpy as np
    import pyarrow.parquet as pq
    from lerobot.datasets.compute_stats import aggregate_stats
    from lerobot.datasets.utils import serialize_dict

    root = ROOT / 'data' / DATASET
    info = json.loads((root / 'meta/info.json').read_text())
    if info['total_episodes'] != 240:
        raise ValueError(f"Expected 240 complete episodes, got {info['total_episodes']}")
    audit = json.loads((root / 'episode_metrics.json').read_text())
    kept = [r for r in audit if r['kept']]
    assert len(kept) == 240
    assert all(r['m1_all_success'] and not r['unrecoverable'] and not r['recoveries'] for r in kept)
    rows = []
    for path in (root / 'meta/episodes').rglob('*.parquet'):
        rows.extend(pq.read_table(path).to_pylist())
    stats = []
    for row in rows:
        if row['episode_index'] >= 200:
            continue
        episode_stats = {}
        for key, value in row.items():
            if key.startswith('stats/'):
                feature, name = key[len('stats/'):].rsplit('/', 1)
                episode_stats.setdefault(feature, {})[name] = np.asarray(value)
        stats.append(episode_stats)
    assert len(stats) == 200 and all(stats)
    original = root / 'meta/stats_all_episodes.json'
    if not original.exists():
        original.write_bytes((root / 'meta/stats.json').read_bytes())
    (root / 'meta/stats.json').write_text(json.dumps(serialize_dict(aggregate_stats(stats)), indent=2))
    manifest = dict(dataset=DATASET, train_episodes=list(range(200)), validation_episodes=list(range(200, 240)),
                    train_stats_only=True, attempted=len(audit), accepted=240,
                    training_seeds=[1000, 1001, 1002], validation_rollout_seeds=[40000, 40019],
                    final_test_seeds=[50000, 50099], n_action_steps=10, checkpoint_selection='fixed final step',
                    policies=POLICIES, pi0='deferred', metric_version='oriented_polyhedron_v1')
    (root / 'split_manifest.json').write_text(json.dumps(manifest, indent=2))
    (ROOT / 'outputs/clean_experiment_manifest.json').write_text(json.dumps(manifest, indent=2))


def summarize():
    rows = []
    for path in sorted((ROOT / 'outputs').glob(f'test_*_{DATASET}_seed*.json')):
        data = json.loads(path.read_text())
        eps = data['episodes']
        rows.append(dict(run=path.stem, n=len(eps),
                         iou=sum(e['bp_iou'] for e in eps) / len(eps),
                         E_h_mm=sum(e['bp_E_h_mm'] for e in eps) / len(eps),
                         E_f_mm=sum(e['bp_E_f_mm'] for e in eps) / len(eps),
                         all_success=sum(e['m1_all_success'] for e in eps),
                         regrasp_after_release=sum(bool(e['regrasped_after_release']) for e in eps),
                         success_without_regrasp=sum(e['m1_all_success'] and not e['regrasped_after_release'] for e in eps)))
    if rows:
        with (ROOT / 'outputs/clean_experiment_results.csv').open('w') as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--smoke', action='store_true', help='two-step GPU training check on existing one-episode preview')
    parser.add_argument('--start', action='store_true', help='detach the full pipeline and write its PID/log')
    a = parser.parse_args()
    os.chdir(ROOT)
    os.environ['MUJOCO_GL'] = 'egl'
    os.environ['PYTHONUNBUFFERED'] = '1'
    (ROOT / 'outputs').mkdir(exist_ok=True)
    (ROOT / 'logs').mkdir(exist_ok=True)
    if a.start:
        with (ROOT / 'logs/clean_experiment.log').open('a') as log:
            child = subprocess.Popen([sys.executable, '-u', str(Path(__file__).resolve())], cwd=ROOT,
                                     stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                                     start_new_session=True)
        (ROOT / 'outputs/clean_experiment.pid').write_text(str(child.pid))
        print(f'Started pipeline PID {child.pid}; log: {ROOT / "logs/clean_experiment.log"}', flush=True)
        return
    if a.smoke:
        for policy in POLICIES:
            tag, cmd = training_args(policy, 999, 'v3_2p1_joint_image_preview', smoke=True)
            if not (ROOT / 'outputs' / tag / 'checkpoints/last/pretrained_model').exists():
                run(cmd, ROOT / 'logs' / f'{tag}.log')
        print('All three GPU training smoke checks passed', flush=True)
        return
    lock = (ROOT / 'outputs/clean_experiment.lock').open('w')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    try:
        root = ROOT / 'data' / DATASET
        if not (root / 'split_manifest.json').exists():
            if not (root / 'episode_metrics.json').exists():
                status('collecting', dataset=DATASET, target=240)
                run([sys.executable, '-u', 'collect.py', '--task', '2p1', '--mortar', 'mortarB',
                     '--pos-rand', '.03', '--yaw-rand', '60', '--valid-supply', '--clean-single-pass',
                     '--cams', 'front,wrist,top', '--obs-set', 'image', '--episodes', '2000',
                     '--target-kept', '240', '--seed0', '1000', '--root', f'data/{DATASET}',
                     '--repo-id', f'local/{DATASET}'], ROOT / 'logs/collect_clean_v3.log')
            finalize_split()
        for seed in (1000, 1001, 1002):
            for policy in POLICIES:
                tag, cmd = training_args(policy, seed)
                checkpoint = ROOT / 'outputs' / tag / 'checkpoints/last/pretrained_model'
                log = ROOT / 'logs' / f'train_{tag}.log'
                if not (checkpoint.exists() and log.exists() and 'End of training' in log.read_text()):
                    status('training', policy=policy, seed=seed, steps=POLICIES[policy], log=str(log))
                    for attempt in range(3):
                        config = checkpoint / 'train_config.json'
                        current_cmd = ([cmd[0], f'--config_path={config}', '--resume=true'] if config.exists() else cmd)
                        try:
                            run(current_cmd, log)
                            break
                        except RuntimeError:
                            if attempt == 2 or not config.exists():
                                raise
                for phase, seed0, episodes in [('validation', 40000, 20), ('test', 50000, 100)]:
                    out = ROOT / 'outputs' / f'{phase}_{tag}.json'
                    if out.exists():
                        continue
                    status('evaluating', policy=policy, seed=seed, split=phase, episodes=episodes)
                    evaluate = [sys.executable, '-u', 'eval_policy.py', '--task', '2p1', '--mortar', 'mortarB',
                                '--ckpt', str(checkpoint), '--episodes', str(episodes), '--seed0', str(seed0),
                                '--size-rand', '0', '--pos-rand', '.03', '--yaw-rand', '60', '--valid-supply',
                                '--n-action-steps', '10', '--disturb', '0', '--out', str(out)]
                    if policy == 'smolvla':
                        evaluate += ['--rename-map', json.dumps(CAMERA_MAP)]
                    run(evaluate, ROOT / 'logs' / f'{phase}_{tag}.log')
                    summarize()
        status('complete')
    except Exception as error:
        status('failed', error=str(error))
        raise


if __name__ == '__main__':
    main()
