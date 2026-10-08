"""KICEM 2026 student paper: concept note (개조식) to judge whether the construction-management angle works.

Not the paper itself.  Counts come from tools/paper_results.py (all paired test episodes); times from
tools/kicem_time_analysis.py (only the episodes whose gate event log was saved).
"""
import json, sys
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, CondPageBreak

HERE = Path(__file__).resolve().parent
SIM = HERE.parent
sys.path.insert(0, str(HERE))
from paper_results import collect, collect_multi

OUTDIR = SIM.parent / "03_KICEM2026_대학생"
FIG = SIM / "outputs" / "kicem2026"
FIG.mkdir(parents=True, exist_ok=True)
FR, FB = str(HERE / "fonts" / "NotoSansKR-Regular.ttf"), str(HERE / "fonts" / "NotoSansKR-Bold.ttf")
pdfmetrics.registerFont(TTFont("KR", FR)); pdfmetrics.registerFont(TTFont("KRB", FB))
pdfmetrics.registerFontFamily("KR", normal="KR", bold="KRB", italic="KR", boldItalic="KRB")
fm.fontManager.addfont(FR)
plt.rcParams.update({"font.family": fm.FontProperties(fname=FR).get_name(), "axes.unicode_minus": False,
                     "axes.spines.top": False, "axes.spines.right": False})
NAVY, GREY = colors.HexColor("#173B57"), colors.HexColor("#5B6770")
W, H = A4
TW = W - 36 * mm
S = dict(
    t=ParagraphStyle("t", fontName="KRB", fontSize=15, leading=21, textColor=NAVY),
    sub=ParagraphStyle("s", fontName="KR", fontSize=8.8, leading=13, textColor=GREY, spaceAfter=6),
    h=ParagraphStyle("h", fontName="KRB", fontSize=11.5, leading=16, textColor=NAVY, spaceBefore=8, spaceAfter=3),
    h2=ParagraphStyle("h2", fontName="KRB", fontSize=9.6, leading=14, spaceBefore=4, spaceAfter=1),
    b=ParagraphStyle("b", fontName="KR", fontSize=9.1, leading=13.6, leftIndent=10, bulletIndent=1, spaceAfter=1),
    bb=ParagraphStyle("bb", fontName="KR", fontSize=8.8, leading=13, leftIndent=22, bulletIndent=12, spaceAfter=0.5),
    c=ParagraphStyle("c", fontName="KR", fontSize=8.4, leading=12),
    cb=ParagraphStyle("cb", fontName="KRB", fontSize=8.4, leading=12),
    cap=ParagraphStyle("cap", fontName="KR", fontSize=7.8, leading=11, textColor=GREY, spaceBefore=2, spaceAfter=5),
)
COND = {"B": "C_anglelaod_inplace", "C": "D_pre_release", "D": "E_replace"}   # paper label -> run name


def pct(k, n):
    return int((Decimal(100 * k) / Decimal(n)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def B(items, sub=False):
    return [Paragraph(t, S["bb" if sub else "b"], bulletText="–" if sub else "•") for t in items]


def table(rows, widths, shade0=True):
    t = Table([[Paragraph(c, S["cb"] if r == 0 or (shade0 and i == 0) else S["c"]) for i, c in enumerate(row)]
               for r, row in enumerate(rows)], colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#B5C0C9")),
                           ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E6EDF3")),
                           ("BACKGROUND", (0, 1), (0, -1), colors.HexColor("#F3F6F8") if shade0 else colors.white),
                           ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 2.6),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 3.2)]))
    return t


def figure(r, tm):
    t = {p: {k: r["test"][p][v] for k, v in COND.items()} for p in ("diffusion", "act")}
    fig, axs = plt.subplots(1, 2, figsize=(8.6, 2.7), dpi=220)
    ax = axs[0]
    labs = ["놓기 전 보정\n(G2 개입)", "놓은 뒤 불합격\n(G3 대상)", "재배치 후 합격\n(불합격 중)"]
    for j, (p, name, col) in enumerate((("diffusion", "Diffusion Policy", "#2F6DA8"), ("act", "ACT", "#E08A2E"))):
        d = t[p]["D"]
        vals = [(d["corrected"], d["releases"]), (d["bad"], d["releases"]), (d["replaced_ok"], d["replaced"])]
        for i, (k, n) in enumerate(vals):
            x = i + (j - 0.5) * 0.38
            ax.bar(x, 100 * k / n, 0.38, color=col, label=name if i == 0 else None)
            ax.text(x, 100 * k / n + 2, f"{pct(k, n)}%\n({k}/{n})", ha="center", fontsize=6.6, linespacing=1.05)
    ax.set_xticks(range(3)); ax.set_xticklabels(labs, fontsize=7.6); ax.set_ylim(0, 118); ax.tick_params(axis="y", labelsize=7.4)
    ax.set_ylabel("비율 (%)", fontsize=8); ax.legend(fontsize=7, frameon=False, loc="upper right")
    ax.set_title("(a) 배치 1회당 검측 결과 (조건 D, 배치 횟수 기준)", fontsize=8.6)
    ax = axs[1]
    items = [("완성까지 시간\nDiffusion", tm["diffusion_D"]["finish_s_complete"], "#2F6DA8"),
             ("완성까지 시간\nACT", tm["act_D"]["finish_s_complete"], "#E08A2E"),
             ("재배치 1회\n추가 시간", tm["act_D"]["replace_cost_s"], "#8A8A8A"),
             ("헛집기 1회\n복구 시간", tm["act_D"]["retry_cost_s"], "#B0B0B0")]
    for i, (lab, q, col) in enumerate(items):
        ax.bar(i, q["median"], 0.55, color=col)
        ax.errorbar(i, q["median"], yerr=[[q["median"] - q["p25"]], [q["p75"] - q["median"]]], color="#333333", lw=0.8, capsize=2)
        ax.text(i + 0.3, q["median"] + 0.6, f"{q['median']:.1f}초\n(n={q['n']})", fontsize=6.6, va="bottom")
    ax.set_xticks(range(4)); ax.set_xticklabels([x[0] for x in items], fontsize=7.4); ax.tick_params(axis="y", labelsize=7.4)
    ax.set_ylabel("초 (중앙값, 사분위)", fontsize=8); ax.set_ylim(0, 40)
    ax.set_title("(b) 시간 (예비: 사건 기록이 남은 회차만)", fontsize=8.6)
    fig.tight_layout(pad=0.4)
    fig.savefig(FIG / "concept_fig.png", facecolor="white"); plt.close(fig)
    return t


def story():
    r, m = collect(), collect_multi()
    tm = json.load(open(SIM / "outputs/final_test/kicem_time.json"))
    t = figure(r, tm)
    dD, aD, aC = t["diffusion"]["D"], t["act"]["D"], t["act"]["C"]
    dB = t["diffusion"]["B"]
    dBm, dAm = m["diffusion"][1000]["res"]["B"], m["diffusion"][1000]["res"]["A"]   # paired rates, same as KSARC
    nd = r["noise"]["diffusion"]
    s = []
    s.append(Paragraph("KICEM 2026 대학생학술발표대회 4쪽 원고 구상안", S["t"]))
    s.append(Paragraph("2026-10-06 · 적합성 판단용 개조식 요약 · 본문 4쪽은 이 방향이 확정되면 작성 · 수치는 기존 시험 결과 재분석(새 학습·평가 없음)", S["sub"]))

    s.append(Paragraph("1. 제목(안)과 KSARC 초록과의 차이", S["h"]))
    s += B(["제목(안): <b>모방학습 조적 로봇의 시공 중 검측과 재시공에 따른 품질·작업시간 분석</b>",
            "영문(안): Quality and Work Time of In-process Inspection and Rework for an Imitation-Learned Masonry Robot",
            "핵심용어(안): 품질관리, 재시공, 작업시간, 조적 로봇"])
    s.append(Spacer(1, 3))
    s.append(table([["", "KSARC 초록(제출 완료)", "KICEM 4쪽(이번)"],
                    ["질문", "검측 단계를 더하면 완성률이 얼마나 오르는가", "검측·재시공에 얼마의 개입과 시간이 드는가, 어떤 단계를 관리해야 하는가"],
                    ["관점", "로봇 기술: 단계별 성능", "건설관리: 품질관리 절차, 재작업, 작업시간"],
                    ["주 결과", "완성률 변화(35→75%, 0→54% 등)", "검측 개입률, 불합격·재시공률, 재시공 성공률, 완성 시간·재시공 시간"],
                    ["완성률", "본론", "배경 1문단 + 표 1개로 축소, KSARC 발표를 인용"],
                    ["새 분석", "-", "사건 기록(언제 무엇을 했는지)에서 개입·재작업·시간 추출"]],
                   [17 * mm, 62 * mm, TW - 79 * mm]))

    s.append(Paragraph("2. 서론 골격", S["h"]))
    s.append(Paragraph("연구 배경", S["h2"]))
    s += B(["건설 현장 품질관리는 시공자 자체 점검 후 감리 검측, 불합격 시 보완시공 후 재검측 절차를 따름(국토교통부 사업관리 업무수행지침 제56조)",
            "로봇 시공이 도입되면 이 검측을 사람이 아닌 장비가 어느 단계에서 수행할지 정해야 함",
            "모방학습 로봇은 시연만으로 동작을 배우므로 조건 변화에 유연하지만, 성공 시연만 학습해 스스로 불량을 인지하지 못함"])
    s.append(Paragraph("문제 정의", S["h2"]))
    s += B(["로봇 시공에서 검측을 넣으면 품질은 오르나, 그 대가(개입 횟수, 재시공, 시간)가 정량화되지 않음",
            "어느 공정 단계의 검측이 관리 대상인지, 재시공을 몇 번 허용할지 판단할 근거가 없음"])
    s.append(Paragraph("연구 목적", S["h2"]))
    s += B(["모방학습 조적 로봇의 시공 중 검측·재시공을 건설 품질관리 절차로 대응시키고, 단계별 개입률·재시공률·작업시간을 정량화함"])
    s.append(Paragraph("제안 방법", S["h2"]))
    s += B(["학습 정책 밖에 현장 절차와 같은 3단계 검측을 둠"])
    s += B(["G1 자재 취급 확인: 들어 올린 뒤 집게 각도·손목 하중으로 파지 판정",
            "G2 시공 중 검측: 놓기 직전 위치·방향·높이 측정 후 보정",
            "G3 시공 후 검측·보완시공: 놓은 직후 허용오차 판정, 불합격 시 모르타르가 굳기 전 1회 재시공"], sub=True)
    s.append(Paragraph("검증 계획 · 예상 기여", S["h2"]))
    s += B(["축소 벽돌 3개 2단 적층 시뮬레이션, Diffusion Policy·ACT, 같은 초기 배치 40·48개에서 기존 시험 결과를 재분석",
            "기여: 로봇 시공 품질관리에서 '어디를 검측하고 재시공을 몇 번 허용할지'와 '그 시간 비용'을 판단하는 정량 근거"])

    s.append(CondPageBreak(110 * mm))
    s.append(Paragraph("3. 예비 결과 (기존 데이터 재분석)", S["h"]))
    s.append(Image(str(FIG / "concept_fig.png"), width=TW, height=TW * 2.7 / 8.6))
    s.append(Paragraph("그림(안). (a) 학습 시드 1개의 전체 시험 배치. (b) 사건 기록이 저장된 회차만(Diffusion 24회, ACT 25회). "
                       "막대는 중앙값, 선은 사분위 범위.", S["cap"]))
    s += B([f"<b>시공 중 검측(G2)은 거의 매번 개입</b>: 놓기 직전 보정이 Diffusion {pct(dD['corrected'], dD['releases'])}%, "
            f"ACT {pct(aD['corrected'], aD['releases'])}%의 배치에서 발생. 정책이 스스로 허용오차 안에 놓는 경우는 드묾",
            f"<b>시공 후 불합격은 ACT에 집중</b>: 놓은 직후 불합격이 ACT {pct(aC['bad'], aC['releases'])}%(재시공 없는 조건 C), "
            f"Diffusion {pct(dD['bad'], dD['releases'])}%",
            f"<b>재시공 1회로 대부분 해결</b>: ACT 재시공 {aD['replaced']}건 중 {aD['replaced_ok']}건 합격"
            f"({pct(aD['replaced_ok'], aD['replaced'])}%), 완성 {aC['full']}→{aD['full']}개(배치 {aD['n']}개 중)",
            f"<b>시간 비용</b>(예비): 재시공 1회 약 {tm['act_D']['replace_cost_s']['median']:.0f}초, 완성 벽체 1개 중앙값 "
            f"Diffusion {tm['diffusion_D']['finish_s_complete']['median']:.0f}초·ACT {tm['act_D']['finish_s_complete']['median']:.0f}초. "
            "재시공 1회는 벽돌 1장 시공 시간과 비슷한 규모",
            f"<b>자재 취급 확인(G1)만으로는 시간만 소모</b>: G1만 둔 조건에서 Diffusion은 파지 판정 {dB['verified']}회에 헛집기 {dB['retries']}회, "
            f"완성률은 정책 단독보다 오히려 낮음({pct(dAm['full'], dAm['n'])}%→{pct(dBm['full'], dBm['n'])}%)",
            f"<b>검측 장비 정확도 요건</b>: 검측 좌표 오차 2 mm에서 완성 {nd[0]['full']}→{nd[2]['full']}회(/{nd[0]['n']}), "
            f"4 mm에서 {nd[4]['full']}회. 허용오차 4.5 mm 대비 계측 오차를 약 2 mm 아래로 관리해야 함"])

    s.append(Paragraph("4. 4쪽 구성(안)", S["h"]))
    s.append(table([["절", "내용", "분량·그림"],
                    ["1 서론", "위 2장 골격(배경, 문제 정의, 목적, 제안 방법, 검증 계획, 예상 기여)", "0.8쪽"],
                    ["2 연구방법", "현장 검측 절차와 G1~G3 대응표, 판정 기준, 분석 지표 정의(개입률, 불합격률, 재시공 성공률, 완성 시간)", "0.8쪽, 표 1"],
                    ["3 실험", "환경 세팅(한 문단), 평가 방법, 결과: 그림(a)(b), 계측 오차 표", "1.4쪽, 그림 2·표 1"],
                    ["4 고찰", "어느 단계를 관리할지(G2 상시, G3 1회), G1 단독의 시간 낭비, 계측 정확도 요건", "0.6쪽"],
                    ["5 결론", "품질관리 절차 관점의 요약과 한계", "0.4쪽"]],
                   [20 * mm, TW - 48 * mm, 28 * mm]))

    s.append(Paragraph("5. 남은 일과 위험", S["h"]))
    s += B(["<b>시간 자료 보강</b>: 사건 기록 JSON이 남은 회차가 절반 정도라 시간 수치는 예비임. 빠진 회차를 같은 설정으로 다시 돌리면 전체로 확정 가능"
            "(GPU 병렬 약 1~1.5시간 예상)",
            "<b>정책 단독(A)의 시간 비교 불가</b>: 정책에 종료 신호가 없어 완성 시각이 기록되지 않음. 시간 비교는 검측 조건(C·D) 사이로 한정",
            "<b>중복 우려</b>: 같은 실험 데이터이므로 KSARC 발표를 참고문헌으로 밝히고, 완성률은 배경으로만 사용. 두 학회 중복게재 규정은 지도교수 확인 필요",
            "<b>현장 대응의 범위</b>: 축소 시뮬레이션의 결과이므로 실제 공사 시간이나 비용으로 환산하지 않고 상대 비교로만 해석"])
    return s


def main():
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else OUTDIR / "KICEM2026_대학생_구상안.pdf"
    doc = SimpleDocTemplate(str(out), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=15 * mm, bottomMargin=14 * mm,
                            title="KICEM 2026 대학생 원고 구상안", author="정원영")
    doc.build(story())
    print(out)


if __name__ == "__main__":
    main()
