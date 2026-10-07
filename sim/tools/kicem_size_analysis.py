"""KICEM 2026 student paper: brick dimensional tolerance vs. an imitation-learned masonry robot.

New runs only (outputs/kicem_size, layout seeds 61000-61029, never used before).  Diffusion Policy (seed-1000 model, trained on
bricks of one nominal size) runs alone, no inspection gate.  size_rand s draws L, W, H each uniformly in +/- s of nominal,
once per run (all three bricks of a run share the size).  The drawn size is recovered by resetting the same scene.
Per-brick pass = brick_sim.metrics rule (4.5 % of L in xy and z, 5 deg yaw, 10 deg tilt) after min-distance assignment.
"""
import json, glob, sys
from pathlib import Path

import numpy as np

SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SIM))
from brick_sim.scene import BrickEnv, blueprint_config, design_poses
from brick_sim.metrics import _assign, quat_to_yaw_tilt

LEVELS = [("s0", 0.0), ("s15", 0.015), ("s30", 0.03), ("s60", 0.06)]
SPEC = {'head_gap': 0.001, 'mortar_impl': 'bed', 'mortar_visual': True, 'target_marks': True, 'supply': 'scatter',
        'cure_settle_steps': 40, 'feasible_supply': True}
NOM = None
RUN = sys.argv[1] if len(sys.argv) > 1 else "kicem_size"     # outputs/<RUN>: kicem_size (policy alone) | kicem_size_e
# scoring reference: "true" = design rebuilt from each run's sampled size; "nominal" = the drawing (nominal size)
SCORE = sys.argv[2] if len(sys.argv) > 2 else "true"


def env_for(s):
    cfg = blueprint_config("mortarB", size_rand=s, pos_rand=0.03, supply_yaw_deg=60.0, valid_supply=True, **SPEC)
    return BrickEnv(cfg)


def per_brick(env, poses):
    D = np.asarray(env.design if SCORE == "true" else design_poses(env.cfg, env.cfg.brick))[:, :4]
    P = np.asarray(poses)[:len(D)]
    P = P[_assign(P, D)]
    L = env.brick.L if SCORE == "true" else env.cfg.brick.L
    exy = np.hypot(P[:, 0] - D[:, 0], P[:, 1] - D[:, 1]); ez = P[:, 2] - D[:, 2]
    yt = [quat_to_yaw_tilt(q)[:2] for q in P[:, 3:7]]
    eyaw = np.abs(np.degrees((np.array([a for a, _ in yt]) - D[:, 3] + np.pi) % (2 * np.pi) - np.pi))
    tilt = np.array([b for _, b in yt])
    tol = 0.05 * L
    ok = (exy < tol) & (np.abs(ez) < tol) & (eyaw < 5.0) & (tilt < 10)
    kind = []
    for i in range(len(D)):
        if ok[i]:
            kind.append("ok")
        elif exy[i] > 0.03:
            kind.append("unplaced")          # never brought to its slot (still at the supply / dropped elsewhere)
        elif tilt[i] >= 10 or abs(ez[i]) >= tol:
            kind.append("riding")            # tilted or lifted: sits on a neighbour's end or edge
        elif eyaw[i] >= 5.0:
            kind.append("yaw")
        else:
            kind.append("offset")            # flat and in place but more than the tolerance away
    return ok.tolist(), kind, (1000 * exy).tolist()


def main():
    global NOM
    rows = []
    for tag, s in LEVELS:
        env = env_for(s)
        files = sorted(glob.glob(str(SIM / f"outputs/{RUN}/diffusion_{tag}_*.json")))
        files += [f for f in sorted(glob.glob(str(SIM / f"outputs/{RUN}/diffusion_{tag}_*.json.partial")))
                  if f[:-len(".partial")] not in files]        # a run still going: its finished episodes
        for f in files:
            for e in json.load(open(f))["episodes"]:
                env.reset(e["seed"])
                b = env.brick
                if NOM is None and s == 0.0:
                    NOM = (b.L, b.W, b.H)
                ok, kind, exy = per_brick(env, e["final_poses"])
                full = bool(e["m1_all_success"]) if SCORE == "true" else all(ok)
                rows.append({"level": tag, "s": s, "seed": e["seed"], "L": b.L, "W": b.W, "H": b.H, "full": full,
                             "ok": ok, "kind": kind, "exy": exy, "iou": float(e["m8_voxel_iou"])})
    if NOM is None:
        NOM = (0.09, 0.042632, 0.027)
    # paired comparison: keep only the layouts every level finished
    common = set.intersection(*[{r["seed"] for r in rows if r["level"] == t} for t, _ in LEVELS])
    rows = [r for r in rows if r["seed"] in common]
    res = {"levels": {}, "bins": {}}
    for tag, s in LEVELS:
        R = [r for r in rows if r["level"] == tag]
        if not R:
            continue
        kinds = [k for r in R for k in r["kind"]]
        res["levels"][tag] = {"s": s, "n": len(R), "seeds": sorted(r["seed"] for r in R), "complete": sum(r["full"] for r in R),
                              "lower_pass": sum(r["ok"][0] + r["ok"][1] for r in R), "top_pass": sum(r["ok"][2] for r in R),
                              "course1": sum(r["ok"][0] and r["ok"][1] for r in R),      # both lower bricks pass
                              "course2_given1": sum(r["ok"][2] for r in R if r["ok"][0] and r["ok"][1]),
                              "bricks": 3 * len(R), "bricks_pass": sum(sum(r["ok"]) for r in R),
                              "kinds": {k: kinds.count(k) for k in ("ok", "unplaced", "riding", "yaw", "offset")},
                              # run-level cause of an incomplete run: first of unplaced > riding > yaw > offset among its bricks
                              "causes": {k: sum(1 for r in R if not r["full"] and next(c for c in ("unplaced", "riding", "yaw", "offset")
                                                                                       if c in r["kind"]) == k)
                                         for k in ("unplaced", "riding", "yaw", "offset")},
                              "iou": round(float(np.mean([r["iou"] for r in R])), 3),
                              "exy_placed_mm": round(float(np.median([x for r in R for x, k in zip(r["exy"], r["kind"]) if k != "unplaced"])), 2)}
    # completion against the actual length deviation, all levels pooled (shorter vs longer than the trained size)
    dl = lambda r: 100 * (r["L"] / NOM[0] - 1)
    for name, lo, hi in (("L<-3%", -99, -3), ("-3~-1%", -3, -1), ("-1~+1%", -1, 1), ("+1~+3%", 1, 3), ("L>+3%", 3, 99)):
        R = [r for r in rows if lo <= dl(r) < hi]
        res["bins"][name] = {"n": len(R), "complete": sum(r["full"] for r in R), "course1": sum(r["ok"][0] and r["ok"][1] for r in R),
                             "riding": sum(k == "riding" for r in R for k in r["kind"]),
                             "bricks_pass": sum(sum(r["ok"]) for r in R), "bricks": 3 * len(R)}
    ss = {tuple(v["seeds"]) for v in res["levels"].values()}
    res["paired"] = len(ss) == 1
    res["rows"] = [{k: v for k, v in r.items() if k not in ("exy",)} for r in rows]
    out = SIM / f"outputs/{RUN}/summary_{SCORE}.json"
    out.write_text(json.dumps(res, indent=1, ensure_ascii=False))
    for k, v in res["levels"].items():
        print(k, {x: y for x, y in v.items() if x != "seeds"})
    for k, v in res["bins"].items():
        print(k, v)
    print("paired", res["paired"])


if __name__ == "__main__":
    main()
