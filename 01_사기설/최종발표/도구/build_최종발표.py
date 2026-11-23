# -*- coding: utf-8 -*-
"""사회기반시스템종합설계 14조 · 최종발표 (2026-12-08) 자료. 표지 포함 10장.
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

# ═══════════════ 3. 목적 · 설계 질문 · 제한조건
s = new(); y = chrome(s, 3, "목표: 3단 16장 벽을 시방 허용오차 안에서 쌓는 제어 체계", "목적 · 설계 질문 · 제한조건")
card(s, M, y, CW, 0.95, "inkdeep", None)
text(s, M + 0.25, y, CW - 0.5, 0.95, "**목적**: 시연으로 배운 정책이 벽을 **시방 허용오차 안에서** 쌓도록, 더해야 할 단계를 찾고 **단계별 효과**를 측정", 17, "white", anchor=MSO_ANCHOR.MIDDLE, spacing=1.1)
c3 = (CW - 0.4) / 3
qy = y + 1.12
for i, (k, v) in enumerate([("설계 질문 ①", "무엇이 쌓기를 막는가"), ("설계 질문 ②", "무엇을 더하면 얼마나 오르는가"), ("설계 질문 ③", "더한 단계는 각각 얼마나 필요한가")]):
    x0 = M + i * (c3 + 0.2)
    card(s, x0, qy, c3, 1.35, "primarysoft", None)
    mtext(s, x0 + 0.15, qy, c3 - 0.3, 1.35, [(k, 15, "primary", True), (f"**{v}**", 17, "inkdeep", True)], align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, spacing=1.05, after=4)
cy = qy + 1.52
cw2 = (CW - 0.3) / 2
kv_card(s, M, cy, cw2, H - cy - 0.55, "제한조건 1 · 성능 (공학)", [("기준", "KCS 41 34 00 조적공사"), ("가로줄눈", "10 ± 3 mm"), ("선 · 면 · 수직 · 위치", "6 mm 이내")])
kv_card(s, M + cw2 + 0.3, cy, cw2, H - cy - 0.55, "제한조건 2 · 현실성", [("사용 정보", "도면 · 카메라 · 로봇 센서"), ("사용 금지", "시뮬레이터 정답 좌표"), ("설계 대상", "정책(ACT) + 정책 밖 검측 제어")], "primary")

# ═══════════════ 4. 환경 · 평가
s = new(); y = chrome(s, 4, "같은 100벽을 벽돌 · 완성 벽 · 시방 합격 벽으로 평가", "실험 환경과 평가 지표")
lw = 7.4
_, eh = picture(s, A("env.png"), M, y, w=lw)
rx = M + lw + 0.3; rw = CW - lw - 0.3
kv_card(s, rx, y, rw, eh, "실험 환경 (MuJoCo)", [("로봇", "UR10e + 집게"), ("벽돌", "190 × 90 × 57 mm"), ("벽", "3단 16장 · 줄눈 10 mm"), ("정책", "ACT · 카메라 3대")], size=15)
my = y + eh + 0.2
c3 = (CW - 0.4) / 3
for i, (k, v, d) in enumerate([("벽돌 성공 / 시도", "설계 자리에 놓인 벽돌", "100벽 × 16장 = 1,600 시도"), ("완성 벽", "16장을 모두 쌓은 벽", "100벽 중"), ("시방 합격 벽", "허용오차 5항목 통과", "완성 벽 중")]):
    x0 = M + i * (c3 + 0.2)
    card(s, x0, my, c3, H - my - 0.55, "primarysoft" if i == 0 else "soft", None)
    mtext(s, x0 + 0.15, my, c3 - 0.3, H - my - 0.55, [(f"**{k}**", 18, "primary" if i == 0 else "inkdeep", True), (v, 15, "inkdeep", False), (d, 15, "inkdeep", False)],
          align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, spacing=1.05, after=3)

# ═══════════════ 5. 설계 과정 ①: 계단
s = new(); y = chrome(s, 5, "원인 찾기 → 고치기 반복: 벽돌 성공 13 % → 100 %", "설계 과정 ① · 무엇을 바꿔 얼마나 올랐나")
steps = ["① 처음", "② 시연 통일", "③ + H", "④ + G0", "⑤ + G2w", "⑥ + G2t", "⑦ G0v"]
text(s, M, y, 6.0, 0.36, "**벽돌 성공률 (%) · 1,600장 중**", 16, "inkdeep")
col_chart(s, M - 0.05, y + 0.35, CW + 0.1, 3.3, steps, [("벽돌 성공률", (13.0, 33.6, 53.4, 83.1, 85.3, 91.4, 100.0), "primary")], 110, 25, fmt="0.0", size=14, gap=60)
table(s, M, y + 3.75, CW, [["같은 100벽"] + steps,
                            ["완성 벽", "0", "0", "12", "59", "60", "83", "**100**"],
                            ["시방 합격 벽", "0", "0", "11", "59", "60", "79", "**96**"]],
      [1.9] + [1.49] * 7, size=15, row_h=0.42, head_h=0.4, align_c=range(1, 8))
footnote(s, "① → ②: 정책 재학습 1회 · ③ ~ ⑦: 정책 고정, 검측만 변경 · " + NOTE)

# ═══════════════ 6. 설계 과정 ②: 원인과 대책
s = new(); y = chrome(s, 6, "실패를 동작으로 나눠 가장 큰 원인부터 제거", "설계 과정 ② · 무엇이 막았고 무엇을 바꿨나")
th = table(s, M, y, CW, [
    ["#", "무엇이 막았나", "무엇을 바꿨나", "벽돌 성공률"],
    ["②", "시연의 손목 방향이 둘로 나뉨 (505 : 495벽)", "**시연 통일**: 한 방향으로 다시 수집 · 재학습", "13.0 → **33.6 %**"],
    ["③", "정책이 차례를 앞질러 검측 기준 자리가 어긋남 (81벽)", "**H**: 기준을 손에 든 벽돌의 자리로 변경", "33.6 → **53.4 %**"],
    ["④ ⑦", "정책이 벽돌 중심에서 3 ~ 4 cm 벗어나 집음", "**G0 · G0v**: 집기 마지막 구간을 검측이 수행", "53.4 → **83.1 %**"],
    ["⑤ ⑥", "정책이 설계 자리에서 먼 곳에서 놓기 시작", "**G2w · G2t**: 넘겨받는 범위 확대 · 운반도 검측이", "83.1 → **91.4 %**"],
], [0.9, 4.6, 4.7, 2.1], size=16, row_h=0.72, head_h=0.44, align_c=(0, 3))
py_ = y + th + 0.3
pwid = (CW - 3 * 0.1) / 4
for i, lab in enumerate(["원인 1개 찾기\n기록 · 영상 추적", "제어 1개 추가\n켜고 끌 수 있게", "같은 100벽 확인\n짝 비교 · 95 % 구간", "다음 원인\n효과 없으면 제외"]):
    chevron(s, M + i * (pwid + 0.1), py_, pwid, H - py_ - 0.6, lab, "inkdeep" if i == 0 else "primarysoft", "white" if i == 0 else "inkdeep", 16, first=(i == 0), sub_color="white" if i == 0 else "inkdeep")

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

# ═══════════════ 8. 결과
s = new(); y = chrome(s, 8, "끝 구성: 1,600장 모두 성공, 완성 100벽 · 시방 합격 96벽", "결과 · 끝 구성과 오차 조건")
lw = 6.3
b3 = (lw - 0.3) / 3
for i, (n_, l_) in enumerate([("100 %", "벽돌 성공 (1,600장)"), ("100벽", "16장 완성"), ("96벽", "시방 합격")]):
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

# ═══════════════ 9. 단계별 기여도 · 알게 된 것
s = new(); y = chrome(s, 9, "단계를 하나씩 빼면: H · G2 · G0 순으로 기여가 큼", "결과 · 단계별 기여도와 알게 된 것")
lw = 6.9
text(s, M, y, lw, 0.36, "**하나씩 뺐을 때 벽돌 성공률 (%)**", 16, "inkdeep")
col_chart(s, M - 0.05, y + 0.38, lw, H - y - 1.0, ["모두", "−G2w", "−G3", "−G1", "−G0", "−G2", "−H"],
          [("벽돌 성공률", (85.3, 83.8, 66.7, 53.2, 52.7, 48.0, 11.4), "primary")], 100, 25, fmt="0.0", size=14, gap=55)
rx = M + lw + 0.3; rw = CW - lw - 0.3
learn = [("시연", "한 방향으로 일관되게 수집"), ("검측 기준", "차례 번호가 아닌 손에 든 벽돌"), ("정밀 구간", "집기 · 놓기는 측정 기반 단계가 수행"), ("시방 합격", "놓은 뒤 재배치(G3)가 결정 · 60 → 2벽")]
lh = (H - y - 0.55 - 3 * 0.15) / 4
for i, (k, v) in enumerate(learn):
    yy = y + i * (lh + 0.15)
    card(s, rx, yy, rw, lh, "soft", None)
    pill(s, rx + 0.18, yy + lh / 2 - 0.2, 0.4, 0.4, str(i + 1), "inkdeep", "white", 15)
    mtext(s, rx + 0.75, yy, rw - 0.9, lh, [(f"**{k}**", 16, "primary", True), (v, 15, "inkdeep", False)], anchor=MSO_ANCHOR.MIDDLE, spacing=1.05, after=2)
footnote(s, "⑤ 구성 기준 · −G1은 참고 값 · " + NOTE)

# ═══════════════ 10. 결론 · 한계
s = new(); y = chrome(s, 10, "결론: 벽돌 성공 13 % → 100 %, 시뮬레이션 · 100벽 범위의 결과", "결론 · 한계 · 계획서 대비 변경")
c3 = (CW - 0.4) / 3
ch_ = 3.6
kv_card(s, M, y, c3, ch_, "결론", [("성과", "13 % → **100 %** · 완성 100벽"), ("방법", "원인 1개씩 제거 · 7단계"), ("산출물", "정책 + 검측 제어 체계"), ("남은 약점", "정책의 선행 접촉 (14벽)")], "primary", size=16)
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
