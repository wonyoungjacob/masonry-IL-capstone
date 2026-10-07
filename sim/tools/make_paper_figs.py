"""Figures of the KICEM student-paper draft: completion rate by condition (bar chart) and the two gate equations."""
import io, json, sys
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from paper_results import collect, collect_multi, wilson

FIG = HERE.parent / "outputs" / "final_test"
NG = str(HERE / "fonts" / "NanumGothic-Regular.ttf")
NGB = str(HERE / "fonts" / "NanumGothic-Bold.ttf")
fm.fontManager.addfont(NG); fm.fontManager.addfont(NGB)
plt.rcParams["font.family"] = fm.FontProperties(fname=NG).get_name()
plt.rcParams["axes.unicode_minus"] = False


def bar_chart():
    m = collect_multi()
    ex = json.load(open(HERE.parent / "outputs" / "gate_val40_v2" / "expert_baseline_50000_50.json"))
    eg = json.load(open(HERE.parent / "outputs" / "gate_val40_v2" / "expert_gate_replace_50000_50.json"))
    conds = ["A", "B", "C", "D"]
    fig, ax = plt.subplots(figsize=(3.45, 1.78), dpi=400)
    w = 0.36
    cols = {"diffusion": "#2F6DA8", "act": "#E08A2E"}
    labs = {"diffusion": "Diffusion Policy", "act": "ACT"}
    for k, pol in enumerate(("diffusion", "act")):
        r = m[pol][1000]["res"]
        x = [i + (k - 0.5) * w for i in range(4)]
        y = [100 * r[c]["rate"] for c in conds]
        lo = [100 * (r[c]["rate"] - r[c]["ci"][0]) for c in conds]
        hi = [100 * (r[c]["ci"][1] - r[c]["rate"]) for c in conds]
        ax.bar(x, y, w, color=cols[pol], label=labs[pol], yerr=[lo, hi], error_kw=dict(lw=0.6, capsize=1.6, ecolor="#333333"))
        for xi, yi, h in zip(x, y, hi):
            ax.text(xi, yi + h + 2, f"{yi:.0f}", ha="center", va="bottom", fontsize=5.6)
    for j, (dat, lab) in enumerate(((ex, "기준선 1"), (eg, "기준선 2"))):
        k = sum(d["full"] for d in dat); n = len(dat); lo, hi = wilson(k, n)
        ax.bar(4.4 + j * 0.8, 100 * k / n, 0.46, color="#9A9A9A", yerr=[[100 * (k / n - lo)], [100 * (hi - k / n)]],
               error_kw=dict(lw=0.6, capsize=1.6, ecolor="#333333"), label="전문가 스크립트" if j == 0 else None)
        ax.text(4.4 + j * 0.8, 100 * hi + 2, f"{100 * k / n:.0f}", ha="center", va="bottom", fontsize=5.6)
    ax.set_xticks([0, 1, 2, 3, 4.4, 5.2])
    ax.set_xticklabels(["A\n정책 단독", "B\n+G1", "C\n+G1·G2", "D\n+G1·G2·G3", "기준선 1\n단독", "기준선 2\n+G1~G3"], fontsize=5.6)
    ax.set_ylabel("완성률 (%)", fontsize=6.3)
    ax.set_ylim(0, 112); ax.set_yticks(range(0, 101, 20)); ax.tick_params(axis="y", labelsize=5.8, length=2)
    ax.tick_params(axis="x", length=0)
    ax.axvline(3.78, color="#BBBBBB", lw=0.5, ls="--")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.spines["left"].set_linewidth(0.5); ax.spines["bottom"].set_linewidth(0.5)
    ax.grid(axis="y", lw=0.3, color="#DDDDDD"); ax.set_axisbelow(True)
    ax.legend(fontsize=5.6, frameon=False, loc="upper left", ncol=3, handlelength=1.2, columnspacing=0.9, borderaxespad=0.1)
    fig.tight_layout(pad=0.3)
    fig.savefig(FIG / "fig_bar.png", dpi=400, facecolor="white")
    plt.close(fig)


def math_img(tex, fs=13, dpi=400):
    plt.rcParams["mathtext.fontset"] = "cm"
    fig = plt.figure(figsize=(0.01, 0.01)); fig.text(0, 0, tex, fontsize=fs)
    buf = io.BytesIO(); fig.savefig(buf, dpi=dpi, bbox_inches="tight", pad_inches=0.02, facecolor="white"); plt.close(fig)
    return Image.open(buf).convert("RGB")


def equation(name, tex, tail, num):
    im = math_img(tex)
    f = ImageFont.truetype(NG, 62)
    W = 2080
    c = Image.new("RGB", (W, im.height + 24), "white"); d = ImageDraw.Draw(c)
    c.paste(im, (40, 12))
    if tail:
        d.text((40 + im.width + 22, 12 + im.height / 2), tail, font=f, fill="black", anchor="lm")
    d.text((W - 20, 12 + im.height / 2), num, font=f, fill="black", anchor="rm")
    c.save(FIG / name, dpi=(400, 400))


SYMS = {"theta_jaw": r"$\theta_{\mathrm{jaw}}$", "Fz": r"$\bar{F}_z$", "mg": r"$m_g g$", "exy": r"$\mathbf{e}_{xy}$",
        "epsi": r"$e_\psi$", "ez": r"$e_z$"}


def symbols(dpi=600, size=9.0):
    """Inline symbol images for the body text; writes sizes (pt) and baseline depth to symbols.json."""
    from matplotlib import mathtext
    from matplotlib.font_manager import FontProperties
    import json
    plt.rcParams["mathtext.fontset"] = "cm"
    meta = {}
    for k, tex in SYMS.items():
        path = FIG / f"sym_{k}.png"
        depth = mathtext.math_to_image(tex, str(path), prop=FontProperties(size=size), dpi=dpi, format="png")
        w, h = Image.open(path).size
        meta[k] = {"w": w * 72 / dpi, "h": h * 72 / dpi, "depth": depth * 72 / dpi, "path": str(path)}
    json.dump(meta, open(FIG / "symbols.json", "w"), indent=1)


if __name__ == "__main__":
    symbols()
    bar_chart()
    equation("fig_eq1.png", r"$\theta_{\mathrm{jaw}} > 0.2\,\mathrm{rad}\ \ \wedge\ \ (\bar{F}_z - m_g g) \geq 0.9\,\mathrm{N}$", "", "(식 1)")
    equation("fig_eq2.png", r"$\Vert \mathbf{e}_{xy} \Vert > 2.5\,\mathrm{mm}\ \ \vee\ \ |e_\psi| > 3^\circ\ \ \vee\ \ e_z > 3\,\mathrm{mm}$", "", "(식 2)")
    print("figures written to", FIG)
