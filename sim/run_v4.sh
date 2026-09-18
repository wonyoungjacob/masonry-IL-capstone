#!/usr/bin/env bash
# Runs after run_v3.sh: the corrected recovery set (mix2) and its comparisons.
#
# Why mix2: the first "mix" set degraded ACT badly (all_ok 63 -> 21 without a kick).  Two design faults:
#   1. --disturb was rolled at each of the 2*n_bricks opportunities, so 0.15 meant 62 % of episodes, not 15 %.
#      mix2 uses --per-episode-kick: exactly P(episode) = 0.3, one kick.
#   2. after a kick the arm froze for 12 steps and those frames were recorded as a "hold" action, teaching the
#      policy to stop mid-episode.  mix2 uses --kick-hold 0: the brick slides while the arm keeps moving.
set -uo pipefail
cd "$(dirname "$0")"
source venv/bin/activate
export MUJOCO_GL=egl
POS=${POS:-0.005}; YAW=${YAW:-10}; EVAL_EPS=${EVAL_EPS:-100}; SEED0=${SEED0:-10000}
STALL_S=${STALL_S:-600}; WORKERS=${WORKERS:-4}
stamp () { date "+%H:%M:%S"; }
while pgrep -f "[b]ash run_v3.sh" > /dev/null; do sleep 60; done
echo "[$(stamp)] run_v3.sh finished -> run_v4"
M2=v2_2p1_joint_image_mix2
while pgrep -f "[c]ollect.py.*$M2" > /dev/null; do sleep 30; done
[ -f "data/$M2/meta/info.json" ] || { echo "[$(stamp)] $M2 missing, abort"; exit 1; }

train () {
  local ds=$1 pol=$2 steps=$3; shift 3
  local out="outputs/${pol}_${ds}" log="logs/train_${pol}_${ds}.log"
  grep -q "End of training" "$log" 2>/dev/null && { echo "[$(stamp)] TRAIN ${pol}_${ds} already done"; return 0; }
  local attempt
  for attempt in 1 2 3; do
    local -a args
    if [ "$attempt" -gt 1 ] && [ -f "$out/checkpoints/last/pretrained_model/train_config.json" ]; then
      echo "[$(stamp)] TRAIN ${pol}_${ds} resume (attempt $attempt)"
      args=(--config_path="$out/checkpoints/last/pretrained_model/train_config.json" --resume=true)
    else
      echo "[$(stamp)] TRAIN ${pol}_${ds} start (${steps} steps, attempt $attempt)"
      args=(--dataset.repo_id="local/$ds" --dataset.root="data/$ds" --policy.device=cuda --policy.push_to_hub=false
            --steps="$steps" --num_workers="$WORKERS" --save_freq=5000 --log_freq=200
            --output_dir="$out" --job_name="${pol}_${ds}" --wandb.enable=false "$@")
    fi
    lerobot-train "${args[@]}" >> "$log" 2>&1 &
    local pid=$!
    while kill -0 "$pid" 2>/dev/null; do
      sleep 60
      local age=$(( $(date +%s) - $(stat -c %Y "$log" 2>/dev/null || echo 0) ))
      if [ "$age" -gt "$STALL_S" ]; then
        echo "[$(stamp)] TRAIN ${pol}_${ds} STALLED ${age}s -> kill"; kill -9 "$pid" 2>/dev/null; sleep 5; break
      fi
    done
    wait "$pid" 2>/dev/null
    grep -q "End of training" "$log" 2>/dev/null && { echo "[$(stamp)] TRAIN ${pol}_${ds} done"; return 0; }
    sleep 10
  done
  echo "[$(stamp)] TRAIN ${pol}_${ds} FAILED"; return 1
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

train $M2 act 40000 --policy.type=act --batch_size=32
evaluate act_$M2 mortarB 0
evaluate act_$M2 mortarB 1.0
evaluate act_$M2 mortarA 0

train $M2 diffusion 60000 --policy.type=diffusion --batch_size=32
evaluate diffusion_$M2 mortarB 0
evaluate diffusion_$M2 mortarB 1.0

train $M2 smolvla 20000 --policy.path=lerobot/smolvla_base --policy.empty_cameras=1 --rename_map="$SMOL_MAP" --batch_size=32
evaluate smolvla_$M2 mortarB 0 --rename-map "$SMOL_MAP"
evaluate smolvla_$M2 mortarB 1.0 --rename-map "$SMOL_MAP"

wait
echo "[$(stamp)] ALL DONE (v4)"
python summarize.py --csv outputs/results.csv
