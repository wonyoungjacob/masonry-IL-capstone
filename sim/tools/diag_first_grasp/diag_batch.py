"""For every collected attempt: static self-penetration at the first-grasp IK pose vs the recorded first-grasp outcome."""
import sys, json, numpy as np, mujoco
sys.path.insert(0, '/home/won/masonry/sim')
from brick_sim.scene import BrickEnv, blueprint_config, JAW_OPEN
from brick_sim.expert import ScriptedExpert
from brick_sim.ik import rot_from_down_yaw

recs = json.load(open('/home/won/masonry/sim/data/v3_2p1_joint_image_clean/episode_metrics.json'))
cfg = blueprint_config('mortarB', size_rand=0, pos_rand=.03, supply_yaw_deg=60, valid_supply=True)
env = BrickEnv(cfg)
out = []
for r in recs:
    seed = r['episode_seed']; env.reset(seed)
    assert np.allclose(env.brick_poses()[:, :3], np.array(r['initial_poses'])[:, :3], atol=1e-6), seed
    ex = ScriptedExpert(env, seed=seed, max_retries=0, clean_single_pass=True)
    ex.order = sorted(range(env.n_bricks), key=lambda b: env.brick_pose(b)[0][0]); ex.slot = {b:k for k,b in enumerate(ex.order)}
    ex.place_bias = {}; i = ex.order[0]
    segs = ex.plan_brick(i); tp, yaw = np.array(segs[1][0]), segs[1][1]
    m, d = env.model, env.data
    q, ep, er = ex.ik.solve(d.qpos[env.arm_qidx].copy(), tp, rot_from_down_yaw(yaw), d.qpos.copy())
    d.qpos[env.arm_qidx] = q; d.qpos[env.jaw_qidx] = JAW_OPEN
    for a in env.brick_qadr: d.qpos[a:a+3] = [1.0, 1.0, 0.5]
    mujoco.mj_forward(m, d)
    names = lambda g: m.body(m.geom_bodyid[g]).name
    pen = 0.0; who = ''
    for c in d.contact[:d.ncon]:
        a, b = names(c.geom1), names(c.geom2)
        if a.startswith('brick') or b.startswith('brick'): continue
        if c.dist < pen: pen, who = c.dist, f"{a}-{b}"
    g0 = [e for e in r['expert_log'] if e.get('stage') == 'grasp']
    fail = bool(g0) and not g0[0]['ok']
    pb = np.array(r['initial_poses'])[i]
    out.append(dict(seed=seed, fail_first=fail, pen_mm=round(-pen*1000, 2), who=who, ik_mm=round(ep*1000, 2),
                    r_brick=round(float(np.hypot(pb[0], pb[1])), 4), r_tcp=round(float(np.hypot(tp[0], tp[1])), 4),
                    yaw_deg=round(float(np.degrees(2*np.arctan2(pb[6], pb[3]))), 1), kept=r['kept']))
json.dump(out, open('/home/won/masonry/sim/outputs/diag_first_grasp/first_grasp_static.json', 'w'), indent=0)
o = out
for thr in (0.5, 1, 2, 3, 5):
    tp_ = sum(1 for x in o if x['fail_first'] and x['pen_mm'] > thr); fp = sum(1 for x in o if not x['fail_first'] and x['pen_mm'] > thr)
    fn = sum(1 for x in o if x['fail_first'] and x['pen_mm'] <= thr); tn = sum(1 for x in o if not x['fail_first'] and x['pen_mm'] <= thr)
    print(f"pen > {thr} mm: fail&flag {tp_:3d}  ok&flag {fp:3d}  fail&clear {fn:3d}  ok&clear {tn:3d}")
print("ik_mm > 1.0 among fails:", sum(1 for x in o if x['fail_first'] and x['ik_mm'] > 1), "/ among ok:", sum(1 for x in o if not x['fail_first'] and x['ik_mm'] > 1))
print("r_tcp: fail min/med/max", *[round(f([x['r_tcp'] for x in o if x['fail_first']]),4) for f in (min, np.median, max)],
      "| ok", *[round(f([x['r_tcp'] for x in o if not x['fail_first']]),4) for f in (min, np.median, max)])
for thr in (0.125, 0.13, 0.135, 0.14):
    print(f"r_tcp < {thr}: fail {sum(1 for x in o if x['fail_first'] and x['r_tcp']<thr)} ok {sum(1 for x in o if not x['fail_first'] and x['r_tcp']<thr)}")
print("fails with pen<=1mm:", [(x['seed'], x['pen_mm'], x['who'], x['r_tcp'], x['yaw_deg']) for x in o if x['fail_first'] and x['pen_mm'] <= 1][:15])
print("ok with pen>2mm:", [(x['seed'], x['pen_mm'], x['r_tcp'], x['yaw_deg']) for x in o if not x['fail_first'] and x['pen_mm'] > 2][:15])
