"""Static feasibility flags for the first grasp of every attempt:
   self_pen  : arm self-penetration at the IK grasp pose (bricks removed)
   nbr_pen   : max penetration of any arm body into a NON-target brick at the grasp pose while the jaw sweeps open->closed
   nbr_hover : same at the hover pose (approach)
"""
import sys, json, numpy as np, mujoco
sys.path.insert(0, '/home/won/masonry/sim')
from brick_sim.scene import BrickEnv, blueprint_config, JAW_OPEN, JAW_CLOSED
from brick_sim.expert import ScriptedExpert
from brick_sim.ik import rot_from_down_yaw

recs = json.load(open('/home/won/masonry/sim/data/v3_2p1_joint_image_clean/episode_metrics.json'))
prev = {x['seed']: x for x in json.load(open('/home/won/masonry/sim/outputs/diag_first_grasp/first_grasp_static.json'))}
cfg = blueprint_config('mortarB', size_rand=0, pos_rand=.03, supply_yaw_deg=60, valid_supply=True)
env = BrickEnv(cfg)
ARM = {'Base','Rotation_Pitch','Upper_Arm','Lower_Arm','Wrist_Pitch_Roll','Fixed_Jaw','Moving_Jaw'}
out = []
for r in recs:
    seed = r['episode_seed']; env.reset(seed)
    ex = ScriptedExpert(env, seed=seed, max_retries=0, clean_single_pass=True)
    ex.order = sorted(range(env.n_bricks), key=lambda b: env.brick_pose(b)[0][0]); ex.slot = {b:k for k,b in enumerate(ex.order)}
    ex.place_bias = {}; i = ex.order[0]
    segs = ex.plan_brick(i)
    m, d = env.model, env.data
    names = lambda g: m.body(m.geom_bodyid[g]).name
    q0 = d.qpos[env.arm_qidx].copy(); qpos0 = d.qpos.copy()
    def worst(tp, yaw, jaws, tgt):
        q, ep, er = ex.ik.solve(q0, np.array(tp), rot_from_down_yaw(yaw), qpos0.copy())
        pen, who = 0.0, ''
        for j in jaws:
            d.qpos[:] = qpos0; d.qpos[env.arm_qidx] = q; d.qpos[env.jaw_qidx] = j
            mujoco.mj_forward(m, d)
            for c in d.contact[:d.ncon]:
                a, b = names(c.geom1), names(c.geom2)
                if (a in ARM and b.startswith('brick') and b != tgt) or (b in ARM and a.startswith('brick') and a != tgt):
                    if c.dist < pen: pen, who = c.dist, f"{a}-{b}@jaw{j:.2f}"
        return -pen*1000, who
    tgt = f'brick_{i}'
    nbr_pen, nbr_who = worst(segs[1][0], segs[1][1], np.linspace(JAW_OPEN, JAW_CLOSED, 12), tgt)
    hov_pen, hov_who = worst(segs[0][0], segs[0][1], [JAW_OPEN], tgt)
    # neighbour distance from the target brick centre
    pb = np.array(r['initial_poses'])
    dn = min(np.hypot(*(pb[j,:2]-pb[i,:2])) for j in range(3) if j != i)
    g0 = [e for e in r['expert_log'] if e.get('stage') == 'grasp']
    out.append(dict(seed=seed, fail_first=bool(g0) and not g0[0]['ok'], self_pen=prev[seed]['pen_mm'], nbr_pen=round(nbr_pen,2), nbr_who=nbr_who,
                    hov_pen=round(hov_pen,2), d_nbr_mm=round(1000*dn,1), r_tcp=prev[seed]['r_tcp'], yaw=prev[seed]['yaw_deg']))
    d.qpos[:] = qpos0; mujoco.mj_forward(m, d)
json.dump(out, open('/home/won/masonry/sim/outputs/diag_first_grasp/first_grasp_static2.json','w'), indent=0)
F = [x for x in out if x['fail_first']]; O = [x for x in out if not x['fail_first']]
def cnt(L, f): return sum(1 for x in L if f(x))
for ts, tn in ((0.5, 0.5), (0.5, 1.0), (0.5, 2.0)):
    fs = lambda x: x['self_pen'] > ts; fnb = lambda x: x['nbr_pen'] > tn; fh = lambda x: x['hov_pen'] > tn
    print(f"self>{ts} nbr>{tn}: fail flagged self {cnt(F,fs)} nbr {cnt(F,fnb)} hover {cnt(F,fh)} any {cnt(F,lambda x: fs(x) or fnb(x) or fh(x))}/{len(F)} | ok flagged self {cnt(O,fs)} nbr {cnt(O,fnb)} hover {cnt(O,fh)} any {cnt(O,lambda x: fs(x) or fnb(x) or fh(x))}/{len(O)}")
print("unexplained fails (self<=0.5, nbr<=0.5, hover<=0.5):")
for x in F:
    if x['self_pen'] <= 0.5 and x['nbr_pen'] <= 0.5 and x['hov_pen'] <= 0.5: print("  ", x)
print("ok but nbr>0.5:", [(x['seed'], x['nbr_pen'], x['nbr_who'], x['d_nbr_mm']) for x in O if x['nbr_pen'] > 0.5][:12])
print("d_nbr among fails w/ nbr flag:", sorted(x['d_nbr_mm'] for x in F if x['nbr_pen']>0.5)[:5], "... ok min d_nbr:", min(x['d_nbr_mm'] for x in O))
