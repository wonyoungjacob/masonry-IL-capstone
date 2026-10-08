"""KICEM 2026 전국대학생학술발표대회 4-page draft: brick dimensional tolerance vs. an imitation-learned masonry robot.

Layout of build_kicem_student.py.  Numbers: tools/kicem_size_analysis.py (run it first).  Result sentences are written in
results_text() from the summary and checked against it.  Output: 03_KICEM2026_대학생/.
"""
import json, sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import (BaseDocTemplate, Frame, FrameBreak, NextPageTemplate, PageTemplate, Paragraph, Spacer, Table,
                                KeepTogether, CondPageBreak, HRFlowable)

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build_kicem_student as BK
from build_kicem_student import S, P, tstyle, img, COLW, FULLW, W, H, LM, RM, TOP, BOT, GAP
import paper_text_kicem_size as PT
from paper_text_kicem_size import pc

SIM = HERE.parent
FIG = SIM / "outputs" / "kicem_size"
OLDFIG = SIM / "outputs" / "final_test"
OUTDIR = SIM.parent / "03_KICEM2026_대학생"
FOOT_H = 13.5 * mm
TITLE = "모방학습 조적 로봇의 시공 품질에 대한 벽돌 치수 편차의 영향"
SUB = "- KS 치수 허용차와 로봇 시공 자재 관리 기준 -"
ETITLE = "Effect of Brick Dimensional Deviation on the Placement Quality of an Imitation-Learned Masonry Robot"
ESUB = "- KS Dimensional Tolerance and Material Acceptance for Robotic Masonry -"
KEYWORDS = "조적 로봇, 모방학습, 자재 품질관리, 치수 허용차, 반입 검수"

# ---- template fonts (03_KICEM2026_대학생/논문 사용폰트.zip) and sizes read from the society's sample PDF
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
KF = HERE / "fonts" / "kicem"
for _n, _f in (("KN", "조선일보명조.ttf"), ("SQB", "NanumSquareB.ttf"), ("SQEB", "NanumSquareEB.ttf"), ("SQN", "NanumSquareNeo-bRg.ttf")):
    pdfmetrics.registerFont(TTFont(_n, str(KF / _f)))
pdfmetrics.registerFontFamily("KN", normal="KN", bold="KN", italic="KN", boldItalic="KN")
for _k, (_font, _size) in {"title": ("SQEB", 15), "sub": ("SQB", 13), "etitle": ("SQEB", 10.5), "esub": ("SQB", 9.5),
                          "author": ("SQB", 9), "eauthor": ("SQB", 8.5), "abshead": ("SQB", 9), "abstract": ("KN", 9),
                          "kw": ("SQN", 8), "h1": ("SQEB", 10), "h2": ("SQB", 9), "body": ("KN", 9), "cap": ("SQB", 8),
                          "tcap": ("SQB", 8), "cell": ("SQN", 7), "cellB": ("SQB", 7), "cellL": ("SQN", 7),
                          "note": ("SQN", 6.5), "ref": ("KN", 8.5), "refh": ("SQEB", 10)}.items():
    S[_k].fontName, S[_k].fontSize = _font, _size


def header(canv, doc):
    canv.saveState()
    canv.setFont("SQN", 7.9)
    canv.drawRightString(W - RM, H - 17.2 * mm, "한국건설관리학회 2026 전국대학생학술발표대회 논문집")
    canv.setFont("SQN", 6.9); canv.setFillColor(colors.HexColor("#666666"))
    canv.drawRightString(W - RM, H - 20.6 * mm, "2026. 11. 6. (금), 디오션리조트 여수 · ISSN 2287-6073")
    canv.restoreState()


def first_page(canv, doc):
    header(canv, doc)
    canv.saveState()
    y = BOT + FOOT_H - 1.2 * mm
    canv.setLineWidth(0.5); canv.line(LM, y, LM + COLW * 0.95, y)
    canv.setFont("KN", 7.3)
    canv.drawString(LM, y - 3.2 * mm, "1) 학생회원, 연세대학교 건설환경공학과 학사과정, jwy01230@yonsei.ac.kr")
    canv.drawString(LM, y - 6.2 * mm, "2) 학생회원, 연세대학교 건설환경공학과 학사과정, lshkbs1@yonsei.ac.kr")
    canv.drawString(LM, y - 9.2 * mm, "3) 일반회원, 연세대학교 건설환경공학과 부교수(교신저자), hongjo@yonsei.ac.kr")
    canv.restoreState()


def flow_figure():
    from reportlab.graphics.shapes import Drawing, Rect, String, Line, Polygon
    w = COLW
    steps = [("공칭 치수 벽돌로 시연 생성", "정답 좌표 스크립트, 200개"), ("모방학습 정책 학습", "Diffusion Policy"),
             ("치수 편차 벽돌 공급", "공칭 / KS 1/2 / KS / KS×2"), ("자율 시공", "같은 초기 배치, 검측 없음"),
             ("벽돌별 판정과 불량 유형 분류", "합격·미배치·걸침·방향·위치"), ("자재 관리 기준 검토", "반입 검수 허용범위")]
    bw, bh, gap = w * 0.78, 17, 5
    h = len(steps) * bh + (len(steps) - 1) * gap + 4
    d = Drawing(w, h)
    x0 = (w - bw) / 2
    for k, (t, sub) in enumerate(steps):
        y = h - 2 - (k + 1) * bh - k * gap
        fill = "#FFF1D0" if k in (2, 4) else "#FFFFFF"
        d.add(Rect(x0, y, bw, bh, fillColor=colors.HexColor(fill), strokeColor=colors.HexColor("#33475B"), strokeWidth=0.6))
        d.add(String(x0 + bw / 2, y + bh - 7.6, t, fontName="SQB", fontSize=6.8, textAnchor="middle"))
        d.add(String(x0 + bw / 2, y + 3.2, sub, fontName="SQN", fontSize=5.6, textAnchor="middle", fillColor=colors.HexColor("#444444")))
        if k < len(steps) - 1:
            xm = x0 + bw / 2
            d.add(Line(xm, y, xm, y - gap + 1.5, strokeWidth=0.6))
            d.add(Polygon([xm - 2, y - gap + 3.2, xm + 2, y - gap + 3.2, xm, y - gap + 0.4], fillColor=colors.black, strokeWidth=0))
    return KeepTogether([Spacer(1, 3), d, P("그림 1. 연구 절차", "cap")])


def table_ks():
    rows = [[P(h, "cellB") for h in ("구분", "공칭 치수(mm)", "허용차(mm)", "공칭 대비", "축소 벽돌 환산(mm)")]]
    for lab, nom, tol, scaled in (("길이", 190, 5.0, 90.0), ("너비", 90, 3.0, 42.6), ("두께", 57, 2.5, 27.0)):
        rows.append([P(lab, "cell"), P(f"{nom}", "cell"), P(f"±{tol:.1f}", "cell"), P(f"±{100 * tol / nom:.1f}%", "cell"),
                     P(f"{scaled:.1f} ± {scaled * tol / nom:.1f}", "cell")])
    t = Table(rows, colWidths=[COLW * f for f in (0.14, 0.2, 0.18, 0.18, 0.3)])
    t.setStyle(tstyle())
    return KeepTogether([P("표 1. KS L 4201:2022 표준형 벽돌의 치수 허용차", "tcap"), t,
                         P("* 축소 벽돌은 긴 변 90 mm로 같은 비율 축소", "note")])


def table_shape(R):
    Lv = R["levels"]
    rows = [[P(h, "cellB") for h in ("수준", "편차 범위", "3D IoU 평균", "배치 벽돌 위치 오차<br/>중앙값(mm)", "벽돌 합격률")]]
    for lab, tag, rng in (("L0", "s0", "0"), ("L1", "s15", "±1.5%"), ("L2", "s30", "±3%"), ("L3", "s60", "±6%")):
        x = Lv[tag]
        rows.append([P(lab, "cell"), P(rng, "cell"), P(f"{x['iou']:.2f}", "cell"), P(f"{x['exy_placed_mm']:.1f}", "cell"),
                     P(pc(x["bricks_pass"], x["bricks"]), "cell")])
    t = Table(rows, colWidths=[COLW * f for f in (0.12, 0.17, 0.2, 0.3, 0.21)])
    t.setStyle(tstyle())
    return KeepTogether([P("표 4. 수준별 형상 일치도와 배치 오차", "tcap"), t,
                         P("* 위치 오차는 목표 위치로 옮겨진 벽돌(미배치 제외)의 중심 수평 오차", "note")])


def table_levels():
    rows = [[P(h, "cellB") for h in ("수준", "s", "길이 편차 범위<br/>(축소 / 실척)", "의미")]]
    for lab, s, desc in (("L0", 0.0, "공칭 치수(학습과 같음)"), ("L1", 1.5, "KS 허용차의 절반"), ("L2", 3.0, "KS 허용차 수준"),
                         ("L3", 6.0, "KS 허용차의 두 배")):
        rows.append([P(lab, "cell"), P(f"±{s:g}%", "cell"), P(f"±{0.9 * s:.1f} / ±{1.9 * s:.1f} mm", "cell"), P(desc, "cellL")])
    t = Table(rows, colWidths=[COLW * f for f in (0.13, 0.15, 0.34, 0.38)])
    t.setStyle(tstyle())
    return KeepTogether([P("표 2. 치수 편차 수준", "tcap"), t, P("* 길이·너비·두께에 각각 같은 s를 적용", "note")])


def table_results(R):
    Lv = R["levels"]
    rows = [[P(h, "cellB") for h in ("수준", "완성", "벽돌<br/>합격률", "아래 단<br/>합격", "위 단<br/>합격", "미배치", "걸침", "방향<br/>오차", "위치<br/>오차")]]
    for lab, tag in (("L0", "s0"), ("L1", "s15"), ("L2", "s30"), ("L3", "s60")):
        x = Lv[tag]; k = x["kinds"]
        rows.append([P(lab, "cell"), P(f"{x['complete']}/{x['n']}", "cell"), P(pc(x["bricks_pass"], x["bricks"]), "cell"),
                     P(f"{x['lower_pass']}/{2 * x['n']}", "cell"), P(f"{x['top_pass']}/{x['n']}", "cell"),
                     P(str(k["unplaced"]), "cell"), P(str(k["riding"]), "cell"), P(str(k["yaw"]), "cell"), P(str(k["offset"]), "cell")])
    t = Table(rows, colWidths=[COLW * f for f in (0.09, 0.11, 0.12, 0.12, 0.11, 0.11, 0.1, 0.12, 0.12)])
    t.setStyle(tstyle([("LINEAFTER", (4, 0), (4, -1), 0.6, colors.black)]))
    return KeepTogether([P("표 3. 수준별 시공 품질과 불합격 벽돌의 유형", "tcap"), t,
                         P(f"* 불합격 유형은 벽돌 수. 같은 초기 배치 {Lv['s0']['n']}개를 모든 수준에 사용", "note")])


def bin_figure(R):
    fm.fontManager.addfont(str(KF / "NanumSquareNeo-bRg.ttf"))
    plt.rcParams.update({"font.family": fm.FontProperties(fname=str(KF / "NanumSquareNeo-bRg.ttf")).get_name(),
                         "axes.unicode_minus": False, "pdf.fonttype": 42, "axes.spines.top": False, "axes.spines.right": False})
    B = R["bins"]
    names = [k for k in B if B[k]["n"]]
    fig, ax = plt.subplots(figsize=(3.45, 1.9), dpi=400)
    rate = [100 * B[k]["complete"] / B[k]["n"] for k in names]
    ax.bar(range(len(names)), rate, 0.55, color="#2F6DA8")
    for i, k in enumerate(names):
        ax.text(i, rate[i] + 2, f"{B[k]['complete']}/{B[k]['n']}", ha="center", fontsize=5.6)
    ax.set_xticks(range(len(names))); ax.set_xticklabels([n.replace("L", "길이 ") for n in names], fontsize=5.6)
    ax.set_ylabel("완성률 (%)", fontsize=6); ax.set_ylim(0, 105); ax.tick_params(labelsize=5.6, length=2)
    ax.set_xlabel("실제 적용된 길이 편차 (학습 치수 대비)", fontsize=6)
    for s_ in ("left", "bottom"):
        ax.spines[s_].set_linewidth(0.5)
    fig.tight_layout(pad=0.3)
    fig.savefig(FIG / "fig_bins.png", dpi=400, facecolor="white"); fig.savefig(FIG / "fig_bins.pdf", facecolor="white"); plt.close(fig)
    return FIG / "fig_bins.png"


def level_figure(R):
    Lv = R["levels"]
    tags, labs = ["s0", "s15", "s30", "s60"], ["L0\n공칭", "L1\n±1.5%", "L2\n±3%(KS)", "L3\n±6%"]
    kinds = [("ok", "합격", "#2F6DA8"), ("offset", "위치 오차", "#9DB9D3"), ("yaw", "방향 오차", "#C9C9C9"),
             ("riding", "걸침", "#E08A2E"), ("unplaced", "미배치", "#7A7A7A")]
    fig, ax = plt.subplots(figsize=(3.45, 1.95), dpi=400)
    bottom = [0.0] * 4
    for key, lab, col in kinds:
        v = [100 * Lv[t]["kinds"][key] / Lv[t]["bricks"] for t in tags]
        ax.bar(range(4), v, 0.6, bottom=bottom, color=col, label=lab, edgecolor="white", linewidth=0.3)
        for i, x in enumerate(v):
            if x >= 7:
                ax.text(i, bottom[i] + x / 2, f"{x:.0f}", ha="center", va="center", fontsize=5.2,
                        color="white" if key in ("ok", "riding", "unplaced") else "black")
        bottom = [b + x for b, x in zip(bottom, v)]
    ax.set_xticks(range(4)); ax.set_xticklabels(labs, fontsize=5.6); ax.set_ylim(0, 100)
    ax.set_ylabel("벽돌 비율 (%)", fontsize=6); ax.tick_params(labelsize=5.6, length=2)
    ax.legend(fontsize=5.2, frameon=False, loc="upper left", bbox_to_anchor=(1.0, 1.0), handlelength=1.0)
    for s_ in ("left", "bottom"):
        ax.spines[s_].set_linewidth(0.5)
    fig.tight_layout(pad=0.3)
    fig.savefig(FIG / "fig_levels.png", dpi=400, facecolor="white"); fig.savefig(FIG / "fig_levels.pdf", facecolor="white"); plt.close(fig)
    return FIG / "fig_levels.png"


def title_block(text):
    return [P(TITLE, "title"), P(SUB, "sub"), Spacer(1, 1), P(ETITLE, "etitle"), P(ESUB, "esub"), Spacer(1, 5),
            P("정원영<super>1)</super>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;임수현<super>2)</super>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;김홍조<super>3)</super>", "author"),
            P("Jung, Wonyoung,&nbsp;&nbsp;&nbsp;&nbsp;Lim, Soohyun,&nbsp;&nbsp;&nbsp;&nbsp;Kim, Hongjo", "eauthor"), Spacer(1, 6),
            HRFlowable(width="100%", thickness=0.9, color=colors.black, spaceBefore=0, spaceAfter=0),
            P("요&nbsp;&nbsp;&nbsp;약", "abshead"), P(text["abstract"], "abstract"), P("키워드: " + KEYWORDS, "kw"),
            HRFlowable(width="100%", thickness=0.9, color=colors.black, spaceBefore=1, spaceAfter=0)]


def build(out, R):
    text = PT.text(R, P)
    bf = bin_figure(R)
    lf = level_figure(R)
    figs = dict(task_figure=lambda: KeepTogether([Spacer(1, 3), img(OLDFIG / "fig_task.png", COLW * 0.92), P("그림 2. 실험 장면(MuJoCo 시뮬레이션)", "cap")]),
                t_levels=table_levels, t_res=lambda: table_results(R), flow_figure=flow_figure, t_ks=table_ks,
                t_shape=lambda: table_shape(R),
                level_figure=lambda: KeepTogether([Spacer(1, 3), img(lf, COLW * 0.95), P("그림 3. 수준별 벽돌의 합격과 불합격 유형", "cap")]),
                bin_figure=lambda: KeepTogether([Spacer(1, 3), img(bf, COLW * 0.95), P("그림 4. 실제 길이 편차 구간별 완성률(모든 수준 합산)", "cap")]))
    tb = title_block(text)
    title_h = sum(f.wrap(FULLW, H)[1] + (getattr(getattr(f, "style", None), "spaceBefore", 0) or 0)
                  + (getattr(getattr(f, "style", None), "spaceAfter", 0) or 0) for f in tb) + 4 * mm
    doc = BaseDocTemplate(str(out), pagesize=BK.A4, leftMargin=LM, rightMargin=RM, topMargin=TOP, bottomMargin=BOT, title=TITLE,
                          author="정원영, 임수현, 김홍조")
    body_h = H - TOP - BOT
    pad = dict(leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    doc.addPageTemplates([
        PageTemplate(id="first", frames=[Frame(LM, H - TOP - title_h, FULLW, title_h, id="title", **pad),
                                         Frame(LM, BOT + FOOT_H, COLW, body_h - title_h - FOOT_H, id="l1", **pad),
                                         Frame(LM + COLW + GAP, BOT, COLW, body_h - title_h, id="r1", **pad)], onPage=first_page),
        PageTemplate(id="later", frames=[Frame(LM, BOT, COLW, body_h, id="l2", **pad),
                                         Frame(LM + COLW + GAP, BOT, COLW, body_h, id="r2", **pad)], onPage=header)])
    st = tb + [FrameBreak(), NextPageTemplate("later")]
    for f in text["flow"](figs):
        if isinstance(f, Paragraph) and f.style.name in ("h1", "h2"):
            st.append(CondPageBreak(36))
        st.append(f)
    st += [P("참고문헌", "refh")] + [P(x, "ref") for x in text["refs"]]
    doc.build(st)
    return doc.page


if __name__ == "__main__":
    from kicem_size_results import results_text
    R = json.load(open(FIG / "summary.json"))
    R.update(results_text(R))
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else OUTDIR / "논문초고_KICEM2026_대학생_4쪽.pdf"
    print(out, "pages:", build(out, R))
