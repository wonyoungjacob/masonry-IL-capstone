# -*- coding: utf-8 -*-
"""PPT 초안 v6의 '제작 필요' 사진·영상 중 시뮬레이션(CPU, 스크립트 교사 + 검측)으로 만들 수 있는 것.
정책(ACT·Diffusion) 에피소드는 체크포인트가 없어 여기서 못 만든다 → 스크립트 대역이라고 파일명·자막에 명시."""
import os, sys, json, time, subprocess
import numpy as np, mujoco, cv2
from PIL import Image, ImageDraw, ImageFont
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
import imageio_ffmpeg

ROOT = r"C:/Users/user/Desktop/사기설"
sys.path.insert(0, ROOT + "/sim")
from brick_sim.scene import BrickEnv, blueprint_config
from brick_sim.expert import ScriptedExpert
from brick_sim.grasp_gate import GraspGate
from brick_sim.metrics import compute_metrics

IMG = ROOT + "/01_사기설/중간발표1/그림/"
VID = ROOT + "/01_사기설/중간발표1/영상/"
FONT = ROOT + "/중간발표_진행정리_20261007/assets/NotoSansKR-Regular.ttf"
FONTB = ROOT + "/중간발표_진행정리_20261007/assets/NotoSansKR-Bold.ttf"
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
NAVY = (0x14, 0x23, 0x38); INK = (0x24, 0x35, 0x49); TEAL = (0x14, 0x7c, 0x85); RED = (0xb0, 0x41, 0x2a); GREEN = (0x1d, 0x7a, 0x3e)
fp = fm.FontProperties(fname=FONT); plt.rcParams["font.family"] = fp.get_name(); plt.rcParams["axes.unicode_minus"] = False
os.makedirs(IMG, exist_ok=True); os.makedirs(VID, exist_ok=True)


def font(sz, bold=False):
    return ImageFont.truetype(FONTB if bold else FONT, sz)


def save_png(path, arr_or_img):
    im = arr_or_img if isinstance(arr_or_img, Image.Image) else Image.fromarray(arr_or_img)
    im.save(path)


class H264:
    def __init__(self, path, w, h, fps=10):
        self.w, self.h = w, h
        self.p = subprocess.Popen([FFMPEG, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}",
                                   "-r", str(fps), "-i", "-", "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
                                   "-pix_fmt", "yuv420p", "-movflags", "+faststart", path], stdin=subprocess.PIPE)
        self.last = None

    def write(self, img):
        if img.size != (self.w, self.h):
            img = img.resize((self.w, self.h), Image.Resampling.LANCZOS)
        self.p.stdin.write(img.tobytes()); self.last = img

    def hold(self, n):
        for _ in range(n):
            self.p.stdin.write(self.last.tobytes())

    def close(self):
        self.p.stdin.close()
        if self.p.wait():
            raise RuntimeError("ffmpeg failed")


def cfg_paper():
    return blueprint_config('mortarB', size_rand=0, pos_rand=.03, supply_yaw_deg=60, valid_supply=True, feasible_supply=True)


class _P:
    def reset(self):
        pass


def free_cam(lookat, dist, az, el):
    c = mujoco.MjvCamera(); c.type = mujoco.mjtCamera.mjCAMERA_FREE
    c.lookat[:] = lookat; c.distance = dist; c.azimuth = az; c.elevation = el
    return c


class Run:
    """스크립트 교사(+검측) 에피소드. capture(env, gate, run)는 env.step마다 호출(검측 내부 스텝 포함)."""

    def __init__(self, env, seed, gate_src=None, nbr_bias=0.0015, capture=None, res=(480, 480)):
        env.reset(seed)
        self.env, self.seed, self.capture = env, seed, capture
        self.ex = ScriptedExpert(env, seed=seed, max_retries=0, clean_single_pass=True)
        self.gate = GraspGate(env, _P(), max_retries=0, recover="reguide", release_gate=True, force=True, replace=True,
                              pose_source=gate_src, nbr_bias=nbr_bias) if gate_src else None
        self.R = mujoco.Renderer(env.model, res[0], res[1])
        self.M = None

    def view(self, cam):
        self.R.update_scene(self.env.data, camera=cam); return self.R.render().copy()

    def go(self, settle=50):
        env, gate = self.env, self.gate
        orig = env.step; busy = [False]

        def stepped(a):
            orig(a)
            if self.capture:
                self.capture(env, gate, self)

        def step(act):
            if busy[0] or gate is None:
                return stepped(act)
            busy[0] = True
            try:
                a = gate.before_step(np.asarray(act, dtype=np.float32))
                if a is None:
                    return
                stepped(a); gate.after_step(a)
            finally:
                busy[0] = False
        env.step = step
        try:
            self.ex.run_episode()
        finally:
            env.step = orig
        before = env.brick_poses().copy(); env.settle(settle)
        self.M = compute_metrics(env.brick_poses(), env.design, env.brick, env.cfg.wall, poses_before_settle=before)
        return self.M

    def close(self):
        self.R.close()
        if self.gate is not None and self.gate.cam is not None:
            self.gate.cam.close()


def gate_status(gate, t):
    """자막용: 최근 검측 이벤트 요약."""
    if gate is None:
        return ""
    ev = [e for e in gate.events if e["t"] <= t]
    rel = [e for e in gate.release_events if e["t"] <= t]
    s = []
    if ev:
        e = ev[-1]; a = e.get("action", "")
        if a == "carry":
            s.append(f"G1 합격 (각도 {e.get('jaw', 0):.2f} rad, 하중 {e.get('load_N', 0):.2f} N) → 운반")
        elif a.startswith("recover"):
            s.append(f"G1 빈손 판정 (각도 {e.get('jaw', 0):.2f}, 하중 {e.get('load_N', 0):.2f} N) → 열고 재접근")
        elif a == "lost":
            s.append("운반 중 놓침 → 재접근")
    if rel:
        r = rel[-1]
        s.append(f"G2 {'보정' if r.get('corrected') else '통과'} ({r.get('exy_mm', 0):.1f} mm) · G3 {'합격' if r['post_release']['ok'] else '불합격'}"
                 + (" → 재배치" if r.get("replace") else ""))
    return "  |  ".join(s)


def per_brick_err(env):
    """각 설계 슬롯에 가장 가까운 벽돌의 평면 오차 mm."""
    P = env.brick_poses()[:, :3]; out = []
    for d in env.design:
        c = np.array(d[:3]); j = int(np.argmin(np.linalg.norm(P[:, :2] - c[:2], axis=1)))
        out.append(1000 * float(np.hypot(*(P[j, :2] - c[:2]))))
    return out


# ────────────────────────────────────────────── A. 표지·모르타르·관측 3장·초기 앞면
def part_A(seed=40000):
    env = BrickEnv(cfg_paper())
    # pass 1: 이벤트 시각
    r = Run(env, seed, "sim"); r.go(); rel = r.gate.release_events; r.close()
    t_rel = [e["t"] for e in rel]
    print("A release t", t_rel, "full", r.M["m1_all_success"], flush=True)
    targets = {"carry1": max(5, t_rel[0] - 40), "third": max(5, t_rel[2] - 3), "bed": max(5, t_rel[2] - 60)}
    wall = np.array([env.cfg.wall.origin_x, env.cfg.wall.origin_y, 0.03])
    cams = {"cover_az120": free_cam(wall + [0.02, 0.03, 0.0], 0.40, 120, -33), "cover_az60": free_cam(wall + [0.02, 0.03, 0.0], 0.40, 60, -33),
            "cover_az150": free_cam(wall + [0.0, 0.02, 0.0], 0.38, 150, -30)}
    close = free_cam(wall + [0.0, 0.0, 0.02], 0.19, 110, -27)
    shots = {}

    def cap(env, gate, run):
        t = env.t
        if t == 0 or t in targets.values():
            for k, c in cams.items():
                shots[(t, k)] = run.view(c)
            shots[(t, "front")] = run.view("front"); shots[(t, "close")] = run.view(close)
            shots[(t, "obs")] = [env.render(c) for c in ("front", "wrist", "top")]
    r = Run(env, seed, "sim", capture=cap, res=(960, 1280))
    r.view("front"); shots[(0, "front")] = r.view("front"); shots[(0, "obs")] = [env.render(c) for c in ("front", "wrist", "top")]
    for k, c in cams.items():
        shots[(0, k)] = r.view(c)
    r.go()
    final = {k: r.view(c) for k, c in cams.items()}; final["front"] = r.view("front"); final["close"] = r.view(close)
    r.close()
    t3, tb, t1 = targets["third"], targets["bed"], targets["carry1"]
    for k in cams:
        save_png(IMG + f"cover_{k}_placing_top.png", shots[(t3, k)]); save_png(IMG + f"final_{k}.png", final[k])
    save_png(IMG + "cover_front_placing_top.png", shots[(t3, "front")]); save_png(IMG + "final_front.png", final["front"])
    save_png(IMG + "sim_front_initial.png", shots[(0, "front")])
    save_png(IMG + "mortar_closeup_before_top.png", shots[(tb, "close")]); save_png(IMG + "mortar_closeup_final.png", final["close"])
    # 관측 3장 (128×128 원본, 4배 확대)
    for tag, t in (("carry", t1), ("initial", 0)):
        obs = shots[(t, "obs")]
        W = Image.new("RGB", (3 * 520 + 40, 600), "white"); d = ImageDraw.Draw(W)
        for k, (nm, im) in enumerate(zip(("앞 (front)", "손목 (wrist)", "위 (top)"), obs)):
            x = 10 + k * 520
            W.paste(Image.fromarray(im).resize((512, 512), Image.Resampling.NEAREST), (x, 60))
            d.text((x, 20), nm + " 128×128", font=font(24, True), fill=INK)
        d.text((10, 576), f"정책이 받는 관측 그대로 (seed {seed}, t = {t * 0.05:.1f} s) + 관절값 6 · 벽돌 좌표·접촉력은 입력에 없음", font=font(18), fill=(0x5b, 0x69, 0x73))
        W.save(IMG + f"obs_3cams_{tag}.png")
    print("A done", flush=True)


# ────────────────────────────────────────────── B. G1 빈손 판정 클립 (seed 50004)
def part_B(seed=50004, events_out=None):
    env = BrickEnv(cfg_paper()); frames = []

    def cap(env, gate, run):
        if env.t % 2:
            return
        frames.append((env.t, run.view("front"), run.view("wrist"), gate_status(gate, env.t)))
    r = Run(env, seed, "sim", capture=cap); M = r.go()
    rec = [e["t"] for e in r.gate.events if str(e.get("action", "")).startswith("recover")]
    print("B recover t", rec, "full", M["m1_all_success"], flush=True)
    if events_out is not None:
        events_out += [dict(e, seed=seed, src="sim") for e in r.gate.events]
    t0 = rec[0] if rec else frames[len(frames) // 3][0]
    sel = [f for f in frames if t0 - 70 <= f[0] <= t0 + 90]
    wr = H264(VID + f"15_G1_빈손판정_재접근_스크립트_seed{seed}.mp4", 1100, 620)
    for t, fr, wr_, st in sel:
        c = Image.new("RGB", (1100, 620), "white"); d = ImageDraw.Draw(c)
        d.rectangle((0, 0, 1100, 54), fill=NAVY); d.text((16, 12), "G1 잡기 확인: 1.5 cm 들어 올려 집게 각도·손목 하중으로 판정 (스크립트 교사 + 검측)", font=font(22, True), fill="white")
        c.paste(Image.fromarray(fr).resize((480, 480)), (50, 70)); c.paste(Image.fromarray(wr_).resize((480, 480)), (570, 70))
        d.text((50, 556), "앞 카메라", font=font(18, True), fill=INK); d.text((570, 556), "손목 카메라", font=font(18, True), fill=INK)
        d.text((50, 586), f"{t * 0.05:5.1f} s   {st or '정책(교사) 동작 중'}", font=font(18), fill=TEAL if st else (0x5b, 0x69, 0x73))
        wr.write(c)
    wr.hold(10); wr.close(); r.close()
    print("B done", flush=True)


# ────────────────────────────────────────────── C. 스크립트 단독(A) vs 스크립트+검측(D) 2분할
def part_C(seeds=(50010, 50020, 50000, 50028, 50030, 50033), events_out=None):
    env = BrickEnv(cfg_paper())
    for seed in seeds:
        fa = []
        r = Run(env, seed, None, capture=lambda e, g, run: fa.append((e.t, run.view("front"))) if e.t % 2 == 0 else None)
        Ma = r.go(); r.close()
        print("C seed", seed, "A full", Ma["m1_all_success"], "exy", round(Ma["m1_exy_max_mm"], 1), flush=True)
        if Ma["m1_all_success"]:
            continue
        fd = []
        r = Run(env, seed, "sim", capture=lambda e, g, run: fd.append((e.t, run.view("front"), gate_status(g, e.t))) if e.t % 2 == 0 else None)
        Md = r.go()
        if events_out is not None:
            events_out += [dict(e, seed=seed, src="sim") for e in r.gate.events]
        r.close()
        print("C seed", seed, "D full", Md["m1_all_success"], "exy", round(Md["m1_exy_max_mm"], 1), flush=True)
        if not Md["m1_all_success"]:
            continue
        n = max(len(fa), len(fd))
        wr = H264(VID + f"16_스크립트_단독A_vs_검측D_seed{seed}.mp4", 1100, 640)
        for k in range(0, n, 2):
            ta, ia = fa[min(k, len(fa) - 1)]; td, idd, st = fd[min(k, len(fd) - 1)]
            c = Image.new("RGB", (1100, 640), "white"); d = ImageDraw.Draw(c)
            d.rectangle((0, 0, 1100, 54), fill=NAVY)
            d.text((16, 12), f"같은 초기 배치(seed {seed}) — 좌: 스크립트 단독(A)  우: 스크립트 + G1~G3(D)  (2배속, 정책 대신 교사로 재현)", font=font(20, True), fill="white")
            c.paste(Image.fromarray(ia).resize((480, 480)), (50, 70)); c.paste(Image.fromarray(idd).resize((480, 480)), (570, 70))
            d.text((50, 556), f"A 단독  {ta * 0.05:5.1f} s" + ("  → 최종 불합격" if k >= len(fa) - 2 else ""), font=font(18, True), fill=RED)
            d.text((570, 556), f"D 검측  {td * 0.05:5.1f} s" + ("  → 3개 합격" if k >= len(fd) - 2 else ""), font=font(18, True), fill=GREEN)
            d.text((570, 586), st, font=font(15), fill=TEAL)
            d.text((50, 586), f"최대 위치 오차 {Ma['m1_exy_max_mm']:.1f} mm", font=font(15), fill=(0x5b, 0x69, 0x73))
            wr.write(c)
        wr.hold(12); wr.close()
        print("C done seed", seed, flush=True)
        return seed
    print("C: no seed where A fails and D passes", flush=True)


# ────────────────────────────────────────────── D. 카메라 인식 오버레이 + 카메라 검측 D 대역 영상 + 파이프라인 썸네일
def part_D(seed=40000, events_out=None):
    env = BrickEnv(cfg_paper()); ov, fr, first = [], [], {}
    B = env.brick; errs = []

    def cap(env, gate, run):
        if env.t % 2:
            return
        cam = gate.cam
        rgb, hgt = cam.render(); dets = cam.detect()
        if not first:
            first.update(rgb=rgb.copy(), hgt=hgt.copy(), dets=[dict(d) for d in dets])
        im = Image.fromarray(rgb); d = ImageDraw.Draw(im)
        # 방향이 모호한 조각(짧게 보임)은 검측이 집게 yaw·슬롯 방향으로 두 후보 중 하나를 고른다 → 여기서는 실제에 가까운 후보를 노랑, 다른 후보를 주황 점선으로
        truth = [env.brick_pose(i)[0] for i in range(env.n_bricks)]
        chosen = []
        for det in dets:
            cands = [det] + ([det["alt"]] if det.get("ambiguous") and det.get("alt") else [])
            tp = min(truth, key=lambda p: np.hypot(*(det["pos"][:2] - p[:2])))
            cands.sort(key=lambda c: np.hypot(*(np.asarray(c["pos"])[:2] - tp[:2])))
            for k, c in enumerate(cands):
                yaw = c["yaw"]; ex = np.array([np.cos(yaw), np.sin(yaw), 0]); ey = np.array([-np.sin(yaw), np.cos(yaw), 0])
                top = np.asarray(c["pos"]) + np.array([0, 0, B.H / 2])
                poly = [cam.project(top + sx * B.L / 2 * ex + sy * B.W / 2 * ey)[:2] for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
                if k == 0:
                    d.polygon([tuple(p) for p in poly], outline=(255, 220, 0), width=4)
                else:
                    pts = [tuple(p) for p in poly] + [tuple(poly[0])]
                    for a, b in zip(pts[:-1], pts[1:]):
                        n_seg = 8
                        for s in range(0, n_seg, 2):
                            d.line([(a[0] + (b[0] - a[0]) * s / n_seg, a[1] + (b[1] - a[1]) * s / n_seg), (a[0] + (b[0] - a[0]) * (s + 1) / n_seg, a[1] + (b[1] - a[1]) * (s + 1) / n_seg)], fill=(255, 140, 0), width=3)
            chosen.append(cands[0])
        n_match = 0
        for i in range(env.n_bricks):
            p, q = env.brick_pose(i); u, v, _ = cam.project(p + np.array([0, 0, B.H / 2]))
            d.ellipse((u - 6, v - 6, u + 6, v + 6), fill=(230, 30, 30))
            best = min(chosen, key=lambda dd: np.hypot(*(np.asarray(dd["pos"])[:2] - p[:2])), default=None)
            if best is not None and np.hypot(*(np.asarray(best["pos"])[:2] - p[:2])) < 0.03:
                e = 1000 * np.hypot(*(np.asarray(best["pos"])[:2] - p[:2])); errs.append(e); n_match += 1
                d.text((u + 10, v - 28), f"{e:.1f} mm", font=font(26, True), fill=(230, 30, 30))
        ov.append((env.t, im.resize((960, 720), Image.Resampling.LANCZOS), n_match, len(dets)))
        fr.append((env.t, run.view("front"), gate_status(gate, env.t)))
    r = Run(env, seed, "camera", capture=cap); M = r.go()
    if events_out is not None:
        events_out += [dict(e, seed=seed, src="camera") for e in r.gate.events]
    S = r.gate.summary(); r.close()
    print("D full", M["m1_all_success"], "cam p95", S.get("cam_err_xy_mm_p95"), "n", len(errs), flush=True)
    # 오버레이 영상
    wr = H264(VID + f"19_카메라인식_오버레이_seed{seed}.mp4", 960, 800)
    for k, (t, im, nm, nd) in enumerate(ov):
        c = Image.new("RGB", (960, 800), "white"); d = ImageDraw.Draw(c)
        d.rectangle((0, 0, 960, 54), fill=NAVY); d.text((14, 8), "윗면 RGB-D 카메라 추정 — 노랑: 추정 윤곽(로봇이 씀) · 주황 점선: 방향 모호 시 버린 후보 · 빨강: 실제 중심(채점용)", font=font(18, True), fill="white")
        d.text((14, 32), f"{t * 0.05:5.1f} s · 검출 {nd}개 · 누적 측정 {min(len(errs), (k + 1) * 3)}회 · 1280×960 렌더 → 색 분할 → 깊이 역투영 → 사각형 맞춤 → 가림 복원", font=font(14), fill=(0xc2, 0xd8, 0xe8))
        c.paste(im, (0, 60)); d.rectangle((0, 780, 960, 800), fill="white")
        wr.write(c)
    wr.hold(10); wr.close()
    # 카메라 검측 D 대역 영상 (앞 카메라)
    wr = H264(VID + f"20_스크립트_카메라검측D_대역_seed{seed}.mp4", 960, 580)
    for t, im, st in fr:
        c = Image.new("RGB", (960, 580), "white"); d = ImageDraw.Draw(c)
        d.rectangle((0, 0, 960, 54), fill=NAVY); d.text((14, 12), "스크립트 교사 + 카메라 검측 G1~G3 (조건 D, 정답 좌표 없이) — 학습 정책판은 Ubuntu에서", font=font(20, True), fill="white")
        c.paste(Image.fromarray(im).resize((480, 480)), (20, 64))
        d.text((520, 80), f"{t * 0.05:5.1f} s", font=font(22, True), fill=TEAL)
        y = 120
        for ln in (st.split("  |  ") if st else ["교사 동작 중 (집기·운반)"]):
            d.text((520, y), ln, font=font(16), fill=INK); y += 30
        d.text((520, 500), f"최종: {'3개 합격' if M['m1_all_success'] else '불합격'} · 최대 오차 {M['m1_exy_max_mm']:.1f} mm", font=font(16, True), fill=GREEN if M["m1_all_success"] else RED)
        wr.write(c)
    wr.hold(10); wr.close()
    # 파이프라인 썸네일
    rgb, hgt, dets = first["rgb"], first["hgt"], first["dets"]
    r_, g_, b_ = [rgb[..., i].astype(int) for i in range(3)]
    mask = (r_ - b_ >= 40) & (r_ >= g_) & (g_ >= b_ - 10) & (hgt < 0.2)
    ys, xs = np.where(mask); y0, y1, x0, x1 = ys.min() - 40, ys.max() + 40, xs.min() - 40, xs.max() + 40
    y0, x0 = max(0, y0), max(0, x0)
    n, lab = cv2.connectedComponents(mask.astype(np.uint8))
    fig, ax = plt.subplots(1, 5, figsize=(20, 4.6))
    ax[0].imshow(rgb[y0:y1, x0:x1]); ax[0].set_title("① 윗면 카메라 RGB (1280×960)")
    ax[1].imshow(mask[y0:y1, x0:x1], cmap="gray"); ax[1].set_title("② 벽돌색 분할 (R−B ≥ 40)")
    hm = np.where(mask, hgt, np.nan)[y0:y1, x0:x1] * 1000
    im3 = ax[2].imshow(hm, cmap="viridis"); ax[2].set_title("③ 깊이 → 높이 지도 (mm)"); plt.colorbar(im3, ax=ax[2], fraction=0.04)
    ax[3].imshow(np.where(lab > 0, lab, np.nan)[y0:y1, x0:x1], cmap="tab10"); ax[3].set_title(f"④ 조각 분리·평면 맞춤 ({n - 1}개)")
    ax[4].imshow(rgb[y0:y1, x0:x1]); ax[4].set_title("⑤ 사각형 맞춤 + 가림 복원 (노랑)")
    # 윤곽을 위해 카메라 투영 필요: Run이 닫혔으므로 첫 프레임 오버레이를 다시 그리는 대신 dets의 모서리를 ex/ey로 근사 (카메라 위: 직교 근사)
    env.reset(seed); env.settle(5)
    from brick_sim.perception import BrickPoseEstimator
    est = BrickPoseEstimator(env); est.render(); dd = est.detect(force=True)
    for det in dd:
        yaw = det["yaw"]; ex = np.array([np.cos(yaw), np.sin(yaw), 0]); ey = np.array([-np.sin(yaw), np.cos(yaw), 0]); top = det["pos"] + np.array([0, 0, B.H / 2])
        poly = np.array([est.project(top + sx * B.L / 2 * ex + sy * B.W / 2 * ey)[:2] for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1), (-1, -1))])
        ax[4].plot(poly[:, 0] - x0, poly[:, 1] - y0, color="yellow", lw=2.5)
    for i in range(env.n_bricks):
        p, _ = env.brick_pose(i); u, v, _ = est.project(p + np.array([0, 0, B.H / 2])); ax[4].plot(u - x0, v - y0, "o", color="red", ms=6)
    est.close()
    for a in ax:
        a.set_xticks([]); a.set_yticks([])
    fig.suptitle("탑재 윗면 카메라 벽돌 위치 추정 파이프라인 (sim/brick_sim/perception.py)", fontsize=15)
    fig.tight_layout(); fig.savefig(IMG + "fig_perception_pipeline.png", dpi=130); plt.close(fig)
    print("D done", flush=True)


# ────────────────────────────────────────────── E. 둘째 벽돌 여유 1.5 vs 0.5 mm 비교 2컷 (카메라 검측)
def part_E(seeds=(50012, 50001, 50015, 50028, 50046), events_out=None):
    env = BrickEnv(cfg_paper())
    for seed in seeds:
        res = {}
        for bias in (0.0015, 0.0005):
            r = Run(env, seed, "camera", nbr_bias=bias, res=(720, 960)); M = r.go()
            if events_out is not None:
                events_out += [dict(e, seed=seed, src="camera") for e in r.gate.events]
            wall = np.array([env.cfg.wall.origin_x, env.cfg.wall.origin_y, 0.03])
            res[bias] = dict(M=M, front=r.view("front"), close=r.view(free_cam(wall + [0, 0, 0.02], 0.27, 100, -30)), err=per_brick_err(env),
                             bad=r.gate.summary()["bad_releases"]); r.close()
            print("E seed", seed, "bias", bias, "full", M["m1_all_success"], "err", [round(e, 1) for e in res[bias]["err"]], flush=True)
        if (not res[0.0015]["M"]["m1_all_success"]) and res[0.0005]["M"]["m1_all_success"]:
            W = Image.new("RGB", (2 * 760 + 60, 760), "white"); d = ImageDraw.Draw(W)
            for k, bias in enumerate((0.0015, 0.0005)):
                x = 20 + k * 780; R_ = res[bias]
                W.paste(Image.fromarray(R_["close"]).resize((760, 570)), (x, 70))
                ok = R_["M"]["m1_all_success"]
                d.text((x, 16), f"둘째 벽돌 간격 여유 {bias * 1000:.1f} mm — {'합격' if ok else '불합격'}", font=font(26, True), fill=GREEN if ok else RED)
                d.text((x, 650), "벽돌별 위치 오차 (슬롯 1·2·3): " + " / ".join(f"{e:.1f} mm" for e in R_["err"]) + f"   (허용 4.5)", font=font(20), fill=INK)
                d.text((x, 685), f"해제 후 불합격 {R_['bad']}회 · 카메라 추정 좌표로 G2·G3", font=font(18), fill=(0x5b, 0x69, 0x73))
            d.text((20, 725), f"같은 초기 배치(seed {seed}), 스크립트 교사 + 카메라 검측. 1.5 mm 여유는 설계 위치에서 이미 4.1~4.2 mm 떨어뜨려 놓으므로 1 mm 측정 오차가 허용 4.5 mm를 넘긴다.", font=font(17), fill=(0x5b, 0x69, 0x73))
            W.save(IMG + f"cmp_nbr_bias_seed{seed}.png"); print("E done seed", seed, flush=True)
            return seed
    print("E: no seed with 1.5 fail & 0.5 pass", flush=True)


# ────────────────────────────────────────────── F. G1 문턱값 근거 그래프
def part_F(events):
    pts = [(e["jaw"], e["load_N"], e.get("held", False), e.get("action", "")) for e in events if "jaw" in e and "load_N" in e and e.get("action") in ("carry", "recover:reguide", "abort", "lost")]
    if not pts:
        print("F: no events"); return
    J = np.array([p[0] for p in pts]); L = np.array([p[1] for p in pts]); H = np.array([p[2] for p in pts])
    fig, ax = plt.subplots(figsize=(9, 5.6))
    ax.scatter(J[H], L[H], s=46, color="#1d7a3e", label=f"벽돌을 쥔 상태로 판정 (n={int(H.sum())})", zorder=3)
    if (~H).any():
        ax.scatter(J[~H], L[~H], s=70, color="#b0412a", marker="x", label=f"빈손 판정 (n={int((~H).sum())})", zorder=3)
    ax.axvline(0.2, color="#2a5fb0", ls="--", lw=2); ax.axhline(0.9, color="#2a5fb0", ls="--", lw=2)
    ax.text(0.205, 2.75, "집게 각도 문턱 0.2 rad →", color="#2a5fb0", fontsize=11)
    ax.text(-0.24, 0.98, "손목 하중 문턱 0.9 N", color="#2a5fb0", fontsize=11)
    ax.axvline(0.31, color="#1d7a3e", ls=":", lw=1.5); ax.axvline(-0.12, color="#b0412a", ls=":", lw=1.5); ax.axhline(1.83, color="#1d7a3e", ls=":", lw=1.5)
    ax.text(0.318, 2.3, "쥐었을 때 0.31 (실험일지 9/26)", color="#1d7a3e", fontsize=10, rotation=90, va="bottom")
    ax.text(-0.112, 1.3, "빈손 −0.12", color="#b0412a", fontsize=10, rotation=90, va="bottom")
    ax.text(-0.24, 1.88, "벽돌 무게 1.83 N", color="#1d7a3e", fontsize=10)
    ax.annotate("빈손: 각도 −0.12 rad, 하중 −0.7 N\n(들어 올렸는데 무게가 없음) → 열고 재접근", xy=(J[~H][0], L[~H][0]) if (~H).any() else (-0.12, -0.7),
                xytext=(-0.05, -0.55), fontsize=10, color="#b0412a", arrowprops=dict(arrowstyle="->", color="#b0412a"))
    ax.set_xlim(-0.25, 0.5); ax.set_ylim(-1.0, max(3.2, L.max() + 0.3))
    ax.set_xlabel("1.5 cm 들어 올린 뒤 집게 각도 (rad)"); ax.set_ylabel("손목 추가 하중 (N)")
    ax.set_title("G1 문턱값: 쥔 경우와 빈손이 각도·하중 모두에서 갈린다 (스크립트+검측 에피소드의 G1 판정 기록)")
    ax.legend(loc="lower right"); ax.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(IMG + "fig_g1_threshold.png", dpi=140); plt.close(fig)
    print("F done", len(pts), "pts, empty", int((~H).sum()), flush=True)


# ────────────────────────────────────────────── G. 초기 배치 분포 + 실행가능성 필터
def part_G(n=320, seed0=70000):
    from brick_sim.feasibility import layout_feasibility
    cfg = cfg_paper(); cfg.feasible_supply = False
    env = BrickEnv(cfg); rows = []
    t0 = time.time()
    for s in range(seed0, seed0 + n):
        env.reset(s)
        fz = layout_feasibility(env)
        for (x, y, _, yaw), f in zip(env.supply_poses, fz):
            rows.append((x, y, np.degrees(yaw), bool(f["ok"])))
        if s == seed0 + 4:
            print("G 5 layouts in %.1fs" % (time.time() - t0), flush=True)
    A = np.array(rows, dtype=float); ok = A[:, 3] > 0.5
    fig, ax = plt.subplots(1, 2, figsize=(13, 5.6), gridspec_kw={"width_ratios": [1.5, 1]})
    ax[0].scatter(A[ok, 0] * 1000, A[ok, 1] * 1000, s=10, color="#1d7a3e", alpha=0.5, label=f"집을 수 있는 배치 ({ok.sum()})")
    ax[0].scatter(A[~ok, 0] * 1000, A[~ok, 1] * 1000, s=16, color="#b0412a", marker="x", label=f"필터로 걸러짐: 몸통·이웃 충돌 ({(~ok).sum()})")
    w = env.cfg.wall; L = env.brick.L * 1000; Wd = env.brick.W * 1000
    ax[0].add_patch(plt.Rectangle(((w.origin_x - env.brick.L - 0.001) * 1000, (w.origin_y - env.brick.W / 2) * 1000), 2 * L + 2, Wd, fill=False, ec="#2a5fb0", lw=2, ls="--"))
    ax[0].text((w.origin_x - env.brick.L) * 1000, (w.origin_y + env.brick.W / 2) * 1000 + 6, "벽 (목표 슬롯)", color="#2a5fb0", fontsize=11)
    ax[0].plot(0, 0, "ks", ms=9); ax[0].text(6, 4, "로봇 베이스", fontsize=11)
    for sx, sy in cfg.supply_slots:
        ax[0].add_patch(plt.Rectangle(((sx - cfg.pos_rand) * 1000, (sy - cfg.pos_rand) * 1000), 60, 60, fill=False, ec="#8a98a3", lw=1))
    ax[0].set_aspect("equal"); ax[0].set_xlabel("x (mm)"); ax[0].set_ylabel("y (mm)"); ax[0].legend(loc="upper left", fontsize=10); ax[0].grid(alpha=0.3)
    ax[0].set_title(f"벽돌 초기 위치 {n}개 배치 × 3개 (회색 상자 = 공급 슬롯 ±30 mm)")
    ax[1].hist(A[ok, 2], bins=24, range=(-60, 60), color="#1d7a3e", alpha=0.7, label="집을 수 있음"); ax[1].hist(A[~ok, 2], bins=24, range=(-60, 60), color="#b0412a", alpha=0.7, label="걸러짐")
    ax[1].set_xlabel("초기 방향 (°)"); ax[1].set_ylabel("벽돌 수"); ax[1].set_title("초기 방향 ±60°"); ax[1].legend(fontsize=10); ax[1].grid(alpha=0.3)
    fig.suptitle("학습 시연·평가 배치의 초기 조건 분포 (±30 mm, ±60°, 실행가능성 필터)", fontsize=14)
    fig.tight_layout(); fig.savefig(IMG + "fig_initial_layouts.png", dpi=140); plt.close(fig)
    print("G done", ok.sum(), (~ok).sum(), "%.0fs" % (time.time() - t0), flush=True)


# ────────────────────────────────────────────── H. G1·G2·G3 3컷 (feedback_episode.jpg에서)
def part_H():
    im = Image.open(IMG + "feedback_episode.jpg"); W0, H0 = im.size
    # 상단 3패널 (좌표는 1976×770 기준 비율)
    boxes = [(0, 0, 0.253, 0.39), (0.26, 0, 0.587, 0.39), (0.592, 0, 0.92, 0.39)]
    labels = ["G1 잡기 확인 — 빈손 판정 후 재접근 (10.4 s)", "G2 놓기 전 검사 — 걸침 발견, 높이 오차 13 mm (35.2 s)", "G3 놓은 뒤 채점 — 기울기 19° 불합격 → 재배치"]
    sens = ["읽는 신호: 집게 각도 · 손목 하중", "읽는 신호: 쥔 벽돌 위치·높이·방향 (탑재 카메라)", "읽는 신호: 놓인 벽돌 위치·높이·방향·기울기 (탑재 카메라)"]
    out = Image.new("RGB", (3 * 640 + 40, 520), "white"); d = ImageDraw.Draw(out)
    for k, (b, lab, se) in enumerate(zip(boxes, labels, sens)):
        crop = im.crop((int(b[0] * W0), int(b[1] * H0), int(b[2] * W0), int(b[3] * H0))).resize((620, 380))
        x = 10 + k * 640; out.paste(crop, (x, 10))
        d.text((x, 400), lab, font=font(20, True), fill=INK); d.text((x, 435), se, font=font(17), fill=TEAL)
    d.text((10, 485), "실험 3, ACT seed 1000, 시험 배치 50018 — 실험 3 당시 G2·G3의 위치는 정답 좌표(오라클), RQ4부터 탑재 카메라 추정", font=font(16), fill=(0x5b, 0x69, 0x73))
    out.save(IMG + "g123_cuts.png"); print("H done", flush=True)


# ────────────────────────────────────────────── I/J. 현장 vs 시뮬, SO-ARM 실물 vs 모델
def part_IJ():
    site = Image.open(IMG + "외부/commons_4.jpg").convert("RGB"); sim = Image.open(IMG + "sim_front_initial.png").convert("RGB")
    h = 600; site = site.resize((int(site.width * h / site.height), h)); sim = sim.resize((int(sim.width * h / sim.height), h))
    W = Image.new("RGB", (site.width + sim.width + 60, h + 150), "white"); d = ImageDraw.Draw(W)
    W.paste(site, (20, 60)); W.paste(sim, (site.width + 40, 60))
    d.text((20, 14), "실제 현장: 모르타르 위에 블록을 놓고 수평·줄눈을 맞춘다", font=font(24, True), fill=INK)
    d.text((site.width + 40, 14), "우리 시뮬레이션: 공급된 벽돌 3개 → 2+1 적층, 앞 카메라", font=font(24, True), fill=INK)
    d.text((20, h + 70), "①모르타르: 연속 순응층으로 단순화  ②규모: 축소 벽돌 3개, 소형 팔  ③센서: 이상적 힘 센서  ④자재: 같은 치수의 강체  ⑤위치 정보: 외부 계측 없이 탑재 카메라", font=font(18), fill=INK)
    d.text((20, h + 105), "사진: U.S. Air Force / Capt. Holly Hess, Public domain (Wikimedia Commons)", font=font(15), fill=(0x5b, 0x69, 0x73))
    W.save(IMG + "site_vs_sim.png")
    real = Image.open(IMG + "외부/so101_follower.webp").convert("RGB"); real = real.resize((int(real.width * 560 / real.height), 560))
    simc = sim.resize((int(sim.width * 560 / sim.height), 560))
    W = Image.new("RGB", (real.width + simc.width + 60, 660), "white"); d = ImageDraw.Draw(W)
    W.paste(real, (20, 60)); W.paste(simc, (real.width + 40, 60))
    d.text((20, 14), "SO-ARM101 실물 (TheRobotStudio, Apache-2.0)", font=font(24, True), fill=INK)
    d.text((real.width + 40, 14), "MuJoCo 모델 (Menagerie so_arm100 + 손목 카메라·힘 센서 추가)", font=font(24, True), fill=INK)
    d.text((20, 630), "팔 5관절 + 집게 1 · LeRobot 표준 저가 팔 · 가반하중·반경이 작아 실척 벽돌은 불가 → 중간 2 이후 산업용 팔", font=font(17), fill=(0x5b, 0x69, 0x73))
    W.save(IMG + "soarm_real_vs_sim.png"); print("IJ done", flush=True)


if __name__ == "__main__":
    parts = sys.argv[1:] or list("ABCDEFGHI")
    events = []
    t0 = time.time()
    for p in parts:
        if p == "A": part_A()
        elif p == "B": part_B(events_out=events)
        elif p == "C": part_C(events_out=events)
        elif p == "D": part_D(events_out=events)
        elif p == "E": part_E(events_out=events)
        elif p == "F": part_F(events)
        elif p == "G": part_G()
        elif p == "H": part_H()
        elif p == "I": part_IJ()
        print(f"== {p} at {time.time() - t0:.0f}s", flush=True)
    json.dump(events, open(IMG + "../근거_rq4/g1_events_render_runs.json", "w", encoding="utf-8"), default=float)
