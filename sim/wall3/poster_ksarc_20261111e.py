"""KSARC 2026 포스터 e판 (2026-11-11 밤). 결과 파일만 읽는다. 시뮬레이션 없음.

d판(poster_ksarc_20261111d.py)에서 사용자 지시(11-11)로 바꾼 것. 숫자는 d판과 같다(wall3.primary_metrics_20261111.compute()).
- 3.3 결과의 주 그림 = '자리별 채운 벽 수'(후보 1을 다듬음). 100벽 모자이크는 뺐다. 제목은 한 줄, 제목과 첫 줄(Full) 사이에
  쌓는 벽 그림(자리 번호 1 ~ 16), 열 번호도 1 ~ 16. 그림 안에 시작값(700300 …)을 적지 않는다.
- 3.1 실험 환경 세팅 = 로봇 팔 · 카메라 · 벽돌이 모두 보이는 그림(fig_env_scene_20261111.py가 만든 PNG를 복사). 완성 벽 사진 2장은 뺐다.
- 결과 표 = 조건 · 완성한 벽 · Full과의 차이 · 차이의 95 % 구간 · 판정. 벽당 채운 자리와 그 차이 열은 뺐다(보조 지표, d판 설명 md에 남음).
- 시방 항목 그림을 다시 그렸다: 결론을 제목으로, 항목마다 무엇을 재는지 작은 그림 + 한 줄 설명, 허용오차 밖 영역 표시.
- 평가 기준 그림에서 모자이크 색 설명을 뺐다.
- 1절(연구 배경 및 목적)을 줄글에서 '꼬리표 + 내용' 7줄로 나눴다: 문제의 빈틈 3가지 · 예상 기여 3가지는 카드, 연구 목적은 강조 상자,
  결과는 그림 1(정책만 → Full의 벽 그림과 완성률). 숫자 상자 3개는 그림 1로 합쳤다. 글 내용은 d판과 같다.
- 참고문헌은 d판 그대로(4편, 작은 글씨).
숫자는 모두 개발 배치 100벽 · 최종 평가 전. 참값 줄은 '참값 (진단)'. 출력이 이미 있으면 덮어쓰지 않는다.

실행: cd sim && MPLCONFIGDIR=<임시>/mpl PYTHONPATH=. venv/bin/python -m wall3.poster_ksarc_20261111e [--tag 20261111e] [--out-dir <임시>]
"""
import argparse, io, json, os, shutil
from pathlib import Path

import numpy as np

from wall3 import primary_metrics_20261111 as pm
from wall3.fig_slot_iou_20261111 import EDGE, HI, LO
from wall3.fig_slot_kcs_20261111 import load_all, summarize, text_color
from wall3.poster_ksarc_20261111 import (AFFIL, AUTHORS_EN, AUTHORS_KO, BLUE, GREY, GRID, INK, INK2, KS, NOTE, NS, ORANGE, Slide,
                                         check_glyphs, check_package, fig_flow, fig_size, mpl_setup, para, preview, quiet, sha16)
from wall3.poster_ksarc_20261111d import (ACK, DARK, EMPTY_EDGE, FILLED, ORDER, TABLE, TITLE_EN, TITLE_KO, TITLE_KO_SUB, fmt2,
                                          fmt_pp, wall_rects)

ENV_PNG = KS / "그림_실험환경_20261111" / "실험환경_로봇_카메라_벽돌.png"     # fig_env_scene_20261111.py 출력 (26.6 × 9.6 cm)
ENV_CM = (26.6, 9.6)
SUB = {"Full": "검측 6단계 모두", "Full − G2w": "넓게 받기 끔", "Full − G3": "놓은 뒤 재배치 끔", "Full − G2": "놓기 전 보정 끔",
       "Full − G0": "집기 정렬 끔", "Full − G1": "집기 확인 끔", "Full − H": "손에 든 벽돌 기준 끔", "검측 없음": "정책만"}
BRICK, BRICK_EDGE = "#e9ecf0", "#8f98a5"
TAG_FILL, GOAL_FILL, GAP_FILL = "DCE7F5", "EEF3FA", "FCEDE5"   # 1절 꼬리표 · 강조 상자와 기여 카드 · 빈틈 카드
ZONE = "#f1f3f5"                                     # 허용오차 밖 영역 (옅은 회색)
TOL = 6.0                                            # ② ③ ④ 허용오차 (mm), 평가지표 md 2.2절
# (키, 이름, 그림 속 한 줄 설명) — 평가지표 md 2.3절 정의를 줄인 말
ITEM_ROWS = [("2", "② 선 및 면", "벽 앞면이 평평한가,\n단 윗면이 수평인가"),
             ("3", "③ 수직도", "위 단이 1단 앞면의 수직선에서\n벗어난 거리"),
             ("4", "④ 평면상 위치", "1단이 바닥 기준선에서\n벗어난 거리")]


# ---------------------------------------------------------------------------------------------- 글자 도우미
def fmt_n(v):
    """벽 수 차이: 0은 부호 없이, 나머지는 부호를 붙인다."""
    return "0" if round(v) == 0 else f"{v:+.0f}".replace("-", "−")


def fmt_ci(ci):
    return f"{fmt_n(ci[0])} ~ {fmt_n(ci[1])}"


def verdict(ci):
    """완성한 벽 수 차이(조건 − Full)의 95 % 구간 → 판정. 구간이 0 아래에만 있으면 몫 있음, 0을 포함하면 구별 못 함."""
    if ci[1] < 0:
        return "몫 있음"
    if ci[0] > 0:
        return "Full보다 많음"
    return "구별 못 함"


def slot_columns(x0=5.2, cw=0.99, hw=0.62, g=0.05, gc=0.30):
    """16자리 칸의 (x, 너비) cm, 쌓는 순서. 반장 자리(6 · 11번)는 좁게, 단 사이는 띄운다."""
    widths = [cw] * 5 + [hw] + [cw] * 4 + [hw] + [cw] * 5
    xs, x = [], x0
    for k, wd in enumerate(widths):
        if k:
            x += gc if k in (5, 11) else g
        xs.append((x, wd))
        x += wd
    return xs


def _canvas(w, h, plt):
    fig = fig_size(w, h, plt)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, w)
    ax.set_ylim(0, h)
    ax.axis("off")
    return fig, ax


# ---------------------------------------------------------------------------------------------- 그림
def fig_summary(S, R, sig_s, drops, unsig, path, w, h, plt):
    """1절 '결과' 줄의 그림: 정책만 → Full(정책 + 검측 6단계). 벽돌 색 = 그 자리를 채운 벽 수(100벽 중, 그림 5와 같은 색),
    아래에 완성률. 오른쪽은 검측 단계 하나를 껐을 때의 완성률 변화."""
    from matplotlib.colors import LinearSegmentedColormap
    from matplotlib.patches import FancyArrowPatch, Rectangle
    cmap = LinearSegmentedColormap.from_list("seq", [LO, HI])
    fig, ax = _canvas(w, h, plt)
    ww = 6.4
    sw = ww / 990.0
    wh = 191.0 * sw
    wy = h - 0.72 - wh
    full, none = R["Full"], R["검측 없음"]
    panels = [(0.2, "검측 없음", "정책만", f"완성률 {none['complete']} %", f"벽당 {none['filled_mean']:.1f}장 (16자리 중)"),
              (8.75, "Full", "Full = 정책 + 검측 6단계", f"완성률 {full['complete']} %",
               f"벽당 {full['filled_mean']:.1f}장 · 시방 합격 {full['spec_pass']} %")]
    dark = "#1b4f8f"
    for x, lab, title, big, small in panels:
        ax.text(x, h - 0.14, title, ha="left", va="top", fontsize=11.5, color=INK, fontweight="bold")
        ax.plot([x - 0.08, x + ww + 0.08], [wy - 0.035] * 2, color=INK2, lw=1.2)
        for (x0, z0, L, H), v in zip(wall_rects(), S[lab]["fill"]):
            ax.add_patch(Rectangle((x + (x0 + 495.0) * sw, wy + z0 * sw), L * sw, H * sw, facecolor=cmap(v / 100), edgecolor=EDGE,
                                   linewidth=0.7))
        ax.text(x, wy - 0.2, big, ha="left", va="top", fontsize=16, color=dark, fontweight="bold")
        ax.text(x, wy - 0.95, small, ha="left", va="top", fontsize=10.5, color=INK2)
    xa0, xa1 = panels[0][0] + ww + 0.3, panels[1][0] - 0.3
    ya = wy + wh / 2
    ax.add_patch(FancyArrowPatch((xa0, ya), (xa1, ya), arrowstyle="-|>", mutation_scale=16, color=INK2, lw=1.5))
    ax.text((xa0 + xa1) / 2, ya + 0.2, "검측 6단계", ha="center", va="bottom", fontsize=9.5, color=INK2)
    xd = panels[1][0] + ww + 0.45
    ax.plot([xd, xd], [0.5, h - 0.15], color=GRID, lw=1.2)
    xr = xd + 0.4
    ax.text(xr, h - 0.14, "검측 단계를 하나만 끄면", ha="left", va="top", fontsize=11.5, color=INK, fontweight="bold")
    ax.text(xr, ya, sig_s, ha="left", va="center", fontsize=13, color=INK)
    ax.text(xr, wy - 0.2, f"완성률 −{min(drops):.0f} ~ −{max(drops):.0f} %p", ha="left", va="top", fontsize=16, color=dark, fontweight="bold")
    ax.text(xr, wy - 0.95, f"{' · '.join(unsig)}는 구별되지 않음", ha="left", va="top", fontsize=10.5, color=INK2)
    ax.text(0.2, 0.08, "벽 그림의 색 = 그 자리를 채운 벽 수 (100벽 중, 진할수록 많음)", ha="left", va="bottom", fontsize=9, color=INK2)
    fig.savefig(path, dpi=300, facecolor="white")
    plt.close(fig)


def set_table_heights(s, first_h, row_h, n_rows):
    """방금 넣은 표의 머리 줄 높이를 따로 주고, 표 틀 높이를 줄 높이의 합으로 맞춘다."""
    fr = s.tree[-1]
    fr.find(".//a:tr", NS).set("h", str(int(round(first_h * 360000))))
    fr.find("p:xfrm/a:ext", NS).set("cy", str(int(round((first_h + row_h * (n_rows - 1)) * 360000))))
    return first_h + row_h * (n_rows - 1)


def fig_main(S, path, w, h, plt):
    """주 결과 그림: 줄 = 조건, 칸 = 그 자리를 채운 벽 수(100벽 중), 끝 두 칸 = 벽 전체 판정(완성 · 시방 합격).
    제목과 첫 줄 사이에 쌓는 벽 그림을 두고 자리마다 1 ~ 16 번호를 붙인다."""
    from matplotlib.colors import LinearSegmentedColormap
    from matplotlib.patches import Rectangle
    cmap = LinearSegmentedColormap.from_list("seq", [LO, HI])
    fig, ax = _canvas(w, h, plt)
    xs = slot_columns()
    xe = xs[-1][0] + xs[-1][1]
    xw = [(xe + 0.55, 2.0), (xe + 0.55 + 2.1, 2.0)]
    xend = xw[-1][0] + xw[-1][1]
    rh, pitch, yb = 0.9, 1.22, 0.78
    n = len(ORDER)
    for i, lab in enumerate(ORDER):
        s = S[lab]
        y = yb + (n - 1 - i) * pitch
        ax.add_patch(Rectangle((0.15, y - 0.11), xend, rh + 0.22, fill=False, edgecolor=GREY, linewidth=1.0))
        ax.text(0.38, y + 0.62, lab, ha="left", va="center", fontsize=12, color=INK, fontweight="bold" if lab == "Full" else None)
        ax.text(0.38, y + 0.21, SUB[lab], ha="left", va="center", fontsize=9, color=INK2)
        for (cx, wd), v in zip(xs, s["fill"]):
            c = cmap(v / 100)
            ax.add_patch(Rectangle((cx, y), wd, rh, facecolor=c, edgecolor=EDGE, linewidth=0.7))
            ax.text(cx + wd / 2, y + rh / 2, str(int(v)), ha="center", va="center", fontsize=10 if wd > 0.8 else 8, color=text_color(c))
        for (cx, wd), v in zip(xw, (s["complete"], s["spec"])):
            c = cmap(v / 100)
            ax.add_patch(Rectangle((cx, y), wd, rh, facecolor=c, edgecolor=EDGE, linewidth=0.7))
            ax.text(cx + wd / 2, y + rh / 2, str(int(v)), ha="center", va="center", fontsize=12.5, color=text_color(c), fontweight="bold")
    ytop = yb + (n - 1) * pitch + rh + 0.11
    # 머리 줄: 자리 번호 1 ~ 16, 단 묶음
    ax.text(0.38, ytop + 0.12, "조건", ha="left", va="bottom", fontsize=10.5, color=INK2)
    for k, (cx, wd) in enumerate(xs):
        ax.text(cx + wd / 2, ytop + 0.12, str(k + 1), ha="center", va="bottom", fontsize=10.5, color=INK)
    for (cx, wd), name in zip(xw, ("완성", "시방 합격")):
        ax.text(cx + wd / 2, ytop + 0.12, name, ha="center", va="bottom", fontsize=11, color=INK, fontweight="bold")
    yg = ytop + 0.68
    for a, b, name in ((0, 4, "1단"), (5, 10, "2단"), (11, 15, "3단")):
        xa, xb_ = xs[a][0], xs[b][0] + xs[b][1]
        ax.plot([xa, xb_], [yg, yg], color=INK2, lw=1.0)
        ax.text((xa + xb_) / 2, yg + 0.08, name, ha="center", va="bottom", fontsize=11, color=INK)
    ax.plot([xw[0][0], xend], [yg, yg], color=INK2, lw=1.0)
    ax.text((xw[0][0] + xend) / 2, yg + 0.08, "벽 전체", ha="center", va="bottom", fontsize=11, color=INK)
    # 쌓는 벽 그림 (실제 비율), 자리 번호 = 쌓는 순서
    ww = 14.0
    sw = ww / 990.0
    wx0 = (xs[0][0] + xe) / 2 - ww / 2
    wy0 = yg + 0.95
    ax.plot([wx0 - 0.3, wx0 + ww + 0.3], [wy0 - 0.05, wy0 - 0.05], color=INK2, lw=1.4)
    for k, (x0, z0, L, H) in enumerate(wall_rects()):
        bx, by = wx0 + (x0 + 495.0) * sw, wy0 + z0 * sw
        ax.add_patch(Rectangle((bx, by), L * sw, H * sw, facecolor=BRICK, edgecolor=BRICK_EDGE, linewidth=0.9))
        ax.text(bx + L * sw / 2, by + H * sw / 2, str(k + 1), ha="center", va="center", fontsize=12.5, color=INK, fontweight="bold")
    for c in range(3):
        ax.text(wx0 - 0.42, wy0 + (c * 67.0 + 28.5) * sw, f"{c + 1}단", ha="right", va="center", fontsize=11, color=INK)
    wtop = wy0 + 191.0 * sw
    ax.text(0.38, wtop - 0.12, "쌓는 벽", ha="left", va="top", fontsize=13, color=INK, fontweight="bold")
    ax.text(0.38, wtop - 0.85, "3단 · 16자리", ha="left", va="top", fontsize=10.5, color=INK2)
    ax.text(0.38, wtop - 1.4, "번호 = 쌓는 순서", ha="left", va="top", fontsize=10.5, color=INK2)
    # 색 눈금
    cx0, cy0, cwid = xw[0][0] + 0.15, wy0 + 1.05, 3.6
    cax = fig.add_axes([cx0 / w, cy0 / h, cwid / w, 0.3 / h])
    cb = fig.colorbar(plt.cm.ScalarMappable(norm=plt.Normalize(0, 100), cmap=cmap), cax=cax, orientation="horizontal")
    cb.set_ticks([0, 50, 100])
    cb.ax.tick_params(labelsize=9.5, length=0, colors=INK2)
    cb.outline.set_edgecolor(EDGE)
    cb.outline.set_linewidth(0.8)
    ax.text(cx0, cy0 + 0.42, "칸 색 = 채운 벽 수", ha="left", va="bottom", fontsize=10.5, color=INK2)
    ax.text(0.15, h - 0.22, "자리별 채운 벽 수 (조건마다 100벽)", ha="left", va="top", fontsize=15, color=INK, fontweight="bold")
    ax.text(0.15, 0.12, "칸의 숫자 = 그 자리를 채운 벽 수 · 완성 = 16자리를 모두 채운 벽 · 시방 합격 = 완성한 벽 가운데 KCS 41 34 00 허용오차를 모두 지킨 벽",
            ha="left", va="bottom", fontsize=9.5, color=INK2)
    assert wtop < h - 0.85, (wtop, h)
    fig.savefig(path, dpi=300, facecolor="white")
    plt.close(fig)


def _arrow(ax, p0, p1):
    ax.annotate("", p1, p0, arrowprops=dict(arrowstyle="<->", color=INK, lw=1.1, shrinkA=0, shrinkB=0, mutation_scale=7))


def icon_plane(ax, x, y):
    """② 위에서 본 한 단: 앞면이 들쭉날쭉한 폭."""
    from matplotlib.patches import Rectangle
    offs = [0.0, 0.17, -0.13, 0.09, -0.05]
    bw, bh, g = 0.47, 0.24, 0.035
    yc = y + 0.95
    for i, o in enumerate(offs):
        ax.add_patch(Rectangle((x + 0.1 + i * (bw + g), yc + o), bw, bh, facecolor=BRICK, edgecolor=BRICK_EDGE, linewidth=0.8))
    lo, hi = yc + min(offs), yc + max(offs)
    for v in (lo, hi):
        ax.plot([x + 0.02, x + 2.72], [v, v], color=INK, lw=0.9, ls=(0, (3, 2)))
    _arrow(ax, (x + 2.86, lo), (x + 2.86, hi))
    ax.text(x + 1.37, y + 0.28, "위에서 본 벽 앞면", ha="center", va="center", fontsize=8.5, color=INK2)


def icon_plumb(ax, x, y):
    """③ 옆에서 본 벽: 1단 앞면에서 세운 수직선과 위 단 앞면의 거리."""
    from matplotlib.patches import Rectangle
    bw, bh, j = 0.52, 0.33, 0.06
    xf = x + 1.05                                                  # 1단 앞면
    ax.plot([x + 0.45, x + 2.45], [y + 0.5, y + 0.5], color=INK2, lw=1.3)
    for c, o in enumerate((0.0, 0.12, 0.30)):
        ax.add_patch(Rectangle((xf + o, y + 0.5 + c * (bh + j)), bw, bh, facecolor=BRICK, edgecolor=BRICK_EDGE, linewidth=0.8))
    top = y + 0.5 + 3 * bh + 2 * j
    ax.plot([xf, xf], [y + 0.5, top + 0.28], color=INK, lw=0.9, ls=(0, (3, 2)))
    _arrow(ax, (xf, top + 0.14), (xf + 0.30, top + 0.14))
    ax.text(xf - 0.12, top + 0.16, "수직선", ha="right", va="center", fontsize=8.5, color=INK2)
    ax.text(x + 1.45, y + 0.28, "옆에서 본 벽", ha="center", va="center", fontsize=8.5, color=INK2)


def icon_position(ax, x, y):
    """④ 위에서 본 1단: 바닥 기준선과 1단 앞면의 거리."""
    from matplotlib.patches import Rectangle
    bw, bh, g = 0.47, 0.24, 0.035
    yl = y + 0.72
    ax.plot([x + 0.02, x + 2.72], [yl, yl], color=INK, lw=0.9, ls=(0, (3, 2)))
    for i in range(5):
        ax.add_patch(Rectangle((x + 0.1 + i * (bw + g), yl + 0.3), bw, bh, facecolor=BRICK, edgecolor=BRICK_EDGE, linewidth=0.8))
    _arrow(ax, (x + 2.86, yl), (x + 2.86, yl + 0.3))
    ax.text(x + 0.1, yl + 0.74, "위에서 본 1단", ha="left", va="center", fontsize=8.5, color=INK2)
    ax.text(x + 1.37, y + 0.36, "바닥 기준선", ha="center", va="center", fontsize=8.5, color=INK2)


def fig_items(res, path, w, h, plt):
    """주 지표 2: 완성한 벽의 ② ③ ④ 측정값. 줄 = 항목, 항목마다 Full(위) · Full − G3(아래), 점 하나 = 완성한 벽 하나."""
    rows = {r["label"]: r for r in res["rows"]}
    conds = [("Full", BLUE), ("Full − G3", ORANGE)]
    xmax = 16.0
    vals = {lab: {k: np.array([wd["items"][k] for wd in rows[lab]["walls_detail"] if wd["complete"]], float) for k, _, _ in ITEM_ROWS}
            for lab, _ in conds}
    nw = {lab: len(vals[lab]["2"]) for lab, _ in conds}
    fig, ax = _canvas(w, h, plt)
    ax0, ay0, aw, ah = 10.5, 1.3, 11.9, h - 3.25
    step, half = 2.7, 1.35
    ylo, yhi = -(len(ITEM_ROWS) - 1) * step - half, half
    ycm = lambda yd: ay0 + (yd - ylo) / (yhi - ylo) * ah
    axs = fig.add_axes([ax0 / w, ay0 / h, aw / w, ah / h])
    axs.axvspan(TOL, xmax, color=ZONE, zorder=0, linewidth=0)
    rng = np.random.default_rng(1)
    for k, (key, name, text) in enumerate(ITEM_ROWS):
        yk = -k * step
        for j, (lab, col) in enumerate(conds):
            y = yk + 0.5 - j * 1.0
            v = vals[lab][key]
            ins = v <= xmax
            axs.scatter(v[ins], y + rng.uniform(-0.28, 0.28, int(ins.sum())), s=20, color=col, alpha=0.85, linewidths=0, zorder=3)
            for q in v[~ins]:                                    # 축 밖의 값: 끝에 세모와 값을 적는다
                axs.scatter([xmax - 0.25], [y], s=34, marker=">", color=col, linewidths=0, zorder=3)
                axs.text(xmax - 0.6, y, f"{q:.1f}", ha="right", va="center", fontsize=9.5, color=INK2)
            med = float(np.median(v))
            axs.plot([med, med], [y - 0.38, y + 0.38], color=INK, lw=1.7, zorder=4)
            ax.text(ax0 - 0.18, ycm(y), lab, ha="right", va="center", fontsize=10.5, color=INK2)
            n_over = int((v > TOL).sum())
            ax.text(ax0 + aw + 0.35, ycm(y), f"{len(v)}벽 중 {n_over}", ha="left", va="center", fontsize=11.5, color=INK,
                    fontweight="bold" if n_over else None)
        cy = ycm(yk)
        (icon_plane, icon_plumb, icon_position)[k](ax, 0.25, cy - 0.95)
        ax.text(3.55, cy + 0.42, name, ha="left", va="center", fontsize=12.5, color=INK, fontweight="bold")
        ax.text(3.55, cy - 0.32, text, ha="left", va="center", fontsize=9.5, color=INK2, linespacing=1.3)
        if k:
            ax.plot([0.15, w - 0.15], [ycm(yk + half)] * 2, color=GRID, lw=1.0)
    axs.axvline(TOL, color=INK, lw=1.2, ls=(0, (4, 3)), zorder=2)
    axs.set_xlim(0, xmax)
    axs.set_ylim(ylo, yhi)
    axs.set_yticks([])
    axs.set_xticks(range(0, 17, 2))
    axs.tick_params(axis="x", labelsize=10.5)
    axs.set_xlabel("기준에서 어긋난 크기 (mm)", fontsize=11)
    quiet(axs, "x")
    ytx = ay0 + ah + 0.1
    xcm = lambda xd: ax0 + xd / xmax * aw
    ax.text(xcm(TOL) - 0.15, ytx, "허용오차 6 mm 안", ha="right", va="bottom", fontsize=10.5, color=INK)
    ax.text(xcm(TOL) + 0.15, ytx, "허용오차 밖", ha="left", va="bottom", fontsize=10.5, color=INK)
    ax.text(ax0 + aw + 0.35, ytx, "6 mm 넘은 벽", ha="left", va="bottom", fontsize=10.5, color=INK2)
    ax.text(0.15, h - 0.2, "G3(놓은 뒤 재배치)를 끄면 완성한 벽도 허용오차 6 mm를 넘는다", ha="left", va="top", fontsize=14,
            color=INK, fontweight="bold")
    ax.text(0.15, h - 0.98, f"점 하나 = 완성한 벽 하나 (Full {nw['Full']}벽 · Full − G3 {nw['Full − G3']}벽) · 굵은 세로줄 = 중앙값",
            ha="left", va="top", fontsize=10.5, color=INK2)
    fig.savefig(path, dpi=300, facecolor="white")
    plt.close(fig)


def fig_eval(path, w, h, plt):
    """채움(느슨) → 완성(주 지표 1) → 시방 합격(보조) 판정 사다리. d판 그림에서 모자이크 색 설명만 뺐다."""
    from matplotlib.patches import FancyArrowPatch, Rectangle
    fig, ax = _canvas(w, h, plt)
    rects = wall_rects()
    steps = [
        ("자리 채움", "설계 자리 중심에서 수평 45 mm, 높이 28.5 mm,\n기울기 45° 안이면 채움 (느슨한 존재 확인)", [1] * 9 + [0] * 7, FILLED, "벽당 채운 자리 (보조)"),
        ("벽 완성", "16자리를 모두 채움", [1] * 16, FILLED, "완성률 (주 지표 1)"),
        ("시방 합격", "완성 + KCS 41 34 00 ①~⑤ 모두\n(②③④ 6 mm, ① 줄눈 10 ± 3 mm)", [1] * 16, BLUE, "시방 합격률 (보조)"),
    ]
    n = len(steps)
    gap = 0.9
    bw = (w - gap * (n - 1)) / n
    s = 2.1 / 990.0                                          # 벽 그림 너비 2.1 cm
    for i, (name, crit, filled, col, metric) in enumerate(steps):
        x = i * (bw + gap)
        ix, iz = x + 0.15, h - 0.55 - 191 * s
        for (x0, z0, L, H), f in zip(rects, filled):
            ax.add_patch(Rectangle((ix + (x0 + 495) * s, iz + z0 * s), L * s, H * s, facecolor=col if f else "white",
                                   edgecolor="white" if f else EMPTY_EDGE, linewidth=0.6))
        ax.text(ix + 2.1 + 0.3, h - 0.42, name, ha="left", va="top", fontsize=15, color=INK, fontweight="bold")
        ax.text(ix + 2.1 + 0.3, h - 1.15, metric, ha="left", va="top", fontsize=11.5, color="#1b4f8f")
        ax.text(x + 0.15, h - 1.95, crit, ha="left", va="top", fontsize=11.5, color=INK2, linespacing=1.3)
        if i < n - 1:
            ax.add_patch(FancyArrowPatch((x + bw - 0.25, h - 0.95), (x + bw + gap - 0.15, h - 0.95), arrowstyle="-|>",
                                         mutation_scale=16, color=INK2, lw=1.5))
    ax.text(0.15, 0.12, "주 지표 2 = 완성된 벽의 시방 항목 ①~⑤ 측정값 (mm, 연속값)  ·  채움 판정은 시방보다 훨씬 느슨하다",
            ha="left", va="bottom", fontsize=12, color=INK)
    fig.savefig(path, dpi=300, facecolor="white")
    plt.close(fig)


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
    if not ENV_PNG.exists():
        raise SystemExit(f"{ENV_PNG} 없음: fig_env_scene_20261111.py를 먼저 돌릴 것 (MuJoCo 필요, 커밋된 PNG가 있으면 그대로 쓴다)")
    res = pm.compute()
    R = {r["label"]: r for r in res["rows"]}
    sources = dict(res["sources"])
    data, src2 = load_all()
    sources.update(src2)
    S = {lab: summarize(ws) for lab, ws in data.items()}
    for lab in ORDER:                                      # 두 계산이 같은 값을 내는지 (같은 rollout.json)
        assert R[lab]["walls"] == 100 and S[lab]["complete"] == R[lab]["complete"] and S[lab]["spec"] == R[lab]["spec_pass"], lab
    dsum = pm.W / "eval_lf_full_diffusion_20261110" / "summary.json"
    dv = json.loads(dsum.read_bytes())["diffusion_all_held+k2+k7"]
    DIFF = {"fill": dv["slots_filled_mean"], "complete": dv["walls_complete"], "spec": dv["spec_pass"]}
    gc = pm.W / "eval_lg_g2c_20261111_compare.json"
    G2C_V = json.loads(gc.read_bytes())["conditions"]["eval_lg_full2_20261111/act_all_held+k2+k7+k8"]["vs_base"]
    for q in (dsum, gc):
        sources[pm.relkey(q)] = sha16(q)
    sources["02_KSARC2026/그림_실험환경_20261111/" + ENV_PNG.name] = sha16(ENV_PNG)
    full, none, g3, noh, diag = R["Full"], R["검측 없음"], R["Full − G3"], R["Full − H"], R["참값 (진단)"]
    loo = [R[k] for k in ORDER[1:7]]
    drops = [-r["vs_full"]["complete_pp"] for r in loo if r["vs_full"]["complete_ci_pp"][1] < 0]
    sig = [r["label"].replace("Full − ", "") for r in loo if r["vs_full"]["complete_ci_pp"][1] < 0]
    unsig = [r["label"].replace("Full − ", "") for r in loo if r["vs_full"]["complete_ci_pp"][1] >= 0]
    sig_s = " · ".join(sorted(sig, key=lambda s: ["G0", "G1", "G2", "G3", "H"].index(s) if s in ["G0", "G1", "G2", "G3", "H"] else 9))
    g3i = g3["vs_full"]["items"]
    plt = mpl_setup()
    figd.mkdir(parents=True)

    LX, RX, CW, HH = 1.78, 30.99, 26.6, 2.19
    S1_TAG, S1_GAP, S1_ROW = 3.5, 0.35, 0.16              # 1절: 꼬리표 너비, 꼬리표와 내용 사이, 줄 사이
    F = {}

    def fig(name, w, h):
        F[name] = (figd / name, w, h)
        return figd / name, w, h

    p, w, h = fig("그림1_정책만_대_검측6단계.png", CW - S1_TAG - S1_GAP, 3.8)
    fig_summary(S, R, sig_s, drops, unsig, p, w, h, plt)
    p, w, h = fig("그림2_검측단계_흐름도.png", CW, 8.6)
    fig_flow(p, w, h, plt)
    p, w, h = fig("그림3_실험환경_로봇_카메라_벽돌.png", *ENV_CM)
    shutil.copyfile(ENV_PNG, p)
    p, w, h = fig("그림4_평가기준_채움_완성_시방.png", CW, 4.0)
    fig_eval(p, w, h, plt)
    p, w, h = fig("그림5_자리별_채운벽수_조건별.png", CW, 16.0)
    fig_main(S, p, w, h, plt)
    p, w, h = fig("그림6_시방항목_Full_FullG3.png", CW, 10.2)
    fig_items(res, p, w, h, plt)
    if a.figures_only:
        print("그림만 만듦:", figd)
        return

    s = Slide()
    s.set_runs("직사각형 8", [(TITLE_KO, 46), (TITLE_KO_SUB, 30), (TITLE_EN, 22)])
    s.set_runs("Text Box 274", [(AUTHORS_KO, 32), (AUTHORS_EN, 26)])
    s.set_runs("Text Box 275", [(t, 18) for t in AFFIL])
    s.remove([f"직사각형 {k}" for k in range(17, 29)])

    def sub(x, y, label):
        s.text(x, y, CW, 1.0, [para([(label, {"bold": True, "color": DARK})], sz=19)], name=f"소제목 {label}", inset=0.05)
        return y + 1.05

    # ================= 왼쪽 단 (글 내용은 d판과 같다)
    # 1절은 줄글 대신 '꼬리표(왼쪽) + 내용(오른쪽)' 줄로 나눈다 (사용자 11-11: 1절이 가장 중요, 줄글이면 읽기 싫다).
    y = 16.56
    s.header(LX + 0.22, y, CW, "1  연구 배경 및 목적")
    y += HH + 0.35
    CX, CWW = LX + S1_TAG + S1_GAP, CW - S1_TAG - S1_GAP

    def chip(y, h, label, strong=False):
        s.text(LX, y, S1_TAG, h, [para([(label, {"bold": True, "color": "FFFFFF" if strong else DARK})], sz=15.5, algn="ctr")],
               fill=DARK if strong else TAG_FILL, geom="roundRect", anchor="ctr", name=f"1절 꼬리표 {label}")

    def row(y, h, label, runs, sz=15, strong=False):
        chip(y, h, label, strong)
        if isinstance(runs, str):
            runs = [(runs, {})]
        s.text(CX, y, CWW, h, [para(runs, sz=sz, lnspc=112)], name=f"1절 {label}", anchor="ctr",
               fill=GOAL_FILL if strong else None, geom="roundRect" if strong else "rect", inset=0.22 if strong else 0.06)
        return y + h + S1_ROW

    def cards(y, h, label, items, widths, fill):
        x = CX
        for k, (wd, t_) in enumerate(zip(widths, items)):
            s.text(x, y, wd, h, [para([(f"({k + 1})  ", {"bold": True, "color": DARK}), (t_, {})], sz=14, lnspc=108)],
                   fill=fill, geom="roundRect", anchor="ctr", name=f"1절 {label} 카드 {k + 1}", inset=0.18)
            x += wd + 0.25

    y = row(y, 1.62, "연구 배경", "숙련 인력이 줄어드는 조적 공사에서 기존 조적 로봇은 경로와 계측을 현장마다 다시 설정해야 한다[4]. "
                                  "사람의 시연으로 동작을 배우는 모방학습(ACT[1])이 그 대안으로 쓰인다.")
    ht, hc = 2.4, 1.7
    chip(y, ht + 0.1 + hc, "문제 정의")
    s.text(CX, y, CWW, ht, [para([
        ("성공 시연만 배운 정책은 실패를 알아채지 못한다. 16장을 잇달아 쌓는 벽에서는 한 장의 실패가 벽 전체를 멈춰, ", {}),
        (f"정책만으로는 벽당 {none['filled_mean']:.1f}장 · 완성 0벽", {"bold": True}),
        ("이다. 그래서 정책 밖에 검측을 붙이지만, 확인한 범위의 선행연구는 여러 단계를 한꺼번에 붙여 전체 성공률만 보고했다. "
         "이렇게는 알 수 없는 것:", {})], sz=15, lnspc=112)], name="1절 문제 정의", anchor="ctr", inset=0.06)
    cards(y + ht + 0.1, hc, "빈틈", ["한정된 센서 · 시간을 어느 단계에 둘지 정할 수 없다", "검측이 오히려 해가 되는 경우를 가려낼 수 없다",
                                    "성공률로는 현장이 받아들일 벽(시방 합격)인지 알 수 없다"], [(CWW - 0.5) / 3] * 3, GAP_FILL)
    y += ht + 0.1 + hc + S1_ROW
    y = row(y, 1.85, "연구 목적", [("같은 학습 정책에 검측 단계를 하나씩 끄고 켜서, ", {}),
                                 ("각 단계가 벽 완성과 시방 합격에 주는 몫", {"bold": True, "color": DARK}), ("과 ", {}),
                                 ("검측이 효과를 내는 조건", {"bold": True, "color": DARK}),
                                 ("을 KCS 41 34 00[3] 기준으로 밝힌다.", {})], sz=15.5, strong=True)
    y = row(y, 1.62, "연구 방법", "MuJoCo[2] 3단 16장 벽에서 ACT 정책(재학습 없음)에 검측 6단계를 붙인 Full과, 그중 하나씩 끈 6조건을 비교한다.")
    y = row(y, 1.62, "검증 계획", "모든 조건을 같은 100벽에서 돌려 벽끼리 짝지어 비교한다. 짝 차이의 95 % 구간이 0 아래면 ‘몫이 있다’, "
                                  "0을 걸치면 ‘구별 못 함’으로 판정한다(효과 없음이 아님).")
    pth, w, h = F["그림1_정책만_대_검측6단계.png"]
    chip(y, h, "결과")
    s.image(pth, CX, y, w, h, f"결과 요약: 정책만은 벽당 {none['filled_mean']:.1f}장 · 완성률 0 %, 검측 6단계를 붙인 Full은 벽당 {full['filled_mean']:.1f}장 · "
                              f"완성률 {full['complete']} % · 시방 합격 {full['spec_pass']} %. {sig_s}는 하나만 꺼도 완성률 −{min(drops):.0f} ~ −{max(drops):.0f} %p, "
                              f"{' · '.join(unsig)}는 구별되지 않음")
    y += h + S1_ROW
    hk = 2.35
    chip(y, hk, "예상 기여")
    cards(y, hk, "기여", ["긴 조적 작업에서 검측 단계별 몫을 시방 기준으로 나눠 잰 자료",
                         "검측이 효과를 내려면 측정 정확도보다 ‘지금 손에 든 벽돌’을 맞게 아는 것이 먼저라는 관찰(실패 분석에서 나온 질문)",
                         "현장 검측 자원의 우선순위"], [6.4, CWW - 0.5 - 6.4 - 5.1, 5.1], GOAL_FILL)
    y += hk + 0.4

    s.header(LX + 0.22, y, CW, "2  연구 방법")
    y += HH + 0.45
    pth, w, h = F["그림2_검측단계_흐름도.png"]
    s.image(pth, LX, y, w, h, "벽돌 한 장의 시간 순서: 정책 접근 → G0 집기 정렬 → G1 집기 확인 → 정책 운반 → G2 놓기 전 보정(+G2w) → G3 놓은 뒤 재배치, H는 G1 순간에 손에 든 벽돌을 정해 G2 · G3의 기준 자리로 씀")
    y += h + 0.25
    trows = [["검측 단계", "하는 일", "쓰는 정보"],
             [("G0 집기 정렬", {"bold": True}), "정책이 공급칸 위로 내려오면 도면 중심에서 대신 집기", "공급대 도면 · 관절값"],
             [("G1 집기 확인", {"bold": True}), "1.5 cm 들어 쥐었나 판정, 못 쥐면 다시", "손목 힘 · 집게 각도"],
             [("G2 놓기 전 보정", {"bold": True}), "손 안 벽돌을 재서 설계 자리에 놓기", "작업대 카메라"],
             [("G2w 넓게 받기", {"bold": True}), "G2가 넘겨받는 거리 15 → 40 cm", "–"],
             [("G3 놓은 뒤 재배치", {"bold": True}), "놓인 벽돌을 재서 어긋나면 다시 놓기", "작업대 카메라"],
             [("H 손에 든 벽돌 기준", {"bold": True}), "G2 · G3의 기준 = 쥔 순간 가장 가까운 공급칸의 벽돌", "도면 · 관절값"]]
    for r in trows[1:]:
        r[1] = (r[1], {"algn": "l"})
    s.table(LX, y, [6.0, 14.4, 6.2], trows, 0.84, sz=14.5, name="검측 단계 표")
    y += 0.84 * len(trows) + 0.35
    qrows = [["연구 질문", "비교 (같은 정책 · 같은 100벽)", "판정"],
             [("RQ1 각 단계의 몫은?\n(계획한 질문)", {"bold": True, "algn": "l"}), ("Full 대 Full − 그 단계 (6쌍)", {"algn": "l"}),
              ("완성률 짝 차이 95 % 구간\n< 0 이면 몫이 있음", {})],
             [("RQ2 효과를 내는 조건은?\n(실패 분석에서 나온 질문)", {"bold": True, "algn": "l"}),
              ("Full 대 참값 (진단): 카메라 대신 정답 좌표\nFull 대 Full − H: 기준 = 차례 번호", {"algn": "l"}),
              ("미리 정한 문턱 없음\n→ 짝 차이로만 보고", {})]]
    s.table(LX, y, [7.4, 11.6, 7.6], qrows, 1.45, sz=14, name="연구 질문 표")
    qrows_h = set_table_heights(s, 0.84, 1.45, len(qrows))
    y += qrows_h + 0.4

    s.header(LX + 0.22, y, CW, "3  실험")
    y += HH + 0.4
    y = sub(LX, y, "3.1  실험 환경 세팅")
    pth, w, h = F["그림3_실험환경_로봇_카메라_벽돌.png"]
    s.image(pth, LX, y, w, h, "실험 환경: 로봇 팔 UR10e와 집게, 공급대의 벽돌, 쌓는 3단 벽, 정면 · 작업대(위) · 손목 카메라 위치와 세 카메라의 시야")
    y += h + 0.05
    s.text(LX, y, CW, 0.7, [para("설명용 그림: 카메라 몸체는 위치를 보이려고 그려 넣은 표식이다 (시뮬레이터의 카메라는 형체가 없다)",
                                 sz=12, algn="ctr", color="5B6370")], name="환경 그림 설명")
    y += 0.75
    s.text(LX, y, CW, 4.6, [
        para([("환경  ", {"bold": True}), ("MuJoCo · UR10e + Robotiq 2F-140 · 벽돌 190 × 90 × 57 mm · 3단 16자리(온장 14 · 반장 2) · 줄눈 10 mm", {})],
             sz=15, bullet=True, after=3),
        para([("공급  ", {"bold": True}), ("위치가 정해진 16칸 공급대, 벽돌은 칸 중심에서 ±10 mm · ±10° 흩어짐", {})], sz=15, bullet=True, after=3),
        para([("정책  ", {"bold": True}), ("ACT, 시연 1,000벽으로 10만 스텝 학습 후 고정. 실행 중에는 정답 좌표를 쓰지 않음(카메라 3대 · 관절값 · 손목 힘)", {})],
             sz=15, bullet=True, after=3),
        para([("배치  ", {"bold": True}), ("모든 조건이 같은 개발 배치 100벽(시작값 700300 ~ 700399) · 최종 평가 전", {})], sz=15, bullet=True)],
        name="환경 글")
    y += 4.6 + 0.2
    y = sub(LX, y, "3.2  평가 방법 (KCS 41 34 00 조적공사 시공 허용오차)")
    pth, w, h = F["그림4_평가기준_채움_완성_시방.png"]
    s.image(pth, LX, y, w, h, "판정 사다리: 자리 채움(느슨, 보조) → 벽 완성(주 지표 1) → 시방 합격(보조), 주 지표 2는 완성 벽의 항목별 측정값")
    left_end = y + h

    # ================= 오른쪽 단
    y = 16.56
    y = sub(RX, y, "3.3  결과")
    pth, w, h = F["그림5_자리별_채운벽수_조건별.png"]
    s.image(pth, RX, y, w, h, "자리별 채운 벽 수: 줄은 조건 8개, 칸은 자리 1 ~ 16을 채운 벽 수(100벽 중), 끝 두 칸은 완성한 벽과 시방 합격 벽. 위쪽은 쌓는 벽 그림과 자리 번호")
    y += h + 0.3
    s.text(RX, y, CW, 0.8, [para([("표 1  단계를 끄면 완성한 벽이 몇 개 줄고, 그 차이는 믿을 만한가 (같은 100벽 비교)", {"bold": True, "color": DARK})], sz=15)],
           name="표 1 제목", inset=0.05)
    y += 0.85
    lrows = [["조건", "완성한 벽\n(100벽 중)", "Full과의 차이\n(완성한 벽 수)", "차이의 95 % 구간\n(벽 수)", "판정"]]
    for lab in TABLE:
        r = R[lab]
        o = {"bold": True} if r["kind"] == "full" else ({"color": "5B6370"} if r["kind"] == "diag" else {})
        if r["kind"] == "full":
            c1, c2, c3 = "기준", "–", "–"
        else:
            v = r["vs_full"]
            c1, c2, c3 = fmt_n(v["complete_pp"]), fmt_ci(v["complete_ci_pp"]), verdict(v["complete_ci_pp"])
            if r["kind"] == "none":
                c3 += " (검측 전체)"
            elif r["kind"] == "diag":
                c3 += " (탐색)"
        lrows.append([(lab, o), (str(r["complete"]), o), (c1, o), (c2, o), (c3, o)])
    s.table(RX, y, [5.2, 4.2, 5.4, 5.6, 6.2], lrows, 0.7, sz=14, name="결과 표")
    y += set_table_heights(s, 1.2, 0.7, len(lrows)) + 0.12
    s.text(RX, y, CW, 1.75, [
        para("차이 = 조건 − Full (같은 100벽의 완성한 벽 수). 95 % 구간 = 시험 벽을 다시 뽑아 구한 차이의 범위(부트스트랩 10000번).",
             sz=11, color="5B6370", after=2),
        para("구간이 0 아래에만 있으면 ‘몫 있음’, 0을 포함하면 ‘구별 못 함’. 참값 (진단) = 카메라 대신 정답 좌표를 준 진단"
             "(실제 로봇 불가 · 실패 분석에서 나온 탐색 질문이라 미리 정한 기준 없음).", sz=11, color="5B6370")], name="결과 표 각주")
    y += 1.85
    pth, w, h = F["그림6_시방항목_Full_FullG3.png"]
    s.image(pth, RX, y, w, h, "완성한 벽의 시방 항목 ② 선 및 면 · ③ 수직도 · ④ 평면상 위치 측정값: Full 60벽은 모두 6 mm 안, Full − G3 23벽은 여러 벽이 6 mm를 넘음")
    y += h + 0.45

    s.header(RX + 0.22, y, CW, "4  고찰")
    y += HH + 0.4
    s.text(RX, y, CW, 7.6, [
        para([("‘손에 든 벽돌’을 아는 것이 먼저다. ", {"bold": True}),
              (f"H를 끄면 {noh['filled_mean']:.2f}장으로 검측 없음({none['filled_mean']:.2f}장)보다 낮다. 정책이 한 차례에 여러 장을 집어 "
               "차례 번호와 손에 든 벽돌이 어긋나면, 검측은 틀린 자리로 맞춘다. 반대로 카메라 대신 정답 좌표를 줘도 완성률 "
               f"{fmt_pp(diag['vs_full']['complete_pp'], diag['vs_full']['complete_ci_pp'])}로 구별되지 않았다(실패 분석에서 나온 질문).", {})],
             sz=15, bullet=True, after=4),
        para([("단계는 서로 기댄다. ", {"bold": True}),
              ("한 장이라도 막히면 벽이 멈추므로 G1 · H는 하나만 꺼도 완성 0벽이다. 단계별 몫은 ‘다른 단계가 모두 있을 때’의 값이라 더해서 읽지 않는다.", {})],
             sz=15, bullet=True, after=4),
        para([("시방 합격은 G3가 만든다. ", {"bold": True}),
              (f"채움 판정이 느슨해 G3 없이도 {g3['complete']}벽이 완성됐지만 시방 합격은 {g3['spec_pass']}벽이다. "
               f"같은 벽끼리 선 · 면 {g3i['2']['diff_mean']:+.1f} mm, 수직도 {g3i['3']['diff_mean']:+.1f} mm(짝 {g3['vs_full']['items_pairs']}벽).", {})],
             sz=15, bullet=True, after=4),
        para([("현장 의미. ", {"bold": True}),
              ("검측 자원은 (1) 어느 자재를 들었는지 맞추기(공급 순서 · 공급대 등록) (2) 놓은 뒤 검측 순으로 둔다. "
               "G1 · G2 · G3는 시공 검측(자체 점검 → 보완 → 재검측)에 대응한다.", {})], sz=15, bullet=True)],
        name="고찰 글")
    y += 7.8

    s.header(RX + 0.22, y, CW, "5  결론")
    y += HH + 0.4
    s.text(RX, y, CW, 5.6, [
        para([(f"정책을 다시 학습하지 않고 검측 6단계를 붙여 3단 16장 벽의 완성률 0 → {full['complete']} %, 시방 합격 0 → {full['spec_pass']} %를 얻었다.", {})],
             sz=15, bullet=True, after=3),
        para([(f"{sig_s}는 각각 몫이 있고, {' · '.join(unsig)}는 이 배치 크기로 구별되지 않았다. 시방 합격은 G3가 맡는다.", {})],
             sz=15, bullet=True, after=3),
        para([("한계와 다음 단계: ", {"bold": True}),
              ("시뮬레이션 · 벽 한 형상 · 정책 1개이며, Full 구성과 문턱을 같은 개발 배치에서 정해 값이 낙관적일 수 있다. "
               f"같은 검측을 Diffusion 정책에 붙이면 벽당 {DIFF['fill']:.2f}장 · 완성 {DIFF['complete']}벽이라 다른 정책으로 일반화하지 않는다. "
               f"놓기 확약(G2c)을 더한 시도는 {fmt2(G2C_V['diff_mean'], G2C_V['ci95'])}장으로 구별되지 않아 Full에서 뺐다. "
               "독립 시험 배치 · 학습 seed 추가 · 실제 로봇으로 확인한다.", {})], sz=15, bullet=True)],
        name="결론 글")
    y += 5.75
    s.text(RX, y, CW, 2.1, [para([("정책을 다시 학습하지 않고, ‘지금 손에 든 벽돌’을 아는 검측 단계로", {"bold": True, "color": "FFFFFF"})],
                                 sz=17, algn="ctr", color="FFFFFF", after=2),
                            para([(f"완성률 0 → {full['complete']} % · 시방 합격 0 → {full['spec_pass']} % (100벽)", {"bold": True, "color": "FFFFFF"})],
                                 sz=20, algn="ctr", color="FFFFFF")],
           fill=DARK, geom="roundRect", anchor="ctr", name="핵심 메시지")
    y += 2.1 + 0.45

    s.header(RX + 0.22, y, CW, "6  감사의 글")
    y += HH + 0.35
    s.text(RX, y, CW, 1.7, [para(ACK, sz=13)], name="감사의 글")
    y += 1.8
    s.text(RX, y, CW, 2.1, [
        para([("참고문헌  ", {"bold": True}),
              ("[1] Zhao, T. Z. et al. (2023) Learning Fine-Grained Bimanual Manipulation with Low-Cost Hardware, RSS. "
               "[2] Todorov, E. et al. (2012) MuJoCo: A Physics Engine for Model-Based Control, IROS. "
               "[3] 국가건설기준센터, KCS 41 34 00 조적공사. "
               "[4] Giftthaler, M. et al. (2017) Mobile Robotic Fabrication at 1:1 Scale: the In situ Fabricator, Construction Robotics, 1, 3–14.", {})],
             sz=11, color="5B6370")], name="참고문헌")
    right_end = y + 2.1

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
    write_md(md, a, res, S, F, sources, warns, errs, pptx, prev, left_end, right_end)
    print("만듦:", pptx, figd, prev, md)
    return warns, errs


def write_md(md, a, res, S, F, sources, warns, errs, pptx, prev, left_end, right_end):
    rel = lambda q: Path(os.path.relpath(q, md.parent)).as_posix()
    R = {r["label"]: r for r in res["rows"]}
    L = [f"# KSARC 2026 포스터 초안 설명 ({a.tag})\n",
         f"> 파일: [`{rel(pptx)}`]({rel(pptx)}) (A1 세로 한 장, 학회 양식 `ksarc-포스터 PPT 양식.pptx`에서 만듦) · 미리보기 [`{rel(prev)}`]({rel(prev)})",
         f"> **포스터의 숫자는 모두 {NOTE}.** 참값 (진단) 줄은 시뮬레이터 정답 좌표를 쓴 진단이라 실제 로봇에서는 불가능하다.",
         "> 만든 스크립트: `sim/wall3/poster_ksarc_20261111e.py` (결과 파일만 읽음). 숫자는 d판과 같다(`sim/wall3/primary_metrics_20261111.py`).",
         "> 주 지표 전체 표 · 지표를 바꿔도 결론이 같은지: [d판 설명](KSARC2026_포스터_초안_20261111d_설명.md). 내용의 근거와 순서: [발표 필수 구성](발표구성_필수항목_20261111.md).\n",
         "## d판에서 바뀐 것 (사용자 지시 11-11)\n",
         "| 바뀐 것 | 내용 | 사용자 말 |", "|---|---|---|",
         "| 1절 연구 배경 및 목적 | 줄글 7문단을 '꼬리표 + 내용' 7줄로 나눔. 문제의 빈틈 3가지와 예상 기여 3가지는 카드, 연구 목적은 강조 상자, 결과는 그림 1(정책만 → Full의 벽 그림과 완성률, 단계 하나를 껐을 때). d판의 숫자 상자 3개는 그림 1로 합침. 글 내용은 d판과 같고 글자는 16 → 15 pt | \"연구 배경 및 목적에도 시각적 구조화 추가되면 좋을거같아. 줄글로 주르르 있으면 1번 섹션부터 읽기 싫잖아. 그리고 1번 섹션이 가장 중요해\" |",
         "| 주 결과 그림 (그림 5) | 100벽 모자이크를 빼고 '자리별 채운 벽 수'로 바꿈. 제목 한 줄, 제목과 첫 줄(Full) 사이에 쌓는 벽 그림(자리 번호 1 ~ 16), 열 번호 1 ~ 16, 단 이름은 1단 · 2단 · 3단만. 그림 안에 시작값을 적지 않음 | \"후보1을 main 그림으로 하고 모자이크 그림 없애자 … 훨씬 깔끔하게 제목을 정하고 … 쌓인 벽체가 어떻게 생긴지 보여줘 … 1~16번으로 넘버링\" |",
         "| 실험 환경 그림 (그림 3) | 로봇 팔 · 카메라 3대 · 벽돌이 한 장면에 보이는 그림 + 세 카메라의 시야. 완성 벽 사진 2장은 뺌 | \"실험환경세팅에서 로봇팔과 카메라와 벽돌이 전부 다 보이는 그림이 필요해\" |",
         "| 결과 표 (표 1) | 열을 조건 · 완성한 벽 · Full과의 차이 · 차이의 95 % 구간 · 판정으로 줄임. 표 위에 표가 답하는 질문을 제목으로 적음. 벽당 채운 자리와 그 차이 열은 뺌 | \"결과표가 아직도 왜 필요한지 잘 모르겟어. 완성률 차이 %와 채운 자리 차이가 뭔맒인지 모르겠음\" |",
         "| 시방 항목 그림 (그림 6) | 결론을 제목으로. 항목마다 무엇을 재는지 작은 그림과 한 줄 설명. 허용오차 밖을 회색 영역으로. 오른쪽에 '몇 벽 중 몇 벽이 6 mm를 넘었나' | \"선 및 면 수직도 평면상 위치 그림은 뭔 말인지 모르겠음\" |",
         "| 평가 기준 그림 (그림 4) | 모자이크 색 설명 세 줄을 빼고 높이를 4.6 → 4.0 cm로 | 모자이크를 뺐으므로 |",
         "| 참고문헌 | d판 그대로 4편, 작은 글씨(11 pt) | \"참고문헌도 지금정도로만 달자 조그맣게\" |\n",
         "## 그림 5 값 (자리 1 ~ 16을 채운 벽 수, 100벽 중)\n",
         "| 조건 | 1단 (1 ~ 5) | 2단 (6 ~ 11) | 3단 (12 ~ 16) | 완성 | 시방 합격 |", "|---|---|---|---|---|---|"]
    for lab in ORDER:
        f = [str(int(v)) for v in S[lab]["fill"]]
        L.append(f"| {lab} ({SUB[lab]}) | {' '.join(f[:5])} | {' '.join(f[5:11])} | {' '.join(f[11:])} | {S[lab]['complete']} | {S[lab]['spec']} |")
    L += ["",
          "- 자리 번호 = 쌓는 순서. 1단 왼쪽부터 1 ~ 5, 2단 6(반장) · 7 ~ 10 · 11(반장), 3단 12 ~ 16. 이전 그림(후보 1)의 0 ~ 15에 1을 더한 것이다.",
          "- 칸의 숫자 = 그 자리를 채운 벽 수. 채움 = 설계 자리 중심에서 수평 45 mm · 높이 28.5 mm · 기울기 45° 안(평가지표 md 2.4절, 느슨한 존재 확인).",
          "- 시방 합격은 벽 전체 판정이라 자리별 칸이 없고 끝 칸에만 있다.\n",
          "## 표 1 읽는 법\n",
          "| 열 | 뜻 | 예 (Full − G3) |", "|---|---|---|",
          f"| 완성한 벽 | 100벽 가운데 16자리를 모두 채운 벽 수 | {R['Full − G3']['complete']} |",
          f"| Full과의 차이 | 그 조건의 완성한 벽 수 − Full의 완성한 벽 수. 같은 100벽이라 1벽 = 1 %p | {R['Full − G3']['complete']} − {R['Full']['complete']} = {fmt_n(R['Full − G3']['vs_full']['complete_pp'])} |",
          f"| 차이의 95 % 구간 | 시험 벽 100개를 다시 뽑아(복원 추출 10000번, 난수 시드 0) 차이를 다시 구했을 때 가운데 95 %가 놓인 범위. 벽을 다르게 골랐다면 차이가 어디까지 달라질 수 있는지 | {fmt_ci(R['Full − G3']['vs_full']['complete_ci_pp'])} |",
          f"| 판정 | 구간이 0 아래에만 있으면 '몫 있음'(그 단계가 완성에 기여), 0을 포함하면 '구별 못 함'(효과 없음이 아니라 이 100벽으로는 가릴 수 없음) | {verdict(R['Full − G3']['vs_full']['complete_ci_pp'])} |\n",
          "| 조건 | 완성한 벽 | Full과의 차이 | 차이의 95 % 구간 | 판정 |", "|---|---|---|---|---|"]
    for lab in TABLE:
        r = R[lab]
        if r["kind"] == "full":
            L.append(f"| {lab} | {r['complete']} | 기준 | – | – |")
        else:
            v = r["vs_full"]
            L.append(f"| {lab} | {r['complete']} | {fmt_n(v['complete_pp'])} | {fmt_ci(v['complete_ci_pp'])} | {verdict(v['complete_ci_pp'])} |")
    L += ["",
          "- **표가 하는 일**: 그림 5는 '몇 벽이 완성됐나'를 보여 주지만, 그 차이가 벽을 어떻게 골랐느냐에 따라 뒤집힐 수 있는지는 말해 주지 않는다. 표 1은 2절 연구 질문 표의 판정 기준(짝 차이 95 % 구간)을 조건마다 적용한 결과다. G2w가 '구별 못 함'이라는 결론과 참값 (진단) 줄은 이 표에만 있다.",
          "- 뺀 열: 벽당 채운 자리(보조 지표)와 그 차이. 자리별 채움은 그림 5가 보여 준다. 값은 d판 설명 md에 있다.",
          "- 검측 없음 줄의 '몫 있음'은 검측 여섯 단계 전체의 몫이다. 참값 (진단) 줄은 실패 분석에서 나온 탐색 질문이라 미리 정한 판정 기준이 없고, 구간이 0을 포함한다는 사실만 적었다.\n",
          "## 그림 6 읽는 법\n",
          "| 항목 | 재는 것 (평가지표 md 2.3절) | 그림 속 설명 | 허용오차 |", "|---|---|---|---|",
          "| ② 선 및 면 | 단마다 윗면 모서리 높이의 들쭉날쭉 (max − min) / 2, 그리고 벽 앞면 모서리를 평면에 맞춘 뒤 남는 들쭉날쭉 (max − min) / 2 | 벽 앞면이 평평한가, 단 윗면이 수평인가 | 6 mm |",
          "| ③ 수직도 | 각 단 앞면이 1단 바닥 높이의 앞면(수직선)에서 벗어난 거리, 벽 양 끝면도 같은 방식 | 위 단이 1단 앞면의 수직선에서 벗어난 거리 | 6 mm |",
          "| ④ 평면상 위치 | 1단 앞면 아래 모서리가 바닥 기준선에서 벗어난 거리, 1단 양 끝면이 설계 위치에서 벗어난 거리 | 1단이 바닥 기준선에서 벗어난 거리 | 6 mm |\n",
          "| 조건 | 완성한 벽 | ② 6 mm 넘은 벽 · 중앙값 · 최대 | ③ | ④ |", "|---|---|---|---|---|"]
    for lab in ("Full", "Full − G3"):
        it = R[lab]["items"]
        f3 = lambda k: f"{it[k]['over_limit']}벽 · {it[k]['median']:.2f} · {it[k]['max']:.2f} mm"
        L.append(f"| {lab} | {it['2']['n']} | {f3('2')} | {f3('3')} | {f3('4')} |")
    L += ["",
          "- 점 하나 = 완성한 벽 하나의 측정값. 미완성 벽은 시방 판정 대상이 아니라 점이 없다. 굵은 세로줄 = 중앙값. 회색 영역 = 허용오차 6 mm 밖.",
          "- 읽는 순서: 파란 점(Full)은 세 항목 모두 점선 왼쪽에 있다 → Full이 완성한 벽은 모두 허용오차 안. 주황 점(Full − G3)은 점선 오른쪽으로 넘어간다 → G3 없이 완성한 벽은 대부분 허용오차 밖.",
          "- 가로축 16 mm를 넘는 값 하나(Full − G3의 ②)는 끝에 세모와 값으로 적었다.",
          "- ① 가로줄눈 · ⑤ 벽 두께는 그리지 않았다(①은 모르타르 모델이 줄눈을 고정해 거의 0, ⑤는 허용 +13 mm로 기준이 다름). 값은 d판 설명 md에 있다.",
          "- 그림 속 작은 그림은 항목의 뜻을 보이는 설명용이며 어긋남을 과장해 그렸다. 한 줄 설명은 정의를 줄인 말이다(③ 끝면, ④ 끝면은 생략).\n",
          "## 그림 3 (실험 환경) 주의\n",
          "- `sim/wall3/fig_env_scene_20261111.py`가 만든 PNG를 그대로 복사했다. 자세한 설명: [그림_실험환경_20261111/설명.md](그림_실험환경_20261111/설명.md).",
          "- 카메라 몸체 · 시선 · 이름표는 그림에만 있다(시뮬레이터의 카메라는 형체가 없는 점). 포스터 그림 아래에 '설명용 그림'이라고 적었다.",
          "- 장면은 시연기(정답 좌표를 쓰는 규칙 동작)로 9번째 벽돌을 놓는 순간이다. Full의 실행 장면이 아니며 결과가 아니다.",
          "- 오른쪽 세 장은 같은 카메라를 512 × 512로 다시 그린 것이다. 정책 입력은 128 × 128이다.\n",
          "## 그림 파일\n", "| 파일 | 내용 | 크기 (포스터 위, cm) |", "|---|---|---|"]
    desc = {"그림1": "1절 결과 줄: 정책만 → Full의 벽 그림(색 = 자리별 채운 벽 수)과 완성률, 단계 하나를 껐을 때의 완성률 변화",
            "그림2": "검측 단계 흐름도 (c · d판과 같은 그림 함수)", "그림3": "실험 환경: 로봇 팔 · 카메라 3대 · 벽돌 + 세 카메라의 시야",
            "그림4": "평가 기준 사다리: 자리 채움(느슨) → 벽 완성(주 1) → 시방 합격(보조)",
            "그림5": "주 결과: 자리별 채운 벽 수(조건 8줄 × 자리 16칸) + 완성 · 시방 합격, 위에 쌓는 벽 그림",
            "그림6": "완성한 벽의 ② · ③ · ④ 측정값, Full 대 Full − G3, 허용오차 6 mm"}
    for nme, (q, w, h) in F.items():
        L.append(f"| [`{rel(q)}`]({rel(q)}) | {desc[nme.split('_')[0]]} | {w:.1f} × {h:.1f} |")
    L += ["\n## 데이터 출처 (sha256 앞 16)\n"] + [f"- `{k}` {v}" for k, v in sorted(sources.items())]
    L += ["\n## 확인할 것 · 남은 것\n",
          "- **시험 배치(730000번대)는 쓰지 않았다.** 모든 수치는 개발 배치다. 포스터 결론에 'Full 구성과 문턱을 같은 개발 배치에서 정해 값이 낙관적일 수 있다'를 적었다.",
          "- **표 1을 둘지 뺄지**는 사용자가 아직 정하지 않았다(11-11 \"왜 필요한지 잘 모르겟어\"). 빼면 G2w '구별 못 함' 판정과 참값 (진단) 줄의 근거가 포스터에서 사라지므로 4절 고찰의 글만 남는다.",
          "- **양식 다듬기**는 윈도우에서 한다(사용자가 줄 레퍼런스 ppt 형식에 맞춤). [윈도우 인계](윈도우_인계_20261111.md) 참고.",
          "- 동그라미 숫자: 나눔고딕에 ①②③ 글자가 없어 pptx 글자에서는 (1)(2)(3)으로 썼다. 그림(PNG) 안은 ①~⑤를 그대로 쓴다. 빼기 기호(−)는 pptx 글자에서 짧은 줄표(–)로 바뀐다.",
          "- 감사의 글: 사용자가 준 문장을 한 글자도 바꾸지 않고 넣었다. 참고문헌 4편의 서지는 원문으로 한 번 더 확인해야 한다.",
          "- PowerPoint로 열어 보지 못했다(이 컴퓨터에 없음). 미리보기 PNG는 스크립트가 대략 그린 것이다. 글꼴(나눔고딕)이 없는 PC에서는 줄바꿈이 달라질 수 있다.",
          f"- 점검: 왼쪽 단 끝 {left_end:.2f} cm · 오른쪽 단 끝 {right_end:.2f} cm (흰 단 끝 83.42 cm). 글자 넘침 · 겹침 경고 {len(warns)}건, 패키지 오류 {len(errs)}건."
          + ("" if not (warns or errs) else " " + " / ".join(warns + errs)),
          "- 다시 만들기 (출력이 있으면 덮어쓰지 않으므로 `--tag`를 새로 준다):",
          "  ```", f"  cd sim && MPLCONFIGDIR=/tmp/mpl PYTHONPATH=. venv/bin/python -m wall3.poster_ksarc_20261111e --tag {a.tag}2", "  ```"]
    md.write_text("\n".join(L) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="20261111e")
    ap.add_argument("--out-dir", default=None, help="기본 02_KSARC2026 (시험 삼아 만들 때는 임시 폴더)")
    ap.add_argument("--figures-only", action="store_true")
    a = ap.parse_args()
    build(a)


if __name__ == "__main__":
    main()
