#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
source venv/bin/activate
export MUJOCO_GL=glfw
python view_demo.py --task 2p1 --mortar mortarB --spec v2 --size-rand 0 \
  --pos-rand 0.03 --yaw-rand 60 --valid-supply --clean-single-pass --seed 4 "$@"
