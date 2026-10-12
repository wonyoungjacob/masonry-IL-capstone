"""Concurrent read-only checkpoint evaluation; stop each pilot on missing vision."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import time

out = Path("outputs/midterm1_fix/camera_only")
logs = Path("logs/midterm1_fix/camera_only")
attempt = sys.argv[1] if len(sys.argv) > 1 else "initial"
if attempt != "initial":
    logs = logs / attempt
    logs.mkdir(exist_ok=False)
prefix = ["venv/bin/python", "-u", str(out / "strict_camera_only.py")]
jobs = [("consistency_test50", prefix + ["consistency", "--seed0", "50000", "--episodes", "50",
                                        "--out", str(out / "consistency_test50.json")])]
for policy in ("act", "diffusion"):
    for condition in ("policy_only", "pre", "prepost"):
        name = f"pilot_{policy}_{condition}_50000"
        jobs.append((name, prefix + ["rollout", "--policy", policy, "--condition", condition,
                     "--seed0", "50000", "--episodes", "1", "--out", str(out / f"{name}.json")]))
with (out / f"jobs_camera_only_{attempt}.txt").open("x") as f:
    for name, command in jobs:
        f.write(shlex.join(command) + " > " + str(logs / f"{name}.log") + " 2>&1\n")
env = {**os.environ, "MUJOCO_GL": "egl", "EVAL_THREADS": "1", "PYTHONDONTWRITEBYTECODE": "1",
       "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"}

def run(job):
    name, command = job
    started = time.time()
    print("START", name, flush=True)
    with (logs / f"{name}.log").open("x") as f:
        p = subprocess.run(command, stdout=f, stderr=subprocess.STDOUT, env=env)
    status = dict(name=name, returncode=p.returncode, elapsed_s=time.time() - started, command=command)
    with (logs / f"{name}_exit.json").open("x") as f:
        json.dump(status, f, indent=2)
    print("EXIT", name, p.returncode, flush=True)
    return status

with ThreadPoolExecutor(max_workers=7) as pool:
    results = list(pool.map(run, jobs))
with (out / f"job_status_{attempt}.json").open("x") as f:
    json.dump(results, f, indent=2)
