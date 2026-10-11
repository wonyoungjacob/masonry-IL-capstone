# -*- coding: utf-8 -*-
"""v7 PPT 자산: Diffusion 실험 2 성공 클립(2배속), 영상 포스터 프레임, 둥근 모서리 사진."""
import os, sys, numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, os.path.dirname(__file__))
from clips_existing import H264, frames, font, NAVY, VID as SRC, OUT as VOUT
ROOT = r"C:/Users/user/Desktop/사기설"
IMG = ROOT + "/01_사기설/중간발표1/그림/"
SP = r"C:/Users/user/AppData/Local/Temp/claude/c--Users-user-Desktop----/be685ff9-f10f-46a4-892d-1862ceb8f949/scratchpad/media/v7"
os.makedirs(SP, exist_ok=True)

# 1) Diffusion 실험 2 성공 (원본 11, 92 s) → 0~46 s 2배속, 3패널 그대로
def clip_diffusion_success():
    wr = H264(VOUT + "06_실험2_Diffusion_성공_2배속_seed50002.mp4", 1080, 500)
    fr = frames("11_실험2_Diffusion_성공사례_seed50002.mp4", 0, 46)
    for k, (t, f) in enumerate(fr):
        if k % 2:
            continue
        c = Image.new("RGB", (1080, 500), "white"); d = ImageDraw.Draw(c)
        c.paste(Image.fromarray(f[60:420]), (0, 60))
        d.rectangle((0, 0, 1080, 60), fill=NAVY)
        d.text((14, 8), "실험 2 Diffusion Policy 성공 사례 (시험 배치 50002, 학습 seed 1000) — 정책 단독, 검측 없음", font=font(22, True), fill="white")
        d.text((14, 36), "앞(FRONT) · 위(TOP) · 손목(WRIST) 카메라 · 2배속 · 넓은 배치(±30 mm, ±60°)에서도 되는 경우", font=font(17), fill=(0xc2, 0xd8, 0xe8))
        d.rectangle((0, 420, 1080, 500), fill=(0xf4, 0xf6, 0xf8))
        d.text((14, 432), f"{t:5.1f} s   실험 2 Diffusion 완성 41/200 중 하나", font=font(20), fill=(0x24, 0x35, 0x49))
        wr.write(c)
    wr.hold(10); wr.close()

# 2) 포스터 프레임 (영상 썸네일)
def posters():
    for n, frac in [("09_스크립트_정상시연_3카메라_2배속.mp4", 0.45), ("11_실험1성공_vs_실험2실패_ACT_3배속.mp4", 0.6),
                    ("06_실험2_Diffusion_성공_2배속_seed50002.mp4", 0.75), ("04_실패3종_순차.mp4", 0.45), ("08_실험1_복구시연섞음_교란.mp4", 0.3),
                    ("16_스크립트_단독A_vs_검측D_seed50010.mp4", 0.85), ("19_카메라인식_오버레이_seed40000.mp4", 0.66)]:
        v = cv2.VideoCapture(VOUT + n); N = int(v.get(cv2.CAP_PROP_FRAME_COUNT)); v.set(cv2.CAP_PROP_POS_FRAMES, int(N * frac)); ok, f = v.read()
        Image.fromarray(cv2.cvtColor(f, cv2.COLOR_BGR2RGB)).save(SP + "/poster_" + n[:2] + ".png")
        print("poster", n[:2], f.shape)

# 3) 둥근 모서리 사진 (투명 PNG)
def rounded(src, dst, r, size=None, crop=None):
    im = Image.open(src).convert("RGB")
    if crop:
        im = im.crop(crop)
    if size:
        im = im.resize(size, Image.Resampling.LANCZOS)
    m = Image.new("L", im.size, 0); ImageDraw.Draw(m).rounded_rectangle((0, 0, im.width - 1, im.height - 1), r, fill=255)
    out = Image.new("RGBA", im.size); out.paste(im, (0, 0)); out.putalpha(m); out.save(dst)

if __name__ == "__main__":
    clip_diffusion_success(); print("clip ok", flush=True)
    posters()
    # 표지: az120 렌더(1280×960) — 아래 여백 잘라 4:3 → 약간 세로로
    rounded(IMG + "cover_cover_az120_placing_top.png", SP + "/cover_rounded.png", 64, crop=(80, 40, 1200, 940))
    rounded(IMG + "final_cover_az120.png", SP + "/final_rounded.png", 48, crop=(80, 40, 1200, 940))
    rounded(IMG + "concept_ur5e_wall.png", SP + "/concept_rounded.png", 48, crop=(0, 110, 1600, 1200))
    rounded(IMG + "site_vs_sim.png", SP + "/site_rounded.png", 40)
    rounded(IMG + "feedback_episode.jpg", SP + "/feedback_rounded.png", 40)
    print("rounded ok")
