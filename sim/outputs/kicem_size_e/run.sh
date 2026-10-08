#!/bin/bash
# 2026-10-07: size tolerance on base system E (policy + gates + one re-place) whose gate plans from the NOMINAL size
# (--gate-nominal-plan).  Layouts 62000-62029; the nominal level is outputs/kicem_nominal/diffusion_E_* (same flags, s=0).
cd /home/won/masonry/sim
export MUJOCO_GL=egl HF_HUB_OFFLINE=1 EVAL_THREADS=1
CK=outputs/diffusion_v3_2p1_joint_image_clean_seed1000/checkpoints/last/pretrained_model
COMMON="--task 2p1 --mortar mortarB --pos-rand .03 --yaw-rand 60 --valid-supply --feasible-supply --n-action-steps 10 --disturb 0 --inference-seed 70000 --seed0 62000"
E="--grasp-gate --gate-recover reguide --release-gate --gate-force --gate-retries 0 --gate-replace --gate-nominal-plan"
for lv in "s15 0.015" "s30 0.03" "s60 0.06"; do set -- $lv
  for k in 0 1 2; do
    seeds=$(seq $((62000+k)) 3 62029 | paste -sd,)
    venv/bin/python -u eval_policy.py $COMMON --ckpt $CK $E --size-rand $2 --seed-list $seeds \
      --out outputs/kicem_size_e/diffusion_${1}_$k.json > logs/kicem_size_e/diffusion_${1}_$k.log 2>&1 &
    sleep 2
  done
done
wait
echo ALLDONE
