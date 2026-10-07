"""Collect the paper numbers from the final runs (2026-09-28).

Every eval_policy.py run prints one line per finished episode, so runs that were stopped at the deadline still count up
to their last finished episode.  Conditions are compared on the seeds that ALL of them finished (paired comparison).
"""
import json, math, re
from pathlib import Path

SIM = Path("/home/won/masonry/sim")
LOGS = SIM / "logs" / "final_test"
EP = re.compile(r"^ep \d+ seed (\d+) .*?succ ([0-9.]+) exy ([0-9.]+)mm fallen (\d+) iou ([0-9.]+)(.*)\((\d+)s\)\s*$")
GATE = re.compile(r"gate verified (\d+) lost (\d+) retries (\d+) abort (\w+) done (\w+) release-corrected (\d+)/(\d+)"
                  r"(?: bad-release (\d+) replaced (\d+)/(\d+) blocked (\d+))?")
CONDS = ["A_policy", "C_anglelaod_inplace", "D_pre_release", "E_replace"]


def parse_log(path):
    out = {}
    for line in Path(path).read_text(errors="ignore").splitlines():
        m = EP.match(line)
        if not m:
            continue
        seed, succ = int(m.group(1)), float(m.group(2))
        r = {"succ": succ, "full": succ >= 0.999, "bricks": round(3 * succ), "exy": float(m.group(3)), "wall_s": int(m.group(7)),
             "iou": float(m.group(5))}
        g = GATE.search(m.group(6))
        if g:
            r.update(verified=int(g.group(1)), lost=int(g.group(2)), retries=int(g.group(3)), abort=g.group(4) == "True",
                     done=g.group(5) == "True", corrected=int(g.group(6)), releases=int(g.group(7)),
                     bad=int(g.group(8) or 0), replaced_ok=int(g.group(9) or 0), replaced=int(g.group(10) or 0))
        out[seed] = r
    return out


def runs(prefix):
    """Episodes of every run whose log starts with prefix.  A finished run's JSON wins over its log (a log can be
    garbled when two processes wrote it, which happened once for seed1002 on 2026-09-28)."""
    eps = {}
    for f in sorted(LOGS.glob(prefix + "*.log")):
        j = SIM / "outputs" / "final_test" / (f.stem + ".json")
        if j.exists():
            for e in json.load(open(j))["episodes"]:
                r = {"succ": e["m1_success_rate"], "full": bool(e["m1_all_success"]), "bricks": round(3 * e["m1_success_rate"]),
                     "iou": float(e["m8_voxel_iou"])}
                if "gate_retries" in e:
                    r.update(verified=e["gate_verified_grasps"], lost=e["gate_lost"], retries=e["gate_retries"],
                             corrected=e["release_corrected"], releases=len(e["release_events"]), bad=e["bad_releases"],
                             replaced_ok=e.get("replaced_ok", 0), replaced=e.get("replaced", 0))
                eps[e["seed"]] = r
        else:
            eps.update(parse_log(f))
    return eps


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def summarize(eps, seeds):
    rows = [eps[s] for s in seeds]
    n = len(rows)
    k = sum(r["full"] for r in rows)
    lo, hi = wilson(k, n)
    s = {"n": n, "full": k, "rate": k / n if n else 0.0, "ci": (lo, hi),
         "bricks": sum(r["bricks"] for r in rows) / n if n else 0.0,
         "iou": sum(r.get("iou", 0.0) for r in rows) / n if n else 0.0}
    if rows and "retries" in rows[0]:
        for key in ("verified", "lost", "retries", "corrected", "releases", "bad", "replaced_ok", "replaced"):
            s[key] = sum(r.get(key, 0) for r in rows)
    return s


def expert(path, seeds):
    o = {x["seed"]: x for x in json.load(open(path))}
    rows = [o[s] for s in seeds if s in o]
    k, n = sum(x["full"] for x in rows), len(rows)
    return {"n": n, "full": k, "rate": k / n if n else 0.0, "ci": wilson(k, n),
            "bricks": sum(round(3 * x["succ"]) for x in rows) / n if n else 0.0,
            "iou": sum(x.get("iou", 0.0) for x in rows) / n if n else 0.0}


def collect():
    res = {"test": {}, "noise": {}, "seeds": {}}
    unchanged = set(json.load(open(SIM / "outputs" / "final_test" / "unchanged_seeds.json")))
    res["reused_A"] = {}
    for pol in ("diffusion", "act"):
        eps = {c: runs(f"test_{pol}_{c}_") for c in CONDS}
        if pol == "diffusion":
            # Diffusion policy-only is reused from the Experiment-2 test run (same checkpoint, n_action_steps 10,
            # max 1800 steps, inference seed 70000+i) on the seeds whose layout the feasibility filter leaves unchanged
            old = json.load(open(SIM / "outputs" / "test_diffusion_v3_2p1_joint_image_clean_seed1000.json"))["episodes"]
            eps["A_policy"] = {e["seed"]: {"succ": e["m1_success_rate"], "full": bool(e["m1_all_success"]),
                                           "bricks": round(3 * e["m1_success_rate"]), "iou": float(e["m8_voxel_iou"])}
                               for e in old if e["seed"] in unchanged}
            res["reused_A"][pol] = True
        paired = [c for c in CONDS if c != "C_anglelaod_inplace"]     # C is the slowest; reported on its own seeds
        common = sorted(set.intersection(*(set(eps[c]) for c in paired)))
        res["seeds"][pol] = common
        res["test"][pol] = {c: summarize(eps[c], common) for c in paired}
        c_seeds = sorted(s for s in eps["C_anglelaod_inplace"] if s < 50050)
        res["test"][pol]["C_anglelaod_inplace"] = summarize(eps["C_anglelaod_inplace"], c_seeds)
        res["seeds"][pol + "_C"] = c_seeds
    # the expert baselines run on the union of the policies' paired seeds (CPU, all 50 finish)
    allseeds = sorted(set(res["seeds"]["diffusion"]) | set(res["seeds"]["act"]))
    for tag, f in (("expert", "expert_baseline_50000_50.json"), ("expert_gate", "expert_gate_replace_50000_50.json")):
        p = SIM / "outputs" / "gate_val40_v2" / f
        res["test"][tag] = {pol: expert(p, res["seeds"][pol]) for pol in ("diffusion", "act")} if p.exists() else None
    # pose-noise sensitivity on validation seeds: 0 mm = the finished val40 run of the same condition
    for pol, pref in (("diffusion", "val40_diffusion_E_noise"), ("act", "val20_act_E_noise")):
        base = json.load(open(SIM / "outputs" / "gate_val40_v2" / f"val40_{pol}_andcheck_replace.json"))["episodes"]
        base = {e["seed"]: {"succ": e["m1_success_rate"], "full": bool(e["m1_all_success"]),
                            "bricks": round(3 * e["m1_success_rate"]), "iou": float(e["m8_voxel_iou"])} for e in base}
        levels = {0: base}
        for mm in (2, 4):
            levels[mm] = runs(f"{pref}{mm}mm")
        # each noise level on the seeds it finished; 0 mm on the seeds of the 2 mm run (the longest noisy run)
        res["noise"][pol] = {mm: summarize(levels[mm], sorted(set(levels[mm]) & set(base))) for mm in (2, 4)}
        res["noise"][pol][0] = summarize(base, sorted(set(levels[2]) & set(base)))
    return res


if __name__ == "__main__":
    r = collect()
    for pol in ("diffusion", "act"):
        print(f"== {pol}: paired test seeds n={len(r['seeds'][pol])}")
        for c in CONDS:
            s = r["test"][pol][c]
            extra = {k: v for k, v in s.items() if k not in ("n", "full", "rate", "ci", "bricks")}
            print(f"  {c:22s} {s['full']:2d}/{s['n']} ({100*s['rate']:.0f}%, CI {100*s['ci'][0]:.0f}-{100*s['ci'][1]:.0f}) bricks {s['bricks']:.2f} {extra}")
        for tag in ("expert", "expert_gate"):
            if r["test"][tag]:
                s = r["test"][tag][pol]
                print(f"  {tag:22s} {s['full']:2d}/{s['n']} ({100*s['rate']:.0f}%) bricks {s['bricks']:.2f}")
        print(f"  noise (validation): " + ", ".join(f"{mm} mm {s['full']}/{s['n']}" for mm, s in r["noise"][pol].items()))
    json.dump(r, open(SIM / "outputs" / "final_test" / "paper_numbers.json", "w"), indent=1, default=list)


# ---------------------------------------------------------------------------------------------- multi-seed (2026-09-28)
NAME = {"A": "A_policy", "B": "C_anglelaod_inplace", "C": "D_pre_release", "D": "E_replace"}


def _old_policy_only(pol, seed, unchanged):
    p = SIM / "outputs" / f"test_{pol}_v3_2p1_joint_image_clean_seed{seed}.json"
    if not p.exists():
        return None
    return {e["seed"]: {"succ": e["m1_success_rate"], "full": bool(e["m1_all_success"]), "bricks": round(3 * e["m1_success_rate"]),
                        "iou": float(e["m8_voxel_iou"])}
            for e in json.load(open(p))["episodes"] if e["seed"] in unchanged}


def collect_seed(pol, seed):
    """Per-condition results of one training seed, paired on the seeds all four conditions finished."""
    unchanged = set(json.load(open(SIM / "outputs" / "final_test" / "unchanged_seeds.json")))
    if seed == 1000:
        eps = {k: runs(f"test_{pol}_{v}_") for k, v in NAME.items()}
        if pol == "diffusion":
            eps["A"] = _old_policy_only(pol, seed, unchanged)
    else:
        eps = {k: runs(f"s{seed}_test_{pol}_{v}") for k, v in NAME.items()}
        old = _old_policy_only(pol, seed, unchanged)
        if old is not None and not eps["A"]:
            eps["A"] = old
    # A, C, D are paired; B (condition without coordinates) only ran fully for seed 1000 -> its own finished seeds
    paired = ("A", "C", "D") if seed == 1000 else ("A", "D")      # extra seeds: C was dropped for time (2026-09-28)
    common = sorted(set.intersection(*(set(eps[k]) for k in paired)))
    res = {k: summarize(eps[k], [x for x in common if x in eps[k]] if k not in paired else common) for k in ("A", "C", "D")}
    b_seeds = sorted(set(eps["B"]) & (set(common) if seed == 1000 else set(eps["B"])))
    res["B"] = summarize(eps["B"], b_seeds)
    return {k: res[k] for k in NAME}, common


def collect_multi():
    out = {}
    for pol in ("diffusion", "act"):
        out[pol] = {}
        for seed in (1000, 1001, 1002):
            res, common = collect_seed(pol, seed)
            out[pol][seed] = {"n": len(common), "res": res}
        pooled = {}
        for k in NAME:
            full = sum(out[pol][s]["res"][k]["full"] for s in (1000, 1001, 1002))
            n = sum(out[pol][s]["res"][k]["n"] for s in (1000, 1001, 1002))
            rates = [out[pol][s]["res"][k]["rate"] for s in (1000, 1001, 1002) if out[pol][s]["res"][k]["n"]]
            pooled[k] = {"full": full, "n": n, "rate": full / n if n else 0.0, "ci": wilson(full, n),
                         "min": min(rates) if rates else 0.0, "max": max(rates) if rates else 0.0}
        out[pol]["pooled"] = pooled
    return out


def print_multi():
    m = collect_multi()
    for pol in ("diffusion", "act"):
        print(f"== {pol}")
        for seed in (1000, 1001, 1002):
            r = m[pol][seed]
            print(f"  seed{seed} n={r['n']}: " + "  ".join(f"{k} {v['full']}/{v['n']}" for k, v in r["res"].items()))
        print("  pooled: " + "  ".join(f"{k} {v['full']}/{v['n']} ({100*v['rate']:.0f}%, seeds {100*v['min']:.0f}-{100*v['max']:.0f}%)"
                                       for k, v in m[pol]["pooled"].items()))
    return m
