"""KICEM 2026 전국대학생학술발표대회 draft: 4 pages in the student sample layout + change notes from page 5.

Layout follows the sample (대학생 샘플.pdf): A4, left/right 16 mm, title block + 요약 box over two columns,
장 10pt / 절 9pt bold / 본문 9pt 150 % / 표 7pt / 그림·표 제목 8pt bold / 참고문헌 8.5pt.  Fonts: 나눔고딕 for headings,
tables and captions (the sample's 나눔스퀘어 is not installed), 나눔명조 for body text (the sample's 조선일보명조 is not
installed).  The submission itself must be typed into the society's HWP template.
"""
import json, sys
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, Frame, FrameBreak, NextPageTemplate, PageTemplate, Paragraph, Spacer, Table,
                                TableStyle, Image, KeepTogether, CondPageBreak, PageBreak, HRFlowable)
from reportlab.graphics.shapes import Drawing, Rect, String, Line, Polygon

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paper_results import collect, collect_multi

HERE = Path(__file__).resolve().parent
FIG = HERE.parent / "outputs" / "final_test"
F = HERE / "fonts"
for name, file in (("NG", "NanumGothic-Regular.ttf"), ("NGB", "NanumGothic-Bold.ttf"), ("NGEB", "NanumGothic-ExtraBold.ttf"),
                   ("NM", "NanumMyeongjo-Regular.ttf"), ("NMB", "NanumMyeongjo-Bold.ttf")):
    pdfmetrics.registerFont(TTFont(name, str(F / file)))
pdfmetrics.registerFont(TTFont("DJ", "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"))   # Latin letters missing in 나눔명조
from reportlab.pdfbase.pdfmetrics import registerFontFamily
registerFontFamily("NM", normal="NM", bold="NMB", italic="NM", boldItalic="NMB")
registerFontFamily("NG", normal="NG", bold="NGB", italic="NG", boldItalic="NGB")

W, H = A4
LM = RM = 16 * mm
TOP, BOT = 30 * mm, 15 * mm
GAP = 7 * mm
FULLW = W - LM - RM
COLW = (FULLW - GAP) / 2
FOOT_H = 11 * mm

S = dict(
    title=ParagraphStyle("t", fontName="NGEB", fontSize=15, leading=19.5, alignment=TA_CENTER),
    sub=ParagraphStyle("s", fontName="NGEB", fontSize=13, leading=17, alignment=TA_CENTER),
    etitle=ParagraphStyle("e", fontName="NGEB", fontSize=10.5, leading=13.7, alignment=TA_CENTER),
    esub=ParagraphStyle("es", fontName="NGEB", fontSize=9.5, leading=12.4, alignment=TA_CENTER),
    author=ParagraphStyle("a", fontName="NGB", fontSize=9, leading=11.7, alignment=TA_CENTER),
    eauthor=ParagraphStyle("ea", fontName="NGB", fontSize=8.5, leading=11, alignment=TA_CENTER),
    abshead=ParagraphStyle("ah", fontName="NGB", fontSize=9, leading=13.5, alignment=TA_CENTER, spaceBefore=6, spaceAfter=4),
    abstract=ParagraphStyle("ab", fontName="NM", fontSize=9, leading=11.7, alignment=TA_JUSTIFY, firstLineIndent=10,
                            leftIndent=8, rightIndent=8),
    kw=ParagraphStyle("k", fontName="NG", fontSize=8, leading=10.4, alignment=TA_LEFT, leftIndent=8, spaceBefore=5, spaceAfter=3),
    h1=ParagraphStyle("h1", fontName="NGEB", fontSize=10, leading=13, spaceBefore=6, spaceAfter=5),
    h2=ParagraphStyle("h2", fontName="NGB", fontSize=9, leading=11.7, spaceBefore=3, spaceAfter=2.5, leftIndent=4),
    body=ParagraphStyle("b", fontName="NM", fontSize=9, leading=13.5, alignment=TA_JUSTIFY, firstLineIndent=10),
    cap=ParagraphStyle("c", fontName="NGB", fontSize=8, leading=9.6, alignment=TA_CENTER, spaceBefore=2, spaceAfter=5),
    tcap=ParagraphStyle("tc", fontName="NGB", fontSize=8, leading=9.6, alignment=TA_LEFT, spaceBefore=5, spaceAfter=2),
    cell=ParagraphStyle("cell", fontName="NG", fontSize=7, leading=8.4, alignment=TA_CENTER),
    cellB=ParagraphStyle("cellB", fontName="NGB", fontSize=7, leading=8.4, alignment=TA_CENTER),
    cellL=ParagraphStyle("cellL", fontName="NG", fontSize=7, leading=8.4, alignment=TA_LEFT),
    note=ParagraphStyle("n", fontName="NG", fontSize=6.5, leading=7.8, alignment=TA_LEFT, spaceBefore=1, spaceAfter=4),
    ref=ParagraphStyle("r", fontName="NM", fontSize=8.5, leading=11, leftIndent=12, firstLineIndent=-12, alignment=TA_JUSTIFY),
    refh=ParagraphStyle("rh", fontName="NGEB", fontSize=10, leading=13, alignment=TA_CENTER, spaceBefore=7, spaceAfter=3),
    # change notes (page 5 onward)
    nh=ParagraphStyle("nh", fontName="NGEB", fontSize=13, leading=17, spaceAfter=4),
    nh2=ParagraphStyle("nh2", fontName="NGB", fontSize=10, leading=13, spaceBefore=8, spaceAfter=3, textColor=colors.HexColor("#1D4E7A")),
    nb=ParagraphStyle("nb", fontName="NG", fontSize=8.6, leading=12.6, leftIndent=9, firstLineIndent=-9, spaceAfter=1.5),
    np=ParagraphStyle("np", fontName="NG", fontSize=8.6, leading=12.6, spaceAfter=3),
    nc=ParagraphStyle("ncell", fontName="NG", fontSize=7.9, leading=10.6, alignment=TA_LEFT),
    ncb=ParagraphStyle("ncellb", fontName="NGB", fontSize=7.9, leading=10.6, alignment=TA_LEFT),
)
GRID = colors.HexColor("#6B7785")
HEADBG = colors.HexColor("#E6E6E6")


def P(text, st="body"):
    return Paragraph(text, S[st])


def pct(s, with_n=True):
    if not s or not s["n"]:
        return "–"
    return f"{s['full']}/{s['n']} ({100 * s['rate']:.0f}%)" if with_n else f"{100 * s['rate']:.0f}%"


def tstyle(extra=()):
    return TableStyle([("LINEABOVE", (0, 0), (-1, 0), 0.9, colors.black), ("LINEBELOW", (0, -1), (-1, -1), 0.9, colors.black),
                       ("INNERGRID", (0, 0), (-1, -1), 0.3, GRID), ("BACKGROUND", (0, 0), (-1, 0), HEADBG),
                       ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 1.4),
                       ("BOTTOMPADDING", (0, 0), (-1, -1), 1.6), ("LEFTPADDING", (0, 0), (-1, -1), 2),
                       ("RIGHTPADDING", (0, 0), (-1, -1), 2)] + list(extra))


def img(path, width):
    from PIL import Image as PI
    w, h = PI.open(path).size
    return Image(str(path), width=width, height=width * h / w)


# --------------------------------------------------------------------------- page decorations
def header(canv, doc):
    canv.saveState()
    canv.setFont("NG", 8.2)
    canv.drawRightString(W - RM, H - 17.2 * mm, "한국건설관리학회 2026 전국대학생학술발표대회 논문집")
    canv.setFont("NG", 6.6); canv.setFillColor(colors.HexColor("#666666"))
    canv.drawRightString(W - RM, H - 20.6 * mm, "2026. 11. 6. (금), 디오션리조트 여수 · ISSN 2287-6073")
    canv.restoreState()


def first_page(canv, doc):
    header(canv, doc)
    canv.saveState()
    y = BOT + FOOT_H - 1.2 * mm
    canv.setLineWidth(0.5)
    canv.line(LM, y, LM + COLW * 0.95, y)
    canv.setFont("NM", 7.5)
    canv.drawString(LM, y - 3.6 * mm, "1) 학생회원, 연세대학교 건설환경공학과 학사과정, jwy01230@yonsei.ac.kr")
    canv.drawString(LM, y - 7.0 * mm, "2) 일반회원, 연세대학교 건설환경공학과 교수(교신저자), hongjo@yonsei.ac.kr")
    canv.restoreState()


def notes_page(canv, doc):
    canv.saveState()
    canv.setFont("NGB", 8); canv.setFillColor(colors.HexColor("#B03A2E"))
    canv.drawString(LM, H - 14 * mm, "수정 내역 (논문 본문이 아님, 제출 시 제외)")
    canv.setFillColor(colors.HexColor("#666666")); canv.setFont("NG", 7.5)
    canv.drawRightString(W - RM, H - 14 * mm, f"{doc.page}쪽")
    canv.setStrokeColor(colors.HexColor("#B03A2E")); canv.setLineWidth(0.6)
    canv.line(LM, H - 16 * mm, W - RM, H - 16 * mm)
    canv.restoreState()


# --------------------------------------------------------------------------- figures and tables
def gate_figure():
    w = COLW
    bw, bh, gap = w * 0.56, 18.5, 5
    x0 = 3
    boxes = [("G0 실행가능성 필터", "집을 수 없는 초기 배치 제외", "#E8EEF3"),
             ("정책: 접근·파지", "영상·관절값 → 관절 목표값", "#FFFFFF"),
             ("G1 파지 검측", "1.5 cm 들고 정지, 식 (1)", "#FFF1D0"),
             ("정책: 운반·하강", "", "#FFFFFF"),
             ("G2 해제 전 검측", "식 (2) 초과 시 보정 후 해제", "#FFF1D0"),
             ("G3 해제 후 검측", "최종 허용오차로 채점", "#FFF1D0"),
             ("다음 블록", "", "#FFFFFF")]
    n = len(boxes)
    h = n * bh + (n - 1) * gap + 6
    d = Drawing(w, h)
    red, blue = colors.HexColor("#B03A2E"), colors.HexColor("#1D4E7A")
    ys = []
    for k, (t, s, c) in enumerate(boxes):
        y = h - 3 - (k + 1) * bh - k * gap
        ys.append(y)
        d.add(Rect(x0, y, bw, bh, fillColor=colors.HexColor(c), strokeColor=colors.HexColor("#33475B"), strokeWidth=0.6))
        if s:
            d.add(String(x0 + bw / 2, y + bh - 8.2, t, fontName="NGB", fontSize=7, textAnchor="middle"))
            d.add(String(x0 + bw / 2, y + 3.4, s, fontName="NG", fontSize=5.8, textAnchor="middle", fillColor=colors.HexColor("#333333")))
        else:
            d.add(String(x0 + bw / 2, y + bh / 2 - 2.5, t, fontName="NGB", fontSize=7, textAnchor="middle"))
        if k < n - 1:
            xm = x0 + bw / 2
            d.add(Line(xm, y, xm, y - gap + 1.5, strokeWidth=0.6))
            d.add(Polygon([xm - 2, y - gap + 3.2, xm + 2, y - gap + 3.2, xm, y - gap + 0.4], fillColor=colors.black, strokeWidth=0))
    xr = x0 + bw
    # G1 fail -> back to pick
    yg1, ypick = ys[2] + bh / 2, ys[1] + bh / 2
    d.add(Line(xr, yg1, xr + 9, yg1, strokeWidth=0.6, strokeColor=red)); d.add(Line(xr + 9, yg1, xr + 9, ypick, strokeWidth=0.6, strokeColor=red))
    d.add(Line(xr + 9, ypick, xr + 2.5, ypick, strokeWidth=0.6, strokeColor=red))
    d.add(Polygon([xr + 3, ypick + 2, xr + 3, ypick - 2, xr + 0.3, ypick], fillColor=red, strokeWidth=0))
    d.add(String(xr + 12, yg1 + 5.5, "불합격: 집게를 열고 4 cm", fontName="NG", fontSize=5.9, fillColor=red))
    d.add(String(xr + 12, yg1 - 1.5, "올린 뒤 정책이 재시도", fontName="NG", fontSize=5.9, fillColor=red))
    d.add(String(xr + 12, yg1 - 10, "시공자 자체 점검에 대응", fontName="NG", fontSize=5.9, fillColor=blue))
    yg2 = ys[4] + bh / 2
    d.add(String(xr + 5, yg2 + 1.5, "놓기 전에 오차를 제거", fontName="NG", fontSize=5.9, fillColor=red))
    d.add(String(xr + 5, yg2 - 7, "시공자 자체 점검에 대응", fontName="NG", fontSize=5.9, fillColor=blue))
    yg3 = ys[5] + bh / 2
    d.add(String(xr + 5, yg3 + 5.5, "불합격: 블록당 1회에 한해", fontName="NG", fontSize=5.9, fillColor=red))
    d.add(String(xr + 5, yg3 - 1.5, "다시 집어 배치", fontName="NG", fontSize=5.9, fillColor=red))
    d.add(String(xr + 5, yg3 - 10, "보완시공 후 재검측에 대응", fontName="NG", fontSize=5.9, fillColor=blue))
    return d


def table_conditions():
    ok, no = "●", "–"
    rows = [[P(h, "cellB") for h in ("조건", "G0", "G1", "재접근<br/>안내", "G2", "G3", "블록<br/>좌표")]]
    spec = [("A 정책 단독", [ok, no, no, no, no], "미사용"), ("B", [ok, ok, no, no, no], "미사용"),
            ("C", [ok, ok, ok, ok, no], "사용"), ("D", [ok, ok, ok, ok, ok], "사용"),
            ("기준선 1 전문가 단독", [ok, no, no, no, no], "사용"), ("기준선 2", [ok, ok, ok, ok, ok], "사용")]
    for lab, marks, xy in spec:
        rows.append([P(lab, "cellL")] + [P(m, "cell") for m in marks] + [P(xy, "cell")])
    t = Table(rows, colWidths=[COLW * f for f in (0.34, 0.10, 0.10, 0.13, 0.10, 0.10, 0.13)])
    t.setStyle(tstyle([("BACKGROUND", (0, 5), (-1, -1), colors.HexColor("#F5F5F5"))]))
    return t


def table_results(r, m):
    T = r["test"]
    d, a = m["diffusion"][1000]["res"], m["act"][1000]["res"]
    rows = [[P("조건", "cellB"), P("Diffusion Policy", "cellB"), "", P("ACT", "cellB"), ""],
            ["", P("완성률", "cellB"), P("IoU", "cellB"), P("완성률", "cellB"), P("IoU", "cellB")]]
    for k, lab in (("A", "A"), ("B", "B"), ("C", "C"), ("D", "D")):
        rows.append([P(lab, "cell"), P(pct(d[k]), "cell"), P(f"{d[k]['iou']:.2f}", "cell"), P(pct(a[k]), "cell"),
                     P(f"{a[k]['iou']:.2f}", "cell")])
    for tag, lab in (("expert", "기준선 1"), ("expert_gate", "기준선 2")):
        e = T[tag]
        rows.append([P(lab, "cell"), P(pct(e["diffusion"]), "cell"), P(f"{e['diffusion']['iou']:.2f}", "cell"),
                     P(pct(e["act"]), "cell"), P(f"{e['act']['iou']:.2f}", "cell")])
    t = Table(rows, colWidths=[COLW * f for f in (0.18, 0.26, 0.15, 0.26, 0.15)])
    t.setStyle(tstyle([("SPAN", (0, 0), (0, 1)), ("SPAN", (1, 0), (2, 0)), ("SPAN", (3, 0), (4, 0)),
                       ("BACKGROUND", (0, 1), (-1, 1), HEADBG), ("BACKGROUND", (0, 6), (-1, -1), colors.HexColor("#F5F5F5"))]))
    return t


def table_seeds(m):
    rows = [[P(h, "cellB") for h in ("정책", "조건", "seed<br/>1000", "seed<br/>1001", "seed<br/>1002", "합산")]]
    for pol, lab in (("diffusion", "Diffusion<br/>Policy"), ("act", "ACT")):
        for k, c in enumerate(("A", "D")):
            cells = [f"{m[pol][sd]['res'][c]['full']}/{m[pol][sd]['res'][c]['n']}" for sd in (1000, 1001, 1002)]
            rows.append([P(lab if k == 0 else "", "cell"), P(c, "cell")] + [P(x, "cell") for x in cells]
                        + [P(pct(m[pol]["pooled"][c]), "cellB")])
    t = Table(rows, colWidths=[COLW * f for f in (0.19, 0.10, 0.155, 0.155, 0.155, 0.245)])
    t.setStyle(tstyle([("SPAN", (0, 1), (0, 2)), ("SPAN", (0, 3), (0, 4)), ("LINEBELOW", (0, 2), (-1, 2), 0.6, colors.black)]))
    return t


def table_noise(r):
    N = r["noise"]
    rows = [[P("계측 오차(표준편차)", "cellB")] + [P(f"{mm_} mm", "cellB") for mm_ in (0, 2, 4)]]
    for pol, lab in (("diffusion", "Diffusion Policy"), ("act", "ACT")):
        rows.append([P(lab, "cellL")] + [P(pct(N[pol][k]), "cell") for k in (0, 2, 4)])
    t = Table(rows, colWidths=[COLW * f for f in (0.34, 0.22, 0.22, 0.22)])
    t.setStyle(tstyle())
    return t


# --------------------------------------------------------------------------- story
def title_block(text):
    return [P("모방학습 기반 조적 로봇의 파지·배치 검측 단계별 효과 분석", "title"),
            P("- 시뮬레이션 벽돌 적층 실험을 중심으로 -", "sub"), Spacer(1, 1),
            P("Stage-wise Effect of Grasp and Placement Inspection on an Imitation-Learned Masonry Robot", "etitle"),
            P("- A Simulation Study of Brick Stacking -", "esub"), Spacer(1, 5),
            P("정원영<super>1)</super>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;김홍조<super>2)</super>", "author"),
            P("Jung, Wonyoung,&nbsp;&nbsp;&nbsp;&nbsp;Kim, Hongjo", "eauthor"), Spacer(1, 6),
            HRFlowable(width="100%", thickness=0.9, color=colors.black, spaceBefore=0, spaceAfter=0),
            P("요&nbsp;&nbsp;&nbsp;약", "abshead"), P(text["abstract"], "abstract"),
            P("키워드: 조적 로봇, 모방학습, 검측, 품질관리", "kw"),
            HRFlowable(width="100%", thickness=0.9, color=colors.black, spaceBefore=1, spaceAfter=0)]


def story(r, m, text, mech):
    s = title_block(text) + [FrameBreak(), NextPageTemplate("later")]
    fl = text["flow"](dict(gate_figure=lambda: KeepTogether([Spacer(1, 3), gate_figure(), P("그림 1. 검측 단계의 구성과 시공 검측 절차의 대응", "cap")]),
                           task_figure=lambda: KeepTogether([Spacer(1, 3), img(FIG / "fig_task.png", COLW * 0.92), P("그림 2. 과제 장면(MuJoCo 시뮬레이션)", "cap")]),
                           bar_figure=lambda: KeepTogether([Spacer(1, 3), img(FIG / "fig_bar.png", COLW * 0.93),
                                                            P("그림 3. 조건별 완성률(학습 seed 1000, 오차 막대는 95% 신뢰구간)", "cap")]),
                           eq1=lambda: KeepTogether([Spacer(1, 3), img(FIG / "fig_eq1.png", COLW), Spacer(1, 3)]),
                           eq2=lambda: KeepTogether([Spacer(1, 3), img(FIG / "fig_eq2.png", COLW), Spacer(1, 3)]),
                           t_cond=lambda: KeepTogether([P("표 1. 비교 조건의 구성", "tcap"), table_conditions(),
                                                        P("* ●: 적용, –: 미적용. 재접근 안내는 G1 불합격 시 다음 블록 위로 손을 옮기는 동작", "note")]),
                           t_res=lambda: KeepTogether([P("표 2. 조건별 완성률과 형상 일치도(학습 seed 1000)", "tcap"), table_results(r, m),
                                                       P("* 같은 초기 배치로 짝지어 비교(Diffusion Policy 40개, ACT 48개)", "note")]),
                           t_seed=lambda: KeepTogether([P("표 3. 학습 seed별 완성 실행 수(A: 정책 단독, D: G1~G3 적용)", "tcap"), table_seeds(m),
                                                        Spacer(1, 4)]),
                           t_noise=lambda: KeepTogether([P("표 4. 계측 오차에 따른 조건 D의 완성률(검증 배치)", "tcap"), table_noise(r),
                                                         Spacer(1, 4)])))
    out = []
    for f in s + fl:
        if isinstance(f, Paragraph) and f.style.name in ("h1", "h2", "rh"):
            out.append(CondPageBreak(36))
        out.append(f)
    out += [P("참고문헌", "refh")] + [P(x, "ref") for x in text["refs"]]
    return out


def build(out, with_notes=True):
    import paper_text_student as PT
    r = collect()
    m = collect_multi()
    mech = json.load(open(FIG / "mech_stats.json"))
    # expert baselines with IoU, paired on each policy's seeds
    for tag, f in (("expert", "expert_baseline_50000_50.json"), ("expert_gate", "expert_gate_replace_50000_50.json")):
        dat = {x["seed"]: x for x in json.load(open(HERE.parent / "outputs" / "gate_val40_v2" / f))}
        for pol in ("diffusion", "act"):
            rows = [dat[sd] for sd in r["seeds"][pol] if sd in dat]
            r["test"][tag][pol]["iou"] = sum(x["iou"] for x in rows) / len(rows)
        r["test"][tag]["all"] = {"full": sum(x["full"] for x in dat.values()), "n": len(dat),
                                 "rate": sum(x["full"] for x in dat.values()) / len(dat)}
    text = PT.text(r, m, mech, P)

    tb = title_block(text)
    title_h = sum(f.wrap(FULLW, H)[1] + (getattr(getattr(f, "style", None), "spaceBefore", 0) or 0)
                  + (getattr(getattr(f, "style", None), "spaceAfter", 0) or 0) for f in tb) + 4 * mm

    doc = BaseDocTemplate(str(out), pagesize=A4, leftMargin=LM, rightMargin=RM, topMargin=TOP, bottomMargin=BOT,
                          title="모방학습 기반 조적 로봇의 파지·배치 검측 단계별 효과 분석", author="정원영, 김홍조")
    body_h = H - TOP - BOT
    pad = dict(leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    f_title = Frame(LM, H - TOP - title_h, FULLW, title_h, id="title", **pad)
    f1l = Frame(LM, BOT + FOOT_H, COLW, body_h - title_h - FOOT_H, id="l1", **pad)
    f1r = Frame(LM + COLW + GAP, BOT, COLW, body_h - title_h, id="r1", **pad)
    f2l = Frame(LM, BOT, COLW, body_h, id="l2", **pad)
    f2r = Frame(LM + COLW + GAP, BOT, COLW, body_h, id="r2", **pad)
    fn = Frame(LM, 16 * mm, FULLW, H - 16 * mm - 20 * mm, id="notes", **pad)
    doc.addPageTemplates([PageTemplate(id="first", frames=[f_title, f1l, f1r], onPage=first_page),
                          PageTemplate(id="later", frames=[f2l, f2r], onPage=header),
                          PageTemplate(id="notes", frames=[fn], onPage=notes_page)])
    st = story(r, m, text, mech)
    if with_notes:
        st += [NextPageTemplate("notes"), PageBreak()] + PT.notes(r, m, mech, S)
    doc.build(st)
    return doc.page


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/home/won/masonry/02_KSARC2026/논문초고_KSARC2026_4쪽.pdf")
    paper_only = build(out.with_name(out.stem + "_본문만.pdf"), with_notes=False)
    total = build(out, with_notes=True)
    print(out, "paper pages:", paper_only, "total pages:", total)
