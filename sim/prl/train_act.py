"""ACT 학습 하나를 자원 한도 안에서 끝까지 돌린다 (지시 문서 4.2). 끝나면 <out>/summary.json을 쓴다(감독이 이것으로 끝남을 판정).

- 학습은 lerobot-train(본 학습과 같은 기본 정책 설정, 배치 32). --chunk 스텝마다 저장하고 프로세스를 끝낸 뒤 그 체크포인트에서 이어 한다
  (데이터 로딩 작업자의 메모리 누적 방지).
- lerobot-train은 매번 별도 systemd scope: MemoryMax · MemorySwapMax · nice 10. 한도를 넘으면 그 학습만 죽는다.
- 감시: 로그가 10분 조용하면 끝내고 이어 함. 5분마다 사용 가능 RAM을 기록, 6 GB 아래로 10분 넘게 머물면 끝내고 이어 함.
  죽은 학습은 마지막 체크포인트에서 최대 3번 이어 한다. VRAM은 30초마다 재서 최고값을 남긴다.
- --probe N: 본 학습 전에 같은 설정으로 N스텝만 돌려 최고 VRAM · RAM과 속도를 잰다(저장 없음). 26 GB를 넘으면 배치를 반으로 줄여 다시 잰다.

실행: cd sim && PYTHONPATH=. venv/bin/python -m prl.train_act --dataset data/<이름> --out outputs/prl/<이름> --seed 1000 --steps 30000
"""
import argparse, json, os, re, shutil, signal, subprocess, time
from pathlib import Path

SIM = Path(__file__).resolve().parents[1]
STALL_S = 600
LOW_RAM_GB, LOW_RAM_S = 6.0, 600


def mem_available_gb():
    for line in open("/proc/meminfo"):
        if line.startswith("MemAvailable"):
            return int(line.split()[1]) / 1048576
    return float("nan")


def gpu_used_mib():
    try:
        return int(subprocess.check_output(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"], text=True).split()[0])
    except Exception:                                     # noqa: BLE001
        return -1


def scope_peak_gb(unit):
    try:
        out = subprocess.check_output(["systemctl", "--user", "show", unit, "-p", "MemoryPeak"], text=True).strip().split("=")[1]
        return int(out) / 2 ** 30
    except Exception:                                     # noqa: BLE001
        return None


def last_step(log):
    try:
        m = re.findall(r"step:(\d+(?:\.\d+)?)([KM]?)", Path(log).read_text(errors="replace")[-20000:])
    except OSError:
        return 0
    if not m:
        return 0
    v, suf = m[-1]
    return int(float(v) * {"": 1, "K": 1000, "M": 1000000}[suf])


def run_chunk(args_list, log, unit, a, state):
    """One lerobot-train process in its own scope. Returns (rc, reason)."""
    # through the venv's activate script: it sets the library path torchcodec needs
    cmd = ["systemd-run", "--user", "--scope", "--quiet", f"--unit={unit}", "-p", f"MemoryMax={a.mem_gb}G", "-p", "MemorySwapMax=2G",
           "nice", "-n", "10", "bash", "-c", 'source venv/bin/activate && exec lerobot-train "$@"', "lerobot-train", *args_list]
    env = dict(os.environ, PYTHONPATH=".", MUJOCO_GL="egl")
    with open(log, "a") as f:
        f.write(f"\n==== {time.strftime('%F %T')} {' '.join(cmd)}\n")
        f.flush()
        p = subprocess.Popen(cmd, cwd=SIM, env=env, stdout=f, stderr=subprocess.STDOUT, start_new_session=True)
    t_low, t_mem, reason = None, 0.0, None
    while p.poll() is None:
        time.sleep(30)
        state["vram_peak_mib"] = max(state["vram_peak_mib"], gpu_used_mib())
        pk = scope_peak_gb(unit + ".scope")
        if pk:
            state["ram_peak_gb"] = max(state["ram_peak_gb"], pk)
        avail = mem_available_gb()
        if time.time() - t_mem >= 300:
            t_mem = time.time()
            state["mem_log"].append([time.strftime("%F %T"), round(avail, 1), last_step(log)])
        t_low = (t_low or time.time()) if avail < LOW_RAM_GB else None
        age = time.time() - os.stat(log).st_mtime
        if t_low and time.time() - t_low > LOW_RAM_S:
            reason = f"low_ram {avail:.1f} GB for {LOW_RAM_S} s"
        elif age > STALL_S:
            reason = f"stalled {age:.0f} s"
        if reason:
            subprocess.run(["systemctl", "--user", "kill", "--signal=KILL", unit + ".scope"], capture_output=True)
            try:
                os.killpg(p.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            p.wait()
            break
    state["vram_peak_mib"] = max(state["vram_peak_mib"], gpu_used_mib() if p.poll() is None else state["vram_peak_mib"])
    return p.returncode, reason


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--seed", type=int, default=1000)
    ap.add_argument("--steps", type=int, default=30000)
    ap.add_argument("--chunk", type=int, default=20000)
    ap.add_argument("--batch", type=int, default=32)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--mem-gb", type=int, default=36)
    ap.add_argument("--backend", default="torchcodec")
    ap.add_argument("--probe", type=int, default=0, help="only N steps to measure peak VRAM / RAM / speed (no checkpoints)")
    ap.add_argument("--vram-limit-gb", type=float, default=26.0)
    ap.add_argument("--max-resume", type=int, default=3)
    a = ap.parse_args()
    out = SIM / a.out
    ds = Path(a.dataset)
    if out.exists() and (out / "summary.json").exists():
        raise SystemExit(f"{out} 이미 끝남: 덮어쓰지 않음")
    out.mkdir(parents=True, exist_ok=True)
    log = out / "train.log"
    run = out / "run"
    tag = re.sub(r"[^A-Za-z0-9]", "-", out.name)[-40:]
    state = {"vram_peak_mib": 0, "ram_peak_gb": 0.0, "mem_log": [], "chunks": [], "deaths": [], "vram_idle_mib": gpu_used_mib()}
    base = [f"--dataset.repo_id=local/{ds.name}", f"--dataset.root={a.dataset}", f"--dataset.video_backend={a.backend}",
            "--policy.type=act", "--policy.device=cuda", "--policy.push_to_hub=false", f"--seed={a.seed}",
            f"--num_workers={a.workers}", "--log_freq=200", "--wandb.enable=false", f"--job_name=prl_{out.name}"]
    t0 = time.time()

    if a.probe:
        batch = a.batch
        probes = []
        while True:
            pdir = out / f"probe_b{batch}"
            if pdir.exists():
                shutil.rmtree(pdir)
            state["vram_peak_mib"], state["ram_peak_gb"] = 0, 0.0
            t1 = time.time()
            rc, reason = run_chunk(base + [f"--steps={a.probe}", f"--batch_size={batch}", "--save_checkpoint=false", "--log_freq=50",
                                           f"--output_dir={pdir}"], log, f"prl-probe-{tag}-b{batch}-{int(t1)}", a, state)
            txt = log.read_text(errors="replace")
            ok = rc == 0 and "End of training" in txt[-5000:]
            peak_gb = state["vram_peak_mib"] / 1024
            probes.append({"batch": batch, "rc": rc, "reason": reason, "ok": ok, "vram_peak_gb": peak_gb, "ram_peak_gb": state["ram_peak_gb"],
                           "wall_s": time.time() - t1, "steps": a.probe})
            if ok and peak_gb <= a.vram_limit_gb:
                break
            if batch <= 4:
                break
            batch //= 2
        (out / "summary.json").write_text(json.dumps({"probe": probes, "batch_ok": batch if probes[-1]["ok"] else None,
                                                      "vram_idle_mib": state["vram_idle_mib"], "elapsed_s": time.time() - t0}, indent=1))
        print(json.dumps(probes, indent=1))
        if not probes[-1]["ok"]:
            raise SystemExit(1)
        return

    def ckpt_step():
        f = run / "checkpoints" / "last" / "training_state" / "training_step.json"
        try:
            return json.loads(f.read_text())["step"]
        except (OSError, ValueError, KeyError):
            return 0

    resumes = 0
    while True:
        done = ckpt_step()
        if done >= a.steps:
            break
        target = min(a.steps, (done // a.chunk + 1) * a.chunk)
        if done == 0:
            if run.exists():                                   # a start that died before its first checkpoint: kept aside
                run.rename(out / f"run_STOPPED_{len(state['deaths'])}_{int(time.time())}")
            args_list = base + [f"--steps={target}", f"--batch_size={a.batch}", f"--save_freq={a.chunk}", f"--output_dir={run}"]
        else:
            args_list = [f"--config_path={run / 'checkpoints' / 'last' / 'pretrained_model' / 'train_config.json'}", "--resume=true",
                         f"--steps={target}", f"--num_workers={a.workers}", f"--dataset.video_backend={a.backend}"]
        t1 = time.time()
        rc, reason = run_chunk(args_list, log, f"prl-tr-{tag}-{int(t1)}", a, state)
        now = ckpt_step()
        state["chunks"].append({"from": done, "to": target, "reached": now, "rc": rc, "reason": reason, "wall_s": time.time() - t1,
                                "started": time.strftime("%F %T", time.localtime(t1))})
        (out / "progress.json").write_text(json.dumps(state, indent=1))
        if now >= target:
            continue
        state["deaths"].append({"at_step": last_step(log), "rc": rc, "reason": reason or "process ended early", "time": time.strftime("%F %T")})
        resumes += 1
        if resumes > a.max_resume:
            (out / "FAILED.json").write_text(json.dumps(state, indent=1))
            raise SystemExit(f"학습이 {a.max_resume}번 이어 해도 끝나지 않음: {state['deaths'][-1]}")
        time.sleep(20)
    txt = log.read_text(errors="replace")
    losses = [float(x) for x in re.findall(r"loss:([0-9.eE+-]+)", txt)]
    ck = run / "checkpoints" / "last" / "pretrained_model"
    cfg = json.loads((ck / "config.json").read_text())
    summ = {"dataset": a.dataset, "seed": a.seed, "steps": a.steps, "batch": a.batch, "chunk": a.chunk, "workers": a.workers,
            "checkpoint": str(ck.relative_to(SIM)), "input_features": {k: v["shape"] for k, v in cfg["input_features"].items()},
            "policy_type": cfg["type"], "chunk_size": cfg.get("chunk_size"), "n_action_steps": cfg.get("n_action_steps"),
            "loss_first": losses[0] if losses else None, "loss_last": losses[-1] if losses else None, "loss_nan": any(x != x for x in losses),
            "vram_peak_gb": state["vram_peak_mib"] / 1024, "vram_idle_mib": state["vram_idle_mib"], "ram_peak_gb": state["ram_peak_gb"],
            "chunks": state["chunks"], "deaths": state["deaths"], "mem_log": state["mem_log"], "elapsed_s": time.time() - t0,
            "mem_max_gb": a.mem_gb, "finished": time.strftime("%F %T")}
    (out / "summary.json").write_text(json.dumps(summ, indent=1))
    print(json.dumps({k: v for k, v in summ.items() if k not in ("mem_log", "chunks")}, indent=1))


if __name__ == "__main__":
    main()
