# 모방학습 기반 조적 로봇 제어 시스템 설계 — 14조 (2026-2 사회기반시스템종합설계)

시뮬레이션(MuJoCo, SO-ARM101)에서 벽돌 3개 2+1 적층을 IK 스크립트 전문가가 시연으로 생성하고, ACT·Diffusion Policy·SmolVLA·π0를 같은 데이터로 학습해 3D IoU·높이 오차·벽면 기준선 이격으로 비교한 뒤, 실패 원인에 대응하는 제어를 설계한다.

## 문서 (목적별 폴더, 2026-10-06 정리)

| 폴더 | 목적 | 주요 파일 |
|---|---|---|
| `01_사기설/` | 사회기반시스템종합설계 과목 진행 | `계획서/설계수행계획서_14조_통합최종본.pdf`(9/15 제출본, 수정하지 않음), `진행보고/진행보고_캡스톤_14조_20261001.pdf`, `발표자료_실험1_실험2_20260922/` |
| `02_KSARC2026/` | 한국건설자동화로보틱스학회 정기학술대회 | `초록_KSARC2026_조적로봇검측.pdf`(완성), `논문초고_KSARC2026_4쪽.pdf`(옛 KICEM 대학생 4쪽 원고를 옮김, 양식은 아직 KICEM) |
| `03_KICEM2026_대학생/` | 한국건설관리학회 대학생학술발표대회 4쪽 | `논문초고_KICEM2026_대학생_4쪽_수정본.pdf`(벽돌 치수 편차, 10/7 수정본), `본문텍스트_수정본.txt`(한글 붙여넣기용), `그림표/`(그림 1~4·표 1~4 PNG), `수정목록_제출본대비.txt` |
| `00_공통/` | 인수인계·선행연구 조사·MuJoCo 화면 | `AI_HANDOFF*.md`, `선행연구_목표정밀도_조사.md` |
| `99_기타/` | 다른 대회 | `KSCE경진대회_신청서_수정본.md` |

실험 기록은 루트의 `실험일지.md`. PDF를 만드는 스크립트는 `sim/tools/build_*.py`이며 기본 출력 경로가 위 폴더를 가리킨다.

## 코드

`sim/` — 환경·IK 전문가·지표·데이터셋 생성·학습·평가. 사용법은 [sim/README.md](sim/README.md).

```bash
# Ubuntu + RTX 5090
git clone <this repo> && cd <repo>/sim
bash setup_ubuntu.sh      # venv, torch cu128, lerobot, mujoco, SO-ARM100 모델
bash run_phase1.sh        # 시연 생성(조건당 120) → ACT/DP 학습 → 100회 평가
```

## 작업 규칙 (팀 공유)

- **모든 파일은 이 저장소로만 주고받는다** (Ubuntu 실험 PC, Windows PC, 노트북, 팀원 PC). 작업 시작 전 `git pull`, 끝나면 `git add` → `git commit` → `git push`.
- 같은 파일(특히 hwp·pptx·docx 같은 바이너리)을 두 사람이 동시에 고치면 병합이 안 된다. 고치기 전에 단톡에 알리고, 끝나면 바로 push한다.
- 코드는 `sim/`, 문서는 목적별 폴더. 데이터셋·체크포인트·로그(`sim/data`, `sim/outputs`, `sim/logs`, 수백 GB)는 커밋하지 않는다. 논문 그림을 다시 만드는 데 필요한 작은 결과 파일(`sim/outputs/kicem_size*/`, `sim/outputs/final_test/fig_task.png`)만 예외로 올려 두었다.
- 학습된 체크포인트가 필요하면 Ubuntu 실험 PC에서 받는다(저장소에는 없음).
- 같은 내용의 zip(발표자료·폰트 묶음)은 올리지 않는다. 풀린 폴더가 저장소에 있다.
- 실험 결과는 `실험일지.md`(루트)에 날짜별로 적는다.

### 처음 받는 법 (Windows·노트북·팀원)

```bash
git clone https://github.com/wonyoungjacob/masonry-IL-capstone.git
cd masonry-IL-capstone
git config core.quotepath false   # 한글 파일 이름을 그대로 표시
```

저장소는 비공개다. 팀원은 저장소 Settings → Collaborators에서 초대를 받아야 clone할 수 있다.
