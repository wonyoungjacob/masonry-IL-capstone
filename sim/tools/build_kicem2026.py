"""KICEM 2026 전국대학생학술발표대회 4-page draft: inspection, rework and work time of an imitation-learned masonry robot.

Layout, fonts and page frames are those of build_kicem_student.py (the student sample layout).  Numbers: tools/kicem_time_analysis.py
(run it first) and paper_results.collect_multi.  Output: 03_KICEM2026_대학생/.
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
from reportlab.graphics.shapes import Drawing, Rect, String, Line, Polygon

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build_kicem_student as BK
from build_kicem_student import S, P, tstyle, img, header, COLW, FULLW, W, H, LM, RM, TOP, BOT, GAP, FOOT_H, HEADBG
from paper_results import collect_multi
import paper_text_kicem2026 as PT

SIM = HERE.parent
FIG = SIM / "outputs" / "kicem2026"
FIG.mkdir(parents=True, exist_ok=True)
OLDFIG = SIM / "outputs" / "final_test"
OUTDIR = SIM.parent / "03_KICEM2026_대학생"
FOOT_H = 13.5 * mm      # three author footnotes


def first_page(canv, doc):
    header(canv, doc)
    canv.saveState()
    y = BOT + FOOT_H - 1.2 * mm
    canv.setLineWidth(0.5); canv.line(LM, y, LM + COLW * 0.95, y)
    canv.setFont("NM", 7.5)
    canv.drawString(LM, y - 3.2 * mm, "1) 학생회원, 연세대학교 건설환경공학과 학사과정, jwy01230@yonsei.ac.kr")
    canv.drawString(LM, y - 6.2 * mm, "2) 학생회원, 연세대학교 건설환경공학과 학사과정, lshkbs1@yonsei.ac.kr")
    canv.drawString(LM, y - 9.2 * mm, "3) 일반회원, 연세대학교 건설환경공학과 부교수(교신저자), hongjo@yonsei.ac.kr")
    canv.restoreState()


# --------------------------------------------------------------------------------------------- figures
def equations():
    from make_paper_figs import equation, FIG as PF
    equation("kicem_eq1.png", r"$\theta_{\mathrm{jaw}} > \theta_{\mathrm{th}}\ \ \wedge\ \ (\bar{F}_z - m_g g) \geq F_{\mathrm{th}}$", "", "(식 1)")
    equation("kicem_eq2.png", r"$\Vert \mathbf{e}_{xy} \Vert > \delta_{xy}\ \ \vee\ \ |e_\psi| > \delta_\psi\ \ \vee\ \ e_z > \delta_z$", "", "(식 2)")
    return PF / "kicem_eq1.png", PF / "kicem_eq2.png"


def gate_figure():
    w = COLW
    bw, bh, gap, x0 = w * 0.54, 18.5, 5, 3
    boxes = [("G0 실행가능성 검토", "집을 수 없는 초기 배치 제외", "#E8EEF3"),
             ("정책: 접근·파지", "영상·관절값 → 관절 목표값", "#FFFFFF"),
             ("G1 자재 취급 확인", "들어 올린 뒤 식 (1)", "#FFF1D0"),
             ("정책: 운반·하강", "", "#FFFFFF"),
             ("G2 시공 중 검측", "식 (2) 초과 시 보정 후 놓기", "#FFF1D0"),
             ("G3 시공 후 검측", "허용오차로 판정", "#FFF1D0"),
             ("다음 블록", "", "#FFFFFF")]
    n = len(boxes); h = n * bh + (n - 1) * gap + 6
    d = Drawing(w, h)
    red, blue = colors.HexColor("#B03A2E"), colors.HexColor("#1D4E7A")
    ys = []
    for k, (t, s, c) in enumerate(boxes):
        y = h - 3 - (k + 1) * bh - k * gap; ys.append(y)
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
    notes = {0: ("", "시공 전 작업 여건 검토"), 2: ("불합격: 운반하지 않고 다시 집기", "시공자 자체 점검"),
             4: ("놓기 전에 오차를 제거", "시공자 자체 점검"), 5: ("불합격: 블록당 1회 다시 놓기", "보완시공 후 재검측")}
    for k, (r_, b_) in notes.items():
        yc = ys[k] + bh / 2
        if r_:
            d.add(String(xr + 4, yc + 1.5, r_, fontName="NG", fontSize=5.9, fillColor=red))
        d.add(String(xr + 4, yc - 7 if r_ else yc - 2, b_, fontName="NG", fontSize=5.9, fillColor=blue))
    return d


def time_figure(T):
    fm.fontManager.addfont(str(HERE / "fonts" / "NanumGothic-Regular.ttf"))
    plt.rcParams.update({"font.family": fm.FontProperties(fname=str(HERE / "fonts" / "NanumGothic-Regular.ttf")).get_name(),
                         "axes.unicode_minus": False, "axes.spines.top": False, "axes.spines.right": False})
    fig, ax = plt.subplots(figsize=(3.45, 1.85), dpi=400)
    col = {"diffusion": "#2F6DA8", "act": "#E08A2E"}
    for j, (p, name) in enumerate((("diffusion", "Diffusion Policy"), ("act", "ACT"))):
        for i, c in enumerate("BCD"):
            v = T[f"{p}_{c}"]["time_per_accepted_wall_s"]
            x = i + (j - 0.5) * 0.38
            if v is None:
                ax.text(x, 8, "완성\n없음", ha="center", fontsize=5.2, color="#555555"); continue
            ax.bar(x, v, 0.38, color=col[p], label=name if i == 1 else None)
            ax.text(x, v + 8, f"{v:.0f}", ha="center", fontsize=5.6)
    ax.set_xticks(range(3)); ax.set_xticklabels(["B\nG1", "C\nG1+G2", "D\nG1+G2+G3"], fontsize=5.8)
    ax.set_ylabel("합격 벽체당 투입 시간 (초)", fontsize=6); ax.tick_params(axis="y", labelsize=5.6, length=2); ax.tick_params(axis="x", length=0)
    ax.legend(fontsize=5.6, frameon=False, loc="upper right")
    for s_ in ("left", "bottom"):
        ax.spines[s_].set_linewidth(0.5)
    fig.tight_layout(pad=0.3)
    fig.savefig(FIG / "fig_time_per_wall.png", dpi=400, facecolor="white"); plt.close(fig)
    return FIG / "fig_time_per_wall.png"


# --------------------------------------------------------------------------------------------- tables
def table_conditions():
    ok, no = "●", "–"
    rows = [[P(h, "cellB") for h in ("조건", "G1", "G1 불합격 시<br/>다음 블록 안내", "G2", "G3", "대응하는 검측 수준")]]
    for lab, marks, desc in (("A", [no, no, no, no], "검측 없음"), ("B", [ok, no, no, no], "자재 취급만 확인"),
                             ("C", [ok, ok, ok, no], "시공 중 검측까지"), ("D", [ok, ok, ok, ok], "보완시공까지")):
        rows.append([P(lab, "cell")] + [P(x, "cell") for x in marks] + [P(desc, "cellL")])
    t = Table(rows, colWidths=[COLW * f for f in (0.09, 0.09, 0.22, 0.09, 0.09, 0.42)])
    t.setStyle(tstyle())
    return KeepTogether([P("표 1. 검측 수준별 비교 조건", "tcap"), t,
                         P("* 모든 조건에 G0 적용, 정책은 같음. ●: 적용, –: 미적용", "note")])


def table_quality(T, m):
    rows = [[P(h, "cellB") for h in ("정책", "조건", "파지<br/>기각률", "G2<br/>개입률", "G3<br/>불합격률", "보완시공<br/>합격", "완성")]]
    for p, name in (("diffusion", "Diffusion<br/>Policy"), ("act", "ACT")):
        for k, c in enumerate("BCD"):
            x = T[f"{p}_{c}"]
            g2 = PT.pc(x["g2_corrected"], x["placements"]) if x["placements"] else "–"
            g3 = PT.pc(x["g3_failed"], x["placements"]) if x["placements"] else "–"
            rp = f"{x['replaced_ok']}/{x['replaced']}" if c == "D" else "–"
            rows.append([P(name if k == 0 else "", "cell"), P(c, "cell"), P(PT.pc(x["grasp_rejected"], x["grasp_checks"]), "cell"),
                         P(g2, "cell"), P(g3, "cell"), P(rp, "cell"), P(f"{x['complete']}/{x['layouts']}", "cell")])
    t = Table(rows, colWidths=[COLW * f for f in (0.17, 0.09, 0.15, 0.14, 0.15, 0.15, 0.15)])
    t.setStyle(tstyle([("SPAN", (0, 1), (0, 3)), ("SPAN", (0, 4), (0, 6)), ("LINEBELOW", (0, 3), (-1, 3), 0.6, colors.black)]))
    return KeepTogether([P("표 2. 검측 수준별 품질 지표", "tcap"), t,
                         P("* 기각률은 파지 판정 수, 개입률·불합격률은 배치 수 기준. 완성 수의 단계별 비교는 정원영 외(2026)에 보고", "note")])


def table_time(T):
    rows = [[P(h, "cellB") for h in ("정책", "조건", "완성 시간<br/>중앙값(초)", "복구 시간<br/>비중", "보완시공<br/>1회(초)", "합격 벽체당<br/>투입 시간(초)")]]
    for p, name in (("diffusion", "Diffusion<br/>Policy"), ("act", "ACT")):
        for k, c in enumerate("BCD"):
            x = T[f"{p}_{c}"]
            fin = f"{x['finish_s']['median']:.1f}" if x["finish_s"] else "–"
            rep = f"{x['replace_s']['median']:.1f}" if x["replace_s"] else "–"
            tw = f"{x['time_per_accepted_wall_s']:.0f}" if x["time_per_accepted_wall_s"] else "–"
            rows.append([P(name if k == 0 else "", "cell"), P(c, "cell"), P(fin, "cell"), P(PT.hu(x["recover_time_share"]), "cell"),
                         P(rep, "cell"), P(tw, "cell")])
    t = Table(rows, colWidths=[COLW * f for f in (0.17, 0.09, 0.18, 0.17, 0.17, 0.22)])
    t.setStyle(tstyle([("SPAN", (0, 1), (0, 3)), ("SPAN", (0, 4), (0, 6)), ("LINEBELOW", (0, 3), (-1, 3), 0.6, colors.black)]))
    return KeepTogether([P("표 3. 검측 수준별 작업시간 지표", "tcap"), t,
                         P("* 시뮬레이션 제어 시간. 미완성 실행은 제한 시간 90초를 투입 시간으로 계산", "note")])


# --------------------------------------------------------------------------------------------- story
def title_block(text):
    return [P("모방학습 조적 로봇의 시공 중 검측과 보완시공에 따른 품질 및 작업시간 분석", "title"),
            P("- 시뮬레이션 벽돌 적층 실험을 중심으로 -", "sub"), Spacer(1, 1),
            P("Quality and Work Time of In-process Inspection and Rework for an Imitation-Learned Masonry Robot", "etitle"),
            P("- A Simulation Study of Brick Stacking -", "esub"), Spacer(1, 5),
            P("정원영<super>1)</super>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;임수현<super>2)</super>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;김홍조<super>3)</super>", "author"),
            P("Jung, Wonyoung,&nbsp;&nbsp;&nbsp;&nbsp;Lim, Soohyun,&nbsp;&nbsp;&nbsp;&nbsp;Kim, Hongjo", "eauthor"), Spacer(1, 6),
            HRFlowable(width="100%", thickness=0.9, color=colors.black, spaceBefore=0, spaceAfter=0),
            P("요&nbsp;&nbsp;&nbsp;약", "abshead"), P(text["abstract"], "abstract"),
            P("키워드: 조적 로봇, 모방학습, 품질관리, 보완시공, 작업시간", "kw"),
            HRFlowable(width="100%", thickness=0.9, color=colors.black, spaceBefore=1, spaceAfter=0)]


def build(out):
    T = json.load(open(SIM / "outputs/final_test/kicem_time.json"))
    m = collect_multi()
    text = PT.text(T, m, P)
    eq1, eq2 = equations()
    tf = time_figure(T)
    figs = dict(gate_figure=lambda: KeepTogether([Spacer(1, 3), gate_figure(), P("그림 1. 검측 단계와 시공 품질관리 절차의 대응", "cap")]),
                task_figure=lambda: KeepTogether([Spacer(1, 3), img(OLDFIG / "fig_task.png", COLW * 0.92), P("그림 2. 실험 장면(MuJoCo 시뮬레이션)", "cap")]),
                eq1=lambda: KeepTogether([Spacer(1, 3), img(eq1, COLW), Spacer(1, 3)]),
                eq2=lambda: KeepTogether([Spacer(1, 3), img(eq2, COLW), Spacer(1, 3)]),
                t_cond=table_conditions, t_quality=lambda: table_quality(T, m), t_time=lambda: table_time(T),
                time_figure=lambda: KeepTogether([Spacer(1, 3), img(tf, COLW * 0.95), P("그림 3. 검측 수준별 합격 벽체당 투입 시간", "cap")]))
    tb = title_block(text)
    title_h = sum(f.wrap(FULLW, H)[1] + (getattr(getattr(f, "style", None), "spaceBefore", 0) or 0)
                  + (getattr(getattr(f, "style", None), "spaceAfter", 0) or 0) for f in tb) + 4 * mm
    doc = BaseDocTemplate(str(out), pagesize=BK.A4, leftMargin=LM, rightMargin=RM, topMargin=TOP, bottomMargin=BOT,
                          title="모방학습 조적 로봇의 시공 중 검측과 보완시공에 따른 품질 및 작업시간 분석", author="정원영, 임수현, 김홍조")
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
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else OUTDIR / "논문초고_KICEM2026_대학생_4쪽.pdf"
    print(out, "pages:", build(out))
