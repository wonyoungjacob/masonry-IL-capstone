"""건식 시연 원자료 → LeRobot 데이터셋(v3). 벽돌 한 장 = 에피소드 1개. wall3.to_lerobot와 같은 구조.

- 깨끗한 합격 벽만 넣는다(시방 합격 + 완주 + 과부하 해제 0번).
- 정책 관측: observation.images.<카메라>(원본을 비율 유지로 줄인 224 × 168을 위아래 28줄씩 채운 224 × 224), observation.state
  (관절 6 + 집게), observation.environment_state(목표 x · y · z · yaw + 반장). 목표 z는 건식 설계 높이.
- info.*(정책 입력 아님): 집게 닫힘, 손목 힘 · 토크, 현재 벽돌 참값 자세, 벽돌 16장 참값 자세, 대본 단계, 쥠 고정 상태.
- 한 번에(master): 기록한 카메라를 모두 넣은 데이터셋 하나. 세팅별 데이터셋은 --subset으로 master에서 카메라만 골라 만든다
  (LeRobot의 remove_feature: 영상은 다시 인코딩하지 않고 복사).
- 다 만든 뒤 다시 읽기 검사, 원자료와 숫자 열 비교, 영상 전수 디코딩 검사(wall3.check_videos), 해시.

실행: cd sim && source venv/bin/activate && PYTHONPATH=. python -m prl.to_lerobot --raw outputs/prl/<수집> --root data/<이름> [--part I N]
      합치기: python -m prl.to_lerobot --merge <part0> <part1> ... --root data/<이름>
      세팅별: python -m prl.to_lerobot --subset data/<master> --cams SB1 WC1 H0 --root data/<이름>
"""
import argparse, hashlib, json, subprocess, sys, time
from pathlib import Path

import numpy as np

from prl.collect import load_images, IMG_H, IMG_W
from wall3.to_lerobot import JOINTS, TASK, target_of, sha256, _table, content_sha256

SIM = Path(__file__).resolve().parents[1]
SIZE = 224
PAD = (SIZE - IMG_H) // 2


def features(cams):
    f = {f"observation.images.{c}": {"dtype": "video", "shape": (SIZE, SIZE, 3), "names": ["height", "width", "channels"]} for c in cams}
    f["observation.state"] = {"dtype": "float32", "shape": (7,), "names": JOINTS + ["gripper"]}
    f["observation.environment_state"] = {"dtype": "float32", "shape": (5,),
                                          "names": ["target_x", "target_y", "target_z", "target_yaw", "target_is_half"]}
    f["action"] = {"dtype": "float32", "shape": (7,), "names": JOINTS + ["gripper"]}
    f["info.gripper_closure"] = {"dtype": "float32", "shape": (1,), "names": ["closure"]}
    f["info.wrist_ft"] = {"dtype": "float32", "shape": (6,), "names": ["fx", "fy", "fz", "tx", "ty", "tz"]}
    f["info.brick_pose"] = {"dtype": "float32", "shape": (7,), "names": ["x", "y", "z", "qw", "qx", "qy", "qz"]}
    f["info.all_brick_poses"] = {"dtype": "float32", "shape": (112,), "names": [f"b{i}_{c}" for i in range(16) for c in "xyzwijk"]}
    f["info.phase"] = {"dtype": "float32", "shape": (1,), "names": ["phase_id"]}
    f["info.grip_lock"] = {"dtype": "float32", "shape": (4,), "names": ["locked", "lock_brick", "pad_n_left", "pad_n_right"]}
    return f


def pad_frames(frames):
    """(T, 168, 224, 3) → (T, 224, 224, 3): the letterboxed policy input."""
    out = np.zeros((len(frames), SIZE, SIZE, 3), np.uint8)
    out[:, PAD:PAD + IMG_H] = frames
    return out


def wall_infos(raw_dirs):
    infos = []
    for rd in raw_dirs:
        for p in rd.glob("raw/wall_*.json"):
            w = json.loads(p.read_text())
            w["_raw_dir"] = rd
            infos.append(w)
    infos.sort(key=lambda w: w["seed"])
    if len({w["seed"] for w in infos}) != len(infos):
        raise SystemExit("같은 시작값이 두 번 들어 있음")
    return infos


def build(raw_dirs, root: Path, repo_id: str, max_walls=0, video_mb=50, part=None, threads=4):
    from lerobot.datasets.lerobot_dataset import LeRobotDataset
    infos = wall_infos(raw_dirs)
    use = [w for w in infos if w["clean_pass"]]
    if max_walls:
        if len(use) < max_walls:
            raise SystemExit(f"깨끗한 합격 벽 {len(use)}개 < 요청 {max_walls}개")
        use = use[:max_walls]
    selected = use
    if part is not None:
        i, n = part
        bounds = np.linspace(0, len(use), n + 1).round().astype(int)
        use = use[bounds[i]:bounds[i + 1]]
    if not use:
        raise SystemExit("변환할 벽이 없음")
    cams = use[0]["cams"]
    ds = LeRobotDataset.create(repo_id, fps=20, features=features(cams), root=str(root), robot_type="ur10e_robotiq2f140",
                               use_videos=True, video_files_size_in_mb=video_mb, streaming_encoding=True, encoder_threads=threads,
                               encoder_queue_maxsize=2000)   # the streaming encoder DROPS frames when its queue is full
                                                             # (made for live recording): the queue must hold a whole episode
    ep_meta, wall_meta = [], []
    ep = 0
    t0 = time.time()
    for wi, w in enumerate(use):
        assert w["cams"] == cams, "raw walls recorded different cameras"
        with np.load(w["_raw_dir"] / "raw" / w["raw_file"]) as zf:
            z = {k: zf[k] for k in zf.files if not k.startswith("imgd_")}
            img = {c: load_images(zf, c) for c in cams}                  # unpadded (padding per frame keeps the memory at one wall)
        assert np.array_equal(z["t"], np.arange(len(z["t"]))), "steps must be contiguous"
        for b in w["bricks"]:
            k = b["slot"]
            s = w["design"][k]
            tgt = target_of(s)
            for i in range(b["start"], b["end"]):
                ds.add_frame({"task": TASK,
                              **{f"observation.images.{c}": pad_frames(img[c][i:i + 1])[0] for c in cams},
                              "observation.state": z["state"][i],
                              "observation.environment_state": tgt,
                              "action": z["action"][i],
                              "info.gripper_closure": np.array([z["closure"][i]], np.float32),
                              "info.wrist_ft": z["ft"][i],
                              "info.brick_pose": z["bricks"][i][k],
                              "info.all_brick_poses": z["bricks"][i].reshape(-1),
                              "info.phase": np.array([z["phase"][i]], np.float32),
                              "info.grip_lock": z["lock"][i]})
            ds.save_episode()
            ep_meta.append({"episode_index": ep, "wall_index": wi, "seed": w["seed"], "slot": k, "course": s["course"],
                            "position": s["index"], "half": s["half"], "start_step": b["start"], "end_step": b["end"],
                            "frames": b["end"] - b["start"], "duration_s": b["duration_s"], "target": tgt.tolist(),
                            "end_err_mm": b["end_err_mm"], "wall_spec_pass": w["eval"]["spec_pass"]})
            ep += 1
        wall_meta.append({"wall_index": wi, "seed": w["seed"], "spec_pass": w["eval"]["spec_pass"],
                          "raw_dir": str(w["_raw_dir"]), "raw_file": w["raw_file"], "raw_sha256": w["raw_sha256"],
                          "marks": [[b["slot"], b["start"], b["end"]] for b in w["bricks"]]})
        print(f"wall {w['seed']}: 16 episodes ({ep} total, {time.time() - t0:.0f} s)", flush=True)
    ds.finalize()
    meta = root / "meta"
    (meta / "prl_episodes.json").write_text(json.dumps(ep_meta, indent=1, default=float))
    (meta / "prl_walls.json").write_text(json.dumps(wall_meta, indent=1, default=float))
    (meta / "prl_source.json").write_text(json.dumps({
        "raw_dirs": [str(r) for r in raw_dirs], "collect_configs": [json.loads((r / "collect_config.json").read_text()) for r in raw_dirs],
        "max_walls": max_walls, "video_files_size_in_mb": video_mb, "n_walls_raw": len(infos), "n_walls_used": len(use), "part": part,
        "cams": cams, "seeds_used": [w["seed"] for w in use], "seeds_not_used": [w["seed"] for w in infos if w not in selected],
        "task": TASK}, indent=1, default=float))
    return ep_meta


def merge(part_roots, root: Path, repo_id: str, video_mb=50):
    from lerobot.datasets.aggregate import aggregate_datasets
    part_roots = [Path(r) for r in part_roots]
    aggregate_datasets([f"local/{r.name}" for r in part_roots], repo_id, roots=part_roots, aggr_root=root, video_files_size_in_mb=video_mb)
    ep_meta, wall_meta, src = [], [], []
    for r in part_roots:
        e = json.loads((r / "meta" / "prl_episodes.json").read_text())
        w = json.loads((r / "meta" / "prl_walls.json").read_text())
        de, dw = len(ep_meta), len(wall_meta)
        ep_meta += [dict(x, episode_index=x["episode_index"] + de, wall_index=x["wall_index"] + dw) for x in e]
        wall_meta += [dict(x, wall_index=x["wall_index"] + dw) for x in w]
        src.append(json.loads((r / "meta" / "prl_source.json").read_text()))
    seeds = [w["seed"] for w in wall_meta]
    if seeds != sorted(seeds) or len(set(seeds)) != len(seeds):
        raise SystemExit("parts are not in seed order")
    meta = root / "meta"
    (meta / "prl_episodes.json").write_text(json.dumps(ep_meta, indent=1, default=float))
    (meta / "prl_walls.json").write_text(json.dumps(wall_meta, indent=1, default=float))
    (meta / "prl_source.json").write_text(json.dumps({"merged_from": [str(r) for r in part_roots], "parts": src, "seeds_used": seeds,
                                                      "n_walls_used": len(seeds), "cams": src[0]["cams"], "task": TASK}, indent=1, default=float))


def subset(master: Path, cams, root: Path, repo_id: str):
    """Dataset of one setting: the master with only `cams` (videos copied, not re-encoded)."""
    from lerobot.datasets.lerobot_dataset import LeRobotDataset
    from lerobot.datasets.dataset_tools import remove_feature
    src = json.loads((master / "meta" / "prl_source.json").read_text())
    missing = [c for c in cams if c not in src["cams"]]
    if missing:
        raise SystemExit(f"master에 없는 카메라: {missing}")
    drop = [f"observation.images.{c}" for c in src["cams"] if c not in cams]
    ds = LeRobotDataset(f"local/{master.name}", root=str(master))
    remove_feature(ds, drop, output_dir=str(root), repo_id=repo_id)
    for name in ("prl_episodes.json", "prl_walls.json"):
        (root / "meta" / name).write_text((master / "meta" / name).read_text())
    (root / "meta" / "prl_source.json").write_text(json.dumps(dict(src, subset_of=str(master), cams=list(cams), cams_master=src["cams"]),
                                                              indent=1, default=float))


def check_raw(root: Path, cams, n_img_walls=2):
    """Numeric columns equal the raw recording slices; for a few walls the decoded video frames are close to the raw frames."""
    ep_meta = json.loads((root / "meta" / "prl_episodes.json").read_text())
    wall_meta = json.loads((root / "meta" / "prl_walls.json").read_text())
    tab = _table(root)
    problems = []
    if not np.array_equal(tab["index"], np.arange(len(tab["index"]))):
        problems.append("index not contiguous")
    by_wall = {}
    for e in ep_meta:
        by_wall.setdefault(e["wall_index"], []).append(e)
    pos = 0
    keys = {"action": "action", "observation.state": "state", "info.wrist_ft": "ft", "info.grip_lock": "lock"}
    for w in wall_meta:
        with np.load(Path(w["raw_dir"]) / "raw" / w["raw_file"]) as zf:
            z = {k: zf[k] for k in ("action", "state", "ft", "closure", "phase", "bricks", "lock")}
        for e in by_wall[w["wall_index"]]:
            a, b = e["start_step"], e["end_step"]
            sl = slice(pos, pos + (b - a))
            if not np.array_equal(tab["episode_index"][sl], np.full(b - a, e["episode_index"])):
                problems.append(f"episode {e['episode_index']} rows")
            for col, rk in keys.items():
                if not np.array_equal(tab[col][sl], z[rk][a:b].reshape(b - a, -1)):
                    problems.append(f"episode {e['episode_index']} {col}")
            if not np.array_equal(tab["info.brick_pose"][sl], z["bricks"][a:b, e["slot"]]):
                problems.append(f"episode {e['episode_index']} brick pose")
            if not np.allclose(tab["observation.environment_state"][sl], np.asarray(e["target"], np.float32)[None], atol=0):
                problems.append(f"episode {e['episode_index']} target")
            pos += b - a
    if pos != len(tab["index"]):
        problems.append(f"rows {len(tab['index'])} != episodes {pos}")
    # decoded frames against the raw frames (video compression is lossy: mean absolute difference must stay small)
    from lerobot.datasets.lerobot_dataset import LeRobotDataset
    ds = LeRobotDataset(f"local/{root.name}", root=str(root), video_backend="pyav")
    rng = np.random.default_rng(0)
    mad = {c: [] for c in cams}
    pick = sorted(rng.choice(len(wall_meta), size=min(n_img_walls, len(wall_meta)), replace=False).tolist())
    for wi in pick:
        w = wall_meta[wi]
        first = sum(e["frames"] for e in ep_meta if e["wall_index"] < wi)
        with np.load(Path(w["raw_dir"]) / "raw" / w["raw_file"]) as zf:
            raw = {c: load_images(zf, c) for c in cams}
        offs = np.cumsum([0] + [e["frames"] for e in by_wall[wi]])
        for e, o in zip(by_wall[wi], offs):
            for j in (0, e["frames"] // 2, e["frames"] - 1):
                item = ds[int(first + o + j)]
                for c in cams:
                    dec = (item[f"observation.images.{c}"].numpy().transpose(1, 2, 0) * 255.0)
                    ref = raw[c][e["start_step"] + j].astype(np.float32)
                    mad[c].append(float(np.abs(dec[PAD:PAD + IMG_H] - ref).mean()))
                    # padding stays black (the rows next to the picture ring a little after video compression: skipped)
                    if float(dec[:PAD - 6].mean()) > 2 or float(dec[PAD + IMG_H + 6:].mean()) > 2:
                        problems.append(f"wall {w['seed']} {c}: padding not black")
    img = {c: {"mean_abs_diff": float(np.mean(v)), "max_abs_diff": float(np.max(v))} for c, v in mad.items()}
    for c, v in img.items():
        if v["max_abs_diff"] > 6.0:
            problems.append(f"{c}: decoded frames differ from raw (mean abs diff up to {v['max_abs_diff']:.1f} of 255)")
    rep = {"rows": int(len(tab["index"])), "episodes_checked": len(ep_meta), "walls_checked": len(wall_meta), "image_walls": [wall_meta[i]["seed"] for i in pick],
           "image_diff": img, "num_episodes": ds.num_episodes, "num_frames": ds.num_frames,
           "expected_frames": int(sum(e["frames"] for e in ep_meta)), "camera_keys": list(ds.meta.camera_keys), "problems": problems[:50]}
    if ds.num_episodes != len(ep_meta) or ds.num_frames != rep["expected_frames"]:
        rep["problems"].append("episode / frame count")
    if sorted(ds.meta.camera_keys) != sorted(f"observation.images.{c}" for c in cams):
        rep["problems"].append("cameras")
    rep["ok"] = not rep["problems"]
    return rep


def finish(root: Path, cams, t_build):
    rep = check_raw(root, cams)
    r = subprocess.run([sys.executable, "-m", "wall3.check_videos", "--root", str(root), "--out", str(root / "meta" / "prl_check_videos.json")],
                       capture_output=True, text=True, cwd=SIM)
    rep["videos_all_decode"] = r.returncode == 0
    rep["content_sha256"] = content_sha256(root)
    rep["ok"] = bool(rep["ok"] and rep["videos_all_decode"])
    files = sorted(p for p in root.rglob("*") if p.is_file() and p.name != "prl_hashes.json")
    hashes = {str(p.relative_to(root)): sha256(p) for p in files}
    total = hashlib.sha256("".join(f"{k}:{v}\n" for k, v in hashes.items()).encode()).hexdigest()
    size = sum(p.stat().st_size for p in files)
    (root / "meta" / "prl_hashes.json").write_text(json.dumps({"dataset_sha256": total, "bytes": size, "files": hashes}, indent=1))
    rep.update(dataset_sha256=total, bytes=size, build_s=t_build)
    (root / "meta" / "prl_verify.json").write_text(json.dumps(rep, indent=1, default=float))
    print(json.dumps({k: v for k, v in rep.items() if k != "problems"}, indent=1, default=float), "\nproblems:", rep["problems"][:10])
    if not rep["ok"]:
        raise SystemExit("verification failed")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", nargs="+", default=None)
    ap.add_argument("--root", required=True)
    ap.add_argument("--max-walls", type=int, default=0)
    ap.add_argument("--video-mb", type=int, default=50)
    ap.add_argument("--part", type=int, nargs=2, default=None, metavar=("I", "N"))
    ap.add_argument("--merge", nargs="+", default=None)
    ap.add_argument("--subset", default=None, help="master dataset folder")
    ap.add_argument("--cams", nargs="*", default=None, help="cameras of the subset")
    ap.add_argument("--threads", type=int, default=4, help="encoder threads per camera stream")
    ap.add_argument("--no-verify", action="store_true", help="parts: verified after the merge")
    a = ap.parse_args()
    root = Path(a.root)
    if root.exists():
        raise SystemExit(f"{root} 이미 있음: 덮어쓰지 않음")
    repo_id = f"local/{root.name}"
    t0 = time.time()
    if a.subset:
        subset(Path(a.subset), a.cams, root, repo_id)
        cams = a.cams
    elif a.merge:
        merge(a.merge, root, repo_id, a.video_mb)
        cams = json.loads((root / "meta" / "prl_source.json").read_text())["cams"]
    else:
        build([Path(r) for r in a.raw], root, repo_id, a.max_walls, a.video_mb, tuple(a.part) if a.part else None, a.threads)
        cams = json.loads((root / "meta" / "prl_source.json").read_text())["cams"]
    if a.no_verify:
        print(f"built {root} ({time.time() - t0:.0f} s), not verified")
        return
    finish(root, cams, time.time() - t0)


if __name__ == "__main__":
    main()
