"""벽 단위 원자료 → LeRobot 데이터셋(v3) 변환 (지시서 단계 5). 벽돌 한 장 = 에피소드 1개.

- 시방 합격한 벽만 넣는다(--all 이면 전부, 스모크 확인용).
- 에피소드 = 벽돌 k의 [시작, 끝) 스텝 (시작 = 철수 자세에서 출발, 끝 = 벽돌이 받침에 정지하고 집게가 철수 자세로 돌아옴).
- 정책 관측: observation.images.{front,top,wrist}(128²), observation.state(관절 6 + 집게 왼쪽 구동 관절 각도),
  observation.environment_state = 목표 정보(도면에서 계산한 그 벽돌의 목표 x·y·z·yaw + 반장 표시 1/0).
- 정책 관측이 아닌 것(info.*, LeRobot은 observation.*·action만 정책 입력으로 씀): 집게 닫힘 각도, 손목 힘·토크, 현재 벽돌 참값 자세,
  벽돌 16장 참값 자세, 대본 단계. 에피소드·벽 메타데이터(벽 번호, 자리 단·순서, 시작값, IoU, 판정)는 meta/wall3_*.json.
- 다 만든 뒤 LeRobot으로 다시 읽어 프레임 수·카메라·목표 정보를 검사하고, 파일 해시를 남긴다.

실행: cd sim && source venv/bin/activate && python -m wall3.to_lerobot --raw outputs/wall3/<수집> --root data/wall3_pilot_<YYYYMMDD> [--all]
      (activate가 torchcodec용 LD_LIBRARY_PATH를 설정한다)
"""
import argparse, hashlib, json, time
from pathlib import Path

import numpy as np

SIM = Path(__file__).resolve().parents[1]
CAMS = ("front", "top", "wrist")
JOINTS = ["shoulder_pan", "shoulder_lift", "elbow", "wrist_1", "wrist_2", "wrist_3"]
TASK = "Lay the next brick of the wall at its target position."


def features(img=128):
    f = {f"observation.images.{c}": {"dtype": "video", "shape": (img, img, 3), "names": ["height", "width", "channels"]} for c in CAMS}
    f["observation.state"] = {"dtype": "float32", "shape": (7,), "names": JOINTS + ["gripper"]}
    f["observation.environment_state"] = {"dtype": "float32", "shape": (5,),
                                          "names": ["target_x", "target_y", "target_z", "target_yaw", "target_is_half"]}
    f["action"] = {"dtype": "float32", "shape": (7,), "names": JOINTS + ["gripper"]}
    f["info.gripper_closure"] = {"dtype": "float32", "shape": (1,), "names": ["closure"]}
    f["info.wrist_ft"] = {"dtype": "float32", "shape": (6,), "names": ["fx", "fy", "fz", "tx", "ty", "tz"]}
    f["info.brick_pose"] = {"dtype": "float32", "shape": (7,), "names": ["x", "y", "z", "qw", "qx", "qy", "qz"]}
    f["info.all_brick_poses"] = {"dtype": "float32", "shape": (112,), "names": [f"b{i}_{c}" for i in range(16) for c in "xyzwijk"]}
    f["info.phase"] = {"dtype": "float32", "shape": (1,), "names": ["phase_id"]}
    return f


def target_of(slot):
    return np.array([slot["x"], slot["y"], slot["z"], slot["yaw"], 1.0 if slot["half"] else 0.0], np.float32)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def build(raw_dir: Path, root: Path, repo_id: str, include_all: bool):
    from lerobot.datasets.lerobot_dataset import LeRobotDataset
    walls = sorted(raw_dir.glob("raw/wall_*.json"), key=lambda p: int(p.stem.split("_")[1]))
    infos = [json.loads(p.read_text()) for p in walls]
    use = [w for w in infos if include_all or (w["eval"]["spec_pass"] and not w.get("fail"))]
    if not use:
        raise SystemExit("변환할 벽이 없음")
    ds = LeRobotDataset.create(repo_id, fps=20, features=features(), root=str(root), robot_type="ur10e_robotiq2f140", use_videos=True)
    ep_meta, wall_meta = [], []
    ep = 0
    t0 = time.time()
    for wi, w in enumerate(use):
        with np.load(raw_dir / "raw" / w["raw_file"]) as zf:      # decompress each array once (indexing an NpzFile
            z = {k: zf[k] for k in zf.files}                     # re-reads the whole array every time)
        assert np.array_equal(z["t"], np.arange(len(z["t"]))), "steps must be contiguous"
        for b in w["bricks"]:
            k = b["slot"]
            s = w["design"][k]
            tgt = target_of(s)
            for i in range(b["start"], b["end"]):
                ds.add_frame({"task": TASK,
                              **{f"observation.images.{c}": z[f"img_{c}"][i] for c in CAMS},
                              "observation.state": z["state"][i],
                              "observation.environment_state": tgt,
                              "action": z["action"][i],
                              "info.gripper_closure": np.array([z["closure"][i]], np.float32),
                              "info.wrist_ft": z["ft"][i],
                              "info.brick_pose": z["bricks"][i][k],
                              "info.all_brick_poses": z["bricks"][i].reshape(-1),
                              "info.phase": np.array([z["phase"][i]], np.float32)})
            ds.save_episode()
            ep_meta.append({"episode_index": ep, "wall_index": wi, "seed": w["seed"], "slot": k, "course": s["course"],
                            "position": s["index"], "half": s["half"], "start_step": b["start"], "end_step": b["end"],
                            "frames": b["end"] - b["start"], "duration_s": b["duration_s"], "target": tgt.tolist(),
                            "base_dist_m": w["base_dist_m"][k], "iou": w["eval"]["iou"][k], "end_err_mm": b["end_err_mm"],
                            "wall_spec_pass": w["eval"]["spec_pass"]})
            ep += 1
        wall_meta.append({"wall_index": wi, "seed": w["seed"], "spec_pass": w["eval"]["spec_pass"], "eval": w["eval"],
                          "raw_file": w["raw_file"], "raw_sha256": w["raw_sha256"], "marks": [[b["slot"], b["start"], b["end"]] for b in w["bricks"]]})
        print(f"wall {w['seed']}: 16 episodes ({ep} total, {time.time() - t0:.0f} s)", flush=True)
    ds.finalize()
    meta = root / "meta"
    (meta / "wall3_episodes.json").write_text(json.dumps(ep_meta, indent=1, default=float))
    (meta / "wall3_walls.json").write_text(json.dumps(wall_meta, indent=1, default=float))
    (meta / "wall3_source.json").write_text(json.dumps({"raw_dir": str(raw_dir), "collect_config": json.loads((raw_dir / "collect_config.json").read_text()),
                                                        "include_all": include_all, "n_walls_raw": len(infos), "n_walls_used": len(use),
                                                        "task": TASK, "features": features()}, indent=1, default=float))
    return ep_meta


def verify(root: Path, repo_id: str, ep_meta):
    """Read back with LeRobot: episode count, frames per episode, cameras, target info per episode."""
    from lerobot.datasets.lerobot_dataset import LeRobotDataset
    ds = LeRobotDataset(repo_id, root=str(root), video_backend="pyav")
    rep = {"num_episodes": ds.num_episodes, "num_frames": ds.num_frames, "expected_episodes": len(ep_meta),
           "expected_frames": int(sum(e["frames"] for e in ep_meta)), "camera_keys": list(ds.meta.camera_keys), "problems": []}
    if ds.num_episodes != len(ep_meta):
        rep["problems"].append("episode count")
    if ds.num_frames != rep["expected_frames"]:
        rep["problems"].append("frame count")
    if sorted(ds.meta.camera_keys) != sorted(f"observation.images.{c}" for c in CAMS):
        rep["problems"].append("cameras")
    eps = ds.meta.episodes
    for e in ep_meta:
        i = e["episode_index"]
        a, b = int(eps["dataset_from_index"][i]), int(eps["dataset_to_index"][i])
        if b - a != e["frames"]:
            rep["problems"].append(f"episode {i} length {b - a} != {e['frames']}")
        for j in (a, (a + b) // 2, b - 1):
            item = ds[j]
            if int(item["episode_index"]) != i:
                rep["problems"].append(f"frame {j} episode index")
            if not np.allclose(item["observation.environment_state"].numpy(), e["target"], atol=1e-6):
                rep["problems"].append(f"episode {i} frame {j} target")
            for c in CAMS:
                if tuple(item[f"observation.images.{c}"].shape) != (3, 128, 128):
                    rep["problems"].append(f"episode {i} frame {j} {c} shape {tuple(item[f'observation.images.{c}'].shape)}")
    rep["checked_frames"] = 3 * len(ep_meta)
    rep["ok"] = not rep["problems"]
    return rep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", required=True, help="collect.py output folder")
    ap.add_argument("--root", required=True, help="new dataset folder (sim/data/wall3_pilot_<YYYYMMDD>)")
    ap.add_argument("--repo-id", default="")
    ap.add_argument("--all", action="store_true", help="include walls that failed the spec (smoke check only)")
    a = ap.parse_args()
    root = Path(a.root)
    if root.exists():
        raise SystemExit(f"{root} 이미 있음: 덮어쓰지 않음")
    repo_id = a.repo_id or f"local/{root.name}"
    t0 = time.time()
    ep_meta = build(Path(a.raw), root, repo_id, a.all)
    t_build = time.time() - t0
    rep = verify(root, repo_id, ep_meta)
    files = sorted(p for p in root.rglob("*") if p.is_file() and p.name != "wall3_hashes.json")
    hashes = {str(p.relative_to(root)): sha256(p) for p in files}
    total = hashlib.sha256("".join(f"{k}:{v}\n" for k, v in hashes.items()).encode()).hexdigest()
    size = sum(p.stat().st_size for p in files)
    (root / "meta" / "wall3_hashes.json").write_text(json.dumps({"dataset_sha256": total, "bytes": size, "files": hashes}, indent=1))
    rep.update(dataset_sha256=total, bytes=size, build_s=t_build)
    (root / "meta" / "wall3_verify.json").write_text(json.dumps(rep, indent=1, default=float))
    print(json.dumps({k: v for k, v in rep.items() if k != "problems"}, indent=1, default=float), "\nproblems:", rep["problems"][:10])
    if not rep["ok"]:
        raise SystemExit("verification failed")


if __name__ == "__main__":
    main()
