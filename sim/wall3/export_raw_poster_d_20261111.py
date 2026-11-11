"""포스터 d판(poster_ksarc_20261111d.py)을 다른 PC에서 다시 만들 수 있도록 필요한 결과 파일만 복사한다 (2026-11-11).

sim/outputs는 커밋하지 않는 규칙이라, 필요한 파일만 02_KSARC2026/원자료_포스터d_20261111/wall3/ 아래에 같은 상대 경로로 복사한다
(사용자 지시 11-11: "필요한 원자료들도 커밋"). 영상(mp4) · 로그는 넣지 않는다. 파일마다 sha256과 원래 경로를 MANIFEST.md에 적는다.
복사본을 읽으려면 환경변수 WALL3_OUT=<복사 폴더>/wall3 를 주고 primary_metrics_20261111 · poster_ksarc_20261111d를 돌린다.
대상 폴더가 이미 있으면 덮어쓰지 않는다.

실행: cd sim && PYTHONPATH=. venv/bin/python -m wall3.export_raw_poster_d_20261111
"""
import hashlib, shutil
from pathlib import Path

from wall3 import primary_metrics_20261111 as pm

SRC = pm.SIM / "outputs" / "wall3"
DST = pm.SIM.parent / "02_KSARC2026" / "원자료_포스터d_20261111"
EXTRA_CONDS = [
    "eval_lg_full2_20261111/act_all_held+k2+k7+k8",      # Full + G2c (SDCG): 결론의 G2c 한 줄
    "eval_lf_full_diffusion_20261110/diffusion_all_held+k2+k7",  # Diffusion + 같은 검측: 결론의 한 줄
]
FILES = ["eval_lf_20261110_compare.json", "eval_lf_g1fix_20261111_compare.json", "eval_lg_g2c_20261111_compare.json",
         "primary_metrics_20261111.json"]


def main():
    if DST.exists():
        raise SystemExit(f"{DST} 이미 있음: 덮어쓰지 않음")
    conds = [k for _, k, _ in pm.ROWS] + EXTRA_CONDS
    todo = [SRC / f for f in FILES]
    for k in conds:
        d, c = k.split("/", 1)
        parts = sorted((SRC / d).glob(f"{c}_part*/rollout.json"))
        assert parts, k
        todo += parts
        for meta in ("plan.json", "summary.json"):
            if (SRC / d / meta).exists() and SRC / d / meta not in todo:
                todo.append(SRC / d / meta)
    rows = []
    for p in todo:
        rel = p.relative_to(SRC)
        q = DST / "wall3" / rel
        q.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, q)
        h = hashlib.sha256(q.read_bytes()).hexdigest()
        assert h == hashlib.sha256(p.read_bytes()).hexdigest()
        rows.append((str(rel), q.stat().st_size, h[:16]))
    L = ["# 포스터 d판 원자료 (복사본)\n",
         "> 2026-11-11, `sim/wall3/export_raw_poster_d_20261111.py`가 `sim/outputs/wall3/`에서 그대로 복사했다(사용자 지시: 필요한 원자료 커밋).",
         "> 숫자는 모두 개발 배치 100벽(시작값 700300 ~ 700399) · 최종 평가 전. 영상 · 로그는 없다.",
         "> 다시 계산: `WALL3_OUT=<이 폴더>/wall3`를 주고 `wall3.primary_metrics_20261111` 또는 `wall3.poster_ksarc_20261111d`를 돌린다.\n",
         "| 파일 (wall3/ 아래) | 바이트 | sha256 앞 16 |", "|---|---|---|"]
    L += [f"| `{r}` | {s} | {h} |" for r, s, h in rows]
    L.append(f"\n합계 {len(rows)}개, {sum(s for _, s, _ in rows) / 1e6:.1f} MB.")
    (DST / "MANIFEST.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"복사 {len(rows)}개 · {sum(s for _, s, _ in rows) / 1e6:.1f} MB → {DST}")


if __name__ == "__main__":
    main()
