"""Presentation-only clips. Never trains or appends to benchmark result files."""
import os
os.environ.setdefault('MUJOCO_GL','egl')
os.environ.setdefault('HF_HUB_OFFLINE','1')
from pathlib import Path
import sys,json,subprocess,gc
import numpy as np
from PIL import Image,ImageDraw,ImageFont
import pyarrow.parquet as pq
import av

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'sim'))
OUT=ROOT/'발표자료_실험1_실험2_20260922'
VID=OUT/'발표용_영상'; IMG=OUT/'이미지'; META=OUT/'근거자료/영상_메타데이터'
for p in [VID,IMG,META]:p.mkdir(parents=True,exist_ok=True)
FONT=str(ROOT/'sim/tools/fonts/NotoSansKR-Regular.ttf')
F=ImageFont.truetype(FONT,18); FS=ImageFont.truetype(FONT,15)
W,H=1080,440

class Writer:
    def __init__(self,name,title,subtitle,fps=10):
        self.name=name;self.title=title;self.subtitle=subtitle;self.fps=fps;self.last=None
        self.p=subprocess.Popen(['ffmpeg','-y','-loglevel','error','-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}',
            '-r',str(fps),'-i','-','-an','-c:v','libx264','-preset','fast','-crf','22','-pix_fmt','yuv420p','-movflags','+faststart',str(VID/(name+'.mp4'))],stdin=subprocess.PIPE)
    def frame(self,images,labels,t,status='',snap=False):
        canvas=Image.new('RGB',(W,H),'#142338');d=ImageDraw.Draw(canvas)
        d.text((14,6),self.title,font=F,fill='white');d.text((14,31),self.subtitle,font=FS,fill='#c2d8e8')
        for k,img in enumerate(images):
            im=Image.fromarray(img) if isinstance(img,np.ndarray) else img
            im=im.resize((360,360),Image.Resampling.NEAREST if '원본' in self.subtitle else Image.Resampling.LANCZOS)
            canvas.paste(im,(360*k,60));d.text((360*k+8,64),labels[k],font=FS,fill='#142338',stroke_width=1,stroke_fill='white')
        d.rectangle((0,420,W,H),fill='#142338');d.text((12,421),f'{t:5.1f}s  |  {status}',font=FS,fill='white')
        self.p.stdin.write(canvas.tobytes());self.last=canvas
        if snap:canvas.save(IMG/f'{self.name}_t{t:05.1f}.png')
    def close(self,hold=10):
        if self.last:
            for _ in range(hold):self.p.stdin.write(self.last.tobytes())
        self.p.stdin.close()
        if self.p.wait():raise RuntimeError('ffmpeg failed')

def original(name,ds,ep,title,note):
    root=ROOT/'sim/data'/ds
    rows=[]
    for p in (root/'meta/episodes').rglob('*.parquet'):rows+=pq.read_table(p).to_pylist()
    row=next(r for r in rows if r['episode_index']==ep)
    cams=[c for c in ['front','top','wrist'] if f'videos/observation.images.{c}/from_timestamp' in row]
    views=[]
    for c in cams:
        key=f'videos/observation.images.{c}';start=row[key+'/from_timestamp'];end=row[key+'/to_timestamp']
        p=root/'videos'/f'observation.images.{c}'/f"chunk-{row[key+'/chunk_index']:03d}"/f"file-{row[key+'/file_index']:03d}.mp4"
        # Accurate timestamps: seek to preceding keyframe and decode the episode interval only.
        container=av.open(str(p));stream=container.streams.video[0];container.seek(int(start/stream.time_base),stream=stream)
        frames=[]
        for frame in container.decode(stream):
            t=float(frame.pts*stream.time_base)
            if t<start-0.0001:continue
            if t>=end-0.0001:break
            frames.append(frame.to_ndarray(format='rgb24'))
        container.close();views.append(frames)
    audit=json.loads((root/'episode_metrics.json').read_text());kept=[r for r in audit if r['kept']];r=kept[ep]
    writer=Writer(name,title,f'수집 당시 저장 영상 원본 128×128 확대 | seed {r["episode_seed"]} | {note}')
    n=min(len(v) for v in views)
    for i in range(0,n,2):
        ims=[v[i] for v in views]
        labels=[c.upper() for c in cams]
        if len(ims)==2:
            blank=Image.new('RGB',(360,360),'#edf2f7');dr=ImageDraw.Draw(blank)
            for j,s in enumerate(['실제 학습 영상','프레임 재생','상부 카메라 없음',f'episode index: {ep}',f'총 {n} frames']):dr.text((25,70+j*35),s,font=F,fill='#142338')
            ims.insert(1,blank);labels.insert(1,'RECORD')
        writer.frame(ims,labels,i/20,'학습 시연 원본 / 정책 결과 아님',i in [0,48,120,240,300,n-2])
    writer.close()
    meta=dict(name=name,kind='dataset_original',dataset=ds,episode_index=ep,seed=r['episode_seed'],frames=n,
              notes=note,audit=r,source_intervals={c:[row[f'videos/observation.images.{c}/from_timestamp'],row[f'videos/observation.images.{c}/to_timestamp']] for c in cams})
    (META/(name+'.json')).write_text(json.dumps(meta,ensure_ascii=False,indent=2))
    print('DONE original',name,flush=True)

def replay(name,title,seed,expert=False,run=None,exp=2,note='',source=None):
    import mujoco,torch
    from brick_sim.scene import BrickEnv,blueprint_config
    from brick_sim.expert import ScriptedExpert
    from brick_sim.metrics import compute_metrics,compute_metrics3
    from eval_policy import load_policy,camera_sources,build_obs
    torch.set_num_threads(1)
    cfg=blueprint_config('mortarB',size_rand=0,pos_rand=.03 if exp==2 else .005,supply_yaw_deg=60 if exp==2 else 10,valid_supply=exp==2)
    env=BrickEnv(cfg);env.reset(seed)
    renderer=mujoco.Renderer(env.model,360,360)
    writer=Writer(name,title,f'발표용 재실행 촬영 | 초기상태 seed {seed} | {note}')
    frames=[]; trace=[]
    def capture(status='',force=False):
        if env.t%2 and not force:return
        ims=[]
        for cam in ['front','top','wrist']:
            renderer.update_scene(env.data,camera=cam);ims.append(renderer.render().copy())
        grasps=[i for i in range(3) if env.grasped(i)]
        writer.frame(ims,['FRONT','TOP','WRIST'],env.t*.05,status+f' | 양턱 접촉: {grasps} | 고정: {np.where(env.cured)[0].tolist()}',
                     env.t in [0,48,90,120,190,238,244,300,360,600,1200,1798] or force)
        if env.t%10==0:trace.append(dict(t=env.t,poses=env.brick_poses().tolist(),grasped=grasps,jaw=float(env.data.qpos[env.jaw_qidx])))
    initial=env.brick_poses().copy();capture('초기 상태')
    if expert:
        ex=ScriptedExpert(env,seed=seed,max_retries=0,clean_single_pass=True)
        ex.run_episode(lambda obs,act,info:capture('수집 전문가 / 실패 시 종료'))
        extra=dict(expert_log=ex.log,unrecoverable=ex.unrecoverable,recoveries=ex.recoveries)
    else:
        ckpt=ROOT/'sim/outputs'/run/'checkpoints/last/pretrained_model'
        is_smol=run.startswith('smolvla');rename={f'observation.images.{a}':f'observation.images.camera{i+1}' for i,a in enumerate(['front','wrist','top'])} if is_smol else None
        policy,pcfg,pre,post=load_policy(str(ckpt),'cuda',rename,10 if exp==2 else None)
        cam=camera_sources(pcfg,rename);inference_seed=70000+(seed-50000) if exp==2 else 70000
        torch.manual_seed(inference_seed);torch.cuda.manual_seed_all(inference_seed);policy.reset()
        for t in range(1800):
            obs=build_obs(env,cam,pcfg)
            with torch.inference_mode():act=post(policy.select_action(pre(obs)))
            env.step(act.squeeze(0).detach().cpu().numpy());capture(f'{pcfg.type.upper()} / 정책 자율 실행')
        extra=dict(run=run,inference_seed=inference_seed,n_action_steps=pcfg.n_action_steps)
        del policy,pre,post;gc.collect();torch.cuda.empty_cache()
    before=env.brick_poses().copy();env.settle(50)
    M=compute_metrics(env.brick_poses(),env.design,env.brick,cfg.wall,poses_before_settle=before)
    M.update({'bp_'+k:v for k,v in compute_metrics3(env.brick_poses(),env.design,env.brick,cfg.wall).items() if k!='assignment'})
    capture(f'최종: 성공 블록 {round(M["m1_success_rate"]*3)}/3, xy 평균 {M["m1_exy_mean_mm"]:.1f} mm',True);writer.close(20)
    compare={}
    if source:
        eps=json.loads((ROOT/'sim/outputs'/source).read_text())['episodes'];original=next(e for e in eps if e['seed']==seed)
        compare=dict(original_success=original['m1_all_success'],original_xy_mm=original['m1_exy_mean_mm'],replay_success=M['m1_all_success'])
        if 'final_poses' in original:compare['max_abs_final_pose_difference']=float(np.max(np.abs(env.brick_poses()-np.array(original['final_poses']))))
    meta=dict(name=name,kind='expert_reconstruction' if expert else 'policy_checkpoint_replay',seed=seed,experiment=exp,notes=note,
              initial_poses=initial.tolist(),final_poses=env.brick_poses().tolist(),metrics=M,comparison=compare,source=source,**extra)
    (META/(name+'.json')).write_text(json.dumps(meta,ensure_ascii=False,indent=2))
    (META/(name+'_trace.json')).write_text(json.dumps(trace))
    renderer.close()
    if env.renderer:env.renderer.close()
    print('DONE replay',name,'success',M['m1_all_success'],'xy',M['m1_exy_mean_mm'],compare,flush=True)

def main():
    jobs=[
      ('original',dict(name='01_실험1_clean_정상시연_원본',ds='v2_2p1_joint_image_clean',ep=0,title='실험 1 | clean 데이터셋 시연',note='외부 교란 없음')),
      ('original',dict(name='02_실험1_mix_해제후교란과복구_원본',ds='v2_2p1_joint_image_mix',ep=2,title='실험 1 | 해제 후 교란·정지·복구가 포함된 과거 시연',note='12.2초 교란 / 재파지 구간 확인')),
      ('original',dict(name='03_실험1_plustop_복구시연_원본',ds='v2_2p1_joint_image_plustop',ep=119,title='실험 1 | 복구 시연과 상부 카메라',note='6.1초 집기 전 교란')),
      ('original',dict(name='04_실험2_clean_단회배치_원본',ds='v3_2p1_joint_image_clean',ep=0,title='실험 2 | 첫 파지 성공·해제 후 재배치 없는 보존 시연',note='첫 학습 에피소드 / 3개 모두 성공')),
      ('replay',dict(name='05_실험2_수집실패_첫파지_seed1001',title='실험 2 | 첫 파지 검증 실패로 폐기',seed=1001,expert=True,note='당시 실패 seed 재현 / 원본 영상은 폐기됨')),
      ('replay',dict(name='06_실험2_수집실패_두번째배치높이_seed1009',title='실험 2 | 두 번째 블록 해제 후 높이·기울기 실패',seed=1009,expert=True,note='약 12초 / 원인 후보: 이웃 블록 걸침')),
      ('replay',dict(name='07_실험2_수집제외_최종정밀도_seed1004',title='실험 2 | 동작은 완료했으나 최종 허용오차 초과',seed=1004,expert=True,note='단계 검사와 최종 성공 기준 차이')),
      ('replay',dict(name='08_실험1_ACT_clean_성공사례_seed10002',title='실험 1 | ACT clean 기준선 재생',seed=10002,exp=1,run='act_v2_2p1_joint_image_clean',source='eval_act_v2_2p1_joint_image_clean_mortarB.json',note='기존 학습 체크포인트 / 100스텝 실행')),
      ('replay',dict(name='09_실험1_Diffusion_plus2_정밀도확인_seed10000',title='실험 1 | Diffusion plus2: 적층 형상과 위치오차를 따로 확인',seed=10000,exp=1,run='diffusion_v2_2p1_joint_image_plus2',source='eval_diffusion_v2_2p1_joint_image_plus2_mortarB.json',note='확률 정책 재실행 예시 / 당시 경로와 다를 수 있음')),
      ('replay',dict(name='10_실험2_ACT_진행실패_seed50000',title='실험 2 | ACT: 파지·운반 단계 진행 확인',seed=50000,run='act_v3_2p1_joint_image_clean_seed1000',source='test_act_v3_2p1_joint_image_clean_seed1000.json',note='학습 seed1000 / 10스텝 실행')),
      ('replay',dict(name='11_실험2_Diffusion_성공사례_seed50002',title='실험 2 | Diffusion: 최종 성공 사례의 과정 확인',seed=50002,run='diffusion_v3_2p1_joint_image_clean_seed1000',source='test_diffusion_v3_2p1_joint_image_clean_seed1000.json',note='학습 seed1000 / 과정 준수는 별도 판정')),
      ('replay',dict(name='12_실험2_SmolVLA_진행실패_seed50000',title='실험 2 | SmolVLA: 미완료 사례',seed=50000,run='smolvla_v3_2p1_joint_image_clean_seed1000',source='test_smolvla_v3_2p1_joint_image_clean_seed1000.json',note='학습 seed1000 / 10스텝 실행')),
    ]
    for kind,kw in jobs:
        if (META/(kw['name']+'.json')).exists():continue
        (original if kind=='original' else replay)(**kw)
    (META/'jobs.json').write_text(json.dumps(jobs,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
