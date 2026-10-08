#!/usr/bin/env bash
# Final consolidated queue (replaces run_v4/v5/v6 from 2026-09-19 01:20), ordered by what each run still answers:
#
#   1. act plus        - does recovery data help when it is ADDED to the clean set instead of replacing part of it?
#                        (clean 120 identical seeds + 60 always-kicked episodes)            <- the open question
#   2. act state       - privileged coordinate baseline (blueprint 4.6.5)
#   3. diffusion plus  - same question for the stronger policy
#   4. diffusion robust- completes the dose-response curve 0 / 17 / 62 / 95 % for Diffusion
#   5. smolvla clean, VLM unfrozen, 40k - the recommended recipe (frozen VLM, 20k) placed all three bricks in
#                        only 2 of 100 episodes, so the four-policy comparison needs a fair second attempt
#   6. smolvla mix2, standard recipe - last, lowest value while the recipe is unresolved
set -uo pipefail
cd "$(dirname "$0")"
source venv/bin/activate
export MUJOCO_GL=egl
POS=${POS:-0.005}; YAW=${YAW:-10}; EVAL_EPS=${EVAL_EPS:-100}; SEED0=${SEED0:-10000}
STALL_S=${STALL_S:-900}; WORKERS=${WORKERS:-4}
stamp () { date "+%H:%M:%S"; }
P=v2_2p1_joint_image_plus
while pgrep -f "[c]ollect.py.*$P" > /dev/null; do sleep 30; done

train () {
  local ds=$1 pol=$2 steps=$3 tag=$4; shift 4
  local out="outputs/${tag}" log="logs/train_${tag}.log"
  grep -q "End of training" "$log" 2>/dev/null && { echo "[$(stamp)] TRAIN ${tag} already done"; return 0; }
  [ -f "data/$ds/meta/info.json" ] || { echo "[$(stamp)] TRAIN ${tag} skipped (no data/$ds)"; return 0; }
  local attempt
  for attempt in 1 2 3; do
    local -a args
    if [ "$attempt" -gt 1 ] && [ -f "$out/checkpoints/last/pretrained_model/train_config.json" ]; then
      echo "[$(stamp)] TRAIN ${tag} resume (attempt $attempt)"
      args=(--config_path="$out/checkpoints/last/pretrained_model/train_config.json" --resume=true)
    else
      echo "[$(stamp)] TRAIN ${tag} start (${steps} steps, attempt $attempt)"
      args=(--dataset.repo_id="local/$ds" --dataset.root="data/$ds" --policy.device=cuda --policy.push_to_hub=false
            --steps="$steps" --num_workers="$WORKERS" --save_freq=5000 --log_freq=200
            --output_dir="$out" --job_name="$tag" --wandb.enable=false "$@")
    fi
    lerobot-train "${args[@]}" >> "$log" 2>&1 &
    local pid=$!
    while kill -0 "$pid" 2>/dev/null; do
      sleep 60
      local age=$(( $(date +%s) - $(stat -c %Y "$log" 2>/dev/null || echo 0) ))
      if [ "$age" -gt "$STALL_S" ]; then
        echo "[$(stamp)] TRAIN ${tag} STALLED ${age}s -> kill"; kill -9 "$pid" 2>/dev/null; sleep 5; break
      fi
    done
    wait "$pid" 2>/dev/null
    grep -q "End of training" "$log" 2>/dev/null && { echo "[$(stamp)] TRAIN ${tag} done"; return 0; }
    sleep 10
  done
  echo "[$(stamp)] TRAIN ${tag} FAILED"; return 1
}
evaluate () {
  local run=$1 mortar=$2 dist=$3; shift 3
  local tag="$mortar"; [ "$dist" != "0" ] && tag="${mortar}_kick"
  [ -d "outputs/$run/checkpoints/last" ] || { echo "[$(stamp)] EVAL ${run} @ ${tag} no checkpoint"; return 0; }
  [ -f "outputs/eval_${run}_${tag}.json" ] && { echo "[$(stamp)] EVAL ${run} @ ${tag} already done"; return 0; }
  echo "[$(stamp)] EVAL ${run} @ ${tag} start (${EVAL_EPS} episodes, background)"
  ( python eval_policy.py --task 2p1 --mortar "$mortar" --ckpt "outputs/$run/checkpoints/last/pretrained_model" \
      --episodes "$EVAL_EPS" --seed0 "$SEED0" --pos-rand "$POS" --yaw-rand "$YAW" --size-rand 0 --disturb "$dist" \
      --out "outputs/eval_${run}_${tag}.json" "$@" > "logs/eval_${run}_${tag}.log" 2>&1 \
    && echo "[$(stamp)] EVAL ${run} @ ${tag} done" || echo "[$(stamp)] EVAL ${run} @ ${tag} FAILED" ) &
}
SMOL_MAP='{"observation.images.front":"observation.images.camera1","observation.images.wrist":"observation.images.camera2"}'
C=v2_2p1_joint_image_clean; R=v2_2p1_joint_image_robust; M2=v2_2p1_joint_image_mix2; S=v2_2p1_joint_state_clean

train $P act 40000 act_$P --policy.type=act --batch_size=32
evaluate act_$P mortarB 0
evaluate act_$P mortarB 1.0

train $S act 40000 act_$S --policy.type=act --batch_size=32
evaluate act_$S mortarB 0

train $P diffusion 60000 diffusion_$P --policy.type=diffusion --batch_size=32
evaluate diffusion_$P mortarB 0
evaluate diffusion_$P mortarB 1.0

train $R diffusion 60000 diffusion_$R --policy.type=diffusion --batch_size=32
evaluate diffusion_$R mortarB 0

train $C smolvla 40000 smolvla_full_$C --policy.path=lerobot/smolvla_base --policy.empty_cameras=1 \
  --policy.train_expert_only=false --policy.freeze_vision_encoder=true --rename_map="$SMOL_MAP" --batch_size=32
evaluate smolvla_full_$C mortarB 0 --rename-map "$SMOL_MAP"
evaluate smolvla_full_$C mortarB 1.0 --rename-map "$SMOL_MAP"

train $M2 smolvla 20000 smolvla_$M2 --policy.path=lerobot/smolvla_base --policy.empty_cameras=1 \
  --rename_map="$SMOL_MAP" --batch_size=32
evaluate smolvla_$M2 mortarB 0 --rename-map "$SMOL_MAP"

wait
echo "[$(stamp)] ALL DONE (v7)"
python summarize.py --csv outputs/results.csv
