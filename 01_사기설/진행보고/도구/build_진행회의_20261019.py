# -*- coding: utf-8 -*-
"""사회기반시스템종합설계 14조 · 진행 회의 (2026-10-19) 발표 자료.
흐름: 배경 → 문제 → 목적 → 방법 → 검증 계획 → 결과(소형 1 + 대형 2) → 기여 → 일정 → 부록(상세 세팅 2) → 참고문헌. 표지 포함 15장.
- 디자인: 랩미팅 v3와 같은 Meta(minimax) 토큰 + 컨설팅 원칙(1장 1메시지, 개조식, 카드·표·프로세스·빅넘버, 고대비).
- 글꼴: Pretendard. 본문 16pt, 보조 14pt(차콜) 이상. 쪽 아래 인용 줄(11pt)과 참고문헌(10.5pt)만 예외.
- 사진·영상이 아직 없는 자리는 주황 점선 '사진 필요 / 영상 필요' 상자로 표시하고, 넣을 내용을 상자 안에 적는다.
- 사용한 사진·영상과 채울 상자 목록을 txt로 출력."""
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
N_SLIDES = 15
SECTIONS = ["배경", "문제", "목적", "방법", "검증", "결과", "기여", "일정", "부록"]
ACTIVE = {2: "배경", 3: "배경", 4: "문제", 5: "목적", 6: "방법", 7: "검증", 8: "결과", 9: "결과", 10: "결과",
          11: "기여", 12: "일정", 13: "부록", 14: "부록", 15: "부록"}
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
    latin = rPr.find(qn("a:latin"))
    for tag in ("a:ea", "a:cs"):
        e = rPr.find(qn(tag))
        if e is None:
            e = etree.Element(qn(tag)); latin.addnext(e) if tag == "a:ea" else rPr.find(qn("a:ea")).addnext(e)
        e.set("typeface", FONT)


def _runs(par, text_, size, color, bold=False, align=None, spacing=1.2):
    if align is not None:
        par.alignment = align
    par.line_spacing = spacing
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


def ph(slide, page, x, y, w, h, kind, title, desc, size=15):
    """채울 사진·영상 자리: 주황 점선 상자 + 넣을 내용."""
    shp = rect(slide, x, y, w, h, "orangesoft", "orange", radius=0.14, line_w=1.75)
    shp.line.dash_style = MSO_LINE.DASH
    lab = f"{kind} 필요"
    pill(slide, x + 0.14, y + 0.13, pw(lab, 13), 0.32, lab, "orange", "white", 13)
    ty = y + 0.52
    mtext(slide, x + 0.16, ty, w - 0.32, h - 0.62, [(f"**{title}**", size, "inkdeep", True), (desc, size - 1, "ink", False)],
          align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, spacing=1.08, after=4)
    PH.append((page, kind, title, desc))


# ── 크롬
def chrome(slide, n, title, section=None):
    text(slide, M, 0.1, 3.3, NAV_H - 0.1, "사회기반시스템종합설계 14조", 13, "inkdeep", True, anchor=MSO_ANCHOR.MIDDLE)
    xx = 3.78
    for s_ in SECTIONS:
        act = ACTIVE.get(n) == s_
        pill(slide, xx, 0.11, 0.74, 0.31, s_, "inkdeep" if act else "canvas", "white" if act else "ink", 12, None if act else "hair", act)
        xx += 0.8
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
    return ty + 0.68


def new():
    return prs.slides.add_slide(BLANK)


# ── 인용 (번호는 처음 나온 순서). 서지는 2026-10-12 · 10-19 확인분
REFS = {
    "liang21": ("Liang et al., 2021", "Liang, C.-J., Wang, X., Kamat, V. R., & Menassa, C. C. (2021). Human–robot collaboration in construction: Classification and research trends. Journal of Construction Engineering and Management, 147(10), 03121006. doi:10.1061/(ASCE)CO.1943-7862.0002154"),
    "giftthaler": ("Giftthaler et al., 2017", "Giftthaler, M., Sandy, T., Dörfler, K., Brooks, I., Buckingham, M., Rey, G., Kohler, M., Gramazio, F., & Buchli, J. (2017). Mobile robotic fabrication at 1:1 scale: The In situ Fabricator. Construction Robotics, 1, 3–14. doi:10.1007/s41693-017-0003-5"),
    "liang22": ("Liang et al., 2022", "Liang, C.-J., Kamat, V. R., Menassa, C. C., & McGee, W. (2022). Trajectory-based skill learning for overhead construction robots using generalized cylinders with orientation. Journal of Computing in Civil Engineering, 36(2), 04021036. doi:10.1061/(ASCE)CP.1943-5487.0001004"),
    "xiao": ("Xiao et al., 2022", "Xiao, B., Chen, C., & Yin, X. (2022). Recent advancements of robotics in construction. Automation in Construction, 144, 104591. doi:10.1016/j.autcon.2022.104591"),
    "ravichandar": ("Ravichandar et al., 2020", "Ravichandar, H., Polydoros, A. S., Chernova, S., & Billard, A. (2020). Recent advances in robot learning from demonstration. Annual Review of Control, Robotics, and Autonomous Systems, 3, 297–330. doi:10.1146/annurev-control-100819-063206"),
    "zhao": ("Zhao et al., 2023 (ACT)", "Zhao, T. Z., Kumar, V., Levine, S., & Finn, C. (2023). Learning fine-grained bimanual manipulation with low-cost hardware. Robotics: Science and Systems XIX. doi:10.15607/RSS.2023.XIX.016"),
    "billard": ("Billard & Kragic, 2019", "Billard, A., & Kragic, D. (2019). Trends and challenges in robot manipulation. Science, 364(6446), eaat8414. doi:10.1126/science.aat8414"),
    "johannink": ("Johannink et al., 2019", "Johannink, T., Bahl, S., Nair, A., Luo, J., Kumar, A., Loskyll, M., Aparicio Ojea, J., Solowjow, E., & Levine, S. (2019). Residual reinforcement learning for robot control. ICRA 2019, 6023–6029. doi:10.1109/ICRA.2019.8794127"),
    "ross": ("Ross et al., 2011 (DAgger)", "Ross, S., Gordon, G., & Bagnell, J. A. (2011). A reduction of imitation learning and structured prediction to no-regret online learning. AISTATS, PMLR 15, 627–635."),
    "laskey": ("Laskey et al., 2017 (DART)", "Laskey, M., Lee, J., Fox, R., Dragan, A., & Goldberg, K. (2017). DART: Noise injection for robust imitation learning. Conference on Robot Learning, PMLR 78, 143–156."),
    "belkhale": ("Belkhale et al., 2023", "Belkhale, S., Cui, Y., & Sadigh, D. (2023). Data quality in imitation learning. NeurIPS 36. arXiv:2306.02437"),
    "rac": ("Hu et al., 2025 (RaC)", "Hu, Z., Wu, R., Enock, N., Li, J., Kadakia, R., Erickson, Z., & Kumar, A. (2025). RaC: Robot learning for long-horizon tasks by scaling recovery and correction. arXiv:2509.07953 (preprint)"),
    "agia": ("Agia et al., 2025 (Sentinel)", "Agia, C., Sinha, R., Yang, J., et al. (2025). Unpacking failure modes of generative policies: Runtime monitoring of consistency and progress. CoRL 2024, PMLR 270, 689–723. arXiv:2410.04640"),
    "rewind": ("Zheng et al., 2026 (Rewind-IL)", "Zheng, G., Seenivasan, S., Johnson-Roberson, M., & Zhi, W. (2026). Rewind-IL: Online failure detection and state respawning for imitation learning. IEEE RA-L (early access). doi:10.1109/LRA.2026.3734897"),
    "huang": ("Huang et al., 2027", "Huang, L., Yang, X., Yan, Q., & Zou, Z. (2027). Vision-language model-based demonstrators for imitation learning in construction robotic timber assembly. Journal of Computing in Civil Engineering, 41(1), 04026116. doi:10.1061/JCCEE5.CPENG-7917 (online 2026)"),
    "chi": ("Chi et al., 2023 (Diffusion Policy)", "Chi, C., Feng, S., Du, Y., Xu, Z., Cousineau, E., Burchfiel, B., & Song, S. (2023). Diffusion Policy: Visuomotor policy learning via action diffusion. Robotics: Science and Systems XIX. doi:10.15607/RSS.2023.XIX.026"),
    "tao": ("Tao et al., 2026", "Tao, X., Wang, Y., Zhu, B., et al. (2026). Vision-driven state-space imitation learning for quadrotor navigation in infrastructure inspection. Computer-Aided Civil and Infrastructure Engineering, 46, 100030."),
    "mujoco": ("Todorov et al., 2012 (MuJoCo)", "Todorov, E., Erez, T., & Tassa, Y. (2012). MuJoCo: A physics engine for model-based control. IEEE/RSJ IROS, 5026–5033. doi:10.1109/IROS.2012.6386109"),
    "lerobot": ("LeRobot", "Hugging Face (2024–). LeRobot: State-of-the-art machine learning for real-world robotics. github.com/huggingface/lerobot (v0.6.1 사용)"),
    "kcs34": ("KCS 41 34 00", "국토교통부 (2021). KCS 41 34 00 조적공사, 건축공사 표준시방서. 국가건설기준센터(KCSC)."),
    "ks": ("KS L 4201", "국가기술표준원 (2022). KS L 4201 점토 벽돌 (표준형 치수 190 × 90 × 57 mm)."),
}
REF_ORDER = []
_PENDING = []


def cite(*keys):
    nums = []
    for k in keys:
        assert k in REFS, k
        if k not in REF_ORDER:
            REF_ORDER.append(k)
        if k not in _PENDING:
            _PENDING.append(k)
        nums.append(REF_ORDER.index(k) + 1)
    return "[" + ",".join(str(n) for n in nums) + "]"


def footnote(slide, extra=None):
    global _PENDING
    keys = list(_PENDING); _PENDING = []
    if not keys and not extra:
        return
    parts = [f"[{REF_ORDER.index(k) + 1}] {REFS[k][0]}" for k in keys]
    line = " · ".join(parts) + (("   " + extra) if extra else "")
    nl = est_lines(line, W - 2 * M - 0.95, 11)
    if nl <= 1:
        text(slide, M, 7.02, W - 2 * M - 0.85, 0.36, line, 11, "charcoal", anchor=MSO_ANCHOR.MIDDLE)
    else:
        nl = est_lines(line, W - 2 * M - 0.95, 10); hh = 0.19 * nl + 0.06
        text(slide, M, 7.44 - hh, W - 2 * M - 0.85, hh, line, 10, "charcoal", spacing=1.0, anchor=MSO_ANCHOR.BOTTOM)


def wall(slide, x, y, w):
    """3단 일자 벽 정면도: 1단 온장 5 / 2단 반장 + 온장 4 + 반장 / 3단 온장 5. 줄눈 10 mm. 반환: 그린 높이."""
    s_ = w / 990.0; hb = 57 * s_; gj = 10 * s_
    rows = [(0, [(0, 190), (200, 190), (400, 190), (600, 190), (800, 190)]),                  # 3단 (위)
            (1, [(0, 90), (100, 190), (300, 190), (500, 190), (700, 190), (900, 90)]),       # 2단
            (2, [(0, 190), (200, 190), (400, 190), (600, 190), (800, 190)])]                 # 1단 (아래)
    for r_, bricks in rows:
        yy = y + r_ * (hb + gj)
        for bx, bl in bricks:
            rect(slide, x + bx * s_, yy, bl * s_, hb, "brickhalf" if bl == 90 else "brick", "white", line_w=0.5)
    ln = slide.shapes.add_connector(1, Inches(x - 0.15), Inches(y + 3 * hb + 2 * gj + 0.02), Inches(x + w + 0.15), Inches(y + 3 * hb + 2 * gj + 0.02))
    ln.line.color.rgb = RGB["charcoal"]; ln.line.width = Pt(1.25)
    return 3 * hb + 2 * gj


def gate_pills(slide, x, y, on, size=12, pw_=0.5, ph_=0.28, gap=0.06):
    for k, g_ in enumerate(("G1", "G2", "G3")):
        a = on[k]
        pill(slide, x + k * (pw_ + gap), y, pw_, ph_, g_, "primary" if a else "canvas", "white" if a else "charcoal", size, None if a else "hair", True)


# ═══════════════════════════ 1 표지
s = new()
pill(s, 0.9, 1.0, 1.35, 0.4, "진행 보고", "inkdeep", "white", 15)
text(s, 0.9, 1.6, 7.3, 1.9, ["모방학습 조적 로봇의", "정책 밖 검측 효과 분석"], 40, "inkdeep", True, spacing=1.08, after=0)
text(s, 0.9, 3.45, 7.3, 0.45, "MuJoCo 시뮬레이션 · UR10e · 시방 기준 3단 벽체", 20, "ink")
ln = s.shapes.add_connector(1, Inches(0.9), Inches(4.15), Inches(6.9), Inches(4.15)); ln.line.color.rgb = RGB["hair"]; ln.line.width = Pt(1)
text(s, 0.9, 4.35, 7.3, 0.42, "**사회기반시스템종합설계 14조**", 20, "inkdeep")
text(s, 0.9, 4.85, 7.3, 0.4, "정원영 · 임수현 · 정성용 · 강건", 18, "ink")
text(s, 0.9, 5.35, 7.3, 0.38, "지도교수: 김홍조 교수님", 17, "ink")
text(s, 0.9, 5.85, 7.3, 0.38, "2026.10.19", 17, "charcoal", True)
ph(s, 1, 8.0, 1.0, 4.83, 5.2, "사진", "새 실험 환경 대표 화면",
   "첨부하신 MuJoCo 화면\nUR10e · 받침대 · 적벽돌 3단 · 공급대\n뷰어 왼쪽 메뉴는 잘라서", 16)
pill(s, W - M - 0.62, H - 0.42, 0.62, 0.32, "1", "inkdeep", "white", 13)

# ═══════════════════════════ 2 연구 배경
s = new(); T = chrome(s, 2, "기존 조적 로봇: 미리 짠 경로 + 현장마다 다시 계측", "연구 배경")
c1 = cite("liang21")
text(s, M, T - 0.02, 7.6, 0.36, f"건설 로봇 연구 259편 분류 · 2021년 기준 {c1}", 15, "charcoal", True)
steps = [("사전 프로그래밍", "135편", ["정해진 경로 반복", "정렬 확인: **사람**"], "예: SAM", "soft", "inkdeep"),
         ("적응형 조작", "72편", ["센서로 **현장 재계측**", "계획 보정 후 실행"], "예: Hadrian X", "soft", "inkdeep"),
         ("모방학습", "3편", ["시연에서 **동작 학습**", "건설 분야 초기 단계"], "본 연구 위치", "primary", "white")]
BW, BG, BOT = 2.45, 0.12, 6.45
hs = [2.85, 3.5, 4.15]
for k, (lab, big, lines, ex, fill, col) in enumerate(steps):
    bx = M + k * (BW + BG); by = BOT - hs[k]
    card(s, bx, by, BW, hs[k], fill=fill, line=None if fill == "primary" else "hairsoft", radius=0.16)
    pill(s, bx + 0.15, by + 0.15, pw(lab, 14), 0.36, lab, "inkdeep" if fill != "primary" else "white", "white" if fill != "primary" else "primary", 14)
    text(s, bx + 0.15, by + 0.6, BW - 0.3, 0.7, big, 34, col if fill == "primary" else "inkdeep", True, spacing=1.0)
    text(s, bx + 0.15, by + 1.3, BW - 0.3, 0.75, lines, 15, col if fill == "primary" else "ink", spacing=1.05, after=1)
    pill(s, bx + 0.15, BOT - 0.5, pw(ex, 13), 0.32, ex, "canvas" if fill != "primary" else "inkdeep", "inkdeep" if fill != "primary" else "white", 13, "hair" if fill != "primary" else None)
# 위로 갈수록 자율성 ↑
text(s, M, T + 0.42, 4.6, 0.4, "로봇 자율성 ↑ · 사람 개입 ↓  →", 15, "primary", True)
XR = M + 3 * BW + 2 * BG + 0.35; WR = W - M - XR
ph(s, 2, XR, T - 0.02, (WR - 0.15) / 2, 2.1, "사진", "SAM 벽돌쌓기", "Construction Robotics\n공식 사진", 14)
ph(s, 2, XR + (WR - 0.15) / 2 + 0.15, T - 0.02, (WR - 0.15) / 2, 2.1, "사진", "Hadrian X 시공", "FBR 공식 사진", 14)
yb = T + 2.25
box = card(s, XR, yb, WR, BOT - yb, fill="criticalsoft", line="critical", radius=0.16, line_w=1.5)
pill(s, XR + 0.18, yb + 0.16, pw("공통 한계", 14), 0.36, "공통 한계", "critical", "white", 14)
c2 = cite("giftthaler", "liang22"); c3 = cite("xiao")
text(s, XR + 0.2, yb + 0.66, WR - 0.4, BOT - yb - 0.75,
     [f"**현장·자재 변경**: 경로·계측 재설정 {c2}", f"**처음 보는 현장**: 적응 못함 {c3}", "**정렬 확인**: 사람 · 외부 계측 몫"],
     17, "inkdeep", spacing=1.15, after=8, anchor=MSO_ANCHOR.MIDDLE)
footnote(s)

# ═══════════════════════════ 3 기존 지식: 왜 학습 기반인가
s = new(); T = chrome(s, 3, "학습 기반: 재프로그래밍·정밀 계측을 시연으로 대체", "연구 배경 · 기존 지식")
LANE_H = 0.92; LX = M + 1.75; CHW = 2.62
for li, (lab, lfill, chs, res, rfill, rcol) in enumerate([
        ("제어 기반", "critical", ["경로 프로그래밍", "현장 계측·정합", "보정 후 실행"], "현장마다 **반복**", "criticalsoft", "critical"),
        ("학습 기반", "primary", ["시연 수집", "정책 학습", "카메라·관절 실행"], "재프로그래밍 **없음**", "primarysoft", "primary")]):
    ly = T + li * (LANE_H + 0.22)
    pill(s, M, ly + LANE_H / 2 - 0.22, 1.55, 0.44, lab, lfill, "white", 16)
    for k, chn in enumerate(chs):
        chevron(s, LX + k * (CHW - 0.08), ly, CHW, LANE_H, chn, "soft", "inkdeep", 17, first=(k == 0))
    rx = LX + 3 * (CHW - 0.08) + 0.2
    card(s, rx, ly + 0.1, W - M - rx, LANE_H - 0.2, fill=rfill, line=None, radius=0.14)
    text(s, rx + 0.1, ly + 0.1, W - M - rx - 0.2, LANE_H - 0.2, res, 18, rcol, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
EY = T + 2 * LANE_H + 0.22 + 0.24
text(s, M, EY - 0.04, 8, 0.36, "근거: 학습 기반을 택하는 이유", 15, "charcoal", True)
EY += 0.36; EW = (W - 2 * M - 0.4) / 3; EH = 1.55
ev = [("환경 바뀌면 재명세 필요", "전통 프로그래밍의 한계\n→ 시연 학습이 대안", cite("ravichandar"), "Annu. Rev. Control Robot."),
      ("궤적 사전 프로그래밍 비현실적", "느슨한 공차 · 설계–시공 차이\n→ 시연 학습(LfD)", cite("liang22"), "J. Comput. Civ. Eng."),
      ("정밀 보정 대신 폐루프 정책", "정밀도 5–8 mm 팔로\nmm 단위 작업 80–90 % 성공", cite("zhao"), "RSS (ACT)")]
for k, (hd, body, cn, venue) in enumerate(ev):
    ex_ = M + k * (EW + 0.2)
    card(s, ex_, EY, EW, EH, fill="canvas", line="hair", radius=0.16)
    text(s, ex_ + 0.18, EY + 0.12, EW - 0.36, 0.4, f"**{hd}**", 17, "inkdeep")
    text(s, ex_ + 0.18, EY + 0.58, EW - 0.36, 0.72, body.split("\n"), 15, "ink", spacing=1.05, after=1)
    text(s, ex_ + 0.18, EY + EH - 0.42, EW - 0.36, 0.32, f"{cn} {venue}", 14, "primary", True)
BY = EY + EH + 0.18
card(s, M, BY, W - 2 * M, 6.92 - BY, fill="orangesoft", line="orange", radius=0.14, line_w=1.25)
c4 = cite("billard", "johannink")
text(s, M + 0.25, BY, W - 2 * M - 0.5, 6.92 - BY, [f"**단, 학습 단독**: 정밀도·보장 부족 → **고전 제어와 결합** 권장 {c4}", "▶ 다음: 모방학습 정책의 실패 대응 문제"], 17, "inkdeep", spacing=1.1, after=4, anchor=MSO_ANCHOR.MIDDLE)
footnote(s)

# ═══════════════════════════ 4 문제 정의: 딜레마 (학계 용어)
s = new(); T = chrome(s, 4, "모방학습의 딜레마: 실패 복구 vs 배치 정밀도", "문제 정의")
CW4 = (W - 2 * M - 0.33) / 2
cols = [("① 성공 시연만 학습", "Behavior Cloning on expert demonstrations", "기존 표현: 미학습"),
        ("② 복구 시연 혼합 학습", "training with recovery (corrective) demonstrations", "기존 표현: 복구 학습")]
for k, (hd, en, old) in enumerate(cols):
    cx = M + k * (CW4 + 0.33)
    card(s, cx, T - 0.04, CW4, 0.98, fill="inkdeep", line=None, radius=0.16)
    text(s, cx + 0.2, T + 0.02, CW4 - 2.3, 0.46, hd, 19, "white", True, anchor=MSO_ANCHOR.MIDDLE)
    text(s, cx + 0.2, T + 0.46, CW4 - 0.4, 0.4, en, 15, "white", anchor=MSO_ANCHOR.MIDDLE)
    pill(s, cx + CW4 - 2.05, T + 0.09, 1.88, 0.34, old, "white", "inkdeep", 13)
MY = T + 1.0
c5 = cite("ross", "zhao")
text(s, M, MY, CW4, 0.7, ["**compounding error** → 학습 분포 이탈", f"→ **실패 상태 미인지** {c5}"], 16, "inkdeep", spacing=1.05, after=0)
c6 = cite("laskey", "belkhale")
text(s, M + CW4 + 0.33, MY, CW4, 0.7, ["**state diversity ↑ ↔ action divergence ↑**", f"→ **배치 정밀도 저하** {c6}"], 16, "inkdeep", spacing=1.05, after=0)
VY = MY + 0.78
# 왼쪽: 빈손 운반 영상 + 빅넘버
vx, vy, vw, vh = movie(s, V + "21_빈손운반_재현_seed40000.mp4", A9 + "poster_21.png", M, VY, 3.55, 2.05)
use(4, "영상", V + "21_빈손운반_재현_seed40000.mp4", "① 집지 못하고도 그대로 운반(실험 3, 정책 단독)"); use(4, "사진", A9 + "poster_21.png", "포스터 프레임")
text(s, M, vy + vh + 0.04, 3.55, 0.34, "빈손으로 집고도 그대로 운반", 15, "inkdeep", True, align=PP_ALIGN.CENTER)
NX = M + 3.75; NW = CW4 - 3.75
for j, (lab, big, col) in enumerate([("Diffusion 정책 단독", "35%", "critical"), ("ACT 정책 단독", "0%", "critical")]):
    ny = VY + j * 1.06
    card(s, NX, ny, NW, 0.96, fill="criticalsoft", line=None, radius=0.14)
    text(s, NX + 0.15, ny + 0.05, NW - 0.3, 0.3, lab, 14, "inkdeep", True)
    text(s, NX + 0.15, ny + 0.32, NW - 0.3, 0.6, big, 28, col, True, spacing=1.0, anchor=MSO_ANCHOR.MIDDLE)
text(s, NX, VY + 2.16, NW, 0.32, "완성률", 14, "inkdeep", True, align=PP_ALIGN.CENTER)
# 오른쪽: 같은 배치 두 영상 + 빅넘버
RX4 = M + CW4 + 0.33; hw4 = (CW4 - 0.2) / 2
hh = 1.34
for k, (vf, po, lab, cap) in enumerate([("25_실험1_Diffusion_복구없이학습_같은배치_2.5배속_0-8s.mp4", A16 + "poster_25.png", "성공 시연만", "② 같은 배치: 성공 시연만 학습"),
                                        ("26_실험1_Diffusion_복구섞어학습_같은배치_2.5배속.mp4", A16 + "poster_26.png", "복구 시연 혼합", "② 같은 배치: 복구 시연 혼합 학습")]):
    _, _, _, hh = movie(s, V + vf, po, RX4 + k * (hw4 + 0.2), VY, hw4, 1.6)
    use(4, "영상", V + vf, cap); use(4, "사진", po, "포스터 프레임")
by4 = VY + hh + 0.08
for k, (lab, big, sub, col, fill) in enumerate([("성공 시연만", "90%", "오차 2.6 mm", "success", "successsoft"), ("복구 시연 혼합", "2%", "오차 6.3 mm", "critical", "criticalsoft")]):
    bx = RX4 + k * (hw4 + 0.2)
    card(s, bx, by4, hw4, 0.86, fill=fill, line=None, radius=0.14)
    mtext(s, bx + 0.12, by4 + 0.02, 1.15, 0.82, [("완성률", 14, "inkdeep", True), (big, 26, col, True)],
          anchor=MSO_ANCHOR.MIDDLE, spacing=0.95, after=0)
    mtext(s, bx + 1.3, by4 + 0.02, hw4 - 1.4, 0.82, [(lab, 14, "inkdeep", True), (sub, 14, "inkdeep", False)],
          anchor=MSO_ANCHOR.MIDDLE, spacing=1.05, after=1)
c7 = cite("rac")
text(s, RX4, by4 + 0.92, CW4, 0.32, f"단, 구조화된 복구 데이터는 효과 보고 {c7} → **단순 혼합** 한정", 14, "inkdeep")
text(s, M, 6.17, CW4, 0.3, "조건 실험 3 · 넓은 배치 ±30 mm·±60° · 시험 배치 40·48회", 14, "charcoal")
text(s, RX4, 6.17, CW4, 0.3, "조건 실험 1 · 좁은 배치 · Diffusion · 각 100회", 14, "charcoal")
card(s, M, 6.5, W - 2 * M, 0.46, fill="primary", line=None, radius=0.16)
text(s, M + 0.2, 6.5, W - 2 * M - 0.4, 0.46, "어느 쪽도 손실 → **정책은 그대로, 실패 인지·보정은 정책 밖 검측으로**", 17, "white", align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
footnote(s)

# ═══════════════════════════ 5 연구 목적 · 연구 질문
s = new(); T = chrome(s, 5, "정책은 그대로, 검측 3단계의 효과를 단계별로 정량화", "연구 목적 · 연구 질문")
GW = 4.25; GH = 1.5
card(s, M, T - 0.04, GW, GH, fill="canvas", line="hair", radius=0.16)
pill(s, M + 0.16, T + 0.08, pw("선행 연구의 공백", 13), 0.32, "선행 연구의 공백", "critical", "white", 13)
c8 = cite("agia", "rewind")
text(s, M + 0.18, T + 0.46, GW - 0.36, GH - 0.52, [f"**실패 감지·복구**: 전체 성공률만 {c8}", "**검측 단계별 기여**: 분리 안 됨", "**건설 품질 기준**: 평가 없음"], 15, "inkdeep", spacing=1.05, after=2)
arrow_right(s, M + GW + 0.1, T + GH / 2 - 0.2, 0.42, 0.4, "charcoal")
PX = M + GW + 0.62; PWd = W - M - PX
card(s, PX, T - 0.04, PWd, GH, fill="primary", line=None, radius=0.16)
pill(s, PX + 0.16, T + 0.08, pw("연구 목적", 13), 0.32, "연구 목적", "white", "primary", 13)
text(s, PX + 0.2, T + 0.44, PWd - 0.4, GH - 0.5,
     ["같은 모방학습 정책 + **정책 밖 검측 3단계** → **시방 합격률** 변화를 단계별 정량화",
      "목표: 정책 단독보다 합격률 높은 **정책 + 검측 구성** 제시"], 16, "white", spacing=1.08, after=4)
# 벽돌 1장 작업 흐름 (카드 + 화살표)
FY = T + GH + 0.16
text(s, M, FY - 0.02, 7.0, 0.34, "벽돌 1장 작업 흐름 · 검측은 정책 밖에서 개입", 15, "charcoal", True)
pill(s, W - M - pw("실행 중 정답 좌표 미사용", 13), FY - 0.02, pw("실행 중 정답 좌표 미사용", 13), 0.32, "실행 중 정답 좌표 미사용", "canvas", "critical", 13, "critical")
FY += 0.4
flow = [("집기", None), ("G1 잡기 확인", "하중 + 집게 각도"), ("운반", None), ("G2 놓기 전 보정", "작업대 카메라"),
        ("놓기", None), ("G3 놓은 뒤 재배치", "작업대 카메라"), ("다음 벽돌", None)]
SWf, GWf, AG = 1.05, 2.17, 0.27
FH = 0.86; fx = M
for k, (lab, sub) in enumerate(flow):
    gate = sub is not None; fw = GWf if gate else SWf
    card(s, fx, FY, fw, FH, fill="primary" if gate else "soft", line=None, radius=0.14)
    parts = [(lab, 15 if gate else 15, "white" if gate else "inkdeep", True)] + ([(sub, 13, "white", False)] if sub else [])
    mtext(s, fx + 0.04, FY, fw - 0.08, FH, parts, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, spacing=1.0, after=1)
    fx += fw
    if k < len(flow) - 1:
        rect(s, fx + 0.05, FY + FH / 2 - 0.1, AG - 0.1, 0.2, "charcoal", None, shape=MSO_SHAPE.RIGHT_ARROW)
        fx += AG
# 연구 질문: 메인 띠 + 서브 4장
QY = FY + FH + 0.18
card(s, M, QY, W - 2 * M, 0.52, fill="inkdeep", line=None, radius=0.14)
text(s, M + 0.2, QY, W - 2 * M - 0.4, 0.52, "**메인 질문**   검측 3단계는 시방 합격률을 **각각 · 함께** 얼마나 높이는가?   → 2×2×2 요인 설계", 17, "white", anchor=MSO_ANCHOR.MIDDLE)
RY5 = QY + 0.64; RW5 = (W - 2 * M - 3 * 0.18) / 4
rqs = [("RQ1", "G1 주효과", "**G1**(하중·각도)만으로\n잡기 실패가 줄어드는가?"), ("RQ2", "G2 주효과", "**G2**(카메라 보정)가\n배치 오차를 줄이는가?"),
       ("RQ3", "G3 주효과", "**G3**(카메라 재배치)가\n불합격을 회복하는가?"), ("RQ4", "상호작용", "함께 켜면 효과가\n**더해지는가**?")]
for k, (q, how, body) in enumerate(rqs):
    rx = M + k * (RW5 + 0.18)
    card(s, rx, RY5, RW5, 6.92 - RY5, fill="canvas", line="hair", radius=0.16)
    pill(s, rx + 0.15, RY5 + 0.14, 0.72, 0.32, q, "primary", "white", 13)
    text(s, rx + 0.95, RY5 + 0.12, RW5 - 1.05, 0.36, how, 14, "charcoal", True, anchor=MSO_ANCHOR.MIDDLE)
    text(s, rx + 0.15, RY5 + 0.56, RW5 - 0.3, 6.92 - RY5 - 0.62, body.split("\n"), 15, "inkdeep", spacing=1.08, after=1)
footnote(s)

# ═══════════════════════════ 6 방법
s = new(); T = chrome(s, 6, "대본 교사 → 모방학습 정책 → 정책 밖 검측", "방법")
SW = (W - 2 * M - 2 * 0.42) / 3; SH = 4.32
c9 = cite("zhao", "huang"); c10 = cite("chi")
stages = [("① 시연 생성 · 교사", ("영상", "대본 시연 1장", "새 환경 · 집기~철수 · 실시간"),
           ["**방식**: 역기구학 대본", "**정보**: 정답 좌표 (시연에만)", "**선별**: 시방 합격 벽만", "**규모**: 벽 1,000개", "**단위**: 벽돌 1장 = 에피소드 1개"],
           f"스크립트 시연 86% > 사람 50% {c9}"),
          ("② 정책 학습 · 학생", ("사진", "정책 입력 3시점", "front · top · wrist 128² 캡처"),
           [f"**정책**: ACT {cite('zhao')} · Diffusion {c10}", "**입력**: 카메라 3대 + 관절 + 목표 자세", "**출력**: 관절 목표 + 집게, 20 Hz", "**학습량**: 10만 스텝 × 배치 32 (동일)", "**반복**: 학습 seed 3 · 마지막 체크포인트"],
           "두 정책 비교 → 결론이 정책 선택에 안 묶임"),
          ("③ 정책 밖 검측 · 실행", ("영상", "G1·G2·G3 장면", "새 환경 · 들기 확인 · 보정 · 재배치"),
           ["**G1**: 들고 멈춘 뒤 하중 + 각도", "**G2**: 놓기 직전 카메라 → 보정", "**G3**: 놓은 뒤 카메라 → 1회 재배치", "**문턱**: 검증 배치로 정해 동결", "**정답 좌표**: 실행 중 미사용"],
           "정책 가중치 고정 → 검측 효과만 분리")]
for k, (hd, phd, lines, why) in enumerate(stages):
    sx = M + k * (SW + 0.42)
    card(s, sx, T - 0.04, SW, SH, fill="canvas", line="hair", radius=0.18)
    pill(s, sx + 0.16, T + 0.08, pw(hd, 15), 0.38, hd, "inkdeep", "white", 15)
    ph(s, 6, sx + 0.16, T + 0.56, SW - 0.32, 1.12, phd[0], phd[1], phd[2], 14)
    text(s, sx + 0.18, T + 1.8, SW - 0.36, 1.85, lines, 15, "ink", spacing=1.06, after=3)
    card(s, sx + 0.14, T + SH - 0.68, SW - 0.28, 0.54, fill="primarysoft", line=None, radius=0.12)
    text(s, sx + 0.22, T + SH - 0.68, SW - 0.44, 0.54, why, 14, "primary", True, anchor=MSO_ANCHOR.MIDDLE, spacing=1.0)
    if k < 2:
        arrow_right(s, sx + SW + 0.05, T + SH / 2 - 0.18, 0.32, 0.36)
BY6 = T + SH + 0.16
c11 = cite("liang22", "tao"); c12 = cite("mujoco"); c13 = cite("lerobot")
for k, (lab, body) in enumerate([("왜 시뮬레이션", f"같은 배치 반복 · 실패 원인 분리 {c11}"), ("물리 엔진", f"MuJoCo 3.13 · 1 ms · 20 Hz {c12}"),
                                 ("구현", f"LeRobot 0.6.1 기본 · RTX 5090 {c13}")]):
    bx = M + k * (SW + 0.42)
    card(s, bx, BY6, SW, 6.92 - BY6, fill="soft", line=None, radius=0.14)
    text(s, bx + 0.16, BY6, SW - 0.32, 6.92 - BY6, [f"**{lab}**", body], 14, "inkdeep", spacing=1.02, after=1, anchor=MSO_ANCHOR.MIDDLE)
footnote(s)

# ═══════════════════════════ 7 검증 계획
s = new(); T = chrome(s, 7, "2×2×2 요인 설계 · KCS 41 34 00 허용오차로 판정", "검증 계획")
LW7 = 6.55
text(s, M, T - 0.04, LW7, 0.36, "8조건 · 같은 정책 가중치 · 같은 시험 배치 · 검측만 켬/끔", 15, "charcoal", True)
conds = [(0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1), (1, 1, 0), (1, 0, 1), (0, 1, 1), (1, 1, 1)]
TW = (LW7 - 3 * 0.14) / 4; TH = 1.02
for i, on in enumerate(conds):
    r_, c_ = divmod(i, 4)
    tx_ = M + c_ * (TW + 0.14); ty_ = T + 0.4 + r_ * (TH + 0.12)
    hl = i in (0, 7)
    card(s, tx_, ty_, TW, TH, fill="primarysoft" if hl else "canvas", line="primary" if hl else "hair", radius=0.14, line_w=1.25 if hl else 0.75)
    text(s, tx_ + 0.12, ty_ + 0.05, TW - 0.24, 0.4, f"**{i + 1}**" + ("  정책 단독" if i == 0 else ("  전체" if i == 7 else "")), 16, "inkdeep")
    gate_pills(s, tx_ + 0.12, ty_ + 0.56, on, size=12, pw_=(TW - 0.24 - 0.12) / 3, ph_=0.3)
AY = T + 0.4 + 2 * (TH + 0.12) + 0.06
AW = (LW7 - 3 * 0.12) / 4; AH = 1.0
for i, (hd, body) in enumerate([("주효과", "켬 − 끔\n4쌍 평균"), ("상호작용", "함께 켤 때\n추가분"),
                                ("짝 비교", "같은 초기\n배치끼리"), ("신뢰구간", "Wilson\n95 %")]):
    ax = M + i * (AW + 0.12)
    card(s, ax, AY, AW, AH, fill="soft", line=None, radius=0.12)
    text(s, ax + 0.12, AY, AW - 0.24, AH, [f"**{hd}**"] + body.split("\n"), 15, "inkdeep", spacing=1.0, after=1, anchor=MSO_ANCHOR.MIDDLE)
PY7 = AY + AH + 0.14
pf = [("검증 배치", "720000번대"), ("문턱 동결", "G1 · G2 · G3"), ("시험 배치", "730000번대 · 잠금")]
pcw = (LW7 + 0.16) / 3
for k, (a_, b_) in enumerate(pf):
    chevron(s, M + k * (pcw - 0.08), PY7, pcw, 6.92 - PY7, a_ + "\n" + b_, "inkdeep" if k == 2 else "soft", "white" if k == 2 else "inkdeep", 15, first=(k == 0))
RX7 = M + LW7 + 0.35; RW7 = W - M - RX7
ck = cite("kcs34")
th7 = table(s, RX7, T - 0.04, RW7, [["시방 항목 " + ck, "원천 허용오차", "이 벽 기준"],
    ["① 가로줄눈 두께", "10 ± 3 mm", "7 ~ 13 mm"],
    ["② 선 및 면", "3 m당 6 mm", "2.0 mm"],
    ["③ 수직도", "3 m당 6 mm", "2.0 mm"],
    ["④ 평면상 위치", "9 m당 6 mm", "2.0 mm"],
    ["⑤ 벽 두께", "−6 ~ +13 mm", "−6 ~ +13 mm"]],
    [2.15, 1.75, 1.6], 15, row_h=0.44, head_h=0.42, align_c=(1, 2))
KY = T - 0.04 + th7 + 0.16
card(s, RX7, KY, RW7, 6.92 - KY, fill="primarysoft", line=None, radius=0.14)
text(s, RX7 + 0.18, KY, RW7 - 0.36, 6.92 - KY,
     ["**합격**: 16자리 채움 + ①~⑤ 모두", "**②③④**: 길이 비례 축소 · 하한 2 mm", "**벽돌별 3D IoU**: 측정값만 보고"], 15, "inkdeep", spacing=1.08, after=5, anchor=MSO_ANCHOR.MIDDLE)
footnote(s)

# ═══════════════════════════ 8 결과 ① 소형 실험
s = new(); T = chrome(s, 8, "소형 실험: 정책 밖 검측으로 완성률 2배 이상", "결과 · 소형 실험")
xx = M
for lab in ["SO-ARM100 · 블록 3개 (2+1)", "배치 ±30 mm · ±60°", "시연 200 · ACT · Diffusion", "시험 배치 40 · 48회"]:
    wd = pw(lab, 14); pill(s, xx, T - 0.04, wd, 0.36, lab, "soft", "inkdeep", 14); xx += wd + 0.12
LW8 = 6.75; CY = T + 0.45
bar_chart(s, M, CY, LW8, 2.55, ["A 정책 단독", "B + G1", "C + G2", "D + G3"],
          [("Diffusion", [35, 30, 72, 75], "primary"), ("ACT", [0, 0, 29, 54], "inkdeep")])
text(s, M, CY + 2.56, LW8, 0.3, "검측은 누적 추가 · B는 27·25회 · **C·D 위치 정보 = 정답 좌표(상한)**", 14, "charcoal")
src = G + "g123_cuts.png"
cut = AS + "p08_g123.png"
Image.open(src).convert("RGB").crop((0, 0, 1960, 470)).save(cut)
iw, ih = picture(s, cut, M, CY + 2.92, w=LW8)
use(8, "사진", src, "소형 환경 G1·G2·G3 장면 원본"); use(8, "사진", cut, "아래 회색 설명 줄을 자른 판")
RX8 = M + LW8 + 0.35; RW8 = W - M - RX8
for j, (lab, big, sub) in enumerate([("Diffusion · A → D", "35% → 75%", ["95% CI", "22–50 → 60–86"]), ("ACT · A → D", "0% → 54%", ["95% CI", "0–7 → 40–67"])]):
    yy = CY + j * 1.2
    card(s, RX8, yy, RW8, 1.1, fill="primarysoft", line=None, radius=0.16)
    text(s, RX8 + 0.2, yy + 0.06, RW8 - 0.4, 0.32, lab, 15, "inkdeep", True)
    text(s, RX8 + 0.2, yy + 0.36, 3.1, 0.68, big, 30, "primary", True, spacing=1.0, anchor=MSO_ANCHOR.MIDDLE)
    text(s, RX8 + 3.3, yy + 0.36, RW8 - 3.45, 0.68, sub, 14, "inkdeep", spacing=1.0, after=0, anchor=MSO_ANCHOR.MIDDLE)
iy = CY + 2.46
for j, (hd, body) in enumerate([("G1 단독: 효과 없음", "다시 집어도 놓기 그대로 → **위치 보정이 핵심**"),
                                ("카메라 위치 추정 (정답 좌표 대신)", "평균 **0.43 mm** · 대본 + 검측 **48/50 vs 45/50**")]):
    yy = iy + j * 1.0
    card(s, RX8, yy, RW8, 0.9, fill="canvas", line="hair", radius=0.14)
    text(s, RX8 + 0.2, yy + 0.04, RW8 - 0.4, 0.82, [f"**{hd}**", body], 15, "inkdeep", spacing=1.04, after=2, anchor=MSO_ANCHOR.MIDDLE)
text(s, RX8, iy + 2.02, RW8, 0.34, "→ 대형 환경: 위치 정보를 **카메라로만** 얻어 재검증", 15, "primary", True)
footnote(s)

# ═══════════════════════════ 9 결과 ② 대형 환경
s = new(); T = chrome(s, 9, "대형 환경: UR10e · 실척 벽돌 3단 16장 구축", "결과 · 대형 환경")
LW9 = 7.05
ph(s, 9, M, T - 0.04, LW9, 4.42, "사진", "새 실험 환경 화면 (첨부하신 PNG)",
   "UR10e · 받침대 0.6 m · 적벽돌 3단 · 뒤쪽 공급대\n뷰어 왼쪽 메뉴는 잘라서 · 가능하면 정면 대각 시점 1장 더", 16)
CHY = T + 4.52
chips = [("벽돌 3개", "**16장**"), ("축소 모형", "**실척**"), ("5 % 임의 기준", "**시방 기준**"), ("정답 좌표", "**카메라**")]
cw9 = (LW9 - 3 * 0.12) / 4
for k, (a_, b_) in enumerate(chips):
    cx = M + k * (cw9 + 0.12)
    card(s, cx, CHY, cw9, 6.92 - CHY, fill="soft", line=None, radius=0.14)
    text(s, cx + 0.08, CHY, cw9 - 0.16, 6.92 - CHY, [a_, "→ " + b_], 15, "inkdeep", align=PP_ALIGN.CENTER, spacing=1.05, after=1, anchor=MSO_ANCHOR.MIDDLE)
RX9 = M + LW9 + 0.35; RW9 = W - M - RX9
text(s, RX9, T - 0.06, RW9, 0.34, "3단 일자 벽 · L 990 × H 191 mm", 15, "charcoal", True)
wh = wall(s, RX9 + 0.2, T + 0.38, RW9 - 0.4)
cks = cite("ks"); ck2 = cite("kcs34")
th9 = table(s, RX9, T + 0.5 + wh + 0.18, RW9, [["항목", "설정"],
    ["로봇", "UR10e · 받침대 0.6 m"],
    ["집게", "Robotiq 2F-140"],
    ["벽돌", f"190×90×57 mm · 1.95 kg {cks}"],
    ["벽", "온장 14 + 반장 2 · 줄눈 10 mm"],
    ["공급", "로봇 뒤 · ±10 mm · ±10°"],
    ["카메라", "앞 · 위 · 손목 · 128²"],
    ["판정", f"시방 5항목 {ck2}"]],
    [1.25, 3.95], 15, row_h=0.4, head_h=0.38)
footnote(s)

# ═══════════════════════════ 10 결과 ③ 진행 현황
s = new(); T = chrome(s, 10, "시연 1,000벽 수집 완료, 본 학습 진행 중", "결과 · 진행 현황")
tl = [("파일럿 50벽", "합격 94 %", "success"), ("환경 보정", "밀림 0.7 mm", "success"), ("동결·재확인", "10/10 합격", "success"),
      ("본 수집", "1,000벽", "success"), ("데이터셋", "16,000개", "success"), ("본 학습", "seed 1000", "primary")]
tw = (W - 2 * M + 0.08 * 5) / 6
for k, (a_, b_, col) in enumerate(tl):
    x_ = M + k * (tw - 0.08)
    cur = col == "primary"
    chevron(s, x_, T - 0.04, tw, 0.9, a_ + "\n" + b_, "primary" if cur else "soft", "white" if cur else "inkdeep", 16, first=(k == 0))
    st = "● 진행 중" if cur else "● 완료"
    text(s, x_ + 0.2, T + 0.9, tw - 0.4, 0.32, st, 14, "primary" if cur else "success", True, align=PP_ALIGN.CENTER)
NY = T + 1.32
nums = [("1,000", "합격 시연 벽", "시도 1,005 · 과부하 3 · 제외 2"), ("16,000", "에피소드", "벽돌 1장 = 1개"),
        ("283만", "프레임", "13.2 GB · 영상 전수 검사"), ("39분", "수집 시간", "작업자 32개 동시")]
nw = (W - 2 * M - 3 * 0.2) / 4
for k, (big, lab, sub) in enumerate(nums):
    nx = M + k * (nw + 0.2)
    card(s, nx, NY, nw, 1.28, fill="canvas", line="hair", radius=0.16)
    text(s, nx + 0.2, NY + 0.06, nw - 0.4, 0.62, big, 30, "primary", True, spacing=1.0, anchor=MSO_ANCHOR.MIDDLE)
    text(s, nx + 0.2, NY + 0.66, nw - 0.4, 0.3, f"**{lab}**", 15, "inkdeep")
    text(s, nx + 0.2, NY + 0.95, nw - 0.4, 0.3, sub, 14, "ink")
BY10 = NY + 1.45; BH10 = 6.92 - BY10
LW10 = 5.6
for j, (hd, a_, b_) in enumerate([("환경 보정 ① 손안 밀림", "원인: 계산 오류 (쥐는 힘 무관)", "조치: 마찰로 버틸 때만 집게에 고정"),
                                  ("환경 보정 ② G1 판정", "하중: 쥠 19.1 N vs 빈손 0 N", "집게 각도: 0.24 vs 0.70 rad")]):
    yy = BY10 + j * (BH10 / 2 + 0.05)
    hh = BH10 / 2 - 0.05
    card(s, M, yy, LW10, hh, fill="successsoft", line=None, radius=0.14)
    text(s, M + 0.2, yy, LW10 - 0.4, hh, [f"**{hd}**", a_, b_], 15, "inkdeep", spacing=1.05, after=1, anchor=MSO_ANCHOR.MIDDLE)
PX10 = M + LW10 + 0.25; PW10 = (W - M - PX10 - 0.2) / 2
ph(s, 10, PX10, BY10, PW10, BH10, "영상", "대본이 3단 벽 16장 쌓기", "새 환경 · 자유 시점 · 5배속 · 30초 이내", 15)
ph(s, 10, PX10 + PW10 + 0.2, BY10, PW10, BH10, "사진", "정책 입력 카메라 3대", "front · top · wrist 같은 순간 캡처 3장", 15)
footnote(s)

# ═══════════════════════════ 11 예상 기여
s = new(); T = chrome(s, 11, "정책·검측 역할 분담과 시방 기준 평가 틀 제시", "예상 기여")
cw11 = (W - 2 * M - 0.25) / 2; ch11 = 2.1
contrib = [("01", "정책·검측 역할 분담", ["검측 단계별 **합격률 기여** 정량화", "집기·운반: 정책 · 품질: 검측"]),
           ("02", "시방 기준 평가 틀", ["KCS 41 34 00 → **시뮬레이션 측정**", "학습 로봇을 **건설 품질**로 평가"]),
           ("03", "외부 계측 없는 검측", ["하중 · 집게 각도 · **작업대 카메라**", "현장 재계측 부담 축소 근거"]),
           ("04", "공개 자산", ["MuJoCo 환경 · 코드", "합격 시연 **벽 1,000개** 데이터셋"])]
for i, (num, hd, lines) in enumerate(contrib):
    r_, c_ = divmod(i, 2)
    cx = M + c_ * (cw11 + 0.25); cy = T + r_ * (ch11 + 0.22)
    card(s, cx, cy, cw11, ch11, fill="canvas", line="hair", radius=0.2)
    text(s, cx + 0.3, cy + 0.2, 1.3, 0.9, num, 40, "primary", True, spacing=1.0)
    text(s, cx + 1.6, cy + 0.28, cw11 - 1.9, 0.5, f"**{hd}**", 21, "inkdeep")
    text(s, cx + 1.6, cy + 0.9, cw11 - 1.9, 1.05, lines, 16, "ink", spacing=1.1, after=4)
BY11 = T + 2 * ch11 + 0.22 + 0.22
card(s, M, BY11, W - 2 * M, 6.92 - BY11, fill="soft", line=None, radius=0.16)
text(s, M + 0.3, BY11, W - 2 * M - 0.6, 6.92 - BY11, "기여의 성격: 새 알고리즘이 아닌 **단계별 분해와 정량화** · 결과는 시뮬레이션 범위 안에서 주장", 17, "inkdeep", align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)

# ═══════════════════════════ 12 추후 일정
s = new(); T = chrome(s, 12, "11/10 카메라 검측 연결 · 12/8 8조건 결과 보고", "추후 일정")
import datetime as dt
d0 = dt.date(2026, 10, 19); d1 = dt.date(2026, 12, 10)
GX = M + 3.05; GWd = W - M - GX; span = (d1 - d0).days


def gx(d):
    return GX + GWd * (d - d0).days / span


AXY = T + 0.05
for d in [dt.date(2026, 10, 19), dt.date(2026, 10, 26), dt.date(2026, 11, 2), dt.date(2026, 11, 9), dt.date(2026, 11, 16),
          dt.date(2026, 11, 23), dt.date(2026, 11, 30), dt.date(2026, 12, 7)]:
    text(s, gx(d) - 0.4, AXY, 0.8, 0.3, f"{d.month}/{d.day}", 14, "charcoal", True, align=PP_ALIGN.CENTER)
    l_ = s.shapes.add_connector(1, Inches(gx(d)), Inches(AXY + 0.34), Inches(gx(d)), Inches(6.2)); l_.line.color.rgb = RGB["hairsoft"]; l_.line.width = Pt(0.75)
tasks = [("본 학습 (seed 1000)", dt.date(2026, 10, 19), dt.date(2026, 10, 24), "primary", "진행 중"),
         ("G2·G3 카메라 연결", dt.date(2026, 10, 22), dt.date(2026, 11, 4), "inkdeep", ""),
         ("학습 seed 2000 · 3000", dt.date(2026, 10, 25), dt.date(2026, 11, 8), "charcoal", ""),
         ("검측 문턱 동결 (검증 배치)", dt.date(2026, 11, 3), dt.date(2026, 11, 9), "inkdeep", ""),
         ("8조건 본시험 (시험 배치)", dt.date(2026, 11, 10), dt.date(2026, 11, 27), "inkdeep", ""),
         ("분석 · 보고서", dt.date(2026, 11, 24), dt.date(2026, 12, 7), "charcoal", "")]
RY = AXY + 0.5; RH = 0.62
for k, (lab, a_, b_, col, tag) in enumerate(tasks):
    yy = RY + k * RH
    text(s, M, yy, 3.0, 0.46, lab, 15, "inkdeep", True, anchor=MSO_ANCHOR.MIDDLE)
    x0, x1 = gx(a_), gx(b_)
    card(s, x0, yy + 0.07, max(0.3, x1 - x0), 0.34, fill=col, line=None, radius=0.17)
    if tag:
        text(s, x1 + 0.08, yy, 1.4, 0.46, tag, 14, "primary", True, anchor=MSO_ANCHOR.MIDDLE)
for d, lab in [(dt.date(2026, 11, 10), "중간발표 2 · 11/10"), (dt.date(2026, 12, 8), "최종발표 · 12/8")]:
    l_ = s.shapes.add_connector(1, Inches(gx(d)), Inches(AXY + 0.34), Inches(gx(d)), Inches(6.25)); l_.line.color.rgb = RGB["critical"]; l_.line.width = Pt(2)
    lw_ = pw(lab, 13); lx_ = min(gx(d) - lw_ / 2, W - M - lw_)
    pill(s, lx_, 6.22, lw_, 0.32, lab, "critical", "white", 13)
l_ = s.shapes.add_connector(1, Inches(gx(d0) + 0.02), Inches(AXY + 0.34), Inches(gx(d0) + 0.02), Inches(6.25)); l_.line.color.rgb = RGB["primary"]; l_.line.width = Pt(2)
pill(s, M + 1.5, 6.22, 1.1, 0.32, "오늘 10/19", "primary", "white", 13)
cy12 = 6.62
xx = M
for lab in ["자원: RTX 5090 1대", "학습 1회: 6~9시간", "평가: 벽당 30~105 s", "계획(안) · 회의 후 확정"]:
    wd = pw(lab, 14); pill(s, xx, cy12, wd, 0.34, lab, "soft", "inkdeep", 14); xx += wd + 0.14

# ═══════════════════════════ 13 부록 · 상세 세팅 ① 시뮬레이터·장면·데이터
s = new(); T = chrome(s, 13, "상세 세팅 ①: 시뮬레이터 · 장면 · 데이터", "부록 · 상세 실험 세팅")
TW13 = (W - 2 * M - 0.3) / 2
t1 = table(s, M, T - 0.04, TW13, [["장면", "설정"],
    ["시뮬레이터", "MuJoCo 3.13 · 물리 1 ms · 제어 20 Hz (목표 선형 보간)"],
    ["접촉", "elliptic 마찰 · impratio 10 · noslip 3"],
    ["로봇", "UR10e (MuJoCo Menagerie) · 받침대 0.6 m"],
    ["집게", "2F-140 (robosuite) · 마디 충돌 끔 · 쥠 약 45 N"],
    ["벽돌", "190×90×57 mm 콘크리트 · 2,000 kg/m³ · 마찰 0.6"],
    ["벽", "1단 온장 5 / 2단 반장+4+반장 / 3단 온장 5"],
    ["모르타르", "순응 접촉층 + 2 s 정지 후 고정"],
    ["잡기 고정", "마찰로 버틸 때만 (패드당 ≥ 20 N) · 과부하 시 해제"]],
    [1.35, 4.6], 14, row_h=0.42, head_h=0.38)
t2 = table(s, M + TW13 + 0.3, T - 0.04, TW13, [["데이터", "설정"],
    ["공급", "로봇 뒤 · ±10 mm · ±10° · 단마다 왼→오"],
    ["카메라", "front · top · wrist · RGB 128² · 20 Hz"],
    ["시연", "역기구학 대본 · 정상 시연만 · 재시도 없음"],
    ["선별", "시방 합격 벽만 · 과부하 해제 벽 제외"],
    ["규모", "벽 1,000개 (시도 1,005) · 에피소드 16,000"],
    ["프레임", "2,833,397 · 13.2 GB · 데이터 해시 기록"],
    ["시작값", "수집 710000~ · 검증 720000~ · 시험 730000~ (잠금)"],
    ["부가 기록", "하중 · 집게 각도 · 참값 자세 (정책 입력 아님)"]],
    [1.35, 4.6], 14, row_h=0.42, head_h=0.38)
NY13 = T - 0.04 + max(t1, t2) + 0.16
card(s, M, NY13, W - 2 * M, 6.92 - NY13, fill="orangesoft", line=None, radius=0.14)
text(s, M + 0.2, NY13, W - 2 * M - 0.4, 6.92 - NY13,
     "**단순화·한계**: 모르타르 침하 미반영 → ① 가로줄눈 구분력 낮음 · 잡기 고정은 계산 오류 대응용 단순화 · 결과는 시뮬레이션 범위", 15, "inkdeep", anchor=MSO_ANCHOR.MIDDLE)

# ═══════════════════════════ 14 부록 · 상세 세팅 ② 정책·학습·평가
s = new(); T = chrome(s, 14, "상세 세팅 ②: 정책 · 학습 · 평가 조건", "부록 · 상세 실험 세팅")
t3 = table(s, M, T - 0.04, TW13, [["정책 · 학습", "설정"],
    ["구현", "LeRobot 0.6.1 기본 설정 · 정책 코드 수정 없음"],
    ["ACT", "chunk 100 · 실행 100"],
    ["Diffusion", "horizon 64 · 실행 32 · 관측 2"],
    ["입력", "카메라 3대 (128²) + 관절 6 · 집게 7 + 목표 정보 5"],
    ["목표 정보", "도면 목표 x · y · z · yaw + 반장 여부"],
    ["출력", "관절 목표 6 + 집게 명령 1"],
    ["학습", "10만 스텝 · 배치 32 · 1만 스텝마다 저장 · 검증 분할 없음"],
    ["seed", "1000 진행 중 → 2000 · 3000 추가 · 마지막 체크포인트"]],
    [1.35, 4.6], 14, row_h=0.42, head_h=0.38)
t4 = table(s, M + TW13 + 0.3, T - 0.04, TW13, [["평가", "설정"],
    ["단위", "벽 1개 (16장) · 벽돌당 17 s"],
    ["순서", "성공 확인 없이 도면 순서대로 다음 벽돌"],
    ["G1", "1.5 cm 들고 정지 → 손목 하중 + 0.2 s 완전 닫힘 각도"],
    ["G2 · G3", "작업대 카메라 위치 추정 · G3 재배치 1회"],
    ["문턱", "검증 배치로 정해 동결 → 시험 배치에 그대로"],
    ["지표", "시방 합격 · 항목별 mm · 벽돌별 3D IoU"],
    ["통계", "같은 배치 짝 비교 · Wilson 95 % · 주효과 · 상호작용"],
    ["정답 좌표", "시연 생성 · 학습 라벨 · 채점에만"]],
    [1.35, 4.6], 14, row_h=0.42, head_h=0.38)
NY14 = T - 0.04 + max(t3, t4) + 0.16
card(s, M, NY14, W - 2 * M, 6.92 - NY14, fill="soft", line=None, radius=0.14)
text(s, M + 0.2, NY14, W - 2 * M - 0.4, 6.92 - NY14,
     "**학습량 근거**: 10만 스텝 × 32 ≈ 프레임 전체 1회 · 미니 학습(데이터 1/20)에서 손실 수렴 확인 · 두 정책 같은 학습량", 15, "inkdeep", anchor=MSO_ANCHOR.MIDDLE)

# ═══════════════════════════ 15 참고문헌
s = new(); T = chrome(s, 15, "참고문헌", "부록 · 참고문헌")
colw = (W - 2 * M - 0.3) / 2
per = len(REF_ORDER) // 2
for ci, sub in enumerate((REF_ORDER[:per], REF_ORDER[per:])):
    items = [f"[{REF_ORDER.index(k) + 1}] {REFS[k][1]}" for k in sub]
    text(s, M + ci * (colw + 0.3), T - 0.08, colw, 6.98 - T, items, 10, "ink", spacing=1.0, after=4)
text(s, M, 7.02, W - 2 * M - 0.85, 0.34, "서지 확인 2026-10-12 · 10-19 (출판사·Crossref·arXiv·학회 페이지) · preprint 표시는 동료심사 게재 미확인", 11, "charcoal", anchor=MSO_ANCHOR.MIDDLE)

assert len(prs.slides) == N_SLIDES, len(prs.slides)
prs.save(OUT)

# ── 미디어·채울 상자 txt
lines = ["진행 회의 (2026-10-19) 슬라이드: 넣은 사진·영상의 GitHub 위치와, 아직 채울 상자 목록", f"저장소: {REPO}  (브랜치 main)", ""]
lines += ["■ 채울 상자 (주황 점선 '사진 필요 / 영상 필요')", "  PowerPoint에서 상자를 지우고 그 자리에 넣으면 됨. 아래 경로로 저장소에 올려 주시면 빌더로 다시 만들 수도 있음:",
          "  01_사기설/진행보고/도구/자산/채움_<쪽>_<번호>.png 또는 .mp4", ""]
for page, kind, title, desc in PH:
    lines.append(f"  [{page}쪽] ({kind}) {title} — {desc.replace(chr(10), ' / ')}")
lines += ["", "■ 이미 넣은 사진·영상"]
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
    lines.append("")
lines += ["[차트·도식]", "  8쪽 막대그래프, 2쪽 계단 그림, 9쪽 벽 정면도, 12쪽 일정표는 PowerPoint 도형·차트라 별도 파일 없음(슬라이드에서 편집 가능).",
          "", "[생성 스크립트]", "  01_사기설/진행보고/도구/build_진행회의_20261019.py"]
open(TXT, "w", encoding="utf-8").write("\n".join(lines))
print("saved", OUT, len(prs.slides), "slides;", len(MEDIA), "media;", len(PH), "placeholders; refs", len(REF_ORDER))
