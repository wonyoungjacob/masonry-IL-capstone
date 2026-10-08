#!/usr/bin/env bash
# Scene spec v2 pipeline (mortarB = contact layer A + bond B):
#   datasets : clean expert (image), robust = disturbance + recovery demos (image), clean state baseline
#   training : ACT / Diffusion / SmolVLA on clean and on robust (same seeds -> same initial states), ACT on state
#   eval     : 100 unseen initial states each (seed0 10000), mortarB; the clean ACT also at mortarA (bond off)
# pi0 needs the gated tokenizer google/paligemma-3b-pt-224 (hf auth login + accept licence) -> PI0=1
set -euo pipefail
cd "$(dirname "$0")"
source venv/bin/activate
export MUJOCO_GL=egl
POS=${POS:-0.005}; YAW=${YAW:-10}; EPS=${EPS:-120}; DISTURB=${DISTURB:-0.4}
EVAL_EPS=${EVAL_EPS:-100}; SEED0=${SEED0:-10000}; PI0=${PI0:-0}
mkdir -p data outputs logs
stamp () { date "+%H:%M:%S"; }

gen () {  # gen <name> <obs-set> <disturb> [extra collect args]  (background)
  local name=$1 obs=$2 dist=$3; shift 3
  if [ -d "data/$name" ]; then echo "[$(stamp)] DATA $name exists, skipping"; return; fi
  echo "[$(stamp)] DATA $name start"
  ( OMP_NUM_THREADS=2 python collect.py --task 2p1 --spec v2 --episodes "$EPS" --mortar mortarB --obs-set "$obs" \
      --disturb "$dist" --pos-rand "$POS" --yaw-rand "$YAW" --root "data/$name" --repo-id "local/$name" "$@" \
      > "logs/collect_$name.log" 2>&1 && echo "[$(stamp)] DATA $name done: $(grep -o 'kept [0-9]*/[0-9]*' logs/collect_$name.log)" \
      || echo "[$(stamp)] DATA $name FAILED" ) &
}
gen v2_2p1_joint_image_clean  image 0.0
gen v2_2p1_joint_image_robust image "$DISTURB"
gen v2_2p1_joint_state_clean  state 0.0
wait

train () {  # train <dataset> <policy> <steps> [extra lerobot-train args...]
  local ds=$1 pol=$2 steps=$3; shift 3
  if [ -d "outputs/${pol}_${ds}/checkpoints/last" ]; then echo "[$(stamp)] TRAIN ${pol}_${ds} exists, skipping"; return; fi
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
C=v2_2p1_joint_image_clean; R=v2_2p1_joint_image_robust; S=v2_2p1_joint_state_clean

train $C act 40000 --policy.type=act --batch_size=32
evaluate act_$C mortarB
evaluate act_$C mortarA
train $R act 40000 --policy.type=act --batch_size=32
evaluate act_$R mortarB
train $C diffusion 60000 --policy.type=diffusion --batch_size=32
evaluate diffusion_$C mortarB
train $R diffusion 60000 --policy.type=diffusion --batch_size=32
evaluate diffusion_$R mortarB
train $C smolvla 20000 --policy.path=lerobot/smolvla_base --policy.empty_cameras=1 --rename_map="$SMOL_MAP" --batch_size=32
evaluate smolvla_$C mortarB --rename-map "$SMOL_MAP"
train $R smolvla 20000 --policy.path=lerobot/smolvla_base --policy.empty_cameras=1 --rename_map="$SMOL_MAP" --batch_size=32
evaluate smolvla_$R mortarB --rename-map "$SMOL_MAP"
if [ "$PI0" = "1" ]; then
  train $C pi0 20000 --policy.path=lerobot/pi0_base --policy.empty_cameras=1 --policy.train_expert_only=true \
    --policy.dtype=bfloat16 --rename_map="$PI0_MAP" --batch_size=16
  evaluate pi0_$C mortarB --rename-map "$PI0_MAP"
  train $R pi0 20000 --policy.path=lerobot/pi0_base --policy.empty_cameras=1 --policy.train_expert_only=true \
    --policy.dtype=bfloat16 --rename_map="$PI0_MAP" --batch_size=16
  evaluate pi0_$R mortarB --rename-map "$PI0_MAP"
fi
train $S act 40000 --policy.type=act --batch_size=32
evaluate act_$S mortarB
wait
echo "[$(stamp)] ALL DONE"
for j in outputs/eval_*v2_*.json; do
  python - "$j" <<'EOF'
import json, sys; d = json.load(open(sys.argv[1])); eps = d["episodes"]
bp = {k: sum(e[k] for e in eps) / len(eps) for k in ("bp_iou", "bp_E_h_mm", "bp_E_f_mm") if k in eps[0]}
fallen = sum(1 for e in eps if e["m7_fallen_count"] > 0)
print(f"{sys.argv[1]}: n={len(eps)} fallen_eps={fallen} " + " ".join(f"{k}={v:.3f}" for k, v in bp.items()))
EOF
done
