"""KSARC 2026 포스터 초안 (2026-11-11). 결과 파일만 읽는다. 시뮬레이션 없음.

학회 양식(02_KSARC2026/ksarc-포스터 PPT 양식.pptx, A1 세로 한 장)을 복사하고 slide1.xml만 새로 짠다.
- 머리(배경 그림 · 제목 · 저자 · 소속 · 로고), 회색 바탕, 흰 단 두 개는 양식 그대로 쓴다. 양식의 예시 칸(제목 · 본문)은 지우고
  같은 모양(절 제목 = 양식 '직사각형 18' 복제, 본문 글머리 = 양식 그림 글머리 rId3)으로 새로 놓는다.
- 그래프 · 흐름도는 matplotlib PNG(이 컴퓨터에 python-pptx · node · LibreOffice가 없어 PowerPoint 기본 차트를 만들 수 없다).
  표는 PowerPoint 표(a:tbl)라 PowerPoint에서 고칠 수 있다.
- 제목은 제출 초록 제목, 저자 · 소속은 이전 포스터(KSARC2026_포스터_논문본문반영.pptx)의 줄을 그대로 옮긴다.
- 숫자는 모두 개발 배치 100벽(시작값 700300 ~ 700399) · 최종 평가 전. 참값 줄은 '참값 (진단)'.
- 나중에 줄을 더하려면(예: SDCG를 넣은 새 Full) --rows-json(줄 목록 전체를 바꿈) 또는 --extra compare.json:키:줄이름(덧붙임).
- 출력이 이미 있으면 덮어쓰지 않는다. 다시 만들 때는 --tag를 새로 준다.
- 미리보기 PNG는 PIL로 도형 위치 · 글자를 대략 그린 것이다(PowerPoint 렌더가 아님). 글자 넘침 · 겹침 점검용.

실행: cd sim && MPLCONFIGDIR=<임시>/mpl PYTHONPATH=. venv/bin/python -m wall3.poster_ksarc_20261111 [--tag 20261111]
"""
import argparse, copy, hashlib, io, json, zipfile
from pathlib import Path
from xml.sax.saxutils import escape

import numpy as np
from lxml import etree

REPO = Path(__file__).resolve().parents[2]
SIM = REPO / "sim"
W = SIM / "outputs" / "wall3"
KS = REPO / "02_KSARC2026"
TPL = KS / "ksarc-포스터 PPT 양식.pptx"
EVID = REPO / "01_사기설" / "근거_우분투_wall3_역방향제거_20261111"
EVID_OLD = REPO / "01_사기설" / "근거_우분투_wall3_검측정보진단_20261103"
FONTS = SIM / "tools" / "fonts"
NOTE = "개발 배치 100벽(시작값 700300 ~ 700399) · 최종 평가 전"

NS = {"p": "http://schemas.openxmlformats.org/presentationml/2006/main",
      "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
      "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
NSDECL = " ".join(f'xmlns:{k}="{v}"' for k, v in NS.items())
REL_IMG = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"
EMU = 360000                                        # EMU per cm

# palette (dataviz reference instance) and text inks
BLUE, ORANGE, GREEN = "#2a78d6", "#eb6834", "#1baf7a"
BLUE_L, GREY = "#a9c8ef", "#b8bec7"
INK, INK2, GRID = "#1f2329", "#5b6370", "#e3e6ea"
ACCENT1 = "4472C4"                                  # template theme accent1 (section headers)
FONT_KR = "나눔고딕"

TITLE_KO = "모방학습 조적 로봇의 파지·배치 검측 단계별 효과"
TITLE_EN = "Stage-wise Effect of Grasp and Placement Inspection on an Imitation-Learned Masonry Robot"
AUTHORS_KO = "정원영¹ • 강현준² • 김홍조³"
AUTHORS_EN = "Jung, Wonyoung • Kang, Hyunjoon • Kim, Hongjo"
AFFIL = ["¹ 학생회원 · 연세대학교 건설환경공학과 학사과정(jwy01230@yonsei.ac.kr)",
         "² 일반회원 · 연세대학교 건설환경공학과 석사과정(hyunjoonkang@yonsei.ac.kr)",
         "³ 교신저자 · 연세대학교 건설환경공학과 부교수(Corresponding Author, hongjo@yonsei.ac.kr)"]

LF = "eval_lf_20261110_compare.json"
G1FIX = "eval_lf_g1fix_20261111_compare.json"
G2C = "eval_lg_g2c_20261111_compare.json"            # 11-11 SDCG(G2c) 추가 시도: Full + G2c 대 Full 다시 (있으면 결론에 한 줄)
G2C_KEY = "eval_lg_full2_20261111/act_all_held+k2+k7+k8"
FULL_KEY = "eval_lf_full_20261110/act_all_held+k2+k7"
# 역방향 제거 줄: (compare json, 키, 줄 이름, 종류) — 종류 'full' · 'loo' · 'none' · 'diag'
ROWS = [
    (LF, FULL_KEY, "Full", "full"),
    (LF, "eval_lf_noG2w_20261110/act_all_held+k2", "Full − G2w", "loo"),
    (LF, "eval_lf_noG3_20261110/act_g1g2_held+k2+k7", "Full − G3", "loo"),
    (G1FIX, "eval_lf_noG1fix_20261111/act_g2g3_held+k2+k7", "Full − G1", "loo"),
    (LF, "eval_lf_noG0_20261110/act_all_held+k7", "Full − G0", "loo"),
    (LF, "eval_lf_noG2_20261110/act_g1g3_held+k2", "Full − G2", "loo"),
    (LF, "eval_lf_noH_20261110/act_all+k2+k7", "Full − H", "loo"),
    (LF, "eval_lf_none_20261110/act_none", "검측 없음", "none"),
    (LF, "eval_lf_truth_20261110/act_all_truth_held+k2+k7", "참값 (진단)", "diag"),
]
# 사다리: (짧은 이름, 설명, 출처) — 출처는 ('summary', 평가 폴더, 조건) 또는 ('compare', json, 키)
LADDER = [   # (번호, 그림 x 이름, 설명, 출처)
    ("1", "처음 정책", "10-22 처음 학습한 정책 + G1 · G2 · G3", ("summary", "eval_gates_20261022", "act_all")),
    ("2", "데이터 정리\n재학습", "10-26 손목 방향을 통일한 시연으로 다시 학습 + G1 · G2 · G3", ("summary", "eval_gates_v2_20261026", "act_all")),
    ("3", "+ H", "11-04 + H (손에 든 벽돌 기준)", ("summary", "eval_gates_info_20261104", "act_all_held")),
    ("4", "+ G0", "11-10 + G0 (집기 정렬)", ("compare", "eval_ladder1_20261110_compare.json", "eval_ladder1_20261110/act_all_held+k2")),
    ("5", "Full\n(+ G2w)", "11-10 Full = + G2w (넓게 받기), 다시 잼", ("compare", LF, FULL_KEY)),
]
FIRST_FAIL = [("Full", LF, FULL_KEY), ("Full − G0", LF, "eval_lf_noG0_20261110/act_all_held+k7"),
              ("검측 없음", LF, "eval_lf_none_20261110/act_none")]


def sha16(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()[:16]


# ---------------------------------------------------------------------------------------------- data
class Data:
    def __init__(self, a):
        self.sources = {}                                     # path -> sha16
        self.cmp = {}
        rows = ROWS
        if a.rows_json:
            rows = [tuple(r) for r in json.loads(Path(a.rows_json).read_text())]
            self._src(Path(a.rows_json))
        for e in a.extra:
            f, k, lab = e.split(":", 2)
            rows = rows + [(f, k, lab, "loo")]
        self.rows = []
        for f, k, lab, kind in rows:
            c = self.compare(f)
            if c is None or k not in c["conditions"]:
                self.rows.append({"label": lab, "kind": kind, "missing": True, "src": f})
                continue
            v = c["conditions"][k]
            self.rows.append({"label": lab, "kind": kind, "missing": False, "src": f, "key": k, "fill": v["filled_mean"],
                              "rate": v["fill_rate_pct"], "complete": v["complete"], "spec": v["spec_pass"],
                              "diff": v.get("vs_base", {}).get("diff_mean"), "ci": v.get("vs_base", {}).get("ci95"),
                              "updown": (v.get("vs_base", {}).get("walls_up"), v.get("vs_base", {}).get("walls_down")),
                              "hist": v.get("first_unfilled_hist", {}), "base": c["base"]})
        self.ladder = []
        for short, xl, desc, src in LADDER:
            if src[0] == "compare":
                v = self.compare(src[1])["conditions"][src[2]]
                fill, comp, spec = v["filled_mean"], v["complete"], v["spec_pass"]
            else:
                d, cond = src[1], src[2]
                p = W / d / "summary.json"
                self._src(p)
                s = json.loads(p.read_text())[cond]
                fill, spec = s["slots_filled_mean"], s["spec_pass"]
                comp = s.get("walls_complete")
                if comp is None:                                # older summaries: count from the rollouts (read only)
                    comp = 0
                    for r in sorted((W / d).glob(f"{cond}_part*/rollout.json")):
                        comp += sum(all(w["eval"]["slots_filled"]) for w in json.loads(r.read_text())["walls"])
            self.ladder.append({"short": short, "xl": xl, "desc": desc, "fill": fill, "complete": comp, "spec": spec, "src": src})
        self.first = []
        for lab, f, k in FIRST_FAIL:
            self.first.append((lab, self.compare(f)["conditions"][k]["first_unfilled_hist"]))

    def _src(self, p):
        p = Path(p)
        self.sources[str(p.relative_to(REPO))] = sha16(p)

    def compare(self, f):
        p = Path(f) if Path(f).is_absolute() else W / f
        if not p.exists():
            return None
        if str(p) not in self.cmp:
            self.cmp[str(p)] = json.loads(p.read_text())
            self._src(p)
        return self.cmp[str(p)]

    def row(self, label):
        return next(r for r in self.rows if r["label"] == label)


# ---------------------------------------------------------------------------------------------- figures
def mpl_setup():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager as fm
    for f in ("NanumGothic-Regular.ttf", "NanumGothic-Bold.ttf", "NanumGothic-ExtraBold.ttf", "NotoSansKR-Regular.ttf", "NotoSansKR-Bold.ttf"):
        fm.fontManager.addfont(str(FONTS / f))
    plt.rcParams.update({"font.family": ["NanumGothic", "Noto Sans KR"],                # Noto: ① · − glyphs "axes.unicode_minus": False, "font.size": 15,
                         "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
                         "axes.titlecolor": INK, "svg.fonttype": "none"})
    return plt


def fig_size(w_cm, h_cm, plt):
    return plt.figure(figsize=(w_cm / 2.54, h_cm / 2.54), dpi=200)


def quiet(ax, grid_axis="x"):
    for s in ("top", "right", "left", "bottom"):
        ax.spines[s].set_visible(False)
    ax.tick_params(length=0)
    if grid_axis:
        ax.grid(axis=grid_axis, color=GRID, linewidth=0.8)
        ax.set_axisbelow(True)


def fig_ladder(d, path, w, h, plt):
    fig = fig_size(w, h, plt)
    gs = fig.add_gridspec(1, 2, width_ratios=[1.0, 1.1], wspace=0.18, left=0.06, right=0.99, top=0.86, bottom=0.2)
    xs = np.arange(len(d.ladder))
    labs = [f"{s['short']}\n{s['xl']}" for s in d.ladder]
    ax = fig.add_subplot(gs[0])
    vals = [s["fill"] for s in d.ladder]
    cols = [BLUE_L] * (len(vals) - 1) + [BLUE]
    ax.bar(xs, vals, width=0.62, color=cols)
    for x, v in zip(xs, vals):
        ax.text(x, v + 0.3, f"{v:.2f}", ha="center", va="bottom", fontsize=15, color=INK, fontweight="bold" if x == xs[-1] else None)
    ax.set_ylim(0, 16)
    ax.set_yticks([0, 4, 8, 12, 16])
    ax.set_xticks(xs, labs, fontsize=12)
    quiet(ax, "y")
    ax.set_title("벽당 채운 자리 (16장 중)", loc="left", fontsize=16, pad=8)
    ax = fig.add_subplot(gs[1])
    wd = 0.36
    comp = [s["complete"] for s in d.ladder]
    spec = [s["spec"] for s in d.ladder]
    ax.bar(xs - wd / 2, comp, width=wd, color=BLUE, label="16장 완성")
    ax.bar(xs + wd / 2, spec, width=wd, color=ORANGE, label="시방 합격")
    for x, c, s in zip(xs, comp, spec):
        ax.text(x - wd / 2, c + 1.5, str(c), ha="center", va="bottom", fontsize=13, color=INK2)
        ax.text(x + wd / 2, s + 1.5, str(s), ha="center", va="bottom", fontsize=13, color=INK2)
    ax.set_ylim(0, 100)
    ax.set_yticks([0, 25, 50, 75, 100])
    ax.set_xticks(xs, labs, fontsize=12)
    quiet(ax, "y")
    ax.set_title("16장 완성 · 시방 합격 (100벽 중)", loc="left", fontsize=16, pad=8)
    ax.legend(frameon=False, fontsize=13, loc="upper left", ncols=2, bbox_to_anchor=(0.0, 1.0))
    fig.savefig(path, dpi=200, facecolor="white")
    plt.close(fig)


def fig_loo(d, path, w, h, plt):
    rows = d.rows
    fig = fig_size(w, h, plt)
    gs = fig.add_gridspec(1, 3, width_ratios=[1.15, 0.8, 1.25], wspace=0.08, left=0.17, right=0.985, top=0.9, bottom=0.08)
    ys = np.arange(len(rows))[::-1].astype(float)
    if rows and rows[-1]["kind"] == "diag":
        ys[-1] -= 0.45                                        # a gap before the diagnosis row
    names = [r["label"] + (" (재측정 중)" if r["missing"] else "") for r in rows]

    def colour(r):
        return BLUE if r["kind"] == "full" else (GREY if r["kind"] in ("diag", "none") else BLUE_L)

    ax = fig.add_subplot(gs[0])
    for y, r in zip(ys, rows):
        if r["missing"]:
            continue
        ax.barh(y, r["fill"], height=0.62, color=colour(r), hatch="//" if r["kind"] == "diag" else None, edgecolor="white", linewidth=0)
        ax.text(r["fill"] + 0.25, y, f"{r['fill']:.2f}", va="center", fontsize=14, color=INK,
                fontweight="bold" if r["kind"] == "full" else None)
    ax.set_xlim(0, 17.5)
    ax.set_xticks([0, 4, 8, 12, 16])
    ax.set_yticks(ys, names, fontsize=15)
    for t, r in zip(ax.get_yticklabels(), rows):
        t.set_color(INK)
        if r["kind"] == "full":
            t.set_fontweight("bold")
    quiet(ax, "x")
    ax.set_title("벽당 채운 자리 (/16)", loc="left", fontsize=15, pad=6)

    ax = fig.add_subplot(gs[1], sharey=ax)
    for y, r in zip(ys, rows):
        if r["missing"]:
            continue
        ax.barh(y, r["spec"], height=0.62, color=ORANGE if r["kind"] != "diag" else GREY,
                hatch="//" if r["kind"] == "diag" else None, edgecolor="white", linewidth=0)
        ax.text(r["spec"] + 2, y, str(r["spec"]), va="center", fontsize=14, color=INK,
                fontweight="bold" if r["kind"] == "full" else None)
    ax.set_xlim(0, 118)
    ax.set_xticks([0, 50, 100])
    ax.tick_params(labelleft=False)
    quiet(ax, "x")
    ax.set_title("시방 합격 (/100)", loc="left", fontsize=15, pad=6)

    ax = fig.add_subplot(gs[2], sharey=ax)
    ax.axvline(0, color=INK2, linewidth=1.2)
    for y, r in zip(ys, rows):
        if r["missing"]:
            continue
        if r["kind"] == "full":
            ax.text(0.3, y, "기준", va="center", ha="left", fontsize=14, color=INK2)
            continue
        lo, hi = r["ci"]
        ax.plot([lo, hi], [y, y], color=INK, linewidth=2.2, solid_capstyle="round")
        ax.plot([r["diff"]], [y], "o", color=INK, markersize=7)
        txt = f"{r['diff']:+.2f} [{lo:+.2f}, {hi:+.2f}]".replace("-", "−")
        if hi >= -6:                                          # label left of the interval when it sits near 0
            ax.text(lo - 0.3, y + 0.33, txt, va="bottom", ha="right", fontsize=12, color=INK2)
        else:
            ax.text(hi + 0.3, y + 0.33, txt, va="bottom", ha="left", fontsize=12, color=INK2)
    ax.set_xlim(-13.5, 1.5)
    ax.set_xticks([-12, -8, -4, 0])
    ax.set_xticklabels(["−12", "−8", "−4", "0"])
    ax.tick_params(labelleft=False)
    quiet(ax, "x")
    ax.set_title("Full 대비 차이 [95 % 구간]", loc="left", fontsize=15, pad=6)
    fig.savefig(path, dpi=200, facecolor="white")
    plt.close(fig)


def fig_first(d, path, w, h, plt):
    fig = fig_size(w, h, plt)
    n = len(d.first)
    gs = fig.add_gridspec(n, 1, hspace=0.35, left=0.16, right=0.99, top=0.9, bottom=0.14)
    xs = np.arange(17)
    for i, (lab, hist) in enumerate(d.first):
        ax = fig.add_subplot(gs[i])
        for x0, x1, nm in ((-0.5, 4.5, "1단"), (4.5, 10.5, "2단"), (10.5, 15.5, "3단")):
            ax.axvspan(x0, x1, color="#f3f5f8" if nm != "2단" else "#e9eef5", linewidth=0, zorder=0)
            if i == 0:
                ax.text((x0 + x1) / 2, 128, nm, ha="center", va="bottom", fontsize=13, color=INK2)
        vals = [hist.get(str(x), 0) for x in xs]
        ax.bar(xs, vals, width=0.7, color=[BLUE] * 16 + [GREEN], zorder=2)
        for x, v in zip(xs, vals):
            if v >= 4:
                ax.text(x, v + 4, str(v), ha="center", va="bottom", fontsize=12, color=INK, zorder=3)
        ax.set_ylim(0, 125)
        ax.set_yticks([0, 50, 100])
        ax.set_xlim(-0.6, 16.6)
        quiet(ax, "y")
        ax.text(-0.06, 0.5, lab, transform=ax.transAxes, ha="right", va="center", fontsize=15, color=INK,
                fontweight="bold" if lab == "Full" else None)
        if i < n - 1:
            ax.set_xticks(xs, [""] * 17)
        else:
            ax.set_xticks(xs, [str(x) for x in range(16)] + ["완성"], fontsize=12)
            ax.set_xlabel("처음 못 채운 자리 (0부터) · 완성 = 16장 다 채움", fontsize=13)
    fig.savefig(path, dpi=200, facecolor="white")
    plt.close(fig)


def fig_flow(path, w, h, plt):
    from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
    fig = fig_size(w, h, plt)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, w)
    ax.set_ylim(0, h)
    ax.axis("off")
    steps = [("정책", "접근", "policy"), ("G0", "집기 정렬", "gate"), ("G1", "집기 확인", "gate"), ("정책", "운반", "policy"),
             ("G2", "놓기 전 보정\n(+ G2w)", "gate"), ("G3", "놓은 뒤\n재배치", "gate"), ("정책", "다음 벽돌", "policy")]
    info = {1: "도면 · 관절값", 2: "손목 힘 · 집게 각도", 4: "작업대 카메라", 5: "작업대 카메라"}
    n = len(steps)
    gap = 0.45
    bw = (w - 0.4 - gap * (n - 1)) / n
    y0, bh = h * 0.52, h * 0.3
    cx = []
    for i, (top, sub, kind) in enumerate(steps):
        x = 0.2 + i * (bw + gap)
        cx.append(x + bw / 2)
        fc, ec, tc = (BLUE, BLUE, "white") if kind == "gate" else ("white", GREY, INK)
        ax.add_patch(FancyBboxPatch((x, y0), bw, bh, boxstyle="round,pad=0,rounding_size=0.25", fc=fc, ec=ec, lw=1.6))
        ax.text(x + bw / 2, y0 + bh * 0.68, top, ha="center", va="center", fontsize=19 if kind == "gate" else 15,
                color=tc, fontweight="bold")
        ax.text(x + bw / 2, y0 + bh * 0.3, sub, ha="center", va="center", fontsize=12.5, color=tc, linespacing=1.15)
        if i in info:
            ax.text(x + bw / 2, y0 + bh + 0.35, info[i], ha="center", va="bottom", fontsize=11.5, color=INK2)
        if i < n - 1:
            ax.add_patch(FancyArrowPatch((x + bw + 0.04, y0 + bh / 2), (x + bw + gap - 0.04, y0 + bh / 2),
                                         arrowstyle="-|>", mutation_scale=14, color=INK2, lw=1.4))
    # H band from G1 to G3
    x0, x1 = cx[2] - bw / 2, cx[5] + bw / 2
    yb = y0 - 0.55
    ax.plot([x0, x0, x1, x1], [y0 - 0.12, yb, yb, y0 - 0.12], color=ORANGE, lw=2.4)
    ax.add_patch(FancyBboxPatch((x0, h * 0.06), x1 - x0, yb - 0.25 - h * 0.06, boxstyle="round,pad=0,rounding_size=0.2",
                                fc="#fdeee6", ec=ORANGE, lw=1.6))
    yt = yb - 0.25
    ax.text(x0 + 0.4, yt - 0.3, "H  손에 든 벽돌 기준", ha="left", va="top", fontsize=17, color=INK, fontweight="bold")
    ax.text(x0 + 0.4, yt - 1.25,
            "G1 순간 손 위치(관절값) → 가장 가까운 공급칸 = 어느 벽돌인가\n→ G2 · G3가 맞출 자리 = 그 벽돌의 설계 자리",
            ha="left", va="top", fontsize=13, color=INK, linespacing=1.35)
    ax.text(0.2, h * 0.36, "정책(ACT) = 학습한 동작\n검측 G = 정책 밖 규칙\n(재학습 없음)", ha="left", va="top",
            fontsize=12, color=INK2, linespacing=1.3)
    fig.savefig(path, dpi=200, facecolor="white")
    plt.close(fig)


def crop_to(src, dst, w_cm, h_cm, focus_y=0.5, box=None, dpi=200):
    from PIL import Image
    im = Image.open(src).convert("RGB")
    if box:
        im = im.crop(box)
    W0, H0 = im.size
    ar = w_cm / h_cm
    if W0 / H0 > ar:
        nw = int(H0 * ar)
        x0 = (W0 - nw) // 2
        im = im.crop((x0, 0, x0 + nw, H0))
    else:
        nh = int(W0 / ar)
        y0 = int(min(max(focus_y * H0 - nh / 2, 0), H0 - nh))
        im = im.crop((0, y0, W0, y0 + nh))
    tw = int(w_cm / 2.54 * dpi)
    im = im.resize((tw, int(tw / ar)), Image.LANCZOS)
    im.save(dst)


def strip_inputs(dst, w_cm, h_cm, dpi=200):
    from PIL import Image, ImageDraw, ImageFont
    names = ("front", "top", "wrist")
    tw, th = int(w_cm / 2.54 * dpi), int(h_cm / 2.54 * dpi)
    canvas = Image.new("RGB", (tw, th), "white")
    lab_h = int(th * 0.14)
    side = min(th - lab_h, (tw - 2 * int(tw * 0.02)) // 3)
    gap = (tw - 3 * side) // 2
    font = ImageFont.truetype(str(FONTS / "NanumGothic-Bold.ttf"), int(lab_h * 0.62))
    d = ImageDraw.Draw(canvas)
    for i, n in enumerate(names):
        im = Image.open(EVID_OLD / "그림" / f"정책입력_집기직전_{n}_8배.png").convert("RGB").resize((side, side), Image.LANCZOS)
        x = i * (side + gap)
        canvas.paste(im, (x, 0))
        d.text((x + side / 2, side + lab_h * 0.15), n, fill=INK2, font=font, anchor="mt")
    canvas.save(dst)


# ---------------------------------------------------------------------------------------------- slide XML
def cm(v):
    return int(round(v * EMU))


PPT_CHARS = {"−": "–", "≫": ">>", "≪": "<<"}               # 나눔고딕 lacks these; the charts (PNG) keep them


def T(s):
    for k, v in PPT_CHARS.items():
        s = s.replace(k, v)
    return s


def rpr(sz, bold=False, color="262626", font=FONT_KR):
    return (f'<a:rPr lang="ko-KR" altLang="en-US" sz="{int(round(sz * 100))}" b="{1 if bold else 0}" dirty="0">'
            f'<a:solidFill><a:srgbClr val="{color}"/></a:solidFill><a:latin typeface="{font}"/><a:ea typeface="{font}"/>'
            f'<a:cs typeface="Arial"/></a:rPr>')


def para(runs, sz=20, algn="l", bullet=False, lnspc=110, after=0, color="262626"):
    """runs: str or list of (text, {bold, color, sz})."""
    if isinstance(runs, str):
        runs = [(runs, {})]
    ppr = f'<a:pPr algn="{algn}"' + (' marL="430000" indent="-430000"' if bullet else ' marL="0" indent="0"') + ">"
    ppr += f'<a:lnSpc><a:spcPct val="{lnspc * 1000}"/></a:lnSpc>'
    if after:
        ppr += f'<a:spcAft><a:spcPts val="{int(after * 100)}"/></a:spcAft>'
    ppr += ('<a:buBlip><a:blip r:embed="rId3"/></a:buBlip>' if bullet else "<a:buNone/>") + "</a:pPr>"
    body = "".join(f'<a:r>{rpr(o.get("sz", sz), o.get("bold", False), o.get("color", color))}'
                   f'<a:t xml:space="preserve">{escape(T(t))}</a:t></a:r>' for t, o in runs)
    return f"<a:p>{ppr}{body}<a:endParaRPr lang=\"ko-KR\" altLang=\"en-US\" sz=\"{int(sz * 100)}\" dirty=\"0\"/></a:p>"


class Slide:
    def __init__(self):
        z = zipfile.ZipFile(TPL)
        self.tpl = z
        self.root = etree.fromstring(z.read("ppt/slides/slide1.xml"))
        self.rels = etree.fromstring(z.read("ppt/slides/_rels/slide1.xml.rels"))
        self.tree = self.root.find(".//p:spTree", NS)
        self.next_id = 100
        self.media = []                                       # (name, bytes)
        self.next_rid = 10
        self.next_img = 10
        self.by_name = {}
        for el in self.tree:
            nv = el.find(".//p:cNvPr", NS)
            if nv is not None:
                self.by_name[nv.get("name")] = el
        self.header_proto = copy.deepcopy(self.by_name["직사각형 18"])     # template section header, kept before the samples go

    def nid(self):
        self.next_id += 1
        return self.next_id

    def add(self, xml):
        el = etree.fromstring(f"<root {NSDECL}>{xml}</root>")[0]
        self.tree.append(el)
        return el

    def image(self, path, x, y, w, h, descr):
        data = Path(path).read_bytes()
        name = f"image{self.next_img}.png"
        self.next_img += 1
        rid = f"rId{self.next_rid}"
        self.next_rid += 1
        self.media.append((name, data))
        r = etree.SubElement(self.rels, "{http://schemas.openxmlformats.org/package/2006/relationships}Relationship")
        r.set("Id", rid)
        r.set("Type", REL_IMG)
        r.set("Target", f"../media/{name}")
        i = self.nid()
        self.add(f'<p:pic><p:nvPicPr><p:cNvPr id="{i}" name="그림 {i}" descr="{escape(descr, {chr(34): "&quot;"})}"/>'
                 f'<p:cNvPicPr><a:picLocks noChangeAspect="1"/></p:cNvPicPr><p:nvPr/></p:nvPicPr>'
                 f'<p:blipFill><a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></p:blipFill>'
                 f'<p:spPr><a:xfrm><a:off x="{cm(x)}" y="{cm(y)}"/><a:ext cx="{cm(w)}" cy="{cm(h)}"/></a:xfrm>'
                 f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr></p:pic>')

    def text(self, x, y, w, h, paras, name=None, anchor="t", fill=None, geom="rect", line=None, inset=0.12):
        i = self.nid()
        fillx = f'<a:solidFill><a:srgbClr val="{fill}"/></a:solidFill>' if fill else "<a:noFill/>"
        lnx = f'<a:ln w="19050"><a:solidFill><a:srgbClr val="{line}"/></a:solidFill></a:ln>' if line else "<a:ln><a:noFill/></a:ln>"
        av = '<a:avLst><a:gd name="adj" fmla="val 8000"/></a:avLst>' if geom == "roundRect" else "<a:avLst/>"
        ins = cm(inset)
        self.add(f'<p:sp><p:nvSpPr><p:cNvPr id="{i}" name="{escape(name or f"글상자 {i}")}"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>'
                 f'<p:spPr><a:xfrm><a:off x="{cm(x)}" y="{cm(y)}"/><a:ext cx="{cm(w)}" cy="{cm(h)}"/></a:xfrm>'
                 f'<a:prstGeom prst="{geom}">{av}</a:prstGeom>{fillx}{lnx}</p:spPr>'
                 f'<p:txBody><a:bodyPr wrap="square" lIns="{ins}" tIns="{ins}" rIns="{ins}" bIns="{ins}" anchor="{anchor}" rtlCol="0">'
                 f'<a:noAutofit/></a:bodyPr><a:lstStyle/>{"".join(paras)}</p:txBody></p:sp>')

    def header(self, x, y, w, label):
        el = copy.deepcopy(self.header_proto)
        nv = el.find(".//p:cNvPr", NS)
        i = self.nid()
        nv.set("id", str(i))
        nv.set("name", f"절 제목 {i}")
        for ext in nv.findall("a:extLst", NS):
            nv.remove(ext)
        off = el.find("./p:spPr/a:xfrm/a:off", NS)
        ext = el.find("./p:spPr/a:xfrm/a:ext", NS)
        off.set("x", str(cm(x)))
        off.set("y", str(cm(y)))
        ext.set("cx", str(cm(w)))
        p = el.find(".//a:p", NS)
        runs = p.findall("a:r", NS)
        for r in runs[1:]:
            p.remove(r)
        runs[0].find("a:t", NS).text = T(label)
        runs[0].find("a:rPr", NS).set("lang", "ko-KR")
        self.tree.append(el)

    def table(self, x, y, col_w, rows, row_h, sz=16, header_fill=ACCENT1, name="표"):
        i = self.nid()
        grid = "".join(f'<a:gridCol w="{cm(c)}"/>' for c in col_w)
        trs = []
        for ri, row in enumerate(rows):
            tcs = []
            for ci, cell in enumerate(row):
                t, o = (cell, {}) if isinstance(cell, str) else cell
                hdr = ri == 0
                fill = header_fill if hdr else o.get("fill", "F4F6F9" if ri % 2 == 0 else "FFFFFF")
                col = "FFFFFF" if hdr else o.get("color", "262626")
                algn = o.get("algn", "ctr" if (hdr or ci > 0) else "l")
                lines = t.split("\n")
                ps = "".join(f'<a:p><a:pPr algn="{algn}"/><a:r>{rpr(o.get("sz", sz), hdr or o.get("bold", False), col)}'
                             f'<a:t xml:space="preserve">{escape(T(ln))}</a:t></a:r></a:p>' for ln in lines)
                ln = '<a:lnB w="9525"><a:solidFill><a:srgbClr val="D0D5DC"/></a:solidFill></a:lnB>'
                nol = "".join(f'<a:{s} w="0"><a:noFill/></a:{s}>' for s in ("lnL", "lnR", "lnT"))
                tcs.append(f'<a:tc><a:txBody><a:bodyPr/><a:lstStyle/>{ps}</a:txBody>'
                           f'<a:tcPr marL="{cm(0.18)}" marR="{cm(0.18)}" marT="{cm(0.06)}" marB="{cm(0.06)}" anchor="ctr">'
                           f'{nol}{ln}<a:solidFill><a:srgbClr val="{fill}"/></a:solidFill></a:tcPr></a:tc>')
            trs.append(f'<a:tr h="{cm(row_h)}">{"".join(tcs)}</a:tr>')
        self.add(f'<p:graphicFrame><p:nvGraphicFramePr><p:cNvPr id="{i}" name="{escape(name)} {i}"/>'
                 f'<p:cNvGraphicFramePr><a:graphicFrameLocks noGrp="1"/></p:cNvGraphicFramePr><p:nvPr/></p:nvGraphicFramePr>'
                 f'<p:xfrm><a:off x="{cm(x)}" y="{cm(y)}"/><a:ext cx="{cm(sum(col_w))}" cy="{cm(row_h * len(rows))}"/></p:xfrm>'
                 f'<a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/table"><a:tbl>'
                 f'<a:tblPr firstRow="1" bandRow="1"/><a:tblGrid>{grid}</a:tblGrid>{"".join(trs)}</a:tbl></a:graphicData></a:graphic>'
                 f'</p:graphicFrame>')

    def set_runs(self, name, lines, keep_first_rpr=True):
        """Replace the text of a template shape: one paragraph per line, each paragraph keeps its first run's rPr."""
        el = self.by_name[name]
        body = el.find(".//p:txBody", NS)
        ps = body.findall("a:p", NS)
        protos = []
        for p in ps:
            r = p.find("a:r", NS)
            protos.append((copy.deepcopy(p.find("a:pPr", NS)) if p.find("a:pPr", NS) is not None else None,
                           copy.deepcopy(r.find("a:rPr", NS)) if r is not None else None))
        protos = [pp for pp in protos if pp[1] is not None] or protos
        for p in ps:
            body.remove(p)
        for k, (txt, sz) in enumerate(lines):
            ppr, rp = protos[min(k, len(protos) - 1)]
            p = etree.SubElement(body, f"{{{NS['a']}}}p")
            if ppr is not None:
                p.append(copy.deepcopy(ppr))
            r = etree.SubElement(p, f"{{{NS['a']}}}r")
            rp = copy.deepcopy(rp)
            if sz:
                rp.set("sz", str(int(sz * 100)))
            r.append(rp)
            t = etree.SubElement(r, f"{{{NS['a']}}}t")
            t.text = T(txt)

    def remove(self, names):
        for n in names:
            el = self.by_name.pop(n)
            self.tree.remove(el)

    def write(self, out, thumb_jpeg):
        slide = etree.tostring(self.root, xml_declaration=True, encoding="UTF-8", standalone=True)
        rels = etree.tostring(self.rels, xml_declaration=True, encoding="UTF-8", standalone=True)
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zo:
            for it in self.tpl.infolist():                       # fresh ZipInfo: writestr() rewrites the one it gets
                if it.filename in ("ppt/slides/slide1.xml", "ppt/slides/_rels/slide1.xml.rels", "docProps/thumbnail.jpeg"):
                    data = {"ppt/slides/slide1.xml": slide, "ppt/slides/_rels/slide1.xml.rels": rels,
                            "docProps/thumbnail.jpeg": thumb_jpeg}[it.filename]
                else:
                    data = self.tpl.read(it.filename)
                zi = zipfile.ZipInfo(it.filename, date_time=it.date_time)
                zi.compress_type = zipfile.ZIP_DEFLATED
                zi.external_attr = it.external_attr
                zo.writestr(zi, data)
            for n, b in self.media:
                zo.writestr(f"ppt/media/{n}", b)
        return slide


# ---------------------------------------------------------------------------------------------- preview (approximate)
def preview(pptx, out_png, px_cm=40):
    """Draw the slide's shapes, pictures, tables and text at their positions (PIL). Returns warnings."""
    from PIL import Image, ImageDraw, ImageFont
    z = zipfile.ZipFile(pptx)
    root = etree.fromstring(z.read("ppt/slides/slide1.xml"))
    rels = {r.get("Id"): r.get("Target") for r in etree.fromstring(z.read("ppt/slides/_rels/slide1.xml.rels"))}
    pres = etree.fromstring(z.read("ppt/presentation.xml"))
    sz = pres.find("p:sldSz", NS)
    Wp, Hp = int(int(sz.get("cx")) / EMU * px_cm), int(int(sz.get("cy")) / EMU * px_cm)
    img = Image.new("RGB", (Wp, Hp), "white")
    dr = ImageDraw.Draw(img)
    scheme = {"bg1": "FFFFFF", "tx1": "000000", "accent1": ACCENT1, "lt1": "FFFFFF", "dk1": "000000"}
    fcache = {}

    def font(pt, bold):
        f = FONTS / ("NanumGothic-Bold.ttf" if bold else "NanumGothic-Regular.ttf")
        k = (pt, bold)
        if k not in fcache:
            fcache[k] = ImageFont.truetype(str(f), max(6, int(round(pt / 72 * 2.54 * px_cm))))
        return fcache[k]

    def colour(el, default=None):
        if el is None:
            return default
        s = el.find("a:srgbClr", NS)
        if s is not None:
            return "#" + s.get("val")
        s = el.find("a:schemeClr", NS)
        if s is not None:
            c = scheme.get(s.get("val"), "888888")
            lm = s.find("a:lumMod", NS)
            if lm is not None:
                f = int(lm.get("val")) / 100000
                c = "".join(f"{int(int(c[i:i + 2], 16) * f):02x}" for i in (0, 2, 4))
            return "#" + c
        return default

    def box(el, xpath):
        x = el.find(xpath, NS)
        off, ext = x.find("a:off", NS), x.find("a:ext", NS)
        return [int(off.get(k)) / EMU * px_cm for k in ("x", "y")] + [int(ext.get(k)) / EMU * px_cm for k in ("cx", "cy")]

    def layout(paras, width):
        """-> list of (line, font, colour, height_px)."""
        out = []
        for p in paras:
            runs = p.findall("a:r", NS)
            ppr = p.find("a:pPr", NS)
            ln = ppr.find("a:lnSpc/a:spcPct", NS) if ppr is not None else None
            lns = int(ln.get("val")) / 100000 if ln is not None else 1.0
            ind = int(ppr.get("marL", "0")) / EMU * px_cm if ppr is not None else 0
            txt = "".join(r.findtext("a:t", default="", namespaces=NS) for r in runs)
            rp = runs[0].find("a:rPr", NS) if runs else p.find("a:endParaRPr", NS)
            pt = int(rp.get("sz", "1800")) / 100 if rp is not None and rp.get("sz") else 18
            bold = rp is not None and rp.get("b") == "1"
            col = colour(rp.find("a:solidFill", NS), "#000000") if rp is not None else "#000000"
            f = font(pt, bold)
            lh = pt / 72 * 2.54 * px_cm * 1.2 * lns
            words, cur = txt.split(" "), ""
            lines = []
            for w_ in words:
                t = (cur + " " + w_) if cur else w_
                if f.getlength(t) <= width - ind or not cur:
                    cur = t
                else:
                    lines.append(cur)
                    cur = w_
            lines.append(cur)
            for k, l_ in enumerate(lines):
                out.append((l_, f, col, lh, ind))
        return out

    warn, boxes = [], []
    skip = {"그림 7", "직사각형 13", "직사각형 14", "직사각형 15", "직사각형 16", "그림 2"}
    for el in root.find(".//p:spTree", NS):
        tag = etree.QName(el).localname
        nv = el.find(".//p:cNvPr", NS)
        if nv is None:
            continue
        name = nv.get("name")
        if tag == "pic":
            x, y, w, h = box(el, "./p:spPr/a:xfrm")
            rid = el.find(".//a:blip", NS).get(f"{{{NS['r']}}}embed")
            im = Image.open(io.BytesIO(z.read("ppt/" + rels[rid].replace("../", "")))).convert("RGB").resize((max(1, int(w)), max(1, int(h))))
            img.paste(im, (int(x), int(y)))
        elif tag == "sp":
            x, y, w, h = box(el, "./p:spPr/a:xfrm")
            sp = el.find("p:spPr", NS)
            fc = colour(sp.find("a:solidFill", NS))
            if fc is None and el.find("p:style/a:fillRef", NS) is not None and sp.find("a:noFill", NS) is None \
                    and sp.find("a:solidFill", NS) is None and name not in ("직사각형 8",) and el.find("p:nvSpPr/p:cNvSpPr", NS).get("txBox") != "1":
                fc = colour(el.find("p:style/a:fillRef", NS))
            ln = sp.find("a:ln/a:solidFill", NS)
            geom = sp.find("a:prstGeom", NS)
            rr = geom is not None and geom.get("prst") == "roundRect"
            if fc or ln is not None:
                if rr:
                    dr.rounded_rectangle([x, y, x + w, y + h], radius=int(min(w, h) * 0.08), fill=fc, outline=colour(ln) if ln is not None else None, width=2)
                else:
                    dr.rectangle([x, y, x + w, y + h], fill=fc, outline=colour(ln) if ln is not None else None)
            body = el.find("p:txBody", NS)
            if body is not None and "".join(body.xpath(".//a:t/text()", namespaces=NS)).strip():
                bp = body.find("a:bodyPr", NS)
                li = int(bp.get("lIns", "91440")) / EMU * px_cm
                ti = int(bp.get("tIns", "45720")) / EMU * px_cm
                lines = layout(body.findall("a:p", NS), w - 2 * li if bp.get("wrap") != "none" else 1e9)
                th = sum(l_[3] for l_ in lines)
                ty = y + ti if bp.get("anchor", "t") == "t" else y + (h - th) / 2
                algn = (body.find("a:p/a:pPr", NS).get("algn") if body.find("a:p/a:pPr", NS) is not None else "l") or "l"
                for l_, f, col, lh, ind in lines:
                    if algn == "ctr":
                        dr.text((x + w / 2, ty + lh * 0.1), l_, font=f, fill=col, anchor="ma")
                    else:
                        dr.text((x + li + ind, ty + lh * 0.1), l_, font=f, fill=col)
                    ty += lh
                bottom = y + ti + th
                if name in ("직사각형 8", "Text Box 274", "Text Box 275"):     # template autofit boxes: must stay in the header band
                    if bottom > 14.14 * px_cm:
                        warn.append(f"머리 넘침: {name} 아래 끝 {bottom / px_cm:.2f} cm > 14.14 cm")
                    continue
                if name not in skip and bottom > y + h + 2:
                    warn.append(f"넘침: {name} 글 높이 {th / px_cm:.2f} cm > 상자 {h / px_cm:.2f} cm")
                boxes.append((name, x, y, w, max(h, bottom - y)))
            elif name not in skip:
                boxes.append((name, x, y, w, h))
        elif tag == "graphicFrame":
            x, y, w, h = box(el, "./p:xfrm")
            tbl = el.find(".//a:tbl", NS)
            cws = [int(g.get("w")) / EMU * px_cm for g in tbl.findall("a:tblGrid/a:gridCol", NS)]
            yy = y
            for tr in tbl.findall("a:tr", NS):
                rh = int(tr.get("h")) / EMU * px_cm
                xx = x
                for tc, cw in zip(tr.findall("a:tc", NS), cws):
                    dr.rectangle([xx, yy, xx + cw, yy + rh], fill=colour(tc.find("a:tcPr/a:solidFill", NS), "#ffffff"), outline="#d0d5dc")
                    lines = layout(tc.findall("a:txBody/a:p", NS), cw - 0.36 * px_cm)
                    th = sum(l_[3] for l_ in lines)
                    if th > rh + 2:
                        warn.append(f"표 칸 넘침: {name} '{lines[0][0][:12]}' {th / px_cm:.2f} > {rh / px_cm:.2f} cm")
                    ty = yy + (rh - th) / 2
                    algn = tc.find("a:txBody/a:p/a:pPr", NS).get("algn", "l")
                    for l_, f, col, lh, ind in lines:
                        if algn == "ctr":
                            dr.text((xx + cw / 2, ty + lh * 0.1), l_, font=f, fill=col, anchor="ma")
                        else:
                            dr.text((xx + 0.18 * px_cm, ty + lh * 0.1), l_, font=f, fill=col)
                        ty += lh
                    xx += cw
                yy += rh
            boxes.append((name, x, y, w, h))
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            a, b = boxes[i], boxes[j]
            ox = min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1])
            oy = min(a[2] + a[4], b[2] + b[4]) - max(a[2], b[2])
            if ox > 4 and oy > 4:
                warn.append(f"겹침: {a[0]} ↔ {b[0]} ({ox / px_cm:.1f} × {oy / px_cm:.1f} cm)")
    img.save(out_png)
    return warn, img


def check_glyphs(pptx):
    """Characters in 나눔고딕 runs that the font does not have (PowerPoint would substitute another font)."""
    from matplotlib.ft2font import FT2Font
    cmap = set(FT2Font(str(FONTS / "NanumGothic-Regular.ttf")).get_charmap()) & set(FT2Font(str(FONTS / "NanumGothic-ExtraBold.ttf")).get_charmap())
    sl = etree.fromstring(zipfile.ZipFile(pptx).read("ppt/slides/slide1.xml"))
    bad = set()
    for r in sl.iter(f"{{{NS['a']}}}r"):
        faces = " ".join(r.xpath("./a:rPr/a:latin/@typeface | ./a:rPr/a:ea/@typeface", namespaces=NS))
        if "나눔" not in faces:
            continue
        for ch in r.findtext("a:t", default="", namespaces=NS):
            if ord(ch) > 127 and ord(ch) not in cmap and not ("\uac00" <= ch <= "\ud7a3"):
                bad.add(ch)
    return sorted(bad)


def check_package(pptx):
    """Zip opens, XML parts parse, every relationship target exists, content types cover every extension."""
    errs = []
    z = zipfile.ZipFile(pptx)
    names = set(z.namelist())
    if len(names) != len(z.namelist()):
        errs.append("zip에 같은 이름이 두 번 있음")
    ct = etree.fromstring(z.read("[Content_Types].xml"))
    defaults = {d.get("Extension").lower() for d in ct if d.tag.endswith("Default")}
    overrides = {o.get("PartName").lstrip("/") for o in ct if o.tag.endswith("Override")}
    for n in names:
        if n.endswith(".xml") or n.endswith(".rels"):
            try:
                etree.fromstring(z.read(n))
            except etree.XMLSyntaxError as e:
                errs.append(f"XML 오류 {n}: {e}")
        ext = n.rsplit(".", 1)[-1].lower()
        if n not in overrides and ext not in defaults:
            errs.append(f"내용 형식 없음: {n}")
    for n in names:
        if not n.endswith(".rels"):
            continue
        base = n.replace("_rels/", "").rsplit(".rels", 1)[0]
        d = base.rsplit("/", 1)[0] if "/" in base else ""
        for r in etree.fromstring(z.read(n)):
            if r.get("TargetMode") == "External":
                continue
            t = r.get("Target")
            p = t.lstrip("/") if t.startswith("/") else str(Path(d) / t)
            p = str(Path(p)).replace("\\", "/")
            parts = []
            for seg in p.split("/"):
                if seg == "..":
                    parts.pop()
                elif seg not in (".", ""):
                    parts.append(seg)
            if "/".join(parts) not in names:
                errs.append(f"관계 대상 없음: {n} → {t}")
    sl = etree.fromstring(z.read("ppt/slides/slide1.xml"))
    ids = [c.get("id") for c in sl.iter(f"{{{NS['p']}}}cNvPr")]
    if len(ids) != len(set(ids)):
        errs.append("도형 id 중복")
    return errs


# ---------------------------------------------------------------------------------------------- build
def build(a):
    tag = a.tag
    od = Path(a.out_dir) if a.out_dir else KS
    pptx = od / f"KSARC2026_포스터_초안_{tag}.pptx"
    figd = od / f"포스터_초안_{tag}_그림"
    prev = od / f"포스터_초안_{tag}_미리보기.png"
    md = od / f"KSARC2026_포스터_초안_{tag}_설명.md"
    for p in (pptx, figd, prev, md):
        if p.exists():
            raise SystemExit(f"{p} 이미 있음: 덮어쓰지 않음 (--tag를 새로 줄 것)")
    d = Data(a)
    plt = mpl_setup()
    figd.mkdir(parents=True)

    # ---- geometry (cm). Columns: inner x 1.78 / 30.99, width 26.6 (template panels x 0.76 / 30.35, w 28.29, y 15.79 ~ 83.42)
    LX, RX, CW, HH = 1.78, 30.99, 26.6, 2.19
    F = {}                                                     # figure name -> (path, w, h)

    def fig(name, w, h):
        F[name] = (figd / name, w, h)
        return figd / name, w, h

    p, w, h = fig("그림1_검측단계_흐름도.png", CW, 9.4)
    fig_flow(p, w, h, plt)
    p, w, h = fig("그림2_단계별_사다리.png", CW, 10.4)
    fig_ladder(d, p, w, h, plt)
    p, w, h = fig("그림3_역방향제거_Full에서하나씩끔.png", CW, 13.4)
    fig_loo(d, p, w, h, plt)
    p, w, h = fig("그림4_처음못채운자리_Full_FullG0_검측없음.png", CW, 10.8)
    fig_first(d, p, w, h, plt)
    p, w, h = fig("사진1_정책입력_카메라3대.png", 18.6, 6.4)
    strip_inputs(p, w, h)
    p, w, h = fig("사진2_Full완성벽_700300_정면.png", 13.0, 8.6)
    crop_to(EVID / "확인영상" / "Full_완성벽_700300_마지막_정면.png", p, w, h, focus_y=0.5)
    p, w, h = fig("사진3_Full완성벽_700300_비스듬히.png", 13.0, 8.6)
    crop_to(EVID / "확인영상" / "Full_완성벽_700300_마지막_비스듬히.png", p, w, h, focus_y=0.5)
    for src in (EVID / "확인영상" / "Full_완성벽_700300_마지막_정면.png", EVID / "확인영상" / "Full_완성벽_700300_마지막_비스듬히.png",
                *[EVID_OLD / "그림" / f"정책입력_집기직전_{n}_8배.png" for n in ("front", "top", "wrist")]):
        d._src(src)

    s = Slide()
    s.set_runs("직사각형 8", [(TITLE_KO, 48), (TITLE_EN, 26)])
    s.set_runs("Text Box 274", [(AUTHORS_KO, 32), (AUTHORS_EN, 26)])
    s.set_runs("Text Box 275", [(t, 18) for t in AFFIL])
    s.remove([f"직사각형 {k}" for k in range(17, 29)])

    full = d.row("Full")
    none = d.row("검측 없음")
    g1 = d.row("Full − G1")
    # ---------------- left column
    y = 16.56
    s.header(LX + 0.22, y, CW, "01  연구 배경과 질문")
    y += HH + 0.55
    s.text(LX, y, CW, 3.6, [
        para([("모방학습 정책(ACT)만으로는 ", {}), ("3단 16장 벽을 벽당 2.0장", {"bold": True}), ("만 채운다", {})], bullet=True, after=4),
        para("정책은 그대로 두고, 정책 밖 검측 단계(G)를 더한다", bullet=True, after=4),
        para([("각 단계의 몫: ", {}), ("모두 켠 Full에서 하나씩 끄기", {"bold": True}), (" (같은 100벽 짝 비교)", {})], bullet=True)],
        name="배경 글")
    y += 3.75
    stats = [(f"{none['fill']:.1f} → {full['fill']:.2f}", "벽당 채운 자리 (16장 중)"), (f"0 → {full['spec']}", "시방 합격 벽 (100벽 중)"),
             (f"{full['rate']:.1f} %", "Full 채움률")]
    sw = (CW - 2 * 0.4) / 3
    for k, (big, lab) in enumerate(stats):
        s.text(LX + k * (sw + 0.4), y, sw, 3.3, [para([(big, {"bold": True, "sz": 40, "color": "1B4F8F"})], sz=40, algn="ctr", lnspc=100),
                                                para(lab, sz=16, algn="ctr", color="5B6370")],
               fill="EEF3FA", geom="roundRect", anchor="ctr", name=f"수치 {k + 1}")
    y += 3.3 + 0.5
    pth, w, h = F["사진1_정책입력_카메라3대.png"]
    s.image(pth, LX, y, w, h, "정책이 받는 카메라 영상 세 장(front · top · wrist, 128 × 128), 집기 직전")
    s.text(LX + w + 0.3, y + 0.2, CW - w - 0.3, h - 0.2, [
        para([("정책 입력", {"bold": True})], sz=18, after=3),
        para("카메라 3대 + 관절값", sz=16, after=2), para("→ 관절 목표값", sz=16, after=2),
        para("시연 1,000벽 (배치 16,000회) 학습, ACT 10만 스텝, 이후 고정", sz=14, color="5B6370")], name="정책 입력 설명")
    y += h + 0.6

    s.header(LX + 0.22, y, CW, "02  검측 단계 (정책 밖 규칙, 재학습 없음)")
    y += HH + 0.5
    pth, w, h = F["그림1_검측단계_흐름도.png"]
    s.image(pth, LX, y, w, h, "벽돌 한 장의 시간 순서: 정책 접근 → G0 집기 정렬 → G1 집기 확인 → 정책 운반 → G2 놓기 전 보정(+G2w) → G3 놓은 뒤 재배치, H는 G1 순간에 손에 든 벽돌을 정해 G2 · G3의 기준 자리로 씀")
    y += h + 0.35
    trows = [["이름", "하는 일", "쓰는 정보"],
             [("G0 집기 정렬", {"bold": True}), "정책이 공급칸 위로 내려오면 도면 중심에서 대신 집기", "공급대 도면 · 관절값"],
             [("G1 집기 확인", {"bold": True}), "1.5 cm 들어 쥐었나 판정, 못 쥐면 다시", "손목 힘 · 집게 각도"],
             [("G2 놓기 전 보정", {"bold": True}), "손 안 벽돌을 재서 설계 자리에 놓기", "작업대 카메라"],
             [("G2w 넓게 받기", {"bold": True}), "G2가 넘겨받는 거리 15 → 40 cm", "–"],
             [("G3 놓은 뒤 재배치", {"bold": True}), "놓인 벽돌을 재서 어긋나면 다시 놓기", "작업대 카메라"],
             [("H 손에 든 벽돌 기준", {"bold": True}), "G2 · G3의 기준 = 쥔 순간 가장 가까운 공급칸의 벽돌", "도면 · 관절값"]]
    for r in trows[1:]:
        r[1] = (r[1], {"algn": "l"})
    s.table(LX, y, [6.0, 14.4, 6.2], trows, 0.92, sz=15, name="검측 단계 표")
    y += 0.92 * len(trows) + 0.6

    s.header(LX + 0.22, y, CW, "03  실험 환경과 평가")
    y += HH + 0.5
    pa, w, h = F["사진2_Full완성벽_700300_정면.png"]
    s.image(pa, LX, y, w, h, "Full로 쌓은 벽 700300, 마지막 장면 정면(로봇 반대쪽에서)")
    pb, w2, _ = F["사진3_Full완성벽_700300_비스듬히.png"]
    s.image(pb, LX + w + (CW - w - w2), y, w2, h, "Full로 쌓은 벽 700300, 마지막 장면 비스듬히")
    y += h + 0.1
    s.text(LX, y, CW, 0.85, [para("Full로 쌓은 벽 (벽 700300, 16 / 16 · 시방 합격): 정면 · 비스듬히", sz=14, algn="ctr", color="5B6370")],
           name="사진 설명")
    y += 0.95
    s.text(LX, y, CW, 3.7, [
        para([("환경  ", {"bold": True}), ("MuJoCo · UR10e + Robotiq 2F-140 · 벽돌 190 × 90 × 57 mm, 3단 16장 (반장 2)", {})], sz=16, bullet=True, after=3),
        para([("평가  ", {"bold": True}), ("같은 100벽 짝 비교 · 벽 단위 부트스트랩 95 % 구간", {})], sz=16, bullet=True, after=3),
        para([("시방  ", {"bold": True}), ("KCS 41 34 00 조적공사 허용오차 5개 항목 모두 통과", {})], sz=16, bullet=True)],
        name="환경 글")
    y += 3.9
    s.header(LX + 0.22, y, CW, "07  H(손에 든 벽돌 기준)가 작동하는 전제")
    y += HH + 0.5
    cards = [("시뮬레이션 (지금 만족)", ["공급칸 위치 · 순서를 앎", "칸 간격 18~26 cm, 흩어짐 ±1 cm → 99.5 % 맞음", "쥔 뒤 놓을 때까지 한 장"], "EEF3FA"),
             ("실제 로봇", ["공급대와 로봇 좌표 등록 (오차가 칸 간격 절반보다 충분히 작게)", "관절값만 씀 → 조명 · 먼지 영향 없음"], "EEF6F1"),
             ("현장", ["묶음 팔레트 → 순서대로 칸에 담는 공급 단계", "적재 실수 · 작업자 개입 → 칸 상태 확인", "로봇이 옮기면 다시 등록"], "FDF1EA")]
    cwid = (CW - 2 * 0.35) / 3
    ch = 7.4
    for k, (hd, items, fc) in enumerate(cards):
        s.text(LX + k * (cwid + 0.35), y, cwid, ch, [para([(hd, {"bold": True})], sz=18, after=5)] +
               [para(t, sz=16, bullet=True, after=3) for t in items], fill=fc, geom="roundRect", name=f"전제 {k + 1}", inset=0.3)
    y += ch + 0.3
    noh = d.row("Full − H")
    s.text(LX, y, CW, 1.5, [para([("H를 끄면 ", {}), (f"{noh['fill']:.2f}장", {"bold": True}),
                                  (f" (검측 없음 {none['fill']:.2f}장보다 낮음): 정책은 한 차례에 여러 장을 쌓아 차례 번호와 손에 든 벽돌이 어긋난다", {})],
                                 sz=15, color="262626")], name="H 요약")
    y += 1.6
    s.text(LX, y, CW, 0.8, [para([("포스터의 모든 수치: " + NOTE, {"bold": True, "color": "1B4F8F"})], sz=14)], name="수치 안내")
    left_end = y + 0.8

    # ---------------- right column
    y = 16.56
    s.header(RX + 0.22, y, CW, "04  결과 1: 단계별 사다리")
    y += HH + 0.5
    pth, w, h = F["그림2_단계별_사다리.png"]
    s.image(pth, RX, y, w, h, "단계별 벽당 채운 자리와 16장 완성 · 시방 합격 벽 수 (① 2.08 → ⑤ 13.65장)")
    y += h + 0.1
    s.text(RX, y, CW, 0.85, [para("1 · 2: 정책 자체를 바꾼 단계 (G1 · G2 · G3 켬) · 3 ~ 5: 검측을 더한 단계 · " + NOTE, sz=13, algn="ctr", color="5B6370")],
           name="사다리 설명")
    y += 1.05
    s.header(RX + 0.22, y, CW, "05  결과 2: Full에서 하나씩 끄기")
    y += HH + 0.5
    pth, w, h = F["그림3_역방향제거_Full에서하나씩끔.png"]
    s.image(pth, RX, y, w, h, "Full과 Full에서 하나씩 끈 조건의 벽당 채운 자리, 시방 합격, Full 대비 짝 차이와 95 % 구간")
    y += h + 0.3
    lrows = [["조건", "채운 자리", "16장 완성", "시방 합격", "Full 대비 [95 % 구간]"]]
    for r in d.rows:
        if r["missing"]:
            lrows.append([r["label"], "재측정 중", "", "", ""])
            continue
        vs = "기준" if r["kind"] == "full" else f"{r['diff']:+.2f} [{r['ci'][0]:+.2f}, {r['ci'][1]:+.2f}]".replace("-", "−")
        o = {"bold": True} if r["kind"] == "full" else {}
        lrows.append([(r["label"], o), (f"{r['fill']:.2f}", o), (str(r["complete"]), o), (str(r["spec"]), o), (vs, o)])
    s.table(RX, y, [6.4, 4.0, 3.9, 3.9, 8.4], lrows, 0.8, sz=15, name="역방향 제거 표")
    y += 0.8 * len(lrows) + 0.1
    s.text(RX, y, CW, 0.85, [para("참값 (진단) = G2 · G3 위치와 손에 든 벽돌 판별을 정답 좌표로 바꾼 진단 (실제 로봇 불가)",
                                  sz=12, color="5B6370")], name="역방향 각주")
    y += 1.05
    s.header(RX + 0.22, y, CW, "06  남은 실패: 처음 못 채운 자리")
    y += HH + 0.5
    pth, w, h = F["그림4_처음못채운자리_Full_FullG0_검측없음.png"]
    s.image(pth, RX, y, w, h, "처음 못 채운 자리 분포: Full, Full − G0, 검측 없음 (100벽, 완성 = 16장)")
    y += h + 0.1
    h1 = full["hist"]
    s6, s3 = h1.get("6", 0), sum(h1.get(str(k), 0) for k in (11, 12, 13))
    s.text(RX, y, CW, 0.85, [para(f"Full의 남은 처음 실패: 자리 6 ({s6}벽) · 3단 자리 11 ~ 13 ({s3}벽)에 흩어짐", sz=14, algn="ctr", color="5B6370")],
           name="처음 실패 설명")
    y += 1.05
    s.header(RX + 0.22, y, CW, "08  결론")
    y += HH + 0.5
    g3 = d.row("Full − G3")
    diag = d.row("참값 (진단)")
    g2w = d.row("Full − G2w")
    concl = [
        para([("H · G2 · G0 · G1 · G3", {"bold": True}), (": 하나만 꺼도 크게 떨어짐 (95 % 구간이 모두 0 아래)", {})], sz=16, bullet=True, after=3),
        para([("G2w (넓게 받기)", {"bold": True}),
              (f": {g2w['diff']:+.2f} [{g2w['ci'][0]:+.2f}, {g2w['ci'][1]:+.2f}], 0을 걸쳐 효과 불확실".replace("-", "−"), {})],
             sz=16, bullet=True, after=3),
        para([("G3는 시방 합격을 만든다", {"bold": True}), (f": 끄면 {full['spec']} → {g3['spec']}벽", {})], sz=16, bullet=True, after=3),
        para([("참값 (진단)으로 바꿔도 차이 없음", {"bold": True}),
              (f" ({diag['diff']:+.2f}장): 남은 실패의 주원인은 카메라 오차가 아닌 것으로 보임".replace("-", "−"), {})], sz=16, bullet=True, after=3),
        para([("한계", {"bold": True}), (f": 시방 합격 {full['spec']} % (목표 70 %) · 시뮬레이션 · 개발 배치 100벽, 시험 배치 평가 전", {})],
             sz=16, bullet=True)]
    c2 = d.compare(G2C)
    conc_h = 5.0
    if c2 is not None and G2C_KEY in c2["conditions"]:
        e2 = c2["conditions"][G2C_KEY]
        v, h2, hb = e2["vs_base"], e2["first_unfilled_hist"], c2["conditions"][c2["base"]]["first_unfilled_hist"]
        concl.insert(-1, para([("추가 시도 SDCG (놓기 확약 G2c)", {"bold": True}),
                               (f": 자리 6 실패 {hb.get('6', 0)} → {h2.get('6', 0)}벽, 그러나 다른 자리에 새 실패 → 전체 "
                                f"{v['diff_mean']:+.2f} [{v['ci95'][0]:+.2f}, {v['ci95'][1]:+.2f}]장, Full에서 제외 · "
                                "VPRA는 3단 벽에선 실패 원인 아님".replace("-", "−"), {})], sz=16, bullet=True, after=3))
        conc_h = 6.5
    s.text(RX, y, CW, conc_h, concl, name="결론 글")
    y += conc_h + 0.2
    s.text(RX, y, CW, 2.0 if conc_h > 5.0 else 2.35, [para([("정책을 다시 학습하지 않고, ‘지금 손에 든 벽돌’을 아는 검측 단계로", {"bold": True, "color": "FFFFFF"})],
                                  sz=18, algn="ctr", color="FFFFFF", after=2),
                             para([(f"벽당 {none['fill']:.1f} → {full['fill']:.2f}장 (16장 중) · 시방 합격 0 → {full['spec']}벽", {"bold": True, "color": "FFFFFF"})],
                                  sz=20, algn="ctr", color="FFFFFF")],
           fill="1B4F8F", geom="roundRect", anchor="ctr", name="핵심 메시지")
    y += 2.15 if conc_h > 5.0 else 2.5
    s.text(RX, y, CW, 0.75, [para("주요 문헌: Zhao et al. (2023) ACT, RSS · Todorov et al. (2012) MuJoCo, IROS · KCS 41 34 00 조적공사 표준시방서",
                                  sz=11, color="5B6370")], name="문헌")
    right_end = y + 0.75

    # ---- write, preview, check
    tmp = pptx.with_suffix(".tmp.pptx")
    s.write(tmp, b"")
    warns, im = preview(tmp, prev)
    th = im.copy()
    th.thumbnail((256, 256))
    buf = io.BytesIO()
    th.save(buf, "JPEG", quality=85)
    s.write(pptx, buf.getvalue())
    tmp.unlink()
    errs = check_package(pptx)
    miss = check_glyphs(pptx)
    if miss:
        warns.append("나눔고딕에 없는 글자: " + " ".join(miss))
    print(f"왼쪽 끝 y {left_end:.2f} cm · 오른쪽 끝 y {right_end:.2f} cm (흰 단 끝 83.42 cm)")
    if left_end > 83.42 or right_end > 83.42:
        warns.append("단 아래로 넘침")
    for w_ in warns:
        print("주의:", w_)
    for e in errs:
        print("패키지 오류:", e)
    write_md(md, d, a, pptx, figd, prev, F, warns, errs)
    print("만듦:", pptx, figd, prev, md)
    return warns, errs


def write_md(md, d, a, pptx, figd, prev, F, warns, errs):
    rel = lambda p: Path(p).relative_to(md.parent).as_posix()
    full, g1 = d.row("Full"), d.row("Full − G1")
    L = []
    L.append(f"# KSARC 2026 포스터 초안 설명 ({a.tag})\n")
    L.append(f"> 파일: [`{rel(pptx)}`]({rel(pptx)}) (A1 세로 한 장, 학회 양식 `ksarc-포스터 PPT 양식.pptx`에서 만듦) · 미리보기 [`{rel(prev)}`]({rel(prev)})")
    L.append(f"> **포스터의 숫자는 모두 {NOTE}.** 참값 (진단) 줄은 시뮬레이터 정답 좌표를 쓴 진단이라 실제 로봇에서는 불가능하다.")
    L.append("> 만든 스크립트: `sim/wall3/poster_ksarc_20261111.py` (결과 파일만 읽음). 다시 만드는 법은 맨 아래.\n")
    L.append("## 한눈에\n")
    L.append("| 위치 | 블록 | 보여 주는 것 | 형식 |")
    L.append("|---|---|---|---|")
    L.append("| 머리 | 제목 · 저자 · 소속 · 로고 | 제출 초록 제목 그대로, 저자 · 소속은 이전 포스터 줄 그대로 | 양식 글상자 |")
    L.append(f"| 왼쪽 01 | 연구 배경과 질문 | 정책만 {d.row('검측 없음')['fill']:.1f}장 → Full {full['fill']:.2f}장, 시방 합격 0 → {full['spec']}, 채움률 {full['rate']:.1f} % (큰 숫자 3개) · 정책 카메라 입력 3장 | 글 · 수치 상자 · 사진 |")
    L.append("| 왼쪽 02 | 검측 단계 | 벽돌 한 장의 시간 순서 흐름도(G0 → G1 → G2(+G2w) → G3, H 띠) · 6개 제어 표(하는 일 · 쓰는 정보) | 그림 · PowerPoint 표 |")
    L.append("| 왼쪽 03 | 실험 환경과 평가 | Full 완성벽 사진 2장(정면 · 비스듬히) · 환경 · 평가 · 시방 3줄 | 사진 · 글 |")
    L.append("| 왼쪽 07 | H가 작동하는 전제 | 시뮬레이션 → 실제 로봇 → 현장 카드 3장 · H를 끈 결과 한 줄 | 도형 카드 |")
    L.append("| 오른쪽 04 | 결과 1: 사다리 | 1 ~ 5단계 벽당 채운 자리 · 16장 완성 · 시방 합격 | 그림 (작은 그래프 2개) |")
    L.append("| 오른쪽 05 | 결과 2: 하나씩 끄기 | 줄마다 벽당 채운 자리 · 시방 합격 · Full 대비 짝 차이 [95 % 구간] 그래프와 같은 값의 표 | 그림 · PowerPoint 표 |")
    L.append("| 오른쪽 06 | 남은 실패 | 처음 못 채운 자리 분포(Full · Full − G0 · 검측 없음, 1 · 2 · 3단 띠) | 그림 |")
    has_g2c = d.compare(G2C) is not None
    L.append(f"| 오른쪽 08 | 결론 | {6 if has_g2c else 5}줄{' (SDCG 추가 시도 한 줄 포함)' if has_g2c else ''} · 핵심 메시지 상자 · 주요 문헌 | 글 |\n")
    L.append("## 역방향 제거 줄 (포스터 05절과 같은 값)\n")
    L.append("| 조건 | 벽당 채운 자리 | 16장 완성 | 시방 합격 | Full 대비 [95 % 구간] | 출처 |")
    L.append("|---|---|---|---|---|---|")
    for r in d.rows:
        if r["missing"]:
            L.append(f"| {r['label']} | 재측정 중 | | | | `{r['src']}` 없음 |")
            continue
        vs = "기준" if r["kind"] == "full" else f"{r['diff']:+.2f} [{r['ci'][0]:+.2f}, {r['ci'][1]:+.2f}]".replace("-", "−")
        L.append(f"| {r['label']} | {r['fill']:.2f} | {r['complete']} | {r['spec']} | {vs} | `{Path(r['src']).name}` · `{r['key']}` |")
    L.append("")
    L.append("- Full = G0 + G1 + G2 + G2w + G3 + H. 한 제어의 몫 = Full − (그것만 끈 줄) = 위 차이의 부호를 뒤집은 값.")
    if not g1["missing"]:
        L.append(f"- Full − G1은 11-11에 고친 코드(G1 꺼짐 + G0에서 정책 리셋)로 다시 잰 값이다(`{G1FIX}`). 11-10 값(8.52장, 구현 누락)은 쓰지 않았다.")
    L.append("- 같은 설정을 다시 돌려도 값이 조금 갈린다(G0 + G1 + G2 + G3 + H 네 번: 13.30 · 13.57 · 13.39 · 13.40장). G2w의 몫은 이 흔들림과 비슷한 크기다.\n")
    L.append("## 사다리 (포스터 04절)\n")
    L.append("| 단계 | 설정 | 벽당 채운 자리 | 16장 완성 | 시방 합격 | 출처 |")
    L.append("|---|---|---|---|---|---|")
    for s_ in d.ladder:
        src = s_["src"]
        L.append(f"| {s_['short']} | {s_['desc']} | {s_['fill']:.2f} | {s_['complete']} | {s_['spec']} | `{src[1]}` · `{src[2]}` |")
    L.append("\n- 1 · 2단계는 정책 자체(학습 데이터)를 바꾼 단계라 검측 효과만의 사다리가 아니다. 1은 10-22 처음 학습한 정책, 2 이후는 손목 방향을 통일한 데이터로 다시 학습한 정책이다.")
    L.append("- 1 · 2단계의 16장 완성 수는 요약 파일에 없어 그 평가의 rollout.json에서 셌다(읽기만).\n")
    L.append("## 그림 · 사진 파일\n")
    L.append("| 파일 | 내용 | 크기 (포스터 위, cm) |")
    L.append("|---|---|---|")
    desc = {"그림1": "검측 단계 흐름도 (matplotlib)", "그림2": "단계별 사다리 (벽당 채운 자리 / 16장 완성 · 시방 합격)",
            "그림3": "역방향 제거 (채운 자리 · 시방 합격 · Full 대비 차이 [95 % 구간])", "그림4": "처음 못 채운 자리 분포",
            "사진1": "정책 입력 카메라 3장 (집기 직전, 11-04 진단 그림 3장을 이어 붙임)", "사진2": "Full 완성벽 700300 정면 (11-11 다시 돌린 장면에서 자름)",
            "사진3": "Full 완성벽 700300 비스듬히"}
    for n, (p, w, h) in F.items():
        L.append(f"| [`{rel(p)}`]({rel(p)}) | {desc[n.split('_')[0]]} | {w:.1f} × {h:.1f} |")
    L.append("\n## 데이터 출처 (sha256 앞 16)\n")
    for k, v in sorted(d.sources.items()):
        L.append(f"- `{k}` {v}")
    L.append("\n## 확인할 것 · 남은 것\n")
    L.append("- **제목**: 제출 초록 제목(‘모방학습 조적 로봇의 파지·배치 검측 단계별 효과’)을 그대로 두었다. 내용은 초록의 3장 실험이 아니라 3단 16장 벽 실험(11-10 역방향 제거)이다. 학회 규정상 제목을 바꿀 수 있는지 확인이 필요하다.")
    L.append("- **저자 · 소속**: 이전 포스터(`KSARC2026_포스터_논문본문반영.pptx`)의 줄을 그대로 옮겼다.")
    L.append("- **이름**: 이전 포스터의 ‘G0 실행가능성 필터’와 이번 ‘G0 집기 정렬’은 다른 제어다. 이번 포스터는 11-10 이름 정리(G0 · G1 · G2 · G2w · G3 · H)만 쓴다.")
    if d.compare(G2C) is not None:
        L.append("- **SDCG · VPRA**: 결론에 한 줄로만 넣었다. SDCG는 G2c(놓기 확약)로 구현해 Full + G2c 대 Full 다시를 쟀다"
                 " (`eval_lg_g2c_20261111_compare.json`). 겨냥한 자리 6 실패는 줄었으나 다른 자리(7 · 1단)에 새 실패가 생겨 전체 효과가 0을 걸쳤다."
                 " 새 실패의 일부는 힘 감지의 오감지로 보인다(추론, 스토리라인 'SDCG · VPRA 검토'). Full에 넣지 않았다."
                 " VPRA는 완성벽 시방 여유로 3단 벽의 실패 원인이 아니라 구현하지 않았다. 표 · 그래프의 Full은 G0 + G1 + G2 + G2w + G3 + H다.")
    else:
        L.append("- **SDCG · VPRA**: 아직 포스터에 없다. 넣게 되면 새 Full과 줄을 `--rows-json` 또는 `--extra`로 주고 `--tag`를 새로 해 다시 만든다.")
    L.append("- **최종 평가**: 시험 배치(730000번대)는 쓰지 않았다(사용 허락 필요). 포스터 숫자는 개발 배치다.")
    L.append("- **글꼴**: 양식대로 나눔고딕 · 나눔고딕 ExtraBold · 맑은 고딕. 나눔고딕이 없는 PC에서는 다른 글꼴로 바뀌어 줄바꿈이 달라질 수 있다.")
    L.append("- **빼기 기호**: 나눔고딕에 수학 빼기(−, U+2212) · ≫ 글자가 없어서, pptx 글자(표 · 글상자)에서는 ‘Full – G0’처럼 짧은 줄표(–)로 바꿔 넣었다. 그림(PNG) 안은 −를 그대로 쓴다.\n")
    L.append("## 만든 방식 · 다시 만드는 법\n")
    L.append("- 이 컴퓨터에 python-pptx · node(pptxgenjs) · LibreOffice가 없어서, 양식 pptx를 그대로 복사하고 `ppt/slides/slide1.xml`만 lxml로 새로 짰다. 양식의 머리 · 바탕 · 두 단 · 로고 · 글머리 그림은 그대로이고, 예시 칸(제목 · 본문 · 안내문)은 지웠다.")
    L.append("- 그래프는 PowerPoint 기본 차트가 아니라 **PNG 그림**이다(위 이유). 값을 바꾸려면 스크립트를 다시 돌린다. 표 두 개(검측 단계 · 역방향 제거)는 PowerPoint 표라 직접 고칠 수 있다.")
    L.append("- 미리보기 PNG는 PowerPoint 렌더가 아니라, 스크립트가 도형 위치와 글자를 대략 그린 것이다(글자 넘침 · 겹침 점검용). 글머리 그림은 그리지 않는다. PowerPoint에서 한 번 열어 확인해야 한다.")
    L.append("- 패키지 점검: 스크립트 자체 점검(관계 대상 · 내용 형식 · XML · 도형 id)과 pptx 스킬의 `validate.py --original <양식>` 모두 통과(이 컴퓨터에서 PowerPoint로 열어 보지는 못함).")
    L.append(f"- 점검 결과: 글자 넘침 · 겹침 경고 {len(warns)}건, 패키지 오류 {len(errs)}건." + ("" if not (warns or errs) else " " + " / ".join(warns + errs)))
    L.append("- 다시 만들기 (출력이 있으면 덮어쓰지 않으므로 `--tag`를 새로 준다):")
    L.append("  ```")
    L.append("  cd sim && MPLCONFIGDIR=/tmp/mpl PYTHONPATH=. venv/bin/python -m wall3.poster_ksarc_20261111 --tag 20261111b \\")
    L.append("      [--extra eval_새비교.json:평가폴더/조건:\"Full − SDCG\"] [--rows-json 줄목록.json]")
    L.append("  ```")
    L.append("  `--rows-json`은 `[[compare json, 키, 줄 이름, 종류], ...]` (종류: full · loo · none · diag). 새 Full로 바꿀 때 쓴다.")
    md.write_text("\n".join(L) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="20261111")
    ap.add_argument("--rows-json", default=None)
    ap.add_argument("--extra", nargs="*", default=[], help="compare.json:key:label (appended rows)")
    ap.add_argument("--out-dir", default=None, help="default 02_KSARC2026 (a scratch dir for trial builds)")
    a = ap.parse_args()
    build(a)


if __name__ == "__main__":
    main()
