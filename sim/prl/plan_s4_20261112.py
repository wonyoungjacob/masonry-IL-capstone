"""4단계 계산 계획 (wall3.supervisor --plan prl.plan_s4_20261112): 시연 수집 → 변환 → 세팅마다 ACT 학습 → 장 단위 시험.

끝남은 결과 파일로만 판정한다(감독 규칙 그대로). 메모리 한도는 작업마다 systemd scope로 건다(지시 문서 4.2):
수집 · 변환 · 평가 MemoryMax 30G, 학습 36G, 모두 MemorySwapMax 2G · nice 10. GPU를 쓰는 단계는 차례로 하나씩 돈다.
단계는 코드가 준비되는 대로 뒤에 덧붙인다(감독을 다시 띄우면 상태 파일에서 이어 함).

실행: systemctl --user start prl-supervisor   (상태: sim/outputs/prl/supervisor_s4_20261112/STATUS.txt)
"""
O = "outputs/prl"
PY = "venv/bin/python"
SUP_NAME = "../prl/supervisor_s4_20261112"          # wall3.supervisor puts it under outputs/wall3/: this resolves to outputs/prl/
COLLECT = f"{O}/s4_collect_20261112"


def scoped(mem_gb, *cmd):
    return ["systemd-run", "--user", "--scope", "--quiet", "-p", f"MemoryMax={mem_gb}G", "-p", "MemorySwapMax=2G",
            "nice", "-n", "10", *cmd]


STAGES = [
    ("S4_collect", [dict(name="S4_collect", kind="rc", module="prl.collect", out=COLLECT,
                         cmd=scoped(30, PY, "-m", "prl.collect", "--seed0", "810000", "--n", "330", "--target-pass", "300",
                                    "--out", COLLECT, "--workers", "6"))]),
]
