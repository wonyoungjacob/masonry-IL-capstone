#!/usr/bin/env bash
# The combination the 2026-09-19 results point at: more recovery episodes AND the overhead camera.
#
#   plus2  (2 cameras, 41 recovery demos) -> collapses 10 -> 3 without a kick, but placement drifts to 6.3 mm
#   plustop(3 cameras, 26 recovery demos) -> placement back to 3.9 mm, IoU back to the clean level (0.848)
#   plus2top = both: clean 120 + 120 kicked episodes, front + wrist + top
set -uo pipefail
cd "$(dirname "$0")"
source venv/bin/activate
export MUJOCO_GL=egl
POS=${POS:-0.005}; YAW=${YAW:-10}; EVAL_EPS=${EVAL_EPS:-100}; SEED0=${SEED0:-10000}
STALL_S=${STALL_S:-900}; WORKERS=${WORKERS:-4}
stamp () { date "+%H:%M:%S"; }
D=v2_2p1_joint_image_plus2top
while pgrep -f "[c]ollect.py.*$D" > /dev/null; do sleep 30; done
[ -f "data/$D/meta/info.json" ] || { echo "[$(stamp)] $D missing, abort"; exit 1; }

train () {
  local ds=$1 pol=$2 steps=$3 tag=$4; shift 4
  local out="outputs/${tag}" log="logs/train_${tag}.log"
  grep -q "End of training" "$log" 2>/dev/null && { echo "[$(stamp)] TRAIN ${tag} already done"; return 0; }
  local attempt
  for attempt in 1 2 3; do
    local -a args
    if [ "$attempt" -gt 1 ] && [ -f "$out/checkpoints/last/pretrained_model/train_config.json" ]; then
      echo "[$(stamp)] TRAIN ${tag} resume (attempt $attempt)"
      args=(--config_path="$out/checkpoints/last/pretrained_model/train_config.json" --resume=true)
    else
      echo "[$(stamp)] TRAIN ${tag} start (${steps} steps, attempt $attempt)"
      args=(--dataset.repo_id="local/$ds" --dataset.root="data/$ds" --policy.device=cuda --policy.push_to_hub=false
            --steps="$steps" --num_workers="$WORKERS" --save_freq=20000 --log_freq=200
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

train $D diffusion 60000 diffusion_$D --policy.type=diffusion --batch_size=32
evaluate diffusion_$D mortarB 0
evaluate diffusion_$D mortarB 1.0
train $D act 40000 act_$D --policy.type=act --batch_size=32
evaluate act_$D mortarB 0
evaluate act_$D mortarB 1.0
wait
echo "[$(stamp)] ALL DONE (v9)"
python summarize.py --csv outputs/results.csv
