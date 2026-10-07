"""Figures of the capstone progress report (2026-10-01).

Numbers come from the stored result files (Experiment 1/2 JSON, tools/paper_results.py for the gate experiment), never typed in
by hand, except the Experiment 1/2 figures that already exist in 발표자료_실험1_실험2_20260922/이미지 and are reused as they are.
"""
import json, sys
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib.patches import FancyBboxPatch
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
SIM = HERE.parent
ROOT = SIM.parent
sys.path.insert(0, str(HERE))
from paper_results import collect, collect_multi

OUT = SIM / "outputs" / "capstone" / "figs"
OUT.mkdir(parents=True, exist_ok=True)
SHOTS = SIM / "outputs" / "capstone"
OLD = ROOT / "01_사기설" / "발표자료_실험1_실험2_20260922" / "이미지"
FR, FB = str(HERE / "fonts" / "NotoSansKR-Regular.ttf"), str(HERE / "fonts" / "NotoSansKR-Bold.ttf")
fm.fontManager.addfont(FR); fm.fontManager.addfont(FB)
plt.rcParams.update({"font.family": fm.FontProperties(fname=FR).get_name(), "axes.unicode_minus": False,
                     "axes.spines.top": False, "axes.spines.right": False})
COL = {"diffusion": "#2F6DA8", "act": "#E08A2E", "smolvla": "#8A8A8A", "expert": "#7A7A7A"}


def pct(k, n):
    return int((Decimal(100 * k) / Decimal(n)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def full_of(path):
    eps = json.load(open(path))["episodes"]
    return sum(bool(e["m1_all_success"]) for e in eps), len(eps)


# ------------------------------------------------------------------------------------------------ 1. timeline
def timeline():
    ev = [("9/15", "설계수행계획서", "리더암 시연 240개\n4개 정책 비교", "plan"),
          ("~9/18", "변경 ①", "리더암 → 시뮬레이션\nIK 스크립트 시연", "change"),
          ("9/18–19", "실험 1", "좁은 초기 배치\n복구 시연 탐색", "exp"),
          ("9/21", "변경 ②", "넓은 초기 배치\n놓은 뒤 재조정 금지", "change"),
          ("9/21–22", "실험 2", "깨끗한 시연 240개\n3개 정책·3시드", "exp"),
          ("9/23", "원인 진단", "첫 파지 실패\n70건 전수 분류", "exp"),
          ("9/23–28", "실험 3", "정책 밖 검측\nG1·G2·G3 단계 추가", "exp"),
          ("9/28–30", "정리", "학회 초고 2편\n(KICEM·KSARC)", "plan")]
    c = {"plan": "#5B6770", "change": "#D9822B", "exp": "#2F6DA8"}
    fig, ax = plt.subplots(figsize=(10.4, 2.35), dpi=220)
    ax.set_xlim(-0.6, len(ev) - 0.4); ax.set_ylim(-1.35, 1.05); ax.axis("off")
    ax.plot([-0.3, len(ev) - 0.7], [0.32, 0.32], color="#B8C2CA", lw=2, zorder=0)
    for i, (d, t, s, k) in enumerate(ev):
        ax.scatter([i], [0.32], s=120, color=c[k], zorder=2, edgecolor="white", linewidth=1.5)
        ax.text(i, 0.72, d, ha="center", va="center", fontsize=8.5, color="#333333")
        ax.add_patch(FancyBboxPatch((i - 0.46, -1.22), 0.92, 1.25, boxstyle="round,pad=0.02,rounding_size=0.06",
                                    facecolor=c[k], alpha=0.10, edgecolor=c[k], lw=0.9))
        ax.text(i, -0.16, t, ha="center", va="center", fontsize=9.6, fontproperties=fm.FontProperties(fname=FB), color=c[k])
        ax.text(i, -0.72, s, ha="center", va="center", fontsize=7.6, color="#222222", linespacing=1.35)
    fig.tight_layout(pad=0.2)
    fig.savefig(OUT / "timeline.png", facecolor="white"); plt.close(fig)


# ------------------------------------------------------------------------------------------------ 2. journey
def journey(m):
    e1 = {p: full_of(SIM / f"outputs/eval_{p}_v2_2p1_joint_image_clean_mortarB.json") for p in ("diffusion", "act")}
    e2 = {}
    for p, seeds in (("diffusion", (1000, 1001)), ("act", (1000, 1001, 1002))):
        ks = [full_of(SIM / f"outputs/test_{p}_v3_2p1_joint_image_clean_seed{s}.json") for s in seeds]
        e2[p] = (sum(k for k, _ in ks), sum(n for _, n in ks))
    pa, pd = m["act"]["pooled"], m["diffusion"]["pooled"]
    stages = ["실험 1\n좁은 배치(±5 mm, ±10°)", "실험 2\n넓은 배치(±30 mm, ±60°)", "실험 3 · 정책 단독\n(못 집는 배치 제외)",
              "실험 3 · 검측 G1~G3"]
    vals = {"diffusion": [e1["diffusion"], e2["diffusion"], (pd["A"]["full"], pd["A"]["n"]), (pd["D"]["full"], pd["D"]["n"])],
            "act": [e1["act"], e2["act"], (pa["A"]["full"], pa["A"]["n"]), (pa["D"]["full"], pa["D"]["n"])]}
    fig, ax = plt.subplots(figsize=(8.6, 3.0), dpi=220)
    w = 0.36
    for j, (p, lab) in enumerate((("diffusion", "Diffusion Policy"), ("act", "ACT"))):
        for i, (k, n) in enumerate(vals[p]):
            x = i + (j - 0.5) * w
            ax.bar(x, 100 * k / n, w, color=COL[p], label=lab if i == 0 else None)
            ax.text(x, 100 * k / n + 2, f"{pct(k, n)}%\n({k}/{n})", ha="center", va="bottom", fontsize=7.2, linespacing=1.1)
    ax.axvspan(1.5, 3.5, color="#EEF3F7", zorder=-1)
    ax.set_xticks(range(4)); ax.set_xticklabels(stages, fontsize=8.2)
    ax.set_ylim(0, 112); ax.set_ylabel("완성률 (%)", fontsize=9); ax.tick_params(axis="y", labelsize=8)
    ax.legend(fontsize=8.2, frameon=False, loc="upper right", ncol=2)
    fig.tight_layout(pad=0.3)
    fig.savefig(OUT / "journey.png", facecolor="white"); plt.close(fig)
    return vals


# ------------------------------------------------------------------------------------------------ 3. experiment 1
def exp1():
    pol = [("Diffusion", "diffusion"), ("ACT", "act"), ("SmolVLA", "smolvla")]
    f = {"diffusion": "eval_diffusion_v2_2p1_joint_image_clean_mortarB.json", "act": "eval_act_v2_2p1_joint_image_clean_mortarB.json",
         "smolvla": "eval_smolvla_v2_2p1_joint_image_clean_mortarB.json"}
    fig, axs = plt.subplots(1, 2, figsize=(9.2, 2.75), dpi=220, gridspec_kw={"width_ratios": [1, 1.5]})
    ax = axs[0]
    for i, (lab, p) in enumerate(pol):
        k, n = full_of(SIM / "outputs" / f[p])
        ax.bar(i, 100 * k / n, 0.6, color=COL[p]); ax.text(i, 100 * k / n + 2, f"{k}/{n}", ha="center", fontsize=8)
    ax.set_xticks(range(3)); ax.set_xticklabels([p[0] for p in pol], fontsize=8.5)
    ax.set_ylim(0, 105); ax.set_ylabel("완성률 (%)", fontsize=8.5); ax.tick_params(axis="y", labelsize=8)
    ax.set_title("(a) 정상 시연만 학습", fontsize=9.5)
    ax = axs[1]
    sets = [("clean\n정상만", "clean"), ("plus\n+복구", "plus"), ("plus2\n+복구 많이", "plus2"), ("plustop\n+복구+위 카메라", "plustop")]
    comp, fall = [], []
    for _, s in sets:
        eps = json.load(open(SIM / f"outputs/eval_diffusion_v2_2p1_joint_image_{s}_mortarB.json"))["episodes"]
        comp.append(100 * sum(bool(e["m1_all_success"]) for e in eps) / len(eps))
        fall.append(sum(e["m7_fallen_count"] > 0 for e in eps))
    x = range(len(sets))
    ax.bar([i - 0.19 for i in x], comp, 0.38, color=COL["diffusion"], label="완성률 (%)")
    ax.bar([i + 0.19 for i in x], fall, 0.38, color="#B9C7D3", label="낙하 판정 에피소드 수")
    for i in x:
        ax.text(i - 0.19, comp[i] + 2, f"{comp[i]:.0f}", ha="center", fontsize=8)
        ax.text(i + 0.19, fall[i] + 2, f"{fall[i]}", ha="center", fontsize=8, color="#555555")
    ax.set_xticks(list(x)); ax.set_xticklabels([s[0] for s in sets], fontsize=7.8)
    ax.set_ylim(0, 105); ax.tick_params(axis="y", labelsize=8); ax.legend(fontsize=7.6, frameon=False, loc="upper right")
    ax.set_title("(b) Diffusion: 복구 시연을 섞었을 때 (각 100회)", fontsize=9.5)
    fig.tight_layout(pad=0.4)
    fig.savefig(OUT / "exp1.png", facecolor="white"); plt.close(fig)


# ------------------------------------------------------------------------------------------------ 4. experiment 2 screenshots
def crop_panel(path, box):
    return Image.open(path).convert("RGB").crop(box)


def strip(items, out, h=300):
    f = ImageFont.truetype(FB, 26); fs = ImageFont.truetype(FR, 22)
    ims = [im.resize((int(im.width * h / im.height), h), Image.Resampling.LANCZOS) for im, _, _ in items]
    W = sum(im.width for im in ims) + 14 * (len(ims) - 1)
    S = Image.new("RGB", (W, h + 80), "white"); d = ImageDraw.Draw(S); x = 0
    for im, (_, t, s) in zip(ims, items):
        S.paste(im, (x, 0)); d.rectangle((x, 0, x + im.width - 1, h - 1), outline="#C8D0D6", width=2)
        d.text((x + 6, h + 6), t, font=f, fill="#173B57"); d.text((x + 6, h + 44), s, font=fs, fill="#444444")
        x += im.width + 14
    S.save(out, quality=92)


def exp2_shots():
    front = (0, 60, 360, 420)
    strip([(crop_panel(OLD / "05_실험2_수집실패_첫파지_seed1001_t002.4.png", (60, 100, 330, 330)), "(a) 첫 파지 실패",
            "집게가 로봇 몸통에 걸려 못 내려감"),
           (crop_panel(OLD / "06_실험2_수집실패_두번째배치높이_seed1009_t011.9.png", (0, 100, 220, 300)), "(b) 잘못 놓음",
            "둘째 블록이 이웃 끝에 걸침(+13 mm)"),
           (crop_panel(OLD / "12_실험2_SmolVLA_진행실패_seed50000_t030.0.png", (0, 90, 360, 330)), "(c) 빈손 운반",
            "블록은 그대로인데 손은 벽 위치로")],
          OUT / "exp2_shots.jpg")


# ------------------------------------------------------------------------------------------------ 5. diagnosis scatter
def diagnosis():
    d = json.load(open(SIM / "outputs/diag_first_grasp/first_grasp_static2.json"))
    groups = [("성공", [x for x in d if not x["fail_first"]], "#C5CCD2", "o", 10),
              ("실패: 로봇 몸통과 충돌", [x for x in d if x["fail_first"] and x["self_pen"] > 0.5], "#C0392B", "o", 22),
              ("실패: 옆 블록과 충돌", [x for x in d if x["fail_first"] and x["self_pen"] <= 0.5 and x["nbr_pen"] > 2], "#E08A2E", "s", 22),
              ("실패: 그 밖", [x for x in d if x["fail_first"] and x["self_pen"] <= 0.5 and x["nbr_pen"] <= 2], "#222222", "x", 26)]
    fig, ax = plt.subplots(figsize=(5.4, 3.1), dpi=220)
    for lab, g, c, mk, s in groups:
        ax.scatter([1000 * x["r_tcp"] for x in g], [x["yaw"] for x in g], s=s, c=c, marker=mk, label=f"{lab} ({len(g)})",
                   linewidths=0.9 if mk == "x" else 0.3, edgecolors="white" if mk != "x" else None, alpha=0.95)
    ax.set_xlabel("로봇 중심에서 집는 위치까지 거리 (mm)", fontsize=8.5); ax.set_ylabel("블록 방향 (°)", fontsize=8.5)
    ax.tick_params(labelsize=7.8); ax.legend(fontsize=7.2, frameon=False, loc="upper left", bbox_to_anchor=(1.0, 1.0))
    ax.set_title("실험 2 시연 수집 454회: 첫 블록 집기 결과", fontsize=9.2)
    fig.tight_layout(pad=0.3)
    fig.savefig(OUT / "diagnosis.png", facecolor="white"); plt.close(fig)
    return {lab: len(g) for lab, g, *_ in groups}


# ------------------------------------------------------------------------------------------------ 6. gate experiment
def stages(m, r):
    fig, axs = plt.subplots(1, 2, figsize=(9.6, 3.05), dpi=220, gridspec_kw={"width_ratios": [1.55, 1]})
    ax = axs[0]
    lab = ["A\n정책 단독", "B\n+G1 파지 확인", "C\n+G2 놓기 전 보정", "D\n+G3 놓은 뒤 재배치"]
    w = 0.38
    for j, (p, name) in enumerate((("diffusion", "Diffusion Policy"), ("act", "ACT"))):
        res = m[p][1000]["res"]
        for i, k in enumerate("ABCD"):
            s = res[k]; x = i + (j - 0.5) * w
            ax.bar(x, 100 * s["rate"], w, color=COL[p], label=name if i == 0 else None)
            ax.text(x, 100 * s["rate"] + 2, f"{pct(s['full'], s['n'])}", ha="center", fontsize=7.8)
    ax.set_xticks(range(4)); ax.set_xticklabels(lab, fontsize=8)
    ax.set_ylim(0, 100); ax.set_ylabel("완성률 (%)", fontsize=8.5); ax.tick_params(axis="y", labelsize=8)
    ax.legend(fontsize=7.8, frameon=False, loc="upper left")
    nd, na = m["diffusion"][1000]["res"]["A"]["n"], m["act"][1000]["res"]["A"]["n"]
    ax.set_title(f"(a) 검측을 한 단계씩 더함 (학습 시드 1개, 같은 초기 배치 {nd}·{na}개)", fontsize=9)
    ax = axs[1]
    pd, pa = m["diffusion"]["pooled"], m["act"]["pooled"]
    ex = {}
    for tag, f in (("alone", "expert_baseline_50000_50.json"), ("gate", "expert_gate_replace_50000_50.json")):
        dat = json.load(open(SIM / "outputs/gate_val40_v2" / f)); ex[tag] = (sum(x["full"] for x in dat), len(dat))
    groups = [("Diffusion\n(시드 3개)", (pd["A"]["full"], pd["A"]["n"]), (pd["D"]["full"], pd["D"]["n"]), COL["diffusion"]),
              ("ACT\n(시드 3개)", (pa["A"]["full"], pa["A"]["n"]), (pa["D"]["full"], pa["D"]["n"]), COL["act"]),
              ("좌표를 아는\n스크립트", ex["alone"], ex["gate"], COL["expert"])]
    for i, (g, a, d, c) in enumerate(groups):
        ax.bar(i - 0.19, 100 * a[0] / a[1], 0.38, color=c, alpha=0.38, label="검측 없음" if i == 0 else None)
        ax.bar(i + 0.19, 100 * d[0] / d[1], 0.38, color=c, label="G1~G3" if i == 0 else None)
        ax.text(i - 0.19, 100 * a[0] / a[1] + 2, f"{pct(*a)}", ha="center", fontsize=7.8)
        ax.text(i + 0.19, 100 * d[0] / d[1] + 2, f"{pct(*d)}", ha="center", fontsize=7.8)
    ax.set_xticks(range(3)); ax.set_xticklabels([g[0] for g in groups], fontsize=8)
    ax.set_ylim(0, 100); ax.tick_params(axis="y", labelsize=8)
    ax.legend(fontsize=7.6, frameon=False, loc="upper left")
    ax.set_title("(b) 학습 시드 3개 합산, 스크립트 비교", fontsize=9)
    fig.tight_layout(pad=0.4)
    fig.savefig(OUT / "stages.png", facecolor="white"); plt.close(fig)
    return ex


def noise(r):
    N = r["noise"]
    fig, ax = plt.subplots(figsize=(3.6, 2.6), dpi=220)
    for p, name in (("diffusion", "Diffusion Policy"), ("act", "ACT")):
        xs = [0, 2, 4]; s = [N[p][mm] for mm in xs]
        ax.plot(xs, [100 * v["full"] / v["n"] for v in s], marker="o", color=COL[p], label=f"{name} (n={s[0]['n']})")
        dy = 4 if p == "diffusion" else -9          # Diffusion labels above the line, ACT below (they meet at 4 mm)
        for x, v in zip(xs, s):
            ax.text(x + 0.12, 100 * v["full"] / v["n"] + dy, f"{v['full']}/{v['n']}", fontsize=7, color=COL[p])
    ax.set_xticks([0, 2, 4]); ax.set_xticklabels(["0", "2", "4"]); ax.set_xlabel("블록 좌표 측정 오차 (표준편차, mm)", fontsize=8)
    ax.set_ylabel("완성률 (%)", fontsize=8); ax.set_ylim(0, 100); ax.set_xlim(-0.3, 4.9); ax.tick_params(labelsize=7.6)
    ax.legend(fontsize=7, frameon=False, loc="upper right")
    fig.tight_layout(pad=0.3)
    fig.savefig(OUT / "noise.png", facecolor="white"); plt.close(fig)


# ------------------------------------------------------------------------------------------------ 7. episode snapshots
def snapshots():
    g, p = SHOTS / "act_s1000_50018_gates", SHOTS / "act_s1000_50018_policy"
    if not (g / "wfinal.jpg").exists():
        return False
    ev = json.load(open(g / "events.json"))
    rel = ev["release_events"]; empty = next(e["t"] for e in ev["gate_events"] if e["action"].startswith("recover"))
    bad = next(r for r in rel if r.get("replace")); t2 = bad["replace"]["second_release"]["t"]
    q = lambda t: 4 * round(t / 4)
    box = (130, 150, 830, 640)
    wb = (60, 145, 900, 535)                          # wall view without the empty background above the arm
    W = lambda path: Image.open(path).crop(wb)
    items = [(Image.open(g / f"t{q(empty):05d}.jpg").crop(box).crop((0, 0, 700, 420)), f"① G1 파지 확인 ({empty / 20:.1f}초)",
              "빈손으로 닫힘 → 다음 블록 위로 다시 접근"),
             (W(g / f"w{q(bad['t']) + 4:05d}.jpg"), f"② G2 놓기 전 보정 ({bad['t'] / 20:.1f}초)",
              f"이웃에 걸려 높이 오차 {bad['ez_mm']:.0f} mm, 보정 불가"),
             (W(g / f"w{q(bad['t']) + 16:05d}.jpg"), "③ G3 놓은 뒤 채점",
              f"기울기 {bad['post_release']['tilt_deg']:.0f}° → 불합격, 재배치 결정"),
             (W(g / f"w{q(t2) + 8:05d}.jpg"), f"④ 1회 재배치 ({t2 / 20:.1f}초)",
              f"다시 놓음: 위치 오차 {bad['replace']['second_release']['post_release']['exy_mm']:.1f} mm"),
             (W(g / "wfinal.jpg"), "⑤ 검측 적용(D) 최종", "3개 모두 합격"),
             (W(p / "wfinal.jpg"), "비교: 정책 단독(A) 최종", "걸친 채 90초가 끝남, 합격 0개")]
    rows = []
    for k in range(0, 6, 3):
        strip(items[k:k + 3], OUT / f"_row{k}.jpg", h=300)
        rows.append(Image.open(OUT / f"_row{k}.jpg"))
    Wd = max(r.width for r in rows)
    G = Image.new("RGB", (Wd, sum(r.height for r in rows) + 10), "white")
    G.paste(rows[0], (0, 0)); G.paste(rows[1], (0, rows[0].height + 10))
    G.save(OUT / "episode.jpg", quality=92)
    for k in (0, 3):
        (OUT / f"_row{k}.jpg").unlink()
    return True


if __name__ == "__main__":
    m, r = collect_multi(), collect()
    timeline()
    print("journey", journey(m))
    exp1(); exp2_shots()
    print("diagnosis", diagnosis())
    print("expert", stages(m, r))
    noise(r)
    print("snapshots", snapshots())
