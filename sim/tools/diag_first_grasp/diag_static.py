"""Static check: put the arm at the IK solution for the grasp pose (brick removed far away) and list self-collisions."""
import sys, numpy as np, mujoco
sys.path.insert(0, '/home/won/masonry/sim')
from brick_sim.scene import BrickEnv, blueprint_config, JAW_OPEN, HOME_QPOS
from brick_sim.expert import ScriptedExpert
from brick_sim.ik import rot_from_down_yaw

def check(seed, flip=False):
    cfg = blueprint_config('mortarB', size_rand=0, pos_rand=.03, supply_yaw_deg=60, valid_supply=True)
    env = BrickEnv(cfg); env.reset(seed)
    ex = ScriptedExpert(env, seed=seed, max_retries=0, clean_single_pass=True)
    ex.order = sorted(range(env.n_bricks), key=lambda b: env.brick_pose(b)[0][0]); ex.slot = {b:k for k,b in enumerate(ex.order)}
    ex.place_bias = {}; i = ex.order[0]
    segs = ex.plan_brick(i)
    tp, yaw = np.array(segs[1][0]), segs[1][1]
    if flip:
        # brick is 180-deg symmetric: put the fixed jaw on the other face -> offset direction flips too
        pb = env.brick_pose(i)[0]; d = tp[:2] - pb[:2]; tp = tp.copy(); tp[:2] = pb[:2] - d; yaw = yaw + np.pi
    m, d = env.model, env.data
    best = None
    for q0 in [HOME_QPOS[:5], np.zeros(5), np.array([0.7,-2.6,2.7,1.4,-0.2]), np.array([0.7,-1.0,1.0,1.5,0.0])]:
        q, ep, er = ex.ik.solve(q0, tp, rot_from_down_yaw(yaw), d.qpos.copy())
        if best is None or ep < best[1]: best = (q, ep, er)
    q, ep, er = best
    d.qpos[env.arm_qidx] = q; d.qpos[env.jaw_qidx] = JAW_OPEN
    # move bricks far away so only arm-arm and arm-floor contacts remain
    for a in env.brick_qadr: d.qpos[a:a+3] = [1.0, 1.0, 0.5]
    mujoco.mj_forward(m, d)
    names = lambda g: m.body(m.geom_bodyid[g]).name
    cts = {}
    for c in d.contact[:d.ncon]:
        k = f"{names(c.geom1)}-{names(c.geom2)}"; cts[k] = min(cts.get(k, 0), c.dist)
    print(f"seed {seed} flip={flip}: target {tp.round(4)} yaw {np.degrees(yaw)%360:.1f} ik_err {ep*1000:.2f}mm/{er:.3f} q {q.round(3)} wrist_roll {q[4]:+.2f}")
    print("   self/floor contacts at IK pose:", {k: round(v*1000,2) for k, v in cts.items()} or "none")
    return cts

for s in (1001, 1023):
    for f in (False, True):
        check(s, f)
