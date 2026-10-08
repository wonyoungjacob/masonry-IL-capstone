"""Instrumented replay of the first grasp for a given seed (Experiment-2 collect config)."""
import sys, json, numpy as np, mujoco
sys.path.insert(0, '/home/won/masonry/sim')
from brick_sim.scene import BrickEnv, blueprint_config, JAW_OPEN
from brick_sim.expert import ScriptedExpert
from brick_sim.ik import rot_from_down_yaw

def run(seed, verbose=True):
    cfg = blueprint_config('mortarB', size_rand=0, pos_rand=.03, supply_yaw_deg=60, valid_supply=True)
    env = BrickEnv(cfg); env.reset(seed)
    ex = ScriptedExpert(env, seed=seed, max_retries=0, clean_single_pass=True)
    ex.dt = env.cfg.ctrl_dt
    ex.q_prev = env.data.qpos[env.arm_qidx].copy()
    p, R = env.tcp_pose(); ex.p_prev = p; ex.yaw_prev = float(np.arctan2(R[1,0],R[0,0])); ex.jaw_prev = JAW_OPEN
    ex.n_fail = 0; ex.place_bias = {}; ex.log = []
    ex.order = sorted(range(env.n_bricks), key=lambda b: env.brick_pose(b)[0][0]); ex.slot = {b:k for k,b in enumerate(ex.order)}
    i = ex.order[0]
    segs = ex.plan_brick(i)
    m, d = env.model, env.data
    names = lambda g: m.body(m.geom_bodyid[g]).name
    log = []
    targets = {}
    orig_solve = ex.ik.solve
    def solve(q0, tp, tR, fq=None):
        q, ep, er = orig_solve(q0, tp, tR, fq)
        targets['tp'] = np.array(tp); targets['q'] = q; targets['ep'] = ep; targets['er'] = er
        return q, ep, er
    ex.ik.solve = solve
    orig_step = env.step
    def step(act):
        r = orig_step(act)
        p, R = env.tcp_pose(); pb, qb = env.brick_pose(i)
        q = d.qpos[env.arm_qidx]
        lo, hi = ex.ik.lo, ex.ik.hi
        at_lim = [int(abs(q[k]-lo[k])<1e-3 or abs(q[k]-hi[k])<1e-3) for k in range(5)]
        cts = []
        for c in d.contact[:d.ncon]:
            a, b = names(c.geom1), names(c.geom2)
            if 'brick_%d'%i in (a,b) or ({a,b} & {'Fixed_Jaw','Moving_Jaw','Wrist_Pitch_Roll','Lower_Arm'} and not {a,b} <= {'Fixed_Jaw','Moving_Jaw','Wrist_Pitch_Roll','Lower_Arm'}):
                cts.append(f"{a}-{b}:{c.dist*1000:.1f}")
        log.append(dict(t=env.t, tp=targets['tp'].round(4).tolist(), tcp=p.round(4).tolist(),
                        track_err_mm=round(1000*float(np.linalg.norm(targets['tp']-p)),1), ik_ep_mm=round(1000*targets['ep'],2), ik_er=round(targets['er'],3),
                        q=np.round(q,3).tolist(), q_cmd=np.round(targets['q'],3).tolist(), at_lim=at_lim,
                        jaw=round(float(d.qpos[env.jaw_qidx]),3), jaw_cmd=round(float(act[5]),3),
                        brick_z_mm=round(1000*pb[2],1), brick_xy=pb[:2].round(4).tolist(), dz_tcp_brick_mm=round(1000*(p[2]-pb[2]),1),
                        grasped=env.grasped(i), contacts=cts))
        return r
    env.step = step
    ex._run_segments(segs[:4], i, None, 0.004)
    initial_z = 0.014
    pb = env.brick_pose(i)[0]
    print(f"seed {seed} brick {i} yaw_b {np.degrees(2*np.arctan2(env.brick_pose(i)[1][3],env.brick_pose(i)[1][0])):.1f} r {np.hypot(*pb[:2]):.4f}  lifted {pb[2]-initial_z>=0.015} grasped {env.grasped(i)}  n_ik_fail {ex.n_fail}")
    print("grasp target (segs[1]):", np.round(segs[1][0],4), "yaw_grasp", round(np.degrees(segs[1][1]),1))
    if verbose:
        for e in log:
            if e['t'] % 4 == 0 or e['t'] in (19,20,21,22,23,32,33,34,40,41,42):
                print(f"t{e['t']:3d} tp{e['tp']} tcp{e['tcp']} trk{e['track_err_mm']:5.1f}mm ik{e['ik_ep_mm']:5.2f}mm/{e['ik_er']:.2f} q{e['q']} lim{e['at_lim']} jaw{e['jaw']:+.2f}/{e['jaw_cmd']:+.2f} bz{e['brick_z_mm']:5.1f} dz{e['dz_tcp_brick_mm']:5.1f} g{int(e['grasped'])} {e['contacts']}")
    return log, segs

if __name__ == '__main__':
    for s in [int(a) for a in sys.argv[1:]]:
        run(s); print('='*100)
