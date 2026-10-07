#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
source venv/bin/activate
export MUJOCO_GL=egl
export PYTHONUNBUFFERED=1
python -u run_clean_experiment.py "$@"
