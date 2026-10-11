# -*- coding: utf-8 -*-
"""중간발표 1 · 10장 · v7 (2026-10-11). 디자인: 'minimax' = Meta 커머스 디자인 시스템 요약을 PPT 토큰으로 옮김.
흰 캔버스, 알약(pill) 탭·배지·버튼, 32px(사진 카드)/16px(기능 타일) 둥근 모서리, 1px 머리선 테두리, 그림자 없음,
코발트(primary)는 슬라이드당 핵심 한 곳만. 본문 16pt 이상(주석·인용·축 라벨 예외). 제목은 개조식."""
import sys, os, re
from PIL import Image
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.oxml.ns import qn
from lxml import etree

OUT = sys.argv[1]
ROOT = r"C:/Users/user/Desktop/사기설/"
G = ROOT + "01_사기설/중간발표1/그림/"; V = ROOT + "01_사기설/중간발표1/영상/"; V0 = ROOT + "01_사기설/발표자료_실험1_실험2_20260922/발표용_영상/"
SP = r"C:/Users/user/AppData/Local/Temp/claude/c--Users-user-Desktop----/be685ff9-f10f-46a4-892d-1862ceb8f949/scratchpad/media/v7/"

# ── tokens
C = dict(canvas="FFFFFF", soft="F1F4F7", hair="CBD2D9", hairsoft="E4E9ED", inkdeep="1C2B33", ink="344854", charcoal="465A69",
         slate="5E6E7A", steel="8A9BA8", stone="A8B5BF", primary="0064E0", primarydeep="0143B5", primarysoft="E5F0FF",
         success="31A24C", attention="F7B928", warning="FFE24D", critical="E41E3F", white="FFFFFF")
RGB = {k: RGBColor.from_string(v) for k, v in C.items()}
FONT = "Malgun Gothic"
W, H = 13.333, 7.5
M = 0.5                      # 좌우 여백 (스펙의 32~48px 거터)
NAV_H = 0.52
SECTIONS = ["개요", "변경", "방법", "결과", "한계", "계획"]
ACTIVE = {2: "개요", 3: "변경", 4: "방법", 5: "방법", 6: "결과", 7: "결과", 8: "결과", 9: "한계", 10: "계획"}

prs = Presentation(); prs.slide_width, prs.slide_height = Inches(W), Inches(H)
BLANK = prs.slide_layouts[6]
page = [0]


# ── primitives
def _cw(ch, size):
    """글자 폭(inch) 추정: 한글·한자 0.95em, 공백 0.3em, 그 외 0.55em."""
    em = size / 72
    if "가" <= ch <= "힣" or "㄰" <= ch <= "㆏" or "一" <= ch <= "鿿" or ch in "·→←①②③④⑤":
        return 1.0 * em
    return 0.3 * em if ch == " " else 0.55 * em


def est_lines(s, width_in, size):
    """줄 수 추정(단어 단위 줄바꿈 근사)."""
    s = s.replace("**", "")
    n, cur = 1, 0.0
    for word in s.split(" "):
        wl = sum(_cw(c, size) for c in word)
        if cur > 0 and cur + 0.3 * size / 72 + wl > width_in:
            n += 1; cur = wl
        else:
            cur += (0.3 * size / 72 if cur > 0 else 0) + wl
    return n


def _runs(par, text, size, color, bold=False, align=None, spacing=1.25):
    if align is not None:
        par.alignment = align
    par.line_spacing = spacing
    for tok in re.split(r"(\*\*.+?\*\*)", text):
        if not tok:
            continue
        r = par.add_run(); b = bold
        if tok.startswith("**"):
            tok, b = tok[2:-2], True
        r.text = tok; r.font.name = FONT; r.font.size = Pt(size); r.font.bold = b; r.font.color.rgb = RGB[color]


def text(slide, x, y, w, h, lines, size=16, color="ink", bold=False, align=None, anchor=MSO_ANCHOR.TOP, spacing=1.25, after=3, bullet=False):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h)); tf = tb.text_frame
    tf.word_wrap = True; tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = Inches(0.04); tf.margin_top = tf.margin_bottom = Inches(0.02)
    for i, ln in enumerate([lines] if isinstance(lines, str) else lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph(); p.space_after = Pt(after)
        _runs(p, ("•  " if bullet else "") + ln, size, color, bold, align, spacing)
    return tb


def rect(slide, x, y, w, h, fill="canvas", line="hairsoft", radius=0.0, line_w=0.75):
    """radius(inch): 0=직각, >0 둥근 모서리. 알약은 radius=min(w,h)/2."""
    shp = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE if radius > 0 else MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    if radius > 0:
        shp.adjustments[0] = min(0.5, radius / min(w, h))
    shp.shadow.inherit = False
    if fill is None:
        shp.fill.background()
    else:
        shp.fill.solid(); shp.fill.fore_color.rgb = RGB[fill]
    if line is None:
        shp.line.fill.background()
    else:
        shp.line.color.rgb = RGB[line]; shp.line.width = Pt(line_w)
    shp.text_frame.margin_left = shp.text_frame.margin_right = Inches(0.12)
    shp.text_frame.margin_top = shp.text_frame.margin_bottom = Inches(0.08)
    return shp


def card(slide, x, y, w, h, radius=0.22, fill="canvas", line="hairsoft"):
    """card-icon-feature(16px≈0.22in) / card-product-feature(32px≈0.44in)."""
    return rect(slide, x, y, w, h, fill, line, radius)


def pill(slide, x, y, w, h, label, fill="inkdeep", color="white", size=12, line=None, bold=True):
    shp = rect(slide, x, y, w, h, fill, line, radius=h / 2)
    tf = shp.text_frame; tf.margin_left = tf.margin_right = Inches(0.08); tf.margin_top = tf.margin_bottom = Inches(0.0)
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE; tf.word_wrap = False
    _runs(tf.paragraphs[0], label, size, color, bold, PP_ALIGN.CENTER, 1.0)
    return shp


def badge(slide, x, y, label, kind="success", w=None, h=0.27, size=12):
    fill = {"success": "success", "critical": "critical", "attention": "attention", "warning": "warning", "ink": "inkdeep", "soft": "soft", "primary": "primary"}[kind]
    color = "inkdeep" if kind in ("warning", "soft") else "white"
    if w is None:
        w = sum(_cw(c, size) for c in label) * 1.08 + 0.34
    return pill(slide, x, y, w, h, label, fill, color, size), w


def badges_row(slide, x, y, labels, kind="success", maxw=8.0, gap=0.12, h=0.3):
    cx, cy = x, y
    for lab in labels:
        w = sum(_cw(c, 12) for c in lab) * 1.08 + 0.34
        if cx + w > x + maxw:
            cx, cy = x, cy + h + 0.1
        badge(slide, cx, cy, lab, kind, w, h); cx += w + gap
    return cy + h


def picture(slide, path, x, y, w=None, h=None):
    im = Image.open(path); a = im.width / im.height
    if w is None:
        w = h * a
    elif h is None:
        h = w / a
    elif w / h > a:
        w = h * a
    else:
        h = w / a
    return slide.shapes.add_picture(path, Inches(x), Inches(y), Inches(w), Inches(h)), w, h


def movie(slide, path, poster, x, y, w, h):
    im = Image.open(poster); a = im.width / im.height
    if w / h > a:
        w2, h2 = h * a, h
    else:
        w2, h2 = w, w / a
    x2 = x + (w - w2) / 2
    slide.shapes.add_movie(path, Inches(x2), Inches(y), Inches(w2), Inches(h2), poster_frame_image=poster, mime_type="video/mp4")
    return x2, y, w2, h2


def _cell_border(cell, bottom="E4E9ED", w=6350):
    tcPr = cell._tc.get_or_add_tcPr()
    for tag in ("a:lnL", "a:lnR", "a:lnT", "a:lnB"):
        for e in tcPr.findall(qn(tag)):
            tcPr.remove(e)
    for tag in ("a:lnL", "a:lnR", "a:lnT"):
        ln = etree.SubElement(tcPr, qn(tag), w="0"); etree.SubElement(ln, qn("a:noFill"))
    ln = etree.SubElement(tcPr, qn("a:lnB"), w=str(w), cap="flat"); sf = etree.SubElement(ln, qn("a:solidFill")); etree.SubElement(sf, qn("a:srgbClr"), val=bottom)


def table(slide, x, y, w, rows, widths, size=16, row_h=0.5, head_h=0.42, align_c=(), badges_col=None):
    """tech-specs-table: 머리글 soft 배경, 행 구분 1px hairline-soft, 열 선 없음. 셀 값에 {ok:..}/{no:..}는 배지로.
    행 높이는 글 줄 수로 추정해 키운다(PowerPoint가 자라게 두면 아래 요소와 겹침). 표 전체 높이를 돌려준다."""
    n, m = len(rows), len(rows[0])
    tot = sum(widths)
    colw = [w * wd / tot for wd in widths]
    heights = []
    for i in range(n):
        if i == 0:
            heights.append(head_h); continue
        lines = max(sum(est_lines(part, colw[j] - 0.18, size) for part in rows[i][j].split("\n")) for j in range(m))
        heights.append(max(row_h, lines * size / 72 * 1.3 + 0.16))
    sh = slide.shapes.add_table(n, m, Inches(x), Inches(y), Inches(w), Inches(sum(heights)))
    tbl = sh.table
    tblPr = tbl._tbl.tblPr; tblPr.set("firstRow", "0"); tblPr.set("bandRow", "0")
    sid = tblPr.find(qn("a:tableStyleId"))
    if sid is None:
        sid = etree.SubElement(tblPr, qn("a:tableStyleId"))
    sid.text = "{2D5ABB26-0587-4C30-8999-92F81FD0307C}"     # No Style, No Grid
    for j, wd in enumerate(colw):
        tbl.columns[j].width = Inches(wd)
    for i in range(n):
        tbl.rows[i].height = Inches(heights[i])
        for j in range(m):
            c = tbl.cell(i, j); c.margin_left = c.margin_right = Inches(0.08); c.margin_top = c.margin_bottom = Inches(0.05)
            c.vertical_anchor = MSO_ANCHOR.MIDDLE
            c.fill.solid(); c.fill.fore_color.rgb = RGB["soft" if i == 0 else "canvas"]
            _cell_border(c, "E4E9ED" if i < n - 1 else "CBD2D9")
            tf = c.text_frame; tf.word_wrap = True
            val = rows[i][j]
            al = PP_ALIGN.CENTER if j in align_c else None
            for k, s in enumerate(val.split("\n")):
                p = tf.paragraphs[0] if k == 0 else tf.add_paragraph()
                mm = re.fullmatch(r"\{(ok|no|at):(.+)\}", s)
                if mm:
                    col = {"ok": "success", "no": "critical", "at": "attention"}[mm.group(1)]
                    _runs(p, "● " + mm.group(2), size - 2, col, True, al, 1.15)
                elif i == 0:
                    _runs(p, s, size - 2, "slate", True, al, 1.15)
                else:
                    _runs(p, s, size, "ink", False, al, 1.15)
    return sum(heights)


# ── chrome
def chrome(slide, n, title, eyebrow=None):
    page[0] = n
    # top nav: wordmark · pill tabs · number
    text(slide, M, 0.1, 3.2, NAV_H - 0.1, "14조 · 중간발표 1", 12, "ink", True, anchor=MSO_ANCHOR.MIDDLE)
    xx = 4.55
    for s in SECTIONS:
        act = ACTIVE.get(n) == s
        pill(slide, xx, 0.12, 0.78, 0.3, s, "inkdeep" if act else "canvas", "white" if act else "ink", 11, None if act else "hair", act)
        xx += 0.86
    pill(slide, W - M - 0.95, 0.12, 0.95, 0.3, f"{n} / 10", "canvas", "inkdeep", 12, "hair")
    ln = slide.shapes.add_connector(1, Inches(0), Inches(NAV_H), Inches(W), Inches(NAV_H)); ln.line.color.rgb = RGB["hairsoft"]; ln.line.width = Pt(0.75)
    tsize = 26 if est_lines(title, W - 2 * M - 0.1, 26) == 1 else (23 if est_lines(title, W - 2 * M - 0.1, 23) == 1 else 20)
    if eyebrow:
        text(slide, M, NAV_H + 0.12, W - 2 * M, 0.26, eyebrow, 12, "steel", True)
        text(slide, M, NAV_H + 0.34, W - 2 * M, 0.6, title, tsize, "inkdeep", True, spacing=1.1, anchor=MSO_ANCHOR.MIDDLE)
    else:
        text(slide, M, NAV_H + 0.16, W - 2 * M, 0.6, title, tsize, "inkdeep", True, spacing=1.1, anchor=MSO_ANCHOR.MIDDLE)
    text(slide, M, H - 0.34, 8, 0.26, "사회기반시스템종합설계 14조 · 중간발표 1 · 2026-10-13 · github.com/wonyoungjacob/masonry-IL-capstone", 10, "stone")
    pill(slide, W - M - 0.62, H - 0.4, 0.62, 0.3, str(n), "inkdeep", "white", 12)


def new():
    return prs.slides.add_slide(BLANK)


TOP = NAV_H + 0.98           # 본문 시작 y (eyebrow 없는 경우 ≈1.5)


# ═══════════════════════════════════════════ 1 표지
s = new(); page[0] = 1
text(s, 0.9, 1.25, 7.0, 0.3, "사회기반시스템종합설계 · 14조 · 중간발표 1 · 2026.10.13", 14, "steel", True)
text(s, 0.9, 1.75, 7.0, 2.6, ["모방학습 조적 로봇의", "실패 보정 딜레마와", "정책 밖 검측 설계"], 40, "inkdeep", True, spacing=1.12, after=0)
text(s, 0.9, 4.45, 7.0, 0.4, "MuJoCo 시뮬레이션 · 벽돌 2+1 적층 · SO-ARM101", 18, "ink")
text(s, 0.9, 5.15, 7.0, 0.4, ["정원영 · 임수현 · 강건 · **정성용 (발표자)**"], 16, "ink")
text(s, 0.9, 5.55, 7.0, 0.35, "지도교수 김홍조", 16, "slate")
pill(s, 0.9, 6.25, 2.3, 0.4, "모든 실험은 시뮬레이션", "inkdeep", "white", 13)
pill(s, 3.32, 6.25, 4.5, 0.4, "github.com/wonyoungjacob/masonry-IL-capstone", "canvas", "inkdeep", 12, "inkdeep")
Image.open(G + "cover_cover_az120_placing_top.png").crop((150, 10, 1070, 930)).save(SP + "cover_sq.png")
card(s, 8.0, 1.05, 4.85, 5.3, radius=0.44)
picture(s, SP + "cover_sq.png", 8.2, 1.25, w=4.45)
text(s, 8.2, 5.85, 4.5, 0.3, "모르타르층 위에 세 번째 벽돌을 놓는 순간 (MuJoCo 렌더)", 11, "stone", align=PP_ALIGN.CENTER)
pill(s, W - M - 0.62, H - 0.4, 0.62, 0.3, "1", "inkdeep", "white", 12)

# ═══════════════════════════════════════════ 2 한눈에 요약
s = new(); chrome(s, 2, "연구 개요: 배경 · 문제 정의 · 연구 질문 · 연구 목적 · 예상 기여")
rows2 = [("연구 배경", ["기존 조적 로봇은 **외부 계측 좌표**에 벽돌마다 다시 맞춰, 조건이 바뀌면 사람이 재설정. 카메라·관절값만 쓰는 **모방학습**은 이 부담이 없음"]),
         ("문제 정의", ["성공 시연만 배운 정책은 **실패 상태를 다루지 못함**. 복구를 가르치면 정상 배치의 **정밀도를 잃고**, 안 가르치면 **실패를 모른 채 진행**"]),
         ("연구 질문", ["**RQ1** 복구를 섞으면 얼마나 나빠지고, 안 섞으면 무엇을 놓치나",
                      "**RQ2** 정책 밖 검측은 얼마나 회복시키고, 비용은 얼마인가",
                      "**RQ3** 자체 감각이면 충분한가, 위치 정보면 어느 정확도인가",
                      "**RQ4** 그 정보를 외부 계측 없이 탑재 카메라로 얻을 수 있는가",
                      "**RQ5** 벽체 규모에서도 같은 분담이 유지되는가"]),
         ("연구 목적", ["**정책은 그대로 두고** 실패 인지·보정을 **정책 밖 검측**에 맡기는 설계의 회복량, 필요한 정보·정확도, 외부 계측 없는 확보 가능성을 밝힘"]),
         ("예상 기여", ["① 딜레마의 정량 근거  ② 정책·검측 분담 경계  ③ 검측 정보 요구 사양(2 mm 미만)  ④ 외부 계측 없는 카메라 검측·코드 공개"])]
y = TOP - 0.08; LW = 8.2; TXW = LW - 1.2
for lab, lines in rows2:
    nl = sum(est_lines(t, TXW - 0.1, 16) for t in lines)
    hh = nl * 16 / 72 * 1.2 + 0.04 * len(lines) + 0.1
    pill(s, M, y + 0.04, 1.05, 0.3, lab, "inkdeep", "white", 12)
    text(s, M + 1.2, y, TXW, hh, lines, 16, "ink", spacing=1.18, after=1)
    y += hh + 0.1
    if lab != "예상 기여":
        ln = s.shapes.add_connector(1, Inches(M), Inches(y - 0.05), Inches(M + LW), Inches(y - 0.05)); ln.line.color.rgb = RGB["hairsoft"]; ln.line.width = Pt(0.75)
# 오른쪽: 딜레마 → 해법 도식 (도형)
X0 = M + LW + 0.3; CW = W - M - X0
yy = TOP - 0.08
text(s, X0, yy, CW, 0.3, "실패 대응을 어디에 둘 것인가", 12, "steel", True); yy += 0.34
card(s, X0, yy, CW, 1.3); text(s, X0 + 0.15, yy + 0.08, CW - 0.3, 0.75, ["**복구를 시연에 섞어 가르침**", "덜 무너지지만 4~10 mm 치우침"], 16, "ink", spacing=1.15, after=1)
badge(s, X0 + 0.15, yy + 0.9, "정밀도 손실", "critical"); yy += 1.3 + 0.12
card(s, X0, yy, CW, 1.3); text(s, X0 + 0.15, yy + 0.08, CW - 0.3, 0.75, ["**복구를 가르치지 않음**", "헛집기·걸침을 모른 채 진행"], 16, "ink", spacing=1.15, after=1)
badge(s, X0 + 0.15, yy + 0.9, "실패 인지 없음", "critical"); yy += 1.3 + 0.08
ar = s.shapes.add_shape(MSO_SHAPE.DOWN_ARROW, Inches(X0 + CW / 2 - 0.2), Inches(yy), Inches(0.4), Inches(0.36)); ar.fill.solid(); ar.fill.fore_color.rgb = RGB["stone"]; ar.line.fill.background(); ar.shadow.inherit = False
yy += 0.44
card(s, X0, yy, CW, 1.5, fill="primary", line=None, radius=0.3)
text(s, X0 + 0.15, yy + 0.08, CW - 0.3, 1.35, ["**정책은 그대로, 검측은 정책 밖에**", "G1 잡기 확인 · G2 놓기 전 보정 · G3 놓은 뒤 재배치"], 16, "white", spacing=1.2, after=2)
yy += 1.5 + 0.06
text(s, X0, yy, CW, 0.5, "로봇이 쓰는 정보는 집게 각도·손목 하중·탑재 카메라뿐. 정답 좌표는 시연 생성·학습 라벨·채점에만.", 11, "stone")

# ═══════════════════════════════════════════ 3 변경 사항
s = new(); chrome(s, 3, "설계수행계획서 대비 변경 사항 및 중간발표 1 목표 달성")
th = table(s, M, TOP, 7.9, [["항목", "계획 → 실제", "이유"],
    ["시연 수집", "실물 리더암 원격조작 → **IK 스크립트 자동 수집**, 454회 중 240개 채택", "조작자 편차 제거, 성공 자동 판정, 확장 가능"],
    ["비교 정책", "ACT·Diffusion·SmolVLA·π0 → **ACT·Diffusion**", "SmolVLA 0~2%로 제외, π0 보류"],
    ["환경 조건", "건식 + 등가 접촉층 → **등가 접촉층만**", "모든 비교에 같은 단순화, 건식은 보류"],
    ["실패 대응", "Phase 2 계획 → **G1~G3 검측을 앞당겨 구현**", "실험 2의 실패가 계기"],
    ["검측 좌표", "신규: 정답 좌표 → **탑재 카메라 추정**", "10/7 피드백 '왜 좌표로 보정하나' 반영"]],
    [1.15, 4.05, 2.7], 16, row_h=0.56, head_h=0.38)
yb = TOP + th + 0.2
text(s, M, yb, 7.9, 0.3, "중간발표 1 목표 (계획서 Phase 1 완료 기준) → 달성", 12, "steel", True)
badges_row(s, M, yb + 0.32, ["실행 가능한 장면", "ACT·Diffusion 학습 seed 3개", "정량 결과 40~300회/실험", "실패 영상·분류", "다음 질문 RQ4·RQ5"], "success", 7.9)
# 영상
xv, yv, wv, hv = movie(s, V + "09_스크립트_정상시연_3카메라_2배속.mp4", SP + "poster_09.png", 8.75, TOP, 4.1, 2.3)
pill(s, xv, yv + hv + 0.1, 3.0, 0.3, "▶ IK 교사 시연 수집 (텔레옵 대신)", "inkdeep", "white", 12)
text(s, 8.75, yv + hv + 0.5, 4.1, 1.9, ["정답 좌표를 아는 스크립트가 집기·운반·놓기를 시연하고, 허용오차 안에 놓은 것만 데이터로 남김",
                                        "앞·위·손목 카메라 128×128 + 관절값 6 → 정책 입력. 좌표는 입력에 없음"], 16, "ink", spacing=1.2)
text(s, 8.75, 6.62, 4.1, 0.4, "영상: 01_사기설/중간발표1/영상/09 (2배속, 10 s)", 11, "stone")

# ═══════════════════════════════════════════ 4 성과 1 실험·방법
s = new(); chrome(s, 4, "성과 1: 연구 질문별 수행 실험 및 방법")
th = table(s, M, TOP, 8.1, [["RQ", "실험 · 조건", "지표"],
    ["RQ1", "실험 1 변형: 복구 시연 섞음 vs 안 섞음(±5 mm, 100회) · 실험 2: 넓은 배치 ±30 mm·±60°(200~300회) 실패 분류", "완성률, 평면 오차, 실패 단계"],
    ["RQ2", "실험 3: 같은 정책에 검측을 한 단계씩 추가 A→B→C→D, 학습 seed 3개 × 시험 배치 40~48", "완성률, 투입 시간"],
    ["RQ3", "B(집게 각도·하중)와 C·D(정답 좌표 = 오라클) 비교 · 좌표 잡음 σ 0/2/4 mm", "완성률 변화"],
    ["RQ4", "탑재 RGB-D 카메라 추정 + 검측, 검증 40·시험 50 배치 (교사 기준 완료, 정책은 진행 중)", "추정 오차, 완성률"]],
    [0.75, 5.6, 1.75], 16, row_h=0.6, head_h=0.38)
yb = TOP + th + 0.2
card(s, M, yb, 8.1, 0.95, fill="soft", line=None)
text(s, M + 0.15, yb + 0.08, 7.8, 0.85, ["**방법의 핵심** 정책 가중치는 고정하고 검측만 더하거나 바꿈. 같은 초기 배치끼리 짝지어 비교하므로 차이를 검측의 효과로 읽을 수 있음"], 16, "ink", spacing=1.2)
# 재현용 환경 박스 (작은 글씨 허용)
X0 = M + 8.1 + 0.3; CW = W - M - X0
card(s, X0, TOP, CW, 5.35)
text(s, X0 + 0.12, TOP + 0.08, CW - 0.24, 0.3, "실험 환경 (재현용)", 12, "steel", True)
env = ["MuJoCo 3.13.0 · SO-ARM100 모델(팔 5관절 + 집게 1) · 물리 1 ms, 제어 20 Hz",
       "벽돌 90×42.632×27 mm, 1,800 kg/m³ (KS 190×90×57 축소) · 모르타르층 4.737 mm, 머리줄눈 1 mm · 정착 2 s 뒤 고정",
       "시연 240개(학습 200, 검증 40), 366프레임 18.3 s · 초기 배치 ±30 mm, ±60°, 실행가능성 필터",
       "입력: 앞·손목·위 카메라 128×128 RGB + 관절 6 · 출력: 관절 목표 6, 실행 10스텝(0.5 s)마다 재관측",
       "ACT 40k 갱신 / Diffusion 60k, 배치 32, LeRobot 0.6.1 기본값, 격자 탐색 없음 · 학습 seed 1000/1001/1002",
       "평가: 검증 40000~40039(문턱값), 시험 50000~50049(성능), 1회 90 s, 짝지은 배치, Wilson 95% CI",
       "성공: 3개 모두 위치 4.5 mm·높이 4.5 mm·방향 5°·기울기 10° (실척 9.5 mm; TMS 402, LABC)",
       "G1: 1.5 cm 들고 각도 >0.2 rad AND 하중 ≥0.9 N · G2: 2.5 mm/3°/3 mm 보정 · G3: 4.5/3 mm/5°/5°, 1회 재배치",
       "카메라 검측: 윗면 카메라 1280×960 RGB-D → 색 분할 → 깊이 역투영 → 사각형 맞춤 → 가림 복원",
       "Ubuntu, RTX 5090 1장, PyTorch 2.11.0+cu128 · 코드·설정·원자료: 저장소 sim/, 실험일지.md"]
text(s, X0 + 0.12, TOP + 0.4, CW - 0.24, 4.9, env, 11, "charcoal", spacing=1.15, after=3, bullet=True)

# ═══════════════════════════════════════════ 5 방법론 근거
s = new(); chrome(s, 5, "방법론 선택 근거: 방법 · 환경 · 교사 · 모델 · 검측 위치 · 순서")
tiles = [("모방학습", "보상 설계 없이 시연을 재현, 표본 효율 높음", "강화학습은 보상 악용 위험, 접촉 많은 긴 작업에 불리 [Huang 2026]"),
         ("MuJoCo 시뮬레이션", "같은 배치를 수백 회 반복, 실패를 그대로 재현해 원인 분리", "실기는 리셋·안전·계측 오차가 정책 오차와 섞임 [Tao 2026]"),
         ("스크립트 교사", "좌표를 알아 시연을 얼마든지 만들고 성공을 자동 판정", "사람 원격조작은 숙련자 필요, 조작 습관 편차 [Huang 2026]"),
         ("ACT · Diffusion Policy", "영상→관절의 두 대표 계열, 공개 구현(LeRobot)으로 재현 가능", "SmolVLA는 0~2%라 제외, π0 보류"),
         ("검측을 정책 밖에", "복구 시연을 섞자 정밀도가 무너짐(실험 1) → 정책은 그대로", "정책 밖 규칙층은 선례 [Lin 2026, Yoon 2025, Xu 2026]"),
         ("오라클 → 잡음 → 카메라", "먼저 정답 좌표로 상한을 재야 필요한 정보가 보임", "처음부터 카메라면 인식 오차와 정책 오차가 섞임 [Huang 2026]")]
TW = (W - 2 * M - 0.5) / 3; TH = 2.45
for k, (hd, why, alt) in enumerate(tiles):
    cx = M + (k % 3) * (TW + 0.25); cy = TOP + (k // 3) * (TH + 0.2)
    card(s, cx, cy, TW, TH)
    pill(s, cx + 0.18, cy + 0.18, 0.3, 0.3, str(k + 1), "inkdeep", "white", 12)
    text(s, cx + 0.58, cy + 0.14, TW - 0.75, 0.4, hd, 18, "inkdeep", True)
    text(s, cx + 0.18, cy + 0.62, TW - 0.36, 1.8, [f"**왜:** {why}", f"**대안은:** {alt}"], 16, "ink", spacing=1.2, after=4)
text(s, M, 6.72, W - 2 * M, 0.3, "Huang et al. 2026 J. Comput. Civ. Eng. · Tao et al. 2026 CACAIE · Lin et al. 2026, Yoon et al. 2025, Xu et al. 2026: 시뮬레이션 전용 건설 로봇 논문", 11, "stone")

# ═══════════════════════════════════════════ 6 핵심 결과 1 영상
s = new(); chrome(s, 6, "성과 2-1: 정책 실행 영상: 좁으면 성공, 넓으면 실패, 복구를 가르치면 더듬거림")
cells = [(V + "11_실험1성공_vs_실험2실패_ACT_3배속.mp4", SP + "poster_11.png", "(a) ACT: 같은 계열, 배치 범위만 다름", "실험 1 ±5 mm **63/100** → 실험 2 ±30 mm **0/300**"),
         (V + "06_실험2_Diffusion_성공_2배속_seed50002.mp4", SP + "poster_06.png", "(b) Diffusion: 넓은 배치에서도 되는 경우", "실험 2 완성 **41/200 (21%)**, 실험 1은 90/100"),
         (V + "04_실패3종_순차.mp4", SP + "poster_04.png", "(c) 실패 3종: 헛집기 · 걸침 · 멈춤 → 딜레마의 한쪽", "정책은 실패를 **알아채지 못한 채** 진행"),
         (V + "08_실험1_복구시연섞음_교란.mp4", SP + "poster_08.png", "(d) 복구 시연을 섞어 학습 → 딜레마의 다른 쪽", "낙하는 줄지만 **4~10 mm 치우침**, 완성 90 → 33 이하")]
CW2 = (W - 2 * M - 0.3) / 2; VH = 2.05
for k, (vp, po, lab, desc) in enumerate(cells):
    cx = M + (k % 2) * (CW2 + 0.3); cy = TOP + (k // 2) * (VH + 0.75)
    movie(s, vp, po, cx, cy, CW2, VH)
    text(s, cx, cy + VH + 0.03, CW2, 0.32, lab, 16, "inkdeep", True)
    text(s, cx, cy + VH + 0.34, CW2, 0.32, desc, 16, "ink")

# ═══════════════════════════════════════════ 7 핵심 결과 2 그래프·표
s = new(); chrome(s, 7, "성과 2-2: 검측을 더하면 완성률 회복: 자체 감각은 부족, 위치 정보는 충분")
nums = [("Diffusion Policy", "28% → 63%", "학습 seed 3개 합산 33→75 / 120회", "primary"),
        ("ACT", "0% → 60%", "학습 seed 3개 합산 0→77 / 128회", "inkdeep"),
        ("좌표를 아는 스크립트", "62% → 88%", "31→44 / 50회 · 동작 생성 방식과 무관", "inkdeep")]
NW = (W - 2 * M - 0.4) / 3
for k, (hd, big, sub, fill) in enumerate(nums):
    cx = M + k * (NW + 0.2)
    card(s, cx, TOP, NW, 1.25, fill=fill, line=None, radius=0.3)
    text(s, cx + 0.2, TOP + 0.08, NW - 0.4, 0.3, hd + " · 정책 단독 → 검측 D", 12, "white", True)
    text(s, cx + 0.2, TOP + 0.36, NW - 0.4, 0.55, big, 30, "white", True, spacing=1.0)
    text(s, cx + 0.2, TOP + 0.9, NW - 0.4, 0.3, sub, 11, "white")
Y2 = TOP + 1.45
th = table(s, M, Y2, 6.5, [["조건", "로봇이 쓰는 정보", "현장", "Diffusion", "ACT"],
    ["A", "카메라 + 관절 (정책 단독)", "{ok:가능}", "35%", "0%"],
    ["B", "+ G1 집게 각도·하중", "{ok:가능}", "30%", "0%"],
    ["C", "+ G2 놓기 전 보정", "{no:오라클}", "73%", "29%"],
    ["D", "+ G3 놓은 뒤 재배치", "{no:오라클}", "**75%**", "**54%**"]],
    [0.7, 2.75, 1.05, 1.2, 0.8], 16, row_h=0.46, head_h=0.36, align_c=(0, 2, 3, 4))
text(s, M, Y2 + th + 0.22, 6.5, 1.0, ["학습 seed 1000, 같은 시험 배치끼리(Diffusion 40 · ACT 48). B는 빈손은 막지만 **어디로 갈지 모름**.",
                                   "효과는 **놓기 직전·놓은 뒤**에서 나옴. 실험 3은 '필요한 정보'를 찾는 진단 실험."], 16, "ink", spacing=1.2)
im = Image.open(G + "stages.png"); gw = W - M - (M + 6.5 + 0.3); gh = min(3.95, gw / (im.width / im.height))
pic, pw, ph = picture(s, G + "stages.png", M + 6.5 + 0.3, Y2, w=gw, h=gh)
text(s, M + 6.8, Y2 + ph + 0.05, gw, 0.5, "(a) 검측을 한 단계씩 더함 (seed 1000) (b) seed 3개 합산과 스크립트 비교. 백분율은 0.5 올림, 원자료 sim/outputs/final_test/", 11, "stone")

# ═══════════════════════════════════════════ 8 보조 결과
s = new(); chrome(s, 8, "성과 3: 보조 결과 검증: 반복성 · 일반성 · 정확도 요구 · 카메라 대체")
checks = [("반복성", "학습 seed 3개 모두 상승: 28→63%, 0→60%. 한 seed의 우연이 아님"),
          ("일반성", "좌표를 아는 스크립트도 62→88%. 검측 효과는 동작 생성 방식과 무관"),
          ("정확도 요구", "검측 좌표에 σ 2 mm 잡음이면 효과 절반(85→63%, 60→30%), 4 mm면 15% → **2 mm 미만 필요**"),
          ("카메라 대체", "탑재 윗면 RGB-D 추정 p95 0.96 mm(1,963회). 스크립트 + 카메라 검측 **45/50**, 오라클 48/50")]
LW = 6.6
for k, (hd, body) in enumerate(checks):
    cy = TOP + k * 1.27
    card(s, M, cy, LW, 1.15)
    badge(s, M + 0.18, cy + 0.2, f"✓ {hd}", "success", 1.5, 0.3)
    text(s, M + 1.85, cy + 0.1, LW - 2.0, 1.0, body, 16, "ink", spacing=1.2)
text(s, M, TOP + 5.12, LW, 0.5, "하중 단독 기각 0/1,456회 → G1은 집게 각도만으로도 가능. 카메라 완성률은 둘째 벽돌 여유 0.5 mm 기준(1.5 mm면 33/50: 병목은 배치 규칙).", 11, "stone")
X0 = M + LW + 0.3; CW = W - M - X0
pic, pw, ph = picture(s, G + "noise.png", X0, TOP, w=CW, h=2.55)
text(s, X0, TOP + ph + 0.02, CW, 0.3, "좌표 오차 σ와 완성률 (검증 배치, 조건 D)", 11, "stone")
pic, pw, ph2 = picture(s, G + "cmp_nbr_bias_seed50012.png", X0, TOP + ph + 0.36, w=CW, h=2.4)
text(s, X0, TOP + ph + 0.38 + ph2, CW, 0.3, "같은 배치: 여유 1.5 mm 불합격 → 0.5 mm 합격 (카메라 검측)", 11, "stone")

# ═══════════════════════════════════════════ 9 한계·현장 차이
s = new(); chrome(s, 9, "문제점 · 한계와 원인: 실제 적용 현장과의 차이")
bn = rect(s, 0, NAV_H + 0.01, W, 0.42, "warning", None)
text(s, M, NAV_H + 0.05, W - 2 * M, 0.34, "교수님 피드백 (10/7)  ‘실제 적용 현장과 차이점을 도출하라’ → 아래 표의 각 행이 그 답", 14, "inkdeep", True, anchor=MSO_ANCHOR.MIDDLE)
# 제목을 배너 아래로 다시
for shp in list(s.shapes):
    if shp.has_text_frame and shp.text_frame.text.startswith("문제점 · 한계와 원인"):
        shp.top = Inches(NAV_H + 0.5)
T9 = NAV_H + 1.2
table(s, M, T9, 8.0, [["구분", "우리 시뮬레이션", "실제 현장", "대응"],
    ["위치를 아는 법", "실험 3은 정답 좌표", "센서 추정, 오차·가림", "탑재 카메라로 교체 (RQ4)"],
    ["모르타르", "순응층, 정착 2 s 뒤 고정", "부착·경화, 재료 편차", "가정 명시, RQ5 재검토"],
    ["규모·장비", "축소 벽돌 3개, 소형 팔", "실척 190×90×57, 벽체", "산업용 팔·벽체 (중간 2 이후)"],
    ["센서", "이상적 힘 센서", "잡음·지연", "잡음 민감도로 정량화"],
    ["자재", "같은 치수의 강체", "KS 허용차, 파손", "치수 편차 별도 실험(KICEM)"]],
    [1.4, 2.3, 2.2, 2.1], 16, row_h=0.6, head_h=0.38)
X0 = M + 8.0 + 0.3; CW = W - M - X0
pic, pw, ph = picture(s, SP + "site_rounded.png", X0, T9, w=CW)
card(s, X0, T9 + ph + 0.2, CW, 5.35 - ph - 0.2)
text(s, X0 + 0.15, T9 + ph + 0.28, CW - 0.3, 0.3, "한계와 원인", 12, "steel", True)
text(s, X0 + 0.15, T9 + ph + 0.58, CW - 0.3, 2.6, ["정책 단독 완성률 낮음(28%/0%): 성공 시연만 배워 분포 밖을 모름",
                                                   "배치 여유 1.5 mm가 카메라 오차를 못 흡수 → 0.5 mm로 수정",
                                                   "B·C는 seed 1개 · GPU 비결정성으로 88회 중 5회 결과 변동"], 16, "ink", spacing=1.2, after=4, bullet=True)

# ═══════════════════════════════════════════ 10 향후 계획
s = new(); chrome(s, 10, "향후 계획 및 우선순위")
pic, pw, ph = picture(s, G + "fig_gantt_priority.png", M, TOP, w=8.3)
card(s, M, TOP + ph + 0.15, 8.3, 6.95 - (TOP + ph + 0.15), fill="soft", line=None)
text(s, M + 0.15, TOP + ph + 0.22, 8.0, 1.1, ["**P1** RQ4 학습 정책 + 카메라 검측 D(Ubuntu 22개 작업, ~10/24) · 대형 환경 구축 병행(~11/3)",
                                           "**P2** 시연 수 곡선 60/120/240 · RQ5 벽체(3단×4~5개)에서 정책 + 카메라 검측, 단별 누적 오차 (~12/1)"], 16, "ink", spacing=1.2)
X0 = M + 8.3 + 0.3; CW = W - M - X0
pic, pw, ph2 = picture(s, SP + "concept_rounded.png", X0, TOP, w=CW)
text(s, X0, TOP + ph2 + 0.05, CW, 0.3, "대형 환경 콘셉트: UR5e + 2F-85, 실척 벽돌 3단×5 (렌더 전용)", 11, "stone")
for k, (lab, kind) in enumerate([("11/10 중간발표 2: RQ4 결과 + 대형 환경 시연", "ink"), ("12/08 최종발표: RQ1~5 종합", "ink"), ("12/15 최종보고서", "soft")]):
    pill(s, X0, TOP + ph2 + 0.4 + k * 0.4, CW, 0.32, lab, "inkdeep" if kind == "ink" else "soft", "white" if kind == "ink" else "inkdeep", 12, None if kind == "ink" else "hair")
text(s, X0, TOP + ph2 + 1.65, CW, 1.1, ["**왜 RQ4 먼저:** 정답 좌표 검측은 같은 지적의 반복, 카메라 없는 정책은 벽돌 10개에서 완성률 0"], 16, "ink", spacing=1.2)

prs.save(OUT)
print("saved", OUT, len(prs.slides), "slides")
