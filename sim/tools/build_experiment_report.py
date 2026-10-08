"""Generate editable Korean Word report and a companion PDF from the same audited content."""
from pathlib import Path
import json, math, html, shutil
from collections import Counter
import numpy as np
from PIL import Image
from docx import Document
from docx.shared import Cm, Pt, RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.enum.text import WD_ALIGN_PARAGRAPH
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,PageBreak,Image as RLImage,KeepTogether
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.pagesizes import A4

ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'01_사기설'/'발표자료_실험1_실험2_20260922';IMG=OUT/'이미지'
A=json.loads((OUT/'근거자료/audit.json').read_text()); E={r['file']:r for r in A['evaluations']}
DS={r['dataset']:r for r in A['datasets']};LOSSES=json.loads((OUT/'근거자료/검증손실.json').read_text())
PAGES=[];blocks=None
def page(title,sub=''):
    global blocks
    blocks=[];PAGES.append(dict(title=title,subtitle=sub,blocks=blocks))
def p(s):blocks.append(('p',s))
def h(s):blocks.append(('h',s))
def table(headers,rows,widths=None):blocks.append(('table',(headers,[[str(x) for x in row] for row in rows],widths)))
def fig(pattern,caption):
    matches=sorted(IMG.glob(pattern));assert matches,pattern
    blocks.append(('fig',(matches[-1].name,caption)))
def note(s):blocks.append(('note',s))
def ev(pol,ds='clean',tail='mortarB'):return E[f'eval_{pol}_v2_2p1_joint_image_{ds}_{tail}.json']
def resrow(label,r):return [label,f"{r['all_success']}/{r['n']}",f"{r['iou']:.3f}",f"{r['E_h_mm']:.2f}",f"{r['E_f_mm']:.2f}",r['fallen_flag_episodes']]
def shortds(name):return name.split('joint_')[-1].replace('image_','').replace('state_clean','state')

page('모방학습 기반 조적 로봇 제어 시스템 설계','실험 1 · 실험 2 통합 보고서 | 사회기반시스템종합설계 · 14조')
p('정원영 · 강건 · 정성용 · 임수현 / 2026년 9월 22일 작성')
fig('04_*t018.2.png','실험 2에서 채택된 실제 시연 영상의 마지막 프레임. 정면·상부·손목 카메라. 합성 예시가 아닌 MuJoCo 수집 원본이다.')
h('보고 목적')
p('기존 다중 데이터셋 비교를 실험 1, 넓은 초기 배치와 단회 배치 시연으로 수행한 최근 실험을 실험 2로 정의한다. 환경·수집·학습·평가 기록을 재집계하고, 성능 저하의 관찰 사실과 원인 가설을 분리하여 다음 설계의 의사결정 근거를 제시한다.')
table(['구분','현재 확정할 수 있는 핵심'],[
 ['실험 1','좁은 초기 분포의 clean 조건: Diffusion 90/100, ACT 63/100 전체 배치 성공. 복구 추가는 일부 안정성 지표를 개선했지만 정확한 배치 성공을 일관되게 개선하지 못했다.'],
 ['실험 2','454회 수집 시도 중 240개 채택(학습 200/검증 40). 완료 시험에서 ACT 0/300, Diffusion 41/200, SmolVLA 0/200.'],
 ['중단 상태','2026-09-22 11:38 KST 사용자 요청으로 학습·평가 파이프라인 중단. 학습 8/9회, 최종 시험 7/9세트 완료. 미완료 결과는 성능 평균에서 제외.'],
 ['다음 의사결정','학습량 확대보다 수집 가능성, 파지 판정, 입력·행동 정합성, ACT 실행 주기의 원인을 먼저 분리한다. 이 보고서의 후속 설계는 제안이며 실행하지 않았다.']],[.18,.82])
note('이 문서의 실험 수치는 저장 JSON·메타데이터·체크포인트 설정을 기준으로 한다. 기존 보고서와 다른 수치는 정정 사항으로 설명한다. 실험 1·2는 조건과 IoU 구현이 달라 성능의 직접 증감 비교에 사용할 수 없다.')

page('1. 보고 범위와 과목 발표의 중심','단순 정책 순위보다, 요구조건에 맞는 제어 시스템을 어떻게 설계했는가')
h('1.1 실험의 경계')
table(['이름','포함 범위','제외·별도 표시'],[
 ['실험 1','scene spec v2의 9개 데이터셋과 ACT·Diffusion·SmolVLA 비교. 학습 완료 18회, 저장된 평가 37세트×100회.','v1 feeder 환경의 검증 데이터 6종과 평가 2건은 역사적 예비 자료. SmolVLA mix2 미완료 실행은 성능 비교 제외.'],
 ['실험 2','v3 이름의 통합 clean 데이터셋 1개. 물리 장면은 v2 mortarB를 유지하고 수집·랜덤화·평가를 변경.','1개 preview와 2스텝 smoke 학습은 실행 점검용이므로 본실험 개수에 포함하지 않음. π0 보류.']],[.14,.44,.42])
p('실험 1은 탐색적 개선의 연속이고 완전한 요인실험이 아니다. 실험 2는 데이터를 단순화하고 시드를 늘린 설계이나 여러 조건을 동시에 변경했으므로, 결과 저하를 특정 변경 하나의 인과효과로 해석할 수 없다.')
h('1.2 과목 안내 PDF를 반영한 발표 방향')
p('「26_2사기설개요.pdf」 2·5·6쪽은 기획–설계–제작의 전 과정과 발표를 강조한다. 12쪽은 단순한 실험을 넘어 최소 두 종류의 제한조건을 고려하도록 안내한다. 따라서 발표의 중심을 “어떤 모델이 이겼나”가 아니라 “모르타르 배치 제약을 만족하는 시스템을 만들기 위해 무엇을 바꾸었고 왜 실패했나”에 둔다.')
table(['설계 제한조건','현재 반영한 요소','아직 확인하지 못한 요소'],[
 ['공학적 성능·재료','배치 오차, 파지 성공, 그리퍼 해제 후 재조정 금지, 블록·그리퍼 간섭','실물 벽돌·모르타르의 거동, 접착·양생 모델의 물리적 타당성'],
 ['경제적 비용·시공성','재작업 억제 요구, 시연 폐기율 47.1%, 학습 자원·작업 횟수 관리','현장 인건비·원가·재료 낭비의 정량 절감액'],
 ['안전성(보조)','파지 실패와 운반 실패를 구분하려는 설계','실제 낙하 위험·사람과의 협업 안전성 검증']],[.21,.39,.40])
note('과목 안내 16쪽의 “표지 포함 10장·10분”은 설계수행계획서 발표 지침이다. 이를 모든 중간·최종 발표의 확정 규칙으로 확대하지 않는다. 본 보고서 말미의 10장 구성은 발표용 제안이다.')
h('읽는 순서')
p('공통 환경·지표 → 실험 1의 수집·학습·결과 → 실험 2의 변경·실패 → 중요한 구현·해석 실수 → 후속 설계 → 영상 안내 → 전수 결과표·출처 순서로 구성했다. 근거자료 폴더에는 재계산 CSV와 원본 기록 사본을 보존했다.')

page('2. 공통 실험 환경','실험 1과 실험 2가 공유하는 시뮬레이션 기반')
table(['항목','실제 설정'],[
 ['시뮬레이터·학습','MuJoCo 3.13 / LeRobot 0.6.1 / PyTorch 2.11+cu128 / RTX 5090 1장. 로컬 GPU 학습, EGL 렌더링.'],
 ['로봇·행동','SO-ARM100, 팔 관절 5개+그리퍼 1개. 6차원 관절 위치 목표를 제어기에 입력. 좌표 이동량이나 힘 명령이 아님.'],
 ['과제','동일 크기 블록 3개: 아래층 2개를 나란히 놓고 위층 1개가 줄눈을 가로지르는 2+1 적층.'],
 ['블록','90×42.632×27 mm, 밀도 1,800 kg/m³, 질량 약 0.1865 kg. 본실험 크기 랜덤화 0.'],
 ['목표 형상','벽 중심 y=-170 mm. 하부 중심 x=-145.5/-54.5 mm, z=13.5 mm. 상부 중심 x=-100 mm, z=45.237 mm. 목표 yaw=0°.'],
 ['줄눈·제어','머리줄눈 1 mm / 수평 모르타르층 명목 두께 4.737 mm. 물리 간격 1 ms, 행동 20 Hz(50 ms).'],
 ['입력','128×128 RGB 정면·손목 영상(+일부 상부), 관절 위치 6개. state 기준선은 영상 대신 특권 환경 상태 26차원+관절.'],
 ['공급','v2는 세 블록이 초기부터 작업 공간에 존재하는 scatter 방식. 순서가 되었을 때 순간이동하는 feeder 방식은 v1 예비 환경.'],
 ['평가 길이','최대 1,800 행동 스텝=90초 실행 후 50스텝=2.5초 정착. 완료 시 자동 종료하지 않음.']],[.23,.77])
fig('08_*t000.0.png','실험 1 초기 장면의 재실행 촬영. 세 공급 블록과 바닥 목표 표시가 처음부터 존재한다. 영상 08은 학습된 ACT의 재생이며, 상부 화면은 발표용 추가 관찰 시점이다.')
note('상부 화면을 발표 영상에 추가한 것과 정책이 상부 카메라를 입력으로 사용한 것은 다르다. 실험 1 clean ACT는 정면·손목 2대만 입력받는다. 세부 치수는 scene.py의 blueprint_config와 design_poses 기준.')

page('3. 물리 모델과 평가 지표의 정확한 의미','평가 수치가 무엇을 측정하고 무엇을 측정하지 않는가')
h('3.1 mortarB의 구현과 한계')
p('mortarB는 연성 접촉층과 정착 후 결합을 사용한다. 하부 두 블록이 목표 슬롯에 정착하면 그 위에 mocap 모르타르 받침 형상이 생성된다. 결합은 실제 벽돌 간 접촉면을 연결하는 방식이 아니라, 벽 영역에서 낮은 속도로 손과 떨어져 40 제어 스텝(2초) 머문 블록을 world에 weld하는 방식이다. 따라서 실물 모르타르의 접착·양생·파괴를 검증했다고 말할 수 없다.')
table(['지표','정의·해석'],[
 ['전체 배치 성공','최소거리 슬롯 대응 후 세 블록 모두 xy 오차<4.5 mm, |z 오차|<4.5 mm, |yaw 오차|<5°, tilt<10°. 4.5 mm는 블록 길이 5%인 내부 평가 문턱이며 실제 시공 허용기준의 인증값이 아니다.'],
 ['블록별 성공률','성공 블록 수/3. “전체 성공률”과 혼용하지 않는다.'],
 ['IoU','실제 블록 합집합과 설계 합집합의 교집합 부피/합집합 부피. 실험 1은 yaw 중심 복셀 근사, 실험 2는 전체 3차원 회전을 반영한 다면체 부피 구현.'],
 ['E_h (mm)','대응된 블록 중심 높이 절대오차의 평균. 실패·미완료 에피소드를 포함해 평균한다.'],
 ['E_f (mm)','설계 앞면 기준면에 대한 블록 앞면 코너의 최대 이격. 실험 1은 작은 y 좌표 4개 코너를 택하는 한계, 실험 2는 물리적 면을 선택.'],
 ['낙하 판정 F','m7_fallen_count>0인 에피소드 수. tilt>15° 또는 중심이 대응 슬롯보다 H/2 이상 낮으면 판정. 공급 위치에 남은 상부 블록도 포함하므로 “실제 붕괴 횟수”가 아니다.'],
 ['재파지 판정','양턱 접촉→그리퍼 열림→재접촉을 추적한 휴리스틱. 공급 위치에서 집기를 다시 시도한 것도 포함할 수 있어 “배치 완료 블록 재조정”과 동일하지 않다.']],[.23,.77])
h('3.2 지표 사이의 충돌을 숨기지 않는다')
p('형상은 서 있어도 x 방향으로 밀리면 E_h와 E_f는 양호하고 IoU·성공률은 낮을 수 있다. 반대로 최종 자세가 맞더라도 그 과정에서 해제 후 재조정했다면 사용자의 시공 요구에는 실패다. 따라서 최종 형상, 단계별 수행, 금지 행동 준수는 별도 평가 축이 필요하다.')
note('실험 1과 2의 IoU/E_f 평균을 직접 빼서 향상·악화량으로 보고하지 않는다. 기준이 공통인 전체 성공률도 초기 상태 분포·카메라·추론 간격이 달라 알고리즘 자체의 효과로 해석할 수 없다.')

page('4. 실험 1 — 데이터 수집과 분류','좁은 공급 분포에서 복구 시연의 양·포함 방식·관측 시점을 탐색')
p('감쇠 최소자승 IK 스크립트 전문가가 관측 가능한 규칙(초기 x가 작은 블록부터)으로 집기·운반·정렬·해제한다. 초기 공급 위치는 슬롯 주변 ±5 mm, yaw는 ±10°. 실패 시 블록당 최대 2회 재시도하고, 교란 후 다시 집거나 놓는 과정도 기록했다. 학습 입력에는 전문가가 쓰는 블록 참값이 일반적으로 포함되지 않는다.')
rows=[]
for name in ['clean','mix','mix2','robust','plus','plus2','plustop','plus2top','state']:
 d=DS['v2_2p1_joint_'+('state_clean' if name=='state' else 'image_'+name)]
 rows.append([name,f"{d['kept']}/{d['attempts']}",f"{d['strict_success_kept']}/{d['kept']}",f"{d['frames']:,}",f"{d['disturbed_kept']}",f"{d['recovery_episodes']}/{d['recovery_events']}",0 if name=='state' else len(d['cameras'].split(','))])
table(['세트','보존/시도','3개 성공/보존','프레임','교란 포함','복구 ep/횟수','카메라'],rows,[.13,.12,.15,.15,.13,.18,.14])
note('“복구 26/41개”라는 과거 표기는 엄밀히 26/41회 복구 이벤트였다. 해당 복구가 발생한 에피소드는 각각 23/36개다. mix 33/33, robust 66/76도 사건 수와 시연 수를 구분해야 한다.')
h('각 세트의 실질적인 차이')
p('clean: 외부 교란 없음. mix: 각 블록의 집기 전·해제 후에 확률 0.15를 반복 적용하고 교란 뒤 정지 구간 포함. mix2: 에피소드 기준 확률 0.30과 정지 0으로 수정. robust: 기회별 확률 0.40. plus/plus2: clean 시도 120회를 유지하고 항상 교란 시도 60/120회를 추가. plustop/plus2top: 대응하는 plus 세트와 같은 수집 설정에 top 카메라 추가. state: 영상 대신 참값 좌표 입력.')
p('실제 교란 비율은 mix 77/120회 시도(64.2%), 보존 중 70/113(61.9%); mix2 26/120(21.7%), 보존 중 19/112(17.0%); robust 114/120(95.0%), 보존 중 107/113(94.7%)다. 설정 확률·시도 비율·보존 비율을 서로 구분한다.')
h('수집 선별의 정정')
p('기존 필터는 stable AND 블록별 성공률≥0.5로, 세 블록 중 두 개만 맞아도 보존할 수 있었다. 실제 clean은 119개 중 118개만 전체 성공, plus2는 202개 중 166개만 전체 성공이었다. 과거 보고서의 “성공 시연만 보존”을 “완전 성공 시연만 보존”으로 이해하면 안 된다.')

page('5. 실험 1 — 학습 정책과 공통 학습 방식','고정 스텝의 오프라인 모방학습; 강화학습이나 온라인 보상 최적화가 아님')
table(['정책','입력·구조·학습 대상','시간 길이'],[
 ['ACT','ResNet18(ImageNet 초기화)+Transformer. hidden 512, heads 8, FFN 3200, encoder 4/decoder 1. CVAE latent 32, KL 가중치 10, dropout 0.1. L1 행동 재구성+KL.','관측 1프레임 / chunk 100 / 100스텝(5초) 실행 / temporal ensemble 미사용'],
 ['Diffusion','ResNet18 시각 인코더와 조건부 U-Net(512/1024/2048). DDPM, noise step 100, epsilon 예측, cosine beta. 관측 조건에서 행동 시퀀스의 노이즈 제거 학습.','관측 2프레임 / horizon 64 / 32스텝(1.6초) 실행 / 추론 step 별도 지정 없음'],
 ['SmolVLA 20k','lerobot/smolvla_base 미세조정. 비전 인코더·VLM을 고정하고 행동 expert 및 상태 투영 학습. 고정 영어 과제 지시문 사용.','관측 1프레임 / chunk 50 / 50스텝(2.5초) 실행 / flow 추론 10스텝'],
 ['SmolVLA 40k','train_expert_only=false로 언어 모델 쪽까지 학습 범위를 넓힘. freeze_vision_encoder=true 유지. 비전까지 전부 푼 “전체 모델 학습”은 아님.','chunk·실행 길이는 20k와 동일']],[.18,.56,.26])
table(['정책','스텝 / 배치','optimizer / lr / weight decay','scheduler'],[
 ['ACT','40,000 / 32','AdamW / 1e-5 / 1e-4','없음'],
 ['Diffusion','60,000 / 32','Adam / 1e-4 / 1e-6','cosine, warmup 500'],
 ['SmolVLA','20,000 또는 40,000 / 32','AdamW / 1e-4 / 1e-10','warmup 1,000, decay 설정 30,000, 최저 2.5e-6']],[.18,.21,.36,.25])
p('학습 seed는 모두 1000. dataset.eval_split=0으로 보존 데이터 전체를 학습에 사용했다. 독립 검증 시연 분할이 없고 완료 체크포인트를 비교했다. 평가 초기 seed 10000~10099는 수집 seed와 분리했으나 반복적인 실험 설계 선택에 같은 시험셋을 참조했으므로 독립적인 최종 검증으로 보기 어렵다.')
p('정규화는 ACT의 영상·상태·행동 mean/std, Diffusion의 영상 mean/std와 상태·행동 min/max, SmolVLA의 상태·행동 mean/std다. ImageNet 시각 통계를 사용하는 설정이며 일반 이미지 증강은 비활성화. SmolVLA의 camera1/2 이름에 정면·손목을 연결한다. 그라디언트 clipping norm은 10, mixed precision은 비활성화되어 있다.')
note('스텝은 optimizer update 횟수다. epoch를 직접 지정한 학습이 아니며, 다음 표의 환산 epoch는 스텝×배치/학습 프레임 수다. 정책별 스텝·배치·chunk가 다르므로 동일 계산 예산 비교도 아니다.')

page('6. 실험 1 — 실제 학습 실행 목록','체크포인트의 train_config.json 및 학습 로그 전수 확인')
rows=[]
for r in A['runs']:
 if r['experiment']!=1 or not r['completed']:continue
 label=r['policy']+(' (VLM 확장)' if r['run'].startswith('smolvla_full') else '')
 rows.append([label,shortds(r['dataset']),f"{r['steps']:,}",r['batch_size'],f"{r['train_frames']:,}",f"{r['nominal_epoch']:.2f}"])
table(['정책','데이터','스텝','배치','학습 프레임','환산 epoch'],rows,[.23,.18,.16,.10,.18,.15])
p('완료 실행은 ACT 8개, Diffusion 8개, SmolVLA clean 2개로 총 18개다. 기존 3쪽 PDF의 “학습 16회”는 현재 저장된 완료 로그와 맞지 않아 정정한다. 실험 1 v2 평가 JSON은 37개이며, v1 예비 평가 2개를 포함해야 종전 표현의 39개가 된다.')
p('SmolVLA mix2는 설정상 20,000스텝이나 정상 종료가 없고 last 체크포인트는 5,000스텝이다. 실행 흔적은 보존하되 완료 학습이나 비교 결과로 계산하지 않는다. 학습 종료 여부는 단순히 체크포인트 폴더 존재로 판단하지 않았다.')
note('Diffusion은 에피소드 마지막 7프레임을 학습 샘플 시작점에서 제외한다. 표는 로그와 대응하는 명목 epoch이며, 실제 샘플 후보 수에 대한 환산 epoch는 근거자료/학습_전수목록.csv의 sampled_epoch에 별도 기록했다. 반복 샘플링과 chunk padding 때문에 “모든 데이터가 정확히 N번 학습됨”을 뜻하지 않는다.')

page('7. 실험 1 — 정책 기준선 결과','동일한 clean 119개, 학습 seed 1000, 각 조건 100회 평가')
rows=[]
for pol,label in [('diffusion','Diffusion'),('act','ACT'),('smolvla','SmolVLA 20k'),('smolvla_full','SmolVLA 40k')]:
 for tail,cond in [('mortarB','무교란'),('mortarB_kick','교란')]:rows.append(resrow(label+' / '+cond,ev(pol,'clean',tail)))
table(['정책 / 조건','전체 성공','IoU','E_h mm','E_f mm','F'],rows,[.31,.15,.13,.13,.14,.14])
fig('그림01*','실험 1의 정책 비교. F는 낙하 판정 에피소드 수이며 실제 붕괴 횟수와 동일하지 않다. 모든 평균은 미완료 실행도 포함한다.')
p('관찰: clean·무교란에서 Diffusion의 최종 성공 90%가 가장 높고 ACT는 63%, SmolVLA는 0~2%였다. 교란 시 Diffusion도 28%, ACT 15%로 낮아졌다. 이 설정의 성능 순서는 확인되지만, 각 정책에 최적화된 튜닝·동일 예산·여러 학습 시드가 없으므로 알고리즘 일반 순위를 확정하지 않는다.')
p('SmolVLA의 40k 결과는 학습 기간과 학습 가능한 모듈을 동시에 바꾼 조건이다. 성능이 개선되지 않았다는 사실만으로 “VLM은 조적 작업을 할 수 없다” 또는 “데이터 개수만이 원인”이라고 결론내릴 수 없다.')

page('8. 실험 1 — 복구 시연과 관측 시점','Diffusion에서 “덜 실패 판정”과 “정확히 놓기”는 일치하지 않았다')
rows=[]
for ds in ['clean','mix','mix2','robust','plus','plus2','plustop','plus2top']:
 r=ev('diffusion',ds);rows.append([ds,f"{r['all_success']}/100",f"{r['iou']:.3f}",f"{r['xy_mm']:.2f}",r['fallen_flag_episodes']])
table(['데이터','전체 성공','IoU','평균 xy mm','F'],rows,[.24,.19,.19,.22,.16])
fig('그림02*','Diffusion의 복구 시연 비교. 안정성 판정의 개선을 전체 시공 성공의 개선으로 바꾸어 말하면 안 된다.')
p('plus2는 F=3/100이지만 전체 성공은 2/100이었다. plustop은 IoU=0.848, F=5/100으로 형상 지표는 좋았으나 전체 성공은 33/100으로 clean 90/100보다 낮았다. plus2top은 무교란 성공 0/100이었다. 배치 편향이 성공 문턱을 넘는 현상을 별도로 설명해야 한다.')
p('교란 조건에서도 clean의 전체 성공 28/100에 비해 plus 3/100, plus2 0/100, plustop 11/100이었다. 따라서 이 자료로 “복구 시연이 조적 작업의 종합 강건성을 입증했다”는 결론은 과도하다. 일부 보조 지표의 개선 및 관측 시점과의 상호작용을 시사하는 탐색 결과로 한정한다.')

page('9. 실험 1 — ACT 및 보조 조건','정면·손목만 볼 때와 상부 시점이 추가될 때의 차이')
rows=[]
for ds in ['clean','mix','mix2','robust','plus','plustop','plus2top']:
 r=ev('act',ds);k=ev('act',ds,'mortarB_kick');rows.append([ds,f"{r['all_success']}/100",f"{k['all_success']}/100",f"{r['iou']:.3f}",r['fallen_flag_episodes'],k['fallen_flag_episodes']])
table(['ACT 데이터','성공 무교란','성공 교란','IoU 무교란','F 무교란','F 교란'],rows,[.2,.17,.17,.16,.15,.15])
p('plus→plustop에서는 무교란 IoU 0.660→0.819, F 46→11로 변화했지만 전체 성공은 51→50으로 높아지지 않았다. 관측 시점이 형상·실패 양상에 영향을 주었을 가능성은 있으나 “상부 카메라가 반드시 있어야 한다”는 일반적 필요조건까지 입증한 결과는 아니다.')
table(['보조 비교','전체 성공','IoU','E_h mm','E_f mm','F'],[
 resrow('ACT image / mortarB',ev('act')),
 resrow('ACT state / mortarB',E['eval_act_v2_2p1_joint_state_clean_mortarB.json']),
 resrow('ACT image / mortarA',ev('act','clean','mortarA'))],[.31,.15,.13,.13,.14,.14])
p('state의 특권 정보가 이 구현에서 좋은 결과를 내지 못한 것은 확인된다. 그러나 상태 표현·네트워크 구조·정규화·용량·튜닝이 달라지므로 “참값 좌표보다 이미지가 본질적으로 낫다”는 결론은 성립하지 않는다.')
p('mortarA는 B 결합을 끈 보조 평가로, 같은 ACT 체크포인트의 성능이 63/100→45/100, E_f 8.68→25.44 mm로 달라졌다. 결합 모델에 대한 민감도는 보여주지만, 학습 환경과 시험 환경의 불일치 효과도 포함한다. 실제 모르타르가 성능을 얼마나 개선하는지 측정한 실험으로 해석하지 않는다.')
h('교란 평가의 범위')
p('에피소드당 한 번을 의도하여 t=40~399 중 무작위 시점에 손과 떨어져 있고 아직 고정되지 않은 블록을 선택한다. 평면 속도 0.3~0.5 m/s를 주며 tipping은 꺼져 있다. 전문가 수집 교란은 집기 전·해제 후의 특정 시점이며 일부 tipping도 있어, 훈련과 시험의 교란 분포가 완전히 일치하지 않는다.')

page('10. 실험 1 — 지지되는 결론과 과장된 결론','후속 설계의 출발점은 관찰의 범위를 정확히 정하는 것이다')
table(['관찰 사실','허용되는 해석','아직 입증되지 않은 주장'],[
 ['clean Diffusion 90%, ACT 63%','이 좁은 초기 분포·설정에서 Diffusion이 우수','모든 조적 과제에서 Diffusion이 ACT보다 우수'],
 ['mix→mix2 ACT 성공 21→49%','데이터 생성 수정 후 성능 회복','정지 프레임 제거 하나가 원인: 교란 확률·분포도 함께 변경됨'],
 ['plus→plustop IoU 개선','상부 관측이 일부 형상 실패를 줄였을 가능성','상부 카메라가 복구 학습의 필수조건'],
 ['plus2에서 F 감소, 성공 2%','불안정 판정과 배치 정확도 사이의 차이','복구 시연의 양이 많을수록 종합 강건성 향상'],
 ['SmolVLA 손실 감소, 성공 저조','오프라인 손실과 폐루프 성공은 다른 평가','시연 수 부족이 유일한 원인, 학습 자체는 완벽'],
 ['state 기준선 성능 낮음','이 표현·구조·설정의 기준선은 열세','특권 정보 일반의 무용성']],[.28,.34,.38])
h('실험 2로 이어진 설계 요구')
p('사용자는 현실의 모르타르 시공을 염두에 두어 그리퍼 해제 후 재조정을 금지하고, 첫 파지에 성공한 깨끗한 시연만 쓰기를 요구했다. 또한 많은 데이터 개수·복구 비율 case를 없애고 초기 공급 위치와 방향을 훨씬 넓히도록 했다. 실험 2는 이 요구를 반영한 설계 전환이지, 실험 1 복구 시연 가설을 한 변수만 바꾸어 검증한 반복 실험은 아니다.')
h('실험 1만으로 먼저 제안할 수 있었던 후속 검증')
p('데이터 수와 카메라 수를 고정한 상태에서 복구의 유무 한 가지만 비교하고, 여러 학습 시드 및 독립 시험셋으로 반복하는 검증이 필요했다. 다만 현재 사용자의 요구에서는 해제 후 재배치를 의도적으로 학습하는 조건을 채택하지 않는다. 복구 일반의 효용과 금지 동작의 허용 여부를 혼동하지 않는다.')
note('중요한 설계 실수: 사후적으로 여러 지표 가운데 좋아진 수치만 골라 권장 조합을 정하면 요구조건을 충족하지 못할 수 있다. “최종 허용오차 내 배치 + 해제 후 재조정 없음”을 선행 성공 정의로 고정해야 한다.')

page('11. 실험 2 — 환경 변경과 통합 데이터','한 데이터셋으로 단순화하고, 첫 파지·단회 배치를 요구')
table(['항목','실험 1','실험 2'],[
 ['초기 위치 / yaw','±5 mm / ±10°','±30 mm / ±60°'],
 ['초기 배치 검사','고정 슬롯 주변 샘플링','중첩·벽 영역·작업 반경 조건을 만족할 때까지 재추출'],
 ['공급 동작','v2 scatter','동일: 세 블록 모두 처음부터 존재'],
 ['시연 분류','9종, 교란·복구·카메라 조건','통합 clean 1종'],
 ['그리퍼 해제 이후','실패 또는 교란 시 재파지 허용','재파지·재배치 시연 금지, 실패 즉시 폐기'],
 ['수집 성공 정의','안정 판정 + 2개 이상 성공','첫 파지·운반·첫 배치 및 최종 3개 전체 성공'],
 ['정책 관측','대부분 2카메라, 일부 3카메라','정면·손목·상부 3카메라 공통'],
 ['물리·크기','v2 mortarB / 고정 크기','유지: 실제 모르타르 모델 개선은 보류']],[.26,.34,.40])
fig('그림04*','실험 2의 초기 분포. 각 점·빈도는 블록 출현이며 에피소드 단위 채택 여부로 색을 구분했다. 블록별 파지 성공률 그래프가 아니다.')
p('초기 기하 검사는 중심 반경 0.13~0.26 m, 벽 오른쪽과 모서리의 여유 15 mm, 블록 사이 분리 간격 10 mm를 사용한다. 이는 열린 그리퍼의 이동 부피나 전체 IK 경로의 실행 가능성을 보장하지 않는다. ±범위에서 뽑은 뒤 거절 샘플링하므로 실제 채택 분포는 단순 균등분포가 아니다.')
note('“초기 모양 랜덤화”는 현재 평면상의 위치와 yaw에 한정된다. 블록 크기·마찰·조명·카메라·초기 roll/pitch, 쌓인 공급 더미 등으로 일반화했다고 주장하지 않는다.')

page('12. 실험 2 — 시연 수집·선별·분할','실패 시연은 학습 데이터로 보존하지 않고 원인 로그만 보존')
table(['단계','수행 내용'],[
 ['생성','seed 1000부터 순차 시도. 총 시도 상한 2,000회, 목표 채택 240개. 실제 seed 1000~1453, 454회 시도 후 종료.'],
 ['첫 파지','접근·하강·닫기·들기 후 50스텝 시점에 블록 상승≥15 mm 및 양턱 접촉·TCP 근접 확인. 실패 즉시 종료.'],
 ['운반·해제 전','운반 및 정렬 중 매 스텝 파지 접촉 유지 확인. 놓기 전 공중 정렬·서보 보정은 허용. 접촉 소실 시 종료.'],
 ['해제 이후','해제·후퇴 후 배치 검사. 재시도 0, 외부 교란 0, 동작 노이즈 0. 실패해도 다시 들지 않음.'],
 ['최종 채택','세 블록 모두 최종 허용오차 충족, 안정 판정, unrecoverable/recoveries=0, 성공 grasp/release 로그 각각 3개.'],
 ['저장','240개 ×366프레임=87,840프레임, 20 Hz. 동작 18.3초/시연, 총 영상 시간은 카메라당 73.2분. 최종 정착 50스텝은 학습 프레임에서 제외.'],
 ['고정 분할','보존 episode 0~199: 학습 200개·73,200프레임(61분). 200~239: 검증 40개·14,640프레임(12.2분).'],
 ['정규화·시험','상태·행동 등 데이터 통계는 학습 200개로 집계. 검증 rollout seed 40000~40019, 시험 seed 50000~50099. 시험은 전문가 성공 여부로 걸러내지 않음.']],[.21,.79])
p('분할은 보존 순서의 앞 200개와 뒤 40개로 고정했다. 프레임을 무작위로 섞어 같은 에피소드가 학습·검증 양쪽에 들어가게 하지는 않았다. 다만 분포가 시드·수집 순서와 연관될 가능성, 검증 40개가 성공 선별 분포라는 한계는 남는다.')
p('학습 데이터에 깨끗한 동작만 넣었다는 것과 학습된 정책이 언제나 깨끗하게 동작한다는 것은 다르다. 파지 확인 장치는 전문가 수집 경로에만 구현되었다. 현재 정책 rollout에는 빈손 운반을 차단하거나 해제된 블록의 재접근을 금지하는 실행 제약이 없다.')
note('최종 그림만 맞춘 성공과 금지 동작을 지키며 한 번에 시공한 성공을 분리해야 한다. 현 시험 결과의 m1_all_success는 전자만 측정한다.')

page('13. 실험 2 — 수집 실패의 구조','454회 중 214회 폐기(47.1%): 데이터 수집기의 실행 가능성 문제부터 분리')
table(['중복 없는 분류','횟수','전체 시도 대비','의미'],[
 ['채택','240','52.9%','학습·검증에 사용'],
 ['첫 파지 검사 실패','139','30.6%','상승·접촉 조건 불충족. 어려운 기하 또는 판정 오검출 가능성을 분리해야 함.'],
 ['해제 후 단계 검사 실패','37','8.1%','z 34회, toppled 2회, xy 1회. 실패 후 재조정하지 않고 종료.'],
 ['동작 완료 후 최종 문턱 탈락','38','8.4%','중간 단계는 통과했지만 더 엄격한 최종 성공 기준에서 탈락.']],[.29,.11,.18,.42])
fig('그림03*','왼쪽: 수집 결과의 중복 없는 분해. 오른쪽: 수집 성공과 별개로, 학습된 정책의 완료 시험 성공률은 낮다.')
p('1순위 가설은 랜덤화 범위 확대에 비해 전문가의 파지·접근 경로가 충분히 일반화되지 않았다는 것이다. 초기 배치 검사는 블록끼리의 기하를 주로 검사하지만, 열린 그리퍼는 약 70 mm까지 벌어져 인접 블록과 충돌할 수 있다. 충돌·IK 도달성·파지 편향을 각 실패에서 따로 검증해야 한다.')
p('2순위 가설은 단계 판정의 민감도다. 파지는 상승 직후의 접촉 조건과 운반 중 매 프레임 접촉으로 판단한다. 실제 지지력이 유지되는데 접촉 신호가 잠시 사라지는 경우와 실제로 놓친 경우가 분리되지 않았다. 성공 시연도 7~8개의 IK 잔차 초과 스텝을 기록하므로 잔차 횟수만으로 실패 원인을 단정하면 안 된다.')
p('3순위는 배치 단계의 이웃 간섭이다. z 검사 실패 34회의 대표 seed1009에서 높이 오차 +13.07 mm, tilt 17.9°를 기록했고, 재현 영상에서 두 번째 블록이 이웃 끝에 걸친 모습이 보인다. 이 사례의 관찰을 모든 34회의 원인으로 일반화하지 않는다.')

page('14. 실험 2 — 학습 설정과 노출량','3개 정책 ×3개 학습 시드 계획; 완료된 8회만 사용')
table(['설정','ACT','Diffusion','SmolVLA'],[
 ['학습 스텝','40,000','60,000','20,000'],
 ['배치 크기','32','32','16'],
 ['chunk / horizon','100','64','50'],
 ['실행 길이','10스텝 / 0.5초','10스텝 / 0.5초','10스텝 / 0.5초'],
 ['관측 프레임','1','2','1'],
 ['명목 환산 epoch','17.49','26.23','4.37'],
 ['실제 샘플 후보 환산','17.49','26.74 (tail 7 제외)','4.37'],
 ['optimizer / lr','AdamW / 1e-5','Adam / 1e-4','AdamW / 1e-4'],
 ['학습 가능한 범위','ACT + ResNet18','U-Net + ResNet18','행동 expert + 상태 투영; VLM·비전 고정'],
 ['완료 학습 시드','1000,1001,1002','1000,1001,1002','1000,1001 (1002 미실행)']],[.29,.23,.24,.24])
p('공통: 동일 200개 학습·40개 검증, 3개 카메라, workers=4, video_backend=pyav, 일반 이미지 증강 비활성, AMP 비활성. 10,000스텝마다 저장하고 5,000스텝마다 최대 2,048 검증 샘플의 loss를 계산했다. 체크포인트 선택은 검증 최적값이 아니라 정해진 마지막 스텝이다. 각 정책의 구조·optimizer 세부값은 실험 1 설정을 대부분 유지했다.')
p('SmolVLA는 원본 이미지 128×128을 입력하지만 정책 내부 이미지 처리 설정은 resize_imgs_with_padding=[512,512]이며 카메라 feature 선언은 256×256이다. 이를 새로운 고해상도 관측을 수집한 것으로 해석하지 않는다. front/wrist/top→camera1/2/3 이름 대응을 사용했다.')
h('새로 발생한 학습량 교란 요인')
p('같은 40k/60k 스텝이라도 데이터가 늘어 ACT의 명목 노출량은 실험 1 clean 29.39→17.49 epoch로 감소했다. SmolVLA는 데이터 증가에 배치 32→16까지 겹쳐 14.69→4.37 epoch로 줄었다. 이 차이는 “깨끗한 데이터가 더 나빴다”는 인과 결론을 막는 요인이다. 증량 학습의 효과는 아직 검증하지 않았다.')
note('10스텝 공통화는 실행 주기를 맞추지만 알고리즘에 중립적인 최적 설정을 보장하지 않는다. 특히 ACT는 chunk 100 중 앞 10개만 실행한 뒤 새 관측에서 다시 예측하며 temporal ensemble이 없다.')

page('15. 실험 2 — 중단 시점과 확정 결과','2026-09-22 11:38 KST 중단 | 완료된 100회 시험 단위만 본표에 포함')
rows=[]
for r in A['evaluations']:
 if not r['file'].startswith('test_'):continue
 name=r['file'].split('_')[1];seed=r['file'].split('seed')[1].split('.')[0]
 rows.append(resrow(name+' / '+seed,r))
table(['정책 / 학습 seed','전체 성공','IoU','E_h mm','E_f mm','F'],rows,[.30,.16,.13,.13,.14,.14])
agg=[]
for pol in ['act','diffusion','smolvla']:
 rr=[r for r in A['evaluations'] if r['file'].startswith('test_'+pol+'_')];n=sum(r['n'] for r in rr);s=sum(r['all_success'] for r in rr)
 agg.append([pol.upper(),f'{s}/{n} ({100*s/n:.1f}%)',f"{np.average([r['iou'] for r in rr],weights=[r['n'] for r in rr]):.4f}",f"{np.mean([r['E_h_mm'] for r in rr]):.2f}",f"{np.mean([r['E_f_mm'] for r in rr]):.2f}"])
table(['완료 시험 합산','전체 성공','IoU','E_h mm','E_f mm'],agg,[.24,.28,.16,.16,.16])
h('미완료를 실패 0건으로 채우지 않는다')
p('Diffusion seed1002는 60k 학습과 검증 20회를 완료했으나 최종 시험 도중 중단됐다. 로그에 시험 3회 완료(seed50000~50002, 전체 성공 1회)가 남고 전체 JSON은 생성되지 않았다. 이것을 100회 결과처럼 쓰거나 3회 비율을 다른 모델과 직접 비교하지 않는다. SmolVLA seed1002는 학습을 시작하지 않았다.')
h('별도의 검증 rollout')
table(['정책','seed1000 /1001 /1002의 전체 성공','용도'],[
 ['ACT','0/20 · 0/20 · 0/20','검증 분포에서도 낮은 성능 확인'],
 ['Diffusion','6/20 · 5/20 · 7/20','seed1002 학습 완료 사실과 시험 미완료를 구분'],
 ['SmolVLA','0/20 · 0/20 · 미실행','학습 시연의 검증 loss와 별개인 폐루프 평가']],[.20,.43,.37])
note('ACT 300회는 서로 다른 초기 상태 300개가 아니다. 같은 100개 초기 seed를 세 학습 모델에 반복 적용했다. Diffusion·SmolVLA 200회도 같은 100개 상태×2개 모델이다. 단순 독립 Bernoulli 300회로 신뢰구간을 계산하지 않는다.')

page('16. 실험 2 — 낮은 성공률의 양상','ACT는 단순한 최종 mm 오차 초과만으로 설명되지 않는다')
fig('그림06*','최종 허용오차 안에 든 블록 개수의 분포. “0개 성공”은 전혀 움직이지 않았다는 뜻이 아니라, 최종 기준을 충족한 블록이 없다는 뜻이다.')
p('ACT는 300회 중 265회에서 성공 블록 0개, 33회에서 1개, 2회에서 2개였다. 대표 seed50000은 공급 위치 근처에서 진행하지 못하고, 90초 후에도 배치 미완료 상태였다. 이전 결과와 맞춰 촬영한 영상 10의 최종 자세는 저장 JSON과 정확히 일치한다.')
fig('그림05*','검증 loss 추이. 정책마다 손실 정의와 정규화가 달라 수치 크기를 정책 간 우열로 비교하지 않는다.')
p('ACT 마지막 검증 loss는 seed1000/1001/1002에서 0.0360/0.0323/0.0340이다. Diffusion은 0.0019/0.0025/0.0026, SmolVLA는 0.0174/0.0186이다. 작은 검증 손실은 성공 시연 분포에서 행동을 어느 정도 맞춘다는 뜻이며, 자율 실행 중 실패 상태에서 회복하거나 단계를 완료한다는 보장은 아니다.')
note('실험 2 정책 실패의 원인은 아직 확정되지 않았다. ACT의 앞 10스텝 반복 실행, 학습·배포 입력 불일치, 성공 선별로 생긴 분포 차이, 상대적으로 줄어든 데이터 노출량 등이 경쟁 가설이다. 보고서 작성 중에는 이 가설을 비교하는 새 학습을 시작하지 않았다.')

page('17. 시각 증거 — 수집기 실패와 판정 차이','동일 초기 seed를 재실행해 촬영한 사례; 당시 폐기 영상은 저장되지 않았음')
fig('06_*t011.9.png','영상 06, 약 11.9초: 두 번째 하부 블록이 이웃 블록 끝에 걸쳐 기울어진 장면. 당시 로그 t=244에서 z +13.07 mm, tilt 17.9°. 실패 후 재배치하지 않고 시연 종료.')
p('이 장면은 최종 위치를 향해 갔다는 사실만으로 올바른 배치가 보장되지 않음을 보여준다. 해제 전 블록 자세·이웃 모서리 간섭·그리퍼 여유를 확인할 설계 근거다. 해제 후 다시 들어 수정하는 방법은 현재 사용자 제약에 맞지 않는다.')
fig('07_*t020.8.png','영상 07, seed1004의 최종 상태: 세 번의 grasp/release 단계는 통과했지만 전체 성공은 2/3. 두 번째 배치의 xy 오차 약 4.86 mm가 최종 4.5 mm 문턱을 초과했다.')
p('단계 검사는 xy 8 mm, z 3 mm, yaw 10° 등을 허용하지만 최종 판정은 xy 4.5 mm, yaw 5° 등이다. 따라서 “모든 동작을 마쳤는데 왜 폐기되었나”를 설명하려면 중간 단계와 최종 기준을 분리해야 한다. 시연 분포를 더 깨끗하게 만드는 효과와 어려운 초기 상태를 제거하는 효과가 함께 발생한다.')

page('18. 시각 증거 — 학습 정책의 진행 실패','발표 영상의 대표 사례는 전체 실패 분포의 빈도를 대신하지 않는다')
fig('10_*t030.0.png','영상 10: ACT, 학습 seed1000 / 초기 seed50000. 30초에도 공급 영역에서 머물며 최종 세 블록 배치를 완수하지 못한다. 90초 실행 전체 영상 포함.')
p('관찰 사실은 공급 위치에서의 단계 진행 실패다. 이를 chunk 실행 길이 때문이라고 확정할 수는 없다. 학습된 같은 checkpoint의 실행 길이를 10/100으로 바꾸는 고정 검증 상태 진단이 이 가설을 구분하는 첫 실험이다.')
fig('12_*t030.0.png','영상 12: SmolVLA, 학습 seed1000 / 초기 seed50000. 공급 블록이 남아 있는데 그리퍼는 목표 영역으로 이동해 있는 장면. 최종 자세는 기존 평가 결과와 정확히 일치한다.')
p('깨끗한 파지 시연만으로 정책의 빈손 이동이 자동으로 차단되지는 않았다. “파지를 배운다”는 학습 목표와 “파지 확인 없이 운반하지 않는다”는 실행 안전 조건은 서로 다르다. 후속 설계에서는 순수 정책 성능과 파지 확인 제어기를 결합한 시스템 성능을 분리해 측정해야 한다.')

page('19. 발표에서 반드시 밝힐 실수와 정정','숫자 정정, 구현 한계, 인과 해석 한계를 구분')
table(['지점','확인 근거와 영향','다음 설계에서의 조치'],[
 ['완전 성공이 아닌 시연 보존','실험 1 collect 필터는 ≥2/3 성공. clean 118/119, plus2 166/202만 전체 성공.','3개 전체 성공·과정 준수 및 단계별 로그로 선별.'],
 ['복구 횟수와 시연 개수 혼동','plus: 26회 복구/23개 ep, plus2: 41회/36개 ep.','사건 수와 사건 포함 ep 수 각각 표기.'],
 ['교란 확률의 단위 혼동','기회별 0.15를 반복 적용. 보존 mix 61.9%, 시도 기준 64.2%.','episode 기준 draw·발생 시점·실제 발생률 기록.'],
 ['원인 하나로 단정한 수정','mix→mix2는 정지 프레임과 교란 분포를 함께 변경.','한 요인만 바꾸는 비교 또는 탐색적 결과로 제한.'],
 ['낙하와 미완료 혼동','F는 낮은 z와 tilt 판정. 공급 위치 미배치도 포함.','실제 파지 후 낙하·미파지·공급 잔류를 별도 검출.'],
 ['물리 모델의 목표 조건 개입','world weld 및 목표 슬롯 확인 후 bed 생성.','실제 접촉 기반 모델과 민감도 검증. 미검증 조건은 명시.'],
 ['실험 간 metric 버전 변경','실험 1 yaw 근사, 실험 2 full rotation. E_f 면 선택도 변경.','가능한 원시 자세를 공통 지표로 재평가한 뒤에만 직접 비교.'],
 ['수집기만 파지 검증','정책 rollout에는 실패 운반 차단이 없음.','정책 단독/제어기 결합 결과를 분리.'],
 ['동시 변경이 많은 실험 2','랜덤화·선별·분할·카메라·추론 주기·Smol 배치가 동시에 변경.','원인을 분리하는 최소 진단부터 수행.'],
 ['학습 시드·시험 재사용','실험 1 학습 seed 1개, 반복 설계에서 같은 시험 seed를 참조.','새 설계의 최종 holdout은 잠그고 개발은 검증 seed로 수행.']],[.23,.41,.36])
p('과거 인수인계에는 초기 평가에서 pre/post-processor를 누락해 정규화되지 않은 행동을 쓴 오류가 보고되어 있다. 현재 eval_policy.py에는 저장된 전처리·후처리 경로가 들어 있다. 이는 회귀 검사 대상으로 남길 이력이며, 이번 ACT 실패가 같은 버그 때문이라고 확인된 것은 아니다.')
note('이번 보고서에서 정정한 결론은 기존 PDF를 덮어쓰지 않고 별도 기록했다. 원 설계 PDF 및 과거 결과 파일은 그대로 보존했다.')

page('20. 실패 원인 가설 — 우선순위와 반증 방법','가설을 더 늘리기보다 어떤 검증으로 탈락시킬 것인지 명확히 한다')
table(['우선순위·가설','근거','구분 실험 / 반증 조건'],[
 ['1. ACT 실행 길이와 단계 진행','기존 100스텝 실행→10스텝. chunk 100·ensemble 없음. 대표 영상에서 공급 근처 정체.','같은 checkpoint·초기상태로 10 대 100만 변경. 파지 단계 완료율·행동 차이 비교. 차이가 없으면 주원인 가설 약화.'],
 ['2. 입력·행동 파이프라인 불일치','3개 학습 seed 모두 0%. 과거 전처리 누락 이력. 현재 경로는 존재.','저장 시연 상태에서 원본 프레임/정규화/카메라 순서/행동 단위/시간 정렬 비교. 전문가 action replay로 제어 경로 확인.'],
 ['3. 성공 선별의 분포 차이','학습은 성공 가능한 200개, 시험은 기하 조건만 만족한 전체 초기 분포. yaw 큰 시연의 채택 감소.','학습에 포함된 초기 seed와 고정 검증 seed 각각 rollout. 학습 상태에서도 실패하면 분포 차이만으로 설명 불가.'],
 ['4. 전문가의 넓은 파지 영역 미지원','수집 139회 첫 파지 실패. 열린 그리퍼 swept volume 미검사.','파지 시 접촉·상승·블록 간격·IK 잔차·각도별 실패 지도. 접촉 다중 프레임 판정과 실제 지지 상태 대조.'],
 ['5. 모방 오차 누적·실패 상태 부재','모든 학습 시연이 정상 완료 경로. 정책 오차로 방문한 상태의 정답 행동 부족.','정상 경로에서 최초 이탈 시점 측정. 해제 전 제한된 교정 시연 추가 여부 비교. 해제 후 재배치 금지 유지.'],
 ['6. 노출량·완료 처리 차이','ACT 17.49 epoch, Smol 4.37. 시연은 18.3초, rollout은90초이고 종료 없음.','프레임 노출량을 기록하고 시간별 배치 성공/금지행동 추적. 더 오래 학습하는 처방은 앞 진단 뒤 결정.']],[.28,.31,.41])
p('1번은 구현 선택을 가장 적은 비용으로 분리할 수 있어 우선한다. “짧은 재계획 간격은 항상 나쁘다”는 주장은 아니다. 2번은 영향이 커서 확인해야 하는 오류 가설이며 현재 발견된 버그가 아니다. 3~6번은 서로 동시에 작동할 수 있다.')
note('현재 확정한 것은 관찰된 실패 양상과 코드 설정의 차이까지다. 본 보고서 생성 과정에서는 10/100 진단, 재학습, 새 데이터 수집 실험을 실행하지 않았다.')

page('21. 다음 실험 설계 A — 재학습 전 진단','기존 checkpoint와 단일 통합 데이터 유지; 검증 단계에서만 원인 분리')
table(['순서','절차','기록·통과 기준(제안)'],[
 ['A0 데이터→제어 재생','학습 시연 10개를 초기 seed에서 재생하며 저장 action을 그대로 실행. 영상·관절·블록 최종 자세 비교.','정상 시연의 배치 재현 여부, 각도 단위·joint 순서·프레임 시점 일치. 오차 허용값은 수치 반복성 측정 후 사전 고정.'],
 ['A1 정책 입력 검사','동일 시점의 데이터와 rollout 관측을 전처리한 뒤 배열·범위·이름·차원 비교. action 후처리도 대조.','mean/std, min/max, 카메라 대응, HWC/CHW, 0~255/0~1, 입력-행동 지연의 체크 결과 표.'],
 ['A2 ACT 최소 이진 비교','학습 seed1000 checkpoint 고정. n_action_steps=10/100, 같은 검증 초기 seed40000~40019. 재학습 없음.','최초 파지·운반·해제·전체 배치 성공, 초기 정체 시간. 차이가 확인되면 다른 기존 학습 seed로 반복.'],
 ['A3 분포 분리','학습에 사용된 초기 상태 20개와 검증 상태20개에서 같은 정책 설정 실행.','훈련 상태 재현도 대 일반화 차이. 학습 상태에서도 실패하면 파이프라인·정책 학습 문제 우선.'],
 ['A4 수집기 실패 진단','기존 실패 seed 목록에서 grasp/z/final 유형을 소수 선택하여 접촉·거리·블록 상승을 기록.','실제 미파지와 접촉 판정 오검출 분리. 파지 가능성은 블록 간격만이 아닌 그리퍼 이동 경로로 검증.']],[.20,.43,.37])
p('A0/A1에서 정합성 오류가 확인되면 먼저 고친 뒤 동일 checkpoint로 평가를 재검증한다. A2에서 실행 길이에 따른 차이가 없으면 실행 주기 가설의 우선순위를 낮춘다. A3에서 학습 초기 상태만 잘 되면 시연 선택 편향과 분포 범위를 우선 개선한다. 이 단계는 대규모 학습 case를 늘리지 않는다.')
p('수집기의 파지 판정을 수정할 경우 기존 데이터의 의미가 달라지므로 새 버전을 부여하고 원본을 유지한다. 단순히 채택률을 높이려고 성공 기준을 느슨하게 하지 않는다. 최종 목표는 첫 파지 성공·운반 중 유지·정확한 첫 배치다.')

page('22. 다음 실험 설계 B — 요구조건 중심의 재설계','진단을 통과한 뒤 데이터셋 하나 또는 단 하나의 이진 비교만 수행')
h('B1. 통합 데이터셋 하나를 유지하는 기본안')
p('넓은 공급 위치·yaw와 초기부터 세 블록이 존재하는 조건은 유지한다. 공급 배치에 열린 그리퍼의 접근·회전 여유를 검사하고, 파지 후 확인 구간을 거쳐 운반한다. 해제 전에 블록 모서리·이웃 간섭·목표 오차를 줄여 한 번에 배치한다. 해제 후 재파지는 시연에 포함하지 않는다. 실패는 실패 유형·초기 자세와 함께 로그로 남기고 학습에서는 제외한다.')
p('수집 목표는 현재와 같은 학습 200개·검증 40개로 시작하되 숫자는 제안이다. 더 많은 데이터의 필요성은 진단 후 결정한다. 정책별 데이터셋을 쪼개지 않고, 분할·카메라·시뮬레이터·지표·종료 기준을 고정한다. 하이퍼파라미터 탐색을 시험셋으로 하지 않는다.')
h('B2. 꼭 비교가 필요할 때만 이진 데이터 설계')
table(['구분','공통','유일한 차이'],[
 ['A: 정상 단회 배치','같은 개수, 초기 분포, 관측, 첫 파지 성공, 해제 후 재조정 금지','정상 경로의 해제 전 정렬만 포함'],
 ['B: 해제 전 교정 포함','동일한 제한조건과 총 시연 수','파지에 성공한 뒤 작은 자세 오차를 가진 운반·배치 직전 상태에서 바로잡는 시연 포함']],[.26,.43,.31])
p('B의 교정은 이미 내려놓고 해제한 블록을 다시 드는 행동이 아니다. 사용자가 현재 원하지 않는 복구 비교이므로 즉시 수행하지 않으며, 기본안은 B1이다. 비교한다면 채택 수·초기 상태 분포를 맞춰 “데이터가 많아서 좋아진 효과”를 분리한다.')
h('B3. 평가 프로토콜 제안')
p('기존 50000~50099는 이미 결과를 확인한 개발 자료로 취급한다. 새로운 최종 시험 seed60000~60099를 잠그고 개발은 검증에서 수행한다. 학습 seed1000/1001/1002를 공통 사용하되 정책별 적정 실행 길이는 A2에서 고정한다. 처음부터 모든 정책·다양한 개수를 다시 학습하지 않고 ACT 기준선의 원인 수정 여부를 먼저 확인한다.')
p('최종 성공은 위치 허용오차뿐 아니라 최초 파지 성공, 운반 중 파지 유지, 최종 해제 후 재접촉·재배치 없음의 결합 조건으로 정의한다. 블록이 목표에 도달하기 전 공급 집기 재시도와 배치 후 재조정을 상태 전이로 구분한다. 순수 정책과 파지 확인 제어기를 붙인 시스템은 별도 결과표로 보고한다.')
note('예상 결과는 방향성 가설이다: 수집 단계의 실패 원인을 제거하면 채택률이 높아지고, 정책 입력·실행 문제를 고치면 초기 단계 완료율이 먼저 개선될 것으로 예상한다. 현재 자료로 목표 성공률이나 실물 성능을 약속하지 않는다.')

page('23. 논문 근거와 본 과제에서의 적용 범위','모방학습의 일반 원리를 모르타르 시공의 허용 행동과 구분')
table(['근거','본 보고서에 사용하는 범위','적용 한계'],[
 ['ACT, Zhao et al. (2023) [L1]','행동 시퀀스 학습은 정밀 조작의 누적 오차를 다루는 접근이다. chunk 길이와 실행 방식은 검증할 설계 변수다.','원 논문의 실물 과제 성능이 우리 환경에서 재현된다는 뜻은 아님.'],
 ['Diffusion Policy, Chi et al. (2023/2024) [L2]','관측 조건부 행동 분포 생성과 receding horizon 실행을 사용한다.','현재의 복구 시연 구성이 최적이거나 조적 특수 제약을 만족한다는 근거는 아님.'],
 ['DAgger, Ross et al. (2011) [L3]','학습 시연 분포와 학습된 정책이 방문하는 상태 분포의 차이가 모방학습의 중요한 문제다.','우리 실험은 DAgger를 구현한 것이 아니며, 정책 실패 원인이 분포 차이만이라는 증명도 아님.'],
 ['DART, Laskey et al. (2017) [L4]','시연 수집 중 교란으로 학습 정책이 방문할 상태를 다루는 시연을 얻는 접근이 있다.','현재 kick 방식은 DART의 최적화된 노이즈 수집 구현과 동일하지 않음. 해제 후 재배치 허용의 근거로 쓰지 않음.'],
 ['SmolVLA, Shukor et al. (2025) [L5]','사전학습 VLA를 제한된 로봇 자원에서 활용하는 비교 대안.','우리의 0~2% 결과는 이 태스크·적응 설정의 실패이며 VLA 전체의 한계가 아님.']],[.28,.36,.36])
p('따라서 “복구 시연이 일반적으로 도움이 될 수 있다”는 연구와 “이미 놓고 해제한 벽돌을 다시 들도록 학습해야 한다”는 주장은 다르다. 본 설계는 사용자의 시공 제약을 우선하여 해제 후 재조정을 허용하지 않고, 필요할 때만 해제 전 정렬·교정의 강건성을 검증한다.')
h('연구적 기여를 표현하는 방법')
p('현재 성과는 조적 작업의 제약을 데이터 수집 및 평가 정의로 옮기고, 성능 지표의 충돌과 실패 단계를 구체화한 시뮬레이션 제어 시스템이다. 새로운 학습 알고리즘의 우월성이나 실제 시공 자동화의 완성을 주장할 단계는 아니다. 다음 단계의 기여는 원인 분리와 요구조건을 만족하는 제어 절차의 실증이 된다.')
note('논문 제목·링크는 마지막 출처 목록에 제공했다. 관련 논문은 일반 원리의 근거이며 본 프로젝트 수치는 로컬 실험 기록만을 사용했다.')

page('24. 발표 구성 제안','10장 예시: 결과가 나빴다는 사실을 설계 의사결정으로 연결')
table(['장','핵심 메시지','추천 그림·영상'],[
 ['1','목표: 모르타르 조건에서 다시 들지 않고 정확히 놓는 조적 로봇','보고서 표지 및 정상 시연 04'],
 ['2','설계 제한조건: 배치 품질, 재작업 억제, 파지 유지','환경 설정 표 / 목표 형상'],
 ['3','실험 1: 좁은 초기 분포에서 정책과 복구 시연을 탐색','그림01 정책 비교'],
 ['4','지표가 말하는 것은 다르다: 덜 불안정해도 정확하지 않을 수 있다','그림02 / 영상09 마지막 상태'],
 ['5','실험 1의 한계를 바탕으로 요구조건을 다시 정의','해제 후 복구 영상02 → 금지 요구'],
 ['6','실험 2: 데이터1개·강한 랜덤화·성공 시연만','그림04 / 영상04'],
 ['7','수집 실패: 214/454, 파지와 배치를 나눠 봐야 한다','영상05,06 / 그림03 왼쪽'],
 ['8','학습 정책 실패: ACT 0%, 단계를 진행하지 못함','영상10 핵심 구간 / 영상12 빈손 이동'],
 ['9','경쟁 가설과 최소 진단: 입력 정합성, 10/100, 선택 편향','20~21절 가설-검증 표'],
 ['10','다음 설계: 해제 전 정확한 정렬·파지 확인·과정 성공 평가','22절 평가 프로토콜과 예상 결과']],[.08,.55,.37])
h('발표에서 강조할 문장')
p('“실험 1에서 안정성 지표 개선을 정확한 시공 성공과 혼동한 부분을 발견했습니다. 실험 2에서는 단회 배치 요구를 데이터에 반영했지만, 파지 확인을 시연 생성기에만 넣었기 때문에 학습 정책의 수행을 보장하지 못했습니다. 다음 단계는 모델을 더 오래 학습시키는 것이 아니라, 실패가 시작되는 지점을 분리해 요구조건을 제어·평가에 함께 반영하는 것입니다.”')
h('질의응답 준비')
p('왜 ACT가 0%인가? → 원인은 미확정이며 실행 길이·입력 정합성·분포 차이를 우선 분리한다. 왜 재조정 시연을 뺐나? → 모르타르 시공 요구조건이며 금지 행동의 빈도로도 평가해야 한다. 왜 실험 1과 직접 비교하지 않나? → 초기 분포·데이터 필터·카메라·실행 주기·지표 구현이 함께 달라졌다. 실제 시공 가능성을 입증했나? → 아직 시뮬레이션 단계이며 물리 모델과 현장 검증이 남았다.')

video_notes=[
 ('01','정상 시연 기준','0~18초','실험1 clean 수집 원본. 성공 동작의 길이·집기 순서를 확인.'),
 ('02','해제 후 교란·복구','10~20초','12.2초 교란 이후 정지·재파지 구간. 현재 금지 요구와 대비.'),
 ('03','상부 카메라·복구','5~16초','집기 전 교란 이후 복구를 3개 시점에서 확인.'),
 ('04','단회 배치 시연','0~18초','실험2 보존 데이터. 첫 파지 성공 및 해제 후 재배치 없음.'),
 ('05','첫 파지 실패','0~3초','seed1001 재현. 파지 검사 실패. 실제 미파지와 접촉 판정 오류는 추가 진단 필요.'),
 ('06','이웃 블록 걸침','9~12초','seed1009 재현. 해제 후 높이·기울기 실패. 다시 들지 않고 종료.'),
 ('07','최종 문턱 탈락','10~18초','seed1004 재현. 동작 완료와 최종 허용오차 만족은 별개.'),
 ('08','실험1 ACT 성공','0~25초, 마지막','기존 ACT seed10002 재생. 당시 성공·평면오차와 일치.'),
 ('09','적층과 정밀도 구분','마지막 5초','실험1 Diffusion plus2 재생 예시. 당시와 경로·수치는 다를 수 있음.'),
 ('10','실험2 ACT 정체','0~15초, 30초 이후','공급 영역에서 진행하지 못함. 저장 최종 자세와 정확히 일치.'),
 ('11','실험2 Diffusion 성공','0~35초, 마지막','최종 성공 사례. 과정 준수와 공급 집기 재시도를 별도로 볼 것.'),
 ('12','실험2 SmolVLA 미완료','0~15초, 30초','블록은 공급 위치, 그리퍼는 목표 위치인 장면. 저장 최종 자세와 일치.'),
]
page('25. 발표용 영상 찾기','발표용_영상 폴더의 00_영상목록.html을 열면 바로 재생 가능')
table(['파일 번호','볼 지점','추천 구간','설명'],video_notes,[.12,.22,.21,.45])
p('01~04는 당시 데이터셋 MP4에서 해당 에피소드의 구간을 잘라 합친 원본 영상이다. 화면은 128×128을 확대했다. 05~07은 당시 폐기 seed와 현재 동일 수집 설정으로 재현한 촬영이며, 당시 저장 영상으로 오해하지 않도록 자막을 넣었다. 08~12는 보존 checkpoint를 재실행한 발표용 촬영이다.')
p('정책 재생은 최대 90초 전체 동작을 포함한다. 행동 중 영상은 10 fps로 표시하고 끝에서 정착 후 최종 화면을 붙였다. 화면의 시뮬레이션 시간은 마지막 정착 2.5초만큼 건너뛸 수 있다. 재생 촬영 결과는 원 시험 집계에 섞지 않았다.')
note('발표 영상은 현상의 예시를 의도적으로 선택했다. 성공·실패 빈도는 앞의 전수 결과표로 판단한다. 영상11은 Diffusion의 확률적·수치적 차이로 최종 자세가 미세하게 달라졌으나 전체 성공 판정은 일치한다. 과거 실험1 Diffusion 영상09는 당시 난수 상태가 저장되지 않아 동일 경로 재현이라고 주장하지 않는다.')

for subset,title in [(lambda r: r['file'].startswith('eval_act_'),'부록 A. 실험 1 전수 평가 — ACT'),(lambda r: not r['file'].startswith('eval_act_'),'부록 B. 실험 1 전수 평가 — Diffusion·SmolVLA')]:
 page(title,'저장된 v2 평가 JSON 전체 | 각 행 100회 | F=낙하 판정 에피소드 수')
 rows=[]
 for r in A['evaluations']:
  if r['experiment']!=1 or not subset(r):continue
  name=r['file'].replace('eval_','').replace('_v2_2p1_joint_image_',' / ').replace('_v2_2p1_joint_state_',' / state_').replace('_mortarB_kick.json',' / B교란').replace('_mortarB.json',' / B').replace('_mortarA.json',' / A')
  rows.append(resrow(name,r))
 table(['정책 / 데이터 / 조건','전체 성공','IoU','E_h mm','E_f mm','F'],rows,[.39,.14,.12,.12,.13,.10])
 note('시험 초기 seed는 10000~10099. 실험 1 IoU는 당시 yaw 기반 구현의 저장값이다. 같은 정책의 동일 시험 상태를 조건별로 반복 사용했으며 학습 반복 시드는 한 개다. 원본 파일명과 정확한 소수값은 근거자료/평가_전수목록.csv에 보존했다.')

page('부록 C. 재현 자료와 출처','숫자는 원본 기록, 해석은 본 보고서 작성 시점의 판단')
table(['자료','위치·용도'],[
 ['Word 보고서','실험1_실험2_통합보고서.docx — 본문·표 편집 가능, 이미지 파일을 문서 내부에 삽입'],
 ['PDF 열람본','실험1_실험2_통합보고서.pdf — 같은 내용으로 만든 고정 레이아웃 열람본'],
 ['발표용 영상','발표용_영상/00_영상목록.html 및 01~12 MP4. 파일명에 실험·정책·실패 유형·seed 표시'],
 ['독립 이미지','이미지/ — 보고서 사용 그래프·MuJoCo 캡처 원본 PNG'],
 ['수치 근거','근거자료/데이터셋_전수목록.csv, 학습_전수목록.csv, 평가_전수목록.csv, audit.json'],
 ['원본 스냅샷','근거자료/원본기록/ — 설계·과목 안내 PDF, 당시 보고서, 코드, 수집·평가 로그 사본'],
 ['영상 출처','근거자료/영상_메타데이터/ — 원본 영상 구간·episode·seed·재생 설정·최종 자세 비교 및 간격별 trace'],
 ['무결성·재생성','근거자료/출처_SHA256.csv, 재생성_도구/ — 숫자·차트·영상·문서 생성 스크립트. 기존 학습 결과는 변경하지 않음']],[.23,.77])
h('로컬 1차 출처')
p('[S1] 26_2사기설개요.pdf, 2·5~7·11~12·16쪽. [S2] 설계수행계획서_14조_통합최종본.pdf, 총36쪽. [S3] 실험보고서.pdf 및 실험일지.md, 과거 서술은 코드·기록으로 대조. [S4] sim/data/*/collect_config.json, episode_metrics.json, meta/info.json. [S5] sim/outputs/*/checkpoints/last/pretrained_model/train_config.json 및 sim/logs/train_*.log. [S6] sim/outputs/eval_*.json, test_*.json, validation_*.json. [S7] scene.py, expert.py, collect.py, eval_policy.py, metrics.py, volume.py, run_clean_experiment.py.')
h('관련 논문(저자 원문·학회 출처)')
p('[L1] Zhao et al. (2023), Learning Fine-Grained Bimanual Manipulation with Low-Cost Hardware. https://arxiv.org/abs/2304.13705')
p('[L2] Chi et al. (2023; 확장판 2024), Diffusion Policy: Visuomotor Policy Learning via Action Diffusion. https://arxiv.org/abs/2303.04137')
p('[L3] Ross et al. (2011), A Reduction of Imitation Learning and Structured Prediction to No-Regret Online Learning. https://proceedings.mlr.press/v15/ross11a.html')
p('[L4] Laskey et al. (2017), DART: Noise Injection for Robust Imitation Learning. https://proceedings.mlr.press/v78/laskey17a.html')
p('[L5] Shukor et al. (2025), SmolVLA: A Vision-Language-Action Model for Affordable and Efficient Robotics. https://arxiv.org/abs/2506.01844')

def xmltag(name,**attrs):
    el=OxmlElement(name)
    for k,v in attrs.items():el.set(qn(k),str(v))
    return el

def render_docx():
    doc=Document();sec=doc.sections[0];sec.page_height=Cm(29.7);sec.page_width=Cm(21)
    sec.top_margin=Cm(1.6);sec.bottom_margin=Cm(1.6);sec.left_margin=Cm(1.8);sec.right_margin=Cm(1.8)
    sec.header_distance=Cm(.65);sec.footer_distance=Cm(.7)
    styles=doc.styles
    for name in ['Normal','Heading 1','Heading 2','Caption']:
        st=styles[name];st.font.name='Noto Sans KR';st._element.get_or_add_rPr().append(xmltag('w:rFonts',**{'w:eastAsia':'Noto Sans KR'}))
    styles['Normal'].font.size=Pt(9.5);styles['Normal'].paragraph_format.line_spacing=1.16;styles['Normal'].paragraph_format.space_after=Pt(6)
    styles['Heading 1'].font.size=Pt(18);styles['Heading 1'].font.color.rgb=RGBColor.from_string('173B57');styles['Heading 1'].paragraph_format.space_after=Pt(9)
    styles['Heading 2'].font.size=Pt(11);styles['Heading 2'].font.color.rgb=RGBColor.from_string('1D6D9E');styles['Heading 2'].paragraph_format.space_before=Pt(8);styles['Heading 2'].paragraph_format.space_after=Pt(4)
    styles['Caption'].font.size=Pt(8);styles['Caption'].font.color.rgb=RGBColor.from_string('526373')
    header=sec.header.paragraphs[0];header.text='사회기반시스템종합설계  |  조적 로봇 제어 시스템 설계  |  14조';header.style='Caption'
    footer=sec.footer.paragraphs[0];footer.alignment=WD_ALIGN_PARAGRAPH.RIGHT
    footer.add_run('2026-09-22  ·  ')
    fld=xmltag('w:fldSimple',**{'w:instr':'PAGE'});footer._p.append(fld)
    for page_index,pg in enumerate(PAGES):
        if page_index:doc.add_page_break()
        doc.add_heading(pg['title'],0 if page_index==0 else 1)
        if pg['subtitle']:r=doc.add_paragraph(pg['subtitle']);r.style='Caption'
        for typ,b in pg['blocks']:
            if typ=='p':doc.add_paragraph(b)
            elif typ=='h':doc.add_heading(b,2)
            elif typ=='note':
                para=doc.add_paragraph(b);para.style='Caption';para.paragraph_format.space_before=Pt(4)
            elif typ=='fig':
                name,cap=b;para=doc.add_paragraph();para.paragraph_format.space_after=Pt(0);para.paragraph_format.keep_with_next=True
                para.add_run().add_picture(str(IMG/name),width=Cm(17.2));doc.add_paragraph(cap,'Caption')
            elif typ=='table':
                heads,rows,widths=b;t=doc.add_table(rows=1,cols=len(heads));t.autofit=False
                widths=widths or [1/len(heads)]*len(heads)
                for j,w in enumerate(widths):t.columns[j].width=Cm(17.4*w)
                for j,s in enumerate(heads):t.rows[0].cells[j].text=s
                for row in rows:
                    cells=t.add_row().cells
                    for j,s in enumerate(row):cells[j].text=s
                t.rows[0]._tr.get_or_add_trPr().append(xmltag('w:tblHeader'))
                for i,row in enumerate(t.rows):
                    row._tr.get_or_add_trPr().append(xmltag('w:cantSplit'))
                    for j,cell in enumerate(row.cells):
                        cell.width=Cm(17.4*widths[j]);tcpr=cell._tc.get_or_add_tcPr()
                        tcpr.append(xmltag('w:shd',**{'w:fill':'173B57' if i==0 else ('EDF3F7' if i%2 else 'FFFFFF')}))
                        for para in cell.paragraphs:
                            para.paragraph_format.space_after=Pt(3);para.paragraph_format.space_before=Pt(3);para.paragraph_format.line_spacing=1.07
                            for run in para.runs:
                                run.font.size=Pt(8.1 if len(heads)>4 else 8.6)
                                if i==0:run.font.bold=True;run.font.color.rgb=RGBColor(255,255,255)
                doc.add_paragraph().paragraph_format.space_after=Pt(0)
    doc.core_properties.title='실험 1·실험 2 통합 보고서 — 모방학습 기반 조적 로봇 제어 시스템 설계'
    doc.core_properties.author='14조';doc.core_properties.subject='사회기반시스템종합설계 실험 기록 및 다음 설계'
    doc.save(OUT/'실험1_실험2_통합보고서.docx')

def render_pdf():
    pdfmetrics.registerFont(TTFont('NotoKR',str(ROOT/'sim/tools/fonts/NotoSansKR-Regular.ttf')))
    pdfmetrics.registerFont(TTFont('NotoKR-B',str(ROOT/'sim/tools/fonts/NotoSansKR-Bold.ttf')))
    st={
      'p':ParagraphStyle('p',fontName='NotoKR',fontSize=9.4,leading=14,spaceAfter=7,wordWrap='CJK'),
      'note':ParagraphStyle('note',fontName='NotoKR',fontSize=8,leading=11.5,spaceAfter=6,textColor=colors.HexColor('#526373'),wordWrap='CJK'),
      'h':ParagraphStyle('h',fontName='NotoKR-B',fontSize=11,leading=16,spaceBefore=6,spaceAfter=5,textColor=colors.HexColor('#1D6D9E'),wordWrap='CJK'),
      'title':ParagraphStyle('title',fontName='NotoKR-B',fontSize=18,leading=24,spaceAfter=10,textColor=colors.HexColor('#173B57'),wordWrap='CJK'),
      'cell':ParagraphStyle('cell',fontName='NotoKR',fontSize=8,leading=11,wordWrap='CJK'),
      'head':ParagraphStyle('head',fontName='NotoKR-B',fontSize=8,leading=11,textColor=colors.white,wordWrap='CJK')}
    esc=lambda s:html.escape(str(s)).replace('\n','<br/>')
    flow=[];width=A4[0]-102
    for i,pg in enumerate(PAGES):
        if i:flow.append(PageBreak())
        flow+=[Paragraph(esc(pg['title']),st['title']),Paragraph(esc(pg['subtitle']),st['note'])]
        for typ,b in pg['blocks']:
            if typ in ['p','h','note']:flow.append(Paragraph(esc(b),st[typ]))
            elif typ=='fig':
                name,cap=b;im=Image.open(IMG/name);hei=width*im.height/im.width
                flow.append(KeepTogether([RLImage(str(IMG/name),width=width,height=hei),Spacer(1,3),Paragraph(esc(cap),st['note'])]))
            elif typ=='table':
                heads,rows,ww=b;ww=ww or [1/len(heads)]*len(heads)
                vals=[[Paragraph(esc(v),st['head' if j==0 else 'cell']) for v in row] for j,row in enumerate([heads]+rows)]
                tab=Table(vals,colWidths=[width*w for w in ww],repeatRows=1,hAlign='LEFT')
                tab.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#173B57')),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.HexColor('#EDF3F7'),colors.white]),('VALIGN',(0,0),(-1,-1),'TOP'),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5),('LEFTPADDING',(0,0),(-1,-1),6),('RIGHTPADDING',(0,0),(-1,-1),6),('LINEBELOW',(0,-1),(-1,-1),.5,colors.HexColor('#BBCBD5'))]))
                flow.extend([tab,Spacer(1,8)])
    def furniture(c,d):
        c.setFont('NotoKR',7);c.setFillColor(colors.HexColor('#526373'));c.drawString(51,817,'사회기반시스템종합설계 | 14조 | 실험 1·2 기록')
        c.drawRightString(544,24,f'2026-09-22  ·  {d.page}')
    SimpleDocTemplate(str(OUT/'실험1_실험2_통합보고서.pdf'),pagesize=A4,leftMargin=51,rightMargin=51,topMargin=43,bottomMargin=39,
        title='실험 1·실험 2 통합 보고서',author='14조').build(flow,onFirstPage=furniture,onLaterPages=furniture)

def video_guide():
    cards=[];md=['# 발표용 영상 안내','', '01~04: 실제 수집 원본. 05~07: 실패 시드 재현. 08~12: 기존 정책 체크포인트 재실행. 학습 재개나 새 본평가가 아닙니다.','']
    for number,title,times,desc in video_notes:
        f=next((OUT/'발표용_영상').glob(number+'_*.mp4'))
        cards.append(f'<article data-title="{html.escape(f.name)}"><h2>{number}. {title}</h2><p><b>추천 구간: {times}</b><br>{desc}</p><video controls preload="metadata" src="{html.escape(f.name)}"></video><p class="file">{html.escape(f.name)}</p></article>')
        md.extend([f'## {number}. {title}',f'- 파일: {f.name}',f'- 추천 구간: {times}',f'- {desc}',''])
    text='''<!doctype html><html lang="ko"><meta charset="utf-8"><title>실험 1·2 발표용 영상</title><style>body{max-width:1200px;margin:40px auto;font-family:Arial,"Noto Sans KR",sans-serif;color:#173b57;background:#edf3f7;padding:0 24px}h1{font-size:32px}header{margin-bottom:25px}input{padding:12px;width:90%;font-size:16px;border:1px solid #aac0cd;border-radius:8px}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(480px,1fr));gap:24px}article{background:white;padding:20px;border-radius:12px;box-shadow:0 3px 12px #1231}video{width:100%;background:#142338}.file{font-size:12px;word-break:break-all}p{line-height:1.7}h2{font-size:20px}</style><header><h1>실험 1·2 발표용 영상</h1><p>01~04 수집 원본 · 05~07 실패 시드 재현 · 08~12 정책 체크포인트 재실행<br>학습은 중단된 상태입니다. 재생 촬영은 원 시험 통계에 포함하지 않았습니다.<br><b>발표 핵심 추천: 02 → 04 → 06 → 10 → 12</b></p><input id="filter" placeholder="실험2, ACT, 파지 등으로 찾기"></header><main>'''+''.join(cards)+'''</main><script>document.querySelector('#filter').addEventListener('input',e=>document.querySelectorAll('article').forEach(a=>a.style.display=a.textContent.toLowerCase().includes(e.target.value.toLowerCase())?'':'none'));</script></html>'''
    (OUT/'발표용_영상/00_영상목록.html').write_text(text)
    (OUT/'발표용_영상/00_먼저읽기.md').write_text('\n'.join(md))

render_docx();render_pdf();video_guide()
(OUT/'근거자료/보고서_내용.json').write_text(json.dumps(PAGES,ensure_ascii=False,indent=2))
md=[]
for pg in PAGES:
    md.extend(['# '+pg['title'],pg['subtitle'],''])
    for typ,b in pg['blocks']:
        if typ in ['p','note']:md.extend([b,''])
        elif typ=='h':md.extend(['## '+b,''])
        elif typ=='fig':md.extend([f'![{b[1]}](이미지/{b[0]})',''])
        elif typ=='table':
            hs,rs,_=b;md.extend(['| '+' | '.join(hs)+' |','|'+'|'.join(['---']*len(hs))+'|']);md.extend('| '+' | '.join(r)+' |' for r in rs);md.append('')
(OUT/'실험1_실험2_통합보고서.md').write_text('\n'.join(md))
for name in ['build_presentation_audit.py','make_presentation_videos.py','make_presentation_charts.py','build_experiment_report.py']:
    shutil.copy2(ROOT/'sim/tools'/name,OUT/'재생성_도구'/name)
print('Report created:',len(PAGES),'logical pages',OUT)
