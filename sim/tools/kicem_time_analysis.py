"""KICEM 2026 student paper (construction-management angle): intervention, rework and work time of the inspection gates.

Episodes: the paired test layouts of the seed-1000 models (same seeds as paper_results.collect: Diffusion 40, ACT 48).
Event logs come from outputs/final_test/test_*.json and, for the layouts whose original run only left a text log,
from outputs/kicem_rerun/*.json (same command, same inference seed; re-runs reproduce the logged result, checked below).

Time is simulated control time (20 Hz).  Completion time = the release of the last brick in a passing pose (after a
re-placement, the second release), because the policy never signals the end.  An unfinished layout uses the whole
90 s limit.  Paper labels: B = G1 only (lift, no coordinates), C = G1 + reguide + G2, D = C + G3.
"""
import json, glob, sys, statistics as st
from pathlib import Path

SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SIM / "tools"))
from paper_results import collect

DT, LIMIT = 0.05, 90.0
COND = {"policy+gate(lift,force)": "B", "policy+gate(reguide,release,force)": "C", "policy+gate(reguide,release,force,replace)": "D"}


def episodes():
    out = {}
    files = sorted(glob.glob(str(SIM / "outputs/final_test/test_*.json"))) + sorted(glob.glob(str(SIM / "outputs/kicem_rerun/*.json")))
    for f in files:
        d = json.load(open(f))
        c = COND.get(d.get("condition"))
        if c is None or not isinstance(d.get("episodes"), list):
            continue
        pol = "act" if "/act_" in d["config"]["ckpt"] else "diffusion"
        for e in d["episodes"]:
            e["_src"] = "rerun" if "kicem_rerun" in f else "test"
            out.setdefault((pol, c), {}).setdefault(e["seed"], e)        # the original test run wins if both exist
    return out


def finish_time(e):
    t = []
    for r in e.get("release_events", []):
        rr = r["replace"].get("second_release") if r.get("replace") else None
        t.append((rr or r)["t"])
    if t:
        return max(t) * DT
    return min(e["steps"], int(LIMIT / DT)) * DT if e.get("gate_done") else None   # B: the gate stops a finished wall


def recover_spans(e):
    """(start, end) of each stretch from a rejected close to the next verified grasp (end None: never recovered)."""
    spans, start = [], None
    for g in e.get("gate_events", []):
        if g["action"].startswith("recover") and start is None:
            start = g["t"]
        elif g["action"] == "carry" and start is not None:
            spans.append((start, g["t"])); start = None
    if start is not None:
        spans.append((start, None))
    return spans


def q(xs):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    k = len(xs)
    return {"n": k, "median": round(st.median(xs), 1), "p25": round(xs[k // 4], 1), "p75": round(xs[min(k - 1, (3 * k) // 4)], 1),
            "mean": round(st.mean(xs), 1)}


def summarize(E):
    full = [e for e in E if e["m1_all_success"]]
    rel = [r for e in E for r in e.get("release_events", [])]
    rejected = sum(e.get("gate_retries", 0) for e in E)
    verified = sum(e.get("gate_verified_grasps", 0) for e in E)
    rec = [s for e in E for s in recover_spans(e)]
    rec_closed = [(b - a) * DT for a, b in rec if b is not None]
    rec_open = [(min(e["steps"], int(LIMIT / DT)) - a) * DT for e in E for a, b in recover_spans(e) if b is None]
    repl = [(r["t"], r["replace"]["second_release"]["t"]) for e in E for r in e.get("release_events", [])
            if r.get("replace") and r["replace"].get("second_release")]
    used = [finish_time(e) if e["m1_all_success"] else LIMIT for e in E]
    return {
        "layouts": len(E), "complete": len(full), "rerun": sum(e["_src"] == "rerun" for e in E),
        "placements": len(rel), "g2_corrected": sum(r["corrected"] for r in rel),
        "g3_failed": sum(bool(r.get("bad_release")) for r in rel),
        "replaced": sum(e.get("replaced", 0) for e in E), "replaced_ok": sum(e.get("replaced_ok", 0) for e in E),
        "grasp_checks": verified + rejected, "grasp_rejected": rejected,
        "recover_s": q(rec_closed), "unrecovered_episodes": sum(1 for e in E if any(b is None for _, b in recover_spans(e))),
        "recover_time_share": round(sum(rec_closed + rec_open) / (len(E) * LIMIT), 3),
        "replace_s": q([(b - a) * DT for a, b in repl]),
        "finish_s": q([finish_time(e) for e in full]),
        "time_per_accepted_wall_s": round(sum(used) / len(full), 1) if full and None not in used else None,
    }


def main():
    r = collect()
    eps = episodes()
    res = {}
    for (pol, c), byseed in sorted(eps.items()):
        seeds = [s for s in r["seeds"][pol] if s in byseed]
        res[f"{pol}_{c}"] = summarize([byseed[s] for s in seeds])
        res[f"{pol}_{c}"]["paired_total"] = len(r["seeds"][pol])
    # the re-runs must reproduce the logged outcome of the original runs
    from paper_results import runs
    names = {"B": "C_anglelaod_inplace", "C": "D_pre_release", "D": "E_replace"}
    mism = []
    for (pol, c), byseed in eps.items():
        if c not in names:
            continue
        logged = runs(f"test_{pol}_{names[c]}_")
        for s, e in byseed.items():
            if e["_src"] == "rerun" and s in logged and logged[s]["full"] != bool(e["m1_all_success"]):
                mism.append((pol, c, s))
    res["rerun_mismatch"] = mism
    res["rerun_total"] = sum(v["rerun"] for k, v in res.items() if isinstance(v, dict) and "rerun" in v)
    out = SIM / "outputs/final_test/kicem_time.json"
    out.write_text(json.dumps(res, indent=1, ensure_ascii=False))
    for k, v in res.items():
        print(k, json.dumps(v, ensure_ascii=False))


if __name__ == "__main__":
    main()
