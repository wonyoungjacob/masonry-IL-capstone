# 모방학습 기반 조적 로봇 제어 시스템 설계 — 14조 (2026-2 사회기반시스템종합설계)

시뮬레이션(MuJoCo, SO-ARM101)에서 벽돌 3개 2+1 적층을 IK 스크립트 전문가가 시연으로 생성하고, ACT·Diffusion Policy·SmolVLA·π0를 같은 데이터로 학습해 3D IoU·높이 오차·벽면 기준선 이격으로 비교한 뒤, 실패 원인에 대응하는 제어를 설계한다.

## 문서

| 파일 | 내용 |
|---|---|
| `설계수행계획서_14조_통합최종본.pdf` | 9/15 제출본 (수정하지 않음) |
| `설계수행계획서_14조_v2_IK시연생성.md/.pdf` | 시연 수집을 리더암 원격조작 → 시뮬레이션 내 IK 스크립트 생성으로 바꾼 청사진 (4.7절 교체, 그 외 동일) |
| `설계수행계획서_14조_v2_변경분.md/.pdf` | 바뀐 곳만 모은 변경분 (원본 문서에 반영용) |
| `선행연구_목표정밀도_조사.md` | 로봇 조적·정밀 픽앤플레이스 약 130편의 목표/달성 정밀도 조사 |
| `MuJoCo_화면/` | 발표용 MuJoCo 예시 장면 |

## 코드

`sim/` — 환경·IK 전문가·지표·데이터셋 생성·학습·평가. 사용법은 [sim/README.md](sim/README.md).

```bash
# Ubuntu + RTX 5090
git clone <this repo> && cd <repo>/sim
bash setup_ubuntu.sh      # venv, torch cu128, lerobot, mujoco, SO-ARM100 모델
bash run_phase1.sh        # 시연 생성(조건당 120) → ACT/DP 학습 → 100회 평가
```

## 작업 규칙

- 코드는 `sim/`, 문서는 루트. 데이터셋·체크포인트·로그(`sim/data`, `sim/outputs`, `sim/logs`)는 커밋하지 않는다.
- 실험 결과는 `sim/outputs/*.json`을 요약해 `실험일지.md`(루트)에 날짜별로 적는다.
- 두 PC(Windows 문서·발표 / Ubuntu 실험)는 이 저장소로만 주고받는다. 작업 시작 전 `git pull`, 끝나면 `git push`.
