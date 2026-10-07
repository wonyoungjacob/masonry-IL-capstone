"""3-page plain-language status summary: Experiment 1, Experiment 2, and the new gate-based design (2026-09-23)."""
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak

HERE = Path(__file__).resolve().parent
pdfmetrics.registerFont(TTFont("KR", str(HERE / "fonts" / "NotoSansKR-Regular.ttf")))
pdfmetrics.registerFont(TTFont("KRB", str(HERE / "fonts" / "NotoSansKR-Bold.ttf")))
H1 = ParagraphStyle("h1", fontName="KRB", fontSize=15, leading=20, spaceAfter=6, textColor=colors.HexColor("#173B57"))
H2 = ParagraphStyle("h2", fontName="KRB", fontSize=11.5, leading=15, spaceBefore=8, spaceAfter=3, textColor=colors.HexColor("#1D6D9E"))
P = ParagraphStyle("p", fontName="KR", fontSize=9.6, leading=14.5, spaceAfter=4)
B = ParagraphStyle("b", parent=P, leftIndent=10, bulletIndent=0, spaceAfter=2)
SM = ParagraphStyle("sm", fontName="KR", fontSize=8.2, leading=11, textColor=colors.HexColor("#555555"))
TS = TableStyle([("FONTNAME", (0, 0), (-1, -1), "KR"), ("FONTSIZE", (0, 0), (-1, -1), 8.8), ("FONTNAME", (0, 0), (-1, 0), "KRB"),
                 ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8EEF3")), ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#9AA8B4")),
                 ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)])

def bl(items):
    return [Paragraph(f"• {t}", B) for t in items]

def tbl(rows, widths):
    t = Table([[Paragraph(c, P) for c in r] for r in rows], colWidths=widths); t.setStyle(TS); return t

s = []
s.append(Paragraph("조적 로봇 모방학습: 지금까지의 상황과 새 설계 (3쪽 요약)", H1))
s.append(Paragraph("14조 · 2026-09-23 · 시뮬레이션(MuJoCo, SO-ARM100) 기준. 실제 로봇 이식은 이 연구 범위 밖이다.", SM))
s.append(Spacer(1, 6))

s.append(Paragraph("1. 우리가 하려는 일", H2))
s.append(Paragraph("로봇팔이 바닥에 흩어진 블록 3개를 집어 아래 2개, 위 1개로 쌓는다. 사람이 짠 프로그램(전문가)이 시범을 보이면 "
                   "그 영상과 관절값을 보고 로봇이 따라 하도록 학습시킨다(모방학습). 블록의 처음 위치와 방향은 매번 무작위다. "
                   "실제 조적에서는 모르타르 위에 놓은 블록을 다시 들면 안 되므로, 한 번 놓은 블록은 다시 잡지 않는다는 규칙을 둔다.", P))

s.append(Paragraph("2. 실험 1 (탐색 단계)에서 알게 된 것", H2))
s.extend(bl([
    "조건: 블록 위치 ±5 mm, 방향 ±10°의 좁은 무작위. 여러 종류의 데이터(정상만 / 교란·복구 포함 등)를 만들어 비교했다.",
    "결과: 정상 시범만으로 학습한 경우 Diffusion 정책 90/100, ACT 63/100 완성. SmolVLA는 거의 0.",
    "교란·복구 시범을 섞으면 블록이 떨어지는 일은 줄지만, 정확히 완성되는 비율은 오히려 낮아졌다(예: Diffusion 2/100).",
    "교훈: 좁은 범위에서는 잘 되지만, ‘복구’ 데이터를 늘리는 것이 곧 정확한 시공으로 이어지지는 않는다.",
]))

s.append(Paragraph("3. 실험 2 (넓은 무작위)에서 생긴 문제", H2))
s.extend(bl([
    "조건: 위치 ±30 mm, 방향 ±60°로 크게 넓힘. 첫 시도에 성공한 시범만 240개 채택(454회 시도), 세 정책을 각 3회 학습.",
    "결과: ACT 0/300, Diffusion 41/200, SmolVLA 0/200 완성. 실험 1보다 크게 나빠졌다.",
    "시범을 모을 때 전문가조차 454회 중 139회 파지 검사에 실패했다. 특히 첫 블록에서 70회.",
]))
s.append(tbl([["구분", "실험 1", "실험 2"],
              ["초기 무작위", "±5 mm, ±10°", "±30 mm, ±60°"],
              ["시범 수 / 길이", "119개, 각 18.3초", "240개, 각 18.3초"],
              ["카메라", "앞 + 손목 (일부 위)", "앞 + 손목 + 위"],
              ["정책 실행 단위", "ACT 5초, Diffusion 1.6초", "모두 0.5초"],
              ["완성률 (최고)", "Diffusion 90/100", "Diffusion 41/200 (ACT 0/300)"]], [45 * mm, 60 * mm, 65 * mm]))

s.append(Paragraph("4. 오늘 원인을 파헤쳐 확인한 것", H2))
s.append(Paragraph("실패 영상(seed 1001)을 그대로 다시 돌려 시점마다 목표 위치, 실제 위치, 접촉을 계측했다. "
                   "이어서 454회 시도를 모두 같은 기준으로 분류했다. 첫 블록 파지 실패 70건의 원인은 세 가지였다.", P))
s.append(tbl([["원인", "설명", "건수"],
              ["A. 로봇이 자기 몸에 부딪힘", "블록이 로봇 밑동에 너무 가까우면 집게가 몸통에 걸려 끝까지 못 내려간다. 팔이 못 닿는 게 아니라 부딪히는 것이다.", "35"],
              ["B. 옆 블록에 부딪힘", "집게는 7 cm까지 벌어지는데 배치 검사는 블록 사이 1 cm만 확인했다. 닫히는 집게가 옆 블록을 쳐서 손이 밀려난다.", "30"],
              ["C. 집게 끝이 블록 위에 얹힘", "집게와 블록 사이 여유가 0 mm라 1~3 mm만 어긋나도 옆면 대신 윗면을 누른다.", "5"]],
             [42 * mm, 108 * mm, 20 * mm]))
s.append(Paragraph("즉 ‘못 집는 배치’가 처음부터 섞여 있었고, 학습 문제 이전에 시범 생성과 배치 검사의 문제였다. "
                   "한편 학습된 정책은 빈손이어도 그대로 운반 동작을 이어 갔다. 시범에는 빈손 상황이 하나도 없었으니 당연한 결과다.", P))

s.append(PageBreak())
s.append(Paragraph("5. 새 가설과 바뀐 설계", H2))
s.append(Paragraph("가설: <b>정책이 ‘집었는지’, ‘제대로 놓을 위치인지’를 스스로 알기를 기대하지 말고, 그 판단은 정책 바깥의 확인 장치(게이트)가 맡는다.</b> "
                   "정책은 동작 생성만 하고, 게이트가 단계 전환을 결정한다. 한 번 놓은 블록은 다시 잡지 않는다는 규칙은 그대로 둔다.", P))
s.append(tbl([["번호", "바꾼 것", "무엇을 해결하나"],
              ["①", "배치 필터: 시작 배치를 뽑을 때 A·B를 미리 계산해 걸러낸다.", "못 집는 배치 제거. 454회 중 실패 65/70을 걸러내고 성공 배치는 25/384만 잃음."],
              ["②", "집게 여유 1.5 mm 추가.", "C 해결. 필터 통과 배치에서 전문가 첫 파지 380/382."],
              ["③", "파지 게이트: 집게가 닫힌 뒤 멈춘 각도를 읽는다. 블록이 있으면 0.31, 빈손이면 -0.12에서 멈춘다.",
               "빈손 운반 차단. 빈손이면 집게를 열고 4 cm 올린 뒤, 다음 블록 위로 손을 옮겨 정책이 다시 시도하게 한다(재지도)."],
              ["④", "놓침 감지: 운반 중 집게가 더 닫히면 놓친 것으로 본다.", "‘잡힌 척’ 오판 2건을 잡아냈다."],
              ["⑤", "해제 게이트: 정책이 집게를 열려는 순간 잡고 있는 블록의 위치·방향·높이 오차를 잰다. 4.5 mm/5°를 넘으면 고친 뒤 연다.",
               "잘못 놓기 방지. 옆 블록은 설계값이 아니라 실제 놓인 이웃에 맞춰 붙인다. 놓은 뒤에는 절대 고치지 않는다."]],
             [12 * mm, 78 * mm, 80 * mm]))

s.append(Paragraph("6. 기존 정책으로 바로 확인한 결과 (검증용 배치 5개, 통계가 아니라 동작 확인)", H2))
s.append(tbl([["조건", "Diffusion 완성", "ACT 완성"],
              ["정책 단독 (기존 방식)", "1/5", "0/5"],
              ["정책 + 파지 게이트", "2/5", "0/5"],
              ["정책 + 파지 게이트 + 해제 게이트", "4/5", "2/5 (나머지 3회는 블록 1개씩 성공)"]], [70 * mm, 45 * mm, 55 * mm]))
s.extend(bl([
    "재학습 없이 같은 모델에 게이트만 붙였다. ACT는 놓기 직전에 5~18 mm 어긋나 있었고 해제 게이트가 14회 중 13회 고쳤다. ACT의 진짜 문제는 파지가 아니라 놓는 정밀도였다.",
    "게이트를 붙인 결과는 항상 ‘정책+게이트’로 따로 표기한다. 정책 자체가 좋아진 것은 아니다.",
    "남은 실패: 위에 올리는 셋째 블록을 다시 안내해도 정책이 빈손으로 닫는 경우, 놓은 뒤 정책이 멈추는 경우.",
]))

s.append(Paragraph("7. 바로 이어서 할 일 (힘 센서, 시뮬레이션 안에서만)", H2))
s.extend(bl([
    "손목에 힘·토크 센서를 시뮬레이션에 추가한다. 블록 무게는 약 1.8 N이라 ‘집게가 이물에 걸려 멈춤’과 ‘블록을 물고 있음’을 구분할 수 있다.",
    "내려놓을 때 목표 높이 전에 힘이 튀면 이웃에 걸치거나 접촉면이 잘못된 것이므로 열기 전에 알 수 있다.",
    "먼저 게이트 판단에만 쓴다(재학습 없음). 검증 배치 40개에서 ‘정책 단독 / 게이트 / 게이트+힘’을 나눠 비교한다.",
    "그 뒤에도 정책 자체가 힘을 알아야만 풀리는 실패가 남을 때만 힘 신호를 정책 입력에 넣고 재학습한다.",
    "촉각(GelSight류) 센서는 현재 하드웨어·시뮬레이션 모두에 없으므로 다루지 않는다.",
]))
s.append(Paragraph("8. 해석할 때 주의할 점", H2))
s.extend(bl([
    "배치 필터를 켜면 시험 문제의 분포가 바뀐다. 이전 실험 1·2 수치와 직접 비교하지 않는다.",
    "게이트는 시뮬레이션의 정확한 블록 좌표를 쓴다. 이 연구 범위에서는 그것으로 충분하며, 실제 로봇 이식은 고려하지 않는다.",
    "5회 확인은 동작 검증이다. 성능 주장은 40개 검증 배치와 100개 시험 배치에서 다시 잰 뒤에 한다.",
]))
s.append(Spacer(1, 4))
s.append(Paragraph("근거 파일: 실험일지.md(2026-09-23 항목), sim/outputs/diag_first_grasp/, sim/brick_sim/feasibility.py, grasp_gate.py, "
                   "발표자료_실험1_실험2_20260922/실험1_실험2_통합보고서.pdf", SM))

out = Path("/home/won/masonry/01_사기설/진행보고/현황요약_실험1_실험2_새설계_20260923.pdf")
SimpleDocTemplate(str(out), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
                  title="조적 로봇 모방학습 현황 요약").build(s)
print(out)
