"""능동 카메라 세팅의 구성(pick)과 필수 조건 판정(judge). 규칙은 기준_해석_능동카메라_20261113.md 4 · 5절(결과 전에 고정).
여기서는 계산만 한다. 손목 H0의 보이는 비율은 1차 계산(같은 궤적 · 같은 프레임)의 값을 쓴다.

실행: cd sim && PYTHONPATH=. venv/bin/python -m prl.select_active pick --grid outputs/prl/<받침 격자> --fixed outputs/prl/s2_metrics_c_20261112 \\
        --out-json prl/active_settings_20261113.json --out-md <표.md>
      cd sim && PYTHONPATH=. venv/bin/python -m prl.select_active judge --settings prl/active_settings_20261113.json --final outputs/prl/<확정 세팅 계산> \\
        --fixed outputs/prl/s2_metrics_c_20261112 --out-json <json> --out-md <표.md>
"""
import argparse, json
from pathlib import Path

import numpy as np

from prl import config as C
from prl.geom_metrics import seg_of_phase, SEGMENTS, TARGETS

TIE = 0.005
SEG = list(SEGMENTS)
PICK_APP, PLACE_APP = SEG.index("집기 접근"), SEG.index("놓기 접근")
T_PICK, T_SLOT = TARGETS.index("pick"), TARGETS.index("slot")
TRACK_MIN = 0.95
FOVEA_RAW = 448          # 참고 값: 가운데 448 × 448 원본 화소를 224로 줄여 본다면(2배)


def load(run, fixed):
    M = json.loads((Path(run) / "metrics.json").read_text())
    F = np.load(Path(run) / "frames.npz")
    G = np.load(Path(fixed) / "frames.npz")
    assert np.array_equal(F["wall"], G["wall"]) and np.array_equal(F["t"], G["t"]) and np.array_equal(F["phase"], G["phase"]), \
        "the active run and the first-round run do not cover the same frames"
    h0 = G["vis"][:, [str(c) for c in G["cams"]].index("H0")]
    cams = [str(c) for c in F["cams"]]
    seg = seg_of_phase()[F["phase"]]
    m_pick = (seg == PICK_APP) & np.isfinite(h0[:, T_PICK])
    m_slot = (seg == PLACE_APP) & np.isfinite(h0[:, T_SLOT])
    return M, F, cams, h0, m_pick, m_slot


def best_of(names, key, tie):
    lo = min(key[n] for n in names)
    tied = sorted(n for n in names if key[n] - lo <= TIE)
    return min(tied, key=lambda n: (tie[n], n)), tied, lo


def px224(mm_raw, crop=None):
    """Pixels of a 90 mm brick edge in the 224 policy image: whole image (1280 → 224) or a centre crop of `crop` raw pixels."""
    return 90.0 / (mm_raw * (C.RAW_W if crop is None else crop) / C.POLICY_IMG)


def pick(a):
    M, F, cams, h0, m_pick, m_slot = load(a.grid, a.fixed)
    vis, cen = F["vis"], F["cen"]
    ci = {n: i for i, n in enumerate(cams)}
    R, O, CL = M["reach"], M["occlusion"], M["clearance_m"]
    assert CL is not None, "the grid run needs --clearance"
    lt_pick = {n: vis[m_pick, ci[n], T_PICK] < 0.5 for n in cams}
    lt_slot = {n: vis[m_slot, ci[n], T_SLOT] < 0.5 for n in cams}
    hp, hs = h0[m_pick, T_PICK] < 0.5, h0[m_slot, T_SLOT] < 0.5
    info = {}
    for n in cams:
        r = R[n]
        info[n] = {"base": M["meta"]["cams"][n]["base"], "pan0": M["meta"]["cams"][n]["pan0"],
                   "reach_supply": r["supply"]["reach"], "reach_wall": r["wall"]["reach"],
                   "clear_robot_m": CL[n]["robot"], "clear_scene_m": CL[n]["scene"],
                   "clear_ok": bool(CL[n]["robot"] >= C.CAM_CLEAR and CL[n]["scene"] >= 0.0),
                   "track_pick": O[n]["centred"]["pick_approach"], "track_place": O[n]["centred"]["place_approach"],
                   "bad_pick_with_H0": float(np.mean(lt_pick[n] & hp)), "bad_slot_with_H0": float(np.mean(lt_slot[n] & hs)),
                   "bad_pick_alone": float(np.mean(lt_pick[n])), "bad_slot_alone": float(np.mean(lt_slot[n])),
                   "mm_far_supply": r["supply"]["raw_mm_per_px_far"], "mm_far_wall": r["wall"]["raw_mm_per_px_far"]}
        info[n]["mm_far_all"] = max(info[n]["mm_far_supply"], info[n]["mm_far_wall"])
        info[n]["bad_sum_with_H0"] = info[n]["bad_pick_with_H0"] + info[n]["bad_slot_with_H0"]
    ok = [n for n in cams if info[n]["clear_ok"]]
    sel, notes = {}, {}

    # A1: 능동 1대(선행) + 손목
    el = [n for n in ok if info[n]["reach_supply"] == 16 and info[n]["reach_wall"] == 16
          and info[n]["track_pick"] >= TRACK_MIN and info[n]["track_place"] >= TRACK_MIN]
    if el:
        p1, tied, lo = best_of(el, {n: info[n]["bad_sum_with_H0"] for n in el}, {n: info[n]["mm_far_all"] for n in el})
        sel["A1"] = {"P1": {"mount": p1, "role": "lead"}}
        notes["A1"] = {"eligible": len(el), "tied": tied, "min_key": lo}
        # A2: 선행 눈(A1의 받침) + 벽 눈 + 손목
        el2 = [n for n in ok if n != p1 and info[n]["reach_wall"] == 16]
        key2 = {n: float(np.mean(lt_slot[p1] & lt_slot[n] & hs)) for n in el2}
        if el2:
            p2, tied2, lo2 = best_of(el2, key2, {n: info[n]["mm_far_wall"] for n in el2})
            sel["A2"] = {"P1": {"mount": p1, "role": "lead"}, "P2": {"mount": p2, "role": "slot"}}
            notes["A2"] = {"eligible": len(el2), "tied": tied2, "min_key": lo2}
    # A3: 공급 눈 + 벽 눈 + 손목
    el3 = [n for n in ok if info[n]["reach_supply"] == 16 and info[n]["track_pick"] >= TRACK_MIN]
    el4 = [n for n in ok if info[n]["reach_wall"] == 16]
    if el3 and el4:
        q1, t3, lo3 = best_of(el3, {n: info[n]["bad_pick_with_H0"] for n in el3}, {n: info[n]["mm_far_supply"] for n in el3})
        el4 = [n for n in el4 if n != q1]
        q2, t4, lo4 = best_of(el4, {n: info[n]["bad_slot_with_H0"] for n in el4}, {n: info[n]["mm_far_wall"] for n in el4})
        sel["A3"] = {"P1": {"mount": q1, "role": "pick"}, "P2": {"mount": q2, "role": "slot"}}
        notes["A3"] = {"eligible_pick": len(el3), "tied_pick": t3, "min_key_pick": lo3, "eligible_slot": len(el4), "tied_slot": t4, "min_key_slot": lo4}
    for s in sel.values():
        for c in s.values():
            c.update(base=info[c["mount"]]["base"], pan0=info[c["mount"]]["pan0"], leave="release")
    out = {"source": {"grid": a.grid, "fixed": a.fixed}, "spec": M["meta"]["spec"], "n_mounts": len(cams), "n_clear": len(ok),
           "settings": sel, "notes": notes, "mounts": info}
    Path(a.out_json).write_text(json.dumps(out, indent=1, ensure_ascii=False))

    L = ["| 세팅 | 카메라 | 받침 | 받침점 (m) | 역할 | 시선 도달 (공급 / 벽) | 집기 접근: 이 카메라와 H0 모두 50 % 미만 | 놓기 접근: 같은 값 | 추종 (집기 / 놓기) | 가장 먼 대상의 원본 mm/화소 (공급 / 벽) | 팔과의 여유 (m) |",
         "|---|---|---|---|---|---|---|---|---|---|---|"]
    for s, cs in sel.items():
        for cn, c in cs.items():
            i = info[c["mount"]]
            L.append(f"| {s} | {cn} | {c['mount']} | ({i['base'][0]:.2f}, {i['base'][1]:.2f}, {i['base'][2]:.2f}) | {c['role']} | {i['reach_supply']}/16 / {i['reach_wall']}/16 | "
                     f"{i['bad_pick_with_H0'] * 100:.1f} % | {i['bad_slot_with_H0'] * 100:.1f} % | {i['track_pick'] * 100:.1f} % / {i['track_place'] * 100:.1f} % | "
                     f"{i['mm_far_supply']:.2f} / {i['mm_far_wall']:.2f} | {i['clear_robot_m']:.3f} |")
    L += ["", f"받침 {len(cams)}곳 중 여유 조건을 만족한 곳 {len(ok)}곳. 값은 모두 '선행' 역할로 계산한 것이다(받침을 고르는 데만 쓴다).", ""]
    for s, nt in notes.items():
        L.append(f"- {s}: " + ", ".join(f"{k} = {v if not isinstance(v, float) else round(v, 4)}" for k, v in nt.items()))
    Path(a.out_md).write_text("\n".join(L) + "\n")
    print("\n".join(L))


def judge(a):
    S = json.loads(Path(a.settings).read_text())
    M, F, cams, h0, m_pick, m_slot = load(a.final, a.fixed)
    vis, cen = F["vis"], F["cen"]
    ci = {n: i for i, n in enumerate(cams)}
    R, O = M["reach"], M["occlusion"]
    hp, hs = h0[m_pick, T_PICK] < 0.5, h0[m_slot, T_SLOT] < 0.5
    res = {}
    for s, cs in S["settings"].items():
        names = {cn: f"{s}_{cn}" for cn in cs}                     # the final run names the cameras <setting>_<P1|P2>
        sup = np.zeros(16, bool); wal = np.zeros(16, bool)
        mm_s = np.full(16, np.inf); mm_w = np.full(16, np.inf)
        for cn, c in cs.items():
            r = R[names[cn]]
            if c["role"] in ("lead", "pick"):
                f = np.array(r["supply"]["flags"]); sup |= f
                mm_s = np.where(f, np.minimum(mm_s, r["supply"]["raw_mm_per_px"]), mm_s)
            if c["role"] in ("lead", "slot"):
                f = np.array(r["wall"]["flags"]); wal |= f
                mm_w = np.where(f, np.minimum(mm_w, r["wall"]["raw_mm_per_px"]), mm_w)
        idx = [ci[n] for n in names.values()]
        bad_pick = float(np.mean((vis[m_pick][:, idx, T_PICK] < 0.5).all(1) & hp))
        bad_slot = float(np.mean((vis[m_slot][:, idx, T_SLOT] < 0.5).all(1) & hs))
        ip = [ci[names[cn]] for cn, c in cs.items() if c["role"] in ("lead", "pick")]
        isl = [ci[names[cn]] for cn, c in cs.items() if c["role"] in ("lead", "slot")]
        tr_pick = float(cen[m_pick][:, ip, 0].any(1).mean())
        tr_place = float(cen[m_slot][:, isl, 1].any(1).mean())
        it = [("시선 도달", bool(sup.all() and wal.all()), f"{int(sup.sum())}/16 · {int(wal.sum())}/16", (32 - int(sup.sum()) - int(wal.sum())) / 16),
              ("집기 접근 가림", bad_pick <= 0.05, f"{bad_pick * 100:.1f} %", bad_pick / 0.05 - 1),
              ("놓기 접근 가림", bad_slot <= 0.05, f"{bad_slot * 100:.1f} %", bad_slot / 0.05 - 1),
              ("추종", tr_pick >= TRACK_MIN and tr_place >= TRACK_MIN, f"{tr_pick * 100:.1f} % · {tr_place * 100:.1f} %",
               max(0.0, (TRACK_MIN - tr_pick) / TRACK_MIN) + max(0.0, (TRACK_MIN - tr_place) / TRACK_MIN))]
        far_s = float(mm_s[np.isfinite(mm_s)].max()) if np.isfinite(mm_s).any() else None
        far_w = float(mm_w[np.isfinite(mm_w)].max()) if np.isfinite(mm_w).any() else None
        res[s] = {"cams": {cn: {**c, "name": names[cn]} for cn, c in cs.items()}, "n_cameras": len(cs) + 1,
                  "items": [{"name": n, "pass": bool(ok), "value": v, "excess": float(ex) if not ok else 0.0} for n, ok, v, ex in it],
                  "bad_pick_frac": bad_pick, "bad_slot_frac": bad_slot, "track_pick": tr_pick, "track_place": tr_place,
                  "n_pick_frames": int(m_pick.sum()), "n_slot_frames": int(m_slot.sum()),
                  "mm_far_supply": far_s, "mm_far_wall": far_w,
                  "px224_whole": {"supply": px224(far_s) if far_s else None, "wall": px224(far_w) if far_w else None},
                  "px224_fovea": {"supply": px224(far_s, FOVEA_RAW) if far_s else None, "wall": px224(far_w, FOVEA_RAW) if far_w else None}}
    # every camera of the final run on its own (comparison of the roles at the same mount)
    per_cam = {}
    for n in cams:
        i = ci[n]
        per_cam[n] = {"role": M["meta"]["cams"][n]["role"], "base": M["meta"]["cams"][n]["base"],
                      "bad_pick_with_H0": float(np.mean((vis[m_pick, i, T_PICK] < 0.5) & hp)),
                      "bad_slot_with_H0": float(np.mean((vis[m_slot, i, T_SLOT] < 0.5) & hs)),
                      "bad_pick_alone": float(np.mean(vis[m_pick, i, T_PICK] < 0.5)), "bad_slot_alone": float(np.mean(vis[m_slot, i, T_SLOT] < 0.5)),
                      "track_pick": float(cen[m_pick, i, 0].mean()), "track_place": float(cen[m_slot, i, 1].mean()),
                      "reach_supply": R[n]["supply"]["reach"], "reach_wall": R[n]["wall"]["reach"]}
    out = {"source": {"settings": a.settings, "final": a.final, "fixed": a.fixed}, "spec": M["meta"]["spec"], "settings": res, "cameras": per_cam}
    Path(a.out_json).write_text(json.dumps(out, indent=1, ensure_ascii=False))
    L = ["| 세팅 | 구성 | 시선 도달 (공급 · 벽) | 집기 접근 가림 | 놓기 접근 가림 | 추종 (집기 · 놓기) | 224 영상에서 90 mm: 전체 영상 (공급 / 벽) | 가운데 잘라 보면 (공급 / 벽) |",
         "|---|---|---|---|---|---|---|---|"]
    for s, r in res.items():
        cells = [f"{'' if i['pass'] else '**'}{i['value']}{'' if i['pass'] else '**'}" for i in r["items"]]
        comp = " + ".join(f"{cn}({c['role']})" for cn, c in r["cams"].items()) + " + H0"
        L.append(f"| {s} | {comp} | {cells[0]} | {cells[1]} | {cells[2]} | {cells[3]} | "
                 f"{r['px224_whole']['supply']:.1f} / {r['px224_whole']['wall']:.1f} 화소 | {r['px224_fovea']['supply']:.1f} / {r['px224_fovea']['wall']:.1f} 화소 |")
    Path(a.out_md).write_text("\n".join(L) + "\n")
    print("\n".join(L))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("pick")
    p.add_argument("--grid", required=True); p.add_argument("--fixed", required=True)
    p.add_argument("--out-json", required=True); p.add_argument("--out-md", required=True)
    j = sub.add_parser("judge")
    j.add_argument("--settings", required=True); j.add_argument("--final", required=True); j.add_argument("--fixed", required=True)
    j.add_argument("--out-json", required=True); j.add_argument("--out-md", required=True)
    a = ap.parse_args()
    for f in (a.out_json, a.out_md):
        if Path(f).exists():
            raise SystemExit(f"{f} 이미 있음: 덮어쓰지 않음")
    (pick if a.cmd == "pick" else judge)(a)


if __name__ == "__main__":
    main()
