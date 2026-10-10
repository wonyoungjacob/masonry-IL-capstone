# -*- coding: utf-8 -*-
"""대형 환경 콘셉트 렌더: Menagerie UR5e + Robotiq 2F-85 + 실척 벽돌(190×90×57, 줄눈 10 mm) 3단×5개 벽체 + 공급 팔레트.
물리 시뮬이 아니라 '이렇게 생길 것'이라는 그림. 팔 자세는 간단한 수치 IK로 벽 위 슬롯에 맞춘다."""
import os, sys, shutil, numpy as np, mujoco
from PIL import Image, ImageDraw, ImageFont
SP = r"C:/Users/user/AppData/Local/Temp/claude/c--Users-user-Desktop----/be685ff9-f10f-46a4-892d-1862ceb8f949/scratchpad"
MEN = SP + "/menagerie"; OUT = SP + "/media/concept"; IMG = r"C:/Users/user/Desktop/사기설/01_사기설/중간발표1/그림/"
FONT = r"C:/Users/user/Desktop/사기설/중간발표_진행정리_20261007/assets/NotoSansKR-Regular.ttf"
os.makedirs(OUT, exist_ok=True)

# 1) UR5e xml 사본에 손목 부착점(attachment_site 위치)에 2F-85를 attach
ur = open(MEN + "/universal_robots_ur5e/ur5e.xml", encoding="utf-8").read()
ur = ur.replace('<asset>', '<asset>\n    <model name="g2f85" file="../robotiq_2f85/2f85.xml"/>', 1)
ur = ur.replace('<site name="attachment_site" pos="0 0.1 0" quat="-1 1 0 0"/>',
                '<site name="attachment_site" pos="0 0.1 0" quat="-1 1 0 0"/>\n                  <frame pos="0 0.1 0" quat="-1 1 0 0"><attach model="g2f85" body="base_mount" prefix="g_"/></frame>')
assert 'attach model="g2f85"' in ur
open(MEN + "/universal_robots_ur5e/ur5e_2f85.xml", "w", encoding="utf-8").write(ur)

# 2) 벽체: 실척 벽돌, 줄눈 10 mm, 3단, 막힌줄눈(반 벽돌 어긋남)
L, W, H, J = 0.190, 0.090, 0.057, 0.010
WX, WY = 0.62, 0.0          # 벽 중심 (로봇 베이스 기준), 벽은 y 방향으로 뻗음
n_per = 5; courses = 3
bricks, mortar = [], []
total_len = n_per * L + (n_per - 1) * J
placed = 0
next_slot = None
for k in range(courses):
    z = H / 2 + k * (H + J)
    if k > 0:
        mortar.append((WX, WY, z - H / 2 - J / 2, W / 2 * 0.97, total_len / 2, J / 2))
    if k % 2 == 0:
        xs = [(-total_len / 2 + L / 2 + i * (L + J)) for i in range(n_per)]
        lens = [L] * n_per
    else:
        xs = [-total_len / 2 + L / 4] + [(-total_len / 2 + L / 2 + J / 2 + L / 2 + i * (L + J)) for i in range(n_per - 1)] + [total_len / 2 - L / 4]
        lens = [L / 2] + [L] * (n_per - 1) + [L / 2]
    for y, ln in zip(xs, lens):
        # 마지막 단은 일부만 놓인 상태로: 3단의 마지막 두 개는 아직 안 놓음(하나는 집게에)
        if k == courses - 1 and y >= xs[-2]:
            if next_slot is None:
                next_slot = (WX, WY + y, z, ln)
            continue
        bricks.append((WX, WY + y, z, W / 2, ln / 2, H / 2)); placed += 1
pallet = [(0.25, -0.62 + i * (W + 0.02), H / 2, L / 2, W / 2, H / 2) for i in range(4)]
pallet_rot = True

def box(name, x, y, z, hx, hy, hz, mat, euler=""):
    return f'<geom name="{name}" type="box" pos="{x:.4f} {y:.4f} {z:.4f}" size="{hx:.4f} {hy:.4f} {hz:.4f}" material="{mat}" {euler}/>'

geoms = [box(f"brick{i}", *b, "brick") for i, b in enumerate(bricks)] + [box(f"bed{i}", *m, "mortar") for i, m in enumerate(mortar)]
geoms += [box(f"pal{i}", *p, "brick", 'euler="0 0 1.5708"') for i, p in enumerate(pallet)]
geoms.append(box("pallet", 0.25, -0.53, 0.012, 0.16, 0.22, 0.012, "wood"))
# 목표 윤곽(파랑 선): 다음 슬롯
nx, ny, nz, nl = next_slot
scene = f'''<mujoco model="concept_wall">
  <compiler angle="radian"/>
  <option gravity="0 0 0"/>
  <asset>
    <model name="ur5e" file="universal_robots_ur5e/ur5e_2f85.xml"/>
    <texture type="skybox" builtin="gradient" rgb1="1 1 1" rgb2="0.86 0.9 0.94" width="256" height="256"/>
    <texture name="grid" type="2d" builtin="checker" rgb1="0.93 0.93 0.93" rgb2="0.84 0.84 0.84" width="512" height="512"/>
    <material name="grid" texture="grid" texrepeat="10 10" reflectance="0.05"/>
    <material name="brick" rgba="0.80 0.38 0.24 1"/>
    <material name="mortar" rgba="0.60 0.58 0.54 1"/>
    <material name="wood" rgba="0.72 0.6 0.42 1"/>
    <material name="ped" rgba="0.30 0.32 0.35 1"/>
  </asset>
  <visual><global offwidth="1600" offheight="1200"/><headlight diffuse="0.7 0.7 0.7" ambient="0.35 0.35 0.35"/></visual>
  <worldbody>
    <light pos="1.5 -1.5 3" dir="-0.4 0.4 -1" diffuse="0.8 0.8 0.8" castshadow="true"/>
    <light pos="-1 1 2.5" dir="0.3 -0.3 -1" diffuse="0.4 0.4 0.4" castshadow="false"/>
    <geom name="floor" type="plane" size="4 4 0.1" material="grid"/>
    <geom name="pedestal" type="box" pos="0 0 0.20" size="0.14 0.14 0.20" material="ped"/>
    <frame pos="0 0 0.40"><attach model="ur5e" body="base" prefix="arm_"/></frame>
    {chr(10).join("    " + g for g in geoms)}
    <site name="slot" type="box" pos="{nx:.4f} {ny:.4f} {nz:.4f}" size="{W/2:.4f} {nl/2:.4f} {H/2:.4f}" rgba="0.2 0.4 0.9 0.35"/>
    <body name="held" pos="0 0 1" mocap="true"><geom type="box" size="{W/2:.4f} {L/2:.4f} {H/2:.4f}" material="brick" quat="0.7071 0 0 0.7071"/></body>
  </worldbody>
</mujoco>'''
open(MEN + "/concept_scene.xml", "w", encoding="utf-8").write(scene)
m = mujoco.MjModel.from_xml_path(MEN + "/concept_scene.xml"); d = mujoco.MjData(m)
print("model ok: nq", m.nq, "bodies", m.nbody, flush=True)

# 3) 간단 IK: g_pinch 사이트를 다음 슬롯 위 (z + 0.12) 에, 집게가 아래를 향하도록
jn = [f"arm_{n}" for n in ("shoulder_pan_joint", "shoulder_lift_joint", "elbow_joint", "wrist_1_joint", "wrist_2_joint", "wrist_3_joint")]
qi = [m.joint(n).qposadr[0] for n in jn]; di = [m.joint(n).dofadr[0] for n in jn]
d.qpos[qi] = [-1.5708, -1.5708, 1.5708, -1.5708, -1.5708, 0]
sid = m.site("arm_g_pinch").id
target = np.array([nx, ny, nz + 0.11])
for it in range(400):
    mujoco.mj_forward(m, d)
    p = d.site_xpos[sid].copy(); R = d.site_xmat[sid].reshape(3, 3)
    # 자세: 사이트 z축이 -world z (아래) 를 향하고, 사이트 x축이 벽 길이 방향(y)과 나란히
    zc = R[:, 2]; err_rot = np.cross(zc, np.array([0, 0, -1.0]))
    xc = R[:, 0]; err_rot2 = np.cross(xc, np.array([0, 1.0, 0])) * 0.5
    err_pos = target - p
    jp = np.zeros((3, m.nv)); jr = np.zeros((3, m.nv)); mujoco.mj_jacSite(m, d, jp, jr, sid)
    Jm = np.vstack([jp[:, di], jr[:, di]]); e = np.concatenate([err_pos * 4, (err_rot + err_rot2) * 2])
    dq = np.linalg.solve(Jm.T @ Jm + 0.05 * np.eye(6), Jm.T @ e)
    d.qpos[qi] += 0.25 * dq
    if np.linalg.norm(err_pos) < 0.002 and np.linalg.norm(err_rot) < 0.02:
        break
mujoco.mj_forward(m, d)
print("IK iters", it, "pos err mm", 1000 * np.linalg.norm(target - d.site_xpos[sid]), flush=True)
# 집게에 벽돌: pinch 사이트 위치에 mocap 벽돌, 손가락 살짝 닫기
hb = m.body("held").mocapid[0]
d.mocap_pos[hb] = d.site_xpos[sid] + np.array([0, 0, -0.01]); d.mocap_quat[hb] = [1, 0, 0, 0]
for jname in ("arm_g_right_driver_joint", "arm_g_left_driver_joint"):
    try:
        d.qpos[m.joint(jname).qposadr[0]] = 0.25
    except Exception as ex:
        print("finger joint", jname, ex)
mujoco.mj_forward(m, d)

R = mujoco.Renderer(m, 1200, 1600)
def shot(name, lookat, dist, az, el):
    c = mujoco.MjvCamera(); c.type = mujoco.mjtCamera.mjCAMERA_FREE; c.lookat[:] = lookat; c.distance = dist; c.azimuth = az; c.elevation = el
    R.update_scene(d, camera=c); im = R.render().copy(); Image.fromarray(im).save(OUT + f"/{name}.png"); return im
views = {"iso": ((0.35, -0.1, 0.25), 1.9, 150, -22), "front": ((0.45, 0.0, 0.2), 1.7, 180, -12), "iso2": ((0.4, -0.15, 0.2), 1.8, 215, -25)}
ims = {k: shot(k, *v) for k, v in views.items()}
R.close()
# 캡션 붙인 최종본
im = Image.fromarray(ims["iso"]); dr = ImageDraw.Draw(im); f = ImageFont.truetype(FONT, 34); fs = ImageFont.truetype(FONT, 26)
dr.rectangle((0, 0, 1600, 110), fill=(20, 35, 56))
dr.text((24, 14), "대형 환경 콘셉트 (중간 2 이후): UR5e + Robotiq 2F-85, 실척 벽돌 190×90×57 mm, 줄눈 10 mm, 3단×5개", font=f, fill="white")
dr.text((24, 64), "MuJoCo Menagerie 모델 · 파란 상자 = 다음 슬롯 · 공급 팔레트에서 1개씩 · 벽돌 1개 = 에피소드 1개 · 렌더 전용(물리·학습 전)", font=fs, fill=(194, 216, 232))
im.save(IMG + "concept_ur5e_wall.png")
print("done", flush=True)
