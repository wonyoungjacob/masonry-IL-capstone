"""후보 그림 두 장 (2026-11-11): k번째 벽돌의 채움과 시방 합격을 시방 기준(KCS 41 34 00) 안에서 보인다. 결과 파일만 읽는다.

후보 1 조건 × 자리 표: 행 = 조건 8개(행마다 박스), 열 = 자리 0 ~ 15(쌓는 순서, 반장 칸은 좁게) + 완성 + 시방 합격.
         칸 = 그 자리를 채운 벽 수(100벽 중). 시방 합격은 벽 전체 판정이라 벽 단위 칸에만 둔다.
후보 3 시방 불합격의 원인 벽돌: 조건마다 박스 하나, 벽 그림 하나. 칸 = 완성했지만 시방 불합격인 벽 가운데, 불합격 항목에서
         '가장 크게 어긋난 벽돌'로 평가 기록에 남은 벽 수. 쓰는 기록: ① 범위를 벗어난 줄눈의 벽돌(slots), ② 면(plane_slot),
         ③ 수직도(worst_slot), ④ 평면상 위치(worst_slot). ② 수평(단 단위 기록)과 ⑤ 벽 두께(x 위치 기록)는 벽돌 하나로 정할 수 없어
         칸에 넣지 않고 글로 센다. 한 벽이 여러 칸에 셀 수 있다(항목마다 벽돌이 다를 때).
색은 0 = 흰색 → 최대 = 주황(사용자 지시). 숫자는 개발 배치 100벽(시작값 700300 ~ 700399) · 최종 평가 전.
WALL3_OUT이 있으면 그 폴더(커밋된 원자료 복사본)를 읽는다. 출력이 있으면 덮어쓰지 않는다.

실행: cd sim && MPLCONFIGDIR=<임시>/mpl PYTHONPATH=. venv/bin/python -m wall3.fig_slot_kcs_20261111 [--out-dir <폴더>]
"""
import argparse, hashlib
from pathlib import Path

import numpy as np

from wall3 import primary_metrics_20261111 as pm
from wall3.fig_slot_iou_20261111 import EDGE, HI, LO, case_box
from wall3.poster_ksarc_20261111 import GREY, INK, INK2, mpl_setup
from wall3.poster_ksarc_20261111d import ORDER, wall_rects

NOTE = "개발 배치 100벽(시작값 700300 ~ 700399) · 최종 평가 전"
OUT = pm.SIM.parent / "02_KSARC2026" / "그림후보_자리별_시방_20261111"
ITEM_NAME = {"1": "①", "2": "②", "3": "③", "4": "④", "5": "⑤"}


def cause(e):
    """완성 · 시방 불합격 벽 하나 → (원인 벽돌 집합, 칸에 못 넣은 기록 목록, 불합격 항목 목록)."""
    slots, other, items = set(), [], []
    b, l, p, q, t = e["1_bed_joint"], e["2_line_plane"], e["3_plumb"], e["4_position"], e["5_thickness"]
    if not b["pass"]:
        items.append("1")
        slots |= set(b["slots"])
    if not l["pass"]:
        items.append("2")
        if l["plane_mm"] > l["tol_mm"]:
            slots.add(l["worst"]["plane_slot"])
        if max(l["level_mm"].values()) > l["tol_mm"]:
            other.append(f"② 수평 {l['worst']['level_course']}단")
    if not p["pass"]:
        items.append("3")
        slots.add(p["worst_slot"])
    if not q["pass"]:
        items.append("4")
        slots.add(q["worst_slot"])
    if not t["pass"]:
        items.append("5")
        other.append("⑤ 벽 두께")
    return slots, other, items


def load_all():
    keys = {lab: k for lab, k, _ in pm.ROWS}
    data, sources = {}, {}
    for lab in ORDER:
        walls, files = pm.load(keys[lab])
        sources.update(files)
        assert len(walls) == 100 and min(walls) == 700300 and max(walls) == 700399, lab
        data[lab] = [walls[s] for s in sorted(walls)]
    return data, sources


def summarize(ws):
    f = np.array([[bool(x) for x in w["eval"]["slots_filled"]] for w in ws])
    comp = int(f.all(1).sum())
    spec = sum(bool(w["eval"]["spec_pass"]) for w in ws)
    cnt = np.zeros(16, int)
    items, other, detail = {}, {}, []
    for w in ws:
        e = w["eval"]
        if not all(e["slots_filled"]) or e["spec_pass"]:
            continue
        sl, ot, it = cause(e)
        for k in sl:
            cnt[k] += 1
        for k in it:
            items[k] = items.get(k, 0) + 1
        for o in ot:
            other[o] = other.get(o, 0) + 1
        detail.append((w["seed"], it, sorted(sl), ot))
    return {"fill": f.sum(0), "complete": comp, "spec": spec, "cause": cnt, "items": items, "other": other, "detail": detail}


def text_color(c):
    return "white" if 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2] < 0.55 else INK


def fig_table(S, path, plt, cmap):
    from matplotlib.patches import Rectangle
    w_cm, h_cm = 26.6, 13.2
    fig = plt.figure(figsize=(w_cm / 2.54, h_cm / 2.54), dpi=300)
    ax = fig.add_axes([0.005, 0.005, 0.99, 0.80])
    widths = [1.0] * 5 + [0.55] + [1.0] * 4 + [0.55] + [1.0] * 5
    gaps = {5: 0.32, 11: 0.32}                       # 단 사이 틈
    x0, xs = 5.3, []
    x = x0
    for k, wd in enumerate(widths):
        x += gaps.get(k, 0.06 if k else 0)
        xs.append((x, wd))
        x += wd
    xc0 = x + 0.75
    xcols = [(xc0, 1.7), (xc0 + 1.7 + 0.08, 1.7)]
    xend = xcols[-1][0] + xcols[-1][1]
    rh, gap = 1.0, 0.42
    n = len(ORDER)
    for i, lab in enumerate(ORDER):
        s = S[lab]
        y = (n - 1 - i) * (rh + gap)
        ax.add_patch(Rectangle((0.12, y - 0.13), xend + 0.13 - 0.12, rh + 0.26, fill=False, edgecolor=GREY, linewidth=1.1))
        ax.text(0.3, y + rh / 2, lab, ha="left", va="center", fontsize=11.5, color=INK, fontweight="bold" if lab == "Full" else None)
        for (cx, wd), v in zip(xs, s["fill"]):
            c = cmap(v / 100)
            ax.add_patch(Rectangle((cx, y), wd, rh, facecolor=c, edgecolor=EDGE, linewidth=0.7))
            ax.text(cx + wd / 2, y + rh / 2, str(int(v)), ha="center", va="center", fontsize=8.5 if wd > 0.6 else 7, color=text_color(c))
        for (cx, wd), v in zip(xcols, (s["complete"], s["spec"])):
            c = cmap(v / 100)
            ax.add_patch(Rectangle((cx, y), wd, rh, facecolor=c, edgecolor=EDGE, linewidth=0.7))
            ax.text(cx + wd / 2, y + rh / 2, str(int(v)), ha="center", va="center", fontsize=10, color=text_color(c), fontweight="bold")
    ytop = (n - 1) * (rh + gap) + rh + 0.2
    for k, (cx, wd) in enumerate(xs):
        ax.text(cx + wd / 2, ytop + 0.05, str(k), ha="center", va="bottom", fontsize=8.5, color=INK2)
    for a, b, name in ((0, 4, "1단"), (5, 10, "2단 (5 · 10 반장)"), (11, 15, "3단")):
        xa, xb = xs[a][0], xs[b][0] + xs[b][1]
        ax.plot([xa, xb], [ytop + 0.75, ytop + 0.75], color=INK2, lw=1.0)
        ax.text((xa + xb) / 2, ytop + 0.85, name, ha="center", va="bottom", fontsize=10, color=INK)
    for (cx, wd), name in zip(xcols, ("완성", "시방 합격")):
        ax.text(cx + wd / 2, ytop + 0.05, name, ha="center", va="bottom", fontsize=9.5, color=INK, fontweight="bold")
    ax.text(xcols[0][0], ytop + 0.85, "벽 단위", ha="left", va="bottom", fontsize=10, color=INK)
    ax.text(x0, ytop + 1.55, "자리 (쌓는 순서, 0부터)", ha="left", va="bottom", fontsize=9.5, color=INK2)
    ax.set_xlim(0, xend + 0.3)
    ax.set_ylim(-0.25, ytop + 2.1)
    ax.axis("off")
    fig.text(0.008, 0.965, "후보 1 · 조건 × 자리: 자리마다 채운 벽 수, 끝 두 칸은 벽 단위 완성 · 시방 합격 (100벽 중)", fontsize=12, color=INK,
             fontweight="bold", va="bottom")
    fig.text(0.008, 0.925, f"채움 = 설계 자리에서 수평 45 mm · 높이 28.5 mm · 기울기 45° 안 (느슨) · 시방 합격 = 완성 + KCS ①~⑤ 모두 · {NOTE}",
             fontsize=8.5, color=INK2, va="bottom")
    cax = fig.add_axes([0.80, 0.885, 0.18, 0.018])
    fig.text(0.79, 0.894, "채운 벽 수 (100벽 중)", fontsize=9, color=INK2, va="center", ha="right")
    cb = fig.colorbar(plt.cm.ScalarMappable(norm=plt.Normalize(0, 100), cmap=cmap), cax=cax, orientation="horizontal")
    cb.set_ticks([0, 50, 100])
    cb.ax.tick_params(labelsize=8.5, length=0, colors=INK2)
    cb.outline.set_visible(False)
    fig.savefig(path, dpi=300, facecolor="white")
    plt.close(fig)


def fig_cause(S, path, plt, cmap_base):
    from matplotlib.colors import LinearSegmentedColormap
    from matplotlib.patches import Rectangle
    vmax = max(int(S[lab]["cause"].max()) for lab in ORDER) or 1
    w_cm, h_cm = 26.6, 16.5
    fig = plt.figure(figsize=(w_cm / 2.54, h_cm / 2.54), dpi=300)
    gs = fig.add_gridspec(4, 2, left=0.018, right=0.982, top=0.82, bottom=0.075, wspace=0.1, hspace=0.42)
    ex = 1.9
    for i, lab in enumerate(ORDER):
        s = S[lab]
        cell = gs[i // 2, i % 2]
        case_box(fig, cell, top_pad=0.0, pad=0.006)
        sg = cell.subgridspec(1, 2, width_ratios=[1.0, 1.0], wspace=0.04)
        at, aw = fig.add_subplot(sg[0]), fig.add_subplot(sg[1])
        at.axis("off")
        nfail = s["complete"] - s["spec"]
        at.text(0.02, 0.92, lab, transform=at.transAxes, ha="left", va="top", fontsize=12, color=INK,
                fontweight="bold" if lab == "Full" else None)
        if s["complete"] == 0:
            msg = ["완성 벽 0", "시방 판정 대상 없음"]
        elif nfail == 0:
            msg = [f"완성 {s['complete']} → 시방 합격 {s['spec']}", "불합격 벽 없음"]
        else:
            its = " · ".join(f"{ITEM_NAME[k]} {v}" for k, v in sorted(s["items"].items()))
            msg = [f"완성 {s['complete']} → 시방 합격 {s['spec']}", f"불합격 {nfail}벽 · 항목별 벽 수", its]
            if s["other"]:
                msg.append("칸 밖: " + " · ".join(f"{k.replace(' 벽 두께', '')} {v}" for k, v in sorted(s["other"].items())))
        for j, m in enumerate(msg):
            at.text(0.02, 0.69 - j * 0.175, m, transform=at.transAxes, ha="left", va="top", fontsize=10 if j == 0 else 9,
                    color=INK if j < 2 else INK2)
        for (x0, z0, L, H), v in zip(wall_rects(), s["cause"]):
            c = cmap_base(v / vmax)
            aw.add_patch(Rectangle((x0, z0 * ex), L, H * ex, facecolor=c, edgecolor=EDGE, linewidth=0.9))
            if nfail:
                aw.text(x0 + L / 2, z0 * ex + H * ex / 2, str(int(v)), ha="center", va="center", fontsize=8.5, color=text_color(c))
        aw.set_xlim(-500, 500)
        aw.set_ylim(-8, (134 + 57) * ex + 8)
        aw.set_aspect("equal")
        aw.axis("off")
    fig.text(0.008, 0.962, "후보 3 · 시방 불합격의 원인 벽돌: 완성했지만 시방 불합격인 벽에서, 불합격 항목이 가장 크게 어긋난 벽돌로 기록한 자리",
             fontsize=11.5, color=INK, fontweight="bold", va="bottom")
    fig.text(0.008, 0.925, f"칸 값 = 그 벽돌이 원인으로 기록된 불합격 벽 수 (한 벽이 여러 칸에 셀 수 있음) · 1단이 아래 · 벽 높이 1.9배 과장 · {NOTE}",
             fontsize=8.5, color=INK2, va="bottom")
    fig.text(0.008, 0.02, "쓰는 기록: ① 범위를 벗어난 줄눈의 벽돌 · ② 면 · ③ 수직도 · ④ 평면상 위치에서 가장 크게 어긋난 벽돌. "
             "② 수평(단 단위)과 ⑤ 벽 두께(x 위치)는 벽돌 하나로 정할 수 없어 칸에 넣지 않고 왼쪽에 센다.", fontsize=8.5, color=INK2, va="bottom")
    cax = fig.add_axes([0.80, 0.872, 0.18, 0.016])
    cb = fig.colorbar(plt.cm.ScalarMappable(norm=plt.Normalize(0, vmax), cmap=cmap_base), cax=cax, orientation="horizontal")
    cb.set_ticks([0, vmax])
    cb.ax.tick_params(labelsize=8.5, length=0, colors=INK2)
    cb.outline.set_visible(False)
    fig.text(0.79, 0.88, "원인으로 기록된 불합격 벽 수", fontsize=9, color=INK2, va="center", ha="right")
    fig.savefig(path, dpi=300, facecolor="white")
    plt.close(fig)
    return vmax


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default=str(OUT))
    a = ap.parse_args()
    od = Path(a.out_dir)
    p1, p3, md = od / "후보1_조건x자리_채움_완성_시방.png", od / "후보3_시방불합격_원인벽돌.png", od / "설명.md"
    for p in (p1, p3, md):
        if p.exists():
            raise SystemExit(f"{p} 이미 있음: 덮어쓰지 않음")
    od.mkdir(parents=True, exist_ok=True)
    data, sources = load_all()
    S = {lab: summarize(ws) for lab, ws in data.items()}
    plt = mpl_setup()
    from matplotlib.colors import LinearSegmentedColormap
    cmap = LinearSegmentedColormap.from_list("w2o", [LO, HI])
    fig_table(S, p1, plt, cmap)
    vmax = fig_cause(S, p3, plt, cmap)

    rel = lambda q: Path(q).relative_to(md.parent).as_posix()
    L = ["# 후보 그림: k번째 벽돌의 채움과 시방 합격 (KCS 기준 안에서)\n",
         f"> 2026-11-11. 스크립트: `sim/wall3/fig_slot_kcs_20261111.py` (결과 파일만 읽음). 숫자는 모두 {NOTE}.",
         "> 포스터(pptx)에 넣을지는 아직 정하지 않았다. 시방 합격은 벽 전체 판정(16개 모두 합격 또는 모두 아님)이라 벽돌별 '시방 합격'은 만들지 않는다.\n",
         "| 그림 | 보여 주는 것 |", "|---|---|",
         f"| [`{rel(p1)}`]({rel(p1)}) | 조건 × 자리 표. 칸 = 그 자리를 채운 벽 수(100벽 중), 끝 두 칸 = 벽 단위 완성 · 시방 합격. 조건마다 박스, 반장 칸은 좁게 |",
         f"| [`{rel(p3)}`]({rel(p3)}) | 조건마다 박스 · 벽 그림 하나. 칸 = 완성했지만 시방 불합격인 벽에서 그 벽돌이 불합격 항목의 '가장 크게 어긋난 벽돌'로 기록된 벽 수 (색 최대 {vmax}) |\n",
         "## 후보 3의 원인 벽돌 기록\n",
         "- 쓰는 평가 기록(`spec_metrics.py` 결과): ① `1_bed_joint.slots`(범위를 벗어난 줄눈의 벽돌), ② `2_line_plane.worst.plane_slot`(면이 불합격일 때), "
         "③ `3_plumb.worst_slot`, ④ `4_position.worst_slot`.",
         "- ② 수평은 단(`level_course`)으로만, ⑤ 벽 두께는 x 위치(`worst_x_m`)로만 기록돼 벽돌 하나로 정할 수 없다. 칸에 넣지 않고 글로 센다.",
         "- '가장 크게 어긋난 벽돌'은 그 항목 값을 정한 벽돌이다. 다른 벽돌도 허용을 넘었을 수 있다(평가 기록에는 가장 큰 것 하나만 있음).\n",
         "| 조건 | 완성 | 시방 합격 | 불합격 벽 | 항목별 불합격 벽 | 칸에 없는 기록 | 원인 벽돌 수 (자리 0 ~ 15) |", "|---|---|---|---|---|---|---|"]
    for lab in ORDER:
        s = S[lab]
        its = " · ".join(f"{ITEM_NAME[k]} {v}" for k, v in sorted(s["items"].items())) or "–"
        ot = " · ".join(f"{k} {v}" for k, v in sorted(s["other"].items())) or "–"
        L.append(f"| {lab} | {s['complete']} | {s['spec']} | {s['complete'] - s['spec']} | {its} | {ot} | {' '.join(str(int(v)) for v in s['cause'])} |")
    L += ["", "### 불합격 벽 하나씩 (시작값 · 불합격 항목 · 원인 벽돌 · 칸에 없는 기록)\n"]
    for lab in ORDER:
        for seed, it, sl, ot in S[lab]["detail"]:
            L.append(f"- {lab} · {seed} · {' '.join(ITEM_NAME[k] for k in it)} · 자리 {sl} · {', '.join(ot) or '–'}")
    L += ["", "## 후보 1의 값 (자리별 채운 벽 수)\n", "| 조건 | 자리 0 ~ 15 | 완성 | 시방 합격 |", "|---|---|---|---|"]
    for lab in ORDER:
        s = S[lab]
        L.append(f"| {lab} | {' '.join(str(int(v)) for v in s['fill'])} | {s['complete']} | {s['spec']} |")
    L += ["\n## 데이터 출처 (sha256 앞 16)\n"] + [f"- `{k}` {v}" for k, v in sorted(sources.items())]
    for q in (p1, p3):
        L.append(f"- 그림 `{q.name}` {hashlib.sha256(q.read_bytes()).hexdigest()[:16]}")
    md.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("만듦:", p1, p3, md)


if __name__ == "__main__":
    main()
