"""학습 정책 롤아웃 (2차 지시 가2: 미니 학습 점검용, 결과로 쓰지 않음).

정책 단독. 다음 벽돌은 도면 순서표(자리 0 → 15)가 정하고, 성공을 확인하지 않고 정해진 규칙으로 넘어간다:
  - 정책의 철수 완료: 팔이 철수 자세에서 한 번 벗어났다가(어느 관절이든 0.3 rad 이상) 다시 모든 관절이 철수 자세 0.05 rad 안,
    관절 속도 0.05 rad/s 미만으로 3스텝 머묾 (로봇 자신의 관절 상태만 봄)
  - 또는 벽돌당 시간 제한 17 s (340스텝)
정책 관측: 카메라 3대(128²), 관절 6 + 집게(왼쪽 구동 관절), 목표 정보(도면 목표 x·y·z·yaw + 반장). 정답 좌표는 채점에만 쓴다.
벽돌마다 정책을 reset 한다(벽돌 한 장 = 에피소드 1개로 학습했으므로).
G1(--g1, 나4): 집게를 닫고 1.5 cm 들어 올리면 정책을 멈추고 하중·각도로 쥠을 확인(wall3/g1.py). 못 쥐었으면 집게를 열고 정책을
reset 해 다시 집게 함(벽돌당 시간 제한 안에서 횟수 제한 없음). 쥐었으면 정책을 reset 하고 이어 감. 확인 동작 시간도 벽돌 시간에 넣는다.

실행: cd sim && source venv/bin/activate && MUJOCO_GL=egl PYTHONPATH=. python -m wall3.rollout --ckpt <pretrained_model> \\
        --env-version pilot_20261016 --seeds 700100 ... --out outputs/wall3/<이름> [--record-first] [--n-action-steps N]
"""
import argparse, hashlib, json, subprocess, sys, time
from pathlib import Path

import numpy as np

SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SIM))
CAMS = ("front", "top", "wrist")
LIMIT_S = 17.0
ALLOWED = [(700053, 700199),          # pilot block, unused seeds (2차 지시: 700100 ~ 700119 for the mini rollouts)
           (700300, 700301)]          # 본학습 지시 5절: sanity check after each main training (not a result)


def obs_of(env, k, cfg_in, torch):
    from wall3.to_lerobot import target_of, TASK
    obs = {}
    for c in CAMS:
        key = f"observation.images.{c}"
        if key in cfg_in:
            obs[key] = torch.from_numpy(env.render(c)).permute(2, 0, 1).float().div(255.0).unsqueeze(0)
    st = np.r_[env.arm_q(), float(env.data.joint("g_finger_joint").qpos[0])].astype(np.float32)
    obs["observation.state"] = torch.from_numpy(st).unsqueeze(0)
    obs["observation.environment_state"] = torch.from_numpy(target_of(env.design[k])).unsqueeze(0)
    obs["task"] = [TASK]
    return obs


def run_wall(env, policy, pre, post, cfg_in, seed, torch, rec=None, q_ret=None, g1=None):
    from wall3.spec_metrics import evaluate_env
    from wall3.g1 import G1Trigger
    env.reset(seed, arm_q=q_ret)
    dt = env.cfg.ctrl_dt
    t0 = time.time()
    bricks = []
    last = np.r_[q_ret, env.cfg.gripper.open_ctrl]
    n_limit = int(round(LIMIT_S / dt))
    g1_steps = 0
    if g1 is not None:
        c = g1.cfg
        g1_steps = sum(max(1, int(round(t / dt))) for t in (c.t_settle, c.t_load, c.t_squeeze, c.t_restore, c.t_open))
    for k in range(env.n):
        policy.reset()
        start = env.t
        z0 = env.brick_pose(k)[0][2]
        zmax = z0
        left, still, reason = False, 0, "timeout"
        qhist = []
        trig = G1Trigger(g1.cfg, dt) if g1 is not None else None
        checks = []
        z_start = [env.brick_pose(j)[0][2] for j in range(env.n)]
        while env.t - start < n_limit:
            obs = obs_of(env, k, cfg_in, torch)
            with torch.inference_mode():
                act = post(policy.select_action(pre(obs))).squeeze(0).detach().cpu().numpy().astype(np.float64)
            if rec is not None:
                rec.frame(f"policy brick {k + 1}", k)
            env.step(act[:6], float(act[6]))
            last = act
            fired = trig is not None and trig.update(float(act[6]), env.tcp()[0][2])
            if fired and n_limit - (env.t - start) < g1_steps:            # not enough time left: no check, the limit stays exact
                checks.append({"t": int(env.t), "skipped": "time_limit"})
                fired = False
            if fired:
                on = (lambda lb: rec.frame(f"G1 {lb[3:]} brick {k + 1}", k)) if rec is not None else None
                m = g1.measure(act[:6], float(act[6]), on)
                ok = g1.decide(m)
                rise = [env.brick_pose(j)[0][2] - z_start[j] for j in range(env.n)]           # scoring only (ground truth)
                checks.append({"t": int(env.t), "load_N": m["load_N"], "angle_rad": m["angle_rad"], "grasped": ok,
                               "brick_z_rise_mm": float(rise[k] * 1000), "max_rise_brick": int(np.argmax(rise)),
                               "max_rise_mm": float(max(rise) * 1000)})
                if not ok:                                   # open and let the policy grasp again
                    for _ in range(max(1, int(round(g1.cfg.t_open / dt)))):
                        env.step(act[:6], env.cfg.gripper.open_ctrl)
                        if rec is not None:
                            rec.frame(f"G1 open brick {k + 1}", k)
                    last = np.r_[act[:6], env.cfg.gripper.open_ctrl]
                    trig.reset()
                policy.reset()
            q = env.arm_q()
            qhist.append(q)
            zmax = max(zmax, env.brick_pose(k)[0][2])
            dev = np.abs(q - q_ret).max()
            if dev > 0.3:
                left = True
            qd = np.abs(env.data.qvel[env.arm_dofadr]).max()
            still = still + 1 if (left and dev < 0.05 and qd < 0.05) else 0
            if still >= 3:
                reason = "retract"
                break
        moved_last3s = float(np.abs(np.array(qhist[-60:]).max(0) - np.array(qhist[-60:]).min(0)).max()) if len(qhist) >= 60 else None
        bricks.append({"slot": k, "start": int(start), "end": int(env.t), "duration_s": (env.t - start) * dt, "end_reason": reason,
                       "grasped_lifted": bool(zmax > z0 + 0.02), "max_lift_mm": float((zmax - z0) * 1000),
                       "stalled": bool(reason == "timeout" and moved_last3s is not None and moved_last3s < 0.02),
                       "joint_range_last3s_rad": moved_last3s,
                       **({"g1_checks": checks, "g1_regrasps": sum(c.get("grasped") is False for c in checks)} if g1 is not None else {})})
    for _ in range(int(round(2.0 / dt))):                 # 2 s settle holding the last command
        env.step(last[:6], float(last[6]))
        if rec is not None:
            rec.frame("settle", -1)
    ev = evaluate_env(env)
    for b in bricks:
        s = env.design[b["slot"]]
        p, q = env.brick_pose(b["slot"])
        from wall3.poses import yaw_of_quat
        b["final_err_mm"] = ((p - [s["x"], s["y"], s["z"]]) * 1000).round(2).tolist()
        b["final_xy_err_mm"] = float(np.hypot(*b["final_err_mm"][:2]))
        b["iou"] = ev["iou"][b["slot"]]
    return {"seed": seed, "bricks": bricks, "eval": ev, "wall_clock_s": time.time() - t0, "sim_s": env.t * dt}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", required=True)
    ap.add_argument("--env-version", required=True)
    ap.add_argument("--seeds", type=int, nargs="+", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--record-first", action="store_true")
    ap.add_argument("--n-action-steps", type=int, default=0)
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--g1", action="store_true", help="G1 grasp check on (condition 2/5/6/8)")
    ap.add_argument("--g1-thr-load", type=float, default=None, help="N; required with --g1")
    ap.add_argument("--g1-thr-angle", type=float, default=None, help="rad; required with --g1")
    a = ap.parse_args()
    if a.g1 and (a.g1_thr_load is None or a.g1_thr_angle is None):
        raise SystemExit("--g1 needs --g1-thr-load and --g1-thr-angle")
    if any(not any(lo <= s <= hi for lo, hi in ALLOWED) for s in a.seeds):
        raise SystemExit(f"롤아웃 시작값은 파일럿 블록 미사용 값 {ALLOWED}만")
    out = Path(a.out)
    if out.exists():
        raise SystemExit(f"{out} 이미 있음: 덮어쓰지 않음")
    out.mkdir(parents=True)
    import torch
    from eval_policy import load_policy
    from wall3.config import scene_config, RETRACT_Q
    from wall3.scene import WallEnv
    policy, pcfg, pre, post = load_policy(a.ckpt, a.device, None, a.n_action_steps or None)
    cfg_in = set(pcfg.input_features)
    env = WallEnv(scene_config(a.env_version))
    q_ret = np.array(RETRACT_Q)
    g1 = None
    if a.g1:
        from wall3.g1 import G1, G1Config
        g1 = G1(env, G1Config(thr_load=a.g1_thr_load, thr_angle=a.g1_thr_angle))
    meta = {"ckpt": a.ckpt, "env_version": a.env_version, "policy_type": pcfg.type, "n_action_steps": pcfg.n_action_steps,
            "input_features": {k: list(v.shape) for k, v in pcfg.input_features.items()},
            "git_commit": subprocess.check_output(["git", "-C", str(SIM), "rev-parse", "HEAD"], text=True).strip(), "limit_s": LIMIT_S,
            "g1": ({**g1.cfg.to_dict(), "tare_N": g1.f0} if g1 is not None else None),
            "scene_sha256": hashlib.sha256(json.dumps(env.cfg.to_dict(), sort_keys=True, default=float).encode()).hexdigest()}
    res = []
    for i, seed in enumerate(a.seeds):
        rec = None
        if a.record_first and i == 0:
            from wall3.view_collect import Recorder
            rec = Recorder(env, out / f"wall_{seed}.mp4", label=f"{pcfg.type} {a.env_version} seed {seed}")
        r = run_wall(env, policy, pre, post, cfg_in, seed, torch, rec, q_ret, g1)
        if rec is not None:
            rec.close()
        res.append(r)
        ev = r["eval"]
        b = r["bricks"]
        print(f"[{pcfg.type}] seed {seed}: lifted {sum(x['grasped_lifted'] for x in b)}/16, retract {sum(x['end_reason'] == 'retract' for x in b)}/16, "
              f"stalled {sum(x['stalled'] for x in b)}, filled {sum(ev['slots_filled'])}/16, spec {ev['spec_pass']}, IoU mean {ev['iou_mean']:.3f}, "
              f"median xy err {np.median([x['final_xy_err_mm'] for x in b]):.1f} mm, wall {r['wall_clock_s']:.0f} s (sim {r['sim_s']:.0f} s)"
              + (f", G1 checks {sum('grasped' in c for x in b for c in x['g1_checks'])} (not grasped {sum(x['g1_regrasps'] for x in b)})" if g1 is not None else ""), flush=True)
        (out / "rollout.json").write_text(json.dumps({"meta": meta, "walls": res}, indent=1, default=float))
    env.close()


if __name__ == "__main__":
    main()
