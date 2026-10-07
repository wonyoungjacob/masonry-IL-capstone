"""KSARC (한국건설자동화로보틱스학회) 정기학술대회 abstract draft in the society's one-page template.

Numbers are taken from tools/paper_results.py (same runs as the KICEM student paper) and rounded half up.
"""
import sys
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import BaseDocTemplate, Frame, PageTemplate, Paragraph, Spacer, HRFlowable

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from paper_results import collect, collect_multi

for name, file in (("NG", "NanumGothic-Regular.ttf"), ("NM", "NanumMyeongjo-Regular.ttf"), ("NMB", "NanumMyeongjo-Bold.ttf")):
    pdfmetrics.registerFont(TTFont(name, str(HERE / "fonts" / file)))
pdfmetrics.registerFontFamily("NM", normal="NM", bold="NMB", italic="NM", boldItalic="NMB")

W, H = A4
LM = RM = 26.5 * mm


def pct(s):
    """Percentage rounded half up (62.5 -> 63), from the exact fraction."""
    return str(int((Decimal(100 * s["full"]) / Decimal(s["n"])).quantize(Decimal("1"), rounding=ROUND_HALF_UP)))


def expert_all():
    import json
    root = HERE.parent / "outputs" / "gate_val40_v2"
    out = {}
    for tag, f in (("alone", "expert_baseline_50000_50.json"), ("gate", "expert_gate_replace_50000_50.json")):
        dat = json.load(open(root / f))
        out[tag] = {"full": sum(x["full"] for x in dat), "n": len(dat)}
    return out


def abstract_text():
    m, r = collect_multi(), collect()
    pd, pa = m["diffusion"]["pooled"], m["act"]["pooled"]
    d, a = m["diffusion"][1000]["res"], m["act"][1000]["res"]
    N = r["noise"]
    nd, na = N["diffusion"], N["act"]
    ex = expert_all()
    assert d["B"]["full"] <= d["A"]["full"] and a["B"]["full"] == 0          # grasp check alone did not raise completion
    assert nd[0]["n"] == nd[2]["n"] and na[0]["n"] == na[2]["n"] and ex["alone"]["n"] == ex["gate"]["n"]
    assert min(pd["D"]["n"], pa["D"]["n"]) >= 120
    return (
        # 연구 배경
        "모방학습은 시연만으로 로봇 동작을 학습하므로, 조건이 바뀔 때마다 절차를 다시 설계해야 하는 기존 조적 로봇의 "
        "대안으로 검토되고 있다. "
        # 문제 정의
        "그러나 성공한 시연만으로 학습한 정책은 블록을 놓치거나 어긋나게 놓아도 인지하지 못할 수 있고, 이를 어느 단계에서 "
        "확인해야 하는지는 명확하지 않다. "
        # 연구 목적
        "본 연구의 목적은 모방학습 조적 로봇에 검측 단계를 차례로 더하며 단계별 완성률 변화를 밝히는 것이다. "
        # 방법
        "이를 위해 학습된 정책 밖에 집게 각도와 손목 하중으로 판정하는 파지 검측, 재접근 안내와 놓기 전 위치 보정, 굳기 전 "
        "1회 재배치를 차례로 두었다. "
        # 검증 계획
        "검증은 로봇팔이 축소 벽돌 3개를 2단으로 쌓는 물리 시뮬레이션으로 수행하였으며, Diffusion Policy와 ACT(Action "
        "Chunking with Transformers)를 같은 초기 배치에서 비교하고 시드 반복, 정답 좌표 스크립트 비교, 계측 오차 실험을 "
        "더하였다. "
        # 결과
        f"그 결과 시드 1개(초기 배치 {d['A']['n']}개, {a['A']['n']}개)에서 완성률(Diffusion Policy, ACT 순)은 정책 단독 "
        f"{pct(d['A'])}%, {pct(a['A'])}%에서 파지 검측만으로는 {pct(d['B'])}%, {pct(a['B'])}%로 오르지 않았으나, 놓기 전 "
        f"보정을 더하자 {pct(d['C'])}%, {pct(a['C'])}%로, 재배치까지 더하자 {pct(d['D'])}%, {pct(a['D'])}%로 높아졌다. 시드 "
        f"3개, 정책당 {min(pd['D']['n'], pa['D']['n'])}회 이상에서도 {pct(pd['A'])}%에서 {pct(pd['D'])}%로, {pct(pa['A'])}%에서 "
        f"{pct(pa['D'])}%로 높아졌고, 스크립트도 같은 검측으로 {pct(ex['alone'])}%에서 {pct(ex['gate'])}%로 높아졌다. 반면 "
        f"좌표에 표준편차 2 mm의 오차를 더하면 완성 횟수는 Diffusion Policy가 {nd[0]['n']}회 중 {nd[0]['full']}회에서 "
        f"{nd[2]['full']}회로, ACT가 {na[0]['n']}회 중 {na[0]['full']}회에서 {na[2]['full']}회로 줄었다. "
        # 예상 기여
        "이는 모방학습 조적 로봇의 완성률이 파지 확인보다 배치 전후의 검측에 좌우됨을 보이며, 로봇 시공 품질관리에서 "
        "배치 전후 검측과 계측 정확도를 우선 검토할 근거가 된다.")


def build(out):
    S = dict(
        title=ParagraphStyle("t", fontName="NMB", fontSize=15, leading=21, alignment=TA_CENTER, spaceAfter=12),
        etitle=ParagraphStyle("e", fontName="NMB", fontSize=15, leading=21, alignment=TA_CENTER, spaceAfter=14),
        author=ParagraphStyle("a", fontName="NM", fontSize=9, leading=13, alignment=TA_CENTER, spaceAfter=7),
        body=ParagraphStyle("b", fontName="NM", fontSize=9, leading=14.8, alignment=TA_JUSTIFY, leftIndent=6, rightIndent=6),
        kw=ParagraphStyle("k", fontName="NM", fontSize=9, leading=13.5, leftIndent=6, spaceBefore=12, spaceAfter=6),
    )
    text = abstract_text()

    def page(canv, doc):
        canv.saveState()
        y = 36 * mm
        canv.setLineWidth(0.7); canv.line(LM, y, W - RM, y)
        canv.setFont("NG", 8.2)
        canv.drawString(LM, y - 4.3 * mm, "1 학생회원 · 연세대학교 건설환경공학과 학사과정(jwy01230@yonsei.ac.kr)")
        canv.drawString(LM, y - 8.3 * mm, "2 일반회원 · 연세대학교 건설환경공학과 석사과정(hyunjoonkang@yonsei.ac.kr)")
        canv.drawString(LM, y - 12.3 * mm, "3 교신저자 · 연세대학교 건설환경공학과 부교수(Corresponding Author, hongjo@yonsei.ac.kr)")
        canv.restoreState()

    doc = BaseDocTemplate(str(out), pagesize=A4, leftMargin=LM, rightMargin=RM, topMargin=27 * mm, bottomMargin=40 * mm,
                          title="모방학습 조적 로봇의 파지·배치 검측 단계별 효과", author="정원영, 강현준, 김홍조")
    fr = Frame(LM, 40 * mm, W - LM - RM, H - 27 * mm - 40 * mm, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    doc.addPageTemplates([PageTemplate(id="p", frames=[fr], onPage=page)])
    doc.build([
        Paragraph("모방학습 조적 로봇의 파지·배치 검측 단계별 효과", S["title"]),
        Paragraph("Stage-wise Effect of Grasp and Placement Inspection<br/>on an Imitation-Learned Masonry Robot", S["etitle"]),
        Paragraph("정원영<super>1</super> • 강현준<super>2</super> • 김홍조<super>3</super>", S["author"]),
        Paragraph("Jung, Wonyoung • Kang, Hyunjoon • Kim, Hongjo", S["author"]), Spacer(1, 8),
        HRFlowable(width="100%", thickness=0.8, color=colors.black, spaceAfter=8),
        Paragraph(text, S["body"]),
        Paragraph("<b>핵심용어</b> : 조적 로봇, 모방학습, 검측, 계측 오차", S["kw"]),
        HRFlowable(width="100%", thickness=0.8, color=colors.black),
    ])
    return text


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/home/won/masonry/02_KSARC2026/초록_KSARC2026_조적로봇검측.pdf")
    t = build(out)
    print(out)
    print("어절 수:", len(t.split()), "| 글자 수(공백 제외):", len(t.replace(" ", "")), "| 문장 수:", t.count("다. ") + 1)
    print(t)
