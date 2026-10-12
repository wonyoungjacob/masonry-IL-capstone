# -*- coding: utf-8 -*-
"""중간발표 1 · 261012 랩미팅.
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
N_SLIDES = 15
SECTIONS = ["개요", "선행", "변경", "방법", "결과", "한계", "계획", "부록"]
ACTIVE = {2: "개요", 3: "선행", 4: "변경", 5: "방법", 6: "방법", 7: "결과", 8: "결과", 9: "결과", 10: "한계", 11: "한계", 12: "계획", 13: "부록", 14: "부록", 15: "부록"}
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
    text(slide, M, 0.1, 3.2, NAV_H - 0.1, "14조 · 랩미팅 2026.10.12", 13, "inkdeep", True, anchor=MSO_ANCHOR.MIDDLE)
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



# ── 랩미팅판 인용 (2026-10-12 확인: 출판사·Crossref·arXiv·학회 페이지). 번호는 슬라이드에 처음 나온 순서
REFS = {
    "labor": ("건설근로자공제회 2025", "건설근로자공제회 (2025). 2026년 건설근로자 수급전망."),
    "giftthaler": ("Giftthaler et al. 2017", "Giftthaler, M., Sandy, T., Dörfler, K., et al. (2017). Mobile robotic fabrication at 1:1 scale: The In situ Fabricator. Construction Robotics, 1, 3–14. doi:10.1007/s41693-017-0003-5"),
    "dorfler": ("Dörfler et al. 2016", "Dörfler, K., Sandy, T., Giftthaler, M., et al. (2016). Mobile robotic brickwork. Robotic Fabrication in Architecture, Art and Design 2016, 204–217. doi:10.1007/978-3-319-26378-6_15"),
    "argall": ("Argall et al. 2009", "Argall, B. D., Chernova, S., Veloso, M., & Browning, B. (2009). A survey of robot learning from demonstration. Robotics and Autonomous Systems, 57(5), 469–483. doi:10.1016/j.robot.2008.10.024"),
    "zhao": ("Zhao et al. 2023 (ACT)", "Zhao, T. Z., Kumar, V., Levine, S., & Finn, C. (2023). Learning fine-grained bimanual manipulation with low-cost hardware. RSS XIX. doi:10.15607/RSS.2023.XIX.016"),
    "chi": ("Chi et al. 2023 (Diffusion Policy)", "Chi, C., Feng, S., Du, Y., et al. (2023). Diffusion Policy: Visuomotor policy learning via action diffusion. RSS XIX. doi:10.15607/RSS.2023.XIX.026"),
    "ross": ("Ross et al. 2011 (DAgger)", "Ross, S., Gordon, G., & Bagnell, J. A. (2011). A reduction of imitation learning and structured prediction to no-regret online learning. AISTATS, PMLR 15, 627–635."),
    "dehaan": ("de Haan et al. 2019", "de Haan, P., Jayaraman, D., & Levine, S. (2019). Causal confusion in imitation learning. NeurIPS 32. arXiv:1905.11979"),
    "belkhale": ("Belkhale et al. 2023", "Belkhale, S., Cui, Y., & Sadigh, D. (2023). Data quality in imitation learning. NeurIPS 36. arXiv:2306.02437"),
    "chen26": ("Chen et al. 2026", "Chen, D., Tang, K., Zhang, Y., Kosuge, K., & Hirata, Y. (2026). Phase-conditioned imitation learning with autonomous failure recovery for robust deformable object manipulation. IEEE/ASME T-Mech (accepted). arXiv:2605.29407"),
    "huang": ("Huang et al. 2027 (online 2026)", "Huang, L., Yang, X., Yan, Q., & Zou, Z. (2027). Vision-language model-based demonstrators for imitation learning in construction robotic timber assembly. J. Comput. Civ. Eng., 41(1), 04026116. doi:10.1061/JCCEE5.CPENG-7917"),
    "osa": ("Osa et al. 2018", "Osa, T., Pajarinen, J., Neumann, G., Bagnell, J. A., Abbeel, P., & Peters, J. (2018). An algorithmic perspective on imitation learning. Foundations and Trends in Robotics, 7(1–2), 1–179. doi:10.1561/2300000053"),
    "kober": ("Kober et al. 2013", "Kober, J., Bagnell, J. A., & Peters, J. (2013). Reinforcement learning in robotics: A survey. IJRR, 32(11), 1238–1274. doi:10.1177/0278364913495721"),
    "amodei": ("Amodei et al. 2016", "Amodei, D., Olah, C., Steinhardt, J., Christiano, P., Schulman, J., & Mané, D. (2016). Concrete problems in AI safety. arXiv:1606.06565"),
    "tao": ("Tao et al. 2026", "Tao, X., Wang, Y., Zhu, B., et al. (2026). Vision-driven state-space imitation learning for quadrotor navigation in infrastructure inspection. Computer-Aided Civil and Infrastructure Engineering, 46, 100030."),
    "liang": ("Liang et al. 2022", "Liang, C.-J., Kamat, V. R., Menassa, C. C., & McGee, W. (2022). Trajectory-based skill learning for overhead construction robots using generalized cylinders with orientation. J. Comput. Civ. Eng., 36(2), 04021036."),
    "kelly": ("Kelly et al. 2019 (HG-DAgger)", "Kelly, M., Sidrane, C., Driggs-Campbell, K., & Kochenderfer, M. J. (2019). HG-DAgger: Interactive imitation learning with human experts. ICRA, 8077–8083. doi:10.1109/ICRA.2019.8793698"),
    "johns": ("Johns 2021", "Johns, E. (2021). Coarse-to-fine imitation learning: Robot manipulation from a single demonstration. ICRA, 4613–4619. doi:10.1109/ICRA48506.2021.9560942"),
    "hsu": ("Hsu et al. 2024", "Hsu, K.-C., Hu, H., & Fisac, J. F. (2024). The safety filter: A unified view of safety-critical control in autonomous systems. Annu. Rev. Control Robot. Auton. Syst., 7, 47–72. doi:10.1146/annurev-control-071723-102940"),
    "agia": ("Agia et al. 2025 (Sentinel)", "Agia, C., Sinha, R., Yang, J., et al. (2025). Unpacking failure modes of generative policies: Runtime monitoring of consistency and progress. CoRL 2024, PMLR 270, 689–723. arXiv:2410.04640"),
    "faild": ("Xu et al. 2025 (FAIL-Detect)", "Xu, C., Nguyen, T. K., Dixon, E., et al. (2025). Can we detect failures without failure data? Uncertainty-aware runtime failure detection for imitation learning policies. RSS 2025. arXiv:2503.08558"),
    "rewind": ("Zheng et al. 2026 (Rewind-IL)", "Zheng, G., Seenivasan, S., Johnson-Roberson, M., & Zhi, W. (2026). Rewind-IL: Online failure detection and state respawning for imitation learning. IEEE RA-L (early access). doi:10.1109/LRA.2026.3734897"),
    "resip": ("Ankile et al. 2024 (ResiP)", "Ankile, L., Simeonov, A., Shenfeld, I., Torne, M., & Agrawal, P. (2024). From imitation to refinement: Residual RL for precise assembly. arXiv:2407.16677 (preprint)"),
    "decor": ("Yuan et al. 2025 (Policy Decorator)", "Yuan, X., Mu, T., Tao, S., Fang, Y., Zhang, M., & Su, H. (2025). Policy Decorator: Model-agnostic online refinement for large policy model. ICLR 2025. arXiv:2412.13630"),
    "ibrahimov": ("Ibrahimov et al. 2026", "Ibrahimov, R., Mozaffari, S., & Adel, A. (2026). Contact-rich robotic manipulation in construction via zero-shot learning: A diffusion policy-guided adaptive control. arXiv:2608.22100 (preprint)"),
    "brickcraft": ("Yu et al. 2026 (BrickCraft)", "Yu, J., Li, B., Tang, Z., et al. (2026). BrickCraft: Visuomotor skill composition with situated manual guidance for long-horizon interlocking brick assembly. arXiv:2605.07605 (preprint)"),
    "rac": ("Hu et al. 2025 (RaC)", "Hu, Z., Wu, R., Enock, N., et al. (2025). RaC: Robot learning for long-horizon tasks by scaling recovery and correction. arXiv:2509.07953 (preprint)"),
    "litvak": ("Litvak et al. 2019", "Litvak, Y., Biess, A., & Bar-Hillel, A. (2019). Learning pose estimation for high-precision robotic assembly using simulated depth images. ICRA 2019. arXiv:1809.10699"),
    "hietanen": ("Hietanen et al. 2021", "Hietanen, A., Latokartano, J., Foi, A., et al. (2021). Benchmarking pose estimation for robot manipulation. Robotics and Autonomous Systems, 143, 103810. doi:10.1016/j.robot.2021.103810"),
    "mandlekar": ("Mandlekar et al. 2022 (robomimic)", "Mandlekar, A., Xu, D., Wong, J., et al. (2022). What matters in learning from offline human demonstrations for robot manipulation. CoRL 2021, PMLR 164, 1678–1690. arXiv:2108.03298"),
    "ks": ("KS L 4201", "국가기술표준원 (2022). KS L 4201 점토 벽돌."),
    "kcs": ("KCS 41 34 02", "국토교통부 (2021). KCS 41 34 02 벽돌공사, 건축공사 표준시방서."),
    "tms": ("Porter 2017 (TMS 402/602)", "Porter, G. (2017). The Acceptability of Masonry. Masonry Advisory Council. (TMS 402/602 세로줄눈 허용오차 −6.4/+9.5 mm)"),
    "labc": ("LABC 2021", "LABC Warranty (2021). Technical Manual v10, Section 1 Tolerances. (벽면 직진도 ±10 mm)"),
    "mujoco": ("Todorov et al. 2012 (MuJoCo)", "Todorov, E., Erez, T., & Tassa, Y. (2012). MuJoCo: A physics engine for model-based control. IEEE/RSJ IROS, 5026–5033."),
    "lerobot": ("LeRobot", "Hugging Face (2024–). LeRobot: State-of-the-art machine learning for real-world robotics. github.com/huggingface/lerobot (v0.6.1 사용)"),
}
REF_ORDER = []
_PENDING = []


def cite(*keys):
    """'[3,4]' 문자열. 처음 나온 순서로 번호."""
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
    """이 쪽에서 인용한 문헌을 맨 아래 한 줄로 (인용은 글씨 크기 규칙 예외)."""
    global _PENDING
    keys = list(_PENDING)
    _PENDING = []
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

# ═══════════════════════════ 1 표지
s = new()
text(s, 0.9, 1.2, 7.0, 0.35, "사회기반시스템종합설계 · 14조 · 랩미팅 2026.10.12 (중간발표 1 자료 기반)", 16, "charcoal", True)
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

footnote(s)

# ═══════════════════════════ 2 연구 개요
s = new(); T = chrome(s, 2, "연구 개요")
rows2 = [("연구 배경", ["기존 조적 로봇: **외부 계측 좌표** 의존 → 조건 바뀌면 재설정 " + cite("giftthaler", "dorfler"),
                      "모방학습: 카메라·관절값만 사용 → **재설정 불필요** " + cite("argall", "zhao", "chi")]),
         ("문제 정의", ["모방학습 정책: **실패 상태 대응 취약** " + cite("ross", "dehaan"),
                      "복구 학습 시 **정밀도 손실**, 미학습 시 **실패 인지 불가** " + cite("belkhale", "chen26")]),
         ("연구 목적", ["**정책은 그대로**, 실패 인지·보정은 **정책 밖 검측** " + cite("huang"),
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

footnote(s)

# ═══════════════════════════ 3 선행연구와 본 연구의 위치 (랩미팅 추가)
s = new(); T = chrome(s, 3, "선행연구 4갈래와 본 연구의 위치", "선행연구")
th = table(s, M, T, W - 2 * M, [["흐름", "대표 연구", "한 것", "본 연구와 차이"],
    ["모방학습 조작 정책", f"ACT {cite('zhao')} · Diffusion Policy {cite('chi')} · robomimic {cite('mandlekar')}", "시연만으로 정밀 조작 학습", "정책 성능이 아니라 **실패 대응을 어디에 둘지**"],
    ["실패 감지·복구", f"DAgger {cite('ross')} · Sentinel {cite('agia')} · FAIL-Detect {cite('faild')} · Rewind-IL {cite('rewind')}", "추가 라벨 수집, 실패 감지, 되감기 재시도", "범용 감지 · **배치 정밀 보정·필요 센싱 정량화 없음**"],
    ["학습 정책 + 외부 보정층", f"Coarse-to-Fine {cite('johns')} · ResiP {cite('resip')} · Policy Decorator {cite('decor')} · Safety filter {cite('hsu')}", "정밀 구간 분리, 잔차 보정, 외부 감시", "보정층을 RL로 학습(보상 필요) · 우리는 **규칙 검사 + 정보·정확도 분리**"],
    ["건설·조적 로봇", f"In situ Fabricator {cite('giftthaler')} · 자동 시연 IL {cite('huang')} · 적응제어 결합 {cite('ibrahimov')} · BrickCraft {cite('brickcraft')}", "외부 계측 정밀도, 자동 시연, 학습 + 적응제어", "Huang et al.이 **지각 기반 확인·폐루프 보정**을 향후 과제로 제시 → 우리가 시뮬레이션에서 수행"]],
    [1.75, 4.0, 2.55, 4.03], 15, row_h=0.5, head_h=0.4)
Y = T + th + 0.2
card(s, M, Y, W - 2 * M, 6.5 - Y, fill="primary", line=None, radius=0.2)
text(s, M + 0.2, Y + 0.08, W - 2 * M - 0.4, 6.5 - Y - 0.16,
     ["**찾지 못한 것**: 동결된 모방학습 정책에 **어떤 검사 단계**와 **어떤 센싱 정보·정확도**가 필요한지 단계별로 분리해 정량화한 연구",
      "→ 기여는 새 알고리즘이 아니라 **분해와 정량화** · 그리퍼 각도·하중 파지 확인은 산업 관행이라 새로움으로 주장하지 않음"],
     16, "white", spacing=1.15, after=4, anchor=MSO_ANCHOR.MIDDLE)
footnote(s)

# ═══════════════════════════ 3 수정 사항 · 진행상황
s = new(); T = chrome(s, 4, "설계수행계획서 대비 수정 사항 및 진행상황 보고")
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
use(4, "영상", V + "09_스크립트_정상시연_3카메라_2배속.mp4", "역기구학 대본의 시연 수집 (앞·위·손목 카메라, 2배속, 10 s)"); use(4, "사진", p09, "영상 포스터 프레임")
text(s, M, yv + hv + 0.04, VW, 0.58, ["**역기구학(IK)**: 목표 위치·자세 → **관절 각도 역산**", "벽돌 좌표로 집기·놓기 경로 자동 생성"], 14, "ink", spacing=1.1, after=1)
XC = M + VW + 0.2; WC = CWL - VW - 0.2
card(s, XC, Y, WC, 6.95 - Y, fill="soft", line=None, radius=0.16)
pill(s, XC + 0.15, Y + 0.15, pw("대본을 쓴 이유", 14), 0.32, "대본을 쓴 이유", "primary", "white", 14)
text(s, XC + 0.15, Y + 0.6, WC - 0.3, 6.95 - Y - 0.7, ["**숙련자 불필요**", "시연 무제한 생성", "**습관 차이 없음**", "조건 비교 공정", "**성공 자동 판정**", "근거 " + cite("huang", "kelly")], 15, "ink", spacing=1.08, after=1)
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

footnote(s)

# ═══════════════════════════ 4 연구 질문별 실험
s = new(); T = chrome(s, 5, "연구 질문 5개와 대응 실험", "성과 1 · 수행 실험")
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

footnote(s)

# ═══════════════════════════ 5 방법론 근거
s = new(); T = chrome(s, 6, "방법 선택 5가지의 근거와 택하지 않은 대안", "방법론 근거")
tiles = [("모방학습", ["보상 함수 설계 불필요 " + cite("osa", "huang"), "시연 재현 → 학습 효율 높음"], "강화학습 → 보상 설계 부담 " + cite("kober", "amodei")),
         ("시뮬레이션", ["같은 배치를 수백 회 반복", "실패 재현으로 원인 분리 " + cite("tao", "liang")], "실기 → 리셋·안전·계측 오차"),
         ("역기구학 대본", ["벽돌 좌표로 시연 자동 생성 " + cite("huang"), "성공 여부 자동 판정·선별"], "원격조작 → 숙련자 필요 " + cite("kelly")),
         ("검사는 정책 밖", ["정책 정밀도 그대로 보존", "검사 효과만 분리 " + cite("johns", "hsu")], "복구 시연 학습 → 정밀도 저하 " + cite("belkhale")),
         ("정답 좌표로 먼저 시험", ["영상 기반 시험 전 기준선 " + cite("huang"), "완벽한 위치일 때 상한 측정"], "바로 카메라 → 오차 원인 혼재")]
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

footnote(s)

# ═══════════════════════════ 6 딜레마 영상
def cond(slide, x, y, w, label, h=0.4):
    """실험 조건 표기 띠: 결과 수치마다 붙인다."""
    card(slide, x, y, w, h, fill="soft", line=None, radius=0.12)
    text(slide, x + 0.12, y, w - 0.24, h, "**조건** " + label, 14, "charcoal", anchor=MSO_ANCHOR.MIDDLE)


def placeholder(slide, x, y, w, h, title, sub):
    shp = rect(slide, x, y, w, h, "soft", "hair", radius=0.12, line_w=1.5)
    shp.line.dash_style = 4
    text(slide, x + 0.15, y + h / 2 - 0.42, w - 0.3, 0.84, [f"**{title}**", sub], 15, "charcoal", align=PP_ALIGN.CENTER, spacing=1.1, after=2)


s = new(); T = chrome(s, 7, "복구 미학습은 실패를 모르고, 복구 학습은 더듬거림", "성과 2 · 핵심 결과 ①")
LW6 = 4.25; XR6 = M + LW6 + 0.3; WR6 = W - M - XR6
# ① 왼쪽
card(s, M, T - 0.06, LW6, 0.46, fill="critical", line=None, radius=0.12)
text(s, M + 0.15, T - 0.06, LW6 - 0.3, 0.46, "딜레마 ①  복구를 가르치지 않으면 " + cite("ross", "rewind"), 16, "white", True, anchor=MSO_ANCHOR.MIDDLE)
VH6 = 2.75
vx, vy, vw, vh = movie(s, V + "21_빈손운반_재현_seed40000.mp4", A9 + "poster_21.png", M, T + 0.5, LW6, VH6)
use(7, "영상", V + "21_빈손운반_재현_seed40000.mp4", "딜레마 ①: 집지 못하고도 그대로 운반"); use(7, "사진", A9 + "poster_21.png", "포스터 프레임")
text(s, M, vy + vh + 0.06, LW6, 0.36, "집지 못하고도 그대로 운반 · 실패 유형 재현", 16, "inkdeep", True)
text(s, M, vy + vh + 0.46, LW6, 0.8, ["정책은 **실패를 알아채지 못한 채** 다음 동작으로", "정책 단독 완성: Diffusion **35%** · ACT **0%**"], 15, "ink", spacing=1.12, after=2)
cond(s, M, 6.55, LW6, "실험 3 · 넓은 배치 · 정책 단독 · 시험 배치")
# ② 오른쪽: 같은 조건 비교
card(s, XR6, T - 0.06, WR6, 0.46, fill="critical", line=None, radius=0.12)
text(s, XR6 + 0.15, T - 0.06, WR6 - 0.3, 0.46, "딜레마 ②  복구를 가르치면 — 학습 데이터만 다름 " + cite("belkhale", "chen26"), 16, "white", True, anchor=MSO_ANCHOR.MIDDLE)
hw6 = (WR6 - 0.25) / 2
A15 = D1 + "도구/v15_자산/"
vh2 = 0
for k, (vf, po, lab) in enumerate([("23_실험1_Diffusion_복구없이학습_배치10000_2.5배속_0-8s.mp4", A15 + "poster_23.png", "딜레마 ②: 복구 없이 학습한 Diffusion (같은 배치, 0~8 s)"),
                                   ("24_실험1_Diffusion_복구섞어학습_배치10000_2.5배속.mp4", A15 + "poster_24.png", "딜레마 ②: 복구 시연을 섞어 학습한 Diffusion (같은 배치)")]):
    _, _, _, hh = movie(s, V + vf, po, XR6 + k * (hw6 + 0.25), T + 0.5, hw6, VH6)
    vh2 = max(vh2, hh)
    use(7, "영상", V + vf, lab); use(7, "사진", po, "포스터 프레임")
yb = T + 0.5 + vh2 + 0.08
for k, (hd, data, big, sub, col) in enumerate([
        ("복구 없이 학습", ["학습 데이터: **정상 시연 119개만**", "벽돌이 어긋난 상황은 본 적 없음"], "90%", "평면 오차 2.6 mm · 깔끔하게 놓음", "success"),
        ("복구 섞어 학습", ["정상 시연 119개 + **복구 시연** 추가", "밀친 벽돌을 다시 집어 고치는 시연"], "2%", "평면 오차 6.3 mm · 다 놓고도 더듬거림", "critical")]):
    cx = XR6 + k * (hw6 + 0.25)
    card(s, cx, yb, hw6, 6.45 - yb, fill="canvas", line=col, radius=0.18)
    text(s, cx + 0.15, yb + 0.06, hw6 - 0.3, 0.32, hd, 16, col, True)
    text(s, cx + 0.15, yb + 0.4, hw6 - 0.3, 0.62, data, 15, "ink", spacing=1.06, after=1)
    text(s, cx + 0.15, yb + 1.06, 1.3, 0.55, big, 28, col, True, spacing=1.0, anchor=MSO_ANCHOR.MIDDLE)
    text(s, cx + 1.4, yb + 1.06, hw6 - 1.55, 0.55, "완성률 (100회)", 15, "charcoal", True, anchor=MSO_ANCHOR.MIDDLE)
    text(s, cx + 0.15, yb + 1.66, hw6 - 0.3, 0.4, sub, 15, "ink")
cond(s, XR6, 6.55, WR6, "실험 1 · 좁은 배치 · Diffusion · 완성률 각 100회 · 영상은 같은 배치(번호 10000) 예시")

footnote(s)

# ═══════════════════════════ 7 핵심 결과 ② 검사 효과
s = new(); T = chrome(s, 8, "정책 밖 검사로 완성률 2배 이상 회복", "성과 2 · 핵심 결과 ②")
LW8 = 5.95
for k, (hd, big, fill, ci) in enumerate([("Diffusion Policy · A → D", "35% → 75%", "primary", "95% CI 22–50 → 60–86%"), ("ACT · A → D", "0% → 54%", "inkdeep", "95% CI 0–7 → 40–67%")]):
    cx = M + k * (LW8 / 2 + 0.08)
    card(s, cx, T, LW8 / 2 - 0.08, 1.5, fill=fill, line=None, radius=0.26)
    text(s, cx + 0.18, T + 1.08, LW8 / 2 - 0.4, 0.34, ci, 14, "white", True)
    text(s, cx + 0.18, T + 0.1, LW8 / 2 - 0.4, 0.34, hd, 15, "white", True)
    text(s, cx + 0.18, T + 0.46, LW8 / 2 - 0.3, 0.65, big, 27, "white", True, spacing=1.0)
Y = T + 1.62
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

footnote(s)

# ═══════════════════════════ 8 보조 검증: 필요한 정확도 + 카메라 (v13의 8·9쪽을 합침)
NOISE = dict(diff=(75, 60, 5), act=(54, 48, 10))
s = new(); T = chrome(s, 9, "위치 오차 평균 5 mm면 효과 소멸, 카메라 추정은 평균 0.43 mm", "성과 3 · 보조 검증")
GAP8 = 0.36
CWs = [4.4, 3.75, W - 2 * M - 4.4 - 3.75 - 2 * GAP8]
XS = [M, M + CWs[0] + GAP8, M + CWs[0] + CWs[1] + 2 * GAP8]
for k, lab in enumerate(["①  위치가 틀리면", "②  카메라로 추정하면", "③  검사에 넣으면"]):
    card(s, XS[k], T - 0.06, CWs[k], 0.44, fill="inkdeep", line=None, radius=0.12)
    text(s, XS[k] + 0.14, T - 0.06, CWs[k] - 0.28, 0.44, lab, 16, "white", True, anchor=MSO_ANCHOR.MIDDLE)
    if k < 2:
        arrow_right(s, XS[k] + CWs[k] + 0.04, T + 0.01, GAP8 - 0.08, 0.28)
Y0 = T + 0.48; YB = 6.4
# ① 측정 오차 주입
x, w = XS[0], CWs[0]
card(s, x, Y0, w, 0.96, fill="primarysoft", line=None, radius=0.16)
text(s, x + 0.12, Y0 + 0.03, w - 0.24, 0.92,
     ["**측정 오차** = 검사가 믿는 중심 − 실제 중심", "중심 x·y·z에 평균 0·표준편차 σ 무작위 오차",
      "σ 2 → 평면 평균 **2.5 mm** · σ 4 → **5.0 mm**"], 15, "inkdeep", spacing=1.08, after=2)
ch8 = line_chart(s, x, Y0 + 1.0, w, 2.38, ["σ 0 (없음)", "σ 2 (2.5 mm)", "σ 4 (5.0 mm)"],
                 [("Diffusion Policy", NOISE["diff"], "primary"), ("ACT", NOISE["act"], "orange")], "주입한 측정 오차 (평면 평균)")
dl = ch8.plots[0].series[1].data_labels
dl.show_value = True; dl.position = XL_LABEL_POSITION.BELOW; dl.font.size = Pt(14); dl.font.bold = True
dl.number_format = '0"%"'; dl.number_format_is_linked = False
try:
    pt = ch8.plots[0].series[1].points[2].data_label; pt.position = XL_LABEL_POSITION.RIGHT
    pt.has_text_frame = True; pt.text_frame.text = f"{NOISE['act'][2]}%"
    for r_ in pt.text_frame.paragraphs[0].runs:
        _font(r_, 14, "inkdeep", True)
except Exception as ex:
    print('point label', ex)
dd, aa = NOISE["diff"], NOISE["act"]
yc = Y0 + 3.42
card(s, x, yc, w, YB - yc, fill="soft", line=None, radius=0.16)
text(s, x + 0.12, yc + 0.04, w - 0.24, YB - yc - 0.08,
     ["5 mm **효과 소멸** (두 정책 p<0.001)", "2.5 mm는 **Diffusion만 유의** (p=0.03)", "→ 평균 2.5 mm 이내 권장 " + cite("litvak", "hietanen")], 15, "ink", spacing=1.06, after=1, anchor=MSO_ANCHOR.MIDDLE)
# ② 카메라 추정
x, w = XS[1], CWs[1]
text(s, x, Y0, w, 0.62, ["**작업대 위 고정 카메라** 1대", "컬러+깊이 영상만으로 벽돌 중심 계산"], 15, "ink", spacing=1.08, after=1)
pimg = A9 + "p08_perception.png"
pw_, ph_ = picture(s, pimg, x, Y0 + 0.66, w=w)
use(9, "사진", D1 + "근거_rq4/perception_demo.png", "카메라 위치 추정 결과 3컷 원본"); use(9, "사진", pimg, "둥근 모서리판")
text(s, x, Y0 + 0.68 + ph_, w, 0.3, "노랑 = 추정 윤곽 · 빨강 = 실제 중심", 14, "charcoal", True)
yc = Y0 + 0.68 + ph_ + 0.36
card(s, x, yc, w, YB - yc, fill="primary", line=None, radius=0.22)
text(s, x + 0.16, yc + 0.08, w - 0.32, 0.32, "카메라 추정 평면 중심 오차", 15, "white", True)
text(s, x + 0.16, yc + 0.4, w - 0.32, 0.6, "평균 0.43 mm", 28, "white", True, spacing=1.0)
text(s, x + 0.16, yc + 1.0, w - 0.32, YB - yc - 1.05, ["95%가 0.96 mm 이내 · 1,963회", "**기준 2.5 mm의 약 1/6**"], 15, "white", spacing=1.1, after=2)
# ③ 검사에 넣은 결과
x, w = XS[2], CWs[2]
text(s, x, Y0, w, 0.62, ["역기구학 대본 + 검사 3단계", "검사가 쓰는 위치만 바꿔 비교"], 15, "ink", spacing=1.08, after=1)
th = table(s, x, Y0 + 0.7, w, [["검사가 쓴 위치", "검증 40", "시험 50"],
                               ["정답 좌표", "38", "48"],
                               ["**카메라 추정**", "**35**", "**45**"]],
           [1.6, 1.0, 1.0], 16, row_h=0.5, head_h=0.4, align_c=(1, 2), bold_col0=False)
yc = Y0 + 0.7 + th + 0.16
card(s, x, yc, w, YB - yc, fill="primarysoft", line=None, radius=0.18)
text(s, x + 0.14, yc + 0.06, w - 0.28, YB - yc - 0.12,
     ["**정답 좌표와 2~3회 차이**", "차이 유의하지 않음 (p=0.25)", "학습 정책 + 카메라는 평가 중"], 16, "inkdeep", spacing=1.12, after=4, anchor=MSO_ANCHOR.MIDDLE)
cond(s, M, 6.55, CWs[0] + GAP8 / 2, "① 정책 + 검사 D · 시험 배치 40·48회")
cond(s, XS[1] - GAP8 / 2 + 0.06, 6.55, W - M - XS[1] + GAP8 / 2 - 0.06, "②③ 역기구학 대본 + 검사 · 카메라 측정 1,963회 · 검증 40 · 시험 50 배치")

footnote(s)

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
                          ["모르타르", "순응층 · 2 s 뒤 고정", "부착 · 경화 · 편차 " + cite("kcs"), "**가정 명시, 벽체서 재검토**"],
                          ["규모·장비", "축소 벽돌 3개 · 소형 팔", "실척 벽체 · 산업용 팔", "**대형 환경 구축 중**"],
                          ["센서", "잡음 없는 힘 센서", "잡음 · 지연", "**잡음 민감도 측정**"],
                          ["자재", "동일 치수 강체", "치수 편차 · 파손 " + cite("ks"), "**치수 편차 별도 실험**"]],
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

footnote(s)

# ═══════════════════════════ 11 랩미팅 논점: 타당성 점검 (랩미팅 추가)
s = new(); T = chrome(s, 11, "랩미팅 논점: 타당성 위협 6가지와 대응", "한계 · 타당성 점검")
table(s, M, T, W - 2 * M, [["위협", "내용", "대응 (중간발표 2까지)"],
    ["딜레마 조건 불일치", "① 실패 미인지는 넓은 배치(실험 2·3), ② 정밀도 손실은 좁은 배치(실험 1)에서 측정", "넓은 배치에서 복구 혼합 데이터로 재학습해 같은 조건 비교"],
    ["'단순 혼합'에 한정", f"복구 데이터를 구조화하면 기본 성능 손실이 없다는 보고 {cite('rac')}", "결론을 '복구 시연을 그냥 섞을 때'로 한정"],
    ["표본·통계", "조건당 40~48회, 조건 B·C는 학습 seed 1개 · 2.5 mm 하락은 Diffusion만 유의(p=0.03)", "seed 3개 × 100회, 신뢰구간·짝지은 검정 보고"],
    ["카메라 결과의 주체", "카메라 검사 결과는 역기구학 대본 기준", "학습 정책 + 카메라 22개 작업 (Ubuntu)"],
    ["평가 배치로 설정 조정", "둘째 벽돌 간격 0.5 mm를 검증·시험 배치 결과를 함께 보고 정함 → 낙관 편향 가능", "새 시험 배치(60000번대)로 재확인"],
    ["시뮬레이션 이상화·기준 축척", "카메라 잡음·보정 오차 없음, 모르타르 단순화 · 4.5 mm = 실척 9.5 mm × 0.47(팀 설정)", "렌더 잡음 주입 · 기준 3·6 mm로 재채점"]],
    [2.45, 5.45, 4.43], 15, row_h=0.5, head_h=0.4)
footnote(s)

# ═══════════════════════════ 10 향후 계획
s = new(); T = chrome(s, 12, "카메라 검측 완료 후 대형 로봇·벽체로 확장", "향후 계획")
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
use(12, "사진", G + "concept_ur5e_wall.png", "대형 환경 콘셉트 원본"); use(12, "사진", cimg, "크롭·둥근 모서리판")
yy = T + ch13 + 0.4
card(s, X13, yy, W13, 6.95 - yy, fill="primarysoft", line=None, radius=0.18)
text(s, X13 + 0.15, yy + 0.08, W13 - 0.3, 6.95 - yy - 0.15,
     ["**카메라 검측이란**", "정답 좌표 대신 **작업대 카메라 영상**으로 벽돌 위치를 추정해 검사에 사용", "**현재 상태**", "대본 기준 검증 완료", "학습 정책 적용 평가 중"],
     15, "inkdeep", spacing=1.1, after=2)

footnote(s)

# ═══════════════════════════ 11 부록: 재현 환경
s = new(); T = chrome(s, 13, "재현용 실험 환경: 시뮬레이터 · 데이터 · 모델 · 평가", "부록 · 재현 정보")
hw5 = (W - 2 * M - 0.3) / 2
t1 = table(s, M, T, hw5, [["항목", "설정"],
                          ["시뮬레이터", "MuJoCo 3.13 · 물리 1 ms · 제어 20 Hz " + cite("mujoco")],
                          ["로봇", "SO-ARM100 모델 · 팔 5관절 + 집게"],
                          ["벽돌", "90×42.6×27 mm · 1,800 kg/m³ " + cite("ks")],
                          ["모르타르", "4.7 mm 순응층 · 정착 2 s 뒤 고정"],
                          ["시연", "240개 (학습 200 · 검증 40) · 18.3 s"],
                          ["초기 배치", "위치 ±30 mm · 방향 ±60°"]],
           [1.5, 4.1], 16, row_h=0.5, head_h=0.42)
t2 = table(s, M + hw5 + 0.3, T, hw5, [["항목", "설정"],
                                      ["입력 → 출력", "카메라 3대 128² + 관절 6 → 관절 목표 6"],
                                      ["학습", "ACT 40k · Diffusion 60k 갱신 · 배치 32 " + cite("lerobot")],
                                      ["반복", "학습 seed 1000 · 1001 · 1002"],
                                      ["평가", "검증 40 · 시험 50 배치 · 1회 90 s"],
                                      ["성공 기준", "위치·높이 4.5 mm · 방향 5° · 기울기 10° " + cite("tms", "labc")],
                                      ["검사 문턱", "잡기 0.2 rad·0.9 N · 보정 2.5 mm · 재배치 4.5 mm"]],
           [1.5, 4.1], 16, row_h=0.5, head_h=0.42)
Y = T + max(t1, t2) + 0.25
hw_ = (W - 2 * M - 0.3) / 2
for k, (hd, val) in enumerate([("계산 환경", "RTX 5090 · PyTorch 2.11 · LeRobot 0.6.1"), ("코드·원자료", "GitHub 저장소 sim/ · 실험일지.md")]):
    cx = M + k * (hw_ + 0.3)
    card(s, cx, Y, hw_, 0.62, fill="soft", line=None, radius=0.14)
    text(s, cx + 0.16, Y + 0.06, hw_ - 0.3, 0.5, f"**{hd}**  {val}", 16, "ink", anchor=MSO_ANCHOR.MIDDLE)


footnote(s)

# ═══════════════════════════ 14·15 참고문헌 (랩미팅 추가)
half = (len(REF_ORDER) + 1) // 2
for pi, chunk in enumerate((REF_ORDER[:half], REF_ORDER[half:])):
    s = new(); T = chrome(s, 14 + pi, f"참고문헌 ({pi + 1}/2)", "부록 · 참고문헌")
    colw = (W - 2 * M - 0.3) / 2
    per = (len(chunk) + 1) // 2
    for ci, sub in enumerate((chunk[:per], chunk[per:])):
        items = [f"[{REF_ORDER.index(k) + 1}] {REFS[k][1]}" for k in sub]
        text(s, M + ci * (colw + 0.3), T - 0.05, colw, 6.95 - T, items, 10.5, "ink", spacing=1.05, after=5)
    if pi == 1:
        text(s, M, 7.02, W - 2 * M - 0.85, 0.34, "서지 확인 2026-10-12 (출판사·Crossref·arXiv·학회 페이지). preprint 표시는 동료심사 게재 미확인.", 11, "charcoal", anchor=MSO_ANCHOR.MIDDLE)

prs.save(OUT)

# ── 미디어 위치 txt
lines = ["중간발표 1 · 261012 랩미팅 슬라이드에 넣은 사진·영상의 GitHub 위치", f"저장소: {REPO}  (브랜치 main)", "",
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
lines += ["[차트·도식]", "  8·9쪽 그래프와 12쪽 간트는 PowerPoint 안에서 직접 그린 차트·도형이라 별도 파일이 없음 (슬라이드에서 데이터 편집 가능).",
          "  같은 내용의 이미지판: 01_사기설/중간발표1/그림/stages.png, noise.png, fig_gantt_priority.png", "",
          "[생성 스크립트]", "  01_사기설/중간발표1/도구/build_ppt_261012_랩미팅.py (이 슬라이드), 도구/미디어/*.py (영상 클립·렌더·도식)"]
open(TXT, "w", encoding="utf-8").write("\n".join(lines))
print("saved", OUT, len(prs.slides), "slides;", len(MEDIA), "media refs")
