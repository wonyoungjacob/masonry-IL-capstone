"""KSARC 2026 포스터 d판 (2026-11-11 저녁). 결과 파일만 읽는다. 시뮬레이션 없음.

c판(poster_ksarc_20261111.py)의 양식 처리 · 표 · 미리보기 · 점검 함수를 그대로 쓰고, 다음을 바꾼다.
- 절 구성을 논문 순서로: 1 연구 배경 및 목적(배경 · 문제 정의 · 목적 · 방법 · 검증 계획 · 결과 · 예상 기여) → 2 연구 방법
  → 3 실험(환경 세팅 · 평가 방법 · 결과) → 4 고찰 → 5 결론 → 6 감사의 글 → 참고문헌. 새 방법론을 제안하는 연구가 아니라
  '연구 방법'이라 부른다(교수님 기준).
- 주 지표를 평가지표 md 2.5절대로: 완성률(주 1) · 완성 벽의 시방 항목 오차(주 2) · 시방 합격(보조) · 벽당 채운 자리(보조).
  값은 wall3.primary_metrics_20261111.compute()로 rollout.json에서 계산한다(짝 차이 구간: 벽 단위 부트스트랩 10000번, 시드 0).
- 결과 그림: 100벽 모자이크(벽 하나 = 3단 16자리 작은 벽 그림) · 완성 벽의 ②③④ 오차 점그림(허용 6 mm 선).
- 숫자는 모두 개발 배치 100벽(시작값 700300 ~ 700399) · 최종 평가 전. 참값 줄은 '참값 (진단)'.
- 출력이 이미 있으면 덮어쓰지 않는다.

실행: cd sim && MPLCONFIGDIR=<임시>/mpl PYTHONPATH=. venv/bin/python -m wall3.poster_ksarc_20261111d [--tag 20261111d] [--out-dir <임시>]
"""
import argparse, io, json
from pathlib import Path

import numpy as np

from wall3 import primary_metrics_20261111 as pm
from wall3.poster_ksarc_20261111 import (AFFIL, AUTHORS_EN, AUTHORS_KO, BLUE, BLUE_L, EVID, EVID_OLD, GREY, GRID, INK, INK2,
                                         KS, NOTE, ORANGE, REPO, SIM, Slide, check_glyphs, check_package, crop_to, fig_flow,
                                         fig_size, mpl_setup, para, preview, quiet, sha16)

TITLE_KO = "모방학습 조적 로봇의 검측 단계별 효과"
TITLE_KO_SUB = "– 3단 벽체의 완성률과 시방 합격 –"
TITLE_EN = "Stage-wise Effects of Inspection on an Imitation-Learned Masonry Robot: A Three-Course Wall Study"
ACK = ("이 논문은 2026년도 정부(과학기술정보통신부)의 재원으로 한국연구재단의 지원을 받아 수행된 연구임"
       "(IRIS 연구개발과제번호: RS-2024-00457308, 연구개발과제명: 자율 진화형 인공지능 기반 제방 붕괴 조기 감지·선제 대응 스마트 센싱 플랫폼).")
# 모자이크 · 표 순서: 완성률 차이가 작은 것부터
ORDER = ["Full", "Full − G2w", "Full − G3", "Full − G2", "Full − G0", "Full − G1", "Full − H", "검측 없음"]
TABLE = ORDER + ["참값 (진단)"]
DARK = "1B4F8F"
FILLED = "#98a3b1"                                    # 미완성 벽의 채운 자리 (중립 회색, 빈 자리와 뚜렷이 다르게)
EMPTY_EDGE = "#cdd3da"


def wall_rects():
    """16 design slots (slot order) as (x0, z0, w, h) in mm, x = wall length, z = up. config.design_slots와 같은 배치."""
    out = []
    for c in range(3):
        z0 = c * 67.0
        if c == 1:
            xs = [(-450.0, 90.0)] + [((-1.5 + i) * 200.0, 190.0) for i in range(4)] + [(450.0, 90.0)]
        else:
            xs = [((-2 + i) * 200.0, 190.0) for i in range(5)]
        for xc, L in xs:
            out.append((xc - L / 2, z0, L, 57.0))
    return out


def category(w):
    return 0 if w["spec"] else (1 if w["complete"] else 2)


def draw_walls(ax, walls, ncol=5, gx=110.0, gz=62.0):
    from matplotlib.collections import PatchCollection
    from matplotlib.patches import Rectangle
    rects = wall_rects()
    walls = sorted(walls, key=lambda w: (category(w), -sum(w["filled"]), w["seed"]))
    pf, pe = [], []
    cf = []
    for i, w in enumerate(walls):
        col, row = i % ncol, i // ncol
        ox, oz = col * (990.0 + gx), -row * (191.0 + gz)
        k = category(w)
        fc = (BLUE, ORANGE, FILLED)[k]
        for (x0, z0, L, H), f in zip(rects, w["filled"]):
            r = Rectangle((ox + x0, oz + z0), L, H)
            if f:
                pf.append(r)
                cf.append(fc)
            else:
                pe.append(r)
    ax.add_collection(PatchCollection(pe, facecolor="white", edgecolor=EMPTY_EDGE, linewidth=0.35))
    ax.add_collection(PatchCollection(pf, facecolor=cf, edgecolor="white", linewidth=0.25))
    nrow = int(np.ceil(len(walls) / ncol))
    ax.set_xlim(-495 - 40, (ncol - 1) * (990 + gx) + 495 + 40)
    ax.set_ylim(-(nrow - 1) * (191 + gz) - 40, 191 + 40)
    ax.set_aspect("equal")
    ax.axis("off")


def fig_mosaic(res, path, w, h, plt):
    rows = {r["label"]: r for r in res["rows"]}
    fig = fig_size(w, h, plt)
    top = 0.885
    gs = fig.add_gridspec(2, 4, left=0.005, right=0.995, top=top - 0.035, bottom=0.005, wspace=0.06, hspace=0.2)
    for i, lab in enumerate(ORDER):
        r = rows[lab]
        ax = fig.add_subplot(gs[i // 4, i % 4])
        draw_walls(ax, r["walls_detail"])
        ax.set_title(f"{lab}", loc="left", fontsize=14, color=INK, fontweight="bold" if lab == "Full" else None, pad=17)
        ax.text(0.0, 1.012, f"완성 {r['complete']} · 시방 합격 {r['spec_pass']} · 평균 {r['filled_mean']:.1f}자리",
                transform=ax.transAxes, ha="left", va="bottom", fontsize=10.5, color=INK2)
    from matplotlib.patches import Rectangle
    items = [(BLUE, None, "완성 · 시방 합격"), (ORANGE, None, "완성 · 시방 불합격"), (FILLED, None, "채운 자리 (미완성 벽)"),
             ("white", EMPTY_EDGE, "빈 자리")]
    x = 0.005
    for fc, ec, lab in items:
        fig.patches.append(Rectangle((x, 0.952), 0.022, 0.026, transform=fig.transFigure, facecolor=fc,
                                     edgecolor=ec or fc, linewidth=0.8))
        t = fig.text(x + 0.028, 0.965, lab, ha="left", va="center", fontsize=12.5, color=INK)
        fig.canvas.draw()
        bb = t.get_window_extent().transformed(fig.transFigure.inverted())
        x = bb.x1 + 0.03
    fig.text(0.995, 0.965, "작은 벽 하나 = 시험 벽 하나 (3단 16자리) × 100", ha="right", va="center", fontsize=11.5, color=INK2)
    fig.savefig(path, dpi=300, facecolor="white")
    plt.close(fig)


def fig_items(res, path, w, h, plt):
    rows = {r["label"]: r for r in res["rows"]}
    conds = [("Full", BLUE), ("Full − G3", ORANGE)]
    items = [("2", "② 선 및 면"), ("3", "③ 수직도"), ("4", "④ 평면상 위치")]
    xmax = 16.0
    fig = fig_size(w, h, plt)
    ax = fig.add_axes([0.275, 0.15, 0.555, 0.8])
    rng = np.random.default_rng(1)
    yt, yl = [], []
    for k, (key, name) in enumerate(items):
        for j, (lab, col) in enumerate(conds):
            y = -(k * 2.7 + j * 1.0)
            v = np.array([wd["items"][key] for wd in rows[lab]["walls_detail"] if wd["complete"]], float)
            vv = np.minimum(v, xmax)
            ax.scatter(vv, y + rng.uniform(-0.28, 0.28, len(v)), s=16, color=col, alpha=0.8, linewidths=0, zorder=3)
            over = int((v > xmax).sum())
            if over:
                ax.text(xmax + 0.15, y, f"▶{over}", va="center", ha="left", fontsize=10, color=INK2)
            med = float(np.median(v))
            ax.plot([med, med], [y - 0.38, y + 0.38], color=INK, lw=1.6, zorder=4)
            n_over = int((v > 6.0).sum())
            ax.text(xmax + 1.3, y, f"{n_over} / {len(v)}", va="center", ha="left", fontsize=12, color=INK,
                    fontweight="bold" if n_over else None)
            yt.append(y)
            yl.append(f"{lab} ({len(v)})")
    ax.axvline(6.0, color=INK, lw=1.2, ls=(0, (4, 3)), zorder=2)
    ax.text(6.1, 0.75, "허용 6 mm", ha="left", va="bottom", fontsize=11.5, color=INK)
    ax.text(xmax + 1.3, 0.75, "6 mm 넘음", ha="left", va="bottom", fontsize=11.5, color=INK2)
    ax.set_xlim(0, xmax)
    ax.set_ylim(-(2 * 2.7 + 1.0) - 0.6, 1.4)
    ax.set_yticks(yt, yl, fontsize=11)
    ax.set_xticks([0, 2, 4, 6, 8, 10, 12, 14, 16])
    ax.set_xlabel("완성된 벽의 측정값 (mm) · 괄호 = 완성 벽 수 · 세로줄 = 중앙값", fontsize=11.5)
    quiet(ax, "x")
    ax.yaxis.set_tick_params(pad=4)
    for t in ax.get_yticklabels():
        t.set_color(INK2)
    # row names sit left of the tick labels
    for k, (key, name) in enumerate(items):
        fig.text(0.005, ax.transData.transform((0, -(k * 2.7 + 0.5)))[1] / fig.bbox.height, name, ha="left", va="center",
                 fontsize=12.5, color=INK, fontweight="bold")
    fig.savefig(path, dpi=300, facecolor="white")
    plt.close(fig)


def fig_eval(path, w, h, plt):
    """채움(느슨) → 완성(주 지표 1) → 시방 합격(보조) 판정 사다리. 모자이크와 같은 색."""
    from matplotlib.patches import FancyArrowPatch, Rectangle
    fig = fig_size(w, h, plt)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, w)
    ax.set_ylim(0, h)
    ax.axis("off")
    rects = wall_rects()
    steps = [
        ("자리 채움", "설계 자리 중심에서 수평 45 mm, 높이 28.5 mm,\n기울기 45° 안이면 채움 (느슨한 존재 확인)\n그림 3 색: 회색 = 미완성 벽의 채운 자리", [1] * 9 + [0] * 7, FILLED, "벽당 채운 자리 (보조)"),
        ("벽 완성", "16자리를 모두 채움\n\n그림 3 색: 주황 = 완성했으나 시방 불합격", [1] * 16, ORANGE, "완성률 (주 지표 1)"),
        ("시방 합격", "완성 + KCS 41 34 00 ①~⑤ 모두\n(②③④ 6 mm, ① 줄눈 10 ± 3 mm)\n그림 3 색: 파랑 = 완성 · 시방 합격", [1] * 16, BLUE, "시방 합격률 (보조)"),
    ]
    n = len(steps)
    gap = 0.9
    bw = (w - gap * (n - 1)) / n
    s = 2.1 / 990.0                                          # icon scale: 2.1 cm wide
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


def fmt_pp(v, ci):
    return f"{v:+.0f} [{ci[0]:+.0f}, {ci[1]:+.0f}]".replace("-", "−")


def fmt2(v, ci):
    return f"{v:+.2f} [{ci[0]:+.2f}, {ci[1]:+.2f}]".replace("-", "−")


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
    res = pm.compute()
    R = {r["label"]: r for r in res["rows"]}
    sources = dict(res["sources"])
    global DIFF, G2C_V
    dsum = pm.W / "eval_lf_full_diffusion_20261110" / "summary.json"
    dv = json.loads(dsum.read_bytes())["diffusion_all_held+k2+k7"]
    DIFF = {"fill": dv["slots_filled_mean"], "complete": dv["walls_complete"], "spec": dv["spec_pass"]}
    gc = pm.W / "eval_lg_g2c_20261111_compare.json"
    G2C_V = json.loads(gc.read_bytes())["conditions"]["eval_lg_full2_20261111/act_all_held+k2+k7+k8"]["vs_base"]
    for q in (dsum, gc):
        sources[pm.relkey(q)] = sha16(q)
    plt = mpl_setup()
    figd.mkdir(parents=True)

    LX, RX, CW, HH = 1.78, 30.99, 26.6, 2.19
    F = {}

    def fig(name, w, h):
        F[name] = (figd / name, w, h)
        return figd / name, w, h

    p, w, h = fig("그림1_검측단계_흐름도.png", CW, 8.6)
    fig_flow(p, w, h, plt)
    p, w, h = fig("그림2_평가기준_채움_완성_시방.png", CW, 4.6)
    fig_eval(p, w, h, plt)
    p, w, h = fig("그림3_100벽_모자이크_조건별.png", CW, 17.0)
    fig_mosaic(res, p, w, h, plt)
    p, w, h = fig("그림4_시방항목오차_Full_FullG3.png", CW, 7.6)
    fig_items(res, p, w, h, plt)
    p, w, h = fig("사진1_Full완성벽_700300_정면.png", 13.0, 7.4)
    crop_to(EVID / "확인영상" / "Full_완성벽_700300_마지막_정면.png", p, w, h, focus_y=0.5)
    p, w, h = fig("사진2_Full완성벽_700300_비스듬히.png", 13.0, 7.4)
    crop_to(EVID / "확인영상" / "Full_완성벽_700300_마지막_비스듬히.png", p, w, h, focus_y=0.5)
    for src in (EVID / "확인영상" / "Full_완성벽_700300_마지막_정면.png", EVID / "확인영상" / "Full_완성벽_700300_마지막_비스듬히.png"):
        sources[str(src.relative_to(REPO))] = sha16(src)
    if a.figures_only:
        print("그림만 만듦:", figd)
        return

    full, none, g3, noh, diag = R["Full"], R["검측 없음"], R["Full − G3"], R["Full − H"], R["참값 (진단)"]
    loo = [R[k] for k in ORDER[1:7]]
    drops = [-r["vs_full"]["complete_pp"] for r in loo if r["vs_full"]["complete_ci_pp"][1] < 0]
    sig = [r["label"].replace("Full − ", "") for r in loo if r["vs_full"]["complete_ci_pp"][1] < 0]
    unsig = [r["label"].replace("Full − ", "") for r in loo if r["vs_full"]["complete_ci_pp"][1] >= 0]
    sig_s = " · ".join(sorted(sig, key=lambda s: ["G0", "G1", "G2", "G3", "H"].index(s) if s in ["G0", "G1", "G2", "G3", "H"] else 9))
    g3i = g3["vs_full"]["items"]
    s = Slide()
    s.set_runs("직사각형 8", [(TITLE_KO, 46), (TITLE_KO_SUB, 30), (TITLE_EN, 22)])
    s.set_runs("Text Box 274", [(AUTHORS_KO, 32), (AUTHORS_EN, 26)])
    s.set_runs("Text Box 275", [(t, 18) for t in AFFIL])
    s.remove([f"직사각형 {k}" for k in range(17, 29)])

    def kv(label, runs, sz=16, after=5):
        if isinstance(runs, str):
            runs = [(runs, {})]
        return para([(label + "  ", {"bold": True, "color": DARK})] + runs, sz=sz, after=after, lnspc=112)

    def sub(x, y, label):
        s.text(x, y, CW, 1.0, [para([(label, {"bold": True, "color": DARK})], sz=19)], name=f"소제목 {label}", inset=0.05)
        return y + 1.05

    # ================= left column
    y = 16.56
    s.header(LX + 0.22, y, CW, "1  연구 배경 및 목적")
    y += HH + 0.5
    s.text(LX, y, CW, 14.2, [
        kv("연구 배경", "숙련 인력이 줄어드는 조적 공사에서 기존 조적 로봇은 경로와 계측을 현장마다 다시 설정해야 한다[4]. "
                      "사람의 시연으로 동작을 배우는 모방학습(ACT[1])이 그 대안으로 쓰인다."),
        kv("문제 정의", [("성공 시연만 배운 정책은 실패를 알아채지 못한다. 16장을 잇달아 쌓는 벽에서는 한 장의 실패가 벽 전체를 멈춰, ", {}),
                       (f"정책만으로는 벽당 {none['filled_mean']:.1f}장 · 완성 0벽", {"bold": True}),
                       ("이다. 그래서 정책 밖에 검측을 붙이지만, 확인한 범위의 선행연구는 여러 단계를 한꺼번에 붙여 전체 성공률만 보고했다. "
                        "이렇게는 (1) 한정된 센서 · 시간을 어느 단계에 둘지 정할 수 없고 (2) 검측이 오히려 해가 되는 경우를 가려낼 수 없으며 "
                        "(3) 성공률로는 현장이 받아들일 벽(시방 합격)인지 알 수 없다.", {})]),
        kv("연구 목적", "같은 학습 정책에 검측 단계를 하나씩 끄고 켜서, 각 단계가 벽 완성과 시방 합격에 주는 몫과 "
                      "검측이 효과를 내는 조건을 KCS 41 34 00[3] 기준으로 밝힌다."),
        kv("연구 방법", "MuJoCo[2] 3단 16장 벽에서 ACT 정책(재학습 없음)에 검측 6단계를 붙인 Full과, 그중 하나씩 끈 6조건을 비교한다."),
        kv("검증 계획", "모든 조건을 같은 100벽에서 돌려 벽끼리 짝지어 비교한다. 짝 차이의 95 % 구간이 0 아래면 ‘몫이 있다’, "
                      "0을 걸치면 ‘구별 못 함’으로 판정한다(효과 없음이 아님)."),
        kv("결과", [(f"Full은 완성률 {full['complete']} % · 시방 합격 {full['spec_pass']} %(정책만 0 %). ", {"bold": True}),
                  (f"{sig_s}는 하나만 꺼도 완성률이 {min(drops):.0f} ~ {max(drops):.0f} %p 떨어지고, "
                   f"{' · '.join(unsig)}는 구별되지 않았다.", {})]),
        kv("예상 기여", "(1) 긴 조적 작업에서 검측 단계별 몫을 시방 기준으로 나눠 잰 자료 (2) 검측이 효과를 내려면 측정 정확도보다 "
                      "‘지금 손에 든 벽돌’을 맞게 아는 것이 먼저라는 관찰(실패 분석에서 나온 질문) (3) 현장 검측 자원의 우선순위", after=0),
    ], name="1절 글")
    y += 14.3
    stats = [(f"{none['filled_mean']:.1f} → {full['filled_mean']:.1f}", "벽당 채운 자리 (16자리 중)"),
             (f"0 → {full['complete']} %", f"완성률 (시방 합격 {full['spec_pass']} %)"),
             (f"−{min(drops):.0f} ~ −{max(drops):.0f} %p", "하나만 꺼도 준 완성률 (G2w 제외)")]
    sw = (CW - 2 * 0.4) / 3
    for k, (big, lab) in enumerate(stats):
        s.text(LX + k * (sw + 0.4), y, sw, 3.0, [para([(big, {"bold": True, "sz": 34, "color": DARK})], sz=34, algn="ctr", lnspc=100),
                                                para(lab, sz=15, algn="ctr", color="5B6370")],
               fill="EEF3FA", geom="roundRect", anchor="ctr", name=f"수치 {k + 1}")
    y += 3.0 + 0.55

    s.header(LX + 0.22, y, CW, "2  연구 방법")
    y += HH + 0.45
    pth, w, h = F["그림1_검측단계_흐름도.png"]
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
    y += 0.84 * len(trows) + 0.45
    qrows = [["연구 질문", "비교 (같은 정책 · 같은 100벽)", "판정"],
             [("RQ1 각 단계의 몫은?\n(계획한 질문)", {"bold": True, "algn": "l"}), ("Full 대 Full − 그 단계 (6쌍)", {"algn": "l"}),
              ("완성률 짝 차이 95 % 구간\n< 0 이면 몫이 있음", {})],
             [("RQ2 효과를 내는 조건은?\n(실패 분석에서 나온 질문)", {"bold": True, "algn": "l"}),
              ("Full 대 참값 (진단): 카메라 대신 정답 좌표\nFull 대 Full − H: 기준 = 차례 번호", {"algn": "l"}),
              ("미리 정한 문턱 없음\n→ 짝 차이로만 보고", {})]]
    s.table(LX, y, [7.4, 11.6, 7.6], qrows, 1.45, sz=14, name="연구 질문 표")
    qrows_h = 0.84 + 1.45 * 2
    s.tree[-1].find(".//{http://schemas.openxmlformats.org/drawingml/2006/main}tr").set("h", str(int(0.84 * 360000)))
    y += qrows_h + 0.55

    s.header(LX + 0.22, y, CW, "3  실험")
    y += HH + 0.4
    y = sub(LX, y, "3.1  실험 환경 세팅")
    pa, w, h = F["사진1_Full완성벽_700300_정면.png"]
    s.image(pa, LX, y, w, h, "Full로 쌓은 벽 700300, 마지막 장면 정면(로봇 반대쪽에서)")
    pb, w2, _ = F["사진2_Full완성벽_700300_비스듬히.png"]
    s.image(pb, LX + w + (CW - w - w2), y, w2, h, "Full로 쌓은 벽 700300, 마지막 장면 비스듬히")
    y += h + 0.05
    s.text(LX, y, CW, 0.75, [para("Full로 쌓은 벽 (벽 700300, 16 / 16 · 시방 합격): 정면 · 비스듬히", sz=13, algn="ctr", color="5B6370")],
           name="사진 설명")
    y += 0.85
    s.text(LX, y, CW, 4.6, [
        para([("환경  ", {"bold": True}), ("MuJoCo · UR10e + Robotiq 2F-140 · 벽돌 190 × 90 × 57 mm · 3단 16자리(온장 14 · 반장 2) · 줄눈 10 mm", {})],
             sz=15, bullet=True, after=3),
        para([("공급  ", {"bold": True}), ("위치가 정해진 16칸 공급대, 벽돌은 칸 중심에서 ±10 mm · ±10° 흩어짐", {})], sz=15, bullet=True, after=3),
        para([("정책  ", {"bold": True}), ("ACT, 시연 1,000벽으로 10만 스텝 학습 후 고정. 실행 중에는 정답 좌표를 쓰지 않음(카메라 · 관절값 · 손목 힘)", {})],
             sz=15, bullet=True, after=3),
        para([("배치  ", {"bold": True}), ("모든 조건이 같은 개발 배치 100벽(시작값 700300 ~ 700399) · 최종 평가 전", {})], sz=15, bullet=True)],
        name="환경 글")
    y += 4.6 + 0.3
    y = sub(LX, y, "3.2  평가 방법 (KCS 41 34 00 조적공사 시공 허용오차)")
    pth, w, h = F["그림2_평가기준_채움_완성_시방.png"]
    s.image(pth, LX, y, w, h, "판정 사다리: 자리 채움(느슨, 보조) → 벽 완성(주 지표 1) → 시방 합격(보조), 주 지표 2는 완성 벽의 항목별 측정값")
    left_end = y + h

    # ================= right column
    y = 16.56
    y = sub(RX, y, "3.3  결과")
    pth, w, h = F["그림3_100벽_모자이크_조건별.png"]
    s.image(pth, RX, y, w, h, "조건별 100벽 모자이크: 작은 벽 하나가 시험 벽 하나, 색은 완성 · 시방 합격 / 완성 · 시방 불합격 / 미완성 벽의 채운 자리 / 빈 자리")
    y += h + 0.3
    lrows = [["조건", "채운 자리\n(/16)", "완성\n(/100)", "시방 합격\n(/100)", "완성률 차이 %p\n[95 % 구간]", "채운 자리 차이\n[95 % 구간]"]]
    for lab in TABLE:
        r = R[lab]
        o = {"bold": True} if r["kind"] == "full" else ({"color": "5B6370"} if r["kind"] == "diag" else {})
        if r["kind"] == "full":
            c1, c2 = "기준", "기준"
        else:
            v = r["vs_full"]
            c1, c2 = fmt_pp(v["complete_pp"], v["complete_ci_pp"]), fmt2(v["filled"], v["filled_ci"])
        lrows.append([(lab, o), (f"{r['filled_mean']:.2f}", o), (str(r["complete"]), o), (str(r["spec_pass"]), o), (c1, o), (c2, o)])
    s.table(RX, y, [4.6, 2.9, 2.6, 3.0, 6.1, 7.4], lrows, 0.7, sz=14, name="결과 표")
    s.tree[-1].find(".//{http://schemas.openxmlformats.org/drawingml/2006/main}tr").set("h", str(int(1.2 * 360000)))
    y += 1.2 + 0.7 * (len(lrows) - 1) + 0.12
    s.text(RX, y, CW, 0.75, [para("참값 (진단) = G2 · G3 위치와 손에 든 벽돌 판별을 정답 좌표로 바꾼 진단(실제 로봇 불가) · 구간: 벽 단위 부트스트랩 10000번",
                                  sz=11.5, color="5B6370")], name="결과 표 각주")
    y += 0.85
    pth, w, h = F["그림4_시방항목오차_Full_FullG3.png"]
    s.image(pth, RX, y, w, h, "완성된 벽의 시방 항목 ② 선 및 면 · ③ 수직도 · ④ 평면상 위치 측정값: Full 60벽과 Full − G3 23벽, 허용 6 mm 선")
    y += h + 0.45

    s.header(RX + 0.22, y, CW, "4  고찰")
    y += HH + 0.4
    s.text(RX, y, CW, 8.4, [
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
    y += 8.6

    s.header(RX + 0.22, y, CW, "5  결론")
    y += HH + 0.4
    s.text(RX, y, CW, 6.0, [
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
    y += 6.15
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
    write_md(md, a, res, F, sources, warns, errs, pptx, prev, left_end, right_end)
    print("만듦:", pptx, figd, prev, md)
    return warns, errs


def write_md(md, a, res, F, sources, warns, errs, pptx, prev, left_end, right_end):
    rel = lambda q: Path(q).relative_to(md.parent).as_posix()
    R = {r["label"]: r for r in res["rows"]}
    full = R["Full"]
    L = [f"# KSARC 2026 포스터 초안 설명 ({a.tag})\n",
         f"> 파일: [`{rel(pptx)}`]({rel(pptx)}) (A1 세로 한 장, 학회 양식 `ksarc-포스터 PPT 양식.pptx`에서 만듦) · 미리보기 [`{rel(prev)}`]({rel(prev)})",
         f"> **포스터의 숫자는 모두 {NOTE}.** 참값 (진단) 줄은 시뮬레이터 정답 좌표를 쓴 진단이라 실제 로봇에서는 불가능하다.",
         "> 만든 스크립트: `sim/wall3/poster_ksarc_20261111d.py` (결과 파일만 읽음). 주 지표 계산: `sim/wall3/primary_metrics_20261111.py`.",
         "> 내용의 근거와 순서: [발표 필수 구성](발표구성_필수항목_20261111.md).\n",
         "## c판에서 바뀐 것\n",
         "| 바뀐 것 | 내용 | 이유 |", "|---|---|---|",
         "| 절 구성 | 1 연구 배경 및 목적(배경 · 문제 정의 · 목적 · 방법 · 검증 계획 · 결과 · 예상 기여) → 2 연구 방법 → 3 실험(3.1 환경 세팅 · 3.2 평가 방법 · 3.3 결과) → 4 고찰 → 5 결론 → 6 감사의 글 → 참고문헌 | 사용자 지시(11-11). 새 방법론 제안이 아니라 2절 이름은 '연구 방법', 1절의 '제안방법'도 같은 이유로 '연구 방법' |",
         "| 범위 | 3단 16장 벽(11-10 역방향 제거)만 | 사용자 지시(11-11): 제출 초록의 블록 3개 실험은 쓰지 않음 |",
         "| 주 지표 | 평가지표 md 2.5절대로 완성률(주 1) · 완성 벽의 시방 항목 오차(주 2). 벽당 채운 자리 · 시방 합격은 보조로 표에 | 사용자 확인(11-11): 핵심 지표는 평가지표 md. 채운 자리는 16자리를 다 못 채우는 단계에서 늘리려고 쓴 값 |",
         f"| 제목 | {TITLE_KO} {TITLE_KO_SUB} / {TITLE_EN} | 사용자 허락(11-11). 탐색 질문(RQ2, 작동 조건)은 제목에 넣지 않았다 (계획한 질문 RQ1만 제목에) |",
         "| 결과 그림 | 100벽 모자이크(그림 3) · 시방 항목 오차 점그림(그림 4) · 평가 기준 사다리(그림 2) | '얼마나 채웠고(느슨한 판정) 그중 몇 개가 시방을 통과했나'를 한눈에 |",
         "| 뺀 것 | 단계별 사다리 그림, 처음 못 채운 자리 그림, H 전제 카드 3장 | 지면. 사다리는 개발 이력이라 연구 설계(하나씩 끄기)의 답이 아님. 처음 실패 위치는 모자이크에 보임. H 전제는 고찰 '현장 의미' 한 줄로 줄임. 모두 c판 · 스토리라인에 남아 있음 |",
         "| 더한 것 | 연구 질문 표(RQ2에 '실패 분석에서 나온 질문' 표시), 판정 기준, 음성 결과(Diffusion · G2c) 한 줄, 감사의 글 | 교수님 기준(탐색 질문 표시 · 판정 기준 · 주장 범위). 불리한 결과도 같이 보임 |\n",
         "## 주 지표 (포스터 3.3절 표 + Full 다시 잰 두 번)\n",
         "| 조건 | 채운 자리 (/16) | 완성 (/100) | 시방 합격 | 완성했으나 불합격 | 완성률 차이 %p [95 %] | 시방 합격 차이 %p [95 %] | 채운 자리 차이 [95 %] |",
         "|---|---|---|---|---|---|---|---|"]
    for r in res["rows"]:
        v = r.get("vs_full")
        if v is None:
            c1 = c2 = c3 = "기준"
        else:
            c1, c2, c3 = fmt_pp(v["complete_pp"], v["complete_ci_pp"]), fmt_pp(v["spec_pp"], v["spec_ci_pp"]), fmt2(v["filled"], v["filled_ci"])
        L.append(f"| {r['label']} | {r['filled_mean']:.2f} | {r['complete']} | {r['spec_pass']} | {r['complete_not_spec']} | {c1} | {c2} | {c3} |")
    L += ["",
          "- 짝 차이 = 조건 − Full, 같은 시작값끼리. 구간은 벽 단위 부트스트랩 10000번(난수 시드 0, `compare_ladder.py`와 같은 방식).",
          "- Full − G1은 11-11에 고친 코드로 다시 잰 값(`eval_lf_noG1fix_20261111`). Full 다시 1 · 2는 같은 Full 설정(같은 조건 이름)을 따로 다시 돌린 것으로, 실행 간 흔들림을 보여 준다(완성률 ±2 %p 안, 구간 약 ±7 %p).\n",
          "## 시방 항목 오차 (주 지표 2, 완성된 벽만, mm)\n",
          "| 조건 | 완성 벽 | ② 선 및 면 중앙값 / 95백분위 / 최대 | ③ 수직도 | ④ 평면상 위치 | ⑤ 벽 두께 (+ 쪽) | 허용 넘은 벽 (②, ③, ④) |",
          "|---|---|---|---|---|---|---|"]
    for r in res["rows"]:
        it = r["items"]
        if it["2"] is None:
            L.append(f"| {r['label']} | 0 | – | – | – | – | – |")
            continue
        f3 = lambda k: f"{it[k]['median']:.2f} / {it[k]['p95']:.2f} / {it[k]['max']:.2f}"
        L.append(f"| {r['label']} | {it['2']['n']} | {f3('2')} | {f3('3')} | {f3('4')} | {f3('5')} | "
                 f"{it['2']['over_limit']}, {it['3']['over_limit']}, {it['4']['over_limit']} |")
    g3, dg = R["Full − G3"]["vs_full"], R["참값 (진단)"]["vs_full"]
    L += ["",
          f"- 같은 벽끼리 짝지은 항목 차이(조건 − Full, 두 조건 모두 완성된 벽만): Full − G3 (짝 {g3['items_pairs']}벽) "
          + " · ".join(f"{n} {fmt2(g3['items'][k]['diff_mean'], g3['items'][k]['ci95'])}" for k, n in (("2", "②"), ("3", "③"), ("4", "④"), ("5", "⑤")))
          + f" mm. 참값 (진단) (짝 {dg['items_pairs']}벽) "
          + " · ".join(f"{n} {fmt2(dg['items'][k]['diff_mean'], dg['items'][k]['ci95'])}" for k, n in (("2", "②"), ("3", "③"), ("4", "④"), ("5", "⑤")))
          + " mm.",
          "- ① 가로줄눈은 모르타르 모델이 줄눈을 10.00 mm로 고정해 거의 0이다(시뮬레이터 단순화). 다만 Full − G3 · Full − G2에서 한 벽씩 ① 값(|t − 10|)이 57 ~ 60 mm로 나왔다(원인 확인 안 함).",
          "- 참값 (진단)의 항목 오차가 Full보다 조금 크다(② · ③ · ⑤). 원인은 확인하지 않았다. 포스터에는 완성률만 쓴다.\n",
          "## 지표를 바꾸면 결론이 바뀌는가\n",
          "| 단계 | 완성률 차이 %p (주 지표 1) | 채운 자리 차이 (11-10 파이프라인 판정 지표) | 판정 |", "|---|---|---|---|"]
    for lab in ORDER[1:7]:
        v = R[lab]["vs_full"]
        j1 = v["complete_ci_pp"][1] < 0
        j2 = v["filled_ci"][1] < 0
        L.append(f"| {lab} | {fmt_pp(v['complete_pp'], v['complete_ci_pp'])} | {fmt2(v['filled'], v['filled_ci'])} | "
                 f"{'둘 다 몫 있음' if j1 and j2 else ('둘 다 구별 못 함' if not j1 and not j2 else '지표에 따라 다름')} |")
    L += ["",
          "- 어느 지표로 보든 몫이 있는 단계(G0 · G1 · G2 · G3 · H)와 구별 못 하는 단계(G2w)는 같다. 크기 순서는 다르다: 완성률로는 G1 = H(둘 다 완성 0) > G0 > G2 > G3, 채운 자리로는 H > G2 > G0 > G1 > G3. 포스터는 완성률 순서로 그렸다.",
          "- 두 문서의 차이: 평가지표 md(10-13)는 완성률 · 항목 오차를 주 지표로 정했고, 11-10 실험 파이프라인은 '벽당 채운 자리'를 판정 지표로 썼다. 사용자 확인(11-11): 핵심 지표는 평가지표 md다.\n",
          "## 그림 · 사진 파일\n", "| 파일 | 내용 | 크기 (포스터 위, cm) |", "|---|---|---|"]
    desc = {"그림1": "검측 단계 흐름도 (c판과 같은 그림 함수)", "그림2": "평가 기준 사다리: 자리 채움(느슨) → 벽 완성(주 1) → 시방 합격(보조), 모자이크 색 범례 겸용",
            "그림3": "조건별 100벽 모자이크: 작은 벽 하나 = 시험 벽 하나(3단 16자리), 파랑 = 완성 · 시방 합격, 주황 = 완성 · 시방 불합격, 회색 = 미완성 벽의 채운 자리, 흰색 = 빈 자리. 칸 안은 합격 → 불합격 → 채운 자리 많은 순으로 정렬",
            "그림4": "완성된 벽의 ② · ③ · ④ 측정값 점그림, Full 대 Full − G3, 허용 6 mm 선, 오른쪽 = 6 mm 넘은 벽 수",
            "사진1": "Full 완성벽 700300 정면", "사진2": "Full 완성벽 700300 비스듬히"}
    for n, (q, w, h) in F.items():
        L.append(f"| [`{rel(q)}`]({rel(q)}) | {desc[n.split('_')[0]]} | {w:.1f} × {h:.1f} |")
    L += ["\n## 데이터 출처 (sha256 앞 16)\n"] + [f"- `{k}` {v}" for k, v in sorted(sources.items())]
    L += ["\n## 확인할 것 · 남은 것\n",
          "- **시험 배치(730000번대)는 쓰지 않았다.** 모든 수치는 개발 배치다. 포스터 결론에 'Full 구성과 문턱을 같은 개발 배치에서 정해 값이 낙관적일 수 있다'를 적었다.",
          "- **RQ2는 실패 분석에서 나온 질문**으로 표시했다(연구 질문 표 · 1절 예상 기여 · 4절 고찰). 미리 정한 판정 문턱이 없어 짝 차이로만 보고한다.",
          "- **제목**: 학회 규정상 바꿀 수 있다고 사용자가 확인(11-11). 영문 제목은 한 줄에 들어가게 부제를 'A Three-Course Wall Study'로 줄였다.",
          "- **저자 · 소속**: c판(이전 포스터 줄)과 같다.",
          "- **동그라미 숫자**: 나눔고딕에 ①②③ 글자가 없어 pptx 글자에서는 (1)(2)(3)으로 썼다. 그림(PNG) 안은 ①~⑤를 그대로 쓴다. 빼기 기호(−)는 pptx 글자에서 짧은 줄표(–)로 바뀐다(c판과 같음).",
          "- **감사의 글**: 사용자가 준 문장을 한 글자도 바꾸지 않고 넣었다.",
          "- **참고문헌**: 4편만 넣었다(본문에서 [1] ~ [4]로 인용). 서지는 [신규성 검토 6절](논문_신규성검토_및_참고문헌.md) 기준이며, 원문으로 한 번 더 확인해야 한다. '확인한 범위의 선행연구는 전체 성공률만 보고' 문장은 문헌 목록 검토에 기댄 것이다.",
          "- PowerPoint로 열어 보지 못했다(이 컴퓨터에 없음). 미리보기 PNG는 스크립트가 대략 그린 것이다. 글꼴(나눔고딕)이 없는 PC에서는 줄바꿈이 달라질 수 있다.",
          f"- 점검: 왼쪽 단 끝 {left_end:.2f} cm · 오른쪽 단 끝 {right_end:.2f} cm (흰 단 끝 83.42 cm). 글자 넘침 · 겹침 경고 {len(warns)}건, 패키지 오류 {len(errs)}건."
          + ("" if not (warns or errs) else " " + " / ".join(warns + errs)),
          "- 다시 만들기 (출력이 있으면 덮어쓰지 않으므로 `--tag`를 새로 준다):",
          "  ```", f"  cd sim && MPLCONFIGDIR=/tmp/mpl PYTHONPATH=. venv/bin/python -m wall3.poster_ksarc_20261111d --tag {a.tag}e", "  ```"]
    md.write_text("\n".join(L) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="20261111d")
    ap.add_argument("--out-dir", default=None, help="default 02_KSARC2026 (a scratch dir for trial builds)")
    ap.add_argument("--figures-only", action="store_true")
    a = ap.parse_args()
    build(a)


if __name__ == "__main__":
    main()
