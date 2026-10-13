"""OFFLINE ONLY. Compare committed camera predictions with separately saved references."""
import json
from pathlib import Path
import sys
import numpy as np
from scipy.optimize import linear_sum_assignment

P=Path('outputs/midterm1_fix/camera_audit')
sys.path.insert(0,str(Path('outputs/midterm1_fix/camera_only').resolve()))
from strict_camera_only import _yaw, _fold, serial, cfg_paper
from brick_sim.scene import design_poses
from brick_sim.metrics import compute_metrics


def lines(p):
    return [json.loads(x) for x in p.read_text().splitlines() if x]


def stat(xs):
    return dict(n=len(xs),mean=float(np.mean(xs)) if xs else None,
                median=float(np.median(xs)) if xs else None,
                p95=float(np.percentile(xs,95)) if xs else None,
                max=float(np.max(xs)) if xs else None)


def score(run):
    det_xy=[]; det_xyz=[]; det_yaw=[]; track_xy=[]; query_xy=[]
    expected=observed=paired=within30=track_expected=tracked=wrong_id=frames=0
    full_xy=[]; partial_xy=[]; failed_queries=0; query_total=0
    episode_metrics=[]
    for ep in run['episodes']:
        stem=f"{run['config']['name']}_s{ep['seed']}"
        predictions=lines(P/(stem+'_predictions.jsonl'))
        refs={r['key']:r for r in lines(P/(stem+'_references.jsonl'))}
        assert len(predictions)==len(refs)==ep['audit_reference_frames']
        assert not ep['controller_forbidden_truth_reads']
        queries=lines(P/(stem+'_queries.jsonl'))
        track_map=None; errors={}
        for pred in predictions:
            gt=np.array(refs[pred['key']]['poses'])
            ds=pred['detections']; ts=pred['tracks']; frames+=1
            expected+=len(gt); observed+=len(ds); track_expected+=len(gt)
            if ds:
                xyz=np.array([d['pos'] for d in ds])
                cost=np.linalg.norm(xyz[:,None,:]-gt[None,:,:3],axis=2)
                di,gi=linear_sum_assignment(cost)
                for d,g in zip(di,gi):
                    delta=xyz[d]-gt[g,:3]
                    xy=float(np.linalg.norm(delta[:2])*1000)
                    det_xy.append(xy); det_xyz.append(float(np.linalg.norm(delta)*1000))
                    det_yaw.append(float(abs(np.degrees(_fold(ds[d]['yaw']-_yaw(gt[g,3:]))))))
                    (full_xy if ds[d]['full'] else partial_xy).append(xy)
                    paired+=1; within30+=int(cost[d,g] < .03)
            ids=sorted(ts,key=int)
            if ids:
                xyz=np.array([ts[i]['pos'] for i in ids])
                ti,gi=linear_sum_assignment(np.linalg.norm(xyz[:,None,:]-gt[None,:,:3],axis=2))
                best={ids[t]:int(g) for t,g in zip(ti,gi)}
                if track_map is None:
                    track_map=best.copy()   # scoring labels ONLY, never returned online
                for i in ids:
                    if i not in track_map:
                        continue
                    g=track_map[i]
                    err=float(np.linalg.norm(np.array(ts[i]['pos'])[:2]-gt[g,:2])*1000)
                    track_xy.append(err); tracked+=1
                    wrong_id+=int(best.get(i)!=g)
                    errors[(pred['key'],i)]=err
        for q in queries:
            query_total+=1
            if q['missing']:
                failed_queries+=1
            else:
                query_xy.append(errors[(q['key'],str(q['track']))])
        last=np.array(refs[predictions[-1]['key']]['poses'])
        cfg=cfg_paper()
        m=compute_metrics(last,design_poses(cfg,cfg.brick),cfg.brick,cfg.wall)
        episode_metrics.append(dict(seed=ep['seed'],status=ep['status'],steps=ep['steps'],
            true_completion_at_recorded_end=m['m1_all_success'],
            true_placement_xy_mean_mm=m['m1_exy_mean_mm']))
    return dict(config=run['config'],frames=frames,expected_brick_observations=expected,
        detections=observed,assigned_detections=paired,
        missing_detection_slots=expected-paired,extra_detections=observed-paired,
        assignments_within_30mm_3d=within30,
        detection_xy_mm=stat(det_xy),detection_xyz_mm=stat(det_xyz),detection_yaw_deg=stat(det_yaw),
        full_detection_xy_mm=stat(full_xy),partial_detection_xy_mm=stat(partial_xy),
        tracked_observations=tracked,expected_track_observations=track_expected,
        track_coverage=tracked/track_expected if track_expected else None,
        wrong_identity_observations=wrong_id,track_xy_fixed_identity_mm=stat(track_xy),
        gate_pose_queries=query_total,missing_gate_pose_queries=failed_queries,
        gate_query_xy_mm=stat(query_xy),episodes=episode_metrics,
        warnings=['Detection error uses one-to-one set assignment after prediction; all assigned errors are retained, including >30mm.',
          'Track error holds the first-frame offline identity mapping fixed; missing tracks are reported separately.',
          'Dynamic frames sampled every 5 control steps plus actual gate queries; not uniform weighting over time.',
          'Gate query error excludes missing queries, which are counted separately. Early stops truncate gated trajectories.',
          'Ideal simulated RGB-D and calibration, not real-camera accuracy.'])


if __name__=='__main__':
    reports=[]
    for f in sorted(P.glob('*_run.json')):
        r=score(json.loads(f.read_text())); reports.append(r)
        print(r['config']['name'],'frames',r['frames'],'det_xy',r['detection_xy_mm'],
              'track_coverage',r['track_coverage'],'gate_query_xy',r['gate_query_xy_mm'],flush=True)
    with (P/'offline_accuracy.json').open('x') as f:
        json.dump(dict(scoring='Offline only; references never sent to the running system.',runs=reports),f,indent=2,default=serial,allow_nan=False)
