"""Midterm-1 slide 6 (2026-10-12): replay an experiment-1 (narrow layout) Diffusion policy on layout seed 10000 and save the
front/top/wrist video, so the clean-trained and the recovery-mixed (plus2) policies can be shown side by side under the same
conditions.  Presentation only; never touches benchmark result files.

    cd sim
    MUJOCO_GL=egl venv/bin/python tools/render_exp1_pair.py diffusion_v2_2p1_joint_image_clean
    MUJOCO_GL=egl venv/bin/python tools/render_exp1_pair.py diffusion_v2_2p1_joint_image_plus2

Same initial layout and inference seed as the 2026-09-22 presentation clip 09 (plus2, seed 10000, inference 70000).
Writes outputs/midterm1_fix/exp1_<run>_seed10000.{mp4,json} and _trace.json.
"""
import os, sys, json, shutil, subprocess
os.environ.setdefault("MUJOCO_GL", "egl"); os.environ.setdefault("HF_HUB_OFFLINE", "1")
from pathlib import Path
import numpy as np, torch, mujoco
from PIL import Image, ImageDraw, ImageFont

SIM = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(SIM))
from brick_sim.scene import BrickEnv, blueprint_config
from brick_sim.metrics import compute_metrics
from eval_policy import load_policy, camera_sources, build_obs

RUN = sys.argv[1]
SEED, INF = 10000, 70000
OUT = SIM / "outputs" / "midterm1_fix"; OUT.mkdir(parents=True, exist_ok=True)
W, H = 1080, 440
fp = SIM / "tools" / "fonts" / "NotoSansKR-Regular.ttf"
F = ImageFont.truetype(str(fp), 18) if fp.exists() else ImageFont.load_default()
FS = ImageFont.truetype(str(fp), 15) if fp.exists() else ImageFont.load_default()
ff = shutil.which("ffmpeg")
if ff is None:
    import imageio_ffmpeg
    ff = imageio_ffmpeg.get_ffmpeg_exe()
name = f"exp1_{RUN}_seed{SEED}"
proc = subprocess.Popen([ff, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", "10", "-i", "-",
                         "-an", "-c:v", "libx264", "-preset", "fast", "-crf", "20", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                         str(OUT / f"{name}.mp4")], stdin=subprocess.PIPE)

cfg = blueprint_config("mortarB", size_rand=0, pos_rand=.005, supply_yaw_deg=10, valid_supply=False)   # experiment-1 layout range
env = BrickEnv(cfg); env.reset(SEED)
R = mujoco.Renderer(env.model, 360, 360)
ckpt = SIM / "outputs" / RUN / "checkpoints" / "last" / "pretrained_model"
policy, pcfg, pre, post = load_policy(str(ckpt), "cuda" if torch.cuda.is_available() else "cpu", None, None)
cam = camera_sources(pcfg, None)
torch.manual_seed(INF)
if torch.cuda.is_available():
    torch.cuda.manual_seed_all(INF)
policy.reset()
trace = []


def frame(status):
    c = Image.new("RGB", (W, H), "#142338"); d = ImageDraw.Draw(c)
    d.text((14, 6), f"실험 1 | {RUN}", font=F, fill="white")
    d.text((14, 31), f"초기 배치 seed {SEED} · 추론 seed {INF} · 정책 자율 실행", font=FS, fill="#c2d8e8")
    for k, cn in enumerate(["front", "top", "wrist"]):
        R.update_scene(env.data, camera=cn); c.paste(Image.fromarray(R.render()), (360 * k, 60))
        d.text((360 * k + 8, 64), cn.upper(), font=FS, fill="#142338")
    d.rectangle((0, 420, W, H), fill="#142338"); d.text((12, 421), f"{env.t * 0.05:5.1f}s  |  {status}", font=FS, fill="white")
    proc.stdin.write(c.tobytes())


frame("초기 상태")
for t in range(1800):
    obs = build_obs(env, cam, pcfg)
    with torch.inference_mode():
        act = post(policy.select_action(pre(obs)))
    env.step(act.squeeze(0).detach().cpu().numpy())
    if env.t % 2 == 0:
        frame("정책 실행 중")
    if env.t % 10 == 0:
        trace.append(dict(t=int(env.t), poses=env.brick_poses().tolist(), jaw=float(env.data.qpos[env.jaw_qidx])))
before = env.brick_poses().copy(); env.settle(50)
M = compute_metrics(env.brick_poses(), env.design, env.brick, cfg.wall, poses_before_settle=before)
for _ in range(20):
    frame(f"최종: 성공 블록 {round(M['m1_success_rate'] * 3)}/3, 평면 오차 평균 {M['m1_exy_mean_mm']:.1f} mm")
proc.stdin.close(); proc.wait(); R.close()
orig = None
ej = SIM / "outputs" / f"eval_{RUN}_mortarB.json"
if ej.exists():
    e = next((x for x in json.loads(ej.read_text())["episodes"] if x.get("seed") == SEED), None)
    if e:
        orig = dict(m1_all_success=e.get("m1_all_success"), m1_exy_mean_mm=e.get("m1_exy_mean_mm"))
meta = dict(run=RUN, seed=SEED, inference_seed=INF, metrics={k: v for k, v in M.items() if not isinstance(v, (list, dict))},
            original_eval_episode=orig)
(OUT / f"{name}.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2, default=float))
(OUT / f"{name}_trace.json").write_text(json.dumps(trace))
print("DONE", name, "all_success", M["m1_all_success"], "exy_mean_mm", round(M["m1_exy_mean_mm"], 2), "original", orig)
