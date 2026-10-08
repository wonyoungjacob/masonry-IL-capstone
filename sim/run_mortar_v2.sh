#!/usr/bin/env bash
# Mortar (A+B = mortarB) condition: train the comparison policies on the same demonstrations (blueprint 4.6.5)
# and evaluate each on 100 unseen initial states (4.9.5).  Datasets are generated beforehand with collect.py:
#   data/<DS>_joint_image_clean (120), data/<DS>_joint_state_clean (120), data/<DS>_joint_image_dart (~118)   DS=2p1 | v2_2p1
# Training runs sequentially on the GPU; each evaluation starts in the background as soon as its policy is done,
# so the next training overlaps with the previous evaluation.
# pi0 needs the gated tokenizer google/paligemma-3b-pt-224 (hf auth login + accept licence) -> run with PI0=1.
set -euo pipefail
cd "$(dirname "$0")"
source venv/bin/activate
export MUJOCO_GL=egl
POS=${POS:-0.005}; YAW=${YAW:-10}; EVAL_EPS=${EVAL_EPS:-100}; SEED0=${SEED0:-10000}
PI0=${PI0:-0}
DS=${DS:-2p1}          # dataset name prefix: "2p1" = scene spec v1 datasets, "v2_2p1" = spec v2 (see brick_sim/scene.py)
mkdir -p outputs logs
stamp () { date "+%H:%M:%S"; }

train () {  # train <dataset> <policy> <steps> [extra lerobot-train args...]
  local ds=$1 pol=$2 steps=$3; shift 3
  echo "[$(stamp)] TRAIN ${pol}_${ds} start (${steps} steps)"
  lerobot-train --dataset.repo_id="local/$ds" --dataset.root="data/$ds" --policy.device=cuda \
    --policy.push_to_hub=false --steps="$steps" --num_workers=8 --save_freq=10000 --log_freq=200 \
    --output_dir="outputs/${pol}_${ds}" --job_name="${pol}_${ds}" --wandb.enable=false "$@" \
    > "logs/train_${pol}_${ds}.log" 2>&1
  echo "[$(stamp)] TRAIN ${pol}_${ds} done"
}

evaluate () {  # evaluate <run name> <mortar> [extra eval_policy.py args...]  (background)
  local run=$1 mortar=$2; shift 2
  echo "[$(stamp)] EVAL ${run} @ ${mortar} start (${EVAL_EPS} episodes, background)"
  ( python eval_policy.py --task 2p1 --mortar "$mortar" --ckpt "outputs/$run/checkpoints/last/pretrained_model" \
      --episodes "$EVAL_EPS" --seed0 "$SEED0" --pos-rand "$POS" --yaw-rand "$YAW" --size-rand 0 \
      --out "outputs/eval_${run}_${mortar}.json" "$@" > "logs/eval_${run}_${mortar}.log" 2>&1 \
    && echo "[$(stamp)] EVAL ${run} @ ${mortar} done" || echo "[$(stamp)] EVAL ${run} @ ${mortar} FAILED" ) &
}

SMOL_MAP='{"observation.images.front":"observation.images.camera1","observation.images.wrist":"observation.images.camera2"}'
PI0_MAP='{"observation.images.front":"observation.images.base_0_rgb","observation.images.wrist":"observation.images.left_wrist_0_rgb"}'

# 1) the four-policy comparison on the same data (image obs, clean expert)
train ${DS}_joint_image_clean act 40000 --policy.type=act --batch_size=32
evaluate act_${DS}_joint_image_clean mortarB
evaluate act_${DS}_joint_image_clean mortarA          # 4.8.4: same policy, bond (B) switched off

train ${DS}_joint_image_clean diffusion 60000 --policy.type=diffusion --batch_size=32
evaluate diffusion_${DS}_joint_image_clean mortarB

train ${DS}_joint_image_clean smolvla 20000 --policy.path=lerobot/smolvla_base --policy.empty_cameras=1 \
  --rename_map="$SMOL_MAP" --batch_size=32
evaluate smolvla_${DS}_joint_image_clean mortarB --rename-map "$SMOL_MAP"

if [ "$PI0" = "1" ]; then
  train ${DS}_joint_image_clean pi0 20000 --policy.path=lerobot/pi0_base --policy.empty_cameras=1 \
    --policy.train_expert_only=true --policy.dtype=bfloat16 --rename_map="$PI0_MAP" --batch_size=16
  evaluate pi0_${DS}_joint_image_clean mortarB --rename-map "$PI0_MAP"
fi

# 2) ablations with ACT: privileged state input, and DART noise-injected demonstrations
train ${DS}_joint_state_clean act 40000 --policy.type=act --batch_size=32
evaluate act_${DS}_joint_state_clean mortarB
train ${DS}_joint_image_dart act 40000 --policy.type=act --batch_size=32
evaluate act_${DS}_joint_image_dart mortarB

wait
echo "[$(stamp)] ALL DONE"
for j in outputs/eval_*.json; do
  python - "$j" <<'EOF'
import json, sys; d = json.load(open(sys.argv[1])); m = d["mean"]; eps = d["episodes"]
bp = {k: sum(e[k] for e in eps) / len(eps) for k in ("bp_iou", "bp_E_h_mm", "bp_E_f_mm") if k in eps[0]}
print(f"{sys.argv[1]}: n={len(eps)} success={m['m1_success_rate']:.2f} fallen={m['m7_fallen_count']:.2f} " +
      " ".join(f"{k}={v:.3f}" for k, v in bp.items()))
EOF
done
