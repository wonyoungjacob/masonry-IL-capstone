"""진단(결과 아님): 장 단위 시험이 만드는 관측이 학습 데이터의 관측과 같은가, 정책이 학습 장면에서 시연을 따라 내는가.

학습에 쓴 벽 하나(기본 810000)의 16자리에서, 에피소드 첫 프레임마다
  (가) 데이터셋에서 꺼낸 관측(학습이 본 것 그대로)으로 정책이 낸 첫 행동 묶음(100스텝)
  (나) 장 단위 시험과 같은 방법(reset_piece → 원본 영상 → 비율 유지 축소 · 채움 → 관절값 · 목표 정보)으로 만든 관측으로 낸 행동 묶음
을 시연의 기록된 행동과 비교한다. 영상 · 상태 · 목표 정보 자체의 차이도 잰다.
(가)가 시연과 가깝고 (나)가 (가)와 가까우면 시험 쪽 관측 구성에는 문제가 없다. (나)만 멀면 관측 구성이 어긋난 것이다.
관측 구성은 prl.eval_piece.worker의 줄을 그대로 옮겼다. 선정 배치(820000번대)는 쓰지 않는다.

실행: cd sim && MUJOCO_GL=egl PYTHONPATH=. venv/bin/python -m prl.diag_obs --ckpt <pretrained_model> --dataset data/<세팅 데이터셋> \\
        --out outputs/prl/<이름>
"""
import argparse, json, time
from pathlib import Path

import numpy as np


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", required=True)
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--seed", type=int, default=810000, help="a wall of the training data")
    ap.add_argument("--out", required=True)
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--slots", type=int, nargs="*", default=None, help="default: all 16")
    ap.add_argument("--no-env", action="store_true", help="self-test without rendering: only (가), the (나) columns repeat (가)")
    a = ap.parse_args()
    out = Path(a.out)
    if out.exists():
        raise SystemExit(f"{out} 이미 있음: 덮어쓰지 않음")
    out.mkdir(parents=True)

    import torch
    from eval_policy import load_policy
    from lerobot.datasets.lerobot_dataset import LeRobotDataset
    from wall3.config import RETRACT_Q
    from wall3.to_lerobot import target_of, TASK, _table
    from prl import config as C
    from prl.env import DryEnv, letterbox

    root = Path(a.dataset)
    policy, pcfg, pre, post = load_policy(a.ckpt, a.device, None, None)
    cams = [k.split(".")[-1] for k in pcfg.input_features if k.startswith("observation.images.")]
    eps = json.loads((root / "meta" / "prl_episodes.json").read_text())
    first = np.cumsum([0] + [e["frames"] for e in eps])
    mine = [e for e in eps if e["seed"] == a.seed]
    assert len(mine) == 16, f"wall {a.seed} is not in the dataset"
    if a.slots is not None:
        mine = [e for e in mine if e["slot"] in a.slots]
    tab = _table(root)
    ds = LeRobotDataset(f"local/{root.name}", root=str(root), video_backend="pyav")
    env = None if a.no_env else DryEnv(fixed_cams=C.final_cams(cams))
    q_ret = np.array(RETRACT_Q)
    raw = np.empty((C.RAW_H, C.RAW_W, 3), np.uint8)

    def chunk(obs, n):
        policy.reset()
        acts = []
        with torch.inference_mode():
            for _ in range(n):
                acts.append(post(policy.select_action(pre(dict(obs)))).squeeze(0).detach().cpu().numpy().astype(np.float64))
        return np.array(acts)

    rows = []
    for e in mine:
        k, i0 = e["slot"], int(first[e["episode_index"]])
        n = min(pcfg.n_action_steps, e["frames"])
        demo = tab["action"][i0:i0 + n].astype(np.float64)
        item = ds[i0]
        assert int(item["episode_index"]) == e["episode_index"] and int(item["frame_index"]) == 0
        obs_ds = {f"observation.images.{c}": item[f"observation.images.{c}"].unsqueeze(0) for c in cams}
        obs_ds["observation.state"] = item["observation.state"].unsqueeze(0)
        obs_ds["observation.environment_state"] = item["observation.environment_state"].unsqueeze(0)
        obs_ds["task"] = [TASK]
        demo_bricks = tab["info.all_brick_poses"][i0].reshape(16, 7)
        if env is None:
            obs_ev, truth = obs_ds, demo_bricks
        else:
            # the same lines as prl.eval_piece.worker
            env.reset_piece(a.seed, k, arm_q=q_ret)
            tgt = torch.from_numpy(target_of(env.design[k])).unsqueeze(0)
            obs_ev = {f"observation.images.{c}": torch.from_numpy(letterbox(env.render_raw(c, out=raw))).permute(2, 0, 1).float().div(255.0).unsqueeze(0)
                      for c in cams}
            st = np.r_[env.arm_q(), float(env.data.joint("g_finger_joint").qpos[0])].astype(np.float32)
            obs_ev["observation.state"] = torch.from_numpy(st).unsqueeze(0)
            obs_ev["observation.environment_state"] = tgt
            obs_ev["task"] = [TASK]
            truth = env.brick_poses()

        a_ds, a_ev = chunk(obs_ds, n), chunk(obs_ev, n)
        img = {c: float((obs_ev[f"observation.images.{c}"] - obs_ds[f"observation.images.{c}"]).abs().mean() * 255.0) for c in cams}
        rows.append({
            "slot": k, "n": int(n),
            "image_mean_abs_diff_255": img,
            "state_max_abs_diff": float(np.abs(obs_ev["observation.state"] - obs_ds["observation.state"]).max()),
            "target_max_abs_diff": float(np.abs(obs_ev["observation.environment_state"] - obs_ds["observation.environment_state"]).max()),
            "scene_brick_xyz_max_diff_mm": float(np.abs(truth[:, :3] - demo_bricks[:, :3]).max() * 1000),   # 참값 (진단)
            "arm_rad": {"ds_vs_demo_mean": float(np.abs(a_ds[:, :6] - demo[:, :6]).mean()), "ds_vs_demo_max": float(np.abs(a_ds[:, :6] - demo[:, :6]).max()),
                        "ev_vs_ds_mean": float(np.abs(a_ev[:, :6] - a_ds[:, :6]).mean()), "ev_vs_ds_max": float(np.abs(a_ev[:, :6] - a_ds[:, :6]).max()),
                        "ev_vs_demo_mean": float(np.abs(a_ev[:, :6] - demo[:, :6]).mean()), "ev_vs_demo_max": float(np.abs(a_ev[:, :6] - demo[:, :6]).max())},
            "gripper": {"ds_vs_demo_max": float(np.abs(a_ds[:, 6] - demo[:, 6]).max()), "ev_vs_ds_max": float(np.abs(a_ev[:, 6] - a_ds[:, 6]).max()),
                        "demo_range": [float(demo[:, 6].min()), float(demo[:, 6].max())]},
        })
        r = rows[-1]
        print(f"slot {k:2d}: image {max(img.values()):5.2f}  state {r['state_max_abs_diff']:.5f}  target {r['target_max_abs_diff']:.2e}  "
              f"scene {r['scene_brick_xyz_max_diff_mm']:.2f} mm | arm rad: ds-demo {r['arm_rad']['ds_vs_demo_mean']:.4f} / {r['arm_rad']['ds_vs_demo_max']:.4f}  "
              f"ev-ds {r['arm_rad']['ev_vs_ds_mean']:.4f} / {r['arm_rad']['ev_vs_ds_max']:.4f}  ev-demo {r['arm_rad']['ev_vs_demo_mean']:.4f} / "
              f"{r['arm_rad']['ev_vs_demo_max']:.4f}", flush=True)
    if env is not None:
        env.close()
    summ = {"no_env": bool(a.no_env), "ckpt": a.ckpt, "dataset": a.dataset, "seed": a.seed, "cams": cams, "n_action_steps": pcfg.n_action_steps, "rows": rows,
            "max": {"image_mean_abs_diff_255": max(max(r["image_mean_abs_diff_255"].values()) for r in rows),
                    "state_max_abs_diff": max(r["state_max_abs_diff"] for r in rows),
                    "target_max_abs_diff": max(r["target_max_abs_diff"] for r in rows),
                    "scene_brick_xyz_max_diff_mm": max(r["scene_brick_xyz_max_diff_mm"] for r in rows),
                    "arm_ds_vs_demo_max_rad": max(r["arm_rad"]["ds_vs_demo_max"] for r in rows),
                    "arm_ev_vs_ds_max_rad": max(r["arm_rad"]["ev_vs_ds_max"] for r in rows),
                    "arm_ev_vs_demo_max_rad": max(r["arm_rad"]["ev_vs_demo_max"] for r in rows)},
            "finished": time.strftime("%F %T")}
    (out / "summary.json").write_text(json.dumps(summ, indent=1, ensure_ascii=False))
    print(json.dumps(summ["max"], indent=1))


if __name__ == "__main__":
    main()
