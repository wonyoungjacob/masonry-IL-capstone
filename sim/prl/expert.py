"""건식 환경용 대본: wall3.expert.WallExpert 그대로, 받침 높이만 모르타르 판 대신 아래 단 벽돌의 실제 윗면(참값, 시연 생성용).

벽 단위(run)와 장 단위(run_piece: 앞선 벽돌을 설계 위치에 미리 놓고 벽돌 k 한 장만) 둘 다 쓴다.
대본 설정은 main_v1과 같다(지시 문서 5.1: 그 밖은 main_v1과 같게).
"""
import numpy as np

from wall3.config import H
from wall3.expert import WallExpert, expert_config
from prl.env import DryEnv

EXPERT_VERSION = "main_v1"


class DryExpert(WallExpert):
    def __init__(self, env: DryEnv, cfg=None):
        super().__init__(env, cfg or expert_config(EXPERT_VERSION))

    def _support_top(self, k):
        """Height of what slot k rests on: the floor (course 1) or the real top of the lower-course bricks under its
        footprint (ground truth, demo only). Falls back to the design value when nothing is there."""
        env = self.env
        s = env.design[k]
        if s["course"] == 1:
            return 0.0
        tops = []
        for i, lo in enumerate(env.design):
            if lo["course"] != s["course"] - 1:
                continue
            p, _ = env.brick_pose(i)
            if abs(p[0] - s["x"]) < (lo["L"] + s["L"]) / 2 and abs(p[1] - s["y"]) < 0.045 and abs(p[2] - lo["z"]) < 0.02:
                tops.append(p[2] + H / 2)
        return float(max(tops)) if tops else s["z"] - H / 2

    def run_piece(self, seed, k, on_step=None, settle_s=2.0):
        """Brick-level trial: bricks 0 .. k−1 pre-placed at design, lay brick k only."""
        env = self.env
        env.reset_piece(seed, k, arm_q=self.q_ret)
        self.on_step = on_step
        self.q_cmd = self.q_ret.copy()
        self.grip_cmd = env.cfg.gripper.open_ctrl
        self.steps = 0
        self.fail = None
        self.touch = []
        self.brick_k = k
        r = self._brick(k)
        r["slot"] = k
        out = {"seed": int(seed), "bricks": [r]}
        if self.fail:
            out["fail"] = {"brick": k, "reason": self.fail, "t": int(env.t)}
        else:
            self.brick_k = -1
            self._hold(int(round(settle_s / self.dt)), 0.0, None, "settle")
        out["steps"] = int(env.t)
        return out
