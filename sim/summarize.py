"""Summarise every outputs/eval_*.json as one table (blueprint 4.9: 3D IoU, E_h, E_f).

Usage:  python summarize.py [--csv results.csv]
"""
import argparse, json, re, statistics as st
from pathlib import Path

HERE = Path(__file__).resolve().parent


def rows():
    for j in sorted((HERE / "outputs").glob("eval_*.json")):
        name = j.stem[len("eval_"):]
        m = re.match(r"(act|diffusion|smolvla|pi0)_(.+?)_(mortarA|mortarB)(_kick)?$", name)
        if not m:
            continue
        policy, dataset, mortar, kick = m.group(1), m.group(2), m.group(3), bool(m.group(4))
        try:
            eps = json.load(open(j, encoding="utf-8"))["episodes"]
        except Exception:
            continue
        if not eps:
            continue
        clean = [e for e in eps if e["m7_fallen_count"] == 0]
        yield dict(policy=policy, dataset=dataset.replace("v2_2p1_joint_", "").replace("_clean", ""),
                   mortar=mortar, kick="yes" if kick else "no", n=len(eps),
                   all_ok=sum(1 for e in eps if e["m1_all_success"]),
                   fallen=sum(1 for e in eps if e["m7_fallen_count"] > 0),
                   iou=st.mean(e["bp_iou"] for e in eps),
                   iou_med=st.median(e["bp_iou"] for e in eps),
                   E_h=st.mean(e["bp_E_h_mm"] for e in eps),
                   E_f=st.mean(e["bp_E_f_mm"] for e in eps),
                   iou_ok=st.mean(e["bp_iou"] for e in clean) if clean else float("nan"),
                   E_h_ok=st.mean(e["bp_E_h_mm"] for e in clean) if clean else float("nan"),
                   E_f_ok=st.mean(e["bp_E_f_mm"] for e in clean) if clean else float("nan"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="")
    a = ap.parse_args()
    R = list(rows())
    if not R:
        print("no eval_*.json yet")
        return
    hdr = f"{'policy':10s} {'data':8s} {'mortar':7s} {'kick':4s} {'n':>3s} {'all_ok':>6s} {'fallen':>6s} " \
          f"{'IoU':>6s} {'IoU_med':>7s} {'E_h':>6s} {'E_f':>6s} | {'IoU*':>6s} {'E_h*':>6s} {'E_f*':>6s}"
    print(hdr); print("-" * len(hdr))
    for r in sorted(R, key=lambda r: (r["policy"], r["dataset"], r["mortar"], r["kick"])):
        print(f"{r['policy']:10s} {r['dataset']:8s} {r['mortar']:7s} {r['kick']:4s} {r['n']:3d} {r['all_ok']:6d} "
              f"{r['fallen']:6d} {r['iou']:6.3f} {r['iou_med']:7.3f} {r['E_h']:6.2f} {r['E_f']:6.2f} | "
              f"{r['iou_ok']:6.3f} {r['E_h_ok']:6.2f} {r['E_f_ok']:6.2f}")
    print("\n* = episodes with no fallen brick only.  E_h/E_f in mm.  all_ok = all three bricks within tolerance.")
    if a.csv:
        import csv
        with open(a.csv, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(R[0])); w.writeheader(); w.writerows(R)
        print("wrote", a.csv)


if __name__ == "__main__":
    main()
