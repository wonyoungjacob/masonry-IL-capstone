"""KICEM 2026 student paper: inspection-scope experiment (which bricks the release gate inspects).

New runs only (outputs/kicem_scope, layout seeds 60000+ never used before).  G1 (grasp check with reguide) is on in every
condition; G2 (pre-release correction) and G3 (post-release score + one re-placement) act only on the inspected slots:
none / lower course (slots 0, 1) / top (slot 2) / all.
Per-slot pass uses the same rule as brick_sim.metrics.compute_metrics (4.5 mm in xy and z, 5 deg yaw, 10 deg tilt) on the
stored final poses, with the same minimum-distance assignment of bricks to slots.
Time is simulated control time; an unfinished layout counts the whole 90 s limit as spent.
"""
import json, glob, sys, statistics as st
from pathlib import Path

import numpy as np

SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SIM))
from brick_sim.scene import BrickEnv, blueprint_config
from brick_sim.metrics import _assign, quat_to_yaw_tilt

DT, LIMIT = 0.05, 90.0
SCOPES = ["none", "lower", "top", "all"]


def scene():
    spec = {'head_gap': 0.001, 'mortar_impl': 'bed', 'mortar_visual': True, 'target_marks': True, 'supply': 'scatter',
            'cure_settle_steps': 40, 'feasible_supply': True}
    cfg = blueprint_config("mortarB", size_rand=0.0, pos_rand=0.03, supply_yaw_deg=60.0, valid_supply=True, **spec)
    return BrickEnv(cfg)


def slot_ok(env, poses):
    D = np.asarray(env.design)[:, :4]
    P = np.asarray(poses)[:len(D)]
    P = P[_assign(P, D)]
    L = env.brick.L
    exy = np.hypot(P[:, 0] - D[:, 0], P[:, 1] - D[:, 1]); ez = P[:, 2] - D[:, 2]
    yt = [quat_to_yaw_tilt(q)[:2] for q in P[:, 3:7]]
    eyaw = np.degrees((np.array([a for a, _ in yt]) - D[:, 3] + np.pi) % (2 * np.pi) - np.pi)
    tilt = np.array([b for _, b in yt])
    return ((exy < 0.05 * L) & (np.abs(ez) < 0.05 * L) & (np.abs(eyaw) < 5.0) & (tilt < 10)).tolist(), (1000 * exy).tolist()


def finish(e):
    t = [((r.get("replace") or {}).get("second_release") if isinstance(r.get("replace"), dict) else None) or r for r in e["release_events"]]
    return max(x["t"] for x in t) * DT if t else None


def q(xs):
    xs = sorted(xs)
    if not xs:
        return None
    k = len(xs)
    return {"n": k, "median": round(st.median(xs), 1), "p25": round(xs[k // 4], 1), "p75": round(xs[min(k - 1, 3 * k // 4)], 1)}


def main():
    env = scene()
    res = {}
    for pol in ("act", "diffusion"):
        for sc in SCOPES:
            eps = {}
            for f in sorted(glob.glob(str(SIM / f"outputs/kicem_scope/{pol}_{sc}_*.json"))):
                for e in json.load(open(f))["episodes"]:
                    eps[e["seed"]] = e
            if not eps:
                continue
            E = [eps[s] for s in sorted(eps)]
            ok = [slot_ok(env, e["final_poses"])[0] for e in E]
            full = [e for e in E if e["m1_all_success"]]
            rel = [r for e in E for r in e["release_events"]]
            insp = [r for r in rel if r.get("inspected", True)]
            used = [finish(e) if e["m1_all_success"] else LIMIT for e in E]
            res[f"{pol}_{sc}"] = {
                "seeds": sorted(eps), "layouts": len(E), "complete": len(full),
                "lower_pass": sum(o[0] + o[1] for o in ok), "lower_n": 2 * len(E),
                "top_pass": sum(o[2] for o in ok), "top_n": len(E),
                "lower_both": sum(o[0] and o[1] for o in ok),
                "top_given_lower": sum(o[2] for o in ok if o[0] and o[1]),
                "placements": len(rel), "inspected": len(insp),
                "g2_corrected": sum(r.get("corrected", False) for r in insp),
                "g3_failed": sum(bool(r.get("bad_release")) for r in insp),
                "replaced": sum(e.get("replaced", 0) for e in E), "replaced_ok": sum(e.get("replaced_ok", 0) for e in E),
                "grasp_rejected": sum(e.get("gate_retries", 0) for e in E),
                "finish_s": q([finish(e) for e in full]),
                "time_per_accepted_wall_s": round(sum(used) / len(full), 1) if full else None,
            }
    # all scopes of a policy must cover the same layouts (paired comparison)
    for pol in ("act", "diffusion"):
        ss = [tuple(res[f"{pol}_{sc}"]["seeds"]) for sc in SCOPES if f"{pol}_{sc}" in res]
        res[f"{pol}_paired"] = len(set(ss)) == 1 if ss else None
    out = SIM / "outputs/kicem_scope/summary.json"
    out.write_text(json.dumps(res, indent=1, ensure_ascii=False))
    for k, v in res.items():
        if isinstance(v, dict):
            v = {x: y for x, y in v.items() if x != "seeds"}
        print(k, json.dumps(v, ensure_ascii=False))


if __name__ == "__main__":
    main()
