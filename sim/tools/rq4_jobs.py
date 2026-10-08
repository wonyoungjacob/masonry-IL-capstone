"""RQ4 job list (2026-10-08): the paper's condition D (= jobs.py 'E_replace': G1 angle AND load, reguide, G2, G3) with the
gate reading the scene's own top camera instead of the simulator pose.  Same checkpoints, same test seeds, same flags as
outputs/final_test/jobs.py, plus --gate-pose-source camera.  One shell command per line; run on the Ubuntu PC from sim/:

    python tools/rq4_jobs.py > outputs/rq4/jobs.txt
    mkdir -p logs/rq4 outputs/rq4
    MUJOCO_GL=egl EVAL_THREADS=1 xargs -P 8 -I{} bash -c '{}' < outputs/rq4/jobs.txt

Before the policy runs, the CPU-only check (expert + gates, sim vs camera; spawn accuracy) takes ~15 min:
    python tools/perception_accuracy.py --spawn 40000:40 --episodes 40000:40 50000:50 --out outputs/rq4/perception_accuracy.json
Compare with outputs/final_test/test_{policy}_E_replace_*.json (oracle) and val40_{policy}_E_noise{1,2,4}mm.json (noise sweep):
the camera result should land where the noise curve predicts for the measured estimator error.
"""
import sys

CK = "outputs/{p}_v3_2p1_joint_image_clean_seed{seed}/checkpoints/last/pretrained_model"
BASE = ("venv/bin/python -u eval_policy.py --task 2p1 --mortar mortarB --size-rand 0 --pos-rand .03 --yaw-rand 60 "
        "--valid-supply --feasible-supply --n-action-steps 10 --disturb 0 --ckpt {ck} --episodes {n} --seed0 {s0} --out {out}")
D = "--grasp-gate --gate-recover reguide --release-gate --gate-force --gate-retries 0 --gate-replace"
jobs = []
for pol in ("diffusion", "act"):
    for seed in (1000, 1001, 1002):
        for k in range(2):                                   # test seeds 50000-50049 in 2 chunks of 25 (paper: 50 layouts)
            s0 = 50000 + 25 * k
            out = f"outputs/rq4/test_{pol}_s{seed}_D_camera_{s0}.json"
            cmd = BASE.format(ck=CK.format(p=pol, seed=seed), n=25, s0=s0, out=out) + " " + D + " --gate-pose-source camera"
            jobs.append(f"{cmd} > logs/rq4/test_{pol}_s{seed}_D_camera_{s0}.log 2>&1")
    # validation batch: the noise sweep (val40_{pol}_E_noise*) was measured on 40000-40039 with seed1000; same here
    out = f"outputs/rq4/val40_{pol}_s1000_D_camera.json"
    cmd = BASE.format(ck=CK.format(p=pol, seed=1000), n=40, s0=40000, out=out) + " " + D + " --gate-pose-source camera"
    jobs.append(f"{cmd} > logs/rq4/val40_{pol}_s1000_D_camera.log 2>&1")
print("\n".join(jobs))
print(f"# {len(jobs)} jobs", file=sys.stderr)
