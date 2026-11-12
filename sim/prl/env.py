"""건식 쌓기 환경 dry_v1: wall3.scene.WallEnv에서 모르타르를 뺀 것 + 카메라 후보.

- 모르타르 판을 깔지 않고(bed), 놓인 벽돌을 고정하지 않는다(cure). 놓인 벽돌은 마찰로만 서 있다.
- 설계 높이는 건식 기준(z = H/2 + (단 − 1) × 57 mm). 가로 좌표 · 로봇 · 집게 · 공급대 · 흩어짐 · 제어 주기는 main_v1과 같다.
- 카메라: 고정 후보(prl.config.FIXED_CAMS)와 손목 후보(H0 = wall3의 wrist, H1, H2)를 모델에 넣는다. 카메라는 물리에 영향이 없다.
- 장 단위 장면(reset_piece): 자리 k보다 앞선 벽돌을 설계 위치에 미리 놓는다.
wall3의 파일은 고치지 않는다(상속).
"""
import cv2
import mujoco
import numpy as np

from wall3 import gripper as G
from wall3.config import W, H
from wall3.scene import WallEnv, _look_at, _quat_from_R, _quat_rotmat, yaw_quat
from prl import config as C


def cam_model_name(name):
    return "wrist" if name == "H0" else name


class DryEnv(WallEnv):
    def __init__(self, cfg=None, fixed_cams=None, extra_cams=None):
        """fixed_cams: {name: spec} to add (default: every candidate in prl.config.FIXED_CAMS).
        extra_cams: more fixed cameras, e.g. the G1 grid (same spec keys: pos, target, up, fovy)."""
        self.cfg = cfg or C.dry_scene()
        if self.cfg.env_version != C.ENV_VERSION:
            raise ValueError(f"DryEnv needs env_version {C.ENV_VERSION!r}")
        self.fixed_cams = dict(C.FIXED_CAMS if fixed_cams is None else fixed_cams)
        self.fixed_cams.update(extra_cams or {})
        self.design = C.dry_design()
        self.n = len(self.design)
        self.cal = G.calibrate(self.cfg.gripper, W)
        self.spec = self._build_spec()
        self.model = self.spec.compile()
        self.data = mujoco.MjData(self.model)
        self._index()
        self.renderer = {}
        self.rng = np.random.default_rng(0)
        self.vopt = mujoco.MjvOption()
        self.vopt.sitegroup[:] = 0
        self.cam_fovy = {n: float(self.model.cam_fovy[self.model.camera(cam_model_name(n)).id])
                         for n in list(self.fixed_cams) + list(C.WRIST_CAMS)}

    # ------------------------------------------------------------------ model
    def _build_spec(self):
        s = super()._build_spec()
        wb = s.worldbody
        for name, c in self.fixed_cams.items():
            wb.add_camera(name=name, pos=list(c["pos"]), quat=_look_at(c["pos"], c["target"], up=c.get("up", (0, 0, 1))),
                          fovy=float(c["fovy"]))
        att = s.site("attachment_site")
        qa = np.asarray(att.quat, float)
        Ra = _quat_rotmat(qa / np.linalg.norm(qa))
        pa = np.asarray(att.pos, float)
        w3 = s.body("wrist_3_link")
        self.wrist_mount = {}
        for name, c in C.WRIST_CAMS.items():
            if "pos" not in c:
                continue
            cam_p = pa + Ra @ np.asarray(c["pos"], float)
            tgt = pa + Ra @ (np.array([0.0, 0.0, self.cal["pad_center_depth"]]) + np.asarray(c["target_tcp_offset"], float))
            f = tgt - cam_p; f /= np.linalg.norm(f)
            x = Ra @ np.array([0.0, 1.0, 0.0])
            x = x - f * (x @ f); x /= np.linalg.norm(x)
            y = np.cross(x, f)
            w3.add_camera(name=name, pos=cam_p, quat=_quat_from_R(np.stack([x, y, -f], axis=1)), fovy=float(c["fovy"]))
            self.wrist_mount[name] = {"pos_gripper": list(c["pos"]), "target_tcp_offset": list(c["target_tcp_offset"])}
        return s

    # ------------------------------------------------------------------ no mortar
    def reset(self, seed: int, arm_q=None):
        super().reset(seed, arm_q)
        self.bed_laid = {1: 0, 2: 0}          # WallEnv.step lays a bed only while bed_laid < 0: never here
        return self

    def _update_cure(self):                   # placed bricks are never welded
        return

    def _update_bed(self, bnd):               # never called (bed_laid >= 0); kept as a guard
        raise RuntimeError("dry_v1 has no mortar bed")

    def reset_piece(self, seed: int, k: int, arm_q=None, settle_steps: int = 10):
        """Scene of the brick-level test: bricks 0 .. k−1 at their design poses, bricks k .. 15 on the supply table with the
        scatter of `seed` (the same draw as the wall-level reset). The arm holds `arm_q` while the scene settles."""
        self.reset(seed, arm_q)
        d = self.data
        for i in range(k):
            s = self.design[i]
            a = self.brick_qadr[i]
            d.qpos[a:a + 3] = [s["x"], s["y"], s["z"]]
            d.qpos[a + 3:a + 7] = yaw_quat(s["yaw"])
        mujoco.mj_forward(self.model, d)
        q = self.last_action
        for _ in range(settle_steps):
            self.step(q[:6], float(q[6]))
        self.t = 0
        return self

    # ------------------------------------------------------------------ images
    def render_raw(self, cam, depth=False):
        """Raw 1280 × 960 image of a candidate camera (colour uint8, or depth in metres along the optical axis)."""
        return self.render(cam_model_name(cam), C.RAW_W, C.RAW_H, depth=depth)

    def policy_image(self, cam):
        return letterbox(self.render_raw(cam))

    def cam_pose(self, cam):
        i = self.model.camera(cam_model_name(cam)).id
        return self.data.cam_xpos[i].copy(), self.data.cam_xmat[i].reshape(3, 3).copy()


def letterbox(raw, size=C.POLICY_IMG):
    """Policy input: the raw image scaled keeping its aspect ratio (area averaging) and padded to size × size."""
    h, w = raw.shape[:2]
    s = size / max(h, w)
    nw, nh = int(round(w * s)), int(round(h * s))
    small = cv2.resize(raw, (nw, nh), interpolation=cv2.INTER_AREA)
    out = np.zeros((size, size, 3), np.uint8)
    y0, x0 = (size - nh) // 2, (size - nw) // 2
    out[y0:y0 + nh, x0:x0 + nw] = small
    return out


def noisy_depth(depth, fovy_deg, kind, rng):
    """Stereo-like depth noise: σ_z = z² × disparity noise ÷ (focal length × baseline), spatially correlated over the
    matching window, invalid (nan) outside the sensor range. depth: metres along the optical axis (H × W)."""
    p = C.DEPTH_NOISE[kind]
    f = C.focal_px(fovy_deg, depth.shape[0])
    fb = f * p["baseline_m"]
    k = int(C.DEPTH_NOISE["corr_px"])
    n = rng.standard_normal(depth.shape).astype(np.float32)
    if k > 1:
        n = cv2.blur(n, (k, k), borderType=cv2.BORDER_REFLECT) * k      # box mean of k² samples: std 1/k → back to 1
    with np.errstate(divide="ignore", invalid="ignore"):
        disp = fb / depth + p["subpixel_px"] * n
        z = fb / disp
    lo, hi = p["range_m"]
    z[~((depth >= lo) & (depth <= hi)) | (disp <= 0)] = np.nan
    return z.astype(np.float32)
