#!/bin/bash
# resume: remaining layouts of each level (rest.txt), same flags as run.sh; nominal level included (s=0).
cd /home/won/masonry/sim
export MUJOCO_GL=egl HF_HUB_OFFLINE=1 EVAL_THREADS=1
CK=outputs/diffusion_v3_2p1_joint_image_clean_seed1000/checkpoints/last/pretrained_model
COMMON="--task 2p1 --mortar mortarB --pos-rand .03 --yaw-rand 60 --valid-supply --feasible-supply --n-action-steps 10 --disturb 0 --inference-seed 70000 --seed0 62000"
E="--grasp-gate --gate-recover reguide --release-gate --gate-force --gate-retries 0 --gate-replace --gate-nominal-plan"
while read tag s k seeds; do
  venv/bin/python -u eval_policy.py $COMMON --ckpt $CK $E --size-rand $s --seed-list $seeds \
    --out outputs/kicem_size_e/diffusion_${tag}_$k.json > logs/kicem_size_e/diffusion_${tag}_$k.log 2>&1 &
  sleep 1
done < outputs/kicem_size_e/rest.txt
wait
echo ALLDONE
