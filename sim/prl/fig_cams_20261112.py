import json, sys, numpy as np, cv2
from prl.geom_metrics import Replay, load_traj
from prl.run_script import PHASES
from prl import config as C
ev = sys.argv[1]
S = json.load(open("prl/settings_20261112.json"))
extra = {n: S["camera_poses"][n] for n in ("WA2", "G1")}
cams = [n for n in list(C.FIXED_CAMS) + list(C.WRIST_CAMS) if n != "WA2"]
rp = Replay(cams, extra)
env = rp.env
z = load_traj("outputs/prl/s2_traj_20261112", 800000)
k = 7
order = ["SA1", "SA2", "SB1", "SB2", "SC1", "SD1", "WA1", "WA2", "WB1", "WC1", "WC2", "WD1", "WE1", "G1", "H0", "H1", "H2"]
for tag, ph, frac, title in (("집기접근", "grasp_descend", 0.0, "pick approach (brick 8, 0.10 m above the grasp)"),
                             ("놓기접근", "place_descend", 0.5, "place approach (brick 8, half way down)")):
    idx = np.nonzero((z["brick"] == k) & (z["phase"] == PHASES.index(ph)))[0]
    rp.set_qpos(z["qpos"][idx[int(frac * (len(idx) - 1))]])
    tiles = []
    for n in order:
        raw = env.render_raw(n)
        t = cv2.resize(raw, (400, 300), interpolation=cv2.INTER_AREA)
        cv2.rectangle(t, (0, 0), (150, 26), (0, 0, 0), -1)
        used = [s for s, r in S["settings"].items() if n in r["cams"]]
        cv2.putText(t, n + (" *" if used else ""), (6, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 0), 2)
        tiles.append(t)
    while len(tiles) % 6:
        tiles.append(np.full((300, 400, 3), 255, np.uint8))
    img = np.vstack([np.hstack(tiles[i:i + 6]) for i in range(0, len(tiles), 6)])
    cv2.imwrite(f"{ev}/2단계_카메라후보_{tag}.jpg", cv2.cvtColor(img, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 82])
    print(tag, img.shape)
rp.close()
