# -*- coding: utf-8 -*-
"""KSARC 포스터 e판의 겉모양만 레퍼런스 포스터 형식으로 바꾼다 (2026-11-11, 윈도우 전용: PowerPoint 필요).

- 내용(글 · 숫자 · 그림 · 표)은 e판 pptx에서 그대로 가져온다. 글자를 새로 쓰지 않는다.
  바뀌는 글자는 제목 양식뿐이다: 절 제목 "1  제목" → "1. 제목", 표 제목 "표 1  …" → "표 1. …".
- 형식은 사용자가 준 레퍼런스(ksarc_포스터_v12.pdf, 강현준 · 김홍조 포스터)에서 읽은 값이다:
  한글 맑은 고딕 · 영문/숫자 Calibri, 절 제목 32 pt 굵게, 소제목 24 pt 굵게 남색, 본문 "•" + 굵은 남색 머리말,
  표 머리 줄 남색 바탕에 흰 굵은 글씨 · 줄마다 옅은 색 번갈아 · 첫 열 굵은 남색, 글 색 #243448 · 남색 #183D69.
- 본문 크기는 레퍼런스가 20 pt지만 e판 내용이 그 크기로는 들어가지 않는다. 그래서 두 단에 다 들어가는 가장 큰
  크기를 찾는다(--body로 고정할 수도 있다). 표 = 본문 × 0.875, 그림 · 표 제목 = 본문 × 0.8 (레퍼런스의 비율).
- 글 상자 높이는 어림하지 않고 PowerPoint가 잰 값(TextRange.BoundHeight, 표는 줄 높이를 줄여 맞춘 값)을 쓴다.
  그 높이로 개체를 위에서 아래로 다시 놓는다. 그림(PNG)은 크기 · 비율을 바꾸지 않는다.

실행 (저장소 루트, PowerShell):
  $env:PYTHONUTF8 = "1"
  python sim\\wall3\\poster_restyle_ksarc_20261111f.py --tag 20261111f
출력: 02_KSARC2026/KSARC2026_포스터_초안_<tag>.pptx, 포스터_초안_<tag>_PowerPoint.png, 포스터_초안_<tag>_배치.json
같은 이름이 있으면 덮어쓰지 않고 멈춘다.
"""
import argparse, json, os, re, shutil, sys, tempfile

from lxml import etree
from pptx import Presentation
from pptx.oxml.ns import qn

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(ROOT, "02_KSARC2026", "KSARC2026_포스터_초안_20261111e.pptx")

# ── 레퍼런스에서 읽은 형식
LATIN, EA = "Calibri", "맑은 고딕"
BODY, NAVY, GRAY = "243448", "183D69", "596879"
TH_FILL, BAND_A, BAND_B = "315F93", "F2F6FA", "FFFFFF"
SEC_PT, SUB_PT, REF_PT = 32, 24, 11                    # 절 제목 · 소제목 (레퍼런스 값), 참고문헌 (사용자: "조그맣게")
TITLE_PT, SUBTITLE_PT, TITLE_EN_PT = 44, 30, 40        # 제목 · 부제(레퍼런스에 없음, e판 값) · 영문 제목
NAME_PT, NAME_EN_PT, AFFIL_PT = 32, 22, 24             # 저자 · 영문 이름 · 소속 (레퍼런스 32 · 21.6 · 24)
LN_BODY, LN_TIGHT = 97, 95                             # 줄 간격 % (맑은 고딕 20 pt에서 줄 높이 약 26 pt = 레퍼런스)

CM = 28.3464567                                        # 1 cm = pt
LX, RX, CW = 1.78, 30.99, 26.6                         # 왼쪽 단 x, 오른쪽 단 x, 단 너비 (e판과 같음)
BAR_DX, BAR_H = 0.28, 1.90                             # 절 제목 띠: 본문보다 양쪽 0.28 cm 넓게, 높이 1.9 cm (레퍼런스 54 pt)
TOP, BOTTOM = 16.30, 83.05                             # 흰 단(15.79 ~ 83.42) 안에서 쓰는 범위
HEAD_BOTTOM = 14.14                                    # 머리 영역 끝
TAG_W, TAG_GAP = 3.5, 0.35                             # 1절 꼬리표 너비 · 간격
# 높이를 줄여 다시 그리는 그림 (여백만 줄어든다. 글자 크기 · 내용은 그대로). 도형 이름: (파일 이름, e판 높이 cm, 새 높이 cm)
REFIG = {"그림 122": ("그림2_검측단계_흐름도.png", 8.6, 7.4), "그림 131": ("그림4_평가기준_채움_완성_시방.png", 4.0, 3.6),
         "그림 137": ("그림6_시방항목_Full_FullG3.png", 10.2, 9.2)}

RPR_ORDER = ["ln", "noFill", "solidFill", "gradFill", "blipFill", "pattFill", "grpFill", "effectLst", "effectDag", "highlight",
             "uLnTx", "uLn", "uFillTx", "uFill", "latin", "ea", "cs", "sym", "hlinkClick", "hlinkMouseOver", "rtl", "extLst"]
PPR_ORDER = ["lnSpc", "spcBef", "spcAft", "buClrTx", "buClr", "buSzTx", "buSzPct", "buSzPts", "buFontTx", "buFont",
             "buNone", "buAutoNum", "buChar", "buBlip", "tabLst", "defRPr", "extLst"]


def _local(e):
    return etree.QName(e).localname


def _sort(parent, order):
    kids = sorted(parent, key=lambda e: order.index(_local(e)) if _local(e) in order else len(order))
    for k in list(parent):
        parent.remove(k)
    for k in kids:
        parent.append(k)


def run_color(r):
    rp = r.find(qn("a:rPr"))
    sf = rp.find(qn("a:solidFill")) if rp is not None else None
    return sf[0].get("val") if sf is not None and len(sf) else None


def run_bold(r):
    rp = r.find(qn("a:rPr"))
    return rp is not None and rp.get("b") == "1"


def style_run(r, size=None, bold=None, color=None, plain=False):
    rp = r.find(qn("a:rPr"))
    if rp is None:
        rp = r.makeelement(qn("a:rPr"), {}); r.insert(0, rp)
    if size is not None:
        rp.set("sz", str(int(round(size * 100))))
    if bold is not None:
        rp.set("b", "1" if bold else "0")
    if plain:                                           # 양식 절 제목의 그림자 · 윤곽선을 뺀다 (레퍼런스는 흰 글씨만)
        for t in ("a:effectLst", "a:ln"):
            for e in rp.findall(qn(t)):
                rp.remove(e)
    if color is not None:
        for e in rp.findall(qn("a:solidFill")):
            rp.remove(e)
        sf = etree.SubElement(rp, qn("a:solidFill")); etree.SubElement(sf, qn("a:srgbClr")).set("val", color)
    for t, face in (("a:latin", LATIN), ("a:ea", EA)):
        e = rp.find(qn(t))
        if e is None:
            e = etree.SubElement(rp, qn(t))
        for k in list(e.attrib):
            del e.attrib[k]
        e.set("typeface", face)
    _sort(rp, RPR_ORDER)


def style_par(p, ln=None, aft=None, bef=None, bullet=None, indent_pt=0.0, algn=None, end_size=None):
    pp = p.find(qn("a:pPr"))
    if pp is None:
        pp = p.makeelement(qn("a:pPr"), {}); p.insert(0, pp)
    if algn:
        pp.set("algn", algn)

    def rep(tag, child, val):
        for e in pp.findall(qn(tag)):
            pp.remove(e)
        if val is not None:
            etree.SubElement(etree.SubElement(pp, qn(tag)), qn(child)).set("val", str(int(val)))
    if ln is not None:
        rep("a:lnSpc", "a:spcPct", ln * 1000)
    if aft is not None:
        rep("a:spcAft", "a:spcPts", aft * 100)
    if bef is not None:
        rep("a:spcBef", "a:spcPts", bef * 100)
    if bullet is not None:
        for t in PPR_ORDER[3:14]:
            for e in pp.findall(qn("a:" + t)):
                pp.remove(e)
        if bullet:
            etree.SubElement(etree.SubElement(pp, qn("a:buClr")), qn("a:srgbClr")).set("val", NAVY)
            etree.SubElement(pp, qn("a:buSzPct")).set("val", "85000")
            etree.SubElement(pp, qn("a:buFont")).set("typeface", "Arial")
            etree.SubElement(pp, qn("a:buChar")).set("char", "•")
            pp.set("marL", str(int(indent_pt * 12700))); pp.set("indent", str(-int(indent_pt * 12700)))
        else:
            etree.SubElement(pp, qn("a:buNone"))
            pp.set("marL", "0"); pp.set("indent", "0")
    _sort(pp, PPR_ORDER)
    ep = p.find(qn("a:endParaRPr"))
    if ep is not None and end_size is not None:
        ep.set("sz", str(int(round(end_size * 100))))


def paras(sh):
    return sh._element.find(qn("p:txBody")).findall(qn("a:p"))


def runs(p):
    return p.findall(qn("a:r"))


def body_color(r):
    """e판의 색 → 레퍼런스의 색. 본문 속 굵은 글씨는 레퍼런스처럼 남색."""
    c = run_color(r)
    if c in ("FFFFFF", "bg1"):
        return None
    if c == "5B6370":
        return GRAY
    if c == "1B4F8F" or run_bold(r):
        return NAVY
    return BODY


def set_fill(sh, mapping):
    sp = sh._element.find(qn("p:spPr"))
    sf = sp.find(qn("a:solidFill")) if sp is not None else None
    if sf is not None and len(sf) and sf[0].get("val") in mapping:
        sf[0].set("val", mapping[sf[0].get("val")])


def redraw_figures(figd):
    """REFIG의 그림을 e판 스크립트의 그림 함수로 새 높이에 맞춰 다시 그린다 (결과 파일만 읽음, 시뮬레이션 없음)."""
    sim = os.path.join(ROOT, "sim")
    if sim not in sys.path:
        sys.path.insert(0, sim)
    os.environ.setdefault("WALL3_OUT", os.path.join(ROOT, "02_KSARC2026", "원자료_포스터d_20261111", "wall3"))
    os.environ.setdefault("MPLCONFIGDIR", os.path.join(tempfile.gettempdir(), "mpl"))
    from wall3 import poster_ksarc_20261111e as E
    from wall3 import primary_metrics_20261111 as pm
    res = pm.compute(); plt = E.mpl_setup()
    os.makedirs(figd)
    out = {}
    for shape, (fname, _, h) in REFIG.items():
        f = os.path.join(figd, fname)
        if fname.startswith("그림2"):
            E.fig_flow(f, CW, h, plt)
        elif fname.startswith("그림4"):
            E.fig_eval(f, CW, h, plt)
        else:
            E.fig_items(res, f, CW, h, plt)
        out[shape] = (f, h)
    return out


def restyle(src, dst, B, figs=None):
    """e판을 읽어 서식만 바꿔 dst에 쓴다. B = 본문 크기(pt). figs = 바꿔 넣을 그림 {도형 이름: (파일, 높이 cm)}.
    위치는 여기서 건드리지 않는다(layout에서)."""
    T = round(B * 0.875 * 2) / 2                         # 표 (레퍼런스 17.5 / 20)
    C = round(B * 0.8 * 2) / 2                           # 그림 · 표 제목 (레퍼런스 16 / 20)
    prs = Presentation(src); sl = prs.slides[0]
    for sh in sl.shapes:
        n = sh.name
        if sh.shape_type == 13:
            if figs and n in figs:                                          # 다시 그린 그림으로 바꿔 넣는다 (너비 그대로, 높이만)
                f, h = figs[n]
                _, rid = sl.part.get_or_add_image_part(f)
                blip = sh._element.find(".//" + qn("a:blip")); old = blip.get(qn("r:embed")); blip.set(qn("r:embed"), rid)
                sh.height = int(round(h * 360000))
                if old != rid:
                    sl.part.drop_rel(old)
            continue
        if getattr(sh, "has_table", False) and sh.has_table:
            tbl = sh._element.find(".//" + qn("a:tbl")); trs = tbl.findall(qn("a:tr"))
            for i, tr in enumerate(trs):
                tr.set("h", str(int((T * 1.33 + 5) * 12700)))               # 최소 줄 높이. 넘치면 PowerPoint가 키운다
                for j, tc in enumerate(tr.findall(qn("a:tc"))):
                    for p in tc.find(qn("a:txBody")).findall(qn("a:p")):
                        style_par(p, ln=100, end_size=T)
                        for r in runs(p):
                            if i == 0:
                                style_run(r, T, True, "FFFFFF")
                            else:
                                bold = run_bold(r)
                                style_run(r, T, bold, GRAY if run_color(r) == "5B6370" else (NAVY if bold else BODY))
                    pr = tc.find(qn("a:tcPr"))
                    sf = pr.find(qn("a:solidFill"))
                    if sf is not None and len(sf):
                        sf[0].set("val", TH_FILL if i == 0 else (BAND_A if i % 2 else BAND_B))
                    for t in ("a:lnL", "a:lnR", "a:lnT", "a:lnB"):
                        e = pr.find(qn(t))
                        if e is None:
                            continue
                        for k in list(e):
                            e.remove(k)
                        if t == "a:lnB" and i == len(trs) - 1:              # 표 맨 아래에만 남색 줄 (레퍼런스)
                            e.set("w", "12700")
                            etree.SubElement(etree.SubElement(e, qn("a:solidFill")), qn("a:srgbClr")).set("val", NAVY)
                        else:
                            etree.SubElement(e, qn("a:noFill"))
            continue
        if not sh.has_text_frame or not sh.text_frame.text.strip():
            continue
        ps = paras(sh)
        if n == "직사각형 8":                                                # 제목 · 부제 · 영문 제목
            for p, sz, b in zip(ps, (TITLE_PT, SUBTITLE_PT, TITLE_EN_PT), (True, False, False)):
                style_par(p, ln=100, end_size=sz)
                for r in runs(p):
                    style_run(r, sz, b)
            r = runs(ps[2])[0]; t = r.find(qn("a:t")); full = t.text      # 영문 제목을 "…Robot:" 뒤에서 줄바꿈 (글자는 그대로)
            k = full.find(": ")
            if k > 0:
                r2 = etree.fromstring(etree.tostring(r)); t.text = full[:k + 1]; r2.find(qn("a:t")).text = full[k + 2:]
                br = r.makeelement(qn("a:br"), {})
                rp = r.find(qn("a:rPr"))
                if rp is not None:
                    br.append(etree.fromstring(etree.tostring(rp)))
                r.addnext(br); br.addnext(r2)
        elif n == "Text Box 274":                                           # 저자
            for p, sz in zip(ps, (NAME_PT, NAME_EN_PT)):
                style_par(p, ln=110, end_size=sz)
                for r in runs(p):
                    style_run(r, sz)
        elif n == "Text Box 275":                                           # 소속
            for p in ps:
                style_par(p, ln=105, end_size=AFFIL_PT)
                for r in runs(p):
                    style_run(r, AFFIL_PT)
        elif n.startswith("절 제목"):                                        # "1  제목" → "1. 제목"
            for p in ps:
                for r in runs(p):
                    t = r.find(qn("a:t")); t.text = re.sub(r"^(\d+)\s+", r"\1. ", t.text)
                    style_run(r, SEC_PT, True, plain=True)
        elif n.startswith("소제목"):
            for p in ps:
                style_par(p, ln=100, end_size=SUB_PT)
                for r in runs(p):
                    t = r.find(qn("a:t")); t.text = re.sub(r"^(\d+\.\d+)\s+", r"\1 ", t.text)
                    style_run(r, SUB_PT, True, NAVY)
        elif n.startswith("1절 꼬리표"):
            set_fill(sh, {"1B4F8F": TH_FILL})
            for p in ps:
                style_par(p, ln=LN_TIGHT, end_size=B)
                for r in runs(p):
                    style_run(r, B, True, None if run_color(r) == "FFFFFF" else NAVY)
        elif re.match(r"1절 (빈틈|기여) 카드", n):
            for p in ps:
                style_par(p, ln=LN_TIGHT, end_size=B - 1)
                for r in runs(p):
                    style_run(r, B - 1, run_bold(r), body_color(r))
        elif n.startswith("1절 "):                                          # 1절 내용 줄 (연구 목적 강조 상자 포함)
            for p in ps:
                style_par(p, ln=LN_BODY, end_size=B)
                for r in runs(p):
                    style_run(r, B, run_bold(r), body_color(r))
        elif n in ("환경 글", "고찰 글", "결론 글"):                           # 본문: "•" + 굵은 남색 머리말
            for i, p in enumerate(ps):
                style_par(p, ln=LN_BODY, aft=0 if i == len(ps) - 1 else round(B * 0.22, 1), bullet=True, indent_pt=B, end_size=B)
                for r in runs(p):
                    style_run(r, B, run_bold(r), body_color(r))
        elif n == "표 1 제목":                                               # "표 1  …" → 굵은 "표 1." + 보통 글씨 (레퍼런스의 표 제목)
            p = ps[0]; r = runs(p)[0]; t = r.find(qn("a:t")); m = re.match(r"^(표\s*\d+)\s+(.*)$", t.text)
            style_par(p, ln=100, end_size=C)
            if m:
                r2 = etree.fromstring(etree.tostring(r)); t.text = m.group(1).replace("표", "표 ").replace("  ", " ") + "."
                r2.find(qn("a:t")).text = " " + m.group(2); r.addnext(r2)
                style_run(r, C, True, BODY); style_run(r2, C, False, BODY)
            else:
                style_run(r, C, True, BODY)
        elif n == "환경 그림 설명":
            for p in ps:
                style_par(p, ln=100, end_size=C)
                for r in runs(p):
                    style_run(r, C, False, BODY)
        elif n == "결과 표 각주":
            for i, p in enumerate(ps):
                style_par(p, ln=100, aft=0 if i == len(ps) - 1 else 2, end_size=max(REF_PT, C - 1))
                for r in runs(p):
                    style_run(r, max(REF_PT, C - 1), False, GRAY)
        elif n == "핵심 메시지":
            set_fill(sh, {"1B4F8F": TH_FILL})
            for p, sz in zip(ps, (B + 2, B + 5)):
                style_par(p, ln=100, end_size=sz)
                for r in runs(p):
                    style_run(r, sz, True)
        elif n == "감사의 글":
            for p in ps:
                style_par(p, ln=LN_BODY, end_size=B - 1)
                for r in runs(p):
                    style_run(r, B - 1, False, BODY)
        elif n == "참고문헌":
            for p in ps:
                style_par(p, ln=100, end_size=REF_PT)
                for r in runs(p):
                    style_run(r, REF_PT, run_bold(r), GRAY)
    prs.save(dst)
    return {"본문": B, "표": T, "그림·표 제목": C, "1절 카드": B - 1, "감사의 글": B - 1, "핵심 메시지": [B + 2, B + 5],
            "결과 표 각주": max(REF_PT, C - 1), "참고문헌": REF_PT, "절 제목": SEC_PT, "소제목": SUB_PT,
            "제목·부제·영문 제목": [TITLE_PT, SUBTITLE_PT, TITLE_EN_PT], "저자·영문 이름·소속": [NAME_PT, NAME_EN_PT, AFFIL_PT]}


# ───────────────────────────── 배치: PowerPoint가 잰 높이로 위에서 아래로 놓는다
# (종류, 도형 이름 또는 이름 머리, 앞 간격 cm, 남는 높이를 나눠 줄 자리인가)
LEFT = [("bar", "절 제목 101", 0.0, False), ("s1", None, 0.30, False),
        ("bar", "절 제목 121", 0.40, True), ("pic", "그림 122", 0.30, False), ("tbl", "검측 단계 표 123", 0.20, True),
        ("tbl", "연구 질문 표 124", 0.28, True),
        ("bar", "절 제목 125", 0.40, True), ("sub", "소제목 3.1", 0.22, False), ("pic", "그림 127", 0.05, False),
        ("txt", "환경 그림 설명", 0.03, False), ("txt", "환경 글", 0.08, True), ("sub", "소제목 3.2", 0.20, True), ("pic", "그림 131", 0.05, False)]
RIGHT = [("sub", "소제목 3.3", 0.0, False), ("pic", "그림 133", 0.05, False), ("txt", "표 1 제목", 0.22, True),
         ("tbl", "결과 표 135", 0.05, False), ("txt", "결과 표 각주", 0.05, False), ("pic", "그림 137", 0.22, True),
         ("bar", "절 제목 138", 0.40, True), ("txt", "고찰 글", 0.28, False),
         ("bar", "절 제목 140", 0.40, True), ("txt", "결론 글", 0.28, False), ("txt", "핵심 메시지", 0.22, True),
         ("bar", "절 제목 143", 0.40, True), ("txt", "감사의 글", 0.25, False), ("txt", "참고문헌", 0.12, True)]
S1_ROWS = [("연구 배경", [("txt", "1절 연구 배경")]),
           ("문제 정의", [("txt", "1절 문제 정의"), ("cards", "1절 빈틈 카드")]),
           ("연구 목적", [("txt", "1절 연구 목적")]),
           ("연구 방법", [("txt", "1절 연구 방법")]),
           ("검증 계획", [("txt", "1절 검증 계획")]),
           ("결과", [("pic", "그림 116")]),
           ("예상 기여", [("cards", "1절 기여 카드")])]
S1_ROW_GAP, S1_IN_GAP = 0.14, 0.10


def layout(path, save_as=None, png=None, max_extra=0.45):
    """path의 pptx를 PowerPoint로 열어 개체를 다시 놓는다. 돌려주는 값: 단 끝(cm), 개체별 위치, 머리 영역 끝."""
    import win32com.client
    names = [sh.name for sh in Presentation(path).slides[0].shapes]              # 파일에 적힌 이름 (PowerPoint는 양식 도형 이름을 영어로 돌려줌)
    app = win32com.client.Dispatch("PowerPoint.Application")
    pres = app.Presentations.Open(os.path.abspath(path), False, False, False)      # 읽기 전용 아님, 창 없이
    try:
        sl = pres.Slides(1)
        assert sl.Shapes.Count == len(names), (sl.Shapes.Count, len(names))
        S = {n: sl.Shapes(i + 1) for i, n in enumerate(names)}                    # 도형 순서로 짝을 맞춤

        def find(prefix):
            if prefix in S:
                return S[prefix]
            hit = [s for k, s in S.items() if k.startswith(prefix)]
            assert len(hit) == 1, (prefix, [h.Name for h in hit])
            return hit[0]

        def need(s, w=None):
            tf = s.TextFrame2
            tf.AutoSize = 0; tf.WordWrap = -1
            if w is not None:
                s.Width = w * CM
            return (tf.TextRange.BoundHeight + tf.MarginTop + tf.MarginBottom) / CM

        def table_h(s):
            t = s.Table
            for i in range(1, t.Rows.Count + 1):
                t.Rows(i).Height = 1                                              # 글이 들어가는 가장 작은 높이로 줄어든다
            return s.Height / CM

        pos = {}

        back = {id(v): k for k, v in S.items()}

        def put(s, x, y, h=None, w=None):
            s.Left = x * CM; s.Top = y * CM
            if w is not None:
                s.Width = w * CM
            if h is not None:
                s.Height = h * CM
            pos[back.get(id(s), s.Name)] = [round(x, 2), round(y, 2), round(s.Width / CM, 2), round(s.Height / CM, 2)]

        # ── 머리 영역: 제목 · 저자 · 소속을 차례로, 가운데에
        tb, ab, fb = S["직사각형 8"], S["Text Box 274"], S["Text Box 275"]
        hs = [need(tb, 51.4), need(ab, 51.4), need(fb, 57.4)]
        gap = 0.25
        y = max(0.55, (HEAD_BOTTOM - sum(hs) - 2 * gap) / 2 - 0.1)
        for s, h, x in zip((tb, ab, fb), hs, (4.0, 4.0, 1.0)):
            put(s, x, y, h); y += h + gap
        head_end = y - gap

        def s1(x, y):
            cx = x + TAG_W + TAG_GAP; cw = CW - TAG_W - TAG_GAP
            for label, parts in S1_ROWS:
                y0 = y; yy = y
                for kind, name in parts:
                    if kind == "txt":
                        s = find(name); h = need(s, cw) + 0.06; put(s, cx, yy, h); yy += h + S1_IN_GAP
                    elif kind == "pic":
                        s = find(name); put(s, cx, yy); yy += s.Height / CM + S1_IN_GAP
                    else:                                                         # 카드 3장: e판의 너비 비율 그대로, 높이는 가장 큰 것
                        cards = [S[f"{name} {i}"] for i in (1, 2, 3)]
                        ws = [c.Width / CM for c in cards]; g = (cw - sum(ws)) / 2
                        h = max(need(c) for c in cards) + 0.06; xx = cx
                        for c, w_ in zip(cards, ws):
                            put(c, xx, yy, h); xx += w_ + g
                        yy += h + S1_IN_GAP
                hrow = max(yy - S1_IN_GAP - y0, 1.0)
                put(find("1절 꼬리표 " + label), x, y0, hrow, TAG_W)
                y = y0 + hrow + S1_ROW_GAP
            return y - S1_ROW_GAP

        def flow(items, x, extra=0.0):
            y = TOP
            for kind, name, gap_, flex in items:
                y += gap_ + (extra if flex else 0.0)
                if kind == "bar":
                    put(find(name), x - BAR_DX, y, BAR_H, CW + 2 * BAR_DX); y += BAR_H
                elif kind == "s1":
                    y = s1(x, y)
                elif kind == "pic":
                    s = find(name); put(s, x, y); y += s.Height / CM
                elif kind == "tbl":
                    s = find(name); s.Left = x * CM; s.Top = y * CM; h = table_h(s); put(s, x, y); y += h
                else:                                                             # 글 상자 · 소제목
                    s = find(name); h = need(s, CW); put(s, x, y, h); y += h
            return y

        ends, extras = [], []
        for items, x in ((LEFT, LX), (RIGHT, RX)):
            end = flow(items, x)
            nflex = sum(1 for it in items if it[3])
            extra = max(0.0, min(max_extra, (BOTTOM - end) / nflex)) if nflex else 0.0
            if extra > 0.01:
                end = flow(items, x, extra)
            ends.append(round(end, 2)); extras.append(round(extra, 2))
        if save_as:
            pres.SaveAs(os.path.abspath(save_as))
        if png:
            sl.Export(os.path.abspath(png), "PNG", 2480, 3508)
        return {"단 끝 cm (왼쪽, 오른쪽)": ends, "쓸 수 있는 끝 cm": BOTTOM, "나눠 준 간격 cm": extras,
                "머리 영역 글 끝 cm": round(head_end, 2), "머리 영역 끝 cm": HEAD_BOTTOM, "개체 (x, y, 너비, 높이 cm)": pos}
    finally:
        pres.Close()


def fits(rep):
    return max(rep["단 끝 cm (왼쪽, 오른쪽)"]) <= BOTTOM + 0.005 and rep["머리 영역 글 끝 cm"] <= HEAD_BOTTOM - 0.3


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--src", default=SRC)
    ap.add_argument("--out-dir", default=os.path.join(ROOT, "02_KSARC2026"))
    ap.add_argument("--body", type=float, default=None, help="본문 크기(pt)를 고정. 안 주면 들어가는 가장 큰 크기를 찾는다")
    ap.add_argument("--max-body", type=float, default=20.0)
    ap.add_argument("--min-body", type=float, default=12.0)
    ap.add_argument("--keep-figures", action="store_true", help="그림 2 · 4 · 6을 다시 그리지 않고 e판 그림 크기 그대로 둔다")
    a = ap.parse_args()
    out = os.path.join(a.out_dir, f"KSARC2026_포스터_초안_{a.tag}.pptx")
    png = os.path.join(a.out_dir, f"포스터_초안_{a.tag}_PowerPoint.png")
    js = os.path.join(a.out_dir, f"포스터_초안_{a.tag}_배치.json")
    figd = os.path.join(a.out_dir, f"포스터_초안_{a.tag}_그림")
    for f in (out, png, js) + (() if a.keep_figures else (figd,)):
        if os.path.exists(f):
            sys.exit(f"이미 있음(덮어쓰지 않음): {f}")
    os.makedirs(a.out_dir, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="poster_restyle_")
    trials = []
    figs = None if a.keep_figures else redraw_figures(figd)

    def trial(B):
        f = os.path.join(tmp, f"try_{B:.1f}.pptx")
        sizes = restyle(a.src, f, B, figs)
        rep = layout(f)
        trials.append({"본문": B, "단 끝": rep["단 끝 cm (왼쪽, 오른쪽)"], "들어감": fits(rep)})
        print(f"  본문 {B:4.1f} pt → 단 끝 {rep['단 끝 cm (왼쪽, 오른쪽)']} (쓸 수 있는 끝 {BOTTOM}) · 머리 {rep['머리 영역 글 끝 cm']}"
              f" → {'들어감' if fits(rep) else '넘침'}", flush=True)
        return f, sizes, rep

    if a.body is not None:
        B = a.body
    else:
        B = a.max_body
        while B >= a.min_body:
            _, _, rep = trial(B)
            if fits(rep):
                break
            B -= 0.5
        else:
            sys.exit("들어가는 크기를 찾지 못함")
    f = os.path.join(tmp, "final_in.pptx")
    sizes = restyle(a.src, f, B, figs)
    rep = layout(f, save_as=out, png=png)
    rep["다시 그린 그림 (e판 높이 → 새 높이 cm)"] = {} if a.keep_figures else {v[0]: [v[1], v[2]] for v in REFIG.values()}
    rep["글자 크기 pt"] = sizes; rep["시험한 크기"] = trials; rep["레퍼런스 본문 pt"] = 20
    json.dump(rep, open(js, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"본문 {B} pt · 단 끝 {rep['단 끝 cm (왼쪽, 오른쪽)']} · {'들어감' if fits(rep) else '넘침'}\n{out}\n{png}\n{js}")


if __name__ == "__main__":
    main()
