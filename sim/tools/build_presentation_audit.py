"""Read-only audit of existing Experiment 1/2 records for the presentation package."""
from pathlib import Path
import json, csv, hashlib, shutil, collections, re
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / '발표자료_실험1_실험2_20260922'
for folder in ['이미지', '발표용_영상', '근거자료', '재생성_도구']:
    (OUT / folder).mkdir(parents=True, exist_ok=True)

def read(p): return json.loads(p.read_text())
def csvwrite(name, rows):
    with (OUT/'근거자료'/name).open('w', encoding='utf-8-sig', newline='') as f:
        w=csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)

datasets=[]
for p in sorted((ROOT/'sim/data').glob('v[23]*/meta/info.json')):
    root=p.parents[1]
    if 'preview' in root.name: continue
    info=read(p); cfg=read(root/'collect_config.json'); audit=read(root/'episode_metrics.json')
    kept=[r for r in audit if r['kept']]
    datasets.append(dict(dataset=root.name, attempts=len(audit), kept=len(kept), frames=info['total_frames'],
        strict_success_kept=sum(r['m1_all_success'] for r in kept),
        disturbed_attempts=sum(bool(r.get('disturbances')) for r in audit),
        disturbed_kept=sum(bool(r.get('disturbances')) for r in kept),
        recovery_episodes=sum(bool(r.get('recoveries')) for r in kept),
        recovery_events=sum(r.get('recoveries',0) for r in kept),
        cameras=cfg['cams'] if cfg['obs_set']!='state' else 'none', config=cfg))

runs=[]
for p in sorted((ROOT/'sim/outputs').glob('*v[23]*/checkpoints/last/pretrained_model/train_config.json')):
    if 'preview' in str(p): continue
    cfg=read(p); name=p.parents[3].name; ds=Path(cfg['dataset']['root']).name
    info=next(x for x in datasets if x['dataset']==ds)
    frames=73200 if ds.startswith('v3') else info['frames']
    n_eps=200 if ds.startswith('v3') else info['kept']
    log=ROOT/'sim/logs'/f'train_{name}.log'; logtext=log.read_text() if log.exists() else ''
    ckstep=p.parents[1].resolve().name
    runs.append(dict(run=name, experiment=2 if ds.startswith('v3') else 1,dataset=ds,
        policy=cfg['policy']['type'], steps=cfg['steps'], checkpoint_step=ckstep,
        batch_size=cfg['batch_size'], seed=cfg['seed'], completed='End of training' in logtext,
        train_frames=frames, nominal_epoch=cfg['steps']*cfg['batch_size']/frames,
        sampled_epoch=cfg['steps']*cfg['batch_size']/(frames-n_eps*cfg['policy'].get('drop_n_last_frames',0)),
        n_action_steps=cfg['policy']['n_action_steps'], config=cfg))

evals=[]
for pattern,exp in [('eval_*v2*.json',1),('test_*v3*.json',2),('validation_*v3*.json',2)]:
    for p in sorted((ROOT/'sim/outputs').glob(pattern)):
        d=read(p); eps=d['episodes']; n=len(eps)
        evals.append(dict(file=p.name,experiment=exp,n=n,all_success=sum(e['m1_all_success'] for e in eps),
            iou=float(np.mean([e['bp_iou'] for e in eps])),E_h_mm=float(np.mean([e['bp_E_h_mm'] for e in eps])),
            E_f_mm=float(np.mean([e['bp_E_f_mm'] for e in eps])),
            xy_mm=float(np.mean([e['m1_exy_mean_mm'] for e in eps])),
            fallen_flag_episodes=sum(e['m7_fallen_count']>0 for e in eps),
            seed_min=min(e['seed'] for e in eps),seed_max=max(e['seed'] for e in eps),
            brick_success_counts=dict(collections.Counter(round(e['m1_success_rate']*3) for e in eps)),
            config=d.get('config',{})))

audit=read(ROOT/'sim/data/v3_2p1_joint_image_clean/episode_metrics.json')
fail=collections.Counter()
for r in audit:
    if r['kept']: fail['accepted']+=1;continue
    bad=next((e for e in r['expert_log'] if not e['ok']),None)
    fail[(bad['stage']+':'+bad.get('why','')) if bad else 'final_tolerance']+=1

snapshot=dict(datasets=datasets,runs=runs,evaluations=evals,collection_outcomes=dict(fail),
              stop=read(ROOT/'sim/outputs/clean_experiment_status.json'))
(OUT/'근거자료/audit.json').write_text(json.dumps(snapshot,ensure_ascii=False,indent=2))
csvwrite('데이터셋_전수목록.csv',[{k:v for k,v in r.items() if k!='config'} for r in datasets])
csvwrite('학습_전수목록.csv',[{k:v for k,v in r.items() if k!='config'} for r in runs])
csvwrite('평가_전수목록.csv',[{k:v for k,v in r.items() if k not in ['config','brick_success_counts']} for r in evals])

sources=[ROOT/x for x in ['01_사기설/계획서/26_2사기설개요.pdf','01_사기설/계획서/설계수행계획서_14조_통합최종본.pdf','01_사기설/진행보고/실험보고서.pdf','실험일지.md','00_공통/AI_HANDOFF.md',
    'sim/brick_sim/scene.py','sim/brick_sim/expert.py','sim/brick_sim/metrics.py','sim/brick_sim/volume.py',
    'sim/collect.py','sim/eval_policy.py','sim/run_clean_experiment.py','sim/outputs/clean_experiment_status.json',
    'sim/logs/test_diffusion_v3_2p1_joint_image_clean_seed1002.log']]
sources+=list((ROOT/'sim/outputs').glob('eval_*v2*.json'))+list((ROOT/'sim/outputs').glob('test_*v3*.json'))+list((ROOT/'sim/outputs').glob('validation_*v3*.json'))
for run in runs:
    checkpoint=ROOT/'sim/outputs'/run['run']/'checkpoints/last/pretrained_model'
    sources.extend(checkpoint/name for name in ['train_config.json','config.json','policy_preprocessor.json','policy_postprocessor.json'] if (checkpoint/name).exists())
for ds in datasets:
    sources.extend((ROOT/'sim/data'/ds['dataset']/x) for x in ['collect_config.json','episode_metrics.json','meta/info.json'])
hashes=[]
for p in sources:
    dest=OUT/'근거자료/원본기록'/p.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
    hashes.append(dict(path=str(p.relative_to(ROOT)),sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
csvwrite('출처_SHA256.csv',hashes)
print('Saved audit',OUT, 'datasets',len(datasets),'runs',len(runs),'evaluations',len(evals),'failures',dict(fail))
