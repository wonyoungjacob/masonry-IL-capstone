# 인수인계 프롬프트 — 모방학습 기반 조적 로봇 제어 (14조 캡스톤)

너는 이 프로젝트를 이어받는 AI 어시스턴트다. 이전 AI(Claude Code)가 2026-09-18~21에 수행한 작업을 그대로 이어서 진행한다.
사용자는 한국어로 대화하며, 답변은 항상 한국어로, 짧고 표 위주로, 주저리주저리 없이 한다.
질문으로 막지 말고 스스로 판단해 진행하되, 되돌리기 어려운 작업(삭제·강제 푸시)만 확인을 받는다.
작업 전에 반드시 `~/masonry/실험일지.md` 와 `~/masonry/실험보고서.pdf` 를 먼저 읽어라. 아래 내용은 그 요약이다.

## 1. 환경
- 저장소: `~/masonry` (git, origin = github.com/wonyoungjacob/masonry-IL-capstone, private, 최신 커밋 5a15ce3, 로컬=origin 동기 상태)
- 시뮬레이터/학습 코드: `~/masonry/sim`, 가상환경 `~/masonry/sim/venv` (`source venv/bin/activate`; activate 끝에 `LD_LIBRARY_PATH` 추가돼 있음 — torchcodec용 nvidia-npp)
- GPU: RTX 5090 1장, torch cu128. 렌더링은 헤드리스 `export MUJOCO_GL=egl`. GUI 확인은 `view_demo.py`.
- 스택: MuJoCo 3.13, LeRobot 0.6.1 (`lerobot-train`, LeRobotDataset v3), reportlab(보고서), fontTools.
- sudo 비밀번호 없음 → 권한 필요한 작업은 사용자에게 명령을 보여주고 직접 실행하게 한다.
- `sim/outputs/` 약 350 GB(중간 체크포인트 3.2 GB × 다수). 정리는 사용자 허락 후에만. 실제 쓰는 것은 각 run의 `checkpoints/last` 뿐.

## 2. 절대 규칙 (사용자가 명시)
1. `설계수행계획서_14조_통합최종본.pdf` 는 절대 수정·삭제 금지.
2. 설계가 바뀌면 설계수행계획서는 **md 파일만** 갱신하고 git에 push 한다 (`설계수행계획서_14조_v2_IK시연생성.md`, `..._v2_변경분.md`). 다른 pdf/html은 삭제해도 됨(통합최종본 제외).
3. 실험 결과·해석은 `실험일지.md` 에 누적 기록(정정이 있으면 지우지 말고 '정정' 표기). 커밋 메시지 한국어.
4. 데이터셋은 한 번에 많이 쌓지 말고 1개 쌓고 MuJoCo로 보여준 뒤 진행(사용자 스타일).

## 3. 코드 구조 (sim/)
| 파일 | 역할 |
|---|---|
| `brick_sim/scene.py` | MuJoCo 씬. `SPEC_V1`(구) / `SPEC_V2`(현행: 머리줄눈 1 mm, 모르타르 베드 시각화, 바닥 타겟 테두리+먹선, 블록 근처 산개 배치 `supply_slots`). `blueprint_config(mortar, spec="v2")`, `BrickEnv.kick_brick()`(교란 임펄스), `_update_bed()`(1층 2개 정상 안착 확인 후 연속 모르타르 베드 1개 생성, 2층 후엔 없음) |
| `brick_sim/expert.py` | `ScriptedExpert`: IK 스크립트 전문가. 벽에 가까운 블록부터 집는 관측 가능한 고정 순서, 파지 검증, 실패 시 재시도(`max_retries`), 교란(`disturb_prob`, `per_episode`, `kick_hold=0`) 후 복구 시연 |
| `brick_sim/metrics.py` | `compute_metrics3` = 계획서 4.9 지표 3종(`bp_iou`, `bp_E_h_mm`, `bp_E_f_mm`). `compute_metrics` = 8지표 진단(낙하 수 `m7_fallen_count`, xy 오차 등), 블록-슬롯 매칭은 `_assign`(최소거리) |
| `collect.py` | 데이터셋 수집. `--spec v2 --disturb p --per-episode-kick --kick-hold 0 --retries N --disturb-from N`. `collect_config.json["scene"]` 에 씬 스펙 기록 |
| `eval_policy.py` | 정책 평가 100회. **LeRobot 0.6 pre/post-processor(정규화)를 반드시 거침** — 초기에 이걸 빠뜨려 평가가 전부 무효였던 이력 있음. `--disturb 1.0` = 매 에피소드 교란. 체크포인트의 학습 데이터셋 씬 스펙을 자동으로 재현 |
| `view_demo.py` | GUI 재생. `--ckpt` 로 정책 재생, `--disturb`, `--spec` |
| `summarize.py` | `outputs/eval_*.json` → 표/`outputs/results.csv` |
| `tools/make_report.py` | `실험보고서.pdf`(3쪽) 자동 생성. 한글 폰트 `tools/fonts/NotoSansKR-*.ttf` 동봉 |
| `run_v7.sh ~ run_v9.sh` | 학습→평가 파이프라인 템플릿. train()에 정체 감시(로그 900 s 정지 시 kill → `--resume=true` 재개), evaluate()는 백그라운드. 새 실험은 이 형식을 복사해 `run_v10.sh` 로 |

과제 표기 `2p1` = 1층 2개 + 2층 1개(총 3개 블록). 평가 조건 `mortarB` 가 기준, `mortarA` 는 보조. 평가: 100 에피소드, seed0 10000, 위치 무작위 ±5 mm, 요 ±10°.

## 4. 데이터셋 (sim/data/, 각 120 시연 기준, 카메라 front+wrist, 관절 상태 입력)
| 이름 | 분류 기준 |
|---|---|
| `2p1_*` (6개) | SPEC_V1 구 씬(dry/joint, image/state, clean/dart). 참고용, 현행 실험에서는 제외 |
| `v2_2p1_joint_image_clean` | 현행 씬, 교란 없음 (기준) |
| `v2_2p1_joint_state_clean` | 이미지 대신 특권 좌표 입력 (계획서 4.6.5 기준선) |
| `v2_2p1_joint_image_mix` | 교란 0.15 의도였으나 버그로 62 % 에피소드 교란 + 정지 프레임 포함 (결함 데이터, 결과 해석 시 주의) |
| `v2_2p1_joint_image_mix2` | 버그 수정 후 에피소드당 교란 17 % |
| `v2_2p1_joint_image_robust` | 거의 전부(95 %) 교란 |
| `v2_2p1_joint_image_plus` | clean 120 + 항상 교란 60 (대체가 아닌 추가) |
| `v2_2p1_joint_image_plus2` | clean 120 + 교란 120 |
| `v2_2p1_joint_image_plustop` | plus 와 같되 상부(top) 카메라 추가 → 3 카메라 |
| `v2_2p1_joint_image_plus2top` | plus2 + top 카메라 |

## 5. 학습 설정
- ACT: 40k step, batch 32 (chunk 100). Diffusion: 60k, batch 32 (n_action_steps 32). SmolVLA: `lerobot/smolvla_base`, 20k(VLM 동결) 및 40k(`train_expert_only=false`), `--rename_map` 으로 front/wrist→camera1/2. π0: 미실행(`google/paligemma-3b-pt-224` 게이트 → HF 로그인·라이선스 동의 필요).
- 학습 결과: `sim/outputs/<policy>_<dataset>/checkpoints/last/pretrained_model`, 로그 `sim/logs/train_*.log`.

## 6. 핵심 결과 (mortarB, 100회 평균; 낙하 = 무너진 에피소드 수, 진단용)
| 정책 / 데이터 | IoU | E_h mm | E_f mm | 낙하(무교란 / 교란) |
|---|---|---|---|---|
| Diffusion clean | 0.845 | 1.04 | 4.6 | 10 / 26 |
| ACT clean | 0.788 | 2.7 | 8.7 | 23 / 33 |
| SmolVLA clean (20k 동결 / 40k) | 0.31 / 0.32 | ~9 | ~35 | 93 / 100 |
| ACT state(특권 좌표) | 0.60 | 2.9 | 22.8 | 48 |
| Diffusion plus | 0.788 | 0.55 | 5.2 | 7 / 13 (xy 편향 ≈ 4 mm) |
| Diffusion plus2 | 0.807 | 0.50 | 3.6 | 3 / 12 (편향 6.3 mm) |
| Diffusion plustop | 0.848 | 0.57 | 3.9 | 5 / 15 (편향 해소) |
| Diffusion plus2top | 0.724 | 0.77 | 4.7 | 6 / 11 |
| Diffusion mix / mix2 / robust | 0.60 / 0.77 / 0.53 | – | – | 32 / 9 / 61 |
| ACT plustop / plus2top | 0.819 / 0.811 | 1.3 / 1.8 | 7.9 / 8.0 | 11 / 16 |

결론: Diffusion > ACT ≫ SmolVLA. 특권 좌표는 이미지보다 나쁨. 복구 시연은 clean 을 대체하면 해롭고 추가하면 낙하를 줄이지만 배치 편향을 만든다. 상부 카메라가 있어야 복구 시연이 쓸모 있다. 복구 시연 양(plus2)과 상부 카메라(top)를 합치면(plus2top) 효과가 더해지지 않는다. 권장 조합: Diffusion + plustop.
전체 표는 `실험결과.csv` / `sim/outputs/results.csv`.

## 7. 반드시 알아야 할 함정 (이미 해결됨, 재발 방지)
- 평가에서 pre/post-processor 누락 → 정규화 안 됨. 새 평가 코드를 쓰면 `make_pre_post_processors` 를 확인할 것.
- 전문가가 보이지 않는 내부 id 순서로 집으면 정책이 학습 불가(ACT 8/10 붕괴). 순서는 관측 가능한 규칙이어야 함.
- 교란 확률을 블록마다 굴리면 에피소드 기준 확률이 폭증. 정지 프레임(`kick_hold`)은 '정지' 행동으로 학습됨 → 0으로.
- `lerobot-train` 이 간헐적으로 GPU 유휴 상태로 멈춤 → 정체 감시 + resume 필수. `run_vN.sh` 를 죽일 때는 자식 `lerobot-train` 먼저 kill.
- 복셀 IoU는 설계 영역 밖 블록을 해석적으로 처리(안 그러면 수 분 소요).
- 평가 스레드 `EVAL_THREADS=1` 이 가장 빠름.
- reportlab 은 CFF(OTF) 한글 폰트 임베드 불가 → 동봉된 TTF 사용.

## 8. 미결 / 선택지 (사용자가 아직 결정 안 함)
- π0 학습(HF 로그인 필요), 시연 수 스케일링(200/500/1000), SmolVLA 재시도, Phase 2 제어 보완, `outputs/` 정리.
- 실험 추가 시 순서: `run_v10.sh` 작성 → 학습·평가 → `summarize.py` → `실험일지.md` 기록 → `tools/make_report.py` 로 PDF 재생성 → git push.
