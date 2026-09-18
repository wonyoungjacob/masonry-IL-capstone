#!/usr/bin/env bash
# Follow-up to run_v2.sh (waits for it to finish):
#   - ACT and Diffusion on the MIX set (mostly clean + ~15 % episodes with one kick and the expert's recovery)
#   - robustness evaluation: every ACT / Diffusion policy (clean / robust / mix) on 100 episodes WITH one kick
#     (eval_policy.py --disturb 1.0) in addition to the kick-free evaluation done by run_v2.sh
set -euo pipefail
cd "$(dirname "$0")"
source venv/bin/activate
export MUJOCO_GL=egl
POS=${POS:-0.005}; YAW=${YAW:-10}; EVAL_EPS=${EVAL_EPS:-100}; SEED0=${SEED0:-10000}
stamp () { date "+%H:%M:%S"; }
while pgrep -f "[b]ash run_v2.sh" > /dev/null; do sleep 60; done
echo "[$(stamp)] run_v2.sh finished -> run_v2b"
M=v2_2p1_joint_image_mix; C=v2_2p1_joint_image_clean; R=v2_2p1_joint_image_robust
while [ ! -f "data/$M/meta/info.json" ] || pgrep -f "[c]ollect.py.*$M" > /dev/null; do sleep 30; done

train () {
  local ds=$1 pol=$2 steps=$3; shift 3
  if [ -d "outputs/${pol}_${ds}/checkpoints/last" ]; then echo "[$(stamp)] TRAIN ${pol}_${ds} exists, skipping"; return; fi
  echo "[$(stamp)] TRAIN ${pol}_${ds} start (${steps} steps)"
  lerobot-train --dataset.repo_id="local/$ds" --dataset.root="data/$ds" --policy.device=cuda \
    --policy.push_to_hub=false --steps="$steps" --num_workers=8 --save_freq=10000 --log_freq=200 \
    --output_dir="outputs/${pol}_${ds}" --job_name="${pol}_${ds}" --wandb.enable=false "$@" \
    > "logs/train_${pol}_${ds}.log" 2>&1
  echo "[$(stamp)] TRAIN ${pol}_${ds} done"
}
evaluate () {  # evaluate <run> <mortar> <disturb> [extra args]  (background)
  local run=$1 mortar=$2 dist=$3; shift 3
  local tag="${mortar}"; [ "$dist" != "0" ] && tag="${mortar}_kick"
  [ -f "outputs/eval_${run}_${tag}.json" ] && { echo "[$(stamp)] EVAL ${run} @ ${tag} exists"; return; }
  echo "[$(stamp)] EVAL ${run} @ ${tag} start (${EVAL_EPS} episodes, background)"
  ( python eval_policy.py --task 2p1 --mortar "$mortar" --ckpt "outputs/$run/checkpoints/last/pretrained_model" \
      --episodes "$EVAL_EPS" --seed0 "$SEED0" --pos-rand "$POS" --yaw-rand "$YAW" --size-rand 0 --disturb "$dist" \
      --out "outputs/eval_${run}_${tag}.json" "$@" > "logs/eval_${run}_${tag}.log" 2>&1 \
    && echo "[$(stamp)] EVAL ${run} @ ${tag} done" || echo "[$(stamp)] EVAL ${run} @ ${tag} FAILED" ) &
}

train $M act 40000 --policy.type=act --batch_size=32
evaluate act_$M mortarB 0
evaluate act_$M mortarB 1.0
evaluate act_$C mortarB 1.0
evaluate act_$R mortarB 1.0
train $M diffusion 60000 --policy.type=diffusion --batch_size=32
evaluate diffusion_$M mortarB 0
evaluate diffusion_$M mortarB 1.0
evaluate diffusion_$C mortarB 1.0
evaluate diffusion_$R mortarB 1.0
wait
echo "[$(stamp)] ALL DONE (v2b)"
for j in outputs/eval_*v2_*.json; do
  python - "$j" <<'EOF'
import json, sys; d = json.load(open(sys.argv[1])); eps = d["episodes"]
bp = {k: sum(e[k] for e in eps) / len(eps) for k in ("bp_iou", "bp_E_h_mm", "bp_E_f_mm") if k in eps[0]}
full = sum(1 for e in eps if e["m1_all_success"]); fallen = sum(1 for e in eps if e["m7_fallen_count"] > 0)
print(f"{sys.argv[1]}: n={len(eps)} all_ok={full} fallen_eps={fallen} " + " ".join(f"{k}={v:.3f}" for k, v in bp.items()))
EOF
done
