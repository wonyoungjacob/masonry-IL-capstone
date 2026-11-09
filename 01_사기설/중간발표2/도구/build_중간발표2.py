# -*- coding: utf-8 -*-
"""사회기반시스템종합설계 14조 · 중간발표 2 발표 자료 (v3, 2026-11-10 발표). 10장.
v1 = 저장소 밖 '14조 중간발표 2.pptx'(Noto Sans KR). v2: 내용은 그대로 두고 형식만 바꿈. v3: 2쪽 실험 조건 · 용어 풀이, 3쪽 벽 그림, 10쪽 일정 채움:
- 글꼴 Pretendard만, 본문 16~17pt · 아래 줄 13~14pt (작은 글씨 · 연한 회색 없음)
- Meta 디자인 토큰(흰 바탕 · 코발트 · 알약 · 둥근 카드 · 그림자 없음) + 컨설팅 원칙(1장 1메시지 · 개조식 · 카드/표/흐름/빅넘버)
- 쪽 제목은 '~다' 문장형 → '~함' 개조식
- 그림은 v1에서 꺼낸 것(도구/자산/). 도구 함수는 진행보고/도구/build_진행회의_20261103.py와 같음.
실행: python build_중간발표2.py <출력.pptx> <안 씀>"""
import sys, os, re
from urllib.parse import quote
from PIL import Image, ImageDraw
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.dml import MSO_LINE
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION, XL_LABEL_POSITION
from pptx.chart.data import CategoryChartData
from pptx.opc.constants import RELATIONSHIP_TYPE as RT
from pptx.oxml.ns import qn
from lxml import etree

OUT = sys.argv[1]; TXT = sys.argv[2]
ROOT = "C:/Users/user/Desktop/사기설/"
D1 = ROOT + "01_사기설/중간발표1/"
G = D1 + "그림/"; V = D1 + "영상/"; A9 = D1 + "도구/v9_자산/"; A16 = D1 + "도구/v16_자산/"
AS = ROOT + "01_사기설/진행보고/도구/자산/"; os.makedirs(AS, exist_ok=True)
REPO = "https://github.com/wonyoungjacob/masonry-IL-capstone"

C = dict(canvas="FFFFFF", soft="F1F4F7", hair="CBD2D9", hairsoft="E4E9ED", inkdeep="1C2B33", ink="2B3B45", charcoal="465A69",
         primary="0064E0", primarysoft="E5F0FF", success="1E8E3E", successsoft="E6F4EA", critical="D0233A", criticalsoft="FDECEE",
         warning="FFE24D", white="FFFFFF", orange="E37400", orangesoft="FFF3E0", brick="B5523B", brickhalf="CF7A5F")
RGB = {k: RGBColor.from_string(v) for k, v in C.items()}
FONT = "Pretendard"
W, H = 13.333, 7.5
M = 0.5
NAV_H = 0.52
N_SLIDES = 10
SECTIONS = ["요약", "수정", "결과", "원인", "계획"]
ACTIVE = {2: "요약", 3: "수정", 4: "수정", 5: "수정", 6: "결과", 7: "원인", 8: "원인", 9: "계획", 10: "계획"}
MEDIA = []           # (page, kind, repo_path, 설명)
PH = []              # (page, kind, title, desc) 채울 상자

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
KFAC = [0.98]


def _cw(ch, size):
    em = size / 72
    if "\uac00" <= ch <= "\ud7a3" or "\u3130" <= ch <= "\u318f" or ch in "·→←↔↑↓①②③④⑤●○×≥":
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
    rPr.set("lang", "ko-KR"); rPr.set("altLang", "en-US")   # 한국어 규칙(어절 단위)으로 줄바꿈
    latin = rPr.find(qn("a:latin"))
    for tag in ("a:ea", "a:cs"):
        e = rPr.find(qn(tag))
        if e is None:
            e = etree.Element(qn(tag)); latin.addnext(e) if tag == "a:ea" else rPr.find(qn("a:ea")).addnext(e)
        e.set("typeface", FONT)


NB = re.compile(r"(\d) (mm|cm|m|s|Hz|M|%|°)(?![A-Za-z])")


def _runs(par, text_, size, color, bold=False, align=None, spacing=1.2):
    if align is not None:
        par.alignment = align
    par.line_spacing = spacing
    par._p.get_or_add_pPr().set("eaLnBrk", "0")   # 한글 단어 중간에서 줄 바꾸지 않음
    text_ = NB.sub("\\1\u00a0\\2", text_)          # 숫자와 단위 사이 줄바꿈 금지
    for tok in re.split(r"(\*\*.+?\*\*)", text_):
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


def mtext(slide, x, y, w, h, parts, align=None, anchor=MSO_ANCHOR.TOP, spacing=1.15, after=3):
    """줄마다 (글, 크기, 색, 굵게) 다르게."""
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h)); tf = tb.text_frame
    tf.word_wrap = True; tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = Inches(0.04); tf.margin_top = tf.margin_bottom = Inches(0.02)
    for i, (t_, sz, col, b) in enumerate(parts):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph(); p.space_after = Pt(after)
        _runs(p, t_, sz, col, b, align, spacing)
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


def card(slide, x, y, w, h, fill="canvas", line="hairsoft", radius=0.22, line_w=0.75):
    return rect(slide, x, y, w, h, fill, line, radius, line_w)


def pill(slide, x, y, w, h, label, fill="inkdeep", color="white", size=13, line=None, bold=True):
    shp = rect(slide, x, y, w, h, fill, line, radius=h / 2)
    tf = shp.text_frame; tf.margin_left = tf.margin_right = Inches(0.06); tf.margin_top = tf.margin_bottom = Inches(0.0)
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE; tf.word_wrap = False
    _runs(tf.paragraphs[0], label, size, color, bold, PP_ALIGN.CENTER, 1.0)
    return shp


def pw(label, size=13):
    return sum(_cw(c, size) for c in label.replace("**", "")) * 1.06 + 0.36


def chevron(slide, x, y, w, h, lines, fill="soft", color="inkdeep", size=16, first=False, sub_color=None):
    shp = rect(slide, x, y, w, h, fill, None, shape=MSO_SHAPE.PENTAGON if first else MSO_SHAPE.CHEVRON)
    try:
        shp.adjustments[0] = 0.28
    except Exception:
        pass
    tf = shp.text_frame; tf.vertical_anchor = MSO_ANCHOR.MIDDLE; tf.word_wrap = True
    tf.margin_left = Inches(0.3 if not first else 0.12); tf.margin_right = Inches(0.22)
    for i, ln in enumerate(lines.split("\n")):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        _runs(p, ln, size if i == 0 else size - 2, color if i == 0 else (sub_color or color), i == 0, PP_ALIGN.CENTER, 1.05)
    return shp


def arrow_right(slide, x, y, w=0.36, h=0.34, color="charcoal"):
    return rect(slide, x, y, w, h, color, None, shape=MSO_SHAPE.RIGHT_ARROW)


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
        lines = max(sum(est_lines(part, colw[j] - 0.2, size) for part in rows[i][j].split("\n")) for j in range(m))
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
            c = tbl.cell(i, j); c.margin_left = c.margin_right = Inches(0.09); c.margin_top = c.margin_bottom = Inches(0.04)
            c.vertical_anchor = MSO_ANCHOR.MIDDLE
            c.fill.solid(); c.fill.fore_color.rgb = RGB[head_fill if i == 0 else "canvas"]
            _cell_border(c, "CBD2D9" if i in (0, n - 1) else "E4E9ED")
            tf = c.text_frame; tf.word_wrap = True
            al = PP_ALIGN.CENTER if j in align_c else None
            for k, s_ in enumerate(rows[i][j].split("\n")):
                p = tf.paragraphs[0] if k == 0 else tf.add_paragraph()
                if i == 0:
                    _runs(p, s_, size - 1, "white" if head_fill == "inkdeep" else "inkdeep", True, al, 1.1)
                else:
                    _runs(p, s_, size, "ink", bold_col0 and j == 0, al, 1.12)
    return sum(heights)


def bar_chart(slide, x, y, w, h, cats, series, gap=60):
    cd = CategoryChartData(); cd.categories = cats
    for n_, v, _ in series:
        cd.add_series(n_, v)
    ch = slide.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(x), Inches(y), Inches(w), Inches(h), cd).chart
    ch.font.size = Pt(14); ch.font.name = FONT; ch.font.color.rgb = RGB["ink"]
    ch.has_legend = True; ch.legend.position = XL_LEGEND_POSITION.TOP; ch.legend.include_in_layout = False
    ch.legend.font.size = Pt(14); ch.legend.font.bold = True
    va = ch.value_axis; va.minimum_scale = 0; va.maximum_scale = 100; va.major_unit = 25
    va.has_major_gridlines = True; va.major_gridlines.format.line.color.rgb = RGB["hairsoft"]; va.format.line.fill.background()
    va.tick_labels.font.size = Pt(13); va.tick_labels.font.color.rgb = RGB["charcoal"]
    ca = ch.category_axis; ca.tick_labels.font.size = Pt(14); ca.tick_labels.font.bold = True; ca.format.line.color.rgb = RGB["hair"]
    pl = ch.plots[0]; pl.gap_width = gap; pl.overlap = -8; pl.has_data_labels = True
    dl = pl.data_labels; dl.number_format = '0"%"'; dl.number_format_is_linked = False; dl.position = XL_LABEL_POSITION.OUTSIDE_END
    dl.font.size = Pt(15); dl.font.bold = True; dl.font.color.rgb = RGB["inkdeep"]
    for ser, (_, _, col) in zip(pl.series, series):
        ser.format.fill.solid(); ser.format.fill.fore_color.rgb = RGB[col]; ser.format.line.fill.background()
    return ch


def ph(slide, page, x, y, w, h, kind, title, desc, size=15, url=None):
    """채울 사진·영상 자리: 주황 점선 상자 + 넣을 내용."""
    shp = rect(slide, x, y, w, h, "orangesoft", "orange", radius=0.14, line_w=1.75)
    shp.line.dash_style = MSO_LINE.DASH
    lab = f"{kind} 필요"
    pill(slide, x + 0.14, y + 0.13, pw(lab, 13), 0.32, lab, "orange", "white", 13)
    ty = y + 0.52
    mtext(slide, x + 0.16, ty, w - 0.32, h - 0.62, [(f"**{title}**", size, "inkdeep", True), (desc, size - 1, "ink", False)],
          align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, spacing=1.08, after=4)
    PH.append((page, kind, title, desc + (f" ▶ 영상·사진 위치: {url}" if url else "")))


# ── 크롬
def chrome(slide, n, title, section=None):
    text(slide, M, 0.1, 3.3, NAV_H - 0.1, "사회기반시스템종합설계 14조", 13, "inkdeep", True, anchor=MSO_ANCHOR.MIDDLE)
    xx = 3.78
    for s_ in SECTIONS:
        act = ACTIVE.get(n) == s_
        pill(slide, xx, 0.11, 0.74, 0.31, s_, "inkdeep" if act else "canvas", "white" if act else "ink", 12, None if act else "hair", act)
        xx += 0.8
    ln = slide.shapes.add_connector(1, Inches(0), Inches(NAV_H), Inches(W), Inches(NAV_H)); ln.line.color.rgb = RGB["hairsoft"]; ln.line.width = Pt(0.75)
    if section:
        pill(slide, M, NAV_H + 0.16, pw(section, 13), 0.32, section, "primarysoft", "primary", 13)
        ty = NAV_H + 0.52
    else:
        ty = NAV_H + 0.18
    tsize = 28 if est_lines(title, W - 2 * M - 0.1, 28) == 1 else 24
    text(slide, M, ty, W - 2 * M, 0.58, title, tsize, "inkdeep", True, spacing=1.05, anchor=MSO_ANCHOR.MIDDLE)
    pill(slide, W - M - 0.62, H - 0.42, 0.62, 0.32, str(n), "inkdeep", "white", 13)
    return ty + 0.68


def new():
    return prs.slides.add_slide(BLANK)


# ═══════════════════════════ 이번 자료 공통 도구
sys.stdout.reconfigure(encoding="utf-8")
CW = W - 2 * M
DATE_STR = "2026.11.10"
SRC1020 = ROOT + "01_사기설/중간발표2/14조_진행회의_20261020 (2).pptx"
V29 = ROOT + "01_사기설/근거_우분투_wall3_재학습_v2/확인영상_20261029/"
WARN = []


def need_h(lines, w, size, spacing=1.05, after=5):
    n = sum(est_lines(l, w - 0.1, size) for l in lines)
    return n * size / 72 * 1.2 * spacing + len(lines) * after / 72 + 0.06


def chk(tag, lines, w, h, size, spacing=1.05, after=5):
    lines = [lines] if isinstance(lines, str) else lines
    nh = need_h(lines, w, size, spacing, after)
    if nh > h + 0.01:
        WARN.append(f"{tag}: 필요 {nh:.2f} > 자리 {h:.2f}")


def badge(slide, label, fill="orange", color="white"):
    w_ = pw(label, 13)
    pill(slide, W - M - w_, NAV_H + 0.16, w_, 0.32, label, fill, color, 13)


def hpill(slide, x, y, label, fill="inkdeep", color="white", size=14, h=0.34):
    w_ = pw(label, size)
    pill(slide, x, y, w_, h, label, fill, color, size)
    return w_


def strip(slide, y, h, lines, fill="soft", line=None, color="inkdeep", size=16, label=None, label_fill="inkdeep", x=None, w=None, tag="strip"):
    x = M if x is None else x
    w = CW if w is None else w
    card(slide, x, y, w, h, fill=fill, line=line, radius=0.14, line_w=1.25 if line else 0.75)
    x0 = x + 0.2
    if label:
        lw = pw(label, 14)
        pill(slide, x0, y + h / 2 - 0.17, lw, 0.34, label, label_fill, "white", 14)
        x0 += lw + 0.18
    lines = [lines] if isinstance(lines, str) else lines
    chk(tag, lines, x + w - x0 - 0.18, h, size, after=2)
    text(slide, x0, y, x + w - x0 - 0.18, h, lines, size, color, anchor=MSO_ANCHOR.MIDDLE, spacing=1.05, after=2)


def info_card(slide, x, y, w, h, label, lines, fill="canvas", line="hair", label_fill="inkdeep", size=16, color="inkdeep", tag="card"):
    card(slide, x, y, w, h, fill=fill, line=line, radius=0.16, line_w=1.25 if line in ("orange", "critical") else 0.75)
    hpill(slide, x + 0.16, y + 0.14, label, label_fill, "white", 14)
    chk(tag, lines, w - 0.36, h - 0.62, size)
    text(slide, x + 0.18, y + 0.56, w - 0.36, h - 0.6, lines, size, color, spacing=1.05, after=5)


def flow_cards(slide, y, h, steps, gap=0.36):
    n = len(steps)
    w_ = (CW - (n - 1) * gap) / n
    for k, (lab, main, sub, fill, subcol) in enumerate(steps):
        x = M + k * (w_ + gap)
        dark = fill in ("primary", "inkdeep")
        card(slide, x, y, w_, h, fill=fill, line=None if fill != "canvas" else "hair", radius=0.16)
        hpill(slide, x + 0.14, y + 0.12, lab, "white" if dark else "inkdeep", "primary" if dark else "white", 14, 0.32)
        chk(f"flow {lab}", [main], w_ - 0.28, h - 0.56 - 0.5, 16)
        mtext(slide, x + 0.14, y + 0.5, w_ - 0.28, h - 0.54,
              [(f"**{main}**", 16, "white" if dark else "inkdeep", True), (sub, 14, "white" if dark else subcol, False)], spacing=1.05, after=3)
        if k < n - 1:
            arrow_right(slide, x + w_ + 0.06, y + h / 2 - 0.13, gap - 0.12, 0.26)


def big_card(slide, x, y, w, h, label, big, sub, fill="soft", big_col="inkdeep", lab_col="charcoal", sub_col="ink", big_size=34, line=None):
    card(slide, x, y, w, h, fill=fill, line=line, radius=0.16, line_w=1.25)
    mtext(slide, x + 0.16, y + 0.04, w - 0.32, h - 0.08, [(label, 14, lab_col, True), (big, big_size, big_col, True), (sub, 14, sub_col, False)],
          anchor=MSO_ANCHOR.MIDDLE, spacing=1.0, after=2)


def fill_chart(slide, x, y, w, h, cats, series):
    cd = CategoryChartData(); cd.categories = cats
    for n_, v, _ in series:
        cd.add_series(n_, v)
    ch = slide.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(x), Inches(y), Inches(w), Inches(h), cd).chart
    ch.font.size = Pt(14); ch.font.name = FONT; ch.font.color.rgb = RGB["ink"]
    ch.has_legend = True; ch.legend.position = XL_LEGEND_POSITION.TOP; ch.legend.include_in_layout = False
    ch.legend.font.size = Pt(14); ch.legend.font.bold = True
    va = ch.value_axis; va.minimum_scale = 0; va.maximum_scale = 110; va.major_unit = 25
    va.has_major_gridlines = True; va.major_gridlines.format.line.color.rgb = RGB["hairsoft"]; va.format.line.fill.background()
    va.tick_labels.font.size = Pt(14); va.tick_labels.font.color.rgb = RGB["charcoal"]
    va.tick_labels.number_format = '0"%"'; va.tick_labels.number_format_is_linked = False
    ca = ch.category_axis; ca.tick_labels.font.size = Pt(14); ca.tick_labels.font.bold = True; ca.format.line.color.rgb = RGB["hair"]
    pl = ch.plots[0]; pl.gap_width = 55; pl.overlap = -5
    for ser, (_, _, col) in zip(pl.series, series):
        ser.format.fill.solid(); ser.format.fill.fore_color.rgb = RGB[col]; ser.format.line.fill.background()
    ser0 = pl.series[0]
    for i, v in enumerate(series[0][1]):
        dl = ser0.points[i].data_label
        dl.position = XL_LABEL_POSITION.OUTSIDE_END
        tf = dl.text_frame; tf.text = str(v)
        r = tf.paragraphs[0].runs[0]; r.font.size = Pt(14); r.font.bold = True; r.font.color.rgb = RGB["primary"]; r.font.name = FONT
    return ch


def page_no(slide, n):
    pill(slide, W - M - 0.62, H - 0.42, 0.62, 0.32, str(n), "inkdeep", "white", 13)




# ═══════════════════════════ 중간발표 2 v2 공통
AS2 = ROOT + "01_사기설/중간발표2/도구/자산/"
WARN = []


def need_h(lines, w, size, spacing=1.05, after=5):
    n = sum(est_lines(l, w - 0.1, size) for l in lines)
    return n * size / 72 * 1.2 * spacing + len(lines) * after / 72 + 0.06


def chk(tag, lines, w, h, size, spacing=1.05, after=5):
    lines = [lines] if isinstance(lines, str) else lines
    nh = need_h(lines, w, size, spacing, after)
    if nh > h + 0.01:
        WARN.append(f"{tag}: 필요 {nh:.2f} > 자리 {h:.2f}")


def badge(slide, label, fill="orange", color="white"):
    w_ = pw(label, 14)
    pill(slide, W - M - w_, NAV_H + 0.16, w_, 0.32, label, fill, color, 14)


def hpill(slide, x, y, label, fill="inkdeep", color="white", size=14, h=0.34):
    w_ = pw(label, size)
    pill(slide, x, y, w_, h, label, fill, color, size)
    return w_


def strip(slide, y, h, lines, fill="soft", line=None, color="inkdeep", size=16, label=None, label_fill="inkdeep", x=None, w=None, tag="strip"):
    x = M if x is None else x
    w = CW if w is None else w
    card(slide, x, y, w, h, fill=fill, line=line, radius=0.14)
    x0 = x + 0.2
    if label:
        lw = pw(label, 14)
        pill(slide, x0, y + h / 2 - 0.17, lw, 0.34, label, label_fill, "white", 14)
        x0 += lw + 0.18
    lines = [lines] if isinstance(lines, str) else lines
    chk(tag, lines, x + w - x0 - 0.18, h, size, after=2)
    text(slide, x0, y, x + w - x0 - 0.18, h, lines, size, color, anchor=MSO_ANCHOR.MIDDLE, spacing=1.05, after=2)


def info_card(slide, x, y, w, h, label, lines, fill="canvas", line="hair", label_fill="inkdeep", size=16, color="inkdeep", tag="card", after=6):
    card(slide, x, y, w, h, fill=fill, line=line, radius=0.16)
    hpill(slide, x + 0.16, y + 0.14, label, label_fill, "white", 14)
    chk(tag, lines, w - 0.36, h - 0.62, size, after=after)
    text(slide, x + 0.18, y + 0.58, w - 0.36, h - 0.62, lines, size, color, spacing=1.05, after=after)


def flow_cards(slide, y, h, steps, gap=0.36):
    n = len(steps)
    w_ = (CW - (n - 1) * gap) / n
    for k, (lab, main, sub, fill, subcol) in enumerate(steps):
        x = M + k * (w_ + gap)
        dark = fill in ("primary", "inkdeep")
        card(slide, x, y, w_, h, fill=fill, line=None if fill != "canvas" else "hair", radius=0.16)
        hpill(slide, x + 0.14, y + 0.12, lab, "white" if dark else "inkdeep", "primary" if dark else "white", 14, 0.32)
        chk(f"flow {lab}", [main, sub], w_ - 0.28, h - 0.54, 16)
        mtext(slide, x + 0.14, y + 0.52, w_ - 0.28, h - 0.56,
              [(f"**{main}**", 17, "white" if dark else "inkdeep", True), (sub, 15, "white" if dark else subcol, False)], spacing=1.05, after=4)
        if k < n - 1:
            arrow_right(slide, x + w_ + 0.06, y + h / 2 - 0.13, gap - 0.12, 0.26)


def big_card(slide, x, y, w, h, label, big, sub, fill="soft", big_col="inkdeep", lab_col="charcoal", sub_col="ink", big_size=34, line=None):
    card(slide, x, y, w, h, fill=fill, line=line, radius=0.16)
    mtext(slide, x + 0.18, y + 0.04, w - 0.36, h - 0.08, [(label, 15, lab_col, True), (big, big_size, big_col, True), (sub, 15, sub_col, False)],
          anchor=MSO_ANCHOR.MIDDLE, spacing=1.0, after=3)


def fill_chart(slide, x, y, w, h, cats, series):
    cd = CategoryChartData(); cd.categories = cats
    for n_, v, _ in series:
        cd.add_series(n_, v)
    ch = slide.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(x), Inches(y), Inches(w), Inches(h), cd).chart
    ch.font.size = Pt(14); ch.font.name = FONT; ch.font.color.rgb = RGB["ink"]
    ch.has_legend = True; ch.legend.position = XL_LEGEND_POSITION.TOP; ch.legend.include_in_layout = False
    ch.legend.font.size = Pt(14); ch.legend.font.bold = True
    va = ch.value_axis; va.minimum_scale = 0; va.maximum_scale = 110; va.major_unit = 25
    va.has_major_gridlines = True; va.major_gridlines.format.line.color.rgb = RGB["hairsoft"]; va.format.line.fill.background()
    va.tick_labels.font.size = Pt(14); va.tick_labels.font.color.rgb = RGB["charcoal"]
    va.tick_labels.number_format = '0"%"'; va.tick_labels.number_format_is_linked = False
    ca = ch.category_axis; ca.tick_labels.font.size = Pt(14); ca.tick_labels.font.bold = True; ca.format.line.color.rgb = RGB["hair"]
    pl = ch.plots[0]; pl.gap_width = 55; pl.overlap = -5
    for ser, (_, _, col) in zip(pl.series, series):
        ser.format.fill.solid(); ser.format.fill.fore_color.rgb = RGB[col]; ser.format.line.fill.background()
    ser0 = pl.series[0]
    for i, v in enumerate(series[0][1]):
        dl = ser0.points[i].data_label
        dl.position = XL_LABEL_POSITION.OUTSIDE_END
        tf = dl.text_frame; tf.text = str(v)
        r = tf.paragraphs[0].runs[0]; r.font.size = Pt(14); r.font.bold = True; r.font.color.rgb = RGB["primary"]; r.font.name = FONT
    return ch


def page_no(slide, n):
    pill(slide, W - M - 0.62, H - 0.42, 0.62, 0.32, str(n), "inkdeep", "white", 13)


def note(slide, line, y=6.98):
    """쪽 아래 출처 · 조건 (원본의 아래 줄을 그대로)."""
    sz = 14 if est_lines(line, CW - 0.95, 14) == 1 else 13
    text(slide, M, y, CW - 0.85, 7.46 - y, line, sz, "charcoal", spacing=1.0, after=0, anchor=MSO_ANCHOR.MIDDLE)


def section_label(slide, x, y, w, label):
    text(slide, x, y, w, 0.34, label, 17, "inkdeep", True, anchor=MSO_ANCHOR.MIDDLE)



def rows_card(slide, x, y, w, h, label, items, label_fill="inkdeep", size=17, inline=False, pill_w=None):
    """라벨 아래에 항목을 행으로 고르게 나눔. items = [(작은 알약, 알약 색, 본문)]."""
    card(slide, x, y, w, h, fill="canvas", line="hair", radius=0.16)
    hpill(slide, x + 0.16, y + 0.14, label, label_fill, "white", 14)
    top = y + 0.62; rh = (y + h - 0.12 - top) / len(items)
    for k, (tg, tf_, body) in enumerate(items):
        ry = top + k * rh
        if k:
            rect(slide, x + 0.2, ry - 0.005, w - 0.4, 0.012, "hair", None)
        if inline:
            pwid = pill_w or pw(tg, 15)
            pill(slide, x + 0.2, ry + rh / 2 - 0.18, pwid, 0.36, tg, tf_, "white", 15)
            chk(f"rows {tg}", [body], w - pwid - 0.55, rh, size, after=0)
            text(slide, x + 0.2 + pwid + 0.15, ry, w - pwid - 0.55, rh, body, size, "inkdeep", anchor=MSO_ANCHOR.MIDDLE, spacing=1.05, after=0)
        else:
            nh = need_h([body], w - 0.4, size, after=0)
            blk = 0.4 + nh; by_ = ry + (rh - blk) / 2
            hpill(slide, x + 0.2, by_, tg, tf_, "white", 14, 0.32)
            chk(f"rows {tg}", [body], w - 0.4, rh - 0.4, size, after=0)
            text(slide, x + 0.2, by_ + 0.4, w - 0.4, nh + 0.05, body, size, "inkdeep", spacing=1.05, after=0)


# ═══════════════════════════ 1 표지
s = new()
pill(s, 0.9, 0.95, 1.45, 0.4, "중간발표 2", "inkdeep", "white", 15)
text(s, 0.9, 1.55, 6.3, 2.5, ["모방학습 조적 로봇의", "정책 밖 검측:", "실척 벽체 확장과", "실패 원인 분석"], 36, "inkdeep", True, spacing=1.05, after=0)
text(s, 0.9, 4.1, 6.3, 0.42, "MuJoCo 시뮬레이션 · UR10e · 표준 벽돌 3단 16장", 18, "ink")
ln = s.shapes.add_connector(1, Inches(0.9), Inches(4.7), Inches(6.9), Inches(4.7)); ln.line.color.rgb = RGB["hair"]; ln.line.width = Pt(1)
text(s, 0.9, 4.88, 6.3, 0.42, "**사회기반시스템종합설계 14조**", 20, "inkdeep")
text(s, 0.9, 5.38, 6.3, 0.4, "정원영 · 임수현 · 정성용 · 강건", 18, "ink")
text(s, 0.9, 5.84, 6.3, 0.38, "지도교수: 김홍조 교수님", 17, "ink")
text(s, 0.9, 6.3, 6.3, 0.38, DATE_STR, 17, "charcoal", True)
iw, ih = picture(s, AS2 + "p01_환경.png", 7.35, 1.35, w=5.45)
text(s, 7.35, 1.35 + ih + 0.1, 5.45, 0.34, "MuJoCo · UR10e · 표준 벽돌 3단 16장", 15, "charcoal", align=PP_ALIGN.CENTER)
page_no(s, 1)

# ═══════════════════════════ 2 지금까지의 내용
s = new(); T = chrome(s, 2, "성공 시연만 배운 정책은 실패를 모름 → 검측을 정책 밖에 둠", "지금까지의 내용 · 중간발표 1")
y = T - 0.04; cw = (CW - 2 * 0.2) / 3; chh = 2.75
rows_card(s, M, y, cw, chh, "문제 · 모방학습의 딜레마",
          [("성공 시연만 학습", "critical", "**실패를 알아채지 못함** · 정책 단독 Diffusion 35 % · ACT 0 %"),
           ("바로잡는 시연도 섞음", "critical", "**정밀도 손실** · 완성률 90 % → 2 %")], size=15)
rows_card(s, M + cw + 0.2, y, cw, chh, "해법 · 정책 밖 검측 3단계",
          [("G1", "primary", "**잡기 확인**: 하중 · 집게 각도"), ("G2", "primary", "**놓기 전 보정**: 벽돌 위치"),
           ("G3", "primary", "**놓은 뒤 재배치**: 벽돌당 1회")], label_fill="primary", inline=True, pill_w=0.62)
x3 = M + 2 * (cw + 0.2)
card(s, x3, y, cw, chh, fill="soft", line=None, radius=0.16)
hpill(s, x3 + 0.16, y + 0.14, "결과 · 소형 실험 (블록 3개)", "success", "white", 14)
mtext(s, x3 + 0.2, y + 0.56, cw - 0.4, chh - 0.62,
      [("Diffusion 완성률 · 단독 → + 검측", 16, "ink", True), ("35 % → 75 %", 30, "primary", True),
       ("ACT 완성률 · 단독 → + 검측", 16, "ink", True), ("0 % → 54 %", 30, "primary", True),
       ("카메라 위치 추정 오차 평균 0.43 mm", 15, "inkdeep", False)], spacing=1.0, after=3)
ey = y + chh + 0.12
card(s, M, ey, CW, 1.05, fill="soft", line=None, radius=0.14)
text(s, M + 0.2, ey, CW - 0.4, 1.05,
     ["**실험 조건 (소형)**: SO-ARM100 · 블록 3개 2+1 적층 · 대본 시연으로 학습 · 학습 seed 1000 · 검측 위치 = 정답 좌표",
      "**35 · 0 · 75 · 54 %** = 실험 3 넓은 배치 (±30 mm · ±60°) · 시험 배치 Diffusion 40 · ACT 48개",
      "**90 % → 2 %** = 실험 1 좁은 배치 (±5 mm · ±10°) · Diffusion 100회",
      "**바로잡는 시연** = 벽돌을 일부러 밀어 놓고 다시 맞추는 동작을 담은 시연"],
     13, "inkdeep", anchor=MSO_ANCHOR.MIDDLE, spacing=1.0, after=1)
ty = ey + 1.05 + 0.04
section_label(s, M, ty, 4, "중간발표 1 이후")
steps = [("10/20", "대형 환경"), ("10/22–26", "데이터 재수집"), ("10/26", "예비 평가"), ("10/28–29", "원인 분석"), ("11/02", "지표 개정"), ("11/03", "제안 3개")]
sw = CW / 6
for k, (d, t_) in enumerate(steps):
    last = k == len(steps) - 1
    chevron(s, M + k * sw, ty + 0.38, sw + 0.12, 0.84, f"{d}\n{t_}", fill="primary" if last else "soft", color="white" if last else "inkdeep",
            size=17, first=(k == 0))
note(s, "14조 · 중간발표 2")
page_no(s, 2)

# ═══════════════════════════ 3 수정된 점 ① 실험 규모
s = new(); T = chrome(s, 3, "블록 3개에서 표준 벽돌 16장으로 확장", "수정된 점 ① · 실험 규모")
y = T - 0.04; LW = 4.75; iw3 = (LW - 0.2) / 2
for k, (f_, cap) in enumerate([("p03_소형_블록3개.png", "중간발표 1 · 블록 3개"), ("p03_대형_벽돌16장.png", "현재 · 벽돌 16장")]):
    picture(s, AS2 + f_, M + k * (iw3 + 0.2), y, w=iw3, h=iw3)
    text(s, M + k * (iw3 + 0.2), y + iw3 + 0.06, iw3, 0.34, cap, 15, "inkdeep", True, align=PP_ALIGN.CENTER)
sy = y + iw3 + 0.5
rows = [["항목", "중간발표 1", "현재"],
        ["로봇", "SO-ARM 소형 팔", "**UR10e** · 받침대 0.6 m"],
        ["작업", "블록 3개 · 2+1 적층", "**벽돌 16장 · 3단 일자 벽**"],
        ["벽돌", "90×42.6×27 mm 축소", "**190×90×57 mm** · 1.95 kg"],
        ["시연", "대본 200개", "**합격 벽 1,000개**"],
        ["검측 위치", "정답 좌표", "**작업대 카메라**"],
        ["실험 설계", "검측 누적 추가", "**2×2×2 요인 설계 (8조건)**"],
        ["반복", "seed 1", "**seed 3**"]]
RX = M + LW + 0.3; RW = W - M - RX
section_label(s, RX, y - 0.02, RW, "3단 일자 벽 · L 990 × H 191 mm · 줄눈 10 mm")
dw = 1.0 / 0.191 * 0.990; dx0 = RX + (RW - dw) / 2; sc = dw / 0.990; dbot = y + 0.42 + 1.0
for c_, xs in enumerate([[0.19] * 5, [0.09] + [0.19] * 4 + [0.09], [0.19] * 5]):
    xx = dx0; yy_ = dbot - (c_ + 1) * 0.057 * sc - c_ * 0.010 * sc
    for L_ in xs:
        rect(s, xx, yy_, L_ * sc, 0.057 * sc, "brickhalf" if L_ < 0.1 else "brick", None)
        xx += (L_ + 0.010) * sc
rect(s, dx0 - 0.12, dbot + 0.01, dw + 0.24, 0.025, "inkdeep", None)
th3 = table(s, RX, dbot + 0.18, RW, rows, [1.6, 2.6, 3.1], size=16, row_h=0.4, head_h=0.4)
th3 += dbot + 0.18 - y
info_card(s, M, sy, LW, y + th3 - sy, "왜 실척인가", ["**축소 모형이 아닌 실척 벽돌**로 쌓아야 시방 기준 (KCS 41 34 00)으로 평가하는 의미가 생김"],
          size=18, tag="p3 why")
note(s, "14조 · 중간발표 2 · 벽돌 규격 KS L 4201")
page_no(s, 3)

# ═══════════════════════════ 4 수정된 점 ② 시연 데이터
s = new(); T = chrome(s, 4, "시연이 두 갈래로 갈리면 ACT는 벽돌을 못 집음", "수정된 점 ② · 시연 데이터")
y = T - 0.04
flow_cards(s, y, 1.7,
           [("① 증상", "셋째 벽돌부터 못 집음", "100벽 평균 약 2장", "criticalsoft", "critical"),
            ("② 원인", "손목 방향이 두 갈래", "벽돌은 180° 대칭 · 505 : 495벽", "canvas", "charcoal"),
            ("③ 해결", "손목 방향을 하나로 고정", "1,000벽 재수집 (1,000 : 0) → 재학습", "canvas", "charcoal"),
            ("④ 결과", "셋째 벽돌 집기 해결", "ACT 0 → 20 / 20", "primary", "white")])
by = y + 1.7 + 0.25; LW = 6.0
rows_card(s, M, by, LW, 6.85 - by, "왜 ACT만 실패했나",
          [("ACT · 회귀형", "inkdeep", "두 갈래 시연의 **평균을 냄** → 어느 시연과도 다른 동작 (집게를 비스듬히 닫음)"),
           ("Diffusion · 생성형", "primary", "두 갈래 중 **하나를 골라 따라감**")])
RX = M + LW + 0.3; RW = W - M - RX
section_label(s, RX, by, RW, "넘기기 시험 · 셋째 벽돌 집은 벽 (20벽 중)")
rows = [["데이터", "손목 방향", "ACT", "Diffusion"],
        ["v1 처음 수집", "505 : 495", "**0 / 20**", "13 / 20"],
        ["v2 재수집", "1,000 : 0", "**20 / 20**", "19 / 20"]]
th = table(s, RX, by + 0.42, RW, rows, [1.9, 1.6, 1.2, 1.35], size=17, row_h=0.52, head_h=0.44, align_c=(1, 2, 3))
ny = by + 0.42 + th + 0.15
strip(s, ny, 6.85 - ny, ["**넘기기 시험**: 앞 2장은 대본, 셋째 벽돌만 정책 · 검측 없음 · 본 벽 10 + 안 본 벽 10", "**이후 결과는 모두 v2 기준**"],
      fill="soft", x=RX, w=RW, size=15, tag="p4 note")
note(s, "14조 · 중간발표 2 · Chi et al., 2023 (Diffusion Policy) · Bishop, 1994")
page_no(s, 4)

# ═══════════════════════════ 5 수정된 점 ③ 평가 기준
s = new(); T = chrome(s, 5, "허용기준 2 mm → 6 mm, 효과는 mm 오차로 비교", "수정된 점 ③ · 평가 기준")
y = T - 0.04; LW = 5.9; bw = (LW - 0.6) / 2; bh = 2.0
big_card(s, M, y, bw, bh, "이전 · ②③④ 허용오차", "2 mm", "벽 길이에 비례해 줄인 팀 설정값 · 표준에 없음", "soft", "inkdeep", "charcoal", "ink", 44)
arrow_right(s, M + bw + 0.12, y + bh / 2 - 0.18, 0.36, 0.36)
big_card(s, M + bw + 0.6, y, bw, bh, "개정 · 11/02", "6 mm", "시방 값 그대로 · 짧은 벽도 어느 구간이든 6 mm 이내", "primary", "white", "white", "white", 44)
gy = y + bh + 0.22
rows_card(s, M, gy, LW, 6.85 - gy, "근거",
          [("시방 “3 m당 6 mm”", "inkdeep", "어느 구간도 6 mm를 넘지 말라는 뜻 → **길이로 줄일 근거가 없음**"),
           ("다만", "orange", "6 mm는 느슨함 (약 1.8° 기울기까지 허용)")])
RX = M + LW + 0.35; RW = W - M - RX
section_label(s, RX, y, RW, "그래서 평가 방식도 바꿈")
rows = [["항목", "이전", "현재"],
        ["시방 합격", "주 판정", "**보조 판정**"],
        ["주 지표", "시방 합격률", "**벽 완성률 + 항목별 오차 (mm)**"],
        ["민감도 분석", "없음", "**허용오차 1~6 mm로 다시 채점**"],
        ["오차 나눠 보기", "없음", "**같은 쪽으로 쏠림 · 무작위** → 긴 벽 예측"]]
table(s, RX, y + 0.44, RW, rows, [1.75, 1.45, 3.3], size=17, row_h=(6.85 - y - 0.44 - 0.46) / 4, head_h=0.46)
note(s, "14조 · 중간발표 2 · KCS 41 34 00 조적공사 (2021)")
page_no(s, 5)

# ═══════════════════════════ 6 실험 결과 100벽
s = new(); T = chrome(s, 6, "검측을 켜도 벽 완성 0 / 100, 뒤로 갈수록 채움 하락", "실험 결과 · 100벽 (10/26)")
badge(s, "예비 평가 · 결과 아님")
y = T - 0.04; LW = 3.6; bh = (6.85 - y - 0.3) / 3
bigs = [("ACT · 검측 없음", "2.0장", "모든 벽이 정확히 2장에서 멈춤", "soft", "inkdeep", "charcoal", "ink"),
        ("ACT + G1 · G2 · G3", "5.4장", "셋째 자리 채움 97 % · 최대 11장", "primary", "white", "white", "white"),
        ("Diffusion + G1 · G2 · G3", "1.1장", "둘째 벽돌부터 막힘", "soft", "inkdeep", "charcoal", "ink")]
for k, b in enumerate(bigs):
    big_card(s, M, y + k * (bh + 0.15), LW, bh, *b, big_size=32)
RX = M + LW + 0.3; RW = W - M - RX
section_label(s, RX, y, RW, "벽돌 자리별 채움 비율 (%) · 1~8번째")
fill_chart(s, RX, y + 0.38, RW, 6.85 - y - 0.38 - 0.5, [f"{i}번째" for i in range(1, 9)],
           [("ACT + 검측", [100, 99, 97, 88, 78, 40, 16, 8], "primary"),
            ("ACT 검측 없음", [100, 100, 0, 0, 0, 0, 0, 0], "inkdeep"),
            ("Diffusion + 검측", [87, 10, 7, 1, 2, 0, 0, 1], "hair")])
text(s, RX, 6.85 - 0.44, RW, 0.4, "**ACT + 검측**: 100 · 99 · 97 · 88 · 78 · 40 · 16 · 8 %", 16, "inkdeep", align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
note(s, "조건: 시작값 700300~700399 · seed 1000 · 벽돌당 17 s · 채움 = 자리 45 mm · 28.5 mm · 45° 이내 (정밀도 판정 아님)")
page_no(s, 6)

# ═══════════════════════════ 7 실패 원인 ① 차례
s = new(); T = chrome(s, 7, "정책이 “몇 번째 차례인지” 모르고 앞질러 감", "실패 원인 ① · 원인 추적 (10/28) · 영상 확인 (10/29)")
y = T - 0.04; LW = 5.55
card(s, M, y, LW, 0.95, fill="inkdeep", line=None, radius=0.16)
text(s, M + 0.2, y, 2.0, 0.95, "52 / 87", 36, "white", True, anchor=MSO_ANCHOR.MIDDLE)
text(s, M + 2.25, y, LW - 2.4, 0.95, "처음 실패 87건 중 **52건이 차례 어긋남**과 연결", 17, "white", anchor=MSO_ANCHOR.MIDDLE, spacing=1.05)
sts = [("1 · 앞질러 감", "2번째 차례에 정책이 **3번째 벽돌까지 놓음** (81 / 100벽)", "critical"),
       ("2 · 기준이 어긋남", "목표 입력과 검측은 여전히 “2번 차례” 기준 → **손에 든 벽돌과 맞지 않음**", "critical"),
       ("3 · 회복 안 됨", "처음 실패 뒤 **99 %는 제 벽돌로 손이 가지 않음**", "critical")]
sy = y + 0.95 + 0.15; sh_ = (6.85 - sy - 2 * 0.14) / 3
for k, (lab, body, col) in enumerate(sts):
    yy = sy + k * (sh_ + 0.14)
    info_card(s, M, yy, LW, sh_, lab, [body], tag=f"p7 {lab}", after=0)
RX = M + LW + 0.3; RW = W - M - RX
iw, ih = picture(s, AS2 + "p07_실패장면.png", RX, y, w=RW)
rows = [["처음 실패한 벽돌의 원인", "건수"],
        ["검측이 다른 차례 자리 기준으로 옮겨 떨어뜨림", "**26**"],
        ["놓은 벽돌이 이웃 벽돌에 걸침", "**18**"],
        ["반장 벽돌을 자리 뒤쪽에 얹어 넘어짐", "**13**"],
        ["엉뚱한 곳에 놓음 · 떨어뜨림", "12"],
        ["집기 실패", "18"]]
table(s, RX, y + ih + 0.15, RW, rows, [5.3, 1.0], size=16, row_h=0.4, head_h=0.4, align_c=(1,), bold_col0=False)
note(s, "진단 자료 · 결과 아님 · 정책 입력은 카메라 · 관절 · 목표뿐, “몇 번째 차례”를 세는 장치는 없음")
page_no(s, 7)

# ═══════════════════════════ 8 실패 원인 ② 기존 연구와의 차이
s = new(); T = chrome(s, 8, "기존 결합 방식은 차례 · 쌓임 · 합격을 다루지 못함", "실패 원인 ② · 기존 연구와의 차이")
y = T - 0.04
strip(s, y, 0.78, "**동작 보정 · 위험 동작 막기 · 모드 바꾸기** → 모두 “지금 동작”만 고침 · 우리 G1~G3도 이 방식 (응용 수준)",
      fill="soft", label="기존 연구", tag="p8 old")
rows = [["가정", "기존 방법이 믿는 것", "조적에서는", "우리 데이터 근거"],
        ["차례", "로봇은 몇 번째 작업인지 안다", "**모른다** · 순서를 앞질러 감", "쥔 벽돌 650번 중 411번이 다른 차례 · **확인**"],
        ["쌓임", "작업은 하나하나 따로다", "**아래 벽돌이 위의 받침** → 오차가 위로 이어짐", "2단 진입 약 40벽 기록 재분석 · **확인 예정**"],
        ["합격", "틀리면 되돌리고, 기준은 설계자가 정함", "**놓으면 못 되돌림** · 기준은 시방", "걸침 18건 · 처음 실패 뒤 99 % 회복 못 함 · **일부 확인**"]]
th = table(s, M, y + 0.78 + 0.22, CW, rows, [1.1, 3.3, 3.7, 4.2], size=17, row_h=0.82, head_h=0.46, align_c=(0,))
cy = y + 0.78 + 0.22 + th + 0.25
strip(s, cy, 6.85 - cy, "동작만 고치는 방법으로는 부족 → **차례 · 쌓임 · 합격을 다루는 규칙이 필요**", fill="inkdeep", color="white", size=19, tag="p8 take")
note(s, "결합 방식 문헌 47편 정리 · Johannink 2019 · Ames 2019 · Seto 1998 (Simplex) · Agia 2024 (Sentinel) · Zheng 2026 (Rewind-IL)")
page_no(s, 8)

# ═══════════════════════════ 9 향후 계획 ① 제안
s = new(); T = chrome(s, 9, "깨진 가정마다 규칙 하나: 정책은 그대로, 규칙은 정책 밖에 둠", "향후 계획 ① · 제안")
badge(s, "가설 · 효과 미측정")
y = T - 0.04; cw = (CW - 2 * 0.22) / 3; chh = 6.85 - y
props = [("차례 → VS³", "① 차례 맞추기", "카메라로 확인한 벽 상태로 다음 목표와 끝 시점을 정하고, 확인 뒤 철수 자세로",
          "정책이 학습 때와 같은 상황에서만 일함 (목표가 맞으면 20 / 20)", "어긋남률 · 완성률"),
         ("쌓임 → VPRA", "② 쌓임 막기", "가로 위치는 도면 기준, 높이는 줄눈 두께로 조금씩 되돌림",
          "되돌림이 있으면 단이 늘어도 오차가 일정 크기에서 멈춤 (단순 모형)", "단 사이 오차 이어짐 · 단당 오차 증가"),
         ("합격 → SDCG", "③ 놓기 전 판정", "놓기 직전 시방 기준으로 판정, 먼저 닿으면 들어 올려 다시 맞춤",
          "되돌릴 수 없는 실수를 놓기 전에 잡음", "걸침률 · 잘못 합격 비율")]
for k, (tag_, name, rule, why, chk_) in enumerate(props):
    x = M + k * (cw + 0.22)
    card(s, x, y, cw, chh, fill="canvas", line="hair", radius=0.16)
    hpill(s, x + 0.18, y + 0.16, tag_, "primarysoft", "primary", 14)
    text(s, x + 0.18, y + 0.58, cw - 0.36, 0.5, name, 22, "inkdeep", True, anchor=MSO_ANCHOR.MIDDLE)
    yy = y + 1.15
    rule_h = max(need_h([r[2]], cw - 0.36, 16, after=0) for r in props) + 0.05
    for lab, body in (("규칙", rule), ("왜 나아지나", why)):
        text(s, x + 0.18, yy, cw - 0.36, 0.3, lab, 15, "charcoal", True)
        bh_ = rule_h if lab == "규칙" else need_h([body], cw - 0.36, 16, after=0) + 0.05
        text(s, x + 0.18, yy + 0.32, cw - 0.36, bh_, body, 16, "inkdeep", spacing=1.05)
        yy += 0.32 + bh_ + 0.2
    strip(s, y + chh - 0.95, 0.78, f"**확인**: {chk_}", fill="soft", x=x + 0.14, w=cw - 0.28, size=15, tag=f"p9 {name}")
    if yy > y + chh - 0.95:
        WARN.append(f"p9 {name}: 본문 {yy:.2f} > 확인 상자 {y + chh - 0.95:.2f}")
note(s, "ACT는 집기 · 옮기기 · 대략 놓기만 · VS³ · VPRA · SDCG는 이번 제안에서 붙인 이름 · 바탕: Sutton 1999 · Jin & Shi 1999 · ISO 14253-1")
page_no(s, 9)

# ═══════════════════════════ 10 향후 계획 ② 순서와 일정
s = new(); T = chrome(s, 10, "차례부터 맞추고, 규칙을 하나씩 더해 효과를 나눔", "향후 계획 ② · 확인 순서와 일정")
y = T - 0.04
seq = [("0 · 기준선", "ACT + G1·G2·G3"), ("1 · 먼저", "+ 차례 맞추기"), ("2", "+ 놓기 전 판정"), ("3", "+ 쌓임 막기"), ("4", "전체 · 함께 효과")]
sw = CW / 5
for k, (a, b) in enumerate(seq):
    hi = k == 1
    chevron(s, M + k * sw, y, sw + 0.12, 1.05, f"{a}\n{b}", fill="primary" if hi else "soft", color="white" if hi else "inkdeep", size=17, first=(k == 0))
sy = y + 1.05 + 0.2
strip(s, sy, 0.72, "차례가 어긋나면 다른 두 규칙의 효과가 묻힘 → **차례 맞추기를 먼저 확인** · 효과가 없으면 해당 가설은 기각", fill="soft", tag="p10 why")
rows = [["기간", "할 일"],
        ["11/11 – 11/17", "**차례 맞추기** 구현 · 100벽 평가 / 2단 진입 벽 기록 재분석 (쌓임 근거)"],
        ["11/18 – 11/24", "**놓기 전 판정** 추가 · 걸침률 비교"],
        ["11/25 – 12/01", "모르타르 모델 보완 → **쌓임 막기** · 단 사이 오차 분석"],
        ["12/02 – 12/07", "mm 오차 · 민감도 분석, 보고서 · 발표 준비"],
        ["12/8", "**최종발표**"]]
table(s, M, sy + 0.72 + 0.22, CW, rows, [2.4, 9.9], size=17, row_h=0.5, head_h=0.44)
note(s, "자원: RTX 5090 1대 · 학습 1회 6~9시간 · 일정은 회의 후 확정")
page_no(s, 10)

prs.save(OUT)
print("saved", OUT)
for w_ in WARN:
    print("  WARN", w_)
