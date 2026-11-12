"""3 · 4단계 계산 계획 (wall3.supervisor --plan prl.plan_s4_20261112):
시연 수집 → 변환(6묶음) + 측정 오차(3단계) → 합치기 · 검사 → 세팅별 데이터셋 → VRAM 시험 → 세팅마다 [ACT 학습 → 장 단위 시험].

끝남은 결과 파일로만 판정한다(감독 규칙 그대로). 메모리 한도는 작업마다 systemd scope로 건다(지시 문서 4.2):
수집 · 평가 30G, 변환 묶음 10G, 학습 36G(train_act가 lerobot-train마다 따로 건다), 모두 MemorySwapMax 2G · nice 10.
GPU를 쓰는 학습 · 시험은 단계를 나눠 하나씩 돈다. 변환(CPU)과 측정(GPU는 영상 그리기만)은 같은 단계에서 함께 돈다.

실행: systemctl --user start prl-supervisor   (상태: sim/outputs/prl/supervisor_s4_20261112/STATUS.txt)
"""
import json
from pathlib import Path

SIM = Path(__file__).resolve().parents[1]
O = "outputs/prl"
D = "data"
PY = "venv/bin/python"
SUP_NAME = "../prl/supervisor_s4_20261112"          # wall3.supervisor puts it under outputs/wall3/: this resolves to outputs/prl/
COLLECT = f"{O}/s4_collect_20261112"
MASTER = f"{D}/prl_s4_master_20261112"
N_PARTS = 6
SETTINGS = json.loads((SIM / "prl" / "settings_20261112.json").read_text())["settings"]
ORDER = ["RB", "RD", "RC", "RE", "RA", "R0"]         # 기하 조건에 가까운 세팅부터(결과가 먼저 필요한 순), 6개 모두 돈다
PROBE = f"{O}/s4_probe_20261112"
# 2026-11-12 23:25 (변환 1차 중단 뒤): 인코더 스레드 1(카메라 9개가 이미 나란히 돈다), 영상 파일 한도 10 MB.
# 에피소드를 붙일 때마다 그 파일 전체를 다시 쓰므로 한도 50 MB에서는 벽 하나에 수 GB를 다시 썼다(HDD).
# 합치기도 같은 한도라서 대부분 복사만 한다. 합친 뒤 검사는 영상 비교 벽을 30개로 늘렸다.
CONV_OPTS = ["--threads", "1", "--video-mb", "10"]


def scoped(mem_gb, *cmd):
    return ["systemd-run", "--user", "--scope", "--quiet", "-p", f"MemoryMax={mem_gb}G", "-p", "MemorySwapMax=2G",
            "nice", "-n", "10", *cmd]


def venv(*cmd):
    """Through the venv's activate script (library path for the video libraries); the python process keeps module / out in argv."""
    return ["bash", "-c", 'source venv/bin/activate && exec "$@"', "venv", "python", *cmd]


def part(i):
    return f"{D}/prl_s4_master_part{i}_20261112"


def ds(s):
    return f"{D}/prl_s4_{s}_20261112"


def train_out(s, seed=1000):
    return f"{O}/s4_train_{s}_s{seed}_20261112"


def eval_out(s, seed=1000):
    return f"{O}/s4_eval_{s}_s{seed}_20261112"


def train_cmd(s, seed=1000):
    def cmd(st):
        b = json.loads((SIM / PROBE / "summary.json").read_text())["batch_ok"]
        return [PY, "-m", "prl.train_act", "--dataset", ds(s), "--out", train_out(s, seed), "--seed", str(seed), "--steps", "30000",
                "--chunk", "20000", "--batch", str(b), "--workers", "4", "--mem-gb", "36"]
    return cmd


STAGES = [
    ("S4_collect", [dict(name="S4_collect", kind="rc", module="prl.collect", out=COLLECT,
                         cmd=scoped(30, PY, "-m", "prl.collect", "--seed0", "810000", "--n", "330", "--target-pass", "300",
                                    "--out", COLLECT, "--workers", "6"))]),
    ("S4_convert_S3_measure",
     [dict(name=f"S4_conv_p{i}", kind="rc", module="prl.to_lerobot", out=part(i),
           cmd=scoped(10, *venv("-m", "prl.to_lerobot", "--raw", COLLECT, "--root", part(i), "--max-walls", "300",
                                "--part", str(i), str(N_PARTS), "--no-verify", *CONV_OPTS))) for i in range(N_PARTS)]
     + [dict(name="S3_measure", kind="summary", module="prl.measure", out=f"{O}/s3_measure_20261112",
             cmd=scoped(30, PY, "-m", "prl.measure", "--zone", "select", "--seed0", "820000", "--n", "100",
                        "--out", f"{O}/s3_measure_20261112", "--workers", "8"))]),
    ("S4_merge", [dict(name="S4_merge", kind="rc", module="prl.to_lerobot", out=MASTER,
                       cmd=scoped(16, *venv("-m", "prl.to_lerobot", "--merge", *[part(i) for i in range(N_PARTS)], "--root", MASTER,
                                            "--video-mb", "10", "--img-walls", "30")))]),
    ("S4_subsets", [dict(name=f"S4_subset_{s}", kind="rc", module="prl.to_lerobot", out=ds(s),
                         cmd=scoped(10, *venv("-m", "prl.to_lerobot", "--subset", MASTER, "--cams", *SETTINGS[s]["cams"], "--root", ds(s))))
                    for s in ORDER]),
    ("S4_probe", [dict(name="S4_probe", kind="summary", module="prl.train_act", out=PROBE,
                       cmd=[PY, "-m", "prl.train_act", "--dataset", ds("RB"), "--out", PROBE, "--probe", "200", "--workers", "4", "--mem-gb", "36"])]),
]
for _s in ORDER:
    STAGES.append((f"S4_train_{_s}", [dict(name=f"S4_train_{_s}", kind="summary", module="prl.train_act", out=train_out(_s), cmd=train_cmd(_s))]))
    STAGES.append((f"S4_eval_{_s}", [dict(name=f"S4_eval_{_s}", kind="summary", module="prl.eval_piece", out=eval_out(_s),
                                          cmd=scoped(30, PY, "-m", "prl.eval_piece", "--ckpt",
                                                     f"{train_out(_s)}/run/checkpoints/last/pretrained_model", "--zone", "select",
                                                     "--seed0", "820000", "--n", "50", "--out", eval_out(_s)))]))

# 2026-11-13 03:30: 진단 1개(결과 아님)를 RD 학습과 RD 시험 사이에 넣었다. RB의 장당 성공률이 낮게 나와(8.6 %), 장 단위 시험이 만드는
# 관측이 학습 데이터의 관측과 같은지 학습 장면(810000)에서 확인한다(prl.diag_obs). GPU를 쓰므로 다른 작업과 겹치지 않게 단계로 넣었고,
# 실패해도 본 계산을 막지 않게 종료 코드는 항상 0이다(결과는 summary.json이 있는지로 본다).
DIAG = f"{O}/s4_diag_obs_RB_20261112"
STAGES.insert([n for n, _ in STAGES].index("S4_train_RD") + 1,
              ("S4_diag_obs_RB", [dict(name="S4_diag_obs_RB", kind="rc", module="prl.diag_obs", out=DIAG,
                                       cmd=scoped(30, "bash", "-c", 'venv/bin/python -m prl.diag_obs "$@"; exit 0', "diag",
                                                  "--ckpt", f"{train_out('RB')}/run/checkpoints/last/pretrained_model",
                                                  "--dataset", ds("RB"), "--out", DIAG))]))
