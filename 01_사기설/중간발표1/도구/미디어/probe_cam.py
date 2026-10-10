# -*- coding: utf-8 -*-
"""자유 카메라 각도 후보를 한 장에 렌더해 고른다 (초기 상태 + 벽 완성 상태 흉내는 안 함)."""
import sys, numpy as np, mujoco, cv2
sys.path.insert(0, r"C:/Users/user/Desktop/사기설/sim")
from brick_sim.scene import BrickEnv, blueprint_config
env = BrickEnv(blueprint_config('mortarB', size_rand=0, pos_rand=.03, supply_yaw_deg=60, valid_supply=True, feasible_supply=True))
env.reset(40000); env.settle(5)
R = mujoco.Renderer(env.model, 240, 320)
wall = np.array([env.cfg.wall.origin_x, env.cfg.wall.origin_y, 0.03])
print("wall", wall, "design", [tuple(round(v, 3) for v in d[:4]) for d in env.design])
print("supply", [tuple(round(v, 3) for v in p) for p in env.supply_poses])
tiles = []
for el in (-20, -35):
    row = []
    for az in (0, 60, 120, 180, 240, 300):
        c = mujoco.MjvCamera(); c.type = mujoco.mjtCamera.mjCAMERA_FREE
        c.lookat[:] = wall + np.array([0.04, 0.05, 0.0]); c.distance = 0.5; c.azimuth = az; c.elevation = el
        R.update_scene(env.data, camera=c); im = R.render().copy()
        cv2.putText(im, f"az{az} el{el}", (5, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2); row.append(im)
    tiles.append(np.hstack(row))
for name in ("front", "top", "wrist"):
    R.update_scene(env.data, camera=name); im = R.render().copy(); cv2.putText(im, name, (5, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2); tiles.append(np.hstack([im] + [np.zeros_like(im)] * 5))
sheet = np.vstack(tiles)
ok, buf = cv2.imencode(".png", cv2.cvtColor(sheet, cv2.COLOR_RGB2BGR))
open(r"C:/Users/user/AppData/Local/Temp/claude/c--Users-user-Desktop----/be685ff9-f10f-46a4-892d-1862ceb8f949/scratchpad/media/probe_cam.png", "wb").write(buf.tobytes())
print("ok")
