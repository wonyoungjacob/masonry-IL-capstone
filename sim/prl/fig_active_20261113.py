"""능동 카메라가 시선 규칙대로 따라가는 모습의 예시 그림: 벽돌 한 장(장 단위)을 대본으로 쌓는 동안의 영상을 순간별로 늘어놓는다.

행: 능동 카메라마다 [전체 영상(224로 줄임), 가운데 448 × 448을 잘라 224로 줄인 것], 손목 H0, 고정 G1(1차의 RE, 비교용).
열: 시작, 집기 접근 중간, 쥠, 운반 중간, 놓기 접근(내려가는 중), 놓고 후퇴한 뒤. 개발용 시작값만 쓴다.

실행: cd sim && MUJOCO_GL=egl PYTHONPATH=. venv/bin/python -m prl.fig_active_20261113 --settings prl/active_settings_20261113.json \\
        --setting A2 --seed 800230 --slot 7 --out <그림.jpg>
"""
import argparse, json
from pathlib import Path

import cv2
import numpy as np

from prl import config as C
from prl.active_cam import ActiveRig, PanTiltSpec, rig_specs
from prl.env import DryEnv, letterbox
from prl.expert import DryExpert
from prl.select_active import FOVEA_RAW

MOMENTS = [("시작", "to_supply", 0.0), ("집기 접근", "to_supply", 0.6), ("쥠", "grasp_close", 1.0), ("운반", "to_wall", 0.5),
           ("놓기 접근", "place_descend", 0.6), ("놓은 뒤", "retreat", 1.0)]
LABEL = ["start", "pick approach", "grasp", "transport", "place approach", "released"]


def fovea(raw):
    h, w = raw.shape[:2]
    c = FOVEA_RAW // 2
    return cv2.resize(raw[h // 2 - c:h // 2 + c, w // 2 - c:w // 2 + c], (C.POLICY_IMG, C.POLICY_IMG), interpolation=cv2.INTER_AREA)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--settings", required=True)
    ap.add_argument("--setting", required=True)
    ap.add_argument("--seed", type=int, default=800230)
    ap.add_argument("--slot", type=int, default=7)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = Path(a.out)
    if out.exists():
        raise SystemExit(f"{out} 이미 있음: 덮어쓰지 않음")
    C.check_seeds("dev", [a.seed])
    S = json.loads(Path(a.settings).read_text())
    spec = PanTiltSpec(**S["spec"]) if S.get("spec") else PanTiltSpec()
    cams = {cn: {"base": c["base"], "pan0": c["pan0"], "role": c["role"], "leave": c.get("leave", "release")}
            for cn, c in S["settings"][a.setting].items()}
    env = DryEnv(fixed_cams=C.final_cams(["G1"]), extra_cams=rig_specs(cams, spec))
    ex = DryExpert(env)
    rig = ActiveRig(env, cams, ex.q_ret, spec)
    frames = []                                                   # (phase, images) per step

    def shot():
        row = []
        for cn in cams:
            raw = env.render_raw(cn).copy()
            row += [letterbox(raw), fovea(raw)]
        row += [letterbox(env.render_raw("H0").copy()), letterbox(env.render_raw("G1").copy())]
        return row

    def on_step(env_, action, phase, k):
        rig.update(k)
        frames.append((phase, shot()))

    rig.reset(a.slot)
    r = ex.run_piece(a.seed, a.slot, on_step=on_step)
    env.close()
    phases = [p for p, _ in frames]
    cols = []
    for _, ph, frac in MOMENTS:
        idx = [i for i, p in enumerate(phases) if p == ph]
        cols.append(frames[idx[min(len(idx) - 1, int(round(frac * (len(idx) - 1))))]][1])
    names = [x for cn in cams for x in (f"{cn} ({cams[cn]['role']}) whole", f"{cn} centre crop")] + ["H0 wrist", "G1 fixed (RE)"]
    s = C.POLICY_IMG
    pad = 22
    sheet = np.full((len(names) * (s + pad) + pad, len(cols) * (s + 4) + 4, 3), 255, np.uint8)
    for ci, col in enumerate(cols):
        cv2.putText(sheet, LABEL[ci], (4 + ci * (s + 4), 15), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1, cv2.LINE_AA)
        for ri, img in enumerate(col):
            y0, x0 = pad + ri * (s + pad), 4 + ci * (s + 4)
            sheet[y0:y0 + s, x0:x0 + s] = img
            if ci == 0:
                cv2.putText(sheet, names[ri], (x0, y0 + s + 15), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 0, 0), 1, cv2.LINE_AA)
    cv2.imwrite(str(out), cv2.cvtColor(sheet, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 90])
    print("fail:", r.get("fail"), "steps:", len(frames), "->", out)


if __name__ == "__main__":
    main()
