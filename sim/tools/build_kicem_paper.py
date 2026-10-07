"""KICEM 2026 2-page draft (A4, two columns), revision 2 (2026-09-28): task figure, equation image, full-width
condition/stage figure + table, construction-standard justifications, construction-management conclusion.
First draft builder kept at outputs/final_test/build_kicem_paper_v1.py."""
import sys
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, Frame, FrameBreak, NextPageTemplate, PageTemplate, Paragraph, Spacer,
                                Table, TableStyle, Image, KeepTogether, CondPageBreak)
from reportlab.graphics.shapes import Drawing, Rect, String, Line, Polygon
from reportlab.graphics import renderPDF

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paper_results import collect, collect_multi

HERE = Path(__file__).resolve().parent
FIG = HERE.parent / "outputs" / "final_test"
pdfmetrics.registerFont(TTFont("KR", str(HERE / "fonts" / "NotoSansKR-Regular.ttf")))
pdfmetrics.registerFont(TTFont("KRB", str(HERE / "fonts" / "NotoSansKR-Bold.ttf")))

W, H = A4
LM = RM = 18 * mm
TOP, BOT = 22 * mm, 16 * mm
GAP = 7 * mm
FULLW = W - LM - RM
COLW = (FULLW - GAP) / 2
TITLE_H = 66 * mm
FOOT_H = 12 * mm

S = dict(
    title=ParagraphStyle("t", fontName="KRB", fontSize=15, leading=20, alignment=TA_CENTER),
    sub=ParagraphStyle("s", fontName="KRB", fontSize=12, leading=16, alignment=TA_CENTER),
    etitle=ParagraphStyle("e", fontName="KRB", fontSize=10.3, leading=13.5, alignment=TA_CENTER),
    author=ParagraphStyle("a", fontName="KR", fontSize=9, leading=12.5, alignment=TA_CENTER),
    kw=ParagraphStyle("k", fontName="KR", fontSize=8, leading=11, alignment=TA_LEFT),
    h1=ParagraphStyle("h1", fontName="KRB", fontSize=9.8, leading=12.5, spaceBefore=4, spaceAfter=1.5),
    h2=ParagraphStyle("h2", fontName="KRB", fontSize=8.7, leading=11.5, spaceBefore=2, spaceAfter=1, leftIndent=3),
    body=ParagraphStyle("b", fontName="KR", fontSize=8.0, leading=11.3, alignment=TA_JUSTIFY, firstLineIndent=8,
                        spaceAfter=1.2),
    cap=ParagraphStyle("c", fontName="KRB", fontSize=7.6, leading=9.6, alignment=TA_CENTER, spaceBefore=1.5, spaceAfter=3),
    tcap=ParagraphStyle("tc", fontName="KRB", fontSize=7.6, leading=9.6, alignment=TA_LEFT, spaceBefore=2, spaceAfter=2),
    cell=ParagraphStyle("cell", fontName="KR", fontSize=6.8, leading=8.3, alignment=TA_CENTER),
    cellB=ParagraphStyle("cellB", fontName="KRB", fontSize=6.8, leading=8.3, alignment=TA_CENTER),
    cellL=ParagraphStyle("cellL", fontName="KR", fontSize=6.8, leading=8.3, alignment=TA_LEFT),
    note=ParagraphStyle("n", fontName="KR", fontSize=6.3, leading=8.0, alignment=TA_LEFT, spaceAfter=2),
    ref=ParagraphStyle("r", fontName="KR", fontSize=7.0, leading=8.7, leftIndent=9, firstLineIndent=-9, spaceAfter=0.4),
    refh=ParagraphStyle("rh", fontName="KRB", fontSize=9.8, leading=12.5, alignment=TA_CENTER, spaceBefore=4, spaceAfter=2),
)


def P(text, st="body"):
    return Paragraph(text, S[st])


def pct(s):
    return f"{s['full']}/{s['n']} ({100 * s['rate']:.0f}%)" if s and s["n"] else "-"


# --------------------------------------------------------------------------- page decorations
def header(canv, doc):
    canv.saveState()
    canv.setFont("KR", 7.2)
    canv.drawRightString(W - RM, H - 12 * mm, "한국건설관리학회 2026 정기학술발표대회 논문집 (Proceedings of KICEM Annual Conference, 2026)")
    canv.setFillColor(colors.HexColor("#555555"))
    canv.drawRightString(W - RM, H - 15.5 * mm, "2026.11.4.(수)~11.6.(금), 디오션리조트 여수 · ISSN 2287-6065")
    canv.restoreState()


def first_page(canv, doc):
    header(canv, doc)
    canv.saveState()
    y = BOT + FOOT_H - 1.5 * mm
    canv.setLineWidth(0.4)
    canv.line(LM, y, LM + 40 * mm, y)
    canv.setFont("KR", 6.4)
    canv.drawString(LM, y - 3.4 * mm, "1) 학생회원, 연세대학교 건설환경공학과 학사과정, jwy01230@yonsei.ac.kr")
    canv.drawString(LM, y - 6.6 * mm, "2) 일반회원, 연세대학교 건설환경공학과 교수, 교신저자, hongjo@yonsei.ac.kr")
    canv.setLineWidth(0.6)
    yk = H - TOP - TITLE_H + 1.5 * mm
    canv.line(LM, yk, W - RM, yk)
    canv.restoreState()


# --------------------------------------------------------------------------- full-width figure 2 + table 1 (page 2 top)
STAGES = [("G0", "실행가능성 필터", "#E8EEF3"), ("정책", "접근·파지", "#FFFFFF"), ("G1", "파지 검측", "#FFF4DC"),
          ("정책", "운반·하강", "#FFFFFF"), ("G2", "해제 전 검측", "#FFF4DC"), ("", "해제", "#FFFFFF"),
          ("G3", "해제 후 검측", "#FFF4DC")]


def stage_flow():
    w, h = FULLW, 62
    d = Drawing(w, h)
    n = len(STAGES)
    gap = 9
    bw = (w - (n - 1) * gap) / n
    bh, y = 25, h - 38
    red, blue = colors.HexColor("#B03A2E"), colors.HexColor("#1D6D9E")
    xs = []
    for k, (tag, name, col) in enumerate(STAGES):
        x = k * (bw + gap)
        xs.append(x)
        d.add(Rect(x, y, bw, bh, fillColor=colors.HexColor(col), strokeColor=colors.HexColor("#33475B"), strokeWidth=0.6))
        if tag:
            d.add(String(x + bw / 2, y + bh - 10, tag, fontName="KRB", fontSize=7.2, textAnchor="middle"))
            d.add(String(x + bw / 2, y + 5, name, fontName="KR", fontSize=6.6, textAnchor="middle"))
        else:
            d.add(String(x + bw / 2, y + bh / 2 - 2.5, name, fontName="KRB", fontSize=7.0, textAnchor="middle"))
        if k < n - 1:
            x1 = x + bw
            d.add(Line(x1, y + bh / 2, x1 + gap - 2, y + bh / 2, strokeWidth=0.6))
            d.add(Polygon([x1 + gap - 3.2, y + bh / 2 + 2, x1 + gap - 3.2, y + bh / 2 - 2, x1 + gap - 0.3, y + bh / 2],
                          fillColor=colors.black, strokeWidth=0))
    notes = {0: ("집을 수 없는 초기 배치 제외", colors.HexColor("#333333")), 2: ("식 (1) 불합격: 열고 올려 재시도", red),
             4: ("식 (2) 초과: 보정 후 해제", red), 6: ("불합격: 블록당 1회 재배치", red)}
    for k, (t, c) in notes.items():
        d.add(String(xs[k] + bw / 2, y - 9, t, fontName="KR", fontSize=5.9, textAnchor="middle", fillColor=c))
    d.add(String((xs[2] + xs[4] + bw) / 2, y + bh + 6, "시공자 자체 점검에 대응 (G1·G2)", fontName="KR", fontSize=6.2,
                 textAnchor="middle", fillColor=blue))
    d.add(Line(xs[2], y + bh + 3, xs[4] + bw, y + bh + 3, strokeWidth=0.5, strokeColor=blue))
    d.add(String(xs[6] + bw / 2, y + bh + 6, "불합격 시 보완시공 후 재검측 (G3)", fontName="KR", fontSize=6.2,
                 textAnchor="middle", fillColor=blue))
    d.add(Line(xs[6], y + bh + 3, xs[6] + bw, y + bh + 3, strokeWidth=0.5, strokeColor=blue))
    return d


def condition_table(r):
    T = r["test"]
    ok, no = "●", "–"
    M = r["multi"]
    head = ["조건", "설명", "G0", "G1", "재접근<br/>안내", "G2", "G3", "정답 좌표<br/>사용", "Diffusion 완성<br/>(seed 1000)",
            "ACT 완성<br/>(seed 1000)", "Diffusion<br/>(3 seed 합산)", "ACT<br/>(3 seed 합산)"]
    rows = [[P(h, "cellB") for h in head]]
    spec = [
        ("A", "정책 단독", [ok, no, no, no, no], "없음", T["diffusion"]["A_policy"], T["act"]["A_policy"]),
        ("B", "A + G1, 불합격 시 제자리 재시도", [ok, ok, no, no, no], "없음", M["diffusion"][1000]["res"]["B"],
         M["act"][1000]["res"]["B"]),
        ("C", "A + G1(재접근 안내) + G2", [ok, ok, ok, ok, no], "사용(상한)", T["diffusion"]["D_pre_release"],
         T["act"]["D_pre_release"]),
        ("D", "C + G3", [ok, ok, ok, ok, ok], "사용(상한)", T["diffusion"]["E_replace"], T["act"]["E_replace"]),
        ("기준선 1", "전문가 스크립트 단독(첫 시도만)", [ok, no, no, no, no], "사용", T["expert"]["diffusion"],
         T["expert"]["act"]),
        ("기준선 2", "전문가 스크립트 + G1~G3", [ok, ok, ok, ok, ok], "사용", T["expert_gate"]["diffusion"],
         T["expert_gate"]["act"]),
    ]
    pooled = {"A": (M["diffusion"]["pooled"]["A"], M["act"]["pooled"]["A"]), "D": (M["diffusion"]["pooled"]["D"], M["act"]["pooled"]["D"])}
    for lab, desc, marks, xy, dd, aa in spec:
        pd, pa = pooled.get(lab, (None, None))
        rows.append([P(lab, "cellB"), P(desc, "cellL")] + [P(m, "cell") for m in marks] +
                    [P(xy, "cell"), P(pct(dd), "cell"), P(pct(aa), "cell"), P(pct(pd) if pd else "–", "cell"),
                     P(pct(pa) if pa else "–", "cell")])
    fr = [0.065, 0.205, 0.035, 0.035, 0.05, 0.035, 0.035, 0.08, 0.115, 0.115, 0.115, 0.115]
    t = Table(rows, colWidths=[FULLW * f for f in fr])
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#8795A1")),
                           ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8EEF3")),
                           ("BACKGROUND", (0, 5), (-1, -1), colors.HexColor("#F4F4F4")),
                           ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                           ("TOPPADDING", (0, 0), (-1, -1), 1.1), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.1),
                           ("LEFTPADDING", (0, 0), (-1, -1), 2), ("RIGHTPADDING", (0, 0), (-1, -1), 2)]))
    return t


def top_block(r):
    """Flowables drawn at the top of page 2 across the full width: figure 2 and table 1."""
    return [stage_flow(), P("그림 2. 검측 단계의 구성과 시공 검측 절차의 대응", "cap"),
            P("표 1. 실험 조건의 구성과 완성률 (시험 배치)", "tcap"), condition_table(r),
            P("●: 적용, –: 미적용. G1은 집게 각도와 손목 하중만 사용함. 재접근 안내·G2·G3는 시뮬레이터 정답 좌표를 사용하므로 "
              "상한값임. A·C·D와 기준선은 모두 완료한 같은 배치로 짝지어 비교하고, B는 완료한 배치 수가 달라 별도 표본임. "
              "Diffusion의 A는 같은 모델·설정의 이전 시험 결과를 배치가 동일한 번호에 한해 재사용함. 3 seed 합산은 seed 1001·1002의 "
              "같은 배치 40개를 더한 값이며, 두 seed의 A는 이전 시험 결과를 재사용함(Diffusion seed 1002는 새로 실행).", "note")]


def _vspace(f):
    st = getattr(f, "style", None)
    return (getattr(st, "spaceBefore", 0) or 0), (getattr(st, "spaceAfter", 0) or 0)


def block_height(flows):
    tot = 0
    for f in flows:
        sb, sa = _vspace(f)
        tot += sb + f.wrap(FULLW, H)[1] + sa
    return tot


# --------------------------------------------------------------------------- body
def noise_table(r):
    N = r["noise"]
    rows = [[P("좌표 측정 잡음 σ", "cellB")] + [P(f"{mm} mm", "cellB") for mm in (0, 2, 4)]]
    for pol, lab in (("diffusion", "Diffusion 완성"), ("act", "ACT 완성")):
        rows.append([P(lab, "cellL")] + [P(pct(N[pol][mm]), "cell") for mm in (0, 2, 4)])
    t = Table(rows, colWidths=[COLW * f for f in (0.31, 0.23, 0.23, 0.23)])
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#8795A1")),
                           ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8EEF3")),
                           ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                           ("TOPPADDING", (0, 0), (-1, -1), 1.1), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.1)]))
    return t


def seed_table(m):
    rows = [[P("정책", "cellB"), P("학습 seed", "cellB"), P("A 정책 단독", "cellB"), P("D 전체 검측", "cellB")]]
    for pol, lab in (("diffusion", "Diffusion"), ("act", "ACT")):
        for sd in (1000, 1001, 1002):
            r = m[pol][sd]["res"]
            rows.append([P(lab if sd == 1000 else "", "cellL"), P(str(sd), "cell"), P(pct(r["A"]), "cell"), P(pct(r["D"]), "cell")])
        pl = m[pol]["pooled"]
        rows.append([P("", "cellL"), P("합산", "cellB"), P(pct(pl["A"]), "cellB"), P(pct(pl["D"]), "cellB")])
    t = Table(rows, colWidths=[COLW * f for f in (0.22, 0.18, 0.30, 0.30)])
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#8795A1")),
                           ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8EEF3")),
                           ("BACKGROUND", (0, 4), (-1, 4), colors.HexColor("#F4F4F4")),
                           ("BACKGROUND", (0, 8), (-1, 8), colors.HexColor("#F4F4F4")),
                           ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                           ("TOPPADDING", (0, 0), (-1, -1), 0.9), ("BOTTOMPADDING", (0, 0), (-1, -1), 0.9)]))
    return t


def img(path, width):
    from PIL import Image as PI
    w, h = PI.open(path).size
    return Image(str(path), width=width, height=width * h / w)


def story(r, text, m):
    s = [P("모방학습 기반 조적 로봇의 파지·배치 검측 단계별 효과 분석", "title"),
         P("- 시뮬레이션 벽돌 적층 실험을 중심으로 -", "sub"), Spacer(1, 2),
         P("Stage-wise Effect of Grasp and Placement Inspection Gates on an Imitation-Learned<br/>"
           "Masonry Robot: A Simulation Study of Brick Stacking", "etitle"), Spacer(1, 5),
         P("정원영<super>1)</super> · 김홍조<super>2)*</super>", "author"),
         P("WONYOUNG JUNG<super>1)</super> · HONGJO KIM<super>2)*</super>", "author"), Spacer(1, 6),
         P("키워드: 조적 자동화, 모방학습, 파지 검증, 검측", "kw"),
         P("Keywords: Masonry Automation, Imitation Learning, Grasp Verification, Construction Inspection", "kw"),
         FrameBreak(), NextPageTemplate("later")]
    s += text["intro"] + text["method1"]
    s += [KeepTogether([img(FIG / "fig_task.png", COLW), P("그림 1. 과제 장면 (MuJoCo 시뮬레이션, 약 1:2.1 축척)", "cap")])]
    s += text["method2"] + [img(FIG / "fig_eq.png", COLW * 0.97), Spacer(1, 2)] + text["method3"]
    s += text["exp"] + text["results"]
    s += [KeepTogether([P("표 2. 좌표 측정 잡음에 따른 조건 D의 완성률 (검증 배치)", "tcap"), noise_table(r),
                        P("각 행은 같은 배치임. 잡음은 게이트가 읽는 블록 좌표에 매 측정마다 더함", "note")])]
    s += text["conclusion"]
    s += [P("참고문헌", "refh")] + [P(x, "ref") for x in text["refs"]]
    # a heading never sits alone at the bottom of a column: move it on only when less than ~3 lines remain
    out = []
    for f in s:
        if isinstance(f, Paragraph) and f.style.name in ("h1", "h2"):
            out.append(CondPageBreak(34))
        out.append(f)
    return out


def build(out):
    import paper_text
    r = collect()
    m = collect_multi()
    r["multi"] = m
    tb = top_block(r)
    tb_h = block_height(tb) + 3 * mm

    def later_page(canv, doc):
        header(canv, doc)
        y = H - TOP
        for f in tb:
            sb, sa = _vspace(f)
            _, h_ = f.wrap(FULLW, H)
            y -= sb + h_
            if isinstance(f, Drawing):
                renderPDF.draw(f, canv, LM, y)
            else:
                f.drawOn(canv, LM, y)
            y -= sa
        canv.saveState(); canv.setLineWidth(0.4); canv.setStrokeColor(colors.HexColor("#999999"))
        canv.line(LM, H - TOP - tb_h + 1.2 * mm, W - RM, H - TOP - tb_h + 1.2 * mm); canv.restoreState()

    doc = BaseDocTemplate(str(out), pagesize=A4, leftMargin=LM, rightMargin=RM, topMargin=TOP, bottomMargin=BOT,
                          title="모방학습 기반 조적 로봇의 파지·배치 검측 단계별 효과 분석", author="정원영, 김홍조")
    body_h = H - TOP - BOT
    f_title = Frame(LM, H - TOP - TITLE_H, FULLW, TITLE_H, id="title", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    f1l = Frame(LM, BOT + FOOT_H, COLW, body_h - TITLE_H - FOOT_H, id="l1", leftPadding=0, rightPadding=0, topPadding=2, bottomPadding=0)
    f1r = Frame(LM + COLW + GAP, BOT, COLW, body_h - TITLE_H, id="r1", leftPadding=0, rightPadding=0, topPadding=2, bottomPadding=0)
    f2l = Frame(LM, BOT, COLW, body_h - tb_h, id="l2", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    f2r = Frame(LM + COLW + GAP, BOT, COLW, body_h - tb_h, id="r2", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    doc.addPageTemplates([PageTemplate(id="first", frames=[f_title, f1l, f1r], onPage=first_page),
                          PageTemplate(id="later", frames=[f2l, f2r], onPage=later_page)])
    doc.build(story(r, paper_text.text(r), m))
    return r, doc.page


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/home/won/masonry/02_KSARC2026/이전판_KICEM2쪽초고/논문초고_KICEM2026_조적로봇검측.pdf")
    r, pages = build(out)
    print(out, "pages:", pages)
