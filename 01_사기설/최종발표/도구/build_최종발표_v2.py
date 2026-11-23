# -*- coding: utf-8 -*-
"""사회기반시스템종합설계 14조 · 최종발표 (2026-12-08) 자료 v2. 표지 포함 10장. v1에서 평가지표를 2쪽(무엇을 재는가 / 어떻게 비교하는가)으로 늘리고 설계 과정을 1쪽으로 합침.
흐름(사기설_마무리_요약과_보고서흐름_20261117.md 5절): 배경 · 문제 → 목적 · 설계 질문 · 제한조건 → 환경 · 평가 → 설계 과정 ① ② → 끝 구성 → 결과 → 단계별 기여도 · 알게 된 것 → 결론 · 한계.
- 숫자: 사기설_마무리_요약과_보고서흐름_20261117.md 2 · 3 · 4 · 7절, 근거_우분투_wall3_벽돌기준_공급이동예비_20261117/벽돌기준_집계.txt,
        근거_우분투_wall3_역방향제거_20261111/표_역방향제거_사다리.md. 모두 개발 배치 100벽(700300 ~ 700399).
- 넣지 않는 것: 제어 only 대 하이브리드 비교(사용자 결정 11-17, 개인 연구로 넘김).
- 형식: 중간발표 1 · 2와 같음(10장, 16:9, Pretendard, Meta 디자인 + 컨설팅 원칙). 도구 함수는 진행보고/도구/build_진행회의_20261103.py 앞부분을 읽어 씀.
usage: python build_최종발표.py <out.pptx>
"""
import sys, os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_PPTX = os.path.abspath(sys.argv[1])
ASSET = os.path.join(HERE, "자산")
S1 = os.path.normpath(os.path.join(HERE, "..", ".."))                      # 01_사기설
src = open(os.path.join(S1, "진행보고", "도구", "build_진행회의_20261103.py"), encoding="utf-8").read()
src = src.split("# ═══════════════════════════ 이번 자료 공통 도구")[0]
sys.argv = [sys.argv[0], OUT_PPTX, OUT_PPTX + ".tmp.txt"]
exec(compile(src, "helpers_20261103", "exec"))

sys.stdout.reconfigure(encoding="utf-8")
N_SLIDES = 10
SECTIONS = ["배경", "목적", "방법", "설계", "결과", "결론"]
ACTIVE = {2: "배경", 3: "목적", 4: "방법", 5: "설계", 6: "설계", 7: "설계", 8: "결과", 9: "결과", 10: "결론"}
CW = W - 2 * M
NOTE = "같은 100벽(1,600장) 기준 · 설정을 고른 배치와 같은 배치"
VIDEO = os.path.join(S1, "근거_우분투_wall3_현실제약_20261116", "확인영상", "하이브리드_제약없음_700300_완성.mp4")


def A(name):
    return os.path.join(ASSET, name)


def col_chart(slide, x, y, w, h, cats, series, vmax, major, fmt="0", size=14, gap=70):
    cd = CategoryChartData(); cd.categories = cats
    for n_, v, _ in series:
        cd.add_series(n_, v)
    ch = slide.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(x), Inches(y), Inches(w), Inches(h), cd).chart
    ch.font.size = Pt(size); ch.font.name = FONT; ch.font.color.rgb = RGB["ink"]
    ch.has_title = False
    ch.has_legend = len(series) > 1
    if ch.has_legend:
        ch.legend.position = XL_LEGEND_POSITION.TOP; ch.legend.include_in_layout = False
        ch.legend.font.size = Pt(size); ch.legend.font.bold = True
    va = ch.value_axis; va.minimum_scale = 0; va.maximum_scale = vmax; va.major_unit = major
    va.has_major_gridlines = True; va.major_gridlines.format.line.color.rgb = RGB["hairsoft"]; va.format.line.fill.background()
    va.tick_labels.font.size = Pt(13); va.tick_labels.font.color.rgb = RGB["charcoal"]
    ca = ch.category_axis; ca.tick_labels.font.size = Pt(size); ca.tick_labels.font.bold = True; ca.format.line.color.rgb = RGB["hair"]
    pl = ch.plots[0]; pl.gap_width = gap; pl.overlap = -8; pl.has_data_labels = True
    dl = pl.data_labels; dl.number_format = fmt; dl.number_format_is_linked = False; dl.position = XL_LABEL_POSITION.OUTSIDE_END
    dl.font.size = Pt(size + 2); dl.font.bold = True; dl.font.color.rgb = RGB["inkdeep"]
    for ser, (_, _, col) in zip(pl.series, series):
        ser.format.fill.solid(); ser.format.fill.fore_color.rgb = RGB[col]; ser.format.line.fill.background()
    return ch


def head(slide, x, y, w, label, fill="inkdeep", color="white", size=15):
    pill(slide, x, y, w, 0.36, label, fill, color, size)


def footnote(slide, s_=NOTE):
    text(slide, M, H - 0.44, 10.5, 0.34, s_, 14, "charcoal", anchor=MSO_ANCHOR.MIDDLE)


def bignum(slide, x, y, w, h, num, label, fill="soft", ncol="primary", nsize=30):
    card(slide, x, y, w, h, fill, None)
    mtext(slide, x + 0.1, y + 0.05, w - 0.2, h - 0.1, [(f"**{num}**", nsize, ncol, True), (label, 15, "inkdeep", False)],
          align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, spacing=1.0, after=2)


def kv_card(slide, x, y, w, h, title, rows, hfill="inkdeep", size=16, fill="canvas", line="hair"):
    card(slide, x, y, w, h, fill, line)
    head(slide, x + 0.2, y + 0.18, min(w - 0.4, pw(title, 15) + 0.1), title, hfill)
    text(slide, x + 0.2, y + 0.7, w - 0.4, h - 0.8, [f"**{k}**: {v}" for k, v in rows], size, "inkdeep", spacing=1.15, after=7)


def wall_rects():
    """16자리(쌓는 순서)의 (x0, z0, 길이, 높이) mm. sim/wall3/poster_ksarc_20261111d.py와 같은 배치."""
    out = []
    for c in range(3):
        z0 = c * 67.0
        xs = ([(-450.0, 90.0)] + [((-1.5 + i) * 200.0, 190.0) for i in range(4)] + [(450.0, 90.0)]) if c == 1 else [((-2 + i) * 200.0, 190.0) for i in range(5)]
        for xc, L in xs:
            out.append((xc - L / 2, z0, L, 57.0))
    return out


def draw_wall(slide, x, y, w, filled):
    sc = w / 990.0
    hh = 191.0 * sc
    for k, (x0, z0, L, Hh) in enumerate(wall_rects()):
        rect(slide, x + (x0 + 495.0) * sc, y + hh - (z0 + Hh) * sc, L * sc, Hh * sc, "primary" if k in filled else "canvas", "charcoal", line_w=1.0)
    return hh


# ═══════════════ 1. 표지
s = new()
pill(s, 0.9, 1.0, 1.35, 0.4, "최종발표", "inkdeep", "white", 15)
text(s, 0.9, 1.55, 6.6, 2.4, ["모방학습 정책과 검측 제어를", "결합한 조적 로봇", "쌓기 제어 체계 설계"], 36, "inkdeep", True, spacing=1.1, after=0)
text(s, 0.9, 3.75, 6.6, 0.45, "표준 벽돌 3단 16장 벽 · 시방 허용오차 기준", 18, "ink")
ln = s.shapes.add_connector(1, Inches(0.9), Inches(4.4), Inches(6.9), Inches(4.4)); ln.line.color.rgb = RGB["hair"]; ln.line.width = Pt(1)
text(s, 0.9, 4.55, 6.3, 0.42, "**사회기반시스템종합설계 14조**", 20, "inkdeep")
text(s, 0.9, 5.05, 6.3, 0.4, "정원영 · 강건 · 정성용 · 임수현", 18, "ink")
text(s, 0.9, 5.55, 6.3, 0.38, "지도교수: 김홍조 교수님", 17, "ink")
text(s, 0.9, 6.05, 6.3, 0.38, "2026.12.08", 17, "charcoal", True)
rounded_img(A("final_wall.png"), A("final_wall_r.png"), 36)
iw, ih = picture(s, A("final_wall_r.png"), 7.55, 1.3, w=5.25)
text(s, 7.55, 1.3 + ih + 0.1, 5.25, 0.34, "MuJoCo · UR10e · 표준 벽돌 3단 16장", 14, "charcoal", align=PP_ALIGN.CENTER)
pill(s, W - M - 0.62, H - 0.42, 0.62, 0.32, "1", "inkdeep", "white", 13)

# ═══════════════ 2. 배경 · 문제
s = new(); y = chrome(s, 2, "시연으로 배운 정책만으로는 1,600장 중 200장만 쌓음", "배경과 문제")
lw = 5.7
kv_card(s, M, y, lw, 2.3, "배경", [("조적 공사", "반복 · 중량물 작업, 숙련 인력 감소"), ("자동화 흐름", "시연을 학습하는 정책(모방학습) 확산"), ("대상 정책", "ACT · 시연 1,000벽 학습")])
kv_card(s, M, y + 2.5, lw, H - y - 3.05, "문제", [("연쇄 중단", "한 장 실패 → 벽 전체 중단"), ("정밀도", "mm 단위 놓기 부족"), ("실패 인지", "성공 시연만 학습 → 인지 불가")], "critical")
rx = M + lw + 0.3; rw = CW - lw - 0.3
card(s, rx, y, rw, H - y - 0.55, "soft", None)
text(s, rx + 0.25, y + 0.15, rw - 0.5, 0.36, "**정책만 실행한 100벽: 채워진 자리**", 16, "inkdeep")
wh = draw_wall(s, rx + 0.45, y + 0.75, rw - 0.9, {0, 1})
gl = s.shapes.add_connector(1, Inches(rx + 0.35), Inches(y + 0.75 + wh + 0.05), Inches(rx + rw - 0.35), Inches(y + 0.75 + wh + 0.05)); gl.line.color.rgb = RGB["charcoal"]; gl.line.width = Pt(1.5)
text(s, rx + 0.25, y + 0.95 + wh, rw - 0.5, 0.34, "파랑: 100벽 모두 채움 · 흰색: 0벽", 14, "inkdeep")
by = y + 1.5 + wh
bw_ = (rw - 0.75) / 2
bignum(s, rx + 0.25, by, bw_, H - by - 0.8, "200 / 1,600장", "벽돌 성공 12.5 %", "canvas", "critical", 26)
bignum(s, rx + 0.5 + bw_, by, bw_, H - by - 0.8, "0벽", "16장 완성", "canvas", "critical", 26)

# ═══════════════ 3. 목적 · 설계 질문 · 환경
s = new(); y = chrome(s, 3, "목표: 3단 16장 벽을 시방 허용오차 안에서 쌓는 제어 체계", "목적 · 설계 질문 · 실험 환경")
card(s, M, y, CW, 0.85, "inkdeep", None)
text(s, M + 0.25, y, CW - 0.5, 0.85, "**목적**: 시연으로 배운 정책이 벽을 **시방 허용오차 안에서** 쌓도록, 더해야 할 단계를 찾고 **단계별 효과**를 측정", 17, "white", anchor=MSO_ANCHOR.MIDDLE, spacing=1.1)
c3 = (CW - 0.4) / 3
qy = y + 1.0
for i, (k, v) in enumerate([("설계 질문 ①", "무엇이 쌓기를 막는가"), ("설계 질문 ②", "무엇을 더하면 얼마나 오르는가"), ("설계 질문 ③", "더한 단계는 각각 얼마나 필요한가")]):
    x0 = M + i * (c3 + 0.2)
    card(s, x0, qy, c3, 1.1, "primarysoft", None)
    mtext(s, x0 + 0.15, qy, c3 - 0.3, 1.1, [(k, 15, "primary", True), (f"**{v}**", 17, "inkdeep", True)], align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, spacing=1.05, after=3)
ey = qy + 1.25
lw = 6.6
_, eh = picture(s, A("env.png"), M, ey, w=lw)
rx = M + lw + 0.3; rw = CW - lw - 0.3
kv_card(s, rx, ey, rw, 1.72, "실험 환경 (MuJoCo)", [("로봇 · 정책", "UR10e + 집게 · ACT"), ("벽", "표준 벽돌 3단 16장 · 줄눈 10 mm")], size=15)
card(s, rx, ey + 1.87, rw, H - (ey + 1.87) - 0.55, "soft", None)
mtext(s, rx + 0.2, ey + 1.87, rw - 0.4, H - (ey + 1.87) - 0.55, [("**제한조건 2개**", 16, "inkdeep", True), ("① 성능: 시방 허용오차 (4쪽)", 15, "inkdeep", False), ("② 현실성: 정답 좌표 미사용 (5쪽)", 15, "inkdeep", False)],
      anchor=MSO_ANCHOR.MIDDLE, spacing=1.05, after=2)

# ═══════════════ 4. 평가지표 ①: 무엇을 재는가
s = new(); y = chrome(s, 4, "평가지표: 국가 표준시방서 기준으로 3단계 판정", "평가지표 ① · 무엇을 재는가 (제한조건 1 · 성능)")
tiers = [("① 벽돌 성공률", "벽돌이 설계 자리에 있는가", "1,600장 중 · 자리 중심 45 mm 안"),
         ("② 벽 완성률", "16장이 모두 쌓였는가", "100벽 중 · 16자리 모두 채움"),
         ("③ 시방 합격률", "허용오차 5항목을 통과하는가", "완성 벽 중 · 5항목 모두 합격")]
tw = (CW - 2 * 0.1) / 3
for i, (a, b, c) in enumerate(tiers):
    x0 = M + i * (tw + 0.1)
    fill = ["soft", "primarysoft", "inkdeep"][i]; col = "white" if i == 2 else "inkdeep"
    shp = rect(s, x0, y, tw, 1.45, fill, None, shape=MSO_SHAPE.PENTAGON if i == 0 else MSO_SHAPE.CHEVRON)
    shp.adjustments[0] = 0.2
    mtext(s, x0 + (0.2 if i == 0 else 0.5), y, tw - 0.9, 1.45, [(f"**{a}**", 18, "white" if i == 2 else "primary", True), (b, 15, col, True), (c, 14, col, False)],
          align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, spacing=1.05, after=2)
text(s, M, y + 1.55, CW, 0.34, "오른쪽으로 갈수록 엄격한 기준 · 세 지표를 같은 표에 함께 보고", 14, "inkdeep", align=PP_ALIGN.CENTER)
ty = y + 2.0
head(s, M, ty, 5.6, "시방 5항목: KCS 41 34 00 조적공사 시공 허용오차", "primary")
table(s, M, ty + 0.48, CW, [
    ["#", "항목", "현장 검측 방법", "시뮬레이션 측정", "허용오차"],
    ["①", "가로줄눈 두께", "줄눈 게이지", "아래위 벽돌 사이 연직 거리", "10 ± 3 mm"],
    ["②", "선 및 면", "수평기 · 규준대", "단 윗면 높이 차 · 앞면 평탄도", "6 mm"],
    ["③", "수직도", "다림추 · 레이저", "1단 앞면 대비 위 단의 이격", "6 mm"],
    ["④", "평면상 위치", "바닥 먹선", "1단 앞면과 설계선의 거리", "6 mm"],
    ["⑤", "벽 두께", "줄자", "가장 앞면과 뒷면의 거리", "−6 ~ +13 mm"],
], [0.5, 2.2, 2.6, 4.4, 2.0], size=15, row_h=0.42, head_h=0.4, align_c=(0, 4))

# ═══════════════ 5. 평가지표 ②: 어떻게 비교하는가
s = new(); y = chrome(s, 5, "비교 방법: 같은 100벽 짝 비교와 95 % 신뢰구간", "평가지표 ② · 어떻게 비교하는가 (제한조건 2 · 현실성)")
proc = ["같은 100벽 실행\n모든 조건에 같은 시작값", "벽 단위 짝 차이\n같은 벽끼리 빼기", "95 % 신뢰구간\n부트스트랩 10,000번", "사전 판정 기준\n구간 < 0: 유의한 감소"]
pwid = (CW - 3 * 0.1) / 4
for i, lab in enumerate(proc):
    chevron(s, M + i * (pwid + 0.1), y, pwid, 1.25, lab, "inkdeep" if i == 3 else "primarysoft", "white" if i == 3 else "inkdeep", 17, first=(i == 0), sub_color="white" if i == 3 else "inkdeep")
gy = y + 1.45
gw = (CW - 0.3) / 2
gh = (H - gy - 0.55 - 0.2) / 2
grid = [("한 번에 하나만 변경", "단계를 하나씩 더하고, 하나씩 빼서 측정", "inkdeep"),
        ("재실행 변동 확인", "같은 조건 재실행: 완성 60 ~ 62벽 · 이보다 작은 차이는 주장 안 함", "inkdeep"),
        ("오차 주입", "계측 · 센서 오차와 팔레트 이동을 넣어 다시 측정", "inkdeep"),
        ("정답 좌표는 채점에만", "로봇은 도면 · 카메라 · 로봇 센서만 사용 (제한조건 2)", "primary")]
for i, (k, v, col) in enumerate(grid):
    x0 = M + (i % 2) * (gw + 0.3); y0 = gy + (i // 2) * (gh + 0.2)
    card(s, x0, y0, gw, gh, "primarysoft" if col == "primary" else "soft", None)
    mtext(s, x0 + 0.25, y0, gw - 0.5, gh, [(f"**{k}**", 18, col, True), (v, 15, "inkdeep", False)], anchor=MSO_ANCHOR.MIDDLE, spacing=1.08, after=4)

# ═══════════════ 6. 설계 과정
s = new(); y = chrome(s, 6, "원인 찾기 → 고치기 반복: 벽돌 성공 13 % → 100 %", "설계 과정 · 무엇이 막았고 무엇을 바꿨나")
lw = 6.9
text(s, M, y, lw, 0.36, "**벽돌 성공률 (%) · 1,600장 중**", 16, "inkdeep")
col_chart(s, M - 0.05, y + 0.35, lw + 0.1, 3.2, ["①", "② 시연", "③ H", "④ G0", "⑤ G2w", "⑥ G2t", "⑦ G0v"],
          [("벽돌 성공률", (13.0, 33.6, 53.4, 83.1, 85.3, 91.4, 100.0), "primary")], 115, 25, fmt="0.0", size=13, gap=45)
table(s, M, y + 3.62, lw, [["100벽 중", "①", "②", "③", "④", "⑤", "⑥", "⑦"],
                           ["완성 벽", "0", "0", "12", "59", "60", "83", "**100**"],
                           ["시방 합격", "0", "0", "11", "59", "60", "79", "**96**"]],
      [1.5] + [0.77] * 7, size=15, row_h=0.42, head_h=0.38, align_c=range(1, 8))
rx = M + lw + 0.3; rw = CW - lw - 0.3
th = table(s, rx, y, rw, [
    ["단계", "막은 원인", "바꾼 것"],
    ["②", "시연의 손목 방향이 둘로 나뉨", "**시연 통일** · 재학습"],
    ["③", "정책이 차례를 앞질러 기준 자리 어긋남", "**H**: 든 벽돌 기준"],
    ["④ ⑦", "벽돌 중심에서 3 ~ 4 cm 벗어나 집음", "**G0 · G0v**: 검측이 집기"],
    ["⑤ ⑥", "설계 자리에서 먼 곳에서 놓기 시작", "**G2w · G2t**: 검측이 운반"],
], [0.75, 2.3, 2.1], size=15, row_h=0.74, head_h=0.4, align_c=(0,))
card(s, rx, y + th + 0.18, rw, H - (y + th + 0.18) - 0.6, "inkdeep", None)
text(s, rx + 0.2, y + th + 0.18, rw - 0.4, H - (y + th + 0.18) - 0.6, "**원인 1개 → 제어 1개 → 같은 100벽 확인**", 16, "white", align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
footnote(s, "①: 처음 학습한 정책 + G1 · G2 · G3 · ③ ~ ⑦: 정책 고정, 검측만 변경")

# ═══════════════ 7. 끝 구성
s = new(); y = chrome(s, 7, "끝 구성: 정책은 고르기 · 접근, mm 구간은 검측이 수행", "설계 결과 · 끝 구성의 분업")
flow = [("접근", "정책"), ("집기", "G0v"), ("쥠 확인", "G1"), ("벽돌 판별", "H"), ("운반", "G2t"), ("놓기 보정", "G2"), ("재배치", "G3")]
fw = (CW - 6 * 0.06) / 7
for i, (a, b) in enumerate(flow):
    chevron(s, M + i * (fw + 0.06), y, fw, 0.95, f"{a}\n{b}", "inkdeep" if i == 0 else "primarysoft", "white" if i == 0 else "inkdeep", 16, first=(i == 0), sub_color="white" if i == 0 else "primary")
ty = y + 1.15
lw = 8.3
table(s, M, ty, lw, [
    ["일", "담당", "쓰는 정보"],
    ["다음 벽돌 고르기 · 공급칸 접근", "정책 (ACT)", "카메라 영상 3장 · 관절값"],
    ["집기", "G0v", "손목 카메라"],
    ["쥠 확인", "G1", "손목 힘 · 집게 각도"],
    ["든 벽돌의 자리 판별", "H", "도면 · 관절값"],
    ["설계 자리까지 운반", "G2t", "도면 · 관절값"],
    ["놓기 전 보정 · 놓은 뒤 재배치", "G2 · G3", "작업대 카메라 · 도면"],
], [3.8, 1.5, 3.0], size=15, row_h=0.47, head_h=0.42, align_c=(1,))
rx = M + lw + 0.3; rw = CW - lw - 0.3
_, ph_ = picture(s, A("final_wall_r.png"), rx, ty, w=rw)
card(s, rx, ty + ph_ + 0.15, rw, H - (ty + ph_ + 0.15) - 0.55, "soft", None)
text(s, rx + 0.15, ty + ph_ + 0.15, rw - 0.3, H - (ty + ph_ + 0.15) - 0.55, "**정답 좌표 미사용**\n도면 · 카메라 · 로봇 센서만 사용", 15, "inkdeep", align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, spacing=1.1)

# ═══════════════ 8. 결과: 끝 구성
s = new(); y = chrome(s, 8, "끝 구성: 1,600장 모두 성공, 완성 100벽 · 시방 합격 96벽", "결과 ① · 끝 구성과 오차 조건")
lw = 6.3
b3 = (lw - 0.3) / 3
for i, (n_, l_) in enumerate([("100 %", "① 벽돌 성공 (1,600장)"), ("100벽", "② 16장 완성"), ("96벽", "③ 시방 합격")]):
    bignum(s, M + i * (b3 + 0.15), y, b3, 1.35, n_, l_, "primarysoft" if i == 0 else "soft", "primary", 28)
text(s, M, y + 1.55, lw, 0.36, "**오차를 넣었을 때**", 16, "inkdeep")
table(s, M, y + 1.95, lw, [
    ["넣은 오차", "벽돌 성공률", "완성 벽", "시방 합격 벽"],
    ["없음", "100 %", "100", "96"],
    ["A · 계측 · 센서 오차", "97.8 %", "94", "93"],
    ["B · 공급 팔레트 30 mm 이동", "100 %", "100", "100"],
    ["A + B", "97.0 %", "92", "92"],
], [2.9, 1.25, 1.0, 1.15], size=15, row_h=0.47, head_h=0.42, align_c=(1, 2, 3))
rx = M + lw + 0.3; rw = CW - lw - 0.3
mx, my_, mw, mh = movie(s, VIDEO, A("final_poster.png"), rx, y, rw, 3.75)
text(s, rx, y + mh + 0.08, rw, 0.36, "**끝 구성으로 쌓은 벽** · 16 / 16장 · 시방 합격", 15, "inkdeep", align=PP_ALIGN.CENTER)
footnote(s, "A: 벽 등록 ±3 mm · ±0.3°, 카메라 보정 오차, 깊이 잡음, 힘 센서 잡음 · " + NOTE)

# ═══════════════ 9. 결과: 단계별 기여도
s = new(); y = chrome(s, 9, "하나씩 빼면: H · G2 · G0 · G3 모두 유의한 감소", "결과 ② · 단계별 기여도 (⑤ 구성 기준)")
lw = 6.6
table(s, M, y, lw, [
    ["뺀 단계", "벽돌 성공률", "차이 [95 % 신뢰구간]", "판정"],
    ["없음 (⑤ 구성)", "85.3 %", "기준", "–"],
    ["− G2w 넓게 받기", "83.8 %", "−1.6 [−4.5, +1.6]", "유의차 없음"],
    ["− G3 놓은 뒤 재배치", "66.7 %", "−18.6 [−24.4, −12.8]", "**유의한 감소**"],
    ["− G0 집기 정렬", "52.7 %", "−32.6 [−38.8, −26.1]", "**유의한 감소**"],
    ["− G2 놓기 전 보정", "48.0 %", "−37.3 [−43.6, −31.0]", "**유의한 감소**"],
    ["− H 든 벽돌 기준", "11.4 %", "−73.9 [−77.9, −69.7]", "**유의한 감소**"],
], [2.35, 1.2, 2.1, 1.3], size=14, row_h=0.5, head_h=0.42, align_c=(1, 2, 3))
rx = M + lw + 0.3; rw = CW - lw - 0.3
bw2 = (rw - 0.2) / 2
bignum(s, rx, y, bw2, 1.45, "60 / 60벽", "⑤ 구성: 완성 중 시방 합격", "soft", "primary", 26)
bignum(s, rx + bw2 + 0.2, y, bw2, 1.45, "2 / 23벽", "− G3: 완성 중 시방 합격", "criticalsoft", "critical", 26)
text(s, rx, y + 1.62, rw, 0.36, "**허용오차 6 mm를 넘은 완성 벽 수**", 16, "inkdeep")
th = table(s, rx, y + 2.0, rw, [
    ["시방 항목", "⑤ 구성 (60벽)", "− G3 (23벽)"],
    ["② 선 및 면", "0", "**16**"],
    ["③ 수직도", "0", "**20**"],
    ["④ 평면상 위치", "0", "**4**"],
], [2.0, 1.6, 1.6], size=15, row_h=0.46, head_h=0.42, align_c=(1, 2))
card(s, rx, y + 2.0 + th + 0.18, rw, H - (y + 2.0 + th + 0.18) - 0.6, "primarysoft", None)
text(s, rx + 0.2, y + 2.0 + th + 0.18, rw - 0.4, H - (y + 2.0 + th + 0.18) - 0.6, "**완성 ≠ 합격**: 시방 합격은 놓은 뒤 재배치(G3)가 결정", 15, "inkdeep", align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
footnote(s, "차이 단위 %p · G1 줄은 구현 누락 영향이 있어 제외 · " + NOTE)

# ═══════════════ 10. 결론 · 한계
s = new(); y = chrome(s, 10, "결론: 벽돌 성공 13 % → 100 %, 시뮬레이션 · 100벽 범위의 결과", "결론 · 한계 · 계획서 대비 변경")
c3 = (CW - 0.4) / 3
ch_ = 3.6
kv_card(s, M, y, c3, ch_, "알게 된 것", [("시연", "한 방향으로 일관되게"), ("검측 기준", "손에 든 벽돌"), ("정밀 구간", "측정 기반 단계가 수행"), ("시방 합격", "놓은 뒤 재배치가 결정"), ("남은 약점", "정책의 선행 접촉 (14벽)")], "primary", size=16)
kv_card(s, M + c3 + 0.2, y, c3, ch_, "한계", [("평가 배치", "설정을 고른 100벽과 동일"), ("시뮬레이션", "모르타르 · 마찰 · 센서 값"), ("공급 위치", "정해진 팔레트 기준"), ("기여도", "⑤ 구성 기준으로 측정")], size=16)
kv_card(s, M + 2 * (c3 + 0.2), y, c3, ch_, "계획서 대비 변경", [("규모", "블록 3개 → 3단 16장 벽"), ("정책", "3종 비교 → ACT 1종"), ("평가", "시방 허용오차 기준 추가")], "charcoal", size=16)
ny = y + ch_ + 0.2
card(s, M, ny, CW, H - ny - 0.55, "inkdeep", None)
text(s, M + 0.3, ny, CW - 0.6, H - ny - 0.55, "**다음**: 정책이 맡은 일(고르기 · 접근)이 꼭 필요한 조건은 후속 연구에서 확인", 17, "white", anchor=MSO_ANCHOR.MIDDLE)

prs.save(OUT_PPTX)
tmp = OUT_PPTX + ".tmp.txt"
if os.path.exists(tmp):
    os.remove(tmp)
print("saved", OUT_PPTX)
