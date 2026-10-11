# -*- coding: utf-8 -*-
"""v9 영상: 7쪽 4칸 교체.
 (a) 11번 ACT 비교 클립 0~7.00 s  (b) 06번 Diffusion 성공 0~11 s
 (c) 빈손 운반: 대본의 집기 위치를 벽돌 끝 너머로 비켜 집게가 허공을 쥐고도 벽까지 운반·'놓기' (실패 유형 재현)
 (d) 복구 시연으로 학습한 Diffusion(실험 1 plus2, seed10000): 3개를 다 놓은 뒤에도 집게가 계속 오르내림 (원본 09, 14~50 s, 2배속)"""
import os, sys, subprocess, numpy as np, cv2, mujoco
from PIL import Image, ImageDraw
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from clips_existing import H264, frames, font, NAVY, OUT as VOUT, FFMPEG
ROOT = r"C:/Users/user/Desktop/사기설"
sys.path.insert(0, ROOT + "/sim")
from brick_sim.scene import BrickEnv, blueprint_config, JAW_OPEN
from brick_sim.expert import ScriptedExpert
POST = ROOT + "/01_사기설/중간발표1/도구/v9_자산/"; os.makedirs(POST, exist_ok=True)
INK = (0x24, 0x35, 0x49)


def trim(src, dst, t1):
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", VOUT + src, "-t", f"{t1:.2f}", "-an", "-c:v", "libx264", "-preset", "medium",
                    "-crf", "20", "-pix_fmt", "yuv420p", "-movflags", "+faststart", VOUT + dst], check=True)


def poster(name, frac):
    v = cv2.VideoCapture(VOUT + name); N = int(v.get(cv2.CAP_PROP_FRAME_COUNT)); v.set(cv2.CAP_PROP_POS_FRAMES, int(N * frac)); ok, f = v.read()
    p = POST + "poster_" + name.split("_")[0] + ".png"; Image.fromarray(cv2.cvtColor(f, cv2.COLOR_BGR2RGB)).save(p); return p


def clip_fumble():
    wr = H264(VOUT + "22_복구시연학습_Diffusion_놓고도더듬거림_2배속.mp4", 1080, 500)
    for k, (t, f) in enumerate(frames("09_실험1_Diffusion_plus2_정밀도확인_seed10000.mp4", 14, 50)):
        if k % 2:
            continue
        c = Image.new("RGB", (1080, 500), "white"); d = ImageDraw.Draw(c)
        c.paste(Image.fromarray(f[60:420]), (0, 60))
        d.rectangle((0, 0, 1080, 60), fill=NAVY)
        d.text((14, 8), "복구 시연을 섞어 학습한 Diffusion Policy (실험 1, 학습 데이터 plus2) — 정책 자율 실행", font=font(22, True), fill="white")
        d.text((14, 36), "앞 · 위 · 손목 카메라 · 2배속 · 24초에 3개를 다 놓은 뒤에도 집게가 계속 오르내림", font=font(17), fill=(0xc2, 0xd8, 0xe8))
        d.rectangle((0, 420, 1080, 500), fill=(0xf4, 0xf6, 0xf8))
        st = "세 번째 벽돌 놓는 중" if t < 24 else "다 놓았는데도 더듬거림"
        d.text((14, 432), f"{t:5.1f} s   {st}", font=font(20, True), fill=INK)
        wr.write(c)
    wr.hold(10); wr.close()


def clip_empty_carry(seed=40000, sign=+1):
    env = BrickEnv(blueprint_config('mortarB', size_rand=0, pos_rand=.03, supply_yaw_deg=60, valid_supply=True, feasible_supply=True))
    env.reset(seed)
    ex = ScriptedExpert(env, seed=seed, max_retries=0, clean_single_pass=True)
    ex.dt = env.cfg.ctrl_dt; ex.q_prev = env.data.qpos[env.arm_qidx].copy()
    p, R = env.tcp_pose(); ex.p_prev = p; ex.yaw_prev = float(np.arctan2(R[1, 0], R[0, 0])); ex.jaw_prev = JAW_OPEN
    ex.n_fail = 0; ex.events = []; ex.recoveries = 0; ex.unrecoverable = []; ex.place_bias = {}; ex.log = []
    ex.order = sorted(range(env.n_bricks), key=lambda b: env.brick_pose(b)[0][0]); ex.slot = {b: k for k, b in enumerate(ex.order)}
    ex._monitor_grasp = False
    i = ex.order[0]; segs = ex.plan_brick(i)
    yaw_g = segs[0][1]; long_ax = np.array([np.cos(yaw_g - np.pi / 2), np.sin(yaw_g - np.pi / 2), 0.0])
    off = sign * (env.brick.L / 2 + 0.022) * long_ax
    segs = [((np.asarray(tp) + (off if k < 4 else 0)), yw, jw, du, "lin" if md == "servo" else md) for k, (tp, yw, jw, du, md) in enumerate(segs)]
    segs.append((np.asarray(segs[-1][0]) + np.array([0.06, 0.06, 0.05]), segs[-1][1], JAW_OPEN, 1.0, "polar"))
    R1 = mujoco.Renderer(env.model, 480, 480); fr = []
    orig = env.step

    def step(a):
        orig(a)
        if env.t % 2 == 0:
            R1.update_scene(env.data, camera="front"); a1 = R1.render().copy()
            R1.update_scene(env.data, camera="wrist"); a2 = R1.render().copy()
            fr.append((env.t * env.cfg.ctrl_dt, a1, a2, float(env.data.qpos[env.jaw_qidx]), bool(env.grasped(i))))
    env.step = step
    try:
        ex._run_segments(segs, i, None, 0.004)
        env.settle(10)
    finally:
        env.step = orig
    R1.close()
    held_any = any(g for *_, g in fr)
    name = f"21_빈손운반_재현_seed{seed}.mp4"
    wr = H264(VOUT + name, 1100, 620)
    for t, a1, a2, jaw, g in fr:
        c = Image.new("RGB", (1100, 620), "white"); d = ImageDraw.Draw(c)
        d.rectangle((0, 0, 1100, 54), fill=NAVY)
        d.text((16, 12), "집지 못했는데도 그대로 운반해 '놓기'까지 진행 (실험 2 정책 실패 유형을 대본으로 재현)", font=font(21, True), fill="white")
        c.paste(Image.fromarray(a1).resize((480, 480)), (50, 70)); c.paste(Image.fromarray(a2).resize((480, 480)), (570, 70))
        d.text((50, 556), "앞 카메라", font=font(18, True), fill=INK); d.text((570, 556), "손목 카메라", font=font(18, True), fill=INK)
        phase = "벽돌 옆을 쥠 (헛집기)" if t < 2.1 else ("빈손으로 벽까지 운반" if t < 4.4 else "빈손으로 '놓기'")
        d.text((50, 586), f"{t:4.1f} s   {phase} · 벽돌을 쥐고 있나: {'예' if g else '아니오'}", font=font(18), fill=INK)
        wr.write(c)
    wr.hold(12); wr.close()
    return name, held_any


if __name__ == "__main__":
    trim("11_실험1성공_vs_실험2실패_ACT_3배속.mp4", "11_실험1성공_vs_실험2실패_ACT_3배속_0-7s.mp4", 7.0)
    trim("06_실험2_Diffusion_성공_2배속_seed50002.mp4", "06_실험2_Diffusion_성공_2배속_0-11s.mp4", 11.0)
    clip_fumble()
    for sign in (+1, -1):
        name, held = clip_empty_carry(40000, sign)
        print("empty carry", name, "sign", sign, "ever grasped:", held, flush=True)
        if not held:
            break
    for n, fr in [("11_실험1성공_vs_실험2실패_ACT_3배속_0-7s.mp4", 0.85), ("06_실험2_Diffusion_성공_2배속_0-11s.mp4", 0.7),
                  (name, 0.5), ("22_복구시연학습_Diffusion_놓고도더듬거림_2배속.mp4", 0.55)]:
        print("poster", poster(n, fr))
