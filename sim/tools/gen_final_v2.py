# -*- coding: utf-8 -*-
"""Build 설계수행계획서_14조_v2_IK시연생성.md from the team's final PDF text, changing ONLY the demonstration-
collection method (leader-arm teleoperation -> IK scripted expert in simulation).

Inputs : scratchpad/final_blueprint.txt (pypdf extraction of 설계수행계획서_14조_통합최종본.pdf)
         sim/out/eval_2p1_{dry,mortarA,mortarB}.json (preliminary IK-expert results for the 2+1 task)
Outputs: 설계수행계획서_14조_v2_IK시연생성.md and 설계수행계획서_14조_v2_변경분.md
"""
import io, json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRATCH = Path(r"C:\Users\user\AppData\Local\Temp\claude\c--Users-user-Desktop----\1bca8ce1-be6b-4e47-b3f0-e236d0653725\scratchpad")
raw = io.open(SCRATCH / "final_blueprint.txt", encoding="utf-8").read()

# ---------------------------------------------------------------- 1. clean the PDF text
lines = raw.split("\n")
out = []
i = 0
while i < len(lines):
    ln = lines[i]
    if ln.startswith("===== PAGE"):
        # skip marker and the following bare page-number line
        i += 1
        if i < len(lines) and re.fullmatch(r"\s*\d+\s*", lines[i]):
            i += 1
        continue
    out.append(ln)
    i += 1
text = "\n".join(out)

# join wrapped lines: a line that is "full width" (>= 40 chars) and does not end a sentence continues on the next
HEAD = re.compile(r"^(\d+(\.\d+)*\s|\[|표 \d|그림 \d|참고문헌|목\s+차)")
joined = []
buf = ""
for ln in text.split("\n"):
    st = ln.rstrip("\n")
    if buf:
        if HEAD.match(st.strip()) or st.strip() == "":
            joined.append(buf); buf = ""
        else:
            buf += st
            if len(st.rstrip()) < 40 or st.rstrip().endswith(("다.", "다. ", ".", ". ", ":", "]")):
                joined.append(buf); buf = ""
            continue
    if st.strip() == "":
        joined.append("")
    elif len(st.rstrip()) >= 40 and not st.rstrip().endswith(("다.", "다. ", ".", ". ", ":", "]")) and not HEAD.match(st.strip()):
        buf = st
    else:
        joined.append(st)
if buf:
    joined.append(buf)
text = "\n".join(joined)


def flex(phrase):
    """Regex that matches the phrase even if the PDF wrapped it anywhere (whitespace/newlines between chars)."""
    parts = [re.escape(c) for c in phrase if not c.isspace()]
    return r"\s*".join(parts)


def rep(phrase, new, count=1):
    global text
    pat = flex(phrase)
    m = re.search(pat, text)
    assert m, "NOT FOUND: " + phrase[:60]
    text = text[: m.start()] + new + text[m.end():]


def replace_section(start_heading, end_heading, new_body):
    """Replace everything from start_heading (inclusive) up to end_heading (exclusive)."""
    global text
    # headings also appear in the table of contents: take the LAST occurrence (the body)
    a = list(re.finditer(flex(start_heading), text))[-1]; b = list(re.finditer(flex(end_heading), text))[-1]
    assert a and b and a.start() < b.start(), (start_heading, end_heading)
    text = text[: a.start()] + new_body.rstrip("\n") + "\n\n" + text[b.start():]


# ---------------------------------------------------------------- 2. preliminary numbers
def load(mode):
    p = ROOT / "sim" / "out" / f"eval_2p1_{mode}.json"
    if not p.exists():
        return None
    r = json.loads(io.open(p, encoding="utf-8").read())
    import statistics as st
    def m(k): return st.mean(x[k] for x in r)
    return {"n": len(r), "iou": m("bp_iou"), "Eh": m("bp_E_h_mm"), "Ef": m("bp_E_f_mm"),
            "exy": m("m1_exy_mean_mm"), "fallen": sum(x["m7_fallen_count"] for x in r), "ikfail": sum(x["ik_fail_steps"] for x in r),
            "steps": r[0]["steps"]}
R = {k: load(k) for k in ["dry", "mortarA", "mortarB"]}

# ---------------------------------------------------------------- 3. replacements (data-collection method only)
rep("[ 모방학습 기반 조적 로봇 제어 시스템 설계 ]", "[ 모방학습 기반 조적 로봇 제어 시스템 설계 ] — v2 (시연 수집 방식 변경본)")
rep("제출일 : 2026. 09. 15.", "제출일 : 2026. 09. 15. (v2 개정 2026. 09. 17. — 4.7절 시연 데이터를 리더암 원격조작에서 시뮬레이션 내 IK 스크립트 생성으로 변경. 그 외 절은 통합최종본과 동일)")

# 2.5 차별성 ①
rep("① 조적 공종에 특화한 시뮬레이션 환경과 실물 리더암 원격조작 시연 데이터셋을 구축한다.",
    "① 조적 공종에 특화한 시뮬레이션 환경과, 시뮬레이션 안에서 역기구학(IK) 스크립트 전문가가 절차적으로 생성한 시연 데이터셋을 구축한다.")
# 3.2 목표 1
rep("실물 리더암 원격조작으로 시연 데이터를 수집하여 조건·초기 상태·수집자를 기록한 데이터셋을 만든다.",
    "시뮬레이션 안의 IK 스크립트 전문가로 시연 데이터를 생성하여 조건·초기 상태·생성 파라미터(랜덤화 폭, 노이즈 주입 여부)를 기록한 데이터셋을 만든다.")
# 3.3
rep("실물 리더암은 시연 입력 장치로만 사용하며, 실물 팔로워 로봇의 시험과 실물 전이(sim-to-real)는 범위에 포함하지 않는다.",
    "시연은 시뮬레이션 안에서 IK 스크립트 전문가가 생성하며(4.7절), 실물 로봇의 시험과 실물 전이(sim-to-real)는 범위에 포함하지 않는다.")
# 3.4
rep("안전은 1.1절의 근골격계 부담을 배경으로 반영하고 실물 리더암 운용에 적용하되, 실제 현장의 안전 개선 효과를 검증한다고 주장하지 않는다.",
    "안전은 1.1절의 근골격계 부담을 배경으로만 반영하며(실물 장비 운용이 없으므로 운용 안전 절차는 해당 없음), 실제 현장의 안전 개선 효과를 검증한다고 주장하지 않는다.")
rep("경제·자원 조건으로는 팀이 시연 수집에 쓸 수 있는 시간, 보유 GPU(2대)의 사용 시간, 학기 일정(중간발표 2회와 최종발표)을 둔다.",
    "경제·자원 조건으로는 시연 생성기 구현·검증에 쓸 수 있는 시간과 생성·렌더링 계산 시간, 보유 GPU(2대)의 사용 시간, 학기 일정(중간발표 2회와 최종발표)을 둔다.")
# 4.2 표 2 row + Nexus note
rep("리더암 시연 수집 경로 보유 SO-ARM101으로 가상 팔로워를 조작", "IK 시연 생성 경로 시뮬레이터 안에서 경로점을 관절 목표로 변환해 시연을 생성")
rep("SO101-Nexus에 리더암 연동과 LeRobot 데이터 기록 구현이 공개됨[75]",
    "mj_jacSite 야코비안으로 감쇠 최소자승 IK를 직접 구현할 수 있고[74][86], LeRobot 데이터셋 기록 형식이 공개됨[68]")
rep("SO101-Nexus는 베타이므로 장치의 영점·관절 방향·그리퍼 매핑과 기록·재생을 검증한 뒤 버전을 고정한다[75]. MuJoCo 선정과 연결 라이브러리의 검증은 별개이다.",
    "IK 전문가는 팀이 직접 구현하므로 도달 가능 영역, 파지 기하, 기록·재생을 검증한 뒤 버전을 고정한다. MuJoCo 선정과 시연 생성기의 검증은 별개이다.")
# 4.5 first paragraph
rep("보유 리더암으로 관측과 행동의 짝을 수집할 수 있으므로, 시연 데이터로 정책을 지도 학습하는 모방학습이 이 질문에 직접 대응한다.",
    "시뮬레이션 안에서 IK 스크립트 전문가가 관측과 행동의 짝을 생성할 수 있으므로, 시연 데이터로 정책을 지도 학습하는 모방학습이 이 질문에 직접 대응한다. 스크립트 시연으로 학습한 정책이 사람 시연으로 학습한 정책보다 같은 과제에서 높은 성공률을 보인 선례가 있다(4.7.2절)[47].")
# 4.10
rep("초기 파이프라인은 리더암 시연 → 같은 데이터로 정책 학습·미세조정",
    "초기 파이프라인은 IK 스크립트 시연 생성(랜덤화·필터링) → 같은 데이터로 정책 학습·미세조정")
rep("환경·물리 설정·리더암 기록 체계와 평가 코드를 구현하고", "환경·물리 설정·IK 시연 생성기와 평가 코드를 구현하고")
rep("건식 조건의 시연을 먼저 수집하면서", "건식 조건의 시연을 먼저 생성하면서")
rep("경제·자원 조건인 시연 수집 시간은 4.7절의 조건당 120개(총 240개)와 4.12절의 1인당 60개 분담으로,",
    "경제·자원 조건인 시연 생성 시간은 4.7절의 조건당 120개(총 240개, 생성 비용이 0에 가까우므로 필요 시 1,000개까지 확장)와 4.12절의 생성기·검수 분담으로,")
rep("안전은 실물 리더암 운용 절차에 적용하되 실제 현장 안전 개선 효과를 검증했다고 주장하지 않는다.",
    "안전은 실물 장비 운용이 없으므로 절차로 다루지 않으며, 실제 현장 안전 개선 효과를 검증했다고 주장하지 않는다.")
rep("[75] SO101-Nexus. 실물 리더암–가상 팔로워 연결 및 데이터 기록.",
    "[75] SO101-Nexus. 실물 리더암–가상 팔로워 연결 및 데이터 기록 (v1에서 인용, v2에서는 사용하지 않음).")
# 4.11 schedule rows
rep("MuJoCo 장면, 파지·구동 한계, 기본 접촉 확인; 리더암 기록·재생", "MuJoCo 장면, 파지·구동 한계, 기본 접촉 확인; IK 시연 생성기 구현·기록·재생")
rep("건식 시연 25·50개 확보, ACT 초기 학습;", "건식 시연 25·50개 생성·필터링, ACT 초기 학습;")
rep("조건별 학습 100+검증 20개 완성, 네 정책 학습; 시험기간 반영", "조건별 학습 100+검증 20개 생성 완료(노이즈 주입 유/무 두 세트), 네 정책 학습; 시험기간 반영")
rep("총 240개 품질 확인·고정 분할, 모델별 학습 로그 / 강건·정성용, 전원 수집", "총 240개 품질 확인·고정 분할, 모델별 학습 로그 / 강건·정성용")
# 4.12 roles
rep("리더암 수집·데이터 검수·에피소드 분할, 두 정책 학습·학습량 곡선", "IK 시연 생성기 운용·랜덤화·노이즈 주입·데이터 검수·에피소드 분할, 두 정책 학습·학습량 곡선")
rep("강건과 기록·재생 확인, 정원영과 보정 제어 및 상태 참값 검산", "강건과 시연 생성기의 IK·파지 기하 확인, 정원영과 보정 제어 및 상태 참값 검산")
rep("시연은 전원이 수집한다. 초기 목표 240개를 1인당 60개로 나누고, 각자 건식 30개·접촉층 30개를 맡는다. 조건마다 5개 배치 패턴에서 학습 5회·검증 1회를 수집하면, 네 명 합계로 패턴당 학습 20회·검증 4회가 된다. 수집자별 편차를 확인할 수 있도록 ID와 오류·재시도 기록을 남긴다.",
    "시연은 IK 스크립트 전문가가 생성하므로 사람이 나누어 수집하지 않는다. 대신 전원이 생성된 시연을 검수한다. 초기 목표 240개를 1인당 60개씩 나누어 영상·궤적·지표를 확인하고, 조건마다 5개 배치 패턴에서 학습 20회·검증 4회가 되도록 생성 시드를 배정한다. 생성 파라미터(시드, 랜덤화 폭, 노이즈 주입 여부)와 필터링에서 제외된 에피소드의 이유를 기록한다.")
# 5.1
rep("조건별 학습 100·검증 20개를 초기 목표로 한 기록, 수집자·배치 패턴·분할 ID",
    "조건별 학습 100·검증 20개를 초기 목표로 한 기록, 생성 시드·랜덤화 폭·노이즈 주입 여부·배치 패턴·분할 ID")
rep("시연 데이터와 수집 체계", "시연 데이터와 생성 체계")

# ---------------------------------------------------------------- 4. whole new 4.7
def fmt(r, key, nd=2):
    return "—" if r is None else f"{r[key]:.{nd}f}"

prelim_rows = []
for mode, label in [("dry", "건식(T-dry)"), ("mortarA", "등가 접촉층 A"), ("mortarB", "접촉층 A + 결합 B")]:
    r = R[mode]
    if r is None:
        prelim_rows.append(f"| {label} | — | — | — | — | — | — |")
    else:
        prelim_rows.append(f"| {label} | {r['n']} | {r['ikfail']} | {fmt(r,'iou',3)} | {fmt(r,'Eh')} | {fmt(r,'Ef')} | {r['fallen']} |")
prelim = "\n".join(prelim_rows)

sec47 = f"""4.7 시연 데이터의 규모와 구성

4.7.1 수집 방식 — 시뮬레이션 안의 IK 스크립트 전문가 (v2 변경)

시연은 사람이 리더암으로 조작하지 않고, 시뮬레이터 안에서 역기구학(IK) 기반 스크립트 전문가가 절차적으로 생성한다. 시뮬레이터는 공급 벽돌과 목표 슬롯의 정확한 위치·자세를 알고 있으므로, 벽돌 자세에 상대적으로 정의한 경로점(사전 파지 → 하강 → 파지 → 들기 → 운반 → 하강 → 서보 보정 → 해제 → 후퇴)을 감쇠 최소자승 IK로 관절 위치 목표로 변환하고, 그 목표를 위치 구동기에 그대로 명령한다. 기록되는 것은 정책이 학습할 관측(손목·고정 카메라 영상, 관절 상태)과 행동(관절 위치 목표 6개)의 짝이며, 정책의 입력에는 벽돌의 참값 좌표를 넣지 않는다(4.1절). 이 방식은 다음 근거에 따른다.

- 로봇 학습 벤치마크의 시연은 대부분 플래너가 만든다. RLBench는 "과제 생성 시 지정한 경로점 위에서 모션 플래너가 동작하므로 시연이 무한히 공급된다"고 명시하고[84], ManiSkill2/3는 모션 플래닝 해법을 공개해 시연을 생성하며 큐브 적층이 그 최소 원형이다[70][85]. Transporter Networks는 스크립트 오라클 시연만으로 블록 적층·팔레타이징을 학습했고, 시연 1→10→100→1,000개에서 피라미드 적층 성공률이 13→43→56→78%로 올랐다[87]. 실물 대규모 데이터셋 BridgeData V2도 픽앤플레이스 9,731개는 스크립트 정책으로 자동 수집했다[88].
- 같은 과제·같은 개수에서 스크립트 시연이 사람 시연보다 학습이 쉽다. ACT 논문의 시뮬레이션 실험은 각 50개 시연으로 큐브 이송 스크립트 86% 대 사람 50%, 양팔 삽입 32% 대 20%를 보고하고, "사람 시연의 확률성과 다봉성이 모방학습을 훨씬 어렵게 만든다"고 적었다[47].
- 행동 일관성이 상태 다양성보다 중요하다. 시연 품질 연구는 행동 발산이 작은 일관된 전문가가 정책을 분포 안에 머물게 하며 상태 다양성이 항상 유익하지는 않다고 보고했다[54]. IK 전문가는 행동 일관성이 극대화된 전문가이고, 다양성은 초기 상태 측(공급 위치·방향)의 랜덤화로 확보한다.
- 생성 시연을 늘리면 사람 시연을 능가한다. RoboCasa는 사람 시연 50개(28.8%)보다 생성 시연 3,000개(47.6%)가 높았고[89], Optimus는 과제당 1,000개의 계획기 시연으로 시각 정책 70~80%를 얻었다[90].
- 건설 도메인의 직접 선례가 있다. Ibrahimov 등(2026)은 목재 장부맞춤·파이프·트러스 조립에서 "각 과제에 대해 시뮬레이션에서 시연 1,000개를 수집"했고 "고정 회전의 Cartesian 궤적을 미분 역기구학 컨트롤러로 추종해 매 제어 주기 관절 위치 목표를 출력"했으며, 시작 위치 랜덤화와 2 mm 대역 제한 외란을 넣어 Diffusion Policy를 학습해 실물 zero-shot 100%(목재·파이프), 90~100%(트러스)를 보고했다[91]. 본 계획의 생성 방식과 거의 같다.

리더암 원격조작 대비 얻는 것과 잃는 것을 분명히 한다. 얻는 것은 시연당 비용이 0에 가까워 규모를 자유롭게 늘릴 수 있다는 점, 수집자 편차가 사라져 조건 간 비교가 깨끗해진다는 점, 조건·초기 상태·시드가 완전히 재현된다는 점이다. 잃는 것은 사람 시연에 자연히 들어 있는 복구 행동(실수 후 수정)과 행동의 다양성이다. 이 손실은 4.7.4절의 완화책으로 대응하며, 리더암 시연과의 비교는 후속 연구로 둔다.

4.7.2 수집 단위와 목표 수

각 환경 조건에서 학습용 성공 시연 100개와 검증용 성공 시연 20개, 총 120개를 초기 목표로 한다. 건식·등가 접촉층을 각각 생성하면 총 240개의 완전한 적층 시연이다. 한 개는 세 벽돌을 모두 놓는 전체 에피소드이며 영상 프레임 수나 파지 횟수가 아니다. 네 정책이 같은 데이터를 공유하므로 정책 수만큼 생성량을 네 배로 늘리지 않는다. 생성 비용이 사실상 0이므로 100개에서 검증 성능이 계속 오르면 200·500·1,000개로 곡선을 연장한다(Optimus·Ibrahimov·Isaac Lab Mimic이 과제당 1,000개를 관행으로 쓴다[90][91][92]).

| 데이터 종류 | 조건당 개수 | 목적 |
|---|---|---|
| 학습 시연 | 100개(확장 시 최대 1,000개) | 정책 학습·미세조정 |
| 검증 시연 | 별도 20개 | 손실·과적합 점검. 학습에 넣지 않음 |
| 학습량 비교 | 학습 100개 안의 25·50·100개(확장 시 200·500·1,000) | 시연 증가가 성능에 주는 효과 확인. 중첩 부분집합으로 구성 |
| 노이즈 주입 비교 | 학습 100개 × 노이즈 유/무 두 세트 | 복구 행동 주입의 효과 확인(4.7.4절) |
| 검증 rollout | 별도 초기 상태 20개/체크포인트 | 정책 실행 성능으로 체크포인트 선택 |
| 최종 시험 rollout | 조건당 100개/학습 시드 | 독립 초기 상태에서 자율 실행. 시연 데이터 수에 포함하지 않음 |
표 6. 시연 데이터의 종류와 목표 수 (v2)

4.7.3 문헌이 뒷받침하는 범위와 우리가 정한 부분

ACT 논문은 시뮬레이션 과제에서 스크립트 시연 50개를 사용했고[47], SmolVLA 공식 문서는 약 50개를 시작점으로 권고하며[76], Diffusion Policy의 실험 표에는 과제에 따라 다른 데이터 수가 사용된다[48]. 이 근거는 수십~수백 개의 시연을 출발점으로 삼을 수 있다는 선례이며, 세 벽돌 적층에 100개면 충분하다는 보장은 아니다. 이번 과제는 세 번의 배치를 포함하므로 약 50개의 시작 사례보다 넓은 초기 수집량을 택하고, 25·50·100개 곡선으로 충분성을 직접 점검한다. π0에 대해서도 100개가 충분하다고 논문을 인용할 수는 없으며[49], 같은 데이터 예산에서 적응 가능성을 시험한다. 2.1절의 척도 법칙[56]에 따라 시연 수를 늘려도 개선되지 않는 구간이 나타나면 데이터 부족이 아니라 정밀도 한계의 신호로 해석하고 제어 보완을 검토한다.

4.7.4 개수보다 중요한 생성 구성 — 알려진 함정과 완화책

각 조건에 대해 공급 벽돌 3개의 배치 패턴을 5개 정의하고, 패턴별 학습 20회·검증 4회를 생성한다. 각 패턴 안에서 위치와 방향을 달리한다. 초기 제안 범위는 기준 공급 위치 주변 평면 ±5 mm, 수직축 회전 ±10°이며, 충돌·도달성 검증 후 확정한다. 이 범위의 변화가 곧 문제 (a)가 묻는 조건 변화이다. 목표 적층 형상은 고정한다. 학습 부분집합은 패턴별 5·10·20회를 포함하도록 만들어 25·50·100개 모두 배치 다양성을 갖추게 한다.

스크립트 시연에는 문헌이 지적한 함정이 있고, 각각에 대응한다.

| 함정 | 근거 | 대응 |
|---|---|---|
| 복구 행동이 없어 분포 밖에서 오차가 누적된다 | 모방학습의 분포 변화 문제[53]; "복합 오차로 정책이 복구할 수 없는 상태로 간다"[54] | DART: 생성 중 실행되는 목표에 노이즈를 주입하고 기록되는 행동 라벨은 깨끗한 전문가 행동으로 남겨, 정책이 벗어난 상태에서 돌아오는 데이터를 얻는다[93]. MimicGen도 행동 노이즈 0.05를 기본으로 쓴다[94]. 노이즈 유/무 두 세트를 만들어 효과를 비교한다 |
| 행동이 단봉·과도하게 매끄러워 다양성이 부족하다 | 사람 시연의 다봉성[47] | 다양성은 초기 상태 측(공급 위치·방향, 벽돌 배치 패턴) 랜덤화로 확보[54]; 과제 인스턴스 수를 늘리는 것이 일반화에 유리[95] |
| 타이밍이 정책 제어 주기와 다르다 | 궤적 길이 이상치 제거[90]; 제어 주기 다운샘플[91] | 시연을 정책 제어 주기(20 Hz)로 생성·기록하고, 길이 이상치를 제거한다 |
| 전문가가 특권 상태(정확한 물체 자세)를 쓴다 | "계획기는 학습자가 쓸 수 없는 정보로 동작한다"[90] | 시뮬레이션이므로 허용. 정책의 관측에는 좌표를 넣지 않는다(4.1절). 좌표 입력 비교군은 별도 실험으로 유지(4.6.5절) |
| IK 특이점·관절 한계·충돌 | 미분 IK 문서[86]; 모션 플래닝 시연은 단순 과제에 한정[85] | 감쇠 최소자승 IK, 관절 한계 클리핑, 도달 가능 영역 사전 맵으로 공급·목표 위치 배치, 로봇 베이스 근처 도달 불가 구역을 피하는 호 경로 |
| 스크립트 시연으로 학습한 영상 정책의 일반화 | 긍정: ACT 86%[47], Optimus 70~80%[90], RoboCasa[89]. 부정: ManiSkill2 순수 BC 큐브 집기 1%[85] | 성공 에피소드만 보존, 시각 조건 랜덤화, 필요 시 1,000개까지 확장 |
표 6-1. 스크립트 시연의 함정과 완화책

동일 시연의 연속 프레임이나 겹치는 행동 묶음이 학습·검증에 나뉘지 않도록 에피소드 단위로 분할한다. 생성 시드, 랜덤화 폭, 노이즈 주입 여부를 기록하고 각 배치 패턴에 고르게 배분한다. 비물리적 관통, IK 오차 초과, 정착 후 붕괴는 데이터 오류로 제외하며 제외 이유를 남긴다. 실패 시도는 별도 로그로 보존하고 생성된 성공 개수와 총 시도 개수를 구분한다. 센서 동기화나 접촉 모델이 잘못되었다면 데이터를 늘리기 전에 그 원인을 수정한다.

4.7.5 생성기 구현과 예비 확인

생성기는 다음과 같이 구현한다. ① 벽돌 공급은 그리드 대신 한 번에 한 장을 공급 슬롯에 놓는 공급기(feeder) 모델로 두며, 이는 Hadrian X와 SAM이 실제로 쓰는 방식이다[46]. ② IK는 MuJoCo의 mj_jacSite 야코비안으로 감쇠 최소자승(λ=0.05)을 반복한다[74][86]. SO-ARM101은 5자유도이지만 "그리퍼가 아래를 향한다"는 제약이 1차원이라 위치 3 + 방향 3의 과제가 5관절에서 일관되게 풀린다. ③ 운반 구간은 로봇 베이스 기준 극좌표로 보간해 베이스 근처의 도달 불가 구역을 피한다. ④ 하강 후 시뮬레이터가 주는 TCP 오차를 명령에 적분하는 서보 보정 구간을 두어 위치 구동기의 정상상태 오차를 없앤다. ⑤ SO-ARM101의 고정 턱은 움직이지 않으므로, 파지·배치 목표를 턱 축 방향으로 (벽돌 폭/2 − 고정 턱 패드 위치)만큼 옮겨 고정 턱 패드가 벽돌 옆면에 닿게 한다. ⑥ 기록은 20 Hz, 손목·고정 카메라 128×128, 관절 상태 6, 행동 6(관절 위치 목표)이며 LeRobot 데이터셋 형식이다[68].

문서 작성 중 MuJoCo 3.4.0에서 4.4절 사양(90×42.632×27 mm, 1,800 kg/m³, 20 Hz, 물리 1 ms)의 2+1 적층을 IK 전문가로 실행해 4.9절의 세 지표를 계산했다(공급 위치 ±5 mm 랜덤화, 시드별 1회).

| 조건 | 에피소드 | IK 오차 초과 스텝 | 3D IoU | E_h (mm) | E_f (mm) | 붕괴 벽돌 |
|---|---|---|---|---|---|---|
{prelim}
표 6-2. IK 스크립트 전문가의 예비 실행 결과 (2026-09-17, NVIDIA GPU 없는 PC의 MuJoCo)

이 값은 로봇 파지·학습 성과가 아니라 시연 생성기가 4.4절 사양에서 동작함을 확인한 것이며, 학습 정책이 도달할 수 있는 상한의 참고치다. 에피소드 한 개(약 20초 분량)의 생성 시간은 렌더링을 제외하면 수 초, 렌더링 포함 약 40초(CPU)이므로 조건당 100개 생성에 1시간 남짓, 1,000개에도 반나절이면 충분하다.

"""
replace_section("4.7 시연 데이터의 규모와 구성", "4.8 모르타르의 구현 범위", sec47)

# ---------------------------------------------------------------- 5. references appended
refs = """
[84] James, S., Ma, Z., Rovick Arrojo, D., Davison, A. J. (2020). RLBench: The robot learning benchmark & learning environment. IEEE Robotics and Automation Letters, 5(2), 3019–3026. arXiv:1909.12271
[85] Gu, J., et al. (2023). ManiSkill2: A unified benchmark for generalizable manipulation skills. ICLR 2023. arXiv:2302.04659; ManiSkill 공식 문서, motion-planning demonstrations 및 stack_cube 해법. https://maniskill.readthedocs.io/
[86] Buss, S. R. (2004). Introduction to inverse kinematics with Jacobian transpose, pseudoinverse and damped least squares methods. Technical report, UC San Diego; NVIDIA Isaac Lab, DifferentialIKController (ik_method="dls") 문서.
[87] Zeng, A., et al. (2020). Transporter networks: Rearranging the visual world for robotic manipulation. CoRL 2020. arXiv:2010.14406
[88] Walke, H., et al. (2023). BridgeData V2: A dataset for robot learning at scale. CoRL 2023. arXiv:2308.12952
[89] Nasiriany, S., et al. (2024). RoboCasa: Large-scale simulation of everyday tasks for generalist robots. RSS 2024. arXiv:2406.02523
[90] Dalal, M., et al. (2023). Imitating task and motion planning with visuomotor transformers (Optimus). CoRL 2023. arXiv:2305.16309
[91] Ibrahimov, R., Mozaffari, S., Adel, A. (2026). Contact-rich robotic manipulation in construction via zero-shot learning: A diffusion policy-guided adaptive control. arXiv:2608.22100
[92] NVIDIA Isaac Lab 공식 문서. Imitation learning: teleoperation and Mimic (generate_dataset, 1,000 trials). https://isaac-sim.github.io/IsaacLab/
[93] Laskey, M., Lee, J., Fox, R., Dragan, A., Goldberg, K. (2017). DART: Noise injection for robust imitation learning. CoRL 2017. arXiv:1703.09327
[94] Mandlekar, A., et al. (2023). MimicGen: A data generation system for scalable robot learning using human demonstrations. CoRL 2023. arXiv:2310.17596
[95] Zisselman, E., et al. (2025). Blindfolded experts generalize better. NeurIPS 2025. arXiv:2510.24194
"""
text = text.rstrip() + "\n" + refs

OUT = ROOT / "설계수행계획서_14조_v2_IK시연생성.md"
io.open(OUT, "w", encoding="utf-8").write(text)
print("->", OUT, len(text), "chars")

# ---------------------------------------------------------------- 6. delta document (paste-ready)
delta = f"""# 설계수행계획서 14조 — v2 변경분 (시연 수집 방식: 리더암 원격조작 → 시뮬레이션 내 IK 스크립트 생성)

통합최종본(2026-09-15)은 그대로 두고, 아래 항목만 바꾼 새 청사진이다. 전체 본문은 설계수행계획서_14조_v2_IK시연생성.md 참조.

## 바뀐 곳 한눈에

| 절 | 통합최종본 | v2 |
|---|---|---|
| 2.5 차별성 ① | 실물 리더암 원격조작 시연 데이터셋 | 시뮬레이션 안에서 IK 스크립트 전문가가 생성한 시연 데이터셋 |
| 3.2 목표 1 | 실물 리더암 원격조작으로 수집, 수집자 기록 | IK 스크립트 전문가로 생성, 생성 파라미터(랜덤화 폭·노이즈 주입) 기록 |
| 3.3 범위 | 실물 리더암은 시연 입력 장치로만 사용 | 실물 장비 없음. 시연은 시뮬레이션 안에서 생성 |
| 3.4 제약조건 | 시연 수집 시간, 리더암 운용 안전 | 생성기 구현·검증 시간과 계산 시간. 운용 안전 절차 해당 없음 |
| 4.2 표 2 | 리더암 시연 수집 경로(SO101-Nexus) | IK 시연 생성 경로(mj_jacSite DLS IK 직접 구현 + LeRobot 기록) |
| 4.5 | 보유 리더암으로 관측·행동 짝 수집 | IK 전문가가 생성. 스크립트 시연이 사람 시연보다 학습이 쉽다는 선례[47] |
| **4.7 전체** | 리더암 수집, 4인 분담 60개 | **IK 생성(4.7.1), 목표 수·확장(4.7.2), 문헌 범위(4.7.3), 함정과 완화책(4.7.4), 구현·예비 확인(4.7.5)** |
| 4.10 | 리더암 시연 → 학습 … | IK 스크립트 시연 생성(랜덤화·필터링) → 학습 … |
| 4.11 일정 | 리더암 기록·재생, 시연 수집 | IK 생성기 구현·기록·재생, 시연 생성·필터링 |
| 4.12 역할 | 강건: 리더암 수집; 전원 60개씩 수집 | 강건: 생성기 운용·랜덤화·노이즈 주입·검수; 전원 60개씩 검수 |
| 5.1 산출물 | 시연 데이터와 수집 체계(수집자 ID) | 시연 데이터와 생성 체계(시드·랜덤화 폭·노이즈 여부) |
| 참고문헌 | [1]~[83] | [84]~[95] 추가 (RLBench, ManiSkill, DLS IK, Transporter, BridgeData V2, RoboCasa, Optimus, Ibrahimov 2026, Isaac Lab Mimic, DART, MimicGen, Blindfolded Experts) |

## 왜 바꾸는가 (발표 답변용 한 문단)

시뮬레이터는 벽돌의 정확한 위치를 알고 있으므로 사람이 리더암으로 조작하지 않아도 IK 스크립트 전문가가 시연을 무한히 만들 수 있다. 이것은 로봇 학습 벤치마크의 표준 관행이며(RLBench "시연 무한 공급", ManiSkill 모션 플래닝 시연, Transporter 오라클), 같은 과제·같은 개수에서 스크립트 시연으로 학습한 정책이 사람 시연보다 성공률이 높았고(ACT 86% 대 50%), 건설 도메인에서는 IK로 추종한 Cartesian 궤적 1,000개로 Diffusion Policy를 학습해 실물 zero-shot 100%를 낸 선례가 있다(Ibrahimov 2026). 잃는 것은 사람 시연의 복구 행동과 다양성이며, DART식 노이즈 주입과 초기 상태 랜덤화로 대응하고 노이즈 유/무 두 세트를 비교한다.

## 새 4.7절 전문

{sec47}
## 추가 참고문헌
{refs}
"""
OUT2 = ROOT / "설계수행계획서_14조_v2_변경분.md"
io.open(OUT2, "w", encoding="utf-8").write(delta)
print("->", OUT2)
