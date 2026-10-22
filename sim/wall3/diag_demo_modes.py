"""시연 데이터 진단 (2026-10-22): 벽돌(자리)마다 대본 행동이 여러 갈래로 갈리는 순간을 찾는다.

에피소드마다 순간 4개(집게 닫기 시작 · 운반 중간 · 집게 열기 시작 · 끝)의 행동(관절 6개 명령값)을 모아, 자리 × 관절마다
값을 정렬해 가장 큰 틈이 gap_rad 이상이고 작은 쪽이 min_frac 이상이면 '갈림'으로 표시한다. 시각(단계 길이)의 퍼짐도 남긴다.
정책이 여러 갈래 시연을 평균 내면 어느 갈래와도 안 맞는 동작이 나온다(ACT 2번 벽돌 집기 실패의 원인).

실행: cd sim && venv/bin/python -m wall3.diag_demo_modes --out <json>
"""
import argparse, glob, json
from pathlib import Path

import numpy as np
import pandas as pd

MOMENTS = ("close", "transport_mid", "open", "end")


def split_of(v, gap_rad, min_frac):
    v = np.sort(v)
    d = np.diff(v)
    i = int(np.argmax(d))
    frac = min(i + 1, len(v) - i - 1) / len(v)
    return {"gap": float(d[i]), "at": float((v[i] + v[i + 1]) / 2), "low_n": i + 1, "high_n": len(v) - i - 1,
            "split": bool(d[i] >= gap_rad and frac >= min_frac)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="data/wall3_main_20261019")
    ap.add_argument("--gap-rad", type=float, default=0.5)
    ap.add_argument("--min-frac", type=float, default=0.005)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    root = Path(a.root)
    eps = json.loads((root / "meta" / "wall3_episodes.json").read_text())
    df = pd.concat([pd.read_parquet(f, columns=["episode_index", "action"]) for f in sorted(glob.glob(str(root / "data" / "*" / "*.parquet")))])
    acts = {i: np.stack(g.action.values) for i, g in df.groupby("episode_index")}
    vals = {k: {m: [] for m in MOMENTS} for k in range(16)}
    steps = {k: {m: [] for m in MOMENTS} for k in range(16)}
    for e in eps:
        A = acts[e["episode_index"]]
        g = A[:, 6]
        ic = int(np.argmax(g > 0.15))
        io = ic + int(np.argmax(g[ic:] < 0.15))
        idx = {"close": ic, "transport_mid": (ic + io) // 2, "open": io, "end": len(A) - 1}
        for m, t in idx.items():
            vals[e["slot"]][m].append(A[t, :6])
            steps[e["slot"]][m].append(t)
    res = {"root": str(root), "episodes": len(eps), "gap_rad": a.gap_rad, "min_frac": a.min_frac, "slots": {}}
    flagged = []
    for k in range(16):
        r = {}
        for m in MOMENTS:
            V = np.array(vals[k][m])
            T = np.array(steps[k][m])
            r[m] = {"step_mean": float(T.mean()), "step_std": float(T.std()), "step_min": int(T.min()), "step_max": int(T.max()),
                    "joints": []}
            for j in range(6):
                sp = split_of(V[:, j], a.gap_rad, a.min_frac)
                r[m]["joints"].append({"mean": float(V[:, j].mean()), "std": float(V[:, j].std()), **sp})
                if sp["split"]:
                    flagged.append({"slot": k, "moment": m, "joint": j, "low_n": sp["low_n"], "high_n": sp["high_n"], "gap_rad": round(sp["gap"], 2),
                                    "at_rad": round(sp["at"], 2)})
        res["slots"][k] = r
    res["flagged"] = flagged
    # whole trajectory: every control step (episodes of a slot have the same timing within ~1 step), every arm joint
    seg = []
    for k in range(16):
        A = [acts[e["episode_index"]] for e in eps if e["slot"] == k]
        T = min(len(x) for x in A)
        X = np.stack([x[:T, :6] for x in A])                        # (episodes, T, 6)
        for j in range(6):
            on = [split_of(X[:, t, j], a.gap_rad, a.min_frac) for t in range(T)]
            t = 0
            while t < T:
                if on[t]["split"]:
                    t1 = t
                    while t1 + 1 < T and on[t1 + 1]["split"]:
                        t1 += 1
                    mn = [min(on[u]["low_n"], on[u]["high_n"]) for u in range(t, t1 + 1)]
                    seg.append({"slot": k, "joint": j, "step_from": t, "step_to": t1, "minority_n_max": int(max(mn)),
                                "gap_rad_max": round(max(on[u]["gap"] for u in range(t, t1 + 1)), 2), "episodes": len(A)})
                    t = t1 + 1
                else:
                    t += 1
    res["trajectory_splits"] = seg
    Path(a.out).write_text(json.dumps(res, indent=1))
    print(f"{len(eps)} episodes; split (gap >= {a.gap_rad} rad, minority >= {a.min_frac:.1%}):")
    for f in flagged:
        print(f"  slot {f['slot']:2d} {f['moment']:13s} joint {f['joint']}: {f['low_n']} / {f['high_n']} (gap {f['gap_rad']} rad at {f['at_rad']})")
    print("whole trajectory (every step, joints 0-5):")
    for g in seg:
        print(f"  slot {g['slot']:2d} joint {g['joint']}: steps {g['step_from']}-{g['step_to']} ({g['step_from'] * 0.05:.2f}-{g['step_to'] * 0.05:.2f} s), "
              f"minority up to {g['minority_n_max']} / {g['episodes']}, gap up to {g['gap_rad_max']} rad")
    print("step (20 Hz) mean ± std per slot: close / open / end")
    for k in range(16):
        r = res["slots"][k]
        print(f"  slot {k:2d}: " + " / ".join(f"{r[m]['step_mean']:.0f}±{r[m]['step_std']:.1f}" for m in ("close", "open", "end"))
              + "   max joint std at close/open: " + " / ".join(f"{max(j['std'] for j in r[m]['joints']):.2f}" for m in ("close", "open")))


if __name__ == "__main__":
    main()
