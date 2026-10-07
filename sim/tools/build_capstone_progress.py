"""Capstone (사회기반시스템종합설계 14조) progress report since the 2026-09-15 design plan.

Short, figure-first.  Each stage is one card: hypothesis -> what we did -> result -> what we learned.
Numbers come from the same collectors as the papers (tools/paper_results.py) and are rounded half up.
Figures: tools/make_capstone_figs.py (run it first).
"""
import json, sys
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, Frame, PageTemplate, Paragraph, Spacer, Table, TableStyle, Image,
                                KeepTogether, CondPageBreak)

HERE = Path(__file__).resolve().parent
SIM = HERE.parent
sys.path.insert(0, str(HERE))
from paper_results import collect, collect_multi

FIG = SIM / "outputs" / "capstone" / "figs"
OLD = SIM.parent / "01_사기설" / "발표자료_실험1_실험2_20260922" / "이미지"
pdfmetrics.registerFont(TTFont("KR", str(HERE / "fonts" / "NotoSansKR-Regular.ttf")))
pdfmetrics.registerFont(TTFont("KRB", str(HERE / "fonts" / "NotoSansKR-Bold.ttf")))
pdfmetrics.registerFontFamily("KR", normal="KR", bold="KRB", italic="KR", boldItalic="KRB")

NAVY, BLUE, ORANGE, GREY = colors.HexColor("#173B57"), colors.HexColor("#2F6DA8"), colors.HexColor("#D9822B"), colors.HexColor("#5B6770")
W, H = A4
LM = RM = 17 * mm
TW = W - LM - RM

S = dict(
    title=ParagraphStyle("t", fontName="KRB", fontSize=17, leading=23, textColor=NAVY),
    sub=ParagraphStyle("s", fontName="KR", fontSize=9, leading=13, textColor=GREY, spaceAfter=8),
    h1=ParagraphStyle("h1", fontName="KRB", fontSize=12.5, leading=17, textColor=NAVY, spaceBefore=9, spaceAfter=4),
    p=ParagraphStyle("p", fontName="KR", fontSize=9.2, leading=14, spaceAfter=3),
    b=ParagraphStyle("b", fontName="KR", fontSize=9.2, leading=14, leftIndent=9, bulletIndent=0, spaceAfter=1.5),
    cell=ParagraphStyle("c", fontName="KR", fontSize=8.6, leading=12.2),
    cellb=ParagraphStyle("cb", fontName="KRB", fontSize=8.6, leading=12.2),
    cap=ParagraphStyle("cap", fontName="KR", fontSize=7.9, leading=11, textColor=GREY, spaceBefore=2, spaceAfter=6),
)


def pct(k, n):
    return int((Decimal(100 * k) / Decimal(n)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def P(t, st="p"):
    return Paragraph(t, S[st])


def bullets(items):
    return [Paragraph(t, S["b"], bulletText="•") for t in items]


def fig(path, width, caption=None):
    from PIL import Image as PI
    w, h = PI.open(path).size
    out = [Image(str(path), width=width, height=width * h / w)]
    if caption:
        out.append(P(caption, "cap"))
    return out


def table(rows, widths, head=True, shade_col0=False):
    data = [[Paragraph(c, S["cellb"] if (head and r == 0) or (shade_col0 and c_i == 0) else S["cell"]) for c_i, c in enumerate(row)]
            for r, row in enumerate(rows)]
    t = Table(data, colWidths=widths, repeatRows=1 if head else 0)
    st = [("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#B5C0C9")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
          ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
          ("LEFTPADDING", (0, 0), (-1, -1), 4.5), ("RIGHTPADDING", (0, 0), (-1, -1), 4.5)]
    if head:
        st.append(("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E6EDF3")))
    if shade_col0:
        st.append(("BACKGROUND", (0, 1 if head else 0), (0, -1), colors.HexColor("#F3F6F8")))
    t.setStyle(TableStyle(st))
    return t


def card(color, rows):
    """가설 / 한 일 / 결과 / 배운 점 card with a coloured label column."""
    data = [[Paragraph(f'<font color="white"><b>{k}</b></font>', S["cell"]), Paragraph(v, S["cell"])] for k, v in rows]
    t = Table(data, colWidths=[17 * mm, TW - 17 * mm])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (0, -1), color), ("BOX", (0, 0), (-1, -1), 0.6, color),
                           ("LINEBELOW", (1, 0), (1, -2), 0.3, colors.HexColor("#D5DDE3")),
                           ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("ALIGN", (0, 0), (0, -1), "CENTER"),
                           ("TOPPADDING", (0, 0), (-1, -1), 3.2), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.8),
                           ("LEFTPADDING", (1, 0), (1, -1), 6)]))
    return t


def numbers():
    m, r = collect_multi(), collect()
    d, a = m["diffusion"][1000]["res"], m["act"][1000]["res"]
    ex = {}
    for tag, f in (("alone", "expert_baseline_50000_50.json"), ("gate", "expert_gate_replace_50000_50.json")):
        dat = json.load(open(SIM / "outputs/gate_val40_v2" / f)); ex[tag] = (sum(x["full"] for x in dat), len(dat))
    lc = json.load(open(SIM / "outputs/final_test/load_check.json"))
    return m, r, d, a, ex, lc


def story():
    m, r, d, a, ex, lc = numbers()
    pd, pa = m["diffusion"]["pooled"], m["act"]["pooled"]
    nd, na = r["noise"]["diffusion"], r["noise"]["act"]
    f = lambda s: f"{pct(s['full'], s['n'])}%({s['full']}/{s['n']})"
    s = []
    s.append(P("모방학습 기반 조적 로봇 제어 시스템 설계: 진행 보고", "title"))
    s.append(P("사회기반시스템종합설계 14조 · 2026-10-01 · 설계수행계획서(9/15) 이후 진행 상황 · 모든 실험은 MuJoCo 시뮬레이션", "sub"))

    # ---------------------------------------------------------------------------------------------- 0
    s.append(P("한눈에 보기", "h1"))
    s.append(P("로봇팔(SO-ARM100: 팔 관절 5개 + 집게 1개)이 바닥에 흩어진 축소 벽돌 3개를 집어 아래 2개, 위 1개로 쌓는다. "
               "사람(여기서는 스크립트)이 보여 준 시연 영상과 관절값만 보고 동작을 배우는 <b>모방학습</b>으로 정책을 만들었다. "
               "<b>완성</b>은 벽돌 3개가 모두 목표 위치 4.5 mm, 방향 5°, 기울기 10° 안에 들어온 경우다."))
    s += fig(SIM / "outputs/final_test/fig_task.png", 105 * mm)
    s += fig(FIG / "journey.png", TW, "그림 1. 단계별 완성률. 실험 1은 초기 배치 범위가 좁아 실험 2·3과 직접 비교하지 않는다. "
             "실험 3은 학습 시드 3개를 합친 값이며, 정책은 실험 2에서 학습한 것을 그대로 썼다.")
    s += bullets([
        "좁은 범위(실험 1)에서는 잘 됐지만, 초기 배치를 넓히자(실험 2) Diffusion 21%, ACT 0%로 떨어졌다.",
        "원인을 파 보니 <b>못 집는 배치가 섞여 있었고</b>, 학습된 정책은 <b>빈손으로 운반하거나 잘못 놓아도 그대로 진행</b>했다.",
        "정책을 다시 학습하지 않고 바깥에 <b>검측 단계 3개</b>(파지 확인, 놓기 전 보정, 놓은 뒤 1회 재배치)를 두자 "
        f"Diffusion {pct(pd['A']['full'], pd['A']['n'])}%→{pct(pd['D']['full'], pd['D']['n'])}%, "
        f"ACT {pct(pa['A']['full'], pa['A']['n'])}%→{pct(pa['D']['full'], pa['D']['n'])}%가 되었다.",
    ])

    # ---------------------------------------------------------------------------------------------- 1
    s.append(CondPageBreak(70 * mm))
    s.append(P("1. 출발점: 설계수행계획서(9/15)와 실제 진행", "h1"))
    s.append(table([["항목", "계획서(9/15)의 계획"],
                    ["연구 질문", "시연으로 배운 조적 정책은 어느 정도 오차로 쌓고 어디서 실패하는가, 그 실패에 맞춘 제어는 얼마나 개선하는가"],
                    ["시연", "리더암 원격조작, 4명이 60개씩 총 240개(건식 120 + 등가 접촉층 120), 초기 배치 ±5 mm·±10°"],
                    ["정책", "ACT, Diffusion Policy, SmolVLA, π0 4종을 같은 데이터로 비교"],
                    ["지표", "3D IoU, 평균 높이 오차, 벽면 기준선 최대 이격 (성공률은 쓰지 않음)"],
                    ["흐름", "Phase 1(~10/13): 환경·시연·ACT 초기 결과 → Phase 2(~12/8): 정책 비교, 실패 원인 분석, 개선 제어 설계·검증"]],
                   [22 * mm, TW - 22 * mm], shade_col0=True))
    s.append(Spacer(1, 5))
    s += fig(FIG / "timeline.png", TW, "그림 2. 9/15 이후 진행. 주황은 계획 변경, 파랑은 실험이다.")

    # ---------------------------------------------------------------------------------------------- 2
    s.append(P("2. 변경 ①: 시연을 사람 조작 대신 스크립트로 생성", "h1"))
    s.append(card(ORANGE, [
        ("바꾼 것", "리더암으로 사람이 조작하던 시연을, 시뮬레이터 안에서 역기구학(IK) 스크립트가 자동으로 만들게 했다."),
        ("이유", "시뮬레이터는 벽돌 좌표를 정확히 알아 시연을 얼마든지 만들 수 있고, 수집자마다 다른 습관이 사라져 조건 비교가 깨끗해진다. "
                "같은 개수일 때 스크립트 시연이 사람 시연보다 학습이 잘 된다는 선례도 있다(ACT 논문: 86% 대 50%)."),
        ("잃은 것", "사람 시연에 자연스럽게 들어가는 실수 후 수정 동작. 실험 1에서 복구 시연을 따로 넣어 보았다."),
    ]))

    # ---------------------------------------------------------------------------------------------- 3
    s.append(CondPageBreak(95 * mm))
    s.append(P("3. 실험 1 (9/18–19): 좁은 초기 배치", "h1"))
    s.append(card(BLUE, [
        ("가설", "① 정상 시연만으로 세 정책 모두 쌓을 수 있다. ② 블록을 쳐서 흐트러뜨린 뒤 다시 집는 <b>복구 시연</b>을 섞으면 더 튼튼해진다."),
        ("한 일", "초기 배치 ±5 mm, ±10°. 정상 시연 119개와 복구 시연을 섞은 데이터 8종으로 학습하고 각 100회 평가했다."),
        ("결과", "정상 시연만: Diffusion 90%, ACT 63%, SmolVLA 2%. 복구 시연을 섞으면 떨어지는 블록은 줄었지만(10→3~7회) "
                "완성률은 90%에서 1~33%로 오히려 낮아졌다."),
        ("배운 점", "떨어지지 않는 것과 정확히 놓는 것은 다르다. 그리고 ±5 mm는 계획서의 질문 (a) \"배치가 달라져도 되는가\"에 답하기에는 너무 쉬웠다."),
    ]))
    s.append(Spacer(1, 4))
    s += fig(FIG / "exp1.png", TW, "그림 3. 실험 1 결과(각 100회).")

    # ---------------------------------------------------------------------------------------------- 4
    s.append(CondPageBreak(60 * mm))
    s.append(P("4. 변경 ②: 실제 시공 조건에 가깝게", "h1"))
    s.append(table([["항목", "실험 1", "실험 2부터", "이유"],
                    ["초기 배치", "±5 mm, ±10°", "±30 mm, ±60°", "좁은 범위는 이미 90%. 조건 변화 적응을 보려면 넓혀야 함"],
                    ["시연 규칙", "실패 후 재시도·복구 포함", "첫 파지에 성공한 깨끗한 시연만", "복구 시연이 정확도를 떨어뜨림(실험 1)"],
                    ["놓은 뒤", "다시 집기 허용", "다시 집기 금지", "모르타르 위에 놓은 벽돌은 다시 들지 않는 것이 시공 원칙"],
                    ["카메라", "앞 + 손목(일부 위)", "앞 + 손목 + 위", "모든 정책에 같은 입력"],
                    ["π0", "계획", "보류", "시간 대비 우선순위"]],
                   [20 * mm, 32 * mm, 42 * mm, TW - 94 * mm], shade_col0=True))

    # ---------------------------------------------------------------------------------------------- 5
    s.append(CondPageBreak(110 * mm))
    s.append(P("5. 실험 2 (9/21–22): 넓은 초기 배치, 깨끗한 시연 240개", "h1"))
    s.append(card(BLUE, [
        ("가설", "깨끗한 시연을 충분히(240개) 주면 넓은 배치에서도 정책이 쌓을 수 있다."),
        ("한 일", "스크립트로 454회 시도해 240개를 채택(학습 200, 검증 40). ACT·Diffusion·SmolVLA를 학습 시드 3개씩 학습해 100개 배치에서 시험했다."),
        ("결과", "완성률 Diffusion 21%(41/200), ACT 0%(0/300), SmolVLA 0%(0/200). "
                "시연을 만드는 스크립트조차 첫 블록 집기에서 70회 실패했다."),
        ("배운 점", "영상에서 세 가지 문제가 보였다. ① 첫 파지 실패 ② 빈손인데 운반 동작을 계속함 ③ 잘못 놓아도 그대로 다음 단계로 감. "
                   "정책은 성공한 시연만 봤기 때문에 '실패한 상태'를 알아채는 법을 배운 적이 없다."),
    ]))
    s.append(Spacer(1, 4))
    s += fig(OLD / "그림03_실험2_수집과정책결과.png", TW * 0.8)
    s += fig(FIG / "exp2_shots.jpg", TW * 0.8, "그림 4. 실험 2. 위: 시연 수집 결과와 정책 시험 결과. 아래: 세 가지 문제 장면.")

    # ---------------------------------------------------------------------------------------------- 6
    s.append(CondPageBreak(118 * mm))
    s.append(P("6. 원인 진단 (9/23): 첫 파지 실패 70건 전수 분류", "h1"))
    s.append(card(BLUE, [
        ("가설", "첫 파지 실패는 학습 문제가 아니라, 처음부터 <b>집을 수 없는 배치</b>가 섞여 있기 때문이다."),
        ("한 일", "실패한 배치를 그대로 재실행해 접촉·관절·위치를 기록하고, 454회 전부에서 집는 자세의 충돌을 계산했다."),
        ("결과", "70건 중 64건이 기하 충돌로 설명됐다. 블록이 로봇에 너무 가까우면 집게가 <b>로봇 몸통</b>에 걸리고(35건), "
                "집게는 7 cm까지 벌어지는데 배치 검사는 블록 사이 1 cm만 봐서 <b>옆 블록</b>을 쳤다(29건)."),
        ("조치", "두 충돌을 미리 계산해 못 집는 배치를 빼는 필터를 만들었다(실패 70건 중 65건 제거, 성공 배치는 384건 중 25건만 빠짐). "
                "집게 여유 1.5 mm를 더하자 필터를 통과한 배치에서 스크립트의 첫 파지가 382회 중 380회 성공했다."),
    ]))
    s.append(Spacer(1, 4))
    s += fig(FIG / "diagnosis.png", TW * 0.58, "그림 5. 로봇 몸통과의 충돌(빨강)은 로봇에 가까운 120~140 mm에 몰려 있다. 각 점은 시도 1회.")

    # ---------------------------------------------------------------------------------------------- 7
    s.append(CondPageBreak(120 * mm))
    s.append(P("7. 실험 3 (9/23–28): 정책 밖에 검측 단계 추가", "h1"))
    s.append(card(BLUE, [
        ("가설", "정책이 실패를 스스로 알아채기를 기대하지 말고, 현장 <b>검측</b>처럼 단계마다 정책 밖에서 확인·보정하면 다시 학습하지 않아도 완성률이 오른다. "
                "그리고 단계마다 효과가 다를 것이다."),
        ("한 일", "실험 2의 정책을 그대로 두고 아래 세 단계를 하나씩 더했다(A→D). 같은 초기 배치에서 비교하고, 학습 시드 3개로 반복했다. "
                "좌표를 아는 스크립트에도 같은 검측을 붙여 보았고, 측정 좌표에 오차를 넣어 보았다."),
    ]))
    s.append(Spacer(1, 4))
    s.append(table([["단계", "언제", "무엇을 보나", "불합격이면"],
                    ["G1 파지 확인", "집은 뒤 1.5 cm 들고 멈췄을 때", "집게 각도 + 손목 하중(시뮬레이션 힘 센서)", "놓고 다음 블록 위로 손을 옮겨 다시 시도(횟수 제한 없음)"],
                    ["G2 놓기 전 보정", "정책이 집게를 열려는 순간", "들고 있는 블록의 위치·방향·높이 오차", "2.5 mm·3°·3 mm를 넘으면 보정한 뒤 놓음"],
                    ["G3 놓은 뒤 재배치", "놓은 직후", "최종 허용오차(4.5 mm, 높이 3 mm, 5°, 기울기 5°)", "블록당 한 번만 다시 집어 놓음(모르타르가 굳기 전 보완시공)"]],
                   [27 * mm, 36 * mm, 50 * mm, TW - 113 * mm], shade_col0=True))
    s.append(Spacer(1, 5))
    s += fig(FIG / "stages.png", TW, "그림 6. (a) 조건 A~D, 학습 시드 1개. "
             "(b) 학습 시드 3개 합산(A와 D)과 좌표를 아는 스크립트(50개 배치).")
    s.append(card(BLUE, [
        ("결과", f"학습 시드 1개: Diffusion {f(d['A'])} → G1 {f(d['B'])} → G2 {f(d['C'])} → G3 {f(d['D'])}, "
                f"ACT {f(a['A'])} → {f(a['B'])} → {f(a['C'])} → {f(a['D'])}. "
                f"시드 3개 합산: Diffusion {f(pd['A'])} → {f(pd['D'])}, ACT {f(pa['A'])} → {f(pa['D'])}. "
                f"좌표를 아는 스크립트도 {pct(*ex['alone'])}% → {pct(*ex['gate'])}%로 올랐다."),
    ]))
    s.append(Spacer(1, 5))
    s += fig(FIG / "episode.jpg", TW * 0.92, "그림 7. 같은 초기 배치(ACT)에서 검측이 작동한 순서와 정책 단독 결과. ①은 위에서, 나머지는 벽면 정면에서 본 장면.")
    s.append(card(BLUE, [
        ("배운 점", "① <b>파지 확인(G1)만으로는 완성률이 오르지 않았다</b>. 빈손 운반은 막지만 놓는 위치가 그대로 틀리기 때문이다. "
                   "② 가장 큰 효과는 <b>놓기 직전 보정(G2)</b>, ACT는 <b>놓은 뒤 재배치(G3)</b>에서 크게 올랐다(29%→54%). "
                   f"③ 파지 판정 {lc['verified']:,}회에서 손목 하중만으로 걸러낸 경우는 {lc['rej_load_only']}건이었다(각도만으로 {lc['rej_angle_only']}건). "
                   "효과를 낸 것은 센서보다 '들어 올린 뒤 판정하는 절차'였다. "
                   f"④ 검측이 쓰는 좌표에 2 mm 오차를 넣으면 완성 횟수가 Diffusion {nd[0]['full']}→{nd[2]['full']}회(/{nd[0]['n']}), "
                   f"ACT {na[0]['full']}→{na[2]['full']}회(/{na[0]['n']})로 줄었다. <b>계측 정확도</b>가 다음 병목이다."),
    ]))
    s.append(Spacer(1, 3))
    s += fig(FIG / "noise.png", TW * 0.42, "그림 8. 검측 좌표 오차에 따른 완성률(검증 배치, 조건 D).")

    # ---------------------------------------------------------------------------------------------- 8
    s.append(CondPageBreak(90 * mm))
    s.append(P("8. 초기 계획 대비 바뀐 점", "h1"))
    s.append(KeepTogether(table([["항목", "계획서(9/15)", "현재", "바꾼 이유"],
                    ["시연 수집", "리더암 원격조작, 4명 분담", "IK 스크립트 자동 생성", "규모·재현성, 수집자 편차 제거"],
                    ["초기 배치", "±5 mm, ±10°, 패턴 5개", "±30 mm, ±60° 무작위 + 못 집는 배치 제외", "좁은 범위는 너무 쉬움(실험 1 90%)"],
                    ["환경 조건", "건식 + 등가 접촉층 2개", "접촉층 1개", "시간 대비 우선순위"],
                    ["정책", "ACT, Diffusion, SmolVLA, π0", "ACT, Diffusion (SmolVLA는 실험 2까지)", "SmolVLA 0~2%, π0 보류"],
                    ["놓은 뒤 규칙", "정하지 않음", "블록당 1회 재배치 허용(실험 2에서는 금지)", "굳기 전 보완시공은 실제 검측 절차와 같음"],
                    ["주 지표", "IoU·높이 오차·벽면 이격 (성공률 미사용)", "완성률 + IoU", "검측 단계의 효과는 합격/불합격으로 읽어야 분명함"],
                    ["개선 제어", "실패 원인 분석 후 선택", "검측 G1~G3", "실패가 파지·배치 단계에 몰려 있음을 확인. <b>계획대로</b>"],
                    ["일정", "Phase 1(~10/13): ACT 초기 결과", "Phase 2의 정책 비교·개선 제어까지 진행", "앞당겨짐"]],
                   [21 * mm, 42 * mm, 50 * mm, TW - 113 * mm], shade_col0=True)))

    # ---------------------------------------------------------------------------------------------- 9
    s.append(CondPageBreak(80 * mm))
    s.append(P("9. 앞으로 바꿀 것과 할 일 (제안)", "h1"))
    s.append(table([["할 일", "왜", "언제"],
                    ["검측이 쓰는 블록 좌표를 시뮬레이터 정답 대신 <b>카메라 영상에서 추정</b>한 값으로 바꿔 다시 측정",
                     "지금 검측은 정확한 좌표를 쓴다. 2 mm 오차에도 완성률이 크게 떨어지므로 현실적인 계측으로 얼마나 유지되는지가 핵심", "~11/10 중간발표 2"],
                    ["검측이 개입한 장면을 시연으로 모아 <b>정책을 다시 학습</b>", "검측이 하던 일을 정책이 배우면 개입이 줄어드는지 확인. 계획서의 '정책만으로 되는 단계와 제어가 필요한 단계의 경계' 질문",
                     "~11/24"],
                    ["계획서 지표(IoU·높이 오차·벽면 이격)를 조건별로 함께 보고", "결과 파일에 이미 기록됨. 계획과의 연결 복원", "10/13 중간발표 1"],
                    ["남은 실패 분석: 시간 초과, 윗단 블록 반복 빈손, ACT의 누르기", "D 조건에서도 남은 25~40%의 원인", "10/13 중간발표 1"],
                    ["축소: 접촉층 2조건 → 1조건, 학습량 곡선(25·50·100개)은 보류", "검측·계측 질문에 시간을 집중", "확정 필요"]],
                   [62 * mm, TW - 62 * mm - 27 * mm, 27 * mm]))
    s.append(Spacer(1, 4))
    s.append(P("현재 상태: 실험 3 결과로 학회 초고 2편(KICEM 2026 대학생 4쪽, KSARC 초록)을 작성했다. 실제 로봇 이식은 계획서대로 범위 밖이다.", "cap"))
    return s


def build(out):
    def page(c, doc):
        c.saveState(); c.setFont("KR", 7.5); c.setFillColor(GREY)
        c.drawRightString(W - RM, 10 * mm, f"14조 진행 보고 · {doc.page}"); c.restoreState()
    doc = BaseDocTemplate(str(out), pagesize=A4, leftMargin=LM, rightMargin=RM, topMargin=15 * mm, bottomMargin=15 * mm,
                          title="14조 진행 보고", author="사회기반시스템종합설계 14조")
    doc.addPageTemplates([PageTemplate(id="p", frames=[Frame(LM, 15 * mm, TW, H - 30 * mm, 0, 0, 0, 0)], onPage=page)])
    doc.build(story())


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else SIM.parent / "01_사기설" / "진행보고" / "진행보고_캡스톤_14조_20261001.pdf"
    build(out)
    print(out)
