"""선정 규칙(지시 문서 6.7, 기준_해석 5 · 8절) 적용: 기하 조건 + 측정 오차 + ACT 장당 성공률 → 표와 판정.

계산만 한다. 기준은 여기서 바꾸지 않는다.
실행: cd sim && PYTHONPATH=. venv/bin/python -m prl.select_final --measure outputs/prl/s3_measure_20261112 \\
        --evals outputs/prl/s4_eval_{S}_s1000_20261112 --out-json <json> --out-md <md>
"""
import argparse, json
from pathlib import Path

from prl import config as C

ORDER = ["R0", "RA", "RB", "RC", "RD", "RE"]


def items(geo, meas):
    """The five necessary items of one setting: (name, pass, value text, relative excess when failed)."""
    out = []
    n_in = min(geo["static_supply"], 16) + min(geo["static_wall"], 16)
    out.append(("정적 포함", geo["static_ok"], f"{geo['static_supply']}/16 · {geo['static_wall']}/16", (32 - n_in) / 16))
    for key, name in (("bad_pick_frac", "집기 접근 가림"), ("bad_slot_frac", "놓기 접근 가림")):
        v = geo[key]
        out.append((name, v <= 0.05, f"{v * 100:.1f} %", v / 0.05 - 1))
    for key, name in (("supply", "공급대 벽돌 측정"), ("placed", "놓인 벽돌 측정")):
        m = meas[key] if meas else None
        if not m or not m["xy_mm"]:
            out.append((name, False, "못 잼", 10.0))
            continue
        p95, miss = m["xy_mm"]["p95"], m["miss_rate"]
        ok = p95 <= 2.0 and miss <= 0.02
        out.append((name, ok, f"{p95:.2f} mm · {miss * 100:.1f} %", max(p95 / 2.0 - 1, 0) + max(miss / 0.02 - 1, 0)))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--measure", required=True)
    ap.add_argument("--evals", required=True, help="eval folder pattern with {S}")
    ap.add_argument("--out-json", required=True)
    ap.add_argument("--out-md", required=True)
    a = ap.parse_args()
    S = C.load_settings()["settings"]
    M = json.loads((Path(a.measure) / "summary.json").read_text())
    res = {}
    for s in ORDER:
        it = items(S[s], M["settings"].get(s))
        ev_path = Path(a.evals.format(S=s)) / "summary.json"
        ev = json.loads(ev_path.read_text()) if ev_path.exists() else None
        fails = [(n, v, ex) for n, ok, v, ex in it if not ok]
        res[s] = {"cams": S[s]["cams"], "items": [{"name": n, "pass": bool(ok), "value": v} for n, ok, v, _ in it],
                  "necessary_pass": not fails, "n_failed": len(fails), "excess": float(sum(ex for _, _, ex in fails)),
                  "occlusion_index": S[s]["occlusion_index"], "n_images": S[s]["n_images"],
                  "act": ({"success_rate": ev["success_rate"], "ci95": ev["success_ci95"], "trials": ev["trials"],
                           "filled_xy_err_mm": ev["filled_xy_err_mm"], "within_6mm": ev["filled_within_6mm_rate_of_trials"],
                           "fail_kinds": ev["fail_kinds"], "timeout_rate": ev["timeout_rate"], "by_slot": ev["success_by_slot"]} if ev else None)}
    passing = [s for s in ORDER if res[s]["necessary_pass"]]
    ranked = sorted([s for s in passing if res[s]["act"]], key=lambda s: -res[s]["act"]["success_rate"])
    nearest = min(ORDER, key=lambda s: (res[s]["n_failed"], res[s]["excess"]))
    decision = {"passing": passing, "ranked": ranked, "nearest": nearest,
                "selected": None, "note": "통과 세팅 없음: 기준을 낮추지 않고 멈춤" if not passing else "seed 2000 · 3000 추가 학습 뒤 최종 비교"}
    out = {"settings": res, "decision": decision, "measure_meta": M.get("_meta")}
    Path(a.out_json).write_text(json.dumps(out, indent=1, ensure_ascii=False))
    L = ["| 세팅 | 구성 | 정적 포함 | 집기 접근 가림 | 놓기 접근 가림 | 공급대 벽돌 측정 (수평 95백분위 · 못 잼) | 놓인 벽돌 측정 | 필수 조건 | ACT 장당 성공률 (95 % 구간) | 채운 것의 수평 오차 중앙값 | 6 mm 이내 |",
         "|---|---|---|---|---|---|---|---|---|---|---|"]
    for s in ORDER:
        r = res[s]
        cells = [f"{'' if i['pass'] else '**'}{i['value']}{'' if i['pass'] else '**'}" for i in r["items"]]
        act = r["act"]
        a_txt = f"{act['success_rate'] * 100:.1f} % ({act['ci95'][0] * 100:.1f} ~ {act['ci95'][1] * 100:.1f})" if act else "–"
        e_txt = f"{act['filled_xy_err_mm']['median']:.1f} mm" if act and act["filled_xy_err_mm"]["n"] else "–"
        w_txt = f"{act['within_6mm'] * 100:.1f} %" if act else "–"
        L.append(f"| {s} | {' + '.join(r['cams'])} | " + " | ".join(cells) + f" | {'통과' if r['necessary_pass'] else f'미달 {r["n_failed"]}개'} | {a_txt} | {e_txt} | {w_txt} |")
    L += ["", f"필수 조건 통과: {', '.join(passing) if passing else '없음'}. 가장 가까운 세팅: {nearest} "
              f"(미달 {res[nearest]['n_failed']}개: {', '.join(i['name'] for i in res[nearest]['items'] if not i['pass'])})."]
    Path(a.out_md).write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
