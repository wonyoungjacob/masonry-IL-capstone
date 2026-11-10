"""실패 원인 제거 사다리 3단계 계획 (2026-11-10, 01_사기설/실험파이프라인_실패원인제거_20261110.md 5절). wall3.supervisor가 돌린다.

L2 판정(4절 규칙): G1r(k1) · G3w(k6)은 G0(k2) 위에서 구간이 0을 걸치고 겨냥한 원인이 줄지 않아 뺀다. 기준 = E3 + G0.
L3_eval   : 같은 100벽(700300 ~ 700399)에서 E3+G0 다시(같은 묶음 기준) · +G2w(k7, 다시 매긴 1위 자리 11 겨냥) (ACT)
L3_compare: 같은 묶음 E3+G0와 짝 비교 (L1 · L2 조건도 표에)
L3_trace  : E3+G0+G2w 추적 기록 → 원인 분류 → 순위 (G2w를 남길 경우의 다음 1위. 빼면 결과로 쓰지 않는다)
조건은 L3 결과를 보기 전에 정했다. 계산만 한다. 판정 · 보고 · 커밋은 결과를 읽고 한다.

실행: cd sim && venv/bin/python -m wall3.supervisor --plan wall3.plan_ladder3_20261110
"""
W = "outputs/wall3"
PY = "venv/bin/python"
SUP_NAME = "supervisor_ladder3_20261110"
CKPT = f"{W}/main_train_v2_20261022/act_s1000/checkpoints/last/pretrained_model"
L1 = f"{W}/eval_ladder1_20261110"
L2 = f"{W}/eval_ladder2_20261110"
L3 = f"{W}/eval_ladder3_20261110"
T3 = f"{W}/diag_trace_ladder3_k2k7_20261110"
CONDS = ["all_held+k2", "all_held+k2+k7"]


def seeds(i, n=100, chunks=5, s0=700300):
    k = n // chunks
    return list(range(s0 + i * k, s0 + (i + 1) * k))


STAGES = [
    ("L3_eval", [dict(name="L3_eval", kind="summary", module="wall3.eval_gates", out=L3,
                      cmd=[PY, "-m", "wall3.eval_gates", "--out", L3, "--train-dir", f"{W}/main_train_v2_20261022",
                           "--policies", "act", "--conditions", *CONDS, "--chunks", "5", "--parallel", "8",
                           "--env-version", "main_v1_eval"])]),
    ("L3_compare", [dict(name="L3_compare", kind="rc", module="wall3.compare_ladder", out=f"{L3}_compare.json",
                         cmd=[PY, "-m", "wall3.compare_ladder", "--evals", L3, L2, L1,
                              "--base", "eval_ladder3_20261110/act_all_held+k2", "--out", f"{L3}_compare.json"],
                         log=f"{L3}_compare.txt")]),
    ("L3_trace", [dict(name=f"L3_trace_part{i}", kind="rc", module="wall3.diag_trace", out=f"{T3}/part{i}",
                       cmd=[PY, "-m", "wall3.diag_trace", "--ckpt", CKPT, "--env-version", "main_v1_eval",
                            "--seeds", *map(str, seeds(i)), "--out", f"{T3}/part{i}",
                            "--gate-pose-source", "camera", "--gate-target", "held_grasp", "--gate-fix", "k2", "k7",
                            "--compare", f"{L3}/act_all_held+k2+k7_part{i}/rollout.json"]) for i in range(5)]),
    ("L3_causes", [dict(name="L3_causes", kind="rc", module="wall3.diag_trace_causes", out=f"{T3}/causes.json",
                        cmd=[PY, "-m", "wall3.diag_trace_causes", T3, "--aim-max-mm", "50", "--perch-mm", "20",
                             "--out", f"{T3}/causes.json"], log=f"{T3}/causes.txt")]),
    ("L3_rank", [dict(name="L3_rank", kind="rc", module="wall3.rank_fail_causes", out=f"{T3}/rank.json",
                      cmd=[PY, "-m", "wall3.rank_fail_causes", "--trace", T3, "--out", f"{T3}/rank.json"],
                      log=f"{T3}/rank.txt")]),
]
