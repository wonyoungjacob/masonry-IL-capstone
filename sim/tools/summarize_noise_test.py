"""Midterm-1 slide 8: completion vs gate pose noise on the test batch, paired with the condition-D test results.

    cd sim && venv/bin/python tools/summarize_noise_test.py      # writes outputs/midterm1_fix/summary_noise.md

sigma 0 = the existing condition-D (E_replace) test results in outputs/final_test (seed1000 model, no pose noise, sim pose).
Paired layouts: Diffusion = outputs/final_test/unchanged_seeds.json present in its D results (expect 40); ACT = every seed in its
D results (expect 48).  Percentages rounded half up.
"""
import glob, json, math
from pathlib import Path

SIM = Path(__file__).resolve().parents[1]
FT = SIM / "outputs" / "final_test"; MF = SIM / "outputs" / "midterm1_fix"
pct = lambda k, n: f"{k}/{n} ({math.floor(100 * k / n + 0.5)}%)" if n else "-"


def episodes(path):
    d = json.loads(Path(path).read_text())
    return d.get("episodes", []), d.get("config", {})


def pol_of(cfg, path):
    s = (cfg.get("ckpt", "") + " " + str(path)).lower()
    return "diffusion" if "diffusion" in s else ("act" if "act" in s else None)


# sigma 0: existing D results
d0 = {"diffusion": {}, "act": {}}
for f in sorted(glob.glob(str(FT / "*.json"))):
    try:
        eps, cfg = episodes(f)
    except Exception:
        continue
    if not cfg or not eps or "seed1000" not in cfg.get("ckpt", ""):
        continue
    if not (cfg.get("gate_replace") and cfg.get("release_gate") and cfg.get("grasp_gate")):
        continue
    if float(cfg.get("gate_pose_noise", 0) or 0) != 0 or cfg.get("gate_pose_source", "sim") != "sim" or float(cfg.get("disturb", 0) or 0) != 0:
        continue
    p = pol_of(cfg, f)
    for e in eps:
        if 50000 <= int(e["seed"]) < 50050 and p:
            d0[p][int(e["seed"])] = bool(e["m1_all_success"])
# sigma 2 / 4: new runs
dn = {(p, mm): {} for p in ("diffusion", "act") for mm in (2, 4)}
incomplete = []
for f in sorted(glob.glob(str(MF / "test_*_s1000_D_noise*mm_*.json"))):
    eps, cfg = episodes(f)
    p = "diffusion" if "_diffusion_" in f else "act"
    mm = 2 if "noise2mm" in f else 4
    for e in eps:
        dn[(p, mm)][int(e["seed"])] = bool(e["m1_all_success"])
incomplete = sorted(glob.glob(str(MF / "*.partial")))

uf = FT / "unchanged_seeds.json"
uns = None
if uf.exists():
    u = json.loads(uf.read_text())
    uns = set(int(x) for x in (u if isinstance(u, list) else u.get("seeds", u.get("unchanged", []))))
paired = {"diffusion": sorted(s for s in d0["diffusion"] if uns is None or s in uns), "act": sorted(d0["act"])}

lines = ["# 측정 오차(gate pose noise) 시험 배치 결과", "",
         "조건: 실험 3 · 넓은 배치 ±30 mm·±60° · 실행가능성 필터 · 학습 seed 1000 · 조건 D(E_replace) · 시험 배치 50000~50049", "",
         "## 짝지은 배치 (7쪽과 같은 배치)", "", "| 정책 | 배치 수 | σ 0 mm | σ 2 mm | σ 4 mm |", "|---|---|---|---|---|"]
for p in ("diffusion", "act"):
    S = paired[p]
    row = [p, str(len(S)), pct(sum(d0[p][s] for s in S), len(S))]
    for mm in (2, 4):
        have = [s for s in S if s in dn[(p, mm)]]
        row.append(pct(sum(dn[(p, mm)][s] for s in have), len(have)) + ("" if len(have) == len(S) else f" ※{len(S) - len(have)}개 없음"))
    lines.append("| " + " | ".join(row) + " |")
lines += ["", "## 50개 전체 (참고)", "", "| 정책 | σ 0 mm | σ 2 mm | σ 4 mm |", "|---|---|---|---|"]
for p in ("diffusion", "act"):
    row = [p, pct(sum(d0[p].values()), len(d0[p]))] + [pct(sum(dn[(p, mm)].values()), len(dn[(p, mm)])) for mm in (2, 4)]
    lines.append("| " + " | ".join(row) + " |")
lines += ["", f"- unchanged_seeds.json: {'있음' if uns is not None else '없음 (Diffusion은 D 결과의 seed 전부 사용)'}",
          f"- σ 0 확인(기대 Diffusion 30/40, ACT 26/48): Diffusion {pct(sum(d0['diffusion'][s] for s in paired['diffusion']), len(paired['diffusion']))}, "
          f"ACT {pct(sum(d0['act'][s] for s in paired['act']), len(paired['act']))}",
          f"- 미완료(.partial) 파일: {', '.join(Path(x).name for x in incomplete) if incomplete else '없음'}"]
MF.mkdir(parents=True, exist_ok=True)
(MF / "summary_noise.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print("\n".join(lines))
