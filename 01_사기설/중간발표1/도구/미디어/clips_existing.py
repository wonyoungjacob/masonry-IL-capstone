# -*- coding: utf-8 -*-
"""기존 발표용 영상(1080×440, FRONT/TOP/WRIST 3패널, 10 fps)에서 발표 클립을 자른다. H.264는 imageio-ffmpeg 바이너리로."""
import subprocess, sys
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont
import imageio_ffmpeg

ROOT = r"C:/Users/user/Desktop/사기설"
VID = ROOT + "/01_사기설/발표자료_실험1_실험2_20260922/발표용_영상/"
OUT = ROOT + "/01_사기설/중간발표1/영상/"
FONT = ROOT + "/중간발표_진행정리_20261007/assets/NotoSansKR-Regular.ttf"
FONTB = ROOT + "/중간발표_진행정리_20261007/assets/NotoSansKR-Bold.ttf"
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
NAVY = (0x14, 0x23, 0x38)
import os; os.makedirs(OUT, exist_ok=True)


def font(sz, bold=False):
    return ImageFont.truetype(FONTB if bold else FONT, sz)


class H264:
    def __init__(self, path, w, h, fps=10):
        self.w, self.h = w, h
        self.p = subprocess.Popen([FFMPEG, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}",
                                   "-r", str(fps), "-i", "-", "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
                                   "-pix_fmt", "yuv420p", "-movflags", "+faststart", path], stdin=subprocess.PIPE)
        self.last = None

    def write(self, img):  # PIL RGB
        assert img.size == (self.w, self.h), (img.size, self.w, self.h)
        self.p.stdin.write(img.tobytes()); self.last = img

    def hold(self, n):
        for _ in range(n):
            self.p.stdin.write(self.last.tobytes())

    def close(self):
        self.p.stdin.close()
        if self.p.wait():
            raise RuntimeError("ffmpeg failed")


def frames(name, t0, t1):
    """(t, frame RGB ndarray 1080x440) for t0<=t<t1."""
    v = cv2.VideoCapture(VID + name); fps = v.get(cv2.CAP_PROP_FPS)
    v.set(cv2.CAP_PROP_POS_FRAMES, int(round(t0 * fps)))
    out = []
    while True:
        ok, f = v.read()
        if not ok:
            break
        t = v.get(cv2.CAP_PROP_POS_FRAMES) / fps
        if t > t1 + 1e-6:
            break
        out.append((t - 1 / fps, cv2.cvtColor(f, cv2.COLOR_BGR2RGB)))
    v.release(); return out


def front(f):
    return Image.fromarray(f[60:420, 0:360])


def canvas_single(img, title, lines, t, w=960, h=540, size=480):
    c = Image.new("RGB", (w, h), "white"); d = ImageDraw.Draw(c)
    d.rectangle((0, 0, w, 54), fill=NAVY); d.text((16, 12), title, font=font(24, True), fill="white")
    im = img.resize((size, size), Image.Resampling.LANCZOS); c.paste(im, (16, 54 + (h - 54 - size) // 2))
    y = 90
    for ln in lines:
        d.text((size + 40, y), ln, font=font(21), fill=(0x24, 0x35, 0x49)); y += 36
    d.text((size + 40, h - 44), f"{t:5.1f} s", font=font(20, True), fill=(0x14, 0x7c, 0x85))
    return c


def canvas_pair(a, b, title, la, lb, ta, tb, w=1100, h=620, size=480):
    c = Image.new("RGB", (w, h), "white"); d = ImageDraw.Draw(c)
    d.rectangle((0, 0, w, 54), fill=NAVY); d.text((16, 12), title, font=font(24, True), fill="white")
    x0 = (w - 2 * size - 40) // 2
    for k, (im, lab, t) in enumerate(((a, la, ta), (b, lb, tb))):
        x = x0 + k * (size + 40)
        c.paste(im.resize((size, size), Image.Resampling.LANCZOS), (x, 70))
        d.text((x, 70 + size + 8), lab, font=font(21, True), fill=(0x14, 0x3a, 0x50))
        d.text((x + size - 90, 70 + size + 8), f"{t:5.1f} s", font=font(20), fill=(0x14, 0x7c, 0x85))
    return c


def clip_failures():
    wr = H264(OUT + "04_실패3종_순차.mp4", 960, 540)
    parts = [("05_실험2_수집실패_첫파지_seed1001.mp4", 0, 4.7, 1, "(a) 헛집기: 집게가 벽돌을 놓치고 빈손으로 올라감",
              ["실험 2 수집 실패 재현 (seed 1001)", "집게가 닫혔지만 벽돌은 그대로", "→ 정책은 집게 상태와 파지 성공을", "   연결하지 못한다"]),
             ("06_실험2_수집실패_두번째배치높이_seed1009.mp4", 7.8, 14.4, 1, "(b) 걸침: 둘째 벽돌이 이웃 끝에 올라탐",
              ["실험 2 수집 실패 재현 (seed 1009)", "설계 좌표대로 놓았지만 이웃이", "어긋나 있어 끝에 걸침 (+13 mm)", "→ 놓기 전 확인이 필요"]),
             ("10_실험2_ACT_진행실패_seed50000.mp4", 0, 16, 2, "(c) 멈춤: 헛집은 뒤 다음 동작으로 못 감 (ACT)",
              ["실험 2 ACT 정책, 시험 배치 50000", "첫 벽돌 위에서 내려간 뒤", "집지 못한 채 90초가 끝남", "→ 실패를 인지하지 못한다"])]
    for name, t0, t1, speed, title, lines in parts:
        fr = frames(name, t0, t1)
        for k, (t, f) in enumerate(fr):
            if k % speed:
                continue
            wr.write(canvas_single(front(f), title, lines + ([f"({speed}배속)"] if speed > 1 else []), t))
        wr.hold(8)
    wr.close()


def clip_exp1_mix():
    wr = H264(OUT + "08_실험1_복구시연섞음_교란.mp4", 960, 540)
    parts = [("02_실험1_mix_해제후교란과복구_원본.mp4", 10, 20, "실험 1 '복구 시연을 섞은' 데이터: 해제 후 교란과 재파지",
              ["수집 당시 저장된 시연 원본", "12.2초에 놓은 벽돌을 흔들고", "다시 잡아 고치는 시연", "이런 시연을 섞어 학습하면", "정상 배치 완성률 90% → 1~33%"]),
             ("03_실험1_plustop_복구시연_원본.mp4", 4, 14, "실험 1 '복구 시연을 섞은' 데이터: 집기 전 교란",
              ["수집 당시 저장된 시연 원본", "6.1초에 벽돌을 밀어 놓고", "새 위치에서 다시 집는 시연", "→ 복구는 데이터로 가르치지 않고", "   정책 밖 검측으로 처리하기로"])]
    for name, t0, t1, title, lines in parts:
        for t, f in frames(name, t0, t1):
            wr.write(canvas_single(front(f), title, lines, t))
        wr.hold(8)
    wr.close()


def clip_expert_demo():
    # 04 원본은 FRONT/TOP/WRIST 3패널(정책이 보는 3대 카메라) → 전체 프레임 2배속, 자막줄만 교체
    wr = H264(OUT + "09_스크립트_정상시연_3카메라_2배속.mp4", 1080, 500)
    fr = frames("04_실험2_clean_단회배치_원본.mp4", 0, 19)
    for k, (t, f) in enumerate(fr):
        if k % 2:
            continue
        c = Image.new("RGB", (1080, 500), "white"); d = ImageDraw.Draw(c)
        c.paste(Image.fromarray(f[60:420]), (0, 60))
        d.rectangle((0, 0, 1080, 60), fill=NAVY)
        d.text((14, 8), "스크립트 교사의 정상 시연 1회 (실험 2, 학습 에피소드 0) — 정책이 보는 3대 카메라 그대로", font=font(22, True), fill="white")
        d.text((14, 36), "앞(FRONT) · 위(TOP) · 손목(WRIST) 128×128 원본 확대 · 2배속 · 벽돌 좌표는 입력에 없다", font=font(17), fill=(0xc2, 0xd8, 0xe8))
        d.rectangle((0, 420, 1080, 500), fill=(0xf4, 0xf6, 0xf8))
        d.text((14, 432), f"{t:5.1f} s   집기 → 운반 → 놓기 × 3회 (아래 단 2개 + 윗단 1개)", font=font(20), fill=(0x24, 0x35, 0x49))
        wr.write(c)
    wr.hold(10); wr.close()


def clip_exp1_vs_exp2():
    wr = H264(OUT + "11_실험1성공_vs_실험2실패_ACT_3배속.mp4", 1100, 620)
    A = frames("08_실험1_ACT_clean_성공사례_seed10002.mp4", 0, 36)
    B = frames("10_실험2_ACT_진행실패_seed50000.mp4", 0, 36)
    n = min(len(A), len(B))
    for k in range(0, n, 3):
        ta, fa = A[k]; tb, fb = B[k]
        wr.write(canvas_pair(front(fa), front(fb), "같은 ACT 계열, 배치 범위만 다름 — 좁으면 되고 넓으면 멈춘다 (3배속)",
                             "실험 1 (±5 mm, ±10°): 3개 완성", "실험 2 (±30 mm, ±60°): 헛집고 정지", ta, tb))
    wr.hold(10); wr.close()


def clip_overhang_slow():
    wr = H264(OUT + "12_걸침_슬로모션_seed1009.mp4", 960, 540)
    for t, f in frames("06_실험2_수집실패_두번째배치높이_seed1009.mp4", 8.3, 13.0):
        c = canvas_single(front(f), "둘째 벽돌이 이웃 끝에 걸치는 순간 (0.5배속)",
                          ["실험 2 수집 실패 재현 (seed 1009)", "먼저 놓인 이웃이 설계 위치에서", "어긋나 있는데 설계 좌표대로 놓음",
                           "", "높이 오차 13 mm · 기울어진 채 해제", "→ 놓기 전 검사(G2)가 막아야 할 실패"], t)
        wr.write(c); wr.write(c)
    wr.hold(10); wr.close()


if __name__ == "__main__":
    for fn in (clip_failures, clip_exp1_mix, clip_expert_demo, clip_exp1_vs_exp2, clip_overhang_slow):
        fn(); print("done", fn.__name__, flush=True)
