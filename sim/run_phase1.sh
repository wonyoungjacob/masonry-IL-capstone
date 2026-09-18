#!/usr/bin/env bash
# Phase 1 of the blueprint (4.7 / 4.10): generate the demonstration datasets with the IK expert and train ACT.
#   datasets  : 2 conditions (dry, joint=A+B) x 2 obs sets (image, state) x 2 noise sets (clean, dart), 120 eps each
#   training  : ACT on dry/image/clean first (the blueprint's first policy), then the rest
# All four condition generators run in parallel (CPU); training uses the GPU.
set -euo pipefail
cd "$(dirname "$0")"
source venv/bin/activate
export MUJOCO_GL=egl
EPS=${EPS:-120}          # 100 train + 20 val per the blueprint
POS=${POS:-0.005}        # +-5 mm supply randomisation (4.7.3)
YAW=${YAW:-10}           # +-10 deg
mkdir -p data outputs logs

gen () {  # gen <mortar> <obs> <noise> <name>
  python collect.py --task 2p1 --episodes "$EPS" --mortar "$1" --obs-set "$2" --noise "$3" \
    --pos-rand "$POS" --yaw-rand "$YAW" --root "data/$4" --repo-id "local/$4" > "logs/collect_$4.log" 2>&1 &
}
# same seeds (default seed0=0) -> identical episodes across obs sets, so image vs state is a fair comparison
gen dry     image 0.0   2p1_dry_image_clean
gen dry     state 0.0   2p1_dry_state_clean
gen dry     image 0.003 2p1_dry_image_dart
gen mortarB image 0.0   2p1_joint_image_clean
wait
tail -n 1 logs/collect_*.log

train () {  # train <dataset> <policy> <steps>
  lerobot-train --dataset.repo_id="local/$1" --dataset.root="data/$1" --policy.type="$2" --policy.device=cuda \
    --policy.push_to_hub=false --steps="$3" --batch_size=32 --num_workers=8 --save_freq=10000 --log_freq=200 \
    --output_dir="outputs/$2_$1" --job_name="$2_$1" --wandb.enable=false 2>&1 | tee "logs/train_$2_$1.log"
}
train 2p1_dry_image_clean act 40000
train 2p1_dry_state_clean act 40000
train 2p1_dry_image_dart  act 40000
train 2p1_joint_image_clean act 40000
train 2p1_dry_image_clean diffusion 60000

# evaluation on 100 unseen initial states per the blueprint (4.9.5)
for d in 2p1_dry_image_clean 2p1_dry_state_clean 2p1_dry_image_dart; do
  python eval_policy.py --task 2p1 --mortar dry --ckpt "outputs/act_$d/checkpoints/last/pretrained_model" \
    --episodes 100 --seed0 10000 --pos-rand "$POS" --yaw-rand "$YAW" --out "outputs/eval_act_$d.json" | tail -12
done
python eval_policy.py --task 2p1 --mortar mortarB --ckpt outputs/act_2p1_joint_image_clean/checkpoints/last/pretrained_model \
  --episodes 100 --seed0 10000 --pos-rand "$POS" --yaw-rand "$YAW" --out outputs/eval_act_2p1_joint_image_clean.json | tail -12
