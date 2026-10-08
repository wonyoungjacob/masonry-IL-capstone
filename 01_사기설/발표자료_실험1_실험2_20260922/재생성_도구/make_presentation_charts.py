from pathlib import Path
import json,re
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'발표자료_실험1_실험2_20260922';IMG=OUT/'이미지'
font_manager.fontManager.addfont(str(ROOT/'sim/tools/fonts/NotoSansKR-Regular.ttf'))
plt.rcParams.update({'font.family':'Noto Sans KR','axes.unicode_minus':False,'font.size':11,'axes.spines.top':False,'axes.spines.right':False,'figure.facecolor':'white','savefig.facecolor':'white'})
A=json.loads((OUT/'근거자료/audit.json').read_text()); E={r['file']:r for r in A['evaluations']}
def save(name):plt.tight_layout();plt.savefig(IMG/name,dpi=180,bbox_inches='tight');plt.close()
def ev(pol,ds,tail='mortarB'):return E[f'eval_{pol}_v2_2p1_joint_image_{ds}_{tail}.json']
colors=['#1d6d9e','#d47735','#467b63']
fig,axs=plt.subplots(1,2,figsize=(10,3.6))
labels=['ACT','Diffusion','SmolVLA\n20k','SmolVLA\n40k']
pols=['act','diffusion','smolvla','smolvla_full']
for ax,key,title in zip(axs,['all_success','iou'],['세 블록 모두 성공 (%)','평균 IoU (실험 1 지표)']):
 for j,tail in enumerate(['mortarB','mortarB_kick']):
  vals=[ev(p,'clean',tail)[key] for p in pols];x=np.arange(4)+(j-.5)*.34
  bars=ax.bar(x,vals,.32,color=['#1d6d9e','#b6ccd9'][j],label=['무교란','교란 1회'][j])
  ax.bar_label(bars,fmt='%.0f' if key=='all_success' else '%.3f',fontsize=9)
 ax.set_xticks(range(4),labels);ax.set_title(title);ax.set_ylim(0,110 if key=='all_success' else 1);ax.legend(fontsize=9)
save('그림01_실험1_정책비교.png')

fig,axs=plt.subplots(1,2,figsize=(10,3.5));ds=['clean','mix2','plus','plus2','plustop','plus2top']
for ax,key,title in zip(axs,['all_success','fallen_flag_episodes'],['세 블록 모두 성공 (%)','낙하 판정 에피소드 수 (실제 붕괴와 다름)']):
 for tail,c,l in [('mortarB','#1d6d9e','무교란'),('mortarB_kick','#d47735','교란 1회')]:
  vals=[ev('diffusion',d,tail)[key] for d in ds];ax.plot(ds,vals,'o-',color=c,label=l)
  for i,v in enumerate(vals):ax.annotate(str(v),(i,v),xytext=(0,6),textcoords='offset points',ha='center',fontsize=9)
 ax.set_title(title,fontsize=11);ax.set_ylim(-4,105 if key=='all_success' else 35);ax.legend(fontsize=9);ax.tick_params(axis='x',rotation=25)
save('그림02_실험1_안정성과정밀도.png')

fig,axs=plt.subplots(1,2,figsize=(10,3.3))
labels=['채택','첫 파지 실패','해제 후 검사 실패','최종 허용오차 탈락'];vals=[240,139,37,38]
bars=axs[0].barh(labels,vals,color=['#467b63','#b14f42','#d47735','#9a8237']);axs[0].bar_label(bars,padding=3);axs[0].set_xlim(0,280);axs[0].invert_yaxis();axs[0].set_title('실험 2 수집 시도 454회: 중복 없는 분류')
pols=['act','diffusion','smolvla'];counts=[]
for p in pols:
 rows=[r for r in A['evaluations'] if r['file'].startswith('test_'+p+'_')]
 n=sum(r['n'] for r in rows);s=sum(r['all_success'] for r in rows);counts.append((n,s))
bars=axs[1].bar(['ACT','Diffusion','SmolVLA'],[s/n*100 for n,s in counts],color=colors)
for b,(n,s) in zip(bars,counts):axs[1].text(b.get_x()+b.get_width()/2,b.get_height()+2,f'{s}/{n}\n{s/n*100:.1f}%',ha='center')
axs[1].set_ylim(0,50);axs[1].set_title('실험 2: 완료된 시험만 집계');axs[1].set_ylabel('전체 배치 성공률 (%)')
save('그림03_실험2_수집과정책결과.png')

audit=json.loads((ROOT/'sim/data/v3_2p1_joint_image_clean/episode_metrics.json').read_text())
fig,axs=plt.subplots(1,2,figsize=(10,3.5))
for kept,label,col in [(False,'폐기된 에피소드','#cf8a79'),(True,'채택된 에피소드','#306a94')]:
 pts=np.array([p[:2] for r in audit if r['kept']==kept for p in r['initial_poses']]);axs[0].scatter(pts[:,0]*1000,pts[:,1]*1000,s=7,alpha=.35,c=col,label=label)
 yaw=[abs(np.degrees(2*np.arctan2(p[6],p[3]))) for r in audit if r['kept']==kept for p in r['initial_poses']]
 axs[1].hist(yaw,bins=[0,15,30,45,60],alpha=.65,label=label,color=col)
axs[0].set_xlabel('초기 중심 x (mm)');axs[0].set_ylabel('초기 중심 y (mm)');axs[0].set_title('실험 2: 실제 초기 공급 위치');axs[0].legend(fontsize=8)
axs[1].set_xlabel('|초기 yaw| (도)');axs[1].set_ylabel('블록 출현 수');axs[1].set_title('성공 선별은 관측 분포도 바꾼다');axs[1].legend(fontsize=8)
save('그림04_실험2_초기분포와선별.png')

losses={};fig,axs=plt.subplots(1,3,figsize=(10,3.2))
for ax,p in zip(axs,pols):
 for seed in [1000,1001,1002]:
  f=ROOT/'sim/logs'/f'train_{p}_v3_2p1_joint_image_clean_seed{seed}.log'
  if not f.exists():continue
  vals=[(int(a),float(b)) for a,b in re.findall(r'step (\d+): eval_loss=([\d.eE+-]+)',f.read_text())]
  losses[f'{p}_{seed}']=vals
  ax.plot([a/1000 for a,b in vals],[b for a,b in vals],'.-',label=str(seed))
 ax.set_title(p.upper());ax.set_xlabel('학습 스텝 (천)');ax.set_ylabel('검증 loss (정책별 정의 다름)');ax.legend(fontsize=8)
save('그림05_실험2_검증손실.png');(OUT/'근거자료/검증손실.json').write_text(json.dumps(losses,indent=2))

fig,ax=plt.subplots(figsize=(9,3.2));bottom=np.zeros(3);totals=[]
for p in pols:totals.append(sum(r['n'] for r in A['evaluations'] if r['file'].startswith('test_'+p+'_')))
for k,col in enumerate(['#b14f42','#d47735','#a4baa1','#376f5d']):
 vals=[sum(r['brick_success_counts'].get(str(k),0) for r in A['evaluations'] if r['file'].startswith('test_'+p+'_')) for p in pols]
 bars=ax.barh(['ACT (300회)','Diffusion (200회)','SmolVLA (200회)'],np.array(vals)/totals*100,left=bottom,color=col,label=f'{k}개 성공')
 for i,v in enumerate(vals):
  if v:ax.text(bottom[i]+(v/totals[i]*100)/2,i,str(v),va='center',ha='center',fontsize=10)
 bottom+=np.array(vals)/totals*100
ax.set_xlim(0,100);ax.set_xlabel('시험 실행 비율 (%), 막대 안 숫자는 실행 횟수');ax.invert_yaxis();ax.legend(ncol=4,loc='upper center',bbox_to_anchor=(.5,1.3));save('그림06_실험2_완료블록수.png')
print('Charts created')
