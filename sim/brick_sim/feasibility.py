"""Static feasibility of the expert's grasp for a supply layout (2026-09-23 first-grasp diagnosis).

Two geometric checks explained 64 of the 70 first-grasp failures of data/v3_2p1_joint_image_clean with 2 false
positives among 384 successes (sim/outputs/diag_first_grasp/):
  self : at the IK solution of the grasp pose the arm penetrates itself (fixed jaw into the Rotation_Pitch link
         near the base; the DLS IK does not know about collisions, physics stops the hand ~13 mm above the brick)
  nbr  : while the jaw closes at the grasp pose some arm body (the 70 mm moving-jaw swing) penetrates a
         neighbouring brick, which shoves the hand ~20 mm off the target
Both are evaluated purely kinematically (mj_forward, no dynamics) with every brick at its initial pose.
"""
from __future__ import annotations

import mujoco
import numpy as np

from .ik import DLSIK, rot_from_down_yaw
from .scene import JAW_OPEN, JAW_CLOSED

ARM_BODIES = ("Base", "Rotation_Pitch", "Upper_Arm", "Lower_Arm", "Wrist_Pitch_Roll", "Fixed_Jaw", "Moving_Jaw")
SELF_TOL = 0.0005    # m: self-penetration above this failed every time in the audit (35/35), never on a success
NBR_TOL = 0.002      # m: neighbour penetration during the jaw sweep (30 fails / 2 successes above this)
JAW_SWEEP = 12


def grasp_feasibility(env, i: int, ik: DLSIK | None = None, self_tol=SELF_TOL, nbr_tol=NBR_TOL) -> dict:
    """Static check of the expert grasp on brick i with all other bricks where they are now.

    Returns {"ok", "self_pen_m", "nbr_pen_m", "ik_pos_err_m", "worst"}; the simulator state is restored.
    """
    from .expert import grasp_pose   # expert imports scene; keep the cycle out of module import time
    m, d = env.model, env.data
    ik = ik or DLSIK(m, env.tcp_site, env.arm_qidx, env.arm_dofidx)
    qpos0, qvel0 = d.qpos.copy(), d.qvel.copy()
    (gx, gy, gz), yaw, _ = grasp_pose(env, i)
    q, ep, _ = ik.solve(qpos0[env.arm_qidx], np.array([gx, gy, gz]), rot_from_down_yaw(yaw), qpos0.copy())
    arm_ids = {m.body(n).id for n in ARM_BODIES}
    brick_ids = {bid: k for k, bid in enumerate(env.brick_bids)}
    self_pen, nbr_pen, worst = 0.0, 0.0, ""
    for jaw in np.linspace(JAW_OPEN, JAW_CLOSED, JAW_SWEEP):
        d.qpos[:] = qpos0
        d.qpos[env.arm_qidx] = q
        d.qpos[env.jaw_qidx] = jaw
        mujoco.mj_forward(m, d)
        for c in d.contact[: d.ncon]:
            b1, b2 = m.geom_bodyid[c.geom1], m.geom_bodyid[c.geom2]
            if b1 in arm_ids and b2 in arm_ids:
                if jaw == JAW_OPEN and c.dist < -self_pen:   # self-collision is judged with the jaw open, as planned
                    self_pen, worst = -c.dist, f"self:{m.body(b1).name}-{m.body(b2).name}"
            elif (b1 in arm_ids and b2 in brick_ids and brick_ids[b2] != i) or \
                 (b2 in arm_ids and b1 in brick_ids and brick_ids[b1] != i):
                if c.dist < -nbr_pen:
                    nbr_pen, worst = -c.dist, f"nbr:{m.body(b1).name}-{m.body(b2).name}@jaw{jaw:.2f}"
    d.qpos[:] = qpos0; d.qvel[:] = qvel0
    mujoco.mj_forward(m, d)
    return {"ok": bool(self_pen <= self_tol and nbr_pen <= nbr_tol), "self_pen_m": float(self_pen),
            "nbr_pen_m": float(nbr_pen), "ik_pos_err_m": float(ep), "worst": worst}


def layout_feasibility(env, **kw) -> list[dict]:
    """grasp_feasibility for every brick, each judged with all the others still lying in the supply area
    (conservative: by the time a later brick is picked some neighbours are already on the wall)."""
    ik = DLSIK(env.model, env.tcp_site, env.arm_qidx, env.arm_dofidx)
    return [grasp_feasibility(env, i, ik, **kw) for i in range(env.n_bricks)]
