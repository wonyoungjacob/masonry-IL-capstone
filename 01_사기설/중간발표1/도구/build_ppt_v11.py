# -*- coding: utf-8 -*-
"""중간발표 1 · v11 (2026-10-11).
- 디자인: minimax(Meta) 토큰 유지 + 컨설팅 원칙(1장 1메시지, 개조식, 카드/표/프로세스/빅넘버, 고대비).
- 글꼴: Pretendard (테마 major/minor latin·ea·Hang + 런 단위 latin/ea).
- 회색·작은 글씨 없음: 본문 16pt, 보조 14pt(차콜) 이상. 인용 문헌 표기 없음(3쪽 직접 인용 1건만 출처 표기).
- 사용한 사진·영상의 저장소 경로를 txt로 출력."""
import sys, os, re, json
from urllib.parse import quote
from PIL import Image, ImageDraw
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION, XL_LABEL_POSITION, XL_MARKER_STYLE
from pptx.chart.data import CategoryChartData
from pptx.opc.constants import RELATIONSHIP_TYPE as RT
from pptx.oxml.ns import qn
from lxml import etree

OUT = sys.argv[1]; TXT = sys.argv[2]
ROOT = "C:/Users/user/Desktop/사기설/"
D1 = ROOT + "01_사기설/중간발표1/"
G = D1 + "그림/"; V = D1 + "영상/"; A7 = D1 + "도구/v7_자산/"; A8 = D1 + "도구/v8_자산/"; A9 = D1 + "도구/v9_자산/"
os.makedirs(A8, exist_ok=True)
REPO = "https://github.com/wonyoungjacob/masonry-IL-capstone"

C = dict(canvas="FFFFFF", soft="F1F4F7", hair="CBD2D9", hairsoft="E4E9ED", inkdeep="1C2B33", ink="2B3B45", charcoal="465A69",
         primary="0064E0", primarysoft="E5F0FF", success="1E8E3E", critical="D0233A", warning="FFE24D", white="FFFFFF", orange="E37400")
RGB = {k: RGBColor.from_string(v) for k, v in C.items()}
FONT = "Pretendard"
W, H = 13.333, 7.5
M = 0.5
NAV_H = 0.52
N_SLIDES = 12
SECTIONS = ["개요", "변경", "방법", "결과", "한계", "계획", "부록"]
ACTIVE = {2: "개요", 3: "변경", 4: "방법", 5: "방법", 6: "결과", 7: "결과", 8: "결과", 9: "결과", 10: "한계", 11: "계획", 12: "부록"}
MEDIA = []           # (page, kind, repo_path, 설명)

prs = Presentation(); prs.slide_width, prs.slide_height = Inches(W), Inches(H)
BLANK = prs.slide_layouts[6]

# ── 테마 글꼴을 Pretendard로 (차트·표·기본 텍스트의 한글까지)
theme = prs.slide_masters[0].part.part_related_by(RT.THEME)
tx = theme.blob.decode("utf-8")
tx = re.sub(r'(<a:(?:major|minor)Font>\s*<a:latin typeface=")[^"]*"', r'\1Pretendard"', tx)
tx = re.sub(r'(<a:ea typeface=")[^"]*"', r'\1Pretendard"', tx)
tx = re.sub(r'(<a:font script="(?:Hang|Jpan|Hans|Hant)" typeface=")[^"]*"', r'\1Pretendard"', tx)
theme._blob = tx.encode("utf-8")


def rel(p):
    return os.path.relpath(p, ROOT).replace("\\", "/")


def use(page, kind, path, note):
    MEDIA.append((page, kind, rel(path), note))


# ── 글자 폭 추정 (줄 수 계산)
KFAC = [0.98]      # 한글 글자 폭(em). 표 높이 추정 때만 Pretendard 실측에 맞춰 0.9로


def _cw(ch, size):
    em = size / 72
    if "\uac00" <= ch <= "\ud7a3" or "\u3130" <= ch <= "\u318f" or ch in "·→←①②③④⑤✓●":
        return KFAC[0] * em
    return 0.3 * em if ch == " " else 0.56 * em


def est_lines(s, width_in, size):
    s = s.replace("**", ""); n, cur = 1, 0.0
    for word in s.split(" "):
        wl = sum(_cw(c, size) for c in word)
        if cur > 0 and cur + 0.3 * size / 72 + wl > width_in:
            n += 1; cur = wl
        else:
            cur += (0.3 * size / 72 if cur > 0 else 0) + wl
    return n


def _font(r, size, color, bold):
    r.font.name = FONT; r.font.size = Pt(size); r.font.bold = bold; r.font.color.rgb = RGB[color]
    rPr = r._r.get_or_add_rPr()
    latin = rPr.find(qn("a:latin"))
    for tag in ("a:ea", "a:cs"):
        e = rPr.find(qn(tag))
        if e is None:
            e = etree.Element(qn(tag)); latin.addnext(e) if tag == "a:ea" else rPr.find(qn("a:ea")).addnext(e)
        e.set("typeface", FONT)


def _runs(par, text, size, color, bold=False, align=None, spacing=1.2):
    if align is not None:
        par.alignment = align
    par.line_spacing = spacing
    for tok in re.split(r"(\*\*.+?\*\*)", text):
        if not tok:
            continue
        r = par.add_run(); b = bold
        if tok.startswith("**"):
            tok, b = tok[2:-2], True
        r.text = tok; _font(r, size, color, b)


def text(slide, x, y, w, h, lines, size=16, color="ink", bold=False, align=None, anchor=MSO_ANCHOR.TOP, spacing=1.2, after=3, bullet=False):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h)); tf = tb.text_frame
    tf.word_wrap = True; tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = Inches(0.04); tf.margin_top = tf.margin_bottom = Inches(0.02)
    for i, ln in enumerate([lines] if isinstance(lines, str) else lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph(); p.space_after = Pt(after)
        _runs(p, ("•  " if bullet else "") + ln, size, color, bold, align, spacing)
    return tb


def rect(slide, x, y, w, h, fill="canvas", line="hairsoft", radius=0.0, line_w=0.75, shape=None):
    shp = slide.shapes.add_shape(shape or (MSO_SHAPE.ROUNDED_RECTANGLE if radius > 0 else MSO_SHAPE.RECTANGLE), Inches(x), Inches(y), Inches(w), Inches(h))
    if radius > 0 and shape is None:
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
    tf = shp.text_frame; tf.margin_left = tf.margin_right = Inches(0.1); tf.margin_top = tf.margin_bottom = Inches(0.05)
    return shp


def card(slide, x, y, w, h, fill="canvas", line="hairsoft", radius=0.22):
    return rect(slide, x, y, w, h, fill, line, radius)


def pill(slide, x, y, w, h, label, fill="inkdeep", color="white", size=13, line=None, bold=True):
    shp = rect(slide, x, y, w, h, fill, line, radius=h / 2)
    tf = shp.text_frame; tf.margin_left = tf.margin_right = Inches(0.06); tf.margin_top = tf.margin_bottom = Inches(0.0)
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE; tf.word_wrap = False
    _runs(tf.paragraphs[0], label, size, color, bold, PP_ALIGN.CENTER, 1.0)
    return shp


def pw(label, size=13):
    return sum(_cw(c, size) for c in label) * 1.06 + 0.36


def chevron(slide, x, y, w, h, label, fill="soft", color="inkdeep", size=16, first=False):
    shp = rect(slide, x, y, w, h, fill, None, shape=MSO_SHAPE.PENTAGON if first else MSO_SHAPE.CHEVRON)
    try:
        shp.adjustments[0] = 0.28
    except Exception:
        pass
    tf = shp.text_frame; tf.vertical_anchor = MSO_ANCHOR.MIDDLE; tf.word_wrap = True
    tf.margin_left = Inches(0.28 if not first else 0.12); tf.margin_right = Inches(0.2)
    lines = label.split("\n")
    for i, ln in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        _runs(p, ln, size if i == 0 else size - 2, color, i == 0, PP_ALIGN.CENTER, 1.05)
    return shp


def arrow_right(slide, x, y, w=0.36, h=0.34, color="charcoal"):
    a = rect(slide, x, y, w, h, color, None, shape=MSO_SHAPE.RIGHT_ARROW); return a


def rounded_img(src, dst, radius_px=48, crop=None, size=None):
    im = Image.open(src).convert("RGB")
    if crop:
        im = im.crop(crop)
    if size:
        im = im.resize(size, Image.Resampling.LANCZOS)
    m = Image.new("L", im.size, 0); ImageDraw.Draw(m).rounded_rectangle((0, 0, im.width - 1, im.height - 1), radius_px, fill=255)
    o = Image.new("RGBA", im.size); o.paste(im, (0, 0)); o.putalpha(m); o.save(dst); return dst


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
    slide.shapes.add_picture(path, Inches(x), Inches(y), Inches(w), Inches(h)); return w, h


def movie(slide, path, poster, x, y, w, h):
    im = Image.open(poster); a = im.width / im.height
    w2, h2 = (h * a, h) if w / h > a else (w, w / a)
    x2 = x + (w - w2) / 2
    slide.shapes.add_movie(path, Inches(x2), Inches(y), Inches(w2), Inches(h2), poster_frame_image=poster, mime_type="video/mp4")
    return x2, y, w2, h2


def _cell_border(cell, bottom="E4E9ED", w=9525):
    tcPr = cell._tc.get_or_add_tcPr()
    for tag in ("a:lnL", "a:lnR", "a:lnT", "a:lnB"):
        for e in tcPr.findall(qn(tag)):
            tcPr.remove(e)
    for tag in ("a:lnL", "a:lnR", "a:lnT"):
        ln = etree.SubElement(tcPr, qn(tag), w="0"); etree.SubElement(ln, qn("a:noFill"))
    ln = etree.SubElement(tcPr, qn("a:lnB"), w=str(w), cap="flat"); sf = etree.SubElement(ln, qn("a:solidFill")); etree.SubElement(sf, qn("a:srgbClr"), val=bottom)


def table(slide, x, y, w, rows, widths, size=16, row_h=0.46, head_h=0.4, align_c=(), head_fill="soft", bold_col0=True):
    n, m = len(rows), len(rows[0]); tot = sum(widths); colw = [w * wd / tot for wd in widths]
    heights = [head_h]; KFAC[0] = 0.9
    for i in range(1, n):
        lines = max(sum(est_lines(re.sub(r"^\{(?:ok|no|at):(.+)\}$", r"● \1", part), colw[j] - 0.2, size) for part in rows[i][j].split("\n")) for j in range(m))
        heights.append(max(row_h, lines * size / 72 * 1.28 + 0.16))
    KFAC[0] = 0.98
    sh = slide.shapes.add_table(n, m, Inches(x), Inches(y), Inches(w), Inches(sum(heights))); tbl = sh.table
    tblPr = tbl._tbl.tblPr; tblPr.set("firstRow", "0"); tblPr.set("bandRow", "0")
    sid = tblPr.find(qn("a:tableStyleId"))
    if sid is None:
        sid = etree.SubElement(tblPr, qn("a:tableStyleId"))
    sid.text = "{2D5ABB26-0587-4C30-8999-92F81FD0307C}"
    for j, cw in enumerate(colw):
        tbl.columns[j].width = Inches(cw)
    for i in range(n):
        tbl.rows[i].height = Inches(heights[i])
        for j in range(m):
            c = tbl.cell(i, j); c.margin_left = c.margin_right = Inches(0.09); c.margin_top = c.margin_bottom = Inches(0.05)
            c.vertical_anchor = MSO_ANCHOR.MIDDLE
            c.fill.solid(); c.fill.fore_color.rgb = RGB[head_fill if i == 0 else "canvas"]
            _cell_border(c, "CBD2D9" if i in (0, n - 1) else "E4E9ED")
            tf = c.text_frame; tf.word_wrap = True
            al = PP_ALIGN.CENTER if j in align_c else None
            for k, s in enumerate(rows[i][j].split("\n")):
                p = tf.paragraphs[0] if k == 0 else tf.add_paragraph()
                mm = re.fullmatch(r"\{(ok|no|at):(.+)\}", s)
                if mm:
                    _runs(p, "● " + mm.group(2), size, {"ok": "success", "no": "critical", "at": "orange"}[mm.group(1)], True, al, 1.1)
                elif i == 0:
                    _runs(p, s, size - 1, "white" if head_fill == "inkdeep" else "inkdeep", True, al, 1.1)
                else:
                    _runs(p, s, size, "ink", bold_col0 and j == 0, al, 1.15)
    return sum(heights)


def chart_common(ch, legend=True):
    ch.font.size = Pt(14); ch.font.name = FONT; ch.font.color.rgb = RGB["ink"]
    ch.has_legend = legend
    if legend:
        ch.legend.position = XL_LEGEND_POSITION.TOP; ch.legend.include_in_layout = False; ch.legend.font.size = Pt(14); ch.legend.font.bold = True
    va = ch.value_axis; va.minimum_scale = 0; va.maximum_scale = 100; va.major_unit = 25
    va.has_major_gridlines = True; va.major_gridlines.format.line.color.rgb = RGB["hairsoft"]; va.format.line.fill.background()
    va.tick_labels.font.size = Pt(13); va.tick_labels.font.color.rgb = RGB["charcoal"]
    ca = ch.category_axis; ca.tick_labels.font.size = Pt(14); ca.tick_labels.font.bold = True; ca.format.line.color.rgb = RGB["hair"]
    ca.has_major_gridlines = False


def bar_chart(slide, x, y, w, h, cats, series, legend=True, gap=70):
    cd = CategoryChartData(); cd.categories = cats
    for n_, v, _ in series:
        cd.add_series(n_, v)
    ch = slide.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(x), Inches(y), Inches(w), Inches(h), cd).chart
    chart_common(ch, legend)
    pl = ch.plots[0]; pl.gap_width = gap; pl.overlap = -8; pl.has_data_labels = True
    dl = pl.data_labels; dl.number_format = '0"%"'; dl.number_format_is_linked = False; dl.position = XL_LABEL_POSITION.OUTSIDE_END
    dl.font.size = Pt(15); dl.font.bold = True; dl.font.color.rgb = RGB["inkdeep"]
    for ser, (_, _, col) in zip(pl.series, series):
        ser.format.fill.solid(); ser.format.fill.fore_color.rgb = RGB[col]; ser.format.line.fill.background()
    return ch


def line_chart(slide, x, y, w, h, cats, series, xtitle):
    cd = CategoryChartData(); cd.categories = cats
    for n_, v, _ in series:
        cd.add_series(n_, v)
    ch = slide.shapes.add_chart(XL_CHART_TYPE.LINE_MARKERS, Inches(x), Inches(y), Inches(w), Inches(h), cd).chart
    chart_common(ch)
    ca = ch.category_axis; ca.has_title = True; ca.axis_title.text_frame.text = xtitle
    for p in ca.axis_title.text_frame.paragraphs:
        for r in p.runs:
            _font(r, 14, "ink", True)
    pl = ch.plots[0]; pl.has_data_labels = True
    dl = pl.data_labels; dl.number_format = '0"%"'; dl.number_format_is_linked = False; dl.position = XL_LABEL_POSITION.ABOVE
    dl.font.size = Pt(15); dl.font.bold = True
    for ser, (_, _, col) in zip(pl.series, series):
        ser.smooth = False; ser.format.line.color.rgb = RGB[col]; ser.format.line.width = Pt(3.25)
        ser.marker.style = XL_MARKER_STYLE.CIRCLE; ser.marker.size = 11
        ser.marker.format.fill.solid(); ser.marker.format.fill.fore_color.rgb = RGB[col]; ser.marker.format.line.color.rgb = RGB[col]
    return ch


# ── 크롬
def chrome(slide, n, title, section=None):
    text(slide, M, 0.1, 3.2, NAV_H - 0.1, "14조 · 중간발표 1", 13, "inkdeep", True, anchor=MSO_ANCHOR.MIDDLE)
    xx = 4.0
    for s_ in SECTIONS:
        act = ACTIVE.get(n) == s_
        pill(slide, xx, 0.11, 0.82, 0.31, s_, "inkdeep" if act else "canvas", "white" if act else "ink", 12, None if act else "hair", act)
        xx += 0.9
    pill(slide, W - M - 1.0, 0.11, 1.0, 0.31, f"{n} / {N_SLIDES}", "canvas", "inkdeep", 13, "hair")
    ln = slide.shapes.add_connector(1, Inches(0), Inches(NAV_H), Inches(W), Inches(NAV_H)); ln.line.color.rgb = RGB["hairsoft"]; ln.line.width = Pt(0.75)
    if section:
        pill(slide, M, NAV_H + 0.16, pw(section, 13), 0.32, section, "primarysoft", "primary", 13)
        ty = NAV_H + 0.52
    else:
        ty = NAV_H + 0.18
    tsize = 28 if est_lines(title, W - 2 * M - 0.1, 28) == 1 else 24
    text(slide, M, ty, W - 2 * M, 0.58, title, tsize, "inkdeep", True, spacing=1.05, anchor=MSO_ANCHOR.MIDDLE)
    pill(slide, W - M - 0.62, H - 0.42, 0.62, 0.32, str(n), "inkdeep", "white", 13)
    return ty + 0.68           # 본문 시작 y


def new():
    return prs.slides.add_slide(BLANK)


# ═══════════════════════════ 1 표지
s = new()
text(s, 0.9, 1.2, 7.0, 0.35, "사회기반시스템종합설계 · 14조 · 중간발표 1 · 2026.10.13", 16, "charcoal", True)
text(s, 0.9, 1.75, 7.0, 2.6, ["모방학습 조적 로봇의", "실패 보정 딜레마와", "정책 밖 검측 설계"], 42, "inkdeep", True, spacing=1.1, after=0)
text(s, 0.9, 4.5, 7.0, 0.4, "MuJoCo 시뮬레이션 · 벽돌 2+1 적층 · SO-ARM101", 20, "ink")
text(s, 0.9, 5.2, 7.0, 0.4, "정원영 · 임수현 · 강건 · **정성용 (발표자)**", 18, "ink")
text(s, 0.9, 5.62, 7.0, 0.36, "지도교수 김홍조", 16, "charcoal")
pill(s, 0.9, 6.3, 2.5, 0.42, "모든 실험은 시뮬레이션", "inkdeep", "white", 14)
src = G + "cover_cover_az120_placing_top.png"
cov = rounded_img(src, A8 + "p01_cover.png", 60, crop=(150, 10, 1070, 930))
picture(s, cov, 8.05, 1.25, w=4.75)
pill(s, W - M - 0.62, H - 0.42, 0.62, 0.32, "1", "inkdeep", "white", 13)
use(1, "사진", src, "표지 사진 원본 (1280×960)"); use(1, "사진", cov, "표지에 넣은 정사각 크롭·둥근 모서리판")

# ═══════════════════════════ 2 연구 개요
s = new(); T = chrome(s, 2, "연구 개요")
rows2 = [("연구 배경", ["기존 조적 로봇: **외부 계측 좌표** 의존 → 조건 바뀌면 재설정",
                      "모방학습: 카메라·관절값만 사용 → **재설정 불필요**"]),
         ("문제 정의", ["모방학습 정책: **실패 상태 대응 취약**",
                      "복구 학습 시 **정밀도 손실**, 미학습 시 **실패 인지 불가**"]),
         ("연구 목적", ["**정책은 그대로**, 실패 인지·보정은 **정책 밖 검측**",
                      "필요 정보·정확도 정량적 규명"])]
LW = 7.55; y = T
for lab, lines in rows2:
    hh = sum(est_lines(t, LW - 1.45, 17) for t in lines) * 17 / 72 * 1.25 + 0.12
    pill(s, M, y + 0.03, 1.2, 0.34, lab, "inkdeep", "white", 14)
    text(s, M + 1.38, y, LW - 1.38, hh, lines, 17, "ink", spacing=1.2, after=2)
    y += hh + 0.14
    ln = s.shapes.add_connector(1, Inches(M), Inches(y - 0.07), Inches(M + LW), Inches(y - 0.07)); ln.line.color.rgb = RGB["hairsoft"]; ln.line.width = Pt(0.75)
pill(s, M, y + 0.03, 1.2, 0.34, "예상 기여", "inkdeep", "white", 14)
contrib = [("①", "딜레마 정량 근거"), ("②", "정책·검측 분담 경계"), ("③", "검측 정보 요구 사양"), ("④", "외부 계측 없는 카메라 검측")]
cw_ = (LW - 1.38 - 0.15) / 2
for k, (num, lab) in enumerate(contrib):
    cx = M + 1.38 + (k % 2) * (cw_ + 0.15); cy = y + (k // 2) * 0.62
    card(s, cx, cy, cw_, 0.52, fill="soft", line=None, radius=0.14)
    text(s, cx + 0.12, cy + 0.06, cw_ - 0.2, 0.42, f"**{num}** {lab}", 16, "inkdeep", anchor=MSO_ANCHOR.MIDDLE)
X0 = M + LW + 0.3; CW = W - M - X0
dsrc = G + "cover_cover_az60_placing_top.png"
demo = rounded_img(dsrc, A8 + "p02_demo.png", 44, crop=(60, 120, 1240, 860))
dw, dh = picture(s, demo, X0, T - 0.02, w=CW)
text(s, X0, T + dh + 0.0, CW, 0.32, "역기구학 대본의 시연 장면 (MuJoCo)", 14, "charcoal", True, align=PP_ALIGN.CENTER)
use(2, "사진", dsrc, "2쪽 시연 장면 원본"); use(2, "사진", demo, "2쪽에 넣은 크롭판")
yy = T + dh + 0.42; hw = (CW - 0.15) / 2
for k, (hd, sub) in enumerate([("복구를 가르침", "정밀도 손실"), ("가르치지 않음", "실패 인지 불가")]):
    cx = X0 + k * (hw + 0.15)
    card(s, cx, yy, hw, 0.95, fill="canvas", line="critical", radius=0.16)
    text(s, cx + 0.08, yy + 0.08, hw - 0.16, 0.4, hd, 16, "inkdeep", True, align=PP_ALIGN.CENTER)
    text(s, cx + 0.08, yy + 0.48, hw - 0.16, 0.4, sub, 16, "critical", True, align=PP_ALIGN.CENTER)
yy += 1.03
rect(s, X0 + CW / 2 - 0.2, yy, 0.4, 0.3, "charcoal", None, shape=MSO_SHAPE.DOWN_ARROW); yy += 0.36
card(s, X0, yy, CW, 0.62, fill="primary", line=None, radius=0.18)
text(s, X0 + 0.1, yy + 0.05, CW - 0.2, 0.52, "**해법: 정책은 그대로, 검측은 정책 밖에**", 16, "white", align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)

# ═══════════════════════════ 3 수정 사항 · 진행상황
s = new(); T = chrome(s, 3, "설계수행계획서 대비 수정 사항 및 진행상황 보고")
CWL = 7.0; GAP = 0.3; XR = M + CWL + GAP; CWR = W - M - XR
for x_, w_, lab in ((M, CWL, "①  수정 사항"), (XR, CWR, "②  진행상황 보고")):
    card(s, x_, T - 0.08, w_, 0.46, fill="inkdeep", line=None, radius=0.12)
    text(s, x_ + 0.15, T - 0.08, w_ - 0.3, 0.46, lab, 18, "white", True, anchor=MSO_ANCHOR.MIDDLE)
Y = T + 0.48
th = table(s, M, Y, CWL, [["항목", "계획", "수정", "이유"],
                          ["시연 수집", "리더암 원격조작", "**역기구학 대본**", "매 시연 숙련자 필요"],
                          ["비교 정책", "4종 동시 비교", "**ACT·Diffusion 우선**", "SmolVLA·π0.5는 추후"],
                          ["실패 대응", "11월 설계", "**검사 3단계 선구현**\n잡기·보정·재배치", "정책 단독 실패 확인"]],
          [1.05, 1.6, 2.2, 2.15], 15, row_h=0.46, head_h=0.38)
Y += th + 0.12
p09 = A7 + "poster_09.png"
VW = 4.55
xv, yv, wv, hv = movie(s, V + "09_스크립트_정상시연_3카메라_2배속.mp4", p09, M, Y, VW, 6.95 - Y - 0.62)
use(3, "영상", V + "09_스크립트_정상시연_3카메라_2배속.mp4", "역기구학 대본의 시연 수집 (앞·위·손목 카메라, 2배속, 10 s)"); use(3, "사진", p09, "영상 포스터 프레임")
text(s, M, yv + hv + 0.04, VW, 0.58, ["**역기구학(IK)**: 목표 위치·자세 → **관절 각도 역산**", "벽돌 좌표로 집기·놓기 경로 자동 생성"], 14, "ink", spacing=1.1, after=1)
XC = M + VW + 0.2; WC = CWL - VW - 0.2
card(s, XC, Y, WC, 6.95 - Y, fill="soft", line=None, radius=0.16)
pill(s, XC + 0.15, Y + 0.15, pw("대본을 쓴 이유", 14), 0.32, "대본을 쓴 이유", "primary", "white", 14)
text(s, XC + 0.15, Y + 0.6, WC - 0.3, 6.95 - Y - 0.7, ["**숙련자 불필요**", "시연 무제한 생성", "**습관 차이 없음**", "조건 비교 공정", "**성공 자동 판정**"], 15, "ink", spacing=1.08, after=1)
# 오른쪽: 진행상황
Y = T + 0.52
steps = [("9/15", "계획서", "done"), ("9/19", "실험 1", "done"), ("9/22", "실험 2", "done"), ("9/28", "실험 3", "done"), ("10/8~", "카메라 검측", "prog"), ("10/13", "중간 1", "now")]
x0, x1 = XR + 0.4, XR + CWR - 0.4
ln = s.shapes.add_connector(1, Inches(x0), Inches(Y + 0.52), Inches(x1), Inches(Y + 0.52)); ln.line.color.rgb = RGB["hair"]; ln.line.width = Pt(2)
for k, (d_, lab, st) in enumerate(steps):
    cx = x0 + (x1 - x0) * k / (len(steps) - 1)
    col = {"done": "inkdeep", "prog": "orange", "now": "primary"}[st]
    text(s, cx - 0.5, Y, 1.0, 0.3, d_, 14, col, True, align=PP_ALIGN.CENTER)
    rect(s, cx - 0.12, Y + 0.4, 0.24, 0.24, col, None, shape=MSO_SHAPE.OVAL)
    text(s, cx - 0.55, Y + 0.68, 1.1, 0.3, lab, 14, col, True, align=PP_ALIGN.CENTER)
Y += 1.15
table(s, XR, Y, CWR, [["계획서 완료 기준", "달성", "상태"],
                     ["실행 가능한 장면", "2+1 적층 · 모르타르층", "{ok:완료}"],
                     ["초기 정책 학습", "2종 × 학습 seed 3", "{ok:완료}"],
                     ["평가 20회 이상", "실험당 40~300회", "{ok:완료}"],
                     ["실패 영상·분류", "실패 4유형 분류", "{ok:완료}"],
                     ["다음 설계 질문", "카메라 검측 · 벽체", "{ok:완료}"],
                     ["카메라 검측", "정책 적용 평가 중", "{at:진행 중}"]],
      [1.65, 2.3, 1.08], 15, row_h=0.52, head_h=0.4, align_c=(2,))

# ═══════════════════════════ 4 연구 질문별 실험
s = new(); T = chrome(s, 4, "연구 질문 5개와 대응 실험", "성과 1 · 수행 실험")
th = table(s, M, T, W - 2 * M, [["연구 질문", "실험", "지표", "상태"],
                                ["**1**  복구 동작을 가르치면 무엇을 얻고 무엇을 잃는가", "실험 1 변형 · 실험 2", "완성률 · 평면 오차", "{ok:완료}"],
                                ["**2**  정책 밖 검사를 더하면 완성률이 얼마나 오르는가", "실험 3 (조건 A → D)", "완성률 · 투입 시간", "{ok:완료}"],
                                ["**3**  검사에 필요한 정보는 무엇이고, 얼마나 정확해야 하는가", "잡기 확인 vs 위치 보정 · 위치 오차 주입", "완성률 변화", "{ok:완료}"],
                                ["**4**  그 위치 정보를 카메라 영상으로 대신할 수 있는가", "카메라 위치 추정 + 검사", "추정 오차 · 완성률", "{at:진행 중}"],
                                ["**5**  벽체 규모에서도 같은 효과가 나는가", "대형 로봇 · 다단 벽체", "단별 누적 오차", "{at:최종}"]],
           [5.3, 3.05, 2.25, 1.1], 16, row_h=0.52, head_h=0.42, align_c=(3,), bold_col0=False)
Y = T + th + 0.28
text(s, M, Y, W - 2 * M, 0.36, "실험 3 설계: 정책 고정, 검사만 한 단계씩 추가", 17, "inkdeep", True)
Y += 0.44
cond = [("A  정책 단독", "카메라 + 관절"), ("B  + 잡기 확인", "집게 각도·하중"), ("C  + 놓기 전 보정", "벽돌 위치"), ("D  + 놓은 뒤 재배치", "벽돌 위치")]
cw4 = (W - 2 * M) / 4
for k, (a_, b_) in enumerate(cond):
    chevron(s, M + k * cw4, Y, cw4 + 0.06, 0.92, f"{a_}\n{b_}", "primary" if k == 3 else "soft", "white" if k == 3 else "inkdeep", 17, first=(k == 0))
Y += 1.05
text(s, M, Y, W - 2 * M, 0.4, "같은 초기 배치끼리 비교 → **완성률 차이 = 검사의 효과**", 17, "ink")

# ═══════════════════════════ 5 방법론 근거
s = new(); T = chrome(s, 5, "방법 선택 5가지의 근거와 택하지 않은 대안", "방법론 근거")
tiles = [("모방학습", ["보상 함수 설계 불필요", "시연 재현 → 학습 효율 높음"], "강화학습 → 보상 설계 부담"),
         ("시뮬레이션", ["같은 배치를 수백 회 반복", "실패를 그대로 재현해 원인 분리"], "실기 → 리셋·안전·계측 오차"),
         ("역기구학 대본", ["벽돌 좌표로 시연 자동 생성", "성공 여부 자동 판정·선별"], "원격조작 → 숙련자 필요"),
         ("검사는 정책 밖", ["정책 정밀도 그대로 보존", "정책 고정 → 검사 효과만 분리"], "복구 시연 학습 → 정밀도 저하"),
         ("정답 좌표로 먼저 시험", ["영상 기반 시험 전 기준선", "완벽한 위치일 때 상한 측정"], "바로 카메라 → 오차 원인 혼재")]
TW = (W - 2 * M - 0.5) / 3; TH = (6.95 - T - 0.22) / 2
for k, (hd, whys, alt) in enumerate(tiles):
    row = 0 if k < 3 else 1; col = k if k < 3 else k - 3
    x_start = M if row == 0 else M + (TW + 0.25) / 2
    cx = x_start + col * (TW + 0.25); cy = T + row * (TH + 0.22)
    card(s, cx, cy, TW, TH, radius=0.22)
    pill(s, cx + 0.2, cy + 0.2, 0.38, 0.38, str(k + 1), "inkdeep", "white", 15)
    text(s, cx + 0.68, cy + 0.14, TW - 0.85, 0.5, hd, 20, "inkdeep", True, anchor=MSO_ANCHOR.MIDDLE)
    pill(s, cx + 0.2, cy + 0.78, 0.68, 0.3, "이유", "success", "white", 13)
    text(s, cx + 0.98, cy + 0.72, TW - 1.12, 0.95, whys, 16, "ink", spacing=1.12, after=3)
    pill(s, cx + 0.2, cy + TH - 0.58, 0.68, 0.3, "대안", "charcoal", "white", 13)
    text(s, cx + 0.98, cy + TH - 0.68, TW - 1.12, 0.5, alt, 16, "charcoal", anchor=MSO_ANCHOR.MIDDLE)

# ═══════════════════════════ 6 딜레마 영상
def cond(slide, x, y, w, label, h=0.4):
    """실험 조건 표기 띠: 결과 수치마다 붙인다."""
    card(slide, x, y, w, h, fill="soft", line=None, radius=0.12)
    text(slide, x + 0.12, y, w - 0.24, h, "**조건** " + label, 14, "charcoal", anchor=MSO_ANCHOR.MIDDLE)


def placeholder(slide, x, y, w, h, title, sub):
    shp = rect(slide, x, y, w, h, "soft", "hair", radius=0.12, line_w=1.5)
    shp.line.dash_style = 4
    text(slide, x + 0.15, y + h / 2 - 0.42, w - 0.3, 0.84, [f"**{title}**", sub], 15, "charcoal", align=PP_ALIGN.CENTER, spacing=1.1, after=2)


s = new(); T = chrome(s, 6, "복구 미학습은 실패를 모르고, 복구 학습은 더듬거림", "성과 2 · 핵심 결과 ①")
LW6 = 4.25; XR6 = M + LW6 + 0.3; WR6 = W - M - XR6
# ① 왼쪽
card(s, M, T - 0.06, LW6, 0.46, fill="critical", line=None, radius=0.12)
text(s, M + 0.15, T - 0.06, LW6 - 0.3, 0.46, "딜레마 ①  복구를 가르치지 않으면", 16, "white", True, anchor=MSO_ANCHOR.MIDDLE)
VH6 = 2.75
vx, vy, vw, vh = movie(s, V + "21_빈손운반_재현_seed40000.mp4", A9 + "poster_21.png", M, T + 0.5, LW6, VH6)
use(6, "영상", V + "21_빈손운반_재현_seed40000.mp4", "딜레마 ①: 집지 못하고도 그대로 운반"); use(6, "사진", A9 + "poster_21.png", "포스터 프레임")
text(s, M, vy + vh + 0.06, LW6, 0.36, "집지 못하고도 그대로 운반 · 실패 유형 재현", 16, "inkdeep", True)
text(s, M, vy + vh + 0.46, LW6, 0.8, ["정책은 **실패를 알아채지 못한 채** 다음 동작으로", "정책 단독 완성: Diffusion **35%** · ACT **0%**"], 15, "ink", spacing=1.12, after=2)
cond(s, M, 6.55, LW6, "실험 3 · 넓은 배치 · 정책 단독 · 시험 배치")
# ② 오른쪽: 같은 조건 비교
card(s, XR6, T - 0.06, WR6, 0.46, fill="critical", line=None, radius=0.12)
text(s, XR6 + 0.15, T - 0.06, WR6 - 0.3, 0.46, "딜레마 ②  복구를 가르치면 — 같은 조건에서 학습 데이터만 다름", 16, "white", True, anchor=MSO_ANCHOR.MIDDLE)
hw6 = (WR6 - 0.25) / 2
placeholder(s, XR6, T + 0.5, hw6, VH6 * 0.84, "영상 자리 (Ubuntu 렌더 예정)", "복구 없이 학습한 Diffusion\n실험 1 · 같은 초기 배치")
vx2, vy2, vw2, vh2 = movie(s, V + "22_복구시연학습_Diffusion_놓고도더듬거림_2배속.mp4", A9 + "poster_22.png", XR6 + hw6 + 0.25, T + 0.5, hw6, VH6)
use(6, "영상", V + "22_복구시연학습_Diffusion_놓고도더듬거림_2배속.mp4", "딜레마 ②: 복구 시연을 섞어 학습한 Diffusion"); use(6, "사진", A9 + "poster_22.png", "포스터 프레임")
yb = T + 0.5 + max(VH6 * 0.84, vh2) + 0.08
for k, (hd, big, sub, col) in enumerate([("복구 없이 학습", "90%", "평면 오차 2.6 mm · 깔끔하게 놓음", "success"),
                                         ("복구 섞어 학습", "2%", "평면 오차 6.3 mm · 다 놓고도 더듬거림", "critical")]):
    cx = XR6 + k * (hw6 + 0.25)
    card(s, cx, yb, hw6, 6.45 - yb, fill="canvas", line=col, radius=0.18)
    text(s, cx + 0.15, yb + 0.08, hw6 - 0.3, 0.34, hd + " · 완성률", 15, "inkdeep", True)
    text(s, cx + 0.15, yb + 0.42, hw6 - 0.3, 0.6, big, 30, col, True, spacing=1.0)
    text(s, cx + 0.15, yb + 1.02, hw6 - 0.3, 0.4, sub, 15, "ink")
cond(s, XR6, 6.55, WR6, "실험 1 · 좁은 배치 ±5 mm·±10° · Diffusion · 교란 없음 · 각 100회")

# ═══════════════════════════ 7 핵심 결과 ② 검사 효과
s = new(); T = chrome(s, 7, "정책 밖 검사로 완성률 2배 이상 회복", "성과 2 · 핵심 결과 ②")
LW8 = 5.95
for k, (hd, big, fill) in enumerate([("Diffusion Policy · A → D", "35% → 75%", "primary"), ("ACT · A → D", "0% → 54%", "inkdeep")]):
    cx = M + k * (LW8 / 2 + 0.08)
    card(s, cx, T, LW8 / 2 - 0.08, 1.2, fill=fill, line=None, radius=0.26)
    text(s, cx + 0.18, T + 0.1, LW8 / 2 - 0.4, 0.34, hd, 15, "white", True)
    text(s, cx + 0.18, T + 0.46, LW8 / 2 - 0.3, 0.65, big, 27, "white", True, spacing=1.0)
Y = T + 1.36
th = table(s, M, Y, LW8, [["조건", "추가 검사", "쓰는 정보", "현장"],
                         ["A", "없음 (정책 단독)", "카메라·관절", "{ok:가능}"],
                         ["B", "+ 잡기 확인", "집게 각도·하중", "{ok:가능}"],
                         ["C", "+ 놓기 전 보정", "벽돌 위치", "{at:카메라 필요}"],
                         ["D", "+ 놓은 뒤 재배치", "벽돌 위치", "{at:카메라 필요}"]],
          [0.65, 1.85, 1.7, 1.75], 16, row_h=0.44, head_h=0.38, align_c=(0, 3))
Y += th + 0.12
card(s, M, Y, LW8, 6.45 - Y, fill="soft", line=None, radius=0.16)
text(s, M + 0.15, Y + 0.08, LW8 - 0.3, 6.45 - Y - 0.12,
     ["**잡기 확인(B)**: 효과 없음 → 어디로 갈지 모름", "**위치 정보(C·D)**: 놓기 전후 보정으로 급상승"], 16, "ink", spacing=1.15, after=4, anchor=MSO_ANCHOR.MIDDLE)
X8 = M + LW8 + 0.35; W8 = W - M - X8
bar_chart(s, X8, T - 0.05, W8, 4.85, ["A 정책 단독", "B +잡기 확인", "C +놓기 전 보정", "D +재배치"],
          [("Diffusion Policy", (35, 30, 73, 75), "primary"), ("ACT", (0, 0, 29, 54), "orange")])
cond(s, M, 6.55, W - 2 * M, "실험 3 · 넓은 배치 ±30 mm·±60° · 실행가능성 필터 · 학습 seed 1000 · 시험 배치 (Diffusion 40회 · ACT 48회) · 위치 정보는 시뮬레이터 정답 좌표")

# ═══════════════════════════ 8 보조 검증 ① 필요한 정확도
s = new(); T = chrome(s, 8, "검사가 믿는 위치가 평균 2.5 mm 틀리면 효과 급감", "성과 3 · 보조 검증 ①")
LW = 5.6
card(s, M, T - 0.06, LW, 2.3, fill="primarysoft", line=None, radius=0.2)
pill(s, M + 0.18, T + 0.08, pw("이 오차의 정의", 14), 0.32, "이 오차의 정의", "primary", "white", 14)
text(s, M + 0.18, T + 0.48, LW - 0.36, 1.75,
     ["**측정 오차** = 검사가 믿는 중심 − 실제 중심",
      "놓은 결과 오차(성공 기준 4.5 mm)·최대 이격과 **다름**",
      "**넣는 법**: 중심 x·y·z에 평균 0·표준편차 σ 무작위 오차",
      "**왜 σ**: 치우침 없이 넣어 평균은 0 → 크기 = 퍼짐 σ"], 15, "inkdeep", spacing=1.12, after=4)
Y = T + 2.38
text(s, M, Y, LW, 0.34, "σ를 평면 중심 거리로 (평균≈1.25σ, 95%≈2.45σ)", 16, "inkdeep", True)
th = table(s, M, Y + 0.4, LW, [["주입 σ (축마다)", "평면 중심 오차 평균", "95%가 이 안"],
                               ["0 mm", "0 mm", "0 mm"],
                               ["2 mm", "**약 2.5 mm**", "약 4.9 mm"],
                               ["4 mm", "약 5.0 mm", "약 9.8 mm"]],
           [1.75, 2.0, 1.85], 15, row_h=0.42, head_h=0.38, align_c=(0, 1, 2), bold_col0=False)
X8 = M + LW + 0.35; W8 = W - M - X8
text(s, X8, T - 0.05, W8, 0.36, "로봇은 틀린 위치로 보정, 채점은 실제 위치로", 16, "inkdeep", True)
line_chart(s, X8, T + 0.32, W8, 3.6, ["σ 0 (오차 없음)", "σ 2 (평균 2.5 mm)", "σ 4 (평균 5.0 mm)"],
           [("Diffusion Policy", (85, 63, 15), "primary"), ("ACT", (60, 30, 15), "orange")], "주입한 측정 오차")
card(s, X8, T + 4.02, W8, 6.45 - T - 4.02, fill="soft", line=None, radius=0.16)
text(s, X8 + 0.15, T + 4.06, W8 - 0.3, 6.45 - T - 4.1, ["평균 2.5 mm 틀리면 ACT **60 → 30%**, Diffusion **85 → 63%**",
                                                         "→ 검사에 쓸 위치는 **평균 2.5 mm보다 충분히 정확**해야 함"], 16, "ink", spacing=1.12, after=3, anchor=MSO_ANCHOR.MIDDLE)
cond(s, M, 6.55, W - 2 * M, "실험 3 · 넓은 배치 · 검사 D · 학습 seed 1000 · 검증 배치 (Diffusion 27회 · ACT 20회, 시간 마감으로 완료분만)")

# ═══════════════════════════ 9 보조 검증 ② 카메라
s = new(); T = chrome(s, 9, "카메라 추정 오차 평균 0.43 mm, 정답 좌표 수준 유지", "성과 3 · 보조 검증 ②")
LW = 6.4
text(s, M, T - 0.05, LW, 0.66, ["**작업대 위 고정 카메라** 1대 (컬러+깊이)", "정답 좌표 없이 영상만으로 벽돌 중심 계산"], 16, "ink", spacing=1.1, after=1)
pimg = A9 + "p08_perception.png"
pw_, ph_ = picture(s, pimg, M, T + 0.66, w=LW)
use(9, "사진", D1 + "근거_rq4/perception_demo.png", "카메라 위치 추정 결과 3컷 원본"); use(9, "사진", pimg, "둥근 모서리판")
text(s, M, T + 0.68 + ph_, LW, 0.3, "노랑 = 카메라 추정 윤곽 · 빨강 = 실제 중심 (채점용)", 14, "charcoal", True)
Y = T + 0.68 + ph_ + 0.42
text(s, M, Y, LW, 0.34, "같은 지표(평면 중심 오차)로 비교", 16, "inkdeep", True)
th = table(s, M, Y + 0.4, LW, [["", "평균", "95%가 이 안"],
                               ["주입 σ 2 mm (효과 급감)", "약 2.5 mm", "약 4.9 mm"],
                               ["**카메라 추정 (실측)**", "**0.43 mm**", "**0.96 mm**"]],
           [2.9, 1.6, 1.9], 15, row_h=0.44, head_h=0.38, align_c=(1, 2), bold_col0=False)
X9 = M + LW + 0.35; W9 = W - M - X9
card(s, X9, T - 0.06, W9, 1.6, fill="primary", line=None, radius=0.24)
text(s, X9 + 0.2, T + 0.04, W9 - 0.4, 0.34, "카메라 추정 평면 중심 오차", 16, "white", True)
text(s, X9 + 0.2, T + 0.4, W9 - 0.4, 0.66, "평균 0.43 mm", 32, "white", True, spacing=1.0)
text(s, X9 + 0.2, T + 1.04, W9 - 0.4, 0.4, "측정 1,963회 · 95%가 0.96 mm 이내 · 최대 1.1 mm", 15, "white")
Y = T + 1.72
text(s, X9, Y, W9, 0.34, "검사에 카메라 추정값을 넣으면", 16, "inkdeep", True)
th = table(s, X9, Y + 0.4, W9, [["검사가 쓴 위치", "검증 40회", "시험 50회"],
                                ["정답 좌표", "38", "48"],
                                ["**카메라 추정**", "**35**", "**45**"]],
           [2.2, 1.35, 1.35], 16, row_h=0.48, head_h=0.4, align_c=(1, 2), bold_col0=False)
yc = Y + 0.4 + th + 0.14
card(s, X9, yc, W9, 6.45 - yc, fill="primarysoft", line=None, radius=0.18)
text(s, X9 + 0.16, yc + 0.06, W9 - 0.32, 6.45 - yc - 0.12, ["**정답 좌표와 2~3회 차이** → 결과 거의 유지", "학습 정책 + 카메라는 평가 중"], 16, "inkdeep", spacing=1.12, after=3, anchor=MSO_ANCHOR.MIDDLE)
cond(s, M, 6.55, W - 2 * M, "넓은 배치 · 실행가능성 필터 · **역기구학 대본 + 검사 3단계** (학습 정책 아님) · 검증 40 · 시험 50 배치")

# ═══════════════════════════ 9 현장 차이 + 한계
s = new()
rect(s, 0, NAV_H + 0.01, W, 0.46, "warning", None)
T = chrome(s, 10, "실제 적용 현장과의 차이와 현재 한계", None)
text(s, M, NAV_H + 0.04, W - 2 * M, 0.4, "교수님 피드백: ‘실제 적용 현장과 차이점 도출’", 16, "inkdeep", True, anchor=MSO_ANCHOR.MIDDLE)
for shp in list(s.shapes):
    if shp.has_text_frame and shp.text_frame.text == "실제 적용 현장과의 차이와 현재 한계":
        shp.top = Inches(NAV_H + 0.55)
T = NAV_H + 1.25
LW11 = 8.6
th = table(s, M, T, LW11, [["구분", "우리 시뮬레이션", "실제 현장", "대응"],
                          ["위치 파악", "정답 좌표 (실험 3)", "센서 추정 · 가림", "**작업대 카메라로 교체 예정**"],
                          ["모르타르", "순응층 · 2 s 뒤 고정", "부착 · 경화 · 편차", "**가정 명시, 벽체서 재검토**"],
                          ["규모·장비", "축소 벽돌 3개 · 소형 팔", "실척 벽체 · 산업용 팔", "**대형 환경 구축 중**"],
                          ["센서", "잡음 없는 힘 센서", "잡음 · 지연", "**잡음 민감도 측정**"],
                          ["자재", "동일 치수 강체", "치수 편차 · 파손", "**치수 편차 별도 실험**"]],
           [1.25, 2.3, 2.15, 2.9], 15, row_h=0.46, head_h=0.38)
X11 = M + LW11 + 0.25; W11 = W - M - X11
site = rounded_img(G + "외부/commons_4.jpg", A8 + "p11_site.png", 40, crop=(0, 250, 1920, 1330))
simi = rounded_img(G + "sim_front_initial.png", A8 + "p11_sim.png", 40, crop=(120, 60, 1180, 660))
ih = (th - 0.06) / 2 - 0.3
sw_, sh_ = picture(s, site, X11, T, w=W11, h=ih)
text(s, X11, T + sh_ + 0.0, W11, 0.3, "실제 현장", 14, "charcoal", True)
sw2, sh2 = picture(s, simi, X11, T + sh_ + 0.33, w=W11, h=ih)
text(s, X11, T + sh_ + 0.33 + sh2, W11, 0.3, "우리 시뮬레이션", 14, "charcoal", True)
use(10, "사진", G + "외부/commons_4.jpg", "현장 사진 원본 (출처: 그림/외부/출처.md)"); use(10, "사진", site, "크롭판")
use(10, "사진", G + "sim_front_initial.png", "시뮬레이션 앞 카메라 원본"); use(10, "사진", simi, "크롭판")
Y = T + th + 0.16
pill(s, M, Y, 1.3, 0.32, "현재 한계", "critical", "white", 14)
Y += 0.42
lims = [("정책 단독 완성률 낮음", "성공 시연만 학습 → 처음 보는 상태에 약함", "정책 밖 검사 3단계 추가"),
        ("학습 정책 + 카메라 결과 없음", "현재 카메라 결과는 역기구학 대본 기준", "평가 중 → 중간발표 2")]
colw12 = [(W - 2 * M - 0.8) * f for f in (0.28, 0.44, 0.28)]
RH = (6.95 - Y - 0.12) / 2
for i, row in enumerate(lims):
    cy = Y + i * (RH + 0.12); xx = M
    for j, val in enumerate(row):
        card(s, xx, cy, colw12[j], RH, fill="soft" if j != 2 else "primarysoft", line=None, radius=0.16)
        text(s, xx + 0.14, cy + 0.04, colw12[j] - 0.28, RH - 0.08, val, 15, "inkdeep", j == 0, anchor=MSO_ANCHOR.MIDDLE, spacing=1.1)
        if j < 2:
            arrow_right(s, xx + colw12[j] + 0.05, cy + RH / 2 - 0.15, 0.3, 0.3)
        xx += colw12[j] + 0.4

# ═══════════════════════════ 10 향후 계획
s = new(); T = chrome(s, 11, "카메라 검측 완료 후 대형 로봇·벽체로 확장", "향후 계획")
GX0 = M + 3.0; GW = 8.65 - GX0
import datetime as dt
d0 = dt.date(2026, 10, 9); d1 = dt.date(2026, 12, 11); span = (d1 - d0).days
X = lambda d: GX0 + GW * ((d - d0).days / span)
for d_ in (dt.date(2026, 10, 20), dt.date(2026, 11, 1), dt.date(2026, 11, 15), dt.date(2026, 12, 1)):
    ln = s.shapes.add_connector(1, Inches(X(d_)), Inches(T + 0.35), Inches(X(d_)), Inches(T + 4.55)); ln.line.color.rgb = RGB["hairsoft"]; ln.line.width = Pt(0.75)
    text(s, X(d_) - 0.4, T, 0.8, 0.3, f"{d_.month}/{d_.day}", 14, "charcoal", True, align=PP_ALIGN.CENTER)
td = dt.date(2026, 10, 11)
ln = s.shapes.add_connector(1, Inches(X(td)), Inches(T + 0.35), Inches(X(td)), Inches(T + 4.55)); ln.line.color.rgb = RGB["inkdeep"]; ln.line.width = Pt(1.5); ln.line.dash_style = 4
pill(s, X(td) - 0.33, T + 0.02, 0.66, 0.28, "오늘", "inkdeep", "white", 12)
rows13 = [("P1", "카메라 검측 + 학습 정책", dt.date(2026, 10, 13), dt.date(2026, 10, 24), "primary"),
          ("P1", "대형 환경 구축", dt.date(2026, 10, 14), dt.date(2026, 11, 3), "primary"),
          ("P2", "시연 수 곡선", dt.date(2026, 10, 24), dt.date(2026, 11, 3), "charcoal"),
          ("P2", "벽체 학습·평가", dt.date(2026, 11, 11), dt.date(2026, 12, 1), "charcoal"),
          ("", "보고서·발표 준비", dt.date(2026, 12, 2), dt.date(2026, 12, 8), "inkdeep")]
ry = T + 0.45
for pr, lab, a_, b_, col in rows13:
    if pr:
        pill(s, M, ry + 0.06, 0.5, 0.32, pr, "primary" if pr == "P1" else "charcoal", "white", 13)
    text(s, M + 0.58, ry - 0.06, 2.4, 0.32, lab, 16, "inkdeep", True)
    text(s, M + 0.58, ry + 0.24, 2.4, 0.28, f"{a_.month}/{a_.day} – {b_.month}/{b_.day}", 14, "charcoal", True)
    rect(s, X(a_), ry + 0.04, X(b_) - X(a_), 0.36, col, None, radius=0.18)
    ry += 0.62
pill(s, M, ry + 0.06, 0.5, 0.32, "P3", "hair", "inkdeep", 13)
text(s, M + 0.58, ry, 5.0, 0.44, "추가 비교: SmolVLA · π0.5", 16, "charcoal", True, anchor=MSO_ANCHOR.MIDDLE)
ry += 0.62
for d_, lab in ((dt.date(2026, 10, 13), "중간 1"), (dt.date(2026, 11, 10), "중간 2"), (dt.date(2026, 12, 8), "최종")):
    rect(s, X(d_) - 0.13, ry + 0.02, 0.26, 0.26, "critical", None, shape=MSO_SHAPE.DIAMOND)
    text(s, X(d_) - 0.6, ry + 0.3, 1.2, 0.32, f"{d_.month}/{d_.day} {lab}", 14, "critical", True, align=PP_ALIGN.CENTER)
text(s, M + 0.58, ry, 2.45, 0.44, "발표", 16, "inkdeep", True, anchor=MSO_ANCHOR.MIDDLE)
X13 = 8.95; W13 = W - M - X13
cimg = A7 + "concept_rounded.png"
cw13, ch13 = picture(s, cimg, X13, T, w=W13)
text(s, X13, T + ch13 + 0.02, W13, 0.3, "대형 환경 콘셉트: UR5e · 실척 벽돌 3단", 14, "charcoal", True, align=PP_ALIGN.CENTER)
use(11, "사진", G + "concept_ur5e_wall.png", "대형 환경 콘셉트 원본"); use(11, "사진", cimg, "크롭·둥근 모서리판")
yy = T + ch13 + 0.4
card(s, X13, yy, W13, 6.95 - yy, fill="primarysoft", line=None, radius=0.18)
text(s, X13 + 0.15, yy + 0.08, W13 - 0.3, 6.95 - yy - 0.15,
     ["**카메라 검측이란**", "정답 좌표 대신 **작업대 카메라 영상**으로 벽돌 위치를 추정해 검사에 사용", "**현재 상태**", "대본 기준 검증 완료", "학습 정책 적용 평가 중"],
     15, "inkdeep", spacing=1.1, after=2)

# ═══════════════════════════ 11 부록: 재현 환경
s = new(); T = chrome(s, 12, "재현용 실험 환경: 시뮬레이터 · 데이터 · 모델 · 평가", "부록 · 재현 정보")
hw5 = (W - 2 * M - 0.3) / 2
t1 = table(s, M, T, hw5, [["항목", "설정"],
                          ["시뮬레이터", "MuJoCo 3.13 · 물리 1 ms · 제어 20 Hz"],
                          ["로봇", "SO-ARM100 모델 · 팔 5관절 + 집게"],
                          ["벽돌", "90×42.6×27 mm · 1,800 kg/m³"],
                          ["모르타르", "4.7 mm 순응층 · 정착 2 s 뒤 고정"],
                          ["시연", "240개 (학습 200 · 검증 40) · 18.3 s"],
                          ["초기 배치", "위치 ±30 mm · 방향 ±60°"]],
           [1.5, 4.1], 16, row_h=0.5, head_h=0.42)
t2 = table(s, M + hw5 + 0.3, T, hw5, [["항목", "설정"],
                                      ["입력 → 출력", "카메라 3대 128² + 관절 6 → 관절 목표 6"],
                                      ["학습", "ACT 40k · Diffusion 60k 갱신 · 배치 32"],
                                      ["반복", "학습 seed 1000 · 1001 · 1002"],
                                      ["평가", "검증 40 · 시험 50 배치 · 1회 90 s"],
                                      ["성공 기준", "위치·높이 4.5 mm · 방향 5° · 기울기 10°"],
                                      ["검사 문턱", "잡기 0.2 rad·0.9 N · 보정 2.5 mm · 재배치 4.5 mm"]],
           [1.5, 4.1], 16, row_h=0.5, head_h=0.42)
Y = T + max(t1, t2) + 0.25
hw_ = (W - 2 * M - 0.3) / 2
for k, (hd, val) in enumerate([("계산 환경", "RTX 5090 · PyTorch 2.11 · LeRobot 0.6.1"), ("코드·원자료", "GitHub 저장소 sim/ · 실험일지.md")]):
    cx = M + k * (hw_ + 0.3)
    card(s, cx, Y, hw_, 0.62, fill="soft", line=None, radius=0.14)
    text(s, cx + 0.16, Y + 0.06, hw_ - 0.3, 0.5, f"**{hd}**  {val}", 16, "ink", anchor=MSO_ANCHOR.MIDDLE)

prs.save(OUT)

# ── 미디어 위치 txt
lines = ["중간발표 1 · v11 슬라이드에 넣은 사진·영상의 GitHub 위치", f"저장소: {REPO}  (브랜치 main)", "",
         "· '저장소 경로'는 저장소 최상위 기준. 'GitHub에서 보기'는 웹 페이지, '바로 받기'는 파일 직접 다운로드 링크.",
         "· 저장소를 통째로 받으려면: GitHub 페이지 → Code → Download ZIP, 또는 git clone 후 같은 경로.", ""]
seen = set()
for page in range(1, N_SLIDES + 1):
    items = [m for m in MEDIA if m[0] == page]
    if not items:
        continue
    lines.append(f"[{page}쪽]")
    for _, kind, path, note in items:
        if (page, path) in seen:
            continue
        seen.add((page, path))
        lines.append(f"  ({kind}) {note}")
        lines.append(f"     저장소 경로: {path}")
        lines.append(f"     GitHub에서 보기: {REPO}/blob/main/{quote(path)}")
        lines.append(f"     바로 받기:      {REPO}/raw/main/{quote(path)}")
    lines.append("")
lines += ["[차트·도식]", "  7·8쪽 그래프와 11쪽 간트는 PowerPoint 안에서 직접 그린 차트·도형이라 별도 파일이 없음 (슬라이드에서 데이터 편집 가능).",
          "  같은 내용의 이미지판: 01_사기설/중간발표1/그림/stages.png, noise.png, fig_gantt_priority.png", "",
          "[생성 스크립트]", "  01_사기설/중간발표1/도구/build_ppt_v11.py (이 슬라이드), 도구/미디어/*.py (영상 클립·렌더·도식)"]
open(TXT, "w", encoding="utf-8").write("\n".join(lines))
print("saved", OUT, len(prs.slides), "slides;", len(MEDIA), "media refs")
