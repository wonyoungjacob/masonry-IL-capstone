"""예비 그림 (2026-11-11): 조건마다 벽 그림 2개 — 자리별 채움 수와 자리별 3D IoU 문턱 통과 수 (100벽 중). 결과 파일만 읽는다.

- 사용자 요청: 벽돌 하나하나의 정확도를 보려는 그림. 시방 합격은 벽 전체 판정(16자리 모두 합격 또는 모두 아님)이라
  자리별로 나눌 수 없어, 두 번째 벽은 평가지표 md 3절의 벽돌별 3D IoU에 문턱을 두어 센다.
- **포스터(pptx)에는 넣지 않는다**(사용자: 표준 시방 기준에 근거하고 싶음). 예비 그림으로만 커밋한다.
- 문턱: 평가지표 md 3절은 IoU에 기준값을 두지 않았다. 여기서는 KCS ②③④ 허용오차 6 mm를 벽면 직각(너비) 방향 밀림으로 바꾼
  IoU = (90 − 6) / (90 + 6) = 0.875를 쓴다(온장 · 반장 같음). 시방 판정이 아니다. 다른 문턱 값도 설명 md에 함께 적는다.
- 채움: 평가지표 md 2.4절 조건 1(수평 45 mm · 높이 28.5 mm · 기울기 45° 안). 빈 자리의 IoU는 0이라 문턱 통과 수 ≤ 채움 수.
- 숫자는 개발 배치 100벽(시작값 700300 ~ 700399) · 최종 평가 전. WALL3_OUT이 있으면 그 폴더(커밋된 원자료 복사본)를 읽는다.

실행: cd sim && MPLCONFIGDIR=<임시>/mpl PYTHONPATH=. venv/bin/python -m wall3.fig_slot_iou_20261111 [--out-dir <폴더>]
"""
import argparse, hashlib
from pathlib import Path

import numpy as np

from wall3 import primary_metrics_20261111 as pm
from wall3.poster_ksarc_20261111 import INK, INK2, mpl_setup
from wall3.poster_ksarc_20261111d import ORDER, wall_rects

THR = 0.875                     # = (90 − 6) / (90 + 6): 벽면 직각 방향 6 mm 밀림
THR_ALT = [(0.810, "높이 방향 6 mm 밀림 (51 / 63)"), (0.875, "너비 방향 6 mm 밀림 (84 / 96) · 그림에 쓴 값"),
           (0.939, "길이 방향 6 mm 밀림 (184 / 196)"), (0.900, "수평 회전 약 5° (평가지표 md 3절 표)")]
NOTE = "개발 배치 100벽(시작값 700300 ~ 700399) · 최종 평가 전"
OUT = pm.SIM.parent / "02_KSARC2026" / "예비그림_3DIoU_20261111"
LO, HI = "#f4f7fb", "#163f73"


def counts(walls, thr):
    f = np.array([[bool(x) for x in w["eval"]["slots_filled"]] for w in walls])
    iou = np.array([w["eval"]["iou"] for w in walls], float)
    return f.sum(0), ((iou >= thr) & f).sum(0)


def draw(ax, vals, title, cmap, ex=1.9):
    from matplotlib.patches import Rectangle
    for (x0, z0, L, H), v in zip(wall_rects(), vals):
        z = z0 * ex
        c = cmap(v / 100.0)
        ax.add_patch(Rectangle((x0, z), L, H * ex, facecolor=c, edgecolor="white", linewidth=1.2))
        lum = 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
        ax.text(x0 + L / 2, z + H * ex / 2, f"{int(v)}", ha="center", va="center", fontsize=8.5,
                color="white" if lum < 0.5 else INK)
    ax.set_xlim(-500, 500)
    ax.set_ylim(-8, (134 + 57) * ex + 8)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title(title, fontsize=9.5, color=INK2, pad=2, loc="left")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default=str(OUT))
    a = ap.parse_args()
    od = Path(a.out_dir)
    png, md = od / "예비_자리별_채움_IoU0.875_조건별.png", od / "설명.md"
    for p in (png, md):
        if p.exists():
            raise SystemExit(f"{p} 이미 있음: 덮어쓰지 않음")
    od.mkdir(parents=True, exist_ok=True)
    keys = {lab: k for lab, k, _ in pm.ROWS}
    data, sources = {}, {}
    for lab in ORDER:
        walls, files = pm.load(keys[lab])
        sources.update(files)
        ws = [walls[s] for s in sorted(walls)]
        assert len(ws) == 100 and min(walls) == 700300 and max(walls) == 700399, lab
        data[lab] = ws

    plt = mpl_setup()
    from matplotlib.colors import LinearSegmentedColormap
    cmap = LinearSegmentedColormap.from_list("seq", [LO, "#7fa6d6", HI])
    w_cm, h_cm = 26.6, 19.0
    fig = plt.figure(figsize=(w_cm / 2.54, h_cm / 2.54), dpi=300)
    gs = fig.add_gridspec(4, 2, left=0.01, right=0.99, top=0.835, bottom=0.015, wspace=0.08, hspace=0.42)
    for i, lab in enumerate(ORDER):
        ws = data[lab]
        fc, ic = counts(ws, THR)
        comp = sum(all(w["eval"]["slots_filled"]) for w in ws)
        spec = sum(bool(w["eval"]["spec_pass"]) for w in ws)
        sg = gs[i // 2, i % 2].subgridspec(1, 2, wspace=0.06)
        ax1, ax2 = fig.add_subplot(sg[0]), fig.add_subplot(sg[1])
        draw(ax1, fc, "채움 (100벽 중)", cmap)
        draw(ax2, ic, f"채움 + IoU ≥ {THR} (예비)", cmap)
        ax1.text(0.0, 1.32, lab, transform=ax1.transAxes, ha="left", va="bottom", fontsize=12.5, color=INK,
                 fontweight="bold" if lab == "Full" else None)
        ax1.text(1.06, 1.32, f"완성 {comp} · 시방 합격 {spec} (벽 단위)", transform=ax1.transAxes, ha="left", va="bottom",
                 fontsize=10, color=INK2)
    cax = fig.add_axes([0.66, 0.935, 0.3, 0.016])
    cb = fig.colorbar(plt.cm.ScalarMappable(norm=plt.Normalize(0, 100), cmap=cmap), cax=cax, orientation="horizontal")
    cb.set_ticks([0, 25, 50, 75, 100])
    cb.ax.tick_params(labelsize=9, length=0, colors=INK2)
    cb.outline.set_visible(False)
    fig.text(0.66, 0.958, "자리마다 해당하는 벽 수 (0 ~ 100)", fontsize=10, color=INK2, va="bottom")
    fig.text(0.01, 0.962, "예비 그림 · 포스터에 넣지 않음", fontsize=12.5, color=INK, fontweight="bold", va="bottom")
    fig.text(0.01, 0.932, f"IoU ≥ {THR} = 벽면 직각 6 mm 밀림에 해당하는 문턱 (시방 판정 아님) · 벽 높이 1.9배 과장",
             fontsize=9, color=INK2, va="bottom")
    fig.text(0.01, 0.905, NOTE + " · 1단이 아래", fontsize=9, color=INK2, va="bottom")
    fig.savefig(png, dpi=300, facecolor="white")
    plt.close(fig)

    rel = lambda q: Path(q).relative_to(md.parent).as_posix()
    L = ["# 예비 그림: 자리별 채움 · 3D IoU 문턱 통과 (포스터에 넣지 않음)\n",
         f"> 2026-11-11. 그림: [`{rel(png)}`]({rel(png)}). 스크립트: `sim/wall3/fig_slot_iou_20261111.py` (결과 파일만 읽음).",
         f"> 숫자는 모두 {NOTE}.\n",
         "## 왜 예비인가\n",
         "- 사용자 요청: 조건마다 벽 그림 2개를 그려, 16자리 각각의 채움 수와 정확도 수를 색 진하기 + 숫자로 보인다.",
         "- 시방 합격은 KCS 기준상 벽 전체 판정이다. 16자리가 모두 합격이거나 모두 아니므로, 자리별로 나누면 16칸이 같은 값이 된다.",
         "- 그래서 두 번째 벽은 평가지표 md 3절의 벽돌별 3D IoU에 문턱을 두어 셌다. 평가지표 md는 IoU에 기준값을 두지 않았다.",
         "- 사용자 결정(11-11): 표준 시방 기준에 근거하고 싶으므로 이 그림은 **pptx에 넣지 않고** 예비로만 둔다.\n",
         "## 문턱\n",
         "| IoU 문턱 | 해당하는 어긋남 (벽돌 하나만, 온장 190 × 90 × 57 mm) |", "|---|---|"]
    L += [f"| {t} | {d} |" for t, d in sorted(THR_ALT)]
    L += ["", "- KCS ②③④ 허용오차 6 mm를 벽면 직각(너비) 방향 밀림으로 바꾼 0.875를 썼다(반장 90 × 90 × 57도 너비 방향은 같은 값).",
          "- IoU는 방향마다 민감도가 달라 문턱 하나로 시방 항목을 대신할 수 없다. 길이 방향 6 mm 밀림은 0.939라 통과하고, 높이 방향 6 mm 밀림은 0.810이라 걸린다.\n",
          "## 조건별 값 (자리 0 ~ 15 = 1단 왼→오 5장, 2단 반장 · 온장 4 · 반장, 3단 5장)\n",
          "| 조건 | 완성 | 시방 합격 | 채움 수 (자리 0 ~ 15) | IoU ≥ 0.875 수 (자리 0 ~ 15) | IoU 문턱별 전체 통과 / 채움 (0.810 · 0.875 · 0.939) |",
          "|---|---|---|---|---|---|"]
    for lab in ORDER:
        ws = data[lab]
        fc, ic = counts(ws, THR)
        comp = sum(all(w["eval"]["slots_filled"]) for w in ws)
        spec = sum(bool(w["eval"]["spec_pass"]) for w in ws)
        alt = " · ".join(f"{int(counts(ws, t)[1].sum())}" for t in (0.810, 0.875, 0.939))
        L.append(f"| {lab} | {comp} | {spec} | {' '.join(str(int(v)) for v in fc)} | {' '.join(str(int(v)) for v in ic)} | {alt} / {int(fc.sum())} |")
    L += ["\n## 데이터 출처 (sha256 앞 16)\n"] + [f"- `{k}` {v}" for k, v in sorted(sources.items())]
    L.append(f"- 그림 `{png.name}` {hashlib.sha256(png.read_bytes()).hexdigest()[:16]}")
    md.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("만듦:", png, md)


if __name__ == "__main__":
    main()
