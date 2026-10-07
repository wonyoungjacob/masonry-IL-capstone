"""Export each figure and table of the KICEM size paper as its own file (vector PDF + 600 dpi PNG) for pasting into HWP.

Same drawing code and fonts as build_kicem_size.py; captions are left out (typed in HWP), table notes stay in the image and
listed in 캡션.txt.  Output: 03_KICEM2026_대학생/그림표/.
"""
import json, shutil, subprocess, sys
from pathlib import Path

from reportlab.pdfgen import canvas

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import importlib
KS = importlib.import_module(sys.argv[1] if len(sys.argv) > 1 else "build_kicem_size")   # build_kicem_e: revised paper
REVISED = KS.__name__ == "build_kicem_e"

OUT = KS.OUTDIR / "그림표"
PAD = 2          # pt of white margin around each item
DPI = 600


def flowable_pdf(fs, path):
    """Flowables stacked top to bottom (a table and its note, or a drawing) on a tight page."""
    fs = fs if isinstance(fs, list) else [fs]
    sz = [f.wrap(KS.COLW, KS.H) for f in fs]
    w, h = max(x for x, _ in sz), sum(y for _, y in sz) + 1.5 * (len(fs) - 1)
    c = canvas.Canvas(str(path), pagesize=(w + 2 * PAD, h + 2 * PAD))
    y = PAD + h
    for f, (_, fh) in zip(fs, sz):
        y -= fh; f.drawOn(c, PAD, y); y -= 1.5
    c.showPage(); c.save()


def to_png(pdf, png):
    subprocess.run(["pdftocairo", "-png", "-singlefile", "-r", str(DPI), str(pdf), str(png.with_suffix(""))], check=True)


def body(kt):
    from reportlab.platypus import Table
    from reportlab.graphics.shapes import Drawing
    return next(x for x in kt._content if isinstance(x, (Table, Drawing)))


def main():
    if REVISED:
        R = json.load(open(KS.FIG / "summary_nominal.json"))
    else:
        from kicem_size_results import results_text
        R = json.load(open(KS.FIG / "summary.json")); R.update(results_text(R))
    OUT.mkdir(exist_ok=True)
    KS.bin_figure(R); KS.level_figure(R)
    caps = []
    items = [("그림 1", body(KS.flow_figure()), "그림 1. 연구 절차", None),
             ("그림 2", KS.OLDFIG / "fig_task.png", "그림 2. 실험 장면(MuJoCo 시뮬레이션)", None),
             ("그림 3", KS.FIG / "fig_levels.pdf", "그림 3. 수준별 층별 성공률" if REVISED else "그림 3. 수준별 벽돌의 합격과 불합격 유형", None),
             ("그림 4", KS.FIG / "fig_bins.pdf", "그림 4. 실제 길이 편차 구간별 1층 성공률과 전체 완성률(모든 수준 합산)" if REVISED else "그림 4. 실제 길이 편차 구간별 완성률(모든 수준 합산)", None)]
    for name, kt in (("표 1", KS.table_ks()), ("표 2", KS.table_levels()), ("표 3", KS.table_results(R)), ("표 4", KS.table_shape(R))):
        cap, note = kt._content[0].text, kt._content[-1].text      # [caption, table, note]
        items.append((name, body(kt), cap, note))   # note typed as text under the image in the HWP (listed in 캡션.txt)
    for name, src, cap, note in items:
        pdf, png = KS.FIG / f"export_{name}.pdf", OUT / f"{name}.png"      # vector intermediate stays in outputs/
        if isinstance(src, Path) and src.suffix == ".png":
            shutil.copy(src, png); pdf = None             # rendered scene: raster only
        elif isinstance(src, Path):
            shutil.copy(src, pdf); to_png(pdf, png)
        else:
            flowable_pdf(src, pdf); to_png(pdf, png)
        caps.append(cap + (f"\n  {note}" if note else ""))
        print(name, png.name, pdf.name if pdf else "-")
    (OUT / "캡션.txt").write_text("\n".join(caps) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
