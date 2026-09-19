"""Build the 3-page Korean PDF summary of the 2026-09-18/19 experiments from outputs/eval_*.json.

Usage:  cd sim && python tools/make_report.py [-o ../실험보고서.pdf]

The report uses only the three blueprint 4.9 metrics (3D IoU, E_h, E_f) as results; the number of episodes
with a fallen brick is shown beside them as a diagnostic, because the three metrics alone do not separate
"collapsed" from "standing but offset".
"""
import argparse, json, statistics as st
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, Frame, PageBreak, PageTemplate, Paragraph, Spacer,
                                Table, TableStyle)

HERE = Path(__file__).resolve().parent
SIM = HERE.parent
FONT_DIRS = [HERE / "fonts", Path("/tmp/claude-1000/-home-won/df8f03e8-8d43-4f99-8e72-2fff6a7571f6/scratchpad")]

ACCENT = colors.HexColor("#1f3864")
GREY = colors.HexColor("#f2f2f2")
LINE = colors.HexColor("#bfbfbf")


def register_fonts():
    for d in FONT_DIRS:
        r, b = d / "NotoSansKR-Regular.ttf", d / "NotoSansKR-Bold.ttf"
        if r.exists() and b.exists():
            pdfmetrics.registerFont(TTFont("KR", str(r)))
            pdfmetrics.registerFont(TTFont("KRb", str(b)))
            pdfmetrics.registerFontFamily("KR", normal="KR", bold="KRb")
            return
    raise SystemExit("NotoSansKR-{Regular,Bold}.ttf not found in " + ", ".join(map(str, FONT_DIRS)))


def load(policy, dataset, tag):
    p = SIM / "outputs" / f"eval_{policy}_v2_2p1_joint_{dataset}_{tag}.json"
    if not p.exists():
        return None
    eps = json.loads(p.read_text(encoding="utf-8"))["episodes"]
    return dict(n=len(eps),
                iou=st.mean(e["bp_iou"] for e in eps),
                eh=st.mean(e["bp_E_h_mm"] for e in eps),
                ef=st.mean(e["bp_E_f_mm"] for e in eps),
                fallen=sum(1 for e in eps if e["m7_fallen_count"] > 0))


def cells(*rows):
    return [[Paragraph(str(c), S["cell"]) if not isinstance(c, Paragraph) else c for c in r] for r in rows]


def table(data, widths, align_right_from=1):
    t = Table(cells(*data), colWidths=widths, repeatRows=1, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, -1), "KR"),
        ("FONTSIZE", (0, 0), (-1, -1), 7.6),
        ("LEADING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("GRID", (0, 0), (-1, -1), 0.4, LINE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, GREY]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (align_right_from, 1), (-1, -1), "CENTER"),
    ]))
    return t


S = {}


def styles():
    S["title"] = ParagraphStyle("t", fontName="KRb", fontSize=16, leading=20, textColor=ACCENT, spaceAfter=1)
    S["sub"] = ParagraphStyle("s", fontName="KR", fontSize=8.5, leading=12, textColor=colors.HexColor("#595959"))
    S["h"] = ParagraphStyle("h", fontName="KRb", fontSize=10.5, leading=14, textColor=ACCENT,
                            spaceBefore=7, spaceAfter=3)
    S["p"] = ParagraphStyle("p", fontName="KR", fontSize=8.4, leading=12, spaceAfter=3)
    S["cell"] = ParagraphStyle("c", fontName="KR", fontSize=7.6, leading=9.6)
    S["cellb"] = ParagraphStyle("cb", fontName="KRb", fontSize=7.6, leading=9.6, textColor=colors.white)
    S["note"] = ParagraphStyle("n", fontName="KR", fontSize=7.3, leading=10,
                               textColor=colors.HexColor("#595959"), spaceBefore=2)


def hdr(*names):
    return [Paragraph(n, S["cellb"]) for n in names]


def fmt(r, keys=("iou", "eh", "ef")):
    if not r:
        return ["-"] * len(keys)
    out = []
    for k in keys:
        out.append(f"{r[k]:.3f}" if k == "iou" else f"{r[k]:.2f}")
    return out


def build(path):
    register_fonts()
    styles()
    doc = BaseDocTemplate(str(path), pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm,
                          topMargin=14 * mm, bottomMargin=14 * mm, title="조적 모방학습 실험 보고서",
                          author="14조")
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="f")

    def page(canvas, d):
        canvas.saveState()
        canvas.setFont("KR", 7)
        canvas.setFillColor(colors.HexColor("#808080"))
        canvas.drawRightString(A4[0] - 16 * mm, 9 * mm, f"{canvas.getPageNumber()} / 3")
        canvas.drawString(16 * mm, 9 * mm, "모방학습 기반 조적 로봇 — 시뮬레이션 실험 결과 (2026-09-18/19)")
        canvas.restoreState()

    doc.addPageTemplates([PageTemplate(id="all", frames=[frame], onPage=page)])
    F = []

    # ---------------------------------------------------------------- page 1
    F.append(Paragraph("조적 모방학습 시뮬레이션 실험 보고서", S["title"]))
    F.append(Paragraph("2026-09-18 ~ 09-19 · MuJoCo 3.13 + LeRobot 0.6 · RTX 5090 · 14조", S["sub"]))
    F.append(Spacer(1, 5))

    F.append(Paragraph("1. 실험 설계", S["h"]))
    F.append(table([
        hdr("항목", "내용"),
        ["과제", "벽돌 3개 2+1 적층 (90 × 42.632 × 27 mm, 1,800 kg/m³), SO-ARM100 5자유도"],
        ["환경", "접촉층 A + 정착 후 결합 B (mortarB). 아래층 2장이 제자리에 정착하면 그 위에 연속 모르타르층 생성"],
        ["관측", "고정·손목 카메라 128 × 128 + 관절 6 (일부 세트는 상방 카메라 추가)"],
        ["행동", "관절 위치 목표 6, 제어 20 Hz, 물리 1 ms"],
        ["시연 생성", "감쇠 최소자승 IK 스크립트 전문가. 공급 위치 ±5 mm, 방향 ±10° 랜덤화"],
        ["평가", "학습에 쓰지 않은 초기 상태 100회 (시드 10000~10099). 교란 없는 조건과 교란 1회 조건 각각"],
        ["교란", "무작위 시점에 벽돌 하나를 0.3~0.5 m/s로 밀어 0.6~2.5 cm 이동"],
    ], [26 * mm, 152 * mm]))

    F.append(Paragraph("2. 평가 지표 — 설계수행계획서 4.9절의 3종", S["h"]))
    F.append(table([
        hdr("지표", "정의", "좋은 방향"),
        ["3D IoU", "실제 벽돌 3개 합집합과 목표 합집합의 교집합 부피 ÷ 합집합 부피 (0.5 mm 복셀)", "1에 가까울수록"],
        ["E_h (mm)", "대응된 벽돌 3개의 중심 높이 차이 절댓값 평균", "0에 가까울수록"],
        ["E_f (mm)", "앞면 코너 12개의 설계 기준면 법선 거리 중 최대 절댓값", "0에 가까울수록"],
    ], [20 * mm, 136 * mm, 22 * mm]))
    F.append(Paragraph("세 값은 모든 에피소드(미완료 포함)의 평균이다. 표의 <b>낙하</b>는 무너진 벽돌이 있는 "
                       "에피소드 수로, 지표가 아니라 실패 원인을 가르기 위한 보조 정보다. 세 지표만으로는 "
                       "‘무너졌다’와 ‘서 있지만 어긋났다’가 구분되지 않기 때문이다.", S["note"]))

    F.append(Paragraph("3. 데이터셋 — 무엇을 기준으로 나눴는가", S["h"]))
    F.append(Paragraph("두 축으로 나눴다. ① <b>복구 시연의 양과 넣는 방식</b> — 로봇이 벽돌을 건드려 밀린 상황에서 "
                       "전문가가 다시 집어 다시 놓는 시연을 얼마나, 어떻게 포함하는가. ② <b>관측 시점</b> — 벽 영역을 "
                       "내려다보는 상방 카메라를 주는가. 모든 세트는 같은 시드의 clean 부분을 공유한다.", S["p"]))
    F.append(table([
        hdr("세트", "구성", "보존", "복구 시연", "카메라", "역할"),
        ["clean", "교란 없음", "119/120", "0", "2대", "기준선"],
        ["mix", "clean 일부를 교란으로 대체 (62%)", "113/120", "33", "2대", "초기 시도 (설계 결함)"],
        ["mix2", "대체하되 17%로 축소, 정지 프레임 제거", "112/120", "8", "2대", "대체 방식"],
        ["robust", "거의 모든 에피소드 교란", "113/120", "76", "2대", "과다 투입 대조군"],
        ["plus", "clean 119 유지 + 교란 44 추가", "163/180", "26", "2대", "추가 방식"],
        ["plus2", "clean 119 유지 + 교란 83 추가", "202/240", "41", "2대", "복구 증량"],
        ["plustop", "plus와 동일 + 상방 카메라", "163/180", "26", "3대", "관측 시점"],
        ["plus2top", "plus2와 동일 + 상방 카메라", "202/240", "41", "3대", "둘 다"],
        ["state", "clean과 동일, 카메라 대신 벽돌 참값 좌표", "119/120", "0", "-", "특권 정보 기준선"],
    ], [18 * mm, 58 * mm, 17 * mm, 17 * mm, 14 * mm, 54 * mm]))
    F.append(Paragraph("총 9종. ‘보존’은 성공 시연만 남긴 수이며, 복구 불가(넘어짐)는 사유와 함께 로그로 보존한다. "
                       "별도로 장면 사양 v1 시절의 검증용 6종이 있으나 결과에는 쓰지 않았다.", S["note"]))

    F.append(PageBreak())

    # ---------------------------------------------------------------- page 2
    F.append(Paragraph("4. 학습 구성 — 정책 × 데이터셋", S["h"]))
    F.append(table([
        hdr("정책", "스텝", "clean", "mix", "mix2", "robust", "plus", "plus2", "plustop", "plus2top", "state"),
        ["ACT", "40,000", "●", "●", "●", "●", "●", "-", "●", "●", "●"],
        ["Diffusion Policy", "60,000", "●", "●", "●", "●", "●", "●", "●", "●", "-"],
        ["SmolVLA", "20,000 / 40,000", "●", "-", "-", "-", "-", "-", "-", "-", "-"],
        ["π0", "-", "미실행", "-", "-", "-", "-", "-", "-", "-", "-"],
    ], [28 * mm, 22 * mm, 13 * mm, 12 * mm, 13 * mm, 15 * mm, 13 * mm, 14 * mm, 16 * mm, 17 * mm, 14 * mm]))
    F.append(Paragraph("학습 16회, 평가 39건(각 100회 롤아웃). SmolVLA는 권장 방식(비전·언어 동결, 2만 스텝)과 "
                       "언어모델까지 미세조정(4만 스텝) 두 조건. π0는 토크나이저 <font name='KR'>google/paligemma-3b-pt-224</font>가 "
                       "접근 제한 저장소라 미실행.", S["note"]))

    F.append(Paragraph("5. 결과 ① 정책 비교 (clean 데이터 119개로 동일 학습)", S["h"]))
    rows = [hdr("정책", "조건", "3D IoU", "E_h (mm)", "E_f (mm)", "낙하")]
    for pol, label in [("diffusion", "Diffusion Policy"), ("act", "ACT"),
                       ("smolvla", "SmolVLA (권장 방식)"), ("smolvla_full", "SmolVLA (VLM 미세조정)")]:
        for tag, cond in [("mortarB", "교란 없음"), ("mortarB_kick", "교란 1회")]:
            r = load(pol, "image_clean", tag)
            if r:
                rows.append([label, cond] + fmt(r) + [str(r["fallen"])])
    F.append(table(rows, [42 * mm, 24 * mm, 26 * mm, 26 * mm, 26 * mm, 20 * mm]))
    F.append(Paragraph("참고 (IK 스크립트 전문가, 상한): IoU 0.88 · E_h 0.11 mm · E_f 2.2 mm", S["note"]))
    F.append(Paragraph("<b>Diffusion Policy가 가장 낫고 SmolVLA는 과제를 수행하지 못했다.</b> 다만 벽돌이 하나도 "
                       "무너지지 않은 에피소드만 보면 세 정책의 IoU가 0.87~0.91, E_h가 0.11~0.12 mm로 사실상 같다. "
                       "순위를 가르는 것은 정밀도가 아니라 세 번의 파지·운반·배치를 끝까지 이어가는 비율이다. "
                       "SmolVLA는 손실이 0.003까지 수렴했음에도 벽돌 하나를 공급 위치에 남기는 실패가 반복됐고, "
                       "학습량을 두 배로 늘려도, 재관측 주기를 2.5초에서 0.5초로 줄여도 같았다.", S["p"]))

    F.append(Paragraph("6. 결과 ② 보조 실험", S["h"]))
    rows = [hdr("비교", "조건", "3D IoU", "E_h (mm)", "E_f (mm)", "낙하")]
    r1, r2 = load("act", "image_clean", "mortarB"), load("act", "state_clean", "mortarB")
    rows.append(["ACT · 영상 입력", "교란 없음"] + fmt(r1) + [str(r1["fallen"])])
    rows.append(["ACT · 좌표 입력(특권)", "교란 없음"] + fmt(r2) + [str(r2["fallen"])])
    r3 = load("act", "image_clean", "mortarA")
    rows.append(["ACT · 결합 B 끔 (mortarA)", "교란 없음"] + fmt(r3) + [str(r3["fallen"])])
    F.append(table(rows, [52 * mm, 22 * mm, 24 * mm, 24 * mm, 24 * mm, 18 * mm]))
    F.append(Paragraph("<b>특권 정보가 이점이 아니었다.</b> 벽돌의 정확한 좌표를 받은 정책이 카메라만 보는 정책보다 "
                       "나빴다(IoU 0.600 대 0.788). 시연 119개 규모에서는 26차원 좌표에서 궤적을 만드는 것보다 "
                       "합성곱 신경망이 영상에서 공간 구조를 읽는 편이 유리하다. 결합 제약을 끄면 E_f가 8.7에서 "
                       "25.4 mm로 나빠져, 4.8.4절이 경계한 ‘제약이 결과를 좋게 만드는’ 효과가 실재함을 확인했다.", S["p"]))

    F.append(PageBreak())

    # ---------------------------------------------------------------- page 3
    F.append(Paragraph("7. 결과 ③ 복구 시연의 양 × 관측 시점", S["h"]))
    rows = [hdr("정책", "세트", "복구", "카메라", "조건", "3D IoU", "E_h (mm)", "E_f (mm)", "낙하")]
    spec = [("diffusion", "Diffusion", [("clean", "0", "2대"), ("plus", "26", "2대"), ("plus2", "41", "2대"),
                                        ("plustop", "26", "3대"), ("plus2top", "41", "3대")]),
            ("act", "ACT", [("clean", "0", "2대"), ("plus", "26", "2대"),
                            ("plustop", "26", "3대"), ("plus2top", "41", "3대")])]
    for pol, label, sets in spec:
        for i, (n, rec, cam) in enumerate(sets):
            for tag, cond in [("mortarB", "교란 없음"), ("mortarB_kick", "교란 1회")]:
                r = load(pol, f"image_{n}", tag)
                if r:
                    rows.append([label if (i == 0 and tag == "mortarB") else "", n, rec, cam, cond]
                                + fmt(r) + [str(r["fallen"])])
    F.append(table(rows, [22 * mm, 20 * mm, 13 * mm, 15 * mm, 20 * mm, 22 * mm, 22 * mm, 22 * mm, 16 * mm]))

    F.append(Paragraph("8. 결론", S["h"]))
    for i, (head, body) in enumerate([
        ("시연은 정책이 볼 수 있는 규칙으로 만들어야 한다.",
         "전문가가 벽돌을 내부 번호순으로 집게 했더니 카메라로는 알 수 없는 순서라 같은 장면에서 첫 집기가 "
         "매번 달라졌고, ACT가 10회 중 8회 실패했다. ‘벽에 가까운 벽돌부터’라는 관측 가능한 규칙으로 바꾸자 정상화됐다."),
        ("목적 없는 정지 구간을 시연에 넣으면 정책이 그것을 배운다.",
         "교란 후 팔이 12스텝 멈추고 그 프레임이 ‘정지’ 행동으로 기록되자 ACT의 IoU가 0.788에서 0.579로 떨어졌다. "
         "정지 프레임을 없애자 0.769로 회복했다."),
        ("복구 시연에는 관측 시점이 전제조건이다.",
         "벽돌이 10~20 mm 밀려도 고정·손목 카메라에서는 화면의 0.25~1.2 %만 바뀐다. 같은 복구 데이터로 상방 카메라만 "
         "추가하자 ACT의 낙하가 46회에서 11회로, IoU가 0.660에서 0.819로 바뀌었다. 복구 데이터가 해로웠던 것이 아니라, "
         "관측에 나타나지 않는 조건을 근거로 행동을 바꾸라고 요구한 것이 문제였다."),
        ("강건성과 정밀도는 맞바꿈 관계이며, 두 개선은 더해지지 않는다.",
         "복구 시연을 26 → 41개로 늘리면 Diffusion의 낙하가 7 → 3회로 줄고, 상방 카메라를 더하면 IoU가 clean 수준으로 "
         "회복한다. 그러나 둘을 합친 plus2top은 교란 시 낙하가 11회로 최저인 대신 벽 길이 방향으로 배치가 밀려 "
         "IoU가 0.724로 떨어졌다(E_h·E_f는 양호). 세 지표를 함께 읽어야 드러나는 현상이다."),
    ], 1):
        F.append(Paragraph(f"<b>{i}. {head}</b> {body}", S["p"]))

    F.append(Paragraph("권장 조합과 다음 단계", S["h"]))
    F.append(table([
        hdr("목적", "조합", "근거"),
        ["종합 품질", "Diffusion + plustop", "IoU 0.848 · E_h 0.57 · E_f 3.89 mm · 낙하 5회 — 세 지표 모두 clean 이상"],
        ["안정성 우선", "Diffusion + plus2", "낙하 3회로 전체 최저"],
        ["교란 내성 우선", "Diffusion + plus2top", "교란 시 낙하 11회로 최저 (정밀도 손실 감수)"],
        ["ACT를 쓸 경우", "plustop 필수", "상방 카메라 없이 복구 데이터를 넣으면 낙하가 23 → 46회로 악화"],
    ], [24 * mm, 40 * mm, 114 * mm]))
    F.append(Paragraph("남은 과제: ① π0 (Hugging Face 로그인과 PaliGemma 라이선스 동의 필요) ② 시연 수 확장 "
                       "(200·500·1,000, 계획서 4.7.2) ③ Phase 2 제어 보완 — 위 맞바꿈이 데이터 구성만으로는 넘기 어렵다는 "
                       "것이 그 근거이며, 배치 직전 구간의 시각 서보가 후보다.", S["note"]))

    doc.build(F)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--out", default=str(SIM.parent / "실험보고서.pdf"))
    a = ap.parse_args()
    build(a.out)
    print("wrote", a.out)
