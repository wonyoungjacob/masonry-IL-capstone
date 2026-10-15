"""robosuite Robotiq 2F-140 집게를 MjSpec에 붙이는 조립 코드 (실험설계 md v9 P1, 선택지 A).

모델 파일(sim/third_party/robosuite_gripper140/robotiq_gripper_140.xml)은 고치지 않는다. 조립할 때 허용된 세 가지만 적용한다.
  ① 집게 몸체끼리 접촉 끄기(contact exclude). 벽돌·벽·탁자와의 접촉은 그대로.
     MuJoCo Menagerie 2F-85(2f85.xml)도 base–driver, base–spring_link, coupler–follower 사이를 <exclude>로 끈다.
  ② 쥐는 힘: 손가락 구동기(position) 이득과 힘 한계. 실제 2F-140 쥐는 힘 사양(약 10 ~ 125 N) 안.
  ③ 집는 높이: 이 파일이 아니라 대본에서 TCP(패드 중심) 위치로 정한다.
그 밖에 robosuite가 이 파일을 합치는 base.xml의 설정(radian 단위, inertiagrouprange 0 0)을 맞춘다.
모양·치수·질량·관성·패드 마찰(기본 1.0)은 바꾸지 않는다.
"""
from dataclasses import dataclass, asdict
from pathlib import Path

import mujoco

SIM = Path(__file__).resolve().parents[1]
GRIPPER_XML = SIM / "third_party/robosuite_gripper140/robotiq_gripper_140.xml"
PREFIX = "g_"
ACTS = ("finger_1", "finger_2")                      # left: finger_joint (0 .. 0.7), right: right_outer_knuckle_joint (-0.7 .. 0)
PADS = ("left_fingerpad_collision", "right_fingerpad_collision")


@dataclass
class GripperConfig:
    exclude_self: bool = True        # ①
    kp: float = 20.0                 # ② position gain (robosuite 20)
    kv: float = 0.0                  #    velocity damping of the position servo (robosuite 0)
    torque_limit: float = 0.0        # ② |actuator torque| limit, N·m (0 = robosuite: no limit)
    close_ctrl: float = 0.7          # closing command (robosuite ctrlrange upper end)
    open_ctrl: float = 0.0
    eq_solref: tuple = ()            # 진단 전용(허용 조정 아님): 손가락 링크 구속(tendon 등식)의 solref. () = 받은 그대로(MuJoCo 기본 0.02 1)
    eq_solimp: tuple = ()            # 진단 전용: 같은 구속의 solimp. () = 받은 그대로(0.9 0.95 0.001)

    def to_dict(self):
        return asdict(self)


def attach(parent_site: "mujoco.MjsSite", spec: "mujoco.MjSpec", cfg: GripperConfig):
    """Attach the gripper to `parent_site` of `spec` (gripper +z = approach direction = site +z). Returns the frame."""
    gr = mujoco.MjSpec.from_file(str(GRIPPER_XML))
    gr.compiler.degree = False                     # robosuite base.xml: <compiler angle="radian">
    gr.compiler.inertiagrouprange = [0, 0]         # robosuite base.xml
    for a in gr.actuators:                         # ②
        a.gainprm[0] = cfg.kp
        a.biasprm[1] = -cfg.kp
        a.biasprm[2] = -cfg.kv
        if cfg.torque_limit > 0:
            a.forcelimited = mujoco.mjtLimited.mjLIMITED_TRUE
            a.forcerange = [-cfg.torque_limit, cfg.torque_limit]
    for e in gr.equalities:                        # 진단 전용 (기본값이면 아무것도 바꾸지 않음)
        if cfg.eq_solref:
            e.solref = list(cfg.eq_solref)
        if cfg.eq_solimp:
            e.solimp = (list(cfg.eq_solimp) + [0.5, 2.0])[:5]
    frame = parent_site.attach_body(gr.body("right_gripper"), PREFIX, "")
    if cfg.exclude_self:                           # ①
        names = [b.name for b in spec.bodies if b.name.startswith(PREFIX)]
        for i, a in enumerate(names):
            for b in names[i + 1:]:
                e = spec.add_exclude()
                e.bodyname1, e.bodyname2 = a, b
    return frame


def grip_ctrl(close: bool, cfg: GripperConfig):
    """Control values for (finger_1, finger_2)."""
    v = cfg.close_ctrl if close else cfg.open_ctrl
    return [v, -v]


def closure(d) -> float:
    """Gripper closure angle (rad) = mean of the two driven knuckle angles (left +, right −). Used by G1."""
    return 0.5 * (float(d.joint(PREFIX + "finger_joint").qpos[0]) - float(d.joint(PREFIX + "right_outer_knuckle_joint").qpos[0]))
