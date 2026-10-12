"""Midterm-1 slide 8 (2026-10-12): the pose-noise test results on EXACTLY the layouts behind slide 7 (condition D 30/40, 26/48).

The condition-D test numbers were collected by tools/paper_results.py from the final_test JSONs plus the per-episode log lines of
runs stopped at the deadline, on the seeds all paired conditions finished.  summarize_noise_test.py read only the JSONs, so it saw
19 / 25 seeds.  This script reuses paper_results.runs() / the same pairing, then reads the sigma 2 / 4 mm runs from
outputs/midterm1_fix on those seeds.  No simulation.

    cd sim && venv/bin/python tools/paired_noise_table.py     # writes outputs/midterm1_fix/paired_noise.{md,json}
"""
import json, math, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paper_results as pr

SIM = pr.SIM
MF = SIM / "outputs" / "midterm1_fix"
pct = lambda k, n: f"{k}/{n} ({math.floor(100 * k / n + 0.5)}%)" if n else "-"
unchanged = set(json.load(open(SIM / "outputs" / "final_test" / "unchanged_seeds.json")))
out = {"seeds": {}, "sigma0": {}, "sigma2": {}, "sigma4": {}}
lines = ["# 측정 오차 시험 배치 결과 — 7쪽과 같은 배치", "",
         "조건: 실험 3 · 넓은 배치 · 실행가능성 필터 · 학습 seed 1000 · 조건 D · 시험 배치. σ 0 = 기존 조건 D(paper_results 집계, 로그 포함)", "",
         "| 정책 | 배치 수 | σ 0 mm | σ 2 mm | σ 4 mm |", "|---|---|---|---|---|"]
for pol in ("diffusion", "act"):
    eps = {c: pr.runs(f"test_{pol}_{c}_") for c in pr.CONDS}
    if pol == "diffusion":
        old = json.load(open(SIM / "outputs" / "test_diffusion_v3_2p1_joint_image_clean_seed1000.json"))["episodes"]
        eps["A_policy"] = {e["seed"]: {"full": bool(e["m1_all_success"])} for e in old if e["seed"] in unchanged}
    paired = [c for c in pr.CONDS if c != "C_anglelaod_inplace"]
    common = sorted(set.intersection(*(set(eps[c]) for c in paired)))
    out["seeds"][pol] = common
    d0 = {s: bool(eps["E_replace"][s]["full"]) for s in common}
    row = [pol, str(len(common)), pct(sum(d0.values()), len(common))]
    out["sigma0"][pol] = d0
    for mm in (2, 4):
        got = {}
        for f in sorted(MF.glob(f"test_{pol}_s1000_D_noise{mm}mm_*.json")):
            for e in json.load(open(f))["episodes"]:
                got[int(e["seed"])] = bool(e["m1_all_success"])
        have = [s for s in common if s in got]
        out[f"sigma{mm}"][pol] = {s: got[s] for s in have}
        row.append(pct(sum(got[s] for s in have), len(have)) + ("" if len(have) == len(common) else f" ※{len(common) - len(have)}개 없음"))
    lines.append("| " + " | ".join(row) + " |")
lines += ["", "- 기대: σ 0 = Diffusion 30/40, ACT 26/48 (7쪽 조건 D)",
          "- 배치 목록: " + "; ".join(f"{p} {out['seeds'][p]}" for p in ("diffusion", "act"))]
MF.mkdir(parents=True, exist_ok=True)
(MF / "paired_noise.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
(MF / "paired_noise.json").write_text(json.dumps(out, indent=1, default=list), encoding="utf-8")
print("\n".join(lines))
