# -*- coding: utf-8 -*-
"""6쪽 딜레마 ②: Ubuntu에서 새로 렌더한 실험 1 Diffusion clean / plus2 (seed 10000) 를 같은 구간 0~50 s, 2.5배속으로 편집."""
import os, sys, cv2
from PIL import Image, ImageDraw
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from clips_existing import H264, font, NAVY, OUT as VOUT
SRC = r"C:/Users/user/Desktop/사기설/01_사기설/중간발표1/근거_우분투_20261012/"
POST = r"C:/Users/user/Desktop/사기설/01_사기설/중간발표1/도구/v15_자산/"; os.makedirs(POST, exist_ok=True)
INK = (0x24, 0x35, 0x49)
JOBS = [("exp1_diffusion_v2_2p1_joint_image_clean_seed10000.mp4", "23_실험1_Diffusion_복구없이학습_배치10000_2.5배속_0-8s.mp4",
         "복구 시연 없이 학습한 Diffusion Policy (실험 1, 학습 데이터 clean)", "3개를 놓은 뒤 팔을 빼고 정지 · 이 배치 결과 3/3 성공", 0.75, 8.0),
        ("exp1_diffusion_v2_2p1_joint_image_plus2_seed10000.mp4", "24_실험1_Diffusion_복구섞어학습_배치10000_2.5배속.mp4",
         "복구 시연을 섞어 학습한 Diffusion Policy (실험 1, 학습 데이터 plus2)", "3개를 놓은 뒤에도 집게가 계속 오르내림 · 이 배치 결과 1/3 성공", 0.8, None)]
for src, dst, title, sub, pf, end_s in JOBS:
    v = cv2.VideoCapture(SRC + src); fps = v.get(cv2.CAP_PROP_FPS); n_end = int(50 * fps)
    frames = []
    while len(frames) < n_end:
        ok, f = v.read()
        if not ok:
            break
        frames.append(cv2.cvtColor(f, cv2.COLOR_BGR2RGB))
    wr = H264(VOUT + dst, 1080, 500); k = 0.0; poster = None
    n_out = 0
    while int(k) < len(frames) and (end_s is None or n_out < int(end_s * 10)):
        i = int(k); f = frames[i]; t = i / fps
        c = Image.new("RGB", (1080, 500), "white"); d = ImageDraw.Draw(c)
        c.paste(Image.fromarray(f[60:420]), (0, 60))
        d.rectangle((0, 0, 1080, 60), fill=NAVY)
        d.text((14, 8), title, font=font(22, True), fill="white")
        d.text((14, 36), "앞 · 위 · 손목 카메라 · 2.5배속 · 같은 초기 배치(배치 번호 10000) · 정책 자율 실행", font=font(17), fill=(0xc2, 0xd8, 0xe8))
        d.rectangle((0, 420, 1080, 500), fill=(0xf4, 0xf6, 0xf8))
        d.text((14, 432), f"{t:5.1f} s   {sub if t >= 24 else '벽돌 3개 적층 중'}", font=font(20, True), fill=INK)
        wr.write(c)
        if poster is None and (i >= int(pf * len(frames)) or (end_s and n_out == int(end_s * 10) - 1)):
            poster = c
        k += 2.5; n_out += 1
    if end_s is None:
        wr.hold(10)
    wr.close()
    poster.save(POST + "poster_" + dst[:2] + ".png")
    print("done", dst, len(frames), "frames")
