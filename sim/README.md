# brick_sim — 조적 IK 시연 생성·학습·평가 파이프라인 (MuJoCo + LeRobot)

## 전체 시각화 메뉴 (Ubuntu 데스크톱)

저장소 루트에서 `bash sim/view_all.sh`를 실행한다. `D`는 실제 수집 영상의 데이터셋·에피소드 선택 페이지,
`E`는 IK 전문가 MuJoCo 실행, 숫자는 해당 체크포인트의 MuJoCo 실행이다. 창을 닫으면 메뉴로 돌아온다.
마우스로 시점을 회전·확대할 수 있으며, 작업이 끝난 후에도 최종 장면을 유지한다.

- `bash sim/view_all.sh --kick`: 정책에 평가 코드와 같은 방식의 교란 1회 적용.
- `bash sim/view_all.sh --seed 10001`: 다른 초기 상태 선택. 기본값은 평가 시드 10000.
- `bash sim/view_all.sh --device cpu`: CUDA를 사용할 수 없을 때 사용(느릴 수 있음).
- `bash sim/view_all.sh --gallery`: 브라우저를 열지 않고 `sim/outputs/dataset_gallery.html` 생성.

데이터셋 페이지는 저장된 카메라 영상을 에피소드 구간별로 보여 준다. 좌표 전용(state) 세트에는 영상이 없다.
AV1 영상 재생을 지원하는 브라우저가 필요하다. 카메라별 재생은 함께 시작하지만 프레임 단위 동기화는 보장하지 않는다.
정책 메뉴는 체크포인트로 **새 rollout**을 실행하며, 과거 평가 결과 JSON의 영상을 재생하는 기능은 아니다.
확률적 정책은 같은 초기 상태에서도 결과가 달라질 수 있다. 기본 조건은 mortarB, 위치 ±5 mm, yaw ±10°, 크기 고정이다.
GUI 실행은 화면에 연결된 로컬 터미널에서 수행한다.

설계수행계획서 14조 v2(시연 수집 = 시뮬레이션 내 IK 스크립트 전문가)의 구현이다. 이 PC(Windows, GPU 없음)에서는 구동 확인용이고, 본실험은 Ubuntu GPU 머신에서 같은 코드로 한다.

## 구성

| 파일 | 역할 |
|---|---|
| `brick_sim/scene.py` | MuJoCo 장면. SO-ARM100(Menagerie) + 벽돌 + 카메라(front/top/wrist) + TCP 사이트. `blueprint_config(mortar)`가 최종본 4.3/4.4 사양(2+1, 90×42.632×27 mm, 1,800 kg/m³, 20 Hz, 1 ms)을 만든다. 모르타르 모드 `dry` / `mortarA`(순응 접촉층) / `mortarB`(A + 정착 후 weld 경화). 벽돌은 공급기(feeder) 슬롯에 한 장씩 올라온다 |
| `brick_sim/ik.py` | 감쇠 최소자승 IK (`mj_jacSite`). 5자유도 팔에서 "그리퍼 아래 향함 + yaw" 과제 |
| `brick_sim/expert.py` | 스크립트 전문가: 사전파지 → 하강 → 파지 → 들기 → 극좌표 운반 → 하강 → 서보 보정 → 해제 → 후퇴. 고정 턱 오프셋(W/2 − 12 mm) 자동 적용. `noise_std`로 DART식 노이즈 주입(라벨은 깨끗한 행동) |
| `brick_sim/metrics.py` | `compute_metrics3` = 최종본 4.9의 3지표(3D IoU, E_h, E_f, 6순열 최소거리 대응). `compute_metrics` = 검측 8종(수직도·직진도·켜수평·줄눈·물림·안정성·IoU 등) |
| `run_expert_eval.py` | 전문가만 돌려 지표 출력. `--task 2p1 --mortar dry|mortarA|mortarB --seeds N --pos-rand 0.005` |
| `collect.py` | LeRobotDataset(v3) 생성. front+wrist 128², `observation.state`(6), `observation.environment_state`(벽돌 절대자세, 좌표기반 정책용), `action`(관절 목표 6). 정착 후 지표로 필터링 |
| `view_demo.py` | 인터랙티브 MuJoCo 뷰어로 실시간 재생. `--task 2p1 --mortar mortarB --loop` |
| `eval_policy.py` | 학습된 LeRobot 정책을 환경에서 롤아웃하고 지표 계산 |
| `brick_sim/feasibility.py` | 스폰 실행가능성 정적 검사(파지 자세 자기충돌, 턱 닫힘 구간 이웃 블록 간섭). `collect.py --feasible-supply`, `eval_policy.py --feasible-supply` |
| `brick_sim/grasp_gate.py` | 정책 롤아웃용 게이트. 집기: 닫힌 뒤 1.5 cm 들고 멈춰 턱 각도 AND 손목 하중으로 확인(`--gate-force`), 빈손이면 열고 상승·재지도 후 정책 재시도(`--gate-retries 0`이면 무제한). 놓기: 해제 직전 좌표 오차 보정(`--release-gate`), 해제 직후 채점해 실패하면 블록당 1회 재배치(`--gate-replace`), 정책의 재파지는 차단. 결과는 `policy+gate(...)`로 표기 |
| `tools/gen_final_v2.py` | 팀 최종본 PDF 텍스트에서 4.7절만 바꾼 v2 청사진 생성 |

## 이 PC에서 확인된 것 (2026-09-17)

- 2+1 과제, IK 전문가, 시드 3개 × 공급 위치 ±5 mm: 건식 IoU 0.88 / E_h 0.20 mm / E_f 2.2 mm, 접착층 A IoU 0.91 / 0.16 / 2.0, A+B IoU 0.88 / 0.16 / 2.3, 붕괴 0, 경화 3/3
- 3단 10장 벽(반절 벽돌 포함) 데이터셋 3에피소드(4,260 프레임) 생성 → `lerobot-train` ACT 50스텝 CPU 학습(1.06 s/step) → `eval_policy.py` 롤아웃까지 구동 확인
- 주의: Windows에서 `torchcodec` DLL이 안 떠서 데이터셋 로딩/학습에 `--dataset.video_backend=pyav` 필요

## Ubuntu GPU 머신에서

```bash
pip install mujoco lerobot av            # torch/CUDA는 LeRobot 요구 버전에 맞춰 설치
cd sim && git clone --depth 1 --filter=blob:none --sparse https://github.com/google-deepmind/mujoco_menagerie.git menagerie \
  && (cd menagerie && git sparse-checkout set trs_so_arm100)
export MUJOCO_GL=egl                      # 헤드리스 렌더링

# 1) 전문가 확인
python run_expert_eval.py --task 2p1 --mortar dry --seeds 5 --pos-rand 0.005

# 2) 시연 생성 (최종본 4.7: 조건당 학습 100 + 검증 20; 노이즈 유/무 두 세트)
python collect.py --task 2p1 --episodes 120 --mortar dry     --pos-rand 0.005 --yaw-rand 10 --root data/2p1_dry_clean   --repo-id local/2p1_dry_clean
python collect.py --task 2p1 --episodes 120 --mortar dry     --pos-rand 0.005 --yaw-rand 10 --noise 0.003 --root data/2p1_dry_dart --repo-id local/2p1_dry_dart
python collect.py --task 2p1 --episodes 120 --mortar mortarB --pos-rand 0.005 --yaw-rand 10 --root data/2p1_joint_clean --repo-id local/2p1_joint_clean

# 3) 학습 (예: ACT). 영상 정책은 environment_state를 빼고, 좌표 정책은 카메라를 빼서 별도 학습
lerobot-train --dataset.repo_id=local/2p1_dry_clean --dataset.root=data/2p1_dry_clean --policy.type=act --policy.device=cuda \
  --steps=50000 --batch_size=32 --output_dir=outputs/act_2p1_dry --job_name=act_2p1_dry --policy.push_to_hub=false

# 4) 평가 (학습에 쓰지 않은 시드)
python eval_policy.py --ckpt outputs/act_2p1_dry/checkpoints/last/pretrained_model --task 2p1 --episodes 100 --seed0 10000
```

`collect.py`는 `--task 2p1`을 지원한다(20 Hz 자동 적용). 영상/좌표 입력 분리는 `--policy.input_features`를 명시하거나 데이터셋을 두 벌로 나누어 학습한다.

## 장면 사양 v2 (2026-09-18)

`brick_sim/scene.py`의 `SPEC_V2`(기본값). 머리줄눈 1 mm(실제 시공처럼 밀착), 접촉층 A = 각 벽돌 윗면의 얇은 모르타르 대리 형상(가시, 그 형상과 다른 벽돌 본체 사이에만 순응 접촉), 바닥에 아래층 목표 테두리(청색)와 벽면 먹선(흑색), 벽돌 3개는 시작부터 작업 공간 안 슬롯 3개에 무작위 순열·±5 mm·±10°로 산개. `SPEC_V1`은 9/18 이전 데이터셋(`data/2p1_*`)의 사양(4.737 mm 줄눈, 보이지 않는 margin 접촉층, 공급기).

- `collect.py --spec v1|v2`가 장면 사양을 `collect_config.json["scene"]`에 기록하고, `eval_policy.py`·`view_demo.py --ckpt`는 체크포인트의 `train_config.json` → 데이터셋 → 사양을 읽어 **학습한 장면 그대로** 평가·재생한다.
- `view_demo.py --ckpt <pretrained_model>`로 학습된 정책을, `--noise 0.003`으로 DART 노이즈 전문가를 뷰어에서 볼 수 있다.
- `eval_policy.py`는 lerobot 0.6의 pre/post-processor(정규화)를 적용하고 GPU에서 추론한다(이전 버전은 정규화를 빼먹어 평가가 무의미했음). torch 스레드는 1개로 제한(`EVAL_THREADS`).
- `metrics.py`의 복셀 IoU는 목표 영역에서 먼 벽돌(미배치)을 해석적으로 처리해 실패 에피소드에서도 1초 안에 끝난다.
- `run_mortar.sh`: mortarB 조건에서 ACT·Diffusion·SmolVLA(+π0, `PI0=1`)·ACT(state)·ACT(dart) 학습과 100회 평가를 순차 실행. SmolVLA/π0는 `--rename_map`으로 카메라 이름을 사전학습 모델에 맞춘다.

## 알려진 한계

- 전문가의 배치 정밀도(≈2 mm)는 위치 구동기(kp=50)의 정상상태 오차와 해제 시 미세 이동이 지배한다. 서보 보정 구간이 이를 절반으로 줄였다.
- 접착층 파라미터는 물성이 아니라 침하량 0.5 mm 목표에서 역산한 값이다(최종본 4.8.3의 주의 그대로).
- 도달 가능 영역: 로봇 베이스 반경 약 0.12 m 이내와 0.27 m 밖은 "아래 향한" 그리퍼로 IK가 풀리지 않는다. 벽·공급기 위치는 이 안에 둔다.
