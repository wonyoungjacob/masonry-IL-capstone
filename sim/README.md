# brick_sim — 조적 IK 시연 생성·학습·평가 파이프라인 (MuJoCo + LeRobot)

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

## 알려진 한계

- 전문가의 배치 정밀도(≈2 mm)는 위치 구동기(kp=50)의 정상상태 오차와 해제 시 미세 이동이 지배한다. 서보 보정 구간이 이를 절반으로 줄였다.
- 접착층 파라미터는 물성이 아니라 침하량 0.5 mm 목표에서 역산한 값이다(최종본 4.8.3의 주의 그대로).
- 도달 가능 영역: 로봇 베이스 반경 약 0.12 m 이내와 0.27 m 밖은 "아래 향한" 그리퍼로 IK가 풀리지 않는다. 벽·공급기 위치는 이 안에 둔다.
