"""Damped least-squares inverse kinematics for the 5-DoF SO-ARM100 on a MuJoCo site.

Task: site position (3) + site orientation (3, via rotation-vector error).  For this arm the
"gripper pointing down" constraint is 1-dimensional (all pitch axes are parallel), so the
6-row task is consistent for 5 joints; DLS handles the redundancy/inconsistency smoothly.
Reference: Buss (2004), "Introduction to inverse kinematics with Jacobian transpose,
pseudoinverse and damped least squares methods"; MuJoCo mj_jacSite.
"""
from __future__ import annotations

import mujoco
import numpy as np


def rot_from_down_yaw(yaw: float) -> np.ndarray:
    """Rotation matrix whose z-axis points to world -z and whose x-axis has the given yaw."""
    x = np.array([np.cos(yaw), np.sin(yaw), 0.0])
    z = np.array([0.0, 0.0, -1.0])
    y = np.cross(z, x)
    return np.stack([x, y, z], axis=1)


def rot_error(R: np.ndarray, Rt: np.ndarray) -> np.ndarray:
    return 0.5 * (np.cross(R[:, 0], Rt[:, 0]) + np.cross(R[:, 1], Rt[:, 1]) + np.cross(R[:, 2], Rt[:, 2]))


class DLSIK:
    def __init__(self, model: mujoco.MjModel, site_id: int, qidx, dofidx, damping=0.05, w_rot=0.4,
                 max_iters=60, tol_pos=5e-4, tol_rot=1e-2, max_dq=0.3):
        self.m = model
        self.d = mujoco.MjData(model)  # private scratch data
        self.site = site_id
        self.qidx = np.asarray(qidx)
        self.dofidx = np.asarray(dofidx)
        self.lo = model.jnt_range[[model.dof_jntid[i] for i in self.dofidx], 0]
        self.hi = model.jnt_range[[model.dof_jntid[i] for i in self.dofidx], 1]
        self.damping = damping
        self.w_rot = w_rot
        self.max_iters = max_iters
        self.tol_pos = tol_pos
        self.tol_rot = tol_rot
        self.max_dq = max_dq
        self.jacp = np.zeros((3, model.nv))
        self.jacr = np.zeros((3, model.nv))

    def solve(self, q0: np.ndarray, target_pos: np.ndarray, target_R: np.ndarray, full_qpos: np.ndarray | None = None):
        """Return (q, pos_err_norm, rot_err_norm). q0: current arm joint angles (len 5)."""
        m, d = self.m, self.d
        if full_qpos is not None:
            d.qpos[:] = full_qpos
        q = np.clip(np.array(q0, dtype=np.float64), self.lo, self.hi)
        lam2 = self.damping ** 2
        for _ in range(self.max_iters):
            d.qpos[self.qidx] = q
            mujoco.mj_kinematics(m, d)
            mujoco.mj_comPos(m, d)
            p = d.site_xpos[self.site]
            R = d.site_xmat[self.site].reshape(3, 3)
            e_p = target_pos - p
            e_r = rot_error(R, target_R)
            if np.linalg.norm(e_p) < self.tol_pos and np.linalg.norm(e_r) < self.tol_rot:
                break
            mujoco.mj_jacSite(m, d, self.jacp, self.jacr, self.site)
            J = np.vstack([self.jacp[:, self.dofidx], self.w_rot * self.jacr[:, self.dofidx]])
            e = np.r_[e_p, self.w_rot * e_r]
            dq = J.T @ np.linalg.solve(J @ J.T + lam2 * np.eye(6), e)
            n = np.linalg.norm(dq)
            if n > self.max_dq:
                dq *= self.max_dq / n
            q = np.clip(q + dq, self.lo, self.hi)
        d.qpos[self.qidx] = q
        mujoco.mj_kinematics(m, d)
        p = d.site_xpos[self.site]
        R = d.site_xmat[self.site].reshape(3, 3)
        return q, float(np.linalg.norm(target_pos - p)), float(np.linalg.norm(rot_error(R, target_R)))
