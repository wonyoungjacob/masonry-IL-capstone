"""3층 벽체 장면: UR10e(받침대 0.6 m) + Robotiq 2F-140(A1+) + 콘크리트 표준벽돌 16장 + 공급대 + 모르타르(mortarB 일반화).

- 로봇·집게 모델 파일은 고치지 않는다. UR10e는 Menagerie 파일을 MjSpec으로 읽어 받침대 위로 옮기고, 집게는 wall3.gripper로 붙인다.
- 모르타르는 brick_sim(mortarB) 모델 그대로: 아래 단 벽돌이 모두 제자리에 놓여 2 s 정지하면 그 실제 윗면 위에 두께 10 mm 순응층
  (벽돌마다 한 장 + 세로줄눈 위 다리 한 장, mocap)을 깔고, 벽 위치에 놓인 벽돌은 2 s 정지 뒤 고정(weld)한다. 1단 아래는 없다.
  침하량은 두께에 비례해 0.5 mm × 10 / 4.737 = 1.06 mm, 감쇠비 1, 계면 마찰 0.75.
- 카메라: front(벽 앞면 쪽에서 고정), top(벽 위 고정), wrist(손목), 정책용 128×128. 검측용 top 고해상도 RGB-D(1280×960).
  overview(녹화용 자유 시점 대신 쓰는 고정 시점, 정책 입력 아님).
"""
from pathlib import Path

import mujoco
import numpy as np

from wall3 import gripper as G
from wall3.config import SceneConfig, design_slots, L_FULL, L_HALF, W, H, RHO, MU_BRICK, JOINT, WALL_Y

SIM = Path(__file__).resolve().parents[1]
UR10E_XML = SIM / "menagerie/universal_robots_ur10e/ur10e.xml"
ARM_JOINTS = ["shoulder_pan_joint", "shoulder_lift_joint", "elbow_joint", "wrist_1_joint", "wrist_2_joint", "wrist_3_joint"]
ARM_ACTS = ["shoulder_pan", "shoulder_lift", "elbow", "wrist_1", "wrist_2", "wrist_3"]
GRIP_ACTS = [G.PREFIX + "finger_1", G.PREFIX + "finger_2"]
HOME_Q = np.array([np.pi / 2, -1.9, 1.9, -1.571, -1.571, 0.0])      # arm folded above the base, facing the wall


def _quat_from_R(R):
    q = np.zeros(4)
    mujoco.mju_mat2Quat(q, np.asarray(R, float).ravel())
    return q


def _look_at(pos, target, up=(0, 0, 1)):
    f = np.asarray(target, float) - np.asarray(pos, float); f /= np.linalg.norm(f)
    x = np.cross(f, up); x /= np.linalg.norm(x)
    y = np.cross(x, f)
    return _quat_from_R(np.stack([x, y, -f], axis=1))


def _quat_rotmat(q):
    R = np.zeros(9)
    q = np.asarray(q, float)
    mujoco.mju_quat2Mat(R, q / np.linalg.norm(q))
    return R.reshape(3, 3)


def yaw_quat(yaw):
    return np.array([np.cos(yaw / 2), 0.0, 0.0, np.sin(yaw / 2)])


class WallEnv:
    def __init__(self, cfg: SceneConfig | None = None):
        self.cfg = cfg or SceneConfig()
        if len(self.cfg.supply_slots) != 16:
            raise ValueError("SceneConfig.supply_slots needs 16 (x, y) slot centres")
        self.design = design_slots()
        self.n = len(self.design)
        self.cal = G.calibrate(self.cfg.gripper, W)
        self.spec = self._build_spec()
        self.model = self.spec.compile()
        self.data = mujoco.MjData(self.model)
        self._index()
        self.renderer = {}
        self.rng = np.random.default_rng(0)
        self.vopt = mujoco.MjvOption()          # robosuite's visual helper sites (group 1) and our TCP site (group 4) hidden
        self.vopt.sitegroup[:] = 0

    # ------------------------------------------------------------------ model
    def _build_spec(self):
        c = self.cfg
        s = mujoco.MjSpec.from_file(str(UR10E_XML))
        s.option.timestep = c.timestep
        s.option.cone = mujoco.mjtCone.mjCONE_ELLIPTIC
        s.option.impratio = c.impratio
        s.option.noslip_iterations = c.noslip_iterations
        s.visual.global_.offwidth = c.hi_w
        s.visual.global_.offheight = c.hi_h
        s.visual.quality.shadowsize = 2048
        # viewer camera marker size = meansize (0.50 m here, set by the floor/table) × scale.camera. The default 0.3 drew a
        # 15 cm box that looked like the wrist camera overlapping the gripper; the camera itself is a point 47.5 mm clear of
        # the nearest gripper geometry and has no body. Visual only: images, physics and data are unchanged.
        s.visual.scale.camera = 0.03
        s.visual.headlight.ambient = [0.25, 0.25, 0.25]
        s.visual.headlight.diffuse = [0.35, 0.35, 0.35]
        s.visual.headlight.specular = [0.05, 0.05, 0.05]
        s.light("spotlight").diffuse = [0.3, 0.3, 0.3]          # UR10e file's spotlight, dimmed (visual only)
        tex = s.add_texture(name="grid", type=mujoco.mjtTexture.mjTEXTURE_2D, builtin=mujoco.mjtBuiltin.mjBUILTIN_CHECKER,
                            rgb1=[0.60, 0.60, 0.58], rgb2=[0.52, 0.52, 0.50], width=300, height=300,
                            mark=mujoco.mjtMark.mjMARK_EDGE, markrgb=[0.45, 0.45, 0.43])
        mat = s.add_material(name="grid", texrepeat=[10, 10], texuniform=True, reflectance=0.02)
        mat.textures[mujoco.mjtTextureRole.mjTEXROLE_RGB] = "grid"
        s.body("base").pos = [0.0, 0.0, c.pedestal_h]
        wb = s.worldbody
        wb.add_light(name="sun", pos=[0.4, 0.2, 2.5], dir=[-0.15, 0.1, -1], type=mujoco.mjtLightType.mjLIGHT_DIRECTIONAL,
                     castshadow=1, diffuse=[0.45, 0.45, 0.45], specular=[0.1, 0.1, 0.1])
        wb.add_light(name="fill", pos=[-0.6, 1.5, 1.8], dir=[0.3, -0.6, -1], type=mujoco.mjtLightType.mjLIGHT_DIRECTIONAL,
                     castshadow=0, diffuse=[0.2, 0.2, 0.2], specular=[0, 0, 0])
        fr = [MU_BRICK, 0.005, 0.0001]
        wb.add_geom(name="floor", type=mujoco.mjtGeom.mjGEOM_PLANE, size=[3, 3, 0.05], friction=fr, material="grid")
        ph = c.pedestal_half
        wb.add_geom(name="pedestal", type=mujoco.mjtGeom.mjGEOM_BOX, size=[ph, ph, c.pedestal_h / 2],
                    pos=[0, 0, c.pedestal_h / 2], rgba=[0.25, 0.25, 0.27, 1], friction=fr)
        tx, ty = c.table_x, c.table_y   # table clear of the pedestal
        wb.add_geom(name="table", type=mujoco.mjtGeom.mjGEOM_BOX,
                    size=[(tx[1] - tx[0]) / 2, (ty[1] - ty[0]) / 2, c.table_h / 2],
                    pos=[(tx[0] + tx[1]) / 2, (ty[0] + ty[1]) / 2, c.table_h / 2], rgba=[0.55, 0.42, 0.30, 1], friction=fr)
        # chalk line (먹선) on the floor along the design front face, and the wall end ticks (visual only)
        yf = WALL_Y + W / 2
        vis = dict(contype=0, conaffinity=0, group=1)
        wb.add_geom(name="chalk", type=mujoco.mjtGeom.mjGEOM_BOX, size=[0.56, 0.0008, 0.0002], pos=[0, yf, 0.0002],
                    rgba=[0.06, 0.06, 0.08, 1], **vis)
        # cameras
        wb.add_camera(name="front", pos=[0.0, 1.75, 0.75], quat=_look_at([0.0, 1.75, 0.75], [0.0, 0.55, 0.10]), fovy=50)
        wb.add_camera(name="top", pos=[0.0, 0.60, 1.85], quat=_look_at([0.0, 0.60, 1.85], [0.0, 0.60, 0.0], up=(0, 1, 0)), fovy=45)
        wb.add_camera(name="overview", pos=[2.1, -1.5, 1.9], quat=_look_at([2.1, -1.5, 1.9], [0.0, 0.0, 0.25]), fovy=50)
        # bricks
        for i, d in enumerate(self.design):
            b = wb.add_body(name=f"brick_{i}", pos=[0, 0, 0])
            b.add_freejoint(name=f"brick_{i}_free")
            # red brick colour common on Korean sites (적벽돌), two close shades so neighbours stay distinguishable.
            # Colour only (2026-10-16): density 2,000 kg/m3, friction 0.6 and size unchanged; mortar colour unchanged.
            col = [0.64, 0.29, 0.21, 1] if i % 2 == 0 else [0.58, 0.26, 0.19, 1]
            b.add_geom(name=f"brick_{i}", type=mujoco.mjtGeom.mjGEOM_BOX, size=[d["L"] / 2, W / 2, H / 2],
                       mass=d["L"] * W * H * RHO, friction=fr, rgba=col, condim=3)
        # mortar beds: boundary 1 (on course 1) and 2 (on course 2); one slab per lower brick + one per head joint
        k = 9.81 / c.mortar_sag
        bdamp = 2.0 * c.mortar_zeta * np.sqrt(k)
        tb = JOINT
        self.beds = {}
        for bnd in (1, 2):
            lower = [i for i, d in enumerate(self.design) if d["course"] == bnd]
            upper = [i for i, d in enumerate(self.design) if d["course"] > bnd]
            names = []
            for j, i in enumerate(lower):
                nm = f"bed{bnd}_{j}"
                bb = wb.add_body(name=nm, mocap=True, pos=[0, 0, -1])
                bb.add_geom(name=nm, type=mujoco.mjtGeom.mjGEOM_BOX,
                            size=[self.design[i]["L"] / 2 + c.bed_overhang, W / 2 + c.bed_overhang, tb / 2],
                            contype=0, conaffinity=0, mass=0, rgba=[0.50, 0.48, 0.44, 1])
                names.append(nm)
            for j in range(len(lower) - 1):
                nm = f"bedj{bnd}_{j}"
                bb = wb.add_body(name=nm, mocap=True, pos=[0, 0, -1])
                bb.add_geom(name=nm, type=mujoco.mjtGeom.mjGEOM_BOX, size=[0.006, W / 2 + c.bed_overhang, tb / 2],
                            contype=0, conaffinity=0, mass=0, rgba=[0.50, 0.48, 0.44, 1])
                names.append(nm)
            for nm in names:
                for i in upper:
                    p = s.add_pair(geomname1=nm, geomname2=f"brick_{i}")
                    p.condim = 4
                    p.friction = [c.mortar_friction, c.mortar_friction, 0.005, 0.0001, 0.0001]
                    p.solref = [-k, -bdamp]
                    p.solimp = [0.95, 0.99, 0.001, 0.5, 2]
            self.beds[bnd] = dict(lower=lower, slabs=names[:len(lower)], joints=names[len(lower):])
        # cure welds (mortarB): brick -> world, activated at run time
        for i in range(self.n):
            e = s.add_equality(name=f"cure_{i}", type=mujoco.mjtEq.mjEQ_WELD, objtype=mujoco.mjtObj.mjOBJ_BODY,
                               name1=f"brick_{i}", active=False)
            e.solref = [0.004, 1]
        # gripper on the flange, TCP site at the pad centre (90 mm closure), wrist camera
        att = s.site("attachment_site")
        G.attach(att, s, c.gripper)
        w3 = s.body("wrist_3_link")
        qa = np.asarray(att.quat, float)
        Ra = _quat_rotmat(qa / np.linalg.norm(qa))          # the UR10e file writes this quat unnormalised (-1 1 0 0)
        pa = np.asarray(att.pos, float)
        w3.add_site(name="tcp", pos=pa + Ra @ [0, 0, self.cal["pad_center_depth"]], quat=att.quat, size=[0.004, 0, 0],
                    rgba=[0, 0, 1, 0.5], group=4)
        cam_p = pa + Ra @ [0.085, 0.0, 0.055]
        tgt = pa + Ra @ [0.0, 0.0, self.cal["pad_center_depth"] + 0.03]
        f = tgt - cam_p; f /= np.linalg.norm(f)
        x = Ra @ [0, 1, 0]
        x = x - f * (x @ f); x /= np.linalg.norm(x)
        y = np.cross(x, f)
        w3.add_camera(name="wrist", pos=cam_p, quat=_quat_from_R(np.stack([x, y, -f], axis=1)), fovy=80)
        return s

    def _index(self):
        m = self.model
        self.arm_qadr = np.array([m.joint(j).qposadr[0] for j in ARM_JOINTS])
        self.arm_dofadr = np.array([m.joint(j).dofadr[0] for j in ARM_JOINTS])
        self.arm_act = np.array([m.actuator(a).id for a in ARM_ACTS])
        self.grip_act = np.array([m.actuator(a).id for a in GRIP_ACTS])
        self.brick_qadr = [m.joint(f"brick_{i}_free").qposadr[0] for i in range(self.n)]
        self.brick_dofadr = [m.joint(f"brick_{i}_free").dofadr[0] for i in range(self.n)]
        self.brick_gid = [m.geom(f"brick_{i}").id for i in range(self.n)]
        self.brick_bid = [m.body(f"brick_{i}").id for i in range(self.n)]
        self.tcp_sid = m.site("tcp").id
        base = m.body("base").id
        self.robot_bodies = {b for b in range(m.nbody) if self._is_desc(b, base)}
        self.gripper_bodies = {b for b in self.robot_bodies if m.body(b).name.startswith(G.PREFIX)}
        self.pad_gids = {m.geom(G.PREFIX + p).id for p in G.PADS} | {
            m.geom(G.PREFIX + n).id for n in ("left_fingertip_collision", "right_fingertip_collision")}
        self.bed_mocap = {nm: m.body_mocapid[m.body(nm).id] for bnd in self.beds.values() for nm in bnd["slabs"] + bnd["joints"]}
        self.bed_gid = {nm: m.geom(nm).id for nm in self.bed_mocap}
        self.n_sub = int(round(self.cfg.ctrl_dt / m.opt.timestep))
        self.ft_force = m.sensor(G.PREFIX + "force_ee").adr[0]
        self.ft_torque = m.sensor(G.PREFIX + "torque_ee").adr[0]
        self.ft_site = m.site(G.PREFIX + "ft_frame").id

    def _is_desc(self, b, root):
        m = self.model
        while b != 0:
            if b == root:
                return True
            b = m.body_parentid[b]
        return False

    # ------------------------------------------------------------------ episode
    def supply_pose(self, i, rng=None):
        """Nominal (rng None) or scattered supply pose of brick i: (pos, yaw)."""
        c = self.cfg
        x, y = c.supply_slots[i]
        yaw = 0.0
        if rng is not None:
            x += rng.uniform(-c.scatter_pos, c.scatter_pos)
            y += rng.uniform(-c.scatter_pos, c.scatter_pos)
            yaw = np.deg2rad(rng.uniform(-c.scatter_yaw_deg, c.scatter_yaw_deg))
        return np.array([x, y, c.table_h + H / 2]), yaw

    def reset(self, seed: int, arm_q=None):
        m, d = self.model, self.data
        mujoco.mj_resetData(m, d)
        self.seed = int(seed)
        self.rng = np.random.default_rng(self.seed)
        self.supply = []
        for i in range(self.n):
            p, yaw = self.supply_pose(i, self.rng)
            self.supply.append((p.copy(), yaw))
            a = self.brick_qadr[i]
            d.qpos[a:a + 3] = p
            d.qpos[a + 3:a + 7] = yaw_quat(yaw)
        q = HOME_Q if arm_q is None else np.asarray(arm_q, float)
        d.qpos[self.arm_qadr] = q
        d.ctrl[self.arm_act] = q
        d.ctrl[self.grip_act] = G.grip_ctrl(False, self.cfg.gripper)
        self.last_action = np.r_[q, self.cfg.gripper.open_ctrl]
        for nm, mid in self.bed_mocap.items():
            d.mocap_pos[mid] = [0, 0, -1]
        # mj_resetData restores eq_active0: cure welds off, gripper coupling equalities on
        self.cured = np.zeros(self.n, bool)
        self.cure_t = np.full(self.n, -1)
        self.settle_count = np.zeros(self.n, int)
        self.bed_count = {1: np.zeros(self.n, int), 2: np.zeros(self.n, int)}
        self.bed_laid = {1: -1, 2: -1}
        self.t = 0
        mujoco.mj_forward(m, d)
        return self

    # ------------------------------------------------------------------ dynamics
    def step(self, arm_ctrl, grip_cmd):
        """One 20 Hz control step. arm_ctrl: 6 joint position targets (rad) to reach at the end of the step;
        grip_cmd: finger_1 command (0 open .. 0.7).

        Like an industrial arm controller (UR servoj interpolates at 500 Hz), the actuator targets are interpolated
        linearly from the previous action to this one over the 50 physics steps. Holding them constant made the very
        stiff UR10e servos (kp 5000) slam to their force limit for 1–2 ms at every 20 Hz update, which twisted the brick
        in the hand."""
        d = self.data
        new = np.r_[np.asarray(arm_ctrl, float), float(grip_cmd)]
        old = self.last_action
        for j in range(1, self.n_sub + 1):
            c = old + (new - old) * (j / self.n_sub)
            d.ctrl[self.arm_act] = c[:6]
            d.ctrl[self.grip_act] = [c[6], -c[6]]
            mujoco.mj_step(self.model, d)
        self.last_action = new
        self.t += 1
        self._update_cure()
        for bnd in (1, 2):
            if self.bed_laid[bnd] < 0:
                self._update_bed(bnd)

    # ------------------------------------------------------------------ state
    def brick_pose(self, i):
        a = self.brick_qadr[i]
        return self.data.qpos[a:a + 3].copy(), self.data.qpos[a + 3:a + 7].copy()

    def brick_poses(self):
        return np.array([self.data.qpos[a:a + 7].copy() for a in self.brick_qadr])

    def brick_vel(self, i):
        a = self.brick_dofadr[i]
        return self.data.qvel[a:a + 6].copy()

    def tcp(self):
        return self.data.site_xpos[self.tcp_sid].copy(), self.data.site_xmat[self.tcp_sid].reshape(3, 3).copy()

    def arm_q(self):
        return self.data.qpos[self.arm_qadr].copy()

    def closure(self):
        return G.closure(self.data)

    def wrist_ft(self):
        """Gripper force/torque sensor (robosuite ft_frame), world frame: (F N, T N·m). Not a policy input."""
        d = self.data
        R = d.site_xmat[self.ft_site].reshape(3, 3)
        return R @ d.sensordata[self.ft_force:self.ft_force + 3], R @ d.sensordata[self.ft_torque:self.ft_torque + 3]

    def _static(self, i):
        v = self.brick_vel(i)
        return np.linalg.norm(v[:3]) < 0.01 and np.linalg.norm(v[3:]) < 0.2

    def hand_clear(self, p):
        return np.linalg.norm(self.tcp()[0] - p) > self.cfg.hand_clear

    def in_slot(self, i, k=None):
        """Brick i sits in design slot k (default k = i) within the bed-laying tolerances (brick_sim brick_in_slot)."""
        c = self.cfg
        dsg = self.design[i if k is None else k]
        p, q = self.brick_pose(i)
        w, x, y, z = q
        yaw = np.arctan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z))
        tilt = np.degrees(np.arccos(np.clip(1 - 2 * (x * x + y * y), -1, 1)))
        if tilt > c.slot_tol_tilt_deg:
            return False
        if np.hypot(p[0] - dsg["x"], p[1] - dsg["y"]) > c.slot_tol_xy or abs(p[2] - dsg["z"]) > c.slot_tol_z:
            return False
        return np.degrees(abs((yaw - dsg["yaw"] + np.pi / 2) % np.pi - np.pi / 2)) <= c.slot_tol_yaw_deg

    def _update_cure(self):
        m, d, c = self.model, self.data, self.cfg
        xs = [s["x"] for s in self.design]
        x_lo, x_hi = min(xs) - 0.6 * L_FULL, max(xs) + 0.6 * L_FULL
        for i in range(self.n):
            if self.cured[i]:
                continue
            p, q = self.brick_pose(i)
            on_wall = abs(p[1] - WALL_Y) < 0.02 and x_lo < p[0] < x_hi and p[2] > 0.3 * H
            ok = on_wall and self._static(i) and self.hand_clear(p)
            self.settle_count[i] = self.settle_count[i] + 1 if ok else 0
            if self.settle_count[i] >= c.cure_settle_steps:
                eq = m.equality(f"cure_{i}").id
                qi = np.r_[q[0], -q[1:]]
                m.eq_data[eq, 0:3] = 0.0
                m.eq_data[eq, 3:6] = _quat_rotmat(qi) @ (-p)
                m.eq_data[eq, 6:10] = qi
                m.eq_data[eq, 10] = 1.0
                d.eq_active[eq] = 1
                self.cured[i] = True
                self.cure_t[i] = self.t

    def _update_bed(self, bnd):
        """Lay the mortar bed on course `bnd` once every brick of it is in its slot, static for 2 s and the hand is off."""
        c, d, m = self.cfg, self.data, self.model
        info = self.beds[bnd]
        cnt = self.bed_count[bnd]
        ready = True
        for i in info["lower"]:
            p, _ = self.brick_pose(i)
            ok = self.in_slot(i) and self._static(i) and self.hand_clear(p)
            cnt[i] = cnt[i] + 1 if ok else 0
            ready &= cnt[i] >= c.cure_settle_steps
        if not ready:
            return
        tb = JOINT
        tops = []
        for nm, i in zip(info["slabs"], info["lower"]):
            p, q = self.brick_pose(i)
            R = _quat_rotmat(q)
            ctr = p + R @ np.array([0.0, 0.0, H / 2 + tb / 2])
            d.mocap_pos[self.bed_mocap[nm]] = ctr
            d.mocap_quat[self.bed_mocap[nm]] = q
            tops.append((p, ctr, self.design[i]["L"]))
        for j, nm in enumerate(info["joints"]):
            (pl, cl, Ll), (pr, cr, Lr) = tops[j], tops[j + 1]
            gap = max((pr[0] - Lr / 2) - (pl[0] + Ll / 2), 0.0)
            m.geom_size[self.bed_gid[nm], 0] = gap / 2 + c.bed_overhang + 0.002
            d.mocap_pos[self.bed_mocap[nm]] = [((pl[0] + Ll / 2) + (pr[0] - Lr / 2)) / 2, (cl[1] + cr[1]) / 2, (cl[2] + cr[2]) / 2]
            d.mocap_quat[self.bed_mocap[nm]] = [1, 0, 0, 0]
        mujoco.mj_forward(m, d)
        self.bed_laid[bnd] = self.t

    # ------------------------------------------------------------------ contacts
    def contacts(self):
        """List of (name_a, name_b, dist) for contacts involving the robot/gripper and anything that is not robot/gripper."""
        m, d = self.model, self.data
        out = []
        for i in range(d.ncon):
            c = d.contact[i]
            b1, b2 = m.geom_bodyid[c.geom1], m.geom_bodyid[c.geom2]
            r1, r2 = b1 in self.robot_bodies, b2 in self.robot_bodies
            if r1 == r2:
                continue
            g_r, g_o = (c.geom1, c.geom2) if r1 else (c.geom2, c.geom1)
            out.append((m.geom(g_r).name or m.body(m.geom_bodyid[g_r]).name, m.geom(g_o).name or m.body(m.geom_bodyid[g_o]).name,
                        float(c.dist), int(g_r), int(g_o)))
        return out

    # ------------------------------------------------------------------ rendering
    def render(self, cam, w=None, h=None, depth=False):
        w = w or self.cfg.img
        h = h or self.cfg.img
        key = (w, h, depth)
        if key not in self.renderer:
            r = mujoco.Renderer(self.model, h, w)
            if depth:
                r.enable_depth_rendering()
            self.renderer[key] = r
        r = self.renderer[key]
        r.update_scene(self.data, camera=cam, scene_option=self.vopt)
        return r.render().copy()

    def close(self):
        for r in self.renderer.values():
            r.close()
        self.renderer = {}
