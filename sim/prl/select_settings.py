"""2단계 정리: 기하 지표 표, 계열별 최선, 세팅 6개의 구성과 좌표, 세팅별 정적 포함 · 가림 조건.

규칙은 지시 문서 6.4 · 6.7과 기준_해석_20261112.md 4 · 5절(결과 전에 고정). 여기서는 계산만 한다.

실행: cd sim && PYTHONPATH=. venv/bin/python -m prl.select_settings --metrics outputs/prl/s2_metrics_20261112 \\
        --clearance outputs/prl/s2_clearance_final_20261112/clearance.json --out-json prl/settings_20261112.json --out-md <표.md>
"""
import argparse, json
from pathlib import Path

import numpy as np

from prl import config as C
from prl.geom_metrics import seg_of_phase, SEGMENTS, TARGETS

TIE = 0.005          # 0.5 %p 이내면 같은 것으로 본다
SEG = list(SEGMENTS)
PICK_APP, PLACE_APP = SEG.index("집기 접근"), SEG.index("놓기 접근")
T_PICK, T_SLOT = TARGETS.index("pick"), TARGETS.index("slot")


def best_of(names, key, tie):
    """Lowest key; candidates within TIE of the lowest are tied and the smaller `tie` value wins."""
    lo = min(key[n] for n in names)
    tied = [n for n in names if key[n] - lo <= TIE]
    return min(tied, key=lambda n: tie[n]), tied


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--metrics", required=True)
    ap.add_argument("--clearance", required=True)
    ap.add_argument("--static", default=None, help="static.json of prl.geom_metrics --static-only (per-slot inclusion flags)")
    ap.add_argument("--out-json", required=True)
    ap.add_argument("--out-md", required=True)
    a = ap.parse_args()
    M = json.loads((Path(a.metrics) / "metrics.json").read_text())
    F = np.load(Path(a.metrics) / "frames.npz")
    cams = [str(c) for c in F["cams"]]
    if a.static:
        S = json.loads(Path(a.static).read_text())
        assert S["static"] == M["static"], "static block differs from the metrics run"
        M["static_flags"] = S["static_flags"]
    vis, phase = F["vis"], F["phase"]
    seg = seg_of_phase()[phase]
    occ, st = M["occlusion"], M["static"]
    clear = json.loads(Path(a.clearance).read_text())["clearance_m"]
    extra = M["meta"]["extra"] or {}
    pose = {n: (extra[n] if n in extra else C.FIXED_CAMS.get(n, C.WRIST_CAMS.get(n))) for n in cams}

    pick_lt = {n: occ[n]["집기 접근"]["pick"]["frac_lt50"] for n in cams}
    slot_lt = {n: occ[n]["놓기 접근"]["slot"]["frac_lt50"] for n in cams}
    pick_med = {n: occ[n]["집기 접근"]["pick"]["median"] for n in cams}
    slot_med = {n: occ[n]["놓기 접근"]["slot"]["median"] for n in cams}
    mm_s = {n: st[n].get("supply", {}).get("raw_mm_per_px", np.inf) for n in cams}
    mm_w = {n: st[n].get("wall", {}).get("raw_mm_per_px", np.inf) for n in cams}

    best, ties = {}, {}
    for fam in ("SA", "SB"):
        best[fam], ties[fam] = best_of(C.FAMILIES[fam], pick_lt, mm_s)
    for fam in ("WA", "WC", "WDE"):
        best[fam], ties[fam] = best_of(C.FAMILIES[fam], slot_lt, mm_w)
    wrist_score = {n: pick_med[n] + slot_med[n] for n in C.WRIST_CAMS}
    best["H"] = max(wrist_score, key=wrist_score.get)

    settings = {"R0": ["WB1", "WA1", "H0"], "RA": [best["SA"], best["WA"], best["H"]], "RB": [best["SB"], best["WC"], best["H"]],
                "RC": [best["SA"], best["WC"], best["H"]], "RD": [best["SB"], best["WDE"], best["H"]], "RE": ["G1", best["H"]]}
    ci = {n: i for i, n in enumerate(cams)}
    res = {}
    for name, cs in settings.items():
        fixed = [c for c in cs if c not in C.WRIST_CAMS]
        idx = [ci[c] for c in cs]
        sup = np.zeros(16, bool); wal = np.zeros(16, bool)
        for c in fixed:
            sup |= np.array(M["static_flags"][c]["supply_in_vis"]); wal |= np.array(M["static_flags"][c]["wall_in_vis"])
        m_pick = (seg == PICK_APP) & np.isfinite(vis[:, idx[0], T_PICK])
        m_slot = (seg == PLACE_APP) & np.isfinite(vis[:, idx[0], T_SLOT])
        bad_pick = float(np.mean((vis[m_pick][:, idx, T_PICK] < 0.5).all(1)))
        bad_slot = float(np.mean((vis[m_slot][:, idx, T_SLOT] < 0.5).all(1)))
        res[name] = {"cams": cs, "n_images": len(cs), "static_supply": int(sup.sum()), "static_wall": int(wal.sum()),
                     "static_ok": bool(sup.all() and wal.all()), "bad_pick_frac": bad_pick, "bad_slot_frac": bad_slot,
                     "occlusion_ok": bool(bad_pick <= 0.05 and bad_slot <= 0.05), "occlusion_index": bad_pick + bad_slot,
                     "n_pick_frames": int(m_pick.sum()), "n_slot_frames": int(m_slot.sum()),
                     "supply_measure_cam": next((c for c in fixed if pose[c].get("side") in ("supply", "both")), None),
                     "wall_measure_cam": ("WA1" if name == "R0" else next((c for c in fixed if pose[c].get("side") in ("wall", "both")), None))}
    used = sorted({c for s in settings.values() for c in s})
    out = {"source": {"metrics": a.metrics, "clearance": a.clearance, "static": a.static}, "best": best, "ties": ties, "wrist_score": wrist_score,
           "settings": res, "cameras_used": used,
           "camera_poses": {n: {k: v for k, v in pose[n].items()} for n in cams}, "wrist_mount_note": "H1 · H2: prl.config.WRIST_CAMS",
           "moved": {"WA2": {"from": list(C.FIXED_CAMS["WA2"]["pos"]), "to": extra["WA2"]["pos"], "why": "팔과의 여유 0.047 m < 0.05 m"}},
           "g1": {"pos": extra["G1"]["pos"], "target": extra["G1"]["target"]}}
    Path(a.out_json).write_text(json.dumps(out, indent=1, ensure_ascii=False))

    L = ["| 카메라 | 위치 (m) | 정적 포함: 공급 / 벽 (포함만) | 집기 접근: 집을 벽돌 중앙값 / 50 % 미만 | 놓기 접근: 놓을 자리 중앙값 / 50 % 미만 | 원본 mm/화소 (공급 / 벽) | 224에서 90 mm (화소) | 입사각 최대 (°) | 깊이 σ (mm) | 팔과의 여유 (m) |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    for n in cams:
        s = st[n]
        p = pose[n].get("pos")
        ppos = f"({p[0]:.2f}, {p[1]:.2f}, {p[2]:.2f})" if p is not None and n not in C.WRIST_CAMS else "손목"
        side = [k for k in ("supply", "wall") if k in s]
        mm = " / ".join(f"{s[k]['raw_mm_per_px']:.2f}" if k in s else "–" for k in ("supply", "wall"))
        px = " / ".join(f"{s[k]['px224_per_90mm']:.1f}" if k in s else "–" for k in ("supply", "wall"))
        inc = " / ".join(f"{s[k]['incidence_max_deg']:.0f}" if k in s else "–" for k in ("supply", "wall"))
        sg = " / ".join(f"{s[k]['depth_sigma_mm']:.1f}" if k in s else "–" for k in ("supply", "wall"))
        cl = clear[n]["robot"] if clear[n]["robot"] is not None else clear[n]["gripper"]
        L.append(f"| {n} | {ppos} | {s['supply_in_vis']}/16 ({s['supply_in']}) / {s['wall_in_vis']}/16 ({s['wall_in']}) | "
                 f"{pick_med[n] * 100:.0f} % / {pick_lt[n] * 100:.1f} % | {slot_med[n] * 100:.0f} % / {slot_lt[n] * 100:.1f} % | {mm} | {px} | {inc} | {sg} | "
                 f"{'≥ 0.50' if cl >= 0.5 else f'{cl:.3f}'} |")
    L += ["", "| 세팅 | 구성 | 정적 포함 (공급 / 벽) | 집기 접근: 모든 영상에서 50 % 미만 | 놓기 접근: 모든 영상에서 50 % 미만 | 가림 조건 (각 5 % 이하) | 정적 포함 조건 |",
          "|---|---|---|---|---|---|---|"]
    for name, r in res.items():
        L.append(f"| {name} | {' + '.join(r['cams'])} | {r['static_supply']}/16 / {r['static_wall']}/16 | {r['bad_pick_frac'] * 100:.1f} % | "
                 f"{r['bad_slot_frac'] * 100:.1f} % | {'통과' if r['occlusion_ok'] else '미달'} | {'통과' if r['static_ok'] else '미달'} |")
    Path(a.out_md).write_text("\n".join(L) + "\n")
    print("\n".join(L))
    print(json.dumps({"best": best, "ties": ties, "wrist_score": wrist_score}, ensure_ascii=False))


if __name__ == "__main__":
    main()
