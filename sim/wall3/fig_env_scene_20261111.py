"""실험 환경 그림 (2026-11-11): 로봇 팔 · 카메라 3대 · 벽돌이 한 장면에 모두 보이는 설명용 그림. 결과가 아니다.

- 사용자 요청(11-11): "실험환경세팅에서 로봇팔과 카메라와 벽돌이 전부 다 보이는 그림".
- 장면: 평가와 같은 환경 설정(main_v1_eval)에서 시연기(WallExpert, 참값을 쓰는 시연 생성기)를 시작값 SEED로 돌려,
  K번째(0부터) 벽돌을 자리 위에서 내리기 시작하는 순간에 멈춘 상태. 벽에 8장, 집게에 1장, 공급대에 7장이 있다.
- 카메라 표식: 시뮬레이터의 카메라는 몸체가 없는 점이다. 정면 · 작업대 카메라 자리에 상자 + 렌즈 + 짧은 시야 모서리 + 시선(가는 선)을
  그려 넣었다(크기는 과장). 표식은 그림에만 있고 실험 장면에는 없다. 손목 카메라는 집게에 붙어 있어 이름만 붙였다.
- 오른쪽 세 장: 같은 순간 세 카메라의 시야. 인쇄용으로 CAM_PX 화소로 그렸다(정책 입력은 128 × 128).
- 화면 밖 렌더 크기(hi_w · hi_h)만 키웠다. 물리 · 카메라 위치 · 시야각은 평가 설정 그대로다.
- 출력이 이미 있으면 덮어쓰지 않는다. MuJoCo + EGL이 필요하다(윈도우에서는 커밋된 PNG를 그대로 쓴다).

실행: cd sim && MUJOCO_GL=egl MPLCONFIGDIR=<임시>/mpl PYTHONPATH=. venv/bin/python -m wall3.fig_env_scene_20261111 [--out-dir <폴더>]
"""
import argparse, hashlib, os, subprocess

os.environ.setdefault("MUJOCO_GL", "egl")
from pathlib import Path

import mujoco
import numpy as np
from PIL import Image

from wall3.config import scene_config
from wall3.expert import WallExpert
from wall3.poster_ksarc_20261111 import BLUE, INK, INK2, KS, REPO, mpl_setup
from wall3.scene import WallEnv

VERSION, SEED, K, PHASE = "main_v1_eval", 700300, 8, "place_descend"
VIEW = dict(azimuth=-38.0, elevation=-14.0, distance=3.4, lookat=(0.12, 0.42, 0.88))
SCENE_PX = (2280, 1200)                     # 가로 × 세로
CAM_PX = 512
OUT = KS / "그림_실험환경_20261111"
MARK = (0.165, 0.471, 0.839, 1.0)           # BLUE
BODY = (0.13, 0.14, 0.16, 1.0)
CAM_NAMES = [("front", "정면 카메라", "정책 입력"), ("top", "작업대 카메라 (위)", "정책 입력 + 검측 G2 · G3\n(색 + 깊이 영상)"),
             ("wrist", "손목 카메라", "정책 입력")]


class _Stop(Exception):
    pass


def build_state():
    """평가 환경에서 시연기를 돌려 K번째 벽돌을 내리기 시작하는 순간에 멈춘 env를 돌려준다."""
    env = WallEnv(scene_config(VERSION, hi_w=2400, hi_h=1800))
    ex = WallExpert(env)

    def cb(env_, action, phase, k):
        if k == K and phase == PHASE:
            raise _Stop

    try:
        ex.run(SEED, on_step=cb)
        raise SystemExit("시연이 멈춤 조건에 닿지 않고 끝남")
    except _Stop:
        pass
    return env


def _add(scn, gtype, size, pos, mat, rgba):
    g = scn.geoms[scn.ngeom]
    mujoco.mjv_initGeom(g, gtype, np.asarray(size, float), np.asarray(pos, float), np.asarray(mat, float).reshape(9),
                        np.asarray(rgba, np.float32))
    g.category = mujoco.mjtCatBit.mjCAT_DECOR
    scn.ngeom += 1
    return g


def _line(scn, p0, p1, radius, rgba):
    g = _add(scn, mujoco.mjtGeom.mjGEOM_CAPSULE, np.zeros(3), np.zeros(3), np.eye(3), rgba)
    mujoco.mjv_connector(g, mujoco.mjtGeom.mjGEOM_CAPSULE, radius, np.asarray(p0, float), np.asarray(p1, float))


def cam_marker(scn, m, d, name, target, cone=0.42):
    """카메라 자리에 상자 + 렌즈 + 짧은 시야 모서리(cone m) + 시선(target까지)을 그린다. 정사각 시야(정책 입력) 기준."""
    cid = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_CAMERA, name)
    p, R = d.cam_xpos[cid].copy(), d.cam_xmat[cid].reshape(3, 3).copy()       # R 열 = 오른쪽 · 위 · 뒤 (카메라는 −z를 본다)
    _add(scn, mujoco.mjtGeom.mjGEOM_BOX, (0.075, 0.055, 0.06), p + R[:, 2] * 0.09, R, BODY)
    _add(scn, mujoco.mjtGeom.mjGEOM_CYLINDER, (0.042, 0.032, 0), p, R, MARK)
    t = np.tan(np.radians(m.cam_fovy[cid]) / 2) * cone
    cs = [p + R @ np.array([sx * t, sy * t, -cone]) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    for c in cs:
        _line(scn, p, c, 0.004, MARK)
    for a, b in zip(cs, cs[1:] + cs[:1]):
        _line(scn, a, b, 0.004, MARK)
    _line(scn, p, target, 0.0022, MARK)
    return p


def render_scene(env):
    m, d = env.model, env.data
    W, H = SCENE_PX
    cam = mujoco.MjvCamera()
    cam.type = mujoco.mjtCamera.mjCAMERA_FREE
    cam.lookat[:] = VIEW["lookat"]
    cam.distance, cam.azimuth, cam.elevation = VIEW["distance"], VIEW["azimuth"], VIEW["elevation"]
    r = mujoco.Renderer(m, H, W)
    r.update_scene(d, camera=cam, scene_option=env.vopt)
    gl = r.scene.camera
    pos = (np.array(gl[0].pos) + np.array(gl[1].pos)) / 2
    fwd, up = np.array(gl[0].forward, float), np.array(gl[0].up, float)
    right = np.cross(fwd, up)
    near, bot, top = float(gl[0].frustum_near), float(gl[0].frustum_bottom), float(gl[0].frustum_top)
    hh = (top - bot) / 2
    hw = hh * W / H
    # 흰 배경판: 시선에 직각, 멀리. emission으로 조명과 무관하게 흰색.
    g = _add(r.scene, mujoco.mjtGeom.mjGEOM_BOX, (200, 200, 0.01), pos + fwd * 60, np.column_stack([right, up, -fwd]), (1, 1, 1, 1))
    g.emission = 1.0
    cam_marker(r.scene, m, d, "front", (0.0, 0.55, 0.10))
    cam_marker(r.scene, m, d, "top", (0.0, 0.60, 0.0))
    img = r.render().copy()
    r.close()

    def project(p):
        v = np.asarray(p, float) - pos
        z = v @ fwd
        return (W / 2 * (1 + (v @ right) / z * near / hw), H / 2 * (1 - ((v @ up) / z * near - (top + bot) / 2) / hh))

    return img, project


def compose(scene, project, cams, anchors, path, plt, w_cm=26.6, h_cm=9.6):
    W, H = SCENE_PX
    fig = plt.figure(figsize=(w_cm / 2.54, h_cm / 2.54), dpi=300)
    sw = h_cm * W / H                                   # 장면 폭 (cm)
    ax = fig.add_axes([0, 0, sw / w_cm, 1])
    ax.imshow(scene)
    ax.set_xlim(0, W)
    ax.set_ylim(H, 0)
    ax.axis("off")
    for text, anchor, (tx, ty), ha in anchors:
        px, py = project(anchor)
        ax.annotate(text, xy=(px, py), xytext=(tx * W, ty * H), ha=ha, va="center", fontsize=10.5, color=INK, fontweight="bold",
                    bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="#c3c9d1", lw=0.7),
                    arrowprops=dict(arrowstyle="-", color=INK, lw=0.9, shrinkA=0, shrinkB=2))
        ax.plot([px], [py], marker="o", ms=3.2, color=INK, zorder=5)
    # 오른쪽: 카메라 시야 세 장 + 이름 · 쓰임
    x0 = sw + 0.45
    th = (h_cm - 0.95 - 2 * 0.22 - 0.1) / 3              # 시야 한 장 높이 (cm)
    fig.text(x0 / w_cm, 1 - 0.12 / h_cm, "세 카메라의 시야", ha="left", va="top", fontsize=11.5, color=INK, fontweight="bold")
    for i, (name, label, use) in enumerate(CAM_NAMES):
        yb = h_cm - 0.95 - (i + 1) * th - i * 0.22
        a = fig.add_axes([x0 / w_cm, yb / h_cm, th / w_cm, th / h_cm])
        a.imshow(cams[name])
        a.set_xticks([])
        a.set_yticks([])
        for s in a.spines.values():
            s.set_edgecolor("#c3c9d1")
            s.set_linewidth(0.8)
        fig.text((x0 + th + 0.3) / w_cm, (yb + th * 0.72) / h_cm, label, ha="left", va="center", fontsize=11, color=INK, fontweight="bold")
        fig.text((x0 + th + 0.3) / w_cm, (yb + th * 0.36) / h_cm, use, ha="left", va="center", fontsize=9.5, color=INK2, linespacing=1.25)
    fig.savefig(path, dpi=300, facecolor="white")
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default=str(OUT))
    a = ap.parse_args()
    od = Path(a.out_dir)
    png, md = od / "실험환경_로봇_카메라_벽돌.png", od / "설명.md"
    parts = {"scene": od / "장면_표식만.png", "front": od / "카메라_정면.png", "top": od / "카메라_작업대.png", "wrist": od / "카메라_손목.png"}
    for p in [png, md, *parts.values()]:
        if p.exists():
            raise SystemExit(f"{p} 이미 있음: 덮어쓰지 않음")
    od.mkdir(parents=True, exist_ok=True)
    env = build_state()
    m, d = env.model, env.data
    scene, project = render_scene(env)
    cams = {n: env.render(n, CAM_PX, CAM_PX) for n, _, _ in CAM_NAMES}
    cid = lambda n: mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_CAMERA, n)
    bp = np.array([env.brick_pose(i)[0] for i in range(env.n)])
    held = int(np.argmin(np.linalg.norm(bp - d.xpos[env.grip_body], axis=1)))        # 집게에 가장 가까운 벽돌
    on_table = [i for i in range(env.n) if bp[i][1] < -0.1]
    on_wall = [i for i in range(env.n) if i != held and i not in on_table]
    assert len(on_table) == 16 - K - 1 and len(on_wall) == K and all(abs(bp[i][1] - 0.6) < 0.06 for i in on_wall), (held, on_table, on_wall)
    tb = bp[max(on_table, key=lambda i: project(bp[i])[0])]             # 화면에서 가장 오른쪽 공급 벽돌
    wl = bp[max(on_wall, key=lambda i: project(bp[i])[1])]              # 화면에서 가장 아래(앞쪽) 벽 벽돌
    arm = (d.xpos[m.body("upper_arm_link").id] + d.xpos[m.body("forearm_link").id]) / 2
    anchors = [("작업대 카메라 (위)", d.cam_xpos[cid("top")], (0.30, 0.085), "right"),
               ("정면 카메라", d.cam_xpos[cid("front")], (0.10, 0.46), "center"),
               ("손목 카메라", d.cam_xpos[cid("wrist")], (0.33, 0.37), "center"),
               ("로봇 팔 UR10e + 집게", arm, (0.80, 0.24), "center"),
               ("공급대의 벽돌", tb, (0.88, 0.50), "center"),
               ("쌓는 벽 (3단 16자리)", wl, (0.24, 0.91), "center")]
    Image.fromarray(scene).save(parts["scene"])
    for n in ("front", "top", "wrist"):
        Image.fromarray(cams[n]).save(parts[n])
    plt = mpl_setup()
    compose(scene, project, cams, anchors, png, plt)

    sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()[:16]
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True).stdout.strip()
    L = ["# 실험 환경 그림: 로봇 팔 · 카메라 · 벽돌 (설명용, 결과 아님)\n",
         f"> 2026-11-11. 그림: [`{png.name}`]({png.name}). 스크립트: `sim/wall3/fig_env_scene_20261111.py` (커밋 {commit[:8]} 다음에 만듦).",
         "> 포스터 3.1절 '실험 환경 세팅'에 쓴다. 숫자 결과가 아니라 장면 설명이다.\n",
         "## 사실\n",
         "| 항목 | 값 |", "|---|---|",
         f"| 환경 설정 | `scene_config(\"{VERSION}\")` (평가와 같음). 화면 밖 렌더 크기만 2400 × 1800으로 키움(물리 · 카메라는 그대로) |",
         f"| 장면 | 시연기 `WallExpert`를 시작값 {SEED}으로 돌려 {K + 1}번째 벽돌을 자리 위에서 내리기 시작한 순간 (`{PHASE}`, 환경 스텝 {env.t}) |",
         f"| 벽돌 | 벽에 {len(on_wall)}장 · 집게에 1장 · 공급대에 {len(on_table)}장 |",
         f"| 보는 방향 | 자유 카메라: 방위 {VIEW['azimuth']}° · 높이각 {VIEW['elevation']}° · 거리 {VIEW['distance']} m · 중심 {VIEW['lookat']} |",
         "| 정면 카메라 | 위치 " + str(d.cam_xpos[cid("front")].round(3).tolist()) + f" m · 세로 시야각 {m.cam_fovy[cid('front')]:.0f}° · 정책 입력 |",
         "| 작업대 카메라 (위) | 위치 " + str(d.cam_xpos[cid("top")].round(3).tolist()) + f" m · 세로 시야각 {m.cam_fovy[cid('top')]:.0f}° · 정책 입력 + 검측 G2 · G3(1280 × 960 색 + 깊이) |",
         f"| 손목 카메라 | 집게에 붙음 · 세로 시야각 {m.cam_fovy[cid('wrist')]:.0f}° · 정책 입력 |",
         f"| 오른쪽 세 장 | 같은 순간 세 카메라의 시야를 {CAM_PX} × {CAM_PX} 화소로 그린 것. 정책 입력은 같은 카메라의 128 × 128 영상 |\n",
         "## 그림에만 있는 것 (실험 장면에는 없음)\n",
         "- **카메라 표식**: 시뮬레이터의 카메라는 몸체가 없는 점이다. 정면 · 작업대 카메라 자리에 상자 + 파란 렌즈 + 짧은 시야 모서리(0.42 m) + "
         "시선(카메라에서 보는 점까지 가는 선)을 그려 넣었다. 크기는 보이도록 키운 것이고 실제 카메라 크기가 아니다. 표식은 그림자를 드리우지 않게 했다.",
         "- **흰 배경**: 시뮬레이터 배경은 검정이라, 멀리 흰 판을 두어 흰색으로 바꿨다.",
         "- **이름표와 이음선**: matplotlib으로 얹었다.\n",
         "## 주의\n",
         "- 이 장면은 **시연기**(참값을 쓰는 시연 생성기)가 만든 것이다. 학습 정책 + 검측(Full)이 만든 장면이 아니다. 환경 구성만 보이는 용도다.",
         "- 검측 G0 · G1 · H는 카메라를 쓰지 않는다(도면 · 관절값 · 손목 힘 · 집게 각도). 포스터 2절 표와 같다.\n",
         "## 파일 (sha256 앞 16)\n"]
    L += [f"- `{p.name}` {sha(p)}" for p in [png, *parts.values()]]
    L += ["", "## 다시 만들기 (MuJoCo + EGL 필요 · 출력이 있으면 덮어쓰지 않음)\n", "```",
          "cd sim && MUJOCO_GL=egl MPLCONFIGDIR=/tmp/mpl PYTHONPATH=. venv/bin/python -m wall3.fig_env_scene_20261111 --out-dir <새 폴더>", "```"]
    md.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("만듦:", png, md)


if __name__ == "__main__":
    main()
