"""Midterm-1 slide 8 (2026-10-12): the gate pose-noise sweep (sigma 2 / 4 mm) on the TEST batch 50000-50049, so it pairs with
the condition-D test results (Diffusion 30/40, ACT 26/48) instead of the 27/20-episode validation subset.

    cd sim
    venv/bin/python tools/noise_test_jobs.py > outputs/midterm1_fix/jobs_noise.txt
    MUJOCO_GL=egl EVAL_THREADS=1 nohup xargs -P 8 -I{} bash -c '{}' < outputs/midterm1_fix/jobs_noise.txt > logs/midterm1_fix/xargs.log 2>&1 &

Source of the base commands, in order:
 1. the condition-D (E_replace) test commands of the seed1000 models printed by outputs/final_test/jobs.py, copied verbatim
    (same chunking -> same inference seeds), only --gate-pose-noise / --out / log changed;
 2. if that script is missing or prints no such command: the same flags as tools/rq4_jobs.py (chunks 50000 and 50025).
Which source was used is printed to stderr.
"""
import re, subprocess, sys
from pathlib import Path

SIM = Path(__file__).resolve().parents[1]
CK = "outputs/{p}_v3_2p1_joint_image_clean_seed1000/checkpoints/last/pretrained_model"
BASE = ("venv/bin/python -u eval_policy.py --task 2p1 --mortar mortarB --size-rand 0 --pos-rand .03 --yaw-rand 60 "
        "--valid-supply --feasible-supply --n-action-steps 10 --disturb 0 --ckpt {ck} --episodes 25 --seed0 {s0} "
        "--grasp-gate --gate-recover reguide --release-gate --gate-force --gate-retries 0 --gate-replace")
SIGMAS = ((0.002, 2), (0.004, 4))


def from_final_test():
    js = SIM / "outputs" / "final_test" / "jobs.py"
    if not js.exists():
        return []
    try:
        txt = subprocess.run([sys.executable, str(js)], cwd=str(SIM), capture_output=True, text=True, timeout=60).stdout
    except Exception:
        return []
    out = []
    for ln in txt.splitlines():
        ln = ln.strip()
        if "eval_policy.py" not in ln or "seed1000" not in ln or "--gate-replace" not in ln or "--gate-pose-noise" in ln:
            continue
        if "50000" not in ln and "50025" not in ln and "--seed-list 500" not in ln:
            continue
        if "--gate-pose-source camera" in ln or "--disturb 0 " not in ln + " ":
            continue
        cmd = ln.split(" > ")[0]
        pol = "diffusion" if "diffusion_v3" in cmd else ("act" if "act_v3" in cmd else None)
        m = re.search(r"--seed0 (\d+)", cmd)
        if pol is None or m is None:
            continue
        out.append((pol, m.group(1), re.sub(r"\s--out\s+\S+", "", cmd)))
    return out


base = from_final_test()
src = "outputs/final_test/jobs.py"
if not base:
    base = [(p, str(s0), BASE.format(ck=CK.format(p=p), s0=s0)) for p in ("diffusion", "act") for s0 in (50000, 50025)]
    src = "fallback (tools/rq4_jobs.py flags)"
jobs = []
for pol, s0, cmd in base:
    for sig, mm in SIGMAS:
        tag = f"test_{pol}_s1000_D_noise{mm}mm_{s0}"
        jobs.append(f"{cmd} --gate-pose-noise {sig} --out outputs/midterm1_fix/{tag}.json > logs/midterm1_fix/{tag}.log 2>&1")
print("\n".join(jobs))
print(f"# {len(jobs)} jobs from {src}", file=sys.stderr)
